#!/usr/bin/env python3
"""Procedurally builds the 3D Satanic Pentagram Halo (`elytrix_satan_circle`),
its 32x32 pixel-art menu icon (`reallyworld:satan_circle_icon`), and a multi-angle
verification preview strip.

100% pure procedural Python + Pillow + NumPy — zero AI generation:
  1. Visual Design (faithful 3D translation of the cracked crimson-obsidian pentagram):
       - 16-segment smooth 3D double ring (`circle_ring`, R = 5.65..6.32, using legal
         Minecraft JSON cube angles 0, ±22.5, ±45 deg just like `elytrix_angel_halo`)
         forged from dark charred obsidian + glowing cracked blood-crimson magma rims.
       - 5 razor-straight 3D interlaced pentagram star chords (`beam_0 .. beam_4`,
         zero staircasing — each chord is an exact axis-aligned 3D obsidian-and-crimson
         beam rotated by ModelEngine bone quaternions at 0, 72, 144, 216, 288 deg!).
       - Central 3D crimson Ankh / Cross emblem suspended inside the inner pentagon,
         plus 5 miniature 3D crimson occult sigil charms (Inverted Cross, Crescent & Star,
         Hexagram, Occult Flame/Om, Iron Cross) orbiting outside the ring at 72 deg intervals!
       - Counter-rotating dark-crimson ember aura (`satan_aura`, 0 -> -360 deg) mirroring
         `halo_aura` in `elytrix_angel_halo`.
  2. Halo Motion (`крутится как нимб вокруг головы`, seamless 6.4s loop @ 20 TPS):
       - Positioned right above & framing the player's head (`Y = 31.85`, bare head top = `30.00`,
         `R = 6.0`..`7.45` < `1.85m` from 1st-person eye -> 100% hidden in 1st-person!).
       - Spins a full seamless `0 -> 360 deg` around the head while gently floating (`±0.20` BB)
         with a subtle `6.0 deg` gyroscopic halo precession so the 5-pointed star & central Ankh
         are clearly readable from horizontal `F5` AND from above without ever touching the head!
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
MODEL = 'elytrix_satan_circle'
ICON = 'satan_circle_icon'

IDLE_LEN = 6.4      # 128 ticks @ 20 TPS — smooth, hypnotic 360-deg halo rotation
IDLE_STEPS = 128


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f'elytrix.satan_circle.v1:{tag}'))


def _pt(x: float, y: float, z: float) -> list[float]:
    return [round(float(x), 4), round(float(y), 4), round(float(z), 4)]


# ---------------------------------------------------------------------------
# 1. Cracked Volcanic Obsidian & Blood-Crimson Magma Texture (128x128, UV 16x16)
# ---------------------------------------------------------------------------
UV_OBSIDIAN_CRACKED = (0.25, 0.25, 3.75, 3.75)   # Charred black-red obsidian crisscrossed by glowing crimson cracks
UV_CRIMSON_RIM      = (4.25, 0.25, 7.75, 3.75)   # Intense blood-crimson glowing bevel rim
UV_MAGMA_CORE       = (8.25, 0.25, 11.75, 3.75)  # Bright molten scarlet-ember fissure / rune glow
UV_DARK_IRON        = (12.25, 0.25, 15.75, 3.75) # Deep charred abyssal iron underside / side shade

UV_STAR_BEAM_TOP    = (0.25, 4.25, 7.75, 5.75)   # Elongated cracked obsidian + central crimson magma vein for star chords
UV_STAR_BEAM_SIDE   = (8.25, 4.25, 15.75, 5.75)  # Glowing blood-red bevel side of star chords
UV_SIGIL_RUBY       = (0.25, 8.25, 3.75, 11.75)  # Crisp glowing blood-ruby rune & Ankh core
UV_AURA_EMBER       = (4.25, 8.25, 7.75, 11.75)  # Translucent dark-crimson ritual aura mist


def build_satan_texture() -> Image.Image:
    """Builds a crisp 128x128 pixel-art texture matching the cracked crimson-black pentagram aesthetic."""
    arr = np.zeros((128, 128, 4), dtype=np.uint8)

    # Tile (0,0) [0..32, 0..32]: Charred obsidian with procedural branching blood-magma cracks
    for py in range(32):
        for px in range(32):
            bx, by = px // 2, py // 2
            # Deterministic volcanic crack network
            v1 = abs(((bx * 3 + by * 5) % 13) - 6)
            v2 = abs(((bx * 7 - by * 4) % 17) - 8)
            edge = min(bx, by, 15 - bx, 15 - by)
            if edge == 0:
                col = (196, 22, 32, 255)
            elif v1 == 0 and v2 <= 3:
                col = (250, 64, 52, 255)   # bright molten crack intersection
            elif v1 == 0 or v2 == 0:
                col = (182, 20, 30, 255)   # deep blood crack
            elif v1 == 1:
                col = (84, 10, 16, 255)    # warm crack halo
            else:
                d = 4 if ((bx + by) % 2 == 0) else 0
                col = (22 + d, 6 + d // 2, 9 + d // 2, 255)
            arr[py, px] = col

    # Tile (1,0) [32..64, 0..32]: Intense Blood-Crimson Bevel Rim
    for py in range(32):
        for px in range(32):
            bx, by = px // 2, py // 2
            crack = ((bx * 5 + by * 3) % 11 == 0)
            edge = min(bx, by, 15 - bx, 15 - by)
            if crack:
                col = (255, 82, 66, 255)
            elif edge == 0:
                col = (128, 12, 20, 255)
            elif edge == 1:
                col = (232, 36, 44, 255)
            else:
                d = 8 if ((bx + by) % 2 == 0) else -6
                col = (192 + d, 22 + max(0, d // 2), 32 + max(0, d // 2), 255)
            arr[py, 32 + px] = col

    # Tile (2,0) [64..96, 0..32]: Bright Molten Scarlet-Ember Core
    for py in range(32):
        for px in range(32):
            bx, by = px // 2, py // 2
            dist = max(abs(bx - 7.5), abs(by - 7.5))
            if dist <= 2.5:
                col = (255, 116, 86, 255)
            elif dist <= 5.0:
                col = (242, 48, 48, 255)
            else:
                col = (188, 22, 32, 255)
            arr[py, 64 + px] = col

    # Tile (3,0) [96..128, 0..32]: Deep Charred Obsidian-Iron Shade
    for py in range(32):
        for px in range(32):
            bx, by = px // 2, py // 2
            vein = ((bx * 3 + by * 7) % 15 == 0)
            col = (112, 14, 22, 255) if vein else (28 + (bx + by) % 2 * 4, 8, 12, 255)
            arr[py, 96 + px] = col

    # Strip [0..64, 32..48]: Star Beam Top/Bottom — bright blood-crimson pentagram bar with a
    # near-black outline (so the 5-pointed star reads on ANY background) and a glowing magma vein!
    for py in range(16):
        for px in range(64):
            by = py // 2      # 0..7 across beam width
            bx = px // 2      # 0..31 along beam length
            if by in (0, 7):
                col = (44, 6, 10, 255)     # near-black outline
            elif by in (1, 6):
                col = (238, 44, 52, 255)   # bright blood-crimson edge
            elif by in (2, 5):
                col = (206, 26, 36, 255)   # crimson body
            elif (bx % 6) in (0, 1):
                col = (252, 92, 68, 255)   # glowing magma vein running along the chord
            else:
                col = (150, 16, 26, 255)   # deep crimson core
            arr[32 + py, px] = col

    # Strip [64..128, 32..48]: Star Beam Side Bevel
    for py in range(16):
        for px in range(64):
            by = py // 2
            bx = px // 2
            if by in (0, 7):
                col = (232, 38, 46, 255)
            elif (bx + by) % 7 == 0:
                col = (248, 68, 56, 255)
            else:
                col = (138, 16, 24, 255)
            arr[32 + py, 64 + px] = col

    # Tile [0..32, 64..96]: Crisp Glowing Blood-Ruby Sigil Tile (for Ankh & 5 outer occult symbols)
    for py in range(32):
        for px in range(32):
            bx, by = px // 2, py // 2
            edge = min(bx, by, 15 - bx, 15 - by)
            if edge == 0:
                col = (146, 14, 24, 255)
            elif (bx * 3 + by * 5) % 8 == 0:
                col = (255, 96, 76, 255)
            else:
                col = (222, 30, 40, 255)
            arr[64 + py, px] = col

    # Tile [32..64, 64..96]: Translucent Dark-Crimson Ritual Aura Mist
    for py in range(32):
        for px in range(32):
            bx, by = px // 2, py // 2
            spark = ((bx * 7 + by * 5) % 13 == 0)
            col = (244, 54, 52, 188) if spark else (156, 16, 26, 132)
            arr[64 + py, 32 + px] = col

    return Image.fromarray(arr)


# ---------------------------------------------------------------------------
# 2. Cube & 16-Gon Smooth Halo Ring Helpers
# ---------------------------------------------------------------------------
def _faces(default_uv: tuple, **overrides) -> dict:
    out = {}
    for side in ('north', 'east', 'south', 'west', 'up', 'down'):
        u = overrides.get(side, default_uv)
        out[side] = {'uv': list(u), 'texture': 0}
    return out


def _cube(name: str, p_from: list[float], p_to: list[float], origin: list[float],
          faces: dict, rot_y: float = 0.0) -> dict:
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
        'rotation': [0.0, round(float(rot_y), 4), 0.0],
        'faces': faces,
        'type': 'cube',
        'uuid': uid(f'cube:{name}'),
        'shade': False,
    }


def _ring_16_segments(prefix: str, radius: float, half_radial: float,
                      y0: float, y1: float, faces: dict, overlap: float = 1.06) -> list[dict]:
    """Builds a gapless 16-sided circular ring using ONLY Minecraft's 5 legal
    single-axis angles {-45.0, -22.5, 0.0, +22.5, +45.0} — exact same proven
    technique as `elytrix_angel_halo`!
    """
    half_chord = radius * math.tan(math.pi / 16.0) * overlap
    segs = []
    for k in range(16):
        theta_deg = k * 22.5
        theta = math.radians(theta_deg)
        cx = radius * math.sin(theta)
        cz = radius * math.cos(theta)

        # Map any k * 22.5 deg tangent into either X-major or Z-major box + rot_y in {-45, -22.5, 0, 22.5, 45}!
        mod4 = k % 4
        quad = (k // 4) % 2  # 0 around Z-poles (N/S), 1 around X-poles (E/W)
        if quad == 0:
            if mod4 == 0:
                hx, hz, ry = half_chord, half_radial, 0.0
            elif mod4 == 1:
                hx, hz, ry = half_chord, half_radial, 22.5
            elif mod4 == 2:
                hx, hz, ry = half_chord, half_radial, 45.0
            else:  # mod4 == 3 -> 67.5 deg = 90 - 22.5 -> Z-major rotated -22.5!
                hx, hz, ry = half_radial, half_chord, -22.5
        else:
            if mod4 == 0:  # 90 / 270 deg -> Z-major, 0 deg
                hx, hz, ry = half_radial, half_chord, 0.0
            elif mod4 == 1:  # 112.5 / 292.5 deg -> Z-major rotated +22.5!
                hx, hz, ry = half_radial, half_chord, 22.5
            elif mod4 == 2:  # 135 / 315 deg -> X-major rotated -45!
                hx, hz, ry = half_chord, half_radial, -45.0
            else:  # 157.5 / 337.5 deg -> X-major rotated -22.5!
                hx, hz, ry = half_chord, half_radial, -22.5

        segs.append(_cube(
            f'{prefix}_{k:02d}',
            [cx - hx, y0, cz - hz],
            [cx + hx, y1, cz + hz],
            [cx, 0.5 * (y0 + y1), cz],
            faces,
            rot_y=ry,
        ))
    return segs


# ---------------------------------------------------------------------------
# 3. Exact Halo Coordinates & Seamless 360-deg Spin Animation
# ---------------------------------------------------------------------------
# Bare player head top = Y = 30.00 (2nd-layer skin hat = Y = 30.47).
# Placing the halo at Y = 31.85 sits right above & framing the head like a true nimbus,
# keeping 100% of the inner pentagram chords & central Ankh unobstructed above the skull!
HALO_Y = 31.85
ROOT_ORIG = [0.0, HALO_Y, 0.0]
STAR_R = 5.76   # Inscribed pentagram star radius inside outer circle R = 5.95


def eval_satan_pose(u: float) -> dict:
    """Evaluates bone transforms at normalized phase u in [0, 1].
    Note: `u` can be 1.0 at the final keyframe so `rot_y` reaches a full `360.0` deg!
    """
    tau = 2.0 * math.pi
    u_per = 0.0 if u >= 1.0 else u

    # Gentle celestial/demonic float + subtle 5.8-deg gyroscopic tilt so the star is visible from side & front!
    hover_y = 0.20 * math.sin(tau * u_per)
    tilt_x = 5.8 * math.cos(tau * u_per)
    tilt_z = 5.8 * math.sin(tau * u_per)

    spin_deg = 360.0 * u
    aura_spin_deg = -360.0 * u
    aura_pulse = 1.0 + 0.028 * math.sin(tau * 2.0 * u_per)

    return {
        'root_pos': [0.0, round(hover_y, 4), 0.0],
        'root_rot': [round(tilt_x, 4), 0.0, round(tilt_z, 4)],
        'ring_rot': [0.0, round(spin_deg, 4), 0.0],
        'aura_rot': [0.0, round(aura_spin_deg, 4), 0.0],
        'aura_scale': [round(aura_pulse, 4), 1.0, round(aura_pulse, 4)],
        'beam_rots': {
            f'beam_{k}': [0.0, round(k * 72.0 + spin_deg, 4), 0.0]
            for k in range(5)
        },
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
    bones = ['satan_root', 'circle_ring', 'satan_aura'] + [f'beam_{k}' for k in range(5)]
    kfs = {b: [] for b in bones}

    # Keyframe every 2 ticks (0.10s -> 65 keyframes over 6.4s) — super light & butter-smooth!
    kf_steps = 64
    for s in range(kf_steps + 1):
        u = s / kf_steps
        t = IDLE_LEN * u
        pose = eval_satan_pose(u)

        kfs['satan_root'].append(_vec_kf('position', 'idle:satan_root', t, *pose['root_pos']))
        kfs['satan_root'].append(_vec_kf('rotation', 'idle:satan_root', t, *pose['root_rot']))

        kfs['circle_ring'].append(_vec_kf('rotation', 'idle:circle_ring', t, *pose['ring_rot']))

        kfs['satan_aura'].append(_vec_kf('rotation', 'idle:satan_aura', t, *pose['aura_rot']))
        kfs['satan_aura'].append(_vec_kf('scale', 'idle:satan_aura', t, *pose['aura_scale']))

        for k in range(5):
            bname = f'beam_{k}'
            kfs[bname].append(_vec_kf('rotation', f'idle:{bname}', t, *pose['beam_rots'][bname]))

    return {
        uid(f'bone:{b}'): {'name': b, 'type': 'bone', 'keyframes': kfs[b]}
        for b in bones
    }


# ---------------------------------------------------------------------------
# 4. 5 Miniature 3D Outer Crimson Occult Sigils (matching image-12.png!)
# ---------------------------------------------------------------------------
def _build_outer_sigil(kind: int, cy: float, cz: float, orig: list[float], faces: dict) -> list[dict]:
    """Builds one of the 5 outer crimson symbols around the pentagram circle (at x ~ 0, z ~ cz = -7.05):
       kind 0: Inverted Latin Cross (bottom / primary point in image-12.png)
       kind 1: Crescent & Star
       kind 2: Hexagram / Seal of Solomon
       kind 3: Sacred Flame / Om Curve
       kind 4: Flared Templar / Iron Cross
    All axis-aligned (`rot_y = 0.0`) inside their own rotated `beam_k` bone!
    """
    y0, y1 = cy - 0.11, cy + 0.11
    c = []
    if kind == 0:
        # Latin / Inverted Cross extending radially outward along -Z
        c.append(_cube('sig0_shaft', [-0.11, y0, cz - 0.68], [0.11, y1, cz + 0.62], orig, faces))
        c.append(_cube('sig0_bar',   [-0.44, y0, cz - 0.30], [0.44, y1, cz - 0.08], orig, faces))
    elif kind == 1:
        # Crescent Moon + Star dot
        c.append(_cube('sig1_arc_b', [-0.42, y0, cz + 0.24], [0.28, y1, cz + 0.44], orig, faces))
        c.append(_cube('sig1_arc_l', [-0.46, y0, cz - 0.28], [-0.24, y1, cz + 0.28], orig, faces))
        c.append(_cube('sig1_arc_t', [-0.42, y0, cz - 0.46], [0.28, y1, cz - 0.26], orig, faces))
        c.append(_cube('sig1_star',  [0.10,  y0, cz - 0.12], [0.34, y1, cz + 0.12], orig, faces))
    elif kind == 2:
        # Hexagram / Star frame
        c.append(_cube('sig2_top_h', [-0.46, y0, cz - 0.34], [0.46, y1, cz - 0.16], orig, faces))
        c.append(_cube('sig2_bot_h', [-0.46, y0, cz + 0.16], [0.46, y1, cz + 0.34], orig, faces))
        c.append(_cube('sig2_v_l',   [-0.32, y0, cz - 0.48], [-0.14, y1, cz + 0.48], orig, faces))
        c.append(_cube('sig2_v_r',   [0.14,  y0, cz - 0.48], [0.32, y1, cz + 0.48], orig, faces))
    elif kind == 3:
        # Occult Flame / Om glyph
        c.append(_cube('sig3_core',  [-0.38, y0, cz - 0.10], [0.38, y1, cz + 0.38], orig, faces))
        c.append(_cube('sig3_loop',  [-0.44, y0, cz - 0.42], [0.18, y1, cz - 0.20], orig, faces))
        c.append(_cube('sig3_dot',   [0.16,  y0, cz - 0.52], [0.38, y1, cz - 0.30], orig, faces))
    else:
        # Iron Cross (4 flared arms + center)
        c.append(_cube('sig4_v',     [-0.16, y0, cz - 0.50], [0.16, y1, cz + 0.50], orig, faces))
        c.append(_cube('sig4_h',     [-0.50, y0, cz - 0.16], [0.50, y1, cz + 0.16], orig, faces))
        c.append(_cube('sig4_cap_n', [-0.30, y0, cz - 0.52], [0.30, y1, cz - 0.36], orig, faces))
        c.append(_cube('sig4_cap_s', [-0.30, y0, cz + 0.36], [0.30, y1, cz + 0.52], orig, faces))
    return c


# ---------------------------------------------------------------------------
# 5. Blueprint Builder (`elytrix_satan_circle.bbmodel`)
# ---------------------------------------------------------------------------
def build_blueprint() -> tuple[dict, Image.Image]:
    texture = build_satan_texture()
    raw = io.BytesIO()
    texture.save(raw, format='PNG', optimize=True)

    elements: list[dict] = []

    def add(c: dict) -> str:
        elements.append(c)
        return c['uuid']

    def add_many(cs: list[dict]) -> list[str]:
        return [add(c) for c in cs]

    ring_obsidian_faces = _faces(
        UV_CRIMSON_RIM,
        up=UV_OBSIDIAN_CRACKED,
        down=UV_OBSIDIAN_CRACKED,
    )
    rim_crimson_faces = _faces(UV_CRIMSON_RIM, up=UV_MAGMA_CORE, down=UV_CRIMSON_RIM)
    sigil_faces = _faces(UV_SIGIL_RUBY, up=UV_MAGMA_CORE, down=UV_SIGIL_RUBY)
    aura_faces = _faces(UV_AURA_EMBER)
    beam_faces = _faces(
        UV_STAR_BEAM_SIDE,
        up=UV_STAR_BEAM_TOP,
        down=UV_STAR_BEAM_TOP,
        east=UV_CRIMSON_RIM,
        west=UV_CRIMSON_RIM,
    )

    # A) `circle_ring` bone: Smooth 16-gon Double Obsidian-Crimson Circle + Central 3D Ankh Emblem!
    circle_uuids: list[str] = []
    # Main cracked volcanic obsidian band (R = 5.92, radial width 0.64, Y = 31.68..32.02)
    circle_uuids.extend(add_many(_ring_16_segments('ring_core', 5.92, 0.32, HALO_Y - 0.17, HALO_Y + 0.17, ring_obsidian_faces)))
    # Raised outer blood-crimson rim (R = 6.26, Y = 31.63..32.07)
    circle_uuids.extend(add_many(_ring_16_segments('ring_out_rim', 6.26, 0.10, HALO_Y - 0.22, HALO_Y + 0.22, rim_crimson_faces)))
    # Raised inner blood-crimson rim (R = 5.58, Y = 31.64..32.06)
    circle_uuids.extend(add_many(_ring_16_segments('ring_in_rim', 5.58, 0.09, HALO_Y - 0.21, HALO_Y + 0.21, rim_crimson_faces)))

    # Central 3D Crimson Ankh Emblem suspended in the exact heart of the pentagram (matches image-12.png!)
    ay0, ay1 = HALO_Y - 0.16, HALO_Y + 0.16
    circle_uuids.extend([
        add(_cube('ankh_stem',    [-0.15, ay0, -0.05], [0.15, ay1,  1.08], ROOT_ORIG, sigil_faces)),
        add(_cube('ankh_arms',    [-0.66, ay0, -0.08], [0.66, ay1,  0.18], ROOT_ORIG, sigil_faces)),
        add(_cube('ankh_loop_l',  [-0.44, ay0, -0.92], [-0.20, ay1, -0.08], ROOT_ORIG, sigil_faces)),
        add(_cube('ankh_loop_r',  [0.20,  ay0, -0.92], [0.44, ay1, -0.08], ROOT_ORIG, sigil_faces)),
        add(_cube('ankh_loop_t',  [-0.38, ay0, -1.08], [0.38, ay1, -0.84], ROOT_ORIG, sigil_faces)),
    ])

    # B) `satan_aura` bone: Counter-rotating dark-crimson ember corona + 8 magma shards (mirrors angel_halo's aura!)
    aura_uuids: list[str] = []
    aura_uuids.extend(add_many(_ring_16_segments('aura_outer', 6.62, 0.12, HALO_Y - 0.06, HALO_Y + 0.06, aura_faces)))
    for m in range(8):
        ang = math.radians(m * 45.0)
        sx = 6.95 * math.sin(ang)
        sz = 6.95 * math.cos(ang)
        aura_uuids.append(add(_cube(
            f'aura_shard_{m}',
            [sx - 0.16, HALO_Y - 0.26, sz - 0.16],
            [sx + 0.16, HALO_Y + 0.26, sz + 0.16],
            [sx, HALO_Y, sz],
            rim_crimson_faces,
            rot_y=45.0 if (m % 2 == 1) else 0.0,
        )))

    # C) 5 Razor-Straight Pentagram Star Beams (`beam_0 .. beam_4`) + Vertex Spikes + 5 Outer Occult Sigils!
    #    Pentagram chord math:
    #      Connecting pentagon vertices at -72 deg and +72 deg on circle radius STAR_R = 5.76:
    #      z_chord = STAR_R * cos(72 deg) = 1.7800
    #      x_half  = STAR_R * sin(72 deg) = 5.4781
    #    Slight micro-stagger in Y (±0.024 BB) across the 5 chords eliminates coplanar z-fighting at the
    #    5 inner pentagon crossings AND gives an authentic over/under woven relief!
    z_chord = STAR_R * math.cos(math.radians(72.0))
    x_half = STAR_R * math.sin(math.radians(72.0))

    beam_bones = []
    for k in range(5):
        dy_weave = (k - 2) * 0.012
        by0 = HALO_Y - 0.15 + dy_weave
        by1 = HALO_Y + 0.15 + dy_weave
        b_uuids: list[str] = [
            # Main cracked obsidian + crimson-bordered pentagram chord
            add(_cube(
                f'star_chord_{k}',
                [-x_half, by0, z_chord - 0.26],
                [x_half,  by1, z_chord + 0.26],
                ROOT_ORIG,
                beam_faces,
            )),
            # Raised glowing crimson star-point spearhead at vertex (0, HALO_Y, -STAR_R)
            add(_cube(
                f'star_vertex_gem_{k}',
                [-0.22, HALO_Y - 0.24, -STAR_R - 0.22],
                [0.22,  HALO_Y + 0.24, -STAR_R + 0.26],
                ROOT_ORIG,
                sigil_faces,
            )),
        ]
        # Outer crimson occult sigil outside each star point (at Z = -7.12, matching image-12.png!)
        sig_cubes = _build_outer_sigil(k, HALO_Y, -7.12, ROOT_ORIG, sigil_faces)
        for idx_s, sc in enumerate(sig_cubes):
            sc['name'] = f'b{k}_{sc["name"]}_{idx_s}'
            sc['uuid'] = uid(f'cube:{sc["name"]}')
            b_uuids.append(add(sc))

        beam_bones.append({
            'name': f'beam_{k}',
            'origin': ROOT_ORIG,
            'rotation': [0.0, 0.0, 0.0],
            'color': 0,
            'uuid': uid(f'bone:beam_{k}'),
            'export': True,
            'mirror_uv': False,
            'isOpen': True,
            'locked': False,
            'visibility': True,
            'autouv': 0,
            'children': b_uuids,
        })

    def bone(name: str, orig: list[float], children: list) -> dict:
        return {
            'name': name,
            'origin': [round(float(v), 4) for v in orig],
            'rotation': [0.0, 0.0, 0.0],
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
        bone('satan_root', ROOT_ORIG, [
            bone('circle_ring', ROOT_ORIG, circle_uuids),
            bone('satan_aura', ROOT_ORIG, aura_uuids),
            *beam_bones,
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
        'animations': [{
            'uuid': uid('anim:idle'),
            'name': 'idle',
            'loop': 'loop',
            'override': False,
            'length': IDLE_LEN,
            'snapping': 20,
            'selected': True,
            'saved': True,
            'path': '',
            'anim_time_update': '',
            'blend_weight': '',
            'start_delay': '',
            'loop_delay': '',
            'animators': build_idle_animators(),
        }],
    }
    return blueprint, texture


# ---------------------------------------------------------------------------
# 6. Hand-Crafted 32x32 Pixel-Art Menu Icon (`reallyworld:satan_circle_icon`)
# ---------------------------------------------------------------------------
def build_satan_icon() -> Image.Image:
    """Draws a crisp 32x32 pixel-art Satanic Pentagram Circle icon directly inspired
    by the cracked crimson-black pentagram reference image.
    """
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    bg_dark   = (24, 6, 9, 255)
    rim_dark  = (118, 12, 20, 255)
    crimson   = (208, 24, 34, 255)
    magma_hi  = (252, 74, 60, 255)
    aura_soft = (156, 16, 26, 155)

    cx, cy = 15.5, 15.0
    r_outer = 11.4
    r_inner = 9.4

    def put(x: int, y: int, c: tuple):
        if 0 <= x < 32 and 0 <= y < 32:
            px[x, y] = c

    # 1. Outer cracked crimson circle ring
    for y in range(32):
        for x in range(32):
            d = math.hypot(x - cx, y - cy)
            if r_inner - 0.4 <= d <= r_outer + 0.4:
                if r_inner + 0.35 <= d <= r_outer - 0.35:
                    crack = ((x * 5 + y * 3) % 9 == 0)
                    put(x, y, magma_hi if crack else bg_dark)
                else:
                    put(x, y, crimson if ((x + y) % 3 != 0) else rim_dark)
            elif r_outer + 0.4 < d <= r_outer + 1.25 and (x + y) % 2 == 0:
                put(x, y, aura_soft)

    # 2. Inverted 5-pointed pentagram star chords (point straight down at y ~ 26!)
    verts = []
    for m in range(5):
        ang = math.radians(90.0 + m * 72.0)  # 90 deg = straight down (+Y in image coords)
        verts.append((cx + 10.2 * math.cos(ang), cy + 10.2 * math.sin(ang)))

    def draw_segment(p0, p1):
        steps = 48
        for i in range(steps + 1):
            t = i / steps
            fx = p0[0] + (p1[0] - p0[0]) * t
            fy = p0[1] + (p1[1] - p0[1]) * t
            ix, iy = int(round(fx)), int(round(fy))
            put(ix, iy, magma_hi if (i % 7 == 0) else crimson)
            for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = ix + ox, iy + oy
                if 0 <= nx < 32 and 0 <= ny < 32 and px[nx, ny][3] == 0:
                    put(nx, ny, bg_dark)

    for m in range(5):
        draw_segment(verts[m], verts[(m + 2) % 5])

    # 3. Tiny crimson Ankh in center + bottom cross & side rune accents (like image-12.png)
    put(15, 14, magma_hi)
    put(16, 14, crimson)
    put(15, 15, crimson)
    put(14, 15, rim_dark)
    put(16, 15, rim_dark)
    put(15, 16, crimson)

    # Bottom cross below the inverted star point (x=15..16, y=28..30)
    for yy in (28, 29, 30):
        put(15, yy, crimson)
        put(16, yy, rim_dark)
    put(14, 29, crimson)
    put(17, 29, crimson)

    # Subtle 4 outer crimson rune sparks around perimeter
    for rx, ry in ((3, 19), (28, 19), (7, 3), (24, 3)):
        put(rx, ry, magma_hi)
        put(rx + 1 if rx < 16 else rx - 1, ry, crimson)

    return img


# ---------------------------------------------------------------------------
# 7. Multi-Angle Verification Preview Renderer (`satan_circle_preview.png`)
# ---------------------------------------------------------------------------
def render_preview(blueprint: dict, texture: Image.Image, icon: Image.Image, out_path: Path):
    panel_w, panel_h = 250, 300
    canvas = Image.new('RGBA', (panel_w * 4 + 210, panel_h), (18, 14, 20, 255))

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
    by_uuid = {el['uuid']: el for el in blueprint['elements']}

    root_group = blueprint['outliner'][0]
    bone_cubes = {}
    for child in root_group['children']:
        bone_cubes[child['name']] = [by_uuid[u] for u in child['children']]

    stages = [
        (0.05,  24.0, -24.0, True),   # 1. Front-3/4 view spinning above player head
        (0.32, -42.0, -28.0, True),   # 2. Side-3/4 view showing halo height & spinning runes
        (0.62, 152.0, -24.0, True),   # 3. Back-3/4 view
        (0.00,   0.0, -86.0, False),  # 4. Top-down closeup proving crisp 5-pointed pentagram + Ankh + 5 sigils!
    ]

    for idx, (u, cam_yaw, cam_pitch, show_head) in enumerate(stages):
        bg = (14, 10, 14, 255) if idx == 3 else (26, 22, 30, 255)
        panel = Image.new('RGBA', (panel_w, panel_h), bg)
        pose = eval_satan_pose(u)

        ay = math.radians(cam_yaw)
        ap = math.radians(cam_pitch)
        cy_m, sy_m = math.cos(ay), math.sin(ay)
        cp_m, sp_m = math.cos(ap), math.sin(ap)

        scale_px = 13.5 if show_head else 14.5
        center_y_world = 28.8 if show_head else HALO_Y
        center_y_px = 175.0 if show_head else 150.0

        def proj(pt):
            dx, dy, dz = pt[0], pt[1] - center_y_world, pt[2]
            xw = dx * cy_m - dz * sy_m
            z1 = dx * sy_m + dz * cy_m
            yw = dy * cp_m - z1 * sp_m
            zw = dy * sp_m + z1 * cp_m
            return (panel_w * 0.5 - xw * scale_px, center_y_px - yw * scale_px, zw)

        faces_to_draw = []

        if show_head:
            ref_boxes = [
                ([-7.5, 18.0, -1.875], [7.5, 22.5, 1.875], (52, 56, 70)),
                ([-3.75, 22.5, -3.75], [3.75, 30.0, 3.75], (84, 90, 110)),
            ]
            for low, high, base_rgb in ref_boxes:
                cs = [
                    np.array([low[0], low[1], low[2]]), np.array([high[0], low[1], low[2]]),
                    np.array([high[0], high[1], low[2]]), np.array([low[0], high[1], low[2]]),
                    np.array([low[0], low[1], high[2]]), np.array([high[0], low[1], high[2]]),
                    np.array([high[0], high[1], high[2]]), np.array([low[0], high[1], high[2]]),
                ]
                for idxs, sm in (((2, 1, 0, 3), 1.0), ((7, 4, 5, 6), 0.86), ((6, 5, 1, 2), 0.92), ((3, 0, 4, 7), 0.90), ((7, 6, 2, 3), 1.05)):
                    p2d = [proj(cs[k]) for k in idxs]
                    cross = (p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1]) - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0])
                    if cross <= 0:
                        col = tuple(min(255, int(c * sm)) for c in base_rgb) + (255,)
                        faces_to_draw.append((sum(p[2] for p in p2d) / 4.0, [(s[0], s[1]) for s in p2d], col, (36, 40, 52, 255)))

        def bone_tf(parent_tf, orig, pos, rot, scale):
            o = np.array(orig)
            t = np.array(pos)
            m = rot_mat(*rot)
            sc = np.array(scale)
            return lambda p: parent_tf(o + t + m @ (sc * (p - o)))

        tf_root = bone_tf(lambda p: p, ROOT_ORIG, pose['root_pos'] if show_head else [0, 0, 0],
                          pose['root_rot'] if show_head else [0, 0, 0], [1.0, 1.0, 1.0])
        b_tfs = {
            'circle_ring': bone_tf(tf_root, ROOT_ORIG, [0, 0, 0], pose['ring_rot'], [1, 1, 1]),
            'satan_aura':  bone_tf(tf_root, ROOT_ORIG, [0, 0, 0], pose['aura_rot'], pose['aura_scale']),
        }
        for k in range(5):
            bname = f'beam_{k}'
            b_tfs[bname] = bone_tf(tf_root, ROOT_ORIG, [0, 0, 0], pose['beam_rots'][bname], [1, 1, 1])

        for bname, cubes in bone_cubes.items():
            tf_fn = b_tfs[bname]
            for el in cubes:
                x0, y0, z0 = el['from']
                x1, y1, z1 = el['to']
                c_orig = np.array(el['origin'])
                c_rot = rot_mat(*el['rotation'])
                raw_cs = [
                    np.array([x0, y0, z0]), np.array([x1, y0, z0]), np.array([x1, y1, z0]), np.array([x0, y1, z0]),
                    np.array([x0, y0, z1]), np.array([x1, y0, z1]), np.array([x1, y1, z1]), np.array([x0, y1, z1]),
                ]
                wcs = [tf_fn(c_orig + c_rot @ (c - c_orig)) for c in raw_cs]
                quads = [
                    ('north', (2, 1, 0, 3), 1.00),
                    ('south', (7, 4, 5, 6), 0.96),
                    ('east',  (6, 5, 1, 2), 0.98),
                    ('west',  (3, 0, 4, 7), 0.98),
                    ('up',    (7, 6, 2, 3), 1.05),
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
                    if rgba[3] < 16:
                        continue
                    col = tuple(min(255, int(c * sm)) for c in rgba[:3]) + (int(rgba[3]),)
                    faces_to_draw.append((z_avg, [(s[0], s[1]) for s in p2d], col, None))

        faces_to_draw.sort(key=lambda item: item[0], reverse=True)
        for _, poly, col, outline in faces_to_draw:
            layer = Image.new('RGBA', (panel_w, panel_h), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer, 'RGBA')
            ld.polygon(poly, fill=col, outline=outline)
            panel.alpha_composite(layer)

        canvas.paste(panel, (idx * panel_w, 0))
        d = ImageDraw.Draw(canvas)
        d.line([(idx * panel_w, 0), (idx * panel_w, panel_h)], fill=(64, 34, 42, 255), width=1)

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

    icon = build_satan_icon()
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

    print(f'Built {MODEL}.bbmodel: {len(blueprint["elements"])} cubes, 7 bones, icon -> {args.assets_dir}')


if __name__ == '__main__':
    main()
