#!/usr/bin/env python3
"""Procedurally builds the adorable shoulder kitten pet (`elytrix_cute_kitten`)
and its 32x32 pixel-art menu icon (`kitten_icon`).

100% pure procedural Python + Pillow — zero AI generation, zero external downloads:
  1. Blockbench `4.10` `free` blueprint (`elytrix_cute_kitten.bbmodel`):
       - `resolution` 16x16, `uv_width`/`uv_height` = 16, `internal: true`, all UVs in `0..16`
       - Zero per-cube rotations (`rotation: [0.0, 0.0, 0.0]` on all 15 cubes)
       - Perched cozily on top of the player's left shoulder (`x=-6.20, y=24.00, z=-0.35`),
         clear of head, Angel Wings / Kaneki Kagune (`Спина`), and Divine Halo (`Шапки`),
         hidden in 1st-person (`< 1.85m` via `fpv_shaders.py`) and 100% visible in `F5` & to others.
       - 11 articulated bones (`body_root` -> `kitten_root` -> `torso` -> `head`/`ear_l`/`ear_r`/
         `paw_l`/`paw_r`/`tail_1` -> `tail_2` -> `tail_3`) with a 3.6s seamless loop (`idle`):
         cozy breathing, heart-melting head tilts, independent ear twitches, shoulder paw-kneading,
         a cute raised front-paw "nya~" wave showing pink toe-beans, and a 3-joint S-wave tail swish!
  2. Hand-crafted 32x32 pixel-art icon (`reallyworld:kitten_icon`) with sparkling aqua eyes,
     sakura-pink inner ears, rosy cheeks, `ω` mouth, golden collar bell, waving paw & pixel heart.
"""
import argparse
import base64
import io
import json
import math
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
MODEL = 'elytrix_cute_kitten'
ICON = 'kitten_icon'

CX = -6.20       # Centered squarely on the player's left shoulder pad (x = -8.0 .. -4.0)
BASE_Y = 24.00   # Resting directly on top of the shoulder (y = 24.0)
CZ = -0.35

ANIM_LENGTH = 3.6
ANIM_STEPS = 72  # 20 ticks/sec -> 73 keyframes (0..72 inclusive)


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f'elytrix.cute_kitten.v1:{tag}'))


# ---------------------------------------------------------------------------
# 1. Hand-Crafted 64x64 Pixel-Art Kitten Texture (UV 16x16 -> 4px per UV unit)
# ---------------------------------------------------------------------------
def build_kitten_texture() -> Image.Image:
    """64x64 pixel-art atlas:
      - UV [0..8, 0..7]   (px 0..31, 0..27):   Chibi kitten front face (sparkling eyes, blush, nose, ω mouth)
      - UV [8..12, 0..4]  (px 32..47, 0..15):  Pointed front ear (white fur rim + sakura-pink inner ear)
      - UV [12..16, 0..4] (px 48..63, 0..15):  Snowy-white soft fur
      - UV [8..12, 4..8]  (px 32..47, 16..31): Pastel cream-lilac tabby back/forehead fur
      - UV [12..16, 4..8] (px 48..63, 16..31): White paw underside with pink toe-beans
      - UV [0..6, 8..12]  (px 0..23, 32..47):  Elytrix pink collar
      - UV [6..10, 8..12] (px 24..39, 32..47): Golden collar bell
      - UV [10..16, 8..12](px 40..63, 32..47): Fluffy cream-tipped tail fur
    """
    fur_white = (255, 253, 252, 255)
    fur_soft = (246, 241, 247, 255)
    fur_tabby = (232, 214, 229, 255)
    fur_tabby_mid = (241, 227, 238, 255)
    ear_pink = (255, 174, 205, 255)
    ear_deep = (242, 136, 178, 255)
    blush = (255, 190, 216, 255)
    nose_pink = (255, 134, 176, 255)
    mouth_col = (132, 90, 114, 255)
    eye_dark = (26, 52, 84, 255)
    eye_mid = (46, 128, 178, 255)
    eye_aqua = (102, 230, 252, 255)
    sparkle = (255, 255, 255, 255)
    collar_main = (248, 190, 251, 255)
    collar_rim = (224, 134, 234, 255)
    gold_hi = (255, 232, 124, 255)
    gold_main = (246, 192, 62, 255)
    gold_slot = (146, 98, 24, 255)
    bean_pink = (255, 164, 198, 255)

    img = Image.new('RGBA', (64, 64), fur_white)
    px = img.load()

    def rect(x0, y0, x1, y1, col):
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if 0 <= xx < 64 and 0 <= yy < 64:
                    px[xx, yy] = col

    # --- Island 1: Front Face (px 0..31, 0..27 -> UV [0..8, 0..7]) ---
    rect(0, 0, 31, 27, fur_white)
    # Soft pastel tabby forehead 'M' markings at top
    rect(7, 0, 10, 4, fur_tabby)
    rect(21, 0, 24, 4, fur_tabby)
    rect(13, 0, 18, 6, fur_tabby_mid)
    rect(15, 0, 16, 8, fur_tabby)
    # Subtle chin shading at bottom row
    rect(0, 25, 31, 27, fur_soft)

    # Big sparkling 7x8 anime-pixel kitten eyes at left (x=4..10, y=9..16) and right (x=21..27, y=9..16)
    for ex in (4, 21):
        rect(ex, 9, ex + 6, 16, eye_dark)
        # Rounded corners for cute soft shape
        px[ex, 9] = fur_white
        px[ex + 6, 9] = fur_white
        px[ex, 16] = fur_white
        px[ex + 6, 16] = fur_white
        # Iris gradient: mid teal -> bright aqua crescent at bottom
        rect(ex + 1, 12, ex + 5, 14, eye_mid)
        rect(ex + 1, 14, ex + 5, 15, eye_aqua)
        rect(ex + 2, 16, ex + 4, 16, eye_aqua)
        # Dark pupil center
        rect(ex + 2, 11, ex + 4, 13, eye_dark)
        # Big 2x2 top-left starlight catchlight + 1px bottom-right twinkle!
        rect(ex + 1, 10, ex + 2, 11, sparkle)
        px[ex + 5, 14] = sparkle

    # Rosy pastel blush cheeks (x=1..6, y=17..20) & (x=25..30, y=17..20)
    rect(2, 17, 6, 19, blush)
    rect(25, 17, 29, 19, blush)

    # Tiny pink inverted-triangle nose (center x=14..17, y=17..19)
    rect(14, 17, 17, 18, nose_pink)
    rect(15, 19, 16, 19, nose_pink)

    # Cute 'ω' cat mouth (x=11..20, y=20..22)
    for xx, yy in (
        (15, 20), (16, 20),
        (14, 21), (17, 21),
        (12, 22), (13, 22), (18, 22), (19, 22),
        (11, 21), (20, 21),
    ):
        px[xx, yy] = mouth_col

    # --- Island 2: Front Ear (px 32..47, 0..15 -> UV [8..12, 0..4]) ---
    rect(32, 0, 47, 15, fur_white)
    rect(35, 4, 44, 15, ear_pink)
    rect(37, 7, 42, 15, ear_deep)
    px[35, 4] = fur_white
    px[44, 4] = fur_white

    # --- Island 3: Snowy-White Fur (px 48..63, 0..15 -> UV [12..16, 0..4]) ---
    rect(48, 0, 63, 15, fur_white)
    rect(48, 13, 63, 15, fur_soft)

    # --- Island 4: Tabby-Striped Back Fur (px 32..47, 16..31 -> UV [8..12, 4..8]) ---
    rect(32, 16, 47, 31, fur_white)
    rect(34, 19, 45, 21, fur_tabby_mid)
    rect(35, 25, 44, 27, fur_tabby)

    # --- Island 5: Paw Pad & Pink Toe-Beans (px 48..63, 16..31 -> UV [12..16, 4..8]) ---
    rect(48, 16, 63, 31, fur_soft)
    # Central palm bean + 3 little toe-beans!
    rect(53, 24, 58, 28, bean_pink)
    rect(50, 19, 52, 22, bean_pink)
    rect(55, 18, 57, 21, bean_pink)
    rect(59, 19, 61, 22, bean_pink)

    # --- Island 6: Elytrix Pink Collar (px 0..23, 32..47 -> UV [0..6, 8..12]) ---
    rect(0, 32, 23, 47, collar_main)
    rect(0, 44, 23, 47, collar_rim)

    # --- Island 7: Golden Collar Bell (px 24..39, 32..47 -> UV [6..10, 8..12]) ---
    rect(24, 32, 39, 47, gold_main)
    rect(26, 34, 32, 38, gold_hi)
    rect(30, 41, 33, 45, gold_slot)
    rect(28, 43, 35, 44, gold_slot)

    # --- Island 8: Fluffy Tail Fur (px 40..63, 32..47 -> UV [10..16, 8..12]) ---
    rect(40, 32, 63, 47, fur_white)
    rect(40, 32, 63, 36, fur_tabby_mid)

    return img


# ---------------------------------------------------------------------------
# 2. Blockbench 4.10 `free` Geometry & 11-Bone Kitten Animation
# ---------------------------------------------------------------------------
UV_WHITE = [12.5, 0.5, 15.5, 3.0]
UV_SHADE = [12.5, 1.0, 15.5, 3.8]
UV_TABBY = [8.5, 4.5, 11.5, 7.5]
UV_EAR_FRONT = [8.0, 0.0, 12.0, 4.0]
UV_BEANS = [12.0, 4.0, 16.0, 8.0]
UV_COLLAR = [0.5, 8.5, 5.5, 11.5]
UV_BELL = [6.0, 8.0, 10.0, 12.0]
UV_TAIL = [10.5, 8.5, 15.5, 11.5]


def _uniform_faces(uv, down_uv=None, north_uv=None, back_uv=None) -> dict:
    return {
        'north': {'uv': list(north_uv or uv), 'texture': 0},
        'east':  {'uv': list(uv), 'texture': 0},
        'south': {'uv': list(back_uv or uv), 'texture': 0},
        'west':  {'uv': list(uv), 'texture': 0},
        'up':    {'uv': list(back_uv or uv), 'texture': 0},
        'down':  {'uv': list(down_uv or UV_SHADE), 'texture': 0},
    }


def _cube(name: str, low: list, high: list, origin: list, faces: dict) -> dict:
    return {
        'name': name,
        'box_uv': False,
        'rescale': False,
        'locked': False,
        'light_emission': 0,
        'render_order': 'default',
        'allow_mirror_modeling': True,
        'from': [round(v, 4) for v in low],
        'to': [round(v, 4) for v in high],
        'autouv': 0,
        'color': 0,
        'origin': [round(v, 4) for v in origin],
        'rotation': [0.0, 0.0, 0.0],
        'faces': faces,
        'type': 'cube',
        'uuid': uid(f'cube:{name}'),
    }


def _bone(name: str, origin: list, cubes: list, children: list) -> dict:
    return {
        'name': name,
        'origin': [round(v, 4) for v in origin],
        'rotation': [0.0, 0.0, 0.0],
        'color': 0,
        'uuid': uid(f'bone:{name}'),
        'export': True,
        'mirror_uv': False,
        'isOpen': True,
        'locked': False,
        'visibility': True,
        'autouv': 0,
        'children': [c['uuid'] for c in cubes] + list(children),
    }


def _smooth_bump(u: float, center: float, half_width: float) -> float:
    """Periodic C1 raised-cosine bump centered at `center` on u in [0, 1)."""
    du = ((u - center + 0.5) % 1.0) - 0.5
    if abs(du) >= half_width:
        return 0.0
    return 0.5 * (1.0 + math.cos(math.pi * du / half_width))


def eval_kitten_pose(u_norm: float) -> dict:
    """Evaluates the 3.6s seamless cute shoulder-kitten animation at u in [0, 1]."""
    u = u_norm % 1.0
    w1 = 2.0 * math.pi * u
    w2 = 2.0 * w1
    w3 = 3.0 * w1
    w6 = 6.0 * w1

    # Cute single-paw "nya~" wave window around u = 0.58!
    nya_wave = _smooth_bump(u, 0.58, 0.19)

    # 1. Cozy purr-breathing bounce on `kitten_root`
    dy = 0.18 * (0.5 - 0.5 * math.cos(w3)) + 0.15 * nya_wave
    torso_rot = (2.5 * math.sin(w2) - 4.0 * nya_wave, 4.0 * math.sin(w1), 2.5 * math.cos(w2))

    # 2. Heart-melting curious head-tilt, happy nod & look-around
    head_tilt = 11.5 * math.sin(w2 + 0.4) + 8.0 * nya_wave
    head_yaw = 13.0 * math.sin(w1 + 0.3) * (1.0 - 0.5 * nya_wave)
    head_pitch = 5.5 * math.sin(w3) - 6.0 * nya_wave
    head_rot = (head_pitch, head_yaw, head_tilt)

    # 3. Playful independent ear twitches!
    flick_l = _smooth_bump(u, 0.21, 0.045) + 0.7 * _smooth_bump(u, 0.28, 0.035)
    flick_r = _smooth_bump(u, 0.76, 0.045) + 0.8 * _smooth_bump(u, 0.56, 0.055)
    ear_l_rot = (8.0 * flick_l, 0.0, -18.0 * flick_l - 3.5 * math.sin(w2))
    ear_r_rot = (8.0 * flick_r, 0.0,  18.0 * flick_r + 3.5 * math.sin(w2))

    # 4. Front paws: alternating "making biscuits" shoulder kneading + cute raised `paw_r` wave!
    knead_r = max(0.0,  math.sin(w3)) * (1.0 - nya_wave)
    knead_l = max(0.0, -math.sin(w3))
    # Raising paw_r forward & up (`rx > 0` swings hanging paw forward -Z & up +Y, showing pink toe-beans!)
    wave_wiggle = math.sin(w6)
    paw_r_rot = (
        26.0 * knead_r + nya_wave * (116.0 + 16.0 * wave_wiggle),
        0.0,
        nya_wave * (14.0 * wave_wiggle),
    )
    paw_l_rot = (26.0 * knead_l, 0.0, 0.0)

    # 5. 3-bone S-wave fluffy tail swish (`tail_1` -> `tail_2` -> `tail_3`)
    tail_1_rot = (6.0 * math.sin(w2),       22.0 * math.sin(w2),        12.0 * math.cos(w2))
    tail_2_rot = (5.0 * math.sin(w2 - 0.8), 20.0 * math.sin(w2 - 0.85), 14.0 * math.cos(w2 - 0.85))
    tail_3_rot = (4.0 * math.sin(w2 - 1.6), 18.0 * math.sin(w2 - 1.70), 16.0 * math.cos(w2 - 1.70))

    return {
        'root_pos': (0.0, dy, 0.0),
        'torso_rot': torso_rot,
        'head_rot': head_rot,
        'ear_l_rot': ear_l_rot,
        'ear_r_rot': ear_r_rot,
        'paw_r_rot': paw_r_rot,
        'paw_l_rot': paw_l_rot,
        'tail_1_rot': tail_1_rot,
        'tail_2_rot': tail_2_rot,
        'tail_3_rot': tail_3_rot,
    }


def _rot_keyframes(bone_name: str, rot_fn) -> list:
    keys = []
    for step in range(ANIM_STEPS + 1):
        t = ANIM_LENGTH * step / ANIM_STEPS
        u = step / ANIM_STEPS
        rx, ry, rz = rot_fn(u)
        keys.append({
            'channel': 'rotation',
            'data_points': [{
                'x': str(round(-rx, 3)),
                'y': str(round(-ry, 3)),
                'z': str(round(rz, 3)),
            }],
            'uuid': uid(f'rkey:{bone_name}:{step}'),
            'time': round(t, 4),
            'color': -1,
            'interpolation': 'linear',
        })
    keys[-1]['data_points'] = [dict(p) for p in keys[0]['data_points']]
    return keys


def _pos_keyframes(bone_name: str, pos_fn) -> list:
    keys = []
    for step in range(ANIM_STEPS + 1):
        t = ANIM_LENGTH * step / ANIM_STEPS
        u = step / ANIM_STEPS
        dx, dy, dz = pos_fn(u)
        keys.append({
            'channel': 'position',
            'data_points': [{
                'x': str(round(-dx, 3)),
                'y': str(round(dy, 3)),
                'z': str(round(dz, 3)),
            }],
            'uuid': uid(f'pkey:{bone_name}:{step}'),
            'time': round(t, 4),
            'color': -1,
            'interpolation': 'linear',
        })
    keys[-1]['data_points'] = [dict(p) for p in keys[0]['data_points']]
    return keys


def build_animation() -> dict:
    poses = [eval_kitten_pose(step / ANIM_STEPS) for step in range(ANIM_STEPS + 1)]

    def at(key):
        return lambda u, _k=key: poses[min(ANIM_STEPS, int(round(u * ANIM_STEPS)))][_k]

    animators = {
        uid('bone:kitten_root'): {
            'name': 'kitten_root',
            'type': 'bone',
            'keyframes': _pos_keyframes('kitten_root', at('root_pos')),
        },
        uid('bone:torso'): {
            'name': 'torso',
            'type': 'bone',
            'keyframes': _rot_keyframes('torso', at('torso_rot')),
        },
        uid('bone:head'): {
            'name': 'head',
            'type': 'bone',
            'keyframes': _rot_keyframes('head', at('head_rot')),
        },
        uid('bone:ear_l'): {
            'name': 'ear_l',
            'type': 'bone',
            'keyframes': _rot_keyframes('ear_l', at('ear_l_rot')),
        },
        uid('bone:ear_r'): {
            'name': 'ear_r',
            'type': 'bone',
            'keyframes': _rot_keyframes('ear_r', at('ear_r_rot')),
        },
        uid('bone:paw_r'): {
            'name': 'paw_r',
            'type': 'bone',
            'keyframes': _rot_keyframes('paw_r', at('paw_r_rot')),
        },
        uid('bone:paw_l'): {
            'name': 'paw_l',
            'type': 'bone',
            'keyframes': _rot_keyframes('paw_l', at('paw_l_rot')),
        },
        uid('bone:tail_1'): {
            'name': 'tail_1',
            'type': 'bone',
            'keyframes': _rot_keyframes('tail_1', at('tail_1_rot')),
        },
        uid('bone:tail_2'): {
            'name': 'tail_2',
            'type': 'bone',
            'keyframes': _rot_keyframes('tail_2', at('tail_2_rot')),
        },
        uid('bone:tail_3'): {
            'name': 'tail_3',
            'type': 'bone',
            'keyframes': _rot_keyframes('tail_3', at('tail_3_rot')),
        },
    }
    return {
        'uuid': uid('animation:idle'),
        'name': 'idle',
        'loop': 'loop',
        'override': False,
        'length': ANIM_LENGTH,
        'snapping': 20,
        'selected': True,
        'anim_time_update': '',
        'blend_weight': '',
        'start_delay': '',
        'loop_delay': '',
        'animators': animators,
    }


def build_blueprint():
    texture = build_kitten_texture()
    raw = io.BytesIO()
    texture.save(raw, format='PNG', optimize=True)

    torso_orig = [CX, BASE_Y + 0.30, CZ]
    head_orig = [CX, BASE_Y + 2.90, CZ - 0.10]
    ear_r_orig = [CX + 1.02, BASE_Y + 5.55, CZ - 0.10]
    ear_l_orig = [CX - 1.02, BASE_Y + 5.55, CZ - 0.10]
    paw_r_orig = [CX + 0.72, BASE_Y + 1.95, CZ - 0.80]
    paw_l_orig = [CX - 0.72, BASE_Y + 1.95, CZ - 0.80]
    t1_orig = [CX, BASE_Y + 0.55, CZ + 1.15]
    t2_orig = [CX, BASE_Y + 1.05, CZ + 2.15]
    t3_orig = [CX, BASE_Y + 2.25, CZ + 2.45]

    c_body = _cube(
        'body_cube',
        [CX - 1.15, BASE_Y + 0.20, CZ - 1.00],
        [CX + 1.15, BASE_Y + 2.85, CZ + 1.20],
        torso_orig,
        _uniform_faces(UV_WHITE, back_uv=UV_TABBY),
    )
    c_chest = _cube(
        'chest_tuft',
        [CX - 0.75, BASE_Y + 1.05, CZ - 1.22],
        [CX + 0.75, BASE_Y + 2.50, CZ - 0.92],
        torso_orig,
        _uniform_faces(UV_WHITE),
    )
    c_collar = _cube(
        'collar_cube',
        [CX - 0.98, BASE_Y + 2.55, CZ - 1.12],
        [CX + 0.98, BASE_Y + 2.92, CZ + 0.92],
        torso_orig,
        _uniform_faces(UV_COLLAR),
    )
    c_bell = _cube(
        'bell_cube',
        [CX - 0.28, BASE_Y + 2.22, CZ - 1.40],
        [CX + 0.28, BASE_Y + 2.74, CZ - 1.00],
        torso_orig,
        _uniform_faces(UV_BELL, down_uv=UV_BELL),
    )
    c_hind_r = _cube(
        'hind_r_cube',
        [CX + 0.25, BASE_Y, CZ - 1.12],
        [CX + 1.22, BASE_Y + 0.78, CZ + 0.95],
        torso_orig,
        _uniform_faces(UV_WHITE, down_uv=UV_BEANS),
    )
    c_hind_l = _cube(
        'hind_l_cube',
        [CX - 1.22, BASE_Y, CZ - 1.12],
        [CX - 0.25, BASE_Y + 0.78, CZ + 0.95],
        torso_orig,
        _uniform_faces(UV_WHITE, down_uv=UV_BEANS),
    )

    head_faces = _uniform_faces(UV_WHITE, back_uv=UV_TABBY)
    head_faces['north'] = {'uv': [0.0, 0.0, 8.0, 7.0], 'texture': 0}
    c_head = _cube(
        'head_cube',
        [CX - 1.55, BASE_Y + 2.90, CZ - 1.55],
        [CX + 1.55, BASE_Y + 5.62, CZ + 1.30],
        head_orig,
        head_faces,
    )
    c_cheek_r = _cube(
        'cheek_r_cube',
        [CX + 1.55, BASE_Y + 3.05, CZ - 1.15],
        [CX + 1.88, BASE_Y + 4.08, CZ + 0.35],
        head_orig,
        _uniform_faces(UV_WHITE),
    )
    c_cheek_l = _cube(
        'cheek_l_cube',
        [CX - 1.88, BASE_Y + 3.05, CZ - 1.15],
        [CX - 1.55, BASE_Y + 4.08, CZ + 0.35],
        head_orig,
        _uniform_faces(UV_WHITE),
    )

    c_ear_r_base = _cube(
        'ear_r_base',
        [CX + 0.52, BASE_Y + 5.55, CZ - 0.60],
        [CX + 1.48, BASE_Y + 6.45, CZ + 0.25],
        ear_r_orig,
        _uniform_faces(UV_WHITE, north_uv=UV_EAR_FRONT, back_uv=UV_TABBY),
    )
    c_ear_r_tip = _cube(
        'ear_r_tip',
        [CX + 0.70, BASE_Y + 6.45, CZ - 0.50],
        [CX + 1.32, BASE_Y + 7.02, CZ + 0.15],
        ear_r_orig,
        _uniform_faces(UV_WHITE, back_uv=UV_TABBY),
    )
    c_ear_l_base = _cube(
        'ear_l_base',
        [CX - 1.48, BASE_Y + 5.55, CZ - 0.60],
        [CX - 0.52, BASE_Y + 6.45, CZ + 0.25],
        ear_l_orig,
        _uniform_faces(UV_WHITE, north_uv=UV_EAR_FRONT, back_uv=UV_TABBY),
    )
    c_ear_l_tip = _cube(
        'ear_l_tip',
        [CX - 1.32, BASE_Y + 6.45, CZ - 0.50],
        [CX - 0.70, BASE_Y + 7.02, CZ + 0.15],
        ear_l_orig,
        _uniform_faces(UV_WHITE, back_uv=UV_TABBY),
    )

    c_paw_r = _cube(
        'paw_r_cube',
        [CX + 0.35, BASE_Y, CZ - 1.28],
        [CX + 1.08, BASE_Y + 2.00, CZ - 0.48],
        paw_r_orig,
        _uniform_faces(UV_WHITE, down_uv=UV_BEANS),
    )
    c_paw_l = _cube(
        'paw_l_cube',
        [CX - 1.08, BASE_Y, CZ - 1.28],
        [CX - 0.35, BASE_Y + 2.00, CZ - 0.48],
        paw_l_orig,
        _uniform_faces(UV_WHITE, down_uv=UV_BEANS),
    )

    c_t1 = _cube(
        'tail_1_cube',
        [CX - 0.32, BASE_Y + 0.35, CZ + 1.10],
        [CX + 0.32, BASE_Y + 1.25, CZ + 2.28],
        t1_orig,
        _uniform_faces(UV_TAIL),
    )
    c_t2 = _cube(
        'tail_2_cube',
        [CX - 0.30, BASE_Y + 0.95, CZ + 2.05],
        [CX + 0.30, BASE_Y + 2.35, CZ + 2.75],
        t2_orig,
        _uniform_faces(UV_TAIL),
    )
    c_t3 = _cube(
        'tail_3_cube',
        [CX - 0.33, BASE_Y + 2.20, CZ + 2.10],
        [CX + 0.33, BASE_Y + 3.55, CZ + 2.82],
        t3_orig,
        _uniform_faces(UV_WHITE, back_uv=UV_TAIL),
    )

    torso_cubes = [c_body, c_chest, c_collar, c_bell, c_hind_r, c_hind_l]
    head_cubes = [c_head, c_cheek_r, c_cheek_l]
    ear_r_cubes = [c_ear_r_base, c_ear_r_tip]
    ear_l_cubes = [c_ear_l_base, c_ear_l_tip]
    elements = (
        torso_cubes + head_cubes + ear_r_cubes + ear_l_cubes
        + [c_paw_r, c_paw_l, c_t1, c_t2, c_t3]
    )

    b_ear_r = _bone('ear_r', ear_r_orig, ear_r_cubes, [])
    b_ear_l = _bone('ear_l', ear_l_orig, ear_l_cubes, [])
    b_head = _bone('head', head_orig, head_cubes, [b_ear_r, b_ear_l])
    b_paw_r = _bone('paw_r', paw_r_orig, [c_paw_r], [])
    b_paw_l = _bone('paw_l', paw_l_orig, [c_paw_l], [])
    b_t3 = _bone('tail_3', t3_orig, [c_t3], [])
    b_t2 = _bone('tail_2', t2_orig, [c_t2], [b_t3])
    b_t1 = _bone('tail_1', t1_orig, [c_t1], [b_t2])
    b_torso = _bone('torso', torso_orig, torso_cubes, [b_head, b_paw_r, b_paw_l, b_t1])
    b_kroot = _bone('kitten_root', [CX, BASE_Y, CZ], [], [b_torso])
    b_root = _bone('body_root', [0.0, 0.0, 0.0], [], [b_kroot])

    texture_entry = {
        'path': '',
        'name': f'{MODEL}.png',
        'folder': '',
        'namespace': '',
        'id': '0',
        'width': texture.width,
        'height': texture.height,
        'uv_width': 16,
        'uv_height': 16,
        'particle': False,
        'use_as_default': False,
        'layers_enabled': False,
        'render_mode': 'default',
        'render_sides': 'auto',
        'frame_time': 1,
        'frame_order_type': 'loop',
        'frame_interpolate': False,
        'visible': True,
        'internal': True,
        'saved': False,
        'uuid': uid('texture'),
        'source': 'data:image/png;base64,' + base64.b64encode(raw.getvalue()).decode('ascii'),
    }

    blueprint = {
        'meta': {'format_version': '4.10', 'model_format': 'free', 'box_uv': False},
        'name': MODEL,
        'model_identifier': MODEL,
        'visible_box': [3, 3, 0],
        'variable_placeholders': '',
        'variable_placeholder_buttons': [],
        'timeline_setups': [],
        'unhandled_root_fields': {},
        'resolution': {'width': 16, 'height': 16},
        'elements': elements,
        'outliner': [b_root],
        'textures': [texture_entry],
        'animations': [build_animation()],
    }
    return blueprint, texture


# ---------------------------------------------------------------------------
# 3. Hand-Crafted 32x32 Pixel-Art Menu Icon (`reallyworld:kitten_icon`)
# ---------------------------------------------------------------------------
def build_kitten_icon() -> Image.Image:
    """Draws a crisp 32x32 pixel-art icon for `Милый котёнок`:
    - Fluffy snowy-white chibi kitten sitting & waving one paw (showing pink toe-bean!)
    - Pointed ears with sakura-pink insides, sparkling aqua eyes, rosy cheeks, pink nose & ω mouth
    - Elytrix pink collar + golden bell, curled fluffy tail, and a tiny pastel-pink heart!
    """
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    outline = (44, 36, 54, 255)
    white = (255, 253, 252, 255)
    shade = (234, 226, 240, 255)
    tabby = (224, 206, 228, 255)
    ear_pink = (255, 168, 202, 255)
    blush = (255, 186, 214, 255)
    nose = (255, 128, 172, 255)
    mouth = (128, 86, 112, 255)
    eye_dark = (26, 52, 86, 255)
    eye_aqua = (98, 228, 252, 255)
    collar = (248, 190, 251, 255)
    gold = (255, 212, 74, 255)
    heart = (255, 146, 194, 255)
    heart_hi = (255, 208, 230, 255)

    def rect(x0, y0, x1, y1, col):
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if 0 <= xx < 32 and 0 <= yy < 32:
                    px[xx, yy] = col

    # 1) Pointed kitten ears: left (x=7..11, y=4..8) & right (x=17..21, y=4..8)
    for ex in (7, 17):
        rect(ex, 6, ex + 4, 8, white)
        rect(ex + 1, 5, ex + 3, 6, white)
        px[ex + 2, 4] = white
        rect(ex + 1, 6, ex + 3, 8, ear_pink)
        px[ex + 2, 5] = ear_pink

    # 2) Big chibi kitten head (x=6..22, y=8..18) + cheek tufts
    rect(7, 8, 21, 18, white)
    rect(6, 11, 22, 16, white)
    rect(5, 13, 23, 15, white)
    rect(7, 18, 21, 18, shade)
    # Tabby forehead stripes
    rect(13, 8, 15, 10, tabby)
    px[14, 11] = tabby
    # Sparkling 3x3 eyes at (9..11, 11..13) & (17..19, 11..13)
    for ex in (9, 17):
        rect(ex, 11, ex + 2, 13, eye_dark)
        rect(ex + 1, 13, ex + 2, 13, eye_aqua)
        px[ex, 11] = (255, 255, 255, 255)
    # Rosy cheeks, pink nose & happy upward 'ω' smile!
    rect(7, 14, 8, 15, blush)
    rect(20, 14, 21, 15, blush)
    px[14, 14] = nose
    for xx, yy in ((11, 15), (12, 16), (13, 16), (14, 15), (15, 16), (16, 16), (17, 15)):
        px[xx, yy] = mouth

    # 3) Elytrix pink collar + golden bell (y=19..20)
    rect(9, 19, 19, 19, collar)
    rect(13, 19, 15, 20, gold)

    # 4) Sitting fluffy body & paws (x=9..19, y=20..27)
    rect(9, 20, 19, 27, white)
    rect(10, 26, 18, 27, shade)
    px[13, 25] = shade
    px[15, 25] = shade
    # Cute raised waving left-of-icon paw (x=5..8, y=17..21) with pink toe-bean!
    rect(5, 17, 8, 20, white)
    rect(6, 18, 7, 19, ear_pink)

    # 5) Fluffy curled tail on right side (x=20..25, y=18..26)
    rect(20, 24, 23, 26, shade)
    rect(22, 20, 25, 24, white)
    rect(21, 18, 24, 20, tabby)

    # 6) 1px crisp dark silhouette outline around the entire kitten
    mask = [[px[x, y][3] > 0 for y in range(32)] for x in range(32)]
    for y in range(32):
        for x in range(32):
            if mask[x][y]:
                continue
            if any(0 <= x + dx < 32 and 0 <= y + dy < 32 and mask[x + dx][y + dy]
                   for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                px[x, y] = outline

    # 7) Tiny pastel-pink pixel heart at top-right (x=24..28, y=5..9)
    for xx, yy in (
        (24, 6), (25, 5), (25, 6), (26, 6), (27, 5), (27, 6), (28, 6),
        (24, 7), (25, 7), (26, 7), (27, 7), (28, 7),
        (25, 8), (26, 8), (27, 8),
        (26, 9),
    ):
        px[xx, yy] = heart
    px[25, 6] = heart_hi

    return img


# ---------------------------------------------------------------------------
# 4. Visual Verification Preview (`kitten_preview.png`)
# ---------------------------------------------------------------------------
def render_preview(blueprint: dict, texture: Image.Image, icon: Image.Image, out_path: Path):
    panel_w, panel_h = 220, 240
    canvas = Image.new('RGBA', (panel_w * 5, panel_h), (26, 28, 38, 255))
    draw = ImageDraw.Draw(canvas)

    def rot_mat(rx, ry, rz):
        ax, ay, az = map(math.radians, (rx, ry, rz))
        cx, sx = math.cos(ax), math.sin(ax)
        cy, sy = math.cos(ay), math.sin(ay)
        cz_, sz_ = math.cos(az), math.sin(az)
        mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
        my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        mz = np.array([[cz_, -sz_, 0], [sz_, cz_, 0], [0, 0, 1]])
        return mz @ my @ mx

    tex_arr = np.array(texture)
    by_name = {el['name']: el for el in blueprint['elements']}

    for idx, u in enumerate((0.06, 0.22, 0.58, 0.80)):
        pose = eval_kitten_pose(u)
        ox0 = idx * panel_w

        def proj(pt):
            ang = math.radians(18.0)
            xw = pt[0] * math.cos(ang) - pt[2] * math.sin(ang)
            zw = pt[0] * math.sin(ang) + pt[2] * math.cos(ang)
            yw = pt[1] - 0.14 * zw
            return (ox0 + 72.0 - xw * 12.5, 212.0 - (yw - 18.0) * 12.5, zw)

        ref_boxes = [
            ([-4, 24, -4], [4, 32, 4], (64, 70, 92, 255)),
            ([-4, 16, -2], [4, 24, 2], (52, 58, 78, 255)),
            ([-8, 16, -2], [-4, 24, 2], (58, 64, 86, 255)),
        ]
        faces_to_draw = []

        for low, high, rcol in ref_boxes:
            x0, y0, z0 = low
            x1, y1, z1 = high
            cs = [np.array([x0,y0,z0]), np.array([x1,y0,z0]), np.array([x1,y1,z0]), np.array([x0,y1,z0]),
                  np.array([x0,y0,z1]), np.array([x1,y0,z1]), np.array([x1,y1,z1]), np.array([x0,y1,z1])]
            for idxs, sm in (((2,1,0,3),1.0), ((6,5,1,2),0.88), ((3,0,4,7),0.85), ((7,6,2,3),1.05)):
                p2d = [proj(cs[k]) for k in idxs]
                cross = (p2d[1][0]-p2d[0][0])*(p2d[2][1]-p2d[0][1]) - (p2d[1][1]-p2d[0][1])*(p2d[2][0]-p2d[0][0])
                if cross <= 0:
                    col = tuple(min(255, int(c * sm)) for c in rcol[:3]) + (255,)
                    faces_to_draw.append((sum(p[2] for p in p2d)/4.0, [(s[0], s[1]) for s in p2d], col, (40,44,60,255)))

        def add_cube(cname, tf_fn, subdiv_north=0):
            el = by_name[cname]
            x0, y0, z0 = el['from']
            x1, y1, z1 = el['to']
            cs = [np.array([x0,y0,z0]), np.array([x1,y0,z0]), np.array([x1,y1,z0]), np.array([x0,y1,z0]),
                  np.array([x0,y0,z1]), np.array([x1,y0,z1]), np.array([x1,y1,z1]), np.array([x0,y1,z1])]
            wcs = [tf_fn(c) for c in cs]
            quads = [
                ('north', (2, 1, 0, 3), 1.00),
                ('south', (7, 4, 5, 6), 0.78),
                ('east',  (6, 5, 1, 2), 0.88),
                ('west',  (3, 0, 4, 7), 0.86),
                ('up',    (7, 6, 2, 3), 1.00),
                ('down',  (0, 1, 5, 4), 0.76),
            ]
            for fname, idxs, sm in quads:
                pts3 = [wcs[k] for k in idxs]
                p2d = [proj(p) for p in pts3]
                cross = (p2d[1][0]-p2d[0][0])*(p2d[2][1]-p2d[0][1]) - (p2d[1][1]-p2d[0][1])*(p2d[2][0]-p2d[0][0])
                if cross > 0:
                    continue
                z_avg = sum(p[2] for p in p2d) / 4.0
                uv = el['faces'][fname]['uv']
                if subdiv_north and fname in ('north', 'down'):
                    n = subdiv_north
                    p_tl, p_bl, p_br, p_tr = pts3
                    for gy in range(n):
                        for gx in range(n):
                            u0, u1 = gx / n, (gx + 1) / n
                            v0, v1 = gy / n, (gy + 1) / n
                            tx = min(63, int((uv[0] + (uv[2] - uv[0]) * (u0 + 0.5 / n)) * 4))
                            ty = min(63, int((uv[1] + (uv[3] - uv[1]) * (v0 + 0.5 / n)) * 4))
                            rgb = tex_arr[ty, tx, :3]
                            col = tuple(int(c * sm) for c in rgb) + (255,)
                            def bilerp(uu, vv):
                                top = p_tl * (1 - uu) + p_tr * uu
                                bot = p_bl * (1 - uu) + p_br * uu
                                return top * (1 - vv) + bot * vv
                            sub = [proj(bilerp(u0, v0)), proj(bilerp(u0, v1)), proj(bilerp(u1, v1)), proj(bilerp(u1, v0))]
                            faces_to_draw.append((z_avg - 0.01, [(s[0], s[1]) for s in sub], col, None))
                else:
                    tx = min(63, int(0.5 * (uv[0] + uv[2]) * 4))
                    ty = min(63, int(0.5 * (uv[1] + uv[3]) * 4))
                    rgb = tex_arr[ty, tx, :3]
                    col = tuple(int(c * sm) for c in rgb) + (255,)
                    faces_to_draw.append((z_avg, [(s[0], s[1]) for s in p2d], col, (165, 152, 178, 180)))

        r_pos = np.array(pose['root_pos'])
        torso_o = np.array([CX, BASE_Y + 0.30, CZ])
        m_torso = rot_mat(*pose['torso_rot'])
        tf_torso = lambda p: torso_o + r_pos + m_torso @ (p - torso_o)

        def child_tf(parent_tf, orig, angles):
            o = np.array(orig)
            m = rot_mat(*angles)
            return lambda p: parent_tf(o + m @ (p - o))

        tf_head = child_tf(tf_torso, [CX, BASE_Y + 2.90, CZ - 0.10], pose['head_rot'])
        tf_er = child_tf(tf_head, [CX + 1.02, BASE_Y + 5.55, CZ - 0.10], pose['ear_r_rot'])
        tf_el = child_tf(tf_head, [CX - 1.02, BASE_Y + 5.55, CZ - 0.10], pose['ear_l_rot'])
        tf_pr = child_tf(tf_torso, [CX + 0.72, BASE_Y + 1.95, CZ - 0.80], pose['paw_r_rot'])
        tf_pl = child_tf(tf_torso, [CX - 0.72, BASE_Y + 1.95, CZ - 0.80], pose['paw_l_rot'])
        tf_t1 = child_tf(tf_torso, [CX, BASE_Y + 0.55, CZ + 1.15], pose['tail_1_rot'])
        tf_t2 = child_tf(tf_t1, [CX, BASE_Y + 1.05, CZ + 2.15], pose['tail_2_rot'])
        tf_t3 = child_tf(tf_t2, [CX, BASE_Y + 2.25, CZ + 2.45], pose['tail_3_rot'])

        for cn in ('body_cube', 'chest_tuft', 'collar_cube', 'bell_cube', 'hind_r_cube', 'hind_l_cube'):
            add_cube(cn, tf_torso)
        add_cube('head_cube', tf_head, subdiv_north=16)
        add_cube('cheek_r_cube', tf_head)
        add_cube('cheek_l_cube', tf_head)
        add_cube('ear_r_base', tf_er, subdiv_north=6)
        add_cube('ear_r_tip', tf_er)
        add_cube('ear_l_base', tf_el, subdiv_north=6)
        add_cube('ear_l_tip', tf_el)
        add_cube('paw_r_cube', tf_pr, subdiv_north=8)
        add_cube('paw_l_cube', tf_pl)
        add_cube('tail_1_cube', tf_t1)
        add_cube('tail_2_cube', tf_t2)
        add_cube('tail_3_cube', tf_t3)

        faces_to_draw.sort(key=lambda item: -item[0])
        for _, poly, fill_col, edge_col in faces_to_draw:
            draw.polygon(poly, fill=fill_col, outline=edge_col)

    # Panel 5: Zoomed 32x32 kitten icon + zoomed face texture
    ox4 = 4 * panel_w
    canvas.alpha_composite(icon.resize((112, 112), Image.NEAREST), (ox4 + 54, 12))
    canvas.alpha_composite(texture.crop((0, 0, 32, 28)).resize((96, 84), Image.NEAREST), (ox4 + 62, 138))
    draw.rectangle([ox4 + 61, 137, ox4 + 158, 222], outline=(248, 190, 251, 255), width=1)
    canvas.save(out_path)


def write_icon_assets(icon: Image.Image, out_assets_dir: Path):
    tex_dir = out_assets_dir / 'reallyworld/textures/item/freak'
    mod_dir = out_assets_dir / 'reallyworld/models/item/freak'
    itm_dir = out_assets_dir / 'reallyworld/items'
    for d in (tex_dir, mod_dir, itm_dir):
        d.mkdir(parents=True, exist_ok=True)

    icon.save(tex_dir / f'{ICON}.png', optimize=True)
    (mod_dir / f'{ICON}.json').write_text(
        json.dumps({
            'parent': 'minecraft:item/generated',
            'textures': {'layer0': f'reallyworld:item/freak/{ICON}'},
        }, separators=(',', ':')) + '\n',
        encoding='utf-8',
    )
    (itm_dir / f'{ICON}.json').write_text(
        json.dumps({
            'model': {'type': 'minecraft:model', 'model': f'reallyworld:item/freak/{ICON}'},
        }, separators=(',', ':')) + '\n',
        encoding='utf-8',
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-bbmodel', default=str(HERE / f'{MODEL}.bbmodel'))
    parser.add_argument('--out-assets', default=str(HERE / 'assets'))
    parser.add_argument('--preview', default=str(HERE / 'kitten_preview.png'))
    args = parser.parse_args()

    blueprint, texture = build_blueprint()
    bb_path = Path(args.out_bbmodel)
    bb_path.write_text(json.dumps(blueprint, indent=2) + '\n', encoding='utf-8')
    texture.save(HERE / f'{MODEL}.png', optimize=True)

    assets_dir = Path(args.out_assets)
    icon = build_kitten_icon()
    write_icon_assets(icon, assets_dir)
    render_preview(blueprint, texture, icon, Path(args.preview))

    print(f'Built {bb_path.name}: {len(blueprint["elements"])} cubes, '
          f'{len(blueprint["animations"][0]["animators"])} animated bones, '
          f'icon -> {assets_dir}')


if __name__ == '__main__':
    main()
