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

TITLE = 'Щупальца Канэки — v18'
SUBTITLE = ('низ и верх отличаются друг от друга, и появилась анимация: руки ходят вперёд-назад и вверх-вниз, каждая в своей фазе')
ROWS = [
    ('Форма', '4 руки из одной точки на спине: 13/13/14/14 костей, кончик заворачивает вперёд'),
    ('Объём', 'каждая кость — квадрат + повёрнутый на 45° (0.707) = восьмигранник'),
    ('Пара', 'верх до x=±18.4 и z=−3.0; низ до x=±19.6, глубже и тоньше — низ не зеркало верха'),
    ('Движение', 'четыре руки ходят вразнобой: вверх-вниз и вперёд-назад, без рывков на стыке петли'),
    ('Клип', 'idle 4 с, петля: ±7° на кончике, у корня ±1°; значения — добавка к ресту, не абсолютные углы'),
    ('Спек', 'свой elytrix_kaneki_tentacles, а не копия спека крыльев'),
    ('Размер', '39.2 × 13.9 × 10.0 единицы (≈2.45 × 0.87 × 0.63 блока), 112 кубов / 55 моделей'),
    ('Толщина', '3.0 сверху и 2.75 снизу, к концу сходит до 66% и обрывается тупым срезом'),
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
