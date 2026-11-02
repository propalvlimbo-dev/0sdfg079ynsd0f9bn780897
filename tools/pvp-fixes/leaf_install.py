#!/usr/bin/env python3
"""Core-only Leaf 1.21.11 #179 installer; not a complete Elytrix fix."""
import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

URL = 'https://github.com/Winds-Studio/Leaf/releases/download/ver-1.21.11/leaf-1.21.11-179.jar'
SHA256 = '5da79782215c1a25edcd7c73b3523b7ecb7f4b86dc8a5846a176ed69bc2cd020'
SIZE = 83953995

def check_stopped(root):
    """Reject known server and restart-wrapper processes. Manual stop still required."""
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal() or int(proc.name)==os.getpid(): continue
        try:
            cwd=(proc/'cwd').resolve(strict=True)
            args=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        except (OSError, PermissionError):
            continue
        if cwd==root and (('java' in Path(args.split(' ')[0]).name and ('-jar' in args or 'net.minecraft' in args)) or 'start.sh' in args):
            raise RuntimeError('server/restart wrapper appears to be running (PID '+proc.name+'); stop it first')

def fetch_leaf(target):
    digest=hashlib.sha256(); size=0
    with urllib.request.urlopen(urllib.request.Request(URL,headers={'User-Agent':'Elytrix-stage-installer/1'}),timeout=90) as inp, target.open('xb') as out:
        while True:
            b=inp.read(1024*1024)
            if not b:break
            size+=len(b)
            if size>SIZE: raise ValueError('Leaf download exceeds expected size')
            digest.update(b); out.write(b)
        out.flush(); os.fsync(out.fileno())
    if size!=SIZE or digest.hexdigest()!=SHA256: raise ValueError('Leaf SHA256/size mismatch; not installed')

def main():
    p=argparse.ArgumentParser(description='Leaf core ONLY; does not fix plugins or tune configs.')
    p.add_argument('server',type=Path); p.add_argument('backup_directory',type=Path)
    p.add_argument('--apply',action='store_true'); p.add_argument('--i-stopped-server-and-restart-loop',action='store_true')
    p.add_argument('--i-backed-up-external-data',action='store_true'); p.add_argument('--i-understand-world-upgrade',action='store_true')
    a=p.parse_args(); root=a.server.resolve(strict=True); backup=a.backup_directory.resolve(strict=True)
    jar=root/'server.jar'
    if not root.is_dir() or not backup.is_dir() or backup==root or backup.is_relative_to(root): raise ValueError('backup directory must be outside the server')
    if jar.is_symlink() or not jar.is_file(): raise ValueError('server.jar must be a regular, non-symlink file')
    check_stopped(root)
    print('Leaf 1.21.11 #179:', URL, '\nSHA256:', SHA256)
    print('Core only. Plugin fixes and config tuning are NOT included. First startup upgrades world data.')
    if not a.apply:
        print('Preflight only: no changes made.')
        return
    if not (a.i_stopped_server_and_restart_loop and a.i_backed_up_external_data and a.i_understand_world_upgrade):
        raise ValueError('all three explicit confirmations are required')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    image=backup/('elytrix-before-leaf-'+stamp+'.tar')
    # Do not follow links into external data: those must be backed up separately.
    symlinks=[p for p in root.rglob('*') if p.is_symlink()]
    if symlinks: raise ValueError('symlink in server tree; back up external targets and resolve manually: '+str(symlinks[0]))
    with tempfile.TemporaryDirectory(prefix='elytrix-leaf-',dir=backup) as td:
        leaf=Path(td)/'leaf.jar'; fetch_leaf(leaf)
        check_stopped(root)
        print('Saving complete server directory to',image,flush=True)
        # Configs and databases may contain secrets. Create the archive privately.
        fd = os.open(image, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        subprocess.run(['tar','--create','--file',str(image),'-C',str(root.parent),root.name],check=True)
        subprocess.run(['tar','--list','--file',str(image)],stdout=subprocess.DEVNULL,check=True)
        check_stopped(root)
        fd, tmp = tempfile.mkstemp(prefix='.server-leaf-',dir=root)
        try:
            with os.fdopen(fd,'wb') as out,leaf.open('rb') as inp:
                shutil.copyfileobj(inp,out); out.flush(); os.fsync(out.fileno())
            info = jar.stat()
            os.chmod(tmp,info.st_mode & 0o777)
            if os.geteuid() == 0: os.chown(tmp,info.st_uid,info.st_gid)
            os.replace(tmp,jar)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
    print('server.jar replaced. Backup:',image)
    print('Nothing was started. Worlds changed by Leaf require restoring the whole pre-upgrade backup to roll back.')

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError) as e:
        print('REFUSED:',e,file=sys.stderr);sys.exit(1)
