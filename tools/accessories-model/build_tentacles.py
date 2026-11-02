#!/usr/bin/env python3
"""Builds Kaneki Ken's Rinkaku Kagune (elytrix_kaneki_tentacles) blueprint, texture & icon.

Canonical Tokyo Ghoul Rinkaku design (remade from scratch):
- Four distinct muscular Rinkaku tentacles (right_upper, left_upper, right_lower,
  left_lower) erupting from one compact Kakuhou organ (root_knot) on the lower-mid
  spine (y ~ 16.3, z ~ 2.2).
- Upper pair arches boldly up above shoulder height (y ~ 24.6), sweeps wide
  (|x| ~ 19.0), and curves menacingly forward past the torso plane (z ~ -3.2).
- Lower pair sweeps wider & lower beneath the ribs (|x| ~ 20.4, y ~ 9.6..14.4)
  and curls forward around the flanks (z ~ -2.6).
- 100% ZERO per-cube rotations (every cube has rotation [0.0, 0.0, 0.0]!) so
  ModelEngine 4.1.0's RotationSolver never triggers UnsupportedOperationException
  on Paper's fastutil IntSets.  Instead of rotated cubes, each bone uses an
  axis-aligned 3-cube chamfered cross-section (vertical muscle core + horizontal
  muscle core + dorsal obsidian-crimson Rinkaku scale ridge) that looks round and
  biomechanical from every camera angle.
- 128x128 procedural pixel-art Tokyo Ghoul texture (arterial blood-crimson muscle,
  obsidian-black Rc-cell veins, wet scarlet specular highlights, imbricated
  Rinkaku scales, and glowing Kakuhou core) + 32x32 menu icon.
- Living 3.6 s seamless 'idle' animation (deltas only) with traveling cephalopod
  whip waves along all four tentacle chains.
"""
import argparse
import base64
import io
import json
import math
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
MODEL = 'elytrix_kaneki_tentacles'
ROOT_ORIGIN = [0.0, 20.0, 0.0]
PARTS = tuple('abcdefghijklmnopqrstuvwx')

# ---------------------------------------------------------------------------
# Canonical 4-Tail Rinkaku Control Curves (Blockbench player coordinates)
# Player stands y=0..32 facing -Z; torso back is z=+2.0; +X = right, -X = left.
# ---------------------------------------------------------------------------
TENDRILS = [
    {
        # Upper right Rinkaku tail: erupts from lumbar Kakuhou (y=14.7), arches back
        # behind the shoulder blade (z=6.6), sweeps high above shoulder/head level
        # (y=29.8, x=20.6), and aims its razor Rinkaku spear tip forward (z=-3.4)!
        'name': 'right_upper',
        'ctrl': [
            (0.70, 14.75,  2.15),
            (1.65, 16.85,  4.45),
            (3.65, 19.65,  6.25),
            (6.85, 22.85,  6.65),
            (10.85, 25.85, 5.75),
            (14.85, 28.15, 3.55),
            (18.15, 29.55, 0.35),
            (20.15, 30.10, -2.15),
            (20.65, 29.85, -3.65),
        ],
        'girth': (3.00, 2.90),
        'blunt': 0.34,
    },
    {
        'name': 'left_upper',
        'ctrl': [
            (-0.70, 14.75,  2.15),
            (-1.65, 16.85,  4.45),
            (-3.65, 19.65,  6.25),
            (-6.85, 22.85,  6.65),
            (-10.85, 25.85, 5.75),
            (-14.85, 28.15, 3.55),
            (-18.15, 29.55, 0.35),
            (-20.15, 30.10, -2.15),
            (-20.65, 29.85, -3.65),
        ],
        'girth': (2.94, 2.84),
        'blunt': 0.34,
    },
    {
        # Lower right Rinkaku tail: erupts slightly lower (y=14.0), dips into an
        # organic anime S-curve beneath the waist (y=11.5, z=7.0), sweeps wider
        # out to the flank (x=22.8), and curls forward at mid-torso height (z=-3.5)!
        'name': 'right_lower',
        'ctrl': [
            (0.75, 14.05,  2.15),
            (2.05, 12.55,  4.55),
            (4.65, 11.55,  6.55),
            (8.25, 11.75,  7.05),
            (12.45, 13.05, 6.05),
            (16.65, 14.95, 3.75),
            (20.15, 16.85, 0.55),
            (22.15, 18.15, -2.05),
            (22.85, 18.65, -3.55),
        ],
        'girth': (2.86, 2.76),
        'blunt': 0.34,
    },
    {
        'name': 'left_lower',
        'ctrl': [
            (-0.75, 14.05,  2.15),
            (-2.05, 12.55,  4.55),
            (-4.65, 11.55,  6.55),
            (-8.25, 11.75,  7.05),
            (-12.45, 13.05, 6.05),
            (-16.65, 14.95, 3.75),
            (-20.15, 16.85, 0.55),
            (-22.15, 18.15, -2.05),
            (-22.85, 18.65, -3.55),
        ],
        'girth': (2.80, 2.70),
        'blunt': 0.34,
    },
]

# Sculpted Kakuhou organ on the lumbar spine (y=14.4): sinks slightly into z < 2.0
# so no air gap shows on the back, and protrudes cleanly behind the spine (z > 4.4).
KNOT = {
    'name': 'root_knot',
    'origin': [0.0, 14.4, 2.3],
    'boxes': [
        (-2.35, 2.35, -1.55, 1.55, -0.85, 1.65, 'kakuhou'),
        (-1.85, 1.85, -2.15, 2.15, -0.75, 1.35, 'side'),
        (-2.70, 2.70, -0.95, 0.95, -0.65, 1.25, 'side'),
        (-1.45, 1.45, -1.10, 1.10,  1.15, 2.35, 'kakuhou'),
        (-0.90, 0.90, -0.65, 0.65,  1.85, 2.85, 'ridge'),
    ],
}

MAX_LEN = 2.55
MIN_TIP_LEN = 0.75
ANIM_LENGTH = 3.6
ANIM_FRAMES = 37   # 0.10 s per keyframe, seamless loop


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'elytrix-kaneki-rinkaku-v10:{tag}'))


def _clamp8(v: float) -> int:
    return max(0, min(255, int(round(v))))


# ---------------------------------------------------------------------------
# Centripetal Catmull-Rom Spline & Exact Rz * Ry Bone Chain Solver
# ---------------------------------------------------------------------------
def smoothstep(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def _cr(p0, p1, p2, p3, t, alpha=0.5):
    def tj(ti, a, b):
        return ti + max(1e-6, math.dist(a, b)) ** alpha

    t0 = 0.0
    t1 = tj(t0, p0, p1)
    t2 = tj(t1, p1, p2)
    t3 = tj(t2, p2, p3)
    tt = t1 + (t2 - t1) * t

    def lerp(a, b, ta, tb, x):
        w = (x - ta) / max(1e-9, tb - ta)
        return tuple(a[i] + (b[i] - a[i]) * w for i in range(len(a)))

    a1 = lerp(p0, p1, t0, t1, tt)
    a2 = lerp(p1, p2, t1, t2, tt)
    a3 = lerp(p2, p3, t2, t3, tt)
    b1 = lerp(a1, a2, t0, t2, tt)
    b2 = lerp(a2, a3, t1, t3, tt)
    return lerp(b1, b2, t1, t2, tt)


def spline(points, per_span=28):
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(len(pts) - 3):
        for step in range(per_span):
            out.append(_cr(*pts[i:i + 4], step / per_span))
    out.append(tuple(points[-1]))
    return out


def _norm(v):
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / length for c in v)


def turn_between(a, b, c):
    u = _norm(tuple(b[i] - a[i] for i in range(3)))
    v = _norm(tuple(c[i] - b[i] for i in range(3)))
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(u[i] * v[i] for i in range(3))))))


def allowed_turn(t: float) -> float:
    return 13.5 if t < 0.65 else 19.5


def adaptive_resample(dense, max_len=MAX_LEN):
    total = sum(math.dist(a, b) for a, b in zip(dense, dense[1:])) or 1.0
    joints = [dense[0]]
    turned = 0.0
    length = 0.0
    walked = 0.0
    for index in range(1, len(dense) - 1):
        step = math.dist(dense[index - 1], dense[index])
        turned += turn_between(dense[index - 1], dense[index], dense[index + 1])
        length += step
        walked += step
        if turned >= allowed_turn(walked / total) or length >= max_len:
            joints.append(dense[index])
            turned = 0.0
            length = 0.0
    joints.append(dense[-1])
    while len(joints) > 3 and math.dist(joints[-2], joints[-1]) < MIN_TIP_LEN:
        joints.pop(-2)
    return joints


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def rot_z(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def rot_y(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]


IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def solve_euler(points):
    world = IDENTITY
    euler = []
    for a, b in zip(points, points[1:]):
        d = _norm(tuple(b[i] - a[i] for i in range(3)))
        local = tuple(sum(world[k][i] * d[k] for k in range(3)) for i in range(3))
        beta = -math.degrees(math.asin(max(-1.0, min(1.0, local[2]))))
        alpha = math.degrees(math.atan2(local[1], local[0]))
        euler.append([0.0, round(beta, 4), round(alpha, 4)])
        world = _matmul(_matmul(world, rot_z(alpha)), rot_y(beta))
    return euler


def chain_points(origin, euler, lengths):
    world = IDENTITY
    point = tuple(origin)
    out = [point]
    for angles, length in zip(euler, lengths):
        world = _matmul(_matmul(world, rot_z(angles[2])), rot_y(angles[1]))
        direction = (world[0][0], world[1][0], world[2][0])
        point = tuple(point[i] + direction[i] * length for i in range(3))
        out.append(point)
    return out


def blade_profile(spec, t: float):
    width0, depth0 = spec['girth']
    blunt = spec.get('blunt', 0.58)
    if t < 0.18:
        share = 0.56 + 0.44 * smoothstep(t / 0.18)
    elif t > 0.42:
        share = 1.0 - (1.0 - blunt) * smoothstep((t - 0.42) / 0.58)
    else:
        share = 1.0
    return (width0 * share, depth0 * share)


def blade_bones(spec):
    points = adaptive_resample(spline(spec['ctrl']))
    if len(points) - 1 > len(PARTS):
        raise SystemExit(f'{spec["name"]}: {len(points) - 1} bones, raise PARTS')
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    euler = solve_euler(points)
    total = sum(lengths)
    bones = []
    walked = 0.0
    cursor = list(points[0])
    for index, (length, angles) in enumerate(zip(lengths, euler)):
        t0, t1 = walked / total, (walked + length) / total
        walked += length
        width, depth = blade_profile(spec, t1)
        bend = abs(angles[2] - (euler[index - 1][2] if index else 0.0))
        overlap = 0.0 if index == 0 else min(
            width * 0.5,
            (width / 2.0) * math.tan(math.radians(min(bend, 45.0)) / 2.0) + 0.36,
        )
        bones.append({
            'name': f'{spec["name"]}_{PARTS[index]}',
            'origin': [round(v, 4) for v in cursor],
            'rotation': angles,
            'length': length,
            'turn': angles[2],
            'yaw': angles[1],
            't': (t0 + t1) / 2.0,
            'is_tip': (index == len(lengths) - 1),
            'box': {
                'x0': round(-overlap, 4),
                'x1': round(length, 4),
                'width': width,
                'depth': depth,
            },
        })
        cursor[0] += length
    return bones


def blade_path(spec):
    bones = blade_bones(spec)
    return chain_points(bones[0]['origin'], [b['rotation'] for b in bones],
                        [b['length'] for b in bones])


# ---------------------------------------------------------------------------
# UV Regions on 128x128 Tokyo Ghoul Rinkaku Texture (UV space 0..16 -> 8 px/unit)
# ---------------------------------------------------------------------------
UV_REGIONS = {
    'side':    [0.0,  0.0,  8.0,  6.0],   # 0..64 x 0..48: arterial crimson muscle + dark Rc veins
    'scales':  [8.0,  0.0, 16.0,  6.0],   # 64..128 x 0..48: armored crimson-obsidian Rinkaku scales
    'top':     [0.0,  6.0,  8.0, 11.0],   # 0..64 x 48..88: glossy scarlet dorsal sheen
    'dark':    [8.0,  6.0, 16.0, 11.0],   # 64..128 x 48..88: deep coagulated crimson-black underside
    'ridge':   [0.0, 11.0,  8.0, 16.0],   # 0..64 x 88..128: obsidian-black dorsal crest + ruby edge
    'kakuhou': [8.0, 11.0, 16.0, 16.0],   # 64..128 x 88..128: glowing Rc-cell Kakuhou eruption flesh
}


def _uv_inset(key: str):
    u0, v0, u1, v1 = UV_REGIONS[key]
    return [round(u0 + 0.08, 3), round(v0 + 0.08, 3), round(u1 - 0.08, 3), round(v1 - 0.08, 3)]


def build_elements(bone):
    """3 axis-aligned [0, 0, 0] boxes forming a rounded chamfered Rinkaku section + dorsal scale.

    CRITICAL: Every cube MUST keep rotation == [0.0, 0.0, 0.0] so all cubes on a
    bone belong to one PlaneGroup and ModelEngine 4.1.0 never invokes the broken
    RotationSolver.fetch removeAll path on Paper's fastutil.
    """
    box = bone['box']
    origin = bone['origin']
    t = bone['t']
    side_key = 'scales' if t > 0.56 else 'side'
    top_key = 'ridge' if bone['is_tip'] else 'top'

    faces_main = {
        'up': {'uv': _uv_inset(top_key), 'texture': 0},
        'down': {'uv': _uv_inset('dark'), 'texture': 0},
        'north': {'uv': _uv_inset(side_key), 'texture': 0},
        'south': {'uv': _uv_inset(side_key), 'texture': 0},
        'east': {'uv': _uv_inset('scales' if bone['is_tip'] else side_key), 'texture': 0},
        'west': {'uv': _uv_inset(side_key), 'texture': 0},
    }
    faces_ridge = {
        'up': {'uv': _uv_inset('ridge'), 'texture': 0},
        'down': {'uv': _uv_inset('dark'), 'texture': 0},
        'north': {'uv': _uv_inset('ridge'), 'texture': 0},
        'south': {'uv': _uv_inset('ridge'), 'texture': 0},
        'east': {'uv': _uv_inset('ridge'), 'texture': 0},
        'west': {'uv': _uv_inset('ridge'), 'texture': 0},
    }

    w = box['width']
    d = box['depth']
    cx = round(origin[0] + (box['x0'] + box['x1']) * 0.5, 4)
    cy = round(origin[1], 4)
    cz = round(origin[2], 4)

    cubes = []
    # Box 0 & Box 1: Crossed axis-aligned chamfered muscle core (0 deg rotation!)
    for idx, (sy, sz) in enumerate(((1.0, 0.74), (0.74, 1.0))):
        hy = w * sy * 0.5
        hz = d * sz * 0.5
        cubes.append({
            'name': f'{bone["name"]}_{idx}',
            'box_uv': False, 'rescale': False, 'locked': False, 'light_emission': 0,
            'render_order': 'default', 'allow_mirror_modeling': True,
            'from': [round(origin[0] + box['x0'], 4), round(origin[1] - hy, 4), round(origin[2] - hz, 4)],
            'to':   [round(origin[0] + box['x1'], 4), round(origin[1] + hy, 4), round(origin[2] + hz, 4)],
            'autouv': 0, 'color': 0,
            'origin': [cx, cy, cz],
            'rotation': [0.0, 0.0, 0.0],
            'faces': {k: dict(v) for k, v in faces_main.items()},
            'type': 'cube',
            'uuid': uid(f'cube:{bone["name"]}:{idx}'),
        })

    # Box 2: Continuous dorsal obsidian-crimson Rinkaku spine + razor spear tip on last bone
    ridge_hy = w * 0.28
    rz_lo = round(origin[2] + d * 0.26, 4)
    rz_hi = round(origin[2] + d * 0.55 + 0.10, 4)
    if rz_hi - rz_lo < 0.22:
        rz_hi = round(rz_lo + 0.22, 4)
    rx0 = round(origin[0] + box['x0'], 4)
    rx1 = round(origin[0] + box['x1'] + (0.95 if bone['is_tip'] else 0.04), 4)
    cubes.append({
        'name': f'{bone["name"]}_ridge',
        'box_uv': False, 'rescale': False, 'locked': False, 'light_emission': 0,
        'render_order': 'default', 'allow_mirror_modeling': True,
        'from': [rx0, round(origin[1] - ridge_hy, 4), rz_lo],
        'to':   [rx1, round(origin[1] + ridge_hy, 4), rz_hi],
        'autouv': 0, 'color': 0,
        'origin': [cx, cy, cz],
        'rotation': [0.0, 0.0, 0.0],
        'faces': {k: dict(v) for k, v in faces_ridge.items()},
        'type': 'cube',
        'uuid': uid(f'cube:{bone["name"]}:ridge'),
    })
    if bone['is_tip']:
        # Sleek tapered Rinkaku spear stinger tip (zero rotation!)
        tip_hy = max(0.24, w * 0.26)
        tip_hz = max(0.24, d * 0.26)
        cubes.append({
            'name': f'{bone["name"]}_stinger',
            'box_uv': False, 'rescale': False, 'locked': False, 'light_emission': 0,
            'render_order': 'default', 'allow_mirror_modeling': True,
            'from': [round(origin[0] + box['x1'] - 0.15, 4), round(origin[1] - tip_hy, 4), round(origin[2] - tip_hz, 4)],
            'to':   [round(origin[0] + box['x1'] + 1.35, 4), round(origin[1] + tip_hy, 4), round(origin[2] + tip_hz, 4)],
            'autouv': 0, 'color': 0,
            'origin': [cx, cy, cz],
            'rotation': [0.0, 0.0, 0.0],
            'faces': {k: dict(v) for k, v in faces_ridge.items()},
            'type': 'cube',
            'uuid': uid(f'cube:{bone["name"]}:stinger'),
        })
    return cubes


def knot_elements():
    elements = []
    origin = KNOT['origin']
    for index, (x0, x1, y0, y1, z0, z1, region) in enumerate(KNOT['boxes']):
        faces = {
            'up': {'uv': _uv_inset('top'), 'texture': 0},
            'down': {'uv': _uv_inset('dark'), 'texture': 0},
            'north': {'uv': _uv_inset('dark'), 'texture': 0},
            'south': {'uv': _uv_inset(region), 'texture': 0},
            'east': {'uv': _uv_inset(region), 'texture': 0},
            'west': {'uv': _uv_inset(region), 'texture': 0},
        }
        elements.append({
            'name': f'{KNOT["name"]}_{index}',
            'box_uv': False, 'rescale': False, 'locked': False, 'light_emission': 0,
            'render_order': 'default', 'allow_mirror_modeling': True,
            'from': [round(origin[0] + x0, 4), round(origin[1] + y0, 4), round(origin[2] + z0, 4)],
            'to':   [round(origin[0] + x1, 4), round(origin[1] + y1, 4), round(origin[2] + z1, 4)],
            'autouv': 0, 'color': 0,
            'origin': [round(origin[0] + (x0 + x1) * 0.5, 4),
                       round(origin[1] + (y0 + y1) * 0.5, 4),
                       round(origin[2] + (z0 + z1) * 0.5, 4)],
            'rotation': [0.0, 0.0, 0.0],
            'faces': faces,
            'type': 'cube',
            'uuid': uid(f'cube:knot:{index}'),
        })
    return elements


# ---------------------------------------------------------------------------
# 128x128 Procedural Pixel-Art Texture (Canonical Tokyo Ghoul Rinkaku Palette)
# ---------------------------------------------------------------------------
def build_texture() -> Image.Image:
    size = 128
    img = Image.new('RGBA', (size, size), (120, 12, 22, 255))
    px = img.load()

    def organic_noise(x, y):
        return (
            math.sin(x * 0.43 + y * 0.79) * 0.42
            + math.sin(x * 0.19 - y * 0.51) * 0.36
            + math.cos((x * 0.31 + y * 0.23) * 1.7) * 0.22
        )

    # 1. Arterial Crimson Muscle + Dark Rc-Cell Veins (x: 0..64, y: 0..48)
    for y in range(0, 48):
        v = (y - 23.5) / 23.5
        cyl = 1.0 - 0.44 * (v * v)
        spec_band = math.exp(-((v + 0.24) / 0.19) ** 2)
        for x in range(0, 64):
            n = organic_noise(x, y)
            # Branching dark obsidian Rc-vein network along X
            vein_y = math.sin(x * 0.21 + 0.7 * math.sin(x * 0.09)) * 0.48
            vein = math.exp(-((v - vein_y) / 0.095) ** 2)
            vein2 = math.exp(-((v + vein_y * 0.7 - 0.15) / 0.075) ** 2) * 0.75
            dark_vein = max(vein, vein2)

            r = (212.0 + 18.0 * n) * cyl
            g = (18.0 + 5.0 * n) * cyl
            b = (32.0 + 7.0 * n) * cyl

            # Dark obsidian-crimson Rc-veins (#18040A)
            r = r * (1.0 - 0.72 * dark_vein) + 22.0 * 0.72 * dark_vein
            g = g * (1.0 - 0.78 * dark_vein) + 4.0 * 0.78 * dark_vein
            b = b * (1.0 - 0.72 * dark_vein) + 12.0 * 0.72 * dark_vein

            # Wet scarlet specular highlight
            r += 54.0 * spec_band * (1.0 - 0.5 * dark_vein)
            g += 36.0 * spec_band * (1.0 - 0.6 * dark_vein)
            b += 42.0 * spec_band * (1.0 - 0.6 * dark_vein)
            px[x, y] = (_clamp8(r), _clamp8(g), _clamp8(b), 255)

    # 2. Imbricated Rinkaku Scales (x: 64..128, y: 0..48)
    for y in range(0, 48):
        v = (y - 23.5) / 23.5
        cyl = 1.0 - 0.42 * (v * v)
        row = y // 6
        vy = (y % 6) / 5.0
        for x in range(64, 128):
            lx = x - 64 + (5 if row % 2 else 0)
            ux = (lx % 10) / 9.0
            n = organic_noise(x, y)
            edge = 1.0 if (ux > 0.82 or vy > 0.80) else 0.0
            plate_dome = math.sin(ux * math.pi) * math.sin(vy * math.pi)
            # Obsidian-tinted armor scale center + glowing scarlet scale rim
            r = (145.0 + 78.0 * plate_dome + 14.0 * n) * cyl
            g = (12.0 + 18.0 * plate_dome) * cyl
            b = (24.0 + 22.0 * plate_dome) * cyl
            if edge > 0.5:
                r, g, b = 236.0 * cyl, 28.0 * cyl, 44.0 * cyl
            elif plate_dome < 0.22:
                r, g, b = 30.0, 5.0, 12.0
            px[x, y] = (_clamp8(r), _clamp8(g), _clamp8(b), 255)

    # 3. Lit Scarlet Dorsal Surface (x: 0..64, y: 48..88)
    for y in range(48, 88):
        v = ((y - 48) - 19.5) / 19.5
        cyl = 1.0 - 0.36 * (v * v)
        spec = math.exp(-(v / 0.24) ** 2)
        for x in range(0, 64):
            n = organic_noise(x, y)
            r = (224.0 + 16.0 * n) * cyl + 38.0 * spec
            g = (24.0 + 6.0 * n) * cyl + 44.0 * spec
            b = (38.0 + 7.0 * n) * cyl + 46.0 * spec
            px[x, y] = (_clamp8(r), _clamp8(g), _clamp8(b), 255)

    # 4. Deep Shadowed Coagulated Underside (x: 64..128, y: 48..88)
    for y in range(48, 88):
        v = ((y - 48) - 19.5) / 19.5
        cyl = 0.72 + 0.28 * (1.0 - v * v)
        for x in range(64, 128):
            n = organic_noise(x, y)
            r = (78.0 + 14.0 * n) * cyl
            g = (7.0 + 2.0 * n) * cyl
            b = (16.0 + 4.0 * n) * cyl
            px[x, y] = (_clamp8(r), _clamp8(g), _clamp8(b), 255)

    # 5. Obsidian-Black Dorsal Chitin Ridge + Glowing Crimson Edge (x: 0..64, y: 88..128)
    for y in range(88, 128):
        v = (y - 88) / 39.0
        au = abs(v - 0.5) * 2.0
        for x in range(0, 64):
            n = organic_noise(x, y)
            # Jet-black obsidian core (#15050B) transitioning to glowing ruby edge (#E61E38)
            rim = max(0.0, (au - 0.56) / 0.44) ** 1.25
            spec = math.exp(-((v - 0.44) / 0.12) ** 2) * 52.0
            r = 20.0 * (1.0 - rim) + 232.0 * rim + spec + n * 4.0
            g = 6.0 * (1.0 - rim) + 24.0 * rim + spec * 0.65
            b = 12.0 * (1.0 - rim) + 42.0 * rim + spec * 0.80
            px[x, y] = (_clamp8(r), _clamp8(g), _clamp8(b), 255)

    # 6. Pulsing Kakuhou Rc-Cell Eruption Core (x: 64..128, y: 88..128)
    for y in range(88, 128):
        dy = (y - 107.5) / 19.5
        for x in range(64, 128):
            dx = (x - 95.5) / 31.5
            rad = math.hypot(dx, dy)
            n = organic_noise(x, y)
            glow = max(0.0, 1.0 - rad * 0.92) ** 1.5
            vein = abs(math.sin(math.atan2(dy, dx) * 5.0 + rad * 4.5))
            vein_glow = glow * (0.45 + 0.55 * (vein ** 2.2))
            r = 28.0 + 225.0 * vein_glow + n * 8.0
            g = 6.0 + 48.0 * (vein_glow ** 1.6)
            b = 14.0 + 42.0 * vein_glow
            px[x, y] = (_clamp8(r), _clamp8(g), _clamp8(b), 255)

    return img


# ---------------------------------------------------------------------------
# Crisp 32x32 Pixel-Art Menu Icon (kaneki_tentacles_icon.png)
# Four unmistakable crimson-obsidian Tokyo Ghoul Rinkaku tails erupting from one core
# ---------------------------------------------------------------------------
def build_menu_icon() -> Image.Image:
    size = 32
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    px = img.load()

    arms = [
        # Upper left & right Rinkaku blades arching with organic anime S-curves
        [(15.5, 22.5), (13.0, 16.5), (7.5, 11.2), (4.0, 6.0), (5.8, 2.2)],
        [(16.5, 22.5), (19.0, 16.5), (24.5, 11.2), (28.0, 6.0), (26.2, 2.2)],
        # Lower left & right Rinkaku blades sweeping wide in low S-curves
        [(15.5, 23.8), (10.5, 26.2), (5.2, 24.0), (2.4, 18.8), (3.6, 14.5)],
        [(16.5, 23.8), (21.5, 26.2), (26.8, 24.0), (29.6, 18.8), (28.4, 14.5)],
    ]

    for arm in arms:
        pts = spline(arm, per_span=18)
        total = max(1, len(pts) - 1)
        for idx, (cx, cy, *_) in enumerate([(p[0], p[1]) for p in pts]):
            t = idx / total
            rad = (2.25 * (1.0 - 0.72 * (t ** 1.35))) if t > 0.10 else (1.40 + 8.0 * t)
            r_int = int(math.ceil(rad + 1.0))
            for yy in range(max(1, int(cy) - r_int), min(size - 1, int(cy) + r_int + 1)):
                for xx in range(max(1, int(cx) - r_int), min(size - 1, int(cx) + r_int + 1)):
                    d = math.hypot(xx - cx, yy - cy)
                    if d <= rad:
                        if t > 0.86:
                            px[xx, yy] = (38, 6, 16, 255) if d > rad * 0.45 else (255, 58, 76, 255)
                        elif d > rad - 0.68:
                            px[xx, yy] = (108, 10, 24, 255)
                        elif d < rad * 0.42:
                            px[xx, yy] = (40, 6, 16, 255) if idx % 8 == 0 else (255, 72, 88, 255)
                        else:
                            px[xx, yy] = (224, 24, 44, 255)

    # Central glowing Kakuhou core at (16, 23.2)
    for yy in range(18, 29):
        for xx in range(12, 21):
            d = math.hypot((xx - 16.0) / 3.3, (yy - 23.2) / 3.5)
            if d <= 1.0:
                if d < 0.42:
                    px[xx, yy] = (255, 112, 98, 255)
                elif d < 0.76:
                    px[xx, yy] = (204, 22, 40, 255)
                else:
                    px[xx, yy] = (28, 6, 14, 255)

    # Clean 1px obsidian silhouette outline
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    opx = out.load()
    for y in range(size):
        for x in range(size):
            if px[x, y][3] > 0:
                opx[x, y] = px[x, y]
                continue
            if any(0 <= x + dx < size and 0 <= y + dy < size and px[x + dx, y + dy][3] > 0
                   for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                opx[x, y] = (24, 4, 10, 240)
    return out


# ---------------------------------------------------------------------------
# Living Anime Rinkaku Animation ('idle', 3.6 s seamless loop, zero-mean deltas!)
# ---------------------------------------------------------------------------
def motion(depth: int, count: int):
    t = depth / max(1, count - 1)
    return 1.15 + 5.8 * (t ** 1.55), 0.58 * t


def build_animation(tendrils):
    animators = {}
    for index, tendril in enumerate(tendrils):
        phase = index * math.pi / 2.15
        count = len(tendril['bones'])
        for depth, bone in enumerate(tendril['bones']):
            gain, lag = motion(depth, count)
            keys = []
            for step in range(ANIM_FRAMES):
                t = ANIM_LENGTH * step / (ANIM_FRAMES - 1)
                w = 2.0 * math.pi * t / ANIM_LENGTH
                # Zero-mean harmonic wave along each Rinkaku tentacle
                up = gain * (
                    0.84 * math.sin(w + phase - lag * 5.8)
                    + 0.16 * math.sin(2.0 * w + phase * 1.6 - lag * 8.5)
                )
                sweep = gain * 0.76 * (
                    0.85 * math.cos(w + phase * 1.3 - lag * 4.4)
                    + 0.15 * math.sin(2.0 * w - phase + lag * 6.0)
                )
                twist = gain * 0.28 * math.sin(w + phase - lag * 4.0)
                keys.append({
                    'channel': 'rotation',
                    'data_points': [{
                        'x': str(round(twist, 3)),
                        'y': str(round(sweep, 3)),
                        'z': str(round(up, 3)),
                    }],
                    'uuid': uid(f'key:{bone["name"]}:{step}'),
                    'time': round(t, 4),
                    'color': -1,
                    'interpolation': 'linear',
                })
            keys[-1]['data_points'] = [dict(point) for point in keys[0]['data_points']]
            animators[uid(f'bone:{bone["name"]}')] = {
                'name': bone['name'],
                'type': 'bone',
                'keyframes': keys,
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


def build_model():
    texture = build_texture()
    raw = io.BytesIO()
    texture.save(raw, format='PNG', optimize=True)
    texture_entry = {
        'path': '', 'name': f'{MODEL}.png', 'folder': '', 'namespace': '', 'id': '0',
        'width': texture.width, 'height': texture.height,
        'uv_width': 16, 'uv_height': 16,
        'particle': False, 'use_as_default': False, 'layers_enabled': False,
        'render_mode': 'default', 'render_sides': 'auto', 'frame_time': 1,
        'frame_order_type': 'loop', 'frame_interpolate': False,
        'visible': True, 'internal': True, 'saved': False,
        'uuid': uid('texture'),
        'source': 'data:image/png;base64,' + base64.b64encode(raw.getvalue()).decode('ascii'),
    }

    elements, bones = [], []
    for tendril in TENDRILS:
        chain = []
        solved_bones = blade_bones(tendril)
        for bone in solved_bones:
            cubes = build_elements(bone)
            chain.append({
                'name': bone['name'],
                'origin': bone['origin'],
                'rotation': bone['rotation'],
                'color': 0,
                'uuid': uid(f'bone:{bone["name"]}'),
                'export': True, 'mirror_uv': False, 'isOpen': True,
                'locked': False, 'visibility': True, 'autouv': 0,
                'children': [c['uuid'] for c in cubes],
            })
            elements.extend(cubes)
        for outer, inner in zip(chain, chain[1:]):
            outer['children'].append(inner)
        bones.append(chain[0])
        tendril['bones'] = [dict(bone) for bone in solved_bones]

    knot_cubes = knot_elements()
    elements.extend(knot_cubes)
    knot_bone = {
        'name': KNOT['name'],
        'origin': list(KNOT['origin']),
        'rotation': [0.0, 0.0, 0.0],
        'color': 0,
        'uuid': uid('bone:knot'),
        'export': True, 'mirror_uv': False, 'isOpen': True,
        'locked': False, 'visibility': True, 'autouv': 0,
        'children': [c['uuid'] for c in knot_cubes],
    }
    root = {
        'name': 'tentacles_root',
        'origin': list(ROOT_ORIGIN),
        'rotation': [0.0, 0.0, 0.0],
        'color': 0,
        'uuid': uid('bone:root'),
        'export': True, 'mirror_uv': False, 'isOpen': True,
        'locked': False, 'visibility': True, 'autouv': 0,
        'children': [knot_bone] + bones,
    }
    return {
        'meta': {'format_version': '4.10', 'model_format': 'free', 'box_uv': False},
        'name': MODEL,
        'model_identifier': MODEL,
        'visible_box': [5, 5, 1],
        'resolution': {'width': 16, 'height': 16},
        'elements': elements,
        'outliner': [root],
        'textures': [texture_entry],
        'animations': [build_animation(TENDRILS)],
    }, texture


# ---------------------------------------------------------------------------
# Report & Multi-Angle Textured Preview Renderer
# ---------------------------------------------------------------------------
def report():
    for spec in TENDRILS:
        path = blade_path(spec)
        xs = [p[0] for p in path]
        widest = max(range(len(path)), key=lambda i: abs(xs[i]))
        tip, before = path[-1], path[-2]
        radial = (tip[0] - before[0]) * math.copysign(1.0, tip[0])
        print(f'{spec["name"]:12s} bones={len(path) - 1:2d} '
              f'tip=({tip[0]:6.1f},{tip[1]:5.1f},{tip[2]:5.1f}) '
              f'widest x={xs[widest]:6.1f} inward={abs(tip[0]) - abs(xs[widest]):+5.2f} '
              f'tipRadial={radial:+5.2f}')
    lo = [min(p[i] for s in TENDRILS for p in blade_path(s)) for i in range(3)]
    hi = [max(p[i] for s in TENDRILS for p in blade_path(s)) for i in range(3)]
    print('bbox', [round(v, 1) for v in lo], [round(v, 1) for v in hi],
          'size', [round(hi[i] - lo[i], 1) for i in range(3)])


def bone_chains(model):
    chains = {}

    def walk(node, chain):
        for bone in node:
            if isinstance(bone, str):
                continue
            own = chain + [(tuple(bone['origin']), list(bone['rotation']))]
            for child in bone.get('children', []):
                if isinstance(child, str):
                    chains[child] = own
            walk([c for c in bone.get('children', []) if isinstance(c, dict)], own)

    walk(model['outliner'], [])
    return chains


def _rotation(axis, angle):
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    if axis == 0:
        return ((1, 0, 0), (0, c, -s), (0, s, c))
    if axis == 1:
        return ((c, 0, s), (0, 1, 0), (-s, 0, c))
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def _apply(matrix, vec):
    return tuple(sum(matrix[i][k] * vec[k] for k in range(3)) for i in range(3))


def _font(size):
    try:
        from PIL import ImageFont
        return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', size)
    except Exception:
        from PIL import ImageFont
        return ImageFont.load_default()


LIGHT = _norm((-0.42, 0.72, 0.55))


def preview(model, out_path, scale=8.0, size=(620, 460), title='', yaw=-26.0, pitch=8.0,
            texture=None, body=False, centre=(0.0, 27.0, 8.0), perspective=0.0,
            shade=0.85, head=False):
    img = Image.new('RGB', size, (18, 20, 30))
    draw = ImageDraw.Draw(img)
    cy_, sy_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp_, sp_ = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    def rotate(x, y, z):
        xr = x * cy_ - z * sy_
        zr = x * sy_ + z * cy_
        yr = y * cp_ - zr * sp_
        zr = y * sp_ + zr * cp_
        return -xr, yr, zr

    def view(x, y, z):
        return rotate(x - centre[0], y - centre[1], z - centre[2])

    def project(x, y, z):
        xr, yr, zr = view(x, y, z)
        factor = scale
        if perspective:
            factor = scale * perspective / max(1.0, perspective - zr)
        return (size[0] / 2 + xr * factor, size[1] / 2 - yr * factor), zr

    chains = bone_chains(model)
    quads = []
    for element in model['elements']:
        origin = element['origin']
        chain = chains.get(element['uuid'], [])
        corner = {}
        for i in (0, 1):
            for j in (0, 1):
                for k in (0, 1):
                    point = (element['from'][0] if i == 0 else element['to'][0],
                             element['from'][1] if j == 0 else element['to'][1],
                             element['from'][2] if k == 0 else element['to'][2])
                    for bone_origin, euler in reversed(chain):
                        for axis_index in range(3):
                            if euler[axis_index]:
                                bone_matrix = _rotation(axis_index, euler[axis_index])
                                rel = tuple(point[n] - bone_origin[n] for n in range(3))
                                point = tuple(bone_origin[n] + _apply(bone_matrix, rel)[n]
                                              for n in range(3))
                    corner[(i, j, k)] = point
        sides = [
            ([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], (0, 0, -1), 'north'),
            ([(0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1)], (0, 0, 1), 'south'),
            ([(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)], (0, 1, 0), 'up'),
            ([(0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)], (0, -1, 0), 'down'),
            ([(1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)], (1, 0, 0), 'east'),
            ([(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)], (-1, 0, 0), 'west'),
        ]
        for keys, normal, face_name in sides:
            pts = [corner[key] for key in keys]
            world = normal
            for _, euler in reversed(chain):
                for axis_index in range(3):
                    if euler[axis_index]:
                        world = _apply(_rotation(axis_index, euler[axis_index]), world)
            quads.append((pts, world, element['faces'][face_name]['uv'], None))

    if body or head:
        depth = 4 if head else 2
        proxy = [
            ((-4, 0, -2), (4, 12, 2), (50, 56, 74)),
            ((-4, 12, -2), (4, 24, 2), (68, 76, 98)),
            ((-8, 12, -2), (-4, 24, 2), (58, 66, 86)),
            ((4, 12, -2), (8, 24, 2), (58, 66, 86)),
            ((-4, 24, -depth), (4, 32, depth), (86, 94, 118)),
        ]
        for low, high, colour in proxy:
            for keys, normal in (
                (((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)), (0, 0, -1)),
                (((0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1)), (0, 0, 1)),
                (((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)), (0, 1, 0)),
                (((1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)), (1, 0, 0)),
                (((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)), (-1, 0, 0)),
            ):
                pts = [(low[0] + (high[0] - low[0]) * ix,
                        low[1] + (high[1] - low[1]) * iy,
                        low[2] + (high[2] - low[2]) * iz) for ix, iy, iz in keys]
                quads.append((pts, normal, None, colour))

    rendered = []
    for pts, normal, uv, flat in quads:
        projected = [project(*pt) for pt in pts]
        depth_val = sum(d for _, d in projected) / len(projected)
        _, _, nz = rotate(*normal)
        rendered.append((depth_val, [q for q, _ in projected], nz, uv, flat, normal))
    rendered.sort(key=lambda item: item[0])

    pixels = texture.convert('RGB').load() if texture is not None else None
    tw = texture.width if texture is not None else 1
    th = texture.height if texture is not None else 1

    for _, poly, nz, uv, flat, normal in rendered:
        if nz <= 0:
            continue
        lambert = max(0.0, sum(normal[i] * LIGHT[i] for i in range(3)))
        factor = 1.0 - shade + shade * (0.45 + 0.78 * lambert)
        if flat is not None or pixels is None:
            colour = flat if flat is not None else (196, 26, 34)
            colour = tuple(_clamp8(c * factor) for c in colour)
            draw.polygon(poly, fill=colour)
            continue
        u0, v0, u1, v1 = uv
        steps = 4
        c00, c10, c11, c01 = poly[0], poly[1], poly[2], poly[3]

        def bilerp(a, b):
            top = (c00[0] + (c10[0] - c00[0]) * a, c00[1] + (c10[1] - c00[1]) * a)
            bottom = (c01[0] + (c11[0] - c01[0]) * a, c01[1] + (c11[1] - c01[1]) * a)
            return (top[0] + (bottom[0] - top[0]) * b, top[1] + (bottom[1] - top[1]) * b)

        for su in range(steps):
            for sv in range(steps):
                a0, a1 = su / steps, (su + 1) / steps
                b0, b1 = sv / steps, (sv + 1) / steps
                cell = [bilerp(a0, b0), bilerp(a1, b0), bilerp(a1, b1), bilerp(a0, b1)]
                tx = int(((u0 + (u1 - u0) * (a0 + a1) * 0.5) / 16.0) * (tw - 1))
                ty = int(((v0 + (v1 - v0) * (b0 + b1) * 0.5) / 16.0) * (th - 1))
                tx = max(0, min(tw - 1, tx))
                ty = max(0, min(th - 1, ty))
                c = pixels[tx, ty]
                colour = tuple(_clamp8(c[k] * factor) for k in range(3))
                draw.polygon(cell, fill=colour)

    font = _font(17)
    draw.rectangle([8, 8, size[0] - 8, 36], fill=(12, 14, 22))
    draw.text((14, 12), title, fill=(248, 190, 251), font=font)
    img.save(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', default=str(HERE))
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    model, texture = build_model()
    (out / f'{MODEL}.bbmodel').write_text(json.dumps(model, separators=(',', ':')), encoding='utf-8')
    texture.save(out / f'{MODEL}.png', format='PNG', optimize=True)
    tex_dest = out / 'assets' / 'modelengine' / 'textures' / 'entity' / 'models'
    tex_dest.mkdir(parents=True, exist_ok=True)
    texture.save(tex_dest / f'{MODEL}.png', format='PNG', optimize=True)

    icon_dir = out / 'assets' / 'reallyworld'
    (icon_dir / 'items').mkdir(parents=True, exist_ok=True)
    (icon_dir / 'models' / 'item' / 'freak').mkdir(parents=True, exist_ok=True)
    (icon_dir / 'textures' / 'item' / 'freak').mkdir(parents=True, exist_ok=True)
    icon_img = build_menu_icon()
    icon_img.save(icon_dir / 'textures' / 'item' / 'freak' / 'kaneki_tentacles_icon.png', format='PNG', optimize=True)
    (icon_dir / 'models' / 'item' / 'freak' / 'kaneki_tentacles_icon.json').write_text(
        json.dumps({
            'parent': 'minecraft:item/generated',
            'textures': {'layer0': 'reallyworld:item/freak/kaneki_tentacles_icon'},
        }, indent=2) + '\n',
        encoding='utf-8',
    )
    (icon_dir / 'items' / 'kaneki_tentacles_icon.json').write_text(
        json.dumps({
            'model': {
                'type': 'minecraft:model',
                'model': 'reallyworld:item/freak/kaneki_tentacles_icon',
            }
        }, indent=2) + '\n',
        encoding='utf-8',
    )

    if args.report:
        report()
    if args.preview:
        panel = (620, 680)
        centre = (0.0, 18.0, 2.0)
        preview(model, out / 'tentacles_back.png', title='КАГУНЕ КАНЕКИ: Вид со спины',
                yaw=0, pitch=6, scale=12.5, size=panel, texture=texture, body=True,
                centre=centre, perspective=240.0, head=True)
        preview(model, out / 'tentacles_front.png', title='КАГУНЕ КАНЕКИ: Вид спереди',
                yaw=180, pitch=6, scale=12.5, size=panel, texture=texture, body=True,
                centre=centre, perspective=240.0, head=True)
        preview(model, out / 'tentacles_angle.png', title='КАГУНЕ КАНЕКИ: Вид 3/4 (Ринкаку)',
                yaw=38, pitch=14, scale=12.0, size=panel, texture=texture, body=True,
                centre=centre, perspective=240.0, head=True)
        preview(model, out / 'tentacles_side.png', title='КАГУНЕ КАНЕКИ: Профиль и изгиб',
                yaw=90, pitch=8, scale=12.5, size=panel, texture=texture, body=True,
                centre=centre, perspective=240.0, head=True)
        preview(model, out / 'tentacles_top.png', title='КАГУНЕ КАНЕКИ: Вид сверху (4 хвоста)',
                yaw=0, pitch=84, scale=12.0, size=panel, texture=texture, body=True,
                centre=centre, perspective=260.0, head=True)
        names = ('tentacles_back', 'tentacles_front', 'tentacles_angle', 'tentacles_side', 'tentacles_top')
        combo = Image.new('RGB', (panel[0] * len(names), panel[1]), (18, 20, 30))
        for index, name in enumerate(names):
            combo.paste(Image.open(out / f'{name}.png'), (panel[0] * index, 0))
            (out / f'{name}.png').unlink(missing_ok=True)
        combo.save(out / 'tentacles_preview.png')
    rotated_count = sum(1 for e in model['elements'] if any(abs(v) > 1e-9 for v in e['rotation']))
    print(f'Built {MODEL}.bbmodel: {len(model["elements"])} cubes (rotated={rotated_count}), '
          f'texture {texture.width}x{texture.height}')


if __name__ == '__main__':
    main()
