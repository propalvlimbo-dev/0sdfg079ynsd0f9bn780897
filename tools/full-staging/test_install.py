#!/usr/bin/env python3
import importlib.util, pathlib, shutil, subprocess, sys, tempfile, unittest
HERE=pathlib.Path(__file__).resolve().parent; REPO=HERE.parents[1]
spec=importlib.util.spec_from_file_location('install',HERE/'install.py');mod=importlib.util.module_from_spec(spec);sys.path.insert(0,str(HERE));spec.loader.exec_module(mod)
class Test(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=pathlib.Path(self.t.name)/'server';self.root.mkdir();self.bundle=pathlib.Path(self.t.name)/'bundle';self.bundle.mkdir()
  for n in ('install.py','free_preview.py'):shutil.copy(HERE/n,self.bundle/n)
  for rel in mod.NEW:
   out=self.bundle/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy(REPO/rel,out)
  for rel in list(mod.EXPECTED)+['plugins/BCases/prizes.yml']+[f'plugins/nKits/Kits/{k}.yml' for k in ('rabbit','hydra','cobra','god','angel','dragon')]:
   p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(subprocess.check_output(['git','show','HEAD:'+rel],cwd=REPO))
 def runit(self,*args):return subprocess.run([sys.executable,str(self.bundle/'install.py'),str(self.root),*args],text=True,capture_output=True)
 def test_preview_and_apply(self):
  r=self.runit();self.assertEqual(r.returncode,0,r.stderr);self.assertFalse((self.root/'plugins/ElytrixGodPickup.jar').exists())
  self.assertNotEqual(self.runit('--apply').returncode,0)
  r=self.runit('--apply','--stopped');self.assertEqual(r.returncode,0,r.stderr)
  for rel in mod.NEW:self.assertEqual((self.root/rel).read_bytes(),(self.bundle/rel).read_bytes())
  self.assertIn('randomeggbuy',(self.root/mod.SPAWNERS).read_text());self.assertIn('p give {player} 300',(self.root/mod.FREE).read_text());self.assertIn('angel {player}',(self.root/mod.FREE).read_text());self.assertIn('Защита IV',(self.root/mod.END).read_text())
  backup=list((self.root/'elytrix-test-backups').glob('partial-*'));self.assertEqual(len(backup),1)
  for rel in mod.EXPECTED:
   if rel in mod.NEW or rel in (mod.SPAWNERS,mod.END,mod.CLAN,mod.FREE):self.assertTrue((backup[0]/rel).exists())
 def test_guard_fails_without_mutation(self):
  (self.root/'plugins/CakeSub-1.0-SNAPSHOT.jar').write_bytes(b'drift');old=(self.root/mod.SPAWNERS).read_bytes()
  r=self.runit('--apply','--stopped');self.assertNotEqual(r.returncode,0);self.assertIn('hash mismatch',r.stderr);self.assertEqual((self.root/mod.SPAWNERS).read_bytes(),old);self.assertFalse((self.root/'elytrix-test-backups').exists())
 def test_symlink_is_rejected(self):
  p=self.root/'plugins/ElytrixRandomEgg.jar';p.unlink();p.symlink_to('/dev/null');self.assertNotEqual(self.runit().returncode,0)
if __name__=='__main__':unittest.main()
