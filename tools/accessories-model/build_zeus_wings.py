#!/usr/bin/env python3
"""Procedurally builds the 3D Zeus Lightning Wings (`elytrix_zeus_wings`), its 32x32
pixel-art menu icon (`reallyworld:zeus_wings_icon`) and a multi-angle verification preview.

100% pure procedural Python + Pillow + NumPy — zero AI generation.

  1. Visual design (faithful 3D translation of "крылья, состоящие из молнии"):
       - Two great arcing wing arms forged from ONE continuous jagged lightning bolt
         each (`wing_r` / `wing_l`): they sprout from the shoulder blades, sweep up
         over the shoulders and curve down to a lowered tip at `X = +-22.2`.
       - 10 primary lightning feathers (`feather_r1..r5`, `feather_l1..l5`): each one
         is an independently animated zig-zag bolt hanging from the arm, with its own
         razor fork branch.  Nothing here is a soft plume — every "feather" is a bolt.
       - A small dark thunder-cloud (`zeus_root`) boiling between the shoulder blades,
         two bright arcs stabbing from the cloud into the shoulders, and two crackling
         spark clusters (`spark_r`, `spark_l`) that pulse and tumble.
       - Palette: electric cyan-white core, electric blue body, deep thunder-indigo
         bevel, dark storm slate cloud, warm gold sparks.
  2. Motion (seamless 4.8 s loop @ 20 TPS = 96 ticks, 64 keyframes):
       - The wings beat gently (`+-8 deg` flap, `+3 deg` double-time shudder, `+-3.5 deg`
         sweep) with a constant high-frequency `+-0.9 deg` electric crackle jitter, so
         the bolts never sit still.
       - Every feather flutters on its own phase and surges `+18%` on its own
         discharge beat — the whole wing "breathes" lightning instead of flapping cloth.
       - The root hovers `+-0.14` BB, the spark clusters pulse `0.55 -> 1.20` and tumble
         a full turn per loop.
  3. Engine safety (the rules that made the earlier models reliable):
       - **Not a single cube is rotated.**  Every jag is an axis-aligned L-step, exactly
         like `elytrix_kaneki_tentacles` / `elytrix_centipede`, so ModelEngine 4.1.0's
         `RotationSolver` is never invoked (it crashes on rotated cubes).
       - Every bone's geometry stays inside `+-24` BB of its own pivot, so ModelEngine's
         `scaleToFit()` never has to rescale a bone.
       - `16.0` BB units = `1.0` block: feet `0.00`, waist `11.25`, neck/shoulders `22.50`,
         bare skull top `30.00`, `+Z` is the player's back.
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
MODEL = 'elytrix_zeus_wings'
ICON = 'zeus_wings_icon'

IDLE_LEN = 4.8       # 96 ticks @ 20 TPS — seamless beat + flutter + discharge loop
IDLE_STEPS = 64

# Shoulder-blade pivot: upper back, just under the neck, on the back surface (+Z).
ROOT_ORIG = [0.0, 22.0, 1.9]


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f'elytrix.zeus_wings.v1:{tag}'))


# ---------------------------------------------------------------------------
# 1. Electric-bolt texture (128x128, UV grid 16x16 -> 32 px tiles = 4 UV units)
# ---------------------------------------------------------------------------
UV_BOLT_CORE = (0.25, 0.25, 3.75, 3.75)      # near-white electric core, cyan streaks
UV_BOLT_MID = (4.25, 0.25, 7.75, 3.75)       # electric blue body
UV_BOLT_EDGE = (8.25, 0.25, 11.75, 3.75)     # deep thunder-indigo bevel
UV_STORM_CLOUD = (12.25, 0.25, 15.75, 3.75)  # dark storm slate cloud
UV_SPARK_GOLD = (0.25, 4.25, 3.75, 7.75)     # warm gold spark
UV_GLOW = (4.25, 4.25, 7.75, 7.75)           # pale cyan-white fork glow


def build_zeus_texture() -> Image.Image:
    """128x128 pixel-art texture: bolt core / body / bevel, storm cloud, gold spark."""
    arr = np.zeros((128, 128, 4), dtype=np.uint8)

    def noise(x: int, y: int, a: int, b: int, m: int) -> int:
        return int(abs(math.sin(x * a + y * b) * 43758.5453) % m)

    # --- Tile (0,0): near-white electric core with horizontal plasma streaks ---
    for py in range(32):
        for px in range(32):
            streak = noise(px, py, 0.9, 7.3, 11)
            edge = min(px, py, 31 - px, 31 - py)
            if py % 6 in (0, 1):
                col = (255, 255, 255, 255)
            elif streak == 0:
                col = (168, 236, 255, 255)
            elif edge == 0:
                col = (198, 242, 255, 255)
            else:
                d = 8 if ((px + py) % 2 == 0) else 0
                col = (226 + d, 250, 255, 255)
            arr[py, px] = col

    # --- Tile (1,0): electric blue body ---
    for py in range(32):
        for px in range(32):
            streak = noise(px, py, 3.1, 5.7, 9)
            edge = min(px, py, 31 - px, 31 - py)
            if py % 7 in (0, 1):
                col = (127, 208, 255, 255)
            elif streak == 0:
                col = (96, 186, 250, 255)
            elif edge == 0:
                col = (27, 111, 214, 255)
            elif edge == 1:
                col = (58, 152, 240, 255)
            else:
                d = 10 if ((px + py) % 2 == 0) else -8
                col = (63 + d, 169 + d // 2, 255, 255)
            arr[py, 32 + px] = col

    # --- Tile (2,0): deep thunder-indigo bevel ---
    for py in range(32):
        for px in range(32):
            crack = noise(px, py, 5.3, 2.9, 13)
            edge = min(px, py, 31 - px, 31 - py)
            if crack == 0:
                col = (75, 73, 200, 255)
            elif edge == 0:
                col = (20, 20, 63, 255)
            elif edge == 1:
                col = (43, 42, 122, 255)
            else:
                d = 6 if ((px + py) % 2 == 0) else -5
                col = (43 + d, 42 + d, 122 + d, 255)
            arr[py, 64 + px] = col

    # --- Tile (3,0): dark storm slate cloud ---
    for py in range(32):
        for px in range(32):
            blob = noise(px // 3, py // 3, 12.9898, 78.233, 7)
            edge = min(px, py, 31 - px, 31 - py)
            if edge == 0:
                col = (24, 29, 44, 255)
            elif blob == 0:
                col = (92, 106, 142, 255)
            elif blob <= 2:
                col = (60, 70, 97, 255)
            else:
                d = 5 if ((px + py) % 2 == 0) else -4
                col = (60 + d, 70 + d, 97 + d, 255)
            arr[py, 96 + px] = col

    # --- Tile (0,1): warm gold spark ---
    for py in range(32):
        for px in range(32):
            ray = noise(px, py, 8.1, 1.7, 5)
            edge = min(px, py, 31 - px, 31 - py)
            if edge == 0:
                col = (196, 138, 24, 255)
            elif ray == 0:
                col = (255, 210, 74, 255)
            else:
                d = 9 if ((px + py) % 2 == 0) else 0
                col = (255, 246 - d, 200 - d * 2, 255)
            arr[32 + py, px] = col

    # --- Tile (1,1): pale cyan-white fork glow ---
    for py in range(32):
        for px in range(32):
            streak = noise(px, py, 2.2, 9.1, 8)
            edge = min(px, py, 31 - px, 31 - py)
            if py % 5 in (0, 1):
                col = (255, 255, 255, 255)
            elif streak == 0:
                col = (159, 233, 255, 255)
            elif edge == 0:
                col = (176, 226, 250, 255)
            else:
                d = 7 if ((px + py) % 2 == 0) else 0
                col = (223 + d, 249, 255, 255)
            arr[32 + py, 32 + px] = col

    return Image.fromarray(arr, 'RGBA')


# ---------------------------------------------------------------------------
# 2. Cube helpers (NO cube is ever rotated — ModelEngine 4.1.0 safe)
# ---------------------------------------------------------------------------
def _faces(default_uv: tuple, **overrides) -> dict:
    out = {}
    for side in ('north', 'east', 'south', 'west', 'up', 'down'):
        out[side] = {'uv': list(overrides.get(side, default_uv)), 'texture': 0}
    return out


def _cube(name: str, p_from: list, p_to: list, origin: list, faces: dict) -> dict:
    low = [round(min(p_from[i], p_to[i]), 4) for i in range(3)]
    high = [round(max(p_from[i], p_to[i]), 4) for i in range(3)]
    return {
        'name': name,
        'box_uv': False,
        'rescale': False,
        'locked': False,
        'light_emission': 15,
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
        'shade': False,
    }


def _mirror(cube: dict, suffix: str = '_l') -> dict:
    """Mirrors a cube across X and gives it a fresh name/uuid (right wing -> left wing)."""
    import copy
    out = copy.deepcopy(cube)
    out['from'] = [round(-cube['to'][0], 4), cube['from'][1], cube['from'][2]]
    out['to'] = [round(-cube['from'][0], 4), cube['to'][1], cube['to'][2]]
    out['name'] = cube['name'].replace('_r', suffix).replace('right', 'left') + suffix
    out['uuid'] = uid(f"cube:{out['name']}")
    return out


def _jag(i: int, seed: float) -> float:
    """Deterministic alternating zig-zag amplitude in [-1.2, -0.45] u [0.45, 1.2]."""
    v = abs(math.sin((i * 12.9898) + (seed * 78.233)) * 43758.5453) % 1.0
    amp = 0.45 + 0.75 * v
    return -amp if (i % 2 == 0) else amp


def jag_chain(prefix: str, points: list, amp: float, seed: float,
              hw: float, hd: float, faces: dict, origin: list, taper: float = 0.5) -> list:
    """One jagged lightning bolt through `points` (list of (x, y, z)).

    Interior nodes are pushed off the polyline by an alternating perpendicular kick,
    and every segment is drawn as an axis-aligned L-step (a horizontal bar then a
    vertical bar).  The chain therefore reads as a hard zig-zag ribbon while
    **not a single cube carries a rotation** — the rule that keeps ModelEngine 4.1.0's
    `RotationSolver` (which crashes on rotated cubes) out of the pipeline.
    """
    pts = []
    n = len(points)
    for i, (px, py, pz) in enumerate(points):
        if i == 0 or i == n - 1:
            pts.append((float(px), float(py), float(pz)))
            continue
        # perpendicular of the average incoming/outgoing direction
        ax, ay = points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]
        bx, by = points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]
        la, lb = math.hypot(ax, ay) or 1.0, math.hypot(bx, by) or 1.0
        nx, ny = -(ay / la + by / lb), (ax / la + bx / lb)
        ln = math.hypot(nx, ny) or 1.0
        nx, ny = nx / ln, ny / ln
        off = amp * _jag(i, seed)
        pts.append((px + nx * off, py + ny * off, float(pz)))

    cubes = []
    segs = len(pts) - 1
    for i in range(segs):
        x0, y0, za = pts[i]
        x1, y1, zb = pts[i + 1]
        h = hw * (1.0 - taper * (i / max(1, segs - 1)))
        zlo, zhi = min(za, zb) - hd, max(za, zb) + hd
        cubes.append(_cube(
            f'{prefix}_h{i:02d}',
            [min(x0, x1) - h, y0 - h, zlo],
            [max(x0, x1) + h, y0 + h, zhi],
            origin, faces))
        cubes.append(_cube(
            f'{prefix}_v{i:02d}',
            [x1 - h, min(y0, y1) - h, zlo],
            [x1 + h, max(y0, y1) + h, zhi],
            origin, faces))
    return cubes


def bolt_cubes(prefix: str, p0: tuple, p1: tuple, z0: float, z1: float,
               hw: float, hd: float, steps: int, amp: float, seed: float,
               faces: dict, origin: list, taper: float = 0.5) -> list:
    """Straight jagged bolt from `p0` to `p1` (XY plane), drifting `z0` -> `z1`."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        pts.append((p0[0] + (p1[0] - p0[0]) * t,
                    p0[1] + (p1[1] - p0[1]) * t,
                    z0 + (z1 - z0) * t))
    return jag_chain(prefix, pts, amp, seed, hw, hd, faces, origin, taper)


def mirror_all(cubes: list, suffix: str = '_l') -> list:
    return [_mirror(c, suffix) for c in cubes]


# ---------------------------------------------------------------------------
# 3. Exact wing geometry (right wing authored in +X; the left one is mirrored)
# ---------------------------------------------------------------------------
# Wing arm: sprouts at the shoulder blade, arcs up over the shoulder and then
# sweeps down to a lowered tip — a classic great-wing silhouette in pure lightning.
ARM_PATH = [
    (1.0, 22.5), (3.6, 23.9), (6.4, 25.1), (9.4, 25.8), (12.4, 25.9),
    (15.2, 25.2), (17.8, 23.7), (20.2, 21.8), (22.2, 19.6),
]
ARM_Z0, ARM_Z1 = 2.05, 1.95

# Five primary bolts per wing: (attach point, tip point, half width, half depth, steps, jag, seed)
FEATHERS = [
    ((4.4, 24.5), (5.6, 17.6), 0.28, 0.25, 5, 0.62, 1.7),
    ((8.2, 25.6), (10.4, 15.2), 0.31, 0.27, 6, 0.72, 3.1),
    ((12.2, 25.9), (15.4, 13.4), 0.33, 0.28, 7, 0.80, 5.9),
    ((16.2, 24.6), (20.2, 12.6), 0.31, 0.27, 7, 0.76, 8.3),
    ((19.8, 21.8), (23.6, 13.8), 0.30, 0.26, 6, 0.68, 11.4),
]
# Razor forks branch off the 2nd and 4th primaries.
FORKS = {
    1: ((9.6, 20.4), (13.4, 18.6), 2),
    3: ((18.4, 18.2), (22.4, 17.0), 2),
}
# Spark clusters hover just above each shoulder blade.
SPARKS = [
    (2.6, 24.4, 2.5), (-2.6, 24.4, 2.5), (3.4, 21.6, 2.9), (-3.4, 21.6, 2.9),
]


def build_geometry(elements: list) -> dict:
    """Fills `elements` and returns {bone_name: [cube uuids]} plus bone pivots."""
    bolt_faces = _faces(UV_BOLT_MID, north=UV_BOLT_CORE, south=UV_BOLT_CORE,
                        up=UV_BOLT_MID, down=UV_BOLT_MID,
                        east=UV_BOLT_EDGE, west=UV_BOLT_EDGE)
    glow_faces = _faces(UV_GLOW, east=UV_BOLT_EDGE, west=UV_BOLT_EDGE)
    cloud_faces = _faces(UV_STORM_CLOUD)
    spark_faces = _faces(UV_SPARK_GOLD, east=UV_GLOW, west=UV_GLOW)

    def add(cube: dict) -> str:
        elements.append(cube)
        return cube['uuid']

    def add_many(cubes: list) -> list:
        return [add(c) for c in cubes]

    bones = {}

    # --- A) zeus_root: thunder cloud boiling between the shoulder blades + 2 arcs ---
    root_cubes = []
    cloud_blocks = [
        (-2.9, 22.5, 1.7, -0.9, 21.5, 3.0),
        (0.9, 22.5, 1.7, 2.9, 21.5, 3.0),
        (-1.9, 23.4, 1.4, 1.9, 22.2, 3.1),
        (-3.4, 21.9, 1.9, -1.7, 21.1, 2.7),
        (1.7, 21.9, 1.9, 3.4, 21.1, 2.7),
        (-0.7, 21.6, 1.5, 0.7, 20.7, 3.2),
    ]
    for i, (x0, y0, z0, x1, y1, z1) in enumerate(cloud_blocks):
        root_cubes.append(_cube(f'cloud_{i}', [x0, y0, z0], [x1, y1, z1],
                                ROOT_ORIG, cloud_faces))
    # two bright arcs stabbing from the cloud out into the shoulders
    arc_pts = [(-1.2, 23.4, 2.6), (-3.6, 23.0, 2.5), (-5.4, 21.9, 2.4), (-7.4, 21.2, 2.2)]
    root_cubes.extend(jag_chain('arc_r', arc_pts, 0.55, 2.2, 0.16, 0.14,
                                glow_faces, ROOT_ORIG, taper=0.35))
    root_cubes.extend(mirror_all(jag_chain('arc_r', arc_pts, 0.55, 2.2, 0.16, 0.14,
                                           glow_faces, ROOT_ORIG, taper=0.35)))
    bones['zeus_root'] = add_many(root_cubes)

    # --- B) wing_r / wing_l: ONE continuous jagged arm bolt arcing over the shoulder ---
    arm_pts = [(x, y, ARM_Z0 + (ARM_Z1 - ARM_Z0) * (i / (len(ARM_PATH) - 1)))
               for i, (x, y) in enumerate(ARM_PATH)]
    arm_r = jag_chain('arm_r', arm_pts, 0.52, 0.7, 0.28, 0.24,
                      bolt_faces, ROOT_ORIG, taper=0.35)
    bones['wing_r'] = add_many(arm_r)
    bones['wing_l'] = add_many(mirror_all(arm_r))

    # --- C) 10 primary lightning feathers (+ 4 razor forks) ---
    for k, (attach, tip, hw, hd, steps, amp, seed) in enumerate(FEATHERS):
        idx = k + 1
        pivot = [round(float(attach[0]), 4), round(float(attach[1]), 4), 2.25]
        cubes = bolt_cubes(f'feather_r{idx}', attach, tip, 2.25, 2.65,
                           hw, hd, steps, amp, seed, bolt_faces, pivot, taper=0.55)
        if k in FORKS:
            (fx0, fy0), (fx1, fy1), fsteps = FORKS[k]
            cubes.extend(bolt_cubes(f'fork_r{idx}', (fx0, fy0), (fx1, fy1), 2.3, 2.5,
                                    0.20, 0.17, fsteps, 0.50, seed + 4.0,
                                    glow_faces, pivot, taper=0.6))
        bones[f'feather_r{idx}'] = add_many(cubes)
        left_pivot = [round(-pivot[0], 4), pivot[1], pivot[2]]
        left = []
        for c in cubes:
            m = _mirror(c)
            m['origin'] = left_pivot
            left.append(m)
        # re-stamp uuids after the pivot change so mirrored names stay unique
        for c in left:
            c['uuid'] = uid(f"cube:{c['name']}")
        bones[f'feather_l{idx}'] = add_many(left)

    # --- D) spark_r / spark_l: crackling clusters above each shoulder blade ---
    for side, (sx, sy, sz) in (('r', SPARKS[0]), ('l', SPARKS[1])):
        pivot = [round(float(sx), 4), round(float(sy), 4), round(float(sz), 4)]
        spark = []
        for m in range(4):
            ang = math.radians(m * 90.0)
            ox = 0.95 * math.sin(ang)
            oy = 0.95 * math.cos(ang)
            spark.append(_cube(
                f'spark_{side}_{m}',
                [pivot[0] + ox - 0.20, pivot[1] + oy - 0.20, pivot[2] - 0.20],
                [pivot[0] + ox + 0.20, pivot[1] + oy + 0.20, pivot[2] + 0.20],
                pivot, spark_faces))
        spark.append(_cube(f'spark_{side}_core',
                           [pivot[0] - 0.26, pivot[1] - 0.26, pivot[2] - 0.26],
                           [pivot[0] + 0.26, pivot[1] + 0.26, pivot[2] + 0.26],
                           pivot, spark_faces))
        bones[f'spark_{side}'] = add_many(spark)

    return bones


# ---------------------------------------------------------------------------
# 4. Seamless 4.8 s animation: wing beat, feather flutter, electric discharge
# ---------------------------------------------------------------------------
FEATHER_IDS = [f'feather_{s}{i}' for s in ('r', 'l') for i in range(1, 6)]
BONE_NAMES = ['zeus_root', 'wing_r', 'wing_l'] + FEATHER_IDS + ['spark_r', 'spark_l']


def eval_zeus_pose(u: float) -> dict:
    """Bone transforms at normalized phase u in [0, 1] (u = 1.0 closes the loop)."""
    tau = 2.0 * math.pi
    up = 0.0 if u >= 1.0 else u

    hover_y = 0.14 * math.sin(tau * up)

    # Wing beat: slow lift + a faster shudder + constant high-frequency crackle.
    flap = 8.0 * math.sin(tau * up) + 3.0 * math.sin(tau * 2.0 * up + 1.1)
    jitter = 0.9 * math.sin(tau * 8.0 * up + 0.6)
    flap_z = flap + jitter
    sweep_y = 3.5 * math.sin(tau * up + 0.35)

    pose = {
        'root_pos': [0.0, round(hover_y, 4), 0.0],
        'root_rot': [round(0.8 * math.sin(tau * up + 0.9), 4), 0.0,
                     round(1.1 * math.sin(tau * up), 4)],
        'wing_rot': {'wing_r': [0.0, round(sweep_y, 4), round(flap_z, 4)],
                     'wing_l': [0.0, round(-sweep_y, 4), round(-flap_z, 4)]},
        'feather_rot': {},
        'feather_scale': {},
        'spark_rot': {},
        'spark_scale': {},
    }

    for side, sign in (('r', 1.0), ('l', -1.0)):
        for i in range(1, 6):
            name = f'feather_{side}{i}'
            phase = 0.55 * (i - 1) + (0.0 if side == 'r' else math.pi)
            flutter = 5.5 * math.sin(tau * up + phase)
            crackle = 1.4 * math.sin(tau * 6.0 * up + i * 1.7)
            pose['feather_rot'][name] = [0.0, 0.0, round(sign * (flutter + crackle), 4)]
            # Discharge: a narrow +18% surge on this feather's own beat.
            beat = (up - (i - 1) * 0.17 - (0.0 if side == 'r' else 0.5)) % 1.0
            pulse = math.exp(-((beat - 0.5) / 0.16) ** 2)
            s = round(1.0 + 0.06 * math.sin(tau * up + phase) + 0.18 * pulse, 4)
            pose['feather_scale'][name] = [s, round(1.0 + 0.05 * pulse, 4), s]

        sname = f'spark_{side}'
        pose['spark_rot'][sname] = [0.0, round(360.0 * u, 4), 0.0]
        beat = (up - (0.0 if side == 'r' else 0.5)) % 1.0
        sp = 0.55 + 0.65 * (max(0.0, math.sin(tau * 3.0 * beat)) ** 3)
        pose['spark_scale'][sname] = [round(sp, 4), round(sp, 4), round(sp, 4)]

    return pose


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
    kfs = {b: [] for b in BONE_NAMES}
    for s in range(IDLE_STEPS + 1):
        u = s / IDLE_STEPS
        t = IDLE_LEN * u
        pose = eval_zeus_pose(u)

        kfs['zeus_root'].append(_vec_kf('position', 'idle:zeus_root', t, *pose['root_pos']))
        kfs['zeus_root'].append(_vec_kf('rotation', 'idle:zeus_root', t, *pose['root_rot']))

        for wing in ('wing_r', 'wing_l'):
            kfs[wing].append(_vec_kf('rotation', f'idle:{wing}', t, *pose['wing_rot'][wing]))

        for name in FEATHER_IDS:
            kfs[name].append(_vec_kf('rotation', f'idle:{name}', t, *pose['feather_rot'][name]))
            kfs[name].append(_vec_kf('scale', f'idle:{name}', t, *pose['feather_scale'][name]))

        for sname in ('spark_r', 'spark_l'):
            kfs[sname].append(_vec_kf('rotation', f'idle:{sname}', t, *pose['spark_rot'][sname]))
            kfs[sname].append(_vec_kf('scale', f'idle:{sname}', t, *pose['spark_scale'][sname]))

    return {uid(f'bone:{b}'): {'name': b, 'type': 'bone', 'keyframes': kfs[b]} for b in BONE_NAMES}


# ---------------------------------------------------------------------------
# 5. Blueprint builder (`elytrix_zeus_wings.bbmodel`)
# ---------------------------------------------------------------------------
def build_blueprint() -> tuple[dict, Image.Image]:
    texture = build_zeus_texture()
    raw = io.BytesIO()
    texture.save(raw, format='PNG', optimize=True)

    elements: list[dict] = []
    bones = build_geometry(elements)

    def bone(name: str, origin: list, children: list, is_open: bool = True) -> dict:
        return {
            'name': name,
            'origin': [round(float(v), 4) for v in origin],
            'rotation': [0.0, 0.0, 0.0],
            'color': 0,
            'uuid': uid(f'bone:{name}'),
            'export': True,
            'mirror_uv': False,
            'isOpen': is_open,
            'locked': False,
            'visibility': True,
            'autouv': 0,
            'children': children,
        }

    def feather_bone(name: str, origin: list, cubes: list) -> dict:
        return bone(name, origin, cubes, is_open=False)

    wing_r_children = list(bones['wing_r']) + [
        feather_bone(f'feather_r{i}', _feather_pivot(i), bones[f'feather_r{i}'])
        for i in range(1, 6)
    ]
    wing_l_children = list(bones['wing_l']) + [
        feather_bone(f'feather_l{i}', _mirror_pivot(_feather_pivot(i)), bones[f'feather_l{i}'])
        for i in range(1, 6)
    ]

    outliner = [
        bone('zeus_root', ROOT_ORIG, [
            *bones['zeus_root'],
            bone('wing_r', ROOT_ORIG, wing_r_children, is_open=False),
            bone('wing_l', ROOT_ORIG, wing_l_children, is_open=False),
            bone('spark_r', _spark_pivot('r'), bones['spark_r'], is_open=False),
            bone('spark_l', _spark_pivot('l'), bones['spark_l'], is_open=False),
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
        'meta': {'format_version': '4.10', 'model_format': 'free', 'box_uv': False},
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
            'path': '', 'name': f'{MODEL}.png', 'folder': '', 'namespace': '', 'id': '0',
            'width': 128, 'height': 128, 'uv_width': 16, 'uv_height': 16,
            'particle': False, 'use_as_default': False, 'layers_enabled': False,
            'sync_to_project': '', 'render_mode': 'default', 'render_sides': 'auto',
            'frame_time': 1, 'frame_order_type': 'loop', 'frame_order': '',
            'frame_interpolate': False, 'visible': True, 'internal': True, 'saved': True,
            'uuid': uid('tex:0'),
            'source': 'data:image/png;base64,' + base64.b64encode(raw.getvalue()).decode('ascii'),
        }],
        'animations': [{
            'uuid': uid('anim:idle'), 'name': 'idle', 'loop': 'loop', 'override': False,
            'length': IDLE_LEN, 'snapping': 20, 'selected': True, 'saved': True,
            'path': '', 'anim_time_update': '', 'blend_weight': '',
            'start_delay': '', 'loop_delay': '',
            'animators': build_idle_animators(),
        }],
    }
    return blueprint, texture


def _feather_pivot(i: int) -> list:
    attach = FEATHERS[i - 1][0]
    return [round(float(attach[0]), 4), round(float(attach[1]), 4), 2.25]


def _mirror_pivot(p: list) -> list:
    return [round(-p[0], 4), p[1], p[2]]


def _spark_pivot(side: str) -> list:
    sx, sy, sz = SPARKS[0] if side == 'r' else SPARKS[1]
    return [round(float(sx), 4), round(float(sy), 4), round(float(sz), 4)]


# ---------------------------------------------------------------------------
# 6. Hand-crafted 32x32 pixel-art menu icon (`reallyworld:zeus_wings_icon`)
# ---------------------------------------------------------------------------
def build_zeus_icon() -> Image.Image:
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    core = (236, 252, 255, 255)
    mid = (63, 169, 255, 255)
    dark = (43, 42, 122, 255)
    cloud = (60, 70, 97, 255)
    cloud_hi = (92, 106, 142, 255)

    def put(x: int, y: int, c: tuple) -> None:
        if 0 <= x < 32 and 0 <= y < 32:
            px[x, y] = c

    def jag_ray(x0: int, y0: int, x1: int, y1: int, steps: int = 4, amp: float = 2.0) -> None:
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        prev = None
        for i in range(steps + 1):
            t = i / steps
            off = 0.0 if i in (0, steps) else amp * (1.0 if i % 2 else -1.0) * (1.0 - 0.35 * t)
            cx = x0 + ux * length * t + nx * off
            cy = y0 + uy * length * t + ny * off
            cur = (int(round(cx)), int(round(cy)))
            if prev is not None:
                for k in range(0, 41):
                    tt = k / 40.0
                    qx = int(round(prev[0] + (cur[0] - prev[0]) * tt))
                    qy = int(round(prev[1] + (cur[1] - prev[1]) * tt))
                    put(qx, qy, dark)
                    put(qx + 1, qy, mid)
                    put(qx, qy + 1, mid)
            cur = cur
            prev = cur
        # bright core pass along the same polyline
        prev = None
        for i in range(steps + 1):
            t = i / steps
            off = 0.0 if i in (0, steps) else amp * (1.0 if i % 2 else -1.0) * (1.0 - 0.35 * t)
            cx = x0 + ux * length * t + nx * off
            cy = y0 + uy * length * t + ny * off
            cur = (int(round(cx)), int(round(cy)))
            if prev is not None:
                for k in range(0, 41):
                    tt = k / 40.0
                    qx = int(round(prev[0] + (cur[0] - prev[0]) * tt))
                    qy = int(round(prev[1] + (cur[1] - prev[1]) * tt))
                    put(qx, qy, core)
            prev = cur

    base_x, base_y = 15.5, 21.0
    # right wing: 5 bolts fanning up and out
    rays_r = [(20, 6), (23, 10), (25, 15), (26, 20), (24, 25)]
    for (tx, ty) in rays_r:
        jag_ray(int(base_x) + 2, int(base_y), tx, ty, steps=4, amp=1.8)
    # left wing (mirror across x = 15.5)
    rays_l = [(11, 6), (8, 10), (6, 15), (5, 20), (7, 25)]
    for (tx, ty) in rays_l:
        jag_ray(int(base_x) - 2, int(base_y), tx, ty, steps=4, amp=1.8)

    # small storm cloud at the base
    for (bx, by, bw, bh) in ((10, 22, 12, 4), (12, 21, 8, 2), (13, 26, 6, 2)):
        for y in range(by, by + bh):
            for x in range(bx, bx + bw):
                if ((x + y) % 5) == 0:
                    put(x, y, cloud_hi)
                else:
                    put(x, y, cloud)

    return img


# ---------------------------------------------------------------------------
# 7. Multi-angle verification preview
# ---------------------------------------------------------------------------
def render_preview(blueprint: dict, texture: Image.Image, icon: Image.Image, out_path: Path) -> None:
    panel_w, panel_h = 250, 300
    canvas = Image.new('RGBA', (panel_w * 4 + 210, panel_h), (18, 22, 30, 255))

    def rot_mat(rx: float, ry: float, rz: float) -> np.ndarray:
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

    # flatten the outliner into (bone name, origin, cubes, parent tf)
    def walk(node, parent_tf, out):
        cubes = [by_uuid[c] for c in node.get('children', []) if isinstance(c, str)]
        orig = np.array(node['origin'], dtype=float)
        out.append((node['name'], orig, cubes, parent_tf))
        for c in node.get('children', []):
            if isinstance(c, dict):
                walk(c, lambda p, o=orig, par=parent_tf: par(o + (p - o)), out)

    stages = [
        (0.05, 0.0, -12.0, True, 'спина 3/4'),
        (0.30, 90.0, -10.0, True, 'сбоку'),
        (0.62, 180.0, -12.0, True, 'спереди'),
        (0.00, 0.0, -88.0, False, 'сверху'),
    ]

    for idx, (u, cam_yaw, cam_pitch, show_body, _label) in enumerate(stages):
        bg = (14, 18, 26, 255) if idx == 3 else (26, 30, 42, 255)
        panel = Image.new('RGBA', (panel_w, panel_h), bg)
        pose = eval_zeus_pose(u)

        ay, ap = math.radians(cam_yaw), math.radians(cam_pitch)
        cy_m, sy_m = math.cos(ay), math.sin(ay)
        cp_m, sp_m = math.cos(ap), math.sin(ap)

        scale_px = 5.2
        center_world = np.array([0.0, 22.0, 2.0])
        center_y_px = 165.0

        def proj(pt):
            d = np.asarray(pt, dtype=float) - center_world
            xw = d[0] * cy_m - d[2] * sy_m
            z1 = d[0] * sy_m + d[2] * cy_m
            yw = d[1] * cp_m - z1 * sp_m
            zw = d[1] * sp_m + z1 * cp_m
            return (panel_w * 0.5 - xw * scale_px, center_y_px - yw * scale_px, zw)

        faces_to_draw = []

        if show_body:
            boxes = [
                ([-3.75, 11.25, -1.875], [3.75, 22.5, 1.875], (52, 56, 70)),
                ([-7.5, 18.0, -1.875], [7.5, 22.5, 1.875], (58, 62, 78)),
                ([-3.75, 22.5, -3.75], [3.75, 30.0, 3.75], (84, 90, 110)),
            ]
            for low, high, base_rgb in boxes:
                cs = [np.array([low[0], low[1], low[2]]), np.array([high[0], low[1], low[2]]),
                      np.array([high[0], high[1], low[2]]), np.array([low[0], high[1], low[2]]),
                      np.array([low[0], low[1], high[2]]), np.array([high[0], low[1], high[2]]),
                      np.array([high[0], high[1], high[2]]), np.array([low[0], high[1], high[2]])]
                for idxs, sm in (((2, 1, 0, 3), 1.0), ((7, 4, 5, 6), 0.86), ((6, 5, 1, 2), 0.92),
                                 ((3, 0, 4, 7), 0.90), ((7, 6, 2, 3), 1.05)):
                    p2d = [proj(cs[k]) for k in idxs]
                    cross = ((p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1])
                             - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0]))
                    if cross <= 0:
                        col = tuple(min(255, int(c * sm)) for c in base_rgb) + (255,)
                        faces_to_draw.append((sum(p[2] for p in p2d) / 4.0,
                                              [(s[0], s[1]) for s in p2d], col, (36, 40, 52, 255)))

        # build bone transforms following the real hierarchy
        def make_tf(parent_tf, orig, pos, rot, scale):
            o = np.array(orig, dtype=float)
            t = np.array(pos, dtype=float)
            m = rot_mat(*rot)
            sc = np.array(scale, dtype=float)
            return lambda p: parent_tf(o + t + m @ (sc * (p - o)))

        root_tf = make_tf(lambda p: p, ROOT_ORIG, pose['root_pos'], pose['root_rot'], [1, 1, 1])
        tf = {'zeus_root': root_tf}
        for wing in ('wing_r', 'wing_l'):
            tf[wing] = make_tf(root_tf, ROOT_ORIG, [0, 0, 0], pose['wing_rot'][wing], [1, 1, 1])
        for name in FEATHER_IDS:
            parent = tf['wing_r'] if name.startswith('feather_r') else tf['wing_l']
            piv = _feather_pivot(int(name[-1]))
            if name.startswith('feather_l'):
                piv = _mirror_pivot(piv)
            tf[name] = make_tf(parent, piv, [0, 0, 0], pose['feather_rot'][name],
                               pose['feather_scale'][name])
        for side in ('r', 'l'):
            name = f'spark_{side}'
            tf[name] = make_tf(root_tf, _spark_pivot(side), [0, 0, 0],
                               pose['spark_rot'][name], pose['spark_scale'][name])

        flat = []
        for root_node in blueprint['outliner']:
            if isinstance(root_node, dict) and root_node['name'] == 'zeus_root':
                walk(root_node, lambda p: p, flat)
        for name, orig, cubes, _parent in flat:
            tf_fn = tf.get(name)
            if tf_fn is None or not cubes:
                continue
            for el in cubes:
                x0, y0, z0 = el['from']
                x1, y1, z1 = el['to']
                c_orig = np.array(el['origin'], dtype=float)
                c_rot = rot_mat(*el['rotation'])
                raw_cs = [np.array([x0, y0, z0]), np.array([x1, y0, z0]),
                          np.array([x1, y1, z0]), np.array([x0, y1, z0]),
                          np.array([x0, y0, z1]), np.array([x1, y0, z1]),
                          np.array([x1, y1, z1]), np.array([x0, y1, z1])]
                wcs = [tf_fn(c_orig + c_rot @ (c - c_orig)) for c in raw_cs]
                quads = [('north', (2, 1, 0, 3), 1.00), ('south', (7, 4, 5, 6), 0.96),
                         ('east', (6, 5, 1, 2), 0.98), ('west', (3, 0, 4, 7), 0.98),
                         ('up', (7, 6, 2, 3), 1.05), ('down', (0, 1, 5, 4), 0.92)]
                for fname, idxs, sm in quads:
                    p2d = [proj(wcs[k]) for k in idxs]
                    cross = ((p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1])
                             - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0]))
                    if cross > 0:
                        continue
                    z_avg = sum(p[2] for p in p2d) / 4.0
                    uv = el['faces'][fname]['uv']
                    tx = min(127, int(0.5 * (uv[0] + uv[2]) * 8))
                    ty = min(127, int(0.5 * (uv[1] + uv[3]) * 8))
                    rgba = tex_arr[ty, tx]
                    if rgba[3] < 16:
                        continue
                    col = tuple(min(255, int(c * sm)) for c in rgba[:3]) + (int(rgba[3]),)
                    faces_to_draw.append((z_avg, [(s[0], s[1]) for s in p2d], col, None))

        faces_to_draw.sort(key=lambda item: item[0], reverse=True)
        for _z, poly, col, outline in faces_to_draw:
            layer = Image.new('RGBA', (panel_w, panel_h), (0, 0, 0, 0))
            ImageDraw.Draw(layer, 'RGBA').polygon(poly, fill=col, outline=outline)
            panel.alpha_composite(layer)

        canvas.paste(panel, (idx * panel_w, 0))
        ImageDraw.Draw(canvas).line([(idx * panel_w, 0), (idx * panel_w, panel_h)],
                                    fill=(60, 70, 96, 255), width=1)

    icon_big = icon.resize((128, 128), Image.NEAREST)
    canvas.alpha_composite(icon_big, (panel_w * 4 + 41, 24))
    tex_small = texture.resize((112, 112), Image.NEAREST)
    canvas.alpha_composite(tex_small, (panel_w * 4 + 49, 170))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bbmodel-out', type=Path,
                        default=ROOT / 'plugins/ModelEngine/blueprints' / f'{MODEL}.bbmodel')
    parser.add_argument('--assets-dir', type=Path, default=HERE / 'assets')
    parser.add_argument('--preview', type=Path, default=None)
    args = parser.parse_args()

    blueprint, texture = build_blueprint()
    args.bbmodel_out.parent.mkdir(parents=True, exist_ok=True)
    args.bbmodel_out.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding='utf-8')

    icon = build_zeus_icon()
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

    print(f'Built {MODEL}.bbmodel: {len(blueprint["elements"])} cubes, '
          f'{len(BONE_NAMES)} bones, icon -> {args.assets_dir}')


if __name__ == '__main__':
    main()
