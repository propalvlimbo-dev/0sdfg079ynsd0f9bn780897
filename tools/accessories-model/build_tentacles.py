#!/usr/bin/env python3
"""Builds the Kaneki kagune (щупальца) blueprint + texture, pixel-art only.

The reference is a set of four organic red tendrils: thick at the root, sweeping
through big open arcs, tapering to a pointed tip with scale plates near the end.

ModelEngine 4.1.0 with Use-New-Rotation=false only accepts one rotation axis per
cube and angles that are multiples of 22.5 degrees, so every curve is built from
many short overlapping segments whose direction is snapped to 22.5 degrees (and
folded into -45..45 by swapping the box cross-section, because a box rotated by
90 degrees looks identical). That reproduces the faceted-but-smooth look of the
reference model instead of the old chunky zig-zag.

Usage:
    python3 tools/accessories-model/build_tentacles.py [--out-dir tools/accessories-model]
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
STEP = 1.75         # arc length of one segment, in 1/16 block units
SNAP = 22.5         # ModelEngine's only supported rotation step
OVERLAP = 0.78      # extra length on both ends so the joints stay closed


def uid(tag):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'elytrix-kaneki:{tag}'))


# --------------------------------------------------------------------------- curves
# Each tendril: control points (Blockbench units, +Z = away from the back) and the
# thickness (across the tendril) along it, from root to tip.
# One side is authored (positive X = the player's right), the other is mirrored.
# Each curve leaves the back, opens into a wide arc, then hooks back towards the
# body and ends in a point, like the reference art.
SIDE = [
    {
        # upper: rises over the shoulder, hooks inwards and down
        'name': 'upper',
        'points': [(0.9, 19.8, 3.6), (6.6, 22.6, 4.1), (11.8, 26.4, 4.7),
                   (14.8, 30.6, 5.4), (15.4, 34.4, 6.1), (13.6, 37.0, 6.8),
                   (10.6, 37.6, 7.4), (8.2, 35.8, 7.8), (7.4, 32.8, 8.0)],
        'width': (5.3, 1.5),
        'depth': (3.7, 1.15),
    },
    {
        # lower: sweeps down and out, then curls up with the tip turned inwards
        'name': 'lower',
        'points': [(0.7, 16.6, 4.6), (6.4, 14.4, 5.2), (12.4, 12.2, 5.9),
                   (18.6, 10.4, 6.5), (24.8, 10.2, 7.1), (28.6, 12.6, 7.7),
                   (29.2, 16.4, 8.3), (27.4, 19.6, 8.7), (24.6, 21.2, 9.0)],
        'width': (5.5, 1.6),
        'depth': (3.9, 1.2),
    },
]


def mirrored(curve):
    return [(-x, y, z + 0.6) for x, y, z in curve]


TENDRILS = []
for _side, _sign in (('right', 1.0), ('left', -1.0)):
    for _spec in SIDE:
        TENDRILS.append({
            'name': f'{_side}_{_spec["name"]}',
            'points': _spec['points'] if _sign > 0 else mirrored(_spec['points']),
            'width': _spec['width'],
            'depth': _spec['depth'],
        })


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


def segments(tendril):
    """Splits a tendril into cubes: centre, direction angle, length and position along it."""
    curve = resample(catmull_rom(tendril['points']), STEP)
    pieces = []
    count = max(1, len(curve) - 1)
    for i, (a, b) in enumerate(zip(curve, curve[1:])):
        dx, dy = b[0] - a[0], b[1] - a[1]
        snapped = round(math.degrees(math.atan2(dy, dx)) / SNAP) * SNAP
        # A box turned by 90 degrees is the same box with its length and width swapped
        # (the Z cross-section stays untouched), so any direction folds into -45..45.
        folded, turns = snapped, 0
        while folded > 45 + 1e-9:
            folded -= 90
            turns += 1
        while folded <= -45 + 1e-9:
            folded += 90
            turns += 1
        centre = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
        pieces.append({'centre': centre, 'angle': folded, 'length': math.dist(a, b),
                       't': (i + 0.5) / count, 'swap': turns % 2 == 1})
    return pieces


def lerp(profile, t):
    return profile[0] + (profile[1] - profile[0]) * (t ** 0.72)


def build_elements(tendril, part):
    """Turns one half of a tendril into Blockbench cubes with per-face UV regions."""
    elements = []
    for index, piece in enumerate(segments(tendril)):
        if (piece['t'] >= 0.5) != (part == 'b'):
            continue
        cx, cy, cz = piece['centre']
        t = piece['t']
        width = lerp(tendril['width'], t)          # across the tendril
        depth = lerp(tendril['depth'], t)          # through the tendril (Z)
        half_len = piece['length'] / 2 + OVERLAP
        if piece['swap']:
            p0 = [cx - width / 2, cy - half_len, cz - depth / 2]
            p1 = [cx + width / 2, cy + half_len, cz + depth / 2]
        else:
            p0 = [cx - half_len, cy - width / 2, cz - depth / 2]
            p1 = [cx + half_len, cy + width / 2, cz + depth / 2]
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
        elements.append({
            'name': f'{tendril["name"]}_{part}{index + 1:02d}',
            'box_uv': False, 'rescale': False, 'locked': False, 'light_emission': 0,
            'render_order': 'default', 'allow_mirror_modeling': True,
            'from': [round(v, 4) for v in p0], 'to': [round(v, 4) for v in p1],
            'autouv': 0, 'color': 0,
            'origin': [round(cx, 4), round(cy, 4), round(cz, 4)],
            'rotation': [0, 0, piece['angle']],
            'faces': faces, 'type': 'cube', 'uuid': uid(f'cube:{tendril["name"]}:{part}:{index}'),
        })
    return elements


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
def build_animation(tendrils):
    """Long, soft sway; the tip of every tendril lags behind its root."""
    length = 8.0
    frames = 33
    animators = {}
    for index, tendril in enumerate(tendrils):
        phase = index * math.pi / 2.2
        for bone_name, lag, gain in ((tendril['bones'][0], 0.0, 2.6),
                                     (tendril['bones'][1], 0.55, 1.5)):
            keys = []
            for step in range(frames):
                t = length * step / (frames - 1)
                wobble = round(gain * math.sin(2 * math.pi * t / length + phase - lag), 3)
                lean = round(0.35 * gain * math.sin(2 * math.pi * t / length + phase + 1.1 - lag), 3)
                keys.append({
                    'channel': 'rotation',
                    'data_points': [{'x': str(lean), 'y': '0', 'z': str(wobble)}],
                    'uuid': uid(f'key:{bone_name}:{step}'),
                    'time': round(t, 3), 'color': -1, 'interpolation': 'linear',
                })
            keys[-1]['data_points'] = [dict(point) for point in keys[0]['data_points']]
            animators[uid(f'bone:{bone_name}')] = {
                'name': bone_name, 'type': 'bone', 'keyframes': keys,
            }
    return {
        'uuid': uid('animation:idle'), 'name': 'idle', 'loop': 'loop', 'override': False,
        'length': length, 'snapping': 30, 'selected': True, 'anim_time_update': '',
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
        curve = resample(catmull_rom(tendril['points']), STEP)
        joint = min(curve, key=lambda p: abs(curve.index(p) / (len(curve) - 1) - 0.5))
        root_cubes = build_elements(tendril, 'a')
        tip_cubes = build_elements(tendril, 'b')
        elements.extend(root_cubes)
        elements.extend(tip_cubes)
        # Two bones per tendril: ModelEngine halves the model resolution (scaleToFit)
        # once a cube sits further than 24 units from its pivot, and a single bone
        # would exceed that on these big arcs.
        tip_bone = {
            'name': f'{tendril["name"]}_b', 'origin': [round(v, 4) for v in joint],
            'rotation': [0, 0, 0], 'color': 0, 'uuid': uid(f'bone:{tendril["name"]}_b'),
            'export': True, 'mirror_uv': False, 'isOpen': True, 'locked': False,
            'visibility': True, 'autouv': 0, 'children': [c['uuid'] for c in tip_cubes],
        }
        bones.append({
            'name': f'{tendril["name"]}_a',
            'origin': [round(v, 4) for v in tendril['points'][0]],
            'rotation': [0, 0, 0], 'color': 0, 'uuid': uid(f'bone:{tendril["name"]}_a'),
            'export': True, 'mirror_uv': False, 'isOpen': True, 'locked': False,
            'visibility': True, 'autouv': 0,
            'children': [c['uuid'] for c in root_cubes] + [tip_bone],
        })
        tendril['bones'] = (f'{tendril["name"]}_a', f'{tendril["name"]}_b')
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
def preview(model, out_path, scale=8.0, size=(620, 460), title='', yaw=-26.0, pitch=8.0, texture=None):
    """Small orthographic flat-shaded renderer (painter's algorithm + back-face culling).

    It is a schematic used to judge the silhouette and the tapering, not an
    in-game screenshot: no textures, no lighting model, no interpolation.
    """
    img = Image.new('RGB', size, (24, 28, 42))
    draw = ImageDraw.Draw(img)
    cy_, sy_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp_, sp_ = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    def rotate(x, y, z):
        xr = x * cy_ + z * sy_
        zr = -x * sy_ + z * cy_
        yr = y * cp_ - zr * sp_
        zr = y * sp_ + zr * cp_
        return xr, yr, zr

    def view(x, y, z):
        # the projection is centred on the middle of the player's back
        return rotate(x, y - 18.0, z - 6.0)

    def project(x, y, z):
        xr, yr, zr = view(x, y, z)
        return (size[0] / 2 + xr * scale, size[1] / 2 - yr * scale + 30), zr

    def cube_quads(element):
        x0, y0, z0 = element['from']
        x1, y1, z1 = element['to']
        angle = math.radians(element['rotation'][2])
        ox, oy, _ = element['origin']
        ca, sa = math.cos(angle), math.sin(angle)

        def rot(x, y):
            dx, dy = x - ox, y - oy
            return (ox + dx * ca - dy * sa, oy + dx * sa + dy * ca)

        corners = {(i, j): rot(x0 if i == 0 else x1, y0 if j == 0 else y1) for i in (0, 1) for j in (0, 1)}
        faces = []
        for zz in (z0, z1):
            faces.append(((corners[(0, 0)], corners[(1, 0)], corners[(1, 1)], corners[(0, 1)]), zz))
        for i in (0, 1):
            faces.append((((corners[(i, 0)], corners[(i, 1)]), (corners[(i, 1)], corners[(i, 0)])), None))
        return corners, faces

    quads = []
    for element in model['elements']:
        x0, y0, z0 = element['from']
        x1, y1, z1 = element['to']
        angle = math.radians(element['rotation'][2])
        ox, oy, _ = element['origin']
        ca, sa = math.cos(angle), math.sin(angle)

        def rot(x, y):
            dx, dy = x - ox, y - oy
            return (ox + dx * ca - dy * sa, oy + dx * sa + dy * ca)

        p = {(i, j, k): rot(x0 if i == 0 else x1, y0 if j == 0 else y1) + (z0 if k == 0 else z1,)
             for i in (0, 1) for j in (0, 1) for k in (0, 1)}
        sides = [
            ([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], (0, 0, -1)),   # front
            ([(0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1)], (0, 0, 1)),    # back
            ([(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)], (0, 1, 0)),   # top
            ([(0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)], (0, -1, 0)),  # bottom
            ([(1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)], (1, 0, 0)),   # right
            ([(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)], (-1, 0, 0)),  # left
        ]
        for keys, normal in sides:
            pts = [p[k] for k in keys]
            face_name = {0: 'north', 1: 'south', 2: 'up', 3: 'down', 4: 'east', 5: 'west'}[len(quads) % 6]
            uv = element['faces'][face_name]['uv']
            quads.append((pts, normal, uv))

    def normal_view(n, angle):
        ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        nx, ny, nz = n[0] * ca - n[1] * sa, n[0] * sa + n[1] * ca, n[2]
        return nx, ny, nz

    rendered = []
    for index, (pts, normal, uv) in enumerate(quads):
        element = model['elements'][index // 6]
        nx, ny, nz = normal_view(normal, element['rotation'][2])
        vx, vy, vz = rotate(nx, ny, nz)   # normals are directions: no translation
        projected = [project(*pt) for pt in pts]
        depth = sum(d for _, d in projected) / len(projected)
        centre = (sum(p[0] for p in pts) / 4, sum(p[1] for p in pts) / 4, sum(p[2] for p in pts) / 4)
        rendered.append((depth, [q for q, _ in projected], (vx, vy, vz), uv, centre))
    rendered.sort(key=lambda item: item[0])

    for _, poly, n, uv, centre in rendered:
        if n[2] >= 0:
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
        preview(model, out / 'tentacles_back.png', title='вид сзади', yaw=0, pitch=0,
                scale=7.4, size=(520, 430), texture=texture)
        preview(model, out / 'tentacles_angle.png', title='вид 3/4', yaw=-32, pitch=14,
                scale=7.4, size=(520, 430), texture=texture)
        combo = Image.new('RGB', (1040, 430), (24, 28, 42))
        combo.paste(Image.open(out / 'tentacles_back.png'), (0, 0))
        combo.paste(Image.open(out / 'tentacles_angle.png'), (520, 0))
        combo.save(out / 'tentacles_preview.png')
    print(f'{len(model["elements"])} cubes in {len(model["outliner"][0]["children"])} tendrils -> {out}')


if __name__ == '__main__':
    main()
