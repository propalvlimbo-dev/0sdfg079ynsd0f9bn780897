#!/usr/bin/env python3
"""Adds the tiny Elytrix notice font to `rp/Elytrix-RP-1.21.zip`.

The owner asked for the "you can't do that in /god or /fly" notice to be written
in a small, pretty font that comes from the resource pack instead of a plain chat
line.  This script draws a pixel font (DejaVu Sans Bold, auto-fitted into 8x8
cells, antialiased, white so the message's own colour tints it) and registers it
as the bitmap font `reallyworld:small`, which `ElytrixEventGuard` then puts on its
action-bar component (`font: reallyworld:small` in its config.yml).

Run it AFTER `tools/accessories-model/merge_pack.py` and
`tools/donate-models/patch_rp_fame.py`: it only ADDS two files and never touches
anything else in the pack.  The rewrite is deterministic (fixed timestamps,
sorted entries), so re-running it produces the identical archive.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'rp/Elytrix-RP-1.21.zip'

FONT_ID = 'small'
NAMESPACE = 'reallyworld'
CELL = 8
COLS = 16
ASCENT = 7
HEIGHT = 8

JSON_PATH = 'assets/%s/font/%s.json' % (NAMESPACE, FONT_ID)
PNG_PATH = 'assets/%s/textures/font/%s.png' % (NAMESPACE, FONT_ID)

# The characters the notice lines are built from: Cyrillic, Latin, digits and the
# punctuation the server's messages use.  Index 0 of every row is left blank on
# purpose - a bitmap font must not claim codepoints it does not define.
CHARSET = (
    u'АБВГДЕЁЖЗИЙКЛМНО'
    u'ПРСТУФХЦЧШЩЪЫЬЭЮЯ'
    u'абвгдеёжзийклмно'
    u'прстуфхцчшщъыьэюя'
    u'ABCDEFGHIJKLMNOP'
    u'QRSTUVWXYZabcdef'
    u'ghijklmnopqrstuv'
    u'wxyz0123456789 ,'
    u'.:;!?-–—/()[]«»"'
    u"'№%+=*<>|♥●•·…↑↓→"
)

FONTS = (
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
)


def pick_font_path() -> str:
    for candidate in FONTS:
        if os.path.isfile(candidate):
            return candidate
    raise SystemExit('no TrueType font with Cyrillic support found: %s' % (FONTS,))


def build_atlas():
    """Returns (png_bytes, rows_of_chars)."""
    from PIL import Image, ImageDraw, ImageFont  # noqa: E402  (needs the sandbox venv)

    path = pick_font_path()
    chars = list(CHARSET)
    rows = [chars[i:i + COLS] for i in range(0, len(chars), COLS)]
    width = COLS * CELL
    height = len(rows) * CELL

    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = None
    for size in (10, 9, 8, 7, 6, 5):
        candidate = ImageFont.truetype(path, size)
        widest = max(candidate.getbbox(c)[2] - candidate.getbbox(c)[0] for c in chars)
        tall = max(candidate.getbbox(c)[3] - candidate.getbbox(c)[1] for c in chars)
        if widest <= CELL and tall <= CELL:
            font = candidate
            break
    if font is None:
        raise SystemExit('could not fit the font into a %dx%d cell' % (CELL, CELL))

    for row_index, row in enumerate(rows):
        for col_index, char in enumerate(row):
            box = font.getbbox(char)
            w = box[2] - box[0]
            h = box[3] - box[1]
            x = col_index * CELL + (CELL - w) // 2 - box[0]
            y = row_index * CELL + (CELL - h) // 2 - box[1]
            draw.text((x, y), char, font=font, fill=(255, 255, 255, 255))

    buffer = io.BytesIO()
    image.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue(), rows


def build_font_json(rows):
    return json.dumps(
        {'providers': [{
            'type': 'bitmap',
            'file': '%s:font/%s.png' % (NAMESPACE, FONT_ID),
            'ascent': ASCENT,
            'height': HEIGHT,
            'chars': [''.join(row) for row in rows],
        }]},
        ensure_ascii=False, indent=2, sort_keys=False).encode('utf-8') + b'\n'


FIXED_DATE = (2020, 1, 1, 0, 0, 0)


def main() -> int:
    if not PACK.is_file():
        raise SystemExit('pack not found: %s' % PACK)

    png, rows = build_atlas()
    font_json = build_font_json(rows)

    with zipfile.ZipFile(PACK) as src:
        entries = [(i.filename, src.read(i.filename)) for i in sorted(src.infolist(),
                                                                      key=lambda i: i.filename)]

    names = {name for name, _ in entries}
    if JSON_PATH in names or PNG_PATH in names:
        raise SystemExit('the notice font is already in the pack: %s / %s' % (JSON_PATH, PNG_PATH))

    entries.append((JSON_PATH, font_json))
    entries.append((PNG_PATH, png))
    entries.sort(key=lambda item: item[0])

    with zipfile.ZipFile(PACK, 'w', zipfile.ZIP_DEFLATED) as out:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            out.writestr(info, data)

    blob = PACK.read_bytes()
    sha1 = hashlib.sha1(blob).hexdigest()
    sha256 = hashlib.sha256(blob).hexdigest()
    print('notice font added: %s + %s' % (JSON_PATH, PNG_PATH))
    print('glyphs: %d (%d rows x %d cols, cell %dx%d)'
          % (len(CHARSET), len(rows), COLS, CELL, CELL))
    print('files:  %d' % len(entries))
    print('size:   %d' % len(blob))
    print('sha1:   %s' % sha1)
    print('sha256: %s' % sha256)
    print('')
    print('next: put this sha1 into plugins/ElytrixRP/config.yml (2 places):')
    print('  %s' % sha1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
