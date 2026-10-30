#!/usr/bin/env python3
import base64, io, json, unittest, uuid
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
class ModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = json.loads((ROOT/'elytrix_kaneki_tentacles.bbmodel').read_text())
    def test_structure_and_references(self):
        m=self.model
        self.assertEqual(m['model_identifier'], 'elytrix_kaneki_tentacles')
        self.assertEqual(len(m['outliner']),1)
        root=m['outliner'][0]; self.assertEqual(root['name'],'tentacles_root')
        self.assertEqual(root['origin'],[0,20,0]); self.assertEqual(len(root['children']),4)
        bones=root['children']; self.assertEqual(len({b['uuid'] for b in bones}),4)
        elems={e['uuid']:e for e in m['elements']}; self.assertEqual(len(elems),20)
        refs=[u for bone in bones for u in bone['children']]
        self.assertEqual(len(set(refs)),len(refs)); self.assertEqual(set(refs),set(elems))
        for e in elems.values():
            uuid.UUID(e['uuid'])
            self.assertTrue(all(a<b for a,b in zip(e['from'],e['to'])))
            self.assertGreaterEqual(e['from'][2],2.4)
            self.assertIn(e['rotation'][2],(-45,-22.5,0,22.5,45))
            self.assertTrue(all(face['texture']==0 for face in e['faces'].values()))
        self.assertGreater(len({b['origin'][1] for b in bones}),1)
        self.assertGreater(len({b['origin'][2] for b in bones}),1)
        self.assertGreater(max(e['to'][2] for e in elems.values()) - min(e['from'][2] for e in elems.values()), 3)
        idle=m['animations'][0]
        self.assertEqual(idle['name'],'idle'); self.assertEqual(idle['loop'],'loop')
        self.assertEqual(set(idle['animators']),{b['uuid'] for b in bones})
        for a in idle['animators'].values():
            keys=a['keyframes']; self.assertEqual(len(keys),25); self.assertEqual(keys[0]['time'],0); self.assertEqual(keys[-1]['time'],idle['length'])
            self.assertTrue(any(abs(float(k['data_points'][0]['z'])) >= 3.9 for k in keys))
            self.assertTrue(all(k['interpolation']=='linear' for k in keys))
            self.assertTrue(all(abs(float(keys[i+1]['data_points'][0]['z']) - float(keys[i]['data_points'][0]['z'])) < 1.1 for i in range(len(keys)-1)))
            self.assertEqual(keys[0]['data_points'],keys[-1]['data_points'])
    def test_texture(self):
        t=self.model['textures'][0]; prefix='data:image/png;base64,'
        self.assertTrue(t['source'].startswith(prefix))
        with Image.open(io.BytesIO(base64.b64decode(t['source'][len(prefix):],validate=True))) as im:
            self.assertEqual(im.size,(64,64)); self.assertEqual(im.mode,'RGBA')
            self.assertGreater(len(im.getcolors(4096)),20)
if __name__=='__main__': unittest.main()
