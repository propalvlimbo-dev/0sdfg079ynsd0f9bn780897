#!/usr/bin/env python3
"""Procedurally builds the FAME donation sword (`reallyworld:item/sword/fame_sword`).

100% pure procedural Python + Pillow + NumPy - zero AI generation.

The donation `TIGER` is replaced by `FAME` (499 RUB, one step below ANGEL), and the
player asked for the FAME kit to carry **its own sword model**.  Every other donation
sword on the server (`god`, `angel`, `dadmin`, `techno`, `easter`, `rose`) is a
Blockbench item model in `assets/reallyworld/models/item/...` with a hand-painted
64x64 atlas, driven by a `custom_model_data` override on
`assets/minecraft/models/item/netherite_sword.json`.  This script produces exactly the
same kind of artefact, in the same coordinate frame, with the same `display` block:

    blade long axis = Z, blade width = Y, blade thickness = X (centred on x = 8)

so the sword sits correctly in the hand, on the ground and in the GUI.

Palette - FAME is deliberately the only AMETHYST/PURPLE donation on the server
(ANGEL is warm white, GOD and D.ADMIN are gold/bronze, TECHNO is dark red):
deep amethyst body -> violet -> hot magenta fuller -> white-hot core, with a
polished gold crossguard so it still reads as a donate-tier weapon.

The model is exported to `tools/accessories-model/assets/reallyworld/...`, i.e.
straight into the tree that `merge_pack.py` merges into the served resource pack.
The `custom_model_data` override itself is added by `patch_rp_fame.py` (run after
`merge_pack.py`), because that file is shared with the hand-made overrides.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = ROOT / 'tools/accessories-model/assets'
NAME = 'fame_sword'
TEX = 64
CMD = 5015          # custom_model_data reserved for the FAME sword

# ---------------------------------------------------------------------------
# 1. Palette
# ---------------------------------------------------------------------------
V_DEEP = (34, 10, 62)
V_DARK = (58, 20, 104)
V_MID = (104, 44, 178)
V_LIT = (176, 104, 244)
M_HOT = (255, 126, 224)
M_PINK = (255, 186, 240)
W_CORE = (255, 244, 255)
G_DARK = (104, 62, 14)
G_MID = (206, 150, 44)
G_LIT = (255, 214, 120)
G_HI = (255, 246, 214)
N_DARK = (16, 6, 30)

# ---------------------------------------------------------------------------
# 2. Texture atlas (64x64).  Each region is (x0, y0, x1, y1) in pixels.
# ---------------------------------------------------------------------------
T_BLADE_FACE = (0, 0, 34, 7)
T_BLADE_EDGE = (0, 8, 34, 9)
T_CORE = (0, 10, 34, 12)
T_TIP = (0, 14, 6, 20)
T_GUARD_FACE = (0, 22, 10, 28)
T_GUARD_SIDE = (0, 29, 10, 31)
T_QUILL_FACE = (11, 22, 21, 28)
T_QUILL_SIDE = (11, 29, 21, 31)
T_GRIP = (0, 33, 10, 43)
T_WRAP = (11, 33, 21, 43)
T_POMMEL = (0, 45, 10, 51)
T_GEM = (11, 45, 21, 51)


def _ramp(stops, t: float):
    t = max(0.0, min(1.0, t))
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


def _mix(c0, c1, k: float):
    k = max(0.0, min(1.0, k))
    return tuple(c0[j] + (c1[j] - c0[j]) * k for j in range(3))


def build_fame_texture() -> Image.Image:
    arr = np.zeros((TEX, TEX, 4), dtype=np.uint8)

    def paint(rect, fn, alpha=None):
        x0, y0, x1, y1 = rect
        w, h = x1 - x0, y1 - y0
        for py in range(h):
            for px in range(w):
                u = (px + 0.5) / w
                v = (py + 0.5) / h
                col, a = fn(u, v)
                arr[y0 + py, x0 + px] = (int(round(col[0])), int(round(col[1])),
                                         int(round(col[2])), int(round(a)))

    # --- the flat of the blade: dark at both cutting edges, hot magenta fuller ---
    def blade(u: float, v: float):
        q = abs(v - 0.5) * 2.0                       # 0 fuller -> 1 edge
        shimmer = (0.05 * math.sin(u * 26.0) + 0.03 * math.sin(u * 61.0 + 1.2))
        col = _ramp([(0.00, W_CORE), (0.16, M_PINK), (0.34, M_HOT),
                     (0.58, V_LIT), (0.82, V_DARK), (1.00, V_DEEP)],
                    max(0.0, min(1.0, q + shimmer)))
        # the last 20% of the length is the tip: it burns out into light
        col = _mix(col, M_PINK, 0.55 * max(0.0, (u - 0.80) / 0.20))
        # a bright hairline exactly on each cutting edge
        col = _mix(col, G_HI, 0.75 * max(0.0, (q - 0.90) / 0.10))
        return col, 255.0

    paint(T_BLADE_FACE, blade)

    # --- the cutting edge (up/down faces): a thin gold hairline --------------
    def edge(u: float, v: float):
        col = _ramp([(0.00, G_HI), (0.30, G_LIT), (0.70, V_LIT), (1.00, V_DEEP)], v)
        col = _mix(col, W_CORE, 0.60 * max(0.0, (u - 0.82) / 0.18))
        return col, 255.0

    paint(T_BLADE_EDGE, edge)

    # --- the fuller: the glowing groove down the middle ----------------------
    def core(u: float, v: float):
        q = abs(v - 0.5) * 2.0
        col = _ramp([(0.00, W_CORE), (0.30, M_PINK), (0.62, M_HOT), (1.00, V_MID)], q)
        col = _mix(col, W_CORE, 0.35 * math.sin(u * 18.0) ** 2)
        return col, 255.0

    paint(T_CORE, core)

    # --- end caps of the blade ----------------------------------------------
    def tip(u: float, v: float):
        d = math.hypot((u - 0.5) * 1.35, (v - 0.5) * 2.0)
        col = _ramp([(0.00, W_CORE), (0.28, M_HOT), (0.60, V_MID), (1.00, V_DEEP)], d)
        return col, 255.0

    paint(T_TIP, tip)

    # --- gold crossguard -----------------------------------------------------
    def gold(u: float, v: float, dark: float):
        t = max(0.0, min(1.0, v * 0.85 + 0.08 + 0.05 * math.sin(u * 9.0)))
        col = _ramp([(0.00, G_HI), (0.24, G_LIT), (0.55, G_MID),
                     (0.82, G_DARK), (1.00, N_DARK)], t)
        return _mix(col, N_DARK, dark), 255.0

    paint(T_GUARD_FACE, lambda u, v: gold(u, v, 0.0))
    paint(T_GUARD_SIDE, lambda u, v: gold(u, v, 0.18))
    paint(T_QUILL_FACE, lambda u, v: gold(u, v, 0.06))
    paint(T_QUILL_SIDE, lambda u, v: gold(u, v, 0.24))

    # --- grip: dark amethyst leather with a woven wrap -----------------------
    def grip(u: float, v: float):
        t = max(0.0, min(1.0, v * 0.9 + 0.05 + 0.05 * math.sin(u * 7.0)))
        col = _ramp([(0.00, V_LIT), (0.30, V_MID), (0.66, V_DARK), (1.00, N_DARK)], t)
        return col, 255.0

    paint(T_GRIP, grip)

    def wrap(u: float, v: float):
        band = 0.5 + 0.5 * math.sin((u * 3.0 + v * 1.0) * math.pi * 2.0)
        col = _mix(V_DARK, G_MID, 0.35 + 0.45 * band)
        col = _mix(col, N_DARK, 0.30 * abs(v - 0.5) * 2.0)
        return col, 255.0

    paint(T_WRAP, wrap)

    # --- pommel + gem --------------------------------------------------------
    def pommel(u: float, v: float):
        d = math.hypot(u - 0.5, v - 0.5) * 2.0
        col = _ramp([(0.00, G_HI), (0.34, G_LIT), (0.68, G_DARK), (1.00, N_DARK)], d)
        return col, 255.0

    paint(T_POMMEL, pommel)

    def gem(u: float, v: float):
        d = math.hypot(u - 0.5, v - 0.5) * 2.0
        col = _ramp([(0.00, W_CORE), (0.26, M_PINK), (0.55, M_HOT),
                     (0.82, V_MID), (1.00, V_DEEP)], d)
        # a little star glint
        glint = max(0.0, 1.0 - math.hypot(u - 0.34, v - 0.34) * 9.0)
        col = _mix(col, W_CORE, 0.85 * glint)
        a = 255.0 if d < 0.98 else 0.0
        return col, a

    paint(T_GEM, gem)

    return Image.fromarray(arr, 'RGBA')


# ---------------------------------------------------------------------------
# 3. Geometry
# ---------------------------------------------------------------------------
# (name, from, to, face tiles, rotation or None)
# face tiles: (east/west, up/down, north/south) - for the blade the long axis is Z,
# so east/west are the two big flats of the blade.
FLAT = 'flat'
EDGE = 'edge'
CAP = 'cap'


def _el(name: str, frm, to, tiles, rotation=None):
    faces = {}
    uv_flat, uv_edge, uv_cap = tiles
    for side in ('east', 'west'):
        faces[side] = {'texture': '#0', 'uv': list(uv_flat)}
    for side in ('up', 'down'):
        faces[side] = {'texture': '#0', 'uv': list(uv_edge)}
    for side in ('north', 'south'):
        faces[side] = {'texture': '#0', 'uv': list(uv_cap)}
    el = {
        'name': name,
        'from': [round(float(v), 4) for v in frm],
        'to': [round(float(v), 4) for v in to],
        'faces': faces,
    }
    if rotation is not None:
        el['rotation'] = rotation
    return el


def _all(name: str, frm, to, tile, rotation=None):
    faces = {side: {'texture': '#0', 'uv': list(tile)} for side in
             ('north', 'east', 'south', 'west', 'up', 'down')}
    el = {
        'name': name,
        'from': [round(float(v), 4) for v in frm],
        'to': [round(float(v), 4) for v in to],
        'faces': faces,
    }
    if rotation is not None:
        el['rotation'] = rotation
    return el


BLADE_TILES = (T_BLADE_FACE, T_BLADE_EDGE, T_TIP)

ELEMENTS = [
    # --- the blade: three tapered plates, tip -> guard ----------------------
    _el('blade_tip', (7.6, 6.6, -16.0), (8.4, 9.4, -8.0), BLADE_TILES),
    _el('blade_mid', (7.5, 5.4, -8.0), (8.5, 10.6, 3.0), BLADE_TILES),
    _el('blade_base', (7.5, 4.7, 3.0), (8.5, 11.3, 12.0), BLADE_TILES),
    # --- the fuller: a glowing groove on BOTH flats -------------------------
    _all('fuller_w', (7.20, 7.2, -14.0), (7.52, 8.8, 10.6), T_CORE),
    _all('fuller_e', (8.48, 7.2, -14.0), (8.80, 8.8, 10.6), T_CORE),
    # --- the gold crossguard ------------------------------------------------
    _el('guard', (6.4, 5.2, 12.0), (9.6, 10.8, 15.4),
        (T_GUARD_FACE, T_GUARD_SIDE, T_GUARD_SIDE)),
    _el('quillon_up', (6.6, 10.4, 12.2), (9.4, 14.8, 15.2),
        (T_QUILL_FACE, T_QUILL_SIDE, T_QUILL_SIDE),
        {'angle': -22.5, 'axis': 'x', 'origin': [8.0, 10.4, 15.2]}),
    _el('quillon_down', (6.6, 1.2, 12.2), (9.4, 5.6, 15.2),
        (T_QUILL_FACE, T_QUILL_SIDE, T_QUILL_SIDE),
        {'angle': 22.5, 'axis': 'x', 'origin': [8.0, 5.6, 15.2]}),
    # --- the grip, its two wraps, the pommel and its gem --------------------
    _all('grip', (7.2, 6.6, 15.4), (8.8, 9.4, 24.0), T_GRIP),
    _all('wrap_01', (7.0, 6.3, 17.2), (9.0, 9.7, 18.4), T_WRAP),
    _all('wrap_02', (7.0, 6.3, 20.2), (9.0, 9.7, 21.4), T_WRAP),
    _all('pommel', (6.8, 6.2, 24.0), (9.2, 9.8, 26.4), T_POMMEL),
    _all('gem', (7.2, 6.6, 26.4), (8.8, 9.4, 28.4), T_GEM),
]

# The `display` block is copied verbatim from the server's other donation swords
# (`sword/dadmin_sword.json`), so the FAME sword is held, dropped and drawn in the
# GUI exactly like every other donate weapon.
DISPLAY = {
    'firstperson_lefthand': {'rotation': [78, 4, -9], 'scale': [0.66, 0.66, 0.66],
                             'translation': [1.75, 5.75, 0.5]},
    'firstperson_righthand': {'rotation': [78, 4, -9], 'scale': [0.66, 0.66, 0.66],
                              'translation': [1.75, 5.75, 0.5]},
    'fixed': {'rotation': [90, 0, 90], 'scale': [0.66, 0.66, 0.66],
              'translation': [-0.25, 0, -0.75]},
    'ground': {'rotation': [45, 0, 0], 'scale': [0.55, 0.55, 0.55],
               'translation': [0, 9, -0.25]},
    'gui': {'rotation': [90, 45, 90], 'scale': [0.4, 0.4, 0.4],
            'translation': [-0.25, 0.25, 0]},
    'thirdperson_lefthand': {'rotation': [90, 0, 0], 'scale': [0.85, 0.85, 0.85],
                             'translation': [0, 8.5, 0.25]},
    'thirdperson_righthand': {'rotation': [90, 0, 0], 'scale': [0.85, 0.85, 0.85],
                              'translation': [0, 8.75, 0.25]},
}


def build_fame_model() -> dict:
    return {
        'credit': 'Procedurally generated for Elytrix (FAME donation sword)',
        'format_version': '1.21.6',
        'gui_light': 'front',
        'texture_size': [TEX, TEX],
        'textures': {'0': f'reallyworld:item/sword/{NAME}',
                     'particle': f'reallyworld:item/sword/{NAME}'},
        'display': DISPLAY,
        'groups': [{'name': 'group', 'color': 0, 'origin': [8.0, 8.0, 12.0],
                    'children': list(range(len(ELEMENTS)))}],
        'elements': ELEMENTS,
    }


def check(model: dict) -> None:
    """Every coordinate must stay inside Minecraft's -16..32 item-model box."""
    for el in model['elements']:
        for k in range(3):
            assert -16.0 <= el['from'][k] <= 32.0, el['name']
            assert -16.0 <= el['to'][k] <= 32.0, el['name']
            assert el['from'][k] < el['to'][k], el['name']
        for side, face in el['faces'].items():
            for v in face['uv']:
                # UVs are in atlas pixels; they must stay inside the 64x64 sheet.
                assert 0.0 <= v <= float(TEX), (el['name'], side, face['uv'])
            u0, v0, u1, v1 = face['uv']
            assert abs(u1 - u0) > 1e-6 and abs(v1 - v0) > 1e-6, (el['name'], side)
    # every atlas region must be referenced by at least one face
    used = set()
    for el in model['elements']:
        for face in el['faces'].values():
            used.add(tuple(face['uv']))
    for key, val in list(globals().items()):
        if key.startswith('T_') and isinstance(val, tuple) and len(val) == 4:
            assert val in used, 'unused atlas region ' + key


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--assets-dir', type=Path, default=ASSETS)
    ap.add_argument('--preview', type=Path, default=None)
    args = ap.parse_args()

    model = build_fame_model()
    check(model)
    texture = build_fame_texture()

    tex_path = args.assets_dir / f'reallyworld/textures/item/sword/{NAME}.png'
    mdl_path = args.assets_dir / f'reallyworld/models/item/sword/{NAME}.json'
    for p in (tex_path, mdl_path):
        p.parent.mkdir(parents=True, exist_ok=True)
    texture.save(tex_path, optimize=True)
    mdl_path.write_text(json.dumps(model, indent=2) + '\n', encoding='utf-8')

    if args.preview is not None:
        texture.resize((256, 256), Image.NEAREST).save(args.preview, optimize=True)

    print(f'Built {NAME}: {len(ELEMENTS)} elements, {TEX}x{TEX} atlas, '
          f'custom_model_data {CMD} -> {mdl_path}')


if __name__ == '__main__':
    main()
