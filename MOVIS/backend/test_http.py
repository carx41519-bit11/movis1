import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from server import Handler
from service import Service

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        service=Service(Path(cls.temp.name)/'http.db')
        service.bootstrap('admin','test-password-http',True)
        class QuietHandler(Handler):
            def log_message(self,*args):pass
        QuietHandler.service=service
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()
    def request(self,path,data=None,token=None):
        headers={}
        if token:headers['Authorization']='Bearer '+token
        if data is not None:headers['Content-Type']='application/json'
        request=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(request,timeout=5) as response:return response.status,response.read().decode()
        except urllib.error.HTTPError as response:return response.code,response.read().decode()
    def login(self):
        code,body=self.request('/login',{'username':'admin','password':'test-password-http'})
        self.assertEqual(code,200);return json.loads(body)['token']
    def test_health_and_unauthorized_inventory(self):
        self.assertEqual(self.request('/health')[0],200)
        self.assertEqual(self.request('/inventory')[0],401)
    def test_web_dashboard_assets_and_path_restriction(self):
        for path,marker in [('/', 'ELDER JAY RICE MILL'),('/dashboard.js','function render()'),('/styles.css', '.sidebar'),('/favicon.svg','<svg')]:
            code,body=self.request(path)
            self.assertEqual(code,200)
            self.assertIn(marker,body)
        self.assertNotEqual(self.request('/../backend/schema.sql')[0],200)
    def test_login_inventory_csv_and_logout(self):
        token=self.login()
        code,body=self.request('/inventory',token=token);self.assertEqual(code,200);self.assertEqual(len(json.loads(body)['stock']),2)
        code,body=self.request('/reports/inventory?format=csv',token=token);self.assertEqual(code,200);self.assertIn('quantity',body)
        self.assertEqual(self.request('/logout',{},token)[0],200)
        self.assertEqual(self.request('/inventory',token=token)[0],401)
    def test_bad_payload_and_conflict_status(self):
        token=self.login()
        for endpoint in ['/returns','/catalog','/manual-adjustments','/scan-additions','/adjustments']:
            self.assertEqual(self.request(endpoint,{},token)[0],410)
        self.assertEqual(self.request('/v2/open',{'kind':'invalid','request_id':'invalid-kind'},token)[0],400)
        self.assertEqual(self.request('/v2/users',{'user_id':999,'active':True,'can_adjust':False},token)[0],400)

    def test_two_clients_share_scans_edits_and_returns(self):
        import base64,io,uuid
        from PIL import Image
        android=self.login();web=self.login()
        def post(path,payload,token=android):
            status,body=self.request(path,payload,token)
            self.assertEqual(status,200,body)
            return json.loads(body)
        def state(token=web,aid=None):
            status,body=self.request('/v2/state'+('?action_id='+aid if aid else ''),token=token)
            self.assertEqual(status,200)
            return json.loads(body)
        image=io.BytesIO();Image.new('RGB',(32,32),'white').save(image,format='JPEG')
        photo=base64.b64encode(image.getvalue()).decode()
        def action(kind,quantity):
            aid=post('/v2/open',{'kind':kind,'products':[1],'request_id':str(uuid.uuid4())})['action_id']
            iid=str(uuid.uuid4())
            post('/v2/image',{'action_id':aid,'image_id':iid,'source':'camera','zoom':1,'image':photo})
            revision=state(android,aid)['action']['revision']
            post('/v2/review',{'action_id':aid,'revision':revision,'image_id':iid,'checked':[{'product_id':1,'quantity':quantity}],'confirmed':True,'request_id':str(uuid.uuid4())})
            return aid,state(android,aid)['action']['revision']
        before=state()['products'][0]['quantity']
        aid,revision=action('stock-in',3)
        self.assertEqual(state()['products'][0]['quantity'],before)
        payload={'action_id':aid,'revision':revision,'request_id':str(uuid.uuid4()),'reason':'Receipt checked','unique_sacks':True}
        post('/v2/submit',payload);post('/v2/submit',payload)
        self.assertEqual(state()['products'][0]['quantity'],before+3)
        aid,revision=action('return',2)
        post('/v2/submit',{'action_id':aid,'revision':revision,'request_id':str(uuid.uuid4()),'reason':'Customer returned sacks','condition':'Unopened','already_stocked':False,'unique_sacks':True})
        self.assertEqual(state()['products'][0]['quantity'],before+3)
        case=next(r for r in state()['cases'] if r['action_id']==aid)
        payload={'case_id':case['id'],'request_id':str(uuid.uuid4()),'quantity':2,'decision':'restock','reason':'Owner inspected usable rice','inspected':True,'usable':True}
        post('/v2/decision',payload,web);post('/v2/decision',payload,web)
        self.assertEqual(state(android)['products'][0]['quantity'],before+5)

if __name__=='__main__':unittest.main()
