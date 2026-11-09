#!/usr/bin/env python3
"""Procedurally builds the 3D Raincloud Hat (`elytrix_lightning_hat`),
its 32x32 pixel-art menu icon (`reallyworld:lightning_hat_icon`), and a 4-angle
verification preview strip.

100% pure procedural Python + Pillow + NumPy — zero AI generation:
  1. Calm Volumetric Cumulus Cloud (`storm_cloud`):
       - 9-cube rounded cumulus silhouette hovering cozy & low right above the player's
         head (`Y = 33.40 .. 37.00`, bare skull top = `30.00`).
       - Soft atmospheric slate-blue/grey palette (`#566478 .. #7C8FA8`) with a
         100% clean, unpainted underside (`down` uses the exact same calm `UV_CLOUD_BASE`
         as the sides — zero dark spots, zero lightning!).
  2. Gentle 3D Dripping Rain (`drop_01 .. drop_12`, seamless 3.2s loop @ 20 TPS):
       - 12 delicate tapered 2-part 3D translucent sky-water droplets distributed under
         the cloud belly (`X in [-3.3..+3.3]`, `Z in [-2.2..+2.2]`).
       - Each droplet condenses smoothly at the cloud base, accelerates downward under
         gravity (`dy = -fall * (0.28*t + 0.72*t^2)`), flattens into a soft micro-splash,
         and holds `scale = [0, 0, 0]` for 4 full server ticks while resetting its Y
         position so ModelEngine's 20-TPS interpolation NEVER streaks upward!
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import math
import sys
import uuid
from pathlib import Path

sys.path.insert(0, '/tmp/pytools')
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = 'elytrix_lightning_hat'
ICON = 'lightning_hat_icon'

IDLE_LEN = 3.2      # 64 ticks @ 20 TPS
IDLE_STEPS = 64


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f'elytrix.rain_cloud_hat.v4:{tag}'))


def _pt(x: float, y: float, z: float) -> list[float]:
    return [round(float(x), 4), round(float(y), 4), round(float(z), 4)]


# ---------------------------------------------------------------------------
# 1. Soft Cumulus Cloud & Crystal Sky-Water Texture (64x64, UV 16x16)
# ---------------------------------------------------------------------------
UV_CLOUD_BASE   = (0.25, 0.25, 3.75, 3.75)    # Calm medium slate-blue cloud body & clean underside
UV_CLOUD_MID    = (4.25, 0.25, 7.75, 3.75)    # Soft cool blue-grey upper-side cumulus puff
UV_CLOUD_CROWN  = (8.25, 0.25, 11.75, 3.75)   # Airy silver-blue sunlit cloud top
UV_CLOUD_LIGHT  = (12.25, 0.25, 15.75, 3.75)  # Bright soft misty highlight on highest crown puff

UV_DROP_BODY    = (0.25, 4.25, 3.75, 7.75)    # Translucent sky-blue water droplet body
UV_DROP_TIP     = (4.25, 4.25, 7.75, 7.75)    # Glistening pale-ice droplet tail / specular highlight


def build_raincloud_texture() -> Image.Image:
    """Builds a crisp 64x64 pixel-art texture for the calm raincloud & translucent raindrops."""
    arr = np.zeros((64, 64, 4), dtype=np.uint8)

    def paint_cloud_tile(tx: int, ty: int, base: tuple, hi: tuple, lo: tuple):
        ox, oy = tx * 16, ty * 16
        for py in range(16):
            for px in range(16):
                bx, by = px // 2, py // 2
                puff = ((bx * 3 + by * 5) % 7 == 0)
                shade = ((bx * 5 - by * 3) % 9 == 0)
                edge = min(bx, by, 7 - bx, 7 - by)
                if edge == 0 and (bx + by) % 2 == 0:
                    c = lo
                elif puff:
                    c = hi
                elif shade:
                    c = lo
                else:
                    d = 3 if ((bx + by) % 2 == 0) else 0
                    c = (base[0] + d, base[1] + d, base[2] + d, 255)
                arr[oy + py, ox + px] = c

    # Row 0: Soft cumulus cloud tiles (100% calm & natural — zero dark/painted bottom!)
    paint_cloud_tile(0, 0, (92, 108, 130, 255),  (102, 118, 142, 255), (84, 98, 120, 255))
    paint_cloud_tile(1, 0, (106, 122, 146, 255), (118, 136, 160, 255), (96, 112, 134, 255))
    paint_cloud_tile(2, 0, (124, 142, 166, 255), (138, 156, 182, 255), (112, 128, 152, 255))
    paint_cloud_tile(3, 0, (142, 160, 186, 255), (156, 174, 198, 255), (128, 146, 172, 255))

    # Tile (0,1): Translucent Sky-Water Droplet Body
    for py in range(16):
        for px in range(16):
            bx, by = px // 2, py // 2
            spec = (bx in (2, 3) and by in (2, 3, 4))
            if spec:
                col = (228, 246, 255, 228)
            elif by >= 6:
                col = (94, 174, 242, 212)
            else:
                col = (126, 198, 252, 198)
            arr[16 + py, px] = col

    # Tile (1,1): Glistening Pale-Aqua Upper Tail
    for py in range(16):
        for px in range(16):
            bx, by = px // 2, py // 2
            col = (212, 240, 255, 190) if ((bx + by) % 2 == 0) else (166, 218, 255, 176)
            arr[16 + py, 16 + px] = col

    return Image.fromarray(arr)


# ---------------------------------------------------------------------------
# 2. Cube Helpers & Raindrop Layout
# ---------------------------------------------------------------------------
def _faces(default_uv: tuple, **overrides) -> dict:
    out = {}
    for side in ('north', 'east', 'south', 'west', 'up', 'down'):
        u = overrides.get(side, default_uv)
        out[side] = {'uv': list(u), 'texture': 0}
    return out


def _cube(name: str, p_from: list[float], p_to: list[float], origin: list[float],
          faces: dict, shade: bool = True, light: int = 0) -> dict:
    low = [round(min(p_from[i], p_to[i]), 4) for i in range(3)]
    high = [round(max(p_from[i], p_to[i]), 4) for i in range(3)]
    return {
        'name': name,
        'box_uv': False,
        'rescale': False,
        'locked': False,
        'light_emission': int(light),
        'render_order': 'default',
        'allow_mirror_modeling': True,
        'from': low,
        'to': high,
        'autouv': 0,
        'color': 0,
        'origin': [round(float(v), 4) for v in origin],
        'rotation': [0.0, 0.0, 0.0],
        'faces': faces,
        'type': 'cube',
        'uuid': uid(f'cube:{name}'),
        'shade': shade,
    }


ROOT_ORIG = [0.0, 34.8, 0.0]
CLOUD_ORIG = [0.0, 35.0, 0.0]

# 12 staggered raindrops under the cumulus belly (`storm_cloud` spans X=[-4.4..+4.4], Z=[-2.8..+2.8], Y_bot=33.40):
# (bone_name, x, start_y, z, fall_distance, phase_offset, speed_cycles_per_loop)
RAINDROPS = [
    ('drop_01', -2.75, 33.42, -1.35, 3.15, 0.00, 2),
    ('drop_02', -1.10, 33.36, -1.65, 3.05, 0.41, 2),
    ('drop_03',  0.85, 33.36, -1.55, 3.05, 0.17, 2),
    ('drop_04',  2.65, 33.42, -1.20, 3.15, 0.63, 2),
    ('drop_05', -3.35, 33.52,  0.05, 3.55, 0.28, 2),
    ('drop_06', -1.45, 33.34,  0.10, 3.02, 0.77, 2),
    ('drop_07',  0.20, 33.34, -0.05, 3.02, 0.52, 2),
    ('drop_08',  1.75, 33.36,  0.20, 3.05, 0.09, 2),
    ('drop_09',  3.35, 33.52, -0.10, 3.55, 0.86, 2),
    ('drop_10', -2.35, 33.42,  1.45, 3.15, 0.34, 2),
    ('drop_11', -0.25, 33.36,  1.65, 3.05, 0.69, 2),
    ('drop_12',  2.20, 33.42,  1.40, 3.15, 0.93, 2),
]


# ---------------------------------------------------------------------------
# 3. Natural Gravity Drip Physics (Zero Upward Interpolation Streaks!)
# ---------------------------------------------------------------------------
def _eval_single_drop(local_p: float, fall_dist: float) -> tuple[float, list[float]]:
    """Evaluates (dy, scale_xyz) for a single raindrop at phase `local_p` in [0, 1):
       [0.00 .. 0.12): Condenses smoothly at cloud belly (dy = 0, scale 0 -> 1)
       [0.12 .. 0.74): Accelerates downward under gravity (dy 0 -> -fall_dist, elongated teardrop)
       [0.74 .. 0.84): Gentle micro-splash flatten at bottom (dy = -fall_dist, scale -> 0)
       [0.84 .. 1.00): Invisible hold (`scale = [0, 0, 0]`) while dy resets to 0.0!
    """
    p = local_p % 1.0
    if p < 0.12:
        s = p / 0.12
        sc = round(s * s * (3.0 - 2.0 * s), 4)
        return 0.0, [sc, sc, sc]
    if p < 0.74:
        t = (p - 0.12) / 0.62
        dy = -fall_dist * (0.28 * t + 0.72 * t * t)
        stretch_y = 1.0 + 0.22 * t
        thin_xz = 1.0 - 0.10 * t
        return round(dy, 4), [round(thin_xz, 4), round(stretch_y, 4), round(thin_xz, 4)]
    if p < 0.84:
        s = (p - 0.74) / 0.10
        fade = max(0.0, 1.0 - s)
        sx = (1.0 + 0.45 * s) * fade
        sy = max(0.0, 0.35 * fade)
        return round(-fall_dist, 4), [round(sx, 4), round(sy, 4), round(sx, 4)]
    # Held strictly at [0, 0, 0] across >= 5 ticks so resetting dy -> 0 is 100% invisible!
    return 0.0, [0.0, 0.0, 0.0]


def eval_rain_pose(u: float) -> dict:
    tau = 2.0 * math.pi
    u_per = u % 1.0

    # Calm drifting cumulus motion
    root_bob = 0.16 * math.sin(tau * u_per)
    root_sway_x = 0.10 * math.sin(tau * u_per + 0.6)
    cloud_roll = 1.2 * math.sin(tau * u_per)
    cloud_breath = 1.0 + 0.018 * math.sin(tau * 2.0 * u_per)

    drops = {}
    for bname, _, _, _, fall_dist, phi, cycles in RAINDROPS:
        local_p = (u_per * cycles + phi) % 1.0
        dy, sc = _eval_single_drop(local_p, fall_dist)
        drops[bname] = ([0.0, dy, 0.0], sc)

    return {
        'root_pos': [round(root_sway_x, 4), round(root_bob, 4), 0.0],
        'cloud_rot': [0.0, 0.0, round(cloud_roll, 4)],
        'cloud_scale': [round(cloud_breath, 4), round(1.0 - 0.010 * math.sin(tau * 2.0 * u_per), 4), round(cloud_breath, 4)],
        'drops': drops,
    }


def _vec_kf(channel: str, tag: str, t: float, x: float, y: float, z: float) -> dict:
    t_r = round(float(t), 4)
    return {
        'channel': channel,
        'data_points': [{'x': str(round(x, 4)), 'y': str(round(y, 4)), 'z': str(round(z, 4))}],
        'uuid': uid(f'kf:{tag}:{channel}:{t_r}'),
        'time': t_r,
        'color': -1,
        'interpolation': 'linear',
    }


def build_idle_animators() -> dict:
    bones = ['lightning_root', 'storm_cloud'] + [r[0] for r in RAINDROPS]
    kfs = {b: [] for b in bones}

    for s in range(IDLE_STEPS + 1):
        u = 0.0 if s == IDLE_STEPS else (s / IDLE_STEPS)
        t = IDLE_LEN * (s / IDLE_STEPS)
        pose = eval_rain_pose(u)

        kfs['lightning_root'].append(_vec_kf('position', 'idle:root', t, *pose['root_pos']))
        kfs['storm_cloud'].append(_vec_kf('rotation', 'idle:cloud', t, *pose['cloud_rot']))
        kfs['storm_cloud'].append(_vec_kf('scale', 'idle:cloud', t, *pose['cloud_scale']))

        for bname, _, _, _, _, _, _ in RAINDROPS:
            d_pos, d_sc = pose['drops'][bname]
            kfs[bname].append(_vec_kf('position', f'idle:{bname}', t, *d_pos))
            kfs[bname].append(_vec_kf('scale', f'idle:{bname}', t, *d_sc))

    return {
        uid(f'bone:{b}'): {'name': b, 'type': 'bone', 'keyframes': kfs[b]}
        for b in bones
    }


# ---------------------------------------------------------------------------
# 4. Blueprint Builder (`elytrix_lightning_hat.bbmodel`)
# ---------------------------------------------------------------------------
def build_blueprint() -> tuple[dict, Image.Image]:
    texture = build_raincloud_texture()
    raw = io.BytesIO()
    texture.save(raw, format='PNG', optimize=True)

    elements: list[dict] = []

    def add(c: dict) -> str:
        elements.append(c)
        return c['uuid']

    # Clean, unpainted cumulus cloud faces (`down` uses the exact same calm `UV_CLOUD_BASE`!)
    cloud_belly_faces = _faces(
        UV_CLOUD_BASE,
        up=UV_CLOUD_MID,
        down=UV_CLOUD_BASE,
    )
    cloud_puff_faces = _faces(
        UV_CLOUD_MID,
        up=UV_CLOUD_CROWN,
        down=UV_CLOUD_BASE,
    )
    cloud_crown_faces = _faces(
        UV_CLOUD_CROWN,
        up=UV_CLOUD_LIGHT,
        down=UV_CLOUD_MID,
    )

    # Cozy low cumulus cloud (`Y = 33.40 .. 37.00` — right above head `Y = 30.00`!)
    cloud_uuids = [
        add(_cube('cloud_core',        [-3.40, 33.40, -2.35], [ 3.40, 35.30,  2.35], CLOUD_ORIG, cloud_belly_faces, shade=True, light=3)),
        add(_cube('cloud_front',       [-2.55, 33.55, -2.85], [ 2.55, 35.05, -2.10], CLOUD_ORIG, cloud_belly_faces, shade=True, light=3)),
        add(_cube('cloud_back',        [-2.65, 33.55,  2.10], [ 2.65, 35.10,  2.85], CLOUD_ORIG, cloud_belly_faces, shade=True, light=3)),
        add(_cube('cloud_left',        [-4.40, 33.65, -1.75], [-3.15, 35.15,  1.75], CLOUD_ORIG, cloud_belly_faces, shade=True, light=3)),
        add(_cube('cloud_right',       [ 3.15, 33.65, -1.75], [ 4.40, 35.15,  1.75], CLOUD_ORIG, cloud_belly_faces, shade=True, light=3)),
        add(_cube('cloud_puff_center', [-2.05, 35.00, -1.75], [ 1.85, 37.00,  1.65], CLOUD_ORIG, cloud_crown_faces, shade=True, light=4)),
        add(_cube('cloud_puff_left',   [-3.65, 34.75, -1.35], [-1.35, 36.35,  1.45], CLOUD_ORIG, cloud_puff_faces,  shade=True, light=4)),
        add(_cube('cloud_puff_right',  [ 1.25, 34.75, -1.45], [ 3.55, 36.25,  1.35], CLOUD_ORIG, cloud_puff_faces,  shade=True, light=4)),
        add(_cube('cloud_puff_rear',   [-1.55, 34.85,  1.15], [ 1.65, 36.15,  2.45], CLOUD_ORIG, cloud_puff_faces,  shade=True, light=4)),
    ]

    drop_body_faces = _faces(UV_DROP_BODY, up=UV_DROP_TIP)
    drop_tip_faces = _faces(UV_DROP_TIP)

    drop_bones = []
    for bname, dx, dy_start, dz, _, _, _ in RAINDROPS:
        d_orig = _pt(dx, dy_start, dz)
        d_uuids = [
            # Lower plump droplet body
            add(_cube(
                f'{bname}_body',
                [dx - 0.095, dy_start - 0.48, dz - 0.095],
                [dx + 0.095, dy_start,        dz + 0.095],
                d_orig,
                drop_body_faces,
                shade=False,
                light=9,
            )),
            # Slender tapered upper water tail
            add(_cube(
                f'{bname}_tail',
                [dx - 0.055, dy_start,        dz - 0.055],
                [dx + 0.055, dy_start + 0.24, dz + 0.055],
                d_orig,
                drop_tip_faces,
                shade=False,
                light=10,
            )),
        ]
        drop_bones.append({
            'name': bname,
            'origin': d_orig,
            'rotation': [0.0, 0.0, 0.0],
            'color': 0,
            'uuid': uid(f'bone:{bname}'),
            'export': True,
            'mirror_uv': False,
            'isOpen': True,
            'locked': False,
            'visibility': True,
            'autouv': 0,
            'children': d_uuids,
        })

    def bone(name: str, orig: list[float], children: list) -> dict:
        return {
            'name': name,
            'origin': [round(float(v), 4) for v in orig],
            'rotation': [0.0, 0.0, 0.0],
            'color': 0,
            'uuid': uid(f'bone:{name}'),
            'export': True,
            'mirror_uv': False,
            'isOpen': True,
            'locked': False,
            'visibility': True,
            'autouv': 0,
            'children': children,
        }

    outliner = [
        bone('lightning_root', ROOT_ORIG, [
            bone('storm_cloud', CLOUD_ORIG, cloud_uuids),
            *drop_bones,
        ]),
        {
            'name': 'hitbox',
            'origin': [0.0, 16.0, 0.0],
            'rotation': [0.0, 0.0, 0.0],
            'color': 0,
            'uuid': uid('bone:hitbox'),
            'export': True,
            'mirror_uv': False,
            'isOpen': False,
            'locked': False,
            'visibility': False,
            'autouv': 0,
            'children': [],
        },
    ]

    blueprint = {
        'meta': {
            'format_version': '4.10',
            'model_format': 'free',
            'box_uv': False,
        },
        'name': MODEL,
        'model_identifier': MODEL,
        'visible_box': [2, 3, 0],
        'variable_placeholders': '',
        'variable_placeholder_buttons': [],
        'timeline_setups': [],
        'unhandled_root_fields': {},
        'resolution': {'width': 16, 'height': 16},
        'elements': elements,
        'outliner': outliner,
        'textures': [{
            'path': '',
            'name': f'{MODEL}.png',
            'folder': '',
            'namespace': '',
            'id': '0',
            'width': 64,
            'height': 64,
            'uv_width': 16,
            'uv_height': 16,
            'particle': False,
            'use_as_default': False,
            'layers_enabled': False,
            'sync_to_project': '',
            'render_mode': 'default',
            'render_sides': 'auto',
            'frame_time': 1,
            'frame_order_type': 'loop',
            'frame_order': '',
            'frame_interpolate': False,
            'visible': True,
            'internal': True,
            'saved': True,
            'uuid': uid('tex:0'),
            'source': 'data:image/png;base64,' + base64.b64encode(raw.getvalue()).decode('ascii'),
        }],
        'animations': [{
            'uuid': uid('anim:idle'),
            'name': 'idle',
            'loop': 'loop',
            'override': False,
            'length': IDLE_LEN,
            'snapping': 20,
            'selected': True,
            'saved': True,
            'path': '',
            'anim_time_update': '',
            'blend_weight': '',
            'start_delay': '',
            'loop_delay': '',
            'animators': build_idle_animators(),
        }],
    }
    return blueprint, texture


# ---------------------------------------------------------------------------
# 5. Hand-Crafted 32x32 Pixel-Art Raincloud Icon (`reallyworld:lightning_hat_icon`)
# ---------------------------------------------------------------------------
def build_raincloud_icon() -> Image.Image:
    """Draws a crisp 32x32 pixel-art fluffy raincloud with sky-blue raindrops (zero lightning!)."""
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    outline   = (58, 70, 88, 255)
    c_base    = (94, 110, 134, 255)
    c_mid     = (120, 138, 164, 255)
    c_crown   = (148, 168, 194, 255)
    c_hi      = (178, 196, 218, 255)

    drop_deep = (78, 158, 236, 255)
    drop_mid  = (118, 196, 255, 255)
    drop_hi   = (216, 244, 255, 255)

    # Fluffy cumulus silhouette made of overlapping circles
    circles = [
        (9.5,  13.5, 4.6),
        (22.0, 13.8, 4.4),
        (15.5, 13.8, 5.2),
        (13.0,  9.8, 4.8),
        (18.8, 10.4, 4.2),
    ]
    inside = set()
    for y in range(32):
        for x in range(32):
            if y > 17:
                continue
            for cx, cy, r in circles:
                if math.hypot(x - cx, y - cy) <= r:
                    inside.add((x, y))
                    break

    for (x, y) in inside:
        is_border = any((x + dx, y + dy) not in inside for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))
        if is_border:
            px[x, y] = outline
        elif y <= 7:
            px[x, y] = c_hi
        elif y <= 10:
            px[x, y] = c_crown
        elif y <= 13:
            px[x, y] = c_mid
        else:
            px[x, y] = c_base

    # 6 crisp pixel-art raindrops dripping underneath the cloud
    drops_2d = [
        (8,  20),
        (13, 23),
        (18, 19),
        (23, 22),
        (10, 27),
        (20, 26),
    ]
    for dx, dy in drops_2d:
        if 0 <= dy - 1 < 32:
            px[dx, dy - 1] = drop_hi
        if 0 <= dy < 32:
            px[dx, dy] = drop_mid
            if dx + 1 < 32:
                px[dx + 1, dy] = drop_deep
        if 0 <= dy + 1 < 32:
            px[dx, dy + 1] = drop_deep
            if dx + 1 < 32:
                px[dx + 1, dy + 1] = drop_mid

    return img


# ---------------------------------------------------------------------------
# 6. 4-Angle Verification Preview Renderer (`lightning_hat_preview.png`)
# ---------------------------------------------------------------------------
def render_preview(blueprint: dict, texture: Image.Image, icon: Image.Image, out_path: Path):
    panel_w, panel_h = 240, 300
    canvas = Image.new('RGBA', (panel_w * 4 + 200, panel_h), (20, 24, 34, 255))

    def rot_mat(rx, ry, rz):
        rx, ry, rz = map(math.radians, (rx, ry, rz))
        cx_, sx_ = math.cos(rx), math.sin(rx)
        cy_, sy_ = math.cos(ry), math.sin(ry)
        cz_, sz_ = math.cos(rz), math.sin(rz)
        mx = np.array([[1, 0, 0], [0, cx_, -sx_], [0, sx_, cx_]])
        my = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]])
        mz = np.array([[cz_, -sz_, 0], [sz_, cz_, 0], [0, 0, 1]])
        return mz @ my @ mx

    tex_arr = np.array(texture)
    by_uuid = {el['uuid']: el for el in blueprint['elements']}
    root_group = blueprint['outliner'][0]
    bone_cubes = {child['name']: [by_uuid[u] for u in child['children']] for child in root_group['children']}
    bone_origs = {child['name']: child['origin'] for child in root_group['children']}

    stages = [
        (0.12,  24.0, -14.0),   # Front-3/4 showing low cloud + falling raindrops
        (0.38, -42.0, -14.0),   # Side-3/4 showing staggered rain curtain
        (0.64,  18.0,  22.0),   # Upward angle proving 100% clean unpainted cloud underside + raindrops!
        (0.86, 152.0, -14.0),   # Back-3/4 view
    ]

    for idx, (u, cam_yaw, cam_pitch) in enumerate(stages):
        panel = Image.new('RGBA', (panel_w, panel_h), (28, 34, 46, 255))
        pose = eval_rain_pose(u)

        ay = math.radians(cam_yaw)
        ap = math.radians(cam_pitch)
        cy_m, sy_m = math.cos(ay), math.sin(ay)
        cp_m, sp_m = math.cos(ap), math.sin(ap)

        def proj(pt):
            dx, dy, dz = pt[0], pt[1] - 29.8, pt[2]
            xw = dx * cy_m - dz * sy_m
            z1 = dx * sy_m + dz * cy_m
            yw = dy * cp_m - z1 * sp_m
            zw = dy * sp_m + z1 * cp_m
            return (panel_w * 0.5 - xw * 14.2, 182.0 - yw * 14.2, zw)

        faces_to_draw = []
        ref_boxes = [
            ([-7.5, 18.0, -1.875], [7.5, 22.5, 1.875], (52, 58, 74)),
            ([-3.75, 22.5, -3.75], [3.75, 30.0, 3.75], (86, 94, 114)),
        ]
        for low, high, base_rgb in ref_boxes:
            cs = [
                np.array([low[0], low[1], low[2]]), np.array([high[0], low[1], low[2]]),
                np.array([high[0], high[1], low[2]]), np.array([low[0], high[1], low[2]]),
                np.array([low[0], low[1], high[2]]), np.array([high[0], low[1], high[2]]),
                np.array([high[0], high[1], high[2]]), np.array([low[0], high[1], high[2]]),
            ]
            for idxs, sm in (((2, 1, 0, 3), 1.0), ((7, 4, 5, 6), 0.86), ((6, 5, 1, 2), 0.92), ((3, 0, 4, 7), 0.90), ((7, 6, 2, 3), 1.05)):
                p2d = [proj(cs[k]) for k in idxs]
                cross = (p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1]) - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0])
                if cross <= 0:
                    col = tuple(min(255, int(c * sm)) for c in base_rgb) + (255,)
                    faces_to_draw.append((sum(p[2] for p in p2d) / 4.0, [(s[0], s[1]) for s in p2d], col, (38, 44, 58, 255)))

        def bone_tf(parent_tf, orig, pos, rot, scale):
            o = np.array(orig)
            t = np.array(pos)
            m = rot_mat(*rot)
            sc = np.array(scale)
            return lambda p: parent_tf(o + t + m @ (sc * (p - o)))

        tf_root = bone_tf(lambda p: p, ROOT_ORIG, pose['root_pos'], [0, 0, 0], [1, 1, 1])
        b_tfs = {'storm_cloud': bone_tf(tf_root, CLOUD_ORIG, [0, 0, 0], pose['cloud_rot'], pose['cloud_scale'])}
        for bname, _, _, _, _, _, _ in RAINDROPS:
            d_pos, d_sc = pose['drops'][bname]
            b_tfs[bname] = bone_tf(tf_root, bone_origs[bname], d_pos, [0, 0, 0], d_sc)

        for bname, cubes in bone_cubes.items():
            if bname != 'storm_cloud' and pose['drops'][bname][1][0] <= 0.01:
                continue
            tf_fn = b_tfs[bname]
            for el in cubes:
                x0, y0, z0 = el['from']
                x1, y1, z1 = el['to']
                raw_cs = [
                    np.array([x0, y0, z0]), np.array([x1, y0, z0]), np.array([x1, y1, z0]), np.array([x0, y1, z0]),
                    np.array([x0, y0, z1]), np.array([x1, y0, z1]), np.array([x1, y1, z1]), np.array([x0, y1, z1]),
                ]
                wcs = [tf_fn(c) for c in raw_cs]
                quads = [
                    ('north', (2, 1, 0, 3), 0.96),
                    ('south', (7, 4, 5, 6), 0.92),
                    ('east',  (6, 5, 1, 2), 0.94),
                    ('west',  (3, 0, 4, 7), 0.94),
                    ('up',    (7, 6, 2, 3), 1.04),
                    ('down',  (0, 1, 5, 4), 0.90),
                ]
                for fname, idxs, sm in quads:
                    p2d = [proj(wcs[k]) for k in idxs]
                    cross = (p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1]) - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0])
                    if cross > 0:
                        continue
                    uv = el['faces'][fname]['uv']
                    tx = min(63, int(0.5 * (uv[0] + uv[2]) * 4))
                    ty = min(63, int(0.5 * (uv[1] + uv[3]) * 4))
                    rgba = tex_arr[ty, tx]
                    if rgba[3] < 16:
                        continue
                    col = tuple(min(255, int(c * sm)) for c in rgba[:3]) + (int(rgba[3]),)
                    faces_to_draw.append((sum(p[2] for p in p2d) / 4.0, [(s[0], s[1]) for s in p2d], col, None))

        faces_to_draw.sort(key=lambda item: item[0], reverse=True)
        for _, poly, col, outline in faces_to_draw:
            layer = Image.new('RGBA', (panel_w, panel_h), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer, 'RGBA')
            ld.polygon(poly, fill=col, outline=outline)
            panel.alpha_composite(layer)

        canvas.paste(panel, (idx * panel_w, 0))
        d = ImageDraw.Draw(canvas)
        d.line([(idx * panel_w, 0), (idx * panel_w, panel_h)], fill=(54, 62, 80, 255), width=1)

    icon_big = icon.resize((128, 128), Image.NEAREST)
    canvas.alpha_composite(icon_big, (panel_w * 4 + 36, 24))
    tex_big = texture.resize((112, 112), Image.NEAREST)
    canvas.alpha_composite(tex_big, (panel_w * 4 + 44, 170))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-bbmodel', '--bbmodel-out', dest='bbmodel_out', type=Path,
                        default=ROOT / 'plugins/ModelEngine/blueprints' / f'{MODEL}.bbmodel')
    parser.add_argument('--assets-dir', type=Path, default=HERE / 'assets')
    parser.add_argument('--preview', type=Path, default=None)
    args = parser.parse_args()

    blueprint, texture = build_blueprint()
    args.bbmodel_out.parent.mkdir(parents=True, exist_ok=True)
    args.bbmodel_out.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding='utf-8')

    icon = build_raincloud_icon()
    icon_tex = args.assets_dir / f'reallyworld/textures/item/{ICON}.png'
    icon_model = args.assets_dir / f'reallyworld/models/item/{ICON}.json'
    icon_item = args.assets_dir / f'reallyworld/items/{ICON}.json'
    for p in (icon_tex, icon_model, icon_item):
        p.parent.mkdir(parents=True, exist_ok=True)

    icon.save(icon_tex, optimize=True)
    icon_model.write_text(json.dumps({
        'parent': 'minecraft:item/generated',
        'textures': {'layer0': f'reallyworld:item/{ICON}'},
    }, indent=2) + '\n', encoding='utf-8')
    icon_item.write_text(json.dumps({
        'model': {'type': 'minecraft:model', 'model': f'reallyworld:item/{ICON}'},
    }, indent=2) + '\n', encoding='utf-8')

    if args.preview is not None:
        render_preview(blueprint, texture, icon, args.preview)

    print(f'Built {MODEL}.bbmodel (raincloud v4): {len(blueprint["elements"])} cubes, {1 + len(RAINDROPS)} bones, icon -> {args.assets_dir}')


if __name__ == '__main__':
    main()
