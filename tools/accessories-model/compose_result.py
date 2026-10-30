#!/usr/bin/env python3
"""Builds the result sheet the user sees: four views plus the numbers.

The four panels come from build_tentacles.py --preview, so the sheet never
invents a picture: it lays out what the generator drew.
"""
import hashlib
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/v10')
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / 'result_preview_v10.png'

TITLE = 'Щупальца Канэки — v10'
SUBTITLE = ('веер из четырёх лучей со спины, глубина 5 единиц, '
            'ни одного витка больше 150°')
ROWS = [
    ('Форма', '4 луча из одного узла: 8/8/6/6 костей, сплайн по референсу'),
    ('Объём', 'каждая кость — квадрат + повёрнутый на 45° (0.707) = восьмигранник'),
    ('Глубина', 'от спинной плоскости z=2.2 до z=7.3 — видно и сверху, и сбоку'),
    ('Круги', 'загиб каждого луча не больше 150°: никаких C-образных обручей'),
    ('Клип', 'анимации нет: плагин больше не переигрывает её поверх рест-позы'),
    ('Спек', 'свой elytrix_kaneki_tentacles, а не копия спека крыльев'),
    ('Размер', '19.7 × 15.2 × 5.0 единицы (≈1.2 × 0.95 × 0.31 блока)'),
]


def font(size, bold=False):
    name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    try:
        return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/' + name, size)
    except Exception:
        return ImageFont.load_default()


def pack_sha1():
    pack = ROOT / 'rp/Elytrix-RP-1.21.zip'
    return hashlib.sha1(pack.read_bytes()).hexdigest()


def main():
    strip = Image.open(SRC / 'tentacles_preview.png').convert('RGB')
    width = strip.width
    head = 118
    row_h = 34
    foot = 40
    body = Image.new('RGB', (width, head + strip.height + 26 + row_h * len(ROWS) + foot), (18, 21, 32))
    draw = ImageDraw.Draw(body)
    draw.rectangle([0, 0, width, 5], fill=(248, 190, 251))
    draw.text((40, 26), TITLE, fill=(240, 240, 248), font=font(40, bold=True))
    draw.text((40, 76), SUBTITLE, fill=(158, 162, 186), font=font(19))
    body.paste(strip, (0, head))
    y = head + strip.height + 26
    label = font(20, bold=True)
    value = font(20)
    for name, text in ROWS:
        draw.text((40, y), name, fill=(248, 190, 251), font=label)
        draw.text((190, y), text, fill=(226, 228, 238), font=value)
        y += row_h
    draw.text((40, y + 4), f'Ресурспак SHA-1 {pack_sha1()}', fill=(140, 143, 166), font=font(17))
    body.save(OUT)
    print('sheet:', OUT, body.size)


if __name__ == '__main__':
    main()
