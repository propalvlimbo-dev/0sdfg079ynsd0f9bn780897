#!/usr/bin/env python3
"""First-person camera-proximity hide shaders & item marker tints for Elytrix-RP-1.21.zip.

How it works:
  * Worn cosmetic accessories carry a constant near-white RGB marker tint in their
    ModelEngine bone item definitions (``assets/modelengine/items/<model>/<bone>.json``):
      - Close-body accessories (``elytrix_kaneki_tentacles``, ``elytrix_centipede``,
        ``elytrix_angel_halo``): ``-196867`` (``0xFFFCFEFD`` -> ``RGB(252, 254, 253)``)
        -> hidden within ``1.85`` blocks of the camera eye.
      - Wide-wingspan accessory (``elytrix_angel_wings``): ``-197122``
        (``0xFFFCFDFE`` -> ``RGB(252, 253, 254)``)
        -> hidden within ``2.85`` blocks of the camera eye.
  * In both ``core/entity.{vsh,fsh}`` and ``core/rendertype_item_entity_translucent_cull.{vsh,fsh}``
    (plus ``rendertype_entity_translucent.{vsh,fsh}`` for <= 1.21.4), when perspective
    world projection is active (``abs(ProjMat[2][3]) > 1e-4``, never matching 2D GUI),
    matching marker vertices restore pure ``vec4(1.0, 1.0, 1.0, Color.a)`` before lighting
    and pass ``elytrixHideRadius`` + camera-space eye distance ``elytrixEyeDist`` to the
    fragment shader, which ``discard``s fragments inside ``elytrixHideRadius``.
  * Result:
      - Wearer in 1st-person (eye distance ``0.15m - 1.55m`` / ``<= 2.70m`` for wings):
        100% hidden — zero visual obstruction!
      - Wearer in F5 3rd-person (camera distance ``3.45m - 4.80m``): 100% visible!
      - All other players viewing the wearer: 100% visible!
"""
import json
import re

CLOSE_TINT_VALUE = -196867   # 0xFFFCFEFD -> RGB(252, 254, 253), hide < 1.85m
WINGS_TINT_VALUE = -197122   # 0xFFFCFDFE -> RGB(252, 253, 254), hide < 2.85m

CLOSE_ACCESSORY_MODELS = (
    'elytrix_kaneki_tentacles',
    'elytrix_centipede',
    'elytrix_angel_halo',
    'elytrix_mini_me',
    'elytrix_cute_kitten',
    'elytrix_mellstroy',
    'elytrix_lightning_hat',
    'elytrix_satan_circle',
    # Аура бабочек — маленькая и компактная: бабочки кружат на радиусе 12.0..13.6 BB
    # и на высотах 2..33 BB, поэтому максимум ~1.1 м от глаз и она СПОКОЙНО влезает
    # в ближнюю отсечку 1.85 м. Это лучше «крыльевой»: бабочки остаются видны другим
    # игрокам, которые стоят ближе 2.85 м, а владельцу всё равно не видны от 1-го лица.
    'elytrix_butterfly_aura',
)
WINGS_ACCESSORY_MODELS = (
    'elytrix_angel_wings',
    'elytrix_zeus_wings',
    # Аура сердечек — это столб высотой 2.3 блока ВОКРУГ игрока (кольцо вынесено за руки,
    # R = 11.4..13.2 BB), поэтому по тем же причинам, что и крылья, она не влезает
    # в отсечку 1.85 м ближнего тинта и использует «крыльевую» отсечку 2.85 м.
    'elytrix_heart_aura',
)

SODIUM_IGNORED_SHADERS = [
    'entity.vsh',
    'entity.fsh',
    'rendertype_item_entity_translucent_cull.vsh',
    'rendertype_item_entity_translucent_cull.fsh',
    'rendertype_entity_translucent.vsh',
    'rendertype_entity_translucent.fsh',
]

VSH_DECL = """out float elytrixHideRadius;
out float elytrixEyeDist;
"""

VSH_INIT = """    ivec3 elytrixTint = ivec3(Color.rgb * 255.0 + 0.5);
    vec4 baseColor = Color;
    elytrixHideRadius = 0.0;
    if (abs(ProjMat[2][3]) > 1e-4) {
        if (elytrixTint == ivec3(252, 254, 253)) {
            elytrixHideRadius = 1.85;
            baseColor = vec4(1.0, 1.0, 1.0, Color.a);
        } else if (elytrixTint == ivec3(252, 253, 254)) {
            elytrixHideRadius = 2.85;
            baseColor = vec4(1.0, 1.0, 1.0, Color.a);
        }
    }
    elytrixEyeDist = length((ModelViewMat * vec4(Position, 1.0)).xyz);
"""

FSH_DECL = """in float elytrixHideRadius;
in float elytrixEyeDist;
"""

FSH_DISCARD = """    if (elytrixHideRadius > 0.0 && elytrixEyeDist < elytrixHideRadius) {
        discard;
    }
"""

# ---------------------------------------------------------------------------
# 1. <= 1.21.1 (root assets/minecraft/shaders/core/)
# ---------------------------------------------------------------------------
ITEM_ENTITY_VSH_1_21_1 = f"""#version 150

#moj_import <light.glsl>
#moj_import <fog.glsl>

in vec3 Position;
in vec4 Color;
in vec2 UV0;
in vec2 UV1;
in ivec2 UV2;
in vec3 Normal;

uniform sampler2D Sampler2;

uniform mat4 ModelViewMat;
uniform mat4 ProjMat;
uniform int FogShape;

uniform vec3 Light0_Direction;
uniform vec3 Light1_Direction;

out float vertexDistance;
out vec4 vertexColor;
out vec2 texCoord0;
out vec2 texCoord1;
{VSH_DECL}
void main() {{
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);
{VSH_INIT}
    vertexDistance = fog_distance(Position, FogShape);
    vertexColor = minecraft_mix_light(Light0_Direction, Light1_Direction, Normal, baseColor) * texelFetch(Sampler2, UV2 / 16, 0);
    texCoord0 = UV0;
    texCoord1 = UV1;
}}
"""

ITEM_ENTITY_FSH_1_21_1 = f"""#version 150

#moj_import <fog.glsl>

uniform sampler2D Sampler0;

uniform vec4 ColorModulator;
uniform float FogStart;
uniform float FogEnd;
uniform vec4 FogColor;

in float vertexDistance;
in vec4 vertexColor;
in vec2 texCoord0;
in vec2 texCoord1;
{FSH_DECL}
out vec4 fragColor;

void main() {{
{FSH_DISCARD}    vec4 color = texture(Sampler0, texCoord0) * vertexColor * ColorModulator;
    if (color.a < 0.1) {{
        discard;
    }}
    fragColor = linear_fog(color, vertexDistance, FogStart, FogEnd, FogColor);
}}
"""

# ---------------------------------------------------------------------------
# 2. 1.21.2 - 1.21.5 (1_21_2/assets/minecraft/shaders/core/, formats 36..62)
# ---------------------------------------------------------------------------
ENTITY_VSH_1_21_2 = f"""#version 150

#moj_import <minecraft:light.glsl>
#moj_import <minecraft:fog.glsl>

in vec3 Position;
in vec4 Color;
in vec2 UV0;
in ivec2 UV1;
in ivec2 UV2;
in vec3 Normal;

#ifndef EMISSIVE
uniform sampler2D Sampler2;
#endif
#ifndef NO_OVERLAY
uniform sampler2D Sampler1;
#endif

uniform mat4 ModelViewMat;
uniform mat4 ProjMat;
uniform mat4 TextureMat;
uniform int FogShape;

uniform vec3 Light0_Direction;
uniform vec3 Light1_Direction;

out float vertexDistance;
out vec4 vertexColor;
out vec4 lightMapColor;
out vec4 overlayColor;
out vec2 texCoord0;
{VSH_DECL}
void main() {{
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);
{VSH_INIT}
    vertexDistance = fog_distance(Position, FogShape);
#ifdef NO_CARDINAL_LIGHTING
    vertexColor = baseColor;
#else
    vertexColor = minecraft_mix_light(Light0_Direction, Light1_Direction, Normal, baseColor);
#endif
    lightMapColor = vec4(1.0);
#ifndef EMISSIVE
    lightMapColor = texelFetch(Sampler2, UV2 / 16, 0);
#endif
    overlayColor = vec4(0.0, 0.0, 0.0, 1.0);
#ifndef NO_OVERLAY
    overlayColor = texelFetch(Sampler1, UV1, 0);
#endif

    texCoord0 = UV0;
#ifdef APPLY_TEXTURE_MATRIX
    texCoord0 = (TextureMat * vec4(UV0, 0.0, 1.0)).xy;
#endif
}}
"""

ENTITY_FSH_1_21_2 = f"""#version 150

#moj_import <minecraft:fog.glsl>

uniform sampler2D Sampler0;

uniform vec4 ColorModulator;
uniform float FogStart;
uniform float FogEnd;
uniform vec4 FogColor;

in float vertexDistance;
in vec4 vertexColor;
in vec4 lightMapColor;
in vec4 overlayColor;
in vec2 texCoord0;
{FSH_DECL}
out vec4 fragColor;

void main() {{
{FSH_DISCARD}    vec4 color = texture(Sampler0, texCoord0);
#ifdef ALPHA_CUTOUT
    if (color.a < ALPHA_CUTOUT) {{
        discard;
    }}
#endif
    color *= vertexColor * ColorModulator;
#ifndef NO_OVERLAY
    color.rgb = mix(overlayColor.rgb, color.rgb, overlayColor.a);
#endif
#ifndef EMISSIVE
    color *= lightMapColor;
#endif
    fragColor = linear_fog(color, vertexDistance, FogStart, FogEnd, FogColor);
}}
"""

ITEM_ENTITY_VSH_1_21_2 = f"""#version 150

#moj_import <minecraft:light.glsl>
#moj_import <minecraft:fog.glsl>

in vec3 Position;
in vec4 Color;
in vec2 UV0;
in vec2 UV1;
in ivec2 UV2;
in vec3 Normal;

uniform sampler2D Sampler2;

uniform mat4 ModelViewMat;
uniform mat4 ProjMat;
uniform int FogShape;

uniform vec3 Light0_Direction;
uniform vec3 Light1_Direction;

out float vertexDistance;
out vec4 vertexColor;
out vec2 texCoord0;
out vec2 texCoord1;
{VSH_DECL}
void main() {{
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);
{VSH_INIT}
    vertexDistance = fog_distance(Position, FogShape);
    vertexColor = minecraft_mix_light(Light0_Direction, Light1_Direction, Normal, baseColor) * texelFetch(Sampler2, UV2 / 16, 0);
    texCoord0 = UV0;
    texCoord1 = UV1;
}}
"""

ITEM_ENTITY_FSH_1_21_2 = f"""#version 150

#moj_import <minecraft:fog.glsl>

uniform sampler2D Sampler0;

uniform vec4 ColorModulator;
uniform float FogStart;
uniform float FogEnd;
uniform vec4 FogColor;

in float vertexDistance;
in vec4 vertexColor;
in vec2 texCoord0;
in vec2 texCoord1;
{FSH_DECL}
out vec4 fragColor;

void main() {{
{FSH_DISCARD}    vec4 color = texture(Sampler0, texCoord0) * vertexColor * ColorModulator;
    if (color.a < 0.1) {{
        discard;
    }}
    fragColor = linear_fog(color, vertexDistance, FogStart, FogEnd, FogColor);
}}
"""

# ---------------------------------------------------------------------------
# 3. 1.21.6 - 1.21.8 (1_21_6/assets/minecraft/shaders/core/, formats 63..68)
# ---------------------------------------------------------------------------
ENTITY_VSH_1_21_6 = f"""#version 150

#moj_import <minecraft:light.glsl>
#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>
#moj_import <minecraft:projection.glsl>

in vec3 Position;
in vec4 Color;
in vec2 UV0;
in ivec2 UV1;
in ivec2 UV2;
in vec3 Normal;

uniform sampler2D Sampler1;
uniform sampler2D Sampler2;

out float sphericalVertexDistance;
out float cylindricalVertexDistance;
out vec4 vertexColor;
out vec4 lightMapColor;
out vec4 overlayColor;
out vec2 texCoord0;
{VSH_DECL}
void main() {{
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);
{VSH_INIT}
    sphericalVertexDistance = fog_spherical_distance(Position);
    cylindricalVertexDistance = fog_cylindrical_distance(Position);
#ifdef NO_CARDINAL_LIGHTING
    vertexColor = baseColor;
#else
    vertexColor = minecraft_mix_light(Light0_Direction, Light1_Direction, Normal, baseColor);
#endif
#ifndef EMISSIVE
    lightMapColor = texelFetch(Sampler2, UV2 / 16, 0);
#endif
    overlayColor = texelFetch(Sampler1, UV1, 0);

    texCoord0 = UV0;
#ifdef APPLY_TEXTURE_MATRIX
    texCoord0 = (TextureMat * vec4(UV0, 0.0, 1.0)).xy;
#endif
}}
"""

ENTITY_FSH_1_21_6 = f"""#version 150

#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>

uniform sampler2D Sampler0;

in float sphericalVertexDistance;
in float cylindricalVertexDistance;
in vec4 vertexColor;
in vec4 lightMapColor;
in vec4 overlayColor;
in vec2 texCoord0;
{FSH_DECL}
out vec4 fragColor;

void main() {{
{FSH_DISCARD}    vec4 color = texture(Sampler0, texCoord0);
#ifdef ALPHA_CUTOUT
    if (color.a < ALPHA_CUTOUT) {{
        discard;
    }}
#endif
    color *= vertexColor * ColorModulator;
#ifndef NO_OVERLAY
    color.rgb = mix(overlayColor.rgb, color.rgb, overlayColor.a);
#endif
#ifndef EMISSIVE
    color *= lightMapColor;
#endif
    fragColor = apply_fog(color, sphericalVertexDistance, cylindricalVertexDistance, FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd, FogColor);
}}
"""

def _item_entity_vsh_ubo(glsl_version):
    return f"""#version {glsl_version}

#moj_import <minecraft:light.glsl>
#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>
#moj_import <minecraft:projection.glsl>

in vec3 Position;
in vec4 Color;
in vec2 UV0;
in vec2 UV1;
in ivec2 UV2;
in vec3 Normal;

uniform sampler2D Sampler2;

out float sphericalVertexDistance;
out float cylindricalVertexDistance;
out vec4 vertexColor;
out vec2 texCoord0;
out vec2 texCoord1;
{VSH_DECL}
void main() {{
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);
{VSH_INIT}
    sphericalVertexDistance = fog_spherical_distance(Position);
    cylindricalVertexDistance = fog_cylindrical_distance(Position);
    vertexColor = minecraft_mix_light(Light0_Direction, Light1_Direction, Normal, baseColor) * texelFetch(Sampler2, UV2 / 16, 0);
    texCoord0 = UV0;
    texCoord1 = UV1;
}}
"""

def _item_entity_fsh_ubo(glsl_version):
    return f"""#version {glsl_version}

#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>

uniform sampler2D Sampler0;

in float sphericalVertexDistance;
in float cylindricalVertexDistance;
in vec4 vertexColor;
in vec2 texCoord0;
in vec2 texCoord1;
{FSH_DECL}
out vec4 fragColor;

void main() {{
{FSH_DISCARD}    vec4 color = texture(Sampler0, texCoord0) * vertexColor * ColorModulator;
    if (color.a < 0.1) {{
        discard;
    }}
    fragColor = apply_fog(color, sphericalVertexDistance, cylindricalVertexDistance, FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd, FogColor);
}}
"""

# ---------------------------------------------------------------------------
# 4. 1.21.9 - 1.21.11 (1_21_9/assets/minecraft/shaders/core/, formats 69..99)
# ---------------------------------------------------------------------------
ENTITY_VSH_1_21_9 = f"""#version 330

#moj_import <minecraft:light.glsl>
#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>
#moj_import <minecraft:projection.glsl>

in vec3 Position;
in vec4 Color;
in vec2 UV0;
in ivec2 UV1;
in ivec2 UV2;
in vec3 Normal;

uniform sampler2D Sampler1;
uniform sampler2D Sampler2;

out float sphericalVertexDistance;
out float cylindricalVertexDistance;
#ifdef PER_FACE_LIGHTING
out vec4 vertexPerFaceColorBack;
out vec4 vertexPerFaceColorFront;
#else
out vec4 vertexColor;
#endif
#ifndef EMISSIVE
out vec4 lightMapColor;
#endif
#ifndef NO_OVERLAY
out vec4 overlayColor;
#endif
out vec2 texCoord0;
{VSH_DECL}
void main() {{
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);
{VSH_INIT}
    sphericalVertexDistance = fog_spherical_distance(Position);
    cylindricalVertexDistance = fog_cylindrical_distance(Position);
#ifdef PER_FACE_LIGHTING
    vec2 light = minecraft_compute_light(Light0_Direction, Light1_Direction, Normal);
    vertexPerFaceColorBack = minecraft_mix_light_separate(-light, baseColor);
    vertexPerFaceColorFront = minecraft_mix_light_separate(light, baseColor);
#elif defined(NO_CARDINAL_LIGHTING)
    vertexColor = baseColor;
#else
    vertexColor = minecraft_mix_light(Light0_Direction, Light1_Direction, Normal, baseColor);
#endif
#ifndef EMISSIVE
    lightMapColor = texelFetch(Sampler2, UV2 / 16, 0);
#endif
#ifndef NO_OVERLAY
    overlayColor = texelFetch(Sampler1, UV1, 0);
#endif

    texCoord0 = UV0;
#ifdef APPLY_TEXTURE_MATRIX
    texCoord0 = (TextureMat * vec4(UV0, 0.0, 1.0)).xy;
#endif
}}
"""

ENTITY_FSH_1_21_9 = f"""#version 330

#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>

uniform sampler2D Sampler0;

in float sphericalVertexDistance;
in float cylindricalVertexDistance;
#ifdef PER_FACE_LIGHTING
in vec4 vertexPerFaceColorBack;
in vec4 vertexPerFaceColorFront;
#else
in vec4 vertexColor;
#endif
#ifndef EMISSIVE
in vec4 lightMapColor;
#endif
#ifndef NO_OVERLAY
in vec4 overlayColor;
#endif
in vec2 texCoord0;
{FSH_DECL}
out vec4 fragColor;

void main() {{
{FSH_DISCARD}    vec4 color = texture(Sampler0, texCoord0);
#ifdef ALPHA_CUTOUT
    if (color.a < ALPHA_CUTOUT) {{
        discard;
    }}
#endif
#ifdef PER_FACE_LIGHTING
    color *= (gl_FrontFacing ? vertexPerFaceColorFront : vertexPerFaceColorBack) * ColorModulator;
#else
    color *= vertexColor * ColorModulator;
#endif
#ifndef NO_OVERLAY
    color.rgb = mix(overlayColor.rgb, color.rgb, overlayColor.a);
#endif
#ifndef EMISSIVE
    color *= lightMapColor;
#endif
    fragColor = apply_fog(color, sphericalVertexDistance, cylindricalVertexDistance, FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd, FogColor);
}}
"""


def patch_legacy_translucent_vsh(vsh_text):
    """Injects elytrixHideRadius / elytrixEyeDist into existing ModelEngine player-skin .vsh."""
    text = vsh_text.replace('\r\n', '\n')
    if 'elytrixHideRadius' in text:
        return text
    anchor_decl = 'out vec2 texCoord0;\n'
    if anchor_decl not in text:
        raise ValueError('unexpected legacy translucent vsh header')
    text = text.replace(anchor_decl, anchor_decl + VSH_DECL, 1)

    pat = re.compile(
        r'vertexColor = minecraft_mix_light\(Light0_Direction, Light1_Direction, (normalize\(Normal\)|Normal), Color\);'
    )
    m = pat.search(text)
    if not m:
        raise ValueError('unexpected legacy translucent vsh lighting line')
    norm_expr = m.group(1)
    repl = (
        VSH_INIT.rstrip('\n')
        + f'\n    vertexColor = minecraft_mix_light(Light0_Direction, Light1_Direction, {norm_expr}, baseColor);'
    )
    text = pat.sub(lambda _: repl, text, count=1)
    return text


def patch_legacy_translucent_fsh(fsh_text):
    """Injects elytrixHideRadius / elytrixEyeDist discard into existing ModelEngine .fsh."""
    text = fsh_text.replace('\r\n', '\n')
    if 'elytrixHideRadius' in text:
        return text
    anchor_decl = 'in vec2 texCoord0;\n'
    if anchor_decl not in text:
        raise ValueError('unexpected legacy translucent fsh header')
    text = text.replace(anchor_decl, anchor_decl + FSH_DECL, 1)

    anchor_main = 'void main() {\n'
    if anchor_main not in text:
        raise ValueError('unexpected legacy translucent fsh main()')
    text = text.replace(anchor_main, anchor_main + FSH_DISCARD, 1)
    return text


def build_fpv_pack_entries(source_data):
    """Builds all shader files, updated pack.mcmeta, and tinted wing/halo item JSONs."""
    updates = {}

    # 1. Patch existing root & 1_21_2 rendertype_entity_translucent.{vsh,fsh}
    for prefix in ('', '1_21_2/'):
        vsh_key = f'{prefix}assets/minecraft/shaders/core/rendertype_entity_translucent.vsh'
        fsh_key = f'{prefix}assets/minecraft/shaders/core/rendertype_entity_translucent.fsh'
        if vsh_key in source_data and fsh_key in source_data:
            updates[vsh_key] = patch_legacy_translucent_vsh(
                source_data[vsh_key].decode('utf-8')).encode('utf-8')
            updates[fsh_key] = patch_legacy_translucent_fsh(
                source_data[fsh_key].decode('utf-8')).encode('utf-8')

    # 2. Root <= 1.21.1 item_entity shader
    updates['assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull.vsh'] = \
        ITEM_ENTITY_VSH_1_21_1.encode('utf-8')
    updates['assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull.fsh'] = \
        ITEM_ENTITY_FSH_1_21_1.encode('utf-8')

    # 3. 1.21.2 - 1.21.5 (formats 36..62)
    updates['1_21_2/assets/minecraft/shaders/core/entity.vsh'] = ENTITY_VSH_1_21_2.encode('utf-8')
    updates['1_21_2/assets/minecraft/shaders/core/entity.fsh'] = ENTITY_FSH_1_21_2.encode('utf-8')
    updates['1_21_2/assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull.vsh'] = \
        ITEM_ENTITY_VSH_1_21_2.encode('utf-8')
    updates['1_21_2/assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull.fsh'] = \
        ITEM_ENTITY_FSH_1_21_2.encode('utf-8')

    # 4. 1.21.6 - 1.21.8 (formats 63..68 via 1_21_6)
    updates['1_21_6/assets/minecraft/shaders/core/entity.vsh'] = ENTITY_VSH_1_21_6.encode('utf-8')
    updates['1_21_6/assets/minecraft/shaders/core/entity.fsh'] = ENTITY_FSH_1_21_6.encode('utf-8')
    updates['1_21_6/assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull.vsh'] = \
        _item_entity_vsh_ubo(150).encode('utf-8')
    updates['1_21_6/assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull.fsh'] = \
        _item_entity_fsh_ubo(150).encode('utf-8')

    # 5. 1.21.9 - 1.21.11 (formats 69..99 via 1_21_9 stacked after 1_21_6)
    updates['1_21_9/assets/minecraft/shaders/core/entity.vsh'] = ENTITY_VSH_1_21_9.encode('utf-8')
    updates['1_21_9/assets/minecraft/shaders/core/entity.fsh'] = ENTITY_FSH_1_21_9.encode('utf-8')
    updates['1_21_9/assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull.vsh'] = \
        _item_entity_vsh_ubo(330).encode('utf-8')
    updates['1_21_9/assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull.fsh'] = \
        _item_entity_fsh_ubo(330).encode('utf-8')

    # 6. Apply constant marker tints to all 4 worn ModelEngine accessories in the pack
    for name, raw in source_data.items():
        if not (name.startswith('assets/modelengine/items/') and name.endswith('.json')):
            continue
        parts = name.split('/')
        if len(parts) < 5:
            continue
        model_id = parts[3]
        if model_id in WINGS_ACCESSORY_MODELS:
            tint_val = WINGS_TINT_VALUE
        elif model_id in CLOSE_ACCESSORY_MODELS:
            tint_val = CLOSE_TINT_VALUE
        else:
            continue
        doc = json.loads(raw.decode('utf-8'))
        if 'model' in doc and isinstance(doc['model'], dict):
            doc['model']['tints'] = [{'type': 'minecraft:constant', 'value': tint_val}]
            updates[name] = json.dumps(doc, separators=(',', ':')).encode('utf-8')

    # 7. Update pack.mcmeta overlays (1_21_2, 1_21_6, 1_21_9) & sodium.ignored_shaders
    mcmeta = json.loads(source_data['pack.mcmeta'].decode('utf-8'))
    mcmeta['overlays'] = {
        'entries': [
            {
                'directory': '1_21_2',
                'formats': {'min_inclusive': 36, 'max_inclusive': 62},
                'min_format': 36,
                'max_format': 62,
            },
            {
                'directory': '1_21_6',
                'formats': {'min_inclusive': 63, 'max_inclusive': 99},
                'min_format': 63,
                'max_format': 99,
            },
            {
                'directory': '1_21_9',
                'formats': {'min_inclusive': 69, 'max_inclusive': 99},
                'min_format': 69,
                'max_format': 99,
            },
        ]
    }
    mcmeta['sodium'] = {'ignored_shaders': list(SODIUM_IGNORED_SHADERS)}
    updates['pack.mcmeta'] = (json.dumps(mcmeta, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

    return updates
