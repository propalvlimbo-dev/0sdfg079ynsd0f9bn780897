#!/usr/bin/env python3
"""Apply the 3.2.6 wing geometry/resource changes to the original 3.2.3 assets.

ModelEngine's center-pivot geometry uses scale 2 for the two inner bones.
Changing a source cube by dz therefore changes the corresponding item-model
coordinates and rotation origins by dz / 2. The feather meshes retain their
local coordinates, because both their cube and bone origins move together.
"""
import json, math, zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[2]
blueprint = ROOT/'plugins/ModelEngine/blueprints/elytrix_angel_wings.bbmodel'
pack_dir = ROOT/'plugins/ModelEngine/resource pack'
rp = ROOT/'rp/Elytrix-RP-1.21.zip'
model = json.loads(blueprint.read_text())
elements = {e['name']: e for e in model['elements']}
assert abs(elements['wing_2']['from'][2] - 4.8) < 1e-6, 'Use unmodified 3.2.3 assets as input'
# Shift faces near the back closer while retaining z >= 3.9 after rotation.
shifts = {0: .02, 1: .02, 2: -.65, 3: .02, 4: -.10, 5: -.65,
          6: .02, 7: .02, 8: -.65, 9: .02, 10: -.10, 11: -.65}
for i, dz in shifts.items():
    e = elements[f'wing_{i}']
    for field in ('from', 'to', 'origin'):
        e[field][2] = round(e[field][2] + dz, 5)
for bone in model['outliner'][0]['children']:
    if bone['name'].startswith('feather_'):
        bone['origin'][2] = round(bone['origin'][2] - .65, 5)
        e = elements[bone['name'] + '_mesh']
        for field in ('from','to','origin'):
            e[field][2] = round(e[field][2] - .65, 5)
for i in range(12):
    e = elements[f'wing_{i}']; angle = math.radians(e['rotation'][1]); ox, _, oz = e['origin']
    min_z = min(oz + math.cos(angle)*(z-oz) - math.sin(angle)*(x-ox)
                for z in (e['from'][2],e['to'][2]) for x in (e['from'][0],e['to'][0]))
    assert min_z >= 3.9, (e['name'], min_z)
assert model['outliner'][0]['origin'] == [0.0,20.4,0.0]
for bone in model['outliner'][0]['children'][:2]:
    assert bone['origin'] == [0.0,20.4,0.0]
blueprint.write_text(json.dumps(model,ensure_ascii=False,indent=2)+'\n')
changes={}
for side, indices in [('right',range(6)),('left',range(6,12))]:
    name = f'assets/modelengine/models/elytrix_angel_wings/{side}_wing_inner.json'
    file = pack_dir/name
    item = json.loads(file.read_text())
    assert len(item['elements']) == 6
    for e,i in zip(item['elements'],indices):
        dz = shifts[i]/2
        for field in ('from','to'):
            e[field][2] = round(e[field][2] + dz, 5)
        if 'rotation' in e:
            e['rotation']['origin'][2] = round(e['rotation']['origin'][2] + dz, 5)
    data = json.dumps(item,separators=(',',':')).encode()
    file.write_bytes(data); changes[name]=data
with zipfile.ZipFile(rp) as old:
    infos=old.infolist(); originals={i.filename: old.read(i) for i in infos}
    atlas_name='assets/minecraft/atlases/blocks.json'
    atlas=json.loads(originals[atlas_name]); sources=atlas['sources']
    if not any(s.get('source')=='entity/models' and s.get('prefix')=='entity/models/' for s in sources):
        sources.append({'type':'directory','source':'entity/models','prefix':'entity/models/'})
    changes[atlas_name]=json.dumps(atlas,ensure_ascii=False,indent=2).encode()
    with NamedTemporaryFile(dir=rp.parent,delete=False) as tmp:
        tmp_name=tmp.name
    with zipfile.ZipFile(tmp_name,'w') as new:
        for info in infos:
            new.writestr(info, changes.get(info.filename,originals[info.filename]))
Path(tmp_name).replace(rp)
print('Updated wing blueprint, two model JSONs, and RP atlas')
