#!/usr/bin/env python3
"""Procedurally builds the 3D Zeus Lightning Wings (`elytrix_zeus_wings`), its 32x32
pixel-art menu icon (`reallyworld:zeus_wings_icon`) and a multi-angle verification preview.

100% pure procedural Python + Pillow + NumPy — zero AI generation.

  1. Visual design v2 — "RAGGED BUNDLE OF DISCHARGES WITH GAPS" ("рваный пучок
     разрядов с просветами"), chosen by the player to replace the earlier
     "arm + 5 feathers" silhouette:
       - Each wing is a FAN OF 6 INDEPENDENT ARCS (`arc_r1..r6`, `arc_l1..l6`) that
         shoot straight out of one shoulder-blade discharge hub.  No shared arm, no
         feather row — six separate bolts fanning from a single point.
       - The fan is deliberately IRREGULAR: angles `+61 / +38 / +27 / +5 / -12 / -33`
         deg and lengths `11.0 / 18.0 / 24.0 / 20.0 / 13.5 / 8.5` BB, so no two arcs
         line up and the wing never reads as a comb.
       - RAGGED: every arc is pierced by missing segments (`gaps`), so you can see
         straight through the wing between the bolts.  Each arc also throws one short
         razor fork and 1-2 loose tip sparks, which is what sells "живое электричество".
       - `wing_r` / `wing_l` are now empty group bones: they carry the whole-wing beat,
         while every arc wobbles and surges on its own phase on top of it.
       - A small storm-indigo cloud (`zeus_root`) boils between the shoulder blades with
         two bright feeder arcs, plus two crackling spark clusters (`spark_r`, `spark_l`).
       - Texture v2 — SMOOTH ENERGY GRADIENT (no scanlines, no per-pixel hash): each
         32x32 tile is a continuous ramp between 3-4 stops, modulated by two very
         low-frequency sine waves and finished with a 4x4 Bayer dither so the 8-bit
         gradient never bands.
       - Palette v2 — COLD BUT BRIGHTER (per the player's pick): white-hot core,
         bright cyan `hue ~192`, electric blue `hue ~210`, deep thunder-indigo
         `hue ~228`.  Every colour lives in hue `180..232`, zero warm/gold pixels.
  2. Motion (seamless 4.8 s loop @ 20 TPS = 96 ticks, 64 keyframes):
       - Whole-wing beat on the group bones (`+-7 deg` flap, `+3 deg` double-time
         shudder, `+-3.5 deg` sweep, `+-0.9 deg` crackle jitter).
       - Every arc independently flutters (`+-4.5 deg` + `1.6 deg` high-frequency
         crackle) and surges `+18%` on its own staggered discharge beat, so the wing
         "breathes" lightning instead of flapping cloth.
       - The root hovers `+-0.14` BB, the spark clusters pulse `0.55 -> 1.20` and tumble
         a full turn per loop.
  3. Engine safety (the rules that made the earlier models reliable):
       - **Not a single cube is rotated.**  Every jag is an axis-aligned L-step, exactly
         like `elytrix_kaneki_tentacles` / `elytrix_centipede`, so ModelEngine 4.1.0's
         `RotationSolver` is never invoked (it crashes on rotated cubes).
       - Every bone's geometry stays inside `+-24` BB of its own pivot (each arc pivots
         40% along its own length, so the longest `24` BB arc reaches only `14.4`),
         which keeps ModelEngine's `scaleToFit()` out of the pipeline.
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

# Right-wing discharge hub.  Every arc is born here; the left hub is the X mirror.
HUB = (1.10, 21.90, 2.35)


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f'elytrix.zeus_wings.v2:{tag}'))


# ---------------------------------------------------------------------------
# 1. Smooth-gradient electric texture (128x128, UV grid 16x16 -> 32 px tiles = 4 UV)
# ---------------------------------------------------------------------------
UV_BOLT_CORE = (0.25, 0.25, 3.75, 3.75)      # white-hot core -> bright cyan
UV_BOLT_MID = (4.25, 0.25, 7.75, 3.75)       # bright cyan -> electric blue
UV_BOLT_EDGE = (8.25, 0.25, 11.75, 3.75)     # electric blue -> deep thunder-indigo
UV_STORM_CLOUD = (12.25, 0.25, 15.75, 3.75)  # storm-indigo cloud
UV_SPARK_ICE = (0.25, 4.25, 3.75, 7.75)      # radial white-hot spark
UV_GLOW = (4.25, 4.25, 7.75, 7.75)           # pale cyan-white fork glow

# 4x4 Bayer matrix — kills 8-bit banding without ever looking dithered at 32 px.
_BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def _ramp(stops, t: float):
    """Piecewise-linear colour ramp.  `stops` = [(pos, (r,g,b)), ...] sorted by pos."""
    if t <= stops[0][0]:
        return stops[0][1]
    if t >= stops[-1][0]:
        return stops[-1][1]
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p0 <= t <= p1:
            k = (t - p0) / (p1 - p0)
            return tuple(int(round(c0[j] + (c1[j] - c0[j]) * k)) for j in range(3))
    return stops[-1][1]


def build_zeus_texture() -> Image.Image:
    """128x128 pixel-art texture: 6 smooth gradient tiles, zero scanlines."""
    arr = np.zeros((128, 128, 4), dtype=np.uint8)

    def tile(tx: int, ty: int) -> tuple:
        """Pixel-iterator factory for the 32x32 tile at grid cell (tx, ty)."""
        return (tx * 32, ty * 32)

    def paint(tx: int, ty: int, fn) -> None:
        ox, oy = tile(tx, ty)
        for py in range(32):
            for px in range(32):
                col = fn(px, py)
                dith = (_BAYER4[py & 3][px & 3] / 16.0 - 0.46875) * 1.7
                arr[oy + py, ox + px] = (
                    max(0, min(255, int(round(col[0] + dith)))),
                    max(0, min(255, int(round(col[1] + dith)))),
                    max(0, min(255, int(round(col[2] + dith)))),
                    255,
                )

    # Two very low-frequency sine waves: gentle large-scale energy wobble, no noise.
    def wob(px: int, py: int) -> float:
        return (0.035 * math.sin(px * 0.21 + py * 0.13)
                + 0.028 * math.sin(px * 0.09 - py * 0.17))

    # --- Tile (0,0): white-hot core -> bright cyan (vertical ramp) ---
    core_stops = [(0.00, (255, 255, 255)), (0.45, (214, 248, 255)), (1.00, (150, 232, 255))]
    paint(0, 0, lambda px, py: _ramp(core_stops, py / 31.0 + wob(px, py)))

    # --- Tile (1,0): bright cyan -> electric blue ---
    mid_stops = [(0.00, (186, 242, 255)), (0.40, (92, 212, 255)), (1.00, (30, 140, 248))]
    paint(1, 0, lambda px, py: _ramp(mid_stops, py / 31.0 + wob(px, py)))

    # --- Tile (2,0): electric blue -> deep thunder-indigo ---
    edge_stops = [(0.00, (78, 146, 244)), (0.45, (32, 88, 206)), (1.00, (12, 28, 94))]
    paint(2, 0, lambda px, py: _ramp(edge_stops, py / 31.0 + wob(px, py)))

    # --- Tile (3,0): storm-indigo cloud (soft, low contrast, still cold) ---
    cloud_stops = [(0.00, (72, 102, 214)), (0.50, (36, 58, 152)), (1.00, (14, 22, 72))]
    paint(3, 0, lambda px, py: _ramp(cloud_stops, py / 31.0 + wob(px, py) * 1.6))

    # --- Tile (0,1): radial white-hot spark ---
    spark_stops = [(0.00, (255, 255, 255)), (0.32, (188, 246, 255)),
                   (0.68, (104, 228, 255)), (1.00, (38, 172, 255))]
    paint(0, 1, lambda px, py: _ramp(
        spark_stops,
        min(1.0, math.hypot(px - 15.5, py - 15.5) / 17.0 + wob(px, py))))

    # --- Tile (1,1): pale cyan-white fork glow ---
    glow_stops = [(0.00, (255, 255, 255)), (0.50, (220, 250, 255)), (1.00, (148, 234, 255))]
    paint(1, 1, lambda px, py: _ramp(glow_stops, py / 31.0 + wob(px, py)))

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
              hw: float, hd: float, faces: dict, origin: list,
              taper: float = 0.5, gaps=()) -> list:
    """One jagged lightning bolt through `points` (list of (x, y, z)).

    Interior nodes are pushed off the polyline by an alternating perpendicular kick,
    and every segment is drawn as an axis-aligned L-step (a horizontal bar then a
    vertical bar).  The chain therefore reads as a hard zig-zag ribbon while
    **not a single cube carries a rotation** — the rule that keeps ModelEngine 4.1.0's
    `RotationSolver` (which crashes on rotated cubes) out of the pipeline.

    `gaps` lists segment indices that are SKIPPED ENTIRELY.  That is what makes the
    wing ragged: the bolt is literally interrupted and you can see through it.
    """
    pts = []
    n = len(points)
    for i, (px, py, pz) in enumerate(points):
        if i == 0 or i == n - 1:
            pts.append((float(px), float(py), float(pz)))
            continue
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
        if i in gaps:
            continue                      # <- deliberate hole in the discharge
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
               faces: dict, origin: list, taper: float = 0.5, gaps=()) -> list:
    """Straight jagged bolt from `p0` to `p1` (XY plane), drifting `z0` -> `z1`."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        pts.append((p0[0] + (p1[0] - p0[0]) * t,
                    p0[1] + (p1[1] - p0[1]) * t,
                    z0 + (z1 - z0) * t))
    return jag_chain(prefix, pts, amp, seed, hw, hd, faces, origin, taper, gaps)


def mirror_all(cubes: list, suffix: str = '_l') -> list:
    return [_mirror(c, suffix) for c in cubes]


# ---------------------------------------------------------------------------
# 3. Geometry v2 — a ragged fan of six discharges per wing
# ---------------------------------------------------------------------------
# (angle deg from horizontal, length BB, L-steps, half width, half depth, jag amp, gaps)
# Angles and lengths are deliberately uneven: +61/+38/+27/+5/-12/-33 and
# 11.0/18.0/24.0/20.0/13.5/8.5, so the fan never reads as a regular comb.
ARCS = [
    (52.0, 11.0, 5, 0.22, 0.19, 0.78, (2,)),
    (34.0, 18.0, 6, 0.26, 0.22, 0.86, (1, 3)),
    (18.0, 23.0, 8, 0.30, 0.25, 0.95, (2, 5)),
    (3.0, 20.0, 8, 0.28, 0.24, 0.90, (1, 4)),
    (-13.0, 13.5, 6, 0.25, 0.21, 0.80, (2,)),
    (-33.0, 8.5, 5, 0.21, 0.18, 0.70, (1, 3)),
]
ARC_COUNT = len(ARCS)

# Where each arc pivots, as a fraction of its own length (0.40 keeps the longest
# 24 BB arc within 14.4 BB of its pivot, well inside ModelEngine's +-24 BB budget).
ARC_PIVOT_T = 0.40

# Razor forks per arc: (start fraction along the arc, angle offset deg, length BB).
# The two longest arcs throw a second fork further out — that is what makes the fan
# read as crackling electricity instead of six tidy sticks.
FORK_SPEC = {
    0: ((0.50, -46.0, 4.2),),
    1: ((0.45, 40.0, 4.6), (0.78, -34.0, 3.4)),
    2: ((0.40, -42.0, 5.4), (0.72, 36.0, 4.0)),
    3: ((0.62, 44.0, 4.6),),
    4: ((0.55, -38.0, 3.8),),
    5: ((0.48, 42.0, 3.2),),
}
# Loose tip sparks per arc: (offset along the arc past the tip, lateral offset BB, size)
TIP_SPARKS = {
    0: ((1.4, 0.7, 0.34),),
    1: ((1.8, -0.9, 0.30), (2.4, 0.5, 0.22)),
    2: ((2.0, 1.0, 0.32), (2.6, -0.6, 0.24)),
    3: ((1.6, -0.8, 0.28),),
    4: ((1.4, 0.7, 0.26),),
    5: (),
}
# Spark clusters hovering just above each shoulder blade.
SPARKS = [
    (2.6, 24.4, 2.5), (-2.6, 24.4, 2.5),
]


def _arc_ray(idx: int):
    """Unit direction, tip point and mid-pivot of arc `idx` (right wing, +X)."""
    ang, length, _steps, _hw, _hd, _amp, _gaps = ARCS[idx]
    ay = HUB[1] + (0.40 - 0.10 * idx)
    ax, az = HUB[0], HUB[2]
    rad = math.radians(ang)
    ux, uy = math.cos(rad), math.sin(rad)
    tip = (ax + ux * length, ay + uy * length, az + 0.55)
    pivot = (ax + ux * length * ARC_PIVOT_T,
             ay + uy * length * ARC_PIVOT_T,
             az + 0.55 * ARC_PIVOT_T)
    return (ax, ay, az), (ux, uy), length, tip, pivot


def _arc_pivot(idx: int) -> list:
    _start, _u, _l, _tip, pivot = _arc_ray(idx)
    return [round(pivot[0], 4), round(pivot[1], 4), round(pivot[2], 4)]


def _mirror_pivot(p: list) -> list:
    return [round(-p[0], 4), p[1], p[2]]


def _spark_pivot(side: str) -> list:
    sx, sy, sz = SPARKS[0] if side == 'r' else SPARKS[1]
    return [round(float(sx), 4), round(float(sy), 4), round(float(sz), 4)]


def build_geometry(elements: list) -> dict:
    """Fills `elements` and returns {bone_name: [cube uuids]}."""
    bolt_faces = _faces(UV_BOLT_MID, north=UV_BOLT_CORE, south=UV_BOLT_CORE,
                        up=UV_BOLT_MID, down=UV_BOLT_MID,
                        east=UV_BOLT_EDGE, west=UV_BOLT_EDGE)
    glow_faces = _faces(UV_GLOW, east=UV_BOLT_EDGE, west=UV_BOLT_EDGE)
    cloud_faces = _faces(UV_STORM_CLOUD)
    spark_faces = _faces(UV_SPARK_ICE, east=UV_GLOW, west=UV_GLOW)

    def add(cube: dict) -> str:
        elements.append(cube)
        return cube['uuid']

    def add_many(cubes: list) -> list:
        return [add(c) for c in cubes]

    bones = {}

    # --- A) zeus_root: storm-indigo cloud between the shoulder blades + 2 feeder arcs ---
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
    feed_pts = [(-1.2, 23.4, 2.6), (-3.6, 23.0, 2.5), (-5.4, 21.9, 2.4), (-7.4, 21.2, 2.2)]
    root_cubes.extend(jag_chain('feed_r', feed_pts, 0.55, 2.2, 0.16, 0.14,
                                glow_faces, ROOT_ORIG, taper=0.35))
    root_cubes.extend(mirror_all(jag_chain('feed_r', feed_pts, 0.55, 2.2, 0.16, 0.14,
                                           glow_faces, ROOT_ORIG, taper=0.35)))
    bones['zeus_root'] = add_many(root_cubes)

    # --- B) wing_r / wing_l: EMPTY group bones, they only carry the whole-wing beat ---
    bones['wing_r'] = []
    bones['wing_l'] = []

    # --- C) 12 ragged arcs: fan from the hub, each with gaps + a razor fork + sparks ---
    for idx in range(ARC_COUNT):
        ang, length, steps, hw, hd, amp, gaps = ARCS[idx]
        (ax, ay, az), (ux, uy), length, tip, _pivot = _arc_ray(idx)
        piv = _arc_pivot(idx)

        # main bolt: sample along the ray, then jag the interior nodes
        pts = []
        for i in range(steps + 1):
            t = i / steps
            pts.append((ax + ux * length * t,
                        ay + uy * length * t,
                        az + 0.55 * t))
        cubes = jag_chain(f'arc_r{idx + 1}', pts, amp, 1.3 + idx * 2.7,
                          hw, hd, bolt_faces, piv, taper=0.45, gaps=gaps)

        # razor forks branching off the bolt
        for fk, (ft, fang, flen) in enumerate(FORK_SPEC.get(idx, ())):
            frad = math.radians(ang + fang)
            fx = ax + ux * length * ft
            fy = ay + uy * length * ft
            fz = az + 0.55 * ft
            cubes.extend(bolt_cubes(
                f'fork_r{idx + 1}_{fk}',
                (fx, fy),
                (fx + math.cos(frad) * flen, fy + math.sin(frad) * flen),
                fz, fz + 0.18,
                hw * 0.68, hd * 0.68, 2, amp * 0.55, 7.0 + idx * 3.0 + fk,
                glow_faces, piv, taper=0.6, gaps=(1,)))

        # loose tip sparks hanging past the end of the bolt
        for k, (along, lat, size) in enumerate(TIP_SPARKS.get(idx, ())):
            trad = math.radians(ang)
            sx = tip[0] + math.cos(trad) * along - math.sin(trad) * lat
            sy = tip[1] + math.sin(trad) * along + math.cos(trad) * lat
            sz = tip[2] + 0.10 * k
            cubes.append(_cube(f'ash_r{idx + 1}_{k}',
                               [sx - size, sy - size, sz - size],
                               [sx + size, sy + size, sz + size],
                               piv, spark_faces))

        bones[f'arc_r{idx + 1}'] = add_many(cubes)

        left_piv = _mirror_pivot(piv)
        left = []
        for c in cubes:
            m = _mirror(c)
            m['origin'] = left_piv
            m['uuid'] = uid(f"cube:{m['name']}")
            left.append(m)
        bones[f'arc_l{idx + 1}'] = add_many(left)

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
# 4. Seamless 4.8 s animation: wing beat, per-arc flutter, electric discharge
# ---------------------------------------------------------------------------
ARC_IDS = [f'arc_{s}{i}' for s in ('r', 'l') for i in range(1, ARC_COUNT + 1)]
BONE_NAMES = ['zeus_root', 'wing_r', 'wing_l'] + ARC_IDS + ['spark_r', 'spark_l']


def eval_zeus_pose(u: float) -> dict:
    """Bone transforms at normalized phase u in [0, 1] (u = 1.0 closes the loop)."""
    tau = 2.0 * math.pi
    up = 0.0 if u >= 1.0 else u

    hover_y = 0.14 * math.sin(tau * up)

    # Whole-wing beat on the empty group bones.
    flap = 7.0 * math.sin(tau * up) + 3.0 * math.sin(tau * 2.0 * up + 1.1)
    jitter = 0.9 * math.sin(tau * 8.0 * up + 0.6)
    flap_z = flap + jitter
    sweep_y = 3.5 * math.sin(tau * up + 0.35)

    pose = {
        'root_pos': [0.0, round(hover_y, 4), 0.0],
        'root_rot': [round(0.8 * math.sin(tau * up + 0.9), 4), 0.0,
                     round(1.1 * math.sin(tau * up), 4)],
        'wing_rot': {'wing_r': [0.0, round(sweep_y, 4), round(flap_z, 4)],
                     'wing_l': [0.0, round(-sweep_y, 4), round(-flap_z, 4)]},
        'arc_rot': {},
        'arc_scale': {},
        'spark_rot': {},
        'spark_scale': {},
    }

    for side, sign in (('r', 1.0), ('l', -1.0)):
        for i in range(1, ARC_COUNT + 1):
            name = f'arc_{side}{i}'
            phase = 0.62 * (i - 1) + (0.0 if side == 'r' else math.pi)
            # Each arc wobbles a little differently: the fan never moves as one plate.
            flutter = 4.5 * math.sin(tau * up + phase)
            crackle = 1.6 * math.sin(tau * 7.0 * up + i * 1.9)
            twist = 1.1 * math.sin(tau * 3.0 * up + phase * 1.7)
            pose['arc_rot'][name] = [round(twist, 4),
                                     round(0.7 * crackle, 4),
                                     round(sign * (flutter + crackle), 4)]
            # Discharge: a narrow +18% surge travelling outward through the fan.
            beat = (up - (i - 1) * 0.14 - (0.0 if side == 'r' else 0.5)) % 1.0
            pulse = math.exp(-((beat - 0.5) / 0.15) ** 2)
            s = round(1.0 + 0.05 * math.sin(tau * up + phase) + 0.18 * pulse, 4)
            pose['arc_scale'][name] = [s, round(1.0 + 0.04 * pulse, 4), s]

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

        for name in ARC_IDS:
            kfs[name].append(_vec_kf('rotation', f'idle:{name}', t, *pose['arc_rot'][name]))
            kfs[name].append(_vec_kf('scale', f'idle:{name}', t, *pose['arc_scale'][name]))

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

    def wing_group(side: str) -> dict:
        arcs = [bone(f'arc_{side}{i}',
                     _arc_pivot(i - 1) if side == 'r' else _mirror_pivot(_arc_pivot(i - 1)),
                     bones[f'arc_{side}{i}'], is_open=False)
                for i in range(1, ARC_COUNT + 1)]
        return bone(f'wing_{side}', ROOT_ORIG, arcs, is_open=False)

    outliner = [
        bone('zeus_root', ROOT_ORIG, [
            *bones['zeus_root'],
            wing_group('r'),
            wing_group('l'),
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


# ---------------------------------------------------------------------------
# 6. Hand-crafted 32x32 pixel-art menu icon (`reallyworld:zeus_wings_icon`)
#    — same ragged fan as the 3D model, cold but bright palette.
# ---------------------------------------------------------------------------
def build_zeus_icon() -> Image.Image:
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    core = (255, 255, 255, 255)      # white-hot core
    mid = (104, 228, 255, 255)       # bright cyan
    dark = (30, 140, 248, 255)       # electric blue
    cloud = (36, 58, 152, 255)       # storm indigo
    cloud_hi = (72, 102, 214, 255)

    def put(x: int, y: int, c: tuple) -> None:
        if 0 <= x < 32 and 0 <= y < 32:
            px[x, y] = c

    def jag_ray(x0: float, y0: float, x1: float, y1: float,
                steps: int = 4, amp: float = 2.0, gaps=()) -> None:
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        nodes = []
        for i in range(steps + 1):
            t = i / steps
            off = 0.0 if i in (0, steps) else amp * (1.0 if i % 2 else -1.0) * (1.0 - 0.35 * t)
            nodes.append((x0 + ux * length * t + nx * off,
                          y0 + uy * length * t + ny * off))
        for i in range(steps):
            if i in gaps:
                continue
            (ax, ay), (bx, by) = nodes[i], nodes[i + 1]
            for k in range(41):
                tt = k / 40.0
                qx = int(round(ax + (bx - ax) * tt))
                qy = int(round(ay + (by - ay) * tt))
                for ox, oy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                    put(qx + ox, qy + oy, mid if (ox or oy) else dark)
        for i in range(steps):
            if i in gaps:
                continue
            (ax, ay), (bx, by) = nodes[i], nodes[i + 1]
            for k in range(41):
                tt = k / 40.0
                put(int(round(ax + (bx - ax) * tt)), int(round(ay + (by - ay) * tt)), core)

    hub_x, hub_y = 15.5, 17.5
    # Six uneven arcs per side — the same irregular fan as the 3D model.
    fan = (
        (52.0, 9.0, 3, 1.5, (1,)),
        (34.0, 13.0, 4, 1.8, (1, 3)),
        (18.0, 14.0, 5, 2.0, (2, 4)),
        (3.0, 13.0, 5, 1.9, (1, 4)),
        (-13.0, 10.0, 4, 1.6, (2,)),
        (-33.0, 7.0, 3, 1.3, (1,)),
    )
    for ang, length, steps, amp, gaps in fan:
        for sgn in (1.0, -1.0):
            rad = math.radians(ang)
            jag_ray(hub_x + sgn * 1.5, hub_y,
                    hub_x + sgn * (1.5 + math.cos(rad) * length),
                    hub_y - math.sin(rad) * length,
                    steps=steps, amp=amp, gaps=gaps)

    # small storm cloud at the base
    for (bx, by, bw, bh) in ((10, 21, 12, 4), (12, 20, 8, 2), (13, 25, 6, 2)):
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

        scale_px = 5.0
        center_world = np.array([0.0, 23.0, 2.0])
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
        for name in ARC_IDS:
            side = 'r' if name.startswith('arc_r') else 'l'
            i = int(name[-1])
            parent = tf['wing_r'] if side == 'r' else tf['wing_l']
            piv = _arc_pivot(i - 1)
            if side == 'l':
                piv = _mirror_pivot(piv)
            tf[name] = make_tf(parent, piv, [0, 0, 0], pose['arc_rot'][name],
                               pose['arc_scale'][name])
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

    drawn = sum(1 for b in BONE_NAMES if b not in ('wing_r', 'wing_l'))
    print(f'Built {MODEL}.bbmodel: {len(blueprint["elements"])} cubes, '
          f'{len(BONE_NAMES)} bones ({drawn} drawn), icon -> {args.assets_dir}')


if __name__ == '__main__':
    main()
