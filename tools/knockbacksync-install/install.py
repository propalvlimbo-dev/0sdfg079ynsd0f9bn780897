#!/usr/bin/env python3
"""Pinned upstream KnockbackSync full jar installer, independent of the core installer."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import urllib.request
import zipfile

URL = 'https://cdn.modrinth.com/data/wGTbjSTq/versions/ydVLBRzX/knockbacksync-bukkit-1.3.6-dev-b143.jar'
SHA512 = '1176d788003f6a58593d6e172e406a6f24e7a730c71068a888ea71934816ea4ac6bd5b7ad4d2cf9de95f6824aba9bca516922e35c540bcc64973c71f7a828a5f'
SIZE = 11832714
FILENAME = 'knockbacksync-bukkit-1.3.6-dev-b143.jar'
PLUGIN = re.compile(r'''(?mi)^name:\s*["']?([^\s"'#]+)''')

# Reuse the same conservative /proc inspection as the DivineMC core installer.
spec = importlib.util.spec_from_file_location('divine_safety', Path(__file__).with_name('core_safety.py'))
safety = importlib.util.module_from_spec(spec)
spec.loader.exec_module(safety)


def plugin_name(z):
    found=[]
    for entry in ('plugin.yml','paper-plugin.yml'):
        if entry in z.namelist():
            info = z.getinfo(entry)
            if info.file_size > 256*1024: raise ValueError('plugin descriptor too large')
            match=PLUGIN.search(z.read(entry).decode('utf-8'))
            if match: found.append(match.group(1).casefold())
    return found


def check_directory(plugins):
    for p in plugins.glob('*.jar'):
        if p.is_symlink(): raise ValueError('plugin jar is a symlink: '+p.name)
        try:
            with zipfile.ZipFile(p) as z:
                if 'knockbacksync' in plugin_name(z):
                    raise ValueError('KnockbackSync already installed as '+p.name+'; refusing duplicates')
        except (zipfile.BadZipFile, UnicodeDecodeError) as e:
            raise ValueError('cannot inspect plugin '+p.name) from e


def fetch(target):
    h=hashlib.sha512(); size=0
    req=urllib.request.Request(URL,headers={'User-Agent':'Elytrix-KnockbackSync-installer/1'})
    with urllib.request.urlopen(req, timeout=120) as inp, target.open('xb') as out:
        while True:
            chunk=inp.read(1024*1024)
            if not chunk: break
            size+=len(chunk)
            if size > SIZE: raise ValueError('download exceeds published size')
            h.update(chunk);out.write(chunk)
        out.flush();os.fsync(out.fileno())
    if size != SIZE or h.hexdigest() != SHA512: raise ValueError('download size or SHA-512 mismatch')
    with zipfile.ZipFile(target) as z:
        if z.testzip() is not None or 'knockbacksync' not in plugin_name(z): raise ValueError('unexpected plugin jar')
        if 'me/caseload/knockbacksync/BukkitLoaderPlugin.class' not in z.namelist(): raise ValueError('missing upstream Bukkit entry point')


def install(root):
    root=root.resolve(strict=True); plugins=root/'plugins'; jar=root/'server.jar'
    if not root.is_dir() or plugins.is_symlink() or not plugins.is_dir() or jar.is_symlink() or not jar.is_file():
        raise ValueError('expected server.jar and non-symlink plugins directory')
    safety.check_stopped(root);check_directory(plugins)
    dest=plugins/FILENAME
    if dest.exists() or dest.is_symlink(): raise ValueError('destination already exists')
    if (plugins/'KnockbackSync').is_symlink(): raise ValueError('KnockbackSync config directory is a symlink')
    fd,tmpname=tempfile.mkstemp(prefix='.knockbacksync-',suffix='.tmp',dir=plugins);os.close(fd);os.unlink(tmpname)
    tmp=Path(tmpname)
    try:
        print('Downloading upstream KnockbackSync 1.3.6-dev-b143 (alpha)...',flush=True)
        fetch(tmp)
        info=jar.stat();os.chmod(tmp,stat.S_IMODE(info.st_mode) & 0o666)
        if os.geteuid()==0:os.chown(tmp,info.st_uid,info.st_gid)
        safety.check_stopped(root);check_directory(plugins)
        # A hard link creates the final name exclusively; never replaces an existing plugin.
        os.link(tmp,dest)
    finally:
        tmp.unlink(missing_ok=True)
    print('Installed:',dest)
    print('Existing config not touched. The server was not started.')
    print('ALPHA: combat and anticheat interaction have not been tested; verify on startup and in PvP.')


def main():
    p=argparse.ArgumentParser(description='Install upstream KnockbackSync only (alpha, untested PvP compatibility).')
    p.add_argument('root',type=Path);p.add_argument('--stopped',action='store_true');p.add_argument('--backed-up',action='store_true')
    a=p.parse_args()
    if not (a.stopped and a.backed_up):raise ValueError('--stopped and --backed-up confirmations required')
    install(a.root)

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,zipfile.BadZipFile,UnicodeDecodeError) as e:print('REFUSED:',e,file=sys.stderr);sys.exit(1)
