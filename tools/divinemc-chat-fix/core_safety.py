#!/usr/bin/env python3
"""Install only DivineMC #30 and a conservative first-run config, never plugins."""
import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

URL = 'https://files.bxteam.org/divinemc/versions/1.21.11/30/divinemc-1.21.11-30.jar'
SIZE = 68614411
SHA256 = '505f6afd69ef2b555977dbfa7c37ea10988511531c8ca1bde1b35b88b3241f79'
CONFIG_SHA256 = 'f99f75e25fe118ca9d71d4b2718ce86694a0f80d00de74ef47119a19f57658b8'
CONFIG = Path(__file__).resolve().with_name('divinemc.yml')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def check_stopped(root):
    proc = Path('/proc')
    if not proc.is_dir():
        raise ValueError('/proc unavailable; cannot check for server process')
    for pid in proc.iterdir():
        if not pid.name.isdecimal() or int(pid.name) == os.getpid():
            continue
        try:
            cwd = (pid / 'cwd').resolve(strict=True)
            args = (pid / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            raise ValueError('cannot inspect processes; run as root on the VDS')
        if cwd != root or not args or not args[0]:
            continue
        exe = Path(os.fsdecode(args[0])).name
        if (exe.startswith('java') and (b'-jar' in args or any(b'net.minecraft' in a for a in args))) or any(Path(os.fsdecode(a)).name == 'start.sh' for a in args[1:] if a):
            raise ValueError('server or start.sh restart loop appears active (PID ' + pid.name + ')')


def download(target):
    h = hashlib.sha256()
    size = 0
    request = urllib.request.Request(URL, headers={'User-Agent': 'Elytrix-DivineMC-install/1'})
    with urllib.request.urlopen(request, timeout=120) as response, target.open('xb') as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > SIZE:
                raise ValueError('download is larger than the published artifact')
            h.update(chunk)
            out.write(chunk)
        out.flush()
        os.fsync(out.fileno())
    if size != SIZE or h.hexdigest() != SHA256:
        raise ValueError('DivineMC download size or SHA-256 mismatch')
    with zipfile.ZipFile(target) as jar:
        if jar.testzip() is not None or 'META-INF/MANIFEST.MF' not in jar.namelist():
            raise ValueError('invalid server JAR')


def atomic_bytes(path, contents, mode, owner):
    fd, tmp = tempfile.mkstemp(prefix='.elytrix-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        if os.geteuid() == 0:
            os.fchown(fd, owner.st_uid, owner.st_gid)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def install(root, backup_base):
    root = root.resolve(strict=True)
    backup_base = backup_base.resolve(strict=True)
    if not root.is_dir() or not backup_base.is_dir() or backup_base == root or backup_base.is_relative_to(root):
        raise ValueError('backup directory must exist outside server directory')
    jar, config = root / 'server.jar', root / 'divinemc.yml'
    if jar.is_symlink() or not jar.is_file():
        raise ValueError('server.jar is missing or a symlink')
    if config.exists() or config.is_symlink():
        raise ValueError('divinemc.yml already exists: refusing to overwrite it')
    if digest(CONFIG) != CONFIG_SHA256:
        raise ValueError('baseline config SHA-256 mismatch')
    check_stopped(root)
    before = digest(jar)
    info = jar.stat()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = backup_base / ('divinemc-core-' + stamp)
    backup.mkdir(mode=0o700)
    try:
        # In addition to (not instead of) the operator's full backup.
        saved = backup / 'server.jar'
        shutil.copy2(jar, saved)
        if digest(saved) != before:
            raise ValueError('failed to verify original server.jar backup')
        candidate = backup / 'divinemc-download.jar'
        print('Downloading official DivineMC 1.21.11 #30...', flush=True)
        download(candidate)
        check_stopped(root)
        if digest(jar) != before or config.exists() or config.is_symlink():
            raise ValueError('server.jar or divinemc.yml changed during download')
        # Create config exclusively. The server must remain stopped throughout.
        fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IMODE(info.st_mode) & 0o666)
        try:
            if os.geteuid() == 0:
                os.fchown(fd, info.st_uid, info.st_gid)
            with os.fdopen(fd, 'wb') as out:
                out.write(CONFIG.read_bytes())
                out.flush()
                os.fsync(out.fileno())
            try:
                check_stopped(root)
                if digest(jar) != before:
                    raise ValueError('server.jar changed during installation')
                atomic_bytes(jar, candidate.read_bytes(), stat.S_IMODE(info.st_mode), info)
            except BaseException:
                config.unlink(missing_ok=True)
                raise
        except BaseException:
            config.unlink(missing_ok=True)
            raise
        candidate.unlink()
    except BaseException:
        print('Installation stopped; original core backup, if created:', backup, file=sys.stderr)
        raise
    print('Installed DivineMC 1.21.11 #30; SHA-256:', digest(jar))
    print('Prior server.jar saved:', saved)
    print('Created divinemc.yml. Other configs, plugins, worlds, databases and RP untouched.')
    print('Server not started. Check all plugins and PvP; this does not fix previous issues.')


def main():
    p = argparse.ArgumentParser(description='Install DivineMC core and baseline ONLY.')
    p.add_argument('root', type=Path)
    p.add_argument('backup_dir', type=Path)
    p.add_argument('--stopped', action='store_true', help='server AND all restart wrappers manually stopped')
    p.add_argument('--backed-up', action='store_true', help='complete fresh backup including external databases made')
    args = p.parse_args()
    if not args.stopped or not args.backed_up:
        raise ValueError('--stopped and --backed-up confirmations are required')
    install(args.root, args.backup_dir)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.SubprocessError) as err:
        print('REFUSED:', err, file=sys.stderr)
        sys.exit(1)
