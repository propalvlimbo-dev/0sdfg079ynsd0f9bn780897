import json, subprocess, tempfile, unittest, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
class PackTests(unittest.TestCase):
 def test_assets_and_original_preserved(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)/'new.zip'; subprocess.run(['python3',str(HERE/'merge_staging_pack.py'),str(ROOT/'rp/Elytrix-RP-1.21.zip'),str(out)],check=True,stdout=subprocess.DEVNULL)
   with zipfile.ZipFile(ROOT/'rp/Elytrix-RP-1.21.zip') as a, zipfile.ZipFile(out) as b:
    self.assertEqual(len(set(b.namelist())-set(a.namelist())),12)
    for n in a.namelist():self.assertEqual(a.read(n),b.read(n),n)
    for bone in ('left_upper','right_upper','left_lower','right_lower'):
     model=json.loads(b.read('assets/modelengine/models/elytrix_kaneki_tentacles/'+bone+'.json'))
     ref=json.loads(b.read('assets/modelengine/items/elytrix_kaneki_tentacles/'+bone+'.json'))['model']['model']
     self.assertEqual(ref,'modelengine:elytrix_kaneki_tentacles/'+bone)
     self.assertEqual(model['textures']['0'],'modelengine:entity/models/elytrix_kaneki_tentacles')
     for e in model['elements']:
      self.assertTrue(all(-16<=n<=32 for n in e['from']+e['to']))
      if 'rotation' in e:self.assertIn(e['rotation']['angle'],(-45,-22.5,0,22.5,45))
 def test_collision_and_existing_output_refused(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)/'a.zip';script=str(HERE/'merge_staging_pack.py');orig=str(ROOT/'rp/Elytrix-RP-1.21.zip')
   subprocess.run(['python3',script,orig,str(out)],check=True,stdout=subprocess.DEVNULL)
   another=Path(td)/'b.zip';r=subprocess.run(['python3',script,str(out),str(another)],capture_output=True);self.assertNotEqual(r.returncode,0);self.assertFalse(another.exists())
   before=out.read_bytes();r=subprocess.run(['python3',script,orig,str(out)],capture_output=True);self.assertNotEqual(r.returncode,0);self.assertEqual(before,out.read_bytes())
if __name__=='__main__':unittest.main()
