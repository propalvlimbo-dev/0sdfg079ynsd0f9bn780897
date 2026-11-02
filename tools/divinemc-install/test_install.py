import importlib.util
import io
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

spec=importlib.util.spec_from_file_location('installer',Path(__file__).with_name('install.py'))
i=importlib.util.module_from_spec(spec);spec.loader.exec_module(i)


def jar_bytes():
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\n')
        z.writestr('binary','dummy')
    return out.getvalue()

class TestInstaller(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.base=Path(self.temp.name)
        self.root=self.base/'server';self.root.mkdir();self.back=self.base/'backup';self.back.mkdir()
        (self.root/'server.jar').write_bytes(b'old server');(self.root/'important.db').write_bytes(b'player-data')
        self.new=jar_bytes()
        self.patchers=[mock.patch.object(i,'SIZE',len(self.new)),mock.patch.object(i,'SHA256',hashlib.sha256(self.new).hexdigest()),mock.patch.object(i,'check_stopped'),mock.patch.object(i.urllib.request,'urlopen',side_effect=lambda *a,**kw:io.BytesIO(self.new))]
        for p in self.patchers:p.start();self.addCleanup(p.stop)
        self.addCleanup(self.temp.cleanup)
    def test_install_preserves_data_and_backups(self):
        i.install(self.root,self.back)
        self.assertEqual((self.root/'server.jar').read_bytes(),self.new)
        self.assertEqual((self.root/'important.db').read_bytes(),b'player-data')
        self.assertEqual((self.root/'divinemc.yml').read_bytes(),i.CONFIG.read_bytes())
        dirs=list(self.back.glob('divinemc-core-*'));self.assertEqual(len(dirs),1)
        self.assertEqual((dirs[0]/'server.jar').read_bytes(),b'old server')
    def test_no_overwrite_existing_config(self):
        (self.root/'divinemc.yml').write_text('custom: true\n')
        with self.assertRaises(ValueError):i.install(self.root,self.back)
        self.assertEqual((self.root/'server.jar').read_bytes(),b'old server')
        self.assertEqual((self.root/'divinemc.yml').read_text(),'custom: true\n')
    def test_bad_download_never_changes_server(self):
        with mock.patch.object(i,'SHA256','0'*64),self.assertRaises(ValueError):i.install(self.root,self.back)
        self.assertEqual((self.root/'server.jar').read_bytes(),b'old server')
        self.assertFalse((self.root/'divinemc.yml').exists())
    def test_no_jar_symlink(self):
        (self.root/'server.jar').unlink();(self.root/'server.jar').symlink_to(self.base/'elsewhere')
        with self.assertRaises(ValueError):i.install(self.root,self.back)
    def test_stopped_check_refusal_no_change(self):
        i.check_stopped.side_effect=ValueError('running')
        with self.assertRaises(ValueError):i.install(self.root,self.back)
        self.assertEqual((self.root/'server.jar').read_bytes(),b'old server')
        self.assertFalse((self.root/'divinemc.yml').exists())
    def test_replace_failure_removes_created_config(self):
        with mock.patch.object(i,'atomic_bytes',side_effect=OSError('failed')),self.assertRaises(OSError):i.install(self.root,self.back)
        self.assertEqual((self.root/'server.jar').read_bytes(),b'old server')
        self.assertFalse((self.root/'divinemc.yml').exists())
    def test_zip_invalid_even_with_matching_hash(self):
        bad=b'not a jar'
        with mock.patch.object(i,'SIZE',len(bad)),mock.patch.object(i,'SHA256',hashlib.sha256(bad).hexdigest()),mock.patch.object(i.urllib.request,'urlopen',return_value=io.BytesIO(bad)),self.assertRaises(zipfile.BadZipFile):i.install(self.root,self.back)
        self.assertEqual((self.root/'server.jar').read_bytes(),b'old server')
    def test_refuse_backup_inside_root(self):
        inside=self.root/'backup';inside.mkdir()
        with self.assertRaises(ValueError):i.install(self.root,inside)
    def test_config_integrity(self):
        with mock.patch.object(i,'CONFIG_SHA256','f'*64),self.assertRaises(ValueError):i.install(self.root,self.back)
        self.assertEqual((self.root/'server.jar').read_bytes(),b'old server')

if __name__=='__main__':unittest.main()
