# -*- coding: utf-8 -*-
"""Rebuilds plugins/nKits/Kits/fame.yml from scratch.

FAME sits exactly one step below ANGEL, so every slot mirrors the ANGEL kit and is
nerfed by one small notch: enchant levels one lower, a couple of stacks smaller and
no `mending`-free extras.  Two slots are FAME's own:

  * slot 0  - the FAME sword, custom_model_data 5015 -> reallyworld:item/sword/fame_sword
              (its own 3D model, see tools/donate-models/build_fame_sword.py)
  * slot 40 - "Шар Славы": a PLAIN player_head, no custom_model_data at all
              (the donation owner asked for a ball with no model - just a head)
  * slot 41 - "Голова Славы": the wearable FAME head
"""
import base64
import io
import json
import struct
import uuid

OUT = 'plugins/nKits/Kits/fame.yml'

SKIN_URL = ('http://textures.minecraft.net/texture/'
            '2c162c16e01433b3da6674d642c3eab4be9e6d71e20a3325564c4d03a812606a')
TEX = base64.b64encode(json.dumps({"textures": {"SKIN": {"url": SKIN_URL}}},
                                  separators=(',', ':')).encode()).decode()
_i = struct.unpack('>4i', uuid.UUID('62bb602f-1479-476b-b9d2-d41fb474405a').bytes)
PROFILE = ('{id:[I;%d,%d,%d,%d],name:"fame_head",properties:'
           '[{name:"textures",value:"%s"}]}' % (_i + (TEX,)))


def name(text, colour='#A855F7', bold=True):
    b = '1b' if bold else '0b'
    return ('{extra:[{bold:%s,color:"%s",italic:0b,obfuscated:0b,strikethrough:0b,'
            'text:"%s",underlined:0b}],text:""}' % (b, colour, text))


def enchants(**pairs):
    return '{' + ','.join('"minecraft:%s":%s' % (k, v) for k, v in sorted(pairs.items())) + '}'


def stack(item, count=1, comps=None):
    lines = ['  - ==: org.bukkit.inventory.ItemStack',
             '    DataVersion: 4556',
             '    id: minecraft:%s' % item]
    if count != 1:
        lines.append('    count: %d' % count)
    if comps:
        lines.append('    components:')
        for key, value in comps:
            lines.append("      %s: '%s'" % (key, value))
    lines.append('    schema_version: 1')
    return lines


def q(s):
    return s.replace("'", "''")


MAIN = []
A = MAIN.append

# ---- 0: the FAME sword (own 3D model, cmd 5015) --------------------------------
A(stack('netherite_sword', comps=[
    ('minecraft:custom_name', name('Клинок Славы FAME')),
    ('minecraft:enchantments',
     enchants(fire_aspect=2, looting=2, mending=1, sharpness=5, sweeping_edge=2, unbreaking=3)),
    ('minecraft:custom_model_data', '{floats:[5015.0f]}'),
]))

# ---- 1..6: tools, one enchant notch below ANGEL -------------------------------
A(stack('netherite_pickaxe', comps=[
    ('minecraft:custom_name', name('Кирка Славы FAME')),
    ('minecraft:enchantments', enchants(efficiency=7, fortune=3, mending=1, unbreaking=3)),
]))
A(stack('netherite_axe', comps=[
    ('minecraft:custom_name', name('Секира Славы FAME')),
    ('minecraft:enchantments', enchants(efficiency=7, mending=1, sharpness=5, unbreaking=3)),
]))
A(stack('netherite_shovel', comps=[
    ('minecraft:custom_name', name('Лопата Славы FAME')),
    ('minecraft:enchantments', enchants(efficiency=7, mending=1, unbreaking=3)),
]))
A(stack('bow', comps=[
    ('minecraft:custom_name', name('Лук Славы FAME')),
    ('minecraft:enchantments',
     enchants(flame=1, infinity=1, mending=1, power=6, punch=2, unbreaking=3)),
]))
A(stack('crossbow', comps=[
    ('minecraft:custom_name', name('Арбалет Славы FAME')),
    ('minecraft:enchantments', enchants(mending=1, multishot=1, quick_charge=3, unbreaking=3)),
]))
A(stack('elytra', comps=[
    ('minecraft:custom_name', name('Крылья Славы FAME')),
    ('minecraft:enchantments', enchants(mending=1, unbreaking=4)),
]))

# ---- 7..19: consumables --------------------------------------------------------
A(stack('firework_rocket', 64))
A(stack('enchanted_golden_apple', 2))          # ANGEL gives 4
A(stack('golden_apple', 64))
A(stack('golden_carrot', 64))
A(stack('ender_pearl', 16))
A(stack('ender_pearl', 16))
A(stack('totem_of_undying'))
A(stack('totem_of_undying'))
A(stack('experience_bottle', 64))
A(stack('chorus_fruit', 64))
A(stack('tipped_arrow', 32, [('minecraft:potion_contents', '{potion:"minecraft:strong_strength"}')]))
A(stack('tipped_arrow', 32, [('minecraft:potion_contents', '{potion:"minecraft:strong_healing"}')]))

# ---- 20..22: splash potions ----------------------------------------------------
A(stack('splash_potion', comps=[('minecraft:potion_contents', '{potion:"minecraft:strong_strength"}')]))
A(stack('splash_potion', comps=[('minecraft:potion_contents', '{potion:"minecraft:strong_swiftness"}')]))
A(stack('splash_potion', comps=[('minecraft:potion_contents', '{potion:"minecraft:long_fire_resistance"}')]))

# ---- 23..29: blocks ------------------------------------------------------------
A(stack('arrow', 64))
A(stack('obsidian', 64))
A(stack('amethyst_block', 64))                 # FAME palette instead of ANGEL quartz
A(stack('purple_concrete', 64))                # FAME palette instead of ANGEL white
A(stack('end_crystal', 12))                    # ANGEL gives 16
A(stack('respawn_anchor', 12))                 # ANGEL gives 16
A(stack('glowstone', 64))

BALL_ATTRS = (
    '[{amount:2.0d,id:"elytrix:armor_fame_ball",operation:"add_value",'
    'slot:"offhand",type:"minecraft:armor"},'
    '{amount:4.0d,id:"elytrix:health_fame_ball",operation:"add_value",'
    'slot:"offhand",type:"minecraft:max_health"},'
    '{amount:2.0d,id:"elytrix:damage_fame_ball",operation:"add_value",'
    'slot:"offhand",type:"minecraft:attack_damage"},'
    '{amount:0.10d,id:"elytrix:speed_fame_ball",operation:"add_multiplied_total",'
    'slot:"offhand",type:"minecraft:movement_speed"}]'
)
BALL_LORE = (
    '[{extra:[{color:"#FF5555",italic:0b,text:"Проклятие утраты"}],italic:0b,text:""},"",'
    '{extra:[{color:"#AAAAAA",italic:0b,text:"Когда во второй руке:"}],italic:0b,text:""},'
    '{extra:[{bold:1b,color:"#55FF55",italic:0b,text:" +2 к Броне"}],italic:0b,text:""},'
    '{extra:[{bold:1b,color:"#55FF55",italic:0b,text:" +4 к Здоровью"}],italic:0b,text:""},'
    '{extra:[{bold:1b,color:"#55FF55",italic:0b,text:" +2 к Урону"}],italic:0b,text:""},'
    '{extra:[{bold:1b,color:"#55FF55",italic:0b,text:" +10% к Скорости"}],italic:0b,text:""}]'
)

# ---- 40: the ball - a plain head, NO custom model ------------------------------
BALL = stack('player_head', comps=[
    ('minecraft:attribute_modifiers', BALL_ATTRS),
    ('minecraft:profile', PROFILE),
    ('minecraft:lore', BALL_LORE),
    ('minecraft:enchantments', '{"minecraft:vanishing_curse":1}'),
    ('minecraft:tooltip_display',
     '{hidden_components:["minecraft:enchantments","minecraft:attribute_modifiers"]}'),
    ('minecraft:custom_name', name('Шар Славы')),
    ('minecraft:custom_data', '{PublicBukkitValues:{"minecraft:fame_ball":"FAME_BALL"}}'),
])

HEAD_ATTRS = (
    '[{amount:2.0d,id:"elytrix:damage_fame_head",operation:"add_value",'
    'slot:"head",type:"minecraft:attack_damage"},'
    '{amount:0.20d,id:"elytrix:speed_fame_head",operation:"add_multiplied_base",'
    'slot:"head",type:"minecraft:movement_speed"},'
    '{amount:1.0d,id:"elytrix:health_fame_head",operation:"add_value",'
    'slot:"head",type:"minecraft:max_health"}]'
)
HEAD_LORE = (
    '[{extra:[{color:"#AAAAAA",italic:0b,text:"Надето на голову:"}],italic:0b,text:""},'
    '{extra:[{bold:1b,color:"#55FF55",italic:0b,text:" +2 к Урону"}],italic:0b,text:""},'
    '{extra:[{bold:1b,color:"#55FF55",italic:0b,text:" +20% к Скорости"}],italic:0b,text:""},'
    '{extra:[{bold:1b,color:"#55FF55",italic:0b,text:" +1 к Здоровью"}],italic:0b,text:""},"",'
    '{extra:[{color:"#FF5555",italic:0b,text:"Проклятие утраты"}],italic:0b,text:""}]'
)

# ---- 41: the wearable FAME head ------------------------------------------------
HEAD = stack('player_head', comps=[
    ('minecraft:attribute_modifiers', HEAD_ATTRS),
    ('minecraft:profile', PROFILE),
    ('minecraft:lore', HEAD_LORE),
    ('minecraft:enchantments', '{"minecraft:vanishing_curse":1}'),
    ('minecraft:tooltip_display',
     '{hidden_components:["minecraft:enchantments","minecraft:attribute_modifiers"]}'),
    ('minecraft:custom_name', name('Голова Славы')),
])

ARMOR = []
B = ARMOR.append
B(stack('netherite_boots', comps=[
    ('minecraft:custom_name', name('Ботинки Славы FAME')),
    ('minecraft:enchantments',
     enchants(depth_strider=3, feather_falling=4, mending=1, protection=4, unbreaking=3)),
]))
B(stack('netherite_leggings', comps=[
    ('minecraft:custom_name', name('Поножи Славы FAME')),
    ('minecraft:enchantments',
     enchants(mending=1, protection=4, swift_sneak=3, unbreaking=3)),
]))
B(stack('netherite_chestplate', comps=[
    ('minecraft:custom_name', name('Нагрудник Славы FAME')),
    ('minecraft:enchantments', enchants(mending=1, protection=4, unbreaking=3)),
]))
B(stack('netherite_helmet', comps=[
    ('minecraft:custom_name', name('Шлем Славы FAME')),
    ('minecraft:enchantments',
     enchants(aqua_affinity=1, mending=1, protection=4, respiration=3, unbreaking=3)),
]))


def main():
    out = io.StringIO()
    w = out.write
    w('Name: fame\n')
    w('Cooldown: 86400\n')
    w('Permission: nKits.kits.fame\n')
    w('Order: 0\n')
    w('FirstTimeJoinKit: false\n')
    w('OneTimeUse: false\n')
    w('Inventory:\n')
    w('  Main:\n')
    for block in MAIN:
        w('\n'.join(block) + '\n')
    for _ in range(11):                    # slots 29..39 stay empty, like ANGEL
        w('  - null\n')
    w('\n'.join(BALL) + '\n')
    w('\n'.join(HEAD) + '\n')
    w('  - null\n')
    w('  Armor:\n')
    for block in ARMOR:
        w('\n'.join(block) + '\n')

    text = out.getvalue()
    io.open(OUT, 'w', encoding='utf-8').write(text)
    print('wrote %s (%d lines)' % (OUT, text.count('\n')))


if __name__ == '__main__':
    main()
