#!/usr/bin/env python3
"""Checks the generated kagune assets and the merged resource pack.

Usage:
    python3 tools/accessories-model/test_model.py            # source assets
    python3 tools/accessories-model/test_model.py --pack=path/to/new-pack.zip \
        [--base=path/to/original-pack.zip]
"""
import io
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
PARTS = ('a', 'b', 'c', 'd', 'e', 'f', 'g')
SNAP = 22.5
ICON = 'assets/reallyworld/textures/item/freak/kaneki_tentacles_icon.png'


def load_blueprint():
    return json.loads((HERE / f'{MODEL}.bbmodel').read_text(encoding='utf-8'))


def flatten(node, out):
    for bone in node:
        if isinstance(bone, str):
            continue
        out[bone['name']] = bone
        flatten(bone.get('children', []), out)


def _chain(bone):
    """The bones of one blade, root first."""
    out = []
    while bone is not None:
        out.append(bone)
        nested = [child for child in bone.get('children', []) if isinstance(child, dict)]
        bone = nested[0] if nested else None
    return out


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
        # every blade is a chain of six bones: the curve is carried by the bones, so
        # the joints can turn by arbitrary angles instead of the 22.5 deg cube grid
        for bone in tendrils:
            chain, node = [], bone
            while node is not None:
                chain.append(node['name'])
                nested = [child for child in node['children'] if isinstance(child, dict)]
                node = nested[0] if nested else None
            self.assertEqual(chain, [bone['name'][:-1] + part for part in PARTS])

    def test_every_blade_grows_from_the_same_spot(self):
        """The reference has all four tendrils leaving one point on the back."""
        roots = [b['origin'] for b in self.model['outliner'][0]['children']]
        self.assertEqual(len({round(r[1], 1) for r in roots}), 1, 'same height')
        self.assertLess(max(r[2] for r in roots) - min(r[2] for r in roots), 1.0,
                        'and the same depth - the depth offset only avoids z-fighting')
        self.assertEqual(len({round(r[0], 1) for r in roots}), 2,
                         'left and right, a hair apart so they do not overlap exactly')

    def test_the_fan_spreads_in_the_top_view(self):
        """Seen from above the four tendrils must fan out, not collapse into a line."""
        import build_tentacles
        yaws = [spec['yaw'] for spec in build_tentacles.BLADES]
        self.assertEqual(len(set(yaws)), 4, 'four different directions')
        self.assertGreater(max(yaws) - min(yaws), 30, 'and a wide spread')
        paths = [build_tentacles.blade_path(spec) for spec in build_tentacles.BLADES]
        points = [point for path in paths for point in path]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        zs = [p[2] for p in points]
        self.assertGreater(max(xs) - min(xs), 60, 'the fan is wider than the body')
        self.assertGreater(max(ys) - min(ys), 30, 'and taller')
        self.assertGreater(max(zs) - min(zs), 12, 'and it opens up behind the back')

    def test_the_blades_are_slim(self):
        """v4 was 8-9 units across and nearly as deep - it read as a fat strap."""
        widest = max(e['to'][1] - e['from'][1] for e in self.model['elements'])
        deepest = max(e['to'][2] - e['from'][2] for e in self.model['elements'])
        self.assertLess(widest, 7.2, 'a tendril, not a beam')
        self.assertLess(deepest, 6.2, 'and about as deep as it is wide')

    def test_the_curve_comes_from_the_bones(self):
        """Cubes stay on the 22.5 grid only if they never rotate; here none do."""
        for element in self.model['elements']:
            self.assertEqual([v for v in element['rotation'] if v], [],
                             'cubes are unrotated: the bone chain bends the blade')
        chains = [[bone['rotation'][2] for bone in _chain(tendril)]
                  for tendril in self.model['outliner'][0]['children']]
        self.assertTrue(chains, 'the chain must actually turn')
        # the first bone carries the direction the tendril leaves the back (up or
        # down), the following joints only bend it, so they stay gentle
        for chain in chains:
            self.assertLessEqual(max(abs(t) for t in chain[1:]), 22.0, 'joints stay gentle')
            self.assertGreaterEqual(min(len(chain), 7), 7, 'seven joints per blade')

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
            rotated = [k for k in range(3) if element['rotation'][k]]
            self.assertLessEqual(len(rotated), 1, 'one rotation axis per cube')
            for k in rotated:
                angle = element['rotation'][k] / SNAP
                self.assertAlmostEqual(angle, round(angle), msg='angle must be a multiple of 22.5')
                self.assertLessEqual(abs(element['rotation'][k]), 90)
            self.assertGreater(element['from'][2], -4.0, 'never punches through the chest')
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
        self.assertEqual(len(animation['animators']), 28, 'every joint of every blade moves')
        for animator in animation['animators'].values():
            keys = animator['keyframes']
            self.assertEqual(keys[0]['time'], 0)
            self.assertEqual(keys[-1]['time'], animation['length'])
            self.assertEqual(keys[0]['data_points'], keys[-1]['data_points'], 'seamless loop')
            largest = 0.0
            for axis in ('x', 'y', 'z'):
                values = [float(k['data_points'][0][axis]) for k in keys]
                # the keys are absolute, so they carry the blade's own bend as well;
                # what has to stay readable is the peak-to-peak swing around it
                largest = max(largest, max(values) - min(values))
            self.assertLess(largest, 27, 'the swing stays readable')
            self.assertGreater(largest, 4.0, 'more motion than the 1-degree v3 sway')


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
                         or name == f'assets/modelengine/textures/entity/models/{MODEL}.png'
                         or name.startswith('assets/reallyworld/')
                         and 'kaneki_tentacles_icon' in name}
            self.assertEqual(generated, expected)
            for name in generated:
                source = HERE / 'assets' / name[len('assets/'):]
                self.assertEqual(pack.read(name), source.read_bytes(), name)

    def test_item_definitions(self):
        with zipfile.ZipFile(self.pack) as pack:
            items = [n for n in pack.namelist() if n.startswith(f'assets/modelengine/items/{MODEL}/')]
            self.assertEqual(len(items), 28)
            for name in items:
                definition = json.loads(pack.read(name))['model']
                self.assertEqual(definition['model'],
                                 f'modelengine:{MODEL}/' + Path(name).stem)
                self.assertEqual(definition['type'], 'minecraft:model')
                self.assertEqual(definition['tints'][0]['type'], 'minecraft:custom_model_data')

    def test_menu_icon_exists(self):
        """The menu puts the icon on a RED_DYE; without these files the slot shows
        the purple/black missing-texture checkerboard."""
        with zipfile.ZipFile(self.pack) as pack:
            names = set(pack.namelist())
            for name in ('assets/reallyworld/items/kaneki_tentacles_icon.json',
                         'assets/reallyworld/models/item/freak/kaneki_tentacles_icon.json',
                         ICON):
                self.assertIn(name, names)
            definition = json.loads(pack.read('assets/reallyworld/items/kaneki_tentacles_icon.json'))
            self.assertEqual(definition['model']['model'], 'reallyworld:item/freak/kaneki_tentacles_icon')
            model = json.loads(pack.read('assets/reallyworld/models/item/freak/kaneki_tentacles_icon.json'))
            self.assertEqual(model['textures']['0'], 'reallyworld:item/freak/kaneki_tentacles_icon')
            image = Image.open(io.BytesIO(pack.read(ICON)))
            self.assertEqual(image.size, (32, 32))
            self.assertEqual(image.mode, 'RGBA')
            self.assertGreater(sum(1 for px in image.getdata() if px[3] > 0), 120, 'icon is drawn')

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
            allowed_changes = {FONT} | {n for n in changed
                                        if MODEL in n or 'kaneki_tentacles_icon' in n}
            self.assertLessEqual(changed, allowed_changes,
                                 'only the tentacle model, its icon and the font may change')
            # the title bitmap may be new or redrawn, everything else is model data
            self.assertIn(TITLE, new_names, 'the menu title bitmap must survive the merge')
            allowed = {n for n in added if n.startswith('assets/modelengine/') and MODEL in n}
            allowed |= {n for n in added if n.startswith('assets/reallyworld/')
                        and 'kaneki_tentacles_icon' in n}
            self.assertLessEqual(added - {TITLE}, allowed)
            for name in ('pack.png', 'assets/minecraft/atlases/blocks.json',
                         'assets/minecraft/items/leather_horse_armor.json',
                         'assets/minecraft/models/item/leather_horse_armor.json'):
                self.assertIn(name, new_names)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]] + [a for a in sys.argv[1:]
                                        if a.startswith('-') and not a.startswith(('--pack=', '--base='))])
