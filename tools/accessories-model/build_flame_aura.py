#!/usr/bin/env python3
"""Процедурно строит 3D-ауру «Пламя» (`elytrix_flame_aura`), её иконку 32x32
(`reallyworld:flame_aura_icon`) и превью для проверки.

100% чистый процедурный Python + Pillow + NumPy — ноль нейрогенерации.

  1. Визуальный замысел — «АУРА: языки пламени поднимаются снизу и гаснут наверху»:
       - Вокруг игрока по кольцу (радиус `11.4..13.2` BB, то есть `0.71..0.83` блока от оси
         тела — СТРОГО ВНЕ игрока: модель игрока вместе с опущенными руками занимает
         `|x| <= 7.5` BB и `|z| <= 3.75` BB, а ближайшая вершина пламени отстоит от этого
         габарита минимум на `~2.1` BB) висит поток из 12 языков пламени.
       - Каждый язык рождается ПОД ногами (`Y = -1.2`, ниже подошвы `Y = 0.00`),
         поднимается вверх до `Y = 34.0` (выше макушки `Y = 30.00`) и там гаснет.
       - Подъём НЕ прямой: язык ещё и обходит кольцо (`0.12` оборота за цикл), качается
         по касательной, покачивается по вертикали и всё время дрожит-мерцает — поэтому
         поток выглядит живым огнём, а не столбом одинаковых спрайтов.
       - Появление и исчезание сделаны через `scale` (всплытие `0 -> 1` у самого низа и
         угасание `1 -> 0` у самого верха), плюс невидимое окно `scale = 0` на стыке цикла.
         Поэтому интерполяция ModelEngine НИКОГДА не протаскивает пламя сверху вниз:
         в момент телепорта на старт оно невидимо (ровно та же техника, что и в 3D-дождике
         `elytrix_lightning_hat` и в ауре сердечек).
       - Фазы 12 языков сдвинуты на `1/12` цикла, так что новый язык появляется каждые
         `~0.42` с и поток получается непрерывным.
  2. Язык пламени — 7 пиксельных строк-кубов (капля: узкий кончик сверху, широкое
     основание снизу) + 1 куб раскалённого ядра + 1 куб-угольник над кончиком,
     ВСЕГО 9 кубов на язык (108 кубов на всю ауру). Ни один куб НЕ повёрнут:
     ModelEngine 4.1.0 `RotationSolver` падает на повёрнутых кубах, поэтому всё собрано
     осевыми параллелепипедами. Ядро выступает на `0.03` BB (микро-ступенька против
     z-fighting, как в `elytrix_satan_circle`).
  3. **Никаких полос.** Каждая строка-куб получает СВОЮ полоску градиента (`_row_faces`),
     поэтому 7 полосок складываются в один непрерывный сверху-вниз переход: кончик
     тёмно-красный, основание почти белое. Ранний прототип давал всем строкам одну и ту же
     область UV, из-за чего сердце выглядело стиральной доской — здесь этого нет.
  4. Инженерная безопасность:
       - **Ни одного повёрнутого куба.**
       - Каждая кость `flame_NN` имеет пивот В ЦЕНТРЕ своего языка, вся геометрия запечена
         вокруг него (расстояние `~1.8` BB). Дальний ход делает анимация позиции:
         максимум `~21` BB от пивота `< 24` BB — лимит ModelEngine для костей.
       - Аура НИКОГДА не поворачивается вместе с телом игрока (ей всегда передаётся
         рысканье `0`) — только следует за ним по позиции.
       - Максимальное удаление вершины от глаз `< 2.85 m`, поэтому тинт `-197122`
         (крыльевой) скрывает ауру от 1-го лица оставаясь полностью видимой в `F5`
         и другим игрокам.
       - `16.0` BB = `1.0` блок: стопы `0.00`, талия `11.25`, шея/плечи `22.50`,
         макушка `30.00`, глаза `25.92`, `+Z` — спина игрока.
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
MODEL = 'elytrix_flame_aura'
ICON = 'flame_aura_icon'

IDLE_LEN = 5.0        # 100 ticks @ 20 TPS — полный цикл подъёма одного языка
IDLE_STEPS = 80       # 16 keyframes/s — телепорт на старт попадает ровно на keyframe

ROOT_ORIG = [0.0, 16.0, 0.0]   # середина пути: геометрия запечена здесь, дальше ходит анимация

FLAME_COUNT = 12
Y_LOW = -1.2          # ниже подошвы — «из под низу»
Y_HIGH = 34.0         # выше макушки — там и гаснет
RISE = 0.72           # доля цикла на подъём, дальше угасание + невидимое окно
DRIFT_TURNS = 0.10    # на сколько оборотов язык обходит кольцо за цикл

PX = 0.30             # размер «пикселя» языка в BB (язык 8x7 пикселей = 2.4 x 2.1 BB)

# Пиксельная маска языка пламени: (строка, x0, x1) в пикселях от левого края,
# строка 0 сверху. Капля: узкий кончик, широкое основание.
FLAME_ROWS = (
    (0, 3, 5),      # кончик
    (1, 3, 5),
    (2, 2, 6),
    (3, 2, 6),
    (4, 1, 7),
    (5, 1, 7),
    (6, 1, 7),      # широкое раскалённое основание
)
# Полуглубина каждой строки — язык объёмный, к основанию толще.
ROW_DEPTH = (0.22, 0.30, 0.38, 0.44, 0.46, 0.44, 0.38)

# 0..16 UV, текстура 64x64 => 1 UV = 4 px, тайлы 32x32 px = 8x8 UV.
UV_BODY = (0.25, 0.25, 7.75, 7.75)      # тело языка: красный кончик -> белое основание
UV_EDGE = (8.25, 0.25, 15.75, 7.75)     # боковые грани, темнее
UV_CORE = (0.25, 8.25, 7.75, 15.75)     # раскалённое ядро у основания
UV_EMBER = (8.25, 8.25, 15.75, 15.75)   # радиальный уголёк над кончиком

_BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f'elytrix.flame_aura.v1:{tag}'))


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
# 1. Текстура 64x64 — гладкие градиенты, без полос и сканлайнов
# ---------------------------------------------------------------------------
def build_flame_texture() -> Image.Image:
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
        return (0.035 * math.sin(px * 0.21 + py * 0.13)
                + 0.028 * math.sin(px * 0.09 - py * 0.17))

    # (0,0) тело языка: сверху тёмно-красный кончик, снизу почти белое основание
    paint(0, 0, lambda px, py: _ramp(
        [(0.00, (176, 38, 24)), (0.30, (232, 84, 26)),
         (0.62, (255, 158, 44)), (1.00, (255, 238, 186))],
        py / 31.0 + wob(px, py)))
    # (32,0) боковые грани, темнее и глубже
    paint(1, 0, lambda px, py: _ramp(
        [(0.00, (112, 20, 14)), (0.35, (188, 56, 16)),
         (0.72, (240, 122, 30)), (1.00, (255, 196, 96))],
        py / 31.0 + wob(px, py)))
    # (0,32) раскалённое ядро у основания
    paint(0, 1, lambda px, py: _ramp(
        [(0.00, (255, 246, 208)), (0.55, (255, 206, 96)), (1.00, (255, 150, 40))],
        py / 31.0 + wob(px, py)))
    # (32,32) уголёк над кончиком: радиальный белый -> красный
    paint(1, 1, lambda px, py: _ramp(
        [(0.00, (255, 250, 226)), (0.30, (255, 214, 120)),
         (0.66, (255, 140, 44)), (1.00, (198, 58, 22))],
        min(1.0, math.hypot(px - 15.5, py - 15.5) / 17.0 + wob(px, py))))

    return Image.fromarray(arr, 'RGBA')


# ---------------------------------------------------------------------------
# 2. Кубы (НИ ОДИН не повёрнут)
# ---------------------------------------------------------------------------
# Каждая из 7 пиксель-строк языка — отдельный куб. Если дать им всем одну и ту же
# UV-область, каждый куб покажет ВЕСЬ градиент и пламя превратится в «стиральную
# доску» из 7 полос. Поэтому строка `r` получает свою полоску градиента: вместе
# 7 полосок складываются в один непрерывный сверху-вниз переход (тёмный кончик ->
# белое основание), то есть в обычную объёмную тень, а не в полосы.
_ROW_BAND = 7.5 / 7.0


def _row_band(top: float, left: float, right: float, row: int) -> tuple:
    y0 = top + row * _ROW_BAND + 0.04
    y1 = top + (row + 1) * _ROW_BAND - 0.04
    return (left, round(y0, 3), right, round(y1, 3))


def _row_faces(row: int) -> dict:
    """Грани строки `row`: своя полоска тела + своя полоска боковой грани."""
    body = _row_band(0.25, 0.25, 7.75, row)
    edge = _row_band(0.25, 8.25, 15.75, row)
    out = {}
    for side in ('north', 'south', 'east', 'west', 'up', 'down'):
        out[side] = {'uv': list(edge if side in ('east', 'west', 'up', 'down') else body),
                     'texture': 0}
    return out


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
# 3. Геометрия: 12 языков, запечённых в центре своего пути
# ---------------------------------------------------------------------------
def flame_spec(i: int) -> dict:
    """Базовые параметры языка `i` (0-based)."""
    base_ang = math.radians(i * (360.0 / FLAME_COUNT) + 7.0 * (i % 3))
    # Кольцо лежит ВНЕ игрока: модель игрока вместе с опущенными руками занимает
    # |x| <= 7.5 BB и |z| <= 3.75 BB, а полуразмер языка ~1.8 BB — поэтому
    # радиус держим от 11.4 BB, чтобы пламя никогда не проходило сквозь тело.
    radius = 11.4 + 1.8 * (((i * 7) % 5) / 4.0)
    scale = 0.85 + 0.30 * (((i * 3) % 4) / 3.0)
    phase = i / FLAME_COUNT
    return {'ang': base_ang, 'r': radius, 'scale': scale, 'phase': phase}


def build_geometry(elements: list) -> dict:
    core_faces = _faces(UV_CORE)
    ember_faces = _faces(UV_EMBER)

    bones = {}
    for i in range(FLAME_COUNT):
        spec = flame_spec(i)
        # Кость живёт в центре пути: вся геометрия запечена вокруг этой точки,
        # а подъём делает анимация позиции (так статический bbox кости крошечный).
        cx = round(math.cos(spec['ang']) * spec['r'], 4)
        cz = round(math.sin(spec['ang']) * spec['r'], 4)
        origin = [cx, ROOT_ORIG[1], cz]
        cubes = []
        for k, (row, x0, x1) in enumerate(FLAME_ROWS):
            s = spec['scale']
            y_hi = (3.5 - row) * PX * s
            y_lo = (2.5 - row) * PX * s
            xa = (x0 - 4) * PX * s
            xb = (x1 - 4) * PX * s
            hd = ROW_DEPTH[row] * s
            cubes.append(_cube(
                f'flame_{i + 1:02d}_r{row}_{k}',
                [origin[0] + xa, origin[1] + y_lo, origin[2] - hd],
                [origin[0] + xb, origin[1] + y_hi, origin[2] + hd],
                origin, _row_faces(row)))
        # раскалённое ядро у основания: чуть выступает вперёд против z-fighting
        s = spec['scale']
        hd = ROW_DEPTH[6] * s + 0.03
        cubes.append(_cube(
            f'flame_{i + 1:02d}_core',
            [origin[0] - 2.0 * PX * s, origin[1] - 3.5 * PX * s, origin[2] - hd],
            [origin[0] + 2.0 * PX * s, origin[1] - 1.5 * PX * s, origin[2] + hd],
            origin, core_faces))
        # крошечный уголёк-искра чуть выше кончика
        cubes.append(_cube(
            f'flame_{i + 1:02d}_emb',
            [origin[0] - 0.5 * PX * s, origin[1] + 3.9 * PX * s, origin[2] - 0.14 * s],
            [origin[0] + 0.5 * PX * s, origin[1] + 4.9 * PX * s, origin[2] + 0.14 * s],
            origin, ember_faces))
        for c in cubes:
            elements.append(c)
        bones[f'flame_{i + 1:02d}'] = [c['uuid'] for c in cubes]
    bones['aura_root'] = []
    return bones


# ---------------------------------------------------------------------------
# 4. Анимация: непрерывный поток снизу вверх
# ---------------------------------------------------------------------------
FLAME_IDS = [f'flame_{i + 1:02d}' for i in range(FLAME_COUNT)]
BONE_NAMES = ['aura_root'] + FLAME_IDS


def _fade(c: float) -> float:
    """Масштаб языка в фазе `c` цикла: всплытие -> полный размер -> угасание -> 0."""
    if c < 0.03:
        return 0.0                      # невидимо у самого низа
    if c < 0.11:
        return (c - 0.03) / 0.08        # всплытие
    if c < 0.78:
        return 1.0
    if c < 0.94:
        return 1.0 - (c - 0.78) / 0.16  # угасание
    return 0.0                          # невидимое окно на стыке цикла


def eval_aura_pose(u: float) -> dict:
    tau = 2.0 * math.pi
    up = 0.0 if u >= 1.0 else u
    pose = {'root_pos': [0.0, round(0.15 * math.sin(tau * up), 4), 0.0],
            'flame_pos': {}, 'flame_rot': {}, 'flame_scale': {}}

    for i, name in enumerate(FLAME_IDS):
        spec = flame_spec(i)
        c = (up - spec['phase']) % 1.0
        t = min(1.0, c / RISE)
        y = Y_LOW + (Y_HIGH - Y_LOW) * t

        ang = spec['ang'] + tau * DRIFT_TURNS * c
        # дыхание кольца — ТОЛЬКО наружу, чтобы пламя никогда не приближалось к игроку
        r = spec['r'] + 0.60 * (0.5 + 0.5 * math.sin(tau * (c * 1.5 + i * 0.37)))
        # живое болтание: касательная качка + вертикальное покачивание. Обе правки
        # НЕ уменьшают радиус, поэтому зазор до игрока остаётся прежним.
        sway = 0.85 * math.sin(tau * (c * 2.5 + i * 0.83))
        bob = 0.50 * math.sin(tau * (c * 3.0 + i * 0.47))
        x = math.cos(ang) * r - math.sin(ang) * sway
        z = math.sin(ang) * r + math.cos(ang) * sway
        y = y + bob

        bx = math.cos(spec['ang']) * spec['r']
        bz = math.sin(spec['ang']) * spec['r']
        pose['flame_pos'][name] = [round(x - bx, 4), round(y - ROOT_ORIG[1], 4),
                                   round(z - bz, 4)]

        # язык повёрнут «лицом» наружу кольца + живое дрожание огня
        face = 90.0 - math.degrees(ang)
        wob_y = 30.0 * math.sin(tau * (c * 3.0 + i * 0.61))
        wob_z = 26.0 * math.sin(tau * (c * 2.0 + i * 1.23))
        wob_x = 16.0 * math.sin(tau * (c * 2.5 + i * 0.29))
        pose['flame_rot'][name] = [round(wob_x, 4), round(face + wob_y, 4), round(wob_z, 4)]

        # пламя вытягивается вверх и всё время мерцает
        flicker = 1.0 + 0.12 * math.sin(tau * (c * 6.0 + i * 0.55))
        f = _fade(c) * spec['scale'] * flicker
        pose['flame_scale'][name] = [round(f * 0.95, 4), round(f * 1.22, 4),
                                     round(f * 0.95, 4)]

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
        for name in FLAME_IDS:
            kfs[name].append(_vec_kf('position', f'idle:{name}', t, *pose['flame_pos'][name]))
            kfs[name].append(_vec_kf('rotation', f'idle:{name}', t, *pose['flame_rot'][name]))
            kfs[name].append(_vec_kf('scale', f'idle:{name}', t, *pose['flame_scale'][name]))
    return {uid(f'bone:{b}'): {'name': b, 'type': 'bone', 'keyframes': kfs[b]}
            for b in BONE_NAMES}


# ---------------------------------------------------------------------------
# 5. Блюпринт
# ---------------------------------------------------------------------------
def build_blueprint() -> tuple[dict, Image.Image]:
    texture = build_flame_texture()
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

    flame_bones = [bone(f'flame_{i + 1:02d}',
                        [round(math.cos(flame_spec(i)['ang']) * flame_spec(i)['r'], 4),
                         ROOT_ORIG[1],
                         round(math.sin(flame_spec(i)['ang']) * flame_spec(i)['r'], 4)],
                        bones[f'flame_{i + 1:02d}'], is_open=False)
                   for i in range(FLAME_COUNT)]

    outliner = [bone('aura_root', ROOT_ORIG, flame_bones)]

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
# 6. Иконка 32x32 (`reallyworld:flame_aura_icon`)
# ---------------------------------------------------------------------------
def build_flame_icon() -> Image.Image:
    """32x32 пиксельная иконка: крупный язык пламени внизу по центру и три мелких,
    которые поднимаются вверх вправо — ровно то, что делает аура в игре."""
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    white = (255, 250, 226, 255)    # почти белое ядро
    hot = (255, 206, 96, 255)       # раскалённый янтарь
    mid = (255, 140, 44, 255)       # оранжевый
    deep = (206, 58, 22, 255)       # тёмно-красный кончик

    def put(x, y, c):
        if 0 <= x < 32 and 0 <= y < 32:
            px[x, y] = c

    # 8x8 маска капли пламени: узкий кончик сверху, широкое основание снизу
    MASK = (
        '...##...',
        '..####..',
        '..####..',
        '.######.',
        '.######.',
        '########',
        '########',
        '.######.',
    )

    def flame(ox: int, oy: int, sc: int = 1) -> None:
        for row, line in enumerate(MASK):
            for col, ch in enumerate(line):
                if ch != '#':
                    continue
                # снизу почти белое ядро, к кончику темнеет до красного
                if row >= 6:
                    col_sel = white if 2 <= col <= 5 else hot
                elif row >= 4:
                    col_sel = hot if 2 <= col <= 5 else mid
                elif row >= 2:
                    col_sel = mid
                else:
                    col_sel = deep
                for dy in range(sc):
                    for dx in range(sc):
                        put(ox + col * sc + dx, oy + row * sc + dy, col_sel)

    # крупный язык внизу по центру (масштаб 3 => 24x24, x 4..27, y 7..30)
    flame(4, 7, 3)
    # ядро основаниия ярче
    for (bx, by) in ((13, 25), (14, 25), (15, 25), (16, 25), (17, 25), (18, 25),
                     (13, 26), (14, 26), (15, 26), (16, 26), (17, 26), (18, 26)):
        put(bx, by, white)

    # три мелких язычка поднимаются вверх и вправо
    flame(2, 3, 1)
    flame(9, 1, 1)
    flame(22, 2, 1)

    # редкие уголки
    for (sx, sy) in ((6, 1), (20, 0), (28, 5), (1, 12)):
        put(sx, sy, white)

    return img


# ---------------------------------------------------------------------------
# 7. Превью
# ---------------------------------------------------------------------------
def render_preview(blueprint: dict, texture: Image.Image, icon: Image.Image, out_path: Path) -> None:
    panel_w, panel_h = 230, 300
    canvas = Image.new('RGBA', (panel_w * 4 + 210, panel_h), (18, 22, 30, 255))
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

    stages = [
        (0.02, 0.0, -12.0, 'спереди 3/4'),
        (0.35, 90.0, -10.0, 'сбоку'),
        (0.68, 180.0, -12.0, 'сзади'),
        (0.50, 0.0, -88.0, 'сверху'),
    ]

    for idx, (u, cam_yaw, cam_pitch, _label) in enumerate(stages):
        panel = Image.new('RGBA', (panel_w, panel_h),
                          (14, 18, 26, 255) if idx == 3 else (26, 30, 42, 255))
        faces_to_draw = []
        pose = eval_aura_pose(u)
        for i, name in enumerate(FLAME_IDS):
            spec = flame_spec(i)
            bx = math.cos(spec['ang']) * spec['r']
            bz = math.sin(spec['ang']) * spec['r']
            origin = [bx, ROOT_ORIG[1], bz]
            pos = pose['flame_pos'][name]
            rot = pose['flame_rot'][name]
            sc = pose['flame_scale'][name]
            o = [origin[0] + pos[0], origin[1] + pos[1], origin[2] + pos[2]]
            m = rot_mat(rot[0], rot[1], rot[2])
            for cu in by_uuid.values():
                if not cu['name'].startswith(f'{name}_'):
                    continue
                for fname in ('north', 'south', 'east', 'west', 'up', 'down'):
                    uv = cu['faces'][fname]['uv']
                    tx = min(63, int(0.5 * (uv[0] + uv[2]) * 4))
                    ty = min(63, int(0.5 * (uv[1] + uv[3]) * 4))
                    rgba = tex_arr[ty, tx]
                    if rgba[3] < 16:
                        continue
                    x0, y0, z0 = cu['from']
                    x1, y1, z1 = cu['to']
                    raw_cs = [np.array([x0, y0, z0]), np.array([x1, y0, z0]),
                              np.array([x1, y1, z0]), np.array([x0, y1, z0]),
                              np.array([x0, y0, z1]), np.array([x1, y0, z1]),
                              np.array([x1, y1, z1]), np.array([x0, y1, z1])]
                    local = [np.array([c[0] - origin[0], c[1] - origin[1], c[2] - origin[2]])
                             for c in raw_cs]
                    scaled = [np.array([c[0] * sc[0], c[1] * sc[1], c[2] * sc[2]]) for c in local]
                    turned = [m @ c for c in scaled]
                    wcs = [np.array([o[0] + c[0], o[1] + c[1], o[2] + c[2]]) for c in turned]
                    quads = [('north', (2, 1, 0, 3)), ('south', (7, 4, 5, 6)),
                             ('east', (6, 5, 1, 2)), ('west', (3, 0, 4, 7)),
                             ('up', (7, 6, 2, 3)), ('down', (0, 1, 5, 4))]
                    for qname, idxs in quads:
                        if qname != fname:
                            continue
                        p3 = [wcs[k] for k in idxs]
                        cam = math.radians(cam_yaw)
                        cp, sp = math.cos(math.radians(cam_pitch)), math.sin(math.radians(cam_pitch))
                        proj = []
                        for p in p3:
                            dx = p[0] * math.cos(cam) - p[2] * math.sin(cam)
                            dz = p[0] * math.sin(cam) + p[2] * math.cos(cam)
                            dy = p[1]
                            yy = dy * cp - dz * sp
                            zz = dy * sp + dz * cp
                            k = 900.0 / (900.0 + zz * 6.0)
                            proj.append((panel_w / 2 + dx * 22.0 * k,
                                         panel_h / 2 + (16.0 - yy) * -22.0 * k + panel_h / 2))
                        col = tuple(rgba[:3]) + (255,)
                        z_avg = sum(p[2] for p in p3) / 4.0
                        faces_to_draw.append((z_avg, proj, col))
        faces_to_draw.sort(key=lambda item: item[0], reverse=True)
        for _z, poly, col in faces_to_draw:
            layer = Image.new('RGBA', (panel_w, panel_h), (0, 0, 0, 0))
            ImageDraw.Draw(layer, 'RGBA').polygon(poly, fill=col)
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
    args.bbmodel_out.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding='utf-8')

    icon = build_flame_icon()
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

    drawn = len(blueprint['elements'])
    drawn_bones = sum(1 for b in blueprint['outliner'][0]['children'] if b['children'])
    print(f'Built {MODEL}.bbmodel: {drawn} cubes, {drawn_bones + 1} bones ({drawn_bones} drawn), '
          f'icon -> {args.assets_dir}')

    if args.preview is not None:
        render_preview(blueprint, texture, icon, args.preview)


if __name__ == '__main__':
    main()
