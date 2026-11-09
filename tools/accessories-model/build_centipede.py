#!/usr/bin/env python3
"""Builds the Full-Body Crawling Tokyo Ghoul Scolopendra (elytrix_centipede).

Design (v6 — Full-Body 3-Wrap Helical Crawl):
- Canonical Tokyo Ghoul Chinese red-headed centipede (Scolopendra subspinipes mutilans):
  glossy jet-black/obsidian imbricated tergite carapace with blood-crimson rims,
  fiery scarlet-red cephalic shield with gleaming ocelli eye clusters & snapping
  black-tipped venomous forcipules (fangs), 2-jointed whip antennae, 28 vermilion
  clawed legs (14 pairs), and forked crimson tail cerci.
- Crawls continuously all over the player's ENTIRE body along a smooth C^infinity
  3-wrap closed helical trajectory (118+ Blockbench units = ~7.4 blocks per loop):
    * Wrap 1: Front chest -> Left collarbone -> Top of Left Shoulder -> Nape of Neck
              / Upper Back -> Top of Right Shoulder -> Front Right Chest
    * Wrap 2: Diagonally across Belly/Abs -> Left Hip -> Outer Left Thigh (y ~ 7.4)
              -> Lower Back / Tailbone -> Outer Right Thigh -> Right Hip
    * Wrap 3: Lower Stomach -> Outside of Left Arm (x ~ -9.1) -> Left & Right
              Shoulder Blades -> Outside of Right Arm (x ~ +9.1) -> Front Chest!
- Gimbal-lock-free 2-stage segment rig under static `body_root` ([0,0,0]):
    * `carrier_01..16` (empty non-root pivot bones, 0 cubes = 0 extra ItemDisplays):
      carry exact 3D curve position + continuous unwrapped Y-yaw (+1080 deg per loop).
    * `seg_01..16` (child renderer bones): carry smooth Z-pitch + surface-hugging
      X-roll so the dorsal obsidian-crimson carapace ALWAYS faces outward from the
      skin/armor while the 28 legs hug and scurry across the body surface!
- 100% ZERO per-cube rotations (every cube has rotation [0, 0, 0]) so ModelEngine
  4.1.0's RotationSolver never crashes on Paper's fastutil.
"""
import argparse
import base64
import bisect
import io
import json
import math
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
MODEL = 'elytrix_centipede'
ROOT_ORIGIN = [0.0, 0.0, 0.0]

NUM_SEGS = 16
SEG_SPACING = 2.45                      # ~39-unit (2.45-block) giant Tokyo Ghoul scolopendra
LEG_SEG_INDICES = tuple(range(2, 16))   # seg_02 .. seg_15 carry 14 pairs = 28 legs

ANIM_LENGTH = 10.8                      # 10.8 s per 3-wrap full-body tour (~11 units/s)
ANIM_STEPS = 108                        # 0.10 s (2 ticks) per keyframe, 109 keys (0..108)
SUB_ANIM_STEPS = 72                     # 0.15 s (3 ticks) for legs/fangs/antennae/cerci

# 18 waypoints forming 3 smooth counter-clockwise helical wraps around the entire body
# (Front -Z -> Left -X -> Back +Z -> Right +X -> Front -Z, x3!)
WAYPOINTS = [
    # --- WRAP 1: Upper chest, both shoulders & nape of neck ---
    ( 0.5, 20.5, -3.42),   # 0: center-right upper chest (front)
    (-4.6, 23.2, -3.12),   # 1: climbing toward left collarbone
    (-6.4, 25.35, 0.20),   # 2: cresting OVER TOP of left shoulder
    (-0.5, 24.55, 3.48),   # 3: across nape of neck / upper back
    ( 6.4, 25.35, 0.40),   # 4: cresting OVER TOP of right shoulder
    ( 4.8, 20.4, -3.18),   # 5: descending front-right chest
    # --- WRAP 2: Belly, hips, both upper thighs & lower back ---
    (-0.8, 15.2, -3.42),   # 6: diagonally across stomach / abs
    (-5.1, 10.8, -2.55),   # 7: down to left front hip
    (-5.25, 7.35, 1.20),   # 8: wrapping around outer left upper thigh
    ( 0.0,  8.85, 3.38),   # 9: across lower back / tailbone (clear of Kagune at y=14.4!)
    ( 5.25, 7.55, 1.00),   # 10: wrapping around outer right upper thigh
    ( 4.5, 10.0, -3.08),   # 11: climbing right front thigh / hip
    # --- WRAP 3: Lower belly, outside of both arms & upper-mid back ---
    (-1.4, 12.6, -3.42),   # 12: lower belly
    (-9.15, 16.8, -0.30),  # 13: wrapping around OUTSIDE of left arm
    (-4.8, 20.9,  3.42),   # 14: climbing left shoulder blade (above Kagune knot!)
    ( 4.8, 21.3,  3.42),   # 15: across upper-mid back
    ( 9.15, 18.6,  0.20),  # 16: wrapping around OUTSIDE of right arm
    ( 5.0, 19.2, -3.18),   # 17: front right ribs -> closes seamlessly into 0!
]


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'elytrix-centipede-v6:{tag}'))


def _clamp8(v: float) -> int:
    return max(0, min(255, int(round(v))))


# ---------------------------------------------------------------------------
# Vector & Matrix Math (exact match to Blockbench / ModelEngine rotateZYX)
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
    rx, ry, rz = euler
    return _mmul(_mmul(_rot_axis(2, rz), _rot_axis(1, ry)), _rot_axis(0, rx))


# ---------------------------------------------------------------------------
# Smooth Closed 3-Wrap Full-Body Curve & Continuous Gimbal-Free Frame Field
# ---------------------------------------------------------------------------
def _catmull_rom_closed(pts, u: float):
    n = len(pts)
    s = (u % 1.0) * n
    i = int(math.floor(s)) % n
    t = s - math.floor(s)
    p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
    t2, t3 = t * t, t * t * t
    return tuple(
        0.5 * (
            2.0 * p1[k]
            + (-p0[k] + p2[k]) * t
            + (2.0 * p0[k] - 5.0 * p1[k] + 4.0 * p2[k] - p3[k]) * t2
            + (-p0[k] + 3.0 * p1[k] - 3.0 * p2[k] + p3[k]) * t3
        )
        for k in range(3)
    )


def _smooth_surface_push(pt):
    """Smoothly repels points outside the player's torso, legs, and arms (with armor clearance)."""
    x, y, z = pt
    # Torso & upper-leg superellipsoid clearance (+armor margin)
    if 4.5 <= y <= 24.6:
        wy = 1.0 if y <= 23.6 else max(0.0, (24.6 - y) / 1.0)
        sx = x / 5.02
        sz = z / 3.48
        r4 = (sx ** 4 + sz ** 4) ** 0.25
        if 1e-6 < r4 < 1.0:
            scale = 1.0 + wy * (1.0 / r4 - 1.0)
            x *= scale
            z *= scale
    # Left & right arms superellipsoid clearance (x ~ +-6.25, y ~ 18.0)
    for sign in (-1.0, 1.0):
        cx = sign * 6.25
        cy = 18.0
        dx = (x - cx) / 2.98
        dy = (y - cy) / 7.15
        dz = z / 3.35
        r4 = (dx ** 4 + dy ** 4 + dz ** 4) ** 0.25
        if 1e-6 < r4 < 1.0:
            inv = 1.0 / r4
            x = cx + (x - cx) * inv
            y = cy + (y - cy) * inv
            z = z * inv
    # Head box clearance (y >= 24.0, |x| < 4.5, |z| < 4.5)
    if y > 23.9:
        hx = x / 4.55
        hz = z / 4.55
        hr4 = (hx ** 4 + hz ** 4) ** 0.25
        if 1e-6 < hr4 < 1.0 and y > 24.2:
            inv = 1.0 / hr4
            x *= inv
            z *= inv
    return (x, y, z)


class FullBodyTrack:
    """Arc-length parameterized C^inf closed 3-wrap track with unwrapped (yaw, pitch, roll)."""

    def __init__(self, dense_n: int = 1800, arc_n: int = 1440):
        raw = [_smooth_surface_push(_catmull_rom_closed(WAYPOINTS, i / dense_n))
               for i in range(dense_n)]
        for sigma in (22.0, 14.0):
            sm = []
            w_rad = int(3 * sigma)
            for i in range(dense_n):
                sx = sy = sz = sw = 0.0
                for d in range(-w_rad, w_rad + 1):
                    w = math.exp(-0.5 * (d / sigma) ** 2)
                    px, py, pz = raw[(i + d) % dense_n]
                    sx += w * px
                    sy += w * py
                    sz += w * pz
                    sw += w
                sm.append(_smooth_surface_push((sx / sw, sy / sw, sz / sw)))
            raw = sm

        curve = []
        for i in range(dense_n):
            sx = sy = sz = sw = 0.0
            for d in range(-36, 37):
                w = math.exp(-0.5 * (d / 12.0) ** 2)
                px, py, pz = raw[(i + d) % dense_n]
                sx += w * px
                sy += w * py
                sz += w * pz
                sw += w
            curve.append((sx / sw, sy / sw, sz / sw))

        cum = [0.0]
        for i in range(1, dense_n + 1):
            cum.append(cum[-1] + math.dist(curve[i - 1], curve[i % dense_n]))
        self.total_length = cum[-1]

        def sample_raw_arc(s_mod: float):
            target = (s_mod % 1.0) * self.total_length
            idx = max(0, min(dense_n - 1, bisect.bisect_right(cum, target) - 1))
            denom = cum[idx + 1] - cum[idx]
            t = (target - cum[idx]) / denom if denom > 1e-9 else 0.0
            a, b = curve[idx], curve[(idx + 1) % dense_n]
            return (a[0] + (b[0] - a[0]) * t,
                    a[1] + (b[1] - a[1]) * t,
                    a[2] + (b[2] - a[2]) * t)

        self.arc_n = arc_n
        self.pts = [sample_raw_arc(i / arc_n) for i in range(arc_n)]

        # Precompute periodic pitch & roll, and unwrapped yaw over [0, 1]
        self.yaws = []
        self.pitches = []
        self.rolls = []
        self.frames = []
        prev_yaw = None
        prev_roll = None
        for i in range(arc_n + 1):
            idx = i % arc_n
            p = self.pts[idx]
            p_prev = self.pts[(idx - 1) % arc_n]
            p_next = self.pts[(idx + 1) % arc_n]
            fwd = _vnorm(_vsub(p_next, p_prev))  # local +X = forward toward head!

            yc = max(8.5, min(22.5, p[1]))
            n_raw = _vnorm((p[0] / 7.5, (p[1] - yc) / 6.5, p[2] / 3.4))
            proj = _vdot(n_raw, fwd)
            up = _vnorm(_vsub(n_raw, _vmul(fwd, proj)))   # local +Y = dorsal carapace UP!
            right = _vcross(fwd, up)                      # local +Z = right flank!

            pitch = math.degrees(math.asin(max(-1.0, min(1.0, fwd[1]))))
            yaw = math.degrees(math.atan2(-fwd[2], fwd[0]))
            if prev_yaw is not None:
                yaw = prev_yaw + ((yaw - prev_yaw + 180.0) % 360.0 - 180.0)
            prev_yaw = yaw

            m0 = _mmul(_rot_axis(1, yaw), _rot_axis(2, pitch))
            u0 = (m0[0][1], m0[1][1], m0[2][1])
            r0 = (m0[0][2], m0[1][2], m0[2][2])
            roll = math.degrees(math.atan2(_vdot(up, r0), _vdot(up, u0)))
            if prev_roll is not None:
                roll = prev_roll + ((roll - prev_roll + 180.0) % 360.0 - 180.0)
            prev_roll = roll

            self.yaws.append(yaw)
            self.pitches.append(pitch)
            self.rolls.append(roll)
            self.frames.append((fwd, up, right))

        self.yaw_winding = round((self.yaws[-1] - self.yaws[0]) / 360.0) * 360.0
        self.roll_winding = round((self.rolls[-1] - self.rolls[0]) / 360.0) * 360.0

    def eval(self, s_continuous: float):
        """Evaluates (pos, yaw, pitch, roll, frame_mat) smoothly for ANY real s_continuous."""
        laps = math.floor(s_continuous)
        frac = s_continuous - laps
        f_idx = frac * self.arc_n
        i0 = int(math.floor(f_idx))
        if i0 >= self.arc_n:
            i0 = self.arc_n - 1
            w = 1.0
        else:
            w = f_idx - i0
        i1 = i0 + 1

        p0 = self.pts[i0 % self.arc_n]
        p1 = self.pts[i1 % self.arc_n]
        pos = tuple(p0[k] + (p1[k] - p0[k]) * w for k in range(3))

        yaw = (self.yaws[i0] + (self.yaws[i1] - self.yaws[i0]) * w) + laps * self.yaw_winding
        pitch = self.pitches[i0] + (self.pitches[i1] - self.pitches[i0]) * w
        roll = (self.rolls[i0] + (self.rolls[i1] - self.rolls[i0]) * w) + laps * self.roll_winding

        mat = _mmul(_rot_axis(1, yaw), _mmul(_rot_axis(2, pitch), _rot_axis(0, roll)))
        return pos, yaw, pitch, roll, mat


# ---------------------------------------------------------------------------
# 128x128 Procedural Pixel-Art Texture (Oriented for Local +X Forward, +-Z Width!)
# ---------------------------------------------------------------------------
UV_REGIONS = {
    'tergite_top':   (0.0,  0.0,  8.0,  4.0),   # 0..64 x 0..32: obsidian carapace + lateral crimson rims
    'tergite_ridge': (0.0,  4.0,  8.0,  6.0),   # 0..64 x 32..48: glossy obsidian dorsal crown + ruby lip
    'tergite_side':  (0.0,  6.0,  8.0,  8.0),   # 0..64 x 48..64: obsidian upper + blood-crimson lower rim
    'sternite':      (0.0,  8.0,  8.0, 10.5),   # 0..64 x 64..84: dark mahogany-crimson belly
    'pleuron':       (0.0, 10.5,  8.0, 13.0),   # 0..64 x 84..104: dark chitin socket
    'claw_black':    (0.0, 13.0,  8.0, 16.0),   # 0..64 x 104..128: glossy pitch-black venom tips/claws
    'head_top':      (8.0,  0.0, 16.0,  4.0),   # 64..128 x 0..32: fiery Tokyo Ghoul scarlet head shield
    'eye_cluster':   (8.0,  4.0, 12.0,  8.0),   # 64..96 x 32..64: black ocelli cluster + glints
    'fang_crimson':  (12.0, 4.0, 16.0,  8.0),   # 96..128 x 32..64: scarlet-to-obsidian forcipule
    'leg_orange':    (8.0,  8.0, 16.0, 12.0),   # 64..128 x 64..96: vermilion/red-orange cylindrical limb
    'antenna_ring':  (8.0, 12.0, 16.0, 16.0),   # 64..128 x 96..128: segmented red-orange antennomeres
}


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

    # 1. Tergite Top (x: 0..64 along X length: x=0 posterior -> x=63 anterior;
    #                 y: 0..32 across Z width: y=0 & y=31 are left/right crimson margins!)
    for y in range(0, 32):
        lat = (y - 15.5) / 15.5
        alat = abs(lat)
        for x in range(0, 64):
            u_len = x / 63.0   # 0 = posterior overlap lip, 1 = anterior
            g = micro_grain(x, y) * 3.5
            r, gr, b = 13.0 + g, 8.0 + g * 0.4, 15.0 + g * 0.6

            # Crisp blood-crimson lateral margins (alat > 0.74)
            if alat > 0.74:
                edge_t = min(1.0, (alat - 0.74) / 0.26) ** 1.2
                r = r * (1.0 - edge_t) + 196.0 * edge_t
                gr = gr * (1.0 - edge_t) + 18.0 * edge_t
                b = b * (1.0 - edge_t) + 32.0 * edge_t

            # Sharp posterior ruby-crimson imbricated rim (u_len < 0.20)
            if u_len < 0.20:
                lip_t = ((0.20 - u_len) / 0.20) ** 1.2
                r = r * (1.0 - lip_t * 0.9) + 202.0 * lip_t * 0.9
                gr = gr * (1.0 - lip_t * 0.9) + 20.0 * lip_t * 0.9
                b = b * (1.0 - lip_t * 0.9) + 36.0 * lip_t * 0.9

            # Anterior overlap occlusion (u_len > 0.84)
            if u_len > 0.84:
                occ = 0.48 + 0.52 * ((1.0 - u_len) / 0.16)
                r, gr, b = r * occ, gr * occ, b * occ

            # Paramedian longitudinal grooves along length
            groove = math.exp(-((alat - 0.32) / 0.045) ** 2)
            r *= 1.0 - 0.40 * groove
            gr *= 1.0 - 0.40 * groove
            b *= 1.0 - 0.35 * groove

            # Glossy wet-chitin specular sheen down dorsal spine
            spec = math.exp(-(lat / 0.18) ** 2) * math.exp(-((u_len - 0.50) / 0.28) ** 2)
            r += 64.0 * spec
            gr += 50.0 * spec
            b += 68.0 * spec
            px[x, y] = (_clamp8(r), _clamp8(gr), _clamp8(b), 255)

    # 2. Tergite Raised Dorsal Ridge (x: 0..64, y: 32..48)
    for y in range(32, 48):
        lat = ((y - 32) - 7.5) / 7.5
        for x in range(0, 64):
            u_len = x / 63.0
            g = micro_grain(x, y) * 3.0
            r, gr, b = 16.0 + g, 10.0 + g * 0.4, 20.0 + g * 0.6
            if u_len < 0.18:
                lt = (0.18 - u_len) / 0.18
                r = r * (1.0 - lt) + 184.0 * lt
                gr = gr * (1.0 - lt) + 18.0 * lt
                b = b * (1.0 - lt) + 32.0 * lt
            spec = math.exp(-(lat / 0.26) ** 2) * (0.4 + 0.6 * math.sin(u_len * math.pi))
            r += 58.0 * spec
            gr += 46.0 * spec
            b += 64.0 * spec
            px[x, y] = (_clamp8(r), _clamp8(gr), _clamp8(b), 255)

    # 3. Tergite Lateral Rim (x: 0..64, y: 48..64)
    for y in range(48, 64):
        v = (y - 48) / 15.0
        for x in range(0, 64):
            g = micro_grain(x, y) * 4.0
            rim = max(0.0, (v - 0.35) / 0.65) ** 1.15
            r = 16.0 * (1.0 - rim) + 188.0 * rim + g
            gr = 9.0 * (1.0 - rim) + 18.0 * rim
            b = 16.0 * (1.0 - rim) + 32.0 * rim
            px[x, y] = (_clamp8(r), _clamp8(gr), _clamp8(b), 255)

    # 4. Ventral Sternite Belly (x: 0..64, y: 64..84)
    for y in range(64, 84):
        lat = abs(((y - 64) - 9.5) / 9.5)
        cyl = 1.0 - 0.42 * (lat ** 1.6)
        for x in range(0, 64):
            u = x / 63.0
            r = (68.0 + 22.0 * math.sin(u * math.pi)) * cyl
            gr = (16.0 + 6.0 * math.sin(u * math.pi)) * cyl
            b = (20.0 + 6.0 * math.sin(u * math.pi)) * cyl
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
        lat = (y - 15.5) / 15.5
        alat = abs(lat)
        for x in range(64, 128):
            u = (x - 64) / 63.0
            g = micro_grain(x, y) * 5.0
            dome = (1.0 - 0.40 * (alat ** 1.8)) * (1.0 - 0.22 * ((u - 0.55) ** 2) * 3.0)
            r = 152.0 + 102.0 * dome + g
            gr = 14.0 + 34.0 * (dome ** 1.6) + g * 0.3
            b = 18.0 + 24.0 * (dome ** 1.6) + g * 0.3

            suture = math.exp(-(alat / 0.045) ** 2) * (1.0 if u < 0.58 else 0.0)
            r *= 1.0 - 0.28 * suture
            gr *= 1.0 - 0.34 * suture

            spec = math.exp(-((lat + 0.12) / 0.22) ** 2) * math.exp(-((u - 0.62) / 0.22) ** 2)
            r += 56.0 * spec
            gr += 66.0 * spec
            b += 50.0 * spec
            px[x, y] = (_clamp8(r), _clamp8(gr), _clamp8(b), 255)

    # 8. Ocelli Eye Cluster (x: 64..96, y: 32..64)
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
            u = (x - 96) / 31.0
            cyl = 1.0 - 0.42 * ((v - 0.5) * 2.0) ** 2
            venom = min(1.0, max(0.0, (u - 0.30) / 0.62)) ** 1.25
            r = (236.0 * (1.0 - venom) + 12.0 * venom) * cyl
            gr = (30.0 * (1.0 - venom) + 7.0 * venom) * cyl
            b = (26.0 * (1.0 - venom) + 12.0 * venom) * cyl
            spec = math.exp(-(((v - 0.45) * 2.0) / 0.25) ** 2) * 42.0
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
# ---------------------------------------------------------------------------
def build_menu_icon() -> Image.Image:
    size = 32
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    px = img.load()

    pts = []
    for i in range(61):
        t = i / 60.0
        ang = 0.32 * math.pi + t * 1.52 * math.pi
        rad = 9.2 - 1.2 * t + 1.8 * math.sin(t * math.pi * 2.0)
        cx = 16.2 + math.cos(ang) * rad
        cy = 16.5 + math.sin(ang) * rad * 0.88
        pts.append((cx, cy, t))

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
                        px[xx, yy] = (68, 52, 74, 255)
                    else:
                        px[xx, yy] = (20, 12, 22, 255)

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
# Local bone convention: +X = forward toward head, +Y = dorsal up, +-Z = flanks
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


# ---------------------------------------------------------------------------
# Full Scolopendra Rig Construction (53 drawn bones + 17 empty carrier/root pivots)
# ---------------------------------------------------------------------------
def build_rig():
    all_elements = []
    carrier_bones = []
    anim_meta = {
        'carriers': [],
        'segs': [],
        'legs': [],
        'head': 'head',
        'fangs': [],
        'antennae': [],
        'cerci': [],
    }

    zero = [0.0, 0.0, 0.0]

    for idx in range(1, NUM_SEGS + 1):
        carrier_name = f'carrier_{idx:02d}'
        seg_name = f'seg_{idx:02d}'

        u = (idx - 1) / (NUM_SEGS - 1)
        taper = math.sin(math.pi * (0.16 + 0.72 * u))
        half_w = round(1.36 + 0.44 * taper, 3)     # width along +-Z
        half_len = 1.36 if idx < NUM_SEGS else 1.18  # length along +-X (+X = forward)

        seg_cubes = [
            make_cube(
                f'{seg_name}_plate', zero,
                (-half_len - 0.16, -0.28, -half_w), (half_len, 0.58, half_w),
                {'up': 'tergite_top', 'down': 'sternite', 'default': 'tergite_side'},
            ),
            make_cube(
                f'{seg_name}_ridge', zero,
                (-half_len - 0.22, 0.54, -half_w * 0.68), (half_len * 0.88, 0.96, half_w * 0.68),
                {'default': 'tergite_ridge'},
            ),
            make_cube(
                f'{seg_name}_belly', zero,
                (-half_len * 0.80, -0.68, -half_w * 0.65), (half_len * 0.80, -0.24, half_w * 0.65),
                {'up': 'sternite', 'down': 'sternite', 'default': 'pleuron'},
            ),
        ]
        all_elements.extend(seg_cubes)
        child_bones = []

        # 28 Jointed Vermilion Legs extending laterally along +-Z and gripping downward (-Y)
        if idx in LEG_SEG_INDICES:
            leg_scale = 0.88 + 0.22 * taper
            for side_tag, sz in (('l', -1.0), ('r', 1.0)):
                leg_name = f'leg_{side_tag}_{idx:02d}'
                hip_origin = [0.0, -0.16, round(sz * (half_w - 0.14), 4)]
                leg_rest_rot = [sz * 8.0, sz * -6.0, 0.0]
                L1 = 1.24 * leg_scale
                L2 = 2.22 * leg_scale
                L3 = 2.82 * leg_scale
                leg_cubes = [
                    make_cube(
                        f'{leg_name}_femur', hip_origin,
                        (-0.25, -0.18, 0.0), (0.25, 0.32, sz * L1),
                        {'default': 'leg_orange'},
                    ),
                    make_cube(
                        f'{leg_name}_tibia', hip_origin,
                        (-0.21, -0.72, sz * (L1 - 0.18)), (0.21, 0.15, sz * L2),
                        {'default': 'leg_orange'},
                    ),
                    make_cube(
                        f'{leg_name}_claw', hip_origin,
                        (-0.16, -1.46, sz * (L2 - 0.22)), (0.16, -0.54, sz * L3),
                        {'down': 'claw_black', 'default': 'leg_orange'},
                    ),
                ]
                all_elements.extend(leg_cubes)
                child_bones.append(make_bone(leg_name, hip_origin, leg_rest_rot, leg_cubes))
                anim_meta['legs'].append((leg_name, idx, sz))

        # Predatory Fiery Crimson Head + Snapping Fangs + 2-Stage Whip Antennae on seg_01
        if idx == 1:
            h_origin = [2.25, 0.04, 0.0]
            head_cubes = [
                make_cube(
                    'head_shield', h_origin,
                    (-1.12, -0.32, -1.70), (1.82, 0.66, 1.70),
                    {'up': 'head_top', 'down': 'sternite', 'default': 'head_top'},
                ),
                make_cube(
                    'head_dome', h_origin,
                    (-0.90, 0.60, -1.20), (1.38, 1.05, 1.20),
                    {'default': 'head_top'},
                ),
                make_cube(
                    'head_brow', h_origin,
                    (1.68, -0.18, -1.22), (2.38, 0.48, 1.22),
                    {'default': 'head_top'},
                ),
                make_cube(
                    'head_eyes_l', h_origin,
                    (0.80, 0.06, -1.86), (1.64, 0.56, -1.46),
                    {'default': 'eye_cluster'},
                ),
                make_cube(
                    'head_eyes_r', h_origin,
                    (0.80, 0.06, 1.46), (1.64, 0.56, 1.86),
                    {'default': 'eye_cluster'},
                ),
            ]
            all_elements.extend(head_cubes)
            head_children = []

            # Venomous forcipules (fang_l at -Z, fang_r at +Z) curving forward (+X) & inward
            for side_tag, sz in (('l', -1.0), ('r', 1.0)):
                fang_name = f'fang_{side_tag}'
                f_origin = [h_origin[0] + 1.52, h_origin[1] - 0.26, sz * 1.35]
                f_rot = [0.0, sz * -16.0, -5.0]
                fang_cubes = [
                    make_cube(
                        f'{fang_name}_base', f_origin,
                        (-0.18, -0.26, -sz * 0.10), (1.22, 0.26, sz * 0.94),
                        {'default': 'fang_crimson'},
                    ),
                    make_cube(
                        f'{fang_name}_mid', f_origin,
                        (1.08, -0.22, sz * 0.14), (2.22, 0.20, sz * 0.84),
                        {'default': 'fang_crimson'},
                    ),
                    make_cube(
                        f'{fang_name}_tip', f_origin,
                        (2.06, -0.18, -sz * 0.58), (2.88, 0.15, sz * 0.40),
                        {'default': 'claw_black'},
                    ),
                ]
                all_elements.extend(fang_cubes)
                head_children.append(make_bone(fang_name, f_origin, f_rot, fang_cubes))
                anim_meta['fangs'].append((fang_name, sz))

            # 2-Stage Whip Antennae probing forward (+X) and outward (+-Z)
            for side_tag, sz in (('l', -1.0), ('r', 1.0)):
                a1_name = f'ant_{side_tag}1'
                a2_name = f'ant_{side_tag}2'
                a1_origin = [h_origin[0] + 2.24, h_origin[1] + 0.18, sz * 0.78]
                a1_rot = [0.0, sz * -22.0, 8.0]
                a1_cubes = [
                    make_cube(f'{a1_name}_s1', a1_origin, (-0.08, -0.18, -0.22), (1.02, 0.20, 0.22),
                              {'default': 'antenna_ring'}),
                    make_cube(f'{a1_name}_s2', a1_origin, (0.96, -0.15, -0.19), (2.00, 0.18, 0.19),
                              {'default': 'antenna_ring'}),
                    make_cube(f'{a1_name}_s3', a1_origin, (1.94, -0.13, -0.17), (2.88, 0.16, 0.17),
                              {'default': 'antenna_ring'}),
                ]
                a1_mat = euler_zyx_to_matrix(a1_rot)
                tip_off = _mvec(a1_mat, (2.82, 0.0, 0.0))
                a2_origin = [round(a1_origin[k] + tip_off[k], 4) for k in range(3)]
                a2_rot = [0.0, sz * -14.0, -10.0]
                a2_cubes = [
                    make_cube(f'{a2_name}_s1', a2_origin, (-0.06, -0.13, -0.15), (0.96, 0.15, 0.15),
                              {'default': 'antenna_ring'}),
                    make_cube(f'{a2_name}_s2', a2_origin, (0.90, -0.14, -0.12), (1.88, 0.11, 0.12),
                              {'default': 'antenna_ring'}),
                    make_cube(f'{a2_name}_tip', a2_origin, (1.82, -0.18, -0.09), (2.72, 0.08, 0.09),
                              {'east': 'claw_black', 'default': 'antenna_ring'},
                    ),
                ]
                all_elements.extend(a1_cubes + a2_cubes)
                a2_bone = make_bone(a2_name, a2_origin, a2_rot, a2_cubes)
                a1_bone = make_bone(a1_name, a1_origin, a1_rot, a1_cubes, [a2_bone])
                head_children.append(a1_bone)
                anim_meta['antennae'].append((a1_name, a2_name, sz))

            child_bones.append(make_bone('head', h_origin, zero, head_cubes, head_children))

        # Forked Tail Cerci trailing behind (-X) on seg_16
        if idx == NUM_SEGS:
            for side_tag, sz in (('l', -1.0), ('r', 1.0)):
                c_name = f'cercus_{side_tag}'
                c_origin = [-1.12, 0.05, sz * 0.72]
                c_rot = [0.0, sz * 22.0, 6.0]
                c_cubes = [
                    make_cube(f'{c_name}_s1', c_origin, (-1.42, -0.20, -0.26), (0.10, 0.26, 0.26),
                              {'default': 'leg_orange'}),
                    make_cube(f'{c_name}_s2', c_origin, (-2.74, -0.17, -0.20), (-1.32, 0.22, 0.20),
                              {'default': 'fang_crimson'}),
                    make_cube(f'{c_name}_tip', c_origin, (-3.82, -0.15, -0.15), (-2.64, 0.16, 0.15),
                              {'west': 'claw_black', 'default': 'claw_black'}),
                ]
                all_elements.extend(c_cubes)
                child_bones.append(make_bone(c_name, c_origin, c_rot, c_cubes))
                anim_meta['cerci'].append((c_name, sz))

        seg_bone = make_bone(seg_name, zero, zero, seg_cubes, child_bones)
        carrier_bone = make_bone(carrier_name, zero, zero, [], [seg_bone])
        carrier_bones.append(carrier_bone)
        anim_meta['carriers'].append((carrier_name, idx))
        anim_meta['segs'].append((seg_name, idx))

    root = make_bone('body_root', ROOT_ORIGIN, zero, [], carrier_bones)
    return root, all_elements, anim_meta


# ---------------------------------------------------------------------------
# Full-Body Crawl Keyframe Generator (Exact ModelEngine 4.1.0 Sign Laws!)
#
# Verified from BlockbenchParser.class lines 161-162 & 192-197:
# - Non-root child with rest origin [0,0,0] -> target Blockbench pos [X, Y, Z]:
#     POSITION keyframe = [-X, +Y, +Z]
# - Bone with rest rotation [rx, ry, rz] -> target Blockbench rot [Rx, Ry, Rz]:
#     ROTATION keyframe = [rx - Rx, ry - Ry, Rz - rz]
#   (and for delta [dx, dy, dz] added to rest: keyframe = [-dx, -dy, +dz])
# ---------------------------------------------------------------------------
def _make_rot_series(bone_name: str, steps: int, fn, close_exact: bool = True):
    keys = []
    for step in range(steps + 1):
        t = ANIM_LENGTH * step / steps
        kx, ky, kz = fn(t, step / steps)
        keys.append({
            'channel': 'rotation',
            'data_points': [{'x': str(round(kx, 3)), 'y': str(round(ky, 3)), 'z': str(round(kz, 3))}],
            'uuid': uid(f'rkey:{bone_name}:{step}'),
            'time': round(t, 4),
            'color': -1,
            'interpolation': 'linear',
        })
    if close_exact:
        keys[-1]['data_points'] = [dict(p) for p in keys[0]['data_points']]
    return keys


def _make_pos_series(bone_name: str, steps: int, fn):
    keys = []
    for step in range(steps + 1):
        t = ANIM_LENGTH * step / steps
        px, py, pz = fn(t, step / steps)
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


def _fang_strike_envelope(u_norm: float) -> float:
    w = 2.0 * math.pi * u_norm
    base = -0.40 * math.sin(3.0 * w) - 0.20 * math.sin(6.0 * w)
    snap = 0.0
    for center in (0.14, 0.22, 0.48, 0.56, 0.81, 0.89):
        du = ((u_norm - center + 0.5) % 1.0) - 0.5
        snap += 1.45 * math.exp(-((du / 0.024) ** 2))
    return base + snap


def build_animation(anim_meta: dict, track: FullBodyTrack):
    animators = {}
    ds_seg = SEG_SPACING / track.total_length
    ds_head = 2.35 / track.total_length

    def add_anim(bone_name: str, keyframes: list):
        animators[uid(f'bone:{bone_name}')] = {
            'name': bone_name,
            'type': 'bone',
            'keyframes': keyframes,
        }

    # 1. Carrier (3D full-body position + unwrapped Y-yaw) & Segment (pitch + surface roll + S-wave)
    for idx in range(1, NUM_SEGS + 1):
        carrier_name = f'carrier_{idx:02d}'
        seg_name = f'seg_{idx:02d}'
        s_offset = -(idx - 1) * ds_seg
        wave_phase = idx * 0.62

        def carrier_pos(_t, u_norm, s0=s_offset):
            pos, _, _, _, _ = track.eval(s0 + u_norm)
            # Blockbench [X, Y, Z] -> ModelEngine non-root POSITION [-X, +Y, +Z]
            return (-pos[0], pos[1], pos[2])

        def carrier_rot(_t, u_norm, s0=s_offset):
            _, yaw, _, _, _ = track.eval(s0 + u_norm)
            # Rest [0,0,0] -> target [0, yaw, 0] => key = [0, -yaw, 0] (unwrapped +1080 deg!)
            return (0.0, -yaw, 0.0)

        def seg_rot(_t, u_norm, s0=s_offset, ph=wave_phase):
            _, _, pitch, roll, _ = track.eval(s0 + u_norm)
            # Subtle organic lateral S-undulation while crawling (6 waves per 10.8s lap)
            s_wave = 6.0 * 2.0 * math.pi * u_norm - ph
            wiggle_yaw = 4.5 * math.sin(s_wave)
            wiggle_roll = 3.0 * math.cos(s_wave)
            # Target Blockbench [Rx, Ry, Rz] = [roll + wiggle_roll, wiggle_yaw, pitch]
            # Keyframe = [-Rx, -Ry, +Rz]
            return (-(roll + wiggle_roll), -wiggle_yaw, pitch)

        add_anim(
            carrier_name,
            _make_pos_series(carrier_name, ANIM_STEPS, carrier_pos)
            + _make_rot_series(carrier_name, ANIM_STEPS, carrier_rot, close_exact=False),
        )
        add_anim(seg_name, _make_rot_series(seg_name, ANIM_STEPS, seg_rot, close_exact=True))

    # 2. Curve-Following Predatory Head Steering + Snapping Lunge
    def head_rot(_t, u_norm):
        _, yaw1, pitch1, _, mat1 = track.eval(u_norm)
        _, _, _, _, mat_h = track.eval(u_norm + ds_head)
        # Relative forward vector of s_head in seg_01's local frame:
        fwd_h = (mat_h[0][0], mat_h[1][0], mat_h[2][0])
        rel_fwd = _mvec(_mtranspose(mat1), fwd_h)
        steer_yaw = math.degrees(math.atan2(-rel_fwd[2], max(0.2, rel_fwd[0])))
        steer_pitch = math.degrees(math.asin(max(-0.85, min(0.85, rel_fwd[1]))))

        w = 2.0 * math.pi * u_norm
        strike = max(0.0, _fang_strike_envelope(u_norm))
        scan_yaw = steer_yaw * 0.75 + 7.5 * math.sin(5.0 * w)
        scan_pitch = steer_pitch * 0.75 - 4.0 * strike + 2.5 * math.cos(6.0 * w)
        scan_roll = 4.0 * math.sin(6.0 * w)
        return (-scan_roll, -scan_yaw, scan_pitch)

    add_anim(anim_meta['head'], _make_rot_series(anim_meta['head'], ANIM_STEPS, head_rot, close_exact=True))

    # 3. Fast Metachronal Scurrying Wave on all 28 Legs (14 step cycles per 10.8s lap!)
    for leg_name, idx, sz in anim_meta['legs']:
        side_offset = 0.0 if sz < 0 else math.pi
        leg_phase = idx * 0.72 + side_offset

        def leg_rot(_t, u_norm, ph=leg_phase, side=sz):
            phi = 14.0 * 2.0 * math.pi * u_norm - ph
            d_yaw = side * 19.5 * math.sin(phi)
            lift = max(0.0, math.cos(phi))
            d_rx = -side * (20.0 * lift - 3.5)
            d_rz = 4.5 * math.sin(phi)
            return (-d_rx, -d_yaw, d_rz)

        add_anim(leg_name, _make_rot_series(leg_name, SUB_ANIM_STEPS, leg_rot, close_exact=True))

    # 4. Snapping / Clacking Venomous Forcipules (fang_l, fang_r)
    for fang_name, sz in anim_meta['fangs']:
        def fang_rot(_t, u_norm, side=sz):
            env = _fang_strike_envelope(u_norm)
            quiver = 2.2 * math.sin(18.0 * 2.0 * math.pi * u_norm)
            # Inward snap: for left fang (sz=-1, at -Z), inward (+Z) around Y is negative Ry delta;
            # for right fang (sz=+1, at +Z), inward (-Z) around Y is positive Ry delta.
            d_ry = side * (22.0 * env + quiver)
            d_rz = -3.5 * env
            return (0.0, -d_ry, d_rz)

        add_anim(fang_name, _make_rot_series(fang_name, SUB_ANIM_STEPS, fang_rot, close_exact=True))

    # 5. Multi-Jointed Whip Antennae Probing Ahead
    for a1_name, a2_name, sz in anim_meta['antennae']:
        asym = 0.0 if sz < 0 else 1.35

        def ant_base(_t, u_norm, side=sz, off=asym):
            w = 2.0 * math.pi * u_norm
            d_ry = side * (12.5 * math.sin(7.0 * w + off) + 5.0 * math.cos(11.0 * w + off))
            d_rz = 8.5 * math.sin(6.0 * w + off) + 3.5 * math.sin(13.0 * w - off)
            return (0.0, -d_ry, d_rz)

        def ant_tip(_t, u_norm, side=sz, off=asym):
            w = 2.0 * math.pi * u_norm
            d_ry = side * (17.5 * math.sin(7.0 * w + off - 0.9) + 7.5 * math.cos(13.0 * w - off))
            d_rz = 12.0 * math.sin(6.0 * w + off - 0.8) + 5.5 * math.sin(15.0 * w + off)
            return (0.0, -d_ry, d_rz)

        add_anim(a1_name, _make_rot_series(a1_name, SUB_ANIM_STEPS, ant_base, close_exact=True))
        add_anim(a2_name, _make_rot_series(a2_name, SUB_ANIM_STEPS, ant_tip, close_exact=True))

    # 6. Forked Tail Cerci Scissoring & Warning Flick
    for c_name, sz in anim_meta['cerci']:
        def cercus_rot(_t, u_norm, side=sz):
            w = 2.0 * math.pi * u_norm
            d_ry = side * (11.5 * math.sin(6.0 * w) - 4.5 * math.cos(12.0 * w))
            d_rz = 6.5 * math.sin(6.0 * w + 0.6)
            return (0.0, -d_ry, d_rz)

        add_anim(c_name, _make_rot_series(c_name, SUB_ANIM_STEPS, cercus_rot, close_exact=True))

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
    track = FullBodyTrack()
    root, elements, anim_meta = build_rig()
    anim = build_animation(anim_meta, track)
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
# Faithful ModelEngine 4.1.0 Transform Preview Renderer (Exact Sign Laws!)
# ---------------------------------------------------------------------------
def _eval_anim_at(model: dict, anim_time: float):
    rot_key = {}
    pos_key = {}
    if not model.get('animations'):
        return rot_key, pos_key
    anim = model['animations'][0]
    t = anim_time % anim['length']
    for animator in anim['animators'].values():
        bname = animator['name']
        for ch, store in (('rotation', rot_key), ('position', pos_key)):
            kfs = [k for k in animator['keyframes'] if k['channel'] == ch]
            if not kfs:
                continue
            lo, hi = kfs[0], kfs[-1]
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
    return rot_key, pos_key


def _bilerp3(p00, p10, p11, p01, u, v):
    return tuple(
        (1 - u) * (1 - v) * p00[i] + u * (1 - v) * p10[i] + u * v * p11[i] + (1 - u) * v * p01[i]
        for i in range(3)
    )


def render_view(model: dict, texture: Image.Image, size=(560, 560), yaw=25.0, pitch=14.0,
                scale=15.0, centre=(0.0, 17.5, 0.0), anim_time=0.0, draw_player=True,
                title='') -> Image.Image:
    img = Image.new('RGB', size, (18, 20, 30))
    draw = ImageDraw.Draw(img)
    tex_px = texture.load()
    tw, th = texture.size

    rot_k, pos_k = _eval_anim_at(model, anim_time)
    chains = {}

    def walk(nodes, chain, is_root=True):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            bname = node['name']
            rk = rot_k.get(bname, [0.0, 0.0, 0.0])
            pk = [0.0, 0.0, 0.0] if is_root else pos_k.get(bname, [0.0, 0.0, 0.0])
            # Exact BlockbenchParser + KeyframeTypes equations:
            eff_euler = [
                node['rotation'][0] - rk[0],
                node['rotation'][1] - rk[1],
                node['rotation'][2] + rk[2],
            ]
            eff_pos = [
                node['origin'][0] - pk[0],
                node['origin'][1] + pk[1],
                node['origin'][2] + pk[2],
            ]
            own = chain + [(tuple(node['origin']), tuple(eff_pos), euler_zyx_to_matrix(eff_euler))]
            for ch in node.get('children', []):
                if isinstance(ch, str):
                    chains[ch] = own
            walk([c for c in node.get('children', []) if isinstance(c, dict)], own, is_root=False)

    walk(model['outliner'], [], is_root=True)

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
            ((-4.0, 0.0, -2.0), (0.0, 12.0, 2.0), (42, 48, 66)),
            ((0.0, 0.0, -2.0), (4.0, 12.0, 2.0), (46, 52, 70)),
            ((-4.0, 12.0, -2.0), (4.0, 24.0, 2.0), (58, 66, 88)),
            ((-8.0, 12.0, -2.0), (-4.0, 24.0, 2.0), (48, 56, 76)),
            ((4.0, 12.0, -2.0), (8.0, 24.0, 2.0), (48, 56, 76)),
            ((-4.0, 24.0, -4.0), (4.0, 32.0, 4.0), (72, 80, 104)),
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
            area = ((p2_full[1][0] - p2[0][0]) * (p2_full[2][1] - p2_full[0][1])
                    - (p2_full[1][1] - p2_full[0][1]) * (p2_full[2][0] - p2_full[0][0])) if False else (
                (p2_full[1][0] - p2_full[0][0]) * (p2_full[2][1] - p2_full[0][1])
                - (p2_full[1][1] - p2_full[0][1]) * (p2_full[2][0] - p2_full[0][0])
            )
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
        render_view(model, texture, yaw=-24.0, pitch=14.0, scale=14.5, centre=(0.0, 16.5, 0.0),
                    anim_time=0.8, title='t=0.8s (Спереди: грудь -> левое плечо -> шея)'),
        render_view(model, texture, yaw=158.0, pitch=16.0, scale=14.5, centre=(0.0, 16.5, 0.0),
                    anim_time=1.8, title='t=1.8s (Со спины: шея -> правое плечо -> грудь)'),
        render_view(model, texture, yaw=-28.0, pitch=12.0, scale=14.5, centre=(0.0, 16.5, 0.0),
                    anim_time=4.4, title='t=4.4s (Живот -> левое бедро и ноги!)'),
        render_view(model, texture, yaw=155.0, pitch=14.0, scale=14.5, centre=(0.0, 16.5, 0.0),
                    anim_time=5.8, title='t=5.8s (Поясница и бёдра со спины)'),
        render_view(model, texture, yaw=-52.0, pitch=14.0, scale=14.5, centre=(0.0, 16.5, 0.0),
                    anim_time=8.2, title='t=8.2s (Ползёт по левой руке на лопатки!)'),
        render_view(model, texture, yaw=48.0, pitch=14.0, scale=14.5, centre=(0.0, 16.5, 0.0),
                    anim_time=9.8, title='t=9.8s (Огибает правую руку обратно на грудь!)'),
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
    tex_dest = args.out_dir / 'assets' / 'modelengine' / 'textures' / 'entity' / 'models'
    tex_dest.mkdir(parents=True, exist_ok=True)
    icon_dir = args.out_dir / 'assets' / 'reallyworld'
    (icon_dir / 'items').mkdir(parents=True, exist_ok=True)
    (icon_dir / 'models' / 'item' / 'freak').mkdir(parents=True, exist_ok=True)
    (icon_dir / 'textures' / 'item' / 'freak').mkdir(parents=True, exist_ok=True)

    bb_path.write_text(json.dumps(blueprint, separators=(',', ':')), encoding='utf-8')
    texture.save(tex_path, format='PNG', optimize=True)
    texture.save(tex_dest / f'{MODEL}.png', format='PNG', optimize=True)

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
    rotated = sum(1 for e in blueprint['elements'] if any(abs(v) > 1e-9 for v in e['rotation']))
    print(f'Built {bb_path.name}: {len(blueprint["elements"])} cubes (rotated={rotated}), '
          f'{len(blueprint["animations"][0]["animators"])} animated bones, '
          f'texture {texture.width}x{texture.height}')


if __name__ == '__main__':
    main()
