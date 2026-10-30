import json, subprocess, tempfile, unittest, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
class PackTests(unittest.TestCase):
 def test_assets_and_original_preserved(self):
  # Exercise the production upgrade merger against an isolated payload directory.
  import shutil
  with tempfile.TemporaryDirectory() as td:
   t=Path(td);shutil.copy(ROOT/'tools/accessories-upgrade/merge.py',t/'merge.py');shutil.copytree(HERE/'staging-assets',t/'staging-assets');shutil.copytree(ROOT/'tools/accessories-upgrade/previous/staging-assets',t/'previous-assets')
   out=t/'pack.zip';subprocess.run(['python3',str(t/'merge.py'),str(ROOT/'rp/Elytrix-RP-1.21.zip'),str(out),'fresh'],check=True,stdout=subprocess.DEVNULL)
   with zipfile.ZipFile(ROOT/'rp/Elytrix-RP-1.21.zip') as a, zipfile.ZipFile(out) as b:
    self.assertEqual(len(set(b.namelist())-set(a.namelist())),13)
    font='assets/minecraft/font/default.json';old=json.loads(a.read(font));new=json.loads(b.read(font));self.assertEqual(new['providers'][1:],old['providers']);self.assertEqual(new['providers'][0]['chars'],['ꏠ'])
    for n in a.namelist():
     if n!=font:self.assertEqual(a.read(n),b.read(n),n)
    for bone in ('left_upper','right_upper','left_lower','right_lower'):
     model=json.loads(b.read('assets/modelengine/models/elytrix_kaneki_tentacles/'+bone+'.json'));ref=json.loads(b.read('assets/modelengine/items/elytrix_kaneki_tentacles/'+bone+'.json'))['model']['model']
     self.assertEqual(ref,'modelengine:elytrix_kaneki_tentacles/'+bone);self.assertEqual(model['textures']['0'],'modelengine:entity/models/elytrix_kaneki_tentacles')
     for e in model['elements']:
      self.assertTrue(all(-16<=n<=32 for n in e['from']+e['to']))
      if 'rotation' in e:self.assertIn(e['rotation']['angle'],(-45,-22.5,0,22.5,45))
   another=t/'new.zip';r=subprocess.run(['python3',str(t/'merge.py'),str(out),str(another),'fresh'],capture_output=True);self.assertNotEqual(r.returncode,0);self.assertFalse(another.exists())
if __name__=='__main__':unittest.main()
