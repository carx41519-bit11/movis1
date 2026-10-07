import sys,secrets,json
from pathlib import Path
project=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(project/'backend'))
from service import Service
from server import Handler
from http.server import ThreadingHTTPServer
work=project/'.work'
work.mkdir(exist_ok=True)
db=work/('browser-'+secrets.token_hex(5)+'.db')
s=Service(db)
pw=secrets.token_urlsafe(20)
s.bootstrap('owner-test',pw)
u=s.auth(s.login({'username':'owner-test','password':pw})['token'])
s.create_user(u,{'username':'staff-test','password':pw,'role':'operator'})
(work/'browser-fixture.json').write_text(json.dumps({'username':'owner-test','staff':'staff-test','password':pw}))
from PIL import Image
Image.new('RGB',(64,64),'white').save(work/'test-image.jpg')
Handler.service=s
ThreadingHTTPServer(('127.0.0.1',8097),Handler).serve_forever()
