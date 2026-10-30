#!/usr/bin/env python3
"""Checks the generated kagune assets and the merged resource pack.

Usage:
    python3 tools/accessories-model/test_model.py            # source assets
    python3 tools/accessories-model/test_model.py --pack=path/to/new-pack.zip \
        [--base=path/to/original-pack.zip]
"""
import json
import math
import sys
import unittest
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = 'elytrix_kaneki_tentacles'
TITLE = 'assets/reallyworld/textures/gui/title/elytrix_accessories.png'
FONT = 'assets/minecraft/font/default.json'
GLYPH = 'ꏠ'
# Cubes further than this from their bone pivot make ModelEngine halve the model
# resolution (JavaItemModel.scaleToFit) - the tendrils must stay under it.
SCALE_LIMIT = 24.0


def load_blueprint():
    return json.loads((HERE / f'{MODEL}.bbmodel').read_text(encoding='utf-8'))


def flatten(node, out):
    for bone in node:
        if isinstance(bone, str):
            continue
        out[bone['name']] = bone
        flatten(bone.get('children', []), out)


class BlueprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = load_blueprint()
        cls.bones = {}
        flatten(cls.model['outliner'], cls.bones)
        cls.elements = {e['uuid']: e for e in cls.model['elements']}

    def test_tendrils_and_bones(self):
        root = self.model['outliner'][0]
        self.assertEqual(root['name'], 'tentacles_root')
        self.assertEqual(root['origin'], [0.0, 20.0, 0.0])
        tendrils = root['children']
        self.assertEqual(len(tendrils), 4, 'upper/lower on both sides')
        names = {b['name'] for b in tendrils}
        self.assertEqual(names, {'left_upper_a', 'left_lower_a', 'right_upper_a', 'right_lower_a'})
        # each root bone owns a second bone for the tip (scaleToFit needs two pivots)
        bones = {b['name']: b for b in tendrils}
        for bone in tendrils:
            nested = [child for child in bone['children'] if isinstance(child, dict)]
            self.assertEqual(len(nested), 1, 'one nested tip bone')
            self.assertEqual(nested[0]['name'], bone['name'][:-1] + 'b')
            self.assertGreater(len([c for c in bone['children'] if isinstance(c, str)]), 3,
                               'the root half has its own cubes')

    def test_no_bone_is_scaled_down(self):
        for name, bone in self.bones.items():
            cubes = [self.elements[u] for u in bone['children'] if isinstance(u, str)]
            if not cubes:
                continue
            pivot = bone['origin']
            furthest = max(math.dist(point, pivot) for cube in cubes
                           for point in (cube['from'], cube['to']))
            self.assertLessEqual(furthest, SCALE_LIMIT, f'{name} would be scaled to half detail')

    def test_segments_are_watertight_and_snapped(self):
        for element in self.model['elements']:
            self.assertTrue(all(a < b for a, b in zip(element['from'], element['to'])))
            self.assertIn(element['rotation'][2], (-45, -22.5, 0, 22.5, 45))
            self.assertGreaterEqual(element['from'][2], 1.5, 'never inside the chest')
            for face, data in element['faces'].items():
                self.assertEqual(data['texture'], 0, face)
                self.assertTrue(all(0 <= value <= 16 for value in data['uv']), face)

    def test_texture(self):
        texture = Image.open(HERE / 'assets/modelengine/textures/entity/models' / f'{MODEL}.png')
        self.assertEqual(texture.size, (64, 64))
        self.assertEqual(texture.mode, 'RGBA')
        colours = {c for c in texture.convert('RGB').getdata()}
        self.assertGreater(len(colours), 30, 'texture must have real shading')

    def test_animation(self):
        animation = self.model['animations'][0]
        self.assertEqual(animation['name'], 'idle')
        self.assertEqual(animation['loop'], 'loop')
        self.assertEqual(len(animation['animators']), 8, 'both bones of every tendril move')
        for animator in animation['animators'].values():
            keys = animator['keyframes']
            self.assertEqual(keys[0]['time'], 0)
            self.assertEqual(keys[-1]['time'], animation['length'])
            self.assertEqual(keys[0]['data_points'], keys[-1]['data_points'], 'seamless loop')
            values = [float(k['data_points'][0]['z']) for k in keys]
            self.assertLess(max(values) - min(values), 9, 'sway stays gentle')
            self.assertTrue(any(abs(v) > 0.5 for v in values))


class PackTests(unittest.TestCase):
    """Runs against a merged pack given with --pack=."""

    def setUp(self):
        packs = [a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--pack=')]
        if not packs:
            self.skipTest('no merged pack given (--pack=...)')
        self.pack = Path(packs[0])

    def test_model_files_match_the_generator(self):
        with zipfile.ZipFile(self.pack) as pack:
            names = set(pack.namelist())
            expected = set()
            for path in sorted((HERE / 'assets').rglob('*')):
                if path.is_file():
                    expected.add('assets/' + path.relative_to(HERE / 'assets').as_posix()
                                 if not path.is_relative_to(HERE / 'assets' / 'modelengine')
                                 else 'assets/modelengine/' + path.relative_to(
                                     HERE / 'assets' / 'modelengine').as_posix())
            generated = {name for name in names
                         if name.startswith(f'assets/modelengine/items/{MODEL}/')
                         or name.startswith(f'assets/modelengine/models/{MODEL}/')
                         or name == f'assets/modelengine/textures/entity/models/{MODEL}.png'}
            self.assertEqual(generated, expected)
            for name in generated:
                source = HERE / 'assets' / name[len('assets/'):]
                self.assertEqual(pack.read(name), source.read_bytes(), name)

    def test_item_definitions(self):
        with zipfile.ZipFile(self.pack) as pack:
            items = [n for n in pack.namelist() if n.startswith(f'assets/modelengine/items/{MODEL}/')]
            self.assertEqual(len(items), 8)
            for name in items:
                definition = json.loads(pack.read(name))['model']
                self.assertEqual(definition['model'],
                                 f'modelengine:{MODEL}/' + Path(name).stem)
                self.assertEqual(definition['type'], 'minecraft:model')
                self.assertEqual(definition['tints'][0]['type'], 'minecraft:custom_model_data')

    def test_title_glyph_registered_once(self):
        with zipfile.ZipFile(self.pack) as pack:
            providers = json.loads(pack.read(FONT))['providers']
            entries = [p for p in providers if GLYPH in p.get('chars', [])]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]['ascent'], 26)
            self.assertEqual(entries[0]['height'], 32)
            self.assertEqual(entries[0]['file'], 'reallyworld:gui/title/elytrix_accessories.png')
            self.assertEqual(len(pack.read(TITLE)), 286)

    def test_system_files_untouched(self):
        base = [a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--base=')]
        base = Path(base[0]) if base else ROOT / 'rp/Elytrix-RP-1.21.zip'
        if base.resolve() == self.pack.resolve():
            self.skipTest('merged pack passed as its own base')
        with zipfile.ZipFile(base) as old, zipfile.ZipFile(self.pack) as new:
            old_names, new_names = set(old.namelist()), set(new.namelist())
            changed = {n for n in old_names & new_names if old.read(n) != new.read(n)}
            added = new_names - old_names
            self.assertEqual(changed, {FONT}, 'only the font file is rewritten')
            # the title bitmap may be new or redrawn, everything else is model data
            self.assertTrue(TITLE in added or TITLE in changed)
            self.assertLessEqual(added - {TITLE},
                                 {n for n in added if n.startswith('assets/modelengine/')
                                  and MODEL in n})
            for name in ('pack.png', 'assets/minecraft/atlases/blocks.json',
                         'assets/minecraft/items/leather_horse_armor.json',
                         'assets/minecraft/models/item/leather_horse_armor.json'):
                self.assertIn(name, new_names)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]] + [a for a in sys.argv[1:]
                                        if a.startswith('-') and not a.startswith(('--pack=', '--base='))])
