import base64
import io
import json
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from service import Service, Error
from webapp import Application


class RiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.s = Service(Path(self.temp.name) / 'test.db')
        self.s.bootstrap('owner', 'test-owner-password')
        self.admin = self.s.auth(self.s.login({'username': 'owner', 'password': 'test-owner-password'})['token'])
        uid = self.s.create_user(self.admin, {'username': 'staff', 'password': 'test-staff-password', 'role': 'operator'})['id']
        self.staff = {'id': uid, 'username': 'staff', 'role': 'operator'}
        out = io.BytesIO()
        Image.new('RGB', (64, 64), 'white').save(out, format='JPEG')
        self.photo = base64.b64encode(out.getvalue()).decode()
        self.r = self.s.rice
        with self.s.connection() as c:
            c.execute('UPDATE rice_products SET quantity=20')

    def tearDown(self):
        self.temp.cleanup()

    def req(self, **data):
        return {'request_id': str(uuid.uuid4()), **data}

    def action(self, aid, user=None):
        return self.r.state(user or self.staff, aid)['action']

    def stock(self):
        return [p['quantity'] for p in self.r.state(self.staff)['products']]

    def open(self, kind='stock-in', products=None):
        return self.r.open(self.staff, self.req(kind=kind, products=products or [1, 2, 3]))['action_id']

    def image(self, aid, counts, iid=None):
        iid = iid or str(uuid.uuid4())
        self.r.image(self.staff, {'action_id': aid, 'image_id': iid, 'source': 'camera', 'zoom': 1, 'image': self.photo})
        self.r.review(self.staff, self.req(action_id=aid, revision=self.action(aid)['revision'], image_id=iid, checked=[{'product_id': p, 'quantity': q} for p, q in counts.items()], confirmed=True))
        return iid

    def complete(self, aid, **extra):
        return self.req(action_id=aid, revision=self.action(aid)['revision'], unique_sacks=True, reason='Verified test transaction', **extra)

    def count(self, counts):
        aid = self.open('count', list(counts))
        self.image(aid, counts)
        self.r.finish(self.staff, self.complete(aid, full_counts={str(p): True for p in counts}, zero_confirmed={str(p): True for p in counts}))
        return aid

    def test_multiple_images_deleted_excluded_and_retry(self):
        aid = self.open()
        for q in (4, 6, 5):
            self.image(aid, {1: q})
        deleted = self.image(aid, {1: 99})
        d = self.req(action_id=aid, revision=self.action(aid)['revision'], image_id=deleted)
        self.r.delete(self.staff, d)
        self.r.delete(self.staff, d)
        self.assertEqual(self.stock(), [20, 20, 20])
        payload = self.complete(aid)
        first = self.r.submit(self.staff, payload)
        self.assertEqual(self.r.submit(self.staff, payload), first)
        self.assertEqual(self.stock(), [35, 20, 20])
        with self.assertRaises(Error):
            self.r.submit(self.staff, {**payload, 'reason': 'Changed'})
        with self.assertRaises(Error):
            self.r.review(self.staff, self.req(action_id=aid, revision=0, image_id=deleted, checked=[], confirmed=True))

    def test_stock_out_all_or_nothing(self):
        aid = self.open('stock-out')
        self.image(aid, {1: 2, 2: 21})
        with self.assertRaises(Error):
            self.r.submit(self.staff, self.complete(aid))
        self.assertEqual(self.stock(), [20, 20, 20])
        self.assertEqual(self.r.state(self.admin)['history'], [])
        self.assertEqual(self.action(aid)['state'], 'open')

    def test_concurrent_stock_out_and_request_retry(self):
        aid = self.open('stock-out', [1])
        self.image(aid, {1: 15})
        payload = self.complete(aid)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.r.submit(self.staff, payload), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.stock()[0], 5)

    def test_count_save_finish_and_permission_then_adjust(self):
        aid = self.count({1: 18, 2: 22})
        self.assertEqual(self.stock(), [20, 20, 20])
        d = self.complete(aid, products=[1, 2], confirmed=True)
        with self.assertRaises(Error) as e:
            self.r.adjust(self.staff, d)
        self.assertEqual(e.exception.status, 403)
        self.r.users(self.admin, {'user_id': self.staff['id'], 'active': True, 'can_adjust': True})
        result = self.r.adjust(self.staff, d)
        self.assertEqual(self.r.adjust(self.staff, d), result)
        self.assertEqual(self.stock(), [18, 22, 20])
        with self.assertRaises(Error):
            self.r.adjust(self.staff, self.complete(aid, products=[1], confirmed=True))

    def test_stale_baseline_before_finish_and_after_finish(self):
        aid = self.open('count', [1])
        self.image(aid, {1: 18})
        with self.s.connection() as c:
            c.execute('UPDATE rice_products SET quantity=25,version=version+1 WHERE id=1')
        with self.assertRaises(Error):
            self.r.finish(self.staff, self.complete(aid, full_counts={'1': True}))
        self.r.refresh_count(self.staff, self.req(action_id=aid, revision=self.action(aid)['revision'], confirmed_review=True))
        with self.assertRaises(Error):
            self.r.finish(self.staff, self.complete(aid, full_counts={'1': True}))
        im = self.action(aid)['images'][0]
        self.r.review(self.staff, self.req(action_id=aid, revision=self.action(aid)['revision'], image_id=im['id'], checked=[{'product_id': 1, 'quantity': 18}], confirmed=True))
        self.r.finish(self.staff, self.complete(aid, full_counts={'1': True}))
        with self.s.connection() as c:
            c.execute('UPDATE rice_products SET quantity=26,version=version+1 WHERE id=1')
        with self.assertRaises(Error):
            self.r.adjust(self.admin, self.complete(aid, products=[1], confirmed=True))
        self.assertEqual(self.stock()[0], 26)

    def test_zero_requires_physical_confirmation(self):
        aid = self.open('count', [1])
        self.image(aid, {1: 0})
        with self.assertRaises(Error):
            self.r.finish(self.staff, self.complete(aid, full_counts={'1': True}))
        self.r.finish(self.staff, self.complete(aid, full_counts={'1': True}, zero_confirmed={'1': True}))
        self.assertEqual(self.stock()[0], 20)

    def test_incomplete_no_images_unchecked_and_invalid_quantities(self):
        aid = self.open()
        with self.assertRaises(Error):
            self.r.submit(self.staff, self.complete(aid))
        iid = str(uuid.uuid4())
        p = {'action_id': aid, 'image_id': iid, 'source': 'camera', 'zoom': 1, 'image': self.photo}
        self.r.image(self.staff, p)
        with self.assertRaises(Error):
            self.r.submit(self.staff, self.complete(aid))
        for qty in (-1, 1.5, '3', True):
            with self.assertRaises(Error):
                self.r.review(self.staff, self.req(action_id=aid, revision=self.action(aid)['revision'], image_id=iid, checked=[{'product_id': 1, 'quantity': qty}], confirmed=True))
        for source, zoom in [('gallery', 1), ('camera', 2)]:
            with self.assertRaises(Error):
                self.r.image(self.staff, {**p, 'source': source, 'zoom': zoom})
        self.assertEqual(self.stock(), [20, 20, 20])

    def test_image_retry_immutability_and_late_deleted_result(self):
        aid = self.open()
        iid = self.image(aid, {1: 2})
        before = self.action(aid)['revision']
        self.r.image(self.staff, {'action_id': aid, 'image_id': iid, 'source': 'camera', 'zoom': 1, 'image': self.photo})
        self.assertEqual(self.action(aid)['revision'], before)
        other = self.open()
        with self.assertRaises(Error):
            self.r.image(self.staff, {'action_id': other, 'image_id': iid, 'source': 'camera', 'zoom': 1, 'image': self.photo})
        # Delete from another request while inference is running.
        self.s.mode = 'yolo'
        workflow = self.r
        class Detector:
            def predict(self, *args, **kw):
                a = workflow.state(workflow_test.staff, aid)['action']
                workflow.delete(workflow_test.staff, workflow_test.req(action_id=aid, revision=a['revision'], image_id='late'))
                return [type('Result', (), {'boxes': []})()]
        workflow_test = self
        self.s.model = Detector()
        result = self.r.image(self.staff, {'action_id': aid, 'image_id': 'late', 'source': 'camera', 'zoom': 1, 'image': self.photo})
        self.assertTrue(result['deleted'])
        late = next(r for r in self.action(aid)['images'] if r['id'] == 'late')
        self.assertEqual(late['reviewed'], 0)
        self.assertEqual(late['raw'], [])

    def case(self, stocked, kind='return'):
        aid = self.open(kind, [1])
        self.image(aid, {1: 3})
        self.r.submit(self.staff, self.complete(aid, already_stocked=stocked, condition='Inspection required'))
        return next(r for r in self.r.state(self.admin)['cases'] if r['action_id'] == aid)

    def test_return_damage_stock_matrix_and_owner_only(self):
        for stocked, decision, delta in [(False, 'restock', 3), (True, 'restock', 0), (False, 'repack', 3), (True, 'repack', 0), (False, 'dispose', 0), (True, 'dispose', -3)]:
            before = self.stock()[0]
            case = self.case(stocked, 'damage' if stocked else 'return')
            self.assertEqual(self.stock()[0], before)
            d = self.req(case_id=case['id'], quantity=3, decision=decision, inspected=True, usable=True, unusable=True, reason='Owner inspected')
            with self.assertRaises(Error):
                self.r.decision(self.staff, d)
            result = self.r.decision(self.admin, d)
            self.assertEqual(self.r.decision(self.admin, d), result)
            self.assertEqual(self.stock()[0], before + delta)
            with self.assertRaises(Error):
                self.r.decision(self.admin, self.req(**{k:v for k,v in d.items() if k!='request_id'}))

    def test_partial_decision_inspection_and_overflow(self):
        case = self.case(False)
        d = self.req(case_id=case['id'], quantity=1, decision='restock', inspected=True, usable=True, reason='Owner inspected')
        with self.assertRaises(Error):
            self.r.decision(self.admin, {**d, 'inspected': False})
        self.r.decision(self.admin, d)
        with self.assertRaises(Error):
            self.r.decision(self.admin, {**d, 'request_id': 'over', 'quantity': 3})
        self.assertEqual(self.stock()[0], 21)
        self.assertEqual(next(c for c in self.r.state(self.admin)['cases'] if c['id']==case['id'])['remaining'], 2)

    def test_atomic_rollback_if_required_history_fails(self):
        aid = self.open()
        self.image(aid, {1: 2, 2: 3})
        original = self.r.change
        def fail(c, user, action, pid, *args):
            if pid == 2:
                raise RuntimeError('Simulated storage failure')
            return original(c, user, action, pid, *args)
        with patch.object(self.r, 'change', fail):
            with self.assertRaises(RuntimeError):
                self.r.submit(self.staff, self.complete(aid))
        self.assertEqual(self.stock(), [20, 20, 20])
        self.assertEqual(self.action(aid)['state'], 'open')
        self.assertEqual(self.r.state(self.admin)['history'], [])

    def test_failed_scan_can_retry_and_retain_original_results(self):
        aid=self.open()
        iid='failed-then-retried'
        self.s.mode='yolo'
        class Broken:
            def predict(self,*args,**kw):
                raise RuntimeError('Test model failure')
        self.s.model=Broken()
        payload={'action_id':aid,'image_id':iid,'source':'camera','zoom':1,'image':self.photo}
        with self.assertRaises(Error):
            self.r.image(self.staff,payload)
        self.assertEqual(self.action(aid)['images'][0]['model_version'],'failed')
        self.assertEqual(self.stock(),[20,20,20])
        self.s.mode='demo'
        self.r.image(self.staff,payload)
        self.assertEqual(self.action(aid)['images'][0]['model_version'],'synthetic-demo')
        self.assertEqual(len(self.action(aid)['images']),1)

    def test_inactive_account_and_staff_privacy(self):
        aid = self.open()
        self.assertEqual(self.r.state(self.admin)['actions'][0]['id'], aid)
        uid = self.s.create_user(self.admin, {'username': 'other', 'password': 'another-password-123', 'role': 'operator'})['id']
        other = {'id': uid, 'role': 'operator', 'username': 'other'}
        self.assertEqual(self.r.state(other)['actions'], [])
        with self.assertRaises(Error):
            self.r.state(other, aid)
        self.r.users(self.admin, {'user_id': self.staff['id'], 'active': False, 'can_adjust': False})
        with self.assertRaises(Error):
            self.r.open(self.staff, self.req(kind='count'))
        with self.assertRaises(Error):
            self.s.login({'username': 'staff', 'password': 'test-staff-password'})

    def test_complete_reports_preserve_raw_data_and_restrict_staff(self):
        aid=self.open('stock-in',[1])
        self.image(aid,{1:2})
        self.r.submit(self.staff,self.complete(aid))
        scans=self.r.report(self.admin,'scans')['rows']
        self.assertEqual(len(json.loads(scans[0]['raw'])),3)
        self.assertEqual(json.loads(scans[0]['checked'])[0]['quantity'],2)
        self.assertNotIn('image',scans[0])
        self.assertEqual(len(self.r.report(self.admin,'inventory')['rows']),3)
        self.assertEqual(self.r.report(self.admin,'history')['rows'][0]['difference'],2)
        for kind in ['inventory','history','counts','cases','decisions','scans']:
            with self.assertRaises(Error):
                self.r.report(self.staff,kind)

    def test_v2_http_staff_web_restriction_and_legacy_disabled(self):
        token = self.s.login({'username': 'staff', 'password': 'test-staff-password'})['token']
        app = Application(self.s)
        def call(path, data=None):
            raw=json.dumps(data).encode() if data is not None else b''
            status=[]
            env={'REQUEST_METHOD':'POST' if data is not None else 'GET','PATH_INFO':path,'HTTP_AUTHORIZATION':'Bearer '+token,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw)}
            out=b''.join(app(env,lambda s,h:status.append(s)))
            return int(status[0].split()[0]),json.loads(out)
        self.assertEqual(call('/v2/state')[0],200)
        self.assertEqual(call('/manual-adjustments',{})[0],410)
        self.assertEqual(call('/reports/movements')[0],403)
        with self.assertRaises(Error):
            self.s.login({'username':'staff','password':'test-staff-password','client':'web'})

    def test_manual_checked_entries_require_reasons_and_matching_products(self):
        aid=self.open('count',[1])
        self.image(aid,{1:2})
        d=self.complete(aid,full_counts={'1':True},manual=[{'product_id':1,'quantity':3,'reason':'Hidden sacks physically checked'}])
        self.r.finish(self.staff,d)
        self.assertEqual(self.action(aid)['comparison'][0]['count'],5)
        self.assertEqual(self.stock()[0],20)


if __name__=='__main__':
    unittest.main()
