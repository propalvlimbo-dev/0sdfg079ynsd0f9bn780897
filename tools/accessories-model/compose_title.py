#!/usr/bin/env python3
"""Draws the «АКСЕССУАРЫ» menu title with the resource pack's own pixel font.

Every other menu title of the pack (МЕНЮ, ДОНАТ, ВАРПЫ, ...) is a 128x32 cell inside
assets/reallyworld/textures/gui/title/title_00.png. This script copies those glyphs
pixel-for-pixel, lays the word out with the same 1px letter spacing, the same 6px cap
height and the same baseline (rows 18-23), so the accessory menu looks exactly like
the DeluxeMenus menus instead of the old squeezed 50px bitmap.

Pure pixel-art, no AI generation and no external images.

Usage: python3 compose_title.py <title_00.png> <out.png>
"""
import sys

import numpy as np
from PIL import Image

WORD = 'АКСЕССУАРЫ'
LIGHT = (76, 62, 77, 255)   # top three rows of every glyph in title_00.png
DARK = (57, 46, 61, 255)    # bottom three rows
CELL = (128, 32)            # same cell size as every other title in the atlas
BASELINE = 18               # first glyph row of МЕНЮ/ДОНАТ/ВАРПЫ... (glyphs are 6px tall)
BAND = (14, 30)             # vertical slice of the atlas that contains all glyphs

# atlas cell (row, column) -> word drawn there
WORDS = {
    (0, 0): 'МЕНЮ', (0, 1): 'ДОНАТ', (0, 2): 'ВАРПЫ', (0, 3): 'ПУТЕВОДИТЕЛЬ',
    (1, 0): 'КОНТРАКТЫ', (1, 1): 'МАГАЗИН', (1, 2): 'ЭНДЕР-СУНДУК', (1, 3): 'ТОРГОВЕЦ',
    (2, 0): 'НАГРАДЫ', (2, 1): 'РАБОТЫ', (2, 2): 'ПРЕФИКСЫ', (2, 3): 'НАБОРЫ',
    (3, 0): 'КВЕСТЫ', (3, 1): 'КИЛЛЕР', (3, 2): 'БОЕВОЙ ПРОПУСК', (3, 3): 'РТП',
    (4, 0): 'КЕЙС', (4, 1): 'КОПИЗЕЙ', (4, 2): 'КАЗИНО', (4, 3): 'АУКЦИОН',
    (5, 0): 'СКУПЩИК', (5, 1): 'БАРОВАР', (5, 2): 'EL+', (5, 3): 'КЛАН',
    (6, 0): 'РЫНОК', (6, 1): 'ГРОУ-ГАРДЕН', (6, 2): 'ХАЛЯВА', (6, 3): 'КУЗНЕЦ',
}


def _runs(mask):
    columns = mask.any(axis=0)
    out, inside = [], False
    for x, filled in enumerate(columns):
        if filled and not inside:
            start, inside = x, True
        elif not filled and inside:
            out.append((start, x - 1))
            inside = False
    if inside:
        out.append((start, len(columns) - 1))
    return out


def extract_font(atlas_path):
    """Copies each letter out of the atlas; the first occurrence wins."""
    atlas = np.array(Image.open(atlas_path).convert('RGBA'))
    font = {}
    for (row, column), word in WORDS.items():
        cell = atlas[row * 32:(row + 1) * 32, column * 128:(column + 1) * 128]
        band = cell[BAND[0]:BAND[1], :, 3] > 10
        glyph_runs = _runs(band)
        index = 0
        for char in word.replace(' ', ''):
            if index >= len(glyph_runs):
                raise ValueError(f'{word}: atlas runs do not match the text')
            start, end = glyph_runs[index]
            if char == 'Ы':                      # Ы is two strokes with a 2px gap
                tail_start, tail_end = glyph_runs[index + 1]
                glyph = np.zeros((band.shape[0], tail_end - start + 1), bool)
                glyph[:, :end - start + 1] = band[:, start:end + 1]
                glyph[:, tail_start - start:] = band[:, tail_start:tail_end + 1]
                index += 2
            else:
                glyph = band[:, start:end + 1]
                index += 1
            ink_rows = np.where(glyph.any(axis=1))[0]
            glyph = glyph[ink_rows.min():ink_rows.max() + 1]   # crop to the 6px cap height
            font.setdefault(char, glyph)
    return font


def compose(font, word=WORD):
    glyphs = [font[char] for char in word]
    width = sum(glyph.shape[1] for glyph in glyphs) + len(glyphs) - 1
    x0 = 32 - width // 2                        # same centring convention as МЕНЮ
    if x0 < 0 or x0 + width > CELL[0]:
        raise ValueError(f'{word} does not fit a {CELL[0]}px title cell')
    canvas = np.zeros((CELL[1], CELL[0], 4), np.uint8)
    x = x0
    for glyph in glyphs:
        for y in range(glyph.shape[0]):
            for dx in range(glyph.shape[1]):
                if glyph[y, dx]:
                    canvas[BASELINE + y, x + dx] = LIGHT if y < 3 else DARK
        x += glyph.shape[1] + 1
    return canvas, width, x0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: compose_title.py <title_00.png> <out.png>')
    bitmap, word_width, left = compose(extract_font(sys.argv[1]))
    Image.fromarray(bitmap).save(sys.argv[2])
    print(f'{WORD}: {word_width}px wide, starts at x={left} of the {CELL[0]}px cell -> {sys.argv[2]}')
