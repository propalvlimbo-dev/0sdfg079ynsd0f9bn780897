#!/usr/bin/env python3
"""Procedurally builds the dancing miniature player-skin shoulder pet (`elytrix_mini_me`),
its pixel-art menu icon (`mini_me_icon`), and the 3-section `/accessories` GUI assets
(`Спина`, `Шапки`, `Питомцы`).

100% pure procedural Python + Pillow — zero AI generation, zero external downloads:
  1. Skin colors & 8x8 front face pixel grid measured directly from the owner's skin:
       - Base skin: pure crisp white `#FFFFFF` (`RGB(255, 255, 255)`)
       - Asymmetric cyan face pixels `#5BFBFF` (`RGB(91, 251, 255)`) on the 8x8 head grid:
           eyes:  (1, 2) and (6, 3)
           smile: (1, 5), (4, 5), (2, 6), (3, 6)
  2. Blockbench `4.10` `free` blueprint (`elytrix_mini_me.bbmodel`):
       - `resolution` 16x16, `uv_width`/`uv_height` = 16, `internal: true`, all UVs in `0..16`
       - Zero per-cube rotations (`rotation: [0.0, 0.0, 0.0]` on every cube)
       - Positioned beside & slightly above the player's right shoulder (`x=+9.6, y=24.0..33.6, z=-0.8`)
         so it coexists cleanly with Angel Wings / Kaneki Kagune (`Спина`) and Divine Halo (`Шапки`),
         hides in 1st-person (`< 1.85m` via `fpv_shaders.py`), and dances clearly in `F5` & to others.
       - 8 articulated bones (`body_root` -> `dancer` -> `pelvis` -> `torso`/`head`/`right_arm`/`left_arm`
         + `right_leg`/`left_leg`) with a seamless 3.2s 8-beat choreographed dance loop (`idle`).
  3. Menu icon (`reallyworld:mini_me_icon`) + native RP slot layouts (`content_acc_hub.png`,
     `content_acc_two.png`, `content_acc_one.png`) + native pixel-font section titles
     (`СПИНА`, `ШАПКИ`, `ПИТОМЦЫ`) extracted pixel-for-pixel from `title_00.png` and `content_00.png`.
"""
import argparse
import base64
import io
import json
import math
import uuid
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import compose_title

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = 'elytrix_mini_me'
ICON = 'mini_me_icon'

SKIN_WHITE = (255, 255, 255, 255)
SKIN_SHADE = (238, 243, 248, 255)
SKIN_CYAN = (91, 251, 255, 255)

# Exact 8x8 front-head cyan pixels measured from the owner's skin screenshot (gx=0..7 L->R, gy=0..7 T->B)
CYAN_FACE_PIXELS = frozenset({
    (1, 2),          # left-of-view eye (higher)
    (6, 3),          # right-of-view eye (1px lower)
    (1, 5), (4, 5),  # smile corners
    (2, 6), (3, 6),  # smile bottom
})

# Miniature classic-arm (4px) player proportions: scale = 0.27 (8.64 Blockbench units = 0.54 blocks tall)
SCALE = 0.27
CX = 9.00       # right beside the player's right shoulder (player head x=-4..+4, right arm x=+4..+8)
FEET_Y = 24.05  # right at shoulder height (y=24.0), top of head y=32.69 aligned with player head
CZ = -0.85      # slightly forward of back accessories (wings/kagune at z=+2..+8)

ANIM_LENGTH = 3.2   # 8 upbeat dance beats @ 150 BPM, exact periodic loop
ANIM_STEPS = 64     # 20 ticks/sec -> 65 keyframes (0..64 inclusive)


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f'elytrix.mini_me.v1:{tag}'))


# ---------------------------------------------------------------------------
# 1. Pixel-Exact 64x64 Skin Texture (UV grid 16x16 -> 4x4 PNG pixels per UV unit)
# ---------------------------------------------------------------------------
def build_skin_texture() -> Image.Image:
    """Builds the crisp 64x64 texture:
    - UV [0..8, 0..8]  (px 0..31, 0..31): 8x8 front head grid (4x4 px per skin pixel)
    - UV [8..16, 0..8] (px 32..63, 0..31): pure crisp white `#FFFFFF` for body/limbs/sides
    - UV [0..8, 8..16] (px 0..31, 32..63): subtle `#EEF3F8` underside for clean 3D depth under shoes/chin
    """
    img = Image.new('RGBA', (64, 64), SKIN_WHITE)
    px = img.load()

    # 8x8 front face at UV [0..8, 0..8] -> each skin pixel is an exact 4x4 block
    for gy in range(8):
        for gx in range(8):
            color = SKIN_CYAN if (gx, gy) in CYAN_FACE_PIXELS else SKIN_WHITE
            for dy in range(4):
                for dx in range(4):
                    px[gx * 4 + dx, gy * 4 + dy] = color

    # Subtle cool-white underside patch at UV [0..8, 8..16] for bottom faces (chin / soles)
    for y in range(32, 64):
        for x in range(0, 32):
            px[x, y] = SKIN_SHADE

    return img


# ---------------------------------------------------------------------------
# 2. Blockbench 4.10 `free` Blueprint & Articulated 8-Bone Dance Choreography
# ---------------------------------------------------------------------------
def _white_faces(bottom_shaded: bool = True) -> dict:
    white_uv = [9.0, 1.0, 15.0, 7.0]
    down_uv = [1.0, 9.0, 7.0, 15.0] if bottom_shaded else white_uv
    return {
        'north': {'uv': list(white_uv), 'texture': 0},
        'east':  {'uv': list(white_uv), 'texture': 0},
        'south': {'uv': list(white_uv), 'texture': 0},
        'west':  {'uv': list(white_uv), 'texture': 0},
        'up':    {'uv': list(white_uv), 'texture': 0},
        'down':  {'uv': list(down_uv),  'texture': 0},
    }


def _head_faces() -> dict:
    faces = _white_faces(bottom_shaded=True)
    # In Minecraft FaceBakery for NORTH (-Z face):
    #   to.x (+X, viewer's LEFT when facing the front) -> uv[0] = 0.0
    #   from.x (-X, viewer's RIGHT when facing the front) -> uv[2] = 8.0
    #   to.y (+Y, TOP) -> uv[1] = 0.0, from.y (-Y, BOTTOM) -> uv[3] = 8.0
    faces['north'] = {'uv': [0.0, 0.0, 8.0, 8.0], 'texture': 0}
    return faces


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


def _smooth_window(u: float, a: float, b: float, feather: float = 0.06) -> float:
    """Periodic smooth indicator for interval [a, b] on u in [0, 1)."""
    def ramp(x):
        x = max(0.0, min(1.0, x))
        return x * x * (3.0 - 2.0 * x)

    # Distance into [a, b] on circle [0, 1)
    u_mod = u % 1.0
    length = (b - a) % 1.0 or 1.0
    rel = (u_mod - a) % 1.0
    rise = ramp(rel / feather)
    fall = 1.0 - ramp((rel - (length - feather)) / feather)
    if rel <= length:
        return min(rise, fall)
    return 0.0


def eval_dance_pose(u_norm: float) -> dict:
    """Evaluates the 8-beat seamless shoulder-dance choreography at normalized time u in [0, 1].

    Returns Blockbench-space translations `(dx, dy, dz)` and Euler angles `(rx, ry, rz)`:
      - `rx > 0` swings downward limbs FORWARD & UP (-Z, +Y)
      - `rz > 0` swings right_arm (+X) OUTWARD & UP (+X, +Y)
      - `rz < 0` swings left_arm (-X) OUTWARD & UP (-X, +Y)
    """
    u = u_norm % 1.0
    w1 = 2.0 * math.pi * u          # 1 cycle per 3.2s
    w2 = 2.0 * w1                   # 2 cycles (4-beat phrase)
    w4 = 4.0 * w1                   # 4 cycles (half-bar groove)
    w8 = 8.0 * w1                   # 8 beats (150 BPM bounce!)

    # Blend between two signature dance styles across the 3.2s loop:
    #   Style A (u ~ 0.0..0.5): Alternating Hype Arm-Pump + Happy Shuffle Kick!
    #   Style B (u ~ 0.5..1.0): Overhead Double-Arm Wave ("Caramelldansen / Groove") + Hip Pop!
    wave_mode = _smooth_window(u, 0.48, 0.96, feather=0.07)
    pump_mode = 1.0 - wave_mode

    # 1. `dancer` root hop & lateral shoulder groove
    beat_hop = 0.95 * (0.5 - 0.5 * math.cos(w8)) + 0.30 * max(0.0, math.sin(w4))
    dx = 0.72 * math.sin(w2) + 0.25 * math.sin(w4)
    dz = -0.22 * math.cos(w2)
    dancer_yaw = 18.0 * math.sin(w2) + 9.0 * math.sin(w1)

    # 2. `pelvis` & `torso` counter-sway
    hip_sway = (10.5 * pump_mode + 15.0 * wave_mode) * math.sin(w4)
    pelvis_rot = (0.0, 8.0 * math.cos(w4), hip_sway)
    torso_rot = (
        6.5 * math.sin(w8 - 0.35),
        -6.0 * math.cos(w4),
        -0.75 * hip_sway,
    )

    # 3. `head` joyful nod, sassy side-tilt & curious look
    head_rot = (
        -10.0 * math.cos(w8) + 4.0,
        15.0 * math.sin(w2 + 0.55),
        (11.0 * pump_mode + 16.5 * wave_mode) * math.sin(w4 + 0.35),
    )

    # 4. `right_arm` & `left_arm`
    # Style A: alternating high outward hype-pumps (keeps front face 100% unobstructed!)
    pump_r = 0.5 + 0.5 * math.sin(w4)
    pump_l = 0.5 - 0.5 * math.sin(w4)
    ra_pump = (22.0 + 34.0 * pump_r, -14.0 * math.cos(w4),  52.0 + 82.0 * pump_r)
    la_pump = (22.0 + 34.0 * pump_l,  14.0 * math.cos(w4), -(52.0 + 82.0 * pump_l))

    # Style B: both arms raised high overhead waving side-to-side in unison!
    sway = math.sin(w4)
    bounce_arm = 10.0 * math.sin(w8)
    ra_wave = (18.0 + bounce_arm, 0.0,  142.0 + 24.0 * sway)
    la_wave = (18.0 + bounce_arm, 0.0, -142.0 + 24.0 * sway)

    right_arm_rot = tuple(pump_mode * a + wave_mode * b for a, b in zip(ra_pump, ra_wave))
    left_arm_rot  = tuple(pump_mode * a + wave_mode * b for a, b in zip(la_pump, la_wave))

    # 5. `right_leg` & `left_leg` upbeat alternating step-kick!
    step = math.sin(w4)
    rl_kick = max(0.0, step)
    ll_kick = max(0.0, -step)
    right_leg_rot = (36.0 * step, 0.0,  14.0 * rl_kick + 4.0 * wave_mode * math.sin(w4))
    left_leg_rot  = (-36.0 * step, 0.0, -14.0 * ll_kick + 4.0 * wave_mode * math.sin(w4))

    return {
        'dancer_pos': (dx, beat_hop, dz),
        'dancer_rot': (0.0, dancer_yaw, 0.0),
        'pelvis_rot': pelvis_rot,
        'torso_rot': torso_rot,
        'head_rot': head_rot,
        'right_arm_rot': right_arm_rot,
        'left_arm_rot': left_arm_rot,
        'right_leg_rot': right_leg_rot,
        'left_leg_rot': left_leg_rot,
    }


def _rot_keyframes(bone_name: str, rot_fn) -> list:
    keys = []
    for step in range(ANIM_STEPS + 1):
        t = ANIM_LENGTH * step / ANIM_STEPS
        u = step / ANIM_STEPS
        rx, ry, rz = rot_fn(u)
        # Verified ModelEngine 4.1.0 BlockbenchParser mapping: target [Rx, Ry, Rz] -> key [-Rx, -Ry, +Rz]
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
        # Verified ModelEngine 4.1.0 non-root position mapping: target [dx, dy, dz] -> key [-dx, +dy, +dz]
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
    poses = [eval_dance_pose(step / ANIM_STEPS) for step in range(ANIM_STEPS + 1)]

    def at(key):
        return lambda u, _k=key: poses[min(ANIM_STEPS, int(round(u * ANIM_STEPS)))][_k]

    animators = {
        uid('bone:dancer'): {
            'name': 'dancer',
            'type': 'bone',
            'keyframes': _pos_keyframes('dancer', at('dancer_pos'))
                       + _rot_keyframes('dancer', at('dancer_rot')),
        },
        uid('bone:pelvis'): {
            'name': 'pelvis',
            'type': 'bone',
            'keyframes': _rot_keyframes('pelvis', at('pelvis_rot')),
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
        uid('bone:right_arm'): {
            'name': 'right_arm',
            'type': 'bone',
            'keyframes': _rot_keyframes('right_arm', at('right_arm_rot')),
        },
        uid('bone:left_arm'): {
            'name': 'left_arm',
            'type': 'bone',
            'keyframes': _rot_keyframes('left_arm', at('left_arm_rot')),
        },
        uid('bone:right_leg'): {
            'name': 'right_leg',
            'type': 'bone',
            'keyframes': _rot_keyframes('right_leg', at('right_leg_rot')),
        },
        uid('bone:left_leg'): {
            'name': 'left_leg',
            'type': 'bone',
            'keyframes': _rot_keyframes('left_leg', at('left_leg_rot')),
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
    texture = build_skin_texture()
    raw = io.BytesIO()
    texture.save(raw, format='PNG', optimize=True)

    # Exact scaled classic-player dimensions (s = 0.30):
    #   head:  8x8x8  -> 2.40 x 2.40 x 2.40
    #   torso: 8x12x4 -> 2.40 x 3.60 x 1.20
    #   arms:  4x12x4 -> 1.20 x 3.60 x 1.20
    #   legs:  4x12x4 -> 1.20 x 3.60 x 1.20
    hw = 4.0 * SCALE        # 1.20 (half torso/head width)
    hd = 2.0 * SCALE        # 0.60 (half torso/limb depth)
    head_hd = 4.0 * SCALE   # 1.20 (half head depth)
    limb_w = 4.0 * SCALE    # 1.20 (classic 4px arm/leg width)
    limb_h = 12.0 * SCALE   # 3.60
    head_h = 8.0 * SCALE    # 2.40

    hip_y = FEET_Y + limb_h         # 27.60
    neck_y = hip_y + limb_h         # 31.20
    shoulder_y = neck_y - 0.30      # 30.90 (anatomical shoulder joint)
    top_y = neck_y + head_h         # 33.60

    head_origin = [CX, neck_y, CZ]
    torso_origin = [CX, hip_y, CZ]
    r_arm_origin = [CX + hw, shoulder_y, CZ]
    l_arm_origin = [CX - hw, shoulder_y, CZ]
    r_leg_origin = [CX + 0.5 * limb_w, hip_y, CZ]
    l_leg_origin = [CX - 0.5 * limb_w, hip_y, CZ]

    c_head = _cube(
        'head_cube',
        [CX - hw, neck_y, CZ - head_hd],
        [CX + hw, top_y, CZ + head_hd],
        head_origin,
        _head_faces(),
    )
    c_torso = _cube(
        'torso_cube',
        [CX - hw, hip_y, CZ - hd],
        [CX + hw, neck_y, CZ + hd],
        torso_origin,
        _white_faces(bottom_shaded=False),
    )
    c_r_arm = _cube(
        'right_arm_cube',
        [CX + hw, hip_y, CZ - hd],
        [CX + hw + limb_w, neck_y, CZ + hd],
        r_arm_origin,
        _white_faces(bottom_shaded=True),
    )
    c_l_arm = _cube(
        'left_arm_cube',
        [CX - hw - limb_w, hip_y, CZ - hd],
        [CX - hw, neck_y, CZ + hd],
        l_arm_origin,
        _white_faces(bottom_shaded=True),
    )
    c_r_leg = _cube(
        'right_leg_cube',
        [CX, FEET_Y, CZ - hd],
        [CX + limb_w, hip_y, CZ + hd],
        r_leg_origin,
        _white_faces(bottom_shaded=True),
    )
    c_l_leg = _cube(
        'left_leg_cube',
        [CX - limb_w, FEET_Y, CZ - hd],
        [CX, hip_y, CZ + hd],
        l_leg_origin,
        _white_faces(bottom_shaded=True),
    )

    elements = [c_head, c_torso, c_r_arm, c_l_arm, c_r_leg, c_l_leg]

    b_head = _bone('head', head_origin, [c_head], [])
    b_r_arm = _bone('right_arm', r_arm_origin, [c_r_arm], [])
    b_l_arm = _bone('left_arm', l_arm_origin, [c_l_arm], [])
    b_torso = _bone('torso', torso_origin, [c_torso], [b_head, b_r_arm, b_l_arm])
    b_r_leg = _bone('right_leg', r_leg_origin, [c_r_leg], [])
    b_l_leg = _bone('left_leg', l_leg_origin, [c_l_leg], [])
    b_pelvis = _bone('pelvis', torso_origin, [], [b_torso, b_r_leg, b_l_leg])
    b_dancer = _bone('dancer', [CX, FEET_Y, CZ], [], [b_pelvis])
    b_root = _bone('body_root', [0.0, 0.0, 0.0], [], [b_dancer])

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
# 3. Hand-Crafted 32x32 Pixel-Art Menu Icon (`reallyworld:mini_me_icon`)
# ---------------------------------------------------------------------------
def build_mini_me_icon() -> Image.Image:
    """Draws the 32x32 pixel-art icon for `Мини-скин` in `Питомцы`:
    - Cute white mini-player mid-dance (left arm raised high waving, right arm out, knee kicked up)
    - Exact 8x8 front head with the owner's `#5BFBFF` cyan asymmetric eyes & crooked smile
    - Crisp dark slate pixel outline + two tiny Elytrix pink/cyan music notes showing it dances!
    """
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    outline = (34, 40, 56, 255)
    white = (255, 255, 255, 255)
    shade = (224, 232, 244, 255)
    deep_shade = (198, 210, 228, 255)
    cyan = SKIN_CYAN
    cyan_dark = (42, 198, 212, 255)
    pink = (248, 190, 251, 255)
    pink_dark = (214, 128, 224, 255)

    def fill_rect(x0, y0, x1, y1, col):
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if 0 <= xx < 32 and 0 <= yy < 32:
                    px[xx, yy] = col

    # 1) 8x8 Head at (x=12..19, y=5..12) + 1px bevel highlight on top, exact cyan face pixels!
    fill_rect(12, 5, 19, 12, white)
    for xx in range(12, 20):
        px[xx, 12] = shade
    for (gx, gy) in CYAN_FACE_PIXELS:
        px[12 + gx, 5 + gy] = cyan

    # 2) Torso (6x8) at (x=13..18, y=13..20)
    fill_rect(13, 13, 18, 20, white)
    fill_rect(13, 19, 18, 20, shade)
    for yy in range(13, 21):
        px[18, yy] = shade

    # 3) Viewer-left arm raised HIGH in celebration! (x=9..11, y=7..15)
    fill_rect(9, 7, 11, 14, white)
    fill_rect(11, 12, 12, 15, white)
    px[9, 7] = shade
    for yy in range(12, 16):
        px[9, yy] = shade

    # 4) Viewer-right arm swinging out to the groove! (x=19..23, y=14..18)
    fill_rect(19, 14, 21, 16, white)
    fill_rect(21, 15, 23, 18, white)
    fill_rect(21, 18, 23, 18, shade)

    # 5) Viewer-left leg planted & slightly bent (x=13..15, y=21..27)
    fill_rect(13, 21, 15, 27, white)
    fill_rect(13, 26, 15, 27, deep_shade)

    # 6) Viewer-right leg kicking up happily to the side! (x=16..20, y=21..25)
    fill_rect(16, 21, 18, 24, white)
    fill_rect(18, 22, 20, 25, white)
    fill_rect(18, 25, 20, 25, deep_shade)

    # 7) Clean 1px 4-connected dark pixel-art silhouette outline around the character
    body_mask = [[px[x, y][3] > 0 for y in range(32)] for x in range(32)]
    for y in range(32):
        for x in range(32):
            if body_mask[x][y]:
                continue
            if any(0 <= x + dx < 32 and 0 <= y + dy < 32 and body_mask[x + dx][y + dy]
                   for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                px[x, y] = outline

    # 8) Two tiny crisp pixel-art music notes showing the dance vibe (top-left cyan, right pink)
    # Cyan eighth-note at (3..6, 3..8)
    for xx, yy in ((5, 3), (6, 3), (5, 4), (5, 5), (5, 6), (5, 7), (4, 6), (3, 7), (4, 7)):
        px[xx, yy] = cyan
    px[6, 4] = cyan_dark
    # Pink eighth-note at (25..28, 6..11)
    for xx, yy in ((27, 6), (28, 6), (27, 7), (27, 8), (27, 9), (27, 10), (26, 9), (25, 10), (26, 10)):
        px[xx, yy] = pink
    px[28, 7] = pink_dark

    return img


# ---------------------------------------------------------------------------
# 4. Native Elytrix RP GUI Overlays & Pixel-Font Section Titles
# ---------------------------------------------------------------------------
ACC_FONT_PROVIDERS = [
    {'type': 'bitmap', 'file': 'reallyworld:gui/content/content_acc_hub.png',   'ascent': 31, 'height': 256, 'chars': ['ꏡ']},
    {'type': 'bitmap', 'file': 'reallyworld:gui/content/content_acc_two.png',   'ascent': 31, 'height': 256, 'chars': ['ꏢ']},
    {'type': 'bitmap', 'file': 'reallyworld:gui/content/content_acc_one.png',   'ascent': 31, 'height': 256, 'chars': ['ꏣ']},
    {'type': 'bitmap', 'file': 'reallyworld:gui/title/elytrix_acc_back.png',    'ascent': 26, 'height': 32,  'chars': ['ꏤ']},
    {'type': 'bitmap', 'file': 'reallyworld:gui/title/elytrix_acc_hats.png',    'ascent': 26, 'height': 32,  'chars': ['ꏥ']},
    {'type': 'bitmap', 'file': 'reallyworld:gui/title/elytrix_acc_pets.png',    'ascent': 26, 'height': 32,  'chars': ['ꏦ']},
    {'type': 'bitmap', 'file': 'reallyworld:gui/content/content_acc_three.png', 'ascent': 31, 'height': 256, 'chars': ['ꏧ']},
    {'type': 'bitmap', 'file': 'reallyworld:gui/content/content_acc_four.png',  'ascent': 31, 'height': 256, 'chars': ['ꏨ']},
    # 4-section menu (Спина / Шапки / Питомцы / Ауры): tabs move to 10,12,14,16
    {'type': 'bitmap', 'file': 'reallyworld:gui/content/content_acc_hub4.png',   'ascent': 31, 'height': 256, 'chars': ['ꏩ']},
    {'type': 'bitmap', 'file': 'reallyworld:gui/content/content_acc_auras3.png', 'ascent': 31, 'height': 256, 'chars': ['ꏫ']},
    {'type': 'bitmap', 'file': 'reallyworld:gui/title/elytrix_acc_auras.png',    'ascent': 26, 'height': 32,  'chars': ['ꏬ']},
]


def build_gui_assets(rp_zip_path: Path, out_assets_dir: Path) -> dict:
    """Extracts the exact 18x18 slot tile from `content_00.png` and pixel glyphs from
    `title_00.png` inside `rp_zip_path`, producing zero-AI native Elytrix GUI overlays.
    """
    with zipfile.ZipFile(rp_zip_path) as zf:
        c00 = np.array(Image.open(zf.open('assets/reallyworld/textures/gui/content/content_00.png')).convert('RGBA'))
        c27 = np.array(Image.open(zf.open('assets/reallyworld/textures/gui/content/content_27.png')).convert('RGBA'))
        t00_bytes = zf.read('assets/reallyworld/textures/gui/title/title_00.png')

    # Slot 20 in content_27 is an isolated single slot (row=2, col=2):
    #   nominal 18x18 inner slot: x=83..100, y=71..88
    #   with 3px outer bevel frame: x=80..103, y=68..91 (24x24)
    outer_tile_24 = c27[68:92, 80:104].copy()
    # Inner 18x18 slot tile from content_00 (row=2, col=4 -> x=119..136, y=71..88) for seamless adjacent joins
    inner_tile_18 = c00[71:89, 119:137].copy()

    # Base canvas: copy content_27's outer dim backdrop and clear the 9x6 chest slot region cleanly to transparent
    base_gui = c27.copy()
    base_gui[32:146, 44:212] = (0, 0, 0, 0)

    def make_content(slots: list) -> Image.Image:
        arr = base_gui.copy()
        # Pass 1: stamp 24x24 outer bevel around every slot so isolated & edge slots get authentic outer borders
        for slot in slots:
            row, col = divmod(slot, 9)
            x0 = 47 + col * 18 - 3
            y0 = 35 + row * 18 - 3
            patch = outer_tile_24
            mask = patch[:, :, 3] > 30
            sub = arr[y0:y0 + 24, x0:x0 + 24]
            sub[mask] = patch[mask]
        # Pass 2: stamp crisp 18x18 inner slot tiles so adjacent slots join identically to content_00/content_11
        for slot in slots:
            row, col = divmod(slot, 9)
            x0 = 47 + col * 18
            y0 = 35 + row * 18
            arr[y0:y0 + 18, x0:x0 + 18] = inner_tile_18
        return Image.fromarray(arr)

    content_dir = out_assets_dir / 'reallyworld/textures/gui/content'
    title_dir = out_assets_dir / 'reallyworld/textures/gui/title'
    content_dir.mkdir(parents=True, exist_ok=True)
    title_dir.mkdir(parents=True, exist_ok=True)

    # With the 4th section (Ауры) the tab row becomes 10,12,14,16 (symmetric around the
    # chest centre slot 13) and the hub row becomes 19,21,23,25 (centre 22).
    layouts = {
        'content_acc_hub.png':   [19, 21, 23, 25, 49],                   # legacy 3-section hub layout, kept so old RPs stay valid
        'content_acc_hub4.png':  [19, 21, 23, 25, 49],                   # Hub: Спина [19], Шапки [21], Питомцы [23], Ауры [25] + Снять всё [49]
        'content_acc_two.png':   [10, 12, 14, 16, 30, 32, 45, 49],       # tabs [10,12,14,16] + 2 items [30,32] + Назад [45] + Снять всё [49]
        'content_acc_one.png':   [10, 12, 14, 16, 31, 45, 49],           # tabs + 1 item  [31]    (Ауры)
        'content_acc_three.png': [10, 12, 14, 16, 29, 31, 33, 45, 49],   # tabs + 3 items [29,31,33]
        'content_acc_auras3.png': [10, 12, 14, 16, 29, 31, 33, 45, 49],  # tabs + 3 items (будущие ауры)
        'content_acc_four.png':  [10, 12, 14, 16, 28, 30, 32, 34, 45, 49],  # tabs + 4 items [28,30,32,34]
    }
    written = {}
    for filename, slots in layouts.items():
        img = make_content(slots)
        dest = content_dir / filename
        img.save(dest, optimize=True)
        written[filename] = img

    # Extract pixel font from title_00.png; derive exact 8x6 'Ш' from 'Щ'[:6, :8]
    tmp_t00 = io.BytesIO(t00_bytes)
    font = compose_title.extract_font(tmp_t00)
    if 'Ш' not in font and 'Щ' in font:
        font['Ш'] = font['Щ'][:6, :8].copy()

    for filename, word in (
        ('elytrix_acc_back.png', 'СПИНА'),
        ('elytrix_acc_hats.png', 'ШАПКИ'),
        ('elytrix_acc_pets.png', 'ПИТОМЦЫ'),
        ('elytrix_acc_auras.png', 'АУРЫ'),
    ):
        bitmap, _, _ = compose_title.compose(font, word=word)
        img = Image.fromarray(bitmap)
        img.save(title_dir / filename, optimize=True)
        written[filename] = img

    return written


# ---------------------------------------------------------------------------
# 5. Visual Verification Strip Renderer (`mini_me_preview.png`)
# ---------------------------------------------------------------------------
def render_preview(blueprint: dict, texture: Image.Image, icon: Image.Image, out_path: Path):
    """Renders 4 dance frames of `elytrix_mini_me` next to a reference player shoulder
    plus a zoomed face & icon check so proportions and face accuracy are visually verified.
    """
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

    elements = {el['uuid']: el for el in blueprint['elements']}

    for idx, u in enumerate((0.08, 0.28, 0.58, 0.82)):
        pose = eval_dance_pose(u)
        ox0 = idx * panel_w
        # Draw subtle reference player head + right shoulder silhouette (facing -Z toward camera!)
        # Camera looks from -Z toward +Z: screen_x = ox0 + 132 - world_x * 9.5, screen_y = 215 - (world_y - 14) * 9.5
        def proj(pt):
            # slight 3/4 view angle so depth is clearly visible too
            ang = math.radians(-16.0)
            xw = pt[0] * math.cos(ang) - pt[2] * math.sin(ang)
            zw = pt[0] * math.sin(ang) + pt[2] * math.cos(ang)
            yw = pt[1] - 0.14 * zw
            return (ox0 + 138.0 - xw * 9.2, 212.0 - (yw - 14.0) * 9.2, zw)

        # Reference player silhouette boxes (head, torso, right arm)
        ref_boxes = [
            ([-4, 24, -4], [4, 32, 4], (64, 70, 92, 255)),
            ([-4, 14, -2], [4, 24, 2], (52, 58, 78, 255)),
            ([4, 14, -2],  [8, 24, 2], (58, 64, 86, 255)),
        ]

        faces_to_draw = []

        def add_box_tris(low, high, tf_fn, is_head=False):
            x0, y0, z0 = low
            x1, y1, z1 = high
            corners = [
                np.array([x0, y0, z0]), np.array([x1, y0, z0]),
                np.array([x1, y1, z0]), np.array([x0, y1, z0]),
                np.array([x0, y0, z1]), np.array([x1, y0, z1]),
                np.array([x1, y1, z1]), np.array([x0, y1, z1]),
            ]
            w_corners = [tf_fn(c) for c in corners]
            quads = [
                ('north', (2, 1, 0, 3), 1.00),
                ('south', (7, 4, 5, 6), 0.78),
                ('east',  (6, 5, 1, 2), 0.88),
                ('west',  (3, 0, 4, 7), 0.84),
                ('up',    (7, 6, 2, 3), 1.00),
                ('down',  (0, 1, 5, 4), 0.70),
            ]
            for fname, idxs, shade_mul in quads:
                pts3 = [w_corners[k] for k in idxs]
                # Backface check in camera space
                p2d = [proj(p) for p in pts3]
                cross = (p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1]) - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0])
                if cross > 0:
                    continue
                z_avg = sum(p[2] for p in p2d) / 4.0
                if is_head and fname == 'north':
                    # Subdivide into exact 8x8 face pixels so we verify cyan face orientation in 3D!
                    p_tl, p_bl, p_br, p_tr = pts3
                    for gy in range(8):
                        for gx in range(8):
                            u0, u1 = gx / 8.0, (gx + 1) / 8.0
                            v0, v1 = gy / 8.0, (gy + 1) / 8.0
                            def bilerp(uu, vv):
                                top = p_tl * (1 - uu) + p_tr * uu
                                bot = p_bl * (1 - uu) + p_br * uu
                                return top * (1 - vv) + bot * vv
                            sub = [proj(bilerp(u0, v0)), proj(bilerp(u0, v1)), proj(bilerp(u1, v1)), proj(bilerp(u1, v0))]
                            base = SKIN_CYAN[:3] if (gx, gy) in CYAN_FACE_PIXELS else (255, 255, 255)
                            col = tuple(int(c * shade_mul) for c in base) + (255,)
                            faces_to_draw.append((z_avg - 0.01, [(s[0], s[1]) for s in sub], col, None))
                else:
                    col = tuple(int(255 * shade_mul) for _ in range(3)) + (255,)
                    faces_to_draw.append((z_avg, [(s[0], s[1]) for s in p2d], col, (90, 102, 128, 255)))

        for low, high, rcol in ref_boxes:
            x0, y0, z0 = low
            x1, y1, z1 = high
            cs = [np.array([x0,y0,z0]), np.array([x1,y0,z0]), np.array([x1,y1,z0]), np.array([x0,y1,z0]),
                  np.array([x0,y0,z1]), np.array([x1,y0,z1]), np.array([x1,y1,z1]), np.array([x0,y1,z1])]
            for idxs, sm in (((2,1,0,3),1.0), ((6,5,1,2),0.88), ((3,0,4,7),0.82), ((7,6,2,3),1.05)):
                p2d = [proj(cs[k]) for k in idxs]
                cross = (p2d[1][0]-p2d[0][0])*(p2d[2][1]-p2d[0][1]) - (p2d[1][1]-p2d[0][1])*(p2d[2][0]-p2d[0][0])
                if cross <= 0:
                    col = tuple(min(255, int(c * sm)) for c in rcol[:3]) + (255,)
                    faces_to_draw.append((sum(p[2] for p in p2d)/4.0, [(s[0], s[1]) for s in p2d], col, (40,44,60,255)))

        # Walk articulated mini_me bone hierarchy
        dancer_orig = np.array([CX, FEET_Y, CZ])
        d_pos = np.array(pose['dancer_pos'])
        m_dancer = rot_mat(*pose['dancer_rot'])
        pelvis_orig = np.array([CX, FEET_Y + 12 * SCALE, CZ])
        m_pelvis = rot_mat(*pose['pelvis_rot'])
        m_torso = rot_mat(*pose['torso_rot'])

        def tf_pelvis(p):
            p1 = pelvis_orig + m_pelvis @ (p - pelvis_orig)
            return dancer_orig + d_pos + m_dancer @ (p1 - dancer_orig)

        def tf_torso(p):
            p0 = pelvis_orig + m_torso @ (p - pelvis_orig)
            return tf_pelvis(p0)

        def limb_tf(parent_tf, orig, rot_angles):
            m = rot_mat(*rot_angles)
            o = np.array(orig)
            return lambda p: parent_tf(o + m @ (p - o))

        bone_Specs = [
            ('torso_cube', tf_torso, False),
            ('head_cube', limb_tf(tf_torso, [CX, FEET_Y + 24 * SCALE, CZ], pose['head_rot']), True),
            ('right_arm_cube', limb_tf(tf_torso, [CX + 4 * SCALE, FEET_Y + 24 * SCALE - 0.3, CZ], pose['right_arm_rot']), False),
            ('left_arm_cube', limb_tf(tf_torso, [CX - 4 * SCALE, FEET_Y + 24 * SCALE - 0.3, CZ], pose['left_arm_rot']), False),
            ('right_leg_cube', limb_tf(tf_pelvis, [CX + 2 * SCALE, FEET_Y + 12 * SCALE, CZ], pose['right_leg_rot']), False),
            ('left_leg_cube', limb_tf(tf_pelvis, [CX - 2 * SCALE, FEET_Y + 12 * SCALE, CZ], pose['left_leg_rot']), False),
        ]
        by_name = {el['name']: el for el in elements.values()}
        for cname, tfn, is_h in bone_Specs:
            el = by_name[cname]
            add_box_tris(el['from'], el['to'], tfn, is_head=is_h)

        # Painter's sort back-to-front (higher z = farther back)
        faces_to_draw.sort(key=lambda item: -item[0])
        for _, poly, fill_col, edge_col in faces_to_draw:
            draw.polygon(poly, fill=fill_col, outline=edge_col)

    # Panel 5: Zoomed 32x32 menu icon + zoomed 8x8 skin face texture check
    ox4 = 4 * panel_w
    icon_big = icon.resize((112, 112), Image.NEAREST)
    canvas.alpha_composite(icon_big, (ox4 + 54, 14))
    face_crop = texture.crop((0, 0, 32, 32)).resize((88, 88), Image.NEAREST)
    canvas.alpha_composite(face_crop, (ox4 + 66, 140))
    draw.rectangle([ox4 + 65, 139, ox4 + 154, 228], outline=(91, 251, 255, 255), width=1)

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
    parser.add_argument('--rp-zip', default=str(ROOT / 'rp/Elytrix-RP-1.21.zip'))
    parser.add_argument('--preview', default=str(HERE / 'mini_me_preview.png'))
    args = parser.parse_args()

    blueprint, texture = build_blueprint()
    bb_path = Path(args.out_bbmodel)
    bb_path.write_text(json.dumps(blueprint, indent=2) + '\n', encoding='utf-8')
    texture.save(HERE / f'{MODEL}.png', optimize=True)

    assets_dir = Path(args.out_assets)
    icon = build_mini_me_icon()
    write_icon_assets(icon, assets_dir)
    build_gui_assets(Path(args.rp_zip), assets_dir)
    render_preview(blueprint, texture, icon, Path(args.preview))

    print(f'Built {bb_path.name}: {len(blueprint["elements"])} cubes, '
          f'{len(blueprint["animations"][0]["animators"])} animated bones, '
          f'icon + 3-section RP GUI assets -> {assets_dir}')


if __name__ == '__main__':
    main()
