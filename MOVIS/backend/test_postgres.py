import base64
import io
import os
import unittest
import uuid
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, quote
from PIL import Image
from service import Service
from test_service import InventoryTests

@unittest.skipUnless(os.environ.get('MOVIS_TEST_DATABASE_URL'), 'Set MOVIS_TEST_DATABASE_URL to a disposable PostgreSQL database')
class PostgresInventoryTests(InventoryTests):
    def setUp(self):
        import psycopg
        self.url=os.environ['MOVIS_TEST_DATABASE_URL']
        self.schema='movis_test_'+uuid.uuid4().hex
        with psycopg.connect(self.url, autocommit=True) as con:
            con.execute('CREATE SCHEMA '+self.schema)
        self.addCleanup(self.drop_schema)
        parts=urlsplit(self.url)
        query=dict(parse_qsl(parts.query));query['options']='-c search_path='+self.schema
        self.service=Service(urlunsplit(parts._replace(query=urlencode(query,quote_via=quote))))
        self.service.bootstrap('admin','test-password-123',True)
        self.user=self.service.auth(self.service.login({'username':'admin','password':'test-password-123'})['token'])
        image=Image.new('RGB',(100,100),'white');out=io.BytesIO();image.save(out,format='JPEG')
        self.photo=base64.b64encode(out.getvalue()).decode()
    def tearDown(self):pass
    def test_migration_preserves_data_and_resets_sequences(self):
        import tempfile
        from pathlib import Path
        from migrate_sqlite_to_postgres import migrate, TABLES
        with self.service.connection() as con:
            con.raw.execute('TRUNCATE '+','.join(TABLES+['sessions'])+' RESTART IDENTITY CASCADE')
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source.db'
            local=Service(source);local.bootstrap('oldadmin','original-password-2026',True)
            counts=migrate(source,self.service.db)
            self.assertEqual(counts['stock'],2)
            account=self.service.auth(self.service.login({'username':'oldadmin','password':'original-password-2026'})['token'])
            item=self.service.catalog(account,{'kind':'item','sku':'AFTER-MIGRATION','name':'New item','model_class':'new_item'})
            self.assertEqual(item['id'],3)
            self.assertEqual(len(local.inventory()['items']),2)
            with self.assertRaises(ValueError):migrate(source,self.service.db)

    def test_hosted_factory_and_session_survive_restart(self):
        import json
        import os
        from unittest.mock import patch
        from webapp import create_app
        token=self.service.login({'username':'admin','password':'test-password-123'})['token']
        with patch.dict(os.environ,{'DATABASE_URL':self.service.db,'MOVIS_HTTPS_HOSTING':'1','MOVIS_MODE':'demo'}):
            for _ in range(2):
                app=create_app();statuses=[]
                body=b''.join(app({'REQUEST_METHOD':'GET','PATH_INFO':'/session','HTTP_AUTHORIZATION':'Bearer '+token},lambda s,h:statuses.append(s)))
                self.assertTrue(statuses[0].startswith('200'))
                self.assertEqual(json.loads(body)['username'],'admin')
    def drop_schema(self):
        import psycopg
        with psycopg.connect(self.url, autocommit=True) as con:
            con.execute('DROP SCHEMA '+self.schema+' CASCADE')

# Keep imported base tests from being discovered a second time.
del InventoryTests
if __name__=='__main__':unittest.main()

