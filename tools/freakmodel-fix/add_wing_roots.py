#!/usr/bin/env python3
"""Add small feathered shoulder roots to the existing two animated wing bones.

This intentionally operates once on the 3.2.8 assets. The source blueprint and
RP's generated bone models are changed together; unrelated pack entries and
textures remain untouched. The two bones retain their shared centre pivot and
scale=2. The geometry is only a candidate until tested on a real client.
"""
import hashlib
import json
import os
import re
import tempfile
import uuid
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
blueprint_path = root / 'plugins/ModelEngine/blueprints/elytrix_angel_wings.bbmodel'
model_root = root / 'plugins/ModelEngine/resource pack'
rp_path = root / 'rp/Elytrix-RP-1.21.zip'
config_path = root / 'plugins/ElytrixRP/config.yml'
blueprint = json.loads(blueprint_path.read_text())
wing_root = next(b for b in blueprint['outliner'] if isinstance(b, dict) and b.get('name') == 'wings_root')
bones = {b['name']: b for b in wing_root['children'] if isinstance(b, dict)}
assert wing_root['origin'] == [0.0, 20.4, 0.0]
for side in ('right', 'left'):
    assert bones[f'{side}_wing_inner']['origin'] == [0.0, 20.4, 0.0]
assert not any(e['name'].startswith('shoulder_root_') for e in blueprint['elements']), 'Already applied'

white_uv = [7.25, 0.20, 8.10, 0.65]  # existing opaque ivory part of the wing texture
feather_uv = [14.0, 13.0625, 15.0, 14.6875]  # existing transparent feather motif

def faces(feather):
    result = {direction: {'uv': white_uv[:], 'texture': 0}
              for direction in ('north', 'south', 'east', 'west', 'up', 'down')}
    if feather:
        result['north']['uv'] = feather_uv[:]
        result['south']['uv'] = [feather_uv[2], feather_uv[1], feather_uv[0], feather_uv[3]]
    return result

def mirror_x(values):
    f, t = values
    return [-t[0], f[1], f[2]], [-f[0], t[1], t[2]]

def new_cube(name, start, end, origin, angle, feather):
    item = {
        'name': name, 'box_uv': False, 'rescale': False, 'locked': False,
        'light_emission': 8, 'render_order': 'default', 'allow_mirror_modeling': True,
        'from': list(start), 'to': list(end), 'autouv': 0, 'color': 0,
        'origin': list(origin), 'rotation': [0.0, 0.0, angle],
        'faces': faces(feather), 'type': 'cube',
        'uuid': str(uuid.uuid5(uuid.NAMESPACE_URL, 'https://elytrix.pw/model/' + name)),
    }
    return item

def generated_cube(cube):
    # Same centred x2 scaling confirmed in the live ModelEngine output.
    pivot = (0.0, 20.4, 0.0)
    to_item = lambda point: [round((point[i] - pivot[i]) / 2.0 + 8.0, 6) for i in range(3)]
    result = {'from': to_item(cube['from']), 'to': to_item(cube['to']), 'faces': {}}
    for direction, face in cube['faces'].items():
        result['faces'][direction] = {'uv': face['uv'][:], 'tintindex': 0,
                                      'rotation': face.get('rotation', 0), 'texture': '#0'}
    if cube['rotation'][2]:
        result['rotation'] = {'origin': to_item(cube['origin']), 'angle': cube['rotation'][2], 'axis': 'z'}
    return result

# Right side: a small root against the back, then two translucent feather tips
# that fan up/down into the existing wing. Left side is a mirrored copy.
specs = [
    ('joint', (1.55, 19.65, 3.95), (3.8, 23.25, 4.55), (0.0, 20.4, 0.0), 0.0, False),
    ('upper', (1.8, 20.4, 4.45), (5.5, 25.8, 4.50), (2.0, 20.4, 4.45), -22.5, True),
    ('lower', (1.8, 17.6, 4.55), (5.0, 22.5, 4.60), (2.0, 21.0, 4.55), 22.5, True),
]
changes = {}
for side in ('right', 'left'):
    path = f'assets/modelengine/models/elytrix_angel_wings/{side}_wing_inner.json'
    model = json.loads((model_root / path).read_text())
    assert len(model['elements']) == 6
    assert model['textures']['0'] == 'modelengine:entity/models/elytrix_archangel_wings'
    for label, start, end, origin, angle, feather in specs:
        if side == 'left':
            start, end = mirror_x((start, end))
            origin = (-origin[0], origin[1], origin[2])
            angle = -angle
        name = f'shoulder_root_{side}_{label}'
        cube = new_cube(name, start, end, origin, angle, feather)
        assert min(cube['from'][2], cube['to'][2]) >= 3.9
        blueprint['elements'].append(cube)
        bones[f'{side}_wing_inner']['children'].append(cube['uuid'])
        generated = generated_cube(cube)
        assert all(-16 <= n <= 32 for field in ('from', 'to') for n in generated[field])
        model['elements'].append(generated)
    changes[path] = json.dumps(model, separators=(',', ':')).encode()

# Reject unintended mismatches and corrupt inputs before writing.
with zipfile.ZipFile(rp_path) as pack:
    assert pack.testzip() is None
    entries = [(i, pack.read(i)) for i in pack.infolist()]
    for path in changes:
        assert pack.read(path) == (model_root / path).read_bytes()
fd, temp = tempfile.mkstemp(dir=rp_path.parent, suffix='.zip')
os.close(fd)
try:
    with zipfile.ZipFile(temp, 'w') as pack:
        for info, content in entries:
            pack.writestr(info, changes.get(info.filename, content))
    with zipfile.ZipFile(temp) as pack:
        assert pack.testzip() is None
        for path, content in changes.items():
            assert pack.read(path) == content
    os.replace(temp, rp_path)
finally:
    if os.path.exists(temp):
        os.unlink(temp)
for path, content in changes.items():
    (model_root / path).write_bytes(content)
blueprint_path.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2) + '\n')
sha1 = hashlib.sha1(rp_path.read_bytes()).hexdigest()
config = config_path.read_text()
old_sha = re.search(r'(?m)^sha1:\s*["\']?([a-f0-9]{40})', config)
assert old_sha
config_path.write_text(config.replace(old_sha.group(1), sha1))
print('Added 3 feathered root pieces to each existing wing bone; RP SHA-1:', sha1)
