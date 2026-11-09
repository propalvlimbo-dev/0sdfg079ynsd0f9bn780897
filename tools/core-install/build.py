#!/usr/bin/env python3
"""Stamps the plugin hash into install.sh and builds elytrix-leaf-1.21.11.zip.

The installer refuses to run when the jar in the package does not match
PLUGIN_SHA, and that constant is easy to forget when the plugin is rebuilt (v24
and v25 shipped a package that would have stopped with "jar повреждён").  This
script makes the two impossible to drift: it always rewrites the constant from
the jar that is actually being packaged.

Usage: python3 tools/core-install/build.py [output.zip]
"""
import hashlib
import re
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'elytrix-leaf-1.21.11.zip'
JAR = HERE / 'plugins/ElytrixFreakModel.jar'
ITEMS = ('install.sh', 'start.sh', 'rollback.sh', 'README.md', 'files', 'plugins', 'rp')
# Every ModelEngine model the server needs; its bones and texture are generated
# by tools/accessories-model/build_modelengine_assets.py.
MODELS = ('elytrix_kaneki_tentacles', 'elytrix_centipede')
MODELS_SRC = ROOT / 'tools/accessories-model'


def sync_models():
    """Makes plugins/ModelEngine an exact copy of tools/accessories-model.

    The core package carries the accessory models itself, so it silently drifted
    from the sources twice: it kept the retired mask and never got the centipede
    (which is why the animal had no texture and never rendered).  Rebuilding the
    package now re-copies the blueprints and regenerates the asset tree, and any
    blueprint the sources no longer contain is deleted.
    """
    target = HERE / 'plugins' / 'ModelEngine'
    blueprints = target / 'blueprints'
    blueprints.mkdir(parents=True, exist_ok=True)
    for path in sorted(blueprints.glob('*.bbmodel')):
        if path.stem not in MODELS:
            path.unlink()
            print(f'blueprint removed: {path.name}')
    for model in MODELS:
        shutil.copyfile(MODELS_SRC / f'{model}.bbmodel', blueprints / f'{model}.bbmodel')
    assets = target / 'resource pack' / 'assets'
    if assets.exists():
        shutil.rmtree(assets)
    shutil.copytree(MODELS_SRC / 'assets', assets)
    files = sum(1 for path in assets.rglob('*') if path.is_file())
    print(f'ModelEngine synced: {len(MODELS)} blueprints, {files} asset files')


def main():
    sync_models()
    digest = hashlib.sha256(JAR.read_bytes()).hexdigest()
    install = HERE / 'install.sh'
    text = install.read_text(encoding='utf-8')
    text, count = re.subn(r'(?m)^PLUGIN_SHA="[0-9a-f]{64}"$', f'PLUGIN_SHA="{digest}"', text)
    if count != 1:
        raise SystemExit('PLUGIN_SHA line not found exactly once in install.sh')
    install.write_text(text, encoding='utf-8')
    print(f'plugins/ElytrixFreakModel.jar sha256 {digest}')
    print(f'install.sh PLUGIN_SHA stamped')

    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as archive:
        for item in ITEMS:
            path = HERE / item
            if path.is_dir():
                for file in sorted(path.rglob('*')):
                    if file.is_file():
                        archive.write(file, file.relative_to(HERE).as_posix())
            elif path.is_file():
                archive.write(path, item)
    print(f'package {OUT} ({OUT.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
