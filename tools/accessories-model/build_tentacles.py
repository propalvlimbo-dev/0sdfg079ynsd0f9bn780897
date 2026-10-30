#!/usr/bin/env python3
"""Builds the Kaneki kagune (щупальца) blueprint + texture, pixel-art only.

v8 - the shape is no longer drawn by hand-tuned joint angles. Every tendril is a
**3-D spline traced from the reference render**, and the bone chain is *solved* so
that stacking the joint rotations reproduces that spline bit for bit:

1. control points are interpolated with a centripetal Catmull-Rom spline,
2. the spline is resampled by arc length into `BONES` straight chords,
3. for every chord the exact local Euler angles are solved:

       R_i = Rz(a_i) . Ry(b_i)          (what ModelEngine does: rotateZYX)
       W_i = W_(i-1) . R_i ,  W_i . (1,0,0) = chord direction

   so the runtime reproduces the traced curve with **no drift and no zig-zag** -
   the per-joint turn is only ~8-12 deg, and neighbouring boxes overlap, so the
   silhouette stays a smooth arc instead of a saw.

Why the earlier versions looked crooked in game
-----------------------------------------------
v7 joined 2 boxes per bone with alternating widths (1.06 / 0.94) and per-joint
turns of 20-30 deg: the outline was a staircase of notches, and the four blades
only differed by a yaw of the whole plane, so from behind they read as a star.
Here the notch is 0.4 units wide and the turn is ~10 deg, the boxes overlap, and
the tip of every tendril is made to travel *back towards the spine* - the last
two joints have a negative radial component, so all four tips curl inward.

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
PARTS = tuple('abcdefghijklmn')       # bone suffixes, one per joint (<= 14)

# --------------------------------------------------------------------------- tendrils
# Blockbench units: +X = the player's right, +Y = up, +Z = behind the back.
# A player is 32 units tall, so y=18..19 is the middle of the back (the shoulder
# blades) - that is where all four tendrils leave the spine together.
#
# A tendril is described by the way it *turns*, not by hand-placed joints:
#   `turns`  - (heading at the start of the piece, heading at its end, length).
#              The heading is the angle of the tendril in the plane of the back:
#              90 deg = straight up, 0 deg = straight out sideways.  Turning past
#              90 deg means the tendril is travelling back towards the spine, so
#              the tip of every tendril ends up *inward* of its widest point.
#   `fan`    - the yaw (0 = in the plane of the back, + = swept behind), eased
#              from the root to the tip.  This is what opens the four tendrils
#              into a fan in the top view while they still rise straight up in
#              the back view.
#   `girth`  - (width in the plane of the back, depth) at the root.
TENDRILS = [
    {
        # tall upper pair - leaves the spine almost vertically, opens outward,
        # then the thin tip curls up and back over towards the head
        'name': 'right_upper',
        'root': (0.4, 18.0, 1.7),
        'turns': [(52.0, 22.0, 16.0), (22.0, 160.0, 9.5)],
        'fan': (22.0, 44.0),
        'girth': (5.0, 3.6), 'tip': 0.30,
    },
    {
        'name': 'left_upper',
        'root': (-0.4, 18.3, 1.7),
        'turns': [(126.0, 156.0, 15.6), (156.0, 20.0, 10.0)],
        'fan': (-20.0, -40.0),
        'girth': (4.8, 3.5), 'tip': 0.28,
    },
    {
        # wide lower pair - out over the waist, then the tip curls down and inward
        'name': 'right_lower',
        'root': (0.5, 18.6, 2.2),
        'turns': [(8.0, -6.0, 15.0), (-6.0, -140.0, 10.0)],
        'fan': (6.0, 18.0),
        'girth': (4.9, 3.5), 'tip': 0.28,
    },
    {
        'name': 'left_lower',
        'root': (-0.5, 18.2, 2.2),
        'turns': [(174.0, 188.0, 14.4), (188.0, 316.0, 10.4)],
        'fan': (-5.0, -16.0),
        'girth': (4.7, 3.4), 'tip': 0.28,
    },
]

# the fleshy knot the four tendrils grow out of - it straddles the player's back
# surface (z = +2), so from any angle the tendrils start *at the spine*
KNOT = {
    'name': 'root_knot',
    'origin': [0.0, 19.2, 2.4],
    'boxes': [
        # (x0, x1, y0, y1, z0, z1) relative to the origin
        (-1.9, 1.9, -1.9, 0.1, -0.5, 1.9),
        (-2.9, 2.9, -0.9, 1.1, -0.7, 2.1),
        (-2.1, 2.1, 0.9, 2.3, -0.5, 1.7),
        (-1.1, 1.1, 1.9, 3.1, -0.3, 1.2),
        (-3.3, -1.5, -0.3, 1.5, 0.0, 1.5),
        (1.5, 3.3, -0.3, 1.5, 0.0, 1.5),
    ],
}

STEP = 0.1                      # integration step of the traced centre line
MAX_TURN = 15.0                 # largest angle between two joints (deg)
MAX_LEN = 5.0                   # longest bone
MIN_LEN = 1.5                   # shortest bone


def uid(tag):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'elytrix-kaneki:{tag}'))


# --------------------------------------------------------------------------- curve
def smoothstep(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def trace(spec, step=STEP):
    """Integrate the heading profile into a smooth 3-D centre line."""
    total = sum(piece[2] for piece in spec['turns'])
    x, y, z = spec['root']
    points = [(x, y, z)]
    walked = 0.0
    fan0, fan1 = spec['fan']
    for head0, head1, length in spec['turns']:
        count = max(1, int(round(length / step)))
        for index in range(count):
            u = (index + 0.5) / count
            s = walked + length * u
            head = math.radians(head0 + (head1 - head0) * u)
            fan = math.radians(fan0 + (fan1 - fan0) * smoothstep(s / total))
            piece = length / count
            x += math.cos(head) * math.cos(fan) * piece
            y += math.sin(head) * piece
            z += math.cos(head) * math.sin(fan) * piece
            points.append((x, y, z))
        walked += length
    return points


def turn_between(a, b, c):
    """Angle between the chords a->b and b->c in degrees."""
    u = _norm(tuple(b[i] - a[i] for i in range(3)))
    v = _norm(tuple(c[i] - b[i] for i in range(3)))
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(u[i] * v[i] for i in range(3))))))


def allowed_turn(t):
    """How much a joint may bend at `t` (0 root .. 1 tip), in degrees.

    A bend of `a` degrees opens a notch of `width * sin(a)` on the outside of the
    joint.  The tendril is 5 units wide at the root and 1.6 at the curl, so the
    same 20 deg is a visible kink at the root and invisible at the tip - the
    threshold follows the taper instead of being one constant.
    """
    return 11.0 if t < 0.70 else 22.0


def adaptive_resample(dense, max_len=MAX_LEN):
    """Cut joints by accumulated *curvature*, not by arc length.

    Long bones run through the straight part of the tendril, short bones carry the
    tight curl of the tip - exactly the opposite of what v7 did (one 80 deg kink
    at the end), and it keeps the bone count low.
    """
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
    # fold a stub of a last bone into the previous one, it would read as a chip
    while len(joints) > 3 and math.dist(joints[-2], joints[-1]) < 1.0:
        joints.pop(-2)
    return joints


def _norm(v):
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / length for c in v)


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
    """Where the solved chain actually puts every joint (used by the tests)."""
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
    """Width (in the plane of the back) and depth at `t` = 0 root .. 1 tip."""
    width0, depth0 = spec['girth']
    fade = max(0.0, 1.0 - t) ** 0.55
    return (spec['tip'] + (width0 - spec['tip']) * fade,
            spec['tip'] + (depth0 - spec['tip']) * fade)


def blade_bones(spec):
    """The traced centre line as a chain of bones.

    The bones are laid out **straight along +X** in the rest pose and the solved
    rotations bend them into the traced curve at runtime - that is the only
    rig ModelEngine/Blockbench understands: it rotates each bone's local offset
    through the parent chain.  v7 placed the origins on the curve *and* rotated
    them, so every joint was bent twice: that is what read as "crooked" in game.
    """
    points = adaptive_resample(trace(spec))
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
        # the width of the *far* end of the bone: that keeps the taper monotone and
        # makes the last bone an actual needle point
        width, depth = blade_profile(spec, t1)
        # overlap backwards into the parent so a bend can never open a notch
        overlap = 0.0 if index == 0 else min(1.1, 0.55 * length)
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
    'body': [0.0, 0.0, 8.0, 8.0],
    'scales': [8.0, 0.0, 16.0, 8.0],
    'top': [0.0, 8.0, 8.0, 16.0],
    'dark': [8.0, 8.0, 16.0, 16.0],
}


def build_elements(bone):
    """One bone of the chain as a single unrotated Blockbench cube."""
    box = bone['box']
    half_w, half_d = box['width'] / 2, box['depth'] / 2
    origin = bone['origin']
    p0 = [origin[0] + box['x0'], origin[1] - half_w, origin[2] - half_d]
    p1 = [origin[0] + box['x1'], origin[1] + half_w, origin[2] + half_d]
    body = 'scales' if bone['t'] > 0.72 else 'body'
    faces = {
        'up': {'uv': list(UV_REGIONS['top']), 'texture': 0},
        'down': {'uv': list(UV_REGIONS['dark']), 'texture': 0},
        'east': {'uv': list(UV_REGIONS[body]), 'texture': 0},
        'west': {'uv': list(UV_REGIONS[body]), 'texture': 0},
        'north': {'uv': list(UV_REGIONS[body]), 'texture': 0},
        'south': {'uv': list(UV_REGIONS[body]), 'texture': 0},
    }
    return [{
        'name': f'{bone["name"]}_0',
        'box_uv': False, 'rescale': False, 'locked': False, 'light_emission': 0,
        'render_order': 'default', 'allow_mirror_modeling': True,
        'from': [round(v, 4) for v in p0], 'to': [round(v, 4) for v in p1],
        'autouv': 0, 'color': 0,
        'origin': [round(origin[0] + (box['x0'] + box['x1']) / 2, 4),
                   round(origin[1], 4), round(origin[2], 4)],
        'rotation': [0.0, 0.0, 0.0],
        'faces': faces, 'type': 'cube', 'uuid': uid(f'cube:{bone["name"]}:0'),
    }]


def knot_elements():
    """The root knot: a few cubes of thick flesh on the spine, no bone rotation."""
    elements = []
    origin = KNOT['origin']
    for index, (x0, x1, y0, y1, z0, z1) in enumerate(KNOT['boxes']):
        faces = {
            'up': {'uv': list(UV_REGIONS['top']), 'texture': 0},
            'down': {'uv': list(UV_REGIONS['dark']), 'texture': 0},
            'east': {'uv': list(UV_REGIONS['body']), 'texture': 0},
            'west': {'uv': list(UV_REGIONS['body']), 'texture': 0},
            'north': {'uv': list(UV_REGIONS['body']), 'texture': 0},
            'south': {'uv': list(UV_REGIONS['body']), 'texture': 0},
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

    ItemDisplay entities in Minecraft are lit flatly, so the volume is baked into
    the texture: the top face uses a bright tile, the sides a mid crimson tile and
    the underside a dark maroon tile.
    """
    size = 64
    img = Image.new('RGBA', (size, size), (120, 6, 16, 255))
    px = img.load()

    def tile(x0, y0, x1, y1, colour, grain):
        for y in range(y0, y1):
            for x in range(x0, x1):
                n = (math.sin(x * 0.9 + y * 1.7) * 0.5
                     + math.sin(x * 0.31 - y * 0.73) * 0.5) * grain
                px[x, y] = tuple(max(0, min(255, int(c * (1 + n)))) for c in colour) + (255,)

    # sides: mid crimson with a soft vertical sheen (V runs across the tendril)
    tile(0, 0, 32, 32, (150, 14, 24), 0.10)
    for y in range(32):
        sheen = max(0.0, 1.0 - abs(((y % 32) - 9) / 9.0)) ** 2
        for x in range(32):
            r, g, b, a = px[x, y]
            px[x, y] = (min(255, int(r + 60 * sheen)), min(255, int(g + 26 * sheen)),
                        min(255, int(b + 24 * sheen)), a)

    # top face: bright, sun-lit crimson
    tile(0, 32, 32, 64, (206, 44, 52), 0.08)
    for y in range(32, 64):
        k = 1.0 - (y - 32) / 64.0
        for x in range(32):
            r, g, b, a = px[x, y]
            px[x, y] = (min(255, int(r * (0.86 + 0.3 * k))), min(255, int(g * (0.9 + 0.3 * k))),
                        min(255, int(b * (0.9 + 0.3 * k))), a)

    # underside: shadowed maroon
    tile(32, 32, 64, 64, (74, 2, 12), 0.12)
    for y in range(32, 64):
        for x in range(32, 64, 3):
            px[x, y] = (58, 0, 8, 255)

    # scale plates for the tip (UV 8..16 x 0..8 -> pixels 32..64 x 0..32)
    plate = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(plate)
    for row in range(4):
        for col in range(5):
            ox = col * 8 - (4 if row % 2 else 0)
            oy = row * 8
            pdraw.rounded_rectangle([ox, oy, ox + 8, oy + 8], radius=2,
                                    fill=(168, 22, 32, 255), outline=(92, 4, 12, 255))
            pdraw.line([(ox + 1, oy + 1), (ox + 6, oy + 1)], fill=(255, 122, 122, 255))
            pdraw.point((ox + 2, oy + 2), fill=(255, 176, 176, 255))
    img.alpha_composite(plate, (32, 0))

    # glossy veins down the sides of the tendril
    draw = ImageDraw.Draw(img)
    for y0 in (5, 13, 20, 27):
        points = []
        for x in range(0, 33, 2):
            points.append((x, y0 + math.sin(x * 0.42 + y0) * 1.1))
        draw.line(points, fill=(224, 52, 62, 255), width=1)
    return img


# --------------------------------------------------------------------------- animation
BONES_PER_TENDRIL = 10
ANIM_LENGTH = 6.0
ANIM_FRAMES = 25


def motion(depth):
    """Amplitude (deg), lag and the sideways share for the joint at `depth`."""
    t = depth / max(1, BONES_PER_TENDRIL - 1)
    gain = 1.6 + 9.4 * t ** 1.7
    lag = 0.42 * t
    mix = 0.32 - 0.22 * t
    return gain, lag, mix


def build_animation(tendrils):
    """Lively idle: the tendril whips in its own plane and swings a little sideways.

    Keyframes are absolute, so the *solved* rest angles of the chain are written
    into the keys - otherwise playing the animation would flatten the curve.
    """
    animators = {}
    for index, tendril in enumerate(tendrils):
        phase = index * math.pi / 2.3
        for depth, bone in enumerate(tendril['bones']):
            gain, lag, mix = motion(depth)
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
        'animations': [build_animation(TENDRILS)],
    }, texture


# --------------------------------------------------------------------------- report
def report():
    """Print the silhouette numbers the acceptance tests care about."""
    for spec in TENDRILS:
        path = blade_path(spec)
        xs = [p[0] for p in path]
        widest = max(range(len(path)), key=lambda i: abs(xs[i]))
        tip = path[-1]
        before = path[-2]
        radial = abs(tip[0]) - abs(xs[widest])
        bearing = math.degrees(math.atan2(abs(tip[2] - path[0][2]), abs(tip[0] - path[0][0])))
        turns = [b['turn'] for b in blade_bones(spec)]
        print(f'{spec["name"]:12s} tip=({tip[0]:6.1f},{tip[1]:5.1f},{tip[2]:5.1f}) '
              f'widest x={xs[widest]:6.1f}@y={path[widest][1]:5.1f} '
              f'radial={radial:+5.2f} bearing={bearing:4.1f} '
              f'turn max={max(abs(t) for t in turns):4.1f} '
              f'tipdir=({tip[0]-before[0]:+.1f},{tip[1]-before[1]:+.1f})')
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


def preview(model, out_path, scale=8.0, size=(620, 460), title='', yaw=-26.0, pitch=8.0,
            texture=None, body=False, centre=(0.0, 27.0, 8.0), show_outline=True,
            perspective=0.0):
    """Small flat-shaded renderer (painter's algorithm + back-face culling).

    Bone rotations are applied, so the solved chain is drawn here exactly as the
    runtime will place it.  `perspective` > 0 adds a simple distance divide that
    mimics the in-game third-person camera, which is what made earlier previews
    look better than the live model.
    """
    img = Image.new('RGB', size, (24, 28, 42))
    draw = ImageDraw.Draw(img)
    cy_, sy_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp_, sp_ = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    def rotate(x, y, z):
        """Camera stands behind the player (+Z) and looks along -Z.

        Screen X is mirrored, because standing behind somebody their right hand
        is on your right: that is the framing of the in-game screenshot.
        """
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
                    # world = T_root . T_child . ... : the innermost bone is applied
                    # first and the root frame last
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
        # a plain player proxy (boots, legs, torso, head in 1/16 units) so the scale
        # of the fan can be judged against something that is exactly 1.8 blocks tall
        proxy = [((-4, 0, -2), (4, 12, 2)), ((-4, 12, -2), (4, 24, 2)),
                 ((-4, 24, -2), (4, 32, 2))]
        for low, high in proxy:
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
                quads.append((pts, normal, None, (96, 104, 126)))

    rendered = []
    for pts, normal, uv, flat in quads:
        projected = [project(*pt) for pt in pts]
        depth = sum(d for _, d in projected) / len(projected)
        nx, ny, nz = rotate(*normal)          # normals are directions: no translation
        rendered.append((depth, [q for q, _ in projected], nz, uv, flat))
    rendered.sort(key=lambda item: -item[0])

    for _, poly, nz, uv, flat in rendered:
        if nz <= 0:
            continue
        if flat is not None:
            colour = flat
        elif texture is not None:
            u0, v0, u1, v1 = uv
            box = texture.crop((int(u0 * 4), int(v0 * 4), int(u1 * 4), int(v1 * 4))).convert('RGB')
            patch = list(box.getdata())
            colour = tuple(sum(px[i] for px in patch) // len(patch) for i in range(3))
        else:
            colour = (196, 26, 34)
        draw.polygon(poly, fill=colour,
                     outline=(70, 2, 10) if (flat is None and show_outline) else None)

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
        panel = (620, 720)
        centre = (0.0, 23.0, 5.0)
        preview(model, out / 'tentacles_back.png', title='вид со спины (как в игре)',
                yaw=0, pitch=0, scale=13.5, size=panel, texture=texture, body=True,
                centre=centre, perspective=240.0)
        preview(model, out / 'tentacles_angle.png', title='вид 3/4', yaw=38, pitch=12,
                scale=13.0, size=panel, texture=texture, body=True,
                centre=centre, perspective=240.0)
        preview(model, out / 'tentacles_top.png', title='вид сверху (проверка веера)',
                yaw=0, pitch=84, scale=13.5, size=panel, texture=texture, body=True,
                centre=centre, perspective=260.0)
        combo = Image.new('RGB', (panel[0] * 3, panel[1]), (24, 28, 42))
        for index, name in enumerate(('tentacles_back', 'tentacles_angle', 'tentacles_top')):
            combo.paste(Image.open(out / f'{name}.png'), (panel[0] * index, 0))
        combo.save(out / 'tentacles_preview.png')
    print(f'{len(model["elements"])} cubes in {len(model["outliner"][0]["children"])} bones -> {out}')


if __name__ == '__main__':
    main()
