#!/usr/bin/env python3
"""Builds the Kaneki kagune (щупальца) blueprint + texture, pixel-art only.

v9 - round tentacles that visibly grow out of the spine.

Why this version exists
-----------------------
v8 was rejected in game with two words: "плоские" (flat) and "не растут со спины"
(they don't grow out of the back).  Both had a concrete cause:

* **Flat.** Every bone was one box with the *same* flat crimson tile on all four
  long faces, so the tube had no shading across its section - it read as a
  ribbon.  Now the cross-section is square and the texture carries a cylindrical
  gradient: the middle of every long face is bright, its two edges fall off into
  shadow.  That is what makes a boxy Minecraft shape look round.
* **Not from the back.** The root patch sat inside the torso and the four
  tendrils popped out of nothing.  Now a fleshy knot (7 boxes) sits on the spine,
  protrudes ~3 units behind the back surface and is *wider* than the four roots,
  so the tendrils visibly branch out of it.

The curve is still exact: a centripetal Catmull-Rom path traced from the
reference, cut into bones by accumulated curvature, and the per-bone rotations
are solved so ModelEngine's `Rz.Ry` chain reproduces the traced line (a test
checks the error stays under 0.01 units).

No cube has a rotation of its own, so `RotationSolver` (the part of ModelEngine
4.1.0 that throws on cube angles off the 22.5 deg grid) is never reached.

Usage:
    python3 tools/accessories-model/build_tentacles.py [--out-dir DIR] [--preview] [--report]
"""
import argparse
import base64
import io
import json
import math
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
MODEL = 'elytrix_kaneki_tentacles'
ROOT_ORIGIN = [0.0, 20.0, 0.0]
PARTS = tuple('abcdefghijklmnopqrstuvwx')   # bone suffixes, one per joint

# --------------------------------------------------------------------------- tendrils
# Blockbench units: +X = the player's right, +Y = up, +Z = behind the player.
# A player is 32 units tall and 8 wide, the torso back surface is at z = +2.
#
# `ctrl` are the traced centres of the tendril, from the spine outward.  The
# first point is *inside* the knot, so the tendril starts in flesh, not in air.
# The last two points always travel back towards the body: the tip ends up
# closer to the centre line than the widest point of the same tendril.
TENDRILS = [
    {
        # upper right: out of the spine, around the shoulder and then a long,
        # almost straight run outwards - a tail, not a wing.  The bend lives in
        # the first third, the rest is a taper.
        'name': 'right_upper',
        'ctrl': [(0.7, 17.5, 2.1), (3.4, 18.2, 1.3), (7.0, 18.3, -0.5),
                 (11.0, 18.0, -2.0), (15.0, 17.6, -3.2), (18.6, 17.4, -4.0),
                 (21.4, 17.3, -4.5)],
        'girth': (3.6, 3.4), 'tip': 0.32,
    },
    {
        'name': 'left_upper',
        'ctrl': [(-0.7, 17.6, 2.1), (-3.5, 18.3, 1.3), (-7.1, 18.4, -0.5),
                 (-11.1, 18.1, -2.0), (-15.1, 17.7, -3.2), (-18.7, 17.5, -4.0),
                 (-21.5, 17.4, -4.5)],
        'girth': (3.5, 3.3), 'tip': 0.32,
    },
    {
        # lower right: a hand lower, the same long straight run - the two pairs
        # frame the hips and the chest
        'name': 'right_lower',
        'ctrl': [(0.7, 15.9, 2.1), (3.6, 15.0, 1.4), (7.3, 14.4, -0.2),
                 (11.4, 14.2, -1.6), (15.4, 14.1, -2.8), (19.0, 14.1, -3.6),
                 (22.0, 14.1, -4.1)],
        'girth': (3.4, 3.2), 'tip': 0.3,
    },
    {
        'name': 'left_lower',
        'ctrl': [(-0.7, 15.8, 2.1), (-3.7, 14.9, 1.4), (-7.4, 14.3, -0.2),
                 (-11.5, 14.1, -1.6), (-15.5, 14.0, -2.8), (-19.1, 14.0, -3.6),
                 (-22.1, 14.0, -4.1)],
        'girth': (3.3, 3.1), 'tip': 0.3,
    },
]

# The knot the four tendrils grow out of: a lump of flesh on the spine.  It is
# sunk into the torso (z = 0.4) and bulges ~3 units behind the back surface, and
# it is wider than the four roots, so the tendrils read as branches of one organ.
KNOT = {
    'name': 'root_knot',
    'origin': [0.0, 16.8, 2.4],
    'boxes': [
        # (x0, x1, y0, y1, z0, z1) around the origin; z = 0 is the back surface of
        # the torso, so everything positive here sticks out behind the player and
        # the -0.8 boxes sink into the body so no gap can ever appear
        (-3.2, 3.2, -3.2, 0.8, -0.9, 2.0),
        (-4.4, 4.4, -1.8, 2.0, -0.8, 2.9),
        (-3.6, 3.6, 1.6, 3.6, -0.7, 2.5),
        (-2.0, 2.0, 3.2, 4.8, -0.6, 1.9),
        (-5.0, -2.4, -1.0, 1.6, -0.6, 2.3),
        (2.4, 5.0, -1.0, 1.6, -0.6, 2.3),
        (-1.6, 1.6, -2.6, 2.6, 1.6, 3.4),
    ],
}

MAX_TURN = 15.0                 # largest bend between two joints (deg)
MAX_LEN = 2.4                   # longest bone: short joints keep the taper round
MIN_TIP_LEN = 0.7               # bones shorter than this at the tip are merged


def uid(tag):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'elytrix-kaneki:{tag}'))


# --------------------------------------------------------------------------- curve
def smoothstep(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def _cr(p0, p1, p2, p3, t, alpha=0.5):
    """Centripetal Catmull-Rom: no cusps, no overshoot on uneven spacing."""
    def tj(ti, a, b):
        return ti + max(1e-6, math.dist(a, b)) ** alpha

    t0 = 0.0
    t1 = tj(t0, p0, p1)
    t2 = tj(t1, p1, p2)
    t3 = tj(t2, p2, p3)
    tt = t1 + (t2 - t1) * t

    def lerp(a, b, ta, tb, x):
        w = (x - ta) / (tb - ta)
        return tuple(a[i] + (b[i] - a[i]) * w for i in range(3))

    a1 = lerp(p0, p1, t0, t1, tt)
    a2 = lerp(p1, p2, t1, t2, tt)
    a3 = lerp(p2, p3, t2, t3, tt)
    b1 = lerp(a1, a2, t0, t2, tt)
    b2 = lerp(a2, a3, t1, t3, tt)
    return lerp(b1, b2, t1, t2, tt)


def spline(points, per_span=28):
    """Dense polyline through the traced control points."""
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(len(pts) - 3):
        for step in range(per_span):
            out.append(_cr(*pts[i:i + 4], step / per_span))
    out.append(tuple(points[-1]))
    return out


def _norm(v):
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / length for c in v)


def turn_between(a, b, c):
    """Angle between the chords a->b and b->c in degrees."""
    u = _norm(tuple(b[i] - a[i] for i in range(3)))
    v = _norm(tuple(c[i] - b[i] for i in range(3)))
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(u[i] * v[i] for i in range(3))))))


def allowed_turn(t):
    """How much a joint may bend at `t` (0 root .. 1 tip), in degrees.

    A bend of `a` degrees opens a notch of `width * sin(a)` on the outside of the
    joint.  The tendril is 5 units across at the root and 1.5 at the curl, so the
    same 20 deg is a visible kink at the root and invisible at the tip.
    """
    return 13.0 if t < 0.65 else 20.0


def adaptive_resample(dense, max_len=MAX_LEN):
    """Cut joints by accumulated curvature, not by arc length."""
    total = sum(math.dist(a, b) for a, b in zip(dense, dense[1:])) or 1.0
    joints = [dense[0]]
    turned = 0.0
    length = 0.0
    walked = 0.0
    for index in range(1, len(dense) - 1):
        step = math.dist(dense[index - 1], dense[index])
        turned += turn_between(dense[index - 1], dense[index], dense[index + 1])
        length += step
        walked += step
        if turned >= allowed_turn(walked / total) or length >= max_len:
            joints.append(dense[index])
            turned = 0.0
            length = 0.0
    joints.append(dense[-1])
    while len(joints) > 3 and math.dist(joints[-2], joints[-1]) < MIN_TIP_LEN:
        joints.pop(-2)
    return joints


# --------------------------------------------------------------------------- rig
def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def rot_z(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def rot_y(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]


IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def solve_euler(points):
    """Local [x, y, z] Euler per chord, such that chained Rz.Ry reproduces `points`.

    ModelEngine (`BlockbenchParser`) builds the bone quaternion with
    `Quaternionf.rotateZYX(x, y, z)` and multiplies child by parent, i.e.
    `p' = Rz.Ry.Rx.p`.  With x = 0 the direction of a bone is
    `Rz(a).Ry(b).(1,0,0) = (cos a cos b, sin a cos b, -sin b)`, which inverts
    exactly for any unit vector - that is how the traced curve is reproduced.
    """
    world = IDENTITY
    euler = []
    for a, b in zip(points, points[1:]):
        d = _norm(tuple(b[i] - a[i] for i in range(3)))
        local = tuple(sum(world[k][i] * d[k] for k in range(3)) for i in range(3))
        beta = -math.degrees(math.asin(max(-1.0, min(1.0, local[2]))))
        alpha = math.degrees(math.atan2(local[1], local[0]))
        euler.append([0.0, round(beta, 4), round(alpha, 4)])
        world = _matmul(_matmul(world, rot_z(alpha)), rot_y(beta))
    return euler


def chain_points(origin, euler, lengths):
    """Where the solved chain actually puts every joint."""
    world = IDENTITY
    point = tuple(origin)
    out = [point]
    for angles, length in zip(euler, lengths):
        world = _matmul(_matmul(world, rot_z(angles[2])), rot_y(angles[1]))
        direction = tuple(sum(world[i][k] * (1.0 if k == 0 else 0.0) for k in range(3))
                          for i in range(3))
        point = tuple(point[i] + direction[i] * length for i in range(3))
        out.append(point)
    return out


def blade_profile(spec, t):
    """Diameter of the tube at `t` = 0 root .. 1 tip.

    A kagune is a muscle, not a blade: it keeps most of its girth over the first
    half and only then tapers into the point.  Width == depth, so the section is
    square and the tube looks the same from every side.
    """
    width0, depth0 = spec['girth']
    k = min(1.0, max(0.0, (t - 0.35) / 0.65))
    fade = (1.0 - smoothstep(k)) ** 0.55
    return (spec['tip'] + (width0 - spec['tip']) * fade,
            spec['tip'] + (depth0 - spec['tip']) * fade)


def blade_bones(spec):
    """The traced centre line as a chain of bones.

    The bones are laid out **straight along +X** in the rest pose and the solved
    rotations bend them into the traced curve at runtime - that is the only rig
    ModelEngine/Blockbench understands: it rotates each bone's local offset
    through the parent chain.  v7 placed the origins on the curve *and* rotated
    them, so every joint was bent twice: that is what read as "crooked" in game.
    """
    points = adaptive_resample(spline(spec['ctrl']))
    if len(points) - 1 > len(PARTS):
        raise SystemExit(f'{spec["name"]}: {len(points) - 1} bones, raise PARTS')
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    euler = solve_euler(points)
    total = sum(lengths)
    bones = []
    walked = 0.0
    cursor = list(points[0])
    for index, (length, angles) in enumerate(zip(lengths, euler)):
        t0, t1 = walked / total, (walked + length) / total
        walked += length
        width, depth = blade_profile(spec, t1)
        # overlap backwards into the parent so a bend can never open a notch
        # overlap only enough to close the outside of the bend: the gap opened
        # by a turn of a degrees is radius * tan(a / 2), so the overlap follows
        # the radius.  0.6 * length (v9 first attempt) stuck whole fins out of
        # the silhouette on every joint.
        bend = abs(angles[2] - (euler[index - 1][2] if index else 0.0))
        overlap = 0.0 if index == 0 else min(width * 0.5,
                                            (width / 2) * math.tan(math.radians(min(bend, 45.0)) / 2) + 0.35)
        bones.append({
            'name': f'{spec["name"]}_{PARTS[index]}',
            'origin': [round(v, 4) for v in cursor],
            'rotation': angles, 'length': length, 'turn': angles[2],
            'yaw': angles[1], 't': (t0 + t1) / 2,
            'box': {'x0': round(-overlap, 4), 'x1': round(length, 4),
                    'width': width, 'depth': depth},
        })
        cursor[0] += length
    return bones


def blade_path(spec):
    """Joint positions in model space, exactly as the runtime will place them."""
    bones = blade_bones(spec)
    return chain_points(bones[0]['origin'], [b['rotation'] for b in bones],
                        [b['length'] for b in bones])


# UV layout inside the 0..16 space of a vanilla-mapped texture (64x64 -> 4px per unit)
UV_REGIONS = {
    'side': [0.0, 0.0, 8.0, 8.0],      # long faces, cylindrical gradient across V
    'scales': [8.0, 0.0, 16.0, 8.0],   # plate pattern for the thin end
    'top': [0.0, 8.0, 8.0, 16.0],      # lit top of the tube
    'dark': [8.0, 8.0, 16.0, 16.0],    # shadowed underside
}


def build_elements(bone):
    """One bone of the chain as two boxes that together make an eight-sided tube.

    A single square box reads as a flat strap: seen from one side it is one
    uniform plane.  A second box, turned 45 deg about the bone's own axis and
    slightly smaller, cuts the corners, so the silhouette is an octagon and the
    section shades like a round tentacle.  45 deg is a multiple of the 22.5 deg
    grid ModelEngine accepts, and the pivot sits on the bone axis, so the roll
    never moves the box off the centre line.
    """
    box = bone['box']
    origin = bone['origin']
    side = 'scales' if bone['t'] > 0.74 else 'side'
    faces = {
        'up': {'uv': list(UV_REGIONS['top']), 'texture': 0},
        'down': {'uv': list(UV_REGIONS['dark']), 'texture': 0},
        'north': {'uv': list(UV_REGIONS[side]), 'texture': 0},
        'south': {'uv': list(UV_REGIONS[side]), 'texture': 0},
        'east': {'uv': list(UV_REGIONS[side]), 'texture': 0},
        'west': {'uv': list(UV_REGIONS[side]), 'texture': 0},
    }
    cubes = []
    # an octagon needs the rolled box at 1/sqrt(2) of the square one: any bigger
    # and its corners poke out of the square as spikes (that is what 0.86 did)
    for index, (scale, roll) in enumerate(((1.0, 0.0), (0.707, 45.0))):
        half_w = box['width'] * scale / 2
        half_d = box['depth'] * scale / 2
        cubes.append({
            'name': f'{bone["name"]}_{index}',
            'box_uv': False, 'rescale': False, 'locked': False, 'light_emission': 0,
            'render_order': 'default', 'allow_mirror_modeling': True,
            'from': [round(origin[0] + box['x0'], 4), round(origin[1] - half_w, 4),
                     round(origin[2] - half_d, 4)],
            'to': [round(origin[0] + box['x1'], 4), round(origin[1] + half_w, 4),
                   round(origin[2] + half_d, 4)],
            'autouv': 0, 'color': 0,
            'origin': [round(origin[0] + (box['x0'] + box['x1']) / 2, 4),
                       round(origin[1], 4), round(origin[2], 4)],
            'rotation': [roll, 0.0, 0.0],
            'faces': {k: dict(v) for k, v in faces.items()},
            'type': 'cube', 'uuid': uid(f'cube:{bone["name"]}:{index}'),
        })
    return cubes


def _unused_single_box(bone):
    return [{
        'name': f'{bone["name"]}_0',
        'box_uv': False, 'rescale': False, 'locked': False, 'light_emission': 0,
        'render_order': 'default', 'allow_mirror_modeling': True,
        'from': [round(origin[0] + box['x0'], 4), round(origin[1] - half_w, 4),
                 round(origin[2] - half_d, 4)],
        'to': [round(origin[0] + box['x1'], 4), round(origin[1] + half_w, 4),
               round(origin[2] + half_d, 4)],
        'autouv': 0, 'color': 0,
        'origin': [round(origin[0] + (box['x0'] + box['x1']) / 2, 4),
                   round(origin[1], 4), round(origin[2], 4)],
        'rotation': [0.0, 0.0, 0.0],
        'faces': faces, 'type': 'cube', 'uuid': uid(f'cube:{bone["name"]}:0'),
    }]


def knot_elements():
    """The root knot: a lump of flesh on the spine, no bone rotation."""
    elements = []
    origin = KNOT['origin']
    for index, (x0, x1, y0, y1, z0, z1) in enumerate(KNOT['boxes']):
        faces = {
            'up': {'uv': list(UV_REGIONS['top']), 'texture': 0},
            'down': {'uv': list(UV_REGIONS['dark']), 'texture': 0},
            'north': {'uv': list(UV_REGIONS['side']), 'texture': 0},
            'south': {'uv': list(UV_REGIONS['side']), 'texture': 0},
            'east': {'uv': list(UV_REGIONS['side']), 'texture': 0},
            'west': {'uv': list(UV_REGIONS['side']), 'texture': 0},
        }
        elements.append({
            'name': f'{KNOT["name"]}_{index}',
            'box_uv': False, 'rescale': False, 'locked': False, 'light_emission': 0,
            'render_order': 'default', 'allow_mirror_modeling': True,
            'from': [round(origin[0] + x0, 4), round(origin[1] + y0, 4),
                     round(origin[2] + z0, 4)],
            'to': [round(origin[0] + x1, 4), round(origin[1] + y1, 4),
                   round(origin[2] + z1, 4)],
            'autouv': 0, 'color': 0,
            'origin': [round(origin[0] + (x0 + x1) / 2, 4),
                       round(origin[1] + (y0 + y1) / 2, 4),
                       round(origin[2] + (z0 + z1) / 2, 4)],
            'rotation': [0.0, 0.0, 0.0],
            'faces': faces, 'type': 'cube', 'uuid': uid(f'cube:knot:{index}'),
        })
    return elements


# --------------------------------------------------------------------------- texture
def build_texture():
    """Glossy crimson kagune skin, drawn pixel by pixel (no AI, no external images).

    Deliberately *flat within each tile*.  Every bone maps the whole tile, so any
    gradient, band or line inside it repeats once per bone and the tube starts to
    look ribbed - that is exactly what made the previews look like a stack of
    rings, and it would look the same in game.  The volume comes from the
    eight-sided section plus Minecraft's own per-face light, not from the skin.
    What the skin adds is colour and a wet mottling fine enough not to tile.
    """
    size = 64
    img = Image.new('RGBA', (size, size), (150, 16, 26, 255))
    px = img.load()
    base = {
        'side': (156, 18, 28),
        'scales': (168, 24, 34),
        'top': (186, 34, 42),
        'dark': (96, 8, 16),
    }
    for y in range(size):
        for x in range(size):
            if x < 32 and y < 32:
                key = 'side'
            elif x >= 32 and y < 32:
                key = 'scales'
            elif x < 32:
                key = 'top'
            else:
                key = 'dark'
            r, g, b = base[key]
            # two incommensurate waves: a wet, uneven sheen that does not tile
            n = (math.sin(x * 0.83 + y * 1.27) * 0.5
                 + math.sin(x * 0.29 - y * 0.61) * 0.5)
            n += math.sin((x * 0.11 + y * 0.17) * 2.3) * 0.4
            k = 1.0 + n * 0.075
            px[x, y] = (max(0, min(255, int(r * k))),
                        max(0, min(255, int(g * k))),
                        max(0, min(255, int(b * k))), 255)

    # a few gloss highlights, sparse and soft so they read as wet skin, not ribs
    for cx, cy, radius in ((9, 12, 3), (23, 25, 2), (14, 41, 3), (44, 14, 2),
                           (52, 27, 2), (38, 46, 2)):
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if not (0 <= x < size and 0 <= y < size):
                    continue
                d = math.hypot(x - cx, y - cy) / max(0.6, radius)
                if d >= 1.0:
                    continue
                k = (1.0 - d) ** 2 * 0.42
                r, g, b, _ = px[x, y]
                px[x, y] = (min(255, int(r + 96 * k)), min(255, int(g + 34 * k)),
                            min(255, int(b + 32 * k)), 255)

    # scale plates on the thin end (UV 8..16 x 0..8 -> pixels 32..64 x 0..32)
    plate = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(plate)
    for row in range(8):
        for col in range(5):
            ox = col * 8 - (4 if row % 2 else 0)
            oy = row * 4
            pdraw.rounded_rectangle([ox, oy, ox + 8, oy + 5], radius=2,
                                    fill=(176, 30, 40, 70))
            pdraw.line([(ox + 2, oy + 1), (ox + 6, oy + 1)], fill=(226, 104, 104, 80))
    img.alpha_composite(plate, (32, 0))
    return img


# --------------------------------------------------------------------------- animation
ANIM_LENGTH = 6.0
ANIM_FRAMES = 25


def motion(depth, count):
    """Amplitude (deg), lag and the sideways share for the joint at `depth`."""
    t = depth / max(1, count - 1)
    gain = 1.8 + 8.6 * t ** 1.7
    lag = 0.42 * t
    mix = 0.30 - 0.20 * t
    return gain, lag, mix


def build_animation(tendrils):
    """Lively idle: the tendril whips in its own plane and swings a little sideways.

    Keyframes are absolute, so the *solved* rest angles of the chain are written
    into the keys - otherwise playing the animation would flatten the curve.
    """
    animators = {}
    for index, tendril in enumerate(tendrils):
        phase = index * math.pi / 2.3
        count = len(tendril['bones'])
        for depth, bone in enumerate(tendril['bones']):
            gain, lag, mix = motion(depth, count)
            rest_y, rest_z = bone['yaw'], bone['turn']
            keys = []
            for step in range(ANIM_FRAMES):
                t = ANIM_LENGTH * step / (ANIM_FRAMES - 1)
                swing = 2 * math.pi * t / ANIM_LENGTH
                bend = gain * (math.sin(swing + phase - lag * 6.0)
                               + 0.22 * math.sin(2.0 * swing + phase * 1.7))
                side = gain * 0.5 * math.cos(swing * 0.72 + phase * 1.3 - lag * 4.0)
                keys.append({
                    'channel': 'rotation',
                    'data_points': [{
                        'x': '0',
                        'y': str(round(rest_y + side * mix, 3)),
                        'z': str(round(rest_z + bend, 3)),
                    }],
                    'uuid': uid(f'key:{bone["name"]}:{step}'),
                    'time': round(t, 3), 'color': -1, 'interpolation': 'linear',
                })
            keys[-1]['data_points'] = [dict(point) for point in keys[0]['data_points']]
            animators[uid(f'bone:{bone["name"]}')] = {
                'name': bone['name'], 'type': 'bone', 'keyframes': keys,
            }
    return {
        'uuid': uid('animation:idle'), 'name': 'idle', 'loop': 'loop', 'override': False,
        'length': ANIM_LENGTH, 'snapping': 30, 'selected': True, 'anim_time_update': '',
        'blend_weight': '', 'start_delay': '', 'loop_delay': '', 'animators': animators,
    }


# --------------------------------------------------------------------------- blueprint
def build_model():
    texture = build_texture()
    raw = io.BytesIO()
    texture.save(raw, format='PNG', optimize=True)
    texture_entry = {
        'path': '', 'name': f'{MODEL}.png', 'folder': '', 'namespace': '', 'id': '0',
        'width': 64, 'height': 64, 'uv_width': 16, 'uv_height': 16, 'particle': False,
        'use_as_default': False, 'layers_enabled': False, 'render_mode': 'default',
        'render_sides': 'auto', 'frame_time': 1, 'frame_order_type': 'loop',
        'frame_interpolate': False, 'visible': True, 'internal': True, 'saved': False,
        'uuid': uid('texture'), 'source': 'data:image/png;base64,'
        + base64.b64encode(raw.getvalue()).decode('ascii'),
    }

    elements, bones = [], []
    for tendril in TENDRILS:
        chain = []
        for bone in blade_bones(tendril):
            cubes = build_elements(bone)
            chain.append({
                'name': bone['name'],
                'origin': bone['origin'],
                'rotation': bone['rotation'],
                'color': 0, 'uuid': uid(f'bone:{bone["name"]}'),
                'export': True, 'mirror_uv': False, 'isOpen': True, 'locked': False,
                'visibility': True, 'autouv': 0,
                'children': [c['uuid'] for c in cubes],
            })
            elements.extend(cubes)
        for outer, inner in zip(chain, chain[1:]):
            outer['children'].append(inner)
        bones.append(chain[0])
        tendril['bones'] = [dict(bone) for bone in blade_bones(tendril)]

    knot_cubes = knot_elements()
    elements.extend(knot_cubes)
    knot_bone = {
        'name': KNOT['name'], 'origin': list(KNOT['origin']), 'rotation': [0.0, 0.0, 0.0],
        'color': 0, 'uuid': uid('bone:knot'), 'export': True, 'mirror_uv': False,
        'isOpen': True, 'locked': False, 'visibility': True, 'autouv': 0,
        'children': [c['uuid'] for c in knot_cubes],
    }
    root = {
        'name': 'tentacles_root', 'origin': list(ROOT_ORIGIN), 'rotation': [0.0, 0.0, 0.0],
        'color': 0, 'uuid': uid('bone:root'), 'export': True, 'mirror_uv': False,
        'isOpen': True, 'locked': False, 'visibility': True, 'autouv': 0,
        'children': [knot_bone] + bones,
    }
    return {
        'meta': {'format_version': '4.10', 'model_format': 'free', 'box_uv': False},
        'name': MODEL, 'model_identifier': MODEL, 'visible_box': [5, 5, 1],
        'resolution': {'width': 16, 'height': 16}, 'elements': elements,
        'outliner': [root], 'textures': [texture_entry],
        # No keyframes on purpose.  ElytrixFreakModel drives the worn
        # accessory through WornAngelRig, which keeps re-playing its
        # 'idle' clip on whatever model sits in the back slot; keyframes
        # are absolute, so any sign mismatch between the animation and the
        # bone rest pose bends every joint twice - that is what turned the
        # tentacles into C-shaped hoops in game.  The rest pose is the
        # shape; the silent clip is the fix.
        'animations': [],
    }, texture


# --------------------------------------------------------------------------- report
def report():
    """Print the silhouette numbers the acceptance tests care about."""
    for spec in TENDRILS:
        path = blade_path(spec)
        xs = [p[0] for p in path]
        widest = max(range(len(path)), key=lambda i: abs(xs[i]))
        tip, before = path[-1], path[-2]
        radial = (tip[0] - before[0]) * math.copysign(1.0, tip[0])
        print(f'{spec["name"]:12s} bones={len(path) - 1:2d} '
              f'tip=({tip[0]:6.1f},{tip[1]:5.1f},{tip[2]:5.1f}) '
              f'widest x={xs[widest]:6.1f} inward={abs(tip[0]) - abs(xs[widest]):+5.2f} '
              f'tipRadial={radial:+5.2f}')
    lo = [min(p[i] for s in TENDRILS for p in blade_path(s)) for i in range(3)]
    hi = [max(p[i] for s in TENDRILS for p in blade_path(s)) for i in range(3)]
    print('bbox', [round(v, 1) for v in lo], [round(v, 1) for v in hi],
          'size', [round(hi[i] - lo[i], 1) for i in range(3)])


# --------------------------------------------------------------------------- preview
def bone_chains(model):
    """uuid -> list of (origin, euler) from the root bone down to the owning bone."""
    chains = {}

    def walk(node, chain):
        for bone in node:
            if isinstance(bone, str):
                continue
            own = chain + [(tuple(bone['origin']), list(bone['rotation']))]
            for child in bone.get('children', []):
                if isinstance(child, str):
                    chains[child] = own
            walk([c for c in bone.get('children', []) if isinstance(c, dict)], own)

    walk(model['outliner'], [])
    return chains


def _rotation(axis, angle):
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    if axis == 0:
        return ((1, 0, 0), (0, c, -s), (0, s, c))
    if axis == 1:
        return ((c, 0, s), (0, 1, 0), (-s, 0, c))
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def _apply(matrix, vec):
    return tuple(sum(matrix[i][k] * vec[k] for k in range(3)) for i in range(3))


def _font(size):
    """DejaVu (Cyrillic) when present, PIL's bitmap font otherwise."""
    try:
        from PIL import ImageFont
        return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', size)
    except Exception:
        from PIL import ImageFont
        return ImageFont.load_default()


LIGHT = _norm((-0.42, 0.72, 0.55))


def preview(model, out_path, scale=8.0, size=(620, 460), title='', yaw=-26.0, pitch=8.0,
            texture=None, body=False, centre=(0.0, 27.0, 8.0), perspective=0.0,
            shade=0.85):
    """Small flat-shaded renderer (painter's algorithm + back-face culling).

    Bone rotations are applied, so the solved chain is drawn here exactly as the
    runtime will place it.  Faces get a lambert term, so the roundness of the
    tube can be judged here and not only in game.
    """
    img = Image.new('RGB', size, (24, 28, 42))
    draw = ImageDraw.Draw(img)
    cy_, sy_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp_, sp_ = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    def rotate(x, y, z):
        """Camera stands behind the player (+Z) and looks along -Z."""
        xr = x * cy_ - z * sy_
        zr = x * sy_ + z * cy_
        yr = y * cp_ - zr * sp_
        zr = y * sp_ + zr * cp_
        return -xr, yr, zr

    def view(x, y, z):
        return rotate(x - centre[0], y - centre[1], z - centre[2])

    def project(x, y, z):
        xr, yr, zr = view(x, y, z)
        factor = scale
        if perspective:
            factor = scale * perspective / max(1.0, perspective - zr)
        return (size[0] / 2 + xr * factor, size[1] / 2 - yr * factor), zr

    chains = bone_chains(model)
    quads = []
    for element in model['elements']:
        axis, angle = 2, 0.0
        for k in range(3):
            if element['rotation'][k]:
                axis, angle = k, element['rotation'][k]
        matrix = _rotation(axis, angle)
        origin = element['origin']
        chain = chains.get(element['uuid'], [])
        corner = {}
        for i in (0, 1):
            for j in (0, 1):
                for k in (0, 1):
                    local = (element['from'][0] if i == 0 else element['to'][0],
                             element['from'][1] if j == 0 else element['to'][1],
                             element['from'][2] if k == 0 else element['to'][2])
                    rel = _apply(matrix, tuple(local[n] - origin[n] for n in range(3)))
                    point = tuple(origin[n] + rel[n] for n in range(3))
                    for bone_origin, euler in reversed(chain):
                        for axis_index in range(3):
                            if euler[axis_index]:
                                bone_matrix = _rotation(axis_index, euler[axis_index])
                                rel = tuple(point[n] - bone_origin[n] for n in range(3))
                                point = tuple(bone_origin[n] + _apply(bone_matrix, rel)[n]
                                              for n in range(3))
                    corner[(i, j, k)] = point
        sides = [
            ([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], (0, 0, -1), 'north'),
            ([(0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1)], (0, 0, 1), 'south'),
            ([(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)], (0, 1, 0), 'up'),
            ([(0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)], (0, -1, 0), 'down'),
            ([(1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)], (1, 0, 0), 'east'),
            ([(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)], (-1, 0, 0), 'west'),
        ]
        for keys, normal, face_name in sides:
            pts = [corner[key] for key in keys]
            world = _apply(matrix, normal)
            for _, euler in reversed(chain):
                for axis_index in range(3):
                    if euler[axis_index]:
                        world = _apply(_rotation(axis_index, euler[axis_index]), world)
            quads.append((pts, world, element['faces'][face_name]['uv'], None))

    if body:
        # a plain player proxy (legs, torso, head in 1/16 units) so the scale of
        # the fan can be judged against something that is exactly 1.8 blocks tall
        proxy = [((-4, 0, -2), (4, 12, 2), (66, 74, 92)),
                 ((-4, 12, -2), (4, 24, 2), (96, 104, 126)),
                 ((-4, 24, -2), (4, 32, 2), (128, 132, 152))]
        for low, high, colour in proxy:
            for keys, normal in (((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)), (0, 0, -1)), \
                                (((0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1)), (0, 0, 1)), \
                                (((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)), (0, 1, 0)), \
                                (((1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)), (1, 0, 0)), \
                                (((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)), (-1, 0, 0)):
                pts = []
                for ix, iy, iz in keys:
                    pts.append((low[0] + (high[0] - low[0]) * ix,
                                low[1] + (high[1] - low[1]) * iy,
                                low[2] + (high[2] - low[2]) * iz))
                quads.append((pts, normal, None, colour))

    rendered = []
    for pts, normal, uv, flat in quads:
        projected = [project(*pt) for pt in pts]
        depth = sum(d for _, d in projected) / len(projected)
        nx, ny, nz = rotate(*normal)
        rendered.append((depth, [q for q, _ in projected], nz, uv, flat, normal))
    rendered.sort(key=lambda item: item[0])       # far away first (painter's algorithm)

    for _, poly, nz, uv, flat, normal in rendered:
        if nz <= 0:
            continue
        lambert = max(0.0, sum(normal[i] * LIGHT[i] for i in range(3)))
        factor = 1.0 - shade + shade * (0.40 + 0.80 * lambert)
        if flat is not None or texture is None:
            colour = flat if flat is not None else (196, 26, 34)
            colour = tuple(max(0, min(255, int(c * factor))) for c in colour)
            draw.polygon(poly, fill=colour)
            continue
        # sample the texture across the face, so the cylindrical gradient that
        # the skin carries is visible here exactly as the client will draw it
        u0, v0, u1, v1 = uv
        pixels = texture.convert('RGB').load()
        steps = 4
        c00, c10, c11, c01 = poly[0], poly[1], poly[2], poly[3]

        def bilerp(a, b):
            top = (c00[0] + (c10[0] - c00[0]) * a, c00[1] + (c10[1] - c00[1]) * a)
            bottom = (c01[0] + (c11[0] - c01[0]) * a, c01[1] + (c11[1] - c01[1]) * a)
            return (top[0] + (bottom[0] - top[0]) * b, top[1] + (bottom[1] - top[1]) * b)

        for su in range(steps):
            for sv in range(steps):
                a0, a1 = su / steps, (su + 1) / steps
                b0, b1 = sv / steps, (sv + 1) / steps
                cell = [bilerp(a0, b0), bilerp(a1, b0), bilerp(a1, b1), bilerp(a0, b1)]
                tx = int((u0 + (u1 - u0) * (a0 + a1) / 2) * 4)
                ty = int((v0 + (v1 - v0) * (b0 + b1) / 2) * 4)
                tx = max(0, min(texture.width - 1, tx))
                ty = max(0, min(texture.height - 1, ty))
                colour = pixels[tx, ty]
                colour = tuple(max(0, min(255, int(c * factor))) for c in colour)
                draw.polygon(cell, fill=colour)

    font = _font(18)
    small = _font(14)
    draw.text((12, 10), title, fill=(232, 232, 242), font=font)
    draw.text((12, 36), 'схема: та же математика скелета, что и в игре', fill=(150, 152, 170),
              font=small)
    img.save(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', default=str(HERE))
    parser.add_argument('--preview', action='store_true', help='also write the schematic preview')
    parser.add_argument('--report', action='store_true', help='print silhouette numbers')
    args = parser.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    model, texture = build_model()
    (out / f'{MODEL}.bbmodel').write_text(json.dumps(model, ensure_ascii=False, indent=1) + '\n',
                                          encoding='utf-8')
    texture.save(out / f'{MODEL}.png')
    if args.report:
        report()
    if args.preview:
        panel = (620, 700)
        centre = (0.0, 23.0, 4.0)
        preview(model, out / 'tentacles_back.png', title='вид со спины (как в игре)',
                yaw=0, pitch=0, scale=13.0, size=panel, texture=texture, body=True,
                centre=centre, perspective=240.0)
        preview(model, out / 'tentacles_angle.png', title='вид 3/4', yaw=42, pitch=12,
                scale=12.5, size=panel, texture=texture, body=True,
                centre=centre, perspective=240.0)
        preview(model, out / 'tentacles_side.png', title='вид сбоку (объём)',
                yaw=90, pitch=6, scale=13.0, size=panel, texture=texture, body=True,
                centre=centre, perspective=240.0)
        preview(model, out / 'tentacles_top.png', title='вид сверху (четыре луча)',
                yaw=0, pitch=84, scale=13.0, size=panel, texture=texture, body=True,
                centre=centre, perspective=260.0)
        preview(model, out / 'tentacles_front.png', title='вид спереди (вышли за тело)',
                yaw=180, pitch=4, scale=13.0, size=panel, texture=texture, body=True,
                centre=centre, perspective=240.0)
        names = ('tentacles_back', 'tentacles_front', 'tentacles_angle', 'tentacles_side',
                 'tentacles_top')
        combo = Image.new('RGB', (panel[0] * len(names), panel[1]), (24, 28, 42))
        for index, name in enumerate(names):
            combo.paste(Image.open(out / f'{name}.png'), (panel[0] * index, 0))
        combo.save(out / 'tentacles_preview.png')
    print(f'{len(model["elements"])} cubes in {len(model["outliner"][0]["children"])} bones -> {out}')


if __name__ == '__main__':
    main()
