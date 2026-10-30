#!/usr/bin/env python3
"""Checks the «АКСЕССУАРЫ» menu title against the resource pack's own font.

The accessory menu must use the same glyphs, the same cap height and the same
baseline as МЕНЮ/ДОНАТ/ВАРПЫ..., i.e. look exactly like the DeluxeMenus menus,
instead of the old 50px hand-drawn bitmap.

Usage: python3 tools/accessories-model/test_title.py [--pack=path/to/Elytrix-RP-1.21.zip]
"""
import sys
import unittest
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from compose_title import WORD, extract_font, compose  # noqa: E402

TITLE = 'assets/reallyworld/textures/gui/title/elytrix_accessories.png'
REFERENCE = 'assets/reallyworld/textures/gui/title/title_00.png'
FONT = 'assets/minecraft/font/default.json'
GLYPH = 'ꏠ'


def load_zip_png(archive, name):
    with zipfile.ZipFile(archive) as z, z.open(name) as handle:
        return np.array(Image.open(handle).convert('RGBA'))


def letter_runs(mask):
    runs, inside = [], False
    for x, filled in enumerate(mask.any(axis=0)):
        if filled and not inside:
            start, inside = x, True
        elif not filled and inside:
            runs.append((start, x - 1))
            inside = False
    if inside:
        runs.append((start, mask.shape[1] - 1))
    return runs


class TitleTests(unittest.TestCase):
    def setUp(self):
        pack = [a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--pack=')]
        self.pack = Path(pack[0]) if pack else ROOT / 'rp/Elytrix-RP-1.21.zip'
        self.reference = load_zip_png(self.pack, REFERENCE)
        self.title = np.array(Image.open(
            ROOT / 'tools/accessories-integration/staging-assets' / TITLE).convert('RGBA'))

    def test_same_cell_size_and_baseline(self):
        self.assertEqual(self.title.shape, (32, 128, 4))
        rows = np.where(self.title[:, :, 3].any(axis=1))[0]
        # МЕНЮ/ДОНАТ/... occupy rows 18..23 inside the 32px cell of title_00.png
        self.assertEqual((int(rows.min()), int(rows.max())), (18, 23))

    def test_bitmap_is_the_composed_pack_font(self):
        """The shipped bitmap must be exactly the pack glyphs laid out by compose_title.py."""
        expected, width, left = compose(extract_font_bytes(self.reference))
        self.assertTrue(np.array_equal(expected, self.title))
        self.assertEqual((width, left), (62, 1))   # 10 letters, 1px gaps, centred on x=32

    def test_glyphs_are_the_pack_glyphs(self):
        ink = self.title[:, :, 3] > 0
        runs = letter_runs(ink)
        # Ы is two strokes 2px apart, so the word yields one run more than it has letters
        self.assertEqual(len(runs), len(WORD) + 1)
        for (_, a_end), (b_start, _) in zip(runs, runs[1:]):
            self.assertEqual(b_start - a_end, 2)   # 1px letter gap plus the 1px separator
        # КАЗИНО (row 4, column 2) gives a clean 'А' from the same atlas
        casino = self.reference[4 * 32:5 * 32, 2 * 128:3 * 128, 3] > 10
        casino = casino[18:24]
        casino_runs = letter_runs(casino)
        letters = {char: casino[:, start:end + 1] for (start, end), char in zip(casino_runs, 'КАЗИНО')}
        self.assertTrue(np.array_equal(letters['А'], ink[18:24, runs[0][0]:runs[0][1] + 1]))
        self.assertTrue(np.array_equal(letters['К'], ink[18:24, runs[1][0]:runs[1][1] + 1]))

    def test_two_tone_shading_like_the_pack(self):
        rgb, ink = self.title[:, :, :3], self.title[:, :, 3] > 0
        for row in range(18, 21):
            self.assertLessEqual({tuple(c) for c in rgb[row][ink[row]]}, {(76, 62, 77)})
        for row in range(21, 24):
            self.assertLessEqual({tuple(c) for c in rgb[row][ink[row]]}, {(57, 46, 61)})

    def test_font_provider_metrics(self):
        """The registered glyph must keep the metrics of the other title providers."""
        merged = ROOT / 'elytrix-accessories-title-test.zip'
        if not merged.is_file():
            self.skipTest('merged test pack is not built')
        import json
        with zipfile.ZipFile(merged) as z:
            providers = json.loads(z.read(FONT))['providers']
            entry = [p for p in providers if GLYPH in p.get('chars', [])]
            self.assertEqual(len(entry), 1)
            self.assertEqual(entry[0]['ascent'], 26)
            self.assertEqual(entry[0]['height'], 32)
            self.assertEqual(entry[0]['file'], 'reallyworld:gui/title/elytrix_accessories.png')
            with z.open(TITLE) as handle:
                self.assertTrue(np.array_equal(
                    np.array(Image.open(handle).convert('RGBA')), self.title))


def extract_font_bytes(reference):
    """extract_font() works on files; write the atlas to a temporary one."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'title.png'
        Image.fromarray(reference).save(path)
        return extract_font(path)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]] + [a for a in sys.argv[1:]
                                        if a.startswith('-') and not a.startswith('--pack=')])
