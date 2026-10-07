"""Production WSGI entry point: gunicorn 'webapp:create_app()'."""
import csv
import io
import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from http.cookies import SimpleCookie, CookieError
from service import Service, Error

MAX_BODY = 9 * 1024 * 1024
WEB_DIR = Path(__file__).resolve().parent.parent / 'web'
STATIC = {'/':('index.html','text/html'), '/index.html':('index.html','text/html'),
          '/dashboard.js':('dashboard.js','text/javascript'), '/styles.css':('styles.css','text/css'),
          '/favicon.svg':('favicon.svg','image/svg+xml')}


class Application:
    def __init__(self, service):
        self.service=service
        self.attempts={}
        self.security_attempts={}
        self.lock=threading.Lock()

    def request_token(self,environ):
        auth=environ.get('HTTP_AUTHORIZATION','')
        if auth.startswith('Bearer '):return auth[7:]
        try:
            cookies=SimpleCookie(environ.get('HTTP_COOKIE',''))
            return cookies['MOVIS_SESSION'].value if 'MOVIS_SESSION' in cookies else ''
        except CookieError:return ''

    def dispatch(self, environ):
        method=environ.get('REQUEST_METHOD','GET')
        path=environ.get('PATH_INFO','/')
        if method=='GET' and path in STATIC:
            filename,mime=STATIC[path]
            return 200,(WEB_DIR/filename).read_text(encoding='utf-8'),mime
        if method=='GET' and path=='/health':
            # Also verifies that persistent storage is readable.
            with self.service.connection() as con:con.execute('SELECT count(*) FROM users').fetchone()
            return 200,{'status':'ok','mode':self.service.mode},'application/json'
        if method not in ['GET','POST']:raise Error('Method not allowed',405)
        data={}
        if method=='POST':
            origin=environ.get('HTTP_ORIGIN')
            if origin:
                parsed=urlsplit(origin)
                if parsed.scheme not in ('http','https') or parsed.netloc.casefold()!=environ.get('HTTP_HOST','').casefold():
                    raise Error('Cross-site requests are not allowed',403)
            if environ.get('HTTP_COOKIE') and not environ.get('HTTP_AUTHORIZATION') and not origin:
                raise Error('Browser requests require a same-site origin',403)
            length=int(environ.get('CONTENT_LENGTH') or 0)
            if length<1 or length>MAX_BODY:raise Error('Invalid request size',413)
            if environ.get('CONTENT_TYPE','').split(';')[0].strip()!='application/json':raise Error('Send application/json',415)
            raw=environ['wsgi.input'].read(length)
            if len(raw)!=length:raise Error('Incomplete request body')
            data=json.loads(raw)
            if not isinstance(data,dict):raise Error('Expected a JSON object')
        if path=='/login' and method=='POST':
            if data.get('client')=='web' and not environ.get('HTTP_ORIGIN'):
                raise Error('Browser sign-in requires a same-site origin',403)
            result=self.service.login(data)
            if data.get('client')=='web':
                result['_session_cookie']=result.pop('token');result['web_session']=True
            return 200,result,'application/json'
        user=self.service.auth(self.request_token(environ))
        if method=='POST' and path=='/account/security':
            return 200,self.service.account_security(user,data),'application/json'
        if path.startswith('/v2/'):
            if method=='GET' and path=='/v2/report':
                query=parse_qs(environ.get('QUERY_STRING',''))
                return 200,self.service.rice.report(user,query.get('kind',['history'])[0]),'application/json'
            if method=='GET' and path=='/v2/state':
                query=parse_qs(environ.get('QUERY_STRING',''))
                return 200,self.service.rice.state(user,query.get('action_id',[None])[0],query.get('images')==['1']),'application/json'
            actions={name:getattr(self.service.rice,name.replace('-', '_')) for name in ('open','image','review','delete','refresh-count','finish','submit','adjust','decision','users','product')}
            if method=='POST' and path[4:] in actions:
                return 200,actions[path[4:]](user,data),'application/json'
            raise Error('Endpoint not found',404)
        if method=='POST' and path in ('/scans','/scan-additions','/manual-adjustments','/adjustments','/returns','/catalog') or (method=='POST' and path.startswith('/returns/')):
            raise Error('Use the updated MOVIS workflow. Legacy stock actions are disabled.',410)
        if path.startswith('/reports/'):
            self.service.authorize(user,True)
        if method=='GET':
            if path=='/session':return 200,user,'application/json'
            if path=='/inventory':return 200,self.service.inventory(),'application/json'
            if path.startswith('/reports/'):
                rows=self.service.report(path.split('/')[-1])
                if parse_qs(environ.get('QUERY_STRING','')).get('format')==['csv']:
                    out=io.StringIO()
                    if rows:
                        writer=csv.DictWriter(out,fieldnames=rows[0].keys());writer.writeheader()
                        writer.writerows({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v) for k,v in row.items()} for row in rows)
                    return 200,out.getvalue(),'text/csv'
                return 200,{'rows':rows},'application/json'
        if method=='POST':
            actions={'/catalog':self.service.catalog,'/users':self.service.create_user,'/scans':self.service.scan,
                     '/scan-additions':self.service.add_scan,'/manual-adjustments':self.service.manual_adjust,
                     '/adjustments':self.service.adjust,'/returns':self.service.create_return}
            if path in actions:return 200,actions[path](user,data),'application/json'
            if path.startswith('/returns/'):
                return 200,self.service.transition(user,int(path.split('/')[-1]),data),'application/json'
            if path=='/logout':
                with self.service.connection() as con:con.execute('DELETE FROM sessions WHERE token=?',(self.request_token(environ),))
                return 200,{'message':'Signed out'},'application/json'
        raise Error('Endpoint not found',404)

    def __call__(self,environ,start_response):
        try:
            status,result,mime=self.dispatch(environ)
        except Error as exc:
            status,result,mime=exc.status,{'error':str(exc)},'application/json'
        except (ValueError,TypeError,KeyError,UnicodeError):
            status,result,mime=400,{'error':'Invalid request fields'},'application/json'
        except sqlite3.IntegrityError:
            status,result,mime=409,{'error':'Duplicate entry or invalid item/location reference'},'application/json'
        except Exception:
            logging.exception('Request failed')
            status,result,mime=500,{'error':'Server could not complete the request'},'application/json'
        session_cookie=result.pop('_session_cookie',None) if isinstance(result,dict) else None
        body=(json.dumps(result) if mime=='application/json' else result).encode('utf-8')
        from http import HTTPStatus
        headers=[('Content-Type',mime+'; charset=utf-8'),('Content-Length',str(len(body))),
                 ('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),
                 ('Referrer-Policy','same-origin'),('X-Frame-Options','DENY'),
                 ('Permissions-Policy','camera=(self), microphone=(), geolocation=()'),
                 ('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")]
        if os.environ.get('MOVIS_HTTPS_HOSTING')=='1':headers.append(('Strict-Transport-Security','max-age=31536000'))
        secure='; Secure' if os.environ.get('MOVIS_HTTPS_HOSTING')=='1' or environ.get('wsgi.url_scheme')=='https' else ''
        if session_cookie:
            headers.append(('Set-Cookie','MOVIS_SESSION='+session_cookie+'; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800'+secure))
        elif status==401 or (status==200 and environ.get('PATH_INFO') in ('/logout','/account/security')):
            headers.append(('Set-Cookie','MOVIS_SESSION=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'+secure))
        if status==429:headers.append(('Retry-After','60'))
        start_response(str(status)+' '+HTTPStatus(status).phrase,headers)
        return [body]


def create_app():
    """Existing databases are kept. A fresh database requires private admin credentials."""
    db=os.environ.get('DATABASE_URL')
    if db and not db.startswith(('postgres://','postgresql://')):
        raise RuntimeError('DATABASE_URL must be a PostgreSQL connection URL')
    if not db:
        if os.environ.get('MOVIS_HTTPS_HOSTING')=='1' and not os.environ.get('MOVIS_DB_PATH'):
            raise RuntimeError('Hosted service requires DATABASE_URL or an explicit persistent MOVIS_DB_PATH')
        db=Path(os.environ.get('MOVIS_DB_PATH','movis.db'))
        db.parent.mkdir(parents=True,exist_ok=True)
    from model_store import prepare_weights
    service=Service(db,os.environ.get('MOVIS_MODE','demo'),prepare_weights())
    with service.connection() as con:count=con.execute('SELECT count(*) FROM users').fetchone()[0]
    if not count:
        username=os.environ.get('MOVIS_ADMIN_USERNAME','').strip()
        password=os.environ.get('MOVIS_ADMIN_PASSWORD','')
        if not username or len(password)<12 or password=='movis-demo-2026':
            raise RuntimeError('First startup requires MOVIS_ADMIN_USERNAME and a new MOVIS_ADMIN_PASSWORD (12+ characters). Do not use the public demo password.')
        service.bootstrap(username,password,demo=os.environ.get('MOVIS_SEED_DEMO')=='1')
    return Application(service)
