#!/usr/bin/env python3
"""Builds the Tokyo Ghoul Scolopendra (elytrix_centipede) blueprint, texture & icon.

Design:
- Canonical Tokyo Ghoul Chinese red-headed centipede (Scolopendra subspinipes mutilans):
  glossy jet-black/obsidian imbricated tergite carapace with blood-crimson rims,
  fiery scarlet-red cephalic shield with ocelli eye clusters & snapping black-tipped
  venomous forcipules (fangs), long 2-jointed whip antennae, 24 independent
  3-segment vermilion/red-orange clawed legs, and forked crimson tail cerci.
- Coils organically around the player's neck, trapezius, shoulders, and upper
  chest/collarbone (armor-safe clearance around chestplate & helmet, 100% clear
  of first-person PvP crosshair, unmistakable from front, back, and both sides).
- Zero per-cube rotations (all cubes [0, 0, 0]); all 3D orientation is carried
  by 47 bone transforms + native Blockbench/ModelEngine looping keyframe animation
  ('idle', 3.2 s seamless loop: body S-wave + metachronal leg scurry + antenna
  whipping + predatory double-snap fang clacks + tail cerci scissoring).
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
MODEL = 'elytrix_centipede'
ROOT_ORIGIN = [0.0, 22.5, 0.0]

# ---------------------------------------------------------------------------
# 3D Neck & Shoulders Coil Control Points (Blockbench player space)
# Player stands y=0..32 facing -Z; -X = left shoulder, +X = right shoulder;
# torso x[-4,4] y[12,24] z[-2,2], arms x[-8,-4] & [4,8] y[12,24] z[-2,2],
# head x[-4,4] y[24,32] z[-4,4].  +1.0 unit armor clearance everywhere!
#
# Head prowls low & menacingly forward over the LEFT shoulder pauldron
# (well outside x=-4.5 helmet & below/beside y=25.92 eye crosshair), while the
# body coils across upper back S-curve -> right shoulder -> diagonal chestplate
# -> forked crimson tail cerci on the lower-left pectoral.
# ---------------------------------------------------------------------------
HEAD_POS = (-6.35, 25.05, -2.95)

COIL_CTRL = [
    (-6.75, 25.20, -1.15),   # seg_01: forcipular collar on left shoulder front-top
    (-7.05, 25.25,  0.65),   # seg_02: left shoulder crown
    (-6.45, 24.95,  2.35),   # seg_03: left posterior shoulder
    (-4.80, 24.40,  3.65),   # seg_04: left trapezius
    (-2.45, 24.65,  4.10),   # seg_05: upper back S-wave high crest (behind nape)
    ( 0.05, 23.60,  4.00),   # seg_06: spine S-wave dip
    ( 2.65, 24.20,  3.90),   # seg_07: right trapezius rise
    ( 5.05, 24.85,  3.15),   # seg_08: right posterior shoulder
    ( 6.85, 25.35,  1.25),   # seg_09: right shoulder crown
    ( 7.05, 25.25, -0.85),   # seg_10: right anterior shoulder
    ( 6.05, 24.55, -2.95),   # seg_11: right front shoulder pauldron (clear of arm corner!)
    ( 4.05, 23.05, -3.75),   # seg_12: upper right chestplate
    ( 1.55, 21.55, -3.85),   # seg_13: center sternum collar
    (-1.05, 20.35, -3.70),   # seg_14: lower-left collarbone telson (tail cerci fork)
]

NUM_SEGS = 14
LEG_SEG_INDICES = tuple(range(2, 14))   # seg_02 .. seg_13 carry 12 pairs = 24 legs

ANIM_LENGTH = 3.2
ANIM_FRAMES = 33                        # 0.10 s step, seamless wrap frame 32 == frame 0


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'elytrix-centipede-v5:{tag}'))


# ---------------------------------------------------------------------------
# Vector & Matrix Math (exact match to ModelEngine 4.1.0 rotateZYX)
# ---------------------------------------------------------------------------
def _vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vmul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vcross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _vnorm(a):
    n = math.sqrt(max(1e-12, _vdot(a, a)))
    return (a[0] / n, a[1] / n, a[2] / n)


def _rot_axis(axis: int, deg: float):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == 0:
        return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))
    if axis == 1:
        return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def _mmul(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )


def _mtranspose(m):
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))


def _mvec(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def euler_zyx_to_matrix(euler):
    """Blockbench / ModelEngine bone rotation matrix: R = Rz(ez) * Ry(ey) * Rx(ex)."""
    rx, ry, rz = euler
    return _mmul(_mmul(_rot_axis(2, rz), _rot_axis(1, ry)), _rot_axis(0, rx))


def matrix_to_euler_zyx(m):
    """Exact inverse of R = Rz(ez) * Ry(ey) * Rx(ex), in degrees."""
    sy = max(-1.0, min(1.0, -m[2][0]))
    ry = math.asin(sy)
    cy = math.cos(ry)
    if abs(cy) > 1e-6:
        rx = math.atan2(m[2][1], m[2][2])
        rz = math.atan2(m[1][0], m[0][0])
    else:
        rx = math.atan2(-m[1][2], m[1][1])
        rz = 0.0
    return [round(math.degrees(rx), 4), round(math.degrees(ry), 4), round(math.degrees(rz), 4)]


# ---------------------------------------------------------------------------
# Centripetal Catmull-Rom Spine & Surface-Hugging Frames
# ---------------------------------------------------------------------------
def _catmull_rom(p0, p1, p2, p3, t, alpha=0.5):
    def tj(ti, a, b):
        return ti + max(1e-5, math.dist(a, b)) ** alpha

    t0 = 0.0
    t1 = tj(t0, p0, p1)
    t2 = tj(t1, p1, p2)
    t3 = tj(t2, p2, p3)
    tt = t1 + (t2 - t1) * t

    def lerp(a, b, ta, tb, x):
        w = (x - ta) / max(1e-9, tb - ta)
        return tuple(a[i] + (b[i] - a[i]) * w for i in range(3))

    a1 = lerp(p0, p1, t0, t1, tt)
    a2 = lerp(p1, p2, t1, t2, tt)
    a3 = lerp(p2, p3, t2, t3, tt)
    b1 = lerp(a1, a2, t0, t2, tt)
    b2 = lerp(a2, a3, t1, t3, tt)
    return lerp(b1, b2, t1, t2, tt)


def sample_collar_stations():
    """Returns 15 smooth stations: [head_pos, seg_01, ..., seg_14] with frames."""
    pts = [HEAD_POS] + list(COIL_CTRL)
    ghost_start = _vadd(pts[0], _vsub(pts[0], pts[1]))
    ghost_end = _vadd(pts[-1], _vsub(pts[-1], pts[-2]))
    ext = [ghost_start] + pts + [ghost_end]

    dense = []
    steps_per_seg = 24
    for i in range(len(pts) - 1):
        for s in range(steps_per_seg):
            dense.append(_catmull_rom(ext[i], ext[i + 1], ext[i + 2], ext[i + 3], s / steps_per_seg))
    dense.append(pts[-1])

    cum = [0.0]
    for i in range(1, len(dense)):
        cum.append(cum[-1] + math.dist(dense[i - 1], dense[i]))
    total_len = cum[-1]

    stations_pos = []
    count = NUM_SEGS + 1
    for idx in range(count):
        target = total_len * (idx / (count - 1))
        lo = 0
        while lo + 1 < len(cum) and cum[lo + 1] < target:
            lo += 1
        hi = min(len(cum) - 1, lo + 1)
        w = 0.0 if hi == lo else (target - cum[lo]) / max(1e-9, cum[hi] - cum[lo])
        p = tuple(dense[lo][k] + (dense[hi][k] - dense[lo][k]) * w for k in range(3))
        stations_pos.append(p)

    stations = []
    for idx, p in enumerate(stations_pos):
        if idx == 0:
            # Sleek horizontal predatory prowl straight ahead (-Z) over left shoulder!
            # Keeps antennae & fangs 100% out of the player's eyes / first-person crosshair.
            fwd = _vnorm((0.06, -0.05, -0.995))
        elif idx == len(stations_pos) - 1:
            fwd = _vnorm(_vsub(stations_pos[idx - 1], stations_pos[idx]))
        else:
            fwd = _vnorm(_vsub(stations_pos[idx - 1], stations_pos[idx + 1]))

        z_axis = _vmul(fwd, -1.0)

        anchor_x = max(-4.2, min(4.2, p[0] * 0.65))
        anchor = (anchor_x, 21.0, 0.0)
        radial = _vsub(p, anchor)
        raw_up = (0.0, 1.0, 0.0) if idx == 0 else _vnorm(_vadd(_vnorm(radial), (0.0, 0.72, 0.0)))

        x_axis = _vnorm(_vcross(raw_up, z_axis))
        y_axis = _vnorm(_vcross(z_axis, x_axis))

        rot_mat = (
            (x_axis[0], y_axis[0], z_axis[0]),
            (x_axis[1], y_axis[1], z_axis[1]),
            (x_axis[2], y_axis[2], z_axis[2]),
        )
        euler = matrix_to_euler_zyx(rot_mat)
        stations.append({
            'pos': [round(v, 4) for v in p],
            'rot': euler,
            'mat': rot_mat,
        })
    return stations


# ---------------------------------------------------------------------------
# 128x128 Procedural Pixel-Art Texture (Canonical Tokyo Ghoul Obsidian + Crimson)
# UV space is 16x16 (8 px per UV unit).
# ---------------------------------------------------------------------------
UV_REGIONS = {
    'tergite_top':   (0.0,  0.0,  8.0,  4.0),   # 0..64 x 0..32: jet-black carapace + crimson rim
    'tergite_ridge': (0.0,  4.0,  8.0,  6.0),   # 0..64 x 32..48: glossy obsidian dorsal crown + ruby lip
    'tergite_side':  (0.0,  6.0,  8.0,  8.0),   # 0..64 x 48..64: obsidian upper + blood-crimson rim
    'sternite':      (0.0,  8.0,  8.0, 10.5),   # 0..64 x 64..84: dark mahogany-crimson belly
    'pleuron':       (0.0, 10.5,  8.0, 13.0),   # 0..64 x 84..104: dark chitin socket
    'claw_black':    (0.0, 13.0,  8.0, 16.0),   # 0..64 x 104..128: glossy pitch-black venom tips/claws
    'head_top':      (8.0,  0.0, 16.0,  4.0),   # 64..128 x 0..32: fiery Tokyo Ghoul scarlet head shield
    'eye_cluster':   (8.0,  4.0, 12.0,  8.0),   # 64..96 x 32..64: black ocelli cluster + glints
    'fang_crimson':  (12.0, 4.0, 16.0,  8.0),   # 96..128 x 32..64: scarlet-to-obsidian forcipule
    'leg_orange':    (8.0,  8.0, 16.0, 12.0),   # 64..128 x 64..96: vermilion/red-orange cylindrical limb
    'antenna_ring':  (8.0, 12.0, 16.0, 16.0),   # 64..128 x 96..128: segmented red-orange antennomeres
}


def _clamp8(v):
    return max(0, min(255, int(round(v))))


def build_texture() -> Image.Image:
    size = 128
    img = Image.new('RGBA', (size, size), (14, 8, 12, 255))
    px = img.load()

    def micro_grain(x, y):
        return (
            math.sin(x * 0.91 + y * 1.37) * 0.45
            + math.sin(x * 0.37 - y * 0.73) * 0.35
            + math.cos((x + y) * 0.53) * 0.20
        )

    # 1. Tergite Top (x: 0..64, y: 0..32) — Deep glossy jet-black plate + sharp blood-crimson rims
    for y in range(0, 32):
        v = y / 31.0
        for x in range(0, 64):
            u = (x - 31.5) / 31.5
            au = abs(u)
            g = micro_grain(x, y) * 3.5

            # Deep obsidian-ebony chitin core (#0B070E .. #160E1B)
            r, gr, b = 13.0 + g, 8.0 + g * 0.4, 15.0 + g * 0.6

            # Crisp blood-crimson lateral margin (au > 0.78)
            if au > 0.76:
                edge_t = min(1.0, (au - 0.76) / 0.24) ** 1.25
                r = r * (1.0 - edge_t) + 188.0 * edge_t
                gr = gr * (1.0 - edge_t) + 16.0 * edge_t
                b = b * (1.0 - edge_t) + 30.0 * edge_t

            # Sharp posterior ruby-crimson imbricated rim (y >= 26)
            if v > 0.81:
                lip_t = ((v - 0.81) / 0.19) ** 1.2
                r = r * (1.0 - lip_t * 0.9) + 196.0 * lip_t * 0.9
                gr = gr * (1.0 - lip_t * 0.9) + 20.0 * lip_t * 0.9
                b = b * (1.0 - lip_t * 0.9) + 34.0 * lip_t * 0.9

            # Anterior overlap occlusion
            if v < 0.16:
                occ = 0.45 + 0.55 * (v / 0.16)
                r, gr, b = r * occ, gr * occ, b * occ

            # Paramedian longitudinal grooves
            groove = math.exp(-((au - 0.32) / 0.04) ** 2)
            r *= 1.0 - 0.40 * groove
            gr *= 1.0 - 0.40 * groove
            b *= 1.0 - 0.35 * groove

            # Glossy wet-chitin specular sheen down the black carapace
            spec = math.exp(-(u / 0.16) ** 2) * math.exp(-((v - 0.50) / 0.28) ** 2)
            r += 64.0 * spec
            gr += 50.0 * spec
            b += 68.0 * spec

            px[x, y] = (_clamp8(r), _clamp8(gr), _clamp8(b), 255)

    # 2. Tergite Raised Dorsal Ridge (x: 0..64, y: 32..48) — Pure glossy obsidian + thin crimson rear edge
    for y in range(32, 48):
        v = (y - 32) / 15.0
        for x in range(0, 64):
            u = (x - 31.5) / 31.5
            g = micro_grain(x, y) * 3.0
            r, gr, b = 16.0 + g, 10.0 + g * 0.4, 20.0 + g * 0.6
            if v > 0.82:
                lt = (v - 0.82) / 0.18
                r = r * (1.0 - lt) + 172.0 * lt
                gr = gr * (1.0 - lt) + 18.0 * lt
                b = b * (1.0 - lt) + 30.0 * lt
            spec = math.exp(-(u / 0.22) ** 2) * (0.4 + 0.6 * math.sin(v * math.pi))
            r += 58.0 * spec
            gr += 46.0 * spec
            b += 64.0 * spec
            px[x, y] = (_clamp8(r), _clamp8(gr), _clamp8(b), 255)

    # 3. Tergite Lateral Rim (x: 0..64, y: 48..64) — Obsidian upper shell + glowing crimson lower margin
    for y in range(48, 64):
        v = (y - 48) / 15.0
        for x in range(0, 64):
            g = micro_grain(x, y) * 4.0
            rim = max(0.0, (v - 0.35) / 0.65) ** 1.15
            r = 16.0 * (1.0 - rim) + 182.0 * rim + g
            gr = 9.0 * (1.0 - rim) + 18.0 * rim
            b = 16.0 * (1.0 - rim) + 30.0 * rim
            px[x, y] = (_clamp8(r), _clamp8(gr), _clamp8(b), 255)

    # 4. Ventral Sternite Belly (x: 0..64, y: 64..84)
    for y in range(64, 84):
        v = (y - 64) / 19.0
        for x in range(0, 64):
            u = abs((x - 31.5) / 31.5)
            cyl = 1.0 - 0.42 * (u ** 1.6)
            r = (68.0 + 22.0 * math.sin(v * math.pi)) * cyl
            gr = (16.0 + 6.0 * math.sin(v * math.pi)) * cyl
            b = (20.0 + 6.0 * math.sin(v * math.pi)) * cyl
            px[x, y] = (_clamp8(r), _clamp8(gr), _clamp8(b), 255)

    # 5. Pleuron Socket Chitin (x: 0..64, y: 84..104)
    for y in range(84, 104):
        for x in range(0, 64):
            g = micro_grain(x, y) * 3.0
            px[x, y] = (_clamp8(24 + g), _clamp8(9 + g * 0.3), _clamp8(14 + g * 0.4), 255)

    # 6. Glossy Pitch-Black Claws & Venom Tips (x: 0..64, y: 104..128)
    for y in range(104, 128):
        v = (y - 104) / 23.0
        for x in range(0, 64):
            u = (x - 31.5) / 31.5
            spec = math.exp(-(u / 0.15) ** 2) * (1.0 - 0.35 * v)
            r = 10.0 + 24.0 * (1.0 - v) ** 2 + 80.0 * spec
            gr = 7.0 + 6.0 * (1.0 - v) ** 2 + 68.0 * spec
            b = 12.0 + 8.0 * (1.0 - v) ** 2 + 82.0 * spec
            px[x, y] = (_clamp8(r), _clamp8(gr), _clamp8(b), 255)

    # 7. Fiery Crimson Cephalic Head Shield (x: 64..128, y: 0..32)
    for y in range(0, 32):
        v = y / 31.0
        for x in range(64, 128):
            u = (x - 95.5) / 31.5
            au = abs(u)
            g = micro_grain(x, y) * 5.0
            dome = (1.0 - 0.42 * (au ** 1.8)) * (1.0 - 0.22 * ((v - 0.45) ** 2) * 3.0)
            r = 148.0 + 104.0 * dome + g
            gr = 14.0 + 32.0 * (dome ** 1.6) + g * 0.3
            b = 18.0 + 24.0 * (dome ** 1.6) + g * 0.3

            suture = math.exp(-(au / 0.04) ** 2) * (1.0 if v > 0.42 else 0.0)
            suture = max(suture, math.exp(-((au - (0.44 - v) * 0.75) / 0.045) ** 2) * (1.0 if v <= 0.44 else 0.0))
            r *= 1.0 - 0.30 * suture
            gr *= 1.0 - 0.36 * suture

            spec = math.exp(-((u + 0.14) / 0.22) ** 2) * math.exp(-((v - 0.38) / 0.22) ** 2)
            r += 56.0 * spec
            gr += 66.0 * spec
            b += 50.0 * spec
            px[x, y] = (_clamp8(r), _clamp8(gr), _clamp8(b), 255)

    # 8. Ocelli Eye Cluster (x: 64..96, y: 32..64) — 4 gleaming black ocelli + silver-crimson glints
    for y in range(32, 64):
        for x in range(64, 96):
            px[x, y] = (18, 6, 10, 255)
    for ox, oy, rad in ((72, 42, 3.4), (80, 40, 3.2), (88, 44, 3.0), (77, 51, 3.0)):
        for y in range(32, 64):
            for x in range(64, 96):
                d = math.hypot(x - ox, y - oy)
                if d <= rad:
                    px[x, y] = (6, 4, 8, 255)
                if math.hypot(x - (ox - 1.0), y - (oy - 1.0)) <= 1.2:
                    px[x, y] = (255, 220, 224, 255)

    # 9. Venomous Forcipule Gradient (x: 96..128, y: 32..64)
    for y in range(32, 64):
        v = (y - 32) / 31.0
        for x in range(96, 128):
            u = (x - 111.5) / 15.5
            cyl = 1.0 - 0.44 * (u * u)
            venom = min(1.0, max(0.0, (v - 0.25) / 0.65)) ** 1.25
            r = (232.0 * (1.0 - venom) + 12.0 * venom) * cyl
            gr = (30.0 * (1.0 - venom) + 7.0 * venom) * cyl
            b = (26.0 * (1.0 - venom) + 12.0 * venom) * cyl
            spec = math.exp(-(u / 0.22) ** 2) * 42.0
            px[x, y] = (_clamp8(r + spec), _clamp8(gr + spec * 0.7), _clamp8(b + spec * 0.8), 255)

    # 10. Jointed Vermilion / Red-Orange Legs & Cerci (x: 64..128, y: 64..96)
    for y in range(64, 96):
        v = (y - 64) / 31.0
        cyl = 0.54 + 0.56 * math.sin(v * math.pi)
        spec = math.exp(-((v - 0.38) / 0.14) ** 2)
        for x in range(64, 128):
            u = (x - 64) / 63.0
            g = micro_grain(x, y) * 4.0
            joint = 1.0
            if u < 0.09:
                joint = 0.36 + 0.64 * (u / 0.09)
            elif u > 0.90:
                joint = 0.34 + 0.66 * ((1.0 - u) / 0.10)
            r = (242.0 * cyl + 38.0 * spec + g) * joint
            gr = (66.0 * cyl + 58.0 * spec + g * 0.4) * joint
            b = (18.0 * cyl + 24.0 * spec) * joint
            px[x, y] = (_clamp8(r), _clamp8(gr), _clamp8(b), 255)

    # 11. Beaded Crimson-Orange Whip Antennae (x: 64..128, y: 96..128)
    for y in range(96, 128):
        v = (y - 96) / 31.0
        cyl = 0.56 + 0.52 * math.sin(v * math.pi)
        for x in range(64, 128):
            bead = abs(math.sin((x - 64) * math.pi / 8.0))
            ring = 0.48 + 0.58 * (bead ** 0.55)
            r = 244.0 * cyl * ring
            gr = 72.0 * cyl * (ring ** 1.25)
            b = 24.0 * cyl * ring
            px[x, y] = (_clamp8(r), _clamp8(gr), _clamp8(b), 255)

    return img


# ---------------------------------------------------------------------------
# Crisp 32x32 Pixel-Art Menu Icon (centipede_icon.png)
# Matches kaneki_tentacles_icon.png style with dark outline + vivid silhouette
# ---------------------------------------------------------------------------
def build_menu_icon() -> Image.Image:
    size = 32
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    px = img.load()

    # S-curve spine from bottom-right tail to top-left predatory crimson head
    pts = []
    for i in range(61):
        t = i / 60.0
        ang = 0.32 * math.pi + t * 1.52 * math.pi
        rad = 9.2 - 1.2 * t + 1.8 * math.sin(t * math.pi * 2.0)
        cx = 16.2 + math.cos(ang) * rad
        cy = 16.5 + math.sin(ang) * rad * 0.88
        pts.append((cx, cy, t))

    # Vermilion-orange jointed legs
    for idx in range(4, 55, 5):
        cx, cy, t = pts[idx]
        nx_p, ny_p, _ = pts[min(60, idx + 1)]
        tx, ty = nx_p - cx, ny_p - cy
        ln = max(1e-5, math.hypot(tx, ty))
        nx, ny = -ty / ln, tx / ln
        for side in (-1.0, 1.0):
            for step in range(1, 5):
                s = step * 0.82
                bend = -0.32 * step
                lx = int(round(cx + nx * side * (1.7 + s) + (tx / ln) * bend))
                ly = int(round(cy + ny * side * (1.7 + s) + (ty / ln) * bend))
                if 1 <= lx < size - 1 and 1 <= ly < size - 1:
                    px[lx, ly] = (252, 84, 28, 255) if step < 4 else (196, 30, 28, 255)

    # Forked crimson tail cerci at pts[0]
    tx0, ty0, _ = pts[0]
    tx1, ty1, _ = pts[3]
    dx, dy = tx0 - tx1, ty0 - ty1
    dl = max(1e-5, math.hypot(dx, dy))
    ux, uy = dx / dl, dy / dl
    for side in (-1.0, 1.0):
        for s in range(1, 5):
            fx = int(round(tx0 + ux * s * 0.85 - uy * side * s * 0.55))
            fy = int(round(ty0 + uy * s * 0.85 + ux * side * s * 0.55))
            if 1 <= fx < size - 1 and 1 <= fy < size - 1:
                px[fx, fy] = (232, 44, 34, 255)

    # Obsidian-black carapace segments with blood-crimson imbricated joints + bright scarlet head
    for idx, (cx, cy, t) in enumerate(pts):
        is_head = t > 0.88
        half_w = 2.55 if is_head else (1.75 + 0.65 * math.sin(t * math.pi))
        r_int = int(math.ceil(half_w + 1.0))
        seg_rim = (idx % 6 == 0)
        for yy in range(max(1, int(cy) - r_int), min(size - 1, int(cy) + r_int + 1)):
            for xx in range(max(1, int(cx) - r_int), min(size - 1, int(cx) + r_int + 1)):
                d = math.hypot(xx - cx, yy - cy)
                if d <= half_w:
                    if is_head:
                        hl = 1.12 if d < 1.1 else (0.95 - 0.25 * (d / half_w))
                        px[xx, yy] = (_clamp8(236 * hl), _clamp8(34 * hl), _clamp8(36 * hl), 255)
                    elif seg_rim or d > half_w - 0.72:
                        px[xx, yy] = (176, 20, 34, 255)
                    elif d < 0.75 and idx % 3 == 1:
                        px[xx, yy] = (68, 52, 74, 255)   # wet chitin glint
                    else:
                        px[xx, yy] = (20, 12, 22, 255)   # jet-black obsidian plate

    # Curved black fangs & orange whip antennae on head (pts[-1])
    hx, hy, _ = pts[-1]
    hx0, hy0, _ = pts[-4]
    fx, fy = hx - hx0, hy - hy0
    fl = max(1e-5, math.hypot(fx, fy))
    ux, uy = fx / fl, fy / fl
    px_n, py_n = -uy, ux
    for side in (-1.0, 1.0):
        for fs in (1.8, 2.7):
            qx = int(round(hx + ux * fs + px_n * side * (2.2 - fs * 0.45)))
            qy = int(round(hy + uy * fs + py_n * side * (2.2 - fs * 0.45)))
            if 1 <= qx < size - 1 and 1 <= qy < size - 1:
                px[qx, qy] = (16, 10, 18, 255)
        for s in range(1, 7):
            ax = int(round(hx + ux * (1.6 + s * 0.85) + px_n * side * (0.9 + s * 0.58 - 0.07 * s * s)))
            ay = int(round(hy + uy * (1.6 + s * 0.85) + py_n * side * (0.9 + s * 0.58 - 0.07 * s * s)))
            if 1 <= ax < size - 1 and 1 <= ay < size - 1:
                px[ax, ay] = (255, 92, 34, 255)

    # Clean 1px dark crimson-black silhouette outline for crisp inventory contrast
    outline = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    opx = outline.load()
    for y in range(size):
        for x in range(size):
            if px[x, y][3] > 0:
                opx[x, y] = px[x, y]
                continue
            if any(0 <= x + dx < size and 0 <= y + dy < size and px[x + dx, y + dy][3] > 0
                   for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                opx[x, y] = (34, 6, 12, 235)
    return outline


# ---------------------------------------------------------------------------
# Cube & Bone Builders (strictly cube rotation = [0, 0, 0]!)
# ---------------------------------------------------------------------------
def make_cube(tag: str, pivot, local_lo, local_hi, face_regions: dict):
    lo = [round(pivot[i] + min(local_lo[i], local_hi[i]), 4) for i in range(3)]
    hi = [round(pivot[i] + max(local_lo[i], local_hi[i]), 4) for i in range(3)]
    faces = {}
    for side in ('north', 'east', 'south', 'west', 'up', 'down'):
        reg_name = face_regions.get(side, face_regions['default'])
        u0, v0, u1, v1 = UV_REGIONS[reg_name]
        faces[side] = {'uv': [round(u0 + 0.08, 3), round(v0 + 0.08, 3),
                              round(u1 - 0.08, 3), round(v1 - 0.08, 3)], 'texture': 0}
    return {
        'name': tag,
        'from': lo,
        'to': hi,
        'autouv': 0,
        'color': 0,
        'origin': [round(v, 4) for v in pivot],
        'rotation': [0.0, 0.0, 0.0],
        'uuid': uid(f'cube:{tag}'),
        'faces': faces,
        'type': 'cube',
    }


def make_bone(name: str, origin, rotation, cubes, children=None):
    return {
        'name': name,
        'origin': [round(v, 4) for v in origin],
        'rotation': [round(v, 4) for v in rotation],
        'color': 0,
        'uuid': uid(f'bone:{name}'),
        'export': True,
        'mirror_uv': False,
        'isOpen': True,
        'locked': False,
        'visibility': True,
        'autouv': 0,
        'children': [c['uuid'] for c in cubes] + (children or []),
    }


def local_to_world(parent_origin, parent_mat, local_offset):
    w = _mvec(parent_mat, local_offset)
    return [round(parent_origin[i] + w[i], 4) for i in range(3)]


# ---------------------------------------------------------------------------
# Full Scolopendra Rig Construction
# ---------------------------------------------------------------------------
def build_rig():
    stations = sample_collar_stations()
    head_st = stations[0]
    seg_stations = stations[1:]

    all_elements = []
    seg_bones = []
    anim_meta = {'segs': [], 'legs': [], 'head': None, 'fangs': [], 'antennae': [], 'cerci': []}

    for idx, st in enumerate(seg_stations, start=1):
        seg_name = f'seg_{idx:02d}'
        origin = st['pos']
        rot = st['rot']
        mat = st['mat']

        u = (idx - 1) / (NUM_SEGS - 1)
        taper = math.sin(math.pi * (0.16 + 0.72 * u))
        half_w = round(1.38 + 0.44 * taper, 3)
        half_len = 1.40 if idx < NUM_SEGS else 1.20

        seg_cubes = [
            make_cube(
                f'{seg_name}_plate', origin,
                (-half_w, -0.30, -half_len), (half_w, 0.60, half_len + 0.18),
                {'up': 'tergite_top', 'down': 'sternite', 'default': 'tergite_side'},
            ),
            make_cube(
                f'{seg_name}_ridge', origin,
                (-half_w * 0.70, 0.56, -half_len * 0.88), (half_w * 0.70, 1.00, half_len + 0.24),
                {'up': 'tergite_ridge', 'down': 'tergite_ridge', 'default': 'tergite_ridge'},
            ),
            make_cube(
                f'{seg_name}_belly', origin,
                (-half_w * 0.66, -0.72, -half_len * 0.82), (half_w * 0.66, -0.26, half_len * 0.82),
                {'up': 'sternite', 'down': 'sternite', 'default': 'pleuron'},
            ),
        ]
        all_elements.extend(seg_cubes)
        child_bones = []

        if idx in LEG_SEG_INDICES:
            leg_scale = 0.90 + 0.22 * taper
            for side_tag, sx in (('l', -1.0), ('r', 1.0)):
                leg_name = f'leg_{side_tag}_{idx:02d}'
                hip_origin = local_to_world(origin, mat, (sx * (half_w - 0.16), -0.16, 0.0))
                leg_rest_rot = [0.0, sx * -8.0, sx * -10.0]
                L1 = 1.28 * leg_scale
                L2 = 2.30 * leg_scale
                L3 = 2.92 * leg_scale
                leg_cubes = [
                    make_cube(
                        f'{leg_name}_femur', hip_origin,
                        (0.0, -0.18, -0.26), (sx * L1, 0.34, 0.26),
                        {'default': 'leg_orange'},
                    ),
                    make_cube(
                        f'{leg_name}_tibia', hip_origin,
                        (sx * (L1 - 0.18), -0.74, -0.22), (sx * L2, 0.16, 0.22),
                        {'default': 'leg_orange'},
                    ),
                    make_cube(
                        f'{leg_name}_claw', hip_origin,
                        (sx * (L2 - 0.22), -1.52, -0.17), (sx * L3, -0.58, 0.17),
                        {'down': 'claw_black', 'default': 'leg_orange',
                         'east': 'claw_black' if sx > 0 else 'leg_orange',
                         'west': 'claw_black' if sx < 0 else 'leg_orange'},
                    ),
                ]
                all_elements.extend(leg_cubes)
                child_bones.append(make_bone(leg_name, hip_origin, leg_rest_rot, leg_cubes))
                anim_meta['legs'].append((leg_name, idx, sx))

        if idx == 1:
            seg1_inv = _mtranspose(mat)
            head_rel_mat = _mmul(seg1_inv, head_st['mat'])
            head_rel_rot = matrix_to_euler_zyx(head_rel_mat)
            h_origin = head_st['pos']
            h_mat = head_st['mat']

            head_cubes = [
                make_cube(
                    'head_shield', h_origin,
                    (-1.72, -0.32, -1.80), (1.72, 0.68, 1.15),
                    {'up': 'head_top', 'down': 'sternite', 'default': 'head_top'},
                ),
                make_cube(
                    'head_dome', h_origin,
                    (-1.22, 0.62, -1.38), (1.22, 1.08, 0.92),
                    {'default': 'head_top'},
                ),
                make_cube(
                    'head_brow', h_origin,
                    (-1.24, -0.18, -2.38), (1.24, 0.50, -1.68),
                    {'default': 'head_top'},
                ),
                make_cube(
                    'head_eyes_l', h_origin,
                    (-1.88, 0.06, -1.65), (-1.48, 0.58, -0.82),
                    {'default': 'eye_cluster'},
                ),
                make_cube(
                    'head_eyes_r', h_origin,
                    (1.48, 0.06, -1.65), (1.88, 0.58, -0.82),
                    {'default': 'eye_cluster'},
                ),
            ]
            all_elements.extend(head_cubes)
            head_children = []

            # Bold, wide-flaring venomous forcipules (fang_l, fang_r) with hooking black venom tips!
            for side_tag, sx in (('l', -1.0), ('r', 1.0)):
                fang_name = f'fang_{side_tag}'
                f_origin = local_to_world(h_origin, h_mat, (sx * 1.38, -0.28, -1.55))
                f_rot = [6.0, sx * -16.0, 0.0]
                fang_cubes = [
                    make_cube(
                        f'{fang_name}_base', f_origin,
                        (-sx * 0.10, -0.28, -1.25), (sx * 0.98, 0.28, 0.18),
                        {'default': 'fang_crimson'},
                    ),
                    make_cube(
                        f'{fang_name}_mid', f_origin,
                        (sx * 0.16, -0.24, -2.28), (sx * 0.88, 0.22, -1.10),
                        {'default': 'fang_crimson'},
                    ),
                    make_cube(
                        f'{fang_name}_tip', f_origin,
                        (-sx * 0.62, -0.20, -2.95), (sx * 0.42, 0.16, -2.12),
                        {'default': 'claw_black'},
                    ),
                ]
                all_elements.extend(fang_cubes)
                head_children.append(make_bone(fang_name, f_origin, f_rot, fang_cubes))
                anim_meta['fangs'].append((fang_name, sx))

            # 2-Stage Whip Antennae angled forward & outward-left (100% clear of player eyes!)
            for side_tag, sx in (('l', -1.0), ('r', 1.0)):
                a1_name = f'ant_{side_tag}1'
                a2_name = f'ant_{side_tag}2'
                a1_origin = local_to_world(h_origin, h_mat, (sx * 0.82, 0.20, -2.28))
                # Left antenna flares outward (-X, +28 deg yaw), right antenna sweeps straight forward (-6 deg yaw)
                yaw_base = 28.0 if sx < 0 else -8.0
                a1_rot = [-6.0, yaw_base, sx * -5.0]
                a1_mat = _mmul(h_mat, euler_zyx_to_matrix(a1_rot))

                a1_cubes = [
                    make_cube(f'{a1_name}_s1', a1_origin, (-0.23, -0.20, -1.05), (0.23, 0.22, 0.08),
                              {'default': 'antenna_ring'}),
                    make_cube(f'{a1_name}_s2', a1_origin, (-0.20, -0.16, -2.05), (0.20, 0.20, -0.98),
                              {'default': 'antenna_ring'}),
                    make_cube(f'{a1_name}_s3', a1_origin, (-0.18, -0.14, -2.95), (0.18, 0.18, -1.98),
                              {'default': 'antenna_ring'}),
                ]
                a2_origin = local_to_world(a1_origin, a1_mat, (0.0, 0.02, -2.88))
                a2_rot = [12.0, 14.0 if sx < 0 else -12.0, 0.0]
                a2_cubes = [
                    make_cube(f'{a2_name}_s1', a2_origin, (-0.16, -0.14, -0.98), (0.16, 0.16, 0.06),
                              {'default': 'antenna_ring'}),
                    make_cube(f'{a2_name}_s2', a2_origin, (-0.13, -0.16, -1.92), (0.13, 0.12, -0.92),
                              {'default': 'antenna_ring'}),
                    make_cube(f'{a2_name}_tip', a2_origin, (-0.10, -0.20, -2.78), (0.10, 0.08, -1.86),
                              {'north': 'claw_black', 'default': 'antenna_ring'}),
                ]
                all_elements.extend(a1_cubes + a2_cubes)
                a2_bone = make_bone(a2_name, a2_origin, a2_rot, a2_cubes)
                a1_bone = make_bone(a1_name, a1_origin, a1_rot, a1_cubes, [a2_bone])
                head_children.append(a1_bone)
                anim_meta['antennae'].append((a1_name, a2_name, sx))

            child_bones.append(make_bone('head', h_origin, head_rel_rot, head_cubes, head_children))
            anim_meta['head'] = 'head'

        if idx == NUM_SEGS:
            for side_tag, sx in (('l', -1.0), ('r', 1.0)):
                c_name = f'cercus_{side_tag}'
                c_origin = local_to_world(origin, mat, (sx * 0.74, 0.05, 1.10))
                c_rot = [8.0, sx * 24.0, sx * 6.0]
                c_cubes = [
                    make_cube(f'{c_name}_s1', c_origin, (-0.28, -0.22, -0.10), (0.28, 0.28, 1.45),
                              {'default': 'leg_orange'}),
                    make_cube(f'{c_name}_s2', c_origin, (-0.22, -0.18, 1.35), (0.22, 0.24, 2.78),
                              {'default': 'fang_crimson'}),
                    make_cube(f'{c_name}_tip', c_origin, (-0.16, -0.16, 2.68), (0.16, 0.18, 3.88),
                              {'south': 'claw_black', 'default': 'claw_black'}),
                ]
                all_elements.extend(c_cubes)
                child_bones.append(make_bone(c_name, c_origin, c_rot, c_cubes))
                anim_meta['cerci'].append((c_name, sx))

        seg_bones.append(make_bone(seg_name, origin, rot, seg_cubes, child_bones))
        anim_meta['segs'].append((seg_name, idx))

    root = make_bone('body_root', ROOT_ORIGIN, [0.0, 0.0, 0.0], [], seg_bones)
    return root, all_elements, anim_meta


# ---------------------------------------------------------------------------
# Full Living Animation ('idle', 3.2 s seamless loop, deltas only!)
# ---------------------------------------------------------------------------
def _rot_keys(bone_name: str, fn):
    keys = []
    for step in range(ANIM_FRAMES):
        t = ANIM_LENGTH * step / (ANIM_FRAMES - 1)
        rx, ry, rz = fn(t)
        keys.append({
            'channel': 'rotation',
            'data_points': [{'x': str(round(rx, 3)), 'y': str(round(ry, 3)), 'z': str(round(rz, 3))}],
            'uuid': uid(f'rkey:{bone_name}:{step}'),
            'time': round(t, 4),
            'color': -1,
            'interpolation': 'linear',
        })
    keys[-1]['data_points'] = [dict(p) for p in keys[0]['data_points']]
    return keys


def _pos_keys(bone_name: str, fn):
    keys = []
    for step in range(ANIM_FRAMES):
        t = ANIM_LENGTH * step / (ANIM_FRAMES - 1)
        px, py, pz = fn(t)
        keys.append({
            'channel': 'position',
            'data_points': [{'x': str(round(px, 3)), 'y': str(round(py, 3)), 'z': str(round(pz, 3))}],
            'uuid': uid(f'pkey:{bone_name}:{step}'),
            'time': round(t, 4),
            'color': -1,
            'interpolation': 'linear',
        })
    keys[-1]['data_points'] = [dict(p) for p in keys[0]['data_points']]
    return keys


def _fang_strike_envelope(t: float) -> float:
    """Periodic predatory double-clack at t=1.04s & 1.32s, plus quick snap at t=2.56s.
    Negative -> flare wide open; positive -> snap shut so black venom tips cross!
    """
    w = 2.0 * math.pi * t / ANIM_LENGTH
    base = -0.45 * math.sin(w) - 0.22 * math.sin(2.0 * w)
    snap = 0.0
    for center, width, amp in ((1.04, 0.085, 1.55), (1.32, 0.085, 1.40), (2.56, 0.095, 1.25)):
        dt = ((t - center + ANIM_LENGTH / 2.0) % ANIM_LENGTH) - ANIM_LENGTH / 2.0
        snap += amp * math.exp(-((dt / width) ** 2))
    return base + snap


def build_animation(anim_meta: dict):
    w1 = 2.0 * math.pi / ANIM_LENGTH
    animators = {}

    def add_anim(bone_name: str, keyframes: list):
        animators[uid(f'bone:{bone_name}')] = {
            'name': bone_name,
            'type': 'bone',
            'keyframes': keyframes,
        }

    # 1. Body S-Wave Undulation across all 14 tergites
    for seg_name, idx in anim_meta['segs']:
        phase = idx * 0.54
        amp = 0.85 + 0.25 * math.cos((idx - 1) * math.pi / 6.5)

        def seg_rot(t, ph=phase, a=amp):
            s = 2.0 * w1 * t - ph
            rx = 2.4 * a * math.sin(s + 0.7)
            ry = 5.4 * a * math.sin(s)
            rz = 5.8 * a * math.cos(s)
            return rx, ry, rz

        def seg_pos(t, ph=phase, i=idx):
            s = 2.0 * w1 * t - ph
            return (
                0.15 * math.sin(s),
                0.10 * math.sin(2.0 * w1 * t - i * 0.4 + 1.1),
                0.12 * math.cos(s),
            )

        add_anim(seg_name, _rot_keys(seg_name, seg_rot) + _pos_keys(seg_name, seg_pos))

    # 2. True Metachronal Scurrying Wave on all 24 Legs (4 step cycles per 3.2 s)
    for leg_name, idx, sx in anim_meta['legs']:
        side_offset = 0.0 if sx < 0 else math.pi
        leg_phase = idx * 0.68 + side_offset

        def leg_rot(t, ph=leg_phase, side=sx):
            phi = 4.0 * w1 * t - ph
            swing = side * 17.5 * math.sin(phi)
            lift_wave = max(0.0, math.cos(phi))
            roll_lift = side * (18.5 * lift_wave - 3.5)
            pitch_twist = 4.8 * math.sin(phi)
            return pitch_twist, swing, roll_lift

        add_anim(leg_name, _rot_keys(leg_name, leg_rot))

    # 3. Alert Predatory Head Scan & Strike Lunge
    def head_rot(t):
        strike = max(0.0, _fang_strike_envelope(t))
        rx = -3.2 * math.sin(2.0 * w1 * t) + 5.0 * strike
        ry = 8.5 * math.sin(w1 * t) + 3.8 * math.sin(3.0 * w1 * t)
        rz = 4.2 * math.cos(2.0 * w1 * t)
        return rx, ry, rz

    add_anim(anim_meta['head'], _rot_keys(anim_meta['head'], head_rot))

    # 4. Snapping / Clacking Venomous Forcipules (fang_l, fang_r)
    # Note: ModelEngine applies rotation keyframe as eff_ry = rest_ry - key_y.
    # For left fang (sx=-1, rest_ry=+16 outward-left), snapping inward-right requires eff_ry < +16 => key_y > 0 (+).
    # For right fang (sx=+1, rest_ry=-16 outward-right), snapping inward-left requires eff_ry > -16 => key_y < 0 (-).
    # Therefore key_y = -sx * 24.0 * env makes BOTH fangs flare wide when env<0 and SNAP SHUT when env>0!
    for fang_name, sx in anim_meta['fangs']:
        def fang_rot(t, side=sx):
            env = _fang_strike_envelope(t)
            quiver = 2.0 * math.sin(6.0 * w1 * t)
            clack_yaw = -side * (24.0 * env + quiver)
            pitch = -3.5 * env
            return pitch, clack_yaw, 0.0

        add_anim(fang_name, _rot_keys(fang_name, fang_rot))

    # 5. Multi-Jointed Whip Antennae
    for a1_name, a2_name, sx in anim_meta['antennae']:
        asym = 0.0 if sx < 0 else 1.35

        def ant_base(t, side=sx, off=asym):
            rx = 7.5 * math.sin(2.0 * w1 * t + off) + 3.0 * math.sin(5.0 * w1 * t - off)
            ry = side * (11.5 * math.sin(2.0 * w1 * t + off * 0.7) + 4.5 * math.cos(3.0 * w1 * t + off))
            rz = side * 4.0 * math.sin(3.0 * w1 * t + off)
            return rx, ry, rz

        def ant_tip(t, side=sx, off=asym):
            rx = 11.5 * math.sin(2.0 * w1 * t + off - 0.85) + 6.0 * math.sin(6.0 * w1 * t + off)
            ry = side * (16.5 * math.sin(2.0 * w1 * t + off * 0.7 - 0.95) + 7.5 * math.cos(5.0 * w1 * t - off))
            rz = side * 5.5 * math.cos(4.0 * w1 * t + off)
            return rx, ry, rz

        add_anim(a1_name, _rot_keys(a1_name, ant_base))
        add_anim(a2_name, _rot_keys(a2_name, ant_tip))

    # 6. Forked Tail Cerci Scissoring & Warning Flick
    for c_name, sx in anim_meta['cerci']:
        def cercus_rot(t, side=sx):
            rx = 6.5 * math.sin(2.0 * w1 * t + 0.6) + 3.0 * math.sin(4.0 * w1 * t)
            ry = side * (11.5 * math.sin(2.0 * w1 * t) - 4.5 * math.cos(4.0 * w1 * t))
            rz = side * 4.0 * math.sin(3.0 * w1 * t)
            return rx, ry, rz

        add_anim(c_name, _rot_keys(c_name, cercus_rot))

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
    root, elements, anim_meta = build_rig()
    anim = build_animation(anim_meta)
    blueprint = {
        'meta': {'format_version': '4.10', 'model_format': 'free', 'box_uv': False},
        'name': MODEL,
        'model_identifier': MODEL,
        'visible_box': [4, 4, 0],
        'resolution': {'width': 16, 'height': 16},
        'elements': elements,
        'outliner': [root],
        'textures': [texture_entry],
        'animations': [anim],
    }
    return blueprint, texture


# ---------------------------------------------------------------------------
# Sub-Quad Textured 3D Preview Renderer (faithful obsidian + crimson rims!)
# ---------------------------------------------------------------------------
def _eval_anim_at(model: dict, anim_time: float):
    rot_delta = {}
    pos_delta = {}
    if not model.get('animations'):
        return rot_delta, pos_delta
    anim = model['animations'][0]
    t = anim_time % anim['length']
    for animator in anim['animators'].values():
        bname = animator['name']
        for ch, store in (('rotation', rot_delta), ('position', pos_delta)):
            kfs = [k for k in animator['keyframes'] if k['channel'] == ch]
            if not kfs:
                continue
            lo = kfs[0]
            hi = kfs[-1]
            for i in range(len(kfs) - 1):
                if kfs[i]['time'] <= t <= kfs[i + 1]['time']:
                    lo, hi = kfs[i], kfs[i + 1]
                    break
            dt = max(1e-9, hi['time'] - lo['time'])
            w = max(0.0, min(1.0, (t - lo['time']) / dt))
            p0, p1 = lo['data_points'][0], hi['data_points'][0]
            store[bname] = [
                float(p0['x']) + (float(p1['x']) - float(p0['x'])) * w,
                float(p0['y']) + (float(p1['y']) - float(p0['y'])) * w,
                float(p0['z']) + (float(p1['z']) - float(p0['z'])) * w,
            ]
    return rot_delta, pos_delta


def _bilerp3(p00, p10, p11, p01, u, v):
    return tuple(
        (1 - u) * (1 - v) * p00[i] + u * (1 - v) * p10[i] + u * v * p11[i] + (1 - u) * v * p01[i]
        for i in range(3)
    )


def render_view(model: dict, texture: Image.Image, size=(560, 500), yaw=25.0, pitch=16.0,
                scale=18.5, centre=(0.0, 23.2, 0.0), anim_time=None, draw_player=True,
                title='') -> Image.Image:
    img = Image.new('RGB', size, (18, 20, 30))
    draw = ImageDraw.Draw(img)
    tex_px = texture.load()
    tw, th = texture.size

    rot_d, pos_d = ({}, {}) if anim_time is None else _eval_anim_at(model, anim_time)

    chains = {}

    def walk(nodes, chain):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            bname = node['name']
            rd = rot_d.get(bname, [0.0, 0.0, 0.0])
            pd = pos_d.get(bname, [0.0, 0.0, 0.0])
            eff_euler = [
                node['rotation'][0] + rd[0],
                node['rotation'][1] - rd[1],
                node['rotation'][2] - rd[2],
            ]
            eff_pos = [node['origin'][0] + pd[0], node['origin'][1] + pd[1], node['origin'][2] - pd[2]]
            own = chain + [(tuple(node['origin']), tuple(eff_pos), euler_zyx_to_matrix(eff_euler))]
            for ch in node.get('children', []):
                if isinstance(ch, str):
                    chains[ch] = own
            walk([c for c in node.get('children', []) if isinstance(c, dict)], own)

    walk(model['outliner'], [])

    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    light = _vnorm((-0.38, 0.74, -0.55))

    def cam_proj(pt):
        dx, dy, dz = pt[0] - centre[0], pt[1] - centre[1], pt[2] - centre[2]
        xr = dx * cy + dz * sy
        zr = -dx * sy + dz * cy
        yr = dy * cp - zr * sp
        zr2 = dy * sp + zr * cp
        return (size[0] * 0.5 - xr * scale, size[1] * 0.5 - yr * scale), -zr2

    quads = []

    if draw_player:
        player_boxes = [
            ((-4.0, 12.0, -2.0), (4.0, 24.0, 2.0), (54, 62, 82)),
            ((-8.0, 12.0, -2.0), (-4.0, 24.0, 2.0), (46, 54, 72)),
            ((4.0, 12.0, -2.0), (8.0, 24.0, 2.0), (46, 54, 72)),
            ((-4.0, 24.0, -4.0), (4.0, 32.0, 4.0), (68, 76, 98)),
            ((-2.8, 27.2, -4.05), (-1.2, 28.2, -3.95), (160, 185, 225)),
            ((1.2, 27.2, -4.05), (2.8, 28.2, -3.95), (160, 185, 225)),
        ]
        face_defs = [
            (((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)), (0, 0, -1)),
            (((0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1)), (0, 0, 1)),
            (((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)), (0, 1, 0)),
            (((0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)), (0, -1, 0)),
            (((1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)), (1, 0, 0)),
            (((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)), (-1, 0, 0)),
        ]
        for lo, hi, base_col in player_boxes:
            for keys, nrm in face_defs:
                pts3 = [(lo[0] + (hi[0] - lo[0]) * k[0],
                         lo[1] + (hi[1] - lo[1]) * k[1],
                         lo[2] + (hi[2] - lo[2]) * k[2]) for k in keys]
                proj = [cam_proj(p) for p in pts3]
                p2 = [p[0] for p in proj]
                area = ((p2[1][0] - p2[0][0]) * (p2[2][1] - p2[0][1])
                        - (p2[1][1] - p2[0][1]) * (p2[2][0] - p2[0][0]))
                if area >= 0:
                    continue
                lam = 0.58 + 0.42 * max(0.0, _vdot(nrm, light))
                col = tuple(_clamp8(c * lam) for c in base_col)
                depth = sum(p[1] for p in proj) / 4.0
                quads.append((depth, p2, col, (34, 40, 56)))

    sides_all = [
        (((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)), (0, 0, -1), 'north'),
        (((0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1)), (0, 0, 1), 'south'),
        (((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)), (0, 1, 0), 'up'),
        (((0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)), (0, -1, 0), 'down'),
        (((1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)), (1, 0, 0), 'east'),
        (((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)), (-1, 0, 0), 'west'),
    ]

    for elem in model['elements']:
        chain = chains.get(elem['uuid'], [])
        lo, hi = elem['from'], elem['to']
        corners = {}
        for ix in (0, 1):
            for iy in (0, 1):
                for iz in (0, 1):
                    pt = (lo[0] if ix == 0 else hi[0],
                          lo[1] if iy == 0 else hi[1],
                          lo[2] if iz == 0 else hi[2])
                    for rest_orig, eff_orig, rmat in reversed(chain):
                        rel = _vsub(pt, rest_orig)
                        pt = _vadd(eff_orig, _mvec(rmat, rel))
                    corners[(ix, iy, iz)] = pt

        is_plate = '_plate' in elem['name'] or 'head_shield' in elem['name']
        sub = 4 if is_plate else 2

        for keys, nrm, fname in sides_all:
            wnrm = nrm
            for _, _, rmat in reversed(chain):
                wnrm = _mvec(rmat, wnrm)
            q3 = [corners[k] for k in keys]
            proj_full = [cam_proj(p) for p in q3]
            p2_full = [p[0] for p in proj_full]
            area = ((p2_full[1][0] - p2_full[0][0]) * (p2_full[2][1] - p2_full[0][1])
                    - (p2_full[1][1] - p2_full[0][1]) * (p2_full[2][0] - p2_full[0][0]))
            if area >= 0:
                continue

            uv = elem['faces'][fname]['uv']
            lam = 0.65 + 0.48 * max(0.0, _vdot(wnrm, light))
            for iu in range(sub):
                for iv in range(sub):
                    u0, u1 = iu / sub, (iu + 1) / sub
                    v0, v1 = iv / sub, (iv + 1) / sub
                    sp3 = [
                        _bilerp3(q3[0], q3[1], q3[2], q3[3], u0, v0),
                        _bilerp3(q3[0], q3[1], q3[2], q3[3], u1, v0),
                        _bilerp3(q3[0], q3[1], q3[2], q3[3], u1, v1),
                        _bilerp3(q3[0], q3[1], q3[2], q3[3], u0, v1),
                    ]
                    sproj = [cam_proj(p) for p in sp3]
                    sp2 = [p[0] for p in sproj]
                    tx = int(((uv[0] + (uv[2] - uv[0]) * (u0 + u1) * 0.5) / 16.0) * (tw - 1))
                    ty = int(((uv[1] + (uv[3] - uv[1]) * (1.0 - (v0 + v1) * 0.5)) / 16.0) * (th - 1))
                    c = tex_px[max(0, min(tw - 1, tx)), max(0, min(th - 1, ty))]
                    col = tuple(_clamp8(c[k] * lam) for k in range(3))
                    depth = sum(p[1] for p in sproj) / 4.0
                    quads.append((depth, sp2, col, None))

    quads.sort(key=lambda q: q[0])
    for _, p2, col, rim in quads:
        draw.polygon(p2, fill=col, outline=rim)

    if title:
        try:
            from PIL import ImageFont
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 15)
        except Exception:
            from PIL import ImageFont
            font = ImageFont.load_default()
        draw.rectangle([8, 8, size[0] - 8, 34], fill=(12, 14, 22))
        draw.text((14, 12), title, fill=(248, 190, 251), font=font)
    return img


def render_preview_sheet(model: dict, texture: Image.Image, out_path: Path):
    panels = [
        render_view(model, texture, yaw=-24.0, pitch=18.0, scale=20.5, centre=(0.0, 23.8, 0.0),
                    anim_time=1.04, title='FRONT-LEFT 3/4 (Вид спереди: плечо, ключица и грудь)'),
        render_view(model, texture, yaw=162.0, pitch=20.0, scale=20.5, centre=(0.0, 24.0, 0.0),
                    anim_time=1.04, title='BACK 3/4 (S-изгиб по шее, лопаткам и плечам)'),
        render_view(model, texture, yaw=-82.0, pitch=14.0, scale=20.5, centre=(0.0, 24.0, 0.0),
                    anim_time=0.40, title='LEFT SHOULDER (Голова сколопендры над плечом)'),
        render_view(model, texture, yaw=0.0, pitch=86.0, scale=21.0, centre=(0.0, 23.5, 0.0),
                    anim_time=1.04, title='TOP COLLAR VIEW (Обхват шеи и плеч сверху)'),
        render_view(model, texture, yaw=-22.0, pitch=26.0, scale=36.0, centre=(-5.8, 25.0, -3.2),
                    anim_time=0.25, draw_player=False, title='ANIM t=0.25s: Жвалы широко раскрыты + волна лап'),
        render_view(model, texture, yaw=-22.0, pitch=26.0, scale=36.0, centre=(-5.8, 25.0, -3.2),
                    anim_time=1.04, draw_player=False, title='ANIM t=1.04s: Бросок и смыкание ядовитых жвал!'),
    ]
    pw, ph = panels[0].size
    sheet = Image.new('RGB', (pw * 2, ph * 3), (12, 14, 22))
    for idx, panel in enumerate(panels):
        sheet.paste(panel, ((idx % 2) * pw, (idx // 2) * ph))
    sheet.save(out_path, format='PNG')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', type=Path, default=HERE)
    ap.add_argument('--preview', action='store_true')
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    blueprint, texture = build_model()
    bb_path = args.out_dir / f'{MODEL}.bbmodel'
    tex_path = args.out_dir / f'{MODEL}.png'
    icon_dir = args.out_dir / 'assets' / 'reallyworld'
    (icon_dir / 'items').mkdir(parents=True, exist_ok=True)
    (icon_dir / 'models' / 'item' / 'freak').mkdir(parents=True, exist_ok=True)
    (icon_dir / 'textures' / 'item' / 'freak').mkdir(parents=True, exist_ok=True)

    bb_path.write_text(json.dumps(blueprint, separators=(',', ':')), encoding='utf-8')
    texture.save(tex_path, format='PNG', optimize=True)

    icon_img = build_menu_icon()
    icon_img.save(icon_dir / 'textures' / 'item' / 'freak' / 'centipede_icon.png', format='PNG', optimize=True)
    (icon_dir / 'models' / 'item' / 'freak' / 'centipede_icon.json').write_text(
        json.dumps({
            'parent': 'minecraft:item/generated',
            'textures': {'layer0': 'reallyworld:item/freak/centipede_icon'},
        }, indent=2) + '\n',
        encoding='utf-8',
    )
    (icon_dir / 'items' / 'centipede_icon.json').write_text(
        json.dumps({
            'model': {
                'type': 'minecraft:model',
                'model': 'reallyworld:item/freak/centipede_icon',
            }
        }, indent=2) + '\n',
        encoding='utf-8',
    )

    if args.preview:
        render_preview_sheet(blueprint, texture, args.out_dir / 'bug_preview.png')
    print(f'Built {bb_path.name}: {len(blueprint["elements"])} cubes, '
          f'{len(blueprint["animations"][0]["animators"])} animated bones, '
          f'texture {texture.width}x{texture.height}')


if __name__ == '__main__':
    main()
