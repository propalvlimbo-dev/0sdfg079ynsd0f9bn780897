#!/usr/bin/env python3
"""Turns a .bbmodel into the ModelEngine item assets the resource pack needs.

Why this exists: ModelEngine draws every bone of a model as an ItemDisplay, and
that display needs an item definition, an item model and the texture in the pack
the server actually serves.  The kagune always shipped those files, the mask and
the centipede never did — which is exactly why they were invisible in game even
though the blueprint loaded ("её просто нету").  Nothing is drawn for a bone
whose item model is missing.

The layout produced here is the one ModelEngine itself uses (verified by
regenerating the working kagune assets and comparing them number by number):

    assets/modelengine/items/<model>/<bone>.json
    assets/modelengine/models/<model>/<bone>.json
    assets/modelengine/textures/entity/models/<model>.png

Geometry rule: every cube of a bone is expressed in that bone's own space,
shifted so the bone pivot lands on the middle of the item (8,8,8).  A per-cube
rotation is kept as the element's own rotation object.

Usage:
    python3 build_modelengine_assets.py <file.bbmodel> <assets-dir> [--check]
"""
import argparse
import base64
import json
import sys
from pathlib import Path

AXES = ('x', 'y', 'z')
SIDES = ('east', 'south', 'north', 'west', 'up', 'down')


def _shift(value, pivot):
    return [round(value[i] - pivot[i] + 8.0, 4) for i in range(3)]


def _rotation(cube, pivot):
    """Blockbench allows one rotated axis per cube; ModelEngine keeps it as-is."""
    angles = cube.get('rotation') or [0.0, 0.0, 0.0]
    for axis, angle in enumerate(angles):
        if angle:
            return {'origin': _shift(cube['origin'], pivot), 'angle': angle, 'axis': AXES[axis]}
    return None


def _element(cube, pivot):
    from_ = _shift(cube['from'], pivot)
    to = _shift(cube['to'], pivot)
    # ModelEngine always writes the low corner first
    low = [min(from_[i], to[i]) for i in range(3)]
    high = [max(from_[i], to[i]) for i in range(3)]
    faces = {}
    for side in SIDES:
        face = (cube.get('faces') or {}).get(side)
        if face is None:
            continue
        faces[side] = {'uv': list(face['uv']), 'tintindex': 0, 'rotation': 0, 'texture': '#0'}
    element = {'from': low, 'to': high, 'faces': faces}
    rotation = _rotation(cube, pivot)
    if rotation is not None:
        element['rotation'] = rotation
    return element


def _bones(model):
    """Yields (bone, cube elements) for every bone that owns cubes directly."""
    elements = {element['uuid']: element for element in model['elements']}

    def walk(node):
        cubes = [elements[child] for child in node.get('children', []) if isinstance(child, str)]
        if cubes:
            yield node, cubes
        for child in node.get('children', []):
            if isinstance(child, dict):
                yield from walk(child)

    for root in model['outliner']:
        yield from walk(root)


def build(bbmodel, out_dir, model_name=None):
    bbmodel = Path(bbmodel)
    model = json.loads(bbmodel.read_text(encoding='utf-8'))
    name = model_name or model.get('name') or bbmodel.stem
    base = Path(out_dir) / 'modelengine'
    items = base / 'items' / name
    models = base / 'models' / name
    textures = base / 'textures' / 'entity' / 'models'
    for directory in (items, models, textures):
        directory.mkdir(parents=True, exist_ok=True)

    written = []
    for bone, cubes in _bones(model):
        pivot = bone['origin']
        # ModelEngine sorts the cubes of a bone by their UUID (verified against the
        # working kagune assets: the order is neither the outliner order nor its
        # reverse, it is the UUID order).
        elements = [_element(cube, pivot) for cube in sorted(cubes, key=lambda c: c['uuid'])]
        body = {
            'textures': {'0': f'modelengine:entity/models/{name}', 'particle': '#0'},
            'elements': elements,
            'display': {'gui': {'rotation': [-150.0, -45.0, 180.0]}},
        }
        definition = {
            'model': {
                'model': f'modelengine:{name}/{bone["name"]}',
                'tints': [{'index': 0, 'default': 16777215, 'type': 'minecraft:custom_model_data'}],
                'type': 'minecraft:model',
            }
        }
        model_path = models / f'{bone["name"]}.json'
        item_path = items / f'{bone["name"]}.json'
        model_path.write_text(json.dumps(body, separators=(',', ':')) + '\n', encoding='utf-8')
        item_path.write_text(json.dumps(definition, separators=(',', ':')) + '\n', encoding='utf-8')
        written.extend((model_path, item_path))

    # the texture travels inside the blueprint as a data URI
    texture = next((t for t in model.get('textures', []) if t.get('source', '').startswith('data:image')), None)
    if texture is None:
        raise SystemExit(f'{bbmodel}: no embedded texture')
    png = base64.b64decode(texture['source'].split(',', 1)[1])
    texture_path = textures / f'{name}.png'
    texture_path.write_bytes(png)
    written.append(texture_path)
    return name, written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('bbmodel')
    parser.add_argument('assets_dir', nargs='?', default=str(Path(__file__).resolve().parent / 'assets'))
    parser.add_argument('--name', help='override the model name used in the asset paths')
    args = parser.parse_args()
    name, written = build(args.bbmodel, args.assets_dir, args.name)
    print(f'{name}: {len([w for w in written if w.suffix == ".json"]) // 2} bones -> {Path(args.assets_dir) / "modelengine"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
