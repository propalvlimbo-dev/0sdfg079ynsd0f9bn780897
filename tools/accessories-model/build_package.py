#!/usr/bin/env python3
"""Builds the deployable ZIP for the Kaneki accessories + menu title.

Contents (relative to /root/RW_GRIEF on the VDS):

    plugins/ModelEngine/blueprints/elytrix_kaneki_tentacles.bbmodel
    plugins/ModelEngine/blueprints/elytrix_kaneki_eyepatch.bbmodel
    plugins/ModelEngine/resource pack/assets/modelengine/...   (generated assets)
    plugins/ModelEngine/resource pack/assets/reallyworld/...   (menu icon)
    plugins/ElytrixFreakModel.jar                              (accessories menu)
    rp/Elytrix-RP-1.21.zip                                     (merged pack)
    plugins/ElytrixRP/config.yml                               (new SHA-1)

Usage: python3 tools/accessories-model/build_package.py [output.zip]
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODELS = ('elytrix_kaneki_tentacles', 'elytrix_kaneki_eyepatch')
TITLE = ROOT / 'tools/accessories-integration/staging-assets/assets/reallyworld/textures/gui/title/elytrix_accessories.png'
# The accessory-enabled plugin build that ships with this package; committing the
# jar keeps the release reproducible instead of depending on a /tmp candidate.
PLUGIN = ROOT / 'tools/accessories-integration/dist/ElytrixFreakModel-v19.jar'
PLUGIN_SHA = 'e26faf1c9b1e779333f4af19e3fd4e52415284c78bc84e2ff4c0e694d971a91c'


def sha1(path):
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()


def build(output):
    output = Path(output).resolve()
    if output.exists():
        raise SystemExit('output already exists: ' + str(output))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # 1. merge the resource pack (new assets + redrawn title)
        merged = tmp / 'Elytrix-RP-1.21.zip'
        result = subprocess.run(
            [sys.executable, str(HERE / 'merge_pack.py'), str(ROOT / 'rp/Elytrix-RP-1.21.zip'),
             str(merged), '--assets', str(HERE / 'assets'), '--title', str(TITLE),
             '--allow-existing-glyph'],
            check=True, capture_output=True, text=True)
        print(result.stdout.strip())
        pack_sha1 = sha1(merged)

        # 2. accessory-enabled plugin (menu + eyepatch hook), hash-checked
        plugin = PLUGIN.read_bytes()
        plugin_sha = hashlib.sha256(plugin).hexdigest()
        if plugin_sha != PLUGIN_SHA:
            raise SystemExit('unexpected accessory plugin build: ' + plugin_sha)

        # 3. ElytrixRP config with the new SHA-1
        config = (ROOT / 'plugins/ElytrixRP/config.yml').read_text(encoding='utf-8')
        pattern = r'(?m)^([ \t]*sha1[ \t]*:[ \t]*)(["\']?[0-9a-fA-F]{40}["\']?)([ \t]*(?:#.*)?)$'
        config, count = re.subn(pattern, lambda m: m.group(1) + '"' + pack_sha1 + '"' + m.group(3), config)
        if count != 1:
            raise SystemExit('ElytrixRP config sha1 entry not found exactly once')

        entries = {}
        for model in MODELS:
            entries[f'plugins/ModelEngine/blueprints/{model}.bbmodel'] = (HERE / f'{model}.bbmodel').read_bytes()
        for path in sorted((HERE / 'assets').rglob('*')):
            if path.is_file():
                name = path.relative_to(HERE).as_posix()          # assets/modelengine/...
                entries[f'plugins/ModelEngine/resource pack/{name}'] = path.read_bytes()
        entries['plugins/ElytrixFreakModel.jar'] = plugin
        entries['rp/Elytrix-RP-1.21.zip'] = merged.read_bytes()
        entries['plugins/ElytrixRP/config.yml'] = config.encode('utf-8')

        with zipfile.ZipFile(output, 'x') as package:
            for name in sorted(entries):
                info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                package.writestr(info, entries[name])

    print('package:', output)
    print('resource pack SHA-1:', pack_sha1)
    print('package SHA-256:', hashlib.sha256(output.read_bytes()).hexdigest())
    print('files:', len(entries))


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'elytrix-tentacles-v4.zip')
