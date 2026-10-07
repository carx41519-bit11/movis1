import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from service import Service
from webapp import Application, create_app

class CloudTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.db=Path(self.temp.name)/'persistent.db'
        self.service=Service(self.db);self.service.bootstrap('cloudadmin','private-password-2026',True)
        self.app=Application(self.service)
    def tearDown(self):self.temp.cleanup()
    def request(self,path,body=None,token=None,cookie=None,origin=None):
        raw=json.dumps(body).encode() if body is not None else b'';status=[]
        environ={'REQUEST_METHOD':'POST' if body is not None else 'GET','PATH_INFO':path,'CONTENT_LENGTH':str(len(raw)), 'CONTENT_TYPE':'application/json','wsgi.input':io.BytesIO(raw),'HTTP_AUTHORIZATION':'Bearer '+token if token else ''}
        environ['HTTP_HOST']='movis.example'
        if cookie:environ['HTTP_COOKIE']=cookie
        if origin:environ['HTTP_ORIGIN']=origin
        output=b''.join(self.app(environ,lambda s,h:status.append((s,dict(h)))))
        return int(status[0][0].split()[0]),output,status[0][1]
    def login(self):
        status,body,_=self.request('/login',{'username':'cloudadmin','password':'private-password-2026'});self.assertEqual(status,200);return json.loads(body)['token']
    def test_static_assets_health_and_auth(self):
        for path in ['/','/dashboard.js','/styles.css','/favicon.svg','/health']:self.assertEqual(self.request(path)[0],200)
        self.assertEqual(self.request('/inventory')[0],401)
        self.assertEqual(self.request('/../backend/schema.sql')[0],401)

    def test_web_cookie_is_httponly_and_android_bearer_is_compatible(self):
        with patch.dict(os.environ,{'MOVIS_HTTPS_HOSTING':'1'}):
            status,body,headers=self.request('/login',{'client':'web','username':'cloudadmin','password':'private-password-2026'},origin='https://movis.example')
        self.assertEqual(status,200);self.assertNotIn('token',json.loads(body))
        cookie=headers['Set-Cookie'].split(';')[0]
        for flag in ('HttpOnly','SameSite=Strict','Secure'):self.assertIn(flag,headers['Set-Cookie'])
        self.assertEqual(self.request('/session',cookie=cookie)[0],200)
        self.assertEqual(self.request('/logout',{},cookie=cookie)[0],403)
        self.assertEqual(self.request('/logout',{},cookie=cookie,origin='https://movis.example')[0],200)
        self.assertEqual(self.request('/session',cookie=cookie)[0],401)
        token=self.login();self.assertEqual(self.request('/inventory',token=token)[0],200)
    def test_write_persists_after_restart_and_logout_revokes(self):
        token=self.login()
        payload={'product_id':1,'sku':'RICE-SIN-25','description':'Persisted 25 kg sack detail','model_class':'sinandomeng'}
        self.assertEqual(self.request('/v2/product',payload,token)[0],200)
        self.app=Application(Service(self.db))
        status,body,_=self.request('/v2/state',token=token);self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['products'][0]['description'],'Persisted 25 kg sack detail')
        self.assertEqual(self.request('/logout',{},token)[0],200)
        self.assertEqual(self.request('/v2/state',token=token)[0],401)

    def test_factory_never_reinitializes_existing_database(self):
        with patch.dict(os.environ,{'MOVIS_DB_PATH':str(self.db),'MOVIS_MODE':'demo','MOVIS_ADMIN_USERNAME':'ignored','MOVIS_ADMIN_PASSWORD':'another-password-2026'}):
            app=create_app()
            with app.service.connection() as con:self.assertEqual(con.execute('SELECT username FROM users').fetchone()[0],'cloudadmin')
    def test_fresh_factory_requires_private_password(self):
        with patch.dict(os.environ,{'MOVIS_DB_PATH':str(Path(self.temp.name)/'fresh.db'),'MOVIS_MODE':'demo','MOVIS_ADMIN_USERNAME':'admin','MOVIS_ADMIN_PASSWORD':'movis-demo-2026'}):
            with self.assertRaises(RuntimeError):create_app()
        with patch.dict(os.environ,{'MOVIS_DB_PATH':str(Path(self.temp.name)/'fresh.db'),'MOVIS_MODE':'demo','MOVIS_ADMIN_USERNAME':'admin','MOVIS_ADMIN_PASSWORD':'brand-new-password-2026'}):
            app=create_app()
            with app.service.connection() as con:self.assertEqual(con.execute('SELECT count(*) FROM items').fetchone()[0],0)
    def test_headers_invalid_quantities_and_stale_conflict(self):
        token=self.login();status,body,headers=self.request('/v2/state',token=token)
        self.assertEqual(headers['X-Frame-Options'],'DENY');self.assertIn("script-src 'self'",headers['Content-Security-Policy'])
        for products in [[-1],[True],[1,1],[]]:
            self.assertEqual(self.request('/v2/open',{'kind':'count','products':products,'request_id':'invalid-products'},token)[0],400)
        self.assertEqual(self.request('/manual-adjustments',{},token)[0],410)

    def test_login_rate_limit(self):
        for _ in range(10):self.request('/login',{'username':'cloudadmin','password':'bad'})
        self.assertEqual(self.request('/login',{'username':'cloudadmin','password':'bad'})[0],429)

    def test_session_restore_and_expiry(self):
        token=self.login()
        status,body,_=self.request('/session',token=token)
        self.assertEqual(status,200)
        account=json.loads(body)
        self.assertEqual(account['username'],'cloudadmin')
        self.assertEqual(account['role'],'admin')
        self.assertNotIn('password',account)
        with self.service.connection() as con:
            con.execute('UPDATE sessions SET expires=0 WHERE token=?',(token,))
        self.assertEqual(self.request('/session',token=token)[0],401)

    def test_password_change_requires_password_and_revokes_all_devices(self):
        first=self.login();second=self.login()
        payload={'action':'change_password','current_password':'wrong','new_password':'new-private-password-2026'}
        self.assertEqual(self.request('/account/security',payload,first)[0],403)
        self.assertEqual(self.request('/session',token=second)[0],200)
        payload['current_password']='private-password-2026'
        payload['new_password']='short'
        self.assertEqual(self.request('/account/security',payload,first)[0],400)
        payload['new_password']='new-private-password-2026'
        self.assertEqual(self.request('/account/security',payload,first)[0],200)
        for token in (first,second):self.assertEqual(self.request('/session',token=token)[0],401)
        self.assertEqual(self.request('/login',{'username':'cloudadmin','password':'private-password-2026'})[0],401)
        self.assertEqual(self.request('/login',{'username':'cloudadmin','password':payload['new_password']})[0],200)

    def test_revoke_is_scoped_to_own_account_and_rate_limited(self):
        admin=self.login()
        self.service.create_user(self.service.auth(admin),{'username':'reader','password':'reader-password-2026','role':'viewer'})
        reader=self.service.login({'username':'reader','password':'reader-password-2026'})['token']
        payload={'action':'revoke_sessions','current_password':'reader-password-2026'}
        self.assertEqual(self.request('/account/security',payload,reader)[0],200)
        self.assertEqual(self.request('/session',token=reader)[0],401)
        self.assertEqual(self.request('/session',token=admin)[0],200)
        for _ in range(5):self.assertEqual(self.request('/account/security',{'action':'revoke_sessions','current_password':'wrong'},admin)[0],403)
        self.assertEqual(self.request('/account/security',{'action':'revoke_sessions','current_password':'wrong'},admin)[0],429)

    def test_cross_origin_post_blocked_and_permissions_header(self):
        raw=b'{}';status=[]
        environ={'REQUEST_METHOD':'POST','PATH_INFO':'/login','CONTENT_LENGTH':'2','CONTENT_TYPE':'application/json','wsgi.input':io.BytesIO(raw),'HTTP_ORIGIN':'https://evil.example','HTTP_HOST':'movis.example'}
        self.app(environ,lambda s,h:status.append(s))
        self.assertTrue(status[0].startswith('403'))
        raw=json.dumps({'username':'cloudadmin','password':'private-password-2026'}).encode()
        environ.update(HTTP_ORIGIN='https://movis.example',CONTENT_LENGTH=str(len(raw)))
        environ['wsgi.input']=io.BytesIO(raw);status.clear()
        self.app(environ,lambda s,h:status.append(s))
        self.assertTrue(status[0].startswith('200'))
        self.assertIn('microphone=()',self.request('/')[2]['Permissions-Policy'])

if __name__=='__main__':unittest.main()
