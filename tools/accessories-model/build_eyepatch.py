#!/usr/bin/env python3
"""Kaneki's eyepatch: a white cloth patch over the left eye, with the strap.

The model lives in the same space as the halo and the wings: +X is the player's
right, +Y is up, +Z is behind him, and the head is the cube x[-4,4] y[24,32]
z[-4,4].  The patch therefore covers the *left* eye (+X) and the band runs round
the head at the hairline, exactly where a real eyepatch strap sits.

Everything is a handful of cubes on a 64x64 pixel-art texture: no smooth shapes,
no AI, the same pipeline as the kagune.

Usage:
    python3 tools/accessories-model/build_eyepatch.py --out-dir /tmp/patch --preview
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
MODEL = 'elytrix_kaneki_eyepatch'
NAMESPACE = 'elytrix-eyepatch'


def uid(tag):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'{NAMESPACE}:{tag}'))


# --------------------------------------------------------------------------- texture
# 64x64, i.e. 4 pixels per model unit.  Every face points at one of these
# regions (Blockbench UV space is 0..16).
UV = {
    'cloth': [0.0, 0.0, 8.0, 4.0],          # lit front of the patch
    'cloth_dark': [8.0, 0.0, 16.0, 4.0],    # underside / shadowed fold
    'strap': [0.0, 4.0, 8.0, 8.0],          # the band round the head
    'strap_dark': [8.0, 4.0, 16.0, 8.0],    # band in shadow
    'stitch': [0.0, 8.0, 8.0, 12.0],        # the hem of the patch
}


def _cloth(draw, box, base, dark, light, weave):
    """A block of woven cloth: flat base, a soft vertical shading, a few threads."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=base)
    # vertical shading: the cloth is a little darker at the bottom edge
    for y in range(y0, y1):
        share = (y - y0) / max(1, (y1 - y0 - 1))
        if share > 0.55:
            k = (share - 0.55) / 0.45
            colour = tuple(int(base[i] + (dark[i] - base[i]) * k * 0.85) for i in range(3))
            draw.line([(x0, y), (x1 - 1, y)], fill=colour)
    # weave: one darker thread every three pixels
    for x in range(x0 + 1, x1 - 1, 3):
        draw.line([(x, y0 + 1), (x, y1 - 2)], fill=weave)
    # a single highlight row under the top edge so the fold catches light
    draw.line([(x0 + 1, y0 + 1), (x1 - 2, y0 + 1)], fill=light)


def build_texture():
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    white = (237, 235, 229, 255)
    white_dark = (188, 184, 176, 255)
    white_light = (252, 251, 247, 255)
    weave = (224, 221, 213, 255)
    strap = (216, 211, 201, 255)
    strap_dark = (168, 163, 153, 255)
    strap_weave = (203, 198, 188, 255)

    # cloth 32x16
    _cloth(draw, (0, 0, 31, 15), white, white_dark, white_light, weave)
    _cloth(draw, (32, 0, 63, 15), white_dark, (150, 146, 138, 255),
           (206, 202, 194, 255), weave)
    # strap 32x16
    _cloth(draw, (0, 16, 31, 31), strap, strap_dark, (233, 229, 220, 255), strap_weave)
    _cloth(draw, (32, 16, 63, 31), strap_dark, (134, 129, 120, 255),
           (186, 181, 171, 255), strap_weave)
    # stitch hem 32x16: cloth with a dashed seam
    _cloth(draw, (0, 32, 31, 47), white, white_dark, white_light, weave)
    for x in range(2, 30, 4):
        draw.line([(x, 36), (x + 1, 36)], fill=(176, 171, 162, 255))
        draw.line([(x, 40), (x + 1, 40)], fill=(176, 171, 162, 255))
    # unused corner stays transparent
    return img


# --------------------------------------------------------------------------- cubes
# (name, from, to, faces) - faces map: which UV region each side uses
PATCH = 'cloth'
PATCH_DARK = 'cloth_dark'
STRAP = 'strap'
STRAP_DARK = 'strap_dark'
STITCH = 'stitch'

CUBES = [
    # The patch itself, flat against the LEFT eye.  In blueprint space the model
    # faces -Z and the character's right hand is +X (the same convention the
    # dwarf/ghoul blueprints use), so the left eye lives at negative X.
    ('patch_face', (-3.95, 27.10, -4.45), (-0.35, 29.90, -3.92),
     {'north': PATCH, 'south': PATCH_DARK, 'east': STITCH, 'west': PATCH,
      'up': PATCH, 'down': PATCH_DARK}),
    # a single raised hem, top and bottom, so it reads as cloth and not a plate
    ('patch_hem_top', (-4.05, 29.90, -4.36), (-0.20, 30.12, -3.94),
     {'north': STITCH, 'south': PATCH_DARK, 'east': STITCH, 'west': STITCH,
      'up': STITCH, 'down': PATCH_DARK}),
    ('patch_hem_bottom', (-4.05, 26.88, -4.36), (-0.20, 27.10, -3.94),
     {'north': STITCH, 'south': PATCH_DARK, 'east': STITCH, 'west': STITCH,
      'up': PATCH, 'down': STITCH}),
    # the tie that carries the patch up to the band
    ('patch_tie', (-2.85, 29.90, -4.30), (-1.55, 30.85, -3.92),
     {'north': STRAP, 'south': STRAP_DARK, 'east': STRAP, 'west': STRAP,
      'up': STRAP, 'down': STRAP_DARK}),
    # the band at the hairline: thin, and only just proud of the head
    ('band_front', (-4.12, 30.55, -4.14), (4.12, 31.10, -3.88),
     {'north': STRAP, 'south': STRAP_DARK, 'east': STRAP, 'west': STRAP,
      'up': STRAP, 'down': STRAP_DARK}),
    ('band_left', (-4.14, 30.55, -4.14), (-3.88, 31.10, 4.14),
     {'north': STRAP, 'south': STRAP_DARK, 'east': STRAP, 'west': STRAP,
      'up': STRAP, 'down': STRAP_DARK}),
    ('band_right', (3.88, 30.55, -4.14), (4.14, 31.10, 4.14),
     {'north': STRAP, 'south': STRAP_DARK, 'east': STRAP, 'west': STRAP,
      'up': STRAP, 'down': STRAP_DARK}),
    ('band_back', (-4.12, 30.55, 3.88), (4.12, 31.10, 4.14),
     {'north': STRAP, 'south': STRAP_DARK, 'east': STRAP, 'west': STRAP,
      'up': STRAP, 'down': STRAP_DARK}),
    # the knot and its two loose ends, tied behind the right ear
    ('knot', (3.82, 29.95, 3.86), (4.52, 31.18, 4.58),
     {'north': STRAP, 'south': STRAP_DARK, 'east': STRAP, 'west': STRAP,
      'up': STRAP, 'down': STRAP_DARK}),
    ('knot_end_a', (3.92, 28.05, 4.02), (4.42, 30.02, 4.44),
     {'north': STRAP, 'south': STRAP_DARK, 'east': STRAP_DARK, 'west': STRAP,
      'up': STRAP, 'down': STRAP_DARK}),
    ('knot_end_b', (4.34, 28.45, 4.24), (4.88, 30.10, 4.72),
     {'north': STRAP, 'south': STRAP_DARK, 'east': STRAP_DARK, 'west': STRAP,
      'up': STRAP, 'down': STRAP_DARK}),
]

BONES = [
    # (name, origin, cube names)
    ('eyepatch_patch', [-2.15, 28.50, -4.20],
     ['patch_face', 'patch_hem_top', 'patch_hem_bottom', 'patch_tie']),
    ('eyepatch_band', [0.0, 30.82, 0.0],
     ['band_front', 'band_left', 'band_right', 'band_back',
      'knot', 'knot_end_a', 'knot_end_b']),
]

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
            'name': name, 'origin': [round(v, 4) for v in origin], 'rotation': [0.0, 0.0, 0.0],
            'color': 0, 'uuid': uid(f'bone:{name}'), 'export': True, 'mirror_uv': False,
            'isOpen': True, 'locked': False, 'visibility': True, 'autouv': 0,
            'children': [by_name[cube]['uuid'] for cube in cube_names],
        })
    root = {
        'name': 'eyepatch_root', 'origin': list(ROOT_ORIGIN), 'rotation': [0.0, 0.0, 0.0],
        'color': 0, 'uuid': uid('bone:root'), 'export': True, 'mirror_uv': False,
        'isOpen': True, 'locked': False, 'visibility': True, 'autouv': 0,
        'children': children,
    }
    return {
        'meta': {'format_version': '4.10', 'model_format': 'free', 'box_uv': False},
        'name': MODEL, 'model_identifier': MODEL, 'visible_box': [5, 5, 1],
        'resolution': {'width': 16, 'height': 16}, 'elements': elements,
        'outliner': [root], 'textures': [texture_entry],
        # No clip: the eyepatch is strapped to the head, it does not breathe.
        # (The rig would play an 'idle' anyway; without one ModelEngine simply
        # has nothing to run, which is exactly what we want here.)
        'animations': [],
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
    print(f'{len(model["elements"])} cubes in {len(model["outliner"][0]["children"])} bones -> {out}')

    if args.preview:
        sys.path.insert(0, str(HERE))
        import build_tentacles                       # reuse the flat-shaded renderer
        panel = (520, 520)
        # the head only: the accessory is 9 x 4.3 x 9.2 units, so frame the head
        centre = (0.0, 28.6, 0.0)
        common = dict(scale=26.0, size=panel, texture=texture, head=True,
                      centre=centre, perspective=0.0)
        build_tentacles.preview(model, out / 'eyepatch_front.png', title='вид спереди',
                                yaw=180, pitch=0, **common)
        build_tentacles.preview(model, out / 'eyepatch_angle.png', title='вид 3/4',
                                yaw=215, pitch=12, **common)
        build_tentacles.preview(model, out / 'eyepatch_side.png', title='вид сбоку',
                                yaw=270, pitch=4, **common)
        names = ('eyepatch_front', 'eyepatch_angle', 'eyepatch_side')
        combo = Image.new('RGB', (panel[0] * len(names), panel[1]), (24, 28, 42))
        for index, name in enumerate(names):
            combo.paste(Image.open(out / f'{name}.png'), (panel[0] * index, 0))
        combo.save(out / 'eyepatch_preview.png')


if __name__ == '__main__':
    main()
