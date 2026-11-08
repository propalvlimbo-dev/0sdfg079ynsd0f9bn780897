#!/usr/bin/env python3
"""Checks the generated Tokyo Ghoul Kagune + full-body Scolopendra assets and merged resource pack.

Usage:
    python3 tools/accessories-model/test_model.py            # source assets
    python3 tools/accessories-model/test_model.py --pack=path/to/new-pack.zip \\
        [--base=path/to/original-pack.zip]
"""
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = 'elytrix_kaneki_tentacles'
PET = 'elytrix_centipede'
MINI_ME = 'elytrix_mini_me'
KITTEN = 'elytrix_cute_kitten'
MELLSTROY = 'elytrix_mellstroy'
MODELS = (MODEL, PET, MINI_ME, KITTEN, MELLSTROY)
TITLE = 'assets/reallyworld/textures/gui/title/elytrix_accessories.png'
FONT = 'assets/minecraft/font/default.json'
GLYPH = 'ꏠ'
SCALE_LIMIT = 24.0
PARTS = tuple('abcdefghijklmnopqrstuvwx')
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
        assert len(cubes) >= 3, f'{bone["name"]} must use multi-cube rounded cross-section'
        length = cubes[0]['to'][0] - bone['origin'][0]
        point = [point[i] + matrix[i][0] * length for i in range(3)]
        out.append(tuple(point))
    return out


class BlueprintTests(unittest.TestCase):
    """Canonical Tokyo Ghoul Kaneki Ken Rinkaku Kagune (4 tails from spinal Kakuhou)."""

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

    def test_tendrils_and_bones(self):
        root = self.model['outliner'][0]
        self.assertEqual(root['name'], 'tentacles_root')
        children = {b['name'] for b in root['children']}
        self.assertEqual(children, {'root_knot'} | {f'{name}_a' for name in TENDRILS},
                         'four tendril chains plus the spinal Kakuhou knot')
        for name, chain in self.chains.items():
            self.assertGreaterEqual(len(chain), 12, f'{name} is a smooth 13-14 bone Rinkaku tail')
            self.assertEqual([b['name'] for b in chain],
                             [f'{name}_{part}' for part in PARTS[:len(chain)]])

    def test_every_tendril_grows_from_the_spine(self):
        starts = [self.paths[name][0] for name in TENDRILS]
        for x, y, z in starts:
            self.assertLessEqual(abs(x), 1.6, 'rooted near spinal centre line')
            self.assertTrue(13.0 <= y <= 19.0, f'lower/mid lumbar Kakuhou sac, got y={y}')
            self.assertTrue(1.5 <= z <= 3.0, 'just behind the back surface')
        spread = max(math.dist(a, b) for a in starts for b in starts)
        self.assertLess(spread, 3.8, 'compact spinal Kakuhou cluster')
        knot = self.cubes['root_knot']
        self.assertGreaterEqual(len(knot), 5, 'sculpted multi-cube Kakuhou knot')
        self.assertLess(min(c['from'][2] for c in knot), 2.1, 'touches the back')
        self.assertGreater(max(c['to'][2] for c in knot), 3.2, 'emerges visibly from spine')
        self.assertLess(max(c['to'][0] for c in knot) - min(c['from'][0] for c in knot), 7.0,
                        'compact spinal knot, never a wide backpack')

    def test_the_rig_reproduces_the_traced_curve_without_double_bending(self):
        import build_tentacles
        specs = {spec['name']: spec for spec in build_tentacles.TENDRILS}
        for name, path in self.paths.items():
            traced = build_tentacles.blade_path(specs[name])
            self.assertEqual(len(path), len(traced))
            error = max(math.dist(a, b) for a, b in zip(path, traced))
            self.assertLess(error, 0.01, f'{name}: rig drifted {error:.3f} units')
        for name, chain in self.chains.items():
            for here, following in zip(chain, chain[1:]):
                self.assertAlmostEqual(following['origin'][1], here['origin'][1], places=3)
                self.assertAlmostEqual(following['origin'][2], here['origin'][2], places=3)
                self.assertGreater(following['origin'][0], here['origin'][0])

    def test_anime_rinkaku_s_sweep_and_slim_taper(self):
        for name, path in self.paths.items():
            turns = []
            for a, b, c in zip(path, path[1:], path[2:]):
                u = [b[i] - a[i] for i in range(3)]
                v = [c[i] - b[i] for i in range(3)]
                nu = math.sqrt(sum(t * t for t in u)) or 1.0
                nv = math.sqrt(sum(t * t for t in v)) or 1.0
                turns.append(math.degrees(math.acos(max(-1.0, min(1.0,
                    sum(u[i] * v[i] for i in range(3)) / (nu * nv))))))
            self.assertLessEqual(max(turns), 28.0, f'{name}: smooth joint bend ({max(turns):.1f} deg)')
            self.assertGreater(max(p[2] for p in path), 6.5, f'{name}: arches back from spine')
            self.assertLess(path[-1][2], -3.0, f'{name}: predatory Rinkaku tip curls forward (-Z)')
            self.assertGreater(max(abs(p[0]) for p in path), 15.0, f'{name}: wide wing-like spread')

        tendril_cubes = [cube for chain in self.chains.values() for bone in chain
                         for cube in self.cubes[bone['name']]]
        widest = max(e['to'][1] - e['from'][1] for e in tendril_cubes)
        deepest = max(e['to'][2] - e['from'][2] for e in tendril_cubes)
        self.assertLessEqual(widest, 3.0, 'slim muscular Rinkaku tail (<= 3.0 px)')
        self.assertLessEqual(deepest, 3.0, 'round muscular cross-section (<= 3.0 px)')

    def test_zero_rotated_cubes_for_paper_fastutil_safety(self):
        """CRITICAL: ModelEngine 4.1.0 RotationSolver.fetch crashes with
        UnsupportedOperationException on Paper fastutil if a bone mixes cube
        rotation PlaneGroups (e.g. [0,0,0] + [45,0,0]). ALL cubes MUST be [0,0,0]."""
        rotated = [(e['name'], e['rotation']) for e in self.model['elements']
                   if any(abs(a) > 1e-9 for a in e.get('rotation', [0, 0, 0]))]
        self.assertEqual(rotated, [], f'rotated cubes trigger Paper fastutil crash: {rotated[:3]}')
        for element in self.model['elements']:
            self.assertTrue(all(a < b for a, b in zip(element['from'], element['to'])))
            self.assertEqual(len(element['faces']), 6)
            for face, data in element['faces'].items():
                self.assertEqual(data['texture'], 0, face)
                self.assertTrue(all(0.0 <= value <= 16.0 for value in data['uv']), face)

    def test_no_bone_is_scaled_down(self):
        for name, bone in self.bones.items():
            cubes = self.cubes[name]
            if not cubes:
                continue
            pivot = bone['origin']
            furthest = max(math.dist(point, pivot) for cube in cubes
                           for point in (cube['from'], cube['to']))
            self.assertLessEqual(furthest, SCALE_LIMIT, f'{name} exceeds Display scale limit')

    def test_texture_128x128_crimson_obsidian(self):
        texture = Image.open(HERE / 'assets/modelengine/textures/entity/models' / f'{MODEL}.png')
        self.assertEqual(texture.size, (128, 128))
        self.assertEqual(texture.mode, 'RGBA')
        colours = {c for c in texture.convert('RGB').getdata()}
        self.assertGreater(len(colours), 80, 'rich Rc-cell vein & crimson scale shading')

    def test_the_idle_clip_moves_as_zero_mean_deltas(self):
        clips = self.model['animations']
        self.assertEqual(len(clips), 1)
        clip = clips[0]
        self.assertEqual(clip['name'], 'idle')
        self.assertEqual(clip['loop'], 'loop')
        self.assertGreaterEqual(clip['length'], 3.5)
        self.assertEqual(len(clip['animators']), len(self.bones) - 2)

        values = []
        for animator in clip['animators'].values():
            keys = animator['keyframes']
            self.assertGreaterEqual(len(keys), 16)
            self.assertEqual(keys[0]['data_points'], keys[-1]['data_points'])
            for key in keys:
                point = key['data_points'][0]
                for axis in ('x', 'y', 'z'):
                    values.append(float(point[axis]))
        self.assertLess(max(abs(v) for v in values), 9.0, 'deltas stay < 9 deg so curves never fold')
        self.assertLess(abs(sum(values) / len(values)), 0.15, 'zero-mean organic undulation')

    def test_modelengine_itself_can_import_kaneki_blueprint(self):
        java, ecj = os.environ.get('JAVA'), os.environ.get('ECJ')
        if not java or not ecj:
            self.skipTest('set JAVA and ECJ to run the real ModelEngine parser')
        out = Path(tempfile.mkdtemp()) / 'assets'
        result = subprocess.run(
            ['sh', str(HERE / 'generate_assets.sh'), str(HERE / f'{MODEL}.bbmodel'), str(out)],
            capture_output=True, text=True, timeout=300, env=dict(os.environ, JAVA=java, ECJ=ecj))
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn('UnsupportedOperationException', output)
        generated = {p.stem for p in (out / 'assets/modelengine/items' / MODEL).glob('*.json')}
        self.assertEqual(generated, {n for n in self.bones if self.cubes[n]})


class CentipedeBlueprintTests(unittest.TestCase):
    """Tokyo Ghoul Scolopendra crawling across the ENTIRE player body."""

    @classmethod
    def setUpClass(cls):
        cls.model = json.loads((HERE / f'{PET}.bbmodel').read_text(encoding='utf-8'))
        cls.bones = {}
        flatten(cls.model['outliner'], cls.bones)
        cls.elements = {e['uuid']: e for e in cls.model['elements']}
        cls.cubes = {name: [cls.elements[u] for u in bone['children'] if isinstance(u, str)]
                     for name, bone in cls.bones.items()}

    def test_children_are_bones_not_dangling_ids(self):
        def walk(node):
            for bone in node:
                self.assertIsInstance(bone, dict)
                for child in bone.get('children', []):
                    if isinstance(child, str):
                        self.assertIn(child, self.elements)
                    else:
                        self.assertIn('name', child)
                walk([c for c in bone.get('children', []) if isinstance(c, dict)])
        walk(self.model['outliner'])

    def test_anatomy_and_gimbal_free_two_stage_stations(self):
        self.assertEqual(self.model['model_identifier'], PET)
        expected_bones = (
            {'body_root', 'head', 'fang_l', 'fang_r', 'ant_l1', 'ant_l2', 'ant_r1', 'ant_r2',
             'cercus_l', 'cercus_r'}
            | {f'carrier_{i:02d}' for i in range(1, 17)}
            | {f'seg_{i:02d}' for i in range(1, 17)}
            | {f'leg_{s}_{i:02d}' for i in range(2, 16) for s in ('l', 'r')}
        )
        self.assertEqual(set(self.bones), expected_bones)
        self.assertEqual(len(self.model['elements']), 161)
        drawn = [n for n in self.bones if self.cubes[n]]
        self.assertEqual(len(drawn), 53)

    def test_no_cube_is_rotated_and_uvs_in_0_16(self):
        rotated = [(c['name'], c['rotation']) for c in self.model['elements']
                   if any(abs(angle) > 1e-9 for angle in c.get('rotation', [0, 0, 0]))]
        self.assertEqual(rotated, [], 'rotated cubes crash ModelEngine on Paper fastutil')
        for c in self.model['elements']:
            for side, face in c['faces'].items():
                for uv_val in face['uv']:
                    self.assertTrue(0.0 <= uv_val <= 16.0, f'{c["name"]}.{side} UV out of 0..16')

    def test_crawls_across_the_entire_body(self):
        """User requirement: 'Сделай чтобы сколопендра прям по всему телу лазила'.
        Verify animated carrier_01 world path spans thighs/legs, waist, chest, back,
        both flanks/arms, shoulders, and neck!"""
        anims = self.model['animations']
        self.assertEqual(len(anims), 1)
        idle = anims[0]
        carrier1 = self.bones['carrier_01']
        ox, oy, oz = carrier1['origin']
        c1_anim = next(a for a in idle['animators'].values() if a['name'] == 'carrier_01')
        pos_keys = [k for k in c1_anim['keyframes'] if k['channel'] == 'position']
        self.assertGreaterEqual(len(pos_keys), 60)

        # Reconstruct ModelEngine world coordinates from BlockbenchParser position formula:
        # tx = ox - px, ty = oy + py, tz = oz + pz
        xs, ys, zs = [], [], []
        for k in pos_keys:
            dp = k['data_points'][0]
            xs.append(ox - float(dp['x']))
            ys.append(oy + float(dp['y']))
            zs.append(oz + float(dp['z']))

        self.assertLess(min(ys), 9.0, f'crawls down onto thighs/legs (min_y={min(ys):.2f})')
        self.assertGreater(max(ys), 24.5, f'climbs up over shoulders/neck (max_y={max(ys):.2f})')
        self.assertLess(min(xs), -5.0, 'wraps around right arm/flank')
        self.assertGreater(max(xs), 5.0, 'wraps around left arm/flank')
        self.assertLess(min(zs), -2.5, 'crawls across front chest & stomach')
        self.assertGreater(max(zs), 2.5, 'crawls across lower & upper back')

    def test_full_living_loop_animation(self):
        idle = self.model['animations'][0]
        self.assertEqual(idle['name'], 'idle')
        self.assertEqual(idle['loop'], 'loop')
        self.assertFalse(idle['override'])
        self.assertEqual(len(idle['animators']), 69, 'all 16 carriers + 53 drawn bones animated')
        for animator in idle['animators'].values():
            rot_keys = [k for k in animator['keyframes'] if k['channel'] == 'rotation']
            self.assertGreaterEqual(len(rot_keys), 30)
            a0, a1 = rot_keys[0]['data_points'][0], rot_keys[-1]['data_points'][0]
            for ax in ('x', 'y', 'z'):
                diff = (float(a1[ax]) - float(a0[ax]) + 180.0) % 360.0 - 180.0
                self.assertLess(abs(diff), 0.05,
                                f'{animator["name"]}.{ax}: rotation loop seam mismatch ({a0[ax]} vs {a1[ax]})')
            pos_keys = [k for k in animator['keyframes'] if k['channel'] == 'position']
            if pos_keys:
                self.assertEqual(pos_keys[0]['data_points'], pos_keys[-1]['data_points'],
                                 f'{animator["name"]}: position loop seam mismatch')

    def test_modelengine_itself_can_import_the_blueprint(self):
        java, ecj = os.environ.get('JAVA'), os.environ.get('ECJ')
        if not java or not ecj:
            self.skipTest('set JAVA and ECJ to run the real ModelEngine parser')
        out = Path(tempfile.mkdtemp()) / 'assets'
        result = subprocess.run(
            ['sh', str(HERE / 'generate_assets.sh'), str(HERE / f'{PET}.bbmodel'), str(out)],
            capture_output=True, text=True, timeout=300, env=dict(os.environ, JAVA=java, ECJ=ecj))
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn('UnsupportedOperationException', output)
        generated = {p.stem for p in (out / 'assets/modelengine/items' / PET).glob('*.json')}
        self.assertEqual(len(generated), 53)
        self.assertEqual(generated, {n for n in self.bones if self.cubes[n]})

    def test_generated_assets_cover_every_bone(self):
        base = HERE / 'assets' / 'modelengine'
        bones = [name for name, bone in self.bones.items()
                 if any(isinstance(c, str) for c in bone['children'])]
        self.assertEqual(len(bones), 53)
        for bone in bones:
            model = json.loads((base / 'models' / PET / f'{bone}.json').read_text())
            definition = json.loads((base / 'items' / PET / f'{bone}.json').read_text())
            self.assertEqual(definition['model']['model'], f'modelengine:{PET}/{bone}')
            self.assertEqual(model['textures']['0'], f'modelengine:entity/models/{PET}')
            self.assertEqual(len(model['elements']), len(self.cubes[bone]))
        texture = Image.open(base / 'textures' / 'entity' / 'models' / f'{PET}.png')
        self.assertEqual(texture.size, (128, 128))
        self.assertEqual(texture.mode, 'RGBA')


class ModelAssetsTests(unittest.TestCase):
    def test_every_model_has_items_models_and_texture(self):
        base = HERE / 'assets' / 'modelengine'
        names = {path.relative_to(base).as_posix() for path in base.rglob('*') if path.is_file()}
        found = {name.split('/')[1] for name in names if name.split('/')[0] in ('items', 'models')}
        self.assertEqual(found, set(MODELS))
        for model in MODELS:
            models = {n for n in names if n.startswith(f'models/{model}/')}
            items = {n for n in names if n.startswith(f'items/{model}/')}
            self.assertTrue(models, f'{model}: no bone models')
            self.assertEqual({n.split('/')[-1] for n in models},
                             {n.split('/')[-1] for n in items}, f'{model}: bones differ')
            self.assertIn(f'textures/entity/models/{model}.png', names)

    def test_the_blueprint_bones_match_the_generated_files(self):
        for model in MODELS:
            blueprint = json.loads((HERE / f'{model}.bbmodel').read_text(encoding='utf-8'))
            bones = {}
            flatten(blueprint['outliner'], bones)
            drawn = {name for name, bone in bones.items()
                     if any(isinstance(c, str) for c in bone['children'])}
            generated = {path.stem for path in (HERE / 'assets' / 'modelengine' / 'models' / model).glob('*.json')}
            self.assertEqual(generated, drawn, f'{model}: stale or missing bone files')


class PackTests(unittest.TestCase):
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
                         if any(name.startswith(f'assets/modelengine/items/{m}/') or
                                name.startswith(f'assets/modelengine/models/{m}/') or
                                name == f'assets/modelengine/textures/entity/models/{m}.png'
                                for m in MODELS)
                         or name.startswith('assets/reallyworld/')
                         and any(ic in name for ic in (
                             'kaneki_tentacles_icon', 'centipede_icon', 'mini_me_icon', 'kitten_icon', 'mellstroy_icon',
                             'content_acc_hub.png', 'content_acc_two.png', 'content_acc_one.png',
                             'content_acc_three.png', 'content_acc_four.png',
                             'elytrix_acc_back.png', 'elytrix_acc_hats.png', 'elytrix_acc_pets.png',
                             'sounds.json', 'sounds/mellstroy/',
                         ))}
            self.assertEqual(generated, expected)
            for name in generated:
                source = HERE / 'assets' / name[len('assets/'):]
                self.assertEqual(pack.read(name), source.read_bytes(), name)

    def test_item_definitions(self):
        with zipfile.ZipFile(self.pack) as pack:
            for model in MODELS:
                blueprint = json.loads((HERE / f'{model}.bbmodel').read_text(encoding='utf-8'))
                bones = {}
                flatten(blueprint['outliner'], bones)
                expected = len([n for n, b in bones.items()
                                if any(isinstance(c, str) for c in b['children'])])
                items = [n for n in pack.namelist()
                         if n.startswith(f'assets/modelengine/items/{model}/')]
                self.assertEqual(len(items), expected, model)
                for name in items:
                    definition = json.loads(pack.read(name))['model']
                    self.assertEqual(definition['model'],
                                     f'modelengine:{model}/' + Path(name).stem)
                    self.assertEqual(definition['type'], 'minecraft:model')
                    self.assertEqual(definition['tints'],
                                     [{'type': 'minecraft:constant', 'value': -196867}])

    def test_first_person_hide_shaders_and_marker_tints(self):
        with zipfile.ZipFile(self.pack) as pack:
            names = set(pack.namelist())
            mcmeta = json.loads(pack.read('pack.mcmeta'))
            self.assertIn('min_format', mcmeta['pack'])
            self.assertIn('max_format', mcmeta['pack'])
            self.assertIn('supported_formats', mcmeta['pack'])
            overlays = mcmeta['overlays']['entries']
            self.assertEqual([e['directory'] for e in overlays], ['1_21_2', '1_21_6', '1_21_9'])
            for entry in overlays:
                self.assertIn('formats', entry)
                self.assertIn('min_format', entry)
                self.assertIn('max_format', entry)
            self.assertEqual(
                set(mcmeta['sodium']['ignored_shaders']),
                {
                    'entity.vsh', 'entity.fsh',
                    'rendertype_item_entity_translucent_cull.vsh',
                    'rendertype_item_entity_translucent_cull.fsh',
                    'rendertype_entity_translucent.vsh',
                    'rendertype_entity_translucent.fsh',
                },
            )
            shader_pairs = [
                ('assets/minecraft/shaders/core/rendertype_entity_translucent', '#version 150'),
                ('assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull', '#version 150'),
                ('1_21_2/assets/minecraft/shaders/core/rendertype_entity_translucent', '#version 150'),
                ('1_21_2/assets/minecraft/shaders/core/entity', '#version 150'),
                ('1_21_2/assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull', '#version 150'),
                ('1_21_6/assets/minecraft/shaders/core/entity', '#version 150'),
                ('1_21_6/assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull', '#version 150'),
                ('1_21_9/assets/minecraft/shaders/core/entity', '#version 330'),
                ('1_21_9/assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull', '#version 330'),
            ]
            for stem, ver in shader_pairs:
                vsh = pack.read(stem + '.vsh').decode('utf-8')
                fsh = pack.read(stem + '.fsh').decode('utf-8')
                self.assertTrue(vsh.startswith(ver), f'{stem}.vsh version mismatch')
                self.assertTrue(fsh.startswith(ver), f'{stem}.fsh version mismatch')
                for src_name, src in ((stem + '.vsh', vsh), (stem + '.fsh', fsh)):
                    self.assertEqual(src.count('{'), src.count('}'), src_name)
                    self.assertEqual(src.count('('), src.count(')'), src_name)
                    ifdefs = sum(1 for ln in src.splitlines() if ln.strip().startswith(('#if ', '#ifdef ', '#ifndef ')))
                    endifs = sum(1 for ln in src.splitlines() if ln.strip().startswith('#endif'))
                    self.assertEqual(ifdefs, endifs, src_name)
                self.assertIn('out float elytrixHideRadius;', vsh)
                self.assertIn('out float elytrixEyeDist;', vsh)
                self.assertIn('ivec3(252, 254, 253)', vsh)
                self.assertIn('ivec3(252, 253, 254)', vsh)
                self.assertIn('abs(ProjMat[2][3]) > 1e-4', vsh)
                self.assertIn('in float elytrixHideRadius;', fsh)
                self.assertIn('in float elytrixEyeDist;', fsh)
                self.assertIn('elytrixEyeDist < elytrixHideRadius', fsh)
            # 1.21.9+ entity shader must support PER_FACE_LIGHTING
            self.assertIn('PER_FACE_LIGHTING', pack.read('1_21_9/assets/minecraft/shaders/core/entity.vsh').decode('utf-8'))
            self.assertIn('PER_FACE_LIGHTING', pack.read('1_21_9/assets/minecraft/shaders/core/entity.fsh').decode('utf-8'))
            # Worn wings & halo also carry marker tints; Priora & GUI icons do NOT
            for n in names:
                if n.startswith('assets/modelengine/items/elytrix_angel_wings/') and n.endswith('.json'):
                    self.assertEqual(json.loads(pack.read(n))['model']['tints'],
                                     [{'type': 'minecraft:constant', 'value': -197122}])
                elif n.startswith('assets/modelengine/items/elytrix_angel_halo/') and n.endswith('.json'):
                    self.assertEqual(json.loads(pack.read(n))['model']['tints'],
                                     [{'type': 'minecraft:constant', 'value': -196867}])
                elif n.startswith('assets/modelengine/items/elytrix_priora_black/') and n.endswith('.json'):
                    self.assertEqual(json.loads(pack.read(n))['model']['tints'][0]['type'],
                                     'minecraft:custom_model_data')

    def test_modelengine_jar_blueprint_cap_removed(self):
        me_jar = HERE.parent.parent / 'plugins' / 'ModelEngine-4.1.0.jar'
        with zipfile.ZipFile(me_jar) as zf:
            cls_bytes = zf.read('com/ticxo/modelengine/core/generator/ModelGeneratorImpl.class')
        # SIPUSH 8192 = 0x11 0x20 0x00 must be present; BIPUSH 12 = 0x10 0x0C followed by IF_ICMPLT (0xA1) must NOT!
        self.assertIn(b'\x11\x20\x00\xa1', cls_bytes)
        self.assertNotIn(b'\x10\x0c\xa1', cls_bytes)

    def test_menu_icon_exists(self):
        with zipfile.ZipFile(self.pack) as pack:
            names = set(pack.namelist())
            for icon_id in ('kaneki_tentacles_icon', 'centipede_icon', 'mini_me_icon', 'kitten_icon', 'mellstroy_icon'):
                item_path = f'assets/reallyworld/items/{icon_id}.json'
                model_path = f'assets/reallyworld/models/item/freak/{icon_id}.json'
                tex_path = f'assets/reallyworld/textures/item/freak/{icon_id}.png'
                for name in (item_path, model_path, tex_path):
                    self.assertIn(name, names)
                definition = json.loads(pack.read(item_path))
                self.assertEqual(definition['model']['model'], f'reallyworld:item/freak/{icon_id}')
                model = json.loads(pack.read(model_path))
                self.assertEqual(model['parent'], 'minecraft:item/generated')
                self.assertEqual(model['textures'],
                                 {'layer0': f'reallyworld:item/freak/{icon_id}'})
                image = Image.open(io.BytesIO(pack.read(tex_path)))
                self.assertEqual(image.size, (32, 32))
                self.assertEqual(image.mode, 'RGBA')
                self.assertGreater(sum(1 for px in image.getdata() if px[3] > 0), 120)

    def test_mellstroy_voice_sounds_and_unshaded_badges_in_pack(self):
        with zipfile.ZipFile(self.pack) as pack:
            names = set(pack.namelist())
            self.assertIn('assets/reallyworld/sounds.json', names)
            sounds = json.loads(pack.read('assets/reallyworld/sounds.json'))
            for clip in ('privet', 'amam', 'voznya', 'babki', 'tancuem', 'miliciya'):
                self.assertIn(f'mellstroy.{clip}', sounds)
                ogg_entry = f'assets/reallyworld/sounds/mellstroy/{clip}.ogg'
                self.assertIn(ogg_entry, names)
                raw = pack.read(ogg_entry)
                self.assertTrue(raw.startswith(b'OggS'))
                self.assertIn(b'vorbis', raw[:256])
            for badge_bone in ('badge_svet', 'badge_amam', 'badge_voznya', 'badge_babki', 'badge_tancuem', 'badge_miliciya'):
                model_json = json.loads(pack.read(f'assets/modelengine/models/elytrix_mellstroy/{badge_bone}.json'))
                self.assertEqual(len(model_json['elements']), 1)
                self.assertIs(model_json['elements'][0].get('shade'), False, badge_bone)
                item_json = json.loads(pack.read(f'assets/modelengine/items/elytrix_mellstroy/{badge_bone}.json'))
                self.assertEqual(item_json['model']['tints'], [{'type': 'minecraft:constant', 'value': -196867}])

    def test_title_glyph_registered_once(self):
        with zipfile.ZipFile(self.pack) as pack:
            names = set(pack.namelist())
            providers = json.loads(pack.read(FONT))['providers']
            entries = [p for p in providers if GLYPH in p.get('chars', [])]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]['ascent'], 26)
            self.assertEqual(entries[0]['height'], 32)
            self.assertEqual(entries[0]['file'], 'reallyworld:gui/title/elytrix_accessories.png')
            self.assertEqual(len(pack.read(TITLE)), 286)
            for ch, expected_file in (
                ('ꏡ', 'reallyworld:gui/content/content_acc_hub.png'),
                ('ꏢ', 'reallyworld:gui/content/content_acc_two.png'),
                ('ꏣ', 'reallyworld:gui/content/content_acc_one.png'),
                ('ꏤ', 'reallyworld:gui/title/elytrix_acc_back.png'),
                ('ꏥ', 'reallyworld:gui/title/elytrix_acc_hats.png'),
                ('ꏦ', 'reallyworld:gui/title/elytrix_acc_pets.png'),
                ('ꏧ', 'reallyworld:gui/content/content_acc_three.png'),
                ('ꏨ', 'reallyworld:gui/content/content_acc_four.png'),
            ):
                matched = [p for p in providers if ch in p.get('chars', [])]
                self.assertEqual(len(matched), 1, f'provider count for {ch!r}')
                self.assertEqual(matched[0]['file'], expected_file)
                zp = 'assets/' + expected_file.replace(':', '/textures/')
                self.assertIn(zp, names)

    def test_system_files_and_mythicmobs_untouched(self):
        with zipfile.ZipFile(self.pack) as new:
            new_names = set(new.namelist())
            for name in ('pack.png', 'assets/minecraft/atlases/blocks.json',
                         'assets/minecraft/items/leather_horse_armor.json',
                         'assets/minecraft/models/item/leather_horse_armor.json',
                         'assets/minecraft/shaders/core/rendertype_entity_translucent.json'):
                self.assertIn(name, new_names)
            for preserved in ('dwarf_blacksmith', 'ghoul', 'ghost', 'gp2_goblin_king',
                              'elytrix_angel_wings', 'elytrix_angel_halo', 'elytrix_priora_black'):
                self.assertTrue(
                    any(n.startswith(f'assets/modelengine/models/{preserved}/') for n in new_names),
                    f'preserved ModelEngine model missing: {preserved}')


class MiniMeBlueprintTest(unittest.TestCase):
    """Verifies the procedural shoulder-dancing miniature skin pet (`elytrix_mini_me`)."""

    @classmethod
    def setUpClass(cls):
        cls.model = json.loads((HERE / f'{MINI_ME}.bbmodel').read_text(encoding='utf-8'))

    def test_blockbench_4_10_free_and_zero_cube_rotations(self):
        self.assertEqual(self.model['meta'], {'format_version': '4.10', 'model_format': 'free', 'box_uv': False})
        self.assertEqual(self.model['resolution'], {'width': 16, 'height': 16})
        self.assertEqual(len(self.model['elements']), 6)
        for cube in self.model['elements']:
            self.assertEqual(cube['rotation'], [0.0, 0.0, 0.0], cube['name'])
            self.assertTrue(all(a < b for a, b in zip(cube['from'], cube['to'])))
            for face_name, face in cube['faces'].items():
                self.assertEqual(face['texture'], 0)
                self.assertTrue(all(0.0 <= v <= 16.0 for v in face['uv']), (cube['name'], face_name))
        tex_meta = self.model['textures'][0]
        self.assertEqual((tex_meta['uv_width'], tex_meta['uv_height']), (16, 16))
        self.assertTrue(tex_meta['internal'])

    def test_exact_white_skin_and_asymmetric_cyan_face(self):
        tex = Image.open(HERE / f'{MINI_ME}.png').convert('RGBA')
        self.assertEqual(tex.size, (64, 64))
        expected_cyan = {(1, 2), (6, 3), (1, 5), (4, 5), (2, 6), (3, 6)}
        for gy in range(8):
            for gx in range(8):
                rgba = tex.getpixel((gx * 4 + 2, gy * 4 + 2))
                if (gx, gy) in expected_cyan:
                    self.assertEqual(rgba, (91, 251, 255, 255), f'cyan pixel mismatch at {(gx, gy)}')
                else:
                    self.assertEqual(rgba, (255, 255, 255, 255), f'white pixel mismatch at {(gx, gy)}')

    def test_shoulder_placement_and_seamless_dance_loop(self):
        xs = [v for c in self.model['elements'] for v in (c['from'][0], c['to'][0])]
        ys = [v for c in self.model['elements'] for v in (c['from'][1], c['to'][1])]
        self.assertGreater(min(xs), 6.0, 'clears player head and shoulder')
        self.assertLess(max(xs), 13.0, 'stays cleanly near shoulder')
        self.assertGreaterEqual(min(ys), 23.5, 'starts at shoulder height')
        self.assertLessEqual(max(ys), 34.0, 'clears overhead halo')
        clips = self.model['animations']
        self.assertEqual(len(clips), 1)
        clip = clips[0]
        self.assertEqual(clip['name'], 'idle')
        self.assertEqual(clip['loop'], 'loop')
        self.assertEqual(len(clip['animators']), 8)
        for anim in clip['animators'].values():
            by_chan = {}
            for kf in anim['keyframes']:
                by_chan.setdefault(kf['channel'], []).append(kf)
            for chan, kfs in by_chan.items():
                self.assertEqual(kfs[0]['data_points'], kfs[-1]['data_points'], (anim['name'], chan))

    def test_modelengine_itself_can_import_mini_me_blueprint(self):
        java, ecj = os.environ.get('JAVA'), os.environ.get('ECJ')
        if not java or not ecj:
            self.skipTest('set JAVA and ECJ to run the real ModelEngine parser')
        out = Path(tempfile.mkdtemp()) / 'assets'
        result = subprocess.run(
            ['sh', str(HERE / 'generate_assets.sh'), str(HERE / f'{MINI_ME}.bbmodel'), str(out)],
            capture_output=True, text=True, timeout=300, env=dict(os.environ, JAVA=java, ECJ=ecj))
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn('UnsupportedOperationException', output)


class CuteKittenBlueprintTest(unittest.TestCase):
    """Verifies the procedural cute shoulder kitten pet (`elytrix_cute_kitten`)."""

    @classmethod
    def setUpClass(cls):
        cls.model = json.loads((HERE / f'{KITTEN}.bbmodel').read_text(encoding='utf-8'))

    def test_blockbench_4_10_free_and_zero_cube_rotations(self):
        self.assertEqual(self.model['meta'], {'format_version': '4.10', 'model_format': 'free', 'box_uv': False})
        self.assertEqual(self.model['resolution'], {'width': 16, 'height': 16})
        self.assertEqual(len(self.model['elements']), 18)
        for cube in self.model['elements']:
            self.assertEqual(cube['rotation'], [0.0, 0.0, 0.0], cube['name'])
            self.assertTrue(all(a < b for a, b in zip(cube['from'], cube['to'])))
            for face_name, face in cube['faces'].items():
                self.assertEqual(face['texture'], 0)
                self.assertTrue(all(0.0 <= v <= 16.0 for v in face['uv']), (cube['name'], face_name))
        tex_meta = self.model['textures'][0]
        self.assertEqual((tex_meta['uv_width'], tex_meta['uv_height']), (16, 16))
        self.assertTrue(tex_meta['internal'])

    def test_left_shoulder_perch_and_seamless_animation(self):
        xs = [v for c in self.model['elements'] for v in (c['from'][0], c['to'][0])]
        ys = [v for c in self.model['elements'] for v in (c['from'][1], c['to'][1])]
        self.assertLess(max(xs), -4.7, 'clears player head and helmet on left shoulder')
        self.assertGreater(min(xs), -10.5, 'perched slightly further left on outer shoulder')
        self.assertGreaterEqual(min(ys), 23.9, 'sits cleanly on top of shoulder')
        self.assertLessEqual(max(ys), 33.5, 'clears overhead halo')
        clips = self.model['animations']
        self.assertEqual(len(clips), 1)
        clip = clips[0]
        self.assertEqual(clip['name'], 'idle')
        self.assertEqual(clip['loop'], 'loop')
        self.assertEqual(len(clip['animators']), 10)
        for anim in clip['animators'].values():
            by_chan = {}
            for kf in anim['keyframes']:
                by_chan.setdefault(kf['channel'], []).append(kf)
            for chan, kfs in by_chan.items():
                self.assertEqual(kfs[0]['data_points'], kfs[-1]['data_points'], (anim['name'], chan))

    def test_modelengine_itself_can_import_kitten_blueprint(self):
        java, ecj = os.environ.get('JAVA'), os.environ.get('ECJ')
        if not java or not ecj:
            self.skipTest('set JAVA and ECJ to run the real ModelEngine parser')
        out = Path(tempfile.mkdtemp()) / 'assets'
        result = subprocess.run(
            ['sh', str(HERE / 'generate_assets.sh'), str(HERE / f'{KITTEN}.bbmodel'), str(out)],
            capture_output=True, text=True, timeout=300, env=dict(os.environ, JAVA=java, ECJ=ecj))
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn('UnsupportedOperationException', output)


class MellstroyBlueprintTest(unittest.TestCase):
    """Verifies the procedural Mellstroy shoulder pet (`elytrix_mellstroy`),
    its 6 `D.Admin BAN`-style 3D pop-up phrase badges, and its real voice clips."""

    @classmethod
    def setUpClass(cls):
        cls.model = json.loads((HERE / f'{MELLSTROY}.bbmodel').read_text(encoding='utf-8'))

    def test_blockbench_4_10_free_and_zero_cube_rotations(self):
        self.assertEqual(self.model['meta'], {'format_version': '4.10', 'model_format': 'free', 'box_uv': False})
        self.assertEqual(self.model['resolution'], {'width': 16, 'height': 16})
        self.assertEqual(len(self.model['elements']), 18)
        badge_cubes = [c for c in self.model['elements'] if c['name'].startswith('badge_')]
        self.assertEqual(len(badge_cubes), 6)
        for c in badge_cubes:
            self.assertIs(c.get('shade'), False, f'{c["name"]} must use shade=false like dadmin_ban')
        for cube in self.model['elements']:
            self.assertEqual(cube['rotation'], [0.0, 0.0, 0.0], cube['name'])
            self.assertTrue(all(a < b for a, b in zip(cube['from'], cube['to'])))
            for face_name, face in cube['faces'].items():
                self.assertEqual(face['texture'], 0)
                self.assertTrue(all(0.0 <= v <= 16.0 for v in face['uv']), (cube['name'], face_name))
        tex_meta = self.model['textures'][0]
        self.assertEqual((tex_meta['width'], tex_meta['height']), (128, 128))
        self.assertEqual((tex_meta['uv_width'], tex_meta['uv_height']), (16, 16))
        self.assertTrue(tex_meta['internal'])

    def test_shoulder_placement_and_ban_style_popup_animations(self):
        body_cubes = [c for c in self.model['elements'] if not c['name'].startswith('badge_')]
        xs = [v for c in body_cubes for v in (c['from'][0], c['to'][0])]
        ys = [v for c in body_cubes for v in (c['from'][1], c['to'][1])]
        self.assertLess(max(xs), -5.8, 'clears player head & helmet')
        self.assertGreater(min(xs), -12.2, 'stays beside outer shoulder')
        self.assertGreaterEqual(min(ys), 23.5, 'starts at shoulder height')
        self.assertLessEqual(max(ys), 35.5, 'clears central overhead halo')

        clips = self.model['animations']
        self.assertEqual([c['name'] for c in clips],
                         ['idle', 'say_svet', 'say_amam', 'say_voznya', 'say_babki', 'say_tancuem', 'say_miliciya'])
        idle = clips[0]
        self.assertEqual(idle['loop'], 'loop')
        self.assertFalse(idle['override'])
        self.assertEqual(len(idle['animators']), 14)
        for anim in idle['animators'].values():
            if anim['name'].startswith('badge_'):
                for kf in anim['keyframes']:
                    self.assertEqual(kf['data_points'], [{'x': '0.0', 'y': '0.0', 'z': '0.0'}])

        for clip in clips[1:]:
            self.assertEqual(clip['loop'], 'once')
            self.assertTrue(clip['override'])
            target_badge = 'badge_' + clip['name'].split('_', 1)[1]
            for anim in clip['animators'].values():
                if anim['name'] == target_badge:
                    scales = [float(kf['data_points'][0]['x']) for kf in anim['keyframes'] if kf['channel'] == 'scale']
                    self.assertEqual(scales[0], 0.0)
                    self.assertEqual(scales[-1], 0.0)
                    self.assertGreater(max(scales), 1.15)
                elif anim['name'].startswith('badge_'):
                    for kf in anim['keyframes']:
                        self.assertEqual(kf['data_points'], [{'x': '0.0', 'y': '0.0', 'z': '0.0'}])

    def test_real_mellstroy_ogg_vorbis_voice_assets(self):
        sounds_json = json.loads((HERE / 'assets/reallyworld/sounds.json').read_text(encoding='utf-8'))
        expected = ('privet', 'amam', 'voznya', 'babki', 'tancuem', 'miliciya')
        self.assertEqual(tuple(sounds_json.keys()), tuple(f'mellstroy.{k}' for k in expected))
        for k in expected:
            ogg_path = HERE / f'assets/reallyworld/sounds/mellstroy/{k}.ogg'
            self.assertTrue(ogg_path.is_file(), f'missing {ogg_path}')
            raw = ogg_path.read_bytes()
            self.assertTrue(raw.startswith(b'OggS'), f'{k}.ogg must be Ogg container')
            self.assertIn(b'vorbis', raw[:256], f'{k}.ogg must be genuine Vorbis, not Opus')
            self.assertNotIn(b'OpusHead', raw[:256], f'{k}.ogg must not be Opus')
            self.assertGreater(len(raw), 8000)

    def test_modelengine_itself_can_import_mellstroy_blueprint(self):
        java, ecj = os.environ.get('JAVA'), os.environ.get('ECJ')
        if not java or not ecj:
            self.skipTest('set JAVA and ECJ to run the real ModelEngine parser')
        out = Path(tempfile.mkdtemp()) / 'assets'
        result = subprocess.run(
            ['sh', str(HERE / 'generate_assets.sh'), str(HERE / f'{MELLSTROY}.bbmodel'), str(out)],
            capture_output=True, text=True, timeout=300, env=dict(os.environ, JAVA=java, ECJ=ecj))
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn('UnsupportedOperationException', output)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]] + [a for a in sys.argv[1:]
                                        if a.startswith('-') and not a.startswith(('--pack=', '--base='))])
