#!/usr/bin/env python3
"""Procedurally builds the 3D Zeus Lightning Wings (`elytrix_zeus_wings`), its 32x32
pixel-art menu icon (`reallyworld:zeus_wings_icon`) and a multi-angle verification preview.

100% pure procedural Python + Pillow + NumPy — zero AI generation.

  1. Visual design v3 — "BRANCHING LIGHTNING THAT READS AS WINGS" ("ветки молний,
     которые вместе выглядят как крылья"), chosen by the player to replace v2's
     fan-of-six-arcs silhouette:
       - Each wing is ONE CONTINUOUS TRUNK BOLT (`trunk_r` / `trunk_l`) that traces the
         wing's leading edge: shoulder hub `(0.9, 20.4)` -> up over the wrist
         `(11.6, 24.5)` -> down and out to the wingtip `(22.8, 17.9)`.  That single arc
         is what makes the whole shape read as a WING and not as a burst.  (The whole
         wing was later dropped `2.0` BB = `0.125` block on request: wrist `26.5 -> 24.5`.)
       - SEVEN BRANCH BOLTS (`branch_r1..r7`, `branch_l1..l7`) split off the trunk and
         hang down/back like primaries — short by the shoulder, longest at the wrist,
         tucking back up at the tip, so their tips trace the wing's trailing edge.
       - Every branch SPLITS AGAIN into 1-2 short barbs, so it is a real lightning
         tree and not a comb of sticks, and throws one loose spark past its tip.
       - STILL RAGGED: the branches are pierced by missing segments (`gaps`), so you
         see straight through the wing between the bolts.  The trunk stays continuous
         on purpose — it is the spar the wing hangs from.
       - `wing_r` / `wing_l` stay empty group bones carrying the whole-wing beat; the
         trunk lags behind that beat, and every branch flutters on its own phase with
         an amplitude that GROWS toward the wingtip (`2.6 deg -> 9.5 deg`).
       - A small storm-indigo cloud (`zeus_root`) boils between the shoulder blades
         with two bright feeder arcs, plus two crackling spark clusters
         (`spark_r`, `spark_l`).
       - Texture v2 — SMOOTH ENERGY GRADIENT (no scanlines, no per-pixel hash): each
         32x32 tile is a continuous ramp between 3-4 stops, modulated by two very
         low-frequency sine waves and finished with a 4x4 Bayer dither so the 8-bit
         gradient never bands.
       - Palette v2 — COLD BUT BRIGHTER (per the player's pick): white-hot core,
         bright cyan `hue ~192`, electric blue `hue ~210`, deep thunder-indigo
         `hue ~228`.  Every colour lives in hue `180..232`, zero warm/gold pixels.
  2. Motion (seamless 4.8 s loop @ 20 TPS = 96 ticks, 64 keyframes):
       - Whole-wing beat on the group bones (`+-6 deg` flap, `+3 deg` double-time
         shudder, `+-3.5 deg` sweep, `+-0.9 deg` crackle jitter).
       - The trunk lags the beat by `+-3.2 deg` and crackles `+-1.4 deg`.
       - Every branch independently flutters (`2.6..9.5 deg` by index + `1.7 deg`
         high-frequency crackle) and surges `+18%` on its own staggered discharge
         beat, so the wing "breathes" lightning instead of flapping cloth.
       - The root hovers `+-0.14` BB, the spark clusters pulse `0.55 -> 1.20` and tumble
         a full turn per loop.
  3. Engine safety (the rules that made the earlier models reliable):
       - **Not a single cube is rotated.**  Every jag is an axis-aligned L-step, exactly
         like `elytrix_kaneki_tentacles` / `elytrix_centipede`, so ModelEngine 4.1.0's
         `RotationSolver` is never invoked (it crashes on rotated cubes).
       - Every bone's geometry stays inside `+-24` BB of its own pivot (the trunk pivots
         at the wrist, the branches 40% along their own length — the worst bone reaches
         only ~13 BB), which keeps ModelEngine's `scaleToFit()` out of the pipeline.
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

# Right-wing discharge hub.  The trunk bolt is born here; the left hub is the X mirror.
# Dropped 2.0 BB (0.125 block) together with the whole wing — the player asked for the
# wings to sit a little lower on the back.
HUB = (0.90, 20.40, 2.30)


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
# 3. Geometry v3 — a branching lightning tree shaped like a wing
# ---------------------------------------------------------------------------
# One continuous TRUNK bolt per wing runs along the wing's leading edge
# (shoulder hub -> up over the wrist -> down and out to the wingtip).  SEVEN
# BRANCH bolts split off it and hang down/back like primaries: short by the
# shoulder, longest at the wrist, tucking back up at the tip, so their tips
# trace the wing's trailing edge.  Every branch splits AGAIN into 1-2 short
# barbs and throws one loose spark past its tip.  The branches are pierced by
# `gaps` so the wing stays ragged and transparent between the bolts — the
# trunk stays continuous on purpose, it is the spar the wing hangs from.
TRUNK = [
    (0.90, 20.40, 2.30),
    (2.60, 21.30, 2.42),
    (4.40, 22.20, 2.55),
    (6.20, 23.05, 2.68),
    (8.00, 23.70, 2.80),
    (9.80, 24.20, 2.90),
    (11.60, 24.50, 2.95),    # <- wrist: the highest point of the whole wing
    (13.35, 24.35, 2.90),
    (15.10, 24.10, 2.85),
    (16.70, 23.55, 2.78),
    (18.30, 22.90, 2.70),
    (19.70, 21.90, 2.62),
    (21.00, 20.80, 2.55),
    (21.95, 19.40, 2.50),
    (22.80, 17.90, 2.45),    # <- wingtip, sweeping down and back
]
# The trunk pivots at the wrist, so the farthest cube (the wingtip) sits only
# ~13 BB away — far inside ModelEngine's +-24 BB bone budget.
TRUNK_PIVOT_I = 6

# (attach index into TRUNK, tip x, tip y, tip z, L-steps, hw, hd, jag amp, gaps)
BRANCHES = [
    (2, 1.60, 16.60, 2.10, 5, 0.24, 0.20, 0.72, (2,)),
    (4, 6.60, 15.40, 2.15, 6, 0.26, 0.21, 0.80, (1, 4)),
    (6, 12.10, 14.90, 2.20, 6, 0.26, 0.21, 0.84, (2,)),
    (8, 17.40, 15.40, 2.30, 6, 0.25, 0.20, 0.78, (1, 4)),
    (10, 21.60, 16.30, 2.45, 5, 0.23, 0.19, 0.70, (2,)),
    (12, 24.10, 17.10, 2.55, 4, 0.21, 0.18, 0.62, (1,)),
    (13, 24.90, 16.30, 2.58, 4, 0.19, 0.17, 0.56, (2,)),
]
BRANCH_COUNT = len(BRANCHES)

# Branch pivots sit 40% along their own length: the longest branch is ~9.6 BB,
# so its farthest cube (plus a 4.3 BB barb) stays under 10 BB from the pivot.
BRANCH_PIVOT_T = 0.40

# Barb splits per branch (1-based): (t along the branch, angle offset deg, length BB).
# The sign alternates so the twigs splay to both sides instead of combing one way.
BARBS = {
    1: ((0.36, 44.0, 3.6), (0.72, -38.0, 2.6)),
    2: ((0.32, -46.0, 4.0), (0.68, 40.0, 2.9)),
    3: ((0.34, 42.0, 4.3), (0.70, -36.0, 3.1)),
    4: ((0.30, -44.0, 4.0), (0.66, 38.0, 2.8)),
    5: ((0.34, 46.0, 3.2), (0.70, -40.0, 2.3)),
    6: ((0.32, -42.0, 2.6), (0.68, 36.0, 1.9)),
    7: ((0.36, 40.0, 2.1),),
}
# Loose spark past each branch tip: (offset along the branch, lateral BB, half size)
BRANCH_TIPS = {
    1: ((0.9, 0.5, 0.30),),
    2: ((1.0, -0.5, 0.30),),
    3: ((1.1, 0.4, 0.28),),
    4: ((1.0, -0.4, 0.26),),
    5: ((0.8, 0.3, 0.24),),
    6: ((0.7, -0.3, 0.22),),
    7: ((0.6, 0.2, 0.20),),
}
# Spark clusters hovering just above each shoulder blade.
SPARKS = [
    (2.6, 22.8, 2.5), (-2.6, 22.8, 2.5),
]


def _trunk_pivot() -> list:
    p = TRUNK[TRUNK_PIVOT_I]
    return [round(float(p[0]), 4), round(float(p[1]), 4), round(float(p[2]), 4)]


# --- ОБЛАЧНЫЙ ОБОДОК СВЕРХУ КРЫЛА (v3.26.0) -----------------------------------
# По просьбе игрока: «Добавь крыльям зевса сверху ободок похожий на облака».
# Это НЕ ещё одна молния, а ПУФЫ из уже существующего штормового материала
# `UV_STORM_CLOUD`, которые едут ВЕРХОМ по дуге ствола (спара) — от плечевого
# хаба через запястье (высшая точка крыла) и до самого кончика. Гребень пухнет
# у запястья и сходит на нет к обоим концам, поэтому ободок читается как облако,
# налипшее на ВЕРХНЮЮ кромку крыла, а не как ровная полоса.
RIM_LIFT = 0.36          # насколько пуф приподнят над осью спар-молнии, BB
RIM_PUFF_T = 0.42        # положение пика гребня по дуге ствола (запястье)
RIM_PUFF_W = 0.40        # ширина колокола гребня по дуге


def _rim_puffs() -> list:
    """Возвращает список (x0, y0, z0, x1, y1, z1) пуфов поверх дуги TRUNK."""
    puffs = []
    n = len(TRUNK)
    for i in range(n):
        # Основной пуф в каждой точке ствола + маленький промежуточный между
        # соседними точками — так ободок получается РВАНО-ПУШИСТЫМ, без щелей.
        for sub, shrink in ((0.0, 1.0), (0.5, 0.62)):
            if sub > 0.0 and i == n - 1:
                continue
            a = TRUNK[i]
            b = TRUNK[min(i + 1, n - 1)]
            x = a[0] + (b[0] - a[0]) * sub
            y = a[1] + (b[1] - a[1]) * sub
            z = a[2] + (b[2] - a[2]) * sub
            t = (i + sub) / (n - 1)
            bell = math.exp(-((t - RIM_PUFF_T) / RIM_PUFF_W) ** 2)
            # Небольшой детерминированный «разброс», чтобы силуэт не был симметричным.
            wob = 0.86 + 0.26 * math.sin(i * 1.73 + sub * 2.1)
            hx = (0.40 + 0.60 * bell) * shrink * wob
            hz = (0.23 + 0.19 * bell) * shrink
            h = (0.58 + 0.52 * bell) * shrink * (0.88 + 0.22 * math.sin(i * 2.31 + sub))
            zc = z + 0.09 * math.sin(i * 2.27 + sub * 1.6)
            y0 = y + RIM_LIFT
            puffs.append((round(x - hx, 4), round(y0, 4), round(zc - hz, 4),
                          round(x + hx, 4), round(y0 + h, 4), round(zc + hz, 4)))
    return puffs


RIM_PUFFS = _rim_puffs()
# Пивот — запястье (та же точка, что и у ствола): самый дальний куб ободка
# (кончик крыла) лежит всего в ~12.7 BB, далеко внутри лимита +-24 BB.
def _rim_pivot() -> list:
    return _trunk_pivot()


def _branch_pivot(idx: int) -> list:
    att, tx, ty, tz = BRANCHES[idx][:4]
    ax, ay, az = TRUNK[att]
    t = BRANCH_PIVOT_T
    return [round(ax + (tx - ax) * t, 4),
            round(ay + (ty - ay) * t, 4),
            round(az + (tz - az) * t, 4)]


def _mirror_pivot(p: list) -> list:
    return [round(-p[0], 4), p[1], p[2]]


def _mirror_chain(cubes: list, pivot: list) -> list:
    """X-mirror a whole cube chain onto a new (mirrored) bone pivot."""
    out = []
    for c in cubes:
        m = _mirror(c)
        m['origin'] = pivot
        m['uuid'] = uid(f"cube:{m['name']}")
        out.append(m)
    return out


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
    # two short feeder bolts: storm cloud -> each wing's trunk hub
    feed_pts = [(-1.8, 23.0, 2.70), (-0.5, 22.1, 2.60), (0.4, 21.1, 2.45), TRUNK[0]]
    root_cubes.extend(jag_chain('feed_r', feed_pts, 0.45, 2.2, 0.16, 0.14,
                                glow_faces, ROOT_ORIG, taper=0.35))
    root_cubes.extend(mirror_all(jag_chain('feed_r', feed_pts, 0.45, 2.2, 0.16, 0.14,
                                           glow_faces, ROOT_ORIG, taper=0.35)))
    bones['zeus_root'] = add_many(root_cubes)

    # --- B) wing_r / wing_l: EMPTY group bones, they only carry the whole-wing beat ---
    bones['wing_r'] = []
    bones['wing_l'] = []

    # --- B2) cloud_rim_r / cloud_rim_l: облачный ободок по ВЕРХУ дуги ствола ---
    rim_piv = _rim_pivot()
    rim_cubes = []
    for i, (x0, y0, z0, x1, y1, z1) in enumerate(RIM_PUFFS):
        rim_cubes.append(_cube(f'cloudrim_{i:02d}', [x0, y0, z0], [x1, y1, z1],
                               rim_piv, cloud_faces))
    bones['cloud_rim_r'] = add_many(rim_cubes)
    bones['cloud_rim_l'] = add_many(_mirror_chain(rim_cubes, _mirror_pivot(rim_piv)))

    # --- C) trunk: one continuous arched bolt per wing = the wing's leading edge ---
    tpiv = _trunk_pivot()
    trunk = jag_chain('trunk_r', TRUNK, 0.82, 5.1, 0.32, 0.24,
                      bolt_faces, tpiv, taper=0.45)
    bones['trunk_r'] = add_many(trunk)
    bones['trunk_l'] = add_many(_mirror_chain(trunk, _mirror_pivot(tpiv)))

    # --- D) seven branch bolts hanging off the trunk, each splitting into barbs ---
    for idx, (att, tx, ty, tz, steps, hw, hd, amp, gaps) in enumerate(BRANCHES):
        ax, ay, az = TRUNK[att]
        bpiv = _branch_pivot(idx)
        pts = []
        for i in range(steps + 1):
            t = i / steps
            pts.append((ax + (tx - ax) * t,
                        ay + (ty - ay) * t,
                        az + (tz - az) * t))
        cubes = jag_chain(f'branch_r{idx + 1}', pts, amp, 11.0 + idx * 3.3,
                          hw, hd, bolt_faces, bpiv, taper=0.5, gaps=gaps)

        # the branch splits again — that is what makes it a lightning TREE
        base = math.atan2(ty - ay, tx - ax)
        for bk, (bt, bang, blen) in enumerate(BARBS.get(idx + 1, ())):
            bx = ax + (tx - ax) * bt
            by = ay + (ty - ay) * bt
            bz = az + (tz - az) * bt
            rad = base + math.radians(bang)
            cubes.extend(bolt_cubes(
                f'barb_r{idx + 1}_{bk}',
                (bx, by),
                (bx + math.cos(rad) * blen, by + math.sin(rad) * blen),
                bz, bz + 0.14,
                hw * 0.66, hd * 0.66, 2, amp * 0.5, 23.0 + idx * 4.0 + bk,
                glow_faces, bpiv, taper=0.6, gaps=(1,)))

        # loose spark hanging past the tip of the branch
        for k, (along, lat, size) in enumerate(BRANCH_TIPS.get(idx + 1, ())):
            sx = tx + math.cos(base) * along - math.sin(base) * lat
            sy = ty + math.sin(base) * along + math.cos(base) * lat
            sz = tz + 0.08 * k
            cubes.append(_cube(f'ash_r{idx + 1}_{k}',
                               [sx - size, sy - size, sz - size],
                               [sx + size, sy + size, sz + size],
                               bpiv, spark_faces))

        bones[f'branch_r{idx + 1}'] = add_many(cubes)
        bones[f'branch_l{idx + 1}'] = add_many(_mirror_chain(cubes, _mirror_pivot(bpiv)))

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
TRUNK_IDS = ['trunk_r', 'trunk_l']
BRANCH_IDS = [f'branch_{s}{i}' for s in ('r', 'l') for i in range(1, BRANCH_COUNT + 1)]
BONE_NAMES = (['zeus_root', 'wing_r', 'wing_l'] + TRUNK_IDS + BRANCH_IDS
              + ['cloud_rim_r', 'cloud_rim_l'] + ['spark_r', 'spark_l'])


def eval_zeus_pose(u: float) -> dict:
    """Bone transforms at normalized phase u in [0, 1] (u = 1.0 closes the loop)."""
    tau = 2.0 * math.pi
    up = 0.0 if u >= 1.0 else u

    hover_y = 0.14 * math.sin(tau * up)

    # Whole-wing beat on the empty group bones.
    flap = 6.0 * math.sin(tau * up) + 3.0 * math.sin(tau * 2.0 * up + 1.1)
    jitter = 0.9 * math.sin(tau * 8.0 * up + 0.6)
    flap_z = flap + jitter
    sweep_y = 3.5 * math.sin(tau * up + 0.35)

    pose = {
        'root_pos': [0.0, round(hover_y, 4), 0.0],
        'root_rot': [round(0.8 * math.sin(tau * up + 0.9), 4), 0.0,
                     round(1.1 * math.sin(tau * up), 4)],
        'wing_rot': {'wing_r': [0.0, round(sweep_y, 4), round(flap_z, 4)],
                     'wing_l': [0.0, round(-sweep_y, 4), round(-flap_z, 4)]},
        'trunk_rot': {},
        'trunk_scale': {},
        'branch_rot': {},
        'branch_scale': {},
        'rim_scale': {},
        'spark_rot': {},
        'spark_scale': {},
    }

    for side, sign in (('r', 1.0), ('l', -1.0)):
        phase = 0.0 if side == 'r' else math.pi

        # The trunk is the spar: it lags the group beat and crackles along its length.
        tname = f'trunk_{side}'
        lag = 3.2 * math.sin(tau * up + 0.30 + phase)
        tcr = 1.4 * math.sin(tau * 7.0 * up + 0.4)
        pose['trunk_rot'][tname] = [round(0.7 * tcr, 4),
                                    round(0.5 * tcr, 4),
                                    round(sign * (lag + tcr), 4)]
        beat = (up - (0.0 if side == 'r' else 0.5)) % 1.0
        pulse = math.exp(-((beat - 0.5) / 0.16) ** 2)
        ts = round(1.0 + 0.03 * math.sin(tau * up + phase) + 0.12 * pulse, 4)
        pose['trunk_scale'][tname] = [ts, round(1.0 + 0.03 * pulse, 4), ts]

        # Branches flutter harder the further out they sit, so the wingtip whips.
        for i in range(1, BRANCH_COUNT + 1):
            name = f'branch_{side}{i}'
            bph = 0.52 * (i - 1) + phase
            amp = 2.6 + 1.15 * (i - 1)
            flutter = amp * math.sin(tau * up + bph)
            crackle = 1.7 * math.sin(tau * 7.0 * up + i * 1.7)
            twist = 1.0 * math.sin(tau * 3.0 * up + bph * 1.6)
            pose['branch_rot'][name] = [round(twist, 4),
                                        round(0.6 * crackle, 4),
                                        round(sign * (flutter + crackle), 4)]
            # Discharge: a narrow +18% surge travelling outward through the tree.
            beat = (up - (i - 1) * 0.11 - (0.0 if side == 'r' else 0.5)) % 1.0
            pulse = math.exp(-((beat - 0.5) / 0.15) ** 2)
            s = round(1.0 + 0.05 * math.sin(tau * up + bph) + 0.18 * pulse, 4)
            pose['branch_scale'][name] = [s, round(1.0 + 0.04 * pulse, 4), s]

        # Облачный ободок не молния: он не трещит, а медленно «кипит» —
        # масштаб дышит на своей фазе, поэтому гребень всё время шевелится.
        rname = f'cloud_rim_{side}'
        rph = 1.15 + phase
        boil = 0.055 * math.sin(tau * 2.0 * up + rph) \
            + 0.030 * math.sin(tau * 5.0 * up + rph * 2.3)
        rs = round(1.0 + boil, 4)
        pose['rim_scale'][rname] = [rs, round(1.0 - 0.4 * boil, 4), rs]

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

        for name in TRUNK_IDS:
            kfs[name].append(_vec_kf('rotation', f'idle:{name}', t, *pose['trunk_rot'][name]))
            kfs[name].append(_vec_kf('scale', f'idle:{name}', t, *pose['trunk_scale'][name]))

        for name in BRANCH_IDS:
            kfs[name].append(_vec_kf('rotation', f'idle:{name}', t, *pose['branch_rot'][name]))
            kfs[name].append(_vec_kf('scale', f'idle:{name}', t, *pose['branch_scale'][name]))

        for rname in ('cloud_rim_r', 'cloud_rim_l'):
            kfs[rname].append(_vec_kf('scale', f'idle:{rname}', t, *pose['rim_scale'][rname]))

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
        kids = [bone(f'trunk_{side}',
                     _trunk_pivot() if side == 'r' else _mirror_pivot(_trunk_pivot()),
                     bones[f'trunk_{side}'], is_open=False)]
        for i in range(1, BRANCH_COUNT + 1):
            bp = _branch_pivot(i - 1)
            kids.append(bone(f'branch_{side}{i}',
                             bp if side == 'r' else _mirror_pivot(bp),
                             bones[f'branch_{side}{i}'], is_open=False))
        # Облачный ободок — ребёнок группы крыла, поэтому он бьёт вместе с ним.
        kids.append(bone(f'cloud_rim_{side}',
                         _rim_pivot() if side == 'r' else _mirror_pivot(_rim_pivot()),
                         bones[f'cloud_rim_{side}'], is_open=False))
        return bone(f'wing_{side}', ROOT_ORIG, kids, is_open=False)

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
#    — same branching lightning wing as the 3D model, cold but bright palette.
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

    def bolt(pts: list, amp: float, gaps=(), halo: bool = True) -> None:
        """Jagged bolt through `pts` (list of (x, y)).

        `halo=True` (the trunk) draws a cyan glow one pixel around a white core,
        `halo=False` (the branches) draws a bare one-pixel core line — at 32x32 six
        haloed bolts merge into a solid blob, so only the spar keeps its glow.
        Interior nodes are kicked off the polyline by an alternating perpendicular
        offset, exactly like the 3D `jag_chain`, and `gaps` skips whole segments so
        the little icon is as ragged and see-through as the model itself.
        """
        P = []
        n = len(pts)
        for i, (x, y) in enumerate(pts):
            if i == 0 or i == n - 1:
                P.append((float(x), float(y)))
                continue
            ax, ay = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
            bx, by = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
            la, lb = math.hypot(ax, ay) or 1.0, math.hypot(bx, by) or 1.0
            nx, ny = -(ay / la + by / lb), (ax / la + bx / lb)
            ln = math.hypot(nx, ny) or 1.0
            off = amp * (1.0 if i % 2 else -1.0)
            P.append((x + nx / ln * off, y + ny / ln * off))

        for i in range(len(P) - 1):
            if i in gaps:
                continue
            (x0, y0), (x1, y1) = P[i], P[i + 1]
            steps = max(3, int(math.hypot(x1 - x0, y1 - y0) * 3))
            for k in range(steps + 1):
                tt = k / steps
                qx = int(round(x0 + (x1 - x0) * tt))
                qy = int(round(y0 + (y1 - y0) * tt))
                if halo:
                    for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        put(qx + ox, qy + oy, mid)
                    put(qx, qy, dark)
                put(qx, qy, core)

    # small storm cloud the wings erupt from — drawn FIRST, bolts on top of it
    for (bx, by, bw, bh) in ((12, 17, 9, 4), (13, 16, 7, 2), (13, 21, 7, 2)):
        for y in range(by, by + bh):
            for x in range(bx, bx + bw):
                put(x, y, cloud_hi if ((x + y) % 5) == 0 else cloud)

    # Right half of the wing (x from 16 outwards); the left half is the X mirror.
    TRUNK_ICON = [(16, 16), (18, 14), (20, 12), (22, 10), (24, 9),
                  (26, 10), (28, 12), (30, 16)]
    BRANCH_ICON = [
        ((18, 14), (16.0, 22)),
        ((20, 12), (19.0, 23)),
        ((22, 10), (23.0, 23)),
        ((25, 9.5), (27.0, 21)),
        ((28, 12), (30.0, 18)),
    ]
    for sgn in (1.0, -1.0):
        def mx(x: float) -> float:
            return 15.5 + sgn * (x - 15.5)

        bolt([(mx(x), y) for x, y in TRUNK_ICON], 1.1)
        for k, (p0, p1) in enumerate(BRANCH_ICON):
            qmid = ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)
            # every other branch is interrupted, so the wing is see-through
            bolt([(mx(p0[0]), p0[1]), (mx(qmid[0]), qmid[1]), (mx(p1[0]), p1[1])],
                 1.0, gaps=(1,) if k % 2 else (), halo=False)

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
        for name in TRUNK_IDS:
            side = name[-1]
            piv = _trunk_pivot()
            if side == 'l':
                piv = _mirror_pivot(piv)
            tf[name] = make_tf(tf[f'wing_{side}'], piv, [0, 0, 0],
                               pose['trunk_rot'][name], pose['trunk_scale'][name])
        for name in BRANCH_IDS:
            side = name[7]                       # 'branch_r3' -> 'r'
            i = int(name[8:])
            piv = _branch_pivot(i - 1)
            if side == 'l':
                piv = _mirror_pivot(piv)
            tf[name] = make_tf(tf[f'wing_{side}'], piv, [0, 0, 0],
                               pose['branch_rot'][name], pose['branch_scale'][name])
        for side in ('r', 'l'):
            name = f'cloud_rim_{side}'
            piv = _rim_pivot()
            if side == 'l':
                piv = _mirror_pivot(piv)
            tf[name] = make_tf(tf[f'wing_{side}'], piv, [0, 0, 0], [0, 0, 0],
                               pose['rim_scale'][name])
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
