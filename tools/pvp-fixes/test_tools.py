#!/usr/bin/env python3
import contextlib, io, os, sys, tarfile, tempfile, unittest, hashlib
from pathlib import Path
import free_preview, leaf_install

ROOT=Path(__file__).resolve().parents[2]
class FreeTest(unittest.TestCase):
 def test_only_rewards_5_onward_are_changed(self):
  source=(ROOT/'plugins/ElytrixFree/gui.yml').read_text(); proposed=free_preview.rewrite(source)
  self.assertEqual(source.split('  free5:\n')[0], proposed.split('  free5:\n')[0])
  for i,(_,_,points,kit) in free_preview.PLAN.items():
   section=proposed.split(f'  free{i}:\n')[1].split(f'  free{i+1}:\n')[0] if i<14 else proposed.split('  free14:\n')[1]
   self.assertIn(f"p give {{player}} {points}", section)
   if kit:self.assertIn(f'nkits:kit {kit} {{player}}', section)
  self.assertIn('nkits:kit angel {player}', proposed)
 def test_rejects_missing_and_duplicate_rewards(self):
  with self.assertRaises(ValueError): free_preview.rewrite('  free5:\n')

class LeafTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); d=Path(self.tmp.name)
  self.root=d/'server'; self.root.mkdir(); self.backup=d/'backups'; self.backup.mkdir(); (self.root/'server.jar').write_bytes(b'old kernel'); (self.root/'world').mkdir(); (self.root/'world'/'level.dat').write_bytes(b'world-data')
  self.oldargs=sys.argv; self.addCleanup(setattr,sys,'argv',self.oldargs)
  self.oldfetch=leaf_install.fetch_leaf; self.addCleanup(setattr,leaf_install,'fetch_leaf',self.oldfetch)
 def invoke(self,*flags):
  sys.argv=['leaf_install',str(self.root),str(self.backup),*flags]
  with contextlib.redirect_stdout(io.StringIO()): leaf_install.main()
 def test_preflight_does_not_change_anything(self):
  self.invoke(); self.assertEqual((self.root/'server.jar').read_bytes(),b'old kernel'); self.assertEqual(list(self.backup.iterdir()),[])
 def test_apply_requires_confirmation(self):
  with self.assertRaises(ValueError): self.invoke('--apply')
  self.assertEqual((self.root/'server.jar').read_bytes(),b'old kernel')
 def test_simulated_download_and_backup(self):
  leaf_install.fetch_leaf=lambda target: target.write_bytes(b'new kernel')
  self.invoke('--apply','--i-stopped-server-and-restart-loop','--i-backed-up-external-data','--i-understand-world-upgrade')
  self.assertEqual((self.root/'server.jar').read_bytes(),b'new kernel')
  archives=list(self.backup.glob('*.tar')); self.assertEqual(len(archives),1)
  with tarfile.open(archives[0]) as tar:
   self.assertEqual(tar.extractfile('server/server.jar').read(),b'old kernel')
   self.assertEqual(tar.extractfile('server/world/level.dat').read(),b'world-data')
 def test_invalid_download_cannot_replace_server(self):
  def bad(target): raise ValueError('sha mismatch')
  leaf_install.fetch_leaf=bad
  with self.assertRaises(ValueError): self.invoke('--apply','--i-stopped-server-and-restart-loop','--i-backed-up-external-data','--i-understand-world-upgrade')
  self.assertEqual((self.root/'server.jar').read_bytes(),b'old kernel')
 def test_fetch_validates_size_and_digest(self):
  original_open=leaf_install.urllib.request.urlopen; oldsize=leaf_install.SIZE; oldhash=leaf_install.SHA256
  self.addCleanup(setattr,leaf_install.urllib.request,'urlopen',original_open)
  self.addCleanup(setattr,leaf_install,'SIZE',oldsize); self.addCleanup(setattr,leaf_install,'SHA256',oldhash)
  leaf_install.urllib.request.urlopen=lambda *a,**k: io.BytesIO(b'leaf')
  leaf_install.SIZE=4; leaf_install.SHA256=hashlib.sha256(b'leaf').hexdigest()
  # The unmodified implementation is tested here, not the mock used in another test.
  leaf_install.fetch_leaf(self.backup/'verified.jar')
  self.assertEqual((self.backup/'verified.jar').read_bytes(),b'leaf')
  leaf_install.SHA256='0'*64
  with self.assertRaises(ValueError):leaf_install.fetch_leaf(self.backup/'bad.jar')
 def test_symlink_causes_refusal(self):
  (self.root/'link').symlink_to('/tmp')
  with self.assertRaises(ValueError): self.invoke('--apply','--i-stopped-server-and-restart-loop','--i-backed-up-external-data','--i-understand-world-upgrade')
  self.assertEqual((self.root/'server.jar').read_bytes(),b'old kernel')
if __name__=='__main__':unittest.main()
