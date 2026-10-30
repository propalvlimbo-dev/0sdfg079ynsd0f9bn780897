#!/usr/bin/env python3
"""Draws the Kaneki eyepatch as a *vanilla head equipment layer*.

Why this exists
---------------
The ModelEngine version of the patch was a separate display entity riding the
player.  Such an entity is drawn for every viewer, including the wearer, so the
patch sat right in front of the first-person camera and at the same time its
rotation had to be copied from the server every tick.  A head equipment layer
is rendered by the client as part of the player model itself:

  * it is hidden in first person automatically (the client never draws your own
    head there) and visible in F5;
  * it follows the head bone, including looking up/down, with zero latency;
  * it is identical for every viewer, so nothing can desync.

Layout: vanilla humanoid armour texture, 64x32, standard skin UVs.
    top      ( 8, 0)-(16, 8)      bottom   (16, 0)-(24, 8)
    right    ( 0, 8)-( 8,16)      front    ( 8, 8)-(16,16)
    left     (16, 8)-(24,16)      back     (24, 8)-(32,16)

The front panel is drawn as seen from outside, so its left edge is the player's
right cheek and its right edge is the player's left cheek - the patch therefore
lives in columns 12..15 of the front panel (Kaneki wears it over the left eye).

Usage: python3 tools/accessories-model/build_eyepatch_equipment.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
TEX = ASSETS / "reallyworld/textures/entity/equipment/humanoid/kaneki_eyepatch.png"
JSON = ASSETS / "reallyworld/equipment/kaneki_eyepatch.json"
PREVIEW = HERE / "eyepatch_equipment_preview.png"

CLOTH = (241, 236, 225, 255)
CLOTH_HI = (252, 249, 243, 255)
CLOTH_SHADE = (218, 210, 196, 255)
CLOTH_SEAM = (199, 190, 174, 255)
STRAP = (198, 188, 170, 255)
STRAP_DARK = (164, 154, 136, 255)
KNOT = (222, 214, 200, 255)

FACES = {
    "top": (8, 0),
    "bottom": (16, 0),
    "right": (0, 8),
    "front": (8, 8),
    "left": (16, 8),
    "back": (24, 8),
}


def face_px(face, i, j):
    """Texture pixel of a head face; i grows left->right in the texture."""
    ox, oy = FACES[face]
    return ox + i, oy + j


def build_texture():
    img = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def put(face, i, j, color):
        x, y = face_px(face, i, j)
        d.point((x, y), color)

    # --- strap: one pixel tall around the sides and the back ---------------
    # Kaneki's strap runs through the hair at the front, so the face itself only
    # gets a two pixel stub that disappears behind the patch: drawing it across
    # the whole face would put a band over the healthy eye.
    for face in ("right", "left", "back"):
        for i in range(8):
            put(face, i, 3, STRAP)
    for i in range(0, 4):
        put("front", i, 3, STRAP)

    # --- the patch itself: 4x5 over the player's left eye ------------------
    for i in range(4, 8):
        for j in range(1, 6):
            put("front", i, j, CLOTH)
    for i, j in ((4, 1), (7, 1), (4, 5), (7, 5)):
        put("front", i, j, (0, 0, 0, 0))          # rounded corners, not a sticker
    for i in (5, 6):
        put("front", i, 1, CLOTH_HI)              # lit top edge
        put("front", i, 5, CLOTH_SHADE)           # shaded hem
    for j in (2, 3, 4):
        put("front", 4, j, CLOTH_SEAM)            # seam towards the nose
        put("front", 7, j, CLOTH_SHADE)           # soft edge towards the ear
    put("front", 6, 2, CLOTH_HI)                  # one quiet highlight, no stripes

    # --- knot at the back of the head, with two short ends -----------------
    for i in (5, 6):
        put("back", i, 3, KNOT)
    put("back", 5, 4, KNOT)
    put("back", 6, 4, STRAP_DARK)
    put("back", 5, 5, STRAP)
    put("back", 6, 5, STRAP_DARK)
    put("back", 6, 6, STRAP_DARK)

    path = TEX
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return img


def build_json():
    JSON.parent.mkdir(parents=True, exist_ok=True)
    JSON.write_text(
        '{\n  "layers": {\n    "humanoid": [\n      {\n'
        '        "texture": "reallyworld:kaneki_eyepatch"\n'
        '      }\n    ]\n  }\n}\n',
        encoding="utf-8",
    )


def preview(tex):
    """Front + left-side + back mock of the head cube, so the art can be checked."""
    scale = 16
    gap = 8
    w = 8 * scale
    img = Image.new("RGBA", (w * 3 + gap * 2, w + 16), (24, 24, 28, 255))
    d = ImageDraw.Draw(img)
    for n, face in enumerate(("front", "left", "back")):
        ox, oy = FACES[face]
        face_img = tex.crop((ox, oy, ox + 8, oy + 8)).resize((w, w), Image.NEAREST)
        base = Image.new("RGBA", (w, w), (128, 96, 76, 255))   # a plain skin tint
        base.alpha_composite(face_img)
        img.alpha_composite(base, (n * (w + gap), 16))
        d.text((n * (w + gap) + 4, 2), ("перед / левый бок / затылок".split(" / "))[n],
               fill=(230, 230, 230, 255))
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    img.save(PREVIEW)


def main():
    tex = build_texture()
    build_json()
    preview(tex)
    print("texture:", TEX.relative_to(HERE.parents[1]))
    print("json   :", JSON.relative_to(HERE.parents[1]))
    print("preview:", PREVIEW.relative_to(HERE.parents[1]))


if __name__ == "__main__":
    main()
