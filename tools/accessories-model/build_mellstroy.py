#!/usr/bin/env python3
"""Procedurally builds the iconic Mellstroy shoulder pet (`elytrix_mellstroy`),
its 6 in-model `D.Admin BAN`-style 3D pixel-art pop-up phrase badges, and its
32x32 pixel-art menu icon (`mellstroy_icon`).

100% pure procedural Python + Pillow — zero AI generation:
  - Backwards white Rolex snapback cap (semicircular forehead cutout showing
    cropped light-brown buzzcut hair, white strap, green & gold Rolex crown tag,
    and rear brim sticking out at +Z)
  - Cheeky wide dimpled grin, raised eyebrow, grey-blue eyes
  - Black Dolce & Gabbana (D&G) luxury tee with white double-stripe collar,
    silver-white crown monograms, V-shaped Cuban gold chain + 3D gold pendant,
    and emerald-green + fiery-orange bird-of-paradise tropical print
  - 3D gold Rolex watch on right wrist + black pants + white/gold sneakers
  - 6 animated 3D `D.Admin BAN`-style pop-up phrase badges (`shade: false`,
    invisible `scale=[0,0,0]` during `idle`, springing up above Mellstroy's cap
    during `say_svet`, `say_amam`, `say_voznya`, `say_babki`, `say_tancuem`,
    `say_miliciya` in sync with real Mellstroy Ogg Vorbis voice clips!)
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
MODEL = 'elytrix_mellstroy'
ICON = 'mellstroy_icon'

SCALE = 0.34
CX = -8.85        # Perched beside/above outer left shoulder (100% clear of head & helmet)
FEET_Y = 23.85    # Shoulder height
CZ = -0.55

ANIM_LENGTH = 4.0
ANIM_STEPS = 80   # 20 ticks/sec -> 81 keyframes (0..80 inclusive)

# (bone_name, anim_name, badge_text, duration_sec, atlas_px_xy, pose_style)
PHRASE_SPECS = (
    ('badge_svet',     'say_svet',     'ДА БУДЕТ СВЕТ!',  4.8, (0,   64), 'svet'),
    ('badge_amam',     'say_amam',     'АМ-АМ-АМ!',       3.4, (64,  64), 'amam'),
    ('badge_voznya',   'say_voznya',   'ПОШЛА ВОЗНЯ!',    2.0, (0,   85), 'voznya'),
    ('badge_babki',    'say_babki',    'БАБКИ РУЛЯТСЯ!',  3.8, (64,  85), 'babki'),
    ('badge_tancuem',  'say_tancuem',  'ТАНЦУЕМ ВСЕ!',    3.2, (0,  106), 'tancuem'),
    ('badge_miliciya', 'say_miliciya', 'ПОМОГИТЕ!',       2.5, (64,   2), 'miliciya'),
)

# Hand-crafted crisp 3x7 / 4x7 bitmap Cyrillic pixel font (zero blurry anti-aliasing!)
PIXEL_FONT_7 = {
    'А': ['.##.', '#..#', '#..#', '####', '#..#', '#..#', '#..#'],
    'Б': ['####', '#...', '#...', '###.', '#..#', '#..#', '###.'],
    'В': ['###.', '#..#', '#..#', '###.', '#..#', '#..#', '###.'],
    'Г': ['####', '#...', '#...', '#...', '#...', '#...', '#...'],
    'Д': ['.##.', '.#.#', '.#.#', '.#.#', '.#.#', '####', '#..#'],
    'Е': ['####', '#...', '#...', '###.', '#...', '#...', '####'],
    'З': ['###.', '...#', '...#', '.##.', '...#', '...#', '###.'],
    'И': ['#..#', '#..#', '#.##', '##.#', '#..#', '#..#', '#..#'],
    'К': ['#..#', '#.#.', '##..', '##..', '#.#.', '#..#', '#..#'],
    'Л': ['..##', '.#.#', '.#.#', '.#.#', '.#.#', '#..#', '#..#'],
    'М': ['#...#', '##.##', '#.#.#', '#...#', '#...#', '#...#', '#...#'],
    'Н': ['#..#', '#..#', '#..#', '####', '#..#', '#..#', '#..#'],
    'О': ['.##.', '#..#', '#..#', '#..#', '#..#', '#..#', '.##.'],
    'П': ['####', '#..#', '#..#', '#..#', '#..#', '#..#', '#..#'],
    'Р': ['###.', '#..#', '#..#', '###.', '#...', '#...', '#...'],
    'С': ['.###', '#...', '#...', '#...', '#...', '#...', '.###'],
    'Т': ['###', '.#.', '.#.', '.#.', '.#.', '.#.', '.#.'],
    'У': ['#..#', '#..#', '#..#', '.###', '...#', '...#', '###.'],
    'Ц': ['#..#.', '#..#.', '#..#.', '#..#.', '#..#.', '####.', '...##'],
    'Ш': ['#.#.#', '#.#.#', '#.#.#', '#.#.#', '#.#.#', '#.#.#', '#####'],
    'Ь': ['#...', '#...', '#...', '###.', '#..#', '#..#', '###.'],
    'Я': ['.###', '#..#', '#..#', '.###', '.#.#', '#..#', '#..#'],
    '!': ['#', '#', '#', '#', '#', '.', '#'],
    '-': ['...', '...', '...', '###', '...', '...', '...'],
    ' ': ['..', '..', '..', '..', '..', '..', '..'],
}

# Compact 3x7 variants used automatically when a 14-char phrase needs to fit inside 56px cleanly
PIXEL_FONT_7_COMPACT = dict(PIXEL_FONT_7, **{
    'А': ['.#.', '#.#', '#.#', '###', '#.#', '#.#', '#.#'],
    'Б': ['###', '#..', '#..', '###', '#.#', '#.#', '###'],
    'В': ['##.', '#.#', '#.#', '##.', '#.#', '#.#', '##.'],
    'Д': ['.##.', '.#.#', '.#.#', '.#.#', '.#.#', '####', '#..#'],
    'Е': ['###', '#..', '#..', '##.', '#..', '#..', '###'],
    'И': ['#..#', '#..#', '#.##', '##.#', '#..#', '#..#', '#..#'],
    'К': ['#.#', '#.#', '##.', '##.', '#.#', '#.#', '#.#'],
    'Л': ['.##', '#.#', '#.#', '#.#', '#.#', '#.#', '#.#'],
    'Р': ['###', '#.#', '#.#', '###', '#..', '#..', '#..'],
    'С': ['###', '#..', '#..', '#..', '#..', '#..', '###'],
    'Т': ['###', '.#.', '.#.', '.#.', '.#.', '.#.', '.#.'],
    'У': ['#.#', '#.#', '#.#', '###', '..#', '..#', '###'],
    'Ц': ['#.#.', '#.#.', '#.#.', '#.#.', '#.#.', '####', '...#'],
    'Ь': ['#..', '#..', '#..', '###', '#.#', '#.#', '###'],
    'Я': ['###', '#.#', '#.#', '###', '.##', '#.#', '#.#'],
    ' ': ['.', '.', '.', '.', '.', '.', '.'],
})


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f'elytrix.mellstroy.v2:{tag}'))


def _pt(dx: float, dy: float, dz: float) -> list:
    return [CX + dx * SCALE, FEET_Y + dy * SCALE, CZ + dz * SCALE]


# ---------------------------------------------------------------------------
# 1. Hand-Crafted 128x128 Pixel-Art Texture Atlas (UV 16x16 -> 8px per UV unit)
# ---------------------------------------------------------------------------
def _build_body_64() -> Image.Image:
    """Builds the exact 64x64 Mellstroy body/cap/D&G/Rolex pixel-art quadrant."""
    skin_base = (246, 206, 184, 255)
    skin_hi = (253, 220, 202, 255)
    skin_shade = (224, 176, 152, 255)
    skin_dimple = (206, 152, 130, 255)
    hair_main = (112, 82, 58, 255)
    hair_dark = (84, 58, 40, 255)
    brow_col = (96, 68, 48, 255)
    eye_white = (250, 252, 255, 255)
    eye_iris = (88, 126, 152, 255)
    eye_pupil = (26, 34, 46, 255)
    lip_upper = (196, 108, 112, 255)
    lip_lower = (214, 122, 126, 255)
    teeth = (252, 252, 250, 255)
    mouth_corner = (146, 72, 78, 255)

    cap_white = (244, 247, 250, 255)
    cap_shade = (214, 222, 230, 255)
    rolex_green = (22, 126, 72, 255)
    gold_bright = (255, 228, 108, 255)
    gold_main = (238, 186, 52, 255)
    gold_deep = (178, 126, 24, 255)

    shirt_black = (22, 24, 30, 255)
    shirt_dark = (14, 16, 20, 255)
    mono_light = (212, 218, 228, 255)
    mono_mid = (132, 140, 154, 255)
    leaf_bright = (46, 196, 88, 255)
    leaf_deep = (22, 132, 58, 255)
    flower_orange = (252, 122, 34, 255)
    flower_gold = (255, 196, 54, 255)

    img = Image.new('RGBA', (64, 64), shirt_black)
    px = img.load()

    def rect(x0, y0, x1, y1, col):
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if 0 <= xx < 64 and 0 <= yy < 64:
                    px[xx, yy] = col

    # 1. Front Face
    rect(0, 0, 31, 31, skin_base)
    rect(0, 0, 31, 5, hair_main)
    rect(8, 0, 23, 3, hair_dark)
    rect(0, 0, 2, 12, hair_main)
    rect(29, 0, 31, 12, hair_main)
    rect(6, 6, 25, 9, skin_hi)
    rect(0, 28, 31, 31, skin_shade)
    rect(0, 22, 2, 31, skin_shade)
    rect(29, 22, 31, 31, skin_shade)

    rect(5, 10, 12, 11, brow_col)
    rect(19, 9, 26, 10, brow_col)
    px[26, 11] = brow_col

    for ex in (6, 20):
        rect(ex, 13, ex + 5, 16, eye_white)
        rect(ex + 1, 13, ex + 4, 16, eye_iris)
        rect(ex + 2, 14, ex + 3, 15, eye_pupil)
        px[ex + 1, 13] = eye_white
        rect(ex, 17, ex + 5, 17, skin_shade)

    rect(14, 15, 17, 20, skin_hi)
    rect(13, 20, 18, 21, skin_shade)

    rect(5, 22, 6, 25, skin_dimple)
    rect(25, 21, 26, 24, skin_dimple)
    rect(9, 23, 22, 24, lip_upper)
    rect(8, 24, 23, 25, teeth)
    px[8, 23] = mouth_corner
    px[23, 23] = mouth_corner
    px[24, 22] = mouth_corner
    rect(10, 26, 21, 27, lip_lower)
    rect(14, 29, 17, 30, skin_dimple)

    # 2. Backwards White Rolex Cap Front
    rect(32, 0, 63, 11, cap_white)
    rect(32, 9, 63, 11, cap_shade)
    rect(41, 3, 54, 11, hair_dark)
    rect(43, 2, 52, 4, hair_main)
    rect(40, 8, 55, 10, cap_white)
    rect(40, 10, 55, 11, cap_shade)
    rect(37, 6, 40, 10, rolex_green)
    px[38, 7] = gold_bright
    px[39, 7] = gold_bright
    px[38, 8] = gold_main
    px[39, 8] = gold_main

    # 3. Clean White Cap / Sneaker
    rect(32, 12, 47, 23, cap_white)
    rect(32, 21, 47, 23, cap_shade)

    # 4. Cropped Brown Buzzcut Hair
    rect(48, 12, 63, 23, hair_main)
    for yy in range(12, 24, 2):
        for xx in range(48 + (yy % 4 == 0), 64, 3):
            px[xx, yy] = hair_dark

    # 5. Warm Skin
    rect(32, 24, 47, 35, skin_base)
    rect(32, 33, 47, 35, skin_shade)

    # 6. Gold Chain & Rolex Watch
    rect(48, 24, 63, 35, gold_main)
    for yy in range(24, 36, 3):
        rect(48, yy, 63, yy, gold_bright)
        if yy + 2 < 36:
            rect(48, yy + 2, 63, yy + 2, gold_deep)
    rect(53, 27, 58, 32, gold_bright)
    rect(54, 28, 57, 31, rolex_green)
    px[55, 29] = gold_bright

    # 7. Black D&G Tropical + Crown Monogram Front Tee + V-shaped Cuban Gold Chain
    rect(0, 32, 23, 63, shirt_black)
    rect(5, 32, 18, 35, mono_light)
    rect(6, 33, 17, 34, shirt_dark)
    rect(8, 32, 15, 33, skin_base)
    rect(0, 32, 2, 36, mono_light)
    rect(21, 32, 23, 36, mono_light)
    for cy in range(37, 62, 5):
        for cx_ in range(2, 21, 5):
            px[cx_, cy + 1] = mono_mid
            px[cx_ + 1, cy] = mono_light
            px[cx_ + 2, cy + 1] = mono_mid
            px[cx_ + 1, cy + 1] = mono_light
    for dx in range(-5, 6):
        rect(11 + dx // 2, 42 + abs(dx), 13 + dx // 2, 58, leaf_deep)
    rect(8, 44, 15, 56, leaf_bright)
    rect(6, 49, 11, 59, leaf_deep)
    rect(13, 47, 18, 58, leaf_deep)
    rect(9, 45, 14, 49, flower_orange)
    rect(10, 44, 13, 46, flower_gold)
    rect(8, 53, 13, 57, flower_orange)
    rect(9, 52, 12, 54, flower_gold)
    for step_i in range(8):
        lx, rx_ = 6 + step_i // 2, 17 - step_i // 2
        yy = 34 + step_i
        rect(lx, yy, lx + 1, yy, gold_bright if step_i % 2 == 0 else gold_main)
        rect(rx_ - 1, yy, rx_, yy, gold_bright if step_i % 2 == 0 else gold_main)
    rect(10, 41, 13, 42, gold_bright)

    # 8. Black D&G Crown-Monogram Back/Sleeve
    rect(24, 36, 39, 63, shirt_black)
    rect(24, 36, 39, 37, mono_light)
    for cy in range(40, 62, 5):
        for cx_ in range(26, 38, 5):
            px[cx_, cy + 1] = mono_mid
            px[cx_ + 1, cy] = mono_light
            px[cx_ + 2, cy + 1] = mono_mid

    # 9. Black Pants + White/Gold Designer Sneakers
    rect(40, 36, 55, 55, shirt_dark)
    rect(40, 56, 55, 63, cap_white)
    rect(40, 58, 55, 59, gold_main)
    rect(40, 62, 55, 63, cap_shade)

    return img


def _render_ban_style_badge(text: str, seed_idx: int) -> Image.Image:
    """Renders a 64x20 pixel-art rounded badge matching the `D.Admin` sphere `BAN` aesthetic:
      - Gleaming gold (`#FFE26A` / `#E09B1B`) rounded 2px border
      - Rich ruby-crimson (`#8A1444` -> `#4E0925`) interior with subtle top highlight
      - Crisp snow-white (`#FFFFFF`) bitmap Cyrillic letters + `#280412` 1px drop shadow
      - Rising gold & pink pixel sparkles underneath (`y = 16..19`), transparent exterior!
    """
    badge = Image.new('RGBA', (64, 20), (0, 0, 0, 0))
    px = badge.load()

    gold_hi = (255, 232, 116, 255)
    gold_mid = (236, 178, 42, 255)
    gold_sh = (168, 108, 18, 255)
    ruby_top = (146, 24, 74, 255)
    ruby_mid = (114, 16, 56, 255)
    ruby_bot = (78, 10, 38, 255)
    pink_spark = (248, 190, 251, 255)
    text_white = (255, 255, 255, 255)
    text_shadow = (42, 5, 20, 255)

    # Measure text width with standard vs compact 7px bitmap font
    font = PIXEL_FONT_7
    glyphs = [font[ch] for ch in text]
    text_w = sum(len(g[0]) for g in glyphs) + max(0, len(glyphs) - 1)
    if text_w > 54:
        font = PIXEL_FONT_7_COMPACT
        glyphs = [font[ch] for ch in text]
        text_w = sum(len(g[0]) for g in glyphs) + max(0, len(glyphs) - 1)

    pad_x = 4
    box_w = min(62, max(text_w + pad_x * 2 + 2, 38))
    x0 = (64 - box_w) // 2
    x1 = x0 + box_w - 1
    y0, y1 = 1, 14  # 14px tall rounded badge + 5px underneath for sparkles

    # Rounded ruby interior + 2px gold border (chamfered corners like dadmin_ban.png!)
    for yy in range(y0, y1 + 1):
        for xx in range(x0, x1 + 1):
            dx = min(xx - x0, x1 - xx)
            dy = min(yy - y0, y1 - yy)
            if dx == 0 and dy <= 1:
                continue
            if dy == 0 and dx <= 1:
                continue
            is_border = (
                yy == y0 or yy == y1 or xx == x0 or xx == x1
                or (dx == 1 and dy == 1)
                or (dx <= 2 and dy == 1)
                or (dx == 1 and dy <= 2)
            )
            if is_border:
                px[xx, yy] = gold_hi if yy <= (y0 + y1) // 2 else (gold_sh if yy == y1 else gold_mid)
            else:
                px[xx, yy] = ruby_top if yy <= y0 + 3 else (ruby_mid if yy <= y1 - 4 else ruby_bot)

    # Subtle inner pink sheen on top row inside frame
    for xx in range(x0 + 3, x1 - 2):
        px[xx, y0 + 1] = (182, 42, 98, 255)

    # Draw drop shadow first, then crisp white bitmap letters centered in badge
    tx = (64 - text_w) // 2
    ty = y0 + 3
    cx_cursor = tx
    for g in glyphs:
        gw = len(g[0])
        for ry in range(7):
            for rx in range(gw):
                if g[ry][rx] == '#':
                    if cx_cursor + rx + 1 < x1 and ty + ry + 1 < y1:
                        px[cx_cursor + rx + 1, ty + ry + 1] = text_shadow
        cx_cursor += gw + 1

    cx_cursor = tx
    for g in glyphs:
        gw = len(g[0])
        for ry in range(7):
            for rx in range(gw):
                if g[ry][rx] == '#':
                    px[cx_cursor + rx, ty + ry] = text_white
        cx_cursor += gw + 1

    # Rising pixel sparkles below & beside the badge (matching dadmin_ban.png!)
    spark_offsets = (
        (-10, 16, gold_hi), (-6, 18, pink_spark), (-2, 16, ruby_top),
        (2, 17, gold_mid), (7, 16, pink_spark), (11, 18, gold_hi),
        (-14, 15, gold_mid), (14, 15, ruby_top),
    )
    for ox, sy, scol in spark_offsets:
        sx = 32 + ox + ((seed_idx % 3) - 1)
        if 1 <= sx < 63 and 0 <= sy < 20:
            px[sx, sy] = scol
    # Corner glint stars on top-left & top-right of gold frame
    if x0 - 1 >= 0:
        px[x0, y0 + 2] = (255, 250, 210, 255)
    if x1 + 1 < 64:
        px[x1, y0 + 2] = (255, 250, 210, 255)

    return badge


def build_mellstroy_texture() -> Image.Image:
    """128x128 RGBA texture atlas (UV 16x16 -> 8 PNG pixels per UV unit):
      - Top-left 64x64 (`UV [0..8, 0..8]`): Mellstroy body, Rolex cap, D&G shirt, chain & watch
      - Remaining transparent quadrants: 6 crisp 64x20 `D.Admin BAN`-style pop-up phrase badges!
    """
    atlas = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
    atlas.paste(_build_body_64(), (0, 0))
    for idx, (_bone, _anim, text, _dur, (bx, by), _style) in enumerate(PHRASE_SPECS):
        badge_img = _render_ban_style_badge(text, idx)
        atlas.paste(badge_img, (bx, by))
    return atlas


# ---------------------------------------------------------------------------
# 2. Blockbench 4.10 `free` Geometry, `idle` Loop & 6 `say_*` Badge Pop-Ups
# ---------------------------------------------------------------------------
# Body UVs (in 128x128 where top-left 64x64 is UV [0..8, 0..8])
UV_FACE_FRONT = [0.0, 0.0, 4.0, 4.0]
UV_CAP_FRONT = [4.0, 0.0, 8.0, 1.5]
UV_CAP_WHITE = [4.25, 1.75, 5.75, 2.75]
UV_HAIR = [6.25, 1.75, 7.75, 2.75]
UV_SKIN = [4.25, 3.25, 5.75, 4.25]
UV_GOLD = [6.0, 3.0, 8.0, 4.5]
UV_GOLD_PURE = [6.0, 3.0, 6.6, 3.4]
UV_SHIRT_FRONT = [0.0, 4.0, 3.0, 8.0]
UV_SHIRT_MONO = [3.0, 4.5, 5.0, 8.0]
UV_PANTS_SHOE = [5.0, 4.5, 7.0, 8.0]
UV_TRANSPARENT = [15.25, 7.25, 15.75, 7.75]


def _badge_uv(px_x: int, px_y: int) -> list:
    return [px_x / 8.0, px_y / 8.0, (px_x + 64) / 8.0, (px_y + 20) / 8.0]


def _faces(default_uv, north=None, south=None, up=None, down=None) -> dict:
    return {
        'north': {'uv': list(north or default_uv), 'texture': 0},
        'east':  {'uv': list(default_uv), 'texture': 0},
        'south': {'uv': list(south or default_uv), 'texture': 0},
        'west':  {'uv': list(default_uv), 'texture': 0},
        'up':    {'uv': list(up or default_uv), 'texture': 0},
        'down':  {'uv': list(down or default_uv), 'texture': 0},
    }


def _cube(name: str, low: list, high: list, origin: list, faces: dict, shade: bool = True) -> dict:
    cube = {
        'name': name,
        'box_uv': False,
        'rescale': False,
        'locked': False,
        'light_emission': 0,
        'render_order': 'default',
        'allow_mirror_modeling': True,
        'from': [round(v, 4) for v in low],
        'to': [round(v, 4) for v in high],
        'autouv': 0,
        'color': 0,
        'origin': [round(v, 4) for v in origin],
        'rotation': [0.0, 0.0, 0.0],
        'faces': faces,
        'type': 'cube',
        'uuid': uid(f'cube:{name}'),
    }
    if not shade:
        cube['shade'] = False
    return cube


def _bone(name: str, origin: list, cubes: list, children: list) -> dict:
    return {
        'name': name,
        'origin': [round(v, 4) for v in origin],
        'rotation': [0.0, 0.0, 0.0],
        'color': 0,
        'uuid': uid(f'bone:{name}'),
        'export': True,
        'mirror_uv': False,
        'isOpen': True,
        'locked': False,
        'visibility': True,
        'autouv': 0,
        'children': [c['uuid'] for c in cubes] + list(children),
    }


def _smooth_window(u: float, start: float, end: float, edge: float = 0.05) -> float:
    if u <= start or u >= end:
        return 0.0
    if u < start + edge:
        return 0.5 - 0.5 * math.cos(math.pi * (u - start) / edge)
    if u > end - edge:
        return 0.5 - 0.5 * math.cos(math.pi * (end - u) / edge)
    return 1.0


def eval_mellstroy_pose(u_norm: float, style: str = 'idle') -> dict:
    """Evaluates Mellstroy's 8-bone body choreography for `idle` or a `say_*` action."""
    u = u_norm % 1.0
    w1 = 2.0 * math.pi * u
    w4 = 4.0 * w1
    w8 = 8.0 * w1

    if style == 'idle':
        w_dada = _smooth_window(u, 0.02, 0.34, 0.05)
        w_net = _smooth_window(u, 0.34, 0.66, 0.05)
        w_svet = _smooth_window(u, 0.66, 0.98, 0.05)
    elif style in ('svet', 'tancuem'):
        env = _smooth_window(u, 0.0, 1.0, 0.12)
        w_dada, w_net, w_svet = 0.0, 0.0, env
    elif style in ('amam', 'miliciya'):
        env = _smooth_window(u, 0.0, 1.0, 0.12)
        w_dada, w_net, w_svet = 0.25 * env, 0.75 * env, 0.0
    else:  # 'voznya', 'babki' -> Rolex watch flex + hype nod!
        env = _smooth_window(u, 0.0, 1.0, 0.12)
        w_dada, w_net, w_svet = env, 0.0, 0.25 * env

    beat_hop = 0.36 * (0.5 - 0.5 * math.cos(w4)) + 0.34 * w_svet * (0.5 - 0.5 * math.cos(w8))
    sway_x = 0.28 * math.sin(w1 * 2.0)

    pelvis_rot = (
        3.0 * math.sin(w4),
        9.0 * math.sin(w1 * 2.0),
        5.0 * math.sin(w1 * 2.0),
    )
    torso_rot = (
        4.0 * w_dada * math.sin(w8) - 6.0 * w_svet,
        10.0 * math.sin(w1 * 2.0),
        -4.5 * math.sin(w1 * 2.0),
    )

    nod_pitch = -20.0 * w_dada * abs(math.sin(w4 * 1.5)) + 10.0 * w_svet
    shake_yaw = 25.0 * w_net * math.sin(w8 * 1.5) + 8.0 * math.sin(w1)
    head_tilt = 9.0 * w_svet * math.sin(w4) + 5.0 * w_dada
    head_rot = (nod_pitch, shake_yaw, head_tilt)

    r_arm_rx = (
        102.0 * w_dada
        + (62.0 + 38.0 * math.sin(w8)) * w_net
        + (148.0 + 12.0 * math.sin(w8)) * w_svet
        + 14.0 * max(0.0, 1.0 - w_dada - w_net - w_svet) * math.sin(w4)
    )
    r_arm_rz = -18.0 * w_dada - 10.0 * w_net + (-28.0 + 10.0 * math.sin(w4)) * w_svet
    r_arm_ry = -18.0 * w_dada + 8.0 * w_svet * math.cos(w4)

    l_arm_rx = (
        28.0 * w_dada * (0.5 + 0.5 * math.sin(w4))
        + (62.0 - 38.0 * math.sin(w8)) * w_net
        + (148.0 - 12.0 * math.sin(w8)) * w_svet
        - 14.0 * max(0.0, 1.0 - w_dada - w_net - w_svet) * math.sin(w4)
    )
    l_arm_rz = 10.0 * w_dada + 10.0 * w_net + (28.0 + 10.0 * math.sin(w4)) * w_svet
    l_arm_ry = 8.0 * w_dada - 8.0 * w_svet * math.cos(w4)

    step_wave = math.sin(w4)
    r_leg_rot = (22.0 * max(0.0, step_wave), 0.0, 3.0)
    l_leg_rot = (22.0 * max(0.0, -step_wave), 0.0, -3.0)

    return {
        'dancer_pos': (sway_x, beat_hop, 0.0),
        'pelvis_rot': pelvis_rot,
        'torso_rot': torso_rot,
        'head_rot': head_rot,
        'right_arm_rot': (r_arm_rx, r_arm_ry, r_arm_rz),
        'left_arm_rot': (l_arm_rx, l_arm_ry, l_arm_rz),
        'right_leg_rot': r_leg_rot,
        'left_leg_rot': l_leg_rot,
    }


def _vec_kf(channel: str, tag: str, t: float, vx: float, vy: float, vz: float) -> dict:
    return {
        'channel': channel,
        'data_points': [{'x': str(round(vx, 3)), 'y': str(round(vy, 3)), 'z': str(round(vz, 3))}],
        'uuid': uid(f'kf:{channel}:{tag}:{round(t, 4)}'),
        'time': round(t, 4),
        'color': -1,
        'interpolation': 'linear',
    }


def _body_animators(anim_tag: str, length: float, steps: int, style: str, seamless_loop: bool) -> dict:
    poses = [eval_mellstroy_pose(step / steps, style=style) for step in range(steps + 1)]

    def rot_kfs(bone_name: str, key: str) -> list:
        kfs = []
        for s in range(steps + 1):
            t = length * s / steps
            rx, ry, rz = poses[s][key]
            kfs.append(_vec_kf('rotation', f'{anim_tag}:{bone_name}', t, -rx, -ry, rz))
        if seamless_loop:
            kfs[-1]['data_points'] = [dict(p) for p in kfs[0]['data_points']]
        return kfs

    def pos_kfs(bone_name: str, key: str) -> list:
        kfs = []
        for s in range(steps + 1):
            t = length * s / steps
            dx, dy, dz = poses[s][key]
            kfs.append(_vec_kf('position', f'{anim_tag}:{bone_name}', t, -dx, dy, dz))
        if seamless_loop:
            kfs[-1]['data_points'] = [dict(p) for p in kfs[0]['data_points']]
        return kfs

    return {
        uid('bone:dancer'):    {'name': 'dancer',    'type': 'bone', 'keyframes': pos_kfs('dancer', 'dancer_pos')},
        uid('bone:pelvis'):    {'name': 'pelvis',    'type': 'bone', 'keyframes': rot_kfs('pelvis', 'pelvis_rot')},
        uid('bone:torso'):     {'name': 'torso',     'type': 'bone', 'keyframes': rot_kfs('torso', 'torso_rot')},
        uid('bone:head'):      {'name': 'head',      'type': 'bone', 'keyframes': rot_kfs('head', 'head_rot')},
        uid('bone:right_arm'): {'name': 'right_arm', 'type': 'bone', 'keyframes': rot_kfs('right_arm', 'right_arm_rot')},
        uid('bone:left_arm'):  {'name': 'left_arm',  'type': 'bone', 'keyframes': rot_kfs('left_arm', 'left_arm_rot')},
        uid('bone:right_leg'): {'name': 'right_leg', 'type': 'bone', 'keyframes': rot_kfs('right_leg', 'right_leg_rot')},
        uid('bone:left_leg'):  {'name': 'left_leg',  'type': 'bone', 'keyframes': rot_kfs('left_leg', 'left_leg_rot')},
    }


def _active_badge_keyframes(anim_tag: str, bone_name: str, length: float, steps: int) -> list:
    """`D.Admin BAN`-style elastic pop-in -> floating gently upward & rocking -> flash-pop -> vanish!"""
    kfs = []
    for s in range(steps + 1):
        u = s / steps
        t = length * u
        if s == 0 or s == steps:
            sc = 0.0
            dy = -0.8 if s == 0 else 1.25
            ry, rz = 0.0, 0.0
        else:
            pop_in = min(1.0, t / 0.16)
            pop_out = min(1.0, (length - t) / 0.18)
            overshoot = 1.20 if 0.12 <= t <= 0.22 else (1.08 if (length - 0.26) <= t <= (length - 0.16) else 1.0)
            pulse = 1.0 + 0.04 * math.sin(2.0 * math.pi * 2.0 * u)
            sc = round(min(pop_in, pop_out) * overshoot * pulse, 3)
            dy = -0.35 + 1.55 * u + 0.18 * math.sin(2.0 * math.pi * 3.0 * u)
            ry = 9.0 * math.sin(2.0 * math.pi * 2.0 * u)
            rz = 4.0 * math.sin(2.0 * math.pi * 3.0 * u)
        kfs.append(_vec_kf('scale', f'{anim_tag}:{bone_name}', t, sc, sc, sc))
        kfs.append(_vec_kf('position', f'{anim_tag}:{bone_name}', t, 0.0, dy, 0.0))
        kfs.append(_vec_kf('rotation', f'{anim_tag}:{bone_name}', t, 0.0, -ry, rz))
    return kfs


def _hidden_badge_keyframes(anim_tag: str, bone_name: str, length: float) -> list:
    return [
        _vec_kf('scale', f'{anim_tag}:{bone_name}', 0.0, 0.0, 0.0, 0.0),
        _vec_kf('scale', f'{anim_tag}:{bone_name}', length, 0.0, 0.0, 0.0),
    ]


def build_animations() -> list:
    # 1. Default continuous dance loop (`idle`): all 6 pop-up badges stay at scale [0, 0, 0]
    idle_animators = _body_animators('idle', ANIM_LENGTH, ANIM_STEPS, 'idle', seamless_loop=True)
    for b_name, *_ in PHRASE_SPECS:
        idle_animators[uid(f'bone:{b_name}')] = {
            'name': b_name,
            'type': 'bone',
            'keyframes': _hidden_badge_keyframes('idle', b_name, ANIM_LENGTH),
        }
    clips = [{
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
        'animators': idle_animators,
    }]

    # 2. Six higher-priority (`override: true`, `loop: once`) phrase animations!
    for active_bone, anim_name, _text, duration, _xy, style in PHRASE_SPECS:
        steps = max(20, int(round(duration * 20)))
        animators = _body_animators(anim_name, duration, steps, style, seamless_loop=True)
        for b_name, *_ in PHRASE_SPECS:
            kfs = (
                _active_badge_keyframes(anim_name, b_name, duration, steps)
                if b_name == active_bone
                else _hidden_badge_keyframes(anim_name, b_name, duration)
            )
            animators[uid(f'bone:{b_name}')] = {
                'name': b_name,
                'type': 'bone',
                'keyframes': kfs,
            }
        clips.append({
            'uuid': uid(f'animation:{anim_name}'),
            'name': anim_name,
            'loop': 'once',
            'override': True,
            'length': duration,
            'snapping': 20,
            'selected': False,
            'anim_time_update': '',
            'blend_weight': '',
            'start_delay': '',
            'loop_delay': '',
            'animators': animators,
        })
    return clips


def build_blueprint():
    texture = build_mellstroy_texture()
    raw = io.BytesIO()
    texture.save(raw, format='PNG', optimize=True)

    pelvis_orig = _pt(0.0, 12.0, 0.0)
    torso_orig = _pt(0.0, 12.0, 0.0)
    head_orig = _pt(0.0, 24.0, 0.0)
    r_arm_orig = _pt(6.0, 22.8, 0.0)
    l_arm_orig = _pt(-6.0, 22.8, 0.0)
    r_leg_orig = _pt(2.0, 12.0, 0.0)
    l_leg_orig = _pt(-2.0, 12.0, 0.0)
    badge_orig = _pt(0.0, 35.8, 0.0)

    c_head = _cube(
        'head_cube',
        _pt(-4.0, 24.0, -4.0),
        _pt(4.0, 32.0, 4.0),
        head_orig,
        _faces(UV_SKIN, north=UV_FACE_FRONT, south=UV_HAIR, up=UV_HAIR, down=UV_SKIN),
    )
    c_cap_crown = _cube(
        'cap_crown',
        _pt(-4.35, 28.6, -4.35),
        _pt(4.35, 32.55, 4.35),
        head_orig,
        _faces(UV_CAP_WHITE, north=UV_CAP_FRONT, up=UV_CAP_WHITE),
    )
    c_cap_brim = _cube(
        'cap_brim',
        _pt(-3.6, 28.6, 4.25),
        _pt(3.6, 29.55, 7.65),
        head_orig,
        _faces(UV_CAP_WHITE),
    )

    c_torso = _cube(
        'torso_cube',
        _pt(-4.0, 12.0, -2.0),
        _pt(4.0, 24.0, 2.0),
        torso_orig,
        _faces(UV_SHIRT_MONO, north=UV_SHIRT_FRONT, south=UV_SHIRT_MONO, up=UV_SHIRT_MONO, down=UV_SHIRT_MONO),
    )
    c_chain = _cube(
        'gold_chain_cube',
        _pt(-0.85, 18.2, -2.35),
        _pt(0.85, 20.1, -1.98),
        torso_orig,
        _faces(UV_GOLD_PURE),
    )

    c_r_sleeve = _cube(
        'right_sleeve_cube',
        _pt(3.95, 19.2, -2.15),
        _pt(8.15, 24.1, 2.15),
        r_arm_orig,
        _faces(UV_SHIRT_MONO),
    )
    c_r_arm = _cube(
        'right_arm_cube',
        _pt(4.1, 12.0, -1.9),
        _pt(7.9, 19.4, 1.9),
        r_arm_orig,
        _faces(UV_SKIN),
    )
    c_rolex = _cube(
        'rolex_watch_cube',
        _pt(3.9, 13.6, -2.12),
        _pt(8.1, 15.1, 2.12),
        r_arm_orig,
        _faces(UV_GOLD),
    )

    c_l_sleeve = _cube(
        'left_sleeve_cube',
        _pt(-8.15, 19.2, -2.15),
        _pt(-3.95, 24.1, 2.15),
        l_arm_orig,
        _faces(UV_SHIRT_MONO),
    )
    c_l_arm = _cube(
        'left_arm_cube',
        _pt(-7.9, 12.0, -1.9),
        _pt(-4.1, 19.4, 1.9),
        l_arm_orig,
        _faces(UV_SKIN),
    )

    c_r_leg = _cube(
        'right_leg_cube',
        _pt(0.05, 0.0, -2.0),
        _pt(3.95, 12.0, 2.0),
        r_leg_orig,
        _faces(UV_PANTS_SHOE, down=UV_CAP_WHITE),
    )
    c_l_leg = _cube(
        'left_leg_cube',
        _pt(-3.95, 0.0, -2.0),
        _pt(-0.05, 12.0, 2.0),
        l_leg_orig,
        _faces(UV_PANTS_SHOE, down=UV_CAP_WHITE),
    )

    # 6 `D.Admin BAN`-style unshaded (`shade: false`) 3D pixel-art pop-up badges above Mellstroy!
    badge_cubes = []
    badge_bones = []
    for b_name, _anim, _text, _dur, (px_x, px_y), _style in PHRASE_SPECS:
        buv = _badge_uv(px_x, px_y)
        c_badge = _cube(
            f'{b_name}_cube',
            _pt(-11.2, 33.2, -0.15),
            _pt(11.2, 40.2, 0.15),
            badge_orig,
            _faces(UV_TRANSPARENT, north=buv, south=buv),
            shade=False,
        )
        badge_cubes.append(c_badge)
        badge_bones.append(_bone(b_name, badge_orig, [c_badge], []))

    head_cubes = [c_head, c_cap_crown, c_cap_brim]
    torso_cubes = [c_torso, c_chain]
    r_arm_cubes = [c_r_sleeve, c_r_arm, c_rolex]
    l_arm_cubes = [c_l_sleeve, c_l_arm]
    elements = head_cubes + torso_cubes + r_arm_cubes + l_arm_cubes + [c_r_leg, c_l_leg] + badge_cubes

    b_head = _bone('head', head_orig, head_cubes, [])
    b_r_arm = _bone('right_arm', r_arm_orig, r_arm_cubes, [])
    b_l_arm = _bone('left_arm', l_arm_orig, l_arm_cubes, [])
    b_torso = _bone('torso', torso_orig, torso_cubes, [b_head, b_r_arm, b_l_arm])
    b_r_leg = _bone('right_leg', r_leg_orig, [c_r_leg], [])
    b_l_leg = _bone('left_leg', l_leg_orig, [c_l_leg], [])
    b_pelvis = _bone('pelvis', pelvis_orig, [], [b_torso, b_r_leg, b_l_leg])
    b_dancer = _bone('dancer', [CX, FEET_Y, CZ], [], [b_pelvis])
    b_root = _bone('body_root', [0.0, 0.0, 0.0], [], [b_dancer] + badge_bones)

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

    blueprint = {
        'meta': {'format_version': '4.10', 'model_format': 'free', 'box_uv': False},
        'name': MODEL,
        'model_identifier': MODEL,
        'visible_box': [3, 4, 0],
        'variable_placeholders': '',
        'variable_placeholder_buttons': [],
        'timeline_setups': [],
        'unhandled_root_fields': {},
        'resolution': {'width': 16, 'height': 16},
        'elements': elements,
        'outliner': [b_root],
        'textures': [texture_entry],
        'animations': build_animations(),
    }
    return blueprint, texture


# ---------------------------------------------------------------------------
# 3. Hand-Crafted 32x32 Pixel-Art Menu Icon (`reallyworld:mellstroy_icon`)
# ---------------------------------------------------------------------------
def build_mellstroy_icon() -> Image.Image:
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    outline = (26, 22, 34, 255)
    cap_w = (245, 248, 252, 255)
    cap_s = (210, 218, 228, 255)
    rolex_g = (22, 132, 74, 255)
    hair = (112, 82, 58, 255)
    skin = (246, 206, 184, 255)
    skin_s = (220, 172, 148, 255)
    eye_b = (72, 118, 152, 255)
    white = (255, 255, 255, 255)
    lip = (196, 98, 104, 255)
    tee = (22, 24, 32, 255)
    gold = (252, 206, 62, 255)
    gold_hi = (255, 238, 132, 255)
    leaf = (42, 192, 86, 255)
    orange = (252, 126, 36, 255)

    def rect(x0, y0, x1, y1, col):
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if 0 <= xx < 32 and 0 <= yy < 32:
                    px[xx, yy] = col

    rect(8, 4, 22, 9, cap_w)
    rect(10, 3, 20, 4, cap_w)
    rect(22, 7, 25, 9, cap_s)
    rect(12, 5, 18, 8, hair)
    rect(11, 8, 19, 8, cap_w)
    rect(9, 7, 10, 8, rolex_g)
    px[10, 7] = gold_hi

    rect(8, 9, 22, 18, skin)
    rect(9, 19, 21, 19, skin_s)
    rect(10, 10, 13, 10, hair)
    rect(17, 9, 20, 9, hair)
    rect(10, 12, 12, 13, white)
    rect(11, 12, 12, 13, eye_b)
    rect(18, 12, 20, 13, white)
    rect(18, 12, 19, 13, eye_b)
    rect(11, 16, 19, 17, lip)
    rect(11, 16, 19, 16, white)
    px[20, 15] = lip

    rect(7, 20, 23, 29, tee)
    rect(11, 20, 19, 20, cap_w)
    rect(12, 24, 18, 29, leaf)
    rect(13, 25, 16, 27, orange)
    for xx, yy in ((11, 21), (11, 22), (12, 23), (13, 24), (14, 25), (15, 25), (16, 25), (17, 24), (18, 23), (19, 22), (19, 21)):
        px[xx, yy] = gold
    px[15, 26] = gold_hi

    rect(4, 16, 6, 23, skin)
    rect(4, 22, 7, 25, tee)
    rect(4, 19, 6, 20, gold)
    px[5, 19] = gold_hi

    orig = img.copy()
    opx = orig.load()
    for yy in range(1, 31):
        for xx in range(1, 31):
            if opx[xx, yy][3] == 0:
                if any(opx[xx + dx, yy + dy][3] > 0 for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                    px[xx, yy] = outline

    for xx, yy in (
        (27, 2),
        (26, 3), (27, 3), (28, 3),
        (25, 4), (27, 4),
        (26, 5), (27, 5), (28, 5),
        (27, 6), (29, 6),
        (26, 7), (27, 7), (28, 7),
        (27, 8),
    ):
        px[xx, yy] = gold_hi if yy <= 4 else gold
    for yy in range(1, 10):
        for xx in range(24, 31):
            if px[xx, yy][3] == 0:
                if any(0 <= xx + dx < 32 and 0 <= yy + dy < 32 and px[xx + dx, yy + dy] in (gold, gold_hi)
                       for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                    px[xx, yy] = outline

    return img


# ---------------------------------------------------------------------------
# 4. Preview Sheet Renderer (`mellstroy_preview.png`)
# ---------------------------------------------------------------------------
def render_preview(blueprint: dict, texture: Image.Image, icon: Image.Image, out_path: Path):
    panel_w, panel_h = 228, 286
    canvas = Image.new('RGBA', (panel_w * 5, panel_h), (20, 22, 30, 255))
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

    # 3 action poses WITH floating 3D `D.Admin BAN`-style badges + 1 idle back view (no badge)!
    views = [
        (0.50, 14.0,  'voznya', 'badge_voznya_cube'),
        (0.50, -12.0, 'amam',   'badge_amam_cube'),
        (0.50, 10.0,  'svet',   'badge_svet_cube'),
        (0.16, 162.0, 'idle',   None),
    ]

    for idx, (u, cam_yaw, style, active_badge_cube) in enumerate(views):
        pose = eval_mellstroy_pose(u, style=style)
        ox0 = idx * panel_w

        def proj(pt, _ang=math.radians(cam_yaw), _ox=ox0):
            dx = pt[0] - CX
            dz = pt[2] - CZ
            xw = dx * math.cos(_ang) - dz * math.sin(_ang)
            zw = dx * math.sin(_ang) + dz * math.cos(_ang)
            yw = pt[1] - 0.14 * zw
            return (_ox + 114.0 - xw * 14.8, 254.0 - (yw - FEET_Y) * 14.8, zw)

        faces_to_draw = []
        sh_low, sh_high = [-8.0, 16.0, -2.0], [-4.0, 24.0, 2.0]
        if idx < 3:
            cs = [np.array([sh_low[0], sh_low[1], sh_low[2]]), np.array([sh_high[0], sh_low[1], sh_low[2]]),
                  np.array([sh_high[0], sh_high[1], sh_low[2]]), np.array([sh_low[0], sh_high[1], sh_low[2]]),
                  np.array([sh_low[0], sh_low[1], sh_high[2]]), np.array([sh_high[0], sh_low[1], sh_high[2]]),
                  np.array([sh_high[0], sh_high[1], sh_high[2]]), np.array([sh_low[0], sh_high[1], sh_high[2]])]
            for idxs, sm in (((2, 1, 0, 3), 1.0), ((7, 6, 2, 3), 1.08), ((3, 0, 4, 7), 0.85)):
                p2d = [proj(cs[k]) for k in idxs]
                cross = (p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1]) - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0])
                if cross <= 0:
                    col = tuple(int(c * sm) for c in (54, 60, 82)) + (255,)
                    faces_to_draw.append((sum(p[2] for p in p2d) / 4.0 + 4.0, [(s[0], s[1]) for s in p2d], col, (38, 42, 58, 255)))

        def add_cube(cname, tf_fn, subdiv_x=0, subdiv_y=0):
            el = by_name[cname]
            x0, y0, z0 = el['from']
            x1, y1, z1 = el['to']
            cs = [np.array([x0, y0, z0]), np.array([x1, y0, z0]), np.array([x1, y1, z0]), np.array([x0, y1, z0]),
                  np.array([x0, y0, z1]), np.array([x1, y0, z1]), np.array([x1, y1, z1]), np.array([x0, y1, z1])]
            wcs = [tf_fn(c) for c in cs]
            unshaded = el.get('shade') is False
            quads = [
                ('north', (2, 1, 0, 3), 1.00),
                ('south', (7, 4, 5, 6), 1.00 if unshaded else 0.82),
                ('east',  (6, 5, 1, 2), 0.90),
                ('west',  (3, 0, 4, 7), 0.88),
                ('up',    (7, 6, 2, 3), 1.02),
                ('down',  (0, 1, 5, 4), 0.76),
            ]
            for fname, idxs, sm in quads:
                pts3 = [wcs[k] for k in idxs]
                p2d = [proj(p) for p in pts3]
                cross = (p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1]) - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0])
                if cross > 0:
                    continue
                z_avg = sum(p[2] for p in p2d) / 4.0
                uv = el['faces'][fname]['uv']
                if subdiv_x and fname in ('north', 'south', 'east', 'west'):
                    nx = subdiv_x
                    ny = subdiv_y or subdiv_x
                    p_tl, p_bl, p_br, p_tr = pts3
                    for gy in range(ny):
                        for gx in range(nx):
                            u0, u1 = gx / nx, (gx + 1) / nx
                            v0, v1 = gy / ny, (gy + 1) / ny
                            tx = min(127, int((uv[0] + (uv[2] - uv[0]) * (u0 + 0.5 / nx)) * 8))
                            ty = min(127, int((uv[1] + (uv[3] - uv[1]) * (v0 + 0.5 / ny)) * 8))
                            rgba = tex_arr[ty, tx]
                            if rgba[3] < 24:
                                continue
                            col = tuple(min(255, int(c * sm)) for c in rgba[:3]) + (int(rgba[3]),)
                            def bilerp(uu, vv):
                                top = p_tl * (1 - uu) + p_tr * uu
                                bot = p_bl * (1 - uu) + p_br * uu
                                return top * (1 - vv) + bot * vv
                            sub = [proj(bilerp(u0, v0)), proj(bilerp(u0, v1)), proj(bilerp(u1, v1)), proj(bilerp(u1, v0))]
                            faces_to_draw.append((z_avg - 0.01, [(s[0], s[1]) for s in sub], col, None))
                else:
                    tx = min(127, int(0.5 * (uv[0] + uv[2]) * 8))
                    ty = min(127, int(0.5 * (uv[1] + uv[3]) * 8))
                    rgba = tex_arr[ty, tx]
                    if rgba[3] < 24:
                        continue
                    col = tuple(min(255, int(c * sm)) for c in rgba[:3]) + (int(rgba[3]),)
                    faces_to_draw.append((z_avg, [(s[0], s[1]) for s in p2d], col, (48, 50, 64, 160)))

        d_pos = np.array(pose['dancer_pos'])
        pelvis_o = np.array(_pt(0.0, 12.0, 0.0))
        m_pelvis = rot_mat(*pose['pelvis_rot'])
        tf_pelvis = lambda p: pelvis_o + d_pos + m_pelvis @ (p - pelvis_o)

        def child_tf(parent_tf, orig, angles):
            o = np.array(orig)
            m = rot_mat(*angles)
            return lambda p: parent_tf(o + m @ (p - o))

        tf_torso = child_tf(tf_pelvis, _pt(0.0, 12.0, 0.0), pose['torso_rot'])
        tf_head = child_tf(tf_torso, _pt(0.0, 24.0, 0.0), pose['head_rot'])
        tf_ra = child_tf(tf_torso, _pt(6.0, 22.8, 0.0), pose['right_arm_rot'])
        tf_la = child_tf(tf_torso, _pt(-6.0, 22.8, 0.0), pose['left_arm_rot'])
        tf_rl = child_tf(tf_pelvis, _pt(2.0, 12.0, 0.0), pose['right_leg_rot'])
        tf_ll = child_tf(tf_pelvis, _pt(-2.0, 12.0, 0.0), pose['left_leg_rot'])

        add_cube('torso_cube', tf_torso, subdiv_x=12)
        add_cube('gold_chain_cube', tf_torso, subdiv_x=6)
        add_cube('head_cube', tf_head, subdiv_x=16)
        add_cube('cap_crown', tf_head, subdiv_x=12)
        add_cube('cap_brim', tf_head)
        add_cube('right_sleeve_cube', tf_ra, subdiv_x=6)
        add_cube('right_arm_cube', tf_ra)
        add_cube('rolex_watch_cube', tf_ra, subdiv_x=6)
        add_cube('left_sleeve_cube', tf_la, subdiv_x=6)
        add_cube('left_arm_cube', tf_la)
        add_cube('right_leg_cube', tf_rl, subdiv_x=10)
        add_cube('left_leg_cube', tf_ll, subdiv_x=10)

        if active_badge_cube is not None:
            badge_o = np.array(_pt(0.0, 35.8, 0.0))
            m_badge = rot_mat(0.0, -3.0, 2.5)
            tf_badge = lambda p, _bo=badge_o, _mb=m_badge: _bo + np.array([0.0, 0.45, 0.0]) + _mb @ (p - _bo)
            add_cube(active_badge_cube, tf_badge, subdiv_x=64, subdiv_y=20)

        faces_to_draw.sort(key=lambda item: -item[0])
        for _, poly, fill_col, edge_col in faces_to_draw:
            draw.polygon(poly, fill=fill_col, outline=edge_col)

    # Panel 5: Zoomed 32x32 icon + all 6 crisp 64x20 `D.Admin BAN`-style pop-up badges!
    ox4 = 4 * panel_w
    canvas.alpha_composite(icon.resize((72, 72), Image.NEAREST), (ox4 + 78, 6))
    for i, (_bone, _anim, _text, _dur, (bx, by), _style) in enumerate(PHRASE_SPECS):
        b_crop = texture.crop((bx, by, bx + 64, by + 20)).resize((128, 40), Image.NEAREST)
        canvas.alpha_composite(b_crop, (ox4 + 50, 82 + i * 33))
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
    parser.add_argument('--preview', default=str(HERE / 'mellstroy_preview.png'))
    args = parser.parse_args()

    blueprint, texture = build_blueprint()
    bb_path = Path(args.out_bbmodel)
    bb_path.write_text(json.dumps(blueprint, indent=2) + '\n', encoding='utf-8')
    texture.save(HERE / f'{MODEL}.png', optimize=True)

    assets_dir = Path(args.out_assets)
    icon = build_mellstroy_icon()
    write_icon_assets(icon, assets_dir)
    render_preview(blueprint, texture, icon, Path(args.preview))

    print(f'Built {bb_path.name}: {len(blueprint["elements"])} cubes, '
          f'{len(blueprint["animations"])} animations, '
          f'icon -> {assets_dir}')


if __name__ == '__main__':
    main()
