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
PATCH_ICON = 'kaneki_eyepatch_icon'
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


def build_patch_icon():
    """A white eyepatch with the strap, drawn pixel by pixel.

    Same 32x32 grid and the same outline-first technique as the kagune icon, so
    the two slots of the menu look like they belong to one set.  The patch is an
    octagon (cut corners), the strap leaves it to both sides and the knot sits
    on the right - the way the patch actually sits on the head.
    """
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    outline = (46, 46, 54, 255)
    shade = (186, 182, 174, 255)
    cloth = (231, 228, 221, 255)
    light = (252, 251, 247, 255)
    seam = (168, 164, 156, 255)

    # the strap: two bands leaving the patch towards the top and bottom right
    for y0, y1, colour, width in ((11, 5, outline, 4), (15, 21, outline, 4)):
        draw.line([(5, y0), (27, y1)], fill=colour, width=width)
    draw.line([(5, 11), (27, 5)], fill=shade, width=2)
    draw.line([(5, 15), (27, 21)], fill=shade, width=2)
    draw.line([(6, 10), (26, 5)], fill=cloth, width=1)
    draw.line([(6, 16), (26, 21)], fill=cloth, width=1)

    # the patch: an octagon of cloth with a raised hem and one stitched fold
    draw.polygon([(9, 8), (22, 8), (24, 10), (24, 23), (22, 25), (9, 25), (7, 23), (7, 10)],
                 fill=outline)
    draw.polygon([(10, 9), (21, 9), (23, 11), (23, 22), (21, 24), (10, 24), (8, 22), (8, 11)],
                 fill=cloth)
    draw.polygon([(10, 9), (21, 9), (23, 11), (10, 12), (8, 11)], fill=light)
    draw.polygon([(23, 21), (23, 22), (21, 24), (10, 24), (8, 22), (8, 21)], fill=shade)
    draw.line([(9, 13), (22, 13)], fill=seam)
    draw.line([(9, 20), (22, 20)], fill=seam)
    # the knot on the strap behind the ear
    draw.rectangle([22, 4, 27, 9], fill=outline)
    draw.rectangle([23, 5, 26, 8], fill=shade)
    draw.line([(24, 6), (25, 7)], fill=cloth)
    return img


def build_model(icon=ICON):
    """A plain generated item model: the 32x32 texture is already the whole icon.

    The same shape v18 shipped with, so the two menu icons render identically on
    the servers that already show the kagune slot.
    """
    return {
        'parent': 'minecraft:item/generated',
        'textures': {'layer0': f'reallyworld:item/freak/{icon}'},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', default='/tmp/icon')
    args = parser.parse_args()
    out = Path(args.out_dir) / 'assets'
    (out / 'reallyworld/textures/item/freak').mkdir(parents=True, exist_ok=True)
    (out / 'reallyworld/models/item/freak').mkdir(parents=True, exist_ok=True)
    (out / 'reallyworld/items').mkdir(parents=True, exist_ok=True)

    for name, image in ((ICON, build_icon()), (PATCH_ICON, build_patch_icon())):
        image.save(out / f'reallyworld/textures/item/freak/{name}.png')
        image.resize((256, 256), Image.NEAREST).save(
            Path(args.out_dir) / f'{name}_preview.png')
        model = out / f'reallyworld/models/item/freak/{name}.json'
        model.write_text(json.dumps(build_model(name), separators=(',', ':')) + '\n', encoding='utf-8')
        definition = out / f'reallyworld/items/{name}.json'
        definition.write_text(json.dumps(
            {'model': {'type': 'minecraft:model', 'model': f'reallyworld:item/freak/{name}'}},
            separators=(',', ':')) + '\n', encoding='utf-8')
        print(f'{name}: {image.size[0]}x{image.size[1]} texture, model + item definition -> {out}')


if __name__ == '__main__':
    main()
