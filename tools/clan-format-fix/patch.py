#!/usr/bin/env python3
"""Propose or apply a narrow NClans change to an isolated config; never production."""
import argparse
import os
from pathlib import Path
import re
import tempfile

# Only the known original or desired values are accepted; no YAML rewrite.
LINE = re.compile(rb'^(clanNameFormat:[ \t]*)(["\'])([^"\'\r\n]*)(\2)([ \t]*(?:#[^\r\n]*)?)(\r?\n|$)', re.MULTILINE)
OLD=b'&8[%clan%&8]'; NEW=b'%clan%'

def rewrite(raw):
    # Detect even malformed/duplicate top-level entries, not just matching values.
    keys = list(re.finditer(rb'^clanNameFormat[ \t]*:',raw,re.MULTILINE))
    matches=list(LINE.finditer(raw))
    if len(keys)!=1 or len(matches)!=1: raise ValueError('Expected exactly one simple clanNameFormat')
    m=matches[0]; value=m.group(3)
    if value==NEW: return raw
    if value!=OLD: raise ValueError('Unknown format; manual review required')
    return raw[:m.start(3)]+NEW+raw[m.end(3):]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config',type=Path); parser.add_argument('--apply',action='store_true')
    args=parser.parse_args(); path=args.config
    if path.is_symlink() or not path.is_file(): raise SystemExit('Expected regular config, not a symlink')
    resolved=path.resolve()
    if resolved.is_relative_to(Path('/root/RW_GRIEF')): raise SystemExit('Production path forbidden; use an offline isolated copy')
    old=path.read_bytes()
    try: new=rewrite(old)
    except ValueError as e: raise SystemExit(str(e))
    if new==old: print('Already set to %clan%; no changes'); return
    if not args.apply: print('Would change clanNameFormat only to %clan%; dry-run'); return
    # Caller must back up the isolated copy first. Preserve mode and do not truncate in-place.
    fd,tmp=tempfile.mkstemp(prefix='.nclans-',dir=path.parent)
    try:
        os.fchmod(fd, path.stat().st_mode & 0o777)
        with os.fdopen(fd,'wb') as f: f.write(new); f.flush(); os.fsync(f.fileno())
        if path.read_bytes()!=old: raise SystemExit('Config changed during operation; refusing')
        os.replace(tmp,path)
        print('Changed clanNameFormat in isolated copy; restart plugin via full server restart')
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
if __name__=='__main__': main()
