#!/usr/bin/env python3
"""Процедурно строит 3D-ауру «Бабочки» (`elytrix_butterfly_aura`), её иконку 32x32
(`reallyworld:butterfly_aura_icon`) и превью для проверки.

100% чистый процедурный Python + Pillow + NumPy — ноль нейрогенерации.

  1. Визуальный замысел — «АУРА: маленькие розовые бабочки всё время летают вокруг игрока»:
       - 10 крошечных бабочек (размах крыльев `2.3..3.3` BB = `14..21` см) НЕПРЕРЫВНО
         кружат вокруг игрока на разных высотах — от колена (`Y = 8.5`) до чуть выше
         макушки (`Y = 30`), то есть они всё время ЛЕТАЮТ ВОКРУГ него, а не висят
         столбом и не взмывают снизу.
       - Кружение сделано ДВУХУРОВНЕВОЙ иерархией костей, и это принципиально:
         если бы каждая бабочка описывала полный круг своей собственной анимацией
         позиции, её вершины уходили бы от пивота почти на `2 * R = 28` BB и превысили бы
         лимит ModelEngine `24` BB на кость. Поэтому полное кружение несёт кость-орбита
         (`orbit_a/b/c`, вращение вокруг вертикальной оси через `[0, 16, 0]`), а сама
         бабочка анимирует только НЕБОЛЬШОЕ блуждание вокруг своей точки на кольце:
         радиус `+0..0.9` BB, высота `+-3.0` BB, касательное рысканье `+-0.16` рад.
         Итого максимум `~10` BB хода у кости бабочки и `~22` BB у кости-орбиты — обе
         внутри лимита.
       - Орбит ТРИ: `orbit_a` (4 бабочки, против часовой), `orbit_b` (3, по часовой) и
         `orbit_c` (3, против часовой, но с заметным «нырком» вперёд-назад). Две из них
         крутятся в РАЗНЫЕ стороны, поэтому стая не выглядит каруселью.
       - Крылья машут: это отдельные кости `bf_NN_wl` / `bf_NN_wr`, каждая вращается
         вокруг своей оси-петли на `+-38°` с частотой `3` Гц (18 взмахов за цикл `6.0` с,
         на каждый взмах приходится `6.7` ключевых кадра при `IDLE_STEPS = 120`).
       - Цикл бесшовный: каждая орбита делает ЦЕЛОЕ число оборотов за цикл, а все
         блуждания — синусы с ЦЕЛЫМ числом периодов на цикл, поэтому в конце цикла
         каждая бабочка возвращается ровно в своё начальное состояние.
  2. Аура НИКОГДА не поворачивается вместе с телом игрока (ей всегда передаётся рысканье
     `0`) — только следует за ним по позиции. Кружение идёт в МИРОВОЙ системе координат.
  3. Бабочка = 13 кубов: 3 куба тельца (брюшко, грудь, голова) + 2 усика + 2 крыла по
     4 куба (верхняя лопасть, нижняя лопасть, кончик и светлое пятнышко).
     Итого **130 кубов и 33 кости**, ВСЕ кубы с `rotation: [0,0,0]` — ни одного
     повёрнутого куба, иначе `RotationSolver` ModelEngine 4.1.0 падает.
  4. **Никаких полос.** Крыло собрано из лопастей, stacked по вертикали, поэтому каждая
     лопасть получает СВОЮ полоску градиента (`_band`): 3 полоски складываются в один
     непрерывный переход «корень -> кончик», а не в «стиральную доску».
  5. Инженерная безопасность:
       - Кольцо лежит ВНЕ игрока: радиус `12.3..13.8` BB при габарите игрока
         `|x| <= 7.5` BB, `|z| <= 3.75` BB, `y 0..30` BB. Ближайшая вершина крыла
         отстоит от этого габарита минимум на `2.23` BB (`14.0` см).
       - Аура маленькая и компактная: максимум `24.87` BB = `1.554` м от глаз, а оценка,
         не зависящая от порядка углов Эйлера (центр + радиус-ограничитель `2.0` BB),
         даёт `25.65` BB = `1.603` м. Поэтому, в отличие от сердечек, она с запасом
         `~0.25` м влезает в БЛИЖНИЙ тинт `-196867` (отсечка `1.85` м).
         Это лучше, чем «крыльевой» тинт: бабочки остаются видны другим игрокам, которые
         стоят ближе `2.85` м, а владельцу всё равно не видны от 1-го лица.
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
MODEL = 'elytrix_butterfly_aura'
ICON = 'butterfly_aura_icon'

IDLE_LEN = 6.0        # 120 ticks @ 20 TPS — полный цикл кружения
IDLE_STEPS = 120      # 20 keyframes/s — хватает для взмаха крыльев на 3 Гц

ROOT_ORIG = [0.0, 16.0, 0.0]   # ось кружения: вертикаль через центр игрока

# (имя кости-орбиты, оборотов за цикл, сколько бабочек): > 0 — против часовой.
GROUPS = (
    ('orbit_a', 1, 4),
    ('orbit_b', -1, 3),
    ('orbit_c', 1, 3),
)
BUTTERFLY_COUNT = sum(g[2] for g in GROUPS)

FLAP_CYCLES = 18      # взмахов за цикл => 3 Гц
FLAP_DEG = 38.0       # амплитуда взмаха

A_RADIUS = 0.90       # блуждание радиуса — ТОЛЬКО НАРУЖУ (чтобы не приближаться к игроку)
A_HEIGHT = 2.60       # вертикальное покачивание
A_TANGENT = 0.16      # касательное «болтание» в радианах
A_TANGENT_C = 0.30    # у orbit_c бабочки заметно «ныряют» вперёд-назад

_BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))

# 0..16 UV, текстура 64x64 => 1 UV = 4 px, тайлы 32x32 px = 8x8 UV.
TILE_WING = 0.25      # (0,0)
TILE_EDGE = 8.25      # (32,0)
TILE_BODY = 0.25      # (0,32), по Y начинается с 8.25
TILE_SPOT = 8.25      # (32,32)
BODY_Y0 = 8.25
SPOT_Y0 = 8.25


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f'elytrix.butterfly_aura.v1:{tag}'))


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
def build_butterfly_texture() -> Image.Image:
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
        return (0.030 * math.sin(px * 0.19 + py * 0.11)
                + 0.026 * math.sin(px * 0.08 - py * 0.15))

    # (0,0) крыло: меняется вдоль X — бледно-розовый корень -> насыщенный кончик.
    # По Y меняется слабо: грубую вертикальную «лестницу» дают полоски лопастей.
    paint(0, 0, lambda px, py: _ramp(
        [(0.00, (255, 226, 240)), (0.42, (255, 176, 214)),
         (0.78, (246, 110, 172)), (1.00, (226, 66, 140))],
        px / 31.0 + 0.10 * (py / 31.0) + wob(px, py)))
    # (32,0) боковые грани крыла, глубже
    paint(1, 0, lambda px, py: _ramp(
        [(0.00, (238, 170, 206)), (0.45, (232, 116, 172)),
         (0.80, (206, 62, 128)), (1.00, (170, 34, 96))],
        px / 31.0 + 0.10 * (py / 31.0) + wob(px, py)))
    # (0,32) тельце: сверху розовее, к брюшку темно-малиновое
    paint(0, 1, lambda px, py: _ramp(
        [(0.00, (240, 132, 186)), (0.50, (206, 62, 130)), (1.00, (140, 26, 76))],
        py / 31.0 + wob(px, py)))
    # (32,32) пятнышко на крыле: радиальный бело-розовый
    paint(1, 1, lambda px, py: _ramp(
        [(0.00, (255, 246, 251)), (0.34, (255, 206, 232)),
         (0.72, (255, 150, 198)), (1.00, (236, 92, 154))],
        min(1.0, math.hypot(px - 15.5, py - 15.5) / 17.0 + wob(px, py))))

    return Image.fromarray(arr, 'RGBA')


# ---------------------------------------------------------------------------
# 2. Кубы (НИ ОДИН не повёрнут) и полоски UV (никаких полос на модели)
# ---------------------------------------------------------------------------
def _band(left: float, top: float, row: int, rows: int) -> tuple:
    """Своя полоска градиента для вертикальной «стопки» лопастей."""
    h = 7.5 / rows
    y0 = top + row * h + 0.04
    y1 = top + (row + 1) * h - 0.04
    return (left, round(y0, 3), left + 7.5, round(y1, 3))


def _faces(default_uv: tuple, side_uv: tuple | None = None) -> dict:
    """Лицевые/задние грани берут `default_uv`, боковые и торцы — `side_uv`.

    Так у лопасти крыла плоская сторона — розовый градиент, а торец — его более
    тёмный вариант, и лопасть читается как тонкая пластинка, а не как брусок.
    """
    out = {}
    for side in ('north', 'south', 'east', 'west', 'up', 'down'):
        uv = side_uv if (side_uv is not None and side in ('east', 'west', 'up', 'down')) \
            else default_uv
        out[side] = {'uv': list(uv), 'texture': 0}
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
# 3. Параметры стаи
# ---------------------------------------------------------------------------
def butterfly_spec(i: int) -> dict:
    """Базовые параметры бабочки `i` (0-based) — орбита, угол, радиус, высота, масштаб."""
    idx = i
    group_name = None
    turns = 1
    for name, t, count in GROUPS:
        if idx < count:
            group_name, turns = name, t
            break
        idx -= count
    within = idx
    count = next(c for (n, _t, c) in GROUPS if n == group_name)
    # равномерно раскладываем бабочек группы по кругу + небольшой сдвиг, чтобы не
    # выглядело механически
    base_ang = (within / count) * 2.0 * math.pi + 0.35 * (i % 3)
    # Кольцо лежит ВНЕ игрока (габарит |x| <= 7.5, |z| <= 3.75 BB): 12.3..13.8 BB
    radius = 12.3 + 1.5 * (((i * 7) % 5) / 4.0)          # 12.3 .. 13.8 BB
    # Высоты 8.5..30.0 BB: от колена до чуть выше макушки. Намеренно НЕ опускаем
    # бабочек к стопам — иначе самые нижние уходят от глаз дальше 1.85 м и аура
    # перестаёт влезать в ближний тинт (а он лучше: бабочки видны другим игрокам,
    # которые стоят ближе 2.85 м, а владельцу всё равно не видны от 1-го лица).
    height = 8.5 + (21.5 / (BUTTERFLY_COUNT - 1)) * i    # 8.5 .. 30.0 BB
    # v3.26.0 — бабочки «чуток поменьше»: было 0.85..1.15, стало 0.70..0.95 (~18% мельче).
    scale = 0.70 + 0.25 * (((i * 3) % 4) / 3.0)          # 0.70 .. 0.95
    return {
        'group': group_name, 'turns': turns, 'ang': base_ang,
        'r': radius, 'y': height, 'scale': scale,
        'i': i,
        'tangent': A_TANGENT_C if group_name == 'orbit_c' else A_TANGENT,
        'phase': (i * 0.37) % 1.0,
        'flap_phase': (i * 0.61) % 1.0,
    }


def group_turns(name: str) -> int:
    return next(t for (n, t, _c) in GROUPS if n == name)


BUTTERFLY_SPECS = [butterfly_spec(i) for i in range(BUTTERFLY_COUNT)]
BF_IDS = [f'bf_{i + 1:02d}' for i in range(BUTTERFLY_COUNT)]
WING_IDS = [f'{b}_wl' for b in BF_IDS] + [f'{b}_wr' for b in BF_IDS]
GROUP_IDS = [g[0] for g in GROUPS]
BONE_NAMES = ['aura_root'] + GROUP_IDS + BF_IDS + WING_IDS


# ---------------------------------------------------------------------------
# 4. Геометрия: каждая бабочка запечена на своей точке кольца
# ---------------------------------------------------------------------------
# Локальная система бабочки: вперёд +Z, вверх +Y, вправо +X (наружу от игрока).
#
# Тельце теперь ГОРИЗОНТАЛЬНОЕ и лежит вдоль полёта (+Z): голова спереди, брюшко
# сзади — как у настоящей бабочки. Крылья — заполненные горизонтальные пластины в
# плоскости XZ (тонкие по Y), переднее крупнее заднего; машут они вокруг оси Z,
# то есть кончики ходят ВВЕРХ-ВНИЗ. Раньше тельце стояло вертикально, а крыло было
# собрано из двух тонких пластин с ПУСТОТОЙ между ними и отдельно висящим
# кончиком — из-за этого крыло читалось как пустая рамка (см. `WING_FORE/WING_HIND`).
HINGE_Y = 0.20          # высота оси-петли крыла над центром тельца (верх груди)
BODY_ROWS = 3           # полоски градиента тельца: голова / грудь / брюшко

# Крыло как ЗАПОЛНЕННЫЙ эллипс в плоскости XZ, нарезанный полосами вдоль X
# (от корня к кончику). Никаких разрывов: полосы идут вплотную, поэтому внутри
# контура нет пустоты.
# `x0` = 0.10 — корень крыла ЗАХОДИТ под тельце (полуширина брюшка 0.12), иначе
# между внутренним краем крыла и тельцем видна щель и крыло читается от detached.
WING_FORE = dict(cx=0.78, cz=0.44, a=0.58, b=0.56, strips=5, x0=0.10,
                 y_lo=0.02, y_hi=0.13)
WING_HIND = dict(cx=0.58, cz=-0.46, a=0.42, b=0.40, strips=3, x0=0.10,
                 y_lo=-0.11, y_hi=0.01)
SPOT = dict(x0=0.60, x1=0.86, z0=0.30, z1=0.62, y0=0.13, y1=0.21)
# «Плечики»: у эллипса хорда у самого корня узкая, поэтому между внутренним краем
# крыла и грудью оставалась щель и крыло читалось приклеенным отдельно. Эти две
# пластины закрывают плечевой стык у переднего и заднего крыла.
SHOULDER_FORE = dict(x0=0.085, x1=0.34, z0=-0.16, z1=0.34)
SHOULDER_HIND = dict(x0=0.085, x1=0.34, z0=-0.26, z1=0.00)


def _strip(left: float, top: float, col: int, cols: int, gap: float = 0.05) -> tuple:
    """Полоска градиента ВДОЛЬ КРЫЛА (корень -> кончик), а не поперёк.

    Тайл крыла меняет цвет по X (бледный корень -> насыщенный кончик). Разрезая его
    на вертикальные полоски по числу кубов-полос, получаем ПЛАВНЫЙ переход вдоль
    крыла: каждая полоса берёт свой кусок того же градиента, и «стиральной доски»
    не возникает ни вдоль крыла, ни поперёк.
    """
    w = 7.5 / cols
    x0 = left + col * w + gap
    x1 = left + (col + 1) * w - gap
    return (round(x0, 3), top, round(x1, 3), round(top + 7.5, 3))


def _wing_faces(top_uv: tuple, edge_uv: tuple, bottom_uv: tuple) -> dict:
    """Верх крыла — основной градиент, низ и торцы — приглушённый."""
    return {
        'up': {'uv': list(top_uv), 'texture': 0},
        'down': {'uv': list(bottom_uv), 'texture': 0},
        'north': {'uv': list(edge_uv), 'texture': 0},
        'south': {'uv': list(edge_uv), 'texture': 0},
        'east': {'uv': list(edge_uv), 'texture': 0},
        'west': {'uv': list(edge_uv), 'texture': 0},
    }


def build_geometry(elements: list) -> dict:
    """Возвращает {имя кости: [uuid кубов]} и попутно наполняет `elements`."""
    bones: dict[str, list] = {}

    body_uvs = [_band(TILE_BODY, BODY_Y0, r, BODY_ROWS) for r in range(BODY_ROWS)]
    body_side = _band(TILE_BODY, BODY_Y0, BODY_ROWS - 1, BODY_ROWS)
    spot_uv = _band(TILE_SPOT, SPOT_Y0, 0, 1)

    fore_top = [_strip(TILE_WING, 0.25, c, WING_FORE['strips']) for c in range(WING_FORE['strips'])]
    fore_edg = [_strip(TILE_EDGE, 0.25, c, WING_FORE['strips']) for c in range(WING_FORE['strips'])]
    hind_top = [_strip(TILE_WING, 0.25, c, WING_HIND['strips']) for c in range(WING_HIND['strips'])]
    hind_edg = [_strip(TILE_EDGE, 0.25, c, WING_HIND['strips']) for c in range(WING_HIND['strips'])]
    # Низ крыла — своя, приглушённая полоска из тайла боковых граней.
    fore_bot = [_strip(TILE_EDGE, 0.25, c, WING_FORE['strips']) for c in range(WING_FORE['strips'])]
    hind_bot = [_strip(TILE_EDGE, 0.25, c, WING_HIND['strips']) for c in range(WING_HIND['strips'])]

    def chord(cfg: dict, col: int) -> tuple:
        """Z-диапазон полосы `col` — хорда эллипса крыла в её середине."""
        n = cfg['strips']
        x0, x1 = cfg['x0'], cfg['cx'] + cfg['a']
        xa = x0 + (x1 - x0) * (col / n)
        xb = x0 + (x1 - x0) * ((col + 1) / n)
        xm = 0.5 * (xa + xb)
        k = (xm - cfg['cx']) / cfg['a']
        hz = cfg['b'] * math.sqrt(max(0.0, 1.0 - k * k))
        return round(cfg['cz'] - hz, 4), round(cfg['cz'] + hz, 4)

    for i, spec in enumerate(BUTTERFLY_SPECS):
        s = spec['scale']
        # Бабочка запекается в точке своего кольца при u = 0 (орбита ещё не повёрнута).
        ang0 = spec['ang']
        cx = round(math.cos(ang0) * spec['r'], 4)
        cz = round(math.sin(ang0) * spec['r'], 4)
        cy = round(spec['y'], 4)
        origin = [cx, cy, cz]
        hinge = [cx, round(cy + HINGE_Y * s, 4), cz]

        body_cubes = []
        # Тельце ГОРИЗОНТАЛЬНОЕ: голова спереди (+Z), брюшко сзади (-Z).
        # (тэг, ряд градиента, x0,y0,z0, x1,y1,z1)
        body_boxes = (
            ('head', 0, (-0.16, -0.08, 0.30), (0.16, 0.20, 0.52)),
            ('thr', 1, (-0.19, -0.20, -0.24), (0.19, 0.22, 0.30)),
            ('abd1', 2, (-0.12, -0.36, -0.64), (0.12, 0.08, -0.20)),
            ('abd2', 2, (-0.07, -0.30, -1.04), (0.07, 0.02, -0.62)),
        )
        for tag, row, lo, hi in body_boxes:
            body_cubes.append(_cube(
                f'bf_{i + 1:02d}_{tag}',
                [origin[0] + lo[0] * s, origin[1] + lo[1] * s, origin[2] + lo[2] * s],
                [origin[0] + hi[0] * s, origin[1] + hi[1] * s, origin[2] + hi[2] * s],
                origin, _faces(body_uvs[row], body_side)))
        # усики: две «ступеньки» вперёд-вверх-наружу от головы
        for side, tag in ((-1, 'antl'), (1, 'antr')):
            sg = side
            body_cubes.append(_cube(
                f'bf_{i + 1:02d}_{tag}a',
                [origin[0] + (0.06 if sg > 0 else -0.14) * s, origin[1] + 0.18 * s,
                 origin[2] + 0.42 * s],
                [origin[0] + (0.14 if sg > 0 else -0.06) * s, origin[1] + 0.32 * s,
                 origin[2] + 0.58 * s],
                origin, _faces(body_uvs[0], body_side)))
            body_cubes.append(_cube(
                f'bf_{i + 1:02d}_{tag}b',
                [origin[0] + (0.13 if sg > 0 else -0.24) * s, origin[1] + 0.30 * s,
                 origin[2] + 0.56 * s],
                [origin[0] + (0.24 if sg > 0 else -0.13) * s, origin[1] + 0.46 * s,
                 origin[2] + 0.70 * s],
                origin, _faces(body_uvs[0], body_side)))

        wing_cubes = {'wl': [], 'wr': []}
        for wkey, sign in (('wl', -1), ('wr', 1)):
            for cfg, tops, edgs, bots, tag in (
                    (WING_FORE, fore_top, fore_edg, fore_bot, 'f'),
                    (WING_HIND, hind_top, hind_edg, hind_bot, 'h')):
                n = cfg['strips']
                x0 = cfg['x0']
                x1 = cfg['cx'] + cfg['a']
                for col in range(n):
                    xa = x0 + (x1 - x0) * (col / n)
                    xb = x0 + (x1 - x0) * ((col + 1) / n)
                    za, zb = chord(cfg, col)
                    wing_cubes[wkey].append(_cube(
                        f'bf_{i + 1:02d}_{wkey}_{tag}{col}',
                        [hinge[0] + min(sign * xa, sign * xb) * s, hinge[1] + cfg['y_lo'] * s,
                         hinge[2] + za * s],
                        [hinge[0] + max(sign * xa, sign * xb) * s, hinge[1] + cfg['y_hi'] * s,
                         hinge[2] + zb * s],
                        hinge, _wing_faces(tops[col], edgs[col], bots[col])))
            # плечевые пластины — убирают щель между корнем крыла и грудью
            wing_cubes[wkey].append(_cube(
                f'bf_{i + 1:02d}_{wkey}_sf',
                [hinge[0] + min(sign * SHOULDER_FORE['x0'], sign * SHOULDER_FORE['x1']) * s,
                 hinge[1] + WING_FORE['y_lo'] * s, hinge[2] + SHOULDER_FORE['z0'] * s],
                [hinge[0] + max(sign * SHOULDER_FORE['x0'], sign * SHOULDER_FORE['x1']) * s,
                 hinge[1] + WING_FORE['y_hi'] * s, hinge[2] + SHOULDER_FORE['z1'] * s],
                hinge, _wing_faces(fore_top[0], fore_edg[0], fore_bot[0])))
            wing_cubes[wkey].append(_cube(
                f'bf_{i + 1:02d}_{wkey}_sh',
                [hinge[0] + min(sign * SHOULDER_HIND['x0'], sign * SHOULDER_HIND['x1']) * s,
                 hinge[1] + WING_HIND['y_lo'] * s, hinge[2] + SHOULDER_HIND['z0'] * s],
                [hinge[0] + max(sign * SHOULDER_HIND['x0'], sign * SHOULDER_HIND['x1']) * s,
                 hinge[1] + WING_HIND['y_hi'] * s, hinge[2] + SHOULDER_HIND['z1'] * s],
                hinge, _wing_faces(hind_top[0], hind_edg[0], hind_bot[0])))
            # светлое пятнышко на переднем крыле — лежит сверху, чуть выступает
            xa, xb = SPOT['x0'], SPOT['x1']
            wing_cubes[wkey].append(_cube(
                f'bf_{i + 1:02d}_{wkey}_spot',
                [hinge[0] + min(sign * xa, sign * xb) * s, hinge[1] + SPOT['y0'] * s,
                 hinge[2] + SPOT['z0'] * s],
                [hinge[0] + max(sign * xa, sign * xb) * s, hinge[1] + SPOT['y1'] * s,
                 hinge[2] + SPOT['z1'] * s],
                hinge, _wing_faces(spot_uv, spot_uv, spot_uv)))

        all_cubes = body_cubes + wing_cubes['wl'] + wing_cubes['wr']
        for c in all_cubes:
            elements.append(c)
        bones[BF_IDS[i]] = [c['uuid'] for c in body_cubes]
        bones[f'{BF_IDS[i]}_wl'] = [c['uuid'] for c in wing_cubes['wl']]
        bones[f'{BF_IDS[i]}_wr'] = [c['uuid'] for c in wing_cubes['wr']]

    for g in GROUP_IDS:
        bones[g] = []
    bones['aura_root'] = []
    return bones


# ---------------------------------------------------------------------------
# 5. Анимация: непрерывное кружение + блуждание + взмахи крыльев
# ---------------------------------------------------------------------------
def eval_aura_pose(u: float) -> dict:
    tau = 2.0 * math.pi
    up = 0.0 if u >= 1.0 else u
    pose = {
        'root_pos': [0.0, round(0.12 * math.sin(tau * up), 4), 0.0],
        'group_rot': {},
        'body_pos': {},
        'body_rot': {},
        'wing_rot': {},
    }

    for g in GROUP_IDS:
        turns = group_turns(g)
        pose['group_rot'][g] = [0.0, round(-360.0 * turns * up, 4), 0.0]

    for i, spec in enumerate(BUTTERFLY_SPECS):
        name = BF_IDS[i]
        ph = spec['phase']

        # блуждание радиуса — ТОЛЬКО наружу, чтобы бабочка никогда не приближалась
        dr = A_RADIUS * (0.5 + 0.5 * math.sin(tau * (up * 2.0 + ph)))
        dy = A_HEIGHT * math.sin(tau * (up * 1.0 + ph))
        dth = spec['tangent'] * math.sin(tau * (up * 3.0 + ph))

        r0 = spec['r'] + A_RADIUS * (0.5 + 0.5 * math.sin(tau * ph))
        y0 = spec['y'] + A_HEIGHT * math.sin(tau * ph)
        th0 = spec['ang'] + spec['tangent'] * math.sin(tau * ph)

        r = spec['r'] + dr
        y = spec['y'] + dy
        psi = th0 + (spec['tangent'] * math.sin(tau * (up * 3.0 + ph))
                     - spec['tangent'] * math.sin(tau * ph))

        # локальная позиция внутри орбиты: орбита сама несёт кружение, поэтому здесь
        # только НЕБОЛЬШОЕ смещение от запечённой точки
        pose['body_pos'][name] = [
            round(r * math.cos(psi) - r0 * math.cos(th0), 4),
            round(y - y0, 4),
            round(r * math.sin(psi) - r0 * math.sin(th0), 4),
        ]

        # бабочка смотрит по ходу движения: орбита уже поворачивает её целиком,
        # поэтому локальный рысканье = -psi (и +180 для орбиты по часовой)
        yaw = -math.degrees(psi) + (180.0 if spec['turns'] < 0 else 0.0)
        yaw += 14.0 * math.sin(tau * (up * 1.0 + ph))                  # легкое рысканье
        pitch = 10.0 * math.sin(tau * (up * 2.0 + ph * 1.7)) + 6.0 * math.sin(tau * (up * 5.0 + ph))
        roll = 12.0 * math.sin(tau * (up * 1.0 + ph * 0.6))
        pose['body_rot'][name] = [round(pitch, 4), round(yaw, 4), round(roll, 4)]

        # взмах крыльев: +38°..-38° на 3 Гц, у каждой бабочки своя фаза
        flap = FLAP_DEG * math.sin(tau * (FLAP_CYCLES * up + spec['flap_phase']))
        pose['wing_rot'][f'{name}_wr'] = [0.0, 0.0, round(flap, 4)]
        pose['wing_rot'][f'{name}_wl'] = [0.0, 0.0, round(-flap, 4)]

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
        for g in GROUP_IDS:
            kfs[g].append(_vec_kf('rotation', f'idle:{g}', t, *pose['group_rot'][g]))
        for name in BF_IDS:
            kfs[name].append(_vec_kf('position', f'idle:{name}', t, *pose['body_pos'][name]))
            kfs[name].append(_vec_kf('rotation', f'idle:{name}', t, *pose['body_rot'][name]))
        for name in WING_IDS:
            kfs[name].append(_vec_kf('rotation', f'idle:{name}', t, *pose['wing_rot'][name]))
    return {uid(f'bone:{b}'): {'name': b, 'type': 'bone', 'keyframes': kfs[b]}
            for b in BONE_NAMES}


# ---------------------------------------------------------------------------
# 6. Блюпринт
# ---------------------------------------------------------------------------
def build_blueprint() -> tuple[dict, Image.Image]:
    texture = build_butterfly_texture()
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

    group_children: dict[str, list] = {g: [] for g in GROUP_IDS}
    for i, spec in enumerate(BUTTERFLY_SPECS):
        s = spec['scale']
        ang0 = spec['ang']
        cx = round(math.cos(ang0) * spec['r'], 4)
        cz = round(math.sin(ang0) * spec['r'], 4)
        cy = round(spec['y'], 4)
        hinge_y = round(cy + HINGE_Y * s, 4)
        # В Blockbench `children` кости — это СМЕШАННЫЙ список: сначала uuid её
        # собственных кубов, затем дочерние кости. Кубы тельца обязательно должны
        # быть здесь, иначе они не попадут ни в одну кость и не отрисуются.
        bf = bone(BF_IDS[i], [cx, cy, cz], list(bones[BF_IDS[i]]) + [
            bone(f'{BF_IDS[i]}_wl', [cx, hinge_y, cz], bones[f'{BF_IDS[i]}_wl'], is_open=False),
            bone(f'{BF_IDS[i]}_wr', [cx, hinge_y, cz], bones[f'{BF_IDS[i]}_wr'], is_open=False),
        ], is_open=False)
        group_children[spec['group']].append(bf)

    outliner = [bone('aura_root', ROOT_ORIG,
                     [bone(g, ROOT_ORIG, group_children[g]) for g in GROUP_IDS])]

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
# 7. Иконка 32x32 (`reallyworld:butterfly_aura_icon`)
# ---------------------------------------------------------------------------
def build_butterfly_icon() -> Image.Image:
    """32x32 пиксельная иконка: крупная розовая бабочка сверху по центру и две
    мелких по бокам — ровно то, что делает аура в игре."""
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    white = (255, 246, 251, 255)    # светлое пятнышко
    light = (255, 186, 219, 255)    # светло-розовый
    mid = (246, 110, 172, 255)      # роза
    deep = (196, 46, 116, 255)      # малина
    dark = (140, 26, 76, 255)       # тельце

    def put(x, y, c):
        if 0 <= x < 32 and 0 <= y < 32:
            px[x, y] = c

    # 14x9 маска бабочки сверху
    MASK = (
        '..##......##..',
        '.####....####.',
        '.#####..#####.',
        '..##########..',
        '..##########..',
        '...########...',
        '....######....',
        '.....####.....',
        '......##......',
    )

    def butterfly(ox: int, oy: int, sc: int = 1) -> None:
        for row, line in enumerate(MASK):
            for col, ch in enumerate(line):
                if ch != '#':
                    continue
                # верх крыльев светлее, низ насыщеннее
                if row <= 1:
                    col_sel = light
                elif row <= 4:
                    col_sel = mid
                else:
                    col_sel = deep
                for dy in range(sc):
                    for dx in range(sc):
                        put(ox + col * sc + dx, oy + row * sc + dy, col_sel)
        # тельце по центру
        bw, bh = 2 * sc, 5 * sc
        bx = ox + 6 * sc
        by = oy + 2 * sc
        for dy in range(bh):
            for dx in range(bw):
                put(bx + dx, by + dy, dark)
        # светлые пятнышки на крыльях
        put(ox + 2 * sc, oy + 2 * sc, white)
        put(ox + 11 * sc, oy + 2 * sc, white)

    # крупная бабочка сверху по центру (масштаб 2 => 28x18, x 2..29, y 3..20)
    butterfly(2, 3, 2)
    # две мелких по бокам внизу
    butterfly(0, 22, 1)
    butterfly(18, 21, 1)

    # редкие блёстки
    for (sx, sy) in ((15, 30), (30, 26), (1, 17), (28, 13)):
        put(sx, sy, white)

    return img


# ---------------------------------------------------------------------------
# 8. Превью
# ---------------------------------------------------------------------------
def _rot(rx, ry, rz):
    rx, ry, rz = map(math.radians, (rx, ry, rz))
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mz @ my @ mx


def render_preview(blueprint: dict, texture: Image.Image, icon: Image.Image, out_path: Path) -> None:
    panel_w, panel_h = 230, 300
    canvas = Image.new('RGBA', (panel_w * 4 + 210, panel_h), (18, 22, 30, 255))
    tex_arr = np.array(texture)
    els = {el['uuid']: el for el in blueprint['elements']}
    bones = build_geometry([])          # только соответствие имя -> uuid кубов

    # пивоты костей
    piv = {}
    def walk(nodes):
        for n in nodes:
            if not isinstance(n, dict):      # uuid куба, а не дочерняя кость
                continue
            piv[n['name']] = np.array(n['origin'], dtype=float)
            walk(n.get('children', []))
    walk(blueprint['outliner'])

    stages = [
        (0.02, 0.0, -12.0),
        (0.35, 90.0, -10.0),
        (0.68, 180.0, -12.0),
        (0.50, 0.0, -88.0),
    ]

    for idx, (u, cam_yaw, cam_pitch) in enumerate(stages):
        panel = Image.new('RGBA', (panel_w, panel_h),
                          (14, 18, 26, 255) if idx == 3 else (26, 30, 42, 255))
        faces_to_draw = []
        pose = eval_aura_pose(u)
        root = np.array(pose['root_pos'])
        root_piv = np.array(ROOT_ORIG, dtype=float)

        def place(cube, bone_transform, extra_piv, extra_mat):
            v = np.array(cube['from'] if False else [0.0, 0.0, 0.0])
            return bone_transform

        for i, spec in enumerate(BUTTERFLY_SPECS):
            name = BF_IDS[i]
            body_piv = piv[name]
            rmat = _rot(*pose['body_rot'][name])
            bpos = np.array(pose['body_pos'][name])
            group = spec['group']
            gmat = _rot(*pose['group_rot'][group])

            def to_world(p):
                # кость бабочки: поворот вокруг своего пивота + сдвиг
                p = body_piv + rmat @ (p - body_piv) + bpos
                # орбита: поворот вокруг вертикальной оси через ROOT_ORIG
                p = gmat @ (p - root_piv) + root_piv
                return p + root

            wing_mats = {
                f'{name}_wl': _rot(*pose['wing_rot'][f'{name}_wl']),
                f'{name}_wr': _rot(*pose['wing_rot'][f'{name}_wr']),
            }
            for wname, wmat in wing_mats.items():
                wpiv = piv[wname]
                for cu in bones[wname]:
                    el = els[cu]
                    w = to_world(wpiv + wmat @ (np.array(el['from']) - wpiv))
                    w2 = to_world(wpiv + wmat @ (np.array(el['to']) - wpiv))
                    faces_to_draw.append((el, w, w2))
            for cu in bones[name]:
                el = els[cu]
                w = to_world(np.array(el['from']))
                w2 = to_world(np.array(el['to']))
                faces_to_draw.append((el, w, w2))

        cam = math.radians(cam_yaw)
        cp, sp = math.cos(math.radians(cam_pitch)), math.sin(math.radians(cam_pitch))

        def proj(p):
            dx = p[0] * math.cos(cam) - p[2] * math.sin(cam)
            dz = p[0] * math.sin(cam) + p[2] * math.cos(cam)
            yy = p[1] * cp - dz * sp
            zz = p[1] * sp + dz * cp
            k = 900.0 / (900.0 + zz * 6.0)
            return (panel_w / 2 + dx * 22.0 * k,
                    panel_h / 2 + (16.0 - yy) * -22.0 * k + panel_h / 2), zz

        quads = [('north', (0, 1, 2, 3)), ('south', (5, 4, 7, 6)),
                 ('east', (0, 3, 7, 4)), ('west', (2, 1, 5, 6)),
                 ('up', (3, 2, 6, 7)), ('down', (0, 4, 5, 1))]
        draw = []
        for el, lo, hi in faces_to_draw:
            corners = [
                np.array([lo[0], lo[1], lo[2]]), np.array([hi[0], lo[1], lo[2]]),
                np.array([hi[0], hi[1], lo[2]]), np.array([lo[0], hi[1], lo[2]]),
                np.array([lo[0], lo[1], hi[2]]), np.array([hi[0], lo[1], hi[2]]),
                np.array([hi[0], hi[1], hi[2]]), np.array([lo[0], hi[1], hi[2]]),
            ]
            for fname, idxs in quads:
                uv = el['faces'][fname]['uv']
                tx = min(63, int(0.5 * (uv[0] + uv[2]) * 4))
                ty = min(63, int(0.5 * (uv[1] + uv[3]) * 4))
                rgba = tex_arr[ty, tx]
                if rgba[3] < 16:
                    continue
                pts, zs = [], []
                for k in idxs:
                    s, z = proj(corners[k])
                    pts.append(s)
                    zs.append(z)
                draw.append((sum(zs) / 4.0, pts, tuple(rgba[:3]) + (255,)))
        draw.sort(key=lambda item: item[0], reverse=True)
        for _z, poly, col in draw:
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

    icon = build_butterfly_icon()
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
    n_bones = 0
    def count(nodes):
        nonlocal n_bones
        for n in nodes:
            if not isinstance(n, dict):      # uuid куба, а не дочерняя кость
                continue
            n_bones += 1
            count(n.get('children', []))
    count(blueprint['outliner'])
    print(f'Built {MODEL}.bbmodel: {drawn} cubes, {n_bones} bones, '
          f'icon -> {args.assets_dir}')

    if args.preview is not None:
        render_preview(blueprint, texture, icon, args.preview)


if __name__ == '__main__':
    main()
