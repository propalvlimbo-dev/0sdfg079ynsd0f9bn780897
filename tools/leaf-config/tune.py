#!/usr/bin/env python3
"""Narrow, reversible Leaf 1.21.11 configuration experiment."""
import argparse, difflib, os, re, shutil, stat, sys, tempfile
from pathlib import Path

SETTINGS={('async','async-chunk-send','enabled'):'true',('async','async-mob-spawning','enabled'):'true',('performance','optimize-block-entities'):'true'}
def transform(src):
 lines=src.splitlines(keepends=True); stack=[]; found={}; version=[]
 pattern=re.compile(r'^( *)([a-zA-Z0-9_.-]+):(?:[ \t]*(.*?))?(\r?\n)?$')
 for i,line in enumerate(lines):
  match=pattern.match(line)
  if not match:continue
  indent=len(match.group(1)); key=match.group(2); raw=match.group(3) or ''
  while stack and stack[-1][0]>=indent:stack.pop()
  path=tuple(x[1] for x in stack)+(key,)
  if path==('config-version',): version.append(raw.strip().strip("'\""))
  if path in SETTINGS:
   found.setdefault(path,[]).append(i)
   m=re.fullmatch(r'(true|false)([ \t]*(?:#.*)?)',raw)
   if not m: raise ValueError('unexpected boolean '+'.'.join(path))
   nl=match.group(4) or ''; lines[i]=match.group(1)+key+': '+SETTINGS[path]+m.group(2)+nl
  if not raw or raw.startswith('#'): stack.append((indent,key))
 if version != ['3.0']:raise ValueError('expected Leaf config-version 3.0')
 for path in SETTINGS:
  if len(found.get(path,[]))!=1:raise ValueError('missing or duplicate '+'.'.join(path))
 return ''.join(lines)

def main():
 p=argparse.ArgumentParser();p.add_argument('server',type=Path);p.add_argument('--apply',action='store_true');p.add_argument('--stopped',action='store_true');a=p.parse_args()
 root=a.server.resolve(strict=True); path=root/'config'/'leaf-global.yml'
 if path.is_symlink() or not path.is_file():raise ValueError('expected regular leaf-global.yml')
 if a.apply and not a.stopped:raise ValueError('confirm test server stopped with --stopped')
 old=path.read_text(encoding='utf8');new=transform(old)
 print(''.join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),fromfile=str(path),tofile='leaf-config-proposed')))
 print('async mob spawning additionally requires Paper per-player-mob-spawns=true, including world overrides.')
 if not a.apply:print('Preview only. No changes.');return
 if new==old:print('Already set; no changes.');return
 back=root/'elytrix-config-backups';
 if back.is_symlink():raise ValueError('backup directory is a symlink')
 back.mkdir(mode=0o700,exist_ok=True);os.chmod(back,0o700);d=Path(tempfile.mkdtemp(prefix='leaf-',dir=back));shutil.copy2(path,d/'leaf-global.yml');os.chmod(d/'leaf-global.yml',0o600)
 fd,tmp=tempfile.mkstemp(prefix='.leaf-tune-',dir=path.parent)
 try:
  info=path.stat();os.fchmod(fd,stat.S_IMODE(info.st_mode))
  if os.geteuid()==0:os.fchown(fd,info.st_uid,info.st_gid)
  with os.fdopen(fd,'w',encoding='utf8',newline='') as f:f.write(new);f.flush();os.fsync(f.fileno())
  if path.read_text(encoding='utf8')!=old:raise ValueError('file changed during staging')
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
 print('Backup:',d)
if __name__=='__main__':
 try:main()
 except (OSError,ValueError) as e:print('REFUSED:',e,file=sys.stderr);sys.exit(1)
