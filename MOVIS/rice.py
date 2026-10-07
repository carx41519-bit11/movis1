"""Paper-aligned rice transactions. SQLite and PostgreSQL share serialized transactions.

Legacy tables remain intact; supported balances migrate once by exact rice name/class.
"""
import base64
import hashlib
import json
import re
import time
import uuid
from io import BytesIO
from pathlib import Path
from service import Error, integer, required, fingerprint, now

PRODUCTS = [(1, 'RICE-SIN-25', 'Sinandomeng', 'sinandomeng'),
            (2, 'RICE-JAS-25', 'Jasmine rice', 'jasmine'),
            (3, 'RICE-BUK-25', 'Buko Pandan rice', 'buko_pandan')]
KINDS = ('stock-in', 'stock-out', 'count', 'return', 'damage')


class RiceWorkflow:
    def __init__(self, service):
        self.s = service
        with service.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            c.executescript(Path(__file__).with_name('rice_schema.sql').read_text())
            for pid, sku, name, cls in PRODUCTS:
                if not c.execute('SELECT id FROM rice_products WHERE id=?', (pid,)).fetchone():
                    aliases = (name.casefold(), name.casefold().replace(' rice', ''), cls)
                    qty = c.execute('SELECT COALESCE(SUM(s.quantity),0) FROM stock s JOIN items i ON i.id=s.item_id WHERE lower(i.name) IN (?,?,?) OR lower(i.model_class) IN (?,?,?)', aliases + aliases).fetchone()[0]
                    c.execute('INSERT INTO rice_products(id,sku,name,model_class,quantity) VALUES(?,?,?,?,?)', (pid, sku, name, cls, integer(qty)))

    def account(self, c, user):
        row = c.execute('SELECT * FROM rice_accounts WHERE user_id=?', (user['id'],)).fetchone()
        if row and not row['active']:
            raise Error('Account is inactive', 403)
        return {'active': True, 'can_adjust': user['role'] == 'admin' or bool(row and row['can_adjust'])}

    def allowed(self, c, user, adjust=False, admin=False):
        access = self.account(c, user)
        self.s.authorize(user, admin)
        if adjust and not access['can_adjust']:
            raise Error('Stock adjustment permission is required', 403)

    def action(self, c, user, aid, open_only=True):
        a = c.execute('SELECT * FROM rice_actions WHERE id=?', (aid,)).fetchone()
        if not a or (a['user_id'] != user['id'] and user['role'] != 'admin'):
            raise Error('Action not found', 404)
        if open_only and a['state'] != 'open':
            raise Error('This action is locked after completion', 409)
        return a

    def retry(self, c, user, data, endpoint):
        key = required(data, 'request_id')
        digest = fingerprint({'endpoint': endpoint, 'user': user['id'], 'data': data})
        old = c.execute('SELECT * FROM rice_requests WHERE id=?', (key,)).fetchone()
        if old:
            if old['payload_hash'] != digest:
                raise Error('Request ID reused with changed information', 409)
            return key, digest, json.loads(old['result'])
        return key, digest, None

    def save(self, c, key, digest, result):
        c.execute('INSERT INTO rice_requests VALUES(?,?,?)', (key, digest, json.dumps(result)))
        return json.loads(json.dumps(result))

    def version(self, a, data):
        if integer(data.get('revision')) != a['revision']:
            raise Error('Action changed. Refresh and review the current images.', 409)

    def snapshot(self, c, ids):
        rows = []
        for pid in ids:
            row = c.execute('SELECT * FROM rice_products WHERE id=?', (integer(pid, 1),)).fetchone()
            if not row:
                raise Error('Unknown rice product')
            rows.append({'product_id': pid, 'quantity': row['quantity'], 'version': row['version']})
        return rows

    def state(self, user, aid=None, include_images=False):
        with self.s.connection() as c:
            access = self.account(c, user)
            result = {'mode': self.s.mode, 'user': {**user, **access},
                      'products': [dict(r) for r in c.execute('SELECT * FROM rice_products ORDER BY id')]}
            if aid:
                a = dict(self.action(c, user, aid, False))
                for field in ('snapshot', 'comparison', 'details'):
                    a[field] = json.loads(a[field])
                images = []
                for r in c.execute('SELECT * FROM rice_images WHERE action_id=? ORDER BY id', (aid,)):
                    row = dict(r)
                    if not include_images:
                        row.pop('image')
                    row.pop('image_hash')
                    row['raw'], row['checked'] = json.loads(row['raw']), json.loads(row['checked'])
                    images.append(row)
                a['images'] = images
                result['action'] = a
                return result
            where, params = ('', ()) if user['role'] == 'admin' else (' WHERE a.user_id=?', (user['id'],))
            result['actions'] = [dict(r) for r in c.execute('SELECT a.*,u.username FROM rice_actions a JOIN users u ON u.id=a.user_id' + where + ' ORDER BY a.created_at DESC LIMIT 200', params)]
            where, params = ('', ()) if user['role'] == 'admin' else (' WHERE h.user_id=?', (user['id'],))
            result['history'] = [dict(r) for r in c.execute('SELECT h.*,p.name,u.username FROM rice_history h JOIN rice_products p ON p.id=h.product_id JOIN users u ON u.id=h.user_id' + where + ' ORDER BY h.created_at DESC LIMIT 1000', params)]
            where, params = ('', ()) if user['role'] == 'admin' else (' WHERE h.user_id=?', (user['id'],))
            result['cases'] = [dict(r) for r in c.execute('SELECT h.*,p.name,u.username FROM rice_cases h JOIN rice_products p ON p.id=h.product_id JOIN users u ON u.id=h.user_id' + where + ' ORDER BY h.created_at DESC LIMIT 500', params)]
            if user['role'] == 'admin':
                result['users'] = [dict(r) for r in c.execute('SELECT u.id,u.username,u.role,COALESCE(a.active,1) AS active,COALESCE(a.can_adjust,0) AS can_adjust FROM users u LEFT JOIN rice_accounts a ON a.user_id=u.id ORDER BY u.id')]
                result['decisions'] = [dict(r) for r in c.execute('SELECT d.*,u.username FROM rice_decisions d JOIN users u ON u.id=d.user_id ORDER BY d.created_at DESC LIMIT 500')]
            return result

    def report(self, user, kind):
        queries = {
            'inventory': 'SELECT * FROM rice_products ORDER BY id',
            'history': 'SELECT h.*,p.name,u.username FROM rice_history h JOIN rice_products p ON p.id=h.product_id JOIN users u ON u.id=h.user_id ORDER BY h.created_at,h.id',
            'counts': "SELECT a.id,a.snapshot,a.comparison,a.details,a.state,u.username,a.created_at FROM rice_actions a JOIN users u ON u.id=a.user_id WHERE a.kind='count' ORDER BY a.created_at,a.id",
            'cases': 'SELECT h.*,p.name,u.username FROM rice_cases h JOIN rice_products p ON p.id=h.product_id JOIN users u ON u.id=h.user_id ORDER BY h.created_at,h.id',
            'decisions': 'SELECT d.*,u.username FROM rice_decisions d JOIN users u ON u.id=d.user_id ORDER BY d.created_at,d.id',
            'scans': 'SELECT i.id,i.action_id,i.deleted,i.reviewed,i.raw,i.checked,i.processing_ms,i.model_version,a.kind,u.username,a.created_at FROM rice_images i JOIN rice_actions a ON a.id=i.action_id JOIN users u ON u.id=a.user_id ORDER BY a.created_at,i.id'
        }
        if kind not in queries:
            raise Error('Unknown report', 404)
        with self.s.connection() as c:
            self.allowed(c, user, admin=True)
            return {'rows': [dict(r) for r in c.execute(queries[kind])]}

    def open(self, user, data):
        with self.s.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            self.allowed(c, user)
            key, digest, old = self.retry(c, user, data, 'open')
            if old is not None:
                return old
            kind = data.get('kind')
            if kind not in KINDS:
                raise Error('Select an allowed transaction before capture')
            ids = data.get('products', [r['id'] for r in c.execute('SELECT id FROM rice_products ORDER BY id')])
            if not isinstance(ids, list) or not ids or any(type(x) is not int for x in ids) or len(set(ids)) != len(ids):
                raise Error('Choose distinct rice products')
            snapshot = self.snapshot(c, ids)
            aid = str(uuid.uuid4())
            c.execute('INSERT INTO rice_actions(id,user_id,kind,snapshot,created_at) VALUES(?,?,?,?,?)', (aid, user['id'], kind, json.dumps(snapshot), now()))
            return self.save(c, key, digest, {'action_id': aid})

    def image(self, user, data):
        # Reserve IDs before inference so a delete wins even when inference returns late.
        aid, iid = required(data, 'action_id'), required(data, 'image_id')
        if data.get('source') != 'camera' or type(data.get('zoom')) is not int or data['zoom'] != 1:
            raise Error('Use a new MOVIS rear-camera image at 1x')
        from PIL import Image, ImageOps, UnidentifiedImageError
        try:
            raw = base64.b64decode(data.get('image', ''), validate=True)
            if not raw or len(raw) > 6 * 1024 * 1024:
                raise Error('Image must be between 1 byte and 6 MB')
            with Image.open(BytesIO(raw)) as src:
                if src.width * src.height > 20000000:
                    raise Error('Image exceeds 20 megapixels')
                picture = ImageOps.exif_transpose(src).convert('RGB')
        except (ValueError, TypeError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
            raise Error('Invalid image')
        ihash = hashlib.sha256(raw).hexdigest()
        with self.s.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            self.allowed(c, user)
            self.action(c, user, aid)
            prior = c.execute('SELECT * FROM rice_images WHERE id=?', (iid,)).fetchone()
            if prior:
                if prior['action_id'] != aid or prior['image_hash'] != ihash:
                    raise Error('Image ID reused with different content', 409)
                if prior['deleted']:
                    raise Error('Image was deleted', 409)
                if prior['model_version'] not in ('processing', 'failed'):
                    return {'image_id': iid}
            else:
                if c.execute('SELECT count(*) FROM rice_images WHERE action_id=? AND deleted=0', (aid,)).fetchone()[0] >= 40:
                    raise Error('Maximum 40 kept images per action')
                c.execute('INSERT INTO rice_images(id,action_id,image,image_hash,raw,processing_ms,model_version) VALUES(?,?,?,?,?,?,?)', (iid, aid, data['image'], ihash, '[]', '0', 'processing'))
                c.execute('UPDATE rice_actions SET revision=revision+1 WHERE id=?', (aid,))
            products = [dict(r) for r in c.execute('SELECT * FROM rice_products')]
        start = time.perf_counter()
        detections = []
        try:
            if self.s.mode == 'demo':
                for p in products:
                    detections.append({'product_id': p['id'], 'name': p['name'], 'class': p['model_class'], 'confidence': .9, 'box': [.1, .1, .4, .4]})
                model = 'synthetic-demo'
            else:
                with self.s.model_lock:
                    prediction = self.s.model.predict(picture, conf=.35, verbose=False)[0]
                for box in prediction.boxes:
                    cls = prediction.names[int(box.cls[0])]
                    p = next((p for p in products if p['model_class'] == cls), None)
                    detections.append({'product_id': p['id'] if p else None, 'name': p['name'] if p else cls, 'class': cls, 'confidence': float(box.conf[0]), 'box': box.xyxyn[0].tolist()})
                model = getattr(self.s, 'weights_digest', 'configured-yolo')
        except Exception:
            with self.s.connection() as c:
                c.execute("UPDATE rice_images SET model_version='failed' WHERE id=? AND deleted=0", (iid,))
            raise Error('Scan failed. Retake or retry this image; stock is unchanged.', 503)
        with self.s.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            a = self.action(c, user, aid)
            row = c.execute('SELECT * FROM rice_images WHERE id=?', (iid,)).fetchone()
            if row['deleted']:
                return {'image_id': iid, 'deleted': True}
            if row['model_version'] not in ('processing', 'failed'):
                return {'image_id': iid}
            c.execute('UPDATE rice_images SET raw=?,processing_ms=?,model_version=? WHERE id=?', (json.dumps(detections), str(round((time.perf_counter() - start) * 1000, 2)), model, iid))
            c.execute('UPDATE rice_actions SET revision=revision+1 WHERE id=?', (aid,))
            return {'image_id': iid}

    def checked(self, lines, allowed_ids, positive=False):
        if not isinstance(lines, list) or len(lines) > len(allowed_ids):
            raise Error('Provide checked rice quantities')
        totals = {}
        for line in lines:
            if not isinstance(line, dict):
                raise Error('Invalid checked quantity row')
            pid, qty = integer(line.get('product_id'), 1), integer(line.get('quantity'), 1 if positive else 0)
            if pid not in allowed_ids or pid in totals:
                raise Error('Duplicate or unselected rice product')
            totals[pid] = qty
        return totals

    def edit(self, user, data, delete=False):
        with self.s.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            self.allowed(c, user)
            key, digest, old = self.retry(c, user, data, 'delete' if delete else 'review')
            if old is not None:
                return old
            a = self.action(c, user, required(data, 'action_id'))
            self.version(a, data)
            row = c.execute('SELECT * FROM rice_images WHERE id=? AND action_id=?', (required(data, 'image_id'), a['id'])).fetchone()
            if not row or row['deleted']:
                raise Error('Image is unavailable', 409)
            if delete:
                c.execute('UPDATE rice_images SET deleted=1,reviewed=0,image=? WHERE id=?', ('', row['id']))
            else:
                if row['model_version'] in ('processing', 'failed'):
                    raise Error('Image must finish processing before review')
                self.checked(data.get('checked'), [x['product_id'] for x in json.loads(a['snapshot'])])
                if data.get('confirmed') is not True:
                    raise Error('Confirm this image was checked')
                c.execute('UPDATE rice_images SET checked=?,reviewed=1 WHERE id=?', (json.dumps(data['checked']), row['id']))
            c.execute('UPDATE rice_actions SET revision=revision+1 WHERE id=?', (a['id'],))
            return self.save(c, key, digest, {'message': 'Deleted' if delete else 'Checked quantities saved; stock unchanged'})

    def delete(self, user, data):
        return self.edit(user, data, True)

    def review(self, user, data):
        return self.edit(user, data)

    def refresh_count(self, user, data):
        with self.s.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            self.allowed(c, user)
            key, digest, old = self.retry(c, user, data, 'refresh-count')
            if old is not None:
                return old
            a = self.action(c, user, required(data, 'action_id'))
            self.version(a, data)
            if a['kind'] != 'count' or data.get('confirmed_review') is not True:
                raise Error('Recheck affected sacks before updating the count baseline')
            rows = self.snapshot(c, [x['product_id'] for x in json.loads(a['snapshot'])])
            c.execute('UPDATE rice_actions SET snapshot=?,revision=revision+1 WHERE id=?', (json.dumps(rows), a['id']))
            c.execute('UPDATE rice_images SET reviewed=0 WHERE action_id=? AND deleted=0', (a['id'],))
            return self.save(c, key, digest, {'message': 'Baseline refreshed. Check every retained image again.'})

    def totals(self, c, a, data):
        ids = [x['product_id'] for x in json.loads(a['snapshot'])]
        totals = {pid: 0 for pid in ids}
        images = list(c.execute('SELECT * FROM rice_images WHERE action_id=? AND deleted=0', (a['id'],)))
        if not images:
            raise Error('Capture and check at least one new image')
        for r in images:
            if not r['reviewed'] or r['model_version'] in ('processing', 'failed'):
                raise Error('Check every retained image before completing this action')
            for pid, qty in self.checked(json.loads(r['checked']), ids).items():
                totals[pid] = integer(totals[pid] + qty)
        entries = data.get('manual', [])
        if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
            raise Error('Provide separately checked quantity rows')
        for entry in entries:
            required(entry, 'reason')
        for pid, qty in self.checked(entries, ids).items():
            totals[pid] = integer(totals[pid] + qty)
        if data.get('unique_sacks') is not True:
            raise Error('Confirm each physical sack is counted only once')
        return totals

    def change(self, c, user, aid, pid, qty, kind, reason):
        p = c.execute('SELECT * FROM rice_products WHERE id=?', (pid,)).fetchone()
        integer(qty)
        delta = qty - p['quantity']
        if delta:
            c.execute('UPDATE rice_products SET quantity=?,version=version+1 WHERE id=?', (qty, pid))
        c.execute('INSERT INTO rice_history VALUES(?,?,?,?,?,?,?,?,?,?)', (str(uuid.uuid4()), aid, pid, kind, p['quantity'], qty, delta, user['id'], reason, now()))

    def complete(self, user, data, count=False):
        with self.s.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            self.allowed(c, user)
            key, digest, old = self.retry(c, user, data, 'finish' if count else 'submit')
            if old is not None:
                return old
            a = self.action(c, user, required(data, 'action_id'))
            self.version(a, data)
            if (a['kind'] == 'count') != count:
                raise Error('Use Finish count for inventory counts')
            reason = required(data, 'reason')
            totals = self.totals(c, a, data)
            comparisons = []
            for snap in json.loads(a['snapshot']):
                pid = snap['product_id']
                p = c.execute('SELECT * FROM rice_products WHERE id=?', (pid,)).fetchone()
                qty = totals[pid]
                if count:
                    if p['version'] != snap['version']:
                        raise Error('Stock changed during counting. Review affected sacks and refresh the baseline.', 409)
                    complete = data.get('full_counts', {}).get(str(pid)) is True
                    if not complete:
                        raise Error('Confirm a complete physical count for every chosen product')
                    if qty == 0 and data.get('zero_confirmed', {}).get(str(pid)) is not True:
                        raise Error('Physically confirm no sacks remain before recording zero')
                    comparisons.append({**snap, 'count': qty, 'difference': qty - p['quantity'], 'complete': True, 'adjusted': False})
                elif qty:
                    if a['kind'] in ('stock-in', 'stock-out'):
                        if a['kind'] == 'stock-out' and qty > p['quantity']:
                            raise Error('Insufficient stock for ' + p['name'] + '. No products were changed.', 409)
                        self.change(c, user, a['id'], pid, p['quantity'] + (qty if a['kind'] == 'stock-in' else -qty), a['kind'], reason)
                    else:
                        if type(data.get('already_stocked')) is not bool:
                            raise Error('Confirm whether these sacks are already included in available stock')
                        condition = required(data, 'condition')
                        cid = str(uuid.uuid4())
                        c.execute('INSERT INTO rice_cases(id,action_id,product_id,kind,quantity,remaining,already_stocked,condition,reason,user_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (cid, a['id'], pid, a['kind'], qty, qty, int(data['already_stocked']), condition, reason, user['id'], now()))
            if not count and not any(totals.values()):
                raise Error('At least one checked quantity must be greater than zero')
            c.execute('UPDATE rice_actions SET state=?,comparison=?,details=?,revision=revision+1 WHERE id=?', ('finished' if count else 'submitted', json.dumps(comparisons), json.dumps(data), a['id']))
            return self.save(c, key, digest, {'action_id': a['id'], 'totals': totals, 'comparison': comparisons, 'message': 'Count saved; stock unchanged' if count else 'Transaction saved'})

    def finish(self, user, data):
        return self.complete(user, data, True)

    def submit(self, user, data):
        return self.complete(user, data)

    def adjust(self, user, data):
        with self.s.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            self.allowed(c, user, adjust=True)
            key, digest, old = self.retry(c, user, data, 'adjust')
            if old is not None:
                return old
            a = self.action(c, user, required(data, 'action_id'), False)
            self.version(a, data)
            if a['kind'] != 'count' or a['state'] != 'finished' or data.get('confirmed') is not True:
                raise Error('Finish a full count before confirming a separate adjustment')
            ids = data.get('products')
            if not isinstance(ids, list) or not ids or any(type(x) is not int for x in ids) or len(set(ids)) != len(ids):
                raise Error('Select distinct product corrections')
            rows = json.loads(a['comparison'])
            reason = required(data, 'reason')
            for pid in ids:
                row = next((r for r in rows if r['product_id'] == pid), None)
                p = c.execute('SELECT * FROM rice_products WHERE id=?', (pid,)).fetchone()
                if not row or row['adjusted'] or not row['complete'] or not row['difference']:
                    raise Error('No pending complete-count difference for this product', 409)
                if p['version'] != row['version']:
                    raise Error('Stock changed after Finish count. Start a new count and review the affected sacks.', 409)
                self.change(c, user, a['id'], pid, row['count'], 'count adjustment', reason)
                row['adjusted'] = True
            c.execute('UPDATE rice_actions SET comparison=?,revision=revision+1 WHERE id=?', (json.dumps(rows), a['id']))
            return self.save(c, key, digest, {'message': 'Chosen stock corrections saved once'})

    def decision(self, user, data):
        with self.s.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            self.allowed(c, user, admin=True)
            key, digest, old = self.retry(c, user, data, 'decision')
            if old is not None:
                return old
            r = c.execute('SELECT * FROM rice_cases WHERE id=?', (required(data, 'case_id'),)).fetchone()
            qty = integer(data.get('quantity'), 1)
            decision = data.get('decision')
            reason = required(data, 'reason')
            if not r or qty > r['remaining'] or decision not in ('restock', 'repack', 'dispose') or data.get('inspected') is not True:
                raise Error('Inspect the record and choose a valid undecided quantity')
            if decision in ('restock', 'repack') and data.get('usable') is not True:
                raise Error('Confirm the rice is usable before restocking or repacking')
            if decision == 'dispose' and data.get('unusable') is not True:
                raise Error('Confirm the rice is unusable before disposal')
            delta = qty if decision in ('restock', 'repack') and not r['already_stocked'] else -qty if decision == 'dispose' and r['already_stocked'] else 0
            p = c.execute('SELECT * FROM rice_products WHERE id=?', (r['product_id'],)).fetchone()
            if delta:
                self.change(c, user, r['action_id'], r['product_id'], p['quantity'] + delta, decision, reason)
            c.execute('INSERT INTO rice_decisions VALUES(?,?,?,?,?,?,?,?)', (key, r['id'], decision, qty, delta, user['id'], reason, now()))
            remaining = r['remaining'] - qty
            c.execute('UPDATE rice_cases SET remaining=?,status=? WHERE id=?', (remaining, 'resolved' if remaining == 0 else 'partially resolved', r['id']))
            return self.save(c, key, digest, {'message': 'Owner decision saved', 'difference': delta, 'remaining': remaining})

    def users(self, user, data):
        with self.s.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            self.allowed(c, user, admin=True)
            uid = integer(data.get('user_id'), 1)
            target = c.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
            if not target or type(data.get('active')) is not bool or type(data.get('can_adjust')) is not bool:
                raise Error('Select an account and valid permissions')
            if uid == user['id'] and not data['active']:
                raise Error('You cannot deactivate your current administrator account')
            if c.execute('SELECT user_id FROM rice_accounts WHERE user_id=?', (uid,)).fetchone():
                c.execute('UPDATE rice_accounts SET active=?,can_adjust=? WHERE user_id=?', (int(data['active']), int(data['can_adjust']), uid))
            else:
                c.execute('INSERT INTO rice_accounts VALUES(?,?,?)', (uid, int(data['active']), int(data['can_adjust'])))
            if not data['active']:
                c.execute('DELETE FROM sessions WHERE user_id=?', (uid,))
            return {'message': 'Account permissions updated'}

    def product(self, user, data):
        with self.s.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            self.allowed(c, user, admin=True)
            creating = 'product_id' not in data
            if creating:
                key, digest, old = self.retry(c, user, data, 'create-product')
                if old is not None:
                    return old
                name = required(data, 'name')
                label = data.get('model_class')
                if label is None or label == '':
                    label = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
                cls = required({'model_class': label}, 'model_class')
                description = data.get('description') or '25 kg rice sack'
                description = required({'description': description}, 'description')
                pid = c.execute('SELECT COALESCE(MAX(id),0)+1 FROM rice_products').fetchone()[0]
                if c.execute('SELECT id FROM rice_products WHERE lower(name)=lower(?)', (name,)).fetchone():
                    raise Error('A rice product with this name already exists', 409)
            else:
                pid = integer(data.get('product_id'), 1)
                if not c.execute('SELECT id FROM rice_products WHERE id=?', (pid,)).fetchone():
                    raise Error('Rice product not found', 404)
                cls = required(data, 'model_class')
                description = required(data, 'description')
            sku = required(data, 'sku')
            if c.execute('SELECT id FROM rice_products WHERE id<>? AND (lower(sku)=lower(?) OR lower(model_class)=lower(?))', (pid, sku, cls)).fetchone():
                raise Error('SKU or scan class label is already used by another product', 409)
            if creating:
                c.execute('INSERT INTO rice_products(id,sku,name,model_class,description) VALUES(?,?,?,?,?)', (pid, sku, name, cls, description))
                return self.save(c, key, digest, {'message': 'Rice product added', 'product_id': pid})
            c.execute('UPDATE rice_products SET sku=?,description=?,model_class=? WHERE id=?', (sku, description, cls, pid))
            return {'message': 'Product details updated', 'product_id': pid}
