#!/usr/bin/env python3
"""Offline consistency checks; does not replace an actual Minecraft client reload."""
from pathlib import Path
import base64, hashlib, json, re, zipfile
root=Path(__file__).resolve().parents[3]
blueprint=json.loads((root/'plugins/ModelEngine/blueprints/elytrix_angel_wings.bbmodel').read_text())
elements={e['name']:e for e in blueprint['elements']}
pack=root/'rp/Elytrix-RP-1.21.zip'
with zipfile.ZipFile(pack) as z:
    assert z.testzip() is None
    for name in z.namelist():
        if name.endswith(('.json','.mcmeta')):
            json.loads(z.read(name))
    atlas=json.loads(z.read('assets/minecraft/atlases/blocks.json'))['sources']
    for src in ('entity','entity/models','archangel_set_texture'):
        assert any(s.get('source')==src for s in atlas),src
    texture='assets/modelengine/textures/entity/models/elytrix_archangel_wings.png'
    assert z.read(texture)==base64.b64decode(blueprint['textures'][0]['source'].split(',')[1])
    for side,indices in [('right',range(6)),('left',range(6,12))]:
        key=f'elytrix_angel_wings/{side}_wing_inner'
        item=json.loads(z.read(f'assets/modelengine/items/{key}.json'))['model']
        assert item['model']==f'modelengine:{key}'
        path=f'assets/modelengine/models/{key}.json'
        raw=z.read(path)
        assert raw==(root/'plugins/ModelEngine/resource pack'/path).read_bytes()
        baked=json.loads(raw)
        assert baked['textures']['0']=='modelengine:entity/models/elytrix_archangel_wings'
        # ModelEngine may emit cubes in a different order on each import.
        remaining=list(baked['elements'])
        assert len(remaining)==len(indices)
        for i in indices:
            src=elements[f'wing_{i}']
            def matches(model_element):
                return all(abs(model_element[field][axis] -
                    ((src[field][axis]-[0,20.4,0][axis])/2+8)) < .001
                    for field in ('from','to') for axis in range(3))
            candidates=[e for e in remaining if matches(e)]
            assert len(candidates)==1,(side,i,len(candidates))
            model_element=candidates[0]
            remaining.remove(model_element)
            if 'rotation' in model_element:
                for axis in range(3):
                    expected=(src['origin'][axis]-[0,20.4,0][axis])/2+8
                    assert abs(model_element['rotation']['origin'][axis]-expected)<.001
            for face in model_element['faces'].values():
                uv=face.get('uv')
                assert uv is None or (uv[0]!=uv[2] and uv[1]!=uv[3]), (side,i,uv)
    for bone in blueprint['outliner'][0]['children']:
        if bone['name'].startswith('feather_'):
            key='elytrix_angel_wings/'+bone['name']
            assert json.loads(z.read(f'assets/modelengine/items/{key}.json'))['model']['model']=='modelengine:'+key
            assert json.loads(z.read(f'assets/modelengine/models/{key}.json'))['textures']['0']=='modelengine:entity/models/elytrix_archangel_wings'
sha=hashlib.sha1(pack.read_bytes()).hexdigest()
config=(root/'plugins/ElytrixRP/config.yml').read_text()
assert re.search(r'^sha1:\s*["\']?'+sha,config,re.M)
print('Assets valid; matching RP SHA-1:',sha)
