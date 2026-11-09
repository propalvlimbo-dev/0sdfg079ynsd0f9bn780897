#!/usr/bin/env python3
"""Процедурно строит 3D-ауру «Смертельная аура» (`elytrix_death_aura`), её иконку
32x32 (`reallyworld:death_aura_icon`) и превью для проверки.

100% чистый процедурный Python + Pillow + NumPy — ноль нейрогенерации.

  1. Визуальный замысел — «СТРАШНАЯ АУРА: из-под ног всё время летит пепел»:
       - Вокруг игрока по кольцу (радиус `10.6..12.6` BB) поднимается поток из
         **10 пепельных хлопьев** `ash_01..ash_10`. Каждое рождается ПОД ногами
         (`Y = -2.0`, ниже подошвы `Y = 0.00`), плывёт вверх до своей высоты
         (`Y = 28.0..33.5`) и там рассыпается.
       - Хлопье = 4 куба: два серых пепельных лоскута (со сдвигом, чтобы силуэт
         был рваным), один ТЛЕЮЩИЙ УГОЛЁК над ними и копоть-хвост под ними.
         Уголёк даёт «страшность»: в сером пепле вспыхивают оранжевые точки.
       - Движение НЕ спиралью: монотонного обхода кольца нет вообще. У каждого
         хлопья свои ПСЕВДОСЛУЧАЙНЫЕ скорость подъёма, профиль разгона, высота
         рассыпания, радиус, фаза и набор ЦЕЛЫХ частот болтания. Целые частоты
         держат цикл бесшовным, а выглядит как живой разнобой.
       - Хлопья КУВЫРКАЮТСЯ: вращение по всем трём осям на целое число оборотов
         за цикл (`nx/ny/nz` целые), поэтому стык цикла остаётся бесшовным.
       - Появление и исчезание сделаны через `scale` (всплытие `0 -> 1` у самого
         низа и рассыпание `1 -> 0` у самого верха) плюс невидимое окно
         `scale = 0` на стыке цикла. Поэтому интерполяция ModelEngine НИКОГДА не
         протаскивает пепел сверху вниз.
  2. Инженерная безопасность:
       - **Ни одного повёрнутого куба** (`RotationSolver` ModelEngine 4.1.0 падает).
       - Каждая кость `ash_NN` имеет пивот В ЦЕНТРЕ своего хлопья, вся геометрия
         запечена вокруг него. Дальний ход делает анимация позиции.
       - «Дыхание» радиуса — ТОЛЬКО НАРУЖУ, поэтому хлопье никогда не задевает
         игрока (габарит `|x| <= 7.5`, `|z| <= 3.75` BB).
       - Всего **11 костей и 40 кубов** — намеренно легко, чтобы не грузить сеть
         (жалоба на «телепорты» ауры: чем меньше костей-сущностей, тем ровнее
         анимация при просадках TPS).
       - `16.0` BB = `1.0` блок: стопы `0.00`, талия `11.25`, шея/плечи `22.50`,
         макушка `30.00`, глаза `25.92`, `+Z` — спина игрока.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import math
import random
import sys
import uuid
from pathlib import Path

sys.path.insert(0, '/tmp/pytools')
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = 'elytrix_death_aura'
ICON = 'death_aura_icon'

IDLE_LEN = 6.0        # 120 ticks @ 20 TPS — полный цикл подъёма одного хлопья
IDLE_STEPS = 120      # 20 keyframes/s — как и во всех остальных моделях пака

ROOT_ORIG = [0.0, 16.0, 0.0]   # середина пути: геометрия запечена здесь, дальше ходит анимация

ASH_COUNT = 10
Y_LOW = -2.0          # ниже подошвы — «из-под ног»
TAU = 2.0 * math.pi

RISE_MIN, RISE_MAX = 0.60, 0.84    # доля цикла на подъём (своя скорость у каждого)
Y_TOP_MIN, Y_TOP_MAX = 28.0, 33.5  # где именно хлопье рассыпается
R_MIN, R_MAX = 11.2, 13.2          # радиус колонны (всегда вне габарита игрока)
GROW = 0.07                        # доля цикла на «всплытие» снизу
CRUMBLE = 0.14                     # доля цикла на рассыпание сверху

_BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))

# 0..16 UV, текстура 64x64 => 1 UV = 4 px, тайлы 32x32 px = 8x8 UV.
UV_ASH = (0.25, 0.25, 7.75, 7.75)        # серый пепел
UV_ASH_EDGE = (8.25, 0.25, 15.75, 7.75)  # тёмные торцы пепла
UV_EMBER = (0.25, 8.25, 7.75, 15.75)     # тлеющий уголёк (радиальный)
UV_SOOT = (8.25, 8.25, 15.75, 15.75)     # копоть-хвост

ASH_IDS = [f'ash_{i + 1:02d}' for i in range(ASH_COUNT)]
BONE_NAMES = ['aura_root'] + ASH_IDS


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f'elytrix.death_aura.v1:{tag}'))


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
            return tuple(int(round(c0[j] + (c1[j] - c0[j]) * k)) for j in range(3))
    return stops[-1][1]


# ---------------------------------------------------------------------------
# 1. Текстура 64x64 — гладкие градиенты, без полос
# ---------------------------------------------------------------------------
def build_death_texture() -> Image.Image:
    arr = np.zeros((64, 64, 4), dtype=np.uint8)

    def paint(tx: int, ty: int, fn) -> None:
        ox, oy = tx * 32, ty * 32
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

    def wob(px: int, py: int) -> float:
        return (0.045 * math.sin(px * 0.23 + py * 0.17)
                + 0.035 * math.sin(px * 0.11 - py * 0.19))

    # (0,0) пепел: светло-серый -> тёмный уголь (по Y — объёмная тень)
    paint(0, 0, lambda px, py: _ramp(
        [(0.00, (176, 172, 178)), (0.42, (104, 100, 108)), (1.00, (42, 40, 48))],
        py / 31.0 + wob(px, py)))
    # (32,0) торцы пепла — ещё темнее
    paint(1, 0, lambda px, py: _ramp(
        [(0.00, (128, 124, 132)), (0.45, (72, 68, 78)), (1.00, (24, 22, 30))],
        py / 31.0 + wob(px, py)))
    # (0,32) тлеющий уголёк: радиальный белый -> жёлтый -> оранжевый -> тёмно-красный
    paint(0, 1, lambda px, py: _ramp(
        [(0.00, (255, 246, 214)), (0.28, (255, 196, 92)),
         (0.62, (232, 108, 26)), (1.00, (104, 22, 10))],
        min(1.0, math.hypot(px - 15.5, py - 15.5) / 17.0 + wob(px, py) * 1.4)))
    # (32,32) копоть: почти чёрная с тёплым отливом в центре
    paint(1, 1, lambda px, py: _ramp(
        [(0.00, (86, 62, 58)), (0.40, (40, 34, 38)), (1.00, (14, 12, 16))],
        min(1.0, math.hypot(px - 15.5, py - 15.5) / 19.0 + wob(px, py))))

    return Image.fromarray(arr, 'RGBA')


# ---------------------------------------------------------------------------
# 2. Кубы (НИ ОДИН не повёрнут)
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
        'inflate': 0.0,
        'mirror_uv': False,
        'rotation': [0.0, 0.0, 0.0],
        'origin': list(origin),
        'faces': faces,
        'uuid': uid(f'cube:{name}'),
        'type': 'cube',
    }


# ---------------------------------------------------------------------------
# 3. Геометрия: 10 хлопьев, запечённых в центре своего пути
# ---------------------------------------------------------------------------
# Локальный силуэт хлопья (в BB до масштаба): два рваных лоскута + уголёк + копоть.
FLAKES = (
    ('flake_a', (-0.55, -0.30, -0.30), (0.05, 0.15, 0.30), UV_ASH),
    ('flake_b', (0.05, -0.10, -0.22), (0.70, 0.35, 0.22), UV_ASH),
    ('ember', (-0.22, 0.30, -0.22), (0.22, 0.62, 0.22), UV_EMBER),
    ('soot', (-0.12, -0.62, -0.12), (0.30, -0.30, 0.12), UV_SOOT),
)


def ash_spec(i: int) -> dict:
    """Псевдослучайные параметры хлопья `i` (0-based). Детерминировано."""
    rnd = random.Random(4421 + i * 6151)
    return {
        'ang': (i / ASH_COUNT) * TAU + rnd.uniform(-0.45, 0.45),
        'r': rnd.uniform(R_MIN, R_MAX),
        'scale': 0.80 + 0.42 * (((i * 5) % 5) / 4.0),        # 0.80 .. 1.22
        'phase': ((i + rnd.uniform(-0.45, 0.45)) / ASH_COUNT) % 1.0,
        'rise': rnd.uniform(RISE_MIN, RISE_MAX),
        'y_top': rnd.uniform(Y_TOP_MIN, Y_TOP_MAX),
        'pow': rnd.uniform(0.85, 1.25),
        'at': rnd.uniform(0.85, 1.95),      # касательная качка, BB
        'ar': rnd.uniform(0.35, 0.95),      # «дыхание» радиуса, только наружу
        'ab': rnd.uniform(0.22, 0.58),      # вертикальное покачивание, BB
        'nt1': rnd.choice((2, 3, 4)), 'nt2': rnd.choice((5, 6, 7)),
        'nr': rnd.choice((1, 2, 3)), 'nb': rnd.choice((2, 3, 4)),
        # кувыркание: ЦЕЛОЕ число оборотов за цикл по каждой оси
        'nx': rnd.choice((1, 2)), 'ny': rnd.choice((1, 2, 3)), 'nz': rnd.choice((1, 2)),
        'pt1': rnd.random(), 'pt2': rnd.random(),
        'pr': rnd.random(), 'pb': rnd.random(),
        'px': rnd.random(), 'py': rnd.random(), 'pz': rnd.random(),
    }


ASH_SPECS = [ash_spec(i) for i in range(ASH_COUNT)]


def build_geometry(elements: list) -> dict:
    bones: dict[str, list] = {}
    faces_cache = {}
    for tag, _lo, _hi, uv in FLAKES:
        faces_cache[tag] = (_faces(uv, east=UV_ASH_EDGE, west=UV_ASH_EDGE,
                                   up=UV_ASH_EDGE, down=UV_ASH_EDGE)
                            if tag.startswith('flake')
                            else _faces(uv))

    for i, spec in enumerate(ASH_SPECS):
        s = spec['scale']
        cx = round(math.cos(spec['ang']) * spec['r'], 4)
        cz = round(math.sin(spec['ang']) * spec['r'], 4)
        origin = [cx, ROOT_ORIG[1], cz]
        cubes = []
        for tag, lo, hi, _uv in FLAKES:
            cubes.append(_cube(
                f'ash_{i + 1:02d}_{tag}',
                [origin[0] + lo[0] * s, origin[1] + lo[1] * s, origin[2] + lo[2] * s],
                [origin[0] + hi[0] * s, origin[1] + hi[1] * s, origin[2] + hi[2] * s],
                origin, faces_cache[tag]))
        for c in cubes:
            elements.append(c)
        bones[ASH_IDS[i]] = [c['uuid'] for c in cubes]
    bones['aura_root'] = []
    return bones


# ---------------------------------------------------------------------------
# 4. Анимация: непрерывный поток пепла снизу вверх
# ---------------------------------------------------------------------------
def _fade(c: float, rise: float) -> float:
    if c < 0.02:
        return 0.0
    if c < 0.02 + GROW:
        return (c - 0.02) / GROW
    if c < rise:
        return 1.0
    if c < rise + CRUMBLE:
        return 1.0 - (c - rise) / CRUMBLE
    return 0.0


def eval_aura_pose(u: float) -> dict:
    up = 0.0 if u >= 1.0 else u
    pose = {'root_pos': [0.0, round(0.12 * math.sin(TAU * up), 4), 0.0],
            'ash_pos': {}, 'ash_rot': {}, 'ash_scale': {}}

    for i, name in enumerate(ASH_IDS):
        spec = ASH_SPECS[i]
        c = (up - spec['phase']) % 1.0

        t = min(1.0, c / spec['rise'])
        y = Y_LOW + (spec['y_top'] - Y_LOW) * (t ** spec['pow'])

        # Касательная качка — нулевое среднее, НИКАКОГО монотонного обхода кольца.
        dang = (spec['at'] / spec['r']) * (
            0.62 * math.sin(TAU * (spec['nt1'] * c + spec['pt1']))
            + 0.38 * math.sin(TAU * (spec['nt2'] * c + spec['pt2'])))
        ang = spec['ang'] + dang
        r = spec['r'] + spec['ar'] * (0.5 + 0.5 * math.sin(TAU * (spec['nr'] * c + spec['pr'])))
        y = y + spec['ab'] * math.sin(TAU * (spec['nb'] * c + spec['pb']))

        x = math.cos(ang) * r
        z = math.sin(ang) * r
        bx = math.cos(spec['ang']) * spec['r']
        bz = math.sin(spec['ang']) * spec['r']
        pose['ash_pos'][name] = [round(x - bx, 4), round(y - ROOT_ORIG[1], 4),
                                 round(z - bz, 4)]

        # Кувыркание: целое число оборотов по каждой оси -> стык цикла бесшовный
        pose['ash_rot'][name] = [
            round(360.0 * spec['nx'] * c + 30.0 * math.sin(TAU * (spec['nt1'] * c + spec['px'])), 4),
            round(360.0 * spec['ny'] * c + 26.0 * math.sin(TAU * (spec['nb'] * c + spec['py'])), 4),
            round(360.0 * spec['nz'] * c + 22.0 * math.sin(TAU * (spec['nt2'] * c + spec['pz'])), 4),
        ]

        flicker = 1.0 + 0.09 * math.sin(TAU * (spec['nr'] * c + spec['px']))
        f = _fade(c, spec['rise']) * spec['scale'] * flicker
        pose['ash_scale'][name] = [round(f, 4), round(f, 4), round(f, 4)]

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
        pose = eval_aura_pose(u)
        kfs['aura_root'].append(_vec_kf('position', 'idle:aura_root', t, *pose['root_pos']))
        for name in ASH_IDS:
            kfs[name].append(_vec_kf('position', f'idle:{name}', t, *pose['ash_pos'][name]))
            kfs[name].append(_vec_kf('rotation', f'idle:{name}', t, *pose['ash_rot'][name]))
            kfs[name].append(_vec_kf('scale', f'idle:{name}', t, *pose['ash_scale'][name]))
    return {uid(f'bone:{b}'): {'name': b, 'type': 'bone', 'keyframes': kfs[b]}
            for b in BONE_NAMES}


# ---------------------------------------------------------------------------
# 5. Блюпринт
# ---------------------------------------------------------------------------
def build_blueprint() -> tuple[dict, Image.Image]:
    texture = build_death_texture()
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

    ash_bones = [bone(ASH_IDS[i],
                      [round(math.cos(ASH_SPECS[i]['ang']) * ASH_SPECS[i]['r'], 4),
                       ROOT_ORIG[1],
                       round(math.sin(ASH_SPECS[i]['ang']) * ASH_SPECS[i]['r'], 4)],
                      bones[ASH_IDS[i]], is_open=False)
                 for i in range(ASH_COUNT)]

    outliner = [bone('aura_root', ROOT_ORIG, ash_bones)]

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
            'width': 64, 'height': 64, 'uv_width': 16, 'uv_height': 16,
            'particle': False, 'use_as_default': False, 'layers_enabled': False,
            'sync_to_project': '', 'render_mode': 'default', 'render_sides': 'auto',
            'frame_time': 1, 'frame_order_type': 'loop', 'frame_order': '',
            'frame_interpolate': False, 'visible': True, 'internal': True, 'saved': True,
            'uuid': uid('tex:0'),
            'source': 'data:image/png;base64,' + base64.b64encode(raw.getvalue()).decode('ascii'),
        }],
    }
    blueprint['animations'] = [{
        'uuid': uid('anim:idle'), 'name': 'idle', 'loop': 'loop', 'override': False,
        'length': IDLE_LEN, 'snapping': 20, 'selected': True, 'saved': True,
        'path': '', 'anim_time_update': '', 'blend_weight': '',
        'start_delay': '', 'loop_delay': '',
        'animators': build_idle_animators(),
    }]
    return blueprint, texture


# ---------------------------------------------------------------------------
# 6. Иконка 32x32 (`reallyworld:death_aura_icon`)
# ---------------------------------------------------------------------------
def build_death_icon() -> Image.Image:
    """32x32: рваные серые хлопья пепла поднимаются вверх, в них тлеют угольки."""
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    ash_light = (150, 146, 152, 255)
    ash_mid = (98, 94, 102, 255)
    ash_dark = (48, 44, 52, 255)
    ember = (255, 186, 74, 255)
    ember_hot = (255, 240, 190, 255)
    ember_deep = (198, 74, 20, 255)

    def put(x, y, c):
        if 0 <= x < 32 and 0 <= y < 32:
            px[x, y] = c

    # (x, y, размер, есть ли уголёк)
    flakes = (
        (14, 26, 2, True), (7, 20, 2, False), (18, 17, 2, True),
        (10, 12, 2, False), (21, 9, 2, True), (13, 5, 1, False),
        (5, 26, 1, False), (24, 22, 1, False), (26, 14, 1, False),
    )
    for (fx, fy, sc, hot) in flakes:
        for dy in range(sc):
            for dx in range(sc):
                put(fx + dx, fy + dy, ash_mid if (dx + dy) % 2 == 0 else ash_light)
        # рваный край — одна тёмная точка справа снизу
        put(fx + sc, fy + sc - 1, ash_dark)
        if sc >= 2:
            put(fx, fy + sc, ash_dark)
        if hot:
            put(fx + sc // 2, fy - 1, ember)
            put(fx + sc // 2, fy - 1, ember_hot if sc >= 2 else ember)

    # тлеющие точки отдельно
    for (ex, ey) in ((16, 29), (9, 23), (20, 20), (23, 12)):
        put(ex, ey, ember)
        put(ex, ey - 1, ember_hot if (ex + ey) % 2 == 0 else ember_deep)

    return img


# ---------------------------------------------------------------------------
# 7. Превью
# ---------------------------------------------------------------------------
def render_preview(blueprint: dict, texture: Image.Image, icon: Image.Image,
                   out_path: Path) -> None:
    panel_w, panel_h = 190, 300
    canvas = Image.new('RGBA', (panel_w * 3 + 170, panel_h), (14, 14, 18, 255))
    tex_arr = np.array(texture)
    by_uuid = {el['uuid']: el for el in blueprint['elements']}

    def rot_mat(rx, ry, rz):
        rx, ry, rz = map(math.radians, (rx, ry, rz))
        cx_, sx_ = math.cos(rx), math.sin(rx)
        cy_, sy_ = math.cos(ry), math.sin(ry)
        cz_, sz_ = math.cos(rz), math.sin(rz)
        mx = np.array([[1, 0, 0], [0, cx_, -sx_], [0, sx_, cx_]])
        my = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]])
        mz = np.array([[cz_, -sz_, 0], [sz_, cz_, 0], [0, 0, 1]])
        return mz @ my @ mx

    stages = ((0.10, 0.0, -10.0), (0.45, 90.0, -8.0), (0.75, 200.0, -10.0))
    for idx, (u, cam_yaw, cam_pitch) in enumerate(stages):
        panel = Image.new('RGBA', (panel_w, panel_h), (20, 20, 26, 255))
        pose = eval_aura_pose(u)
        M = rot_mat(cam_pitch, cam_yaw, 0.0)
        scale = 7.0
        cx0, cy0 = panel_w / 2, panel_h / 2 + 40
        faces_to_draw = []
        for name in ASH_IDS:
            f = pose['ash_scale'][name][0]
            if f <= 0.001:
                continue
            off = np.array(pose['ash_pos'][name], dtype=float)
            rot = np.array(pose['ash_rot'][name], dtype=float)
            Rm = rot_mat(rot[0], rot[1], rot[2])
            base = np.array([math.cos(ASH_SPECS[ASH_IDS.index(name)]['ang'])
                             * ASH_SPECS[ASH_IDS.index(name)]['r'],
                             ROOT_ORIG[1],
                             math.sin(ASH_SPECS[ASH_IDS.index(name)]['ang'])
                             * ASH_SPECS[ASH_IDS.index(name)]['r']])
            for cu in (c for c in blueprint['elements'] if c['name'].startswith(name)):
                a = np.array(cu['from'], dtype=float) - base
                b = np.array(cu['to'], dtype=float) - base
                a = Rm @ (a * f) + base + off
                b = Rm @ (b * f) + base + off
                xs = (a[0], b[0]); ys = (a[1], b[1]); zs = (a[2], b[2])
                for axis, fixed in ((0, (ys, zs)), (1, (xs, zs)), (2, (xs, ys))):
                    pass
                corners = []
                for xx in xs:
                    for yy in ys:
                        for zz in zs:
                            corners.append(np.array([xx, yy - 16.0, zz]))
                p2d = []
                for cor in corners:
                    q = M @ cor
                    p2d.append((cx0 + q[0] * scale, cy0 - q[1] * scale, q[2]))
                uv = cu['faces']['north']['uv']
                u0 = int(uv[0] * 4); v0 = int(uv[1] * 4)
                col = tuple(int(c) for c in tex_arr[min(63, v0 + 8), min(63, u0 + 8)][:3]) + (255,)
                z_avg = sum(p[2] for p in p2d) / 8.0
                faces_to_draw.append((z_avg, [(s[0], s[1]) for s in p2d], col, None))
        faces_to_draw.sort(key=lambda item: item[0], reverse=True)
        for _z, poly, col, outline in faces_to_draw:
            layer = Image.new('RGBA', (panel_w, panel_h), (0, 0, 0, 0))
            ImageDraw.Draw(layer, 'RGBA').polygon(poly, fill=col, outline=outline)
            panel.alpha_composite(layer)
        canvas.paste(panel, (idx * panel_w, 0))

    icon_big = icon.resize((128, 128), Image.NEAREST)
    canvas.alpha_composite(icon_big, (panel_w * 3 + 21, 24))
    tex_small = texture.resize((112, 112), Image.NEAREST)
    canvas.alpha_composite(tex_small, (panel_w * 3 + 29, 170))
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

    icon = build_death_icon()
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

    drawn = sum(1 for b in BONE_NAMES if b != 'aura_root')
    print(f'Built {MODEL}.bbmodel: {len(blueprint["elements"])} cubes, '
          f'{len(BONE_NAMES)} bones ({drawn} drawn), icon -> {args.assets_dir}')


if __name__ == '__main__':
    main()
