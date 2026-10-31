"""Elytrix's flying centipede: a segmented creature that hovers over the head.

Eleven bones, sixty-odd cubes.  The chain is `body_root -> c1 -> c2 -> ... -> c9`
with the head hanging off `c1`, so a yaw on one segment carries everything behind
it and a travelling wave runs down the body.  ElytrixFreakModel drives that wave
with a ManualAnimator, so the animal literally crawls and drifts left and right
instead of hanging still.

Space: +Y up, the player faces -Z, the head cube is x[-4,4] y[24,32] z[-4,4],
so y 34.5-36.8 is just above the head and the body reaches from the forehead
(z=-7.4) to behind the head (z=+7).

No cube carries a rotation.  ModelEngine 4.1.0 cannot import a blueprint whose
bones mix rotated cubes: its RotationSolver dies with
`UnsupportedOperationException: remove` inside `AbstractSet.removeAll`
(`RotationSolver.fetch`, line 255) and the whole model is dropped — which is why
the animal never appeared in game even though the file looked fine in Blockbench.
The angled legs, antennae, fangs and cerci are therefore built from two stacked
axis-aligned boxes each: the silhouette still reads as angled, but nothing has to
be rotated at parse time.  tools/accessories-model/test_model.py re-runs the real
ModelEngine generator on this blueprint to keep that true.

Usage:
    python3 tools/accessories-model/build_centipede.py --out-dir /tmp/bug --preview
"""
import argparse
import base64
import io
import json
import math
import sys
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
MODEL = 'elytrix_centipede'
NAMESPACE = 'elytrix-centipede'
SEGMENTS = 9

UV = {
    'chitin':      [0.0, 0.0, 8.0, 4.0],     # px   0, 0 .. 32,16
    'chitin_dark': [8.0, 0.0, 16.0, 4.0],    # px  32, 0 .. 64,16
    'pink':        [0.0, 4.0, 8.0, 8.0],     # px   0,16 .. 32,32
    'joint':       [8.0, 4.0, 16.0, 8.0],    # px  32,16 .. 64,32
    'leg':         [0.0, 8.0, 8.0, 12.0],    # px   0,32 .. 32,48
    'eye':         [8.0, 8.0, 16.0, 12.0],   # px  32,32 .. 64,48
}

BODY_Y0, BODY_Y1 = 34.55, 36.20     # the ring: 1.65 px tall, 2.4 px wide
SPINE_Y0, SPINE_Y1 = 36.20, 36.55   # the pink plate riding on the ring
BODY_HALF_W = 1.20
HALF_L = 0.72
Z0 = -4.60          # centre of the first segment
STEP = 1.30


def uid(tag):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'{NAMESPACE}:{tag}'))


# --------------------------------------------------------------------------- texture
def build_texture():
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # chitin: bone white with a cool shade and a lit edge
    d.rectangle((0, 0, 31, 15), fill=(238, 233, 226, 255))
    d.line([(0, 0), (31, 0)], fill=(255, 252, 247, 255))
    d.line([(0, 14), (31, 14)], fill=(196, 189, 181, 255))
    for x in range(0, 32, 6):
        d.line([(x, 3), (x, 12)], fill=(224, 218, 210, 255))
    d.rectangle((32, 0, 63, 15), fill=(198, 191, 183, 255))
    d.line([(32, 0), (63, 0)], fill=(226, 220, 212, 255))

    # pink plates, the Elytrix accent
    d.rectangle((0, 16, 31, 31), fill=(248, 190, 251, 255))
    d.line([(0, 16), (31, 16)], fill=(255, 226, 255, 255))
    d.line([(0, 30), (31, 30)], fill=(206, 140, 214, 255))
    for x in range(2, 32, 7):
        d.line([(x, 19), (x, 27)], fill=(240, 172, 246, 255))

    # joints between the plates
    d.rectangle((32, 16, 63, 31), fill=(64, 44, 52, 255))
    d.line([(32, 16), (63, 16)], fill=(96, 68, 78, 255))
    d.line([(32, 30), (63, 30)], fill=(44, 28, 34, 255))

    # legs
    d.rectangle((0, 32, 31, 47), fill=(86, 60, 70, 255))
    d.line([(0, 32), (31, 32)], fill=(118, 86, 98, 255))
    d.line([(0, 46), (31, 46)], fill=(58, 38, 46, 255))

    # the eyes: red with a black slit and a highlight
    d.rectangle((32, 32, 63, 47), fill=(168, 18, 22, 255))
    d.ellipse((34, 34, 61, 45), fill=(226, 38, 36, 255))
    d.rectangle((45, 34, 50, 45), fill=(10, 4, 6, 255))
    d.point((39, 36), fill=(255, 214, 208, 255))
    return img


# --------------------------------------------------------------------------- geometry
def faces(region):
    return {side: region for side in ('north', 'south', 'east', 'west', 'up', 'down')}


def cube(name, low, high, region):
    """One axis-aligned box.  Rotation is deliberately not supported here."""
    return {
        'name': name,
        'box_uv': False, 'rescale': False, 'locked': False, 'light_emission': 0,
        'render_order': 'default', 'allow_mirror_modeling': True,
        'from': [round(v, 4) for v in low],
        'to': [round(v, 4) for v in high],
        'autouv': 0, 'color': 0, 'inflate': 0,
        'origin': [round((low[i] + high[i]) / 2, 4) for i in range(3)],
        'rotation': [0.0, 0.0, 0.0],
        'faces': {side: {'uv': list(UV[r]), 'texture': 0} for side, r in faces(region).items()},
        'type': 'cube', 'uuid': uid(f'cube:{name}'),
    }


def curve(index):
    """A gentle S baked into the rest pose, so the animal is never a straight rod."""
    return round(0.55 * math.sin(index * 0.62), 3)


def legs(index, dx, z):
    """Two stacked boxes per side: they step outwards and downwards like a leg."""
    out = []
    for side, sign in (('l', -1.0), ('r', 1.0)):
        inner = BODY_HALF_W
        out.append(cube(f'leg_a_{side}_{index}',
                        (dx + sign * inner, 34.95, z - 0.34),
                        (dx + sign * (inner + 0.95), 35.35, z + 0.34), 'leg'))
        out.append(cube(f'leg_b_{side}_{index}',
                        (dx + sign * (inner + 0.50), 34.20, z - 0.28),
                        (dx + sign * (inner + 1.35), 34.95, z + 0.28), 'joint'))
    return out


def segment_cubes(index, z):
    """One body ring: the shell, a pink plate on top and two stepped legs."""
    dx = curve(index)
    cubes = [
        cube(f'body_{index}', (dx - BODY_HALF_W, BODY_Y0, z - HALF_L),
             (dx + BODY_HALF_W, BODY_Y1, z + HALF_L), 'chitin'),
        cube(f'plate_{index}', (dx - 0.88, SPINE_Y0, z - 0.52),
             (dx + 0.88, SPINE_Y1, z + 0.52), 'pink'),
    ]
    cubes.extend(legs(index, dx, z))
    return cubes


def head_cubes():
    dx = curve(0)
    return [
        cube('head', (dx - 1.45, 34.45, -7.30), (dx + 1.45, 36.30, -5.60), 'chitin'),
        cube('head_plate', (dx - 1.05, 36.30, -7.05), (dx + 1.05, 36.62, -5.85), 'pink'),
        cube('eye_l', (dx - 1.05, 35.30, -7.40), (dx - 0.45, 35.90, -7.24), 'eye'),
        cube('eye_r', (dx + 0.45, 35.30, -7.40), (dx + 1.05, 35.90, -7.24), 'eye'),
        # antennae: two boxes each, stepping up and forward (no rotation, see the
        # module docstring — ModelEngine drops a model whose cubes are rotated)
        cube('antenna_a_l', (dx - 0.98, 36.30, -7.10), (dx - 0.62, 36.58, -6.55), 'leg'),
        cube('antenna_b_l', (dx - 1.22, 36.50, -7.72), (dx - 0.86, 36.78, -7.10), 'joint'),
        cube('antenna_a_r', (dx + 0.62, 36.30, -7.10), (dx + 0.98, 36.58, -6.55), 'leg'),
        cube('antenna_b_r', (dx + 0.86, 36.50, -7.72), (dx + 1.22, 36.78, -7.10), 'joint'),
        # mandibles under the face, pointing forward and down
        cube('fang_l', (dx - 0.88, 33.95, -7.20), (dx - 0.52, 34.45, -6.45), 'joint'),
        cube('fang_r', (dx + 0.52, 33.95, -7.20), (dx + 0.88, 34.45, -6.45), 'joint'),
    ]


def tail_cubes(z):
    """Two cerci at the very back, stepped outwards."""
    return [
        cube('cercus_a_l', (-0.80, 34.75, z + HALF_L), (-0.46, 35.10, z + 1.35), 'leg'),
        cube('cercus_b_l', (-1.12, 34.55, z + 1.15), (-0.78, 34.90, z + 1.85), 'joint'),
        cube('cercus_a_r', (0.46, 34.75, z + HALF_L), (0.80, 35.10, z + 1.35), 'leg'),
        cube('cercus_b_r', (0.78, 34.55, z + 1.15), (1.12, 34.90, z + 1.85), 'joint'),
    ]


def build_model():
    texture = build_texture()
    raw = io.BytesIO()
    texture.save(raw, format='PNG', optimize=True)
    texture_entry = {
        'path': '', 'name': f'{MODEL}.png', 'folder': '', 'namespace': '', 'id': '0',
        'width': 64, 'height': 64, 'uv_width': 16, 'uv_height': 16, 'particle': False,
        'use_as_default': False, 'layers_enabled': False, 'render_mode': 'default',
        'render_sides': 'auto', 'frame_time': 1, 'frame_order_type': 'loop',
        'frame_interpolate': False, 'visible': True, 'internal': True, 'saved': False,
        'uuid': uid('texture'), 'source': 'data:image/png;base64,'
        + base64.b64encode(raw.getvalue()).decode('ascii'),
    }

    elements = []
    bones = {}

    # the head, hung off the first ring
    head_cubes_list = head_cubes()
    elements.extend(head_cubes_list)
    bones['head'] = {
        'name': 'head', 'origin': [curve(0), 35.2, -6.0], 'rotation': [0.0, 0.0, 0.0],
        'color': 0, 'uuid': uid('bone:head'), 'export': True, 'mirror_uv': False,
        'isOpen': True, 'locked': False, 'visibility': True, 'autouv': 0,
        'children': [c['uuid'] for c in head_cubes_list],
    }

    chain = None
    for index in range(SEGMENTS, 0, -1):
        z = Z0 + (index - 1) * STEP
        cubes = segment_cubes(index, z)
        if index == SEGMENTS:
            cubes.extend(tail_cubes(z))
        elements.extend(cubes)
        bone = {
            'name': f'c{index}', 'origin': [curve(index), 35.2, round(z - 0.70, 4)],
            'rotation': [0.0, 0.0, 0.0], 'color': 0, 'uuid': uid(f'bone:c{index}'),
            'export': True, 'mirror_uv': False, 'isOpen': True, 'locked': False,
            'visibility': True, 'autouv': 0,
            'children': [c['uuid'] for c in cubes],
        }
        # A child bone is a nested object in the Blockbench outliner.  Shipping
        # its UUID as a string (what this file used to do) makes the parser look
        # for an *element* with that id, fail, and drop the whole model — the
        # reason the centipede never appeared in game.
        if chain is not None:
            bone['children'].append(chain)              # the rest of the body
        if index == 1:
            bone['children'].append(bones['head'])
        bones[f'c{index}'] = bone
        chain = bone

    root = {
        'name': 'body_root', 'origin': [0.0, 35.2, -6.0], 'rotation': [0.0, 0.0, 0.0],
        'color': 0, 'uuid': uid('bone:root'), 'export': True, 'mirror_uv': False,
        'isOpen': True, 'locked': False, 'visibility': True, 'autouv': 0,
        'children': [bones['c1']],
    }
    return {
        'meta': {'format_version': '4.10', 'model_format': 'free', 'box_uv': False},
        'name': MODEL, 'model_identifier': MODEL, 'visible_box': [5, 5, 1],
        'resolution': {'width': 16, 'height': 16}, 'elements': elements,
        'outliner': [root], 'textures': [texture_entry], 'animations': [],
    }, texture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', default=str(HERE))
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    model, texture = build_model()
    (out / f'{MODEL}.bbmodel').write_text(
        json.dumps(model, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    texture.save(out / f'{MODEL}.png')

    low = [min(c['from'][i] for c in model['elements']) for i in range(3)]
    high = [max(c['to'][i] for c in model['elements']) for i in range(3)]
    print(f'bbox {[round(v, 2) for v in low]} {[round(v, 2) for v in high]} '
          f'size {[round(high[i] - low[i], 2) for i in range(3)]}')
    print(f'{len(model["elements"])} cubes, 10 bones -> {out}')

    if args.preview:
        sys.path.insert(0, str(HERE))
        import build_tentacles
        panel = (520, 520)
        centre = (0.0, 34.0, 0.0)
        common = dict(scale=24.0, size=panel, texture=texture, head=True,
                      centre=centre, perspective=0.0)
        build_tentacles.preview(model, out / 'bug_front.png', title='вид спереди',
                                yaw=180, pitch=8, **common)
        build_tentacles.preview(model, out / 'bug_angle.png', title='вид 3/4',
                                yaw=214, pitch=16, **common)
        build_tentacles.preview(model, out / 'bug_side.png', title='вид сбоку',
                                yaw=270, pitch=10, **common)
        names = ('bug_front', 'bug_angle', 'bug_side')
        combo = Image.new('RGB', (panel[0] * len(names), panel[1]), (24, 28, 42))
        for index, name in enumerate(names):
            combo.paste(Image.open(out / f'{name}.png'), (panel[0] * index, 0))
        combo.save(out / 'bug_preview.png')


if __name__ == '__main__':
    main()
