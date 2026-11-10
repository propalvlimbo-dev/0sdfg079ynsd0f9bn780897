#!/usr/bin/env python3
"""Процедурно строит 3D-ауру «Смертельная аура» (`elytrix_death_aura`), её иконку
32x32 (`reallyworld:death_aura_icon`) и превью для проверки.

100% чистый процедурный Python + Pillow + NumPy — ноль нейрогенерации.

  1. Визуальный замысел — «СТРАШНАЯ АУРА: из-под ног всё время летит пепел»:
       - **ВОСХОДЯЩИЙ ВИХРЬ (v3.26.1).** Пепел НЕ просто поднимается вверх и НЕ
         кружит по орбите на одной высоте — он ЗАКРУЧИВАЕТСЯ вокруг игрока и
         одновременно ВСПЛЫВАЕТ, то есть каждое хлопье описывает винтовую линию
         от самых стоп до уровня глаз и чуть выше. Это сделано специально, чтобы
         полёт ОТЛИЧАЛСЯ от двух других аур:
           * `Аура сердечек` — подъём БЕЗ спирали вообще (рандомный разнобой);
           * `Аура бабочек` — орбиты на ПОСТОЯННОЙ высоте, к тому же в РАЗНЫЕ
             стороны (стая не карусель);
           * `Смертельная аура` — ОДИН согласованный смерч: ВСЕ хлопья крутятся
             в ОДНУ сторону (`TURNS > 0`), как настоящий вихрь, а не россыпь.
       - Вихрь РАСШИРЯЕТСЯ кверху: у стоп радиус минимальный (`11.6..12.6` BB),
         наверху — максимальный (`+1.4..+2.4` BB). Столб читается как воронка
         смерча, а не как ровный цилиндр.
       - Скорость закрутки у каждого хлопья СВОЯ (`TURNS = 0.75..1.35` оборота
         за цикл), поэтому столб расслаивается на витки и «живёт», а не крутится
         монолитным барабаном.
       - Пепла МНОГО (просьба игрока): `34` хлопьев `ash_01..ash_34`.
       - МОДЕЛЬ ХЛОПЬЯ v3.28.0. Одна плоская пластинка читалась как конфетти, а
         пять кубов в одной точке — как комок, поэтому теперь хлопье — это
         **РВАНОЕ ПЕПЕЛЬНОЕ ПЯТНО**: основная пластинка（`0.76..1.04` BB) плюс
         ОДИН смещённый осколок, который ломает прямоугольный силуэт, плюс
         (у двух третей хлопьев) ТЛЕЮЩИЙ УГОЛЁК ровно по центру — он даёт
         «страшность»: в сером пепле вспыхивают оранжевые точки. Размер и
         пропорции у каждого хлопья свои, поэтому пепел не выглядит штампованным.
       - Хлопья КУВЫРКАЮТСЯ: вращение по всем трём осям на ЦЕЛОЕ число оборотов
         за цикл (`nx/ny/nz` целые), поэтому стык цикла остаётся бесшовным.
       - Появление и исчезание сделаны через `scale` (всплытие `0 -> 1` у самого
         низа и рассыпание `1 -> 0` у самого верха) плюс невидимое окно
         `scale = 0` на стыке цикла. Поэтому интерполяция ModelEngine НИКОГДА не
         протаскивает пепел сверху вниз.
  2. Инженерная безопасность:
       - **Ни одного повёрнутого куба** (`RotationSolver` ModelEngine 4.1.0 падает).
       - Вся геометрия хлопья запечена вокруг ОСИ ВИХРЯ (= пивот `aura_root`),
         а наружу её выносит ТОЛЬКО анимация позиции. Это принципиально: при
         винтовом движении отклонение от «своего» стартового угла доходило бы до
         `2*R` и превысило лимит `+-24` BB, а так максимум хода кости = радиус
         плюс полувысота столба.
       - Радиус ТОЛЬКО ВНЕ игрока (габарит `|x| <= 7.5`, `|z| <= 3.75` BB), рост
         радиуса идёт НАРУЖУ, поэтому хлопье никогда не задевает игрока.
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

# Ось вихря. Y выбран ПОСЕРЕДИНЕ вертикального хода столба, чтобы максимальный
# ход кости (радиус + полувысота) оставался далеко внутри лимита +-24 BB.
ROOT_ORIG = [0.0, 14.8, 0.0]

ASH_COUNT = 34        # 10 -> 26 (больше пепла) -> 34 (равномернее, без кучек)
Y_LOW = -1.8          # ниже подошвы — «из-под ног»
Y_TOP_MIN, Y_TOP_MAX = 26.5, 28.5   # высота, на которой начинается рассыпание
R_BOT_MIN, R_BOT_MAX = 11.6, 12.6   # радиус у стоп (всегда вне габарита игрока)
R_GROW_MIN, R_GROW_MAX = 1.2, 2.0   # насколько воронка расширяется к верху
TURNS_MIN, TURNS_MAX = 0.99, 1.03   # оборотов вокруг игрока за цикл (ВСЕ в одну сторону;
                                    # узкий диапазон = равномерное расслоение сохраняется)
# Константы двумерной последовательности R2 (пластическое число).
R2_A1 = 0.7548776662466927
R2_A2 = 0.5698402909980532
GROW = 0.06                         # доля цикла на «всплытие» снизу
CRUMBLE = 0.13                      # доля цикла на рассыпание сверху
# За время рассыпания частица ПРОДОЛЖАЕТ подниматься (и крутиться). Раньше
# прогресс `t` обрезался на 1.0, из-за чего ВСЕ догорающие частицы замирали
# на одной высоте и сбивались в заметную кучу у самого верха столба.
CRUMBLE_RISE = 17.0                 # BB подъёма за фазу рассыпания
RISE_FRACTION = 0.75                # доля цикла на подъём (одинаковая у всех)

TAU = 2.0 * math.pi

_BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))

# 0..16 UV, текстура 64x64 => 1 UV = 4 px, тайлы 32x32 px = 8x8 UV.
UV_ASH = (0.25, 0.25, 7.75, 7.75)        # серый пепел
UV_ASH_EDGE = (8.25, 0.25, 15.75, 7.75)  # тёмные торцы пепла
UV_EMBER = (0.25, 8.25, 7.75, 15.75)     # тлеющий уголёк (радиальный)
UV_SOOT = (8.25, 8.25, 15.75, 15.75)     # копоть-хвост

ASH_IDS = [f'ash_{i + 1:02d}' for i in range(ASH_COUNT)]
BONE_NAMES = ['aura_root'] + ASH_IDS


def uid(tag: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f'elytrix.death_aura.v2:{tag}'))


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

    # Мелкая «зола»: две несинхронные синусоиды + детерминированный шум, чтобы
    # пепел был ПЯТНИСТЫМ, а не ровным градиентом.
    def speck(px, py, freq, gain):
        v = (math.sin(px * freq + py * freq * 0.61)
             + math.sin(px * freq * 1.73 - py * freq * 0.37 + 1.7)
             + math.sin(py * freq * 2.31 + px * freq * 0.19 + 0.4)) / 3.0
        return v * gain

    # (0,0) лицевая сторона пепла: светлый тёпло-серый -> уголь, пятнистый
    paint(0, 0, lambda px, py: _ramp(
        [(0.00, (214, 208, 202)), (0.34, (156, 148, 146)),
         (0.68, (96, 90, 92)), (1.00, (46, 42, 48))],
        max(0.0, min(1.0, py / 31.0 + wob(px, py) + speck(px, py, 0.9, 0.10)))))
    # (32,0) рваные торцы — темнее и «обугленнее»
    paint(1, 0, lambda px, py: _ramp(
        [(0.00, (150, 138, 138)), (0.40, (86, 76, 78)),
         (0.74, (48, 42, 48)), (1.00, (22, 20, 26))],
        max(0.0, min(1.0, py / 31.0 + wob(px, py) + speck(px, py, 1.15, 0.13)))))
    # (0,32) тлеющий уголёк: радиальный белый -> жёлтый -> оранжевый -> тёмно-красный
    paint(0, 1, lambda px, py: _ramp(
        [(0.00, (255, 252, 240)), (0.26, (255, 214, 120)),
         (0.58, (244, 128, 34)), (0.82, (176, 52, 14)), (1.00, (74, 16, 8))],
        min(1.0, math.hypot(px - 15.5, py - 15.5) / 17.0 + wob(px, py) * 1.4)))
    # (32,32) копоть: почти чёрная с тёплым отливом в центре
    paint(1, 1, lambda px, py: _ramp(
        [(0.00, (112, 82, 72)), (0.38, (52, 42, 46)), (1.00, (12, 11, 15))],
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
# 3. Геометрия: 26 хлопьев, запечённых вокруг ОСИ ВИХРЯ
# ---------------------------------------------------------------------------
# ОДНО ХЛОПЬЕ = РВАНОЕ ПЕПЕЛЬНОЕ ПЯТНО (v3.28.0).
#   * v3.26: 5 кубов в ОДНОЙ точке -> частицы слипались в заметные «комья».
#   * v3.27: ровно одна тонкая пластинка -> комков нет, но пепел читался как
#     ровные прямоугольники-конфетти и был слишком мелким.
#   * v3.28: основная пластинка КРУПНЕЕ (`0.76..1.04` BB против `0.52..0.80`),
#     и к ней приставлен ОДИН смещённый осколок. Осколок смещён на `0.55..0.80`
#     полудлины, поэтому он именно ЛОМАЕТ прямоугольный силуэт, а не собирается
#     с пластинкой в комок. Уголёк сидит ровно ПО ЦЕНТРУ пластинки, а не рядом.
# Размер и пропорции у каждого хлопья свои, поэтому пепел не штампованный.
def _flake_parts(i: int):
    rnd = random.Random(8801 + i * 3167)
    hx = rnd.uniform(0.38, 0.52)     # полудлина  основной пластинки
    hz = rnd.uniform(0.25, 0.38)     # полуширина основной пластинки
    th = rnd.uniform(0.055, 0.085)   # полу толщина — пепел ТОНКИЙ
    # осколок, ломающий силуэт: смещён по X/Z на долю пластинки и мельче её
    ox = rnd.uniform(0.55, 0.78) * hx * rnd.choice((1.0, -1.0))
    oz = rnd.uniform(0.28, 0.58) * hz * rnd.choice((1.0, -1.0))
    oy = rnd.uniform(-0.07, 0.09)
    jx = rnd.uniform(0.30, 0.46) * hx
    jz = rnd.uniform(0.32, 0.52) * hz
    jt = th * rnd.uniform(0.55, 0.85)
    return (hx, hz, th), (ox, oy, oz, jx, jt, jz)


def ash_spec(i: int) -> dict:
    """Параметры хлопья `i` (0-based). Детерминировано.

    v3.27.0 — РАВНОМЕРНОЕ РАССЛОЕНИЕ вместо случайного набора. Раньше угол и
    фаза брались «случайно» и независимо, из-за чего частицы то и дело
    сбивались в кучки. Теперь и угол, и фаза РАЗЛОЖЕНЫ ПО СЛОТАМ:
      * фаза   = (i + небольшой джиттер) / N  -> частицы равномерно распределены
        по времени, а значит и по высоте столба;
      * угол   = ((i * 11) mod N + джиттер) / N * TAU, где 11 взаимно просто с N
        -> соседние по времени частицы разнесены по кругу, кучек нет;
      * `turns` почти одинаковы у всех (0.98..1.18), поэтому равномерное
        расслоение СОХРАНЯЕТСЯ на всём пути вверх (смерч не «сбивается»).
    Джиттер намеренно меньше слота (+-0.16 / +-0.20), то есть частица может
    сдвинуться внутри своей доли, но НЕ может перескочить к соседней.
    """
    rnd = random.Random(4421 + i * 6151)
    slot = 1.0 / ASH_COUNT
    # Двумерная последовательность R2 (plastic-constant low discrepancy): пара
    # (фаза, угол) = (frac(i*A1), frac(i*A2)) — это САМАЯ равномерная раскладка
    # точек на торе без решётки. Ключевое свойство: если у двух частиц близкие
    # углы, то их фазы (а значит и высоты) гарантированно ДАЛЕКИ, и наоборот.
    # Обычный «шаг с взаимно простым множителем» этим свойством не обладает
    # (например, при N=34 и шаге 11 частицы i и i+3 оказывались в соседних
    # угловых слотах и слипались), поэтому он заменён на R2.
    return {
        'ang': (((i * R2_A2) % 1.0) * TAU + rnd.uniform(-0.10, 0.10) * slot * TAU) % TAU,
        'r_bot': rnd.uniform(R_BOT_MIN, R_BOT_MAX),
        'r_grow': rnd.uniform(R_GROW_MIN, R_GROW_MAX),
        # `turns` и `rise` у ВСЕХ частиц ОДИНАКОВЫЕ. Любой разброс давал бы
        # дифференциальный дрейф: частицы с разной скоростью со временем
        # нагоняли друг друга и слипались. Ровный смерч — это как раз жёсткое
        # вращение столба; разнообразие дают размер, кувыркание и радиус.
        'turns': TURNS_MIN,                            # ВСЕГДА > 0 -> один смерч
        'scale': 0.80 + 0.50 * (((i * 5) % 6) / 5.0),  # 0.80 .. 1.30
        'phase': ((i * R2_A1) % 1.0 + rnd.uniform(-0.12, 0.12) * slot) % 1.0,
        # ВАЖНО: скорость подъёма, верхняя точка и профиль у всех частиц почти
        # ОДИНАКОВЫЕ. Раз они одинаковы, высота частицы однозначно определяется
        # её фазой, а фазы разложены по слотам -> высоты РАВНОМЕРНО расслоены и
        # две частицы не могут одновременно оказаться и на одной высоте, и на
        # одном угле (угол сдвинут на 11 слотов). Разнообразие дают размер,
        # кувыркание, радиус и покачивание, а НЕ скорость.
        'rise': RISE_FRACTION,
        'y_top': rnd.uniform(Y_TOP_MIN, Y_TOP_MAX),
        'pow': rnd.uniform(0.98, 1.02),
        'ar': rnd.uniform(0.22, 0.55),     # «дыхание» радиуса, только наружу
        'ab': rnd.uniform(0.16, 0.40),     # вертикальное покачивание, BB
        'nr': rnd.choice((1, 2, 3)), 'nb': rnd.choice((2, 3, 4)),
        # кувыркание: ЦЕЛОЕ число оборотов за цикл по каждой оси
        'nx': rnd.choice((1, 2)), 'ny': rnd.choice((1, 2, 3)), 'nz': rnd.choice((1, 2)),
        'pr': rnd.random(), 'pb': rnd.random(),
        'px': rnd.random(), 'py': rnd.random(), 'pz': rnd.random(),
    }


def rnd_ember(i: int) -> float:
    """Половина размера тлеющего уголька (0.17..0.28 BB), детерминированно."""
    return random.Random(5507 + i * 907).uniform(0.085, 0.140)


ASH_SPECS = [ash_spec(i) for i in range(ASH_COUNT)]


def build_geometry(elements: list) -> dict:
    bones: dict[str, list] = {}
    faces_cache = {
        'flake': _faces(UV_ASH, east=UV_ASH_EDGE, west=UV_ASH_EDGE,
                        up=UV_ASH_EDGE, down=UV_ASH_EDGE),
        'edge': _faces(UV_ASH_EDGE, up=UV_ASH, down=UV_ASH_EDGE),
        'ember': _faces(UV_EMBER),
        'soot': _faces(UV_SOOT),
    }

    for i, spec in enumerate(ASH_SPECS):
        s = spec['scale']
        (hx, hz, th), (ox, oy, oz, jx, jt, jz) = _flake_parts(i)
        # ВСЯ геометрия запечена вокруг ОСИ ВИХРЯ — наружу её выносит анимация.
        o = list(ROOT_ORIG)
        cubes = [_cube(
            f'ash_{i + 1:02d}_flake',
            [o[0] - hx * s, o[1] - th * s, o[2] - hz * s],
            [o[0] + hx * s * 0.90, o[1] + th * s, o[2] + hz * s * 0.94],
            o, faces_cache['flake']), _cube(
            # осколок: рваный край, из-за него хлопье никогда не прямоугольное
            f'ash_{i + 1:02d}_shard',
            [o[0] + (ox - jx) * s, o[1] + (oy - jt) * s, o[2] + (oz - jz) * s],
            [o[0] + (ox + jx) * s, o[1] + (oy + jt) * s, o[2] + (oz + jz) * s],
            o, faces_cache['edge'])]
        # у двух третей хлопьев в центре тлеет уголёк — это искра НА пепле,
        # а не второй комок рядом с ним.
        if i % 3 != 2:
            e = rnd_ember(i)
            cubes.append(_cube(
                f'ash_{i + 1:02d}_ember',
                [o[0] - e, o[1] + th * s - 0.02 * s, o[2] - e],
                [o[0] + e, o[1] + th * s + 0.26 * s, o[2] + e],
                o, faces_cache['ember']))
        # у каждого третьего — хвостик копоти снизу-сзади (силуэт ещё рванее)
        if i % 3 == 1:
            cubes.append(_cube(
                f'ash_{i + 1:02d}_soot',
                [o[0] + (-ox * 0.55 - jx * 0.7) * s, o[1] - th * s - 0.16 * s,
                 o[2] + (-oz * 0.55 - jz * 0.7) * s],
                [o[0] + (-ox * 0.55 + jx * 0.7) * s, o[1] - th * s,
                 o[2] + (-oz * 0.55 + jz * 0.7) * s],
                o, faces_cache['soot']))
        for c in cubes:
            elements.append(c)
        bones[ASH_IDS[i]] = [c['uuid'] for c in cubes]
    bones['aura_root'] = []
    return bones


# ---------------------------------------------------------------------------
# 4. Анимация: непрерывный ВОСХОДЯЩИЙ ВИХРЬ пепла
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
        c = (up - spec['phase']) % 1.0      # c == 1.0 и c == 0.0 дают scale 0 -> стык невидим

        # `cu` НЕ обрезается: пока частица догорает, она продолжает и подниматься,
        # и закручиваться — иначе все рассыпающиеся частицы вставали бы в одну
        # точку у верха столба и собирались в кучу.
        cu = c / spec['rise']
        t = min(1.0, cu)
        y = Y_LOW + (spec['y_top'] - Y_LOW) * (t ** spec['pow'])
        if cu > 1.0:
            y += (cu - 1.0) * CRUMBLE_RISE

        # --- ВИХРЬ: угол раскручивается за время подъёма, ВСЕГДА в одну сторону ---
        ang = spec['ang'] + spec['turns'] * TAU * cu
        # --- ВОРОНКА: у стоп радиус минимальный, к верху расширяется ---
        r = spec['r_bot'] + spec['r_grow'] * (min(cu, 1.15) ** 0.85) \
            + spec['ar'] * (0.5 + 0.5 * math.sin(TAU * (spec['nr'] * c + spec['pr'])))
        y = y + spec['ab'] * math.sin(TAU * (spec['nb'] * c + spec['pb']))

        x = math.cos(ang) * r
        z = math.sin(ang) * r
        pose['ash_pos'][name] = [round(x, 4), round(y - ROOT_ORIG[1], 4), round(z, 4)]

        # Кувыркание: целое число оборотов по каждой оси -> стык цикла бесшовный
        pose['ash_rot'][name] = [
            round(360.0 * spec['nx'] * c + 30.0 * math.sin(TAU * (spec['nr'] * c + spec['px'])), 4),
            round(360.0 * spec['ny'] * c + 26.0 * math.sin(TAU * (spec['nb'] * c + spec['py'])), 4),
            round(360.0 * spec['nz'] * c + 22.0 * math.sin(TAU * 3.0 * c + spec['pz']), 4),
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

    # Пивот каждого хлопья — ось вихря, поэтому смещение кости минимально,
    # а весь «вынос» наружу делает анимация позиции.
    ash_bones = [bone(ASH_IDS[i], ROOT_ORIG, bones[ASH_IDS[i]], is_open=False)
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
    """32x32: вихрь пепла — рваные серые хлопья закручиваются вверх, тлеют угольки."""
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    px = img.load()

    ash_hi = (206, 200, 196, 255)
    ash_mid = (140, 132, 132, 255)
    ash_low = (84, 78, 82, 255)
    ash_dark = (38, 34, 40, 255)
    ember_hot = (255, 246, 208, 255)
    ember = (255, 186, 72, 255)
    ember_deep = (206, 78, 20, 255)

    def put(x, y, c):
        if 0 <= x < 32 and 0 <= y < 32:
            px[x, y] = c

    # (x, y, ширина, высота, есть ли уголёк, куда смещён рваный осколок)
    # Раскладка «смерч»: широкий низ, узкий верх.
    flakes = (
        (4, 26, 3, 2, False, (1, 0)), (12, 27, 3, 2, True, (-1, 1)),
        (19, 25, 3, 2, False, (1, -1)), (26, 23, 2, 2, False, (-1, 0)),
        (7, 21, 3, 3, True, (1, 1)), (15, 22, 3, 2, False, (-1, -1)),
        (22, 20, 3, 2, True, (1, 0)), (27, 18, 2, 2, False, (0, 1)),
        (9, 16, 3, 3, False, (-1, 1)), (17, 17, 3, 2, True, (1, -1)),
        (24, 14, 2, 2, False, (-1, 0)), (4, 17, 2, 2, False, (1, 0)),
        (11, 11, 3, 2, True, (1, 1)), (19, 11, 2, 2, False, (-1, -1)),
        (26, 9, 2, 2, False, (0, -1)),
        (13, 6, 2, 2, True, (1, 0)), (21, 4, 2, 2, False, (-1, 1)),
    )
    for (fx, fy, fw, fh, hot, (sx, sy)) in flakes:
        for dy in range(fh):
            for dx in range(fw):
                # пятнистая поверхность: светлый верх, тёмный низ
                c = ash_hi if (dx + dy) % 3 == 0 else (ash_mid if dy < fh - 1 else ash_low)
                put(fx + dx, fy + dy, c)
        # РВАНОСТЬ: осколок, приставленный к углу, ломает прямоугольник
        jx = fx + (fw - 1 if sx > 0 else 0) + sx
        jy = fy + (fh - 1 if sy > 0 else 0) + sy
        put(jx, jy, ash_low)
        put(jx + sx, jy, ash_dark)
        if hot:
            put(fx + fw // 2, fy + 1, ember_hot)
            put(fx + fw // 2, fy, ember)

    # отдельно тлеющие точки
    for (ex, ey) in ((16, 30), (9, 24), (20, 23), (14, 19), (23, 16), (15, 14), (7, 13)):
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
        scale = 6.0
        cx0, cy0 = panel_w / 2, panel_h / 2 + 40
        faces_to_draw = []
        for name in ASH_IDS:
            f = pose['ash_scale'][name][0]
            if f <= 0.001:
                continue
            off = np.array(pose['ash_pos'][name], dtype=float)
            rot = np.array(pose['ash_rot'][name], dtype=float)
            Rm = rot_mat(rot[0], rot[1], rot[2])
            base = np.array(ROOT_ORIG, dtype=float)
            for cu in (c for c in blueprint['elements'] if c['name'].startswith(name)):
                a = np.array(cu['from'], dtype=float) - base
                b = np.array(cu['to'], dtype=float) - base
                a = Rm @ (a * f) + base + off
                b = Rm @ (b * f) + base + off
                xs = (a[0], b[0]); ys = (a[1], b[1]); zs = (a[2], b[2])
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
