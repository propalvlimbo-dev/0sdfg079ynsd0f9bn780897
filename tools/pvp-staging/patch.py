#!/usr/bin/env python3
"""Small, hash-guarded staging-only config patch. Python 3 stdlib only."""
import argparse
import difflib
import hashlib
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone

CLAN = 'plugins/NClans/config.yml'
SHOP = 'plugins/DeluxeMenus/gui_menus/shop/endshop.yml'
FREE = 'plugins/ElytrixFree/gui.yml'
NERUM = 'plugins/nKits/Kits/nerum.yml'
EXPECTED = {
    CLAN: '168927783849a7666afb37818deed50d4952cdbfe64e4f4f116f327934c3a8e5',
    SHOP: 'e06e5bf06f572a68864c50e7b43fa0e93c981a5a590b59e9f2c9e04b69376101',
    FREE: 'e3a579bfe5f7b058e4af8642c5911a4931679cbece3f9a4432953597ee461390',
    NERUM: 'e2fbc5a0d662d2d5ac46e247e7f552edbdfd69d0b6c48ce9b35f5beda40e94b4',
}

def once(s, old, new):
    if s.count(old) != 1:
        raise ValueError('expected exactly one occurrence: ' + repr(old))
    return s.replace(old, new, 1)

def transform(files):
    changed = dict(files)
    changed[CLAN] = once(files[CLAN], 'clanNameFormat: "&8[%clan%&8]"', 'clanNameFormat: "%clan%"')
    # This lore belongs to the Strannik helmet; kit is independently checked below.
    changed[SHOP] = once(files[SHOP], "    - '&r&#aaaaaaЗащита V&r'", "    - '&r&#aaaaaaЗащита IV&r'")
    if files[NERUM].count('PROTECTION_ENVIRONMENTAL: 4') != 1:
        raise ValueError('nerum helmet is not Protection IV; inspect the live kit manually')
    pattern = r'(?ms)^(  free5:\n)(.*?)(?=^  free6:\n)'
    match = re.search(pattern, files[FREE])
    if not match:
        raise ValueError('free5/free6 structure not recognized')
    block = match.group(0)
    block = once(block, "      - '&#F8BEFB&l┃  &7• &fКейс с рилликами &7(x1)'", "      - '&#F8BEFB&l┃  &7• &fКейс с наборами &7(x1)'\n      - '&#F8BEFB&l┃  &7• &fКейс с донатом &7(x2)'\n      - '&#F8BEFB&l┃  &7• &#F8BEFB300 рилликов &fꐃ'")
    block = once(block, "      - 'bcases give {player} rilik 1'", "      - 'bcases give {player} kits 1'\n      - 'bcases give {player} donate 2'\n      - 'p give {player} 300'")
    changed[FREE] = files[FREE][:match.start()] + block + files[FREE][match.end():]
    return {p: changed[p] for p in (CLAN, SHOP, FREE)}

def main():
    ap = argparse.ArgumentParser(description='Только тестовая копия сервера, не production.')
    ap.add_argument('server', type=Path, help='путь к изолированной копии сервера')
    ap.add_argument('--apply', action='store_true', help='применить после остановки тестового сервера')
    ap.add_argument('--stopped', action='store_true', help='подтверждение, что тестовый сервер остановлен')
    args = ap.parse_args()
    root = args.server.resolve(strict=True)
    # Do not allow accidentally running this limited, unfinished patch on the specified live path.
    if root == Path('/root/RW_GRIEF').resolve():
        raise ValueError('live server path is forbidden; use an isolated copy')
    if args.apply and not args.stopped:
        raise ValueError('--apply requires --stopped: stop the test server first')
    data = {}
    for rel, expected in EXPECTED.items():
        path = (root / rel).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError('path escapes test server: ' + rel)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('hash mismatch, refusing to patch: ' + rel)
        data[rel] = raw.decode('utf-8')
    updates = transform(data)
    for rel, new in updates.items():
        print(''.join(difflib.unified_diff(data[rel].splitlines(keepends=True), new.splitlines(keepends=True), fromfile=rel, tofile=rel+' (staging)')))
    if not args.apply:
        print('Предпросмотр: ничего не записано. На production не запускать.')
        return
    backup = root / ('pvp-staging-backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(mode=0o700)
    # Save every original before replacing any file.
    for rel in updates:
        dest = backup / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, dest)
    for rel, new in updates.items():
        path = root / rel
        fd, tmp = tempfile.mkstemp(prefix='.pvp-staging-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
                f.write(new)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, path.stat().st_mode & 0o777)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
    print('Оригиналы изменённых конфигов: ' + str(backup))

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, UnicodeError) as exc:
        print('ОТКАЗ: ' + str(exc), file=sys.stderr)
        sys.exit(1)
