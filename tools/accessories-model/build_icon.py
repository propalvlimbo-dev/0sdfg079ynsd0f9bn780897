#!/usr/bin/env python3
"""Draws the menu icon for the Kaneki accessory and the item model that shows it.

The `/аксессуары` menu puts the icon on a RED_DYE with the item model
`reallyworld:kaneki_tentacles_icon` (see AccessoryController.java). Without those
files the slot renders the purple/black missing-texture checkerboard, which is the
bug this script fixes.

Everything is drawn pixel by pixel with Pillow - no AI art, no downloaded images.

Usage:
    python3 tools/accessories-model/build_icon.py --out-dir /tmp/icon
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ICON = 'kaneki_tentacles_icon'
SIZE = 32
OUTLINE = (58, 0, 10, 255)
BODY = (168, 16, 26, 255)
MID = (206, 40, 48, 255)
LIGHT = (236, 74, 84, 255)
GLOW = (255, 150, 158, 255)


def spike(draw, root, tip, bend, width, colour):
    """One tapered kagune spike: a curved, pixellated triangle from root to tip."""
    steps = 26
    left, right = [], []
    for i in range(steps + 1):
        t = i / steps
        # quadratic bezier so the spike curves instead of being a straight stick
        x = (1 - t) ** 2 * root[0] + 2 * (1 - t) * t * bend[0] + t * t * tip[0]
        y = (1 - t) ** 2 * root[1] + 2 * (1 - t) * t * bend[1] + t * t * tip[1]
        w = max(0.5, width * (1.0 - t) ** 0.85)
        dx = 2 * (1 - t) * (bend[0] - root[0]) + 2 * t * (tip[0] - bend[0])
        dy = 2 * (1 - t) * (bend[1] - root[1]) + 2 * t * (tip[1] - bend[1])
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        nx, ny = -dy / length, dx / length
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    draw.polygon(left + right[::-1], fill=colour)


def build_icon():
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    root = (16.0, 29.0)
    spikes = [
        ((3.0, 6.5), (9.0, 18.5), 3.0),     # far left, long
        ((9.5, 2.5), (12.5, 16.0), 2.5),    # left, tall
        ((22.5, 2.0), (19.5, 16.0), 2.4),   # right, tall
        ((29.0, 7.5), (22.5, 18.0), 2.7),   # far right
    ]
    # dark silhouette first (the outline), then the body, then the gloss
    for tip, bend, width in spikes:
        spike(draw, root, tip, bend, width + 1.2, OUTLINE)
    for tip, bend, width in spikes:
        spike(draw, root, tip, bend, width, BODY)
    for tip, bend, width in spikes:
        spike(draw, root, tip, bend, width * 0.55, MID)
    # a thin highlight that follows the same curve, so it always stays inside
    for tip, bend, width in spikes:
        left = (root[0] + (bend[0] - root[0]) * 0.30, root[1] + (bend[1] - root[1]) * 0.30)
        far = (root[0] + (tip[0] - root[0]) * 0.80, root[1] + (tip[1] - root[1]) * 0.80)
        spike(draw, left, far, bend, width * 0.22, LIGHT)
    return img


def build_model():
    """One 1/16-block thin plate whose faces show the 32x32 icon."""
    faces = {}
    for name in ('north', 'south', 'east', 'west', 'up', 'down'):
        faces[name] = {'uv': [0, 0, 16, 16], 'texture': '#0'}
    return {
        'credit': 'Elytrix - Kaneki accessory menu icon',
        'textures': {0: f'reallyworld:item/freak/{ICON}', 'particle': f'reallyworld:item/freak/{ICON}'},
        'elements': [{
            'from': [0, 0, 7.6], 'to': [16, 16, 8.4],
            'faces': faces,
        }],
        'display': {
            'gui': {'rotation': [0, 0, 0], 'translation': [0, 0, 0], 'scale': [1, 1, 1]},
            'ground': {'rotation': [0, 0, 0], 'translation': [0, 2, 0], 'scale': [0.5, 0.5, 0.5]},
            'fixed': {'rotation': [0, 0, 0], 'translation': [0, 0, 0], 'scale': [1, 1, 1]},
            'firstperson_righthand': {'rotation': [0, 45, 0], 'translation': [0, 2, 0], 'scale': [0.4, 0.4, 0.4]},
            'firstperson_lefthand': {'rotation': [0, 45, 0], 'translation': [0, 2, 0], 'scale': [0.4, 0.4, 0.4]},
            'thirdperson_righthand': {'rotation': [0, 45, 0], 'translation': [0, 2, 0], 'scale': [0.4, 0.4, 0.4]},
            'thirdperson_lefthand': {'rotation': [0, 45, 0], 'translation': [0, 2, 0], 'scale': [0.4, 0.4, 0.4]},
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', default='/tmp/icon')
    args = parser.parse_args()
    out = Path(args.out_dir) / 'assets'
    (out / 'reallyworld/textures/item/freak').mkdir(parents=True, exist_ok=True)
    (out / 'reallyworld/models/item/freak').mkdir(parents=True, exist_ok=True)
    (out / 'reallyworld/items').mkdir(parents=True, exist_ok=True)

    icon = build_icon()
    icon.save(out / f'reallyworld/textures/item/freak/{ICON}.png')
    icon.resize((256, 256), Image.NEAREST).save(Path(args.out_dir) / 'icon_preview.png')

    model = out / f'reallyworld/models/item/freak/{ICON}.json'
    model.write_text(json.dumps(build_model(), separators=(',', ':')), encoding='utf-8')

    definition = out / f'reallyworld/items/{ICON}.json'
    definition.write_text(json.dumps(
        {'model': {'type': 'minecraft:model', 'model': f'reallyworld:item/freak/{ICON}'}},
        separators=(',', ':')), encoding='utf-8')
    print(f'icon -> {out} ({icon.size[0]}x{icon.size[1]} texture, model + item definition)')


if __name__ == '__main__':
    main()
