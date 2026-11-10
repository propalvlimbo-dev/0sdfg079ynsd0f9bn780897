# -*- coding: utf-8 -*-
"""Rebuilds plugins/DeluxeMenus/gui_menus/kits_preview/preview_fame.yml straight
from plugins/nKits/Kits/fame.yml, so the preview can never drift from the kit again.

Layout (kept identical to every other preview in the folder):
  * 0 / 9 / 18 / 27 - helmet / chest / leggings / boots
  * 36              - the off-hand item (the FAME ball)
  * 2..8, 11..17, 20..26, 29..35 - the rest of the kit
  * 45 - the kit badge, 47/48 - back, 50/51 - claim
The FAME sword keeps `model_data: 5015`, so the preview shows the real 3D model.
"""
import io
import re

import yaml  # noqa: E402

KIT = 'plugins/nKits/Kits/fame.yml'
OUT = 'plugins/DeluxeMenus/gui_menus/kits_preview/preview_fame.yml'

# DeluxeMenus preview keys -> the kit component that carries them
ENCHANT_KEY = 'minecraft:enchantments'

LOOT_SLOTS = ([2, 3, 4, 5, 6, 7, 8]
              + list(range(11, 18))
              + list(range(20, 27))
              + list(range(29, 36)))

HEAD_LINES = """menu_title: §fꈁꀀꈂꍗꈂꀁ§fꈃꄑ
open_command: kitpreview_fame
register_command: true
size: 54
items:
"""

ENCHANT_RENAME = {
    'minecraft:': '',
}


def material(item_id):
    return str(item_id).replace('minecraft:', '').upper()


def enchantments(components):
    raw = components.get(ENCHANT_KEY)
    if not raw:
        return []
    names = []
    for key, value in re.findall(r'"([^"]+)":\s*([0-9]+)', raw):
        for old, new in ENCHANT_RENAME.items():
            key = key.replace(old, new)
        names.append('%s;%s' % (key.upper(), value))
    return sorted(names)


def plain_text(component):
    """Pulls the visible text out of a custom_name component (best effort)."""
    if not component:
        return None
    out = []
    depth = 0
    i = 0
    while i < len(component):
        ch = component[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        elif ch == '"' and depth:
            j = i + 1
            buf = []
            while j < len(component) and component[j] != '"':
                buf.append(component[j])
                j += 1
            text = ''.join(buf)
            if 'text' in component[max(0, i - 40):i] and text and not text.startswith('minecraft'):
                out.append(text)
            i = j
        i += 1
    return ' '.join(out).strip() or None


def emit(name, slot, item, out, extra_lines=None, amount=None):
    out.append('  %s:' % name)
    out.append('    slot: %d' % slot)
    out.append('    amount: %d' % (amount or item.get('count', 1)))
    out.append('    material: %s' % material(item.get('id')))
    if extra_lines:
        for line in extra_lines:
            out.append(line if line.startswith('    ') else '    %s' % line)
    ench = enchantments(item.get('components') or {})
    if ench:
        out.append('    enchantments:')
        for e in ench:
            out.append('    - %s' % e)


def main():
    kit = yaml.safe_load(io.open(KIT, encoding='utf-8'))
    inv = kit['Inventory']
    armor = inv['Armor']
    main_items = [x for x in inv['Main'] if x]

    ball = None
    head = None
    for item in main_items:
        if str(item.get('id')) != 'minecraft:player_head':
            continue
        name = str((item.get('components') or {}).get('minecraft:custom_name') or '')
        if 'Шар' in name:
            ball = item
        elif head is None:
            head = item
    assert ball is not None and head is not None, 'the FAME ball/head went missing from the kit'

    def is_special(item):
        components = item.get('components') or {}
        return ('5015' in str(components.get('minecraft:custom_model_data') or '')
                or str(item.get('id')) == 'minecraft:player_head')

    loot = [x for x in main_items if x is not ball]
    # the grid has 28 slots and the kit has more: keep the sword and the head (the
    # items players actually care about) and drop plain filler such as glowstone
    special = [x for x in loot if is_special(x)]
    special_ids = set(id(x) for x in special)
    filler = [x for x in loot if id(x) not in special_ids
              and str(x.get('id')) not in ('minecraft:glowstone',)]
    loot = (special + filler)[:len(LOOT_SLOTS)]
    assert len(loot) == len(LOOT_SLOTS), (len(loot), len(LOOT_SLOTS))
    assert any('5015' in str((x.get('components') or {}).get('minecraft:custom_model_data') or '')
               for x in loot), 'the FAME sword dropped out of the preview'
    assert any(str(x.get('id')) == 'minecraft:player_head' for x in loot), 'the FAME head dropped out'

    out = [HEAD_LINES.rstrip('\n')]

    # armour column: boots / leggings / chest / helmet bottom-up
    for index, slot in enumerate((27, 18, 9, 0)):
        item = armor[index]
        name = plain_text((item.get('components') or {}).get('minecraft:custom_name'))
        emit('armor_%d' % index, slot, item, out,
             extra_lines=['    display_name: \'&l%s\'' % name] if name else None)

    # off-hand: the ball
    ball_name = plain_text((ball.get('components') or {}).get('minecraft:custom_name'))
    emit('offhand_item', 36, ball, out,
         extra_lines=['    display_name: \'&#A855F7&l%s\'' % ball_name] if ball_name else None)

    # the kit itself
    for index, item in enumerate(loot):
        components = item.get('components') or {}
        extras = []
        name = plain_text(components.get('minecraft:custom_name'))
        if name:
            extras.append('    display_name: \'&l%s\'' % name)
        cmd = components.get('minecraft:custom_model_data')
        if cmd and '5015' in str(cmd):
            extras.append('    model_data: 5015')
        if str(item.get('id')) == 'minecraft:player_head':
            extras.append('    display_name: \'&#A855F7&lГолова Славы\'')
        emit('loot_%d' % index, LOOT_SLOTS[index], item, out, extra_lines=extras or None)

    out.append("""  kit_badge:
    material: purple_shulker_box
    slot: 45
    display_name: '&#AAAAAAНабор &#A855F7&lFAME'
    lore:
    - '&8Предпросмотр набора'
    - ''
    - '&7Слева отображается броня и'
    - '&7предмет второй руки (щит/тотем).'
    - '&7Справа — всё содержимое набора!'
  btn_back:
    material: structure_void
    slots:
    - 47
    - 48
    display_name: '&#F8BEFB◄ Назад к списку наборов'
    lore:
    - '&7Нажмите, чтобы вернуться в &f/kits'
    click_commands:
    - '[openguimenu] kits'
  btn_claim:
    material: structure_void
    slots:
    - 50
    - 51
    display_name: '&#55FF55✔ Получить этот набор'
    lore:
    - '&7Нажмите, чтобы взять набор'
    click_commands:
    - '[close]'
    - '[player] kit fame'
""".rstrip('\n'))

    io.open(OUT, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('wrote %s (%d lines)' % (OUT, len(out)))


if __name__ == '__main__':
    main()
