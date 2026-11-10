#!/usr/bin/env python3
"""Procedurally builds the Zeus wings (`elytrix_zeus_wings`), its 32x32 pixel-art menu
icon (`reallyworld:zeus_wings_icon`) and a multi-angle verification preview.

100% pure procedural Python + Pillow + NumPy — zero AI generation.

  1. Visual design v4 — "A REAL FEATHERED WING" (v3.26/v3.27 were a lightning tree and
     then a staircase feather plane; the player asked for a complete remake "from zero",
     shaped like the angel wings, with a completely redrawn, pleasant texture).
       - The wing is built the way a bird's wing is built: ONE ARM (humerus + radius)
         traces the leading edge from the shoulder blade out over the wrist and down to
         the wingtip, and THIRTEEN FEATHERS hang off that arm — six secondaries on the
         inner half, seven primaries on the hand.  Their tips trace a smooth concave
         trailing edge, exactly like an angel-wing silhouette.
       - Every feather is a FLAT LANCE PLATE (a real vane, not a comb of bolts) built
         from 5 overlapping axis-aligned segments that taper root -> tip, so the
         silhouette is a proper feather and not a rectangle.
       - THE FEATHERS ARE FANNED BY BONE ROTATION, not by cube rotation.  Each feather
         sits on its own bone whose `idle` keyframes carry the fan angle
         (`rotateZYX = Rz.Ry.Rx`).  Keyframes are used (and not the static
         `bone.rotation`) on purpose: ModelEngine 4.1.0 applies the animation on top of
         the blueprint pose, so this is correct whether it composes or replaces, and it
         keeps **every single cube at rotation [0,0,0]** — the rule that keeps
         ModelEngine's `RotationSolver` (it crashes on Paper's fastutil) out of the
         pipeline.
       - Zeus identity is kept by the MATERIAL, not by the silhouette: the feathers are
         storm-cloud blue with a white-hot quill and electric tips, a thunderhead boils
         between the shoulder blades and on each shoulder joint, and two spark clusters
         crackle above the blades.
  2. Texture v4 — 256x256 (was 128x128), 16 hand-painted 56x56 tiles on a 16x16 UV grid.
     Every tile is a SMOOTH multi-stop ramp modulated by two low-frequency sines and
     finished with a 4x4 Bayer dither, so the 8-bit gradients never band.  The feather
     tiles carry a bright quill, fine barb streaks and a glowing tip; the cloud tiles are
     soft volumetric puffs.  Palette stays COLD (per the player's pick): white-hot core,
     ice cyan, electric blue, storm indigo.  Zero warm/gold pixels.
  3. Motion (seamless 4.8 s loop, 65 keyframes @ ~13.5 fps):
       - Whole-wing beat on the empty group bones: `+-5.5 deg` flap, `+2.4 deg`
         double-time shudder, `+-3 deg` sweep, `+-0.8 deg` crackle jitter.
       - Every feather ripples on its own phase, amplitude growing toward the wingtip
         (`1.1 -> 3.0 deg`), so the wing breathes like plumage instead of flapping a slab.
       - The arm lags the beat, the clouds boil, the sparks tumble a full turn per loop.
  4. Engine safety:
       - **Not a single cube is rotated** — every fan angle lives on a bone keyframe.
       - Every cube corner stays inside 23 BB of its own bone pivot (ModelEngine's
         `scaleToFit()` budget is 24).
       - `16.0` BB units = `1.0` block: feet `0.00`, waist `11.25`, neck/shoulders
         `22.50`, bare skull top `30.00`, `+Z` is the player's back.  The whole wing
         plane sits at `z ~ 3.5..3.8`, i.e. just BEHIND the back surface (`|z| <= 3.48`
         torso, `3.35` arms), so no feather is ever buried inside the player.
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

IDLE_LEN = 4.8       # 96 ticks @ 20 TPS — seamless beat + feather ripple loop
IDLE_STEPS = 64      # 65 keyframes

TEX = 256            # texture is 256x256 on a 16x16 UV grid -> 16 px per UV unit

# Shoulder-blade pivot of the storm cloud that the wings erupt from.
ROOT_ORIG = [0.0, 22.0, 1.9]

# ---------------------------------------------------------------------------
# 1. The wing skeleton
# ---------------------------------------------------------------------------
# Arm / leading edge of the RIGHT wing (the left one is the X mirror).  It leaves the
# shoulder blade, crests over the wrist (the highest point of the wing) and sweeps down
# and out to the wingtip.  `z` stays just behind the back the whole way.
# `z` is CONSTANT: the whole wing plane sits 3.68 BB behind the player's centre line,
# i.e. just clear of the back surface (torso `|z| <= 3.48`, arms `3.35`).  The depth
# layering of the plumage comes from FEATHER_SHINGLE, not from tilting the spar — a
# tilted vane would smear across several shingle steps and start z-fighting.
ARM_Z = 3.68
ARM = [
    (1.15, 21.60, ARM_Z),     # 0  shoulder
    (3.00, 22.40, ARM_Z),
    (4.95, 23.05, ARM_Z),
    (6.95, 23.60, ARM_Z),
    (9.00, 23.95, ARM_Z),     # 4  WRIST — highest point of the wing
    (11.10, 23.85, ARM_Z),
    (13.20, 23.20, ARM_Z),
    (15.30, 22.15, ARM_Z),
    (17.30, 20.70, ARM_Z),
    (19.20, 19.00, ARM_Z),
    (21.30, 16.90, ARM_Z),    # 10 wingtip
]
ARM_PIVOT_I = 4              # the arm bone pivots on the wrist
ARM_HALF = (0.52, 0.17)      # half thickness at the shoulder -> at the tip

# Feather rows: (s along the arm, tip x, tip y, tip dz, half width).
# `s` is the normalised arc length along ARM; the tip is given in absolute model
# coordinates so the trailing edge can be sculpted directly.
# `dz` is deliberately 0 everywhere: a tilted vane would span more Z than the
# 0.10 BB shingle step below, and neighbouring feathers would start z-fighting.
SECONDARIES = (
    (0.040, 2.60, 18.10, 0.00, 0.95),
    (0.100, 4.20, 16.85, 0.00, 0.98),
    (0.160, 5.90, 16.05, 0.00, 1.01),
    (0.220, 7.60, 15.55, 0.00, 1.04),
    (0.280, 9.30, 15.25, 0.00, 1.07),
    (0.340, 11.05, 15.15, 0.00, 1.10),
)
PRIMARIES = (
    (0.420, 12.90, 15.20, 0.00, 1.30),
    (0.510, 15.30, 14.30, 0.00, 1.34),
    (0.600, 17.70, 13.50, 0.00, 1.36),
    (0.690, 20.00, 12.90, 0.00, 1.34),
    (0.780, 22.00, 12.50, 0.00, 1.28),
    (0.870, 23.20, 12.30, 0.00, 1.16),
    (0.960, 24.00, 12.20, 0.00, 0.95),
)
FEATHERS = tuple(('sec',) + row for row in SECONDARIES) + \
           tuple(('pri',) + row for row in PRIMARIES)
FEATHER_COUNT = len(FEATHERS)

# One feather = 5 overlapping segments (start, end, width factor) along its own axis.
FEATHER_SEGS = (
    (0.000, 0.24, 1.00),
    (0.200, 0.52, 0.98),
    (0.480, 0.78, 0.88),
    (0.740, 0.95, 0.66),
    (0.910, 1.00, 0.30),
)
FEATHER_THICK = 0.06        # the vane is a thin plate (half 0.03)
FEATHER_SHINGLE = 0.10      # each feather sits 0.10 BB behind the one in front of
                            # it, so overlapping vanes can never z-fight

# Shoulder thunderhead puffs (offset from the arm's shoulder point, +Z is back).
SHOULDER_PUFF = (1.50, 22.30, 3.85)
SHOULDER_PUFFS = (
    (-0.95, 0.80, -0.30, 1.35, 0.55, 0.50),
    (0.10, 1.15, -0.25, 1.30, 0.35, 0.55),
    (1.00, 0.75, -0.10, 0.90, 0.45, 0.40),
    (-0.40, 0.25, -0.22, 1.05, -0.40, 0.48),
    (0.40, 1.55, -0.15, 0.60, 0.50, 0.34),
)

# Storm cloud boiling between the shoulder blades (model space, +Z is the back).
ROOT_CLOUD = (
    (-2.90, 22.55, 1.60, -0.90, 21.40, 3.10),
    (0.90, 22.55, 1.60, 2.90, 21.40, 3.10),
    (-1.95, 23.45, 1.40, 1.95, 22.15, 3.15),
    (-3.40, 21.95, 1.85, -1.70, 21.05, 2.80),
    (1.70, 21.95, 1.85, 3.40, 21.05, 2.80),
    (-0.75, 21.65, 1.50, 0.75, 20.60, 3.25),
)

# Two short feeder bolts: storm cloud -> each shoulder joint.
FEEDER = [(-1.80, 23.00, 2.80), (-0.60, 22.10, 2.70), (0.45, 21.25, 2.60),
          (1.15, 21.60, 3.55)]

# Spark clusters crackling along the leading edge, just above the arm and clear of
# the head box (|x| < 4.55 for y > 24).
SPARKS = ((6.20, 24.90, 3.85), (-6.20, 24.90, 3.85))


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.uuid5(uuid.NAMESPACE_OID, 'elytrix.zeus_wings.v4'), tag))


# ---------------------------------------------------------------------------
# 2. Texture v4 — 256x256, 16 tiles of 56x56 px on a 16x16 UV grid
# ---------------------------------------------------------------------------
# Tile rects are (u0, v0, u1, v1) in UV units; 1 UV = 16 px, each tile keeps a 4 px
# margin so neighbouring tiles can never bleed into each other.
def _tile(tx: int, ty: int) -> tuple:
    return (tx * 4 + 0.25, ty * 4 + 0.25, tx * 4 + 3.75, ty * 4 + 3.75)


UV_PRI_FACE = _tile(0, 0)     # primary feather vane (the showpiece)
UV_SEC_FACE = _tile(1, 0)     # secondary feather vane — softer, cooler
UV_VANE_EDGE = _tile(2, 0)    # the thin edge faces of a feather
UV_QUILL = _tile(3, 0)        # bright quill / rim-light strip
UV_CLOUD_TOP = _tile(0, 1)    # sunlit thunderhead
UV_CLOUD_MID = _tile(1, 1)    # body of the thunderhead
UV_CLOUD_DEEP = _tile(2, 1)   # shadowed underside
UV_SPARK = _tile(3, 1)        # radial white-hot spark
UV_ARM = _tile(0, 2)          # the wing bone / leading edge
UV_ARM_CORE = _tile(1, 2)     # white-hot spine of the arm
UV_TIP_GLOW = _tile(2, 2)     # glowing feather tip
UV_DOWN = _tile(3, 2)         # soft down / small covert feather
UV_BOLT = _tile(0, 3)         # lightning streak (feeder arcs)
UV_MEMBRANE = _tile(1, 3)     # dark under-vane
UV_RIM = _tile(2, 3)          # cool rim light
UV_CORE = _tile(3, 3)         # pure white-hot core

_BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))

# Cold Zeus palette — white-hot core -> ice -> electric blue -> storm indigo.
C_WHITE = (255, 255, 255)
C_ICE = (226, 246, 255)
C_PALE = (168, 224, 255)
C_LIT = (96, 178, 246)
C_MID = (42, 104, 200)
C_EDGE = (26, 44, 108)
C_DEEP = (14, 22, 62)
C_NIGHT = (8, 12, 38)


def _ramp(stops, t: float):
    if t <= stops[0][0]:
        return stops[0][1]
    if t >= stops[-1][0]:
        return stops[-1][1]
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p0 <= t <= p1:
            k = (t - p0) / (p1 - p0)
            return tuple(c0[j] + (c1[j] - c0[j]) * k for j in range(3))
    return stops[-1][1]


def _smooth(a: float, b: float, x: float) -> float:
    t = 0.0 if b <= a else max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def _mix(c0, c1, k: float):
    k = max(0.0, min(1.0, k))
    return tuple(c0[j] + (c1[j] - c0[j]) * k for j in range(3))


def build_zeus_texture() -> Image.Image:
    arr = np.zeros((TEX, TEX, 4), dtype=np.uint8)

    def paint(tile: tuple, fn) -> None:
        u0, v0, u1, v1 = tile
        x0, y0 = int(round(u0 * 16.0)), int(round(v0 * 16.0))
        w = int(round(u1 * 16.0)) - x0
        h = int(round(v1 * 16.0)) - y0
        for py in range(h):
            for px in range(w):
                u = (px + 0.5) / w
                v = (py + 0.5) / h
                col = fn(u, v)
                dith = (_BAYER4[py & 3][px & 3] / 16.0 - 0.46875) * 1.3
                arr[y0 + py, x0 + px] = (
                    max(0, min(255, int(round(col[0] + dith)))),
                    max(0, min(255, int(round(col[1] + dith)))),
                    max(0, min(255, int(round(col[2] + dith)))),
                    255,
                )

    # ---- Feather vane -----------------------------------------------------
    # u = along the feather (0 root -> 1 tip), v = across it (0.5 = the quill).
    def vane(u: float, v: float, primary: bool) -> tuple:
        q = abs(v - 0.5) * 2.0                      # 0 at the quill, 1 at the edge
        # fine barb streaks running from the quill outwards and towards the tip
        barb = (0.078 * math.sin((u * 15.5 - q * 6.5) * math.pi)
                + 0.044 * math.sin((u * 28.0 + q * 10.5) * math.pi + 1.3)
                + 0.026 * math.sin((u * 47.0 - q * 17.0) * math.pi + 0.4))
        t = max(0.0, min(1.0, q + barb))
        if primary:
            col = _ramp([(0.00, C_WHITE), (0.10, C_ICE), (0.26, C_PALE),
                         (0.50, C_LIT), (0.76, C_MID), (1.00, C_DEEP)], t)
        else:
            col = _ramp([(0.00, C_ICE), (0.13, C_PALE), (0.32, C_LIT),
                         (0.58, C_MID), (0.82, C_EDGE), (1.00, C_NIGHT)], t)
        # the root sits in the shadow of the feather in front of it
        col = _mix(C_NIGHT, col, 0.62 + 0.38 * _smooth(0.0, 0.13, u))
        # every feather is a little brighter on the leading (low-v) half
        col = _mix(col, C_ICE, 0.10 * (1.0 - _smooth(0.35, 0.95, v)))
        # the tip burns out into pure light
        col = _mix(col, C_WHITE, 0.48 * _smooth(0.84, 1.0, u))
        # a crisp dark rim so every feather keeps a readable outline
        col = _mix(col, C_NIGHT, 0.58 * _smooth(0.90, 1.0, q))
        # a white-hot quill line down the middle
        quill = (1.0 - _smooth(0.022, 0.095, q)) * (0.58 + 0.42 * _smooth(0.75, 0.05, u))
        col = _mix(col, C_WHITE, 0.88 * quill)
        return col

    paint(UV_PRI_FACE, lambda u, v: vane(u, v, True))
    paint(UV_SEC_FACE, lambda u, v: vane(u, v, False))

    # ---- Thin edge faces of the vane -------------------------------------
    def edge(u: float, v: float) -> tuple:
        t = max(0.0, min(1.0, v + 0.05 * math.sin(u * 22.0 * math.pi)))
        col = _ramp([(0.00, C_PALE), (0.22, C_LIT), (0.55, C_EDGE), (1.00, C_NIGHT)], t)
        return _mix(col, C_WHITE, 0.45 * _smooth(0.88, 1.0, u))

    paint(UV_VANE_EDGE, edge)

    # ---- Quill / rim-light strip -----------------------------------------
    def quill(u: float, v: float) -> tuple:
        t = abs(v - 0.5) * 2.0
        col = _ramp([(0.00, C_WHITE), (0.18, C_ICE), (0.46, C_PALE),
                     (0.72, C_LIT), (1.00, C_EDGE)], t)
        return _mix(col, C_WHITE, 0.30 * _smooth(0.85, 1.0, u))

    paint(UV_QUILL, quill)

    # ---- Storm cloud ------------------------------------------------------
    def cloud(u: float, v: float, stops, grain: float) -> tuple:
        t = max(0.0, min(1.0,
                         v * 0.82 + 0.20
                         + grain * math.sin(u * 7.3 + v * 4.1)
                         + 0.6 * grain * math.sin(u * 3.1 - v * 6.7 + 1.1)))
        return _ramp(stops, t)

    paint(UV_CLOUD_TOP, lambda u, v: cloud(
        u, v, [(0.00, C_WHITE), (0.20, C_ICE), (0.48, C_PALE),
               (0.76, C_LIT), (1.00, C_MID)], 0.055))
    paint(UV_CLOUD_MID, lambda u, v: cloud(
        u, v, [(0.00, C_PALE), (0.24, C_LIT), (0.55, C_MID),
               (0.82, C_EDGE), (1.00, C_DEEP)], 0.060))
    paint(UV_CLOUD_DEEP, lambda u, v: cloud(
        u, v, [(0.00, C_LIT), (0.26, C_MID), (0.58, C_EDGE),
               (0.84, C_DEEP), (1.00, C_NIGHT)], 0.055))

    # ---- Radial spark -----------------------------------------------------
    def spark(u: float, v: float) -> tuple:
        d = math.hypot(u - 0.5, v - 0.5) * 2.0
        t = max(0.0, min(1.0, d * 1.05 + 0.05 * math.sin(u * 19.0 + v * 13.0)))
        return _ramp([(0.00, C_WHITE), (0.22, C_ICE), (0.48, C_PALE),
                      (0.74, C_LIT), (1.00, C_MID)], t)

    paint(UV_SPARK, spark)

    # ---- Wing bone / leading edge ----------------------------------------
    def arm(u: float, v: float) -> tuple:
        t = abs(v - 0.5) * 2.0 + 0.04 * math.sin(u * 26.0 * math.pi)
        col = _ramp([(0.00, C_ICE), (0.20, C_PALE), (0.48, C_LIT),
                     (0.78, C_MID), (1.00, C_EDGE)], max(0.0, min(1.0, t)))
        return _mix(col, C_WHITE, 0.22 * (1.0 - _smooth(0.0, 0.35, u)))

    paint(UV_ARM, arm)

    def arm_core(u: float, v: float) -> tuple:
        t = abs(v - 0.5) * 2.0
        return _ramp([(0.00, C_WHITE), (0.22, C_ICE), (0.52, C_PALE),
                      (0.80, C_LIT), (1.00, C_MID)], max(0.0, min(1.0, t)))

    paint(UV_ARM_CORE, arm_core)

    # ---- Feather tip glow -------------------------------------------------
    def tip(u: float, v: float) -> tuple:
        d = math.hypot((u - 0.18) * 0.85, (v - 0.5) * 2.0)
        t = max(0.0, min(1.0, d + 0.04 * math.sin(v * 21.0)))
        return _ramp([(0.00, C_WHITE), (0.20, C_ICE), (0.45, C_PALE),
                      (0.72, C_LIT), (1.00, C_MID)], t)

    paint(UV_TIP_GLOW, tip)

    # ---- Soft down / covert ----------------------------------------------
    def down(u: float, v: float) -> tuple:
        t = max(0.0, min(1.0, v * 0.85 + 0.10
                         + 0.07 * math.sin(u * 11.0 + v * 7.5)
                         + 0.05 * math.sin(u * 23.0 - v * 5.0)))
        col = _ramp([(0.00, C_ICE), (0.22, C_PALE), (0.50, C_LIT),
                     (0.78, C_MID), (1.00, C_DEEP)], t)
        return _mix(col, C_WHITE, 0.16 * _smooth(0.80, 1.0, u))

    paint(UV_DOWN, down)

    # ---- Lightning streak -------------------------------------------------
    def bolt(u: float, v: float) -> tuple:
        t = abs(v - 0.5) * 2.0
        return _ramp([(0.00, C_WHITE), (0.16, C_ICE), (0.40, C_PALE),
                      (0.68, C_LIT), (1.00, C_MID)], max(0.0, min(1.0, t)))

    paint(UV_BOLT, bolt)

    # ---- Dark under-vane --------------------------------------------------
    def membrane(u: float, v: float) -> tuple:
        t = max(0.0, min(1.0, v * 0.9 + 0.06 + 0.04 * math.sin(u * 17.0)))
        return _ramp([(0.00, C_LIT), (0.24, C_MID), (0.56, C_EDGE),
                      (0.82, C_DEEP), (1.00, C_NIGHT)], t)

    paint(UV_MEMBRANE, membrane)

    # ---- Cool rim light ---------------------------------------------------
    def rim(u: float, v: float) -> tuple:
        t = max(0.0, min(1.0, v + 0.03 * math.sin(u * 15.0)))
        return _ramp([(0.00, C_ICE), (0.28, C_PALE), (0.58, C_LIT),
                      (0.84, C_MID), (1.00, C_EDGE)], t)

    paint(UV_RIM, rim)

    # ---- Pure core --------------------------------------------------------
    def core(u: float, v: float) -> tuple:
        t = math.hypot(u - 0.5, v - 0.5) * 1.9
        return _ramp([(0.00, C_WHITE), (0.45, C_ICE), (0.78, C_PALE),
                      (1.00, C_LIT)], max(0.0, min(1.0, t)))

    paint(UV_CORE, core)

    return Image.fromarray(arr, 'RGBA')


# ---------------------------------------------------------------------------
# 3. Cube helpers (NO cube is ever rotated — ModelEngine 4.1.0 safe)
# ---------------------------------------------------------------------------
SIDES = ('north', 'east', 'south', 'west', 'up', 'down')


def _faces(default_uv: tuple, **overrides) -> dict:
    out = {}
    for side in SIDES:
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
        'inflate': 0.0,
        'mirror_uv': False,
        'origin': [round(float(v), 4) for v in origin],
        'rotation': [0.0, 0.0, 0.0],
        'faces': faces,
        'type': 'cube',
        'uuid': uid(f'cube:{name}'),
    }


def _slice_u(tile: tuple, f0: float, f1: float) -> tuple:
    """The sub-rect of `tile` covering the feather-length fraction [f0, f1]."""
    return (round(tile[0] + (tile[2] - tile[0]) * f0, 4), tile[1],
            round(tile[0] + (tile[2] - tile[0]) * f1, 4), tile[3])


# ---------------------------------------------------------------------------
# 4. Geometry: the arm polyline, the feathers, the clouds
# ---------------------------------------------------------------------------
_ARM_CUM = [0.0]
for _i in range(1, len(ARM)):
    _ARM_CUM.append(_ARM_CUM[-1] + math.dist(ARM[_i - 1][:2], ARM[_i][:2]))
_ARM_LEN = _ARM_CUM[-1]


def arm_at(s: float) -> tuple:
    """Point on the leading edge at normalised arc length `s`."""
    d = max(0.0, min(1.0, s)) * _ARM_LEN
    i = min(len(_ARM_CUM) - 2, max(0, int(np.searchsorted(_ARM_CUM, d)) - 1))
    span = _ARM_CUM[i + 1] - _ARM_CUM[i] or 1.0
    f = (d - _ARM_CUM[i]) / span
    a, b = ARM[i], ARM[i + 1]
    return tuple(a[k] + (b[k] - a[k]) * f for k in range(3))


def feather_spec(i: int) -> dict:
    """Root, tip, length, half-width and fan angles of feather `i` (right wing)."""
    row, s, tx, ty, tdz, hw = FEATHERS[i]
    root = arm_at(s)
    # Shingle: feather `i` sits a little further back than feather `i - 1`, so the
    # overlapping vanes never share a depth plane (no z-fighting on the wing).
    rz = root[2] + i * FEATHER_SHINGLE
    tz = rz + tdz
    dx, dy, dz = tx - root[0], ty - root[1], tdz
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    # ModelEngine builds the bone quaternion as Rz.Ry.Rx, so local +X ends up along
    #   d = (cos t * cos p, sin t, -cos t * sin p)
    # Invert that for the direction we want the feather to point.
    horiz = math.sqrt(dx * dx + dy * dy) or 1e-9
    theta = math.atan2(dy, dx)                       # Z rotation: the fan angle
    phi = math.atan2(-dz, horiz)                     # Y rotation: backward sweep
    return {
        'row': row,
        'root': (root[0], root[1], rz),
        'tip': (tx, ty, tz),
        'length': length,
        'hw': hw,
        'theta': math.degrees(theta),
        'phi': math.degrees(phi),
    }


FEATHER_SPECS = [feather_spec(i) for i in range(FEATHER_COUNT)]
SEC_IDS = [f'sec_r{i + 1:02d}' for i in range(len(SECONDARIES))] + \
          [f'sec_l{i + 1:02d}' for i in range(len(SECONDARIES))]
PRI_IDS = [f'pri_r{i + 1:02d}' for i in range(len(PRIMARIES))] + \
          [f'pri_l{i + 1:02d}' for i in range(len(PRIMARIES))]
FEATHER_IDS = SEC_IDS + PRI_IDS
ARM_IDS = ('arm_r', 'arm_l')
SHOULDER_IDS = ('shoulder_r', 'shoulder_l')
SPARK_IDS = ('spark_r', 'spark_l')
BONE_NAMES = ['zeus_root', 'wing_r', 'wing_l'] + list(ARM_IDS) + \
             list(SHOULDER_IDS) + FEATHER_IDS + list(SPARK_IDS) + ['hitbox']


def _mirror_x(p) -> list:
    return [round(-p[0], 4), round(p[1], 4), round(p[2], 4)]


def feather_cubes(side: str, i: int) -> list:
    """The 5 tapered segments of one feather, laid out UNROTATED along local X.

    The bone's `idle` keyframes carry the fan angle, so nothing here is rotated.
    """
    spec = FEATHER_SPECS[i]
    rx, ry, rz = spec['root']
    dirx = -1.0 if side == 'l' else 1.0
    # For the left wing the root is the X mirror and the feather runs towards -X.
    if side == 'l':
        rx = -rx
    hw = spec['hw']
    ht = FEATHER_THICK / 2.0
    face_tile = UV_PRI_FACE if spec['row'] == 'pri' else UV_SEC_FACE
    cubes = []
    for k, (f0, f1, wf) in enumerate(FEATHER_SEGS):
        a = spec['length'] * f0
        b = spec['length'] * f1
        w = hw * wf
        xa, xb = rx + dirx * a, rx + dirx * b
        lo = [min(xa, xb), ry - w, rz - ht]
        hi = [max(xa, xb), ry + w, rz + ht]
        root_side_u = (dirx > 0.0)                 # is the low-x end the root?
        north = _slice_u(face_tile, f0, f1)
        if not root_side_u:
            north = (north[2], north[1], north[0], north[3])
        south = (north[2], north[1], north[0], north[3])
        rim = _slice_u(UV_QUILL, f0, f1)
        edge = _slice_u(UV_VANE_EDGE, f0, f1)
        faces = {
            'north': {'uv': list(north), 'texture': 0},
            'south': {'uv': list(south), 'texture': 0},
            'up': {'uv': list(rim), 'texture': 0},
            'down': {'uv': list(edge), 'texture': 0},
            'east': {'uv': list(UV_TIP_GLOW if f1 >= 0.999 else edge), 'texture': 0},
            'west': {'uv': list(UV_MEMBRANE if f0 <= 0.001 else UV_VANE_EDGE),
                     'texture': 0},
        }
        if side == 'l':
            # east/west swap because the plate runs towards -X
            faces['east'], faces['west'] = faces['west'], faces['east']
        cubes.append(_cube(f'{_feather_bone_name(side, i)}_{k}',
                           lo, hi, [rx, ry, rz], faces))
    return cubes


def _feather_bone_name(side: str, i: int) -> str:
    row, idx = ('sec', i) if i < len(SECONDARIES) else ('pri', i - len(SECONDARIES))
    return f'{row}_{side}{idx + 1:02d}'


def arm_cubes(side: str) -> list:
    """The wing bone: an L-stepped tapered bar along the leading edge."""
    pts = [p if side == 'r' else (-p[0], p[1], p[2]) for p in ARM]
    cubes = []
    n = len(pts)
    for i in range(n - 1):
        f = i / (n - 2)
        t = ARM_HALF[0] + (ARM_HALF[1] - ARM_HALF[0]) * f
        (x0, y0, z0), (x1, y1, z1) = pts[i], pts[i + 1]
        faces = _faces(UV_ARM, up=UV_ARM_CORE, down=UV_CLOUD_DEEP)
        cubes.append(_cube(f'arm_{side}_h{i:02d}',
                           [min(x0, x1) - 0.0, y0 - t, z0 - t],
                           [max(x0, x1) + 0.0, y0 + t, z0 + t],
                           pts[ARM_PIVOT_I], faces))
        cubes.append(_cube(f'arm_{side}_v{i:02d}',
                           [x1 - t, min(y0, y1), z1 - t],
                           [x1 + t, max(y0, y1), z1 + t],
                           pts[ARM_PIVOT_I], faces))
    return cubes


def build_geometry(elements: list) -> dict:
    bones: dict[str, list] = {name: [] for name in BONE_NAMES}

    def add(cube: dict) -> str:
        elements.append(cube)
        return cube['uuid']

    # --- zeus_root: the thunderhead between the shoulder blades + 2 feeder arcs ---
    root_cubes = []
    for i, (x0, y0, z0, x1, y1, z1) in enumerate(ROOT_CLOUD):
        f = i / max(1, len(ROOT_CLOUD) - 1)
        tile = UV_CLOUD_TOP if f < 0.34 else (UV_CLOUD_MID if f < 0.72 else UV_CLOUD_DEEP)
        root_cubes.append(_cube(f'cloud_{i:02d}', [x0, y0, z0], [x1, y1, z1],
                                ROOT_ORIG, _faces(tile, up=UV_CLOUD_TOP,
                                                  down=UV_CLOUD_DEEP)))
    for side, sgn in (('r', 1.0), ('l', -1.0)):
        pts = [(sgn * x, y, z) for (x, y, z) in FEEDER]
        for i in range(len(pts) - 1):
            (x0, y0, z0), (x1, y1, z1) = pts[i], pts[i + 1]
            root_cubes.append(_cube(
                f'feed_{side}_{i}',
                [min(x0, x1) - 0.14, min(y0, y1) - 0.14, min(z0, z1) - 0.14],
                [max(x0, x1) + 0.14, max(y0, y1) + 0.14, max(z0, z1) + 0.14],
                ROOT_ORIG, _faces(UV_BOLT, east=UV_CORE, west=UV_CORE)))
    bones['zeus_root'] = [add(c) for c in root_cubes]

    # --- wing_r / wing_l: empty group bones carrying the whole-wing beat ---
    for side in ('r', 'l'):
        cubes = arm_cubes(side)
        bones[f'arm_{side}'] = [add(c) for c in cubes]

        sp = SHOULDER_PUFF
        pivot = [sp[0] if side == 'r' else -sp[0], sp[1], sp[2]]
        puffs = []
        for i, (dx0, dy0, dz0, dx1, dy1, dz1) in enumerate(SHOULDER_PUFFS):
            sx = -1.0 if side == 'l' else 1.0
            x0, x1 = pivot[0] + sx * dx0, pivot[0] + sx * dx1
            tile = UV_CLOUD_TOP if i % 3 == 0 else (UV_CLOUD_MID if i % 3 == 1
                                                    else UV_CLOUD_DEEP)
            puffs.append(_cube(f'puff_{side}_{i:02d}',
                               [min(x0, x1), pivot[1] + min(dy0, dy1), pivot[2] + dz0],
                               [max(x0, x1), pivot[1] + max(dy0, dy1), pivot[2] + dz1],
                               pivot, _faces(tile, up=UV_CLOUD_TOP, down=UV_CLOUD_DEEP)))
        bones[f'shoulder_{side}'] = [add(c) for c in puffs]

        for i in range(FEATHER_COUNT):
            bones[_feather_bone_name(side, i)] = [add(c) for c in feather_cubes(side, i)]

    # --- spark clusters above each shoulder blade ---
    for side, (sx, sy, sz) in (('r', SPARKS[0]), ('l', SPARKS[1])):
        pivot = [round(float(sx), 4), round(float(sy), 4), round(float(sz), 4)]
        spark = []
        for m in range(4):
            ang = math.radians(m * 90.0 + 22.0)
            ox, oy = 0.95 * math.sin(ang), 0.95 * math.cos(ang)
            spark.append(_cube(f'spark_{side}_{m}',
                               [pivot[0] + ox - 0.19, pivot[1] + oy - 0.19, pivot[2] - 0.19],
                               [pivot[0] + ox + 0.19, pivot[1] + oy + 0.19, pivot[2] + 0.19],
                               pivot, _faces(UV_SPARK)))
        spark.append(_cube(f'spark_{side}_core',
                           [pivot[0] - 0.26, pivot[1] - 0.26, pivot[2] - 0.26],
                           [pivot[0] + 0.26, pivot[1] + 0.26, pivot[2] + 0.26],
                           pivot, _faces(UV_CORE)))
        bones[f'spark_{side}'] = [add(c) for c in spark]

    return bones


# ---------------------------------------------------------------------------
# 5. Seamless 4.8 s animation — this is also where the fan angles live
# ---------------------------------------------------------------------------
TAU = 2.0 * math.pi


def eval_zeus_pose(u: float) -> dict:
    """Bone transforms at normalised phase u in [0, 1] (u = 1.0 closes the loop).

    Feather rotations are ABSOLUTE fan angles plus a small ripple: ModelEngine applies
    the animation on top of the blueprint pose, and every blueprint bone here has
    rotation [0,0,0], so the result is correct whichever way it composes.
    """
    up = 0.0 if u >= 1.0 else u

    pose = {
        'root_pos': [0.0, round(0.13 * math.sin(TAU * up), 4), 0.0],
        'root_rot': [round(0.7 * math.sin(TAU * up + 0.9), 4), 0.0,
                     round(1.0 * math.sin(TAU * up), 4)],
        'wing_rot': {},
        'arm_rot': {},
        'shoulder_scale': {},
        'feather_rot': {},
        'feather_scale': {},
        'spark_rot': {},
        'spark_scale': {},
    }

    flap = 5.5 * math.sin(TAU * up) + 2.4 * math.sin(TAU * 2.0 * up + 1.1)
    jitter = 0.8 * math.sin(TAU * 8.0 * up + 0.6)
    sweep = 3.0 * math.sin(TAU * up + 0.35)
    pose['wing_rot']['wing_r'] = [0.0, round(sweep, 4), round(flap + jitter, 4)]
    pose['wing_rot']['wing_l'] = [0.0, round(-sweep, 4), round(-(flap + jitter), 4)]

    for side, sign in (('r', 1.0), ('l', -1.0)):
        phase = 0.0 if side == 'r' else math.pi

        # the arm is the wing's spar: it lags the beat and crackles
        lag = 2.4 * math.sin(TAU * up + 0.30 + phase)
        crackle = 1.1 * math.sin(TAU * 7.0 * up + 0.4)
        pose['arm_rot'][f'arm_{side}'] = [round(0.6 * crackle, 4),
                                          round(0.4 * crackle, 4),
                                          round(sign * (lag + crackle), 4)]

        # the shoulder thunderhead slowly boils
        boil = (0.055 * math.sin(TAU * 2.0 * up + 1.15 + phase)
                + 0.030 * math.sin(TAU * 5.0 * up + 2.3 + phase))
        s = round(1.0 + boil, 4)
        pose['shoulder_scale'][f'shoulder_{side}'] = [s, round(1.0 - 0.45 * boil, 4), s]

        for i in range(FEATHER_COUNT):
            spec = FEATHER_SPECS[i]
            name = _feather_bone_name(side, i)
            # the ripple grows towards the wingtip so the plumage "breathes"
            amp = 1.1 + 1.9 * (i / max(1, FEATHER_COUNT - 1))
            ripple = amp * math.sin(TAU * up + 0.55 * i + phase)
            shiver = 0.7 * math.sin(TAU * 5.0 * up + i * 1.7)
            th = spec['theta'] + sign * 0.0 + ripple + shiver
            ph = spec['phi'] * (1.0 if side == 'r' else -1.0)
            pose['feather_rot'][name] = [
                round(0.4 * shiver, 4),
                round(ph + 0.35 * math.sin(TAU * up + 0.4 * i + phase), 4),
                round(th if side == 'r' else -th, 4),
            ]
            beat = (up - i * 0.055 - (0.0 if side == 'r' else 0.5)) % 1.0
            pulse = math.exp(-((beat - 0.5) / 0.18) ** 2)
            fs = round(1.0 + 0.015 * math.sin(TAU * up + i) + 0.05 * pulse, 4)
            pose['feather_scale'][name] = [fs, round(1.0 + 0.02 * pulse, 4), fs]

        pose['spark_rot'][f'spark_{side}'] = [0.0, round(360.0 * u, 4), 0.0]
        beat = (up - (0.0 if side == 'r' else 0.5)) % 1.0
        sp = 0.55 + 0.65 * (max(0.0, math.sin(TAU * 3.0 * beat)) ** 3)
        pose['spark_scale'][f'spark_{side}'] = [round(sp, 4)] * 3

    return pose


def _vec_kf(channel: str, tag: str, t: float, x: float, y: float, z: float) -> dict:
    t_r = round(float(t), 4)
    return {
        'channel': channel,
        'data_points': [{'x': str(round(x, 4)), 'y': str(round(y, 4)),
                         'z': str(round(z, 4))}],
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
        for name in ARM_IDS:
            kfs[name].append(_vec_kf('rotation', f'idle:{name}', t, *pose['arm_rot'][name]))
        for name in SHOULDER_IDS:
            kfs[name].append(_vec_kf('scale', f'idle:{name}', t,
                                      *pose['shoulder_scale'][name]))
        for name in FEATHER_IDS:
            kfs[name].append(_vec_kf('rotation', f'idle:{name}', t,
                                      *pose['feather_rot'][name]))
            kfs[name].append(_vec_kf('scale', f'idle:{name}', t,
                                      *pose['feather_scale'][name]))
        for name in SPARK_IDS:
            kfs[name].append(_vec_kf('rotation', f'idle:{name}', t, *pose['spark_rot'][name]))
            kfs[name].append(_vec_kf('scale', f'idle:{name}', t, *pose['spark_scale'][name]))

    return {uid(f'bone:{b}'): {'name': b, 'type': 'bone', 'keyframes': kfs[b]}
            for b in BONE_NAMES if kfs[b]}


# ---------------------------------------------------------------------------
# 6. Blueprint builder
# ---------------------------------------------------------------------------
def build_blueprint() -> tuple[dict, Image.Image]:
    texture = build_zeus_texture()
    raw = io.BytesIO()
    texture.save(raw, format='PNG', optimize=True)

    elements: list[dict] = []
    bones = build_geometry(elements)

    def bone(name: str, origin: list, children: list, visible: bool = True) -> dict:
        return {
            'name': name,
            'origin': [round(float(v), 4) for v in origin],
            'rotation': [0.0, 0.0, 0.0],
            'color': 0,
            'uuid': uid(f'bone:{name}'),
            'export': True,
            'mirror_uv': False,
            'isOpen': False,
            'locked': False,
            'visibility': visible,
            'autouv': 0,
            'children': children,
        }

    def wing_group(side: str) -> dict:
        sx = 1.0 if side == 'r' else -1.0
        pivot = [round(sx * ARM[0][0], 4), round(ARM[0][1], 4), round(ARM[0][2], 4)]
        arm_pivot = [round(sx * ARM[ARM_PIVOT_I][0], 4),
                     round(ARM[ARM_PIVOT_I][1], 4), round(ARM[ARM_PIVOT_I][2], 4)]
        sp = SHOULDER_PUFF
        sh_pivot = [round(sx * sp[0], 4), round(sp[1], 4), round(sp[2], 4)]
        kids = [
            bone(f'arm_{side}', arm_pivot, bones[f'arm_{side}']),
            bone(f'shoulder_{side}', sh_pivot, bones[f'shoulder_{side}']),
        ]
        for i in range(FEATHER_COUNT):
            spec = FEATHER_SPECS[i]
            fpx = sx * spec['root'][0]
            kids.append(bone(_feather_bone_name(side, i),
                             [round(fpx, 4), round(spec['root'][1], 4),
                              round(spec['root'][2], 4)],
                             bones[_feather_bone_name(side, i)]))
        return bone(f'wing_{side}', pivot, kids)

    outliner = [
        bone('zeus_root', ROOT_ORIG, [
            *bones['zeus_root'],
            wing_group('r'),
            wing_group('l'),
            bone('spark_r', list(SPARKS[0]), bones['spark_r']),
            bone('spark_l', list(SPARKS[1]), bones['spark_l']),
        ]),
        bone('hitbox', [0.0, 16.0, 0.0], [], visible=False),
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
            'width': TEX, 'height': TEX, 'uv_width': 16, 'uv_height': 16,
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
# 7. Hand-crafted 32x32 pixel-art menu icon (`reallyworld:zeus_wings_icon`)
# ---------------------------------------------------------------------------
def build_zeus_icon() -> Image.Image:
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    core = (255, 255, 255, 255)
    ice = (214, 244, 255, 255)
    pale = (150, 214, 255, 255)
    lit = (72, 150, 236, 255)
    deep = (26, 44, 108, 255)
    night = (12, 18, 48, 255)
    cloud = (58, 92, 178, 255)
    cloud_hi = (128, 176, 240, 255)

    def put(x: int, y: int, c: tuple) -> None:
        if 0 <= x < 32 and 0 <= y < 32:
            px[x, y] = c

    # thunderhead the wings grow out of
    for (bx, by, bw, bh) in ((13, 15, 7, 3), (12, 17, 9, 2), (14, 13, 5, 2)):
        for y in range(by, by + bh):
            for x in range(bx, bx + bw):
                put(x, y, cloud_hi if ((x + y) % 5) == 0 else cloud)

    # One feather = a short line from the root towards the tip; the row of tips traces
    # the trailing edge of the wing, exactly like the 3D model.
    ROOTS = ((16, 13), (17, 12), (19, 11), (21, 11), (23, 12), (25, 13), (27, 15))
    TIPS = ((15, 22), (17, 24), (19, 25), (22, 25), (25, 24), (28, 22), (30, 19))
    for sgn in (1.0, -1.0):
        def mx(x: float) -> float:
            return 15.5 + sgn * (x - 15.5)
        for k in range(len(ROOTS)):
            (x0, y0), (x1, y1) = ROOTS[k], TIPS[k]
            steps = max(3, int(math.hypot(x1 - x0, y1 - y0) * 2))
            wide = 1.5 if k >= 3 else 1.0
            for s in range(steps + 1):
                t = s / steps
                qx = x0 + (x1 - x0) * t
                qy = y0 + (y1 - y0) * t
                for off in (0.0, wide, -wide, 2.0 * wide, -2.0 * wide):
                    if abs(off) > 2.4 * wide:
                        continue
                    xx, yy = qx + off, qy
                    if t > 0.86:
                        col = core
                    elif abs(off) < 0.6:
                        col = ice
                    elif abs(off) < 1.3:
                        col = pale
                    else:
                        col = lit
                    put(int(round(mx(xx))), int(round(yy)), col)
            put(int(round(mx(x0))), int(round(y0)), core)
            put(int(round(mx(x1))), min(31, int(round(y1)) + 1), night)

    # sparks
    for (ex, ey) in ((9, 11), (22, 9), (6, 16), (26, 16)):
        put(ex, ey, core)
        put(ex, ey - 1, ice)
        put(ex, ey + 1, ice)

    return img


# ---------------------------------------------------------------------------
# 8. Multi-angle verification preview
# ---------------------------------------------------------------------------
def _rot_zxy(rx: float, ry: float, rz: float) -> np.ndarray:
    """ModelEngine builds the bone quaternion as Rz . Ry . Rx."""
    rx, ry, rz = map(math.radians, (rx, ry, rz))
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    mx = np.array([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]])
    my = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]])
    mz = np.array([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]])
    return mz @ my @ mx


def _bone_chain(blueprint: dict):
    """Yields (bone name, bone dict, parent transform builder, cubes)."""
    by_uuid = {el['uuid']: el for el in blueprint['elements']}
    out = []

    def walk(node, parent):
        cubes = [by_uuid[c] for c in node.get('children', []) if isinstance(c, str)]
        out.append((node['name'], node, parent, cubes))
        for c in node.get('children', []):
            if isinstance(c, dict):
                walk(c, node)
    for root in blueprint['outliner']:
        walk(root, None)
    return out


def render_preview(blueprint: dict, texture: Image.Image, icon: Image.Image,
                   out_path: Path) -> None:
    panel_w, panel_h = 250, 300
    canvas = Image.new('RGBA', (panel_w * 4 + 210, panel_h), (18, 22, 30, 255))
    tex_arr = np.array(texture)
    chain = _bone_chain(blueprint)
    parents = {name: (parent['name'] if parent else None)
               for name, _node, parent, _c in chain}

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
        scale_px = 4.6
        center_world = np.array([0.0, 21.0, 3.0])
        center_y_px = 170.0

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
                                              [(s[0], s[1]) for s in p2d], col,
                                              (36, 40, 52, 255)))

        tfs = {}

        def make_tf(name, node, pos, rot, scale):
            parent = parents.get(name)
            par_tf = tfs.get(parent) if parent else (lambda p: p)
            o = np.array(node['origin'], dtype=float)
            t = np.array(pos, dtype=float)
            m = _rot_zxy(*rot)
            sc = np.array(scale, dtype=float)

            def tf(p, o=o, t=t, m=m, sc=sc, par_tf=par_tf):
                return par_tf(o + t + m @ (sc * (np.asarray(p, dtype=float) - o)))
            return tf

        for name, node, _parent, _cubes in chain:
            if name == 'hitbox':
                continue
            if name == 'zeus_root':
                tfs[name] = make_tf(name, node, pose['root_pos'], pose['root_rot'], [1, 1, 1])
            elif name in ('wing_r', 'wing_l'):
                tfs[name] = make_tf(name, node, [0, 0, 0], pose['wing_rot'][name], [1, 1, 1])
            elif name in ARM_IDS:
                tfs[name] = make_tf(name, node, [0, 0, 0], pose['arm_rot'][name], [1, 1, 1])
            elif name in SHOULDER_IDS:
                tfs[name] = make_tf(name, node, [0, 0, 0], [0, 0, 0],
                                    pose['shoulder_scale'][name])
            elif name in FEATHER_IDS:
                tfs[name] = make_tf(name, node, [0, 0, 0], pose['feather_rot'][name],
                                    pose['feather_scale'][name])
            elif name in SPARK_IDS:
                tfs[name] = make_tf(name, node, [0, 0, 0], pose['spark_rot'][name],
                                    pose['spark_scale'][name])
            else:
                tfs[name] = make_tf(name, node, [0, 0, 0], [0, 0, 0], [1, 1, 1])

        for name, node, _parent, cubes in chain:
            if not cubes:
                continue
            tf_fn = tfs.get(name)
            if tf_fn is None:
                continue
            for el in cubes:
                x0, y0, z0 = el['from']
                x1, y1, z1 = el['to']
                c_orig = np.array(el['origin'], dtype=float)
                c_rot = _rot_zxy(*el['rotation'])
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
                    tx = min(TEX - 1, int(0.5 * (uv[0] + uv[2]) * 16.0))
                    ty = min(TEX - 1, int(0.5 * (uv[1] + uv[3]) * 16.0))
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
    args.bbmodel_out.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2),
                                encoding='utf-8')

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

    drawn = sum(1 for b in BONE_NAMES if b not in ('wing_r', 'wing_l', 'hitbox'))
    print(f'Built {MODEL}.bbmodel: {len(blueprint["elements"])} cubes, '
          f'{len(BONE_NAMES)} bones ({drawn} drawn), icon -> {args.assets_dir}')


if __name__ == '__main__':
    main()
