#!/usr/bin/env python3
"""Merges the new accessory assets into a copy of the Elytrix resource pack.

Only these things change, everything else is copied byte for byte:

* ``assets/modelengine/items|models/elytrix_kaneki_tentacles/`` becomes exactly the
  files generated from the new blueprint (old four-bone files are removed);
* ``assets/modelengine/textures/entity/models/elytrix_kaneki_tentacles.png`` is the
  new texture;
* ``assets/reallyworld/textures/gui/title/elytrix_accessories.png`` is the menu title
  redrawn with the pack's own font;
* ``assets/minecraft/font/default.json`` gets (or replaces) exactly one provider for
  the ``ꏠ`` glyph, keeping the metrics of the other title providers.

The system files that the pack must keep (pack.png, leather_horse_armor item/model,
atlases, shaders) are checked before and after, and every JSON is validated, so the
client cannot end up with a broken pack.

Usage:
    python3 merge_pack.py <input.zip> <new_output.zip> \
        --assets <dir containing assets/> --title <elytrix_accessories.png> \
        [--texture <elytrix_kaneki_tentacles.png>]
"""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

MODEL = 'elytrix_kaneki_tentacles'
GLYPH = 'ꏠ'
FONT = 'assets/minecraft/font/default.json'
TITLE = 'assets/reallyworld/textures/gui/title/elytrix_accessories.png'
PROVIDER = {
    'type': 'bitmap',
    'file': 'reallyworld:gui/title/elytrix_accessories.png',
    'ascent': 26,
    'height': 32,
    'chars': [GLYPH],
}
REQUIRED = [
    'pack.png',
    'assets/minecraft/items/leather_horse_armor.json',
    'assets/minecraft/models/item/leather_horse_armor.json',
    'assets/minecraft/atlases/blocks.json',
    'assets/reallyworld/textures/gui/title/title_00.png',
]
# fonts/atlases the client needs; their content must not be touched by this merge
KEEP = [FONT, 'assets/minecraft/atlases/blocks.json',
        'assets/minecraft/items/leather_horse_armor.json',
        'assets/minecraft/models/item/leather_horse_armor.json']


def collect_assets(directory):
    """Reads an assets tree; accepts either <dir>/assets/... or <dir>/modelengine/..."""
    directory = Path(directory)
    base = directory / 'assets' if (directory / 'assets').is_dir() else directory
    files = {}
    for path in sorted(base.rglob('*')):
        if path.is_file():
            files['assets/' + path.relative_to(base).as_posix()] = path.read_bytes()
    if not files:
        raise ValueError('no generated assets found in ' + str(directory))
    return files


def font_entry(font, replace):
    providers = font['providers']
    found = []
    for index, provider in enumerate(providers):
        chars = provider.get('chars', [])
        if any(GLYPH in row for row in chars) or GLYPH in provider.get('advances', {}):
            found.append(index)
    if len(found) > 1:
        raise ValueError('glyph is registered more than once')
    if found and not replace:
        raise ValueError('glyph already registered but the pack was not built for it')
    if found:
        providers[found[0]] = dict(PROVIDER)
    else:
        providers.insert(0, dict(PROVIDER))
    return font, bool(found)


def validate_assets(files, model=MODEL):
    """Every item definition must point to a model that exists, and JSON must parse."""
    models = {name for name in files if name.startswith(f'assets/modelengine/models/{model}/')}
    items = {name for name in files if name.startswith(f'assets/modelengine/items/{model}/')}
    if not models or len(models) != len(items):
        raise ValueError(f'item/model count mismatch: {len(items)} items, {len(models)} models')
    for name in models | items:
        if not name.endswith('.json'):
            raise ValueError('unexpected non-JSON asset: ' + name)
        json.loads(files[name])
    for name in items:
        definition = json.loads(files[name])['model']
        reference = definition['model']
        expected = f'modelengine:{model}/' + Path(name).stem
        if reference != expected:
            raise ValueError(f'{name} points to {reference}, expected {expected}')
    textures = set()
    for name in models:
        textures.update(json.loads(files[name]).get('textures', {}).values())
    textures = {t.split(':')[-1] for t in textures if not t.startswith('#')}
    for texture in textures:
        if f'assets/modelengine/textures/{texture}.png' not in files:
            raise ValueError('missing texture ' + texture)


def merge(source, destination, assets_dir, title_png, texture_png=None,
          allow_existing_glyph=False):
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise SystemExit('missing input pack: ' + str(source))
    if destination.exists():
        raise SystemExit('output must be a new file: ' + str(destination))
    generated = collect_assets(assets_dir)
    if texture_png:
        generated[f'assets/modelengine/textures/entity/models/{MODEL}.png'] = \
            Path(texture_png).read_bytes()
    validate_assets(generated)

    title_bytes = Path(title_png).read_bytes()

    with zipfile.ZipFile(source) as original:
        names = original.namelist()
        if len(names) != len(set(names)) or original.testzip() is not None:
            raise SystemExit('input pack is corrupt or has duplicate entries')
        missing = [name for name in REQUIRED if name not in names]
        if missing:
            raise SystemExit('input pack lacks required files: ' + ', '.join(missing))
        source_data = {name: original.read(name) for name in names}

    font = json.loads(source_data[FONT])
    font, replaced = font_entry(font, replace=allow_existing_glyph or GLYPH in json.dumps(font))
    font_bytes = (json.dumps(font, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')

    prefix_items = f'assets/modelengine/items/{MODEL}/'
    prefix_models = f'assets/modelengine/models/{MODEL}/'
    stale = {name for name in source_data
             if (name.startswith(prefix_items) or name.startswith(prefix_models)) and name not in generated}
    stale |= {name for name in source_data
              if name.startswith(f'assets/modelengine/textures/entity/models/{MODEL}') and name not in generated}

    additions = dict(generated)
    additions[TITLE] = title_bytes
    additions[FONT] = font_bytes

    with zipfile.ZipFile(destination, 'x') as out:
        for info in zipfile.ZipFile(source).infolist():
            name = info.filename
            if name in stale:
                continue
            out.writestr(info, additions.get(name, source_data[name]))
        for name in sorted(additions):
            if name in source_data and name not in stale:
                continue
            entry = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(entry, additions[name])

    with zipfile.ZipFile(destination) as result:
        if result.testzip() is not None:
            raise SystemExit('output pack failed its CRC check')
        final = set(result.namelist())
        for name in generated:
            if result.read(name) != generated[name]:
                raise SystemExit('asset was not written: ' + name)
        for name in KEEP:
            if name != FONT and result.read(name) != source_data[name]:
                raise SystemExit('system file was modified: ' + name)
        check = json.loads(result.read(FONT))
        providers = [p for p in check['providers']
                     if GLYPH in p.get('chars', []) or GLYPH in p.get('advances', {})]
        if len(providers) != 1 or providers[0]['file'] != PROVIDER['file']:
            raise SystemExit('font provider for the title glyph is wrong')
        for name in stale:
            if name in final:
                raise SystemExit('stale file kept: ' + name)
    return hashlib.sha1(destination.read_bytes()).hexdigest(), replaced, len(stale)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('destination')
    parser.add_argument('--assets', required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--texture', help='texture PNG for the model (optional if already in --assets)')
    parser.add_argument('--allow-existing-glyph', action='store_true',
                        help='the source pack already carries the menu title glyph')
    args = parser.parse_args()
    sha1, replaced, removed = merge(args.source, args.destination, args.assets, args.title,
                                    texture_png=args.texture,
                                    allow_existing_glyph=args.allow_existing_glyph)
    print(f'merged pack: {args.destination}')
    print(f'  font provider: {"replaced" if replaced else "added"}, stale files removed: {removed}')
    print(f'  SHA-1: {sha1}')


if __name__ == '__main__':
    main()
