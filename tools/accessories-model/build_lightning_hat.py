#!/usr/bin/env python3
"""Procedural 3D Blockbench 4.10 generator for `elytrix_lightning_hat` (Грозовая молния — v2 Glass & Calm Stormcloud).

Refinements per user visual feedback:
  1. Lightning bolt, branching forks, shockwave ring & strike sparks are built out of
     **translucent Minecraft glass** (`alpha = 105..200` pale ice-blue & frosted white glass
     with subtle vanilla glass diagonal specular glints, zero harsh borders, zero double-box stickers).
  2. Positioned **lower** right above the player's crown (`Y = 32.65 .. 43.8`, ~3.5 BB units lower
     than v1; player head top = `32.0`, strictly `< 1.85m` from camera eye for 100% 1st-person hide).
  3. **Cloud bottom is completely unpainted** — no underside veins/stripes and no protruding
     colored bottom nodes; calm uniform slate-grey cloud across the bottom and sides.
  4. **Calmer, softer textures** inspired by natural atmospheric stormclouds & pale ice glass
     (soft muted cool slate-blue/grey cumulus cloud + serene white/ice-blue translucent glass,
     zero neon pink/purple/yellow noise).
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
MODEL = 'elytrix_lightning_hat'
ICON = 'lightning_hat_icon'
NS = uuid.UUID('7e41c8b2-94d3-4f16-a8c5-3b27e91f6042')

IDLE_LEN = 3.2
IDLE_STEPS = 64  # 20 TPS

STRIKE_LEN = 1.3
STRIKE_STEPS = 26  # 20 TPS


def uid(tag: str) -> str:
    return str(uuid.uuid5(NS, tag))


def _pt(x: float, y: float, z: float) -> list[float]:
    return [round(float(x), 4), round(float(y), 4), round(float(z), 4)]


# UV rectangles in 0..16 space (8 px per unit on 128x128 RGBA texture)
UV_GLASS_CORE = [0.25, 0.25, 3.75, 3.75]      # Translucent frosted white glass (main bolt core)
UV_GLASS_ICE = [4.25, 0.25, 7.75, 3.75]       # Translucent pale ice-blue stained glass (bolt & branches)
UV_GLASS_MIST = [8.25, 0.25, 11.75, 3.75]     # Soft misty sky-glass (delicate tips & shockwave ring)
UV_GLASS_GLINT = [12.25, 0.25, 15.75, 3.75]   # Brighter frosted crystal glass (strike tip & sparks)
UV_CLOUD_BASE = [0.5, 4.5, 7.5, 7.5]          # Calm muted slate-blue/grey cloud (sides & UNPAINTED bottom!)
UV_CLOUD_CROWN = [8.5, 4.5, 15.5, 7.5]        # Softly sunlit upper cumulus dome (calm cool grey-blue)
UV_RING_GLASS = [0.5, 8.5, 7.5, 11.5]         # Calm translucent ice-white glass shockwave band
UV_RING_SOFT = [8.5, 8.5, 15.5, 11.5]         # Softer translucent pale-blue glass outer ring


def _faces(default_uv, **overrides) -> dict:
    out = {}
    for side in ('north', 'east', 'south', 'west', 'up', 'down'):
        uv = overrides.get(side, default_uv)
        out[side] = {'uv': list(uv), 'texture': 0}
    return out


def _cube(name: str, p_from: list[float], p_to: list[float], origin: list[float], faces: dict, shade: bool = False, light: int = 15) -> dict:
    return {
        'name': name,
        'type': 'cube',
        'from': p_from,
        'to': p_to,
        'origin': origin,
        'rotation': [0.0, 0.0, 0.0],
        'autouv': 0,
        'box_uv': False,
        'rescale': False,
        'locked': False,
        'visibility': True,
        'shade': shade,
        'light_emission': light,
        'color': 0,
        'faces': faces,
        'uuid': uid(f'cube:{name}'),
    }


def _paint_glass_patch(px, x0: int, y0: int, w: int, h: int,
                       base_rgba: tuple[int, int, int, int],
                       glint_rgba: tuple[int, int, int, int],
                       rim_rgba: tuple[int, int, int, int]):
    """Paints a calm, authentic Minecraft stained-glass texture patch (translucent body + subtle diagonal glint, NO dark border)."""
    for ly in range(h):
        for lx in range(w):
            bx, by = lx // 2, ly // 2
            edge = min(bx, by, (w // 2 - 1) - bx, (h // 2 - 1) - by)
            # Classic subtle vanilla glass diagonal specular streaks
            glint_main = (bx + by) in (5, 6, 17, 18) and 2 <= bx <= (w // 2 - 3) and 2 <= by <= (h // 2 - 3)
            glint_sub = (bx + by) == 11 and 4 <= bx <= 9
            if glint_main or glint_sub:
                col = glint_rgba
            elif edge == 0:
                col = rim_rgba
            else:
                col = base_rgba
            px[x0 + lx, y0 + ly] = col


def build_lightning_texture() -> Image.Image:
    """Builds a calm, atmospheric 128x128 RGBA atlas:
       - Translucent white & pale ice-blue glass for the lightning bolt (alpha 105..200)
       - Calm, soft slate-grey/blue cumulus cloud with ZERO bottom markings or loud colors.
    """
    img = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
    px = img.load()

    # 1. [0..32, 0..32] Translucent Frosted White Glass (main lightning shaft)
    _paint_glass_patch(
        px, 0, 0, 32, 32,
        base_rgba=(234, 245, 255, 172),
        glint_rgba=(255, 255, 255, 218),
        rim_rgba=(214, 234, 250, 184),
    )

    # 2. [32..64, 0..32] Translucent Pale Ice-Blue Glass (mid bolt & branches)
    _paint_glass_patch(
        px, 32, 0, 32, 32,
        base_rgba=(188, 220, 246, 148),
        glint_rgba=(238, 249, 255, 198),
        rim_rgba=(168, 206, 238, 162),
    )

    # 3. [64..96, 0..32] Soft Misty Sky Glass (fine outer fork tips)
    _paint_glass_patch(
        px, 64, 0, 32, 32,
        base_rgba=(172, 206, 236, 122),
        glint_rgba=(224, 242, 255, 170),
        rim_rgba=(158, 194, 228, 136),
    )

    # 4. [96..128, 0..32] Bright Crystal White Glass (spear tip & strike sparks)
    _paint_glass_patch(
        px, 96, 0, 32, 32,
        base_rgba=(244, 250, 255, 192),
        glint_rgba=(255, 255, 255, 232),
        rim_rgba=(222, 239, 252, 198),
    )

    # 5. [0..64, 32..64] Calm Storm-Slate Cloud Base (used on sides AND bottom — completely clean & calm!)
    # Soft cool slate-grey palette (#566478 .. #63738A): gentle 4x4 texel variation of only ~8 RGB units!
    cloud_base_tones = [
        (86, 100, 120, 255),
        (91, 106, 127, 255),
        (96, 111, 133, 255),
        (89, 103, 124, 255),
    ]
    for y in range(32, 64):
        for x in range(0, 64):
            bx, by = x // 8, (y - 32) // 8
            idx = int(1.5 + 1.4 * math.sin(bx * 0.9 + by * 0.7)) % len(cloud_base_tones)
            px[x, y] = cloud_base_tones[idx]

    # 6. [64..128, 32..64] Soft Upper Cumulus Crown (slightly airier cool grey-blue #687992 .. #788AA4)
    cloud_crown_tones = [
        (104, 121, 146, 255),
        (111, 129, 155, 255),
        (118, 137, 163, 255),
        (108, 125, 150, 255),
    ]
    for y in range(32, 64):
        for x in range(64, 128):
            bx, by = (x - 64) // 8, (y - 32) // 8
            idx = int(1.5 + 1.4 * math.cos(bx * 0.8 - by * 0.7)) % len(cloud_crown_tones)
            px[x, y] = cloud_crown_tones[idx]

    # 7. [0..64, 64..96] Translucent Glass Shockwave Ring (inner frosted glass band)
    for y in range(64, 96):
        for x in range(0, 64):
            ly = y - 64
            band = abs(ly - 15)
            glint = ((x // 4 + ly // 4) % 7 == 0)
            if glint:
                col = (250, 254, 255, 190)
            elif band <= 5:
                col = (228, 243, 255, 160)
            else:
                col = (192, 222, 246, 126)
            px[x, y] = col

    # 8. [64..128, 64..96] Translucent Glass Shockwave Ring (outer soft mist-glass band)
    for y in range(64, 96):
        for x in range(64, 128):
            ly = y - 64
            band = abs(ly - 15)
            if band <= 5:
                col = (204, 230, 250, 136)
            else:
                col = (176, 208, 238, 104)
            px[x, y] = col

    return img


def build_lightning_icon() -> Image.Image:
    """Builds a calm, crisp 32x32 pixel-art menu icon matching the slate cumulus cloud + glass lightning."""
    icon = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = icon.load()

    OUTLINE = (38, 46, 62, 255)
    CLOUD_LOW = (84, 98, 118, 255)
    CLOUD_MID = (102, 118, 142, 255)
    CLOUD_TOP = (124, 142, 168, 255)
    GLASS_EDGE = (154, 196, 232, 225)
    GLASS_ICE = (196, 228, 252, 215)
    GLASS_WHITE = (242, 250, 255, 240)
    GLASS_GLINT = (255, 255, 255, 255)
    MIST_RING = (182, 216, 244, 190)

    def put(x: int, y: int, c: tuple[int, int, int, int]):
        if 0 <= x < 32 and 0 <= y < 32:
            px[x, y] = c

    # 1. Fluffy cumulus stormcloud at top (y = 2..10), clean unpainted bottom!
    cloud_spans = {
        2: (13, 19),
        3: (10, 21),
        4: (8, 23),
        5: (6, 25),
        6: (5, 26),
        7: (5, 26),
        8: (6, 25),
    }
    for y, (x0, x1) in cloud_spans.items():
        for x in range(x0 - 1, x1 + 2):
            if x == x0 - 1 or x == x1 + 1 or y == 2:
                put(x, y, OUTLINE)
            elif y <= 4:
                put(x, y, CLOUD_TOP)
            elif y <= 6:
                put(x, y, CLOUD_MID)
            else:
                put(x, y, CLOUD_LOW)
    for x in range(6, 26):
        put(x, 9, OUTLINE)

    # 2. Calm translucent glass shockwave ring at bottom (y = 24..29)
    ring_pts = [
        (8, 26), (9, 25), (10, 25), (11, 24),
        (20, 24), (21, 25), (22, 25), (23, 26),
        (7, 27), (24, 27),
        (8, 28), (9, 28), (10, 29), (11, 29), (12, 29), (13, 29),
        (14, 29), (15, 29), (16, 29), (17, 29), (18, 29), (19, 29),
        (20, 29), (21, 29), (22, 28), (23, 28),
    ]
    for rx, ry in ring_pts:
        put(rx, ry, MIST_RING)
    for rx in range(13, 19):
        put(rx, 28, GLASS_WHITE)

    # 3. Crystalline glass lightning bolt (y = 8..27)
    bolt_rows = {
        8:  (15, 19),
        9:  (14, 18),
        10: (13, 17),
        11: (12, 16),
        12: (11, 15),
        13: (10, 15),
        14: (9,  20),
        15: (10, 21),
        16: (15, 20),
        17: (14, 19),
        18: (14, 18),
        19: (13, 17),
        20: (13, 17),
        21: (13, 16),
        22: (13, 16),
        23: (14, 16),
        24: (14, 15),
        25: (14, 15),
        26: (14, 15),
        27: (14, 14),
    }
    for y, (x0, x1) in bolt_rows.items():
        for x in range(x0, x1 + 1):
            if x == x0 or x == x1:
                put(x, y, GLASS_EDGE if x == x1 else GLASS_ICE)
            elif (x + y) % 5 == 0:
                put(x, y, GLASS_GLINT)
            else:
                put(x, y, GLASS_WHITE)

    # Delicate fine glass branches (like image-10.png)
    for bx, by in ((9, 16), (8, 17), (7, 18), (20, 17), (21, 18), (22, 19)):
        put(bx, by, GLASS_ICE)

    return icon


def eval_lightning_pose(u: float, mode: str = 'idle') -> dict:
    """Evaluates all bone positions, rotations, and scales at normalized time u in [0, 1]."""
    tau = 2.0 * math.pi

    if mode == 'idle':
        hover_y = 0.24 * math.sin(tau * u)
        cloud_sway_x = 0.20 * math.sin(tau * u)
        cloud_rot = [
            1.2 * math.sin(tau * 2.0 * u),
            5.0 * math.sin(tau * u),
            1.6 * math.cos(tau * 2.0 * u),
        ]
        cloud_sc = [1.0, 1.0, 1.0]

        jitter_z = 1.6 * math.sin(tau * 6.0 * u) + 0.9 * math.cos(tau * 10.0 * u)
        jitter_y = 4.0 * math.sin(tau * 2.0 * u)

        bolt_dy = 0.0
        bolt_sc = [0.94 + 0.04 * math.sin(tau * 6.0 * u), 0.96, 0.94 + 0.04 * math.sin(tau * 6.0 * u)]
        bolt_rot = [0.0, jitter_y, jitter_z]

        fork_sc = 0.84 + 0.10 * math.sin(tau * 5.0 * u)
        fork_spread = 3.0 * math.sin(tau * 4.0 * u)

        ring_sc_xz = 0.48 + 0.05 * math.sin(tau * 3.0 * u)
        ring_sc_y = 0.70
        ring_ry = 14.0 * math.sin(tau * 2.0 * u)

        sparks_sc = 0.0
        sparks_dy = 0.0
        arc_flare = 0.82 + 0.10 * math.sin(tau * 6.0 * u)

        # Storm Charge-Up window: [0.38, 0.485] — bolt retracts smoothly into cumulus cloud
        if 0.38 <= u < 0.485:
            p = (u - 0.38) / (0.485 - 0.38)
            ease = p * p * (3.0 - 2.0 * p)
            cloud_sc = [1.0 + 0.11 * ease, 1.0 + 0.08 * ease, 1.0 + 0.11 * ease]
            cloud_rot[2] += 3.2 * math.sin(p * math.pi * 4.0)
            bolt_dy = 2.5 * ease
            bolt_sc = [0.94 - 0.70 * ease, 0.96 - 0.80 * ease, 0.94 - 0.70 * ease]
            fork_sc = 0.84 * (1.0 - 0.82 * ease)
            ring_sc_xz = 0.48 - 0.30 * ease
            arc_flare = 0.82 * (1.0 - 0.78 * ease)

        # STRIKE SLAM #1: [0.485, 0.540]
        elif 0.485 <= u < 0.540:
            p = (u - 0.485) / (0.540 - 0.485)
            slam = min(1.0, p * 2.5)
            cloud_sc = [1.12 - 0.05 * p, 0.94 + 0.06 * p, 1.12 - 0.05 * p]
            bolt_dy = 2.5 * (1.0 - slam) - 0.45 * slam
            bolt_sc = [0.24 + 0.84 * slam, 0.16 + 0.98 * slam, 0.24 + 0.84 * slam]
            bolt_rot = [1.0, -5.0, 3.0]
            fork_sc = 1.12 * slam
            fork_spread = 14.0 * slam
            ring_sc_xz = 0.18 + 1.00 * p
            ring_sc_y = 1.20 - 0.20 * p
            sparks_sc = 1.05 * slam
            sparks_dy = 0.35 * p
            arc_flare = 1.12 * slam

        # Inter-stroke flicker dip: [0.540, 0.570]
        elif 0.540 <= u < 0.570:
            p = (u - 0.540) / (0.570 - 0.540)
            cloud_sc = [1.06, 1.01, 1.06]
            bolt_dy = -0.15
            bolt_sc = [0.48, 0.58, 0.48]
            bolt_rot = [-1.0, 4.0, -2.5]
            fork_sc = 0.46
            fork_spread = 5.0
            ring_sc_xz = 1.18 + 0.10 * p
            ring_sc_y = 0.90
            sparks_sc = 0.50
            sparks_dy = 0.45
            arc_flare = 0.55

        # STRIKE #2 RETURN-STROKE DOUBLE FLASH: [0.570, 0.640]
        elif 0.570 <= u < 0.640:
            p = (u - 0.570) / (0.640 - 0.570)
            flash = math.sin(min(1.0, p * 1.35) * math.pi * 0.5)
            cloud_sc = [1.09 - 0.04 * p, 0.96 + 0.04 * p, 1.09 - 0.04 * p]
            bolt_dy = -0.40 * (1.0 - 0.35 * p)
            bolt_sc = [1.06 - 0.08 * p, 1.12 - 0.10 * p, 1.06 - 0.08 * p]
            bolt_rot = [-1.0, 6.0 * (1.0 - 0.5 * p), -3.0]
            fork_sc = 1.08 - 0.14 * p
            fork_spread = 16.0 - 5.0 * p
            ring_sc_xz = 1.28 + 0.16 * p
            ring_sc_y = 1.08 - 0.22 * p
            sparks_sc = (0.98 - 0.28 * p) * flash
            sparks_dy = 0.45 + 0.35 * p
            arc_flare = 1.08 - 0.14 * p

        # Aftershock dissipation back to seamless hover: [0.640, 0.840]
        elif 0.640 <= u < 0.840:
            p = (u - 0.640) / (0.840 - 0.640)
            ease = 1.0 - (p * p * (3.0 - 2.0 * p))
            cloud_sc = [1.0 + 0.05 * ease, 1.0, 1.0 + 0.05 * ease]
            bolt_dy = -0.26 * ease
            bolt_sc = [0.94 + 0.04 * ease, 0.96 + 0.06 * ease, 0.94 + 0.04 * ease]
            fork_sc = 0.84 + 0.10 * ease
            fork_spread = 3.0 + 8.0 * ease
            ring_sc_xz = 0.48 + 0.96 * ease
            ring_sc_y = 0.70 + 0.16 * ease
            sparks_sc = max(0.0, 0.70 * (1.0 - min(1.0, p * 1.6)))
            sparks_dy = 0.80 * min(1.0, p * 1.6)
            arc_flare = 0.82 + 0.12 * ease

    else:
        # Dedicated `strike` override clip (1.3s): rapid charge -> triple return-stroke slam -> settle
        hover_y = 0.0
        cloud_sway_x = 0.0
        cloud_rot = [0.0, 0.0, 0.0]
        ring_ry = 18.0 * math.sin(tau * u)
        if u in (0.0, 1.0):
            cloud_sc = [1.0, 1.0, 1.0]
            bolt_dy = 0.0
            bolt_sc = [0.95, 0.96, 0.95]
            bolt_rot = [0.0, 0.0, 0.0]
            fork_sc = 0.84
            fork_spread = 0.0
            ring_sc_xz = 0.48
            ring_sc_y = 0.70
            sparks_sc = 0.0
            sparks_dy = 0.0
            arc_flare = 0.82
        elif u < 0.16:
            p = u / 0.16
            cloud_sc = [1.0 + 0.12 * p, 1.0 + 0.09 * p, 1.0 + 0.12 * p]
            cloud_rot = [0.0, 0.0, 3.5 * math.sin(p * math.pi * 2.0)]
            bolt_dy = 2.6 * p
            bolt_sc = [0.95 - 0.72 * p, 0.96 - 0.80 * p, 0.95 - 0.72 * p]
            bolt_rot = [0.0, 0.0, 0.0]
            fork_sc = 0.18
            fork_spread = -3.0
            ring_sc_xz = 0.20
            ring_sc_y = 0.50
            sparks_sc = 0.0
            sparks_dy = 0.0
            arc_flare = 0.22
        elif u < 0.62:
            p = (u - 0.16) / (0.62 - 0.16)
            stroke = abs(math.cos(p * math.pi * 2.5))
            cloud_sc = [1.12 - 0.06 * p, 0.94 + 0.06 * p, 1.12 - 0.06 * p]
            cloud_rot = [1.5 * math.sin(p * math.pi * 6.0), 0.0, -2.5 * math.cos(p * math.pi * 6.0)]
            bolt_dy = -0.45 + 0.20 * (1.0 - stroke)
            bolt_sc = [0.68 + 0.40 * stroke, 0.74 + 0.42 * stroke, 0.68 + 0.40 * stroke]
            bolt_rot = [1.2 * math.sin(p * math.pi * 5.0), 7.0 * math.sin(p * math.pi * 3.0), 3.5 * math.cos(p * math.pi * 5.0)]
            fork_sc = 0.58 + 0.56 * stroke
            fork_spread = 6.0 + 11.0 * stroke
            ring_sc_xz = 0.28 + 1.18 * p
            ring_sc_y = 0.80 + 0.38 * stroke
            sparks_sc = 0.40 + 0.65 * stroke
            sparks_dy = 0.75 * p
            arc_flare = 0.65 + 0.48 * stroke
        else:
            p = (u - 0.62) / (1.0 - 0.62)
            ease = 1.0 - (p * p * (3.0 - 2.0 * p))
            cloud_sc = [1.0 + 0.05 * ease, 1.0, 1.0 + 0.05 * ease]
            bolt_dy = -0.32 * ease
            bolt_sc = [0.95 + 0.08 * ease, 0.96 + 0.12 * ease, 0.95 + 0.08 * ease]
            bolt_rot = [0.0, 2.5 * ease, -1.2 * ease]
            fork_sc = 0.84 + 0.16 * ease
            fork_spread = 8.0 * ease
            ring_sc_xz = 0.48 + 0.98 * ease
            ring_sc_y = 0.70 + 0.16 * ease
            sparks_sc = max(0.0, 0.72 * (1.0 - min(1.0, p * 1.7)))
            sparks_dy = 0.75 + 0.25 * p
            arc_flare = 0.82 + 0.16 * ease

    # 4 connected diagonal glass lightning tendrils (`arc_nw`, `arc_ne`, `arc_sw`, `arc_se`)
    arcs = {}
    for idx, aname in enumerate(('arc_nw', 'arc_ne', 'arc_sw', 'arc_se')):
        ph = tau * (2.0 * u + 0.25 * idx)
        sign_x = -1.0 if 'w' in aname else 1.0
        sign_z = -1.0 if 'n' in aname else 1.0
        sc_i = max(0.0, round(arc_flare * (0.90 + 0.12 * math.sin(ph)), 3))
        arcs[aname] = {
            'pos': [0.0, round(0.12 * math.sin(ph), 3), 0.0],
            'rot': [round(sign_z * 6.0 * math.sin(ph), 3), round(8.0 * math.cos(ph), 3), round(sign_x * (6.0 + 10.0 * max(0.0, arc_flare - 0.80)), 3)],
            'scale': [sc_i, sc_i, sc_i],
        }

    return {
        'hat_root_pos': [0.0, round(hover_y, 3), 0.0],
        'cloud_pos': [round(cloud_sway_x, 3), 0.0, 0.0],
        'cloud_rot': [round(v, 3) for v in cloud_rot],
        'cloud_scale': [round(v, 3) for v in cloud_sc],
        'bolt_pos': [0.0, round(bolt_dy, 3), 0.0],
        'bolt_rot': [round(v, 3) for v in bolt_rot],
        'bolt_scale': [round(v, 3) for v in bolt_sc],
        'fork_l_rot': [0.0, 0.0, round(-fork_spread, 3)],
        'fork_l_scale': [round(fork_sc, 3)] * 3,
        'fork_r_rot': [0.0, 0.0, round(fork_spread, 3)],
        'fork_r_scale': [round(fork_sc, 3)] * 3,
        'ring_rot': [0.0, round(ring_ry, 3), 0.0],
        'ring_scale': [round(ring_sc_xz, 3), round(ring_sc_y, 3), round(ring_sc_xz, 3)],
        'sparks_pos': [0.0, round(sparks_dy, 3), 0.0],
        'sparks_scale': [round(sparks_sc, 3)] * 3,
        'arcs': arcs,
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


def _build_clip_animators(clip_name: str, length: float, steps: int, mode: str) -> dict:
    bones = [
        'hat_root', 'storm_cloud', 'bolt_main', 'fork_left', 'fork_right',
        'impact_ring', 'impact_sparks', 'arc_nw', 'arc_ne', 'arc_sw', 'arc_se',
    ]
    kfs_by_bone = {b: [] for b in bones}

    for s in range(steps + 1):
        u = s / steps
        u_eval = 0.0 if (mode == 'idle' and s == steps) else u
        t = length * u
        pose = eval_lightning_pose(u_eval, mode=mode)

        kfs_by_bone['hat_root'].append(_vec_kf('position', f'{clip_name}:hat_root', t, *pose['hat_root_pos']))

        kfs_by_bone['storm_cloud'].append(_vec_kf('position', f'{clip_name}:storm_cloud', t, *pose['cloud_pos']))
        kfs_by_bone['storm_cloud'].append(_vec_kf('rotation', f'{clip_name}:storm_cloud', t, *pose['cloud_rot']))
        kfs_by_bone['storm_cloud'].append(_vec_kf('scale', f'{clip_name}:storm_cloud', t, *pose['cloud_scale']))

        kfs_by_bone['bolt_main'].append(_vec_kf('position', f'{clip_name}:bolt_main', t, *pose['bolt_pos']))
        kfs_by_bone['bolt_main'].append(_vec_kf('rotation', f'{clip_name}:bolt_main', t, *pose['bolt_rot']))
        kfs_by_bone['bolt_main'].append(_vec_kf('scale', f'{clip_name}:bolt_main', t, *pose['bolt_scale']))

        kfs_by_bone['fork_left'].append(_vec_kf('rotation', f'{clip_name}:fork_left', t, *pose['fork_l_rot']))
        kfs_by_bone['fork_left'].append(_vec_kf('scale', f'{clip_name}:fork_left', t, *pose['fork_l_scale']))

        kfs_by_bone['fork_right'].append(_vec_kf('rotation', f'{clip_name}:fork_right', t, *pose['fork_r_rot']))
        kfs_by_bone['fork_right'].append(_vec_kf('scale', f'{clip_name}:fork_right', t, *pose['fork_r_scale']))

        kfs_by_bone['impact_ring'].append(_vec_kf('rotation', f'{clip_name}:impact_ring', t, *pose['ring_rot']))
        kfs_by_bone['impact_ring'].append(_vec_kf('scale', f'{clip_name}:impact_ring', t, *pose['ring_scale']))

        kfs_by_bone['impact_sparks'].append(_vec_kf('position', f'{clip_name}:impact_sparks', t, *pose['sparks_pos']))
        kfs_by_bone['impact_sparks'].append(_vec_kf('scale', f'{clip_name}:impact_sparks', t, *pose['sparks_scale']))

        for aname, adata in pose['arcs'].items():
            kfs_by_bone[aname].append(_vec_kf('position', f'{clip_name}:{aname}', t, *adata['pos']))
            kfs_by_bone[aname].append(_vec_kf('rotation', f'{clip_name}:{aname}', t, *adata['rot']))
            kfs_by_bone[aname].append(_vec_kf('scale', f'{clip_name}:{aname}', t, *adata['scale']))

    return {
        uid(f'bone:{b}'): {
            'name': b,
            'type': 'bone',
            'keyframes': kfs_by_bone[b],
        }
        for b in bones
    }


def build_animations() -> list[dict]:
    return [
        {
            'uuid': uid('animation:idle'),
            'name': 'idle',
            'loop': 'loop',
            'override': False,
            'length': IDLE_LEN,
            'snapping': 20,
            'selected': True,
            'anim_time_update': '',
            'blend_weight': '',
            'start_delay': '',
            'loop_delay': '',
            'animators': _build_clip_animators('idle', IDLE_LEN, IDLE_STEPS, 'idle'),
        },
        {
            'uuid': uid('animation:strike'),
            'name': 'strike',
            'loop': 'once',
            'override': True,
            'length': STRIKE_LEN,
            'snapping': 20,
            'selected': False,
            'anim_time_update': '',
            'blend_weight': '',
            'start_delay': '',
            'loop_delay': '',
            'animators': _build_clip_animators('strike', STRIKE_LEN, STRIKE_STEPS, 'strike'),
        },
    ]


# Shared bone origins (lowered ~4.7 BB units vs v1 so the hat hugs right above the player's head Y=32.0!)
ROOT_ORIG = [0.0, 32.4, 0.0]
CLOUD_ORIG = [0.0, 39.8, 0.0]
BOLT_ORIG = [0.0, 35.8, 0.0]
FORK_L_ORIG = [-0.95, 36.4, 0.0]
FORK_R_ORIG = [0.95, 36.0, 0.0]
RING_ORIG = [0.0, 32.45, 0.0]
SPARKS_ORIG = [0.0, 32.55, 0.0]
ARC_ORIGINS = {
    'arc_nw': [-0.55, 37.2, -0.22],
    'arc_ne': [0.55,  37.0, -0.22],
    'arc_sw': [-0.55, 36.2,  0.22],
    'arc_se': [0.55,  36.0,  0.22],
}


def build_blueprint() -> tuple[dict, Image.Image]:
    texture = build_lightning_texture()
    raw = io.BytesIO()
    texture.save(raw, format='PNG', optimize=True)

    elements: list[dict] = []

    def add(c: dict) -> str:
        elements.append(c)
        return c['uuid']

    # 1. Organic Asymmetric Fluffy Cumulus Cloud (`storm_cloud`: Y = 38.6 .. 42.5, cozy & low above head!)
    #    IMPORTANT: `down` uses `UV_CLOUD_BASE` (exact same calm slate-grey as sides — ZERO bottom coloring/veins/nodes!).
    cloud_base_faces = _faces(UV_CLOUD_BASE, up=UV_CLOUD_CROWN, down=UV_CLOUD_BASE)
    cloud_crown_faces = _faces(UV_CLOUD_CROWN, down=UV_CLOUD_BASE)
    cloud_uuids = [
        # Flush, clean flat-bottomed cumulus base (Y = 38.6 .. 40.5, completely unpainted underside!)
        add(_cube('cloud_main',    _pt(-3.4, 38.6, -2.5), _pt(3.4,  40.5, 2.5),  CLOUD_ORIG, cloud_base_faces)),
        add(_cube('cloud_left',    _pt(-4.6, 38.7, -1.8), _pt(-3.4, 40.2, 1.9),  CLOUD_ORIG, cloud_base_faces)),
        add(_cube('cloud_right',   _pt(3.4,  38.7, -1.9), _pt(4.5,  40.3, 1.8),  CLOUD_ORIG, cloud_base_faces)),
        add(_cube('cloud_front',   _pt(-2.6, 38.7, -3.3), _pt(2.4,  40.1, -2.5), CLOUD_ORIG, cloud_base_faces)),
        add(_cube('cloud_back',    _pt(-2.4, 38.7,  2.5), _pt(2.7,  40.2, 3.3),  CLOUD_ORIG, cloud_base_faces)),
        # Organic asymmetric upper cumulus billows (like image-10.png — NOT a symmetric stepped pyramid!)
        add(_cube('cloud_dome_r',  _pt(-0.8, 40.5, -1.9), _pt(2.6,  42.0, 1.9),  CLOUD_ORIG, cloud_crown_faces)),
        add(_cube('cloud_top_r',   _pt(-0.2, 42.0, -1.3), _pt(2.0,  42.6, 1.3),  CLOUD_ORIG, cloud_crown_faces)),
        add(_cube('cloud_dome_l',  _pt(-3.3, 40.5, -1.6), _pt(-0.8, 41.5, 1.5),  CLOUD_ORIG, cloud_crown_faces)),
        add(_cube('cloud_puff_f',  _pt(-1.9, 40.5, -2.5), _pt(1.2,  41.3, -1.9), CLOUD_ORIG, cloud_crown_faces)),
    ]

    # 2. Single-layer Translucent Glass Lightning Bolt (`bolt_main`: Y = 32.4 .. 38.7)
    #    Non-overlapping Y spans (`y0..y1` abut flush with 0 internal overlap!) so translucent glass
    #    renders crystal-clean like genuine Minecraft stained glass!
    bolt_uuids: list[str] = []
    bolt_segments = [
        # (tag, cx, y0, y1, half_w, half_z, glass_uv)
        # Upper glass shaft emerging from cloud base (Y = 38.7 -> 35.9)
        ('u1', -0.75, 38.0, 38.7, 0.46, 0.36, UV_GLASS_CORE),
        ('u2', -0.20, 37.3, 38.0, 0.44, 0.35, UV_GLASS_CORE),
        ('u3',  0.35, 36.6, 37.3, 0.42, 0.34, UV_GLASS_ICE),
        ('u4',  0.85, 35.9, 36.6, 0.40, 0.33, UV_GLASS_CORE),
        # Crisp horizontal glass zig-zag jog (+0.95 -> -0.95 at Y = 35.35 .. 35.9)
        ('m1', -0.05, 35.35, 35.9, 1.28, 0.34, UV_GLASS_CORE),
        # Lower glass spear plunging onto crown (Y = 35.35 -> 32.4)
        ('l1', -0.85, 34.75, 35.35, 0.40, 0.32, UV_GLASS_ICE),
        ('l2', -0.60, 34.15, 34.75, 0.35, 0.29, UV_GLASS_CORE),
        ('l3', -0.36, 33.60, 34.15, 0.30, 0.26, UV_GLASS_CORE),
        ('l4', -0.16, 33.10, 33.60, 0.24, 0.22, UV_GLASS_GLINT),
        ('l5', -0.05, 32.70, 33.10, 0.19, 0.18, UV_GLASS_GLINT),
        ('l6',  0.00, 32.38, 32.70, 0.13, 0.13, UV_GLASS_GLINT),
    ]
    for tag, cx, y0, y1, hw, hz, guv in bolt_segments:
        bolt_uuids.append(add(_cube(
            f'bolt_glass_{tag}',
            _pt(cx - hw, y0, -hz),
            _pt(cx + hw, y1, hz),
            BOLT_ORIG,
            _faces(guv),
        )))

    # 3. Connected Continuous Crystalline Glass Side Branches (`fork_left`, `fork_right`)
    fork_l_uuids = [
        add(_cube('fork_l_1', _pt(-1.60, 35.65, -0.14), _pt(-0.95, 36.15, 0.14), FORK_L_ORIG, _faces(UV_GLASS_ICE))),
        add(_cube('fork_l_2', _pt(-2.10, 35.10, -0.12), _pt(-1.42, 35.65, 0.12), FORK_L_ORIG, _faces(UV_GLASS_ICE))),
        add(_cube('fork_l_3', _pt(-2.52, 34.55, -0.10), _pt(-1.95, 35.10, 0.10), FORK_L_ORIG, _faces(UV_GLASS_MIST))),
        add(_cube('fork_l_4', _pt(-2.85, 34.00, -0.09), _pt(-2.40, 34.55, 0.09), FORK_L_ORIG, _faces(UV_GLASS_MIST))),
    ]
    fork_r_uuids = [
        add(_cube('fork_r_1', _pt(0.95, 35.45, -0.14), _pt(1.60, 35.95, 0.14), FORK_R_ORIG, _faces(UV_GLASS_ICE))),
        add(_cube('fork_r_2', _pt(1.42, 34.90, -0.12), _pt(2.10, 35.45, 0.12), FORK_R_ORIG, _faces(UV_GLASS_ICE))),
        add(_cube('fork_r_3', _pt(1.95, 34.35, -0.10), _pt(2.52, 34.90, 0.10), FORK_R_ORIG, _faces(UV_GLASS_MIST))),
        add(_cube('fork_r_4', _pt(2.40, 33.80, -0.09), _pt(2.85, 34.35, 0.09), FORK_R_ORIG, _faces(UV_GLASS_MIST))),
    ]

    # 4. Four Continuous Thin Glass Sub-Branches (`arc_nw`, `arc_ne`, `arc_sw`, `arc_se`)
    #    Each segment overlaps cleanly at its step corner so every tendril reads as ONE continuous glass filament!
    arc_bones = []
    arc_specs = [
        ('arc_nw', -1.0, -1.0),
        ('arc_ne',  1.0, -1.0),
        ('arc_sw', -1.0,  1.0),
        ('arc_se',  1.0,  1.0),
    ]
    for aname, sx, sz in arc_specs:
        a_orig = ARC_ORIGINS[aname]
        ox, oy, oz = a_orig
        c1 = add(_cube(
            f'{aname}_1',
            _pt(min(ox, ox + sx * 0.42) - 0.09, oy - 0.65, min(oz, oz + sz * 0.30) - 0.09),
            _pt(max(ox, ox + sx * 0.42) + 0.09, oy,        max(oz, oz + sz * 0.30) + 0.09),
            a_orig, _faces(UV_GLASS_ICE),
        ))
        c2 = add(_cube(
            f'{aname}_2',
            _pt(min(ox + sx * 0.32, ox + sx * 0.80) - 0.08, oy - 1.30, min(oz + sz * 0.22, oz + sz * 0.58) - 0.08),
            _pt(max(ox + sx * 0.32, ox + sx * 0.80) + 0.08, oy - 0.65, max(oz + sz * 0.22, oz + sz * 0.58) + 0.08),
            a_orig, _faces(UV_GLASS_MIST),
        ))
        c3 = add(_cube(
            f'{aname}_3',
            _pt(min(ox + sx * 0.70, ox + sx * 1.12) - 0.07, oy - 1.90, min(oz + sz * 0.50, oz + sz * 0.82) - 0.07),
            _pt(max(ox + sx * 0.70, ox + sx * 1.12) + 0.07, oy - 1.30, max(oz + sz * 0.50, oz + sz * 0.82) + 0.07),
            a_orig, _faces(UV_GLASS_MIST),
        ))
        arc_bones.append({
            'name': aname,
            'origin': a_orig,
            'color': 0,
            'uuid': uid(f'bone:{aname}'),
            'export': True,
            'mirror_uv': False,
            'isOpen': True,
            'locked': False,
            'visibility': True,
            'autouv': 0,
            'children': [c1, c2, c3],
        })

    # 5. Calm Translucent Glass Shockwave Ring (`impact_ring`, Y = 32.35 .. 32.62, right above crown!)
    ring_in = _faces(UV_RING_GLASS)
    ring_out = _faces(UV_RING_SOFT)
    ring_uuids = [
        add(_cube('ring_n',  _pt(-1.5, 32.36, -2.9), _pt(1.5, 32.62, -2.55), RING_ORIG, ring_in)),
        add(_cube('ring_s',  _pt(-1.5, 32.36,  2.55), _pt(1.5, 32.62, 2.9),  RING_ORIG, ring_in)),
        add(_cube('ring_w',  _pt(-2.9, 32.36, -1.5), _pt(-2.55, 32.62, 1.5), RING_ORIG, ring_in)),
        add(_cube('ring_e',  _pt(2.55, 32.36, -1.5), _pt(2.9, 32.62,  1.5),  RING_ORIG, ring_in)),
        add(_cube('ring_nw', _pt(-2.55, 32.34, -2.55), _pt(-1.5, 32.58, -1.5), RING_ORIG, ring_out)),
        add(_cube('ring_ne', _pt(1.5,   32.34, -2.55), _pt(2.55, 32.58, -1.5), RING_ORIG, ring_out)),
        add(_cube('ring_sw', _pt(-2.55, 32.34,  1.5),  _pt(-1.5, 32.58,  2.55), RING_ORIG, ring_out)),
        add(_cube('ring_se', _pt(1.5,   32.34,  1.5),  _pt(2.55, 32.58,  2.55), RING_ORIG, ring_out)),
    ]

    # 6. Delicate Translucent Glass Strike Sparks (`impact_sparks`, burst on strike only)
    sparks_uuids = [
        add(_cube('spark_n1', _pt(-0.12, 32.55, -1.9), _pt(0.12, 33.0, -1.2), SPARKS_ORIG, _faces(UV_GLASS_GLINT))),
        add(_cube('spark_n2', _pt(-0.09, 33.0,  -2.5), _pt(0.09, 33.4, -1.9), SPARKS_ORIG, _faces(UV_GLASS_ICE))),
        add(_cube('spark_s1', _pt(-0.12, 32.55,  1.2), _pt(0.12, 33.0,  1.9), SPARKS_ORIG, _faces(UV_GLASS_GLINT))),
        add(_cube('spark_s2', _pt(-0.09, 33.0,   1.9), _pt(0.09, 33.4,  2.5), SPARKS_ORIG, _faces(UV_GLASS_ICE))),
        add(_cube('spark_w1', _pt(-1.9, 32.55, -0.12), _pt(-1.2, 33.0, 0.12), SPARKS_ORIG, _faces(UV_GLASS_GLINT))),
        add(_cube('spark_w2', _pt(-2.5, 33.0,  -0.09), _pt(-1.9, 33.4, 0.09), SPARKS_ORIG, _faces(UV_GLASS_ICE))),
        add(_cube('spark_e1', _pt(1.2,  32.55, -0.12), _pt(1.9,  33.0, 0.12), SPARKS_ORIG, _faces(UV_GLASS_GLINT))),
        add(_cube('spark_e2', _pt(1.9,  33.0,  -0.09), _pt(2.5,  33.4, 0.09), SPARKS_ORIG, _faces(UV_GLASS_ICE))),
    ]

    def bone(bname: str, orig: list[float], children: list) -> dict:
        return {
            'name': bname,
            'origin': orig,
            'color': 0,
            'uuid': uid(f'bone:{bname}'),
            'export': True,
            'mirror_uv': False,
            'isOpen': True,
            'locked': False,
            'visibility': True,
            'autouv': 0,
            'children': children,
        }

    outliner = [
        bone('hat_root', ROOT_ORIG, [
            bone('storm_cloud', CLOUD_ORIG, cloud_uuids),
            bone('bolt_main', BOLT_ORIG, [
                *bolt_uuids,
                bone('fork_left', FORK_L_ORIG, fork_l_uuids),
                bone('fork_right', FORK_R_ORIG, fork_r_uuids),
            ]),
            bone('impact_ring', RING_ORIG, ring_uuids),
            bone('impact_sparks', SPARKS_ORIG, sparks_uuids),
            *arc_bones,
        ]),
        {
            'name': 'hitbox',
            'origin': [0.0, 16.0, 0.0],
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
            'width': 128,
            'height': 128,
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
            'uuid': uid('texture:0'),
            'relative_path': '',
            'source': 'data:image/png;base64,' + base64.b64encode(raw.getvalue()).decode('ascii'),
        }],
        'animations': build_animations(),
    }
    return blueprint, texture


def render_preview(blueprint: dict, texture: Image.Image, icon: Image.Image, out_path: Path):
    """Renders a 5-panel inspection sheet with TRUE RGBA alpha-compositing so glass translucency
    and the clean unpainted cloud underside are verified visually:
       Panel 1: Calm hover right above head (`u = 0.12`, sandstone-like light backdrop to show glass translucency!)
       Panel 2: Charge-up inside cloud (`u = 0.465`)
       Panel 3: Glass Lightning Strike Slam (`u = 0.505`)
       Panel 4: Bottom-up inspection view (looking up at the cloud underside, matching user's image-9.png!)
       Panel 5: Zoomed 32x32 menu icon + calm glass/cloud texture atlas
    """
    panel_w, panel_h = 236, 300
    # Warm sandstone-grey & twilight split background so semi-transparent glass is clearly visible!
    canvas = Image.new('RGBA', (panel_w * 5, panel_h), (38, 44, 58, 255))

    def rot_mat(rx, ry, rz):
        ax, ay, az = map(math.radians, (rx, ry, rz))
        cx_, sx_ = math.cos(ax), math.sin(ax)
        cy_, sy_ = math.cos(ay), math.sin(ay)
        cz_, sz_ = math.cos(az), math.sin(az)
        mx = np.array([[1, 0, 0], [0, cx_, -sx_], [0, sx_, cx_]])
        my = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]])
        mz = np.array([[cz_, -sz_, 0], [sz_, cz_, 0], [0, 0, 1]])
        return mz @ my @ mx

    tex_arr = np.array(texture)
    by_name = {el['name']: el for el in blueprint['elements']}

    # (u, cam_yaw, cam_pitch, show_head)
    stages = [
        (0.12,  16.0,  -10.0, True),   # 1. Hover right above head
        (0.465, 16.0,  -10.0, True),   # 2. Cloud charge-up
        (0.505, -20.0, -10.0, True),   # 3. Strike slam + branches + glass wave!
        (0.12,  12.0,   46.0, False),  # 4. Looking UP at the bottom of the cloud (verifies unpainted bottom!)
    ]

    for idx, (u, cam_yaw, cam_pitch, show_head) in enumerate(stages):
        panel = Image.new('RGBA', (panel_w, panel_h), (196, 186, 152, 255) if idx in (0, 3) else (32, 38, 52, 255))
        pose = eval_lightning_pose(u, mode='idle')

        ay = math.radians(cam_yaw)
        ap = math.radians(cam_pitch)
        cy_m, sy_m = math.cos(ay), math.sin(ay)
        cp_m, sp_m = math.cos(ap), math.sin(ap)

        scale_px = 14.5 if show_head else 18.5
        center_y_world = 32.5 if show_head else 38.2
        center_y_px = 192.0 if show_head else 155.0

        def proj(pt):
            dx, dy, dz = pt[0], pt[1] - center_y_world, pt[2]
            xw = dx * cy_m - dz * sy_m
            z1 = dx * sy_m + dz * cy_m
            yw = dy * cp_m - z1 * sp_m
            zw = dy * sp_m + z1 * cp_m
            return (118.0 - xw * scale_px, center_y_px - yw * scale_px, zw)

        faces_to_draw = []

        if show_head:
            ref_boxes = [
                ([-8.0, 19.0, -2.0], [8.0, 24.0, 2.0], (56, 64, 82)),
                ([-4.0, 24.0, -4.0], [4.0, 32.0, 4.0], (86, 96, 118)),
            ]
            for low, high, base_rgb in ref_boxes:
                cs = [
                    np.array([low[0], low[1], low[2]]), np.array([high[0], low[1], low[2]]),
                    np.array([high[0], high[1], low[2]]), np.array([low[0], high[1], low[2]]),
                    np.array([low[0], low[1], high[2]]), np.array([high[0], low[1], high[2]]),
                    np.array([high[0], high[1], high[2]]), np.array([low[0], high[1], high[2]]),
                ]
                for idxs, sm in (((2, 1, 0, 3), 1.0), ((7, 4, 5, 6), 0.86), ((6, 5, 1, 2), 0.92), ((3, 0, 4, 7), 0.90), ((7, 6, 2, 3), 1.06)):
                    p2d = [proj(cs[k]) for k in idxs]
                    cross = (p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1]) - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0])
                    if cross <= 0:
                        col = tuple(min(255, int(c * sm)) for c in base_rgb) + (255,)
                        faces_to_draw.append((sum(p[2] for p in p2d) / 4.0 + 2.0, [(s[0], s[1]) for s in p2d], col, (42, 48, 64, 255)))

        def bone_tf(parent_tf, orig, pos, rot, scale):
            o = np.array(orig)
            t = np.array(pos)
            m = rot_mat(*rot)
            sc = np.array(scale)
            return lambda p: parent_tf(o + t + m @ (sc * (p - o)))

        tf_root = bone_tf(lambda p: p, ROOT_ORIG, pose['hat_root_pos'], [0.0, 0.0, 0.0], [1.0, 1.0, 1.0])
        tf_cloud = bone_tf(tf_root, CLOUD_ORIG, pose['cloud_pos'], pose['cloud_rot'], pose['cloud_scale'])
        tf_bolt = bone_tf(tf_root, BOLT_ORIG, pose['bolt_pos'], pose['bolt_rot'], pose['bolt_scale'])
        tf_fl = bone_tf(tf_bolt, FORK_L_ORIG, [0.0, 0.0, 0.0], pose['fork_l_rot'], pose['fork_l_scale'])
        tf_fr = bone_tf(tf_bolt, FORK_R_ORIG, [0.0, 0.0, 0.0], pose['fork_r_rot'], pose['fork_r_scale'])
        tf_ring = bone_tf(tf_root, RING_ORIG, [0.0, 0.0, 0.0], pose['ring_rot'], pose['ring_scale'])
        tf_sparks = bone_tf(tf_root, SPARKS_ORIG, pose['sparks_pos'], [0.0, 0.0, 0.0], pose['sparks_scale'])

        arc_tfs = {
            aname: bone_tf(tf_root, ARC_ORIGINS[aname], pose['arcs'][aname]['pos'], pose['arcs'][aname]['rot'], pose['arcs'][aname]['scale'])
            for aname in ('arc_nw', 'arc_ne', 'arc_sw', 'arc_se')
        }

        def add_cube(cname, tf_fn):
            el = by_name[cname]
            x0, y0, z0 = el['from']
            x1, y1, z1 = el['to']
            cs = [
                np.array([x0, y0, z0]), np.array([x1, y0, z0]), np.array([x1, y1, z0]), np.array([x0, y1, z0]),
                np.array([x0, y0, z1]), np.array([x1, y0, z1]), np.array([x1, y1, z1]), np.array([x0, y1, z1]),
            ]
            wcs = [tf_fn(c) for c in cs]
            if np.linalg.norm(wcs[6] - wcs[0]) < 0.04:
                return
            is_cloud = cname.startswith('cloud_')
            quads = [
                ('north', (2, 1, 0, 3), 0.96 if is_cloud else 1.00),
                ('south', (7, 4, 5, 6), 0.94 if is_cloud else 0.99),
                ('east',  (6, 5, 1, 2), 0.91 if is_cloud else 0.97),
                ('west',  (3, 0, 4, 7), 0.91 if is_cloud else 0.97),
                ('up',    (7, 6, 2, 3), 1.03 if is_cloud else 1.02),
                ('down',  (0, 1, 5, 4), 0.89 if is_cloud else 0.96),
            ]
            for fname, idxs, sm in quads:
                pts3 = [wcs[k] for k in idxs]
                p2d = [proj(p) for p in pts3]
                cross = (p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1]) - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0])
                if cross > 0:
                    continue
                z_avg = sum(p[2] for p in p2d) / 4.0
                uv = el['faces'][fname]['uv']
                tx = min(127, int(0.5 * (uv[0] + uv[2]) * 8))
                ty = min(127, int(0.5 * (uv[1] + uv[3]) * 8))
                rgba = tex_arr[ty, tx]
                if rgba[3] < 16:
                    continue
                alpha = int(rgba[3])
                col = tuple(min(255, int(c * sm)) for c in rgba[:3]) + (alpha,)
                outline = (210, 234, 252, 95) if alpha < 245 else None
                faces_to_draw.append((z_avg, [(s[0], s[1]) for s in p2d], col, outline))

        for name in by_name:
            if name.startswith('cloud_'):
                add_cube(name, tf_cloud)
            elif name.startswith('bolt_'):
                add_cube(name, tf_bolt)
            elif name.startswith('fork_l_'):
                add_cube(name, tf_fl)
            elif name.startswith('fork_r_'):
                add_cube(name, tf_fr)
            elif name.startswith('ring_'):
                add_cube(name, tf_ring)
            elif name.startswith('spark_'):
                add_cube(name, tf_sparks)
            else:
                for aname, atf in arc_tfs.items():
                    if name.startswith(aname):
                        add_cube(name, atf)

        faces_to_draw.sort(key=lambda item: -item[0])
        for _, poly, fill_col, edge_col in faces_to_draw:
            layer = Image.new('RGBA', (panel_w, panel_h), (0, 0, 0, 0))
            ldraw = ImageDraw.Draw(layer)
            ldraw.polygon(poly, fill=fill_col, outline=edge_col)
            panel.alpha_composite(layer)

        canvas.alpha_composite(panel, (idx * panel_w, 0))

    draw = ImageDraw.Draw(canvas)
    for i in range(1, 5):
        draw.line([(i * panel_w, 0), (i * panel_w, panel_h)], fill=(64, 74, 96, 255), width=1)

    ox4 = 4 * panel_w
    canvas.alpha_composite(icon.resize((128, 128), Image.NEAREST), (ox4 + 54, 18))
    # Checkerboard behind atlas swatch so glass alpha translucency is clearly visible
    sw_size = 112
    checker = Image.new('RGBA', (sw_size, sw_size), (48, 56, 72, 255))
    cdraw = ImageDraw.Draw(checker)
    for cy in range(0, sw_size, 8):
        for cx in range(0, sw_size, 8):
            if ((cx // 8) + (cy // 8)) % 2 == 0:
                cdraw.rectangle([cx, cy, cx + 7, cy + 7], fill=(82, 94, 116, 255))
    checker.alpha_composite(texture.resize((sw_size, sw_size), Image.NEAREST))
    canvas.alpha_composite(checker, (ox4 + 62, 168))
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
    parser.add_argument('--preview', default=str(HERE / 'lightning_hat_preview.png'))
    args = parser.parse_args()

    blueprint, texture = build_blueprint()
    bb_path = Path(args.out_bbmodel)
    bb_path.write_text(json.dumps(blueprint, indent=2) + '\n', encoding='utf-8')
    texture.save(HERE / f'{MODEL}.png', optimize=True)

    assets_dir = Path(args.out_assets)
    icon = build_lightning_icon()
    write_icon_assets(icon, assets_dir)
    render_preview(blueprint, texture, icon, Path(args.preview))

    print(
        f'Built {bb_path.name}: {len(blueprint["elements"])} cubes, '
        f'{len(blueprint["animations"])} animations, '
        f'icon -> {assets_dir}'
    )


if __name__ == '__main__':
    main()
