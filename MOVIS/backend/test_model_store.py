import hashlib, io, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from model_store import prepare_weights

class ModelStoreTests(unittest.TestCase):
    def test_demo_never_downloads_weights(self):
        with patch.dict(os.environ,{'MOVIS_MODE':'demo','MOVIS_WEIGHTS_URL':'https://example.com/model'},clear=True),patch('model_store.urlopen') as open_url:
            self.assertIsNone(prepare_weights());open_url.assert_not_called()
    def test_checksum_and_https_are_required(self):
        with patch.dict(os.environ,{'MOVIS_MODE':'yolo','MOVIS_WEIGHTS_URL':'http://example.com/model'},clear=True):
            with self.assertRaises(RuntimeError):prepare_weights()
    def test_verified_download_is_atomic_and_tampering_rejected(self):
        body=b'fake model bytes for storage contract only'
        class Response(io.BytesIO):
            def geturl(self):return 'https://example.com/model'
        with tempfile.TemporaryDirectory() as temp,patch('model_store.tempfile.gettempdir',return_value=temp):
            env={'MOVIS_MODE':'yolo','MOVIS_WEIGHTS_URL':'https://example.com/model','MOVIS_WEIGHTS_SHA256':hashlib.sha256(body).hexdigest()}
            with patch.dict(os.environ,env,clear=True),patch('model_store.urlopen',return_value=Response(body)):
                self.assertEqual(Path(prepare_weights()).read_bytes(),body)
            env['MOVIS_WEIGHTS_SHA256']='0'*64
            with patch.dict(os.environ,env,clear=True),patch('model_store.urlopen',return_value=Response(body)):
                with self.assertRaises(RuntimeError):prepare_weights()
            self.assertFalse((Path(temp)/'movis-models/best.pt.part').exists())
    def test_embedded_file_with_checksum(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'best.pt';file.write_bytes(b'contract fixture')
            with patch.dict(os.environ,{'MOVIS_MODE':'yolo','MOVIS_WEIGHTS':str(file),'MOVIS_WEIGHTS_SHA256':'0'*64},clear=True):
                with self.assertRaises(RuntimeError):prepare_weights()

if __name__=='__main__':unittest.main()
