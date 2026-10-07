"""Transactional MOVIS domain service. No inventory updates during inference."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import database


class Error(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc).isoformat()


MAX_QUANTITY = 2147483647
SESSION_IDLE_SECONDS = 30 * 60


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex()
    return 'pbkdf2_sha256$600000$' + salt + '$' + digest


def password_matches(password, stored):
    if not isinstance(password, str) or len(password)>500:return False
    try:
        if stored.startswith('pbkdf2_sha256$'):
            _, rounds, salt, expected = stored.split('$')
            rounds=int(rounds)
            if rounds<200000 or rounds>2000000:return False
        else:
            salt, expected = stored.split(':');rounds=200000
        digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),rounds).hex()
        return hmac.compare_digest(expected,digest)
    except (ValueError,TypeError):return False


def integer(value, minimum=0):
    if type(value) is not int or not minimum <= value <= MAX_QUANTITY:
        raise Error(f'Expected a whole number between {minimum} and {MAX_QUANTITY}')
    return value


def required(data, key):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise Error(f'{key} is required (maximum 500 characters)')
    return value.strip()


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class Service:
    def __init__(self, db, mode='demo', weights=None):
        self.db, self.mode = str(db), mode
        self.model = None
        self.model_lock = threading.Lock()
        if mode == 'yolo':
            if not weights or not Path(weights).is_file():
                raise Error('YOLO mode requires an existing warehouse-trained weights file')
            from ultralytics import YOLO
            self.model = YOLO(weights)
        elif mode != 'demo':
            raise Error('Mode must be demo or yolo')
        database.initialize(self.db)
        if weights and Path(weights).is_file():
            self.weights_digest = hashlib.sha256(Path(weights).read_bytes()).hexdigest()
        from rice import RiceWorkflow
        self.rice = RiceWorkflow(self)

    @contextmanager
    def connection(self):
        with database.connection(self.db) as con:
            yield con

    def bootstrap(self, username, password, demo=False):
        if not isinstance(password,str) or not 12<=len(password)<=128:
            raise Error('Use a password between 12 and 128 characters')
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            if con.execute('SELECT count(*) FROM users').fetchone()[0]:
                raise Error('Database already initialized')
            con.execute('INSERT INTO users(username,password,role) VALUES(?,?,?)', (username, password_hash(password), 'admin'))
            if demo:
                con.execute("INSERT INTO locations(name) VALUES('DEMO shelf A')")
                for sku, name, cls, qty in [('DEMO-001', 'Demo carton', 'demo_carton', 10), ('DEMO-002', 'Demo bottle', 'demo_bottle', 8)]:
                    cur = con.execute('INSERT INTO items(sku,name,model_class) VALUES(?,?,?)', (sku, name, cls))
                    con.execute('INSERT INTO stock VALUES(?,?,?,0)', (cur.lastrowid, 1, qty))

    def login(self, data):
        username=data.get('username')
        if not isinstance(username,str) or not username.strip() or len(username)>100:
            raise Error('Invalid username or password',401)
        self.throttle('login:'+hashlib.sha256(username.strip().casefold().encode()).hexdigest(),10)
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            user = con.execute('SELECT * FROM users WHERE username=?', (data.get('username'),)).fetchone()
            password = data.get('password', '')
            matches=password_matches(password,user['password'] if user else 'pbkdf2_sha256$600000$00000000000000000000000000000000$'+'0'*64)
            if not user or not matches:
                raise Error('Invalid username or password', 401)
            self.rice.account(con, dict(user))
            if data.get('client') == 'web' and user['role'] != 'admin':
                raise Error('Staff accounts use the Android application', 403)
            if not user['password'].startswith('pbkdf2_sha256$600000$'):
                con.execute('UPDATE users SET password=? WHERE id=?',(password_hash(password),user['id']))
            token = secrets.token_urlsafe(32)
            con.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
            con.execute('INSERT INTO sessions VALUES(?,?,?)', (token, user['id'], time.time() + 8*3600))
            con.execute('INSERT INTO session_activity VALUES(?,?)',(token,time.time()))
            return {'token': token, 'role': user['role'], 'username': user['username']}

    def auth(self, token):
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            user = con.execute('SELECT u.id,u.username,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?', (token, time.time())).fetchone()
            if not user:
                raise Error('Please sign in again', 401)
            active=con.execute('SELECT last_seen FROM session_activity WHERE token=?',(token,)).fetchone()
            if active and active['last_seen'] < time.time()-SESSION_IDLE_SECONDS:
                raise Error('Session expired after inactivity. Please sign in again',401)
            if active:con.execute('UPDATE session_activity SET last_seen=? WHERE token=?',(time.time(),token))
            else:con.execute('INSERT INTO session_activity VALUES(?,?)',(token,time.time()))
            self.rice.account(con, dict(user))
            return dict(user)

    def throttle(self, bucket, limit, global_limit=120):
        """Database-backed rolling rate limit survives process restarts and workers."""
        stamp=time.time()
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('DELETE FROM auth_attempts WHERE attempted_at<?',(stamp-60,))
            count=con.execute('SELECT count(*) FROM auth_attempts WHERE bucket=?',(bucket,)).fetchone()[0]
            total=con.execute('SELECT count(*) FROM auth_attempts').fetchone()[0]
            if count>=limit or total>=global_limit:
                raise Error('Too many attempts. Wait one minute.',429)
            con.execute('INSERT INTO auth_attempts(bucket,attempted_at) VALUES(?,?)',(bucket,stamp))

    def authorize(self, user, admin=False):
        if user['role'] not in (['admin'] if admin else ['admin', 'operator']):
            raise Error('Your role cannot perform this action', 403)

    def inventory(self):
        with self.connection() as con:
            return {'mode': self.mode,
                    'items': [dict(r) for r in con.execute('SELECT * FROM items ORDER BY name')],
                    'locations': [dict(r) for r in con.execute('SELECT * FROM locations ORDER BY name')],
                    'stock': [dict(r) for r in con.execute('SELECT s.*,i.name,i.sku,l.name AS location FROM stock s JOIN items i ON i.id=s.item_id JOIN locations l ON l.id=s.location_id ORDER BY i.name,l.name')]}

    def account_security(self, user, data):
        """Re-authenticate and atomically revoke every device session for this account."""
        self.throttle('security:'+str(user['id']),5)
        current = data.get('current_password')
        action = data.get('action')
        if not isinstance(current, str) or len(current) > 500:
            raise Error('Enter your current password')
        if action not in ('change_password', 'revoke_sessions'):
            raise Error('Choose a valid account security action')
        new = data.get('new_password')
        if action == 'change_password':
            if not isinstance(new, str) or not 12 <= len(new) <= 128:
                raise Error('Use a new password between 12 and 128 characters')
            if new == current:
                raise Error('Choose a different password')
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            account = con.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone()
            if not account or not password_matches(current, account['password']):
                raise Error('Current password is incorrect', 403)
            if action == 'change_password':
                con.execute('UPDATE users SET password=? WHERE id=?', (password_hash(new), user['id']))
            con.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
        return {'message': 'Password changed. Sign in again.' if action == 'change_password' else 'All devices signed out. Sign in again.'}

    def catalog(self, user, data):
        self.authorize(user, True)
        with self.connection() as con:
            if data.get('kind') == 'location':
                cur = con.execute('INSERT INTO locations(name) VALUES(?)', (required(data, 'name'),))
            elif data.get('kind') == 'item':
                cls = required(data, 'model_class')
                cur = con.execute('INSERT INTO items(sku,name,model_class) VALUES(?,?,?)', (required(data, 'sku'), required(data, 'name'), cls))
            elif data.get('kind') == 'stock':
                item = integer(data.get('item_id'), 1)
                loc = integer(data.get('location_id'), 1)
                cur = con.execute('INSERT INTO stock VALUES(?,?,0,0)', (item, loc))
            elif data.get('kind') == 'update_item':
                item_id = integer(data.get('id'), 1)
                cur = con.execute('UPDATE items SET sku=?,name=?,model_class=? WHERE id=?', (required(data,'sku'),required(data,'name'),required(data,'model_class'),item_id))
                if not cur.rowcount:
                    raise Error('Item not found',404)
                return {'id':item_id,'message':'Updated'}
            else:
                raise Error('Choose item, location, or stock')
            return {'id': cur.lastrowid, 'message': 'Created'}

    def create_user(self, user, data):
        self.authorize(user, True)
        password = data.get('password')
        role = data.get('role')
        if not isinstance(password,str) or not 12<=len(password)<=128 or role not in ['admin', 'operator', 'viewer']:
            raise Error('Use a 12–128 character password and a valid role')
        with self.connection() as con:
            cur = con.execute('INSERT INTO users(username,password,role) VALUES(?,?,?)', (required(data, 'username'), password_hash(password), role))
            return {'id': cur.lastrowid}

    def scan(self, user, data):
        self.authorize(user)
        loc = integer(data.get('location_id'), 1)
        from PIL import Image, ImageOps, UnidentifiedImageError
        from io import BytesIO
        try:
            raw = base64.b64decode(data.get('image', ''), validate=True)
            if not raw or len(raw) > 6*1024*1024:
                raise Error('Photo must be between 1 byte and 6 MB')
            with Image.open(BytesIO(raw)) as src:
                if src.width * src.height > 20000000:
                    raise Error('Photo must be at most 20 megapixels')
                picture = ImageOps.exif_transpose(src).convert('RGB')
        except (ValueError, TypeError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
            raise Error('Invalid or unsafe image')
        started = time.perf_counter()
        with self.connection() as con:
            snapshot = [dict(r) for r in con.execute('SELECT * FROM stock WHERE location_id=?', (loc,))]
            classes = {r['model_class']: dict(r) for r in con.execute('SELECT * FROM items')}
            if not con.execute('SELECT id FROM locations WHERE id=?', (loc,)).fetchone():
                raise Error('Unknown location')
        detections = []
        if self.mode == 'demo':
            # Synthetic boxes deliberately do not inspect the photograph.
            for row in snapshot[:2]:
                item = next((x for x in classes.values() if x['id'] == row['item_id']), None)
                if item:
                    for index in range(2):
                        x = .08 + index*.4
                        detections.append({'item_id': item['id'], 'name': item['name'], 'class': item['model_class'], 'confidence': .9, 'box': [x,.12,x+.28,.44]})
        else:
            with self.model_lock:
                result = self.model.predict(picture, conf=.35, verbose=False)[0]
            for box in result.boxes:
                cls = result.names[int(box.cls[0])]
                item = classes.get(cls)
                detections.append({'item_id': item['id'] if item else None, 'name': item['name'] if item else cls, 'class': cls, 'confidence': float(box.conf[0]), 'box': box.xyxyn[0].tolist()})
        scan_id = str(uuid.uuid4())
        with self.connection() as con:
            con.execute('INSERT INTO scans VALUES(?,?,?,?,?,?,?)', (scan_id, user['id'], loc, self.mode, json.dumps(detections), json.dumps(snapshot), now()))
        return {'id': scan_id, 'mode': self.mode, 'detections': detections, 'snapshot': snapshot, 'processing_ms': round((time.perf_counter()-started)*1000, 2), 'warning': 'Synthetic sample detections; photo content was not analyzed.' if self.mode == 'demo' else 'Verify visible detections. Hidden stock cannot be counted reliably. Use incoming addition only for new goods; reconciliation requires a physical count of the entire item/location.'}

    def _change(self, con, user, item, loc, count, stock, key, digest, reason, source, scan_id=None):
        integer(count)
        difference=count-stock['quantity']
        stamp=now()
        cur=con.execute('INSERT INTO adjustments(request_key,payload_hash,scan_id,item_id,location_id,previous_quantity,verified_quantity,difference,reason,user_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (key,digest,scan_id,item,loc,stock['quantity'],count,difference,reason,user['id'],stamp))
        con.execute('UPDATE stock SET quantity=?,version=version+1 WHERE item_id=? AND location_id=?',(count,item,loc))
        con.execute('INSERT INTO movements(item_id,location_id,difference,resulting_quantity,source_type,source_id,user_id,created_at) VALUES(?,?,?,?,?,?,?,?)',(item,loc,difference,count,source,cur.lastrowid,user['id'],stamp))
        return dict(con.execute('SELECT * FROM adjustments WHERE id=?',(cur.lastrowid,)).fetchone())

    def add_scan(self,user,data):
        self.authorize(user)
        if data.get('confirmed') is not True:
            raise Error('Confirm the quantities to add first')
        key,scan_id,reason=required(data,'request_key'),required(data,'scan_id'),required(data,'reason')
        lines=data.get('items')
        if not isinstance(lines,list) or not lines or len(lines)>500:
            raise Error('Select at least one item to add')
        seen=set()
        for line in lines:
            if not isinstance(line,dict):raise Error('Invalid item row')
            item=integer(line.get('item_id'),1);integer(line.get('quantity'),1)
            if item in seen:raise Error('Select each item only once')
            seen.add(item)
        digest=fingerprint({**data,'_user_id':user['id']})
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            old=con.execute('SELECT * FROM scan_commits WHERE request_key=?',(key,)).fetchone()
            if old:
                if old['payload_hash']!=digest:raise Error('Request key reused with different content',409)
                return json.loads(old['result'])
            scan=con.execute('SELECT * FROM scans WHERE id=?',(scan_id,)).fetchone()
            if not scan or scan['user_id']!=user['id']:raise Error('Scan does not belong to this user')
            if con.execute('SELECT 1 FROM scan_commits WHERE scan_id=?',(scan_id,)).fetchone() or con.execute('SELECT 1 FROM adjustments WHERE scan_id=?',(scan_id,)).fetchone():
                raise Error('This photo has already been added or used for an adjustment',409)
            changes=[]
            for line in lines:
                item=line['item_id'];loc=scan['location_id']
                stock=con.execute('SELECT * FROM stock WHERE item_id=? AND location_id=?',(item,loc)).fetchone()
                if not stock:raise Error('Register the selected item at this location first')
                changes.append(self._change(con,user,item,loc,stock['quantity']+line['quantity'],stock,key+':'+str(item),digest,reason,'photo addition',scan_id))
            result={'scan_id':scan_id,'changes':changes}
            con.execute('INSERT INTO scan_commits VALUES(?,?,?,?)',(key,digest,scan_id,json.dumps(result)))
            return result

    def manual_adjust(self,user,data):
        self.authorize(user)
        if data.get('confirmed') is not True:raise Error('Confirm the manual stock change')
        item=integer(data.get('item_id'),1);loc=integer(data.get('location_id'),1)
        count=integer(data.get('quantity'));version=integer(data.get('expected_version'))
        key,reason=required(data,'request_key'),required(data,'reason')
        digest=fingerprint({**data,'_user_id':user['id']})
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            old=con.execute('SELECT * FROM adjustments WHERE request_key=?',(key,)).fetchone()
            if old:
                if old['payload_hash']!=digest:raise Error('Request key reused with different content',409)
                return dict(old)
            stock=con.execute('SELECT * FROM stock WHERE item_id=? AND location_id=?',(item,loc)).fetchone()
            if not stock:raise Error('Stock record not found',404)
            if stock['version']!=version:raise Error('Stock changed. Refresh before editing again.',409)
            return self._change(con,user,item,loc,count,stock,key,digest,reason,'manual adjustment')

    def adjust(self, user, data):
        self.authorize(user)
        if data.get('confirmed') is not True or data.get('complete_location_count') is not True:
            raise Error('Confirm a verified count of the ENTIRE selected item/location; partial photos cannot replace stock')
        item, loc, count = integer(data.get('item_id'), 1), integer(data.get('location_id'), 1), integer(data.get('verified_quantity'))
        key, reason, scan_id = required(data, 'request_key'), required(data, 'reason'), required(data, 'scan_id')
        digest = fingerprint({**data, '_user_id': user['id']})
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            old = con.execute('SELECT * FROM adjustments WHERE request_key=?', (key,)).fetchone()
            if old:
                if old['payload_hash'] != digest:
                    raise Error('Request key reused with different content', 409)
                return dict(old)
            scan = con.execute('SELECT * FROM scans WHERE id=?', (scan_id,)).fetchone()
            if not scan or scan['user_id'] != user['id'] or scan['location_id'] != loc:
                raise Error('Scan does not belong to this user and location')
            if con.execute('SELECT 1 FROM scan_commits WHERE scan_id=?',(scan_id,)).fetchone():
                raise Error('This scan was already used to add incoming stock. Take a new scan for reconciliation.',409)
            snapshot = next((r for r in json.loads(scan['snapshot']) if r['item_id'] == item), None)
            if not snapshot:
                raise Error('Item was not registered in this scan location')
            if con.execute('SELECT id FROM adjustments WHERE scan_id=? AND item_id=? AND location_id=?', (scan_id,item,loc)).fetchone():
                raise Error('This scan/item has already been committed', 409)
            stock = con.execute('SELECT * FROM stock WHERE item_id=? AND location_id=?', (item, loc)).fetchone()
            if stock['version'] != snapshot['version']:
                raise Error('Stock changed after the scan. Take a new scan and verify again.', 409)
            difference = count - stock['quantity']
            stamp = now()
            cur = con.execute('INSERT INTO adjustments(request_key,payload_hash,scan_id,item_id,location_id,previous_quantity,verified_quantity,difference,reason,user_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (key,digest,scan_id,item,loc,stock['quantity'],count,difference,reason,user['id'],stamp))
            con.execute('UPDATE stock SET quantity=?,version=version+1 WHERE item_id=? AND location_id=?', (count,item,loc))
            con.execute('INSERT INTO movements(item_id,location_id,difference,resulting_quantity,source_type,source_id,user_id,created_at) VALUES(?,?,?,?,?,?,?,?)', (item,loc,difference,count,'adjustment',cur.lastrowid,user['id'],stamp))
            return dict(con.execute('SELECT * FROM adjustments WHERE id=?', (cur.lastrowid,)).fetchone())

    def create_return(self, user, data):
        self.authorize(user)
        item, loc, qty = integer(data.get('item_id'),1), integer(data.get('location_id'),1), integer(data.get('quantity'),1)
        reason, key = required(data,'reason'), required(data,'request_key')
        digest = fingerprint({**data, '_user_id': user['id']})
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            old = con.execute('SELECT * FROM returns WHERE request_key=?', (key,)).fetchone()
            if old:
                if old['payload_hash'] != digest:
                    raise Error('Request key reused with different content',409)
                return dict(old)
            if not con.execute('SELECT * FROM stock WHERE item_id=? AND location_id=?', (item,loc)).fetchone():
                raise Error('Register this item/location stock first')
            stamp = now()
            cur = con.execute('INSERT INTO returns(request_key,payload_hash,item_id,location_id,quantity,reason,user_id,created_at) VALUES(?,?,?,?,?,?,?,?)', (key,digest,item,loc,qty,reason,user['id'],stamp))
            con.execute('INSERT INTO return_events(return_id,previous_status,new_status,user_id,created_at) VALUES(?,?,?,?,?)', (cur.lastrowid,None,'pending inspection',user['id'],stamp))
            return dict(con.execute('SELECT * FROM returns WHERE id=?', (cur.lastrowid,)).fetchone())

    def transition(self, user, return_id, data):
        self.authorize(user)
        target = data.get('status')
        allowed = {'pending inspection': ['accepted','damaged'], 'accepted': ['returned to available stock','damaged'], 'damaged': [], 'returned to available stock': []}
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            ret = con.execute('SELECT * FROM returns WHERE id=?', (return_id,)).fetchone()
            if not ret:
                raise Error('Return not found',404)
            if target == ret['status']:
                return dict(ret)
            if target not in allowed[ret['status']]:
                raise Error('Invalid return status transition',409)
            if target == 'returned to available stock' and data.get('confirmed_suitable') is not True:
                raise Error('Confirm inspection and suitability before restocking')
            stamp = now()
            if target == 'returned to available stock':
                stock=con.execute('SELECT quantity FROM stock WHERE item_id=? AND location_id=?',(ret['item_id'],ret['location_id'])).fetchone()
                if not stock:raise Error('Stock record not found',404)
                integer(stock['quantity']+ret['quantity'])
                con.execute('UPDATE stock SET quantity=quantity+?,version=version+1 WHERE item_id=? AND location_id=?', (ret['quantity'],ret['item_id'],ret['location_id']))
                qty = con.execute('SELECT quantity FROM stock WHERE item_id=? AND location_id=?', (ret['item_id'],ret['location_id'])).fetchone()[0]
                con.execute('INSERT INTO movements(item_id,location_id,difference,resulting_quantity,source_type,source_id,user_id,created_at) VALUES(?,?,?,?,?,?,?,?)', (ret['item_id'],ret['location_id'],ret['quantity'],qty,'return',return_id,user['id'],stamp))
            con.execute('INSERT INTO return_events(return_id,previous_status,new_status,user_id,created_at) VALUES(?,?,?,?,?)', (return_id,ret['status'],target,user['id'],stamp))
            con.execute('UPDATE returns SET status=? WHERE id=?', (target,return_id))
            return dict(con.execute('SELECT * FROM returns WHERE id=?', (return_id,)).fetchone())

    def report(self, kind):
        queries = {
            'inventory': 'SELECT s.*,i.name,i.sku,l.name AS location FROM stock s JOIN items i ON i.id=s.item_id JOIN locations l ON l.id=s.location_id',
            'adjustments': 'SELECT a.*,u.username FROM adjustments a JOIN users u ON u.id=a.user_id ORDER BY a.id DESC',
            'returns': 'SELECT r.*,i.name,l.name AS location,u.username FROM returns r JOIN items i ON i.id=r.item_id JOIN locations l ON l.id=r.location_id JOIN users u ON u.id=r.user_id ORDER BY r.id DESC',
            'movements': 'SELECT m.*,i.name,l.name AS location,u.username FROM movements m JOIN items i ON i.id=m.item_id JOIN locations l ON l.id=m.location_id JOIN users u ON u.id=m.user_id ORDER BY m.id DESC',
            'scans': "SELECT s.*,u.username,l.name AS location, CASE WHEN EXISTS(SELECT 1 FROM adjustments a WHERE a.scan_id=s.id) THEN 'verified and committed' ELSE 'pending review' END AS verification_status FROM scans s JOIN users u ON u.id=s.user_id JOIN locations l ON l.id=s.location_id ORDER BY s.created_at DESC",
            'return_events': 'SELECT e.*,u.username FROM return_events e JOIN users u ON u.id=e.user_id ORDER BY e.id DESC'
        }
        if kind not in queries:
            raise Error('Unknown report',404)
        with self.connection() as con:
            rows = [dict(r) for r in con.execute(queries[kind])]
            for row in rows:
                row.pop('payload_hash', None)
            return rows
