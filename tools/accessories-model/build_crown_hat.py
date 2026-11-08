#!/usr/bin/env python3
"""Procedurally builds the 3D Royal Crown hat (`elytrix_royal_crown`),
its 32x32 pixel-art menu icon (`reallyworld:crown_icon`), and a multi-angle
verification preview strip.

100% pure procedural Python + Pillow + NumPy — zero AI generation:
  1. Exact In-Game 3D Head-Glued Rig (`приклеена к голове` — full `yaw` + `pitch`):
       - Calibrated directly to vanilla Minecraft's `PlayerRenderer` (`0.9375` scale):
           * Exact player neck / head rotation joint: `[0.0, 22.50, 0.0]` (`1.40625m`)
           * Bare player head:  X/Z in `[-3.75, +3.75]`, Y in `[22.50, 30.00]`
           * 2nd-layer skin hat: X/Z in `[-4.22, +4.22]`, Y up to `30.47`
       - Root bone `hi_crown_root` uses ModelEngine 4.1.0's built-in `hi_` inherited `Head`
         behavior (`DefaultBehaviorParser` -> `BoneBehaviorTypes.HEAD`, `inherited = true`)
         pivoted at the exact player neck joint `[0.0, 22.50, 0.0]`, with `setLockPitch(false)`
         and live packet-level `xHeadRot = playerPitch` + `sneak` neck-drop compensation
         (`-2.34` BB units when crouching). Looking straight up (`-90°`), straight ahead (`0°`),
         or straight down (`+90°`) swings the crown along the exact same 3D head arc with
         0.00mm detachment!
  2. Subtle Royal Animation (`небольшая анимация`, `idle` loop 3.6s @ 20 TPS):
       - `hi_crown_root` and `crown_body` have ZERO wobble/drift (`0.00` BB relative motion)
         so the golden circlet stays 100% superglued to the player's forehead & temples.
       - Inset faceted jewels (`crown_gems`) gently pulse with a subtle gleam, while four
         delicate 3D golden/diamond glint stars (`glint_n`, `glint_e`, `glint_s`, `glint_w`)
         twinkle, rotate, and shimmer in staggered waves in the tilted head's own local frame.
  3. Blockbench `4.10` `free` blueprint (`elytrix_royal_crown.bbmodel`):
       - `resolution` 16x16, `uv_width`/`uv_height` = 16, `internal: true`, all UVs in `0..16`
       - Zero per-cube rotations (`rotation: [0.0, 0.0, 0.0]` on every cube)
       - `< 1.85m` from 1st-person eye -> auto-hidden in 1st-person (`CLOSE_TINT_VALUE`)
         while crisp & visible in `F5` and to all other players.
"""
import argparse
import base64
import io
import json
import math
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = 'elytrix_royal_crown'
ICON = 'crown_icon'

IDLE_LENGTH = 3.6   # 72 ticks @ 20 TPS — calm, noble shimmer loop
IDLE_STEPS = 72


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f'elytrix.royal_crown.v1:{tag}'))


# ---------------------------------------------------------------------------
# 1. Calm, Rich Pixel-Art Royal Gold, Velvet & Jewel Texture (128x128, UV 16x16)
# ---------------------------------------------------------------------------
UV_GOLD_BAND      = (0.25, 0.25, 3.75, 3.75)    # Rich brushed royal gold band
UV_GOLD_RIM       = (4.25, 0.25, 7.75, 3.75)    # Bright burnished gold rim / bevel
UV_GOLD_SPECULAR  = (8.25, 0.25, 11.75, 3.75)   # Pale champagne-gold finial pearl / highlight
UV_GOLD_SHADE     = (12.25, 0.25, 15.75, 3.75)  # Warm antique gold inner / underside shade

UV_VELVET_CRIMSON = (0.25, 4.25, 3.75, 7.75)    # Deep royal crimson velvet cap
UV_RUBY_FACET     = (4.25, 4.25, 7.75, 7.75)    # Faceted sovereign ruby
UV_SAPPHIRE_FACET = (8.25, 4.25, 11.75, 7.75)   # Faceted royal sapphire
UV_DIAMOND_FACET  = (12.25, 4.25, 15.75, 7.75)  # Crisp ice-diamond cabochon & glint core

UV_GLINT_GOLD     = (0.25, 8.25, 3.75, 11.75)   # Translucent warm champagne glint ray
UV_GLINT_ICE      = (4.25, 8.25, 7.75, 11.75)   # Translucent crystal-diamond glint ray


def build_crown_texture() -> Image.Image:
    """Builds a 128x128 pixel-art texture (8x8 PNG pixels per 1x1 UV unit)."""
    arr = np.zeros((128, 128, 4), dtype=np.uint8)

    def fill_tile(tx: int, ty: int, base_rgba: tuple, bevel_hi: tuple | None = None,
                  bevel_lo: tuple | None = None, checker_delta: int = 0):
        x0, y0 = tx * 32, ty * 32
        for py in range(32):
            for px in range(32):
                bx, by = px // 4, py // 4
                r, g, b, a = base_rgba
                if checker_delta:
                    d = checker_delta if ((bx + by) % 2 == 0) else -checker_delta
                    if (bx * 5 + by * 3) % 7 == 0:
                        d += checker_delta // 2
                    r = max(0, min(255, r + d))
                    g = max(0, min(255, g + d))
                    b = max(0, min(255, b + d))
                if bevel_hi and (by == 0 or bx == 0):
                    r, g, b, a = bevel_hi
                elif bevel_lo and (by == 7 or bx == 7):
                    r, g, b, a = bevel_lo
                arr[y0 + py, x0 + px] = (r, g, b, a)

    # Row 0: Royal Gold Metallics (warm, noble gold — zero harsh neon yellow!)
    fill_tile(0, 0, (226, 168, 46, 255), bevel_hi=(246, 202, 86, 255), bevel_lo=(186, 128, 26, 255), checker_delta=5)
    fill_tile(1, 0, (244, 198, 78, 255), bevel_hi=(255, 228, 134, 255), bevel_lo=(204, 148, 36, 255), checker_delta=4)
    fill_tile(2, 0, (253, 228, 138, 255), bevel_hi=(255, 245, 196, 255), bevel_lo=(228, 182, 72, 255), checker_delta=3)
    fill_tile(3, 0, (176, 120, 26, 255), bevel_hi=(198, 140, 38, 255), bevel_lo=(144, 94, 18, 255), checker_delta=4)

    # Row 1: Velvet & Faceted Royal Gems
    fill_tile(0, 1, (118, 26, 40, 255), bevel_hi=(138, 34, 50, 255), bevel_lo=(92, 18, 30, 255), checker_delta=4)
    fill_tile(1, 1, (196, 38, 58, 255), bevel_hi=(242, 98, 114, 255), bevel_lo=(136, 20, 36, 255), checker_delta=5)
    fill_tile(2, 1, (58, 116, 196, 255), bevel_hi=(128, 184, 246, 255), bevel_lo=(36, 76, 142, 255), checker_delta=5)
    fill_tile(3, 1, (214, 240, 255, 255), bevel_hi=(248, 254, 255, 255), bevel_lo=(158, 204, 238, 255), checker_delta=4)

    # Crisp top-left corner jewel specular glints inside Ruby, Sapphire, and Diamond tiles
    for tx, glint_col in ((1, (250, 128, 144, 255)), (2, (168, 214, 255, 255)), (3, (255, 255, 255, 255))):
        x0, y0 = tx * 32, 32
        for b in (1, 2):
            arr[y0 + b * 4:y0 + (b + 1) * 4, x0 + b * 4:x0 + (b + 1) * 4] = glint_col

    # Row 2: Delicate Translucent Sparkle Glint Rays
    fill_tile(0, 2, (255, 238, 176, 215), bevel_hi=(255, 250, 220, 238), bevel_lo=(238, 204, 112, 190), checker_delta=3)
    fill_tile(1, 2, (232, 247, 255, 215), bevel_hi=(252, 255, 255, 238), bevel_lo=(186, 222, 248, 190), checker_delta=3)

    return Image.fromarray(arr)


# ---------------------------------------------------------------------------
# 2. Cube & Bone Helpers (strict zero cube-rotation, all UVs inside 0..16)
# ---------------------------------------------------------------------------
def _faces(uv_all: tuple, up: tuple | None = None, down: tuple | None = None,
           inner_side: tuple | None = None, inner_dir: str | None = None) -> dict:
    res = {}
    for side in ('north', 'east', 'south', 'west', 'up', 'down'):
        if side == 'up' and up is not None:
            u = up
        elif side == 'down' and down is not None:
            u = down
        elif inner_side is not None and side == inner_dir:
            u = inner_side
        else:
            u = uv_all
        res[side] = {'uv': list(u), 'texture': 0}
    return res


def _cube(name: str, p_from: list, p_to: list, origin: list, faces: dict, shade: bool = True) -> dict:
    low = [round(min(p_from[i], p_to[i]), 4) for i in range(3)]
    high = [round(max(p_from[i], p_to[i]), 4) for i in range(3)]
    return {
        'name': name,
        'box_uv': False,
        'rescale': False,
        'locked': False,
        'light_emission': 0,
        'render_order': 'default',
        'allow_mirror_modeling': True,
        'from': low,
        'to': high,
        'autouv': 0,
        'color': 0,
        'origin': [round(v, 4) for v in origin],
        'rotation': [0.0, 0.0, 0.0],
        'faces': faces,
        'type': 'cube',
        'uuid': uid(f'cube:{name}'),
        'shade': shade,
    }


def _pt(x: float, y: float, z: float) -> list[float]:
    return [round(x, 4), round(y, 4), round(z, 4)]


# Bone origins calibrated to exact Minecraft PlayerRenderer (0.9375 scale):
#   - NECK_ORIG = [0.0, 22.50, 0.0] is the exact vanilla HumanoidModel.head neck pivot
#     (24px * 0.9375 = 22.50 BB = 1.40625m). Using `hi_crown_root` at [0.0, 22.50, 0.0]
#     makes ModelEngine's HeadImpl (inherited=true) rotate the entire crown in full 3D
#     (yaw + pitch) along the exact same head arc as the player's skull!
ROOT_BONE_NAME = 'hi_crown_root'
ROOT_ORIG = [0.0, 22.50, 0.0]
SNEAK_NECK_OFFSET_Y = -2.34  # Crouching neck drop (-5.9375 BB) minus Pose.CROUCHING passenger drop (-3.60 BB)
BODY_ORIG = [0.0, 29.8, 0.0]
GEMS_ORIG = [0.0, 29.8, 0.0]
GLINT_ORIGINS = {
    'glint_n': [0.0,  33.85, -4.05],
    'glint_e': [4.05, 33.45,  0.0],
    'glint_s': [0.0,  33.45,  4.05],
    'glint_w': [-4.05, 33.45, 0.0],
}


# ---------------------------------------------------------------------------
# 3. Subtle Royal Animation (`idle` 3.6s + `sneak` crouch neck-offset loop)
# ---------------------------------------------------------------------------
def eval_crown_pose(u: float) -> dict:
    """Evaluates bone transforms at normalized loop phase u in [0, 1).
    `hi_crown_root` and `crown_body` stay 100% locked (0.00mm / 0.00 deg drift)
    to the player's head, while inset jewels gently gleam and 4 delicate royal
    sparkles twinkle above the spires in the tilted head's local coordinate frame.
    """
    tau = 2.0 * math.pi

    # Subtle jewel gleam pulse (scales radially by only ±1.8% around GEMS_ORIG)
    gem_pulse = 1.0 + 0.018 * math.sin(tau * 2.0 * u)
    gems_scale = [round(gem_pulse, 4), round(1.0 + 0.025 * math.sin(tau * 2.0 * u), 4), round(gem_pulse, 4)]

    # 4 staggered twinkling glint stars above the cardinal spires
    glints = {}
    phases = [
        ('glint_n', 0.08),
        ('glint_e', 0.33),
        ('glint_s', 0.58),
        ('glint_w', 0.83),
    ]
    for gname, center_u in phases:
        # Periodic wrapped distance in [-0.5, 0.5]
        du = (u - center_u + 0.5) % 1.0 - 0.5
        half_win = 0.20
        if abs(du) < half_win:
            w = 0.5 * (1.0 + math.cos(math.pi * du / half_win))  # smooth raised-cosine bell in [0, 1]
            sc = round(1.08 * w, 4)
            dy = round(0.36 * (du / half_win + 1.0) * 0.5, 4)
            ry = round(95.0 * (du / half_win), 3)
        else:
            sc = 0.0
            dy = 0.0
            ry = 0.0
        glints[gname] = {
            'pos': [0.0, dy, 0.0],
            'rot': [0.0, ry, 0.0],
            'scale': [sc, sc, sc],
        }

    return {
        'root_pos': [0.0, 0.0, 0.0],
        'root_rot': [0.0, 0.0, 0.0],
        'gems_scale': gems_scale,
        'glints': glints,
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
    bones = ['crown_gems', 'glint_n', 'glint_e', 'glint_s', 'glint_w']
    kfs = {b: [] for b in bones}
    for s in range(IDLE_STEPS + 1):
        u_eval = 0.0 if s == IDLE_STEPS else (s / IDLE_STEPS)
        t = IDLE_LENGTH * (s / IDLE_STEPS)
        pose = eval_crown_pose(u_eval)

        kfs['crown_gems'].append(_vec_kf('scale', 'idle:crown_gems', t, *pose['gems_scale']))

        for gname in ('glint_n', 'glint_e', 'glint_s', 'glint_w'):
            gp = pose['glints'][gname]
            kfs[gname].append(_vec_kf('position', f'idle:{gname}', t, *gp['pos']))
            kfs[gname].append(_vec_kf('rotation', f'idle:{gname}', t, *gp['rot']))
            kfs[gname].append(_vec_kf('scale', f'idle:{gname}', t, *gp['scale']))

    return {
        uid(f'bone:{b}'): {'name': b, 'type': 'bone', 'keyframes': kfs[b]}
        for b in bones
    }


def build_sneak_animators() -> dict:
    """Shifts `hi_crown_root` neck pivot down by -2.34 BB while crouching (`Shift`)
    so the crown stays flush on the crouched skull as well as standing!
    """
    return {
        uid(f'bone:{ROOT_BONE_NAME}'): {
            'name': ROOT_BONE_NAME,
            'type': 'bone',
            'keyframes': [
                _vec_kf('position', f'sneak:{ROOT_BONE_NAME}', 0.0, 0.0, SNEAK_NECK_OFFSET_Y, 0.0),
                _vec_kf('position', f'sneak:{ROOT_BONE_NAME}', 0.2, 0.0, SNEAK_NECK_OFFSET_Y, 0.0),
            ],
        }
    }


# ---------------------------------------------------------------------------
# 4. Blueprint Builder (`elytrix_royal_crown.bbmodel`)
# ---------------------------------------------------------------------------
def build_blueprint() -> tuple[dict, Image.Image]:
    texture = build_crown_texture()
    raw = io.BytesIO()
    texture.save(raw, format='PNG', optimize=True)

    elements: list[dict] = []

    def add(c: dict) -> str:
        elements.append(c)
        return c['uuid']

    # Exact Head Fit Parameters:
    #   Bare player head = ±3.75, Y = 22.50..30.00
    #   2nd-layer skin hat = ±4.22, Y up to 30.47
    #   Crown inner wall = ±3.82 (hugs bare head skin-tight with 0.07 BB clearance!)
    #   Crown outer wall = ±4.28 (rims ±4.38 — clears 2nd-layer skin hat cleanly!)
    IN_W = 3.82
    OUT_W = 4.28
    RIM_W = 4.38

    band_faces_n = _faces(UV_GOLD_BAND, up=UV_GOLD_RIM, down=UV_GOLD_SHADE, inner_side=UV_GOLD_SHADE, inner_dir='south')
    band_faces_s = _faces(UV_GOLD_BAND, up=UV_GOLD_RIM, down=UV_GOLD_SHADE, inner_side=UV_GOLD_SHADE, inner_dir='north')
    band_faces_w = _faces(UV_GOLD_BAND, up=UV_GOLD_RIM, down=UV_GOLD_SHADE, inner_side=UV_GOLD_SHADE, inner_dir='east')
    band_faces_e = _faces(UV_GOLD_BAND, up=UV_GOLD_RIM, down=UV_GOLD_SHADE, inner_side=UV_GOLD_SHADE, inner_dir='west')
    rim_faces = _faces(UV_GOLD_RIM, up=UV_GOLD_SPECULAR, down=UV_GOLD_SHADE)
    peak_faces = _faces(UV_GOLD_RIM, up=UV_GOLD_SPECULAR, down=UV_GOLD_SHADE)
    pearl_faces = _faces(UV_GOLD_SPECULAR, down=UV_GOLD_RIM)
    velvet_faces = _faces(UV_VELVET_CRIMSON, down=UV_VELVET_CRIMSON)

    body_uuids: list[str] = [
        # A) Royal Crimson Velvet Cushion Cap resting right on head top Y = 30.02..30.76!
        add(_cube('velvet_cap_base', _pt(-3.80, 30.02, -3.80), _pt(3.80, 30.48, 3.80), BODY_ORIG, velvet_faces)),
        add(_cube('velvet_cap_dome', _pt(-2.65, 30.48, -2.65), _pt(2.65, 30.76, 2.65), BODY_ORIG, velvet_faces)),

        # B) Lower Burnished Gold Molding Rim (Y = 28.55 .. 28.95 — wraps down onto forehead/temples!)
        add(_cube('rim_low_n', _pt(-RIM_W, 28.55, -RIM_W), _pt(RIM_W,  28.95, -IN_W),  BODY_ORIG, rim_faces)),
        add(_cube('rim_low_s', _pt(-RIM_W, 28.55,  IN_W),  _pt(RIM_W,  28.95,  RIM_W), BODY_ORIG, rim_faces)),
        add(_cube('rim_low_w', _pt(-RIM_W, 28.55, -IN_W),  _pt(-IN_W,  28.95,  IN_W),  BODY_ORIG, rim_faces)),
        add(_cube('rim_low_e', _pt(IN_W,   28.55, -IN_W),  _pt(RIM_W,  28.95,  IN_W),  BODY_ORIG, rim_faces)),

        # C) Main Brushed Royal Gold Circlet Band (Y = 28.95 .. 30.65)
        add(_cube('band_n', _pt(-OUT_W, 28.95, -OUT_W), _pt(OUT_W,  30.65, -IN_W),  BODY_ORIG, band_faces_n)),
        add(_cube('band_s', _pt(-OUT_W, 28.95,  IN_W),  _pt(OUT_W,  30.65,  OUT_W), BODY_ORIG, band_faces_s)),
        add(_cube('band_w', _pt(-OUT_W, 28.95, -IN_W),  _pt(-IN_W,  30.65,  IN_W),  BODY_ORIG, band_faces_w)),
        add(_cube('band_e', _pt(IN_W,   28.95, -IN_W),  _pt(OUT_W,  30.65,  IN_W),  BODY_ORIG, band_faces_e)),

        # D) Upper Filigree Gold Molding Rim (Y = 30.65 .. 30.98)
        add(_cube('rim_top_n', _pt(-RIM_W, 30.65, -RIM_W), _pt(RIM_W,  30.98, -IN_W),  BODY_ORIG, rim_faces)),
        add(_cube('rim_top_s', _pt(-RIM_W, 30.65,  IN_W),  _pt(RIM_W,  30.98,  RIM_W), BODY_ORIG, rim_faces)),
        add(_cube('rim_top_w', _pt(-RIM_W, 30.65, -IN_W),  _pt(-IN_W,  30.98,  IN_W),  BODY_ORIG, rim_faces)),
        add(_cube('rim_top_e', _pt(IN_W,   30.65, -IN_W),  _pt(RIM_W,  30.98,  IN_W),  BODY_ORIG, rim_faces)),

        # E) Front Sovereign Fleur-de-Lis Peak (North, -Z: tallest flagship spire Y = 30.98 .. 33.48)
        add(_cube('peak_n_1',     _pt(-1.42, 30.98, -4.30), _pt(1.42, 31.68, -3.82), BODY_ORIG, peak_faces)),
        add(_cube('peak_n_2',     _pt(-0.94, 31.68, -4.28), _pt(0.94, 32.35, -3.84), BODY_ORIG, peak_faces)),
        add(_cube('peak_n_wings', _pt(-1.24, 31.88, -4.26), _pt(1.24, 32.22, -3.88), BODY_ORIG, pearl_faces)),
        add(_cube('peak_n_3',     _pt(-0.48, 32.35, -4.26), _pt(0.48, 32.98, -3.86), BODY_ORIG, peak_faces)),
        add(_cube('peak_n_pearl', _pt(-0.32, 32.98, -4.26), _pt(0.32, 33.48, -3.84), BODY_ORIG, pearl_faces)),

        # F) Back Cardinal Peak (South, +Z: Y = 30.98 .. 33.08)
        add(_cube('peak_s_1',     _pt(-1.25, 30.98, 3.82),  _pt(1.25, 31.58, 4.30),  BODY_ORIG, peak_faces)),
        add(_cube('peak_s_2',     _pt(-0.82, 31.58, 3.84),  _pt(0.82, 32.18, 4.28),  BODY_ORIG, peak_faces)),
        add(_cube('peak_s_3',     _pt(-0.44, 32.18, 3.86),  _pt(0.44, 32.68, 4.26),  BODY_ORIG, peak_faces)),
        add(_cube('peak_s_pearl', _pt(-0.28, 32.68, 3.84),  _pt(0.28, 33.08, 4.26),  BODY_ORIG, pearl_faces)),

        # G) Left & Right Cardinal Peaks (West -X & East +X: Y = 30.98 .. 33.08)
        add(_cube('peak_w_1',     _pt(-4.30, 30.98, -1.25), _pt(-3.82, 31.58, 1.25), BODY_ORIG, peak_faces)),
        add(_cube('peak_w_2',     _pt(-4.28, 31.58, -0.82), _pt(-3.84, 32.18, 0.82), BODY_ORIG, peak_faces)),
        add(_cube('peak_w_3',     _pt(-4.26, 32.18, -0.44), _pt(-3.86, 32.68, 0.44), BODY_ORIG, peak_faces)),
        add(_cube('peak_w_pearl', _pt(-4.26, 32.68, -0.28), _pt(-3.84, 33.08, 0.28), BODY_ORIG, pearl_faces)),

        add(_cube('peak_e_1',     _pt(3.82,  30.98, -1.25), _pt(4.30,  31.58, 1.25), BODY_ORIG, peak_faces)),
        add(_cube('peak_e_2',     _pt(3.84,  31.58, -0.82), _pt(4.28,  32.18, 0.82), BODY_ORIG, peak_faces)),
        add(_cube('peak_e_3',     _pt(3.86,  32.18, -0.44), _pt(4.26,  32.68, 0.44), BODY_ORIG, peak_faces)),
        add(_cube('peak_e_pearl', _pt(3.84,  32.68, -0.28), _pt(4.26,  33.08, 0.28), BODY_ORIG, pearl_faces)),

        # H) 4 Corner Spires (NW, NE, SW, SE: Y = 30.98 .. 32.22)
        add(_cube('peak_nw_1', _pt(-4.32, 30.98, -4.32), _pt(-3.30, 31.55, -3.82), BODY_ORIG, peak_faces)),
        add(_cube('peak_nw_2', _pt(-4.32, 30.98, -3.82), _pt(-3.82, 31.55, -3.30), BODY_ORIG, peak_faces)),
        add(_cube('peak_nw_p', _pt(-4.28, 31.55, -4.28), _pt(-3.78, 32.22, -3.78), BODY_ORIG, pearl_faces)),

        add(_cube('peak_ne_1', _pt(3.30,  30.98, -4.32), _pt(4.32,  31.55, -3.82), BODY_ORIG, peak_faces)),
        add(_cube('peak_ne_2', _pt(3.82,  30.98, -3.82), _pt(4.32,  31.55, -3.30), BODY_ORIG, peak_faces)),
        add(_cube('peak_ne_p', _pt(3.78,  31.55, -4.28), _pt(4.28,  32.22, -3.78), BODY_ORIG, pearl_faces)),

        add(_cube('peak_sw_1', _pt(-4.32, 30.98,  3.82), _pt(-3.30, 31.55,  4.32), BODY_ORIG, peak_faces)),
        add(_cube('peak_sw_2', _pt(-4.32, 30.98,  3.30), _pt(-3.82, 31.55,  3.82), BODY_ORIG, peak_faces)),
        add(_cube('peak_sw_p', _pt(-4.28, 31.55,  3.78), _pt(-3.78, 32.22,  4.28), BODY_ORIG, pearl_faces)),

        add(_cube('peak_se_1', _pt(3.30,  30.98,  3.82), _pt(4.32,  31.55,  4.32), BODY_ORIG, peak_faces)),
        add(_cube('peak_se_2', _pt(3.82,  30.98,  3.30), _pt(4.32,  31.55,  3.82), BODY_ORIG, peak_faces)),
        add(_cube('peak_se_p', _pt(3.78,  31.55,  3.78), _pt(4.28,  32.22,  4.28), BODY_ORIG, pearl_faces)),
    ]

    # I) 3D Faceted Jewels (`crown_gems` bone — gently gleams in `idle`)
    ruby_faces = _faces(UV_RUBY_FACET)
    sapphire_faces = _faces(UV_SAPPHIRE_FACET)
    diamond_faces = _faces(UV_DIAMOND_FACET)
    gems_uuids: list[str] = [
        # Front sovereign centerpiece Ruby + inner ruby crown facet
        add(_cube('gem_front_ruby_base', _pt(-0.62, 29.22, -4.48), _pt(0.62,  30.40, -4.26), GEMS_ORIG, ruby_faces, shade=False)),
        add(_cube('gem_front_ruby_top',  _pt(-0.36, 29.46, -4.56), _pt(0.36,  30.16, -4.46), GEMS_ORIG, ruby_faces, shade=False)),
        add(_cube('gem_peak_n_diamond',  _pt(-0.28, 31.22, -4.42), _pt(0.28,  31.82, -4.26), GEMS_ORIG, diamond_faces, shade=False)),
        # Flanking front Ice-Diamonds
        add(_cube('gem_front_dia_l',     _pt(-2.55, 29.42, -4.45), _pt(-1.90, 30.18, -4.26), GEMS_ORIG, diamond_faces, shade=False)),
        add(_cube('gem_front_dia_r',     _pt(1.90,  29.42, -4.45), _pt(2.55,  30.18, -4.26), GEMS_ORIG, diamond_faces, shade=False)),
        # Left & Right Royal Sapphires
        add(_cube('gem_west_sapphire',   _pt(-4.48, 29.32, -0.52), _pt(-4.26, 30.30,  0.52), GEMS_ORIG, sapphire_faces, shade=False)),
        add(_cube('gem_east_sapphire',   _pt(4.26,  29.32, -0.52), _pt(4.48,  30.30,  0.52), GEMS_ORIG, sapphire_faces, shade=False)),
        # Back Royal Ruby
        add(_cube('gem_south_ruby',      _pt(-0.52, 29.32,  4.26), _pt(0.52,  30.30,  4.48), GEMS_ORIG, ruby_faces, shade=False)),
    ]

    # J) 4 Delicate Twinkling Royal Glint Stars (`glint_n`, `glint_e`, `glint_s`, `glint_w`)
    glint_bones = []
    for gname, gorig in GLINT_ORIGINS.items():
        gx, gy, gz = gorig
        g_faces_gold = _faces(UV_GLINT_GOLD)
        g_faces_ice = _faces(UV_GLINT_ICE)
        c_vert = add(_cube(f'{gname}_v', _pt(gx - 0.06, gy - 0.34, gz - 0.06), _pt(gx + 0.06, gy + 0.34, gz + 0.06), gorig, g_faces_ice, shade=False))
        c_horz = add(_cube(f'{gname}_x', _pt(gx - 0.30, gy - 0.06, gz - 0.06), _pt(gx + 0.30, gy + 0.06, gz + 0.06), gorig, g_faces_gold, shade=False))
        c_z    = add(_cube(f'{gname}_z', _pt(gx - 0.06, gy - 0.06, gz - 0.30), _pt(gx + 0.06, gy + 0.06, gz + 0.30), gorig, g_faces_gold, shade=False))
        glint_bones.append({
            'name': gname,
            'origin': gorig,
            'color': 0,
            'uuid': uid(f'bone:{gname}'),
            'export': True,
            'mirror_uv': False,
            'isOpen': True,
            'locked': False,
            'visibility': True,
            'autouv': 0,
            'children': [c_vert, c_horz, c_z],
        })

    def bone(name: str, orig: list, children: list) -> dict:
        return {
            'name': name,
            'origin': [round(v, 4) for v in orig],
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
        bone(ROOT_BONE_NAME, ROOT_ORIG, [
            bone('crown_body', BODY_ORIG, body_uuids),
            bone('crown_gems', GEMS_ORIG, gems_uuids),
            *glint_bones,
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
            'uuid': uid('tex:0'),
            'source': 'data:image/png;base64,' + base64.b64encode(raw.getvalue()).decode('ascii'),
        }],
        'animations': [
            {
                'uuid': uid('anim:idle'),
                'name': 'idle',
                'loop': 'loop',
                'override': False,
                'length': IDLE_LENGTH,
                'snapping': 20,
                'selected': True,
                'saved': True,
                'path': '',
                'anim_time_update': '',
                'blend_weight': '',
                'start_delay': '',
                'loop_delay': '',
                'animators': build_idle_animators(),
            },
            {
                'uuid': uid('anim:sneak'),
                'name': 'sneak',
                'loop': 'loop',
                'override': False,
                'length': 0.2,
                'snapping': 20,
                'selected': False,
                'saved': True,
                'path': '',
                'anim_time_update': '',
                'blend_weight': '',
                'start_delay': '',
                'loop_delay': '',
                'animators': build_sneak_animators(),
            },
        ],
    }
    return blueprint, texture


# ---------------------------------------------------------------------------
# 5. Hand-Crafted 32x32 Pixel-Art Menu Icon (`reallyworld:crown_icon`)
# ---------------------------------------------------------------------------
def build_crown_icon() -> Image.Image:
    """Draws a crisp 32x32 pixel-art Royal Crown icon with crimson velvet interior,
    gold bevels, center ruby, side diamonds/sapphires, pearl finials, and sparkle glints.
    """
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    outline    = (34, 28, 36, 255)
    gold_dark  = (176, 118, 24, 255)
    gold_mid   = (226, 168, 46, 255)
    gold_hi    = (248, 206, 88, 255)
    gold_spec  = (255, 242, 178, 255)
    velvet_dk  = (104, 20, 34, 255)
    velvet_hi  = (138, 32, 48, 255)
    ruby_dk    = (148, 22, 40, 255)
    ruby_hi    = (232, 62, 82, 255)
    ruby_glint = (255, 190, 200, 255)
    dia_mid    = (156, 214, 250, 255)
    dia_hi     = (244, 252, 255, 255)

    def put(x: int, y: int, c: tuple):
        if 0 <= x < 32 and 0 <= y < 32:
            px[x, y] = c

    def rect(x0: int, y0: int, x1: int, y1: int, c: tuple):
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                put(xx, yy, c)

    # 1. Crimson velvet dome peeking inside the crown (x=8..23, y=13..17)
    rect(8, 14, 23, 18, velvet_dk)
    rect(10, 13, 21, 15, velvet_hi)

    # 2. Five classic royal golden spires rising from the band (left, mid-left, tall center, mid-right, right)
    # Left outer spire
    rect(5, 12, 7, 18, gold_mid)
    rect(5, 10, 6, 12, gold_hi)
    # Mid-left spire
    rect(9, 13, 12, 18, gold_mid)
    rect(10, 10, 11, 13, gold_hi)
    # Tall center sovereign spire
    rect(14, 11, 17, 18, gold_mid)
    rect(14, 8,  17, 11, gold_hi)
    rect(15, 7,  16, 8,  gold_spec)
    # Mid-right spire
    rect(19, 13, 22, 18, gold_mid)
    rect(20, 10, 21, 13, gold_hi)
    # Right outer spire
    rect(24, 12, 26, 18, gold_dark)
    rect(25, 10, 26, 12, gold_mid)

    # Pearl finials on top of the 5 spires
    for cx, cy in ((5, 8), (10, 8), (15, 5), (20, 8), (25, 8)):
        rect(cx, cy, cx + 1, cy + 1, gold_spec)
        put(cx + 1, cy + 1, gold_hi)

    # 3. Main jewelled golden circlet band (x=5..26, y=17..23) + lower & upper rims
    rect(4, 17, 27, 18, gold_hi)       # upper gold rim
    rect(5, 19, 26, 22, gold_mid)      # main band
    for yy in range(19, 23):
        put(5, yy, gold_hi)
        put(6, yy, gold_hi)
        put(25, yy, gold_dark)
        put(26, yy, gold_dark)
    rect(4, 23, 27, 24, gold_dark)     # lower gold rim
    rect(5, 23, 20, 23, gold_hi)       # crisp rim highlight

    # 4. Faceted Center Ruby (x=14..17, y=19..22) + Flanking Ice-Diamonds (x=8..10, x=21..23)
    rect(14, 19, 17, 22, ruby_dk)
    rect(14, 19, 16, 21, ruby_hi)
    put(15, 19, ruby_glint)

    for dx in (8, 21):
        rect(dx, 20, dx + 2, 21, dia_mid)
        put(dx, 20, dia_hi)
        put(dx + 1, 20, dia_hi)

    # 5. Clean 1px 4-connected dark pixel-art outline around the entire crown
    mask = [[px[x, y][3] > 0 for y in range(32)] for x in range(32)]
    for y in range(32):
        for x in range(32):
            if mask[x][y]:
                continue
            if any(0 <= x + dx < 32 and 0 <= y + dy < 32 and mask[x + dx][y + dy]
                   for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                put(x, y, outline)

    # 6. Two crisp subtle royal glint stars above the crown (no heavy outline so they look airy!)
    for gx, gy in ((6, 4), (24, 4)):
        put(gx, gy, gold_spec)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            put(gx + dx, gy + dy, (255, 244, 196, 200))

    return img


# ---------------------------------------------------------------------------
# 6. Multi-Angle Preview Renderer (`crown_hat_preview.png`)
# ---------------------------------------------------------------------------
def render_preview(blueprint: dict, texture: Image.Image, icon: Image.Image, out_path: Path):
    panel_w, panel_h = 240, 300
    canvas = Image.new('RGBA', (panel_w * 4 + 210, panel_h), (24, 28, 38, 255))

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
    by_name = {el['name']: el for el in blueprint['elements']}

    # (u, cam_yaw, cam_pitch, head_pitch_deg, label)
    # head_pitch_deg matches Bukkit Location.getPitch(): negative = looking UP, positive = looking DOWN!
    stages = [
        (0.08, -32.0, -10.0, -48.0, 'PITCH -48° (UP)'),     # 1. Looking UP (-48 deg): crown swings back & up on skull!
        (0.08,  24.0, -12.0,   0.0, 'PITCH 0° (LEVEL)'),    # 2. Looking LEVEL (0 deg): flush on forehead & temples!
        (0.33, -32.0, -14.0, +48.0, 'PITCH +48° (DOWN)'),   # 3. Looking DOWN (+48 deg): crown swings forward & down!
        (0.58, -68.0,  -8.0, +72.0, 'PITCH +72° (STEEP)'),  # 4. Steep DOWN (+72 deg) side view: 0.00mm detachment!
    ]

    for idx, (u, cam_yaw, cam_pitch, head_pitch_deg, label) in enumerate(stages):
        bg = (196, 186, 152, 255) if idx == 1 else (32, 38, 52, 255)
        panel = Image.new('RGBA', (panel_w, panel_h), bg)
        pose = eval_crown_pose(u)

        ay = math.radians(cam_yaw)
        ap = math.radians(cam_pitch)
        cy_m, sy_m = math.cos(ay), math.sin(ay)
        cp_m, sp_m = math.cos(ap), math.sin(ap)

        scale_px = 14.5
        center_y_world = 26.8
        center_y_px = 172.0

        def proj(pt):
            dx, dy, dz = pt[0], pt[1] - center_y_world, pt[2]
            xw = dx * cy_m - dz * sy_m
            z1 = dx * sy_m + dz * cy_m
            yw = dy * cp_m - z1 * sp_m
            zw = dy * sp_m + z1 * cp_m
            return (panel_w * 0.5 - xw * scale_px, center_y_px - yw * scale_px, zw)

        def bone_tf(parent_tf, orig, pos, rot, scale):
            o = np.array(orig)
            t = np.array(pos)
            m = rot_mat(*rot)
            sc = np.array(scale)
            return lambda p: parent_tf(o + t + m @ (sc * (p - o)))

        # In Blockbench coords (-Z = front), Bukkit +pitch (looking down) = -rx rotation around NECK [0, 22.50, 0]!
        head_rx_bb = -head_pitch_deg
        tf_neck = bone_tf(lambda p: p, ROOT_ORIG, [0.0, 0.0, 0.0], [head_rx_bb, 0.0, 0.0], [1.0, 1.0, 1.0])

        faces_to_draw = []

        # 1) Stationary torso/shoulders below neck Y = 22.50
        torso_boxes = [
            ([-7.5, 16.5, -1.875], [7.5, 22.5, 1.875], (56, 64, 82), lambda p: p),
        ]
        # 2) Pitching player head + front eyes rotating around exact neck joint [0.0, 22.50, 0.0]!
        head_boxes = [
            ([-3.75, 22.5, -3.75], [3.75, 30.0, 3.75], (96, 108, 132), tf_neck),
            ([-2.70, 25.2, -3.79], [-1.05, 26.2, -3.74], (235, 242, 255), tf_neck),
            ([1.05,  25.2, -3.79], [2.70,  26.2, -3.74], (235, 242, 255), tf_neck),
        ]
        for low, high, base_rgb, box_tf in torso_boxes + head_boxes:
            cs = [
                box_tf(np.array([low[0], low[1], low[2]])), box_tf(np.array([high[0], low[1], low[2]])),
                box_tf(np.array([high[0], high[1], low[2]])), box_tf(np.array([low[0], high[1], low[2]])),
                box_tf(np.array([low[0], low[1], high[2]])), box_tf(np.array([high[0], low[1], high[2]])),
                box_tf(np.array([high[0], high[1], high[2]])), box_tf(np.array([low[0], high[1], high[2]])),
            ]
            for idxs, sm in (((2, 1, 0, 3), 1.0), ((7, 4, 5, 6), 0.86), ((6, 5, 1, 2), 0.92), ((3, 0, 4, 7), 0.90), ((7, 6, 2, 3), 1.05), ((0, 1, 5, 4), 0.82)):
                p2d = [proj(cs[k]) for k in idxs]
                cross = (p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1]) - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0])
                if cross <= 0:
                    col = tuple(min(255, int(c * sm)) for c in base_rgb) + (255,)
                    z_avg = sum(p[2] for p in p2d) / 4.0
                    if base_rgb[0] > 200:
                        z_avg -= 0.25
                    faces_to_draw.append((z_avg, [(s[0], s[1]) for s in p2d], col, (42, 48, 64, 255) if base_rgb[0] < 200 else None))

        tf_root = bone_tf(tf_neck, ROOT_ORIG, pose['root_pos'], pose['root_rot'], [1.0, 1.0, 1.0])
        tf_body = bone_tf(tf_root, BODY_ORIG, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1.0, 1.0, 1.0])
        tf_gems = bone_tf(tf_root, GEMS_ORIG, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], pose['gems_scale'])
        tf_glints = {
            gname: bone_tf(tf_root, GLINT_ORIGINS[gname], pose['glints'][gname]['pos'], pose['glints'][gname]['rot'], pose['glints'][gname]['scale'])
            for gname in ('glint_n', 'glint_e', 'glint_s', 'glint_w')
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
            if np.linalg.norm(wcs[6] - wcs[0]) < 0.03:
                return
            quads = [
                ('north', (2, 1, 0, 3), 1.00),
                ('south', (7, 4, 5, 6), 0.92),
                ('east',  (6, 5, 1, 2), 0.95),
                ('west',  (3, 0, 4, 7), 0.94),
                ('up',    (7, 6, 2, 3), 1.05),
                ('down',  (0, 1, 5, 4), 0.86),
            ]
            for fname, idxs, sm in quads:
                pts3 = [wcs[k] for k in idxs]
                p2d = [proj(p) for p in pts3]
                cross = (p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1]) - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0])
                if cross > 0:
                    continue
                z_avg = sum(p[2] for p in p2d) / 4.0
                if cname.startswith('gem_'):
                    z_avg -= 0.65
                uv = el['faces'][fname]['uv']
                tx = min(127, int(0.5 * (uv[0] + uv[2]) * 8))
                ty = min(127, int(0.5 * (uv[1] + uv[3]) * 8))
                rgba = tex_arr[ty, tx]
                if rgba[3] < 16:
                    continue
                col = tuple(min(255, int(c * sm)) for c in rgba[:3]) + (int(rgba[3]),)
                faces_to_draw.append((z_avg, [(s[0], s[1]) for s in p2d], col, None))

        for name in by_name:
            if name.startswith('gem_'):
                add_cube(name, tf_gems)
            elif name.startswith('glint_'):
                gprefix = '_'.join(name.split('_')[:2])
                add_cube(name, tf_glints[gprefix])
            else:
                add_cube(name, tf_body)

        faces_to_draw.sort(key=lambda item: item[0], reverse=True)
        for _, poly, col, outline in faces_to_draw:
            layer = Image.new('RGBA', (panel_w, panel_h), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer, 'RGBA')
            ld.polygon(poly, fill=col, outline=outline)
            panel.alpha_composite(layer)

        canvas.paste(panel, (idx * panel_w, 0))
        d = ImageDraw.Draw(canvas)
        d.line([(idx * panel_w, 0), (idx * panel_w, panel_h)], fill=(62, 70, 88, 255), width=1)

    icon_big = icon.resize((128, 128), Image.NEAREST)
    canvas.alpha_composite(icon_big, (panel_w * 4 + 41, 24))
    tex_small = texture.resize((112, 112), Image.NEAREST)
    canvas.alpha_composite(tex_small, (panel_w * 4 + 49, 170))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bbmodel-out', type=Path, default=ROOT / 'plugins/ModelEngine/blueprints' / f'{MODEL}.bbmodel')
    parser.add_argument('--assets-dir', type=Path, default=HERE / 'assets')
    parser.add_argument('--preview', type=Path, default=None)
    args = parser.parse_args()

    blueprint, texture = build_blueprint()
    args.bbmodel_out.parent.mkdir(parents=True, exist_ok=True)
    args.bbmodel_out.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding='utf-8')

    icon = build_crown_icon()
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

    print(f'Built {MODEL}.bbmodel: {len(blueprint["elements"])} cubes, {len(blueprint["animations"])} animation, icon -> {args.assets_dir}')


if __name__ == '__main__':
    main()
