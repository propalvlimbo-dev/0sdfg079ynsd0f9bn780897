#!/usr/bin/env python3
"""Integrity check: only intended entries are changed in the patched JARs."""
import io,subprocess,zipfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE='37ec54155b6493fc8cbe114d37d2a8a37299c993'
class BinaryTest(unittest.TestCase):
 def test_entry_integrity(self):
  expected=[('plugins/CloudQuests.jar',{'plugin.yml','cs/cloudstudio/deobf/Class047.class'},{'cs/cloudstudio/deobf/CakeSubPermission.class'}),('plugins/CloudEnchants.jar',{'cs/cloudstudio/recovered/cloudenchants/CustomEnchantManager.class'},{'cs/cloudstudio/recovered/cloudenchants/LegacyEnchantCompat.class'})]
  for name,changed,added in expected:
   with self.subTest(name=name):
    old=zipfile.ZipFile(io.BytesIO(subprocess.check_output(['git','show',f'{BASE}:{name}'],cwd=ROOT)));new=zipfile.ZipFile(ROOT/name)
    original={x for x in old.namelist() if not x.endswith('/')};current={x for x in new.namelist() if not x.endswith('/')}
    self.assertEqual(current-original,added);self.assertEqual(original-current,set());self.assertEqual({n for n in original if old.read(n)!=new.read(n)},changed)
    for f in added:self.assertEqual(int.from_bytes(new.read(f)[6:8],'big'),65)
 def test_egg_preserves_default_config(self):
  old=zipfile.ZipFile(io.BytesIO(subprocess.check_output(['git','show',f'{BASE}:plugins/ElytrixRandomEgg.jar'],cwd=ROOT)));new=zipfile.ZipFile(ROOT/'plugins/ElytrixRandomEgg.jar')
  self.assertEqual(old.read('config.yml'),new.read('config.yml'))
  self.assertEqual(int.from_bytes(new.read('org/smilestudio/smilerandomegg/SmileRandomEgg.class')[6:8],'big'),65)
if __name__=='__main__':unittest.main()
