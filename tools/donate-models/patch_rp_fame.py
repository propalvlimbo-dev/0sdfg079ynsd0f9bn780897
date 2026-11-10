#!/usr/bin/env python3
"""Adds the FAME donation sword to the Elytrix resource pack.

`merge_pack.py` copies every byte it does not own, so it can never touch
`assets/minecraft/models/item/netherite_sword.json` - that file carries the
hand-made `custom_model_data` overrides of the other donation swords (100..106,
5012..5014).  This script runs right AFTER `merge_pack.py` and inserts exactly one
new override, `5015 -> reallyworld:item/sword/fame_sword`, leaving every existing
override untouched.

The pack is rewritten deterministically (fixed date, deflate, sorted names) so the
`SHA-1` printed here is the one that goes into `plugins/ElytrixRP/config.yml`.
Running it twice is a no-op.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXED_DATE = (2020, 1, 1, 0, 0, 0)
SWORD_JSON = 'assets/minecraft/models/item/netherite_sword.json'
MODEL_ID = 'reallyworld:item/sword/fame_sword'
CMD = 5015
TEXTURE = f'assets/reallyworld/textures/item/sword/{MODEL_ID.rsplit("/", 1)[-1]}.png'
MODEL_PATH = f'assets/reallyworld/models/item/sword/{MODEL_ID.rsplit("/", 1)[-1]}.json'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pack', type=Path, default=ROOT / 'rp/Elytrix-RP-1.21.zip')
    args = ap.parse_args()
    pack: Path = args.pack

    with __import__('zipfile').ZipFile(pack) as src:
        data = {i.filename: src.read(i.filename) for i in src.infolist()
                if not i.filename.endswith('/')}

    missing = [n for n in (SWORD_JSON, MODEL_PATH, TEXTURE) if n not in data]
    if missing:
        raise SystemExit('pack is missing: ' + ', '.join(missing))

    model = json.loads(data[MODEL_PATH].decode('utf-8'))
    if model.get('textures', {}).get('particle') != \
            f'reallyworld:item/sword/{MODEL_ID.rsplit("/", 1)[-1]}':
        raise SystemExit('fame_sword.json does not point at the right texture')

    sword = json.loads(data[SWORD_JSON].decode('utf-8'))
    overrides = sword.setdefault('overrides', [])
    for entry in overrides:
        if entry.get('predicate', {}).get('custom_model_data') == CMD:
            print(f'{SWORD_JSON} already has custom_model_data {CMD} - nothing to do')
            return 0
        if entry.get('model') == MODEL_ID:
            raise SystemExit('the FAME model is already bound to another CMD')

    overrides.append({'predicate': {'custom_model_data': CMD}, 'model': MODEL_ID})
    # keep the list sorted by predicate, exactly like the hand-made part of the file
    overrides.sort(key=lambda e: e.get('predicate', {}).get('custom_model_data', 0))
    data[SWORD_JSON] = json.dumps(sword, ensure_ascii=False, indent=2).encode('utf-8')

    import zipfile
    with zipfile.ZipFile(pack, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        for name in sorted(data):
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            out.writestr(info, data[name])

    raw = pack.read_bytes()
    print('files: %d' % len(data))
    print('size:  %d' % len(raw))
    print('sha1:  %s' % hashlib.sha1(raw).hexdigest())
    print('sha256:%s' % hashlib.sha256(raw).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
