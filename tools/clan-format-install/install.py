#!/usr/bin/env python3
"""Narrow NClans display-format update, does not alter clans or player data."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import core_safety
from rewrite import rewrite


def install(root, backup_root):
    root=root.resolve(strict=True); backup_root=backup_root.resolve(strict=True)
    if not root.is_dir() or not backup_root.is_dir() or backup_root==root or backup_root.is_relative_to(root):
        raise ValueError('backup directory must exist outside server directory')
    path=root
    for part in ('plugins','NClans','config.yml'):
        path=path/part
        if path.is_symlink(): raise ValueError('symlink in config path: '+str(path))
    if not path.is_file():raise ValueError('NClans config missing')
    core_safety.check_stopped(root)
    old=path.read_bytes();new=rewrite(old)
    if new==old:
        print('clanNameFormat already %clan%; no changes')
        return
    info=path.stat()
    backup=backup_root/('nclans-format-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(mode=0o700);backupfile=backup/'config.yml'
    # Config may contain secrets; keep private and do not expose it in output.
    with backupfile.open('xb') as out:
        os.fchmod(out.fileno(),0o600);out.write(old);out.flush();os.fsync(out.fileno())
    if backupfile.read_bytes()!=old:raise ValueError('backup verification failed')
    fd,tmp=tempfile.mkstemp(prefix='.nclans-format-',dir=path.parent)
    try:
        os.fchmod(fd,stat.S_IMODE(info.st_mode))
        if os.geteuid()==0:os.fchown(fd,info.st_uid,info.st_gid)
        with os.fdopen(fd,'wb') as out:
            out.write(new);out.flush();os.fsync(out.fileno())
        core_safety.check_stopped(root)
        if path.is_symlink() or path.read_bytes()!=old:raise ValueError('config changed; refusing')
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    print('Changed clanNameFormat only. Original config saved privately:',backupfile)
    print('No player or clan databases were touched. Restart the server and verify TAB.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path);parser.add_argument('backup',type=Path)
    parser.add_argument('--stopped',action='store_true');parser.add_argument('--backed-up',action='store_true')
    a=parser.parse_args()
    if not (a.stopped and a.backed_up):raise ValueError('confirm --stopped and --backed-up')
    install(a.root,a.backup)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError) as e:print('REFUSED:',e,file=sys.stderr);sys.exit(1)
