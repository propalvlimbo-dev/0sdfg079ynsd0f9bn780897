import hashlib, importlib.util, os, shutil, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/accessories-install'))
import install
class TestInstall(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.d=Path(self.tmp.name);self.root=self.d/'server';self.back=self.d/'backup';self.back.mkdir();self.served=self.d/'RP/Elytrix-RP-1.21.zip';self.served.parent.mkdir()
  for n in ('plugins/ModelEngine/blueprints','plugins/ElytrixRP','rp'):(self.root/n).mkdir(parents=True)
  shutil.copy(ROOT/'plugins/ElytrixFreakModel.jar',self.root/'plugins/ElytrixFreakModel.jar')
  shutil.copy(ROOT/'plugins/ModelEngine-4.1.0.jar',self.root/'plugins/ModelEngine-4.1.0.jar')
  shutil.copy(ROOT/'plugins/ModelEngine/config.yml',self.root/'plugins/ModelEngine/config.yml')
  shutil.copy(ROOT/'plugins/ElytrixRP/config.yml',self.root/'plugins/ElytrixRP/config.yml')
  shutil.copy(ROOT/'rp/Elytrix-RP-1.21.zip',self.root/'rp/Elytrix-RP-1.21.zip');shutil.copy(self.root/'rp/Elytrix-RP-1.21.zip',self.served)
  for n in ('elytrix_angel_wings','elytrix_angel_halo'):(self.root/'plugins/ModelEngine/blueprints'/(n+'.bbmodel')).write_text('test')
  self.patches=[patch.object(install,'HERE',Path(os.environ.get('ACCESSORY_PACKAGE','/tmp/accessory-package'))),patch.object(install.core_safety,'check_stopped')]
  for p in self.patches:p.start();self.addCleanup(p.stop)
  self.jar=self.root/'plugins/ElytrixFreakModel.jar';self.rp=self.root/'rp/Elytrix-RP-1.21.zip';self.config=self.root/'plugins/ElytrixRP/config.yml';self.bp=self.root/'plugins/ModelEngine/blueprints/elytrix_kaneki_tentacles.bbmodel'
 def test_install_and_rollback(self):
  old={p:p.read_bytes() for p in (self.jar,self.rp,self.served,self.config)}
  install.install(self.root,self.served,self.back);self.assertTrue(self.bp.exists());self.assertEqual(install.sha(self.jar.read_bytes()),install.NEW_JAR)
  self.assertEqual(self.rp.read_bytes(),self.served.read_bytes());newsha=hashlib.sha1(self.rp.read_bytes()).hexdigest();self.assertIn(newsha,self.config.read_text())
  backup=next(self.back.iterdir());install.rollback(self.root,self.served,backup);self.assertFalse(self.bp.exists());self.assertEqual({p:p.read_bytes() for p in old},old)
 def test_mismatch_refused(self):
  old=self.jar.read_bytes();self.served.write_bytes(b'other')
  with self.assertRaises(ValueError):install.install(self.root,self.served,self.back)
  self.assertEqual(self.jar.read_bytes(),old);self.assertFalse(self.bp.exists());self.assertEqual(list(self.back.iterdir()),[])
 def test_active_refused(self):
  install.core_safety.check_stopped.side_effect=ValueError('server active')
  with self.assertRaises(ValueError):install.install(self.root,self.served,self.back)
  self.assertFalse(self.bp.exists());self.assertEqual(list(self.back.iterdir()),[])
 def test_failure_rolls_back(self):
  old={p:p.read_bytes() for p in (self.jar,self.rp,self.served,self.config)};real=install.atomic;calls=[0]
  def fail_once(*args):
   calls[0]+=1
   if calls[0]==3:raise OSError('simulated write failure')
   return real(*args)
  with patch.object(install,'atomic',side_effect=fail_once),self.assertRaises(OSError):install.install(self.root,self.served,self.back)
  self.assertFalse(self.bp.exists());self.assertEqual({p:p.read_bytes() for p in old},old)
 def test_bad_model_config_refused(self):
  cfg=self.root/'plugins/ModelEngine/config.yml';cfg.write_text(cfg.read_text().replace('Use-New-Rotation: false','Use-New-Rotation: true'))
  with self.assertRaises(ValueError):install.install(self.root,self.served,self.back)
  self.assertEqual(list(self.back.iterdir()),[])
 def test_rollback_refuses_modified(self):
  install.install(self.root,self.served,self.back);self.config.write_text(self.config.read_text()+'\n# changed\n')
  with self.assertRaises(ValueError):install.rollback(self.root,self.served,next(self.back.iterdir()))
  self.assertTrue(self.bp.exists());self.assertEqual(install.sha(self.jar.read_bytes()),install.NEW_JAR)
if __name__=='__main__':unittest.main()
