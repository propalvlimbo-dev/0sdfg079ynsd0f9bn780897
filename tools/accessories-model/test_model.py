#!/usr/bin/env python3
"""Checks the generated kagune assets and the merged resource pack.

Usage:
    python3 tools/accessories-model/test_model.py            # source assets
    python3 tools/accessories-model/test_model.py --pack=path/to/new-pack.zip \\
        [--base=path/to/original-pack.zip]
"""
import io
import json
import math
import sys
import unittest
import zipfile
from pathlib import Path

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
PARTS = tuple('abcdefghijklmnopqrstuvwx')
SNAP = 22.5
ICON = 'assets/reallyworld/textures/item/freak/kaneki_tentacles_icon.png'
TENDRILS = ('left_upper', 'left_lower', 'right_upper', 'right_lower')


def load_blueprint():
    return json.loads((HERE / f'{MODEL}.bbmodel').read_text(encoding='utf-8'))


def flatten(node, out):
    for bone in node:
        if isinstance(bone, str):
            continue
        out[bone['name']] = bone
        flatten(bone.get('children', []), out)


def _chain(bone):
    """The bones of one tendril, root first."""
    out = []
    node = bone
    while node is not None:
        out.append(node)
        nested = [child for child in node.get('children', []) if isinstance(child, dict)]
        node = nested[0] if nested else None
    return out


def _rot(axis, angle):
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    if axis == 0:
        return ((1, 0, 0), (0, c, -s), (0, s, c))
    if axis == 1:
        return ((c, 0, s), (0, 1, 0), (-s, 0, c))
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _bend(bone, matrix):
    """ModelEngine builds the bone quaternion with rotateZYX: p' = Rz.Ry.Rx.p."""
    out = matrix
    for axis in (2, 1, 0):
        if bone['rotation'][axis]:
            out = _mul(out, _rot(axis, bone['rotation'][axis]))
    return out


def rig_path(chain, cubes_of):
    """Rebuild the tendril exactly the way ModelEngine stacks the bones."""
    matrix = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    point = list(chain[0]['origin'])
    out = [tuple(point)]
    for bone in chain:
        matrix = _bend(bone, matrix)
        cubes = cubes_of[bone['name']]
        length = cubes[0]['to'][0] - bone['origin'][0]
        # every bone is two boxes (square + rolled 45 deg = octagonal section)
        assert len(cubes) == 2, bone['name']
        point = [point[i] + matrix[i][0] * length for i in range(3)]
        out.append(tuple(point))
    return out


class BlueprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = load_blueprint()
        cls.bones = {}
        flatten(cls.model['outliner'], cls.bones)
        cls.elements = {e['uuid']: e for e in cls.model['elements']}
        cls.cubes = {}
        for name, bone in cls.bones.items():
            cls.cubes[name] = [cls.elements[u] for u in bone['children'] if isinstance(u, str)]
        cls.chains = {name: _chain(cls.bones[f'{name}_a']) for name in TENDRILS}
        cls.paths = {name: rig_path(chain, cls.cubes) for name, chain in cls.chains.items()}

    # ------------------------------------------------------------------ top level
    def test_tendrils_and_bones(self):
        root = self.model['outliner'][0]
        self.assertEqual(root['name'], 'tentacles_root')
        self.assertEqual(root['origin'], [0.0, 20.0, 0.0])
        children = {b['name'] for b in root['children']}
        self.assertEqual(children, {'root_knot'} | {f'{name}_a' for name in TENDRILS},
                         'four tendril chains plus the knot they grow out of')
        for name, chain in self.chains.items():
            self.assertGreaterEqual(len(chain), 6, f'{name} is a real chain, not a stick')
            self.assertEqual([b['name'] for b in chain],
                             [f'{name}_{part}' for part in PARTS[:len(chain)]])

    def test_every_tendril_grows_from_the_spine(self):
        """All four starts are inside one another's footprint, on the back."""
        starts = [self.paths[name][0] for name in TENDRILS]
        for x, y, z in starts:
            self.assertLessEqual(abs(x), 1.2, 'on the centre line, not on the shoulders')
            self.assertTrue(13.0 <= y <= 19.0, f'the back, between the ribs and the waist, got y={y}')
            self.assertTrue(1.2 <= z <= 3.0, 'just behind the torso, never in front of it')
        spread = max(math.dist(a, b) for a in starts for b in starts)
        self.assertLess(spread, 2.6, 'one common root, not four separate ones')
        # the knot has to bridge the torso surface (z = 2), otherwise it floats
        knot = self.cubes['root_knot']
        self.assertGreaterEqual(len(knot), 3, 'the knot is a lump, not a plane')
        self.assertLess(min(c['from'][2] for c in knot), 2.0, 'the knot touches the back')
        self.assertGreater(max(c['to'][2] for c in knot), 3.0, 'and stands out of it')

    def test_the_tendrils_never_curl_into_a_hoop(self):
        """The in-game rejection of v9: the tips hooked so far that each tendril
        read as a big red C wrapped around the body.

        A kagune is a spear with a shallow S, not a hoop: the joints of one
        tendril may not add up to a half turn, and the last joint may not hook
        back across the tendril's own axis.
        """
        import build_tentacles
        specs = {spec['name']: spec for spec in build_tentacles.TENDRILS}
        for name, path in self.paths.items():
            bones = build_tentacles.blade_bones(specs[name])
            # ignore the first bone: it carries the tendril's launch direction,
            # what matters here is how much the chain *adds* to it
            heading = max(abs(sum(b['turn'] for b in bones[1:i + 1])) for i in range(len(bones)))
            self.assertLess(heading, 150.0, f'{name}: {heading:.0f} deg of bend is a hoop')
            # a hoop curls back on itself: its two ends are much closer than the
            # path is long.  A fan blade keeps most of its length as a chord.
            arc = sum(b['length'] for b in bones)
            chord = math.dist(path[0], path[-1])
            self.assertGreater(chord / arc, 0.60,
                               f'{name}: the tendril curls back instead of fanning out')
            widest = max(build_tentacles.spline(specs[name]['ctrl']),
                         key=lambda p: abs(p[0]))
            tip, before = path[-1], path[-2]
            self.assertLess(abs(tip[0]), abs(widest[0]) + 0.6,
                            f'{name}: the tip flares outwards instead of finishing the fan')
            radial = (tip[0] - before[0]) * math.copysign(1.0, tip[0])
            self.assertGreater(radial, -1.0, f'{name}: the last joint hooks back like a claw')

    def test_the_rig_reproduces_the_traced_curve(self):
        """The bones must be laid out straight and bent by their rotations.

        v7 placed each bone *on* the curve and rotated it as well, so every joint
        bent twice - that is what looked crooked on the player's back.
        """
        import build_tentacles
        specs = {spec['name']: spec for spec in build_tentacles.TENDRILS}
        for name, path in self.paths.items():
            traced = build_tentacles.blade_path(specs[name])
            self.assertEqual(len(path), len(traced))
            error = max(math.dist(a, b) for a, b in zip(path, traced))
            self.assertLess(error, 0.01, f'{name}: the rig drifted {error:.2f} units')
        # and the rest pose really is straight along +X
        for name, chain in self.chains.items():
            for here, following in zip(chain, chain[1:]):
                self.assertAlmostEqual(following['origin'][1], here['origin'][1], places=3)
                self.assertAlmostEqual(following['origin'][2], here['origin'][2], places=3)
                self.assertGreater(following['origin'][0], here['origin'][0])

    def test_no_zigzag(self):
        """Every joint bends gently - no saw-tooth, no staircase."""
        for name, path in self.paths.items():
            turns = []
            for a, b, c in zip(path, path[1:], path[2:]):
                u = [b[i] - a[i] for i in range(3)]
                v = [c[i] - b[i] for i in range(3)]
                nu = math.sqrt(sum(t * t for t in u)) or 1.0
                nv = math.sqrt(sum(t * t for t in v)) or 1.0
                turns.append(math.degrees(math.acos(max(-1.0, min(1.0,
                    sum(u[i] * v[i] for i in range(3)) / (nu * nv))))))
            self.assertLessEqual(max(turns), 32.0, f'{name}: a joint kinks {max(turns):.0f} deg')
            self.assertLess(sum(turns) / len(turns), 20.0, f'{name}: the curve is even')
        # the cross-section must taper monotonically: the v7 "rib" pattern
        # (1.06 / 0.94 alternating) was half of the saw-tooth look
        # The section is narrow at the root (so four arms leave one point),
        # full in the body and blunt at the end - it must never get *thicker*
        # again after the body, which is what made v7 look saw-toothed.
        for name, chain in self.chains.items():
            widths = [self.cubes[b['name']][0]['to'][1] - self.cubes[b['name']][0]['from'][1]
                      for b in chain]
            body = widths[1:]
            for a, b in zip(body, body[1:]):
                self.assertGreaterEqual(a + 0.05, b, f'{name}: the tendril widens again')

    def test_the_fan_spreads_in_the_top_view(self):
        """Seen from above the four arms must be four separate shapes.

        They spread across the back, not ahead of it: v14 shot them 15 units
        forward and the verdict was "слишком ровно идут, не как у Канеки".

        Symmetric pairs share a bearing, so counting angles is the wrong test.
        What has to hold is that the four outermost points are far apart in
        space - that is what "не плоские" means geometrically.
        """
        apex = {name: max(path, key=lambda p: abs(p[0])) for name, path in self.paths.items()}
        names = list(apex)
        for i, first in enumerate(names):
            for second in names[i + 1:]:
                self.assertGreater(math.dist(apex[first], apex[second]), 2.5,
                                   f'{first} and {second} overlap')
        # the two pairs sit at clearly different heights, otherwise they merge
        # into one thick bar in the back view
        for side in ('right', 'left'):
            self.assertGreater(abs(apex[f'{side}_upper'][1] - apex[f'{side}_lower'][1]), 2.8,
                               f'{side}: the pairs must not sit at the same height')
        # and every tendril has to come round the torso to the front (z < 0 is
        # in front of the spine, the body plane is at z = -2)
        for name, path in self.paths.items():
            self.assertLess(path[-1][2], -1.5, f'{name}: the tips curl forward')
        points = [p for path in self.paths.values() for p in path]
        xs = [p[0] for p in points]
        zs = [p[2] for p in points]
        wide, reach = max(xs) - min(xs), max(zs) - min(zs)
        self.assertGreater(wide, 30.0, 'the arms span the whole back')
        self.assertLess(reach, 12.0, 'the curl is a bend, not a run forward')

    def test_the_arms_open_across_the_back(self):
        """The reference: four arms out of one point on the spine, spreading
        sideways across the back like a claw - not four spears shot forward.

        v14 was exactly that spear and the verdict was "слишком ровно идут".
        """
        import build_tentacles
        specs = {spec['name']: spec for spec in build_tentacles.TENDRILS}
        for name, path in self.paths.items():
            spec = specs[name]
            # every joint travels further from the centre line than the one
            # before it: the arm opens out, it never curls back inside itself
            radii = [abs(p[0]) for p in path]
            for before, after in zip(radii, radii[1:]):
                self.assertGreater(after, before, f'{name}: the arm folds back in')
            # the arm has to *leave* the spine (the arc bulges behind the back)
            # and then curl forward: the last joint must travel towards the way
            # the player faces (-Z), which is what v16 did not do at all.
            self.assertGreater(max(p[2] for p in path), 4.5,
                               f'{name}: the arm still lies flat on the back')
            self.assertLess(path[-1][2], -1.5,
                            f'{name}: the tip must curl towards where the player looks')
            self.assertGreater(max(p[2] for p in path) - path[-1][2], 6.0,
                               f'{name}: the curl at the end is too weak')
            # and it must be long: reach out past the shoulders
            self.assertGreater(max(abs(p[0]) for p in path), 16.0,
                               f'{name}: the arm is too short')
            # the root really sits on the spine, not out on the shoulder
            self.assertLessEqual(abs(path[0][0]), 1.2, f'{name}: root off the centre line')
            self.assertGreaterEqual(path[0][2], 1.6, f'{name}: root in front of the back')
            # three legs like the reference: up/out, sideways, tip
            bones = build_tentacles.blade_bones(spec)
            self.assertGreaterEqual(len(bones), 8, f'{name}: an arm needs elbows, not one bend')

    def test_the_root_knot_stays_compact(self):
        """One narrow point on the spine, not a red backpack."""
        knot = [cube for cube in self.cubes['root_knot']]
        left = min(c['from'][0] for c in knot)
        right = max(c['to'][0] for c in knot)
        self.assertLess(right - left, 7.0, 'the knot grew into a backpack')

    def test_the_blades_are_slim(self):
        """v4 was 8-9 units across and nearly as deep - it read as a fat strap."""
        tendril = [cube for chain in self.chains.values() for bone in chain
                   for cube in self.cubes[bone['name']]]
        widest = max(e['to'][1] - e['from'][1] for e in tendril)
        deepest = max(e['to'][2] - e['from'][2] for e in tendril)
        # v12 was 5.6 across and the verdict was "слишком жирные"
        # v16 was 4.8 across and the verdict was "жирные"
        self.assertLess(widest, 3.4, 'a slim tendril, not a beam')
        self.assertLess(deepest, 3.4, 'and as deep as it is wide - a round tube, not a ribbon')
        for cube in tendril:
            across, through = cube['to'][1] - cube['from'][1], cube['to'][2] - cube['from'][2]
            self.assertLess(abs(across - through), 0.6,
                            'square section: the tube must not be flat')
        # v15 ended on a 0.34 point and the verdict was "убери писюльки"
        tips = [self.cubes[chain[-1]['name']][0] for chain in self.chains.values()]
        for cube in tips:
            self.assertGreater(cube['to'][1] - cube['from'][1], 1.6,
                               'the arm must end on a blunt stump, not a spike')

    def test_the_curve_comes_from_the_bones(self):
        """Cubes stay on the 22.5 grid only if they never rotate; here none do."""
        for element in self.model['elements']:
            # only the 45 deg roll of the octagonal section is allowed: the curve
            # itself must come from the bones, never from a cube angle
            for axis in (1, 2):
                self.assertEqual(element['rotation'][axis], 0.0,
                                 'no pitch/yaw on a cube: the bone chain bends the tendril')
            self.assertIn(element['rotation'][0], (0.0, 45.0))
            self.assertEqual(len(element['faces']), 6)

    def test_no_bone_is_scaled_down(self):
        for name, bone in self.bones.items():
            cubes = self.cubes[name]
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

    def test_the_idle_clip_moves_but_stays_a_delta(self):
        """One 'idle' clip that sways the arms - as *deltas*, never absolutes.

        WornAngelRig keeps re-playing the model's own 'idle' on the back slot.
        ModelEngine 4.1 applies a rotation keyframe as
        `bone.localRotation.add(key)` (KeyframeTypes), so a keyframe that already
        carries the solved rest angle doubles every bend - that is what turned v9
        into C-shaped hoops.  Hence: exactly one clip, small values, mean zero.
        """
        clips = self.model['animations']
        self.assertEqual(len(clips), 1, 'one clip, and it is the idle')
        clip = clips[0]
        self.assertEqual(clip['name'], 'idle', 'the rig looks the clip up by this name')
        self.assertEqual(clip['loop'], 'loop')
        self.assertGreaterEqual(clip['length'], 3.0, 'a sway, not a twitch')
        self.assertEqual(len(clip['animators']), len(self.bones) - 2,
                         'every joint sways (the root and the knot stay put)')

        values = []
        moved = {'y': 0, 'z': 0}
        for animator in clip['animators'].values():
            keys = animator['keyframes']
            self.assertGreaterEqual(len(keys), 12, 'the sway needs real keyframes')
            self.assertEqual(keys[0]['data_points'], keys[-1]['data_points'],
                             'the loop has to close without a jump')
            for key in keys:
                point = key['data_points'][0]
                for axis in ('y', 'z'):
                    value = float(point[axis])
                    values.append(value)
                    if abs(value) > 0.5:
                        moved[axis] += 1
        self.assertLess(max(abs(v) for v in values), 9.0,
                        'past ~9 deg the engine folds the arm - that is the v9 bug')
        self.assertLess(abs(sum(values) / len(values)), 0.15,
                        'a clip of deltas has to average zero, not sit at rest')
        self.assertGreater(moved['z'], 0, 'the arms must swing up and down')
        self.assertGreater(moved['y'], 0, 'and forward and back')

    def test_the_two_pairs_differ(self):
        """Upper and lower arms are not a mirror: the user asked for a slight
        difference, so the lower pair reaches further and curls less."""
        upper = self.paths['right_upper']
        lower = self.paths['right_lower']
        reach_upper = max(point[0] for point in upper)
        reach_lower = max(point[0] for point in lower)
        self.assertGreater(abs(reach_lower - reach_upper), 0.6,
                           'the pairs are a perfect mirror again')
        # and the two pairs do not sit at the same height
        depth_upper = max(point[2] for point in upper)
        depth_lower = max(point[2] for point in lower)
        self.assertGreater(abs(depth_upper - depth_lower), 0.3,
                           'both pairs bulge out to exactly the same depth')


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
        # one item definition per bone that owns cubes (the root owns none)
        expected = len([name for name, bone in BlueprintTests.bones.items()
                        if any(isinstance(c, str) for c in bone['children'])])
        with zipfile.ZipFile(self.pack) as pack:
            items = [n for n in pack.namelist() if n.startswith(f'assets/modelengine/items/{MODEL}/')]
            self.assertEqual(len(items), expected)
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
            self.assertEqual(model['parent'], 'minecraft:item/generated')
            self.assertEqual(model['textures'],
                             {'layer0': 'reallyworld:item/freak/kaneki_tentacles_icon'})
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
