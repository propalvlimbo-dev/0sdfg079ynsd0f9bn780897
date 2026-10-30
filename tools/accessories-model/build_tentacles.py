#!/usr/bin/env python3
"""Builds the Kaneki kagune (щупальца) blueprint + texture, pixel-art only.

v5. The reference is four long, *slim* crimson blades that leave the back and sweep
outward in big smooth arcs, tapering into needle points.

What changed after the in-game screenshots of v4
------------------------------------------------
* **They were fat straps.** The cross-section was 8-9 units wide and nearly as deep,
  so the blade read as a beam. It is now 4.6 units at the root and drops to 0.22 at
  the tip (about a fifth of a block), with the depth about half of that.
* **The silhouette was a saw.** v4 changed the cube angle every 2 units and cube
  angles may only be multiples of 22.5 deg, so the edge was a staircase. The curve is
  now carried by a *chain of six bones* (bones take arbitrary angles - the shipped
  dwarves use values such as -79.9 deg) and every cube is an unrotated box inside its
  bone, so the outline has ~10 deg joints instead of 22.5 deg zig-zag.
* **The hierarchy does the bending.** Cubes are authored in the rest pose along +X and
  the runtime stacks each bone's rotation on its parent's, exactly like the
  gp2_goblin_warrior leg -> shin -> foot chain (nested bones with rotations such as
  [47.4, 23.3, -18.5]).

No cube has a rotation of its own, so `RotationSolver` - the part of ModelEngine
4.1.0 that throws on cube angles off the 22.5 deg grid - is never reached.

Usage:
    python3 tools/accessories-model/build_tentacles.py [--out-dir DIR] [--preview]
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
PARTS = ('a', 'b', 'c', 'd', 'e', 'f')   # six bones per blade = six joints to animate
SEGMENTS = 8                      # long straight pieces per blade
SNAP = 22.5                       # the only angles ModelEngine 4.1.0 accepts

# --------------------------------------------------------------------------- blades
# Blockbench units: +X = the player's right, +Y = up, +Z = behind the back.
# `start` is the direction of the first segment in the blade's own XY plane,
# `curve` bends it per unit of length, `yaw` turns the whole plane around the back.
# The four blades deliberately differ: a perfect mirror pair reads as cardboard.
BLADES = [
    {
        # right upper: leaves the shoulder blade level, flattens over the middle and
        # hooks up at the tip - the claw of the reference
        'name': 'right_upper',
        'root': (1.4, 19.8, 2.4), 'yaw': -24.0, 'length': 50.0,
        'turns': (0.0, 9.0, 6.0, 6.0, 8.0, 10.0),
        'girth': (5.2, 3.0), 'tip': 0.26,
    },
    {
        # right lower: lower on the back, dips first and rises the whole way after -
        # the opposite curvature to the upper blade, so the pair is never parallel
        'name': 'right_lower',
        'root': (1.6, 14.6, 3.0), 'yaw': -32.0, 'length': 42.0,
        'turns': (0.0, -4.0, 4.0, 6.0, 8.0, 10.0),
        'girth': (4.9, 2.8), 'tip': 0.24,
    },
    {
        # left upper: longer than its right twin and it lifts earlier
        'name': 'left_upper',
        'root': (-1.3, 20.8, 3.2), 'yaw': 180.0 + 21.0, 'length': 47.0,
        'turns': (0.0, 11.0, 7.0, 6.0, 7.0, 9.0),
        'girth': (5.0, 2.9), 'tip': 0.26,
    },
    {
        # left lower: the shortest blade and the widest yaw - the fan is never
        # mirror-symmetric, which is what keeps it from looking like cardboard
        'name': 'left_lower',
        'root': (-1.6, 13.9, 3.6), 'yaw': 180.0 + 29.0, 'length': 40.0,
        'turns': (0.0, -6.0, 4.0, 6.0, 8.0, 10.0),
        'girth': (4.7, 2.7), 'tip': 0.24,
    },
]

TENDRILS = [dict(spec) for spec in BLADES]


def uid(tag):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'elytrix-kaneki:{tag}'))


def blade_path(spec):
    """Joint positions of the blade in world space (the transform the runtime uses).

    The rest pose runs along +X; bone k has its own turn, which stacks on top of the
    parent's frame, so the direction of bone k is the sum of the turns up to it.  The
    root bone additionally yaws the whole blade around the back.
    """
    count = len(spec['turns'])
    length = spec['length'] / count
    yaw = math.radians(spec['yaw'])
    x, y, z = spec['root']
    points = [(x, y, z)]
    angle = 0.0
    for turn in spec['turns']:
        angle += turn
        rad = math.radians(angle)
        x += length * math.cos(rad) * math.cos(yaw)
        y += length * math.sin(rad)
        z -= length * math.cos(rad) * math.sin(yaw)
        points.append((x, y, z))
    return points


def blade_profile(spec, t):
    """Width (across the blade) and depth (through it) at `t` = 0 root .. 1 tip.

    A kagune is a scythe: it stays meaty for the first third and then runs out into
    a needle, so the exponent is close to linear but slightly convex.
    """
    width0, depth0 = spec['girth']
    fade = max(0.0, 1.0 - t) ** 0.85
    width = spec['tip'] + (width0 - spec['tip']) * fade
    depth = spec['tip'] + (depth0 - spec['tip']) * fade
    return width, depth


def blade_bones(spec, sub=2):
    """The blade as a chain of bones, each with straight boxes in the rest pose.

    The rest pose runs along +X; the curve comes entirely from the bones' own
    rotations, which the runtime stacks parent -> child.  That is what makes the
    outline smooth: a bone may turn by any angle, a cube only by multiples of 22.5.
    """
    count = len(spec['turns'])
    length = spec['length'] / count
    root = spec['root']
    bones = []
    for index, turn in enumerate(spec['turns']):
        origin = (root[0] + length * index, root[1], root[2])
        boxes = []
        for part in range(sub):
            t0, t1 = part / sub, (part + 1) / sub
            width, depth = blade_profile(spec, (index + (t0 + t1) / 2) / count)
            boxes.append({
                'x0': round(length * t0, 4), 'x1': round(length * t1, 4),
                'width': width, 'depth': depth,
                't': (index + (t0 + t1) / 2) / count,
            })
        bones.append({
            'name': f'{spec["name"]}_{PARTS[index]}',
            'origin': [round(v, 4) for v in origin],
            'turn': turn,
            'boxes': boxes,
        })
    return bones


# UV layout inside the 0..16 space of a vanilla-mapped texture (64x64 -> 4px per unit)
UV_REGIONS = {
    'body': [0.0, 0.0, 8.0, 8.0],
    'scales': [8.0, 0.0, 16.0, 8.0],
    'top': [0.0, 8.0, 8.0, 16.0],
    'dark': [8.0, 8.0, 16.0, 16.0],
}


def uv_rect(region):
    return list(UV_REGIONS[region])


def build_elements(bone):
    """One bone of the blade as unrotated Blockbench cubes with per-face UV regions."""
    elements = []
    for index, box in enumerate(bone['boxes']):
        width, depth = box['width'] / 2, box['depth'] / 2
        p0 = [bone['origin'][0] + box['x0'], bone['origin'][1] - width,
              bone['origin'][2] - depth]
        p1 = [bone['origin'][0] + box['x1'], bone['origin'][1] + width,
              bone['origin'][2] + depth]
        body = 'scales' if box['t'] > 0.72 else 'body'
        faces = {
            'up': {'uv': uv_rect('top'), 'texture': 0},
            'down': {'uv': uv_rect('dark'), 'texture': 0},
            'east': {'uv': uv_rect(body), 'texture': 0},
            'west': {'uv': uv_rect(body), 'texture': 0},
            'north': {'uv': uv_rect(body), 'texture': 0},
            'south': {'uv': uv_rect(body), 'texture': 0},
        }
        elements.append({
            'name': f'{bone["name"]}_{index}',
            'box_uv': False, 'rescale': False, 'locked': False, 'light_emission': 0,
            'render_order': 'default', 'allow_mirror_modeling': True,
            'from': [round(v, 4) for v in p0], 'to': [round(v, 4) for v in p1],
            'autouv': 0, 'color': 0,
            'origin': [round(bone['origin'][0] + (box['x0'] + box['x1']) / 2, 4),
                       round(bone['origin'][1], 4), round(bone['origin'][2], 4)],
            'rotation': [0.0, 0.0, 0.0],
            'faces': faces, 'type': 'cube', 'uuid': uid(f'cube:{bone["name"]}:{index}'),
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
ANIM_LENGTH = 6.0
ANIM_FRAMES = 37
# per joint of the chain: amplitude (degrees), lag, and the mix between the in-plane
# bend (z) and the sideways swing (y)
BONE_MOTION = (
    (2.5, 0.00, (1.00, 0.40)),
    (4.0, 0.08, (1.00, 0.30)),
    (5.5, 0.16, (1.00, 0.24)),
    (7.0, 0.23, (1.00, 0.18)),
    (9.0, 0.30, (1.00, 0.14)),
    (11.0, 0.38, (1.00, 0.10)),
)


def build_animation(tendrils):
    """Lively idle: the blade whips in its own plane and swings a little sideways.

    Keyframes are absolute, so the root bone's static yaw is written into its keys -
    otherwise playing the animation would flatten the fan.
    """
    animators = {}
    for index, tendril in enumerate(tendrils):
        phase = index * math.pi / 2.3
        for depth, (bone_name, (gain, lag, mix)) in enumerate(zip(tendril['bones'], BONE_MOTION)):
            yaw = tendril['yaw'] if depth == 0 else 0.0
            base = 0.0 if depth == 0 else tendril['turns'][depth]
            keys = []
            for step in range(ANIM_FRAMES):
                t = ANIM_LENGTH * step / (ANIM_FRAMES - 1)
                swing = 2 * math.pi * t / ANIM_LENGTH
                bend = gain * (math.sin(swing + phase - lag * 6.0)
                               + 0.30 * math.sin(2.0 * swing + phase * 1.7))
                side = gain * 0.55 * math.cos(swing * 0.75 + phase * 1.3 - lag * 4.0)
                keys.append({
                    'channel': 'rotation',
                    'data_points': [{
                        'x': '0',
                        'y': str(round(yaw + side * mix[1], 3)),
                        'z': str(round(base + bend * mix[0], 3)),
                    }],
                    'uuid': uid(f'key:{bone_name}:{step}'),
                    'time': round(t, 3), 'color': -1, 'interpolation': 'linear',
                })
            keys[-1]['data_points'] = [dict(point) for point in keys[0]['data_points']]
            animators[uid(f'bone:{bone_name}')] = {
                'name': bone_name, 'type': 'bone', 'keyframes': keys,
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
        for index, bone in enumerate(blade_bones(tendril)):
            cubes = build_elements(bone)
            chain.append({
                'name': bone['name'],
                'origin': bone['origin'],
                # the root bone turns the whole blade around the back, the rest of
                # the chain bends it inside its own plane
                'rotation': [0.0, tendril['yaw'], 0.0] if index == 0
                else [0.0, 0.0, bone['turn']],
                'color': index, 'uuid': uid(f'bone:{bone["name"]}'),
                'export': True, 'mirror_uv': False, 'isOpen': True, 'locked': False,
                'visibility': True, 'autouv': 0,
                'children': [c['uuid'] for c in cubes],
            })
            elements.extend(cubes)
        for outer, inner in zip(chain, chain[1:]):
            outer['children'].append(inner)
        bones.append(chain[0])
        tendril['bones'] = tuple(f'{tendril["name"]}_{part}' for part in PARTS)
    root = {
        'name': 'tentacles_root', 'origin': list(ROOT_ORIGIN), 'rotation': [0.0, 0.0, 0.0],
        'color': 0, 'uuid': uid('bone:root'), 'export': True, 'mirror_uv': False,
        'isOpen': True, 'locked': False, 'visibility': True, 'autouv': 0,
        'children': bones,
    }
    return {
        'meta': {'format_version': '4.10', 'model_format': 'free', 'box_uv': False},
        'name': MODEL, 'model_identifier': MODEL, 'visible_box': [5, 5, 1],
        'resolution': {'width': 16, 'height': 16}, 'elements': elements,
        'outliner': [root], 'textures': [texture_entry],
        'animations': [build_animation(TENDRILS)],
    }, texture


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
            texture=None, body=False):
    """Small orthographic flat-shaded renderer (painter's algorithm + back-face culling).

    Bone rotations are applied, so the yaw of each blade is visible here exactly as
    it will be in game.  It stays a schematic: flat shading, no lighting model.
    """
    img = Image.new('RGB', size, (24, 28, 42))
    draw = ImageDraw.Draw(img)
    cy_, sy_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp_, sp_ = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    def rotate(x, y, z):
        """Camera sits behind the player (+Z) and looks along -Z."""
        xr = x * cy_ - z * sy_
        zr = x * sy_ + z * cy_
        yr = y * cp_ - zr * sp_
        zr = y * sp_ + zr * cp_
        return -xr, yr, zr

    def view(x, y, z):
        return rotate(x, y - 22.0, z - 10.0)

    def project(x, y, z):
        xr, yr, zr = view(x, y, z)
        return (size[0] / 2 + xr * scale, size[1] / 2 - yr * scale), zr

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
    rendered.sort(key=lambda item: item[0])

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
        draw.polygon(poly, fill=colour, outline=(70, 2, 10) if flat is None else (58, 62, 78))

    font = _font(18)
    small = _font(14)
    draw.text((12, 10), title, fill=(232, 232, 242), font=font)
    draw.text((12, 36), 'схема (плоская заливка), не игровой рендер', fill=(150, 152, 170), font=small)
    img.save(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', default=str(HERE))
    parser.add_argument('--preview', action='store_true', help='also write the schematic preview')
    args = parser.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    model, texture = build_model()
    (out / f'{MODEL}.bbmodel').write_text(json.dumps(model, ensure_ascii=False, indent=1) + '\n',
                                          encoding='utf-8')
    texture.save(out / f'{MODEL}.png')
    if args.preview:
        panel = (680, 470)
        preview(model, out / 'tentacles_back.png', title='вид со спины', yaw=0, pitch=0,
                scale=5.6, size=panel, texture=texture, body=True)
        preview(model, out / 'tentacles_angle.png', title='вид 3/4', yaw=-38, pitch=16,
                scale=5.6, size=panel, texture=texture, body=True)
        preview(model, out / 'tentacles_top.png', title='вид сверху (проверка объёма)',
                yaw=-12, pitch=76, scale=5.6, size=panel, texture=texture, body=True)
        combo = Image.new('RGB', (panel[0] * 3, panel[1]), (24, 28, 42))
        for index, name in enumerate(('tentacles_back', 'tentacles_angle', 'tentacles_top')):
            combo.paste(Image.open(out / f'{name}.png'), (panel[0] * index, 0))
        combo.save(out / 'tentacles_preview.png')
    print(f'{len(model["elements"])} cubes in {len(model["outliner"][0]["children"])} blades -> {out}')


if __name__ == '__main__':
    main()
