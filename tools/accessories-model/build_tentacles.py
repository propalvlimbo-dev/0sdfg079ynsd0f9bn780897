#!/usr/bin/env python3
"""Builds the Kaneki kagune (щупальца) blueprint + texture, pixel-art only.

v4. The reference is four organic red tendrils that burst out of the back: thick at
the root, sweeping through big open 3-D arcs (up, outward *and* backwards), tapering
to a pointed tip with scale plates near the end.

Why the model is built this way
-------------------------------
* Every tendril is a real 3-D curve (Catmull-Rom through 3-D control points), so the
  group never collapses into a flat "cardboard fan" when seen from above or from the
  side.  The previous revision kept dz nearly constant, which is exactly why the
  in-game result read as one level bar.
* ModelEngine 4.1.0 writes one rotation per cube (axis + any angle, and for 1.21.4
  item models the rotation is preserved as `{"origin":..,"angle":..,"axis":..}`).
  A cube can therefore only be tilted inside the plane that is perpendicular to the
  chosen axis.  For every segment we pick the axis with the *smallest* direction
  component, so the segment lies almost exactly in that plane and the long axis of
  the box follows the curve tangent.
* Each tendril is a chain of three bones instead of two: it keeps every cube within
  scaleToFit()'s 24-unit limit (a bigger distance silently halves that bone) and it
  gives the animation nine joints per side to move.

Usage:
    python3 tools/accessories-model/build_tentacles.py [--out-dir tools/accessories-model] [--preview]
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
STEP = 2.0          # arc length of one segment, in 1/16 block units
OVERLAP = 0.75      # extra length on both ends so the joints stay closed
PARTS = ('a', 'b', 'c', 'd')

# --------------------------------------------------------------------------- curves
# Blockbench units: +X = the player's right, +Y = up, +Z = behind the back.
# The four tendrils are deliberately NOT mirror images of each other: different
# height, different reach, different depth and a different tip, which is what makes
# the group read as organic instead of as a symmetric cardboard cut-out.
def sweep(root, heading, pitch, yaw_rate, pitch_rate, length, steps=6):
    """Control points of a crescent: march forward while the tangent keeps turning.

    `heading` is the direction in the XZ plane (0 = +X/right, 90 = +Z/behind),
    `pitch` is the climb angle, the two rates bend the curve per unit of length.
    """
    points = [root]
    x, y, z = root
    step = length / steps
    h, p = heading, pitch
    for _ in range(steps):
        ch, sh = math.cos(math.radians(h)), math.sin(math.radians(h))
        cp = math.cos(math.radians(p))
        x += cp * ch * step
        y += math.sin(math.radians(p)) * step
        z += cp * sh * step
        points.append((round(x, 2), round(y, 2), round(z, 2)))
        h += yaw_rate * step
        p += pitch_rate * step
    return points


SIDE = [
    {
        # right upper: the longest blade, climbs gently out of the shoulder blade
        # and ends in the point that sits above the shoulder in the reference
        'name': 'right_upper',
        'points': sweep((1.4, 19.0, 2.2), heading=22, pitch=8,
                        yaw_rate=0.60, pitch_rate=0.38, length=46),
        'width': (9.2, 1.05),
    },
    {
        # right lower: leaves the hip a little downward, then curls back upward -
        # the opposite curvature to the upper one, so the pair is never level
        'name': 'right_lower',
        'points': sweep((1.6, 15.4, 3.4), heading=24, pitch=-4,
                        yaw_rate=0.52, pitch_rate=0.55, length=42),
        'width': (8.6, 1.0),
    },
    {
        # left upper: starts higher and stays flat, swings further behind the player
        'name': 'left_upper',
        'points': sweep((-1.2, 21.0, 4.4), heading=152, pitch=5,
                        yaw_rate=-0.58, pitch_rate=0.18, length=39),
        'width': (8.8, 1.1),
    },
    {
        # left lower: the shortest blade, dips the deepest and flicks up at the tip
        'name': 'left_lower',
        'points': sweep((-1.6, 13.6, 5.2), heading=148, pitch=-8,
                        yaw_rate=-0.52, pitch_rate=0.60, length=32),
        'width': (8.0, 1.0),
    },
]

TENDRILS = [dict(spec) for spec in SIDE]


def uid(tag):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'elytrix-kaneki:{tag}'))


def catmull_rom(points, samples_per_span=24):
    """Centripetal-ish Catmull-Rom through the control points (padded at both ends)."""
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(len(pts) - 3):
        p0, p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        for s in range(samples_per_span):
            t = s / samples_per_span
            t2, t3 = t * t, t * t * t
            out.append(tuple(
                0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t
                       + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                       + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3)
                for k in range(3)))
    out.append(pts[-2])
    return out


def resample(curve, step):
    """Uniform arc-length resampling."""
    lengths = [0.0]
    for a, b in zip(curve, curve[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    total = lengths[-1]
    count = max(2, int(round(total / step)))
    result = []
    for i in range(count):
        target = total * i / (count - 1)
        j = 0
        while j < len(lengths) - 2 and lengths[j + 1] < target:
            j += 1
        span = lengths[j + 1] - lengths[j] or 1.0
        t = (target - lengths[j]) / span
        result.append(tuple(curve[j][k] + (curve[j + 1][k] - curve[j][k]) * t for k in range(3)))
    return result


def _unit(vec):
    length = math.sqrt(sum(v * v for v in vec)) or 1.0
    return tuple(v / length for v in vec)


def segments(tendril):
    """Splits a tendril into cubes: centre, 3-D direction and segment length."""
    curve = resample(catmull_rom(tendril['points']), STEP)
    pieces = []
    count = max(1, len(curve) - 1)
    for i, (a, b) in enumerate(zip(curve, curve[1:])):
        direction = _unit(tuple(b[k] - a[k] for k in range(3)))
        pieces.append({
            'centre': tuple((a[k] + b[k]) / 2 for k in range(3)),
            'direction': direction,
            'length': math.dist(a, b), 't': (i + 0.5) / count,
            'start': a, 'end': b,
        })
    return pieces


def tilt_axis(pieces):
    """One tilt axis for a whole bone.

    A cube can only be rotated around one axis, and its long side has to stay
    perpendicular to it, so the bone uses the axis its segments cross the least.
    Keeping a single axis per bone also avoids ModelEngine splitting a bone into
    several item models.
    """
    def error(axis):
        return sum(abs(p['direction'][axis]) for p in pieces)
    return min(range(3), key=error)


def _tilt(axis, direction):
    """Angle (degrees) and long axis of the box for a segment inside `axis`' plane."""
    if axis == 2:            # tilt around Z, box runs along X
        return math.degrees(math.atan2(direction[1], direction[0])), 0
    if axis == 1:            # tilt around Y, box runs along X
        return math.degrees(math.atan2(-direction[2], direction[0])), 0
    return math.degrees(math.atan2(direction[2], direction[1])), 1     # around X, along Y


def lerp(profile, t):
    """Blade profile: stays broad for the first half, then runs out into a point."""
    root, tip = profile
    body = root * (1.0 - 0.35 * min(t, 0.55))
    if t <= 0.55:
        return body
    k = (t - 0.55) / 0.45
    return tip + (body - tip) * (1.0 - k ** 1.6)


def build_elements(tendril, part):
    """Turns one third of a tendril into Blockbench cubes with per-face UV regions."""
    elements = []
    pieces = segments(tendril)
    bounds = bone_ranges(len(pieces), len(PARTS))
    index_of_part = PARTS.index(part)
    low, high = bounds[index_of_part]
    axis = tilt_axis(pieces[low:high])
    for index, piece in enumerate(pieces):
        if not low <= index < high:
            continue
        t = piece['t']
        width = lerp(tendril['width'], t)          # across the tendril
        depth = width * 0.85                       # through it (thick blade)
        angle, long_axis = _tilt(axis, piece['direction'])
        # ModelEngine 4.1.0 only accepts one rotation axis per cube and, more
        # importantly, it snaps/combinates anything else through RotationSolver -
        # which throws on 4.1.0. Multiples of 22.5 are legal, so snap to them.
        angle = round(angle / 22.5) * 22.5
        while angle > 90.0:
            angle -= 180.0
        while angle <= -90.0:
            angle += 180.0
        centre = piece['centre']
        half = piece['length'] / 2 + OVERLAP
        cross = [k for k in range(3) if k not in (long_axis, axis)][0]
        p0, p1 = list(centre), list(centre)
        p0[long_axis] -= half
        p1[long_axis] += half
        p0[cross] -= width / 2
        p1[cross] += width / 2
        p0[axis] -= depth / 2
        p1[axis] += depth / 2
        # near the tip the faces switch to the scale-plate texture region
        body = 'scales' if t > 0.78 else 'body'
        faces = {
            'up': {'uv': uv_rect('top'), 'texture': 0},
            'down': {'uv': uv_rect('dark'), 'texture': 0},
            'east': {'uv': uv_rect(body), 'texture': 0},
            'west': {'uv': uv_rect(body), 'texture': 0},
            'north': {'uv': uv_rect(body), 'texture': 0},
            'south': {'uv': uv_rect(body), 'texture': 0},
        }
        rotation = [0, 0, 0]
        rotation[axis] = round(angle, 3)
        elements.append({
            'name': f'{tendril["name"]}_{part}{index + 1:02d}',
            'box_uv': False, 'rescale': False, 'locked': False, 'light_emission': 0,
            'render_order': 'default', 'allow_mirror_modeling': True,
            'from': [round(v, 4) for v in p0], 'to': [round(v, 4) for v in p1],
            'autouv': 0, 'color': 0,
            'origin': [round(v, 4) for v in centre],
            'rotation': rotation,
            'faces': faces, 'type': 'cube', 'uuid': uid(f'cube:{tendril["name"]}:{index}'),
        })
    return elements


def bone_ranges(count, parts):
    """Splits `count` segments into `parts` contiguous, non-empty groups."""
    bounds = []
    for part in range(parts):
        low = round(count * part / parts)
        high = round(count * (part + 1) / parts)
        bounds.append((low, max(high, low + 1)))
    return bounds


# UV layout inside the 0..16 space of a vanilla-mapped texture (64x64 -> 4px per unit)
UV_REGIONS = {
    'body': [0.0, 0.0, 8.0, 8.0],
    'scales': [8.0, 0.0, 16.0, 8.0],
    'top': [0.0, 8.0, 8.0, 16.0],
    'dark': [8.0, 8.0, 16.0, 16.0],
}


def uv_rect(region):
    return list(UV_REGIONS[region])


# --------------------------------------------------------------------------- texture
def build_texture():
    """Glossy crimson kagune skin, drawn pixel by pixel (no AI, no external images).

    ItemDisplay entities in Minecraft are lit flatly, so the volume is baked into
    the texture: the top face uses a bright tile, the sides a mid crimson tile and
    the underside a dark maroon tile. That is what makes the tendril read as a
    rounded limb instead of a flat ribbon.
    """
    size = 64
    img = Image.new('RGBA', (size, size), (120, 6, 16, 255))
    px = img.load()

    def tile(x0, y0, x1, y1, colour, grain):
        for y in range(y0, y1):
            for x in range(x0, x1):
                n = (math.sin(x * 0.9 + y * 1.7) * 0.5 + math.sin(x * 0.31 - y * 0.73) * 0.5) * grain
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
# per bone of the chain: (gain, lag, axis mix) - the tip moves the most and lags
BONE_MOTION = (
    (2.6, 0.00, (0.55, 0.45)),
    (5.0, 0.12, (0.35, 0.65)),
    (8.4, 0.22, (0.70, 0.30)),
    (12.0, 0.34, (0.45, 0.55)),
)


def build_animation(tendrils):
    """Lively idle: every joint swings on two axes, the tip lags behind its root."""
    animators = {}
    for index, tendril in enumerate(tendrils):
        phase = index * math.pi / 2.4
        for depth, (bone_name, (gain, lag, mix)) in enumerate(zip(tendril['bones'], BONE_MOTION)):
            keys = []
            for step in range(ANIM_FRAMES):
                t = ANIM_LENGTH * step / (ANIM_FRAMES - 1)
                swing = 2 * math.pi * t / ANIM_LENGTH
                primary = gain * (math.sin(swing + phase - lag * 6.0)
                                  + 0.35 * math.sin(2.0 * swing + phase * 1.7))
                secondary = gain * 0.75 * math.cos(swing * 0.75 + phase * 1.3 - lag * 4.0)
                keys.append({
                    'channel': 'rotation',
                    'data_points': [{
                        'x': str(round(primary * mix[0], 3)),
                        'y': '0',
                        'z': str(round(secondary * mix[1], 3)),
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
        pieces = segments(tendril)
        bounds = bone_ranges(len(pieces), len(PARTS))
        chain = []
        for part_index, part in enumerate(PARTS):
            low, _ = bounds[part_index]
            origin = pieces[low]['start']
            chain.append({
                'name': f'{tendril["name"]}_{part}',
                'origin': [round(v, 4) for v in origin],
                'rotation': [0, 0, 0], 'color': part_index, 'uuid': uid(f'bone:{tendril["name"]}_{part}'),
                'export': True, 'mirror_uv': False, 'isOpen': True, 'locked': False,
                'visibility': True, 'autouv': 0,
                'children': [c['uuid'] for c in build_elements(tendril, part)],
            })
            elements.extend(build_elements(tendril, part))
        for upper, lower in zip(chain, chain[1:]):
            upper['children'].append(lower)
        bones.append(chain[0])
        tendril['bones'] = tuple(f'{tendril["name"]}_{part}' for part in PARTS)
    root = {
        'name': 'tentacles_root', 'origin': list(ROOT_ORIGIN), 'rotation': [0, 0, 0],
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


def preview(model, out_path, scale=8.0, size=(620, 460), title='', yaw=-26.0, pitch=8.0, texture=None):
    """Small orthographic flat-shaded renderer (painter's algorithm + back-face culling).

    It is a schematic used to judge the silhouette and the tapering, not an
    in-game screenshot: no textures, no lighting model, no interpolation.  All three
    rotation axes are honoured, so what you see is what the resource pack contains.
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
        # the projection is centred between the shoulder blades and the tips
        return rotate(x, y - 25.0, z - 12.0)

    def project(x, y, z):
        xr, yr, zr = view(x, y, z)
        return (size[0] / 2 + xr * scale, size[1] / 2 - yr * scale), zr

    quads = []
    for element in model['elements']:
        axis, angle = 2, 0.0
        for k in range(3):
            if element['rotation'][k]:
                axis, angle = k, element['rotation'][k]
        matrix = _rotation(axis, angle)
        origin = element['origin']
        corner = {}
        for i in (0, 1):
            for j in (0, 1):
                for k in (0, 1):
                    local = (element['from'][0] if i == 0 else element['to'][0],
                             element['from'][1] if j == 0 else element['to'][1],
                             element['from'][2] if k == 0 else element['to'][2])
                    rel = _apply(matrix, tuple(local[n] - origin[n] for n in range(3)))
                    corner[(i, j, k)] = tuple(origin[n] + rel[n] for n in range(3))
        sides = [
            ([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], (0, 0, -1), 'north'),
            ([(0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1)], (0, 0, 1), 'south'),
            ([(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)], (0, 1, 0), 'up'),
            ([(0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)], (0, -1, 0), 'down'),
            ([(1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)], (1, 0, 0), 'east'),
            ([(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)], (-1, 0, 0), 'west'),
        ]
        for keys, normal, face_name in sides:
            pts = [corner[k] for k in keys]
            quads.append((pts, _apply(matrix, normal), element['faces'][face_name]['uv']))

    rendered = []
    for pts, normal, uv in quads:
        vx, vy, vz = rotate(*normal)          # normals are directions: no translation
        projected = [project(*pt) for pt in pts]
        depth = sum(d for _, d in projected) / len(projected)
        rendered.append((depth, [q for q, _ in projected], (vx, vy, vz), uv))
    rendered.sort(key=lambda item: item[0])

    for _, poly, n, uv in rendered:
        if n[2] <= 0:
            continue
        if texture is not None:
            # average colour of the 16x16 texel patch of this face
            u0, v0, u1, v1 = uv
            box = texture.crop((int(u0 * 4), int(v0 * 4), int(u1 * 4), int(v1 * 4))).convert('RGB')
            patch = list(box.getdata())
            colour = tuple(sum(px[i] for px in patch) // len(patch) for i in range(3))
        else:
            light = max(0.0, -(n[0] * -0.42 + n[1] * 0.58 + n[2] * -0.7))
            shade = 0.46 + 0.78 * light
            colour = (min(255, int(206 * shade)), min(255, int(28 * shade)), min(255, int(36 * shade)))
        draw.polygon(poly, fill=colour, outline=(70, 2, 10))

    draw.text((10, 10), title, fill=(232, 232, 242))
    draw.text((10, 26), 'schematic preview (flat shading), not an in-game render', fill=(150, 152, 170))
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
                scale=6.4, size=panel, texture=texture)
        preview(model, out / 'tentacles_angle.png', title='вид 3/4', yaw=-38, pitch=16,
                scale=6.4, size=panel, texture=texture)
        preview(model, out / 'tentacles_top.png', title='вид сверху (проверка объёма)',
                yaw=-12, pitch=76, scale=6.4, size=panel, texture=texture)
        combo = Image.new('RGB', (panel[0] * 3, panel[1]), (24, 28, 42))
        for index, name in enumerate(('tentacles_back', 'tentacles_angle', 'tentacles_top')):
            combo.paste(Image.open(out / f'{name}.png'), (panel[0] * index, 0))
        combo.save(out / 'tentacles_preview.png')
    print(f'{len(model["elements"])} cubes in {len(model["outliner"][0]["children"])} tendrils -> {out}')


if __name__ == '__main__':
    main()
