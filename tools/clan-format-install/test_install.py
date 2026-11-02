import os, tempfile, unittest
from pathlib import Path
from unittest import mock
import install

class TestInstall(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        p=Path(self.tmp.name);self.root=p/'server';self.back=p/'back';self.back.mkdir();self.config=self.root/'plugins/NClans/config.yml';self.config.parent.mkdir(parents=True)
        self.old=b'# private config\r\nclanNameFormat: "&8[%clan%&8]" # keep\r\nclanChatPrefix: "[Clan]"\r\n';self.config.write_bytes(self.old)
        self.check=mock.patch.object(install.core_safety,'check_stopped');self.check.start();self.addCleanup(self.check.stop)
    def test_expected_change_and_private_backup(self):
        install.install(self.root,self.back)
        self.assertEqual(self.config.read_bytes(),self.old.replace(b'&8[%clan%&8]',b'%clan%'))
        b=list(self.back.glob('nclans-format-*/config.yml'));self.assertEqual(len(b),1);self.assertEqual(b[0].read_bytes(),self.old);self.assertEqual(b[0].stat().st_mode & 0o777,0o600)
    def test_already_fixed(self):
        self.config.write_bytes(self.old.replace(b'&8[%clan%&8]',b'%clan%'))
        install.install(self.root,self.back);self.assertEqual(list(self.back.iterdir()),[])
    def test_custom_and_duplicate_refused(self):
        for raw in (self.old.replace(b'&8[%clan%&8]',b'[%clan%]'),self.old+b'clanNameFormat: "%clan%"\n'):
            self.config.write_bytes(raw)
            with self.assertRaises(ValueError):install.install(self.root,self.back)
            self.assertEqual(self.config.read_bytes(),raw)
    def test_symlink_refused(self):
        self.config.unlink();self.config.symlink_to(self.back)
        with self.assertRaises(ValueError):install.install(self.root,self.back)
    def test_active_refused(self):
        install.core_safety.check_stopped.side_effect=ValueError('active')
        with self.assertRaises(ValueError):install.install(self.root,self.back)
        self.assertEqual(self.config.read_bytes(),self.old)
    def test_replacement_failed_preserves_file(self):
        with mock.patch.object(install.os,'replace',side_effect=OSError('failure')),self.assertRaises(OSError):install.install(self.root,self.back)
        self.assertEqual(self.config.read_bytes(),self.old)
        self.assertEqual(list(self.config.parent.glob('.nclans-format-*')),[])

if __name__=='__main__':unittest.main()
