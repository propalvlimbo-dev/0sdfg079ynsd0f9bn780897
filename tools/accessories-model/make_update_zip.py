#!/usr/bin/env python3
"""Builds `elytrix-update.zip` (ШАБЛОН Б из AI_INSTRUCTIONS.txt).

The archive is the full accessories/RP payload (`elytrix-freakmodel.zip`) plus every
plugin config, kit and jar that changed in the release, all with paths relative to
the server root, so `unzip -oq elytrix-update.zip -d /root/RW_GRIEF` is enough.
"""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/accessories-model'))
import make_deploy_zip as MD  # noqa: E402

OUT = ROOT / 'elytrix-update.zip'
FIXED_DATE = (2020, 1, 1, 0, 0, 0)

EXTRA = [
    'plugins/ElytrixEventGuard.jar',
    'plugins/ElytrixGodPickup.jar',
    'plugins/NMascot-1.0.jar',
    'plugins/ElytrixRP/config.yml',
    'config/paper-world-defaults.yml',
    'config/leaf-global.yml',
    'plugins/TAB/config.yml',
    'plugins/WGExtender/config.yml',
    'plugins/WorldGuard/config.yml',
    'plugins/ElytrixGranter/config.yml',
    'plugins/BCases/prizes.yml',
    'plugins/ItemKeep/data.yml',
    'plugins/ElytrixDealer/items.yml',
    'plugins/ElytrixCooldowns/config.yml',
    'plugins/DeluxeMenus/config.yml',
    'plugins/DeluxeMenus/gui_menus/kits.yml',
    'plugins/DeluxeMenus/gui_menus/kits_preview/preview_fame.yml',
    'plugins/DeluxeMenus/gui_menus/priv/donate.yml',
    'plugins/DeluxeMenus/gui_menus/shop/sphere.yml',
    'plugins/DecentHolograms/holograms/don1.yml',
    'plugins/DecentHolograms/holograms/don2.yml',
    'plugins/nKits/Kits/angel.yml',
    'plugins/nKits/Kits/fame.yml',
    'plugins/nKits/Kits/bull.yml',
    'plugins/nKits/Kits/bunny.yml',
    'plugins/nKits/Kits/cobra.yml',
    'plugins/nKits/Kits/dhelper.yml',
    'plugins/nKits/Kits/dracula.yml',
    'plugins/nKits/Kits/dragon.yml',
    'plugins/nKits/Kits/god.yml',
    'plugins/nKits/Kits/hydra.yml',
    'plugins/nKits/Kits/media.yml',
    'plugins/nKits/Kits/pegas.yml',
    'plugins/nKits/Kits/plus.yml',
    'plugins/nKits/Kits/pluspro.yml',
    'plugins/nKits/Kits/pvp.yml',
    'plugins/nKits/Kits/pvp1.yml',
    'plugins/nKits/Kits/pvp2.yml',
    'plugins/nKits/Kits/pvp3.yml',
    'plugins/nKits/Kits/pvpp.yml',
    'plugins/nKits/Kits/rabbit.yml',
    'plugins/nKits/Kits/vampire.yml',
]

FORBIDDEN = ('ModelEngine/config.yml', '.data/cache.json', 'owned_accessories.yml')


def main():
    entries = {}
    for rel, path in MD.collect():
        if any(bad in rel for bad in FORBIDDEN):
            continue
        entries[rel] = path
    for rel in EXTRA:
        p = ROOT / rel
        if not p.is_file():
            raise SystemExit('missing required file: ' + rel)
        entries[rel] = p

    seen = set()
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(entries):
            if rel in seen:
                raise SystemExit('duplicate entry: ' + rel)
            seen.add(rel)
            info = zipfile.ZipInfo(rel, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, entries[rel].read_bytes())

    data = OUT.read_bytes()
    print('files:  %d' % len(seen))
    print('size:   %d' % OUT.stat().st_size)
    print('sha1:   %s' % hashlib.sha1(data).hexdigest())
    print('sha256: %s' % hashlib.sha256(data).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
