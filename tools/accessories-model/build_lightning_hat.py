#!/usr/bin/env python3
"""Procedural 3D Blockbench 4.10 generator for `elytrix_lightning_hat` (Грозовая молния).

Creates:
  1. `elytrix_lightning_hat.bbmodel` — ModelEngine 4.1.0 `free` blueprint (`uv_width=16`,
     `uv_height=16`, `internal=true`, all cube rotations `[0,0,0]`, `shade=false` self-luminous
     plasma) featuring a dark storm-indigo thunderhead, multi-layered 3D zig-zag thunderbolt,
     branching side forks, 4 orbiting temple arcs, and an expanding 8-segment impact shockwave
     ring + radial sparks above the player's crown (`Y = 33.8 .. 49.9`, strictly `< 1.85m` from
     the wearer's eye so the FPV shader hides it 100% in 1st-person while keeping it 100% visible
     in F5 and to other players).
  2. Two seamless 20-TPS keyframe animations:
       - `idle` (`loop`, `3.2s`): continuous hover & high-voltage crackle + storm charge-up +
         downward thunderbolt slam + realistic return-stroke double-flash + expanding shockwave!
       - `strike` (`once`, `override=true`, `1.3s`): instant triple-flash super-strike played
         immediately on equip and periodically while worn.
  3. Crisp 32x32 pixel-art menu icon (`reallyworld:lightning_hat_icon`) + preview strip PNG.
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


# UV rectangles in 0..16 space (8 px per unit on 128x128 texture)
UV_CORE_WHITE = [0.25, 0.25, 3.75, 3.75]     # Blinding white-cyan plasma core
UV_BOLT_CYAN = [4.25, 0.25, 7.75, 3.75]      # High-voltage electric sky-cyan shell
UV_PLASMA_PINK = [8.25, 0.25, 11.75, 3.75]   # Signature Elytrix violet-pink plasma (#F8BEFB)
UV_TIP_GOLD = [12.25, 0.25, 15.75, 3.75]     # White-gold high-voltage spearpoint spark
UV_CLOUD_TOP = [0.25, 4.25, 7.75, 7.75]      # Dark storm-indigo thundercloud top/sides
UV_CLOUD_UNDER = [8.25, 4.25, 15.75, 7.75]   # Charged storm underside with cyan/pink veins
UV_RING_INNER = [0.25, 8.25, 7.75, 11.75]    # Shockwave ring bright cyan-white inner band
UV_RING_OUTER = [8.25, 8.25, 15.75, 11.75]   # Shockwave ring neon cyan + pink outer band


def _faces(default_uv, **overrides) -> dict:
    out = {}
    for side in ('north', 'east', 'south', 'west', 'up', 'down'):
        uv = overrides.get(side, default_uv)
        out[side] = {'uv': list(uv), 'texture': 0}
    return out


def _cube(name: str, p_from: list[float], p_to: list[float], origin: list[float], faces: dict, shade: bool = False) -> dict:
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
        'light_emission': 15,
        'color': 0,
        'faces': faces,
        'uuid': uid(f'cube:{name}'),
    }


def build_lightning_texture() -> Image.Image:
    """Builds a crisp 128x128 pixel-art storm & plasma atlas (zero blur, pure pixel art)."""
    img = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
    px = img.load()

    # 1. [0..32, 0..32] Blinding white-cyan plasma core
    for y in range(32):
        for x in range(32):
            edge = min(x, y, 31 - x, 31 - y)
            checker = ((x // 2) + (y // 2)) % 2
            if edge <= 2:
                col = (168, 248, 255, 255)
            elif edge <= 5:
                col = (216, 253, 255, 255) if checker == 0 else (238, 255, 255, 255)
            else:
                col = (255, 255, 255, 255)
            px[x, y] = col

    # 2. [32..64, 0..32] Electric sky-cyan bolt shell
    for y in range(32):
        for x in range(32, 64):
            lx = x - 32
            edge = min(lx, y, 31 - lx, 31 - y)
            diag = ((lx // 2) - (y // 2)) % 5
            if edge <= 2:
                col = (10, 134, 238, 255)
            elif edge <= 5:
                col = (30, 196, 255, 255)
            elif diag == 0:
                col = (162, 248, 255, 255)
            else:
                col = (68, 234, 255, 255)
            px[x, y] = col

    # 3. [64..96, 0..32] Signature Elytrix neon violet-pink plasma (#F8BEFB)
    for y in range(32):
        for x in range(64, 96):
            lx = x - 64
            edge = min(lx, y, 31 - lx, 31 - y)
            spark = ((lx * 3 + y * 5) % 13 == 0)
            if edge <= 2:
                col = (168, 85, 247, 255)
            elif edge <= 5:
                col = (226, 136, 252, 255)
            elif spark:
                col = (255, 246, 255, 255)
            else:
                col = (248, 190, 251, 255)
            px[x, y] = col

    # 4. [96..128, 0..32] High-voltage white-gold spark spearpoint
    for y in range(32):
        for x in range(96, 128):
            lx = x - 96
            edge = min(lx, y, 31 - lx, 31 - y)
            if edge <= 2:
                col = (94, 236, 255, 255)
            elif edge <= 6:
                col = (255, 232, 118, 255)
            else:
                col = (255, 253, 236, 255)
            px[x, y] = col

    # 5. [0..64, 32..64] Dark storm-indigo thundercloud top & sides (pixel-art blocks)
    for y in range(32, 64):
        for x in range(0, 64):
            bx, by = x // 4, (y - 32) // 4
            h = (bx * 7 + by * 13 + (bx ^ by) * 5) % 11
            if by <= 1 or h >= 9:
                col = (58, 70, 118, 255)
            elif h >= 5:
                col = (40, 49, 88, 255)
            elif h >= 2:
                col = (29, 35, 66, 255)
            else:
                col = (22, 26, 52, 255)
            px[x, y] = col

    # 6. [64..128, 32..64] Charged storm underside with glowing cyan & #F8BEFB lightning veins
    for y in range(32, 64):
        for x in range(64, 128):
            lx, ly = x - 64, y - 32
            bx, by = lx // 2, ly // 2
            vein_a = abs((bx - 16) + ((by * 3) % 5 - 2))
            vein_b = abs((by - 8) + ((bx * 2) % 5 - 2))
            if vein_a == 0 or vein_b == 0:
                col = (232, 254, 255, 255)
            elif vein_a == 1:
                col = (84, 238, 255, 255)
            elif vein_b == 1:
                col = (248, 190, 251, 255)
            else:
                h = (bx * 5 + by * 9) % 7
                col = (34, 41, 78, 255) if h < 4 else (48, 56, 104, 255)
            px[x, y] = col

    # 7. [0..64, 64..96] Shockwave ring bright cyan-white inner plasma
    for y in range(64, 96):
        for x in range(0, 64):
            ly = y - 64
            band = abs(ly - 15)
            if band <= 4:
                col = (255, 255, 255, 255)
            elif band <= 9:
                col = (118, 248, 255, 255)
            else:
                col = (28, 190, 255, 255)
            px[x, y] = col

    # 8. [64..128, 64..96] Shockwave ring neon cyan + Elytrix violet-pink outer band
    for y in range(64, 96):
        for x in range(64, 128):
            lx, ly = x - 64, y - 64
            band = abs(ly - 15)
            alt = ((lx // 4) % 2 == 0)
            if band <= 4:
                col = (248, 190, 251, 255) if alt else (142, 250, 255, 255)
            elif band <= 10:
                col = (206, 118, 250, 255) if alt else (52, 218, 255, 255)
            else:
                col = (146, 78, 232, 255)
            px[x, y] = col

    return img


def build_lightning_icon() -> Image.Image:
    """Builds a razor-sharp 32x32 pixel-art menu icon (`reallyworld:lightning_hat_icon`)."""
    icon = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = icon.load()

    OUTLINE = (16, 20, 42, 255)
    CLOUD_DARK = (30, 37, 70, 255)
    CLOUD_MID = (46, 56, 102, 255)
    CLOUD_HI = (70, 84, 144, 255)
    CYAN_DEEP = (16, 168, 250, 255)
    CYAN_BRIGHT = (82, 242, 255, 255)
    PINK_NEON = (248, 190, 251, 255)
    PINK_DEEP = (204, 112, 246, 255)
    WHITE = (255, 255, 255, 255)
    GOLD_WHITE = (255, 248, 176, 255)

    def put(x: int, y: int, c: tuple[int, int, int, int]):
        if 0 <= x < 32 and 0 <= y < 32:
            px[x, y] = c

    # 1. Compact storm cloud crown at top (y = 2..10, x = 5..26)
    cloud_spans = {
        2: (11, 20),
        3: (8, 23),
        4: (6, 25),
        5: (5, 26),
        6: (5, 26),
        7: (6, 25),
        8: (7, 24),
    }
    for y, (x0, x1) in cloud_spans.items():
        for x in range(x0 - 1, x1 + 2):
            if x == x0 - 1 or x == x1 + 1 or y == 2:
                put(x, y, OUTLINE)
            elif y <= 4:
                put(x, y, CLOUD_HI if (x + y) % 3 != 0 else CLOUD_MID)
            elif y <= 6:
                put(x, y, CLOUD_MID if (x % 2 == 0) else CLOUD_DARK)
            else:
                put(x, y, CLOUD_DARK)
    for x in range(7, 25):
        put(x, 9, OUTLINE)
    # Glowing underside veins inside cloud
    for x in (10, 11, 19, 20):
        put(x, 7, PINK_NEON)
    for x in range(13, 19):
        put(x, 7, CYAN_BRIGHT)
        put(x, 8, WHITE if 14 <= x <= 17 else CYAN_DEEP)

    # 2. Impact shockwave ring at bottom (y = 24..29, x = 5..26)
    ring_pts = [
        (7, 26), (8, 25), (9, 25), (10, 24), (11, 24),
        (20, 24), (21, 24), (22, 25), (23, 25), (24, 26),
        (6, 27), (25, 27),
        (7, 28), (8, 28), (9, 29), (10, 29), (11, 29), (12, 29),
        (19, 29), (20, 29), (21, 29), (22, 29), (23, 28), (24, 28),
        (13, 29), (14, 29), (15, 29), (16, 29), (17, 29), (18, 29),
    ]
    for rx, ry in ring_pts:
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            if px[rx + ox, ry + oy][3] == 0:
                put(rx + ox, ry + oy, OUTLINE)
    for rx, ry in ring_pts:
        is_pink = rx in (7, 8, 23, 24, 6, 25)
        put(rx, ry, PINK_NEON if is_pink else CYAN_BRIGHT)
    for rx in range(13, 19):
        put(rx, 28, WHITE)

    # 3. Iconic razor-sharp zig-zag thunderbolt (y = 7..27)
    # Each row: (x_left, x_right)
    bolt_rows = {
        7:  (15, 20),
        8:  (14, 19),
        9:  (13, 18),
        10: (12, 17),
        11: (11, 16),
        12: (10, 15),
        13: (9,  15),
        14: (8,  21),  # sharp mid-jag crossbar!
        15: (9,  22),
        16: (15, 21),
        17: (14, 20),
        18: (14, 19),
        19: (13, 18),
        20: (13, 17),
        21: (13, 17),
        22: (13, 16),
        23: (13, 16),
        24: (14, 16),
        25: (14, 15),
        26: (14, 15),
        27: (14, 14),
    }
    # Outline pass around thunderbolt
    for y, (x0, x1) in bolt_rows.items():
        for x in range(x0, x1 + 1):
            for ox in (-1, 0, 1):
                for oy in (-1, 0, 1):
                    nx, ny = x + ox, y + oy
                    if 0 <= nx < 32 and 0 <= ny < 32 and ny not in bolt_rows:
                        if ny >= 9:
                            put(nx, ny, OUTLINE)
                    elif 0 <= nx < 32 and 0 <= ny < 32:
                        bx0, bx1 = bolt_rows[ny]
                        if nx < bx0 or nx > bx1:
                            put(nx, ny, OUTLINE)

    # Fill pass for thunderbolt (cyan edge + #F8BEFB highlight + white-gold core)
    for y, (x0, x1) in bolt_rows.items():
        for x in range(x0, x1 + 1):
            if y >= 25:
                put(x, y, GOLD_WHITE if x == x0 else WHITE)
            elif x == x0:
                put(x, y, CYAN_BRIGHT)
            elif x == x1:
                put(x, y, PINK_NEON if y % 2 == 0 else CYAN_DEEP)
            elif x == x0 + 1 and (x1 - x0) >= 4:
                put(x, y, CYAN_BRIGHT)
            else:
                put(x, y, WHITE if y < 22 else GOLD_WHITE)

    # 4. Crisp side electric sparks around the strike!
    sparks = [
        (4, 13, CYAN_BRIGHT), (3, 12, WHITE),
        (27, 13, PINK_NEON), (28, 12, WHITE),
        (5, 21, PINK_DEEP), (4, 20, PINK_NEON),
        (26, 21, CYAN_DEEP), (27, 20, CYAN_BRIGHT),
        (10, 26, GOLD_WHITE), (20, 26, GOLD_WHITE),
    ]
    for sx, sy, scol in sparks:
        put(sx, sy, scol)

    return icon


def eval_lightning_pose(u: float, mode: str = 'idle') -> dict:
    """Evaluates all bone positions, rotations, and scales at normalized time u in [0, 1].

    `mode == 'idle'` (3.2s seamless loop):
      - u in [0.00, 0.39): Hover & lively electric crackle above head
      - u in [0.39, 0.485): Storm cloud swells & charges; bolt retracts upward into cloud!
      - u in [0.485, 0.535): STRIKE #1 SLAM! Bolt slams down onto head, shockwave explodes!
      - u in [0.535, 0.575): Brief flicker dip between return strokes
      - u in [0.575, 0.635): STRIKE #2 RETURN STROKE FLASH! Second blinding flash + wider wave!
      - u in [0.635, 1.00]: Shockwave dissipates & residual arcs crackle back into seamless loop!

    `mode == 'strike'` (1.3s override super-strike):
      - Rapid charge -> Triple high-voltage return-stroke slam -> clean settle!
    """
    tau = 2.0 * math.pi

    if mode == 'idle':
        # Seamless periodic base hum
        hover_y = 0.35 * math.sin(tau * u)
        cloud_sway_x = 0.28 * math.sin(tau * u)
        cloud_rot = [
            1.8 * math.sin(tau * 2.0 * u),
            6.0 * math.sin(tau * u),
            2.2 * math.cos(tau * 2.0 * u),
        ]
        cloud_sc = [1.0, 1.0, 1.0]

        # Crisp high-frequency electric crackle (seamless harmonics)
        jitter_z = 2.2 * math.sin(tau * 7.0 * u) + 1.4 * math.cos(tau * 11.0 * u)
        jitter_y = 5.0 * math.sin(tau * 3.0 * u)

        bolt_dy = 0.0
        bolt_sc = [0.92 + 0.05 * math.sin(tau * 8.0 * u), 0.94, 0.92 + 0.05 * math.sin(tau * 8.0 * u)]
        bolt_rot = [0.0, jitter_y, jitter_z]

        fork_sc = 0.82 + 0.12 * math.sin(tau * 6.0 * u)
        fork_spread = 4.0 * math.sin(tau * 5.0 * u)

        ring_sc_xz = 0.52 + 0.06 * math.sin(tau * 4.0 * u)
        ring_sc_y = 0.70
        ring_ry = (360.0 * u) % 360.0  # Smooth 360 deg spin per loop -> wait: linear 0..360!
        ring_ry = 18.0 * math.sin(tau * 2.0 * u)

        sparks_sc = 0.0
        sparks_dy = 0.0
        arc_flare = 0.85 + 0.15 * math.sin(tau * 9.0 * u)

        # Storm Charge-Up window: [0.38, 0.485]
        if 0.38 <= u < 0.485:
            p = (u - 0.38) / (0.485 - 0.38)
            ease = p * p * (3.0 - 2.0 * p)
            cloud_sc = [1.0 + 0.14 * ease, 1.0 + 0.10 * ease, 1.0 + 0.14 * ease]
            cloud_rot[2] += 4.5 * math.sin(p * math.pi * 4.0)
            bolt_dy = 3.1 * ease
            bolt_sc = [0.88 - 0.66 * ease, 0.94 - 0.78 * ease, 0.88 - 0.66 * ease]
            fork_sc = 0.82 * (1.0 - 0.80 * ease)
            ring_sc_xz = 0.50 - 0.30 * ease
            arc_flare = 0.80 - 0.45 * ease

        # STRIKE SLAM #1: [0.485, 0.540]
        elif 0.485 <= u < 0.540:
            p = (u - 0.485) / (0.540 - 0.485)
            slam = min(1.0, p * 2.5)
            cloud_sc = [1.15 - 0.07 * p, 0.92 + 0.08 * p, 1.15 - 0.07 * p]
            bolt_dy = 3.1 * (1.0 - slam) - 0.75 * slam
            bolt_sc = [0.22 + 0.90 * slam, 0.16 + 1.08 * slam, 0.22 + 0.90 * slam]
            bolt_rot = [1.5, -6.0, 4.0]
            fork_sc = 1.12 * slam
            fork_spread = 16.0 * slam
            ring_sc_xz = 0.20 + 1.05 * p
            ring_sc_y = 1.30 - 0.20 * p
            sparks_sc = 1.10 * slam
            sparks_dy = 0.45 * p
            arc_flare = 1.15

        # Inter-stroke flicker dip: [0.540, 0.570]
        elif 0.540 <= u < 0.570:
            p = (u - 0.540) / (0.570 - 0.540)
            cloud_sc = [1.08, 1.02, 1.08]
            bolt_dy = -0.25
            bolt_sc = [0.46, 0.58, 0.46]
            bolt_rot = [-1.0, 5.0, -3.0]
            fork_sc = 0.48
            fork_spread = 6.0
            ring_sc_xz = 1.25 + 0.10 * p
            ring_sc_y = 0.95
            sparks_sc = 0.55
            sparks_dy = 0.55
            arc_flare = 0.85

        # STRIKE #2 RETURN-STROKE DOUBLE FLASH: [0.570, 0.640]
        elif 0.570 <= u < 0.640:
            p = (u - 0.570) / (0.640 - 0.570)
            flash = math.sin(min(1.0, p * 1.35) * math.pi * 0.5)
            cloud_sc = [1.12 - 0.06 * p, 0.95 + 0.05 * p, 1.12 - 0.06 * p]
            bolt_dy = -0.65 * (1.0 - 0.35 * p)
            bolt_sc = [1.08 - 0.10 * p, 1.18 - 0.14 * p, 1.08 - 0.10 * p]
            bolt_rot = [-1.5, 8.0 * (1.0 - 0.5 * p), -4.0]
            fork_sc = 1.08 - 0.14 * p
            fork_spread = 18.0 - 6.0 * p
            ring_sc_xz = 1.35 + 0.18 * p
            ring_sc_y = 1.15 - 0.25 * p
            sparks_sc = (1.05 - 0.30 * p) * flash
            sparks_dy = 0.55 + 0.45 * p
            arc_flare = 1.12 - 0.12 * p

        # Aftershock dissipation back to seamless hover: [0.640, 0.840]
        elif 0.640 <= u < 0.840:
            p = (u - 0.640) / (0.840 - 0.640)
            ease = 1.0 - (p * p * (3.0 - 2.0 * p))
            cloud_sc = [1.0 + 0.06 * ease, 1.0, 1.0 + 0.06 * ease]
            bolt_dy = -0.42 * ease
            bolt_sc = [0.92 + 0.06 * ease, 0.94 + 0.10 * ease, 0.92 + 0.06 * ease]
            fork_sc = 0.82 + 0.12 * ease
            fork_spread = 4.0 + 8.0 * ease
            ring_sc_xz = 0.52 + 1.01 * ease
            ring_sc_y = 0.70 + 0.20 * ease
            sparks_sc = max(0.0, 0.75 * (1.0 - min(1.0, p * 1.6)))
            sparks_dy = 1.00 * min(1.0, p * 1.6)
            arc_flare = 0.85 + 0.15 * ease

    else:
        # Dedicated `strike` override clip (1.3s): instant charge -> triple flash slam -> clean settle
        hover_y = 0.0
        cloud_sway_x = 0.0
        cloud_rot = [0.0, 0.0, 0.0]
        ring_ry = 24.0 * math.sin(tau * u)
        if u in (0.0, 1.0):
            cloud_sc = [1.0, 1.0, 1.0]
            bolt_dy = 0.0
            bolt_sc = [0.94, 0.94, 0.94]
            bolt_rot = [0.0, 0.0, 0.0]
            fork_sc = 0.85
            fork_spread = 0.0
            ring_sc_xz = 0.52
            ring_sc_y = 0.70
            sparks_sc = 0.0
            sparks_dy = 0.0
            arc_flare = 0.85
        elif u < 0.16:
            p = u / 0.16
            cloud_sc = [1.0 + 0.16 * p, 1.0 + 0.12 * p, 1.0 + 0.16 * p]
            cloud_rot = [0.0, 0.0, 5.0 * math.sin(p * math.pi * 2.0)]
            bolt_dy = 3.2 * p
            bolt_sc = [0.94 - 0.72 * p, 0.94 - 0.78 * p, 0.94 - 0.72 * p]
            bolt_rot = [0.0, 0.0, 0.0]
            fork_sc = 0.20
            fork_spread = -4.0
            ring_sc_xz = 0.22
            ring_sc_y = 0.50
            sparks_sc = 0.0
            sparks_dy = 0.0
            arc_flare = 0.40
        elif u < 0.62:
            p = (u - 0.16) / (0.62 - 0.16)
            # 3 sharp high-voltage return strokes!
            stroke = abs(math.cos(p * math.pi * 2.5))
            cloud_sc = [1.16 - 0.08 * p, 0.92 + 0.08 * p, 1.16 - 0.08 * p]
            cloud_rot = [2.0 * math.sin(p * math.pi * 6.0), 0.0, -3.5 * math.cos(p * math.pi * 6.0)]
            bolt_dy = -0.75 + 0.25 * (1.0 - stroke)
            bolt_sc = [0.68 + 0.44 * stroke, 0.74 + 0.50 * stroke, 0.68 + 0.44 * stroke]
            bolt_rot = [1.5 * math.sin(p * math.pi * 5.0), 9.0 * math.sin(p * math.pi * 3.0), 4.5 * math.cos(p * math.pi * 5.0)]
            fork_sc = 0.60 + 0.55 * stroke
            fork_spread = 8.0 + 12.0 * stroke
            ring_sc_xz = 0.30 + 1.25 * p
            ring_sc_y = 0.85 + 0.45 * stroke
            sparks_sc = 0.45 + 0.70 * stroke
            sparks_dy = 0.95 * p
            arc_flare = 0.90 + 0.28 * stroke
        else:
            p = (u - 0.62) / (1.0 - 0.62)
            ease = 1.0 - (p * p * (3.0 - 2.0 * p))
            cloud_sc = [1.0 + 0.06 * ease, 1.0, 1.0 + 0.06 * ease]
            bolt_dy = -0.50 * ease
            bolt_sc = [0.94 + 0.12 * ease, 0.94 + 0.16 * ease, 0.94 + 0.12 * ease]
            bolt_rot = [0.0, 3.0 * ease, -1.5 * ease]
            fork_sc = 0.85 + 0.18 * ease
            fork_spread = 10.0 * ease
            ring_sc_xz = 0.52 + 1.03 * ease
            ring_sc_y = 0.70 + 0.20 * ease
            sparks_sc = max(0.0, 0.80 * (1.0 - min(1.0, p * 1.7)))
            sparks_dy = 0.95 + 0.35 * p
            arc_flare = 0.85 + 0.20 * ease

    # 4 temple arcs orbit/crackle with phase offsets
    arcs = {}
    for idx, aname in enumerate(('arc_nw', 'arc_ne', 'arc_sw', 'arc_se')):
        ph = tau * (3.0 * u + 0.25 * idx)
        sign_x = -1.0 if 'w' in aname else 1.0
        sign_z = -1.0 if 'n' in aname else 1.0
        sc_i = max(0.0, round(arc_flare * (0.86 + 0.18 * math.sin(ph)), 3))
        arcs[aname] = {
            'pos': [0.0, round(0.25 * math.sin(ph), 3), 0.0],
            'rot': [round(sign_z * 10.0 * math.sin(ph), 3), round(14.0 * math.cos(ph), 3), round(sign_x * (8.0 + 10.0 * (arc_flare - 0.85)), 3)],
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
        # Guarantee exact loop endpoint match for seamless `idle`
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


def build_blueprint() -> tuple[dict, Image.Image]:
    texture = build_lightning_texture()
    raw = io.BytesIO()
    texture.save(raw, format='PNG', optimize=True)

    root_orig = _pt(0.0, 34.8, 0.0)
    cloud_orig = _pt(0.0, 45.2, 0.0)
    bolt_orig = _pt(0.0, 39.8, 0.0)
    fork_l_orig = _pt(-1.9, 40.8, 0.0)
    fork_r_orig = _pt(1.9, 40.2, 0.0)
    ring_orig = _pt(0.0, 33.9, 0.0)
    sparks_orig = _pt(0.0, 34.1, 0.0)

    elements: list[dict] = []

    def add(c: dict) -> str:
        elements.append(c)
        return c['uuid']

    # 1. Storm Cloud cluster (Y = 43.7 .. 47.2, compact stormhead with glowing #F8BEFB + cyan veins)
    cloud_faces = _faces(UV_CLOUD_TOP, down=UV_CLOUD_UNDER)
    cloud_vein_faces = _faces(UV_PLASMA_PINK, north=UV_BOLT_CYAN, south=UV_BOLT_CYAN, down=UV_CORE_WHITE)
    cloud_uuids = [
        add(_cube('cloud_main',   _pt(-3.6, 44.3, -2.8), _pt(3.6, 46.5, 2.8), cloud_orig, cloud_faces)),
        add(_cube('cloud_crown',  _pt(-2.4, 46.2, -2.0), _pt(2.4, 47.2, 2.0), cloud_orig, cloud_faces)),
        add(_cube('cloud_left',   _pt(-4.8, 44.1, -2.1), _pt(-3.1, 45.9, 2.1), cloud_orig, cloud_faces)),
        add(_cube('cloud_right',  _pt(3.1, 44.1, -2.1),  _pt(4.8, 45.9, 2.1), cloud_orig, cloud_faces)),
        add(_cube('cloud_front',  _pt(-2.5, 44.2, -3.7), _pt(2.5, 45.8, -2.4), cloud_orig, cloud_faces)),
        add(_cube('cloud_back',   _pt(-2.5, 44.2, 2.4),  _pt(2.5, 45.8, 3.7), cloud_orig, cloud_faces)),
        add(_cube('cloud_node_c', _pt(-1.3, 43.7, -1.1), _pt(1.3, 44.4, 1.1), cloud_orig, cloud_vein_faces)),
        add(_cube('cloud_node_l', _pt(-3.8, 43.8, -0.7), _pt(-2.4, 44.3, 0.7), cloud_orig, _faces(UV_PLASMA_PINK))),
        add(_cube('cloud_node_r', _pt(2.4, 43.8, -0.7),  _pt(3.8, 44.3, 0.7), cloud_orig, _faces(UV_BOLT_CYAN))),
    ]

    # 2. Centerpiece 3D Jagged Thunderbolt (`bolt_main`: Y = 33.7 .. 44.8)
    # Unified Electric Cyan plasma shell + raised 3D Pure White hot core + Golden-White strike tip!
    bolt_uuids: list[str] = []
    bolt_segments = [
        # (tag, cx, y0, y1, half_w, half_z, shell_uv)
        # Upper shaft slanting from (-1.35 -> +1.85 in world X so from North viewer it slants Top-Right -> Mid-Left just like the icon!)
        ('u1', -1.25, 43.6, 44.8, 0.98, 0.60, UV_BOLT_CYAN),
        ('u2', -0.45, 42.6, 43.8, 0.96, 0.58, UV_BOLT_CYAN),
        ('u3',  0.35, 41.7, 42.8, 0.94, 0.56, UV_BOLT_CYAN),
        ('u4',  1.15, 40.8, 41.9, 0.92, 0.55, UV_BOLT_CYAN),
        ('u5',  1.85, 40.0, 41.0, 0.90, 0.54, UV_BOLT_CYAN),
        # Sharp horizontal mid-jag crossbar (+1.85 -> -1.75)
        ('m1',  0.65, 39.8, 40.9, 1.00, 0.58, UV_BOLT_CYAN),
        ('m2', -0.55, 39.6, 40.7, 1.00, 0.58, UV_BOLT_CYAN),
        ('m3', -1.65, 39.4, 40.5, 0.92, 0.56, UV_PLASMA_PINK),
        # Lower strike spear plunging from (-1.50 -> 0.0, Y=33.7) right onto the crown!
        ('l1', -1.35, 38.4, 39.6, 0.86, 0.52, UV_BOLT_CYAN),
        ('l2', -1.00, 37.4, 38.6, 0.78, 0.48, UV_BOLT_CYAN),
        ('l3', -0.68, 36.5, 37.6, 0.68, 0.44, UV_BOLT_CYAN),
        ('l4', -0.38, 35.6, 36.7, 0.56, 0.38, UV_BOLT_CYAN),
        ('l5', -0.16, 34.8, 35.8, 0.44, 0.32, UV_TIP_GOLD),
        ('l6', -0.04, 34.1, 35.0, 0.32, 0.26, UV_TIP_GOLD),
        ('l7',  0.00, 33.6, 34.3, 0.20, 0.20, UV_CORE_WHITE),
    ]
    for tag, cx, y0, y1, hw, hz, suv in bolt_segments:
        bolt_uuids.append(add(_cube(
            f'bolt_shell_{tag}',
            _pt(cx - hw, y0, -hz),
            _pt(cx + hw, y1, hz),
            bolt_orig,
            _faces(suv),
        )))
        if tag != 'l7':
            cw = max(0.18, round(hw * 0.56, 3))
            cz = round(hz + 0.12, 3)
            core_uv = UV_TIP_GOLD if tag in ('l5', 'l6') else UV_CORE_WHITE
            bolt_uuids.append(add(_cube(
                f'bolt_core_{tag}',
                _pt(cx - cw, y0 + 0.06, -cz),
                _pt(cx + cw, y1 - 0.06, cz),
                bolt_orig,
                _faces(core_uv),
            )))

    # 3. Sleek razor-thin branching side lightning forks (`fork_left`, `fork_right`)
    fork_l_uuids = [
        add(_cube('fork_l_1', _pt(-2.55, 39.2, -0.22), _pt(-1.65, 39.85, 0.22), fork_l_orig, _faces(UV_BOLT_CYAN))),
        add(_cube('fork_l_2', _pt(-3.30, 38.4, -0.18), _pt(-2.40, 39.30, 0.18), fork_l_orig, _faces(UV_CORE_WHITE))),
        add(_cube('fork_l_3', _pt(-3.95, 37.6, -0.15), _pt(-3.15, 38.55, 0.15), fork_l_orig, _faces(UV_PLASMA_PINK))),
        add(_cube('fork_l_4', _pt(-4.40, 36.9, -0.12), _pt(-3.80, 37.75, 0.12), fork_l_orig, _faces(UV_TIP_GOLD))),
    ]
    fork_r_uuids = [
        add(_cube('fork_r_1', _pt(1.65, 39.8, -0.22), _pt(2.55, 40.45, 0.22), fork_r_orig, _faces(UV_BOLT_CYAN))),
        add(_cube('fork_r_2', _pt(2.40, 39.0, -0.18), _pt(3.30, 39.90, 0.18), fork_r_orig, _faces(UV_CORE_WHITE))),
        add(_cube('fork_r_3', _pt(3.15, 38.2, -0.15), _pt(3.95, 39.15, 0.15), fork_r_orig, _faces(UV_PLASMA_PINK))),
        add(_cube('fork_r_4', _pt(3.80, 37.5, -0.12), _pt(4.40, 38.35, 0.12), fork_r_orig, _faces(UV_TIP_GOLD))),
    ]

    # 4. Four sleek articulated orbiting electric temple arcs (`arc_nw`, `arc_ne`, `arc_sw`, `arc_se`)
    arc_bones = []
    arc_specs = [
        ('arc_nw', -3.3, -3.3, -1.0, -1.0, UV_BOLT_CYAN, UV_PLASMA_PINK),
        ('arc_ne',  3.3, -3.3,  1.0, -1.0, UV_PLASMA_PINK, UV_BOLT_CYAN),
        ('arc_sw', -3.3,  3.3, -1.0,  1.0, UV_PLASMA_PINK, UV_BOLT_CYAN),
        ('arc_se',  3.3,  3.3,  1.0,  1.0, UV_BOLT_CYAN, UV_PLASMA_PINK),
    ]
    for aname, ax, az, sx, sz, uv_a, uv_b in arc_specs:
        a_orig = _pt(ax, 35.8, az)
        c1 = add(_cube(f'{aname}_1', _pt(ax - 0.18, 34.8, az - 0.18), _pt(ax + 0.18, 35.9, az + 0.18), a_orig, _faces(uv_a)))
        c2 = add(_cube(f'{aname}_2', _pt(ax + sx * 0.28 - 0.16, 35.7, az + sz * 0.28 - 0.16), _pt(ax + sx * 0.28 + 0.16, 36.8, az + sz * 0.28 + 0.16), a_orig, _faces(UV_CORE_WHITE)))
        c3 = add(_cube(f'{aname}_3', _pt(ax - 0.14, 36.6, az - 0.14), _pt(ax + 0.14, 37.6, az + 0.14), a_orig, _faces(uv_b)))
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

    # 5. Expanding 8-segment electric shockwave ring (`impact_ring`, Y = 33.65 .. 34.15)
    ring_in = _faces(UV_RING_INNER)
    ring_out = _faces(UV_RING_OUTER)
    ring_uuids = [
        add(_cube('ring_n',  _pt(-1.9, 33.7, -3.7), _pt(1.9, 34.15, -3.15), ring_orig, ring_in)),
        add(_cube('ring_s',  _pt(-1.9, 33.7,  3.15), _pt(1.9, 34.15, 3.7),  ring_orig, ring_in)),
        add(_cube('ring_w',  _pt(-3.7, 33.7, -1.9), _pt(-3.15, 34.15, 1.9), ring_orig, ring_in)),
        add(_cube('ring_e',  _pt(3.15, 33.7, -1.9), _pt(3.7, 34.15, 1.9),   ring_orig, ring_in)),
        add(_cube('ring_nw', _pt(-3.25, 33.65, -3.25), _pt(-1.85, 34.1, -1.85), ring_orig, ring_out)),
        add(_cube('ring_ne', _pt(1.85,  33.65, -3.25), _pt(3.25, 34.1, -1.85),  ring_orig, ring_out)),
        add(_cube('ring_sw', _pt(-3.25, 33.65, 1.85),  _pt(-1.85, 34.1, 3.25),  ring_orig, ring_out)),
        add(_cube('ring_se', _pt(1.85,  33.65, 1.85),  _pt(3.25, 34.1, 3.25),   ring_orig, ring_out)),
    ]

    # 6. Sleek radial strike burst sparks (`impact_sparks`, burst outward/upward at moment of impact!)
    sparks_uuids = [
        add(_cube('spark_n1', _pt(-0.20, 34.0, -2.5), _pt(0.20, 34.7, -1.5), sparks_orig, _faces(UV_TIP_GOLD))),
        add(_cube('spark_n2', _pt(-0.15, 34.6, -3.4), _pt(0.15, 35.3, -2.4), sparks_orig, _faces(UV_CORE_WHITE))),
        add(_cube('spark_s1', _pt(-0.20, 34.0,  1.5), _pt(0.20, 34.7,  2.5), sparks_orig, _faces(UV_TIP_GOLD))),
        add(_cube('spark_s2', _pt(-0.15, 34.6,  2.4), _pt(0.15, 35.3,  3.4), sparks_orig, _faces(UV_CORE_WHITE))),
        add(_cube('spark_w1', _pt(-2.5, 34.0, -0.20), _pt(-1.5, 34.7, 0.20), sparks_orig, _faces(UV_PLASMA_PINK))),
        add(_cube('spark_w2', _pt(-3.4, 34.6, -0.15), _pt(-2.4, 35.3, 0.15), sparks_orig, _faces(UV_CORE_WHITE))),
        add(_cube('spark_e1', _pt(1.5,  34.0, -0.20), _pt(2.5,  34.7, 0.20), sparks_orig, _faces(UV_BOLT_CYAN))),
        add(_cube('spark_e2', _pt(2.4,  34.6, -0.15), _pt(3.4,  35.3, 0.15), sparks_orig, _faces(UV_CORE_WHITE))),
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
        bone('hat_root', root_orig, [
            bone('storm_cloud', cloud_orig, cloud_uuids),
            bone('bolt_main', bolt_orig, [
                *bolt_uuids,
                bone('fork_left', fork_l_orig, fork_l_uuids),
                bone('fork_right', fork_r_orig, fork_r_uuids),
            ]),
            bone('impact_ring', ring_orig, ring_uuids),
            bone('impact_sparks', sparks_orig, sparks_uuids),
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
    """Renders a 5-panel inspection sheet showing:
       Panel 1: Hover & electric crackle above player head (`u = 0.12`)
       Panel 2: Storm Cloud Charge-Up (`u = 0.46`, bolt retracted into glowing stormhead!)
       Panel 3: LIGHTNING STRIKE SLAM #1 (`u = 0.505`, bolt slamming crown + shockwave burst!)
       Panel 4: RETURN-STROKE DOUBLE FLASH (`u = 0.595`, angled 3/4 view + wide shockwave!)
       Panel 5: Zoomed 32x32 menu icon + texture swatch!
    """
    panel_w, panel_h = 236, 300
    canvas = Image.new('RGBA', (panel_w * 5, panel_h), (16, 19, 32, 255))
    draw = ImageDraw.Draw(canvas)

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

    stages = [
        (0.12,  16.0,  'idle',   '1. HOVER & CRACKLE'),
        (0.465, 16.0,  'idle',   '2. CLOUD CHARGE-UP'),
        (0.505, 14.0,  'idle',   '3. LIGHTNING STRIKE!'),
        (0.595, -28.0, 'idle',   '4. DOUBLE-FLASH WAVE'),
    ]

    for idx, (u, cam_yaw, mode, _label) in enumerate(stages):
        pose = eval_lightning_pose(u, mode=mode)
        ox0 = idx * panel_w

        # Subtle panel divider
        if idx > 0:
            draw.line([(ox0, 0), (ox0, panel_h)], fill=(40, 46, 72, 255), width=1)

        def proj(pt, _ang=math.radians(cam_yaw), _ox=ox0):
            dx = pt[0]
            dz = pt[2]
            xw = dx * math.cos(_ang) - dz * math.sin(_ang)
            zw = dx * math.sin(_ang) + dz * math.cos(_ang)
            yw = pt[1] - 0.18 * zw
            return (_ox + 118.0 - xw * 13.2, 258.0 - (yw - 24.0) * 9.8, zw)

        faces_to_draw = []

        # Reference player head [-4..4, 24..32, -4..4] & shoulders [-8..8, 18..24, -2..2]
        ref_boxes = [
            ([-8.0, 19.0, -2.0], [8.0, 24.0, 2.0], (42, 48, 68)),
            ([-4.0, 24.0, -4.0], [4.0, 32.0, 4.0], (68, 76, 104)),
        ]
        for low, high, base_rgb in ref_boxes:
            cs = [
                np.array([low[0], low[1], low[2]]), np.array([high[0], low[1], low[2]]),
                np.array([high[0], high[1], low[2]]), np.array([low[0], high[1], low[2]]),
                np.array([low[0], low[1], high[2]]), np.array([high[0], low[1], high[2]]),
                np.array([high[0], high[1], high[2]]), np.array([low[0], high[1], high[2]]),
            ]
            for idxs, sm in (((2, 1, 0, 3), 1.0), ((7, 4, 5, 6), 0.85), ((6, 5, 1, 2), 0.92), ((3, 0, 4, 7), 0.90), ((7, 6, 2, 3), 1.08)):
                p2d = [proj(cs[k]) for k in idxs]
                cross = (p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1]) - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0])
                if cross <= 0:
                    col = tuple(min(255, int(c * sm)) for c in base_rgb) + (255,)
                    faces_to_draw.append((sum(p[2] for p in p2d) / 4.0 + 2.0, [(s[0], s[1]) for s in p2d], col, (28, 32, 48, 255)))

        def bone_tf(parent_tf, orig, pos, rot, scale):
            o = np.array(orig)
            t = np.array(pos)
            m = rot_mat(*rot)
            sc = np.array(scale)
            return lambda p: parent_tf(o + t + m @ (sc * (p - o)))

        tf_root = bone_tf(lambda p: p, [0.0, 34.8, 0.0], pose['hat_root_pos'], [0.0, 0.0, 0.0], [1.0, 1.0, 1.0])
        tf_cloud = bone_tf(tf_root, [0.0, 45.2, 0.0], pose['cloud_pos'], pose['cloud_rot'], pose['cloud_scale'])
        tf_bolt = bone_tf(tf_root, [0.0, 39.8, 0.0], pose['bolt_pos'], pose['bolt_rot'], pose['bolt_scale'])
        tf_fl = bone_tf(tf_bolt, [-1.9, 40.8, 0.0], [0.0, 0.0, 0.0], pose['fork_l_rot'], pose['fork_l_scale'])
        tf_fr = bone_tf(tf_bolt, [1.9, 40.2, 0.0], [0.0, 0.0, 0.0], pose['fork_r_rot'], pose['fork_r_scale'])
        tf_ring = bone_tf(tf_root, [0.0, 33.9, 0.0], [0.0, 0.0, 0.0], pose['ring_rot'], pose['ring_scale'])
        tf_sparks = bone_tf(tf_root, [0.0, 34.1, 0.0], pose['sparks_pos'], [0.0, 0.0, 0.0], pose['sparks_scale'])

        arc_tfs = {
            'arc_nw': bone_tf(tf_root, [-3.3, 35.8, -3.3], pose['arcs']['arc_nw']['pos'], pose['arcs']['arc_nw']['rot'], pose['arcs']['arc_nw']['scale']),
            'arc_ne': bone_tf(tf_root, [3.3, 35.8, -3.3],  pose['arcs']['arc_ne']['pos'], pose['arcs']['arc_ne']['rot'], pose['arcs']['arc_ne']['scale']),
            'arc_sw': bone_tf(tf_root, [-3.3, 35.8, 3.3],  pose['arcs']['arc_sw']['pos'], pose['arcs']['arc_sw']['rot'], pose['arcs']['arc_sw']['scale']),
            'arc_se': bone_tf(tf_root, [3.3, 35.8, 3.3],   pose['arcs']['arc_se']['pos'], pose['arcs']['arc_se']['rot'], pose['arcs']['arc_se']['scale']),
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
            quads = [
                ('north', (2, 1, 0, 3), 1.00),
                ('south', (7, 4, 5, 6), 0.98),
                ('east',  (6, 5, 1, 2), 0.95),
                ('west',  (3, 0, 4, 7), 0.95),
                ('up',    (7, 6, 2, 3), 1.02),
                ('down',  (0, 1, 5, 4), 0.92),
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
                if rgba[3] < 24:
                    continue
                col = tuple(min(255, int(c * sm)) for c in rgba[:3]) + (int(rgba[3]),)
                faces_to_draw.append((z_avg, [(s[0], s[1]) for s in p2d], col, None))

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
            draw.polygon(poly, fill=fill_col, outline=edge_col)

    # Panel 5: Zoomed 32x32 menu icon + 128x128 plasma atlas preview
    ox4 = 4 * panel_w
    draw.line([(ox4, 0), (ox4, panel_h)], fill=(40, 46, 72, 255), width=1)
    canvas.alpha_composite(icon.resize((128, 128), Image.NEAREST), (ox4 + 54, 18))
    canvas.alpha_composite(texture.resize((112, 112), Image.NEAREST), (ox4 + 62, 168))
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
