#!/usr/bin/env python3
"""Build the deployment archive `elytrix-freakmodel.zip` (v3.23.0) straight from the repository.

Contents (see AI_INSTRUCTIONS.txt, section 8, step 5):
  * plugins/ElytrixFreakModel.jar          (+ plugins/ElytrixFreakModel/config.yml)
  * plugins/ElytrixRP.jar                  (+ plugins/ElytrixRP/config.yml)
  * plugins/ModelEngine-4.1.0.jar
  * plugins/ModelEngine/blueprints/*.bbmodel
  * plugins/ModelEngine/resource pack/**   (ModelEngine's generated pack: elytrix models,
                                            the patched FPV shaders and the pack metadata)
  * rp/Elytrix-RP-1.21.zip

Deliberately NEVER shipped (they live on the VDS and must not be clobbered):
  * plugins/ModelEngine/config.yml
  * any `.data/cache.json`
  * owned_accessories.yml / databases
"""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'elytrix-freakmodel.zip'

RP_PACK = ROOT / 'plugins/ModelEngine/resource pack'

TOP_FILES = [
    'plugins/ElytrixFreakModel.jar',
    'plugins/ElytrixFreakModel/config.yml',
    'plugins/ElytrixRP.jar',
    'plugins/ElytrixRP/config.yml',
    'plugins/ModelEngine-4.1.0.jar',
    'rp/Elytrix-RP-1.21.zip',
]

FORBIDDEN_SUBSTRINGS = (
    'ModelEngine/config.yml',
    '.data/cache.json',
    'owned_accessories.yml',
)

FIXED_DATE = (2020, 1, 1, 0, 0, 0)


def collect():
    entries = []
    for rel in TOP_FILES:
        p = ROOT / rel
        if not p.is_file():
            raise SystemExit('missing required file: ' + rel)
        entries.append((rel, p))

    blueprints = sorted((ROOT / 'plugins/ModelEngine/blueprints').glob('*.bbmodel'))
    if not blueprints:
        raise SystemExit('no blueprints found')
    for p in blueprints:
        entries.append(('plugins/ModelEngine/blueprints/' + p.name, p))

    if not RP_PACK.is_dir():
        raise SystemExit('missing ModelEngine resource pack')
    for p in sorted(RP_PACK.rglob('*')):
        if not p.is_file():
            continue
        rel = 'plugins/ModelEngine/resource pack/' + p.relative_to(RP_PACK).as_posix()
        if any(bad in rel for bad in FORBIDDEN_SUBSTRINGS):
            continue
        entries.append((rel, p))
    return entries


def main():
    entries = collect()
    seen = set()
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rel, src in entries:
            if rel in seen:
                continue
            seen.add(rel)
            info = zipfile.ZipInfo(rel, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, src.read_bytes())
    size = OUT.stat().st_size
    sha1 = hashlib.sha1(OUT.read_bytes()).hexdigest()
    sha256 = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print('files: %d' % len(seen))
    print('size:  %d' % size)
    print('sha1:  %s' % sha1)
    print('sha256:%s' % sha256)


if __name__ == '__main__':
    sys.exit(main())
