#!/usr/bin/env python3
"""Kaneki's half-mask as a real ModelEngine model (not an armour texture).

What the shape imitates: black leather over the lower face, a row of big ivory
teeth instead of a mouth (the zipper is open), a metal slider at the right end of
that row, one red kakugan eye in the left hole, stitched leather everywhere else
and two thin straps round the head.  Nothing here is a texture stretched over the
vanilla head: it is a 21-cube mesh that stands 2-6 pixels proud of the skin.

The root bone is named `h_mask`, i.e. the `h_` prefix that ModelEngine's
Blockbench parser reads as BoneBehaviorTypes.HEAD, so the whole mask turns with
the head yaw *and* pitch instead of sliding over the face.

Model space is the one the halo/wings already use: +Y up, the player faces -Z,
the head is the cube x[-4,4] y[24,32] z[-4,4], the neck pivot is (0,24,0).

Usage:
    python3 tools/accessories-model/build_mask.py --out-dir /tmp/mask --preview
"""
import argparse
import base64
import io
import json
import sys
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
MODEL = 'elytrix_kaneki_mask'
NAMESPACE = 'elytrix-mask'

# 64x64 atlas, 4 pixels per model unit (UV space above is 0..16).
UV = {
    'leather':      [0.0, 0.0, 8.0, 4.0],    # px   0, 0 .. 32,16   lit front
    'leather_dark': [8.0, 0.0, 16.0, 4.0],   # px  32, 0 .. 64,16   sides / shadow
    'teeth':        [0.0, 4.0, 8.0, 8.0],    # px   0,16 .. 32,32   ivory bar
    'eye':          [8.0, 4.0, 16.0, 8.0],   # px  32,16 .. 64,32   kakugan
    'metal':        [0.0, 8.0, 8.0, 12.0],   # px   0,32 .. 32,48   zipper slider
    'strap':        [8.0, 8.0, 16.0, 12.0],  # px  32,32 .. 64,48   strap
}

FRONT_Z = -4.44          # outer leather
DEEP_Z = -4.56           # chin / brow that stand a little further out
BACK_Z = -4.02           # inner surface, just off the skin (skin is at -4.0)


def uid(tag):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'{NAMESPACE}:{tag}'))


# --------------------------------------------------------------------------- texture
LEATHER = (40, 40, 49, 255)
LEATHER_MID = (52, 52, 63, 255)
LEATHER_HI = (74, 74, 88, 255)
DARK = (27, 27, 34, 255)
STITCH = (20, 20, 26, 255)


def _leather(draw, box, base, hi, mid, stitch):
    x0, y0, x1, y1 = box
    draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=base)
    for y in range(y0, y1):
        share = (y - y0) / max(1, y1 - y0 - 1)
        if share < 0.30:
            draw.line([(x0, y), (x1 - 1, y)], fill=mid)
        elif share > 0.72:
            draw.line([(x0, y), (x1 - 1, y)],
                      fill=tuple(int(base[i] * 0.88) for i in range(3)) + (255,))
    # dashed stitches just inside the border
    for x in range(x0 + 2, x1 - 2, 4):
        draw.point((x, y0 + 2), fill=stitch)
        draw.point((x, y1 - 3), fill=stitch)
    for y in range(y0 + 3, y1 - 3, 4):
        draw.point((x0 + 1, y), fill=stitch)
        draw.point((x1 - 2, y), fill=stitch)
    # creases so it is not one flat tone
    for x in (x0 + 6, x0 + 7, x1 - 9, x1 - 8):
        draw.line([(x, y0 + 4), (x, y1 - 5)], fill=hi)


def build_texture():
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    _leather(d, (0, 0, 32, 16), LEATHER, LEATHER_HI, LEATHER_MID, STITCH)
    _leather(d, (32, 0, 64, 16), DARK, LEATHER_MID, LEATHER, STITCH)

    # teeth: warm ivory, lit along the cutting edge, gum shadow at the root
    d.rectangle((0, 16, 31, 31), fill=(238, 234, 222, 255))
    d.line([(0, 16), (31, 16)], fill=(255, 253, 248, 255))
    d.line([(0, 17), (31, 17)], fill=(250, 247, 238, 255))
    d.line([(0, 29), (31, 29)], fill=(206, 200, 186, 255))
    d.line([(0, 30), (31, 30)], fill=(178, 172, 158, 255))
    d.rectangle((32, 16, 63, 31), fill=(212, 207, 194, 255))
    for x in range(0, 32, 8):
        d.line([(x, 18), (x, 28)], fill=(224, 219, 206, 255))

    # kakugan: red iris, black slit pupil, one white highlight
    d.rectangle((32, 16, 63, 31), fill=(96, 8, 12, 255))
    d.ellipse((33, 18, 62, 29), fill=(176, 20, 24, 255))
    d.ellipse((35, 19, 60, 28), fill=(231, 40, 38, 255))
    d.ellipse((38, 20, 57, 27), fill=(250, 96, 86, 255))
    d.rectangle((46, 18, 49, 30), fill=(12, 4, 6, 255))
    d.point((41, 20), fill=(255, 214, 208, 255))

    d.rectangle((0, 32, 31, 47), fill=(196, 203, 212, 255))
    d.line([(0, 32), (31, 32)], fill=(238, 244, 250, 255))
    d.line([(0, 46), (31, 46)], fill=(112, 118, 126, 255))
    d.rectangle((32, 32, 63, 47), fill=(30, 30, 37, 255))
    d.line([(32, 34), (63, 34)], fill=(52, 52, 62, 255))
    return img


# --------------------------------------------------------------------------- geometry
LEATHER_FACES = {'north': 'leather', 'south': 'leather_dark', 'east': 'leather_dark',
                 'west': 'leather_dark', 'up': 'leather_dark', 'down': 'leather_dark'}
DARK_FACES = dict.fromkeys(('north', 'south', 'east', 'west', 'up', 'down'), 'leather_dark')
TOOTH_FACES = {'north': 'teeth', 'south': 'metal', 'east': 'teeth', 'west': 'teeth',
               'up': 'teeth', 'down': 'teeth'}
METAL_FACES = dict.fromkeys(('north', 'south', 'east', 'west', 'up', 'down'), 'metal')
EYE_FACES = {'north': 'eye', 'south': 'eye', 'east': 'metal', 'west': 'metal',
             'up': 'metal', 'down': 'metal'}
STRAP_FACES = dict.fromkeys(('north', 'south', 'east', 'west', 'up', 'down'), 'strap')

CUBES = [
    # chin: narrow and pushed forward, so the profile is not a straight slab
    ('chin', (-2.70, 24.02, DEEP_Z), (2.70, 25.12, BACK_Z), LEATHER_FACES),
    ('jaw_l', (-4.12, 24.02, FRONT_Z), (-2.70, 25.12, BACK_Z), LEATHER_FACES),
    ('jaw_r', (2.70, 24.02, FRONT_Z), (4.12, 25.12, BACK_Z), LEATHER_FACES),
    # the open mouth: a black slot, then the teeth standing in front of it
    ('mouth', (-3.34, 25.12, FRONT_Z + 0.16), (3.34, 26.62, BACK_Z), DARK_FACES),
    ('tooth_1', (-3.24, 25.26, FRONT_Z - 0.04), (-2.62, 26.46, FRONT_Z + 0.16), TOOTH_FACES),
    ('tooth_2', (-2.50, 25.26, FRONT_Z - 0.04), (-1.88, 26.46, FRONT_Z + 0.16), TOOTH_FACES),
    ('tooth_3', (-1.76, 25.26, FRONT_Z - 0.04), (-1.14, 26.46, FRONT_Z + 0.16), TOOTH_FACES),
    ('tooth_4', (-1.02, 25.26, FRONT_Z - 0.04), (-0.40, 26.46, FRONT_Z + 0.16), TOOTH_FACES),
    ('tooth_5', (-0.28, 25.26, FRONT_Z - 0.04), (0.34, 26.46, FRONT_Z + 0.16), TOOTH_FACES),
    ('tooth_6', (0.46, 25.26, FRONT_Z - 0.04), (1.08, 26.46, FRONT_Z + 0.16), TOOTH_FACES),
    ('tooth_7', (1.20, 25.26, FRONT_Z - 0.04), (1.82, 26.46, FRONT_Z + 0.16), TOOTH_FACES),
    ('tooth_8', (1.94, 25.26, FRONT_Z - 0.04), (2.56, 26.46, FRONT_Z + 0.16), TOOTH_FACES),
    ('zipper_pull', (2.72, 24.62, FRONT_Z - 0.02), (3.34, 25.34, FRONT_Z + 0.20), METAL_FACES),
    # band under the eyes, then the cheeks that leave the two eye holes open
    ('under_eye', (-4.12, 26.62, FRONT_Z + 0.02), (4.12, 27.05, BACK_Z), LEATHER_FACES),
    ('cheek_l', (-4.12, 27.05, FRONT_Z + 0.02), (-3.06, 29.40, BACK_Z), LEATHER_FACES),
    ('cheek_r', (3.06, 27.05, FRONT_Z + 0.02), (4.12, 29.40, BACK_Z), LEATHER_FACES),
    ('nose', (-0.62, 27.05, DEEP_Z + 0.06), (0.62, 29.40, BACK_Z), LEATHER_FACES),
    # brow: overhangs the two holes, right under the hairline
    ('brow', (-4.12, 29.40, DEEP_Z + 0.04), (4.12, 30.04, BACK_Z), LEATHER_FACES),
    # the kakugan fills the left hole; the right hole stays open on the skin
    ('kakugan', (-2.96, 27.22, FRONT_Z + 0.10), (-0.80, 29.26, FRONT_Z + 0.26), EYE_FACES),
    # thin straps round the head, they disappear under the hair
    ('strap_l', (-4.34, 27.62, -4.04), (-4.12, 28.26, 3.70), STRAP_FACES),
    ('strap_r', (4.12, 27.62, -4.04), (4.34, 28.26, 3.70), STRAP_FACES),
    ('strap_b', (-4.34, 27.62, 3.46), (4.34, 28.26, 3.70), STRAP_FACES),
]

BONES = [
    ('mask_shell', [0.0, 27.2, -4.3],
     ['chin', 'jaw_l', 'jaw_r', 'under_eye', 'cheek_l', 'cheek_r', 'nose', 'brow']),
    ('mask_mouth', [0.0, 25.8, -4.4],
     ['mouth', 'tooth_1', 'tooth_2', 'tooth_3', 'tooth_4', 'tooth_5', 'tooth_6',
      'tooth_7', 'tooth_8', 'zipper_pull']),
    ('mask_eye', [-1.9, 28.2, -4.3], ['kakugan']),
    ('mask_straps', [0.0, 27.9, 0.0], ['strap_l', 'strap_r', 'strap_b']),
]

ROOT_NAME = 'mask_root'          # plain root, keeps the model's own pivot
HEAD_BONE = 'h_mask'             # h_ prefix = ModelEngine HEAD behaviour
ROOT_ORIGIN = [0.0, 24.0, 0.0]


def build_elements():
    elements = []
    for name, low, high, faces in CUBES:
        elements.append({
            'name': name,
            'box_uv': False, 'rescale': False, 'locked': False, 'light_emission': 0,
            'render_order': 'default', 'allow_mirror_modeling': True,
            'from': [round(v, 4) for v in low],
            'to': [round(v, 4) for v in high],
            'autouv': 0, 'color': 0, 'inflate': 0,
            'origin': [round((low[i] + high[i]) / 2, 4) for i in range(3)],
            'rotation': [0.0, 0.0, 0.0],
            'faces': {side: {'uv': list(UV[region]), 'texture': 0}
                      for side, region in faces.items()},
            'type': 'cube', 'uuid': uid(f'cube:{name}'),
        })
    return elements


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

    elements = build_elements()
    by_name = {cube['name']: cube for cube in elements}
    children = []
    for name, origin, cube_names in BONES:
        children.append({
            'name': name, 'origin': [round(v, 4) for v in origin],
            'rotation': [0.0, 0.0, 0.0], 'color': 0, 'uuid': uid(f'bone:{name}'),
            'export': True, 'mirror_uv': False, 'isOpen': True, 'locked': False,
            'visibility': True, 'autouv': 0,
            'children': [by_name[cube]['uuid'] for cube in cube_names],
        })
    head = {
        'name': HEAD_BONE, 'origin': list(ROOT_ORIGIN), 'rotation': [0.0, 0.0, 0.0],
        'color': 0, 'uuid': uid('bone:head'), 'export': True, 'mirror_uv': False,
        'isOpen': True, 'locked': False, 'visibility': True, 'autouv': 0,
        'children': children,
    }
    root = {
        'name': ROOT_NAME, 'origin': list(ROOT_ORIGIN), 'rotation': [0.0, 0.0, 0.0],
        'color': 0, 'uuid': uid('bone:root'), 'export': True, 'mirror_uv': False,
        'isOpen': True, 'locked': False, 'visibility': True, 'autouv': 0,
        'children': [head],
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
    print(f'{len(model["elements"])} cubes, head bone {HEAD_BONE} -> {out}')

    if args.preview:
        sys.path.insert(0, str(HERE))
        import build_tentacles
        panel = (520, 520)
        centre = (0.0, 28.2, 0.0)
        common = dict(scale=27.0, size=panel, texture=texture, head=True,
                      centre=centre, perspective=0.0)
        build_tentacles.preview(model, out / 'mask_front.png', title='вид спереди',
                                yaw=180, pitch=0, **common)
        build_tentacles.preview(model, out / 'mask_angle.png', title='вид 3/4',
                                yaw=214, pitch=8, **common)
        build_tentacles.preview(model, out / 'mask_side.png', title='вид сбоку',
                                yaw=268, pitch=4, **common)
        names = ('mask_front', 'mask_angle', 'mask_side')
        combo = Image.new('RGB', (panel[0] * len(names), panel[1]), (24, 28, 42))
        for index, name in enumerate(names):
            combo.paste(Image.open(out / f'{name}.png'), (panel[0] * index, 0))
        combo.save(out / 'mask_preview.png')


if __name__ == '__main__':
    main()
