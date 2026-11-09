import hashlib, importlib.util, io, sys, tempfile, unittest, zipfile
from pathlib import Path
from unittest import mock

spec=importlib.util.spec_from_file_location('kbi',Path(__file__).with_name('install.py'))
i=importlib.util.module_from_spec(spec);spec.loader.exec_module(i)

def plugin(name='KnockbackSync',main=True):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        z.writestr('plugin.yml','name: '+name+'\n')
        if main:z.writestr('me/caseload/knockbacksync/BukkitLoaderPlugin.class',b'class')
    return b.getvalue()

class TestInstall(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'server';self.root.mkdir();self.plugins=self.root/'plugins';self.plugins.mkdir();(self.root/'server.jar').write_bytes(b'old core')
        self.config=self.plugins/'KnockbackSync';self.config.mkdir();(self.config/'config.yml').write_text('enabled: false\n')
        self.content=plugin()
        for p in (mock.patch.object(i,'SIZE',len(self.content)),mock.patch.object(i,'SHA512',hashlib.sha512(self.content).hexdigest()),mock.patch.object(i.safety,'check_stopped'),mock.patch.object(i.urllib.request,'urlopen',side_effect=lambda *a,**k:io.BytesIO(self.content))):
            p.start();self.addCleanup(p.stop)
    def test_installs_without_overwriting_config(self):
        i.install(self.root)
        self.assertEqual((self.plugins/i.FILENAME).read_bytes(),self.content)
        self.assertEqual((self.config/'config.yml').read_text(),'enabled: false\n')
        self.assertEqual((self.root/'server.jar').read_bytes(),b'old core')
    def test_existing_plugin_detected_by_descriptor(self):
        (self.plugins/'renamed.jar').write_bytes(plugin('KnockbackSync'))
        with self.assertRaises(ValueError):i.install(self.root)
        self.assertFalse((self.plugins/i.FILENAME).exists())
    def test_bad_hash(self):
        with mock.patch.object(i,'SHA512','0'*128),self.assertRaises(ValueError):i.install(self.root)
        self.assertFalse((self.plugins/i.FILENAME).exists())
        self.assertFalse(list(self.plugins.glob('.knockbacksync-*')))
    def test_wrong_identity_even_when_hash_matches(self):
        wrong=plugin('Other');h=hashlib.sha512(wrong).hexdigest()
        with mock.patch.object(i,'SIZE',len(wrong)),mock.patch.object(i,'SHA512',h),mock.patch.object(i.urllib.request,'urlopen',return_value=io.BytesIO(wrong)),self.assertRaises(ValueError):i.install(self.root)
        self.assertFalse((self.plugins/i.FILENAME).exists())
    def test_active_server_refused(self):
        i.safety.check_stopped.side_effect=ValueError('running')
        with self.assertRaises(ValueError):i.install(self.root)
        self.assertFalse((self.plugins/i.FILENAME).exists())
    def test_config_symlink_refused(self):
        (self.config/'config.yml').unlink();self.config.rmdir();self.config.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):i.install(self.root)
    def test_bad_plugin_file_refuses(self):
        (self.plugins/'broken.jar').write_text('not a jar')
        with self.assertRaises(ValueError):i.install(self.root)
        self.assertFalse((self.plugins/i.FILENAME).exists())

if __name__=='__main__':unittest.main()
