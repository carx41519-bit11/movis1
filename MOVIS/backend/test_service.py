import base64
import io
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image
from service import Service, Error

class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.service=Service(Path(self.temp.name)/'test.db')
        self.service.bootstrap('admin','test-password-123',True)
        self.user=self.service.auth(self.service.login({'username':'admin','password':'test-password-123'})['token'])
        image=Image.new('RGB',(100,100),'white');out=io.BytesIO();image.save(out,format='JPEG')
        self.photo=base64.b64encode(out.getvalue()).decode()
    def tearDown(self):
        self.temp.cleanup()
    def scan(self):
        return self.service.scan(self.user,{'location_id':1,'image':self.photo})
    def adjustment(self,scan=None,**overrides):
        data={'scan_id':(scan or self.scan())['id'],'item_id':1,'location_id':1,'verified_quantity':4,'reason':'Physical count verified','confirmed':True,'complete_location_count':True,'request_key':'adjust-1'}
        return {**data,**overrides}
    def return_record(self,key='return-1'):
        return self.service.create_return(self.user,{'item_id':1,'location_id':1,'quantity':3,'reason':'Customer returned unopened goods','request_key':key})
    def stock(self):
        return next(r for r in self.service.inventory()['stock'] if r['item_id']==1)
    def test_login_and_expired_session(self):
        with self.assertRaises(Error):self.service.login({'username':'admin','password':'bad'})
        with self.service.connection() as con:con.execute('UPDATE sessions SET expires=0')
        with self.assertRaises(Error):self.service.auth('invalid')

    def test_legacy_password_upgrade_preserves_account(self):
        import hashlib
        salt='0123456789abcdef'
        legacy=salt+':'+hashlib.pbkdf2_hmac('sha256',b'test-password-123',salt.encode(),200000).hex()
        with self.service.connection() as con:con.execute('UPDATE users SET password=? WHERE id=?',(legacy,self.user['id']))
        result=self.service.login({'username':'admin','password':'test-password-123'})
        self.assertEqual(self.service.auth(result['token'])['id'],self.user['id'])
        with self.service.connection() as con:self.assertTrue(con.execute('SELECT password FROM users WHERE id=?',(self.user['id'],)).fetchone()[0].startswith('pbkdf2_sha256$600000$'))

    def test_server_idle_expiry_and_old_session_compatibility(self):
        import time
        token=self.service.login({'username':'admin','password':'test-password-123'})['token']
        with self.service.connection() as con:con.execute('UPDATE session_activity SET last_seen=? WHERE token=?',(time.time()-1801,token))
        with self.assertRaises(Error):self.service.auth(token)
        with self.service.connection() as con:
            con.execute('DELETE FROM session_activity WHERE token=?',(token,))
        # Pre-upgrade session rows receive activity tracking on first use.
        self.assertEqual(self.service.auth(token)['id'],self.user['id'])

    def test_rate_limit_survives_service_restart(self):
        from service import Service
        for _ in range(10):
            with self.assertRaises(Error):self.service.login({'username':'missing','password':'wrong'})
        with self.assertRaises(Error) as caught:Service(self.service.db).login({'username':'missing','password':'wrong'})
        self.assertEqual(caught.exception.status,429)

    def test_malformed_images_and_quantity_overflow_are_rejected(self):
        for value in (None,{},'not-base64'):
            with self.assertRaises(Error):self.service.scan(self.user,{'location_id':1,'image':value})
        with self.assertRaises(Error):self.service.manual_adjust(self.user,{'item_id':1,'location_id':1,'quantity':2147483648,'expected_version':0,'confirmed':True,'request_key':'overflow','reason':'Invalid'})
        self.assertEqual(self.stock()['quantity'],10)

    def test_scan_cannot_switch_from_addition_to_reconciliation(self):
        scan=self.scan()
        self.service.add_scan(self.user,{'scan_id':scan['id'],'items':[{'item_id':1,'quantity':2}],'reason':'Receiving','confirmed':True,'request_key':'purpose-add'})
        with self.assertRaises(Error) as caught:
            self.service.adjust(self.user,self.adjustment(scan,item_id=2,request_key='purpose-reconcile'))
        self.assertEqual(caught.exception.status,409)

    def test_new_account_password_whitespace_is_preserved(self):
        self.service.create_user(self.user,{'username':'spaces','password':'  passphrase-123  ','role':'viewer'})
        self.assertEqual(self.service.login({'username':'spaces','password':'  passphrase-123  '})['role'],'viewer')
        with self.assertRaises(Error):self.service.login({'username':'spaces','password':'passphrase-123'})
    def test_scan_is_synthetic_and_does_not_mutate_stock(self):
        before=self.stock();scan=self.scan()
        self.assertEqual(scan['mode'],'demo');self.assertIn('Synthetic',scan['warning'])
        self.assertEqual(before,self.stock());self.assertTrue(scan['detections'])
    def test_partial_count_and_unconfirmed_rejected(self):
        for field in ['confirmed','complete_location_count']:
            with self.assertRaises(Error):self.service.adjust(self.user,self.adjustment(**{field:False}))
        self.assertEqual(self.stock()['quantity'],10)
    def test_adjustment_history_and_exact_retry(self):
        payload=self.adjustment();first=self.service.adjust(self.user,payload);second=self.service.adjust(self.user,payload)
        self.assertEqual(first['id'],second['id']);self.assertEqual(first['difference'],-6)
        self.assertEqual(self.stock()['quantity'],4);self.assertEqual(len(self.service.report('movements')),1)
    def test_idempotency_key_cannot_be_repurposed(self):
        payload=self.adjustment();self.service.adjust(self.user,payload)
        with self.assertRaises(Error):self.service.adjust(self.user,{**payload,'verified_quantity':9})
    def test_same_scan_cannot_be_committed_twice(self):
        payload=self.adjustment();self.service.adjust(self.user,payload)
        with self.assertRaises(Error):self.service.adjust(self.user,{**payload,'request_key':'new-key'})
    def test_concurrent_scans_only_one_commits(self):
        a=self.adjustment(self.scan(),request_key='a');b=self.adjustment(self.scan(),request_key='b',verified_quantity=7)
        def commit(payload):
            try:self.service.adjust(self.user,payload);return 'ok'
            except Error as e:return e.status
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(commit,[a,b]))
        self.assertCountEqual(results,['ok',409]);self.assertEqual(len(self.service.report('adjustments')),1)
    def test_return_requires_inspection_and_explicit_restock(self):
        ret=self.return_record();self.assertEqual(self.stock()['quantity'],10)
        with self.assertRaises(Error):self.service.transition(self.user,ret['id'],{'status':'returned to available stock','confirmed_suitable':True})
        self.service.transition(self.user,ret['id'],{'status':'accepted'})
        with self.assertRaises(Error):self.service.transition(self.user,ret['id'],{'status':'returned to available stock'})
        payload={'status':'returned to available stock','confirmed_suitable':True}
        self.service.transition(self.user,ret['id'],payload);self.service.transition(self.user,ret['id'],payload)
        self.assertEqual(self.stock()['quantity'],13);self.assertEqual(len(self.service.report('return_events')),3)
    def test_concurrent_restock_is_once(self):
        ret=self.return_record();self.service.transition(self.user,ret['id'],{'status':'accepted'})
        with ThreadPoolExecutor(2) as pool:list(pool.map(lambda _:self.service.transition(self.user,ret['id'],{'status':'returned to available stock','confirmed_suitable':True}),[1,2]))
        self.assertEqual(self.stock()['quantity'],13);self.assertEqual(len(self.service.report('movements')),1)
    def test_damaged_goods_cannot_be_restocked(self):
        ret=self.return_record();self.service.transition(self.user,ret['id'],{'status':'damaged'})
        with self.assertRaises(Error):self.service.transition(self.user,ret['id'],{'status':'returned to available stock','confirmed_suitable':True})
        self.assertEqual(self.stock()['quantity'],10)
    def test_return_creation_retry_is_once(self):
        a=self.return_record();b=self.return_record();self.assertEqual(a['id'],b['id']);self.assertEqual(len(self.service.report('returns')),1)
    def test_viewer_cannot_mutate_and_operator_cannot_manage(self):
        self.service.create_user(self.user,{'username':'viewer','password':'viewer-password','role':'viewer'})
        viewer=self.service.auth(self.service.login({'username':'viewer','password':'viewer-password'})['token'])
        with self.assertRaises(Error):self.service.scan(viewer,{'location_id':1,'image':self.photo})
        with self.assertRaises(Error):self.service.catalog({'id':1,'role':'operator'},{'kind':'location','name':'B'})
    def test_invalid_images_and_quantities(self):
        with self.assertRaises(Error):self.service.scan(self.user,{'location_id':1,'image':'bad!'})
        for count in [-1,True,1.5]:
            with self.assertRaises(Error):self.service.adjust(self.user,self.adjustment(verified_quantity=count))
    def test_restock_invalidates_old_scan(self):
        payload=self.adjustment();ret=self.return_record();self.service.transition(self.user,ret['id'],{'status':'accepted'});self.service.transition(self.user,ret['id'],{'status':'returned to available stock','confirmed_suitable':True})
        with self.assertRaises(Error):self.service.adjust(self.user,payload)
    def test_catalog_accepts_future_training_classes(self):
        item=self.service.catalog(self.user,{'kind':'item','sku':'REAL-01','name':'Future item','model_class':'future_item'})
        location=self.service.catalog(self.user,{'kind':'location','name':'Real shelf'})
        self.service.catalog(self.user,{'kind':'stock','item_id':item['id'],'location_id':location['id']})
        self.assertTrue(any(r['model_class']=='future_item' for r in self.service.inventory()['items']))
    def addition(self,scan=None,**overrides):
        return {**{'scan_id':(scan or self.scan())['id'],'items':[{'item_id':1,'quantity':3},{'item_id':2,'quantity':1}],'reason':'Incoming goods','confirmed':True,'request_key':'photo-add-1'},**overrides}
    def test_photo_addition_is_additive_and_editable(self):
        payload=self.addition(items=[{'item_id':1,'quantity':7}]);result=self.service.add_scan(self.user,payload)
        self.assertEqual(self.stock()['quantity'],17);self.assertEqual(result['changes'][0]['difference'],7)
    def test_photo_add_retry_and_new_key_cannot_duplicate(self):
        payload=self.addition();self.service.add_scan(self.user,payload);self.service.add_scan(self.user,payload)
        self.assertEqual(self.stock()['quantity'],13)
        with self.assertRaises(Error):self.service.add_scan(self.user,{**payload,'request_key':'new'})
        with self.assertRaises(Error):self.service.add_scan(self.user,{**payload,'items':[{'item_id':1,'quantity':9}]})
    def test_unconfirmed_or_invalid_photo_add_is_atomic(self):
        with self.assertRaises(Error):self.service.add_scan(self.user,self.addition(confirmed=False))
        with self.assertRaises(Error):self.service.add_scan(self.user,self.addition(items=[{'item_id':1,'quantity':3},{'item_id':999,'quantity':1}]))
        self.assertEqual(self.stock()['quantity'],10)
    def test_concurrent_photo_adds_preserve_both_receipts(self):
        a=self.addition(self.scan(),request_key='a');b=self.addition(self.scan(),request_key='b')
        with ThreadPoolExecutor(2) as pool:list(pool.map(lambda p:self.service.add_scan(self.user,p),[a,b]))
        self.assertEqual(self.stock()['quantity'],16)
    def test_manual_change_and_stale_write_and_retry(self):
        payload={'item_id':1,'location_id':1,'quantity':6,'expected_version':0,'reason':'Manual correction','confirmed':True,'request_key':'manual-1'}
        self.service.manual_adjust(self.user,payload);self.service.manual_adjust(self.user,payload)
        self.assertEqual(self.stock()['quantity'],6)
        with self.assertRaises(Error):self.service.manual_adjust(self.user,{**payload,'request_key':'manual-2','quantity':8})
        with self.assertRaises(Error):self.service.manual_adjust({'id':1,'role':'viewer'},payload)

if __name__=='__main__':unittest.main()
