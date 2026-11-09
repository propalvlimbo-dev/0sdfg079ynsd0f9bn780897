#!/usr/bin/env python3
"""Процедурно строит 3D-ауру «Сердечки» (`elytrix_heart_aura`), её иконку 32x32
(`reallyworld:heart_aura_icon`) и превью для проверки.

100% чистый процедурный Python + Pillow + NumPy — ноль нейрогенерации.

  1. Визуальный замысел — «АУРА: сердечки поднимаются снизу и тают наверху»:
       - Вокруг игрока по кольцу (радиус `4.4..5.6` BB, то есть `0.28..0.35` блока от оси
         тела — сразу за плечами, `±3.75` BB полуширина головы) висит поток из 12 сердечек.
       - Каждое сердечко рождается ПОД ногами (`Y = -1.2`, ниже подошвы `Y = 0.00`),
         поднимается вверх до своей высоты (`Y = 29.5..34.5`, то есть до или чуть выше
         макушки `Y = 30.00`) и там тает.
       - **Никакой спирали.** Раньше сердечко за цикл ещё и монотонно обходило кольцо
         (`DRIFT_TURNS = 0.10` оборота) — из-за этого траектория читалась как винтовая
         линия. Теперь монотонный обход убран полностью: сердечко поднимается почти
         вертикально и только «болтается» вокруг своей колонны нулевым средним.
       - «Рандомность» дана ПСЕВДОСЛУЧАЙНЫМИ параметрами на каждое сердечко (свой
         азимут, радиус, скорость подъёма, профиль разгона, высота таяния, фаза и свой
         набор целых частот болтания). Все частоты целые — цикл остаётся бесшовным, а
         выглядит как живой разнобой: сердечки не идут строем и не повторяют друг друга.
       - Появление и исчезание сделаны через `scale` (всплытие `0 -> 1` у самого низа и
         таяние `1 -> 0` у самого верха), плюс невидимое окно `scale = 0` на стыке цикла.
         Поэтому интерполяция ModelEngine НИКОГДА не протаскивает сердечко сверху вниз:
         в момент телепорта на старт оно невидимо (ровно та же техника, что и в 3D-дождике
         `elytrix_lightning_hat`).
       - Фазы 12 сердечек сдвинуты на `1/12` цикла, так что новое сердечко появляется
         каждые `0.5` с и поток получается непрерывным.
  2. Сердечко — 8 пиксельных строк-кубов + 1 куб-блик, ВСЕГО 9 кубов на сердечко
     (108 кубов на всю ауру). Ни один куб НЕ повёрнут: ModelEngine 4.1.0 `RotationSolver`
     падает на повёрнутых кубах, поэтому всё собрано осевыми параллелепипедами.
     Сердечко «пухлое»: полуглубина строк `0.28..0.45` BB, блик выступает на `0.03` BB
     (микро-ступенька против z-fighting, как в `elytrix_satan_circle`).
  3. Инженерная безопасность:
       - **Ни одного повёрнутого куба.**
       - Каждая кость `heart_NN` имеет пивот В ЦЕНТРЕ своего сердечка, а вся геометрия
         запечена вокруг него (расстояние `~1.5` BB). Дальний ход делает анимация
         позиции: максимум `~19` BB, то есть `20.5` BB от пивота `< 24` BB — лимит
         ModelEngine для костей.
       - Максимальное удаление вершины от глаз `~1.73 m` `< 1.85 m`, поэтому тинт `-196867`
         скрывает ауру от 1-го лица оставаясь полностью видимой в `F5` и другим игрокам.
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
MODEL = 'elytrix_heart_aura'
ICON = 'heart_aura_icon'

IDLE_LEN = 6.0        # 120 ticks @ 20 TPS — полный цикл подъёма одного сердечка
IDLE_STEPS = 120      # 20 keyframes/s — как и во всех остальных моделях пака

ROOT_ORIG = [0.0, 16.0, 0.0]   # середина пути: геометрия запечена здесь, дальше ходит анимация

HEART_COUNT = 12
Y_LOW = -1.2          # ниже подошвы — «из под низу»
TAU = 2.0 * math.pi

# Движение НЕ спираль: монотонный обход кольца убран полностью (было DRIFT_TURNS).
# Вместо него у каждого сердечка СВОЙ набор псевдослучайных параметров: свой азимут,
# свой радиус, своя скорость подъёма, своя высота таяния и свой частотный набор
# «болтания». Все частоты ЦЕЛЫЕ, поэтому цикл остаётся бесшовным, а выглядит это
# как живой разнобой, а не как карусель.
RISE_MIN, RISE_MAX = 0.62, 0.86    # доля цикла на подъём (своя скорость у каждого)
Y_TOP_MIN, Y_TOP_MAX = 29.5, 34.5  # где именно сердечко растает
R_MIN, R_MAX = 11.2, 13.4          # радиус колонны (всегда вне габарита игрока)

PX = 0.30             # размер «пикселя» сердечка в BB (сердце 8x7 пикселей = 2.4 x 2.1 BB)

# Пиксельная маска сердца: (строка, x0, x1) в пикселях от левого края, строка 0 сверху.
HEART_ROWS = (
    (0, 0, 2), (0, 5, 8),
    (1, 0, 8),
    (2, 0, 8),
    (3, 0, 8),
    (4, 1, 7),
    (5, 2, 6),
    (6, 3, 5),
)
# Полуглубина каждой строки — «пухлость» сердца.
ROW_DEPTH = (0.30, 0.45, 0.45, 0.45, 0.40, 0.35, 0.28)

# 0..16 UV, текстура 64x64 => 1 UV = 4 px, тайлы 32x32 px = 8x8 UV.
UV_HEART = (0.25, 0.25, 7.75, 7.75)     # нежно-розовое тело
UV_EDGE = (8.25, 0.25, 15.75, 7.75)     # глубокая роза (боковые грани)
UV_HIGH = (0.25, 8.25, 7.75, 15.75)     # бледно-розовый блик
UV_SPARK = (8.25, 8.25, 15.75, 15.75)   # радиальная бело-розовая искра

_BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f'elytrix.heart_aura.v1:{tag}'))


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
def build_heart_texture() -> Image.Image:
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

    # (0,0) тело сердца: светлый персиково-розовый -> насыщенная роза
    paint(0, 0, lambda px, py: _ramp(
        [(0.00, (255, 219, 230)), (0.45, (255, 152, 184)), (1.00, (233, 92, 135))],
        py / 31.0 + wob(px, py)))
    # (32,0) боковые грани: роза -> глубокая малина
    paint(1, 0, lambda px, py: _ramp(
        [(0.00, (255, 165, 194)), (0.45, (236, 92, 134)), (1.00, (176, 46, 88))],
        py / 31.0 + wob(px, py)))
    # (0,32) блик: почти белый -> бледно-розовый
    paint(0, 1, lambda px, py: _ramp(
        [(0.00, (255, 255, 255)), (0.50, (255, 236, 242)), (1.00, (255, 196, 214))],
        py / 31.0 + wob(px, py)))
    # (32,32) искра-сердечко: радиальный белый -> роза
    paint(1, 1, lambda px, py: _ramp(
        [(0.00, (255, 255, 255)), (0.30, (255, 226, 236)),
         (0.66, (255, 150, 184)), (1.00, (232, 72, 118))],
        min(1.0, math.hypot(px - 15.5, py - 15.5) / 17.0 + wob(px, py))))

    return Image.fromarray(arr, 'RGBA')


# ---------------------------------------------------------------------------
# 2. Кубы (НИ ОДИН не повёрнут)
# ---------------------------------------------------------------------------
# Каждая из 7 пиксель-строк сердца — отдельный куб. Если дать им всем одну и ту же
# UV-область, каждый куб покажет ВЕСЬ градиент и сердце превратится в «стиральную
# доску» из 7 полос. Поэтому строка `r` получает свою полоску градиента: вместе
# 7 полосок складываются в один непрерывный сверху-вниз переход (светлый верх ->
# насыщенный низ), то есть в обычную объёмную тень, а не в полосы.
_ROW_BAND = 7.5 / 7.0


def _row_band(top: float, left: float, right: float, row: int) -> tuple:
    y0 = top + row * _ROW_BAND + 0.04
    y1 = top + (row + 1) * _ROW_BAND - 0.04
    return (left, round(y0, 3), right, round(y1, 3))


def _heart_row_faces(row: int) -> dict:
    """Лицевые грани строки `row`: своя полоска тела + своя полоска боковой грани."""
    body = _row_band(0.25, 0.25, 7.75, row)
    edge = _row_band(0.25, 8.25, 15.75, row)
    return _faces(body, east=edge, west=edge, up=edge, down=edge)
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
# 3. Геометрия: 12 сердечек, запечённых в центре своего пути
# ---------------------------------------------------------------------------
def heart_spec(i: int) -> dict:
    """Псевдослучайные параметры сердечка `i` (0-based).

    Всё детерминировано (фиксированный seed на номер сердечка), поэтому сборка
    воспроизводима, но глазу набор параметров читается как «рандом»: сердечки не
    идут строем и не образуют спирали.
    """
    rnd = random.Random(9173 + i * 7919)
    # Азимут: равномерно по кругу, но с заметным сдвигом — чтобы не было «спиц».
    ang = (i / HEART_COUNT) * TAU + rnd.uniform(-0.42, 0.42)
    # Кольцо лежит ВНЕ игрока: модель игрока вместе с опущенными руками занимает
    # |x| <= 7.5 BB и |z| <= 3.75 BB, а полуразмер сердечка ~1.5 BB — поэтому
    # радиус держим от 11.2 BB, чтобы сердечко никогда не проходило сквозь тело.
    radius = rnd.uniform(R_MIN, R_MAX)
    scale = 0.85 + 0.30 * (((i * 3) % 4) / 3.0)
    # Фаза stratified + джиттер: поток непрерывный, но не «тик-так» поровну.
    phase = ((i + rnd.uniform(-0.45, 0.45)) / HEART_COUNT) % 1.0
    return {
        'ang': ang, 'r': radius, 'scale': scale, 'phase': phase,
        'rise': rnd.uniform(RISE_MIN, RISE_MAX),   # своя скорость подъёма
        'y_top': rnd.uniform(Y_TOP_MIN, Y_TOP_MAX),  # своя высота таяния
        'pow': rnd.uniform(0.82, 1.22),            # профиль: разгон / торможение
        'at': rnd.uniform(0.80, 1.90),             # амплитуда касательной качки, BB
        'ar': rnd.uniform(0.35, 0.95),             # «дыхание» радиуса, только НАРУЖУ
        'ab': rnd.uniform(0.20, 0.55),             # вертикальное покачивание, BB
        # Целые частоты — цикл бесшовный; разные наборы дают неповторимый рисунок.
        'nt1': rnd.choice((2, 3, 4)), 'nt2': rnd.choice((5, 6, 7)),
        'nr': rnd.choice((1, 2, 3)), 'nb': rnd.choice((2, 3, 4)),
        'pt1': rnd.random(), 'pt2': rnd.random(),
        'pr': rnd.random(), 'pb': rnd.random(),
        'pw1': rnd.random(), 'pw2': rnd.random(), 'pw3': rnd.random(),
    }


def build_geometry(elements: list) -> dict:
    high_faces = _faces(UV_HIGH)
    spark_faces = _faces(UV_SPARK)

    bones = {}
    for i in range(HEART_COUNT):
        spec = heart_spec(i)
        # Кость живёт в центре пути: вся геометрия запечена вокруг этой точки,
        # а подъём делает анимация позиции (так статический bbox кости крошечный).
        cx = round(math.cos(spec['ang']) * spec['r'], 4)
        cz = round(math.sin(spec['ang']) * spec['r'], 4)
        origin = [cx, ROOT_ORIG[1], cz]
        cubes = []
        for k, (row, x0, x1) in enumerate(HEART_ROWS):
            s = spec['scale']
            y_hi = (3.5 - row) * PX * s
            y_lo = (2.5 - row) * PX * s
            xa = (x0 - 4) * PX * s
            xb = (x1 - 4) * PX * s
            hd = ROW_DEPTH[row] * s
            cubes.append(_cube(
                f'heart_{i + 1:02d}_r{row}_{k}',
                [origin[0] + xa, origin[1] + y_lo, origin[2] - hd],
                [origin[0] + xb, origin[1] + y_hi, origin[2] + hd],
                origin, _heart_row_faces(row)))
        # блик: чуть выступает вперёд, микро-ступенька против z-fighting
        s = spec['scale']
        hd = ROW_DEPTH[1] * s + 0.03
        cubes.append(_cube(
            f'heart_{i + 1:02d}_hi',
            [origin[0] - 3.0 * PX * s, origin[1] + 1.5 * PX * s, origin[2] - hd],
            [origin[0] - 1.8 * PX * s, origin[1] + 2.6 * PX * s, origin[2] + hd],
            origin, high_faces))
        # крошечная искра-спутник чуть выше сердца
        cubes.append(_cube(
            f'heart_{i + 1:02d}_spk',
            [origin[0] + 3.2 * PX * s, origin[1] + 4.6 * PX * s, origin[2] - 0.16 * s],
            [origin[0] + 4.2 * PX * s, origin[1] + 5.6 * PX * s, origin[2] + 0.16 * s],
            origin, spark_faces))
        for c in cubes:
            elements.append(c)
        bones[f'heart_{i + 1:02d}'] = [c['uuid'] for c in cubes]
    bones['aura_root'] = []
    return bones


# ---------------------------------------------------------------------------
# 4. Анимация: непрерывный поток снизу вверх
# ---------------------------------------------------------------------------
HEART_IDS = [f'heart_{i + 1:02d}' for i in range(HEART_COUNT)]
BONE_NAMES = ['aura_root'] + HEART_IDS


GROW = 0.07      # доля цикла на «всплытие» снизу
MELT = 0.13      # доля цикла на таяние сверху


def _fade(c: float, rise: float) -> float:
    """Масштаб сердечка в фазе `c` цикла: всплытие -> полный размер -> таяние -> 0.

    `rise` у каждого сердечка свой, поэтому и тает оно на своей высоте. Хвост цикла
    (после `rise + MELT`) — невидимое окно: в этот момент сердечко уже возвращается
    на старт, и стык цикла гарантированно ничего не двигает.
    """
    if c < 0.02:
        return 0.0                          # невидимо у самого низа
    if c < 0.02 + GROW:
        return (c - 0.02) / GROW            # всплытие
    if c < rise:
        return 1.0
    if c < rise + MELT:
        return 1.0 - (c - rise) / MELT      # таяние
    return 0.0                              # невидимое окно на стыке цикла


def eval_aura_pose(u: float) -> dict:
    up = 0.0 if u >= 1.0 else u
    pose = {'root_pos': [0.0, round(0.15 * math.sin(TAU * up), 4), 0.0],
            'heart_pos': {}, 'heart_rot': {}, 'heart_scale': {}}

    for i, name in enumerate(HEART_IDS):
        spec = heart_spec(i)
        c = (up - spec['phase']) % 1.0

        # Подъём: почти вертикальный, со СВОИМ профилем скорости у каждого сердечка.
        t = min(1.0, c / spec['rise'])
        y = Y_LOW + (spec['y_top'] - Y_LOW) * (t ** spec['pow'])

        # Касательная качка — НУЛЕВОЕ среднее и НИКАКОГО монотонного обхода кольца,
        # поэтому спирали нет: сердечко просто болтается вокруг своей колонны.
        dang = (spec['at'] / spec['r']) * (
            0.62 * math.sin(TAU * (spec['nt1'] * c + spec['pt1']))
            + 0.38 * math.sin(TAU * (spec['nt2'] * c + spec['pt2'])))
        ang = spec['ang'] + dang
        # «Дыхание» радиуса — ТОЛЬКО наружу, чтобы сердечко никогда не приближалось
        # к игроку (r >= r0 >= 11.2 BB на всём цикле).
        r = spec['r'] + spec['ar'] * (0.5 + 0.5 * math.sin(TAU * (spec['nr'] * c + spec['pr'])))
        y = y + spec['ab'] * math.sin(TAU * (spec['nb'] * c + spec['pb']))

        x = math.cos(ang) * r
        z = math.sin(ang) * r

        bx = math.cos(spec['ang']) * spec['r']
        bz = math.sin(spec['ang']) * spec['r']
        pose['heart_pos'][name] = [round(x - bx, 4), round(y - ROOT_ORIG[1], 4),
                                   round(z - bz, 4)]

        # сердечко повёрнуто «лицом» наружу своей колонны + живое покачивание
        face = 90.0 - math.degrees(ang)
        wob_y = 22.0 * math.sin(TAU * (spec['nt1'] * c + spec['pw1']))
        wob_z = 18.0 * math.sin(TAU * (spec['nt2'] * c + spec['pw2']))
        wob_x = 12.0 * math.sin(TAU * (spec['nb'] * c + spec['pw3']))
        pose['heart_rot'][name] = [round(wob_x, 4), round(face + wob_y, 4), round(wob_z, 4)]

        # лёгкое «дыхание» размера поверх общей кривой появления/таяния
        flutter = 1.0 + 0.07 * math.sin(TAU * (spec['nr'] * c + spec['pw1']))
        f = _fade(c, spec['rise']) * spec['scale'] * flutter
        pose['heart_scale'][name] = [round(f, 4), round(f, 4), round(f, 4)]

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
        for name in HEART_IDS:
            kfs[name].append(_vec_kf('position', f'idle:{name}', t, *pose['heart_pos'][name]))
            kfs[name].append(_vec_kf('rotation', f'idle:{name}', t, *pose['heart_rot'][name]))
            kfs[name].append(_vec_kf('scale', f'idle:{name}', t, *pose['heart_scale'][name]))
    return {uid(f'bone:{b}'): {'name': b, 'type': 'bone', 'keyframes': kfs[b]}
            for b in BONE_NAMES}


# ---------------------------------------------------------------------------
# 5. Блюпринт
# ---------------------------------------------------------------------------
def build_blueprint() -> tuple[dict, Image.Image]:
    texture = build_heart_texture()
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

    heart_bones = [bone(f'heart_{i + 1:02d}',
                        [round(math.cos(heart_spec(i)['ang']) * heart_spec(i)['r'], 4),
                         ROOT_ORIG[1],
                         round(math.sin(heart_spec(i)['ang']) * heart_spec(i)['r'], 4)],
                        bones[f'heart_{i + 1:02d}'], is_open=False)
                   for i in range(HEART_COUNT)]

    outliner = [bone('aura_root', ROOT_ORIG, heart_bones)]

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
# 6. Иконка 32x32 (`reallyworld:heart_aura_icon`)
# ---------------------------------------------------------------------------
def build_heart_icon() -> Image.Image:
    """32x32 пиксельная иконка: крупное сердце внизу по центру и три мелких,
    которые поднимаются вверх вправо — ровно то, что делает аура в игре."""
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    core = (255, 255, 255, 255)     # белый блик
    light = (255, 186, 208, 255)    # светло-розовый
    mid = (255, 108, 148, 255)      # роза
    deep = (206, 46, 92, 255)       # малина

    def put(x, y, c):
        if 0 <= x < 32 and 0 <= y < 32:
            px[x, y] = c

    MASK = (
        '.##..##.',
        '########',
        '########',
        '.######.',
        '..####..',
        '...##...',
    )

    def heart(ox: int, oy: int, sc: int = 1) -> None:
        for row, line in enumerate(MASK):
            for col, ch in enumerate(line):
                if ch != '#':
                    continue
                # простая «пухлость»: светлее сверху-слева, темнее к низу-справа
                if row == 0 and col <= 3:
                    col_sel = core if col in (2, 3) else light
                elif row <= 2 and col <= 3:
                    col_sel = light
                elif row >= 4:
                    col_sel = deep
                else:
                    col_sel = mid
                for dy in range(sc):
                    for dx in range(sc):
                        put(ox + col * sc + dx, oy + row * sc + dy, col_sel)

    # крупное сердце внизу по центру (масштаб 3 => 24x18, x 3..26, y 14..31)
    heart(3, 14, 3)
    put(6, 16, core)
    put(7, 16, core)
    put(6, 17, core)
    put(7, 17, core)

    # три мелких сердечка поднимаются вверх и вправо
    heart(2, 8, 1)
    heart(11, 3, 1)
    heart(21, 7, 1)

    # редкие искорки
    for (sx, sy) in ((9, 2), (25, 3), (19, 12)):
        put(sx, sy, core)

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
        bg = (14, 18, 26, 255) if idx == 3 else (26, 30, 42, 255)
        panel = Image.new('RGBA', (panel_w, panel_h), bg)
        pose = eval_aura_pose(u)
        ay, ap = math.radians(cam_yaw), math.radians(cam_pitch)
        cy_m, sy_m = math.cos(ay), math.sin(ay)
        cp_m, sp_m = math.cos(ap), math.sin(ap)
        scale_px = 4.4
        center_world = np.array([0.0, 16.0, 0.0])
        center_y_px = 190.0

        def proj(pt):
            d = np.asarray(pt, dtype=float) - center_world
            xw = d[0] * cy_m - d[2] * sy_m
            z1 = d[0] * sy_m + d[2] * cy_m
            yw = d[1] * cp_m - z1 * sp_m
            zw = d[1] * sp_m + z1 * cp_m
            return (panel_w * 0.5 - xw * scale_px, center_y_px - yw * scale_px, zw)

        faces_to_draw = []

        # силуэт игрока для масштаба
        body = [([-3.75, 0.0, -1.875], [3.75, 30.0, 1.875], (58, 64, 84))]
        for low, high, col in body:
            corners = [np.array([low[0], low[1], low[2]]), np.array([high[0], low[1], low[2]]),
                       np.array([high[0], high[1], low[2]]), np.array([low[0], high[1], low[2]]),
                       np.array([low[0], low[1], high[2]]), np.array([high[0], low[1], high[2]]),
                       np.array([high[0], high[1], high[2]]), np.array([low[0], high[1], high[2]])]
            quads = [('north', (2, 1, 0, 3), 1.00), ('south', (7, 4, 5, 6), 0.80),
                     ('east', (6, 5, 1, 2), 0.90), ('west', (3, 0, 4, 7), 0.86),
                     ('up', (7, 6, 2, 3), 1.05), ('down', (0, 1, 5, 4), 0.72)]
            for _f, idxs, sm in quads:
                p2d = [proj(corners[k]) for k in idxs]
                cross = ((p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1])
                         - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0]))
                if cross > 0:
                    continue
                faces_to_draw.append((-1e9, [(s[0], s[1]) for s in p2d],
                                      tuple(int(c * sm) for c in col) + (255,), None))

        # сами сердечки
        for node in blueprint['outliner']:
            for child in node.get('children', []):
                if not isinstance(child, dict):
                    continue
                name = child['name']
                origin = np.array(child['origin'], dtype=float)
                pos = np.array(pose['heart_pos'][name], dtype=float)
                rot = np.array(pose['heart_rot'][name], dtype=float)
                sc = np.array(pose['heart_scale'][name], dtype=float)
                m = rot_mat(*rot)

                def tf(p, o=origin, t=pos, mm=m, ss=sc):
                    return o + t + mm @ (ss * (p - o))

                for cuid in child.get('children', []):
                    el = by_uuid.get(cuid)
                    if el is None:
                        continue
                    x0, y0, z0 = el['from']
                    x1, y1, z1 = el['to']
                    raw_cs = [np.array([x0, y0, z0]), np.array([x1, y0, z0]),
                              np.array([x1, y1, z0]), np.array([x0, y1, z0]),
                              np.array([x0, y0, z1]), np.array([x1, y0, z1]),
                              np.array([x1, y1, z1]), np.array([x0, y1, z1])]
                    wcs = [tf(c) for c in raw_cs]
                    quads = [('north', (2, 1, 0, 3), 1.00), ('south', (7, 4, 5, 6), 0.96),
                             ('east', (6, 5, 1, 2), 0.98), ('west', (3, 0, 4, 7), 0.98),
                             ('up', (7, 6, 2, 3), 1.05), ('down', (0, 1, 5, 4), 0.92)]
                    for fname, idxs, sm in quads:
                        p2d = [proj(wcs[k]) for k in idxs]
                        cross = ((p2d[1][0] - p2d[0][0]) * (p2d[2][1] - p2d[0][1])
                                 - (p2d[1][1] - p2d[0][1]) * (p2d[2][0] - p2d[0][0]))
                        if cross > 0:
                            continue
                        uv = el['faces'][fname]['uv']
                        tx = min(63, int(0.5 * (uv[0] + uv[2]) * 4))
                        ty = min(63, int(0.5 * (uv[1] + uv[3]) * 4))
                        rgba = tex_arr[ty, tx]
                        if rgba[3] < 16:
                            continue
                        col = tuple(min(255, int(c * sm)) for c in rgba[:3]) + (int(rgba[3]),)
                        z_avg = sum(p[2] for p in p2d) / 4.0
                        faces_to_draw.append((z_avg, [(s[0], s[1]) for s in p2d], col, None))

        faces_to_draw.sort(key=lambda item: item[0], reverse=True)
        for _z, poly, col, outline in faces_to_draw:
            layer = Image.new('RGBA', (panel_w, panel_h), (0, 0, 0, 0))
            ImageDraw.Draw(layer, 'RGBA').polygon(poly, fill=col, outline=outline)
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

    icon = build_heart_icon()
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
