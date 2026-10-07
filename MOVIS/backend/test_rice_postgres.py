"""Run the paper's workflows in a disposable PostgreSQL schema when configured."""
import os
import unittest
import uuid
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qsl, urlencode, quote
import test_rice


@unittest.skipUnless(os.environ.get('MOVIS_TEST_DATABASE_URL'), 'Disposable PostgreSQL database not configured')
class RicePostgresTests(test_rice.RiceTests):
    def setUp(self):
        import psycopg
        self.pg_url=os.environ['MOVIS_TEST_DATABASE_URL']
        self.schema='rice_test_'+uuid.uuid4().hex
        with psycopg.connect(self.pg_url,autocommit=True) as c:
            c.execute('CREATE SCHEMA '+self.schema)
        self.addCleanup(self.drop_schema)
        parts=urlsplit(self.pg_url)
        query=dict(parse_qsl(parts.query));query['options']='-c search_path='+self.schema
        target=parts._replace(query=urlencode(query,quote_via=quote)).geturl()
        original=test_rice.Service
        with patch.object(test_rice,'Service',lambda ignored:original(target)):
            super().setUp()

    def drop_schema(self):
        import psycopg
        with psycopg.connect(self.pg_url,autocommit=True) as c:
            c.execute('DROP SCHEMA '+self.schema+' CASCADE')

    def test_new_workflow_migration_preserves_images_balances_and_outcomes(self):
        import json
        import psycopg
        from pathlib import Path
        from migrate_sqlite_to_postgres import migrate
        local=test_rice.Service(Path(self.temp.name)/'migration-source.db')
        local.bootstrap('migrated-owner','migration-test-password')
        account=local.auth(local.login({'username':'migrated-owner','password':'migration-test-password'})['token'])
        r=local.rice
        aid=r.open(account,self.req(kind='stock-in',products=[1]))['action_id']
        r.image(account,{'action_id':aid,'image_id':'migration-image','source':'camera','zoom':1,'image':self.photo})
        a=r.state(account,aid)['action']
        r.review(account,self.req(action_id=aid,revision=a['revision'],image_id='migration-image',checked=[{'product_id':1,'quantity':2}],confirmed=True))
        a=r.state(account,aid)['action']
        payload=self.req(action_id=aid,revision=a['revision'],reason='Migration fixture',unique_sacks=True)
        result=r.submit(account,payload)
        target_schema='rice_migration_'+uuid.uuid4().hex
        with psycopg.connect(self.pg_url,autocommit=True) as c:
            c.execute('CREATE SCHEMA '+target_schema)
        try:
            parts=urlsplit(self.pg_url)
            query=dict(parse_qsl(parts.query));query['options']='-c search_path='+target_schema
            target=parts._replace(query=urlencode(query,quote_via=quote)).geturl()
            counts=migrate(local.db,target)
            self.assertEqual(counts['rice_images'],1)
            migrated=test_rice.Service(target)
            user=migrated.auth(migrated.login({'username':'migrated-owner','password':'migration-test-password'})['token'])
            self.assertEqual(migrated.rice.state(user)['products'][0]['quantity'],2)
            self.assertEqual(migrated.rice.state(user,aid,True)['action']['images'][0]['image'],self.photo)
            self.assertEqual(migrated.rice.submit(user,payload),result)
            with self.assertRaises(ValueError):
                migrate(local.db,target)
        finally:
            with psycopg.connect(self.pg_url,autocommit=True) as c:
                c.execute('DROP SCHEMA '+target_schema+' CASCADE')
