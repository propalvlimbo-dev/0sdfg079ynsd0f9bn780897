#!/usr/bin/env python3
"""Install a narrow experimental DivineMC #30 early chat executor workaround."""
import argparse, hashlib, os, re, shlex, stat, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
import core_safety
HERE=Path(__file__).resolve().parent
CORE_SHA='505f6afd69ef2b555977dbfa7c37ea10988511531c8ca1bde1b35b88b3241f79'
AGENT_SHA='04b63aa3b5dffd6dcb6bee6b98c33cda1d8684aad3d5b2ea79bcb7b9ef80be71'
def sha(x):return hashlib.sha256(x).hexdigest()
def regular(p):
 for x in [p,*p.parents]:
  if x.is_symlink():raise ValueError('symlink in path: '+str(x))
 if not p.is_file():raise ValueError('required file missing: '+str(p))
 return p

def atomic(path,data,info,mode=None):
 fd,tmp=tempfile.mkstemp(prefix='.divine-chat-fix-',dir=path.parent)
 try:
  os.fchmod(fd,stat.S_IMODE(info.st_mode) if mode is None else mode)
  if os.geteuid()==0:os.fchown(fd,info.st_uid,info.st_gid)
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def install(root,backup_root):
 root=root.resolve(strict=True);backup_root=backup_root.resolve(strict=True)
 if not root.is_dir() or not backup_root.is_dir() or backup_root==root or backup_root.is_relative_to(root):raise ValueError('backup dir must be outside server directory')
 if re.search(r'\s',str(root)):raise ValueError('unsupported whitespace in server path')
 core_safety.check_stopped(root)
 jar=regular(root/'server.jar');start=regular(root/'start.sh');agent=root/'elytrix-divine-chat-fix.jar'
 if sha(jar.read_bytes())!=CORE_SHA:raise ValueError('server.jar is not the exact official DivineMC 1.21.11 #30 build; no files changed')
 if agent.exists() or agent.is_symlink():raise ValueError('agent file already exists; refusing to overwrite')
 patch=regular(HERE/'elytrix-divine-chat-agent.jar').read_bytes()
 if sha(patch)!=AGENT_SHA:raise ValueError('agent SHA-256 mismatch')
 old=start.read_bytes();text=old.decode('utf8')
 if '-javaagent:' in text and 'elytrix-divine-chat' in text:raise ValueError('workaround already present in start.sh')
 pattern=r'(?m)^([ \t]*java[ \t]*\\)(\r?\n)'
 matches=list(re.finditer(pattern,text))
 if len(matches)!=1:raise ValueError('start.sh is not the expected restart script; no files changed')
 m=matches[0];nl=m.group(2);insert='    -javaagent:'+str(agent)+' \\'+nl
 new=(text[:m.end()]+insert+text[m.end():]).encode('utf8')
 backup=backup_root/('divine-chat-fix-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));backup.mkdir(mode=0o700)
 saved=backup/'start.sh';saved.write_bytes(old);saved.chmod(0o600)
 if saved.read_bytes()!=old:raise ValueError('backup failed')
 (backup/'installed-start.sha256').write_text(sha(new)+'\n');(backup/'installed-start.sha256').chmod(0o600)
 info=start.stat();done=False
 try:
  core_safety.check_stopped(root)
  if start.is_symlink() or start.read_bytes()!=old or agent.exists() or agent.is_symlink():raise ValueError('file changed during preparation')
  atomic(agent,patch,info,0o644);done=True
  atomic(start,new,info)
 except BaseException:
  if done:agent.unlink(missing_ok=True)
  print('Installation failed; start.sh backup:',saved,file=sys.stderr);raise
 print('Experimental early-chat fix installed; original start.sh backup:',saved)
 print('Server remains stopped. Start using start.sh; look for [Elytrix early-chat-fix] disabled virtual threads before server construction')
 cmd=[sys.executable,str(HERE/'install.py'),str(root),str(backup),'--stopped','--rollback']
 print('Rollback command (stop server and wrapper first):',shlex.join(cmd))

def rollback(root,backup):
 root=root.resolve(strict=True);backup=backup.resolve(strict=True)
 core_safety.check_stopped(root)
 start=regular(root/'start.sh');agent=regular(root/'elytrix-divine-chat-fix.jar');old=regular(backup/'start.sh').read_bytes()
 expected=regular(backup/'installed-start.sha256').read_text().strip()
 if sha(start.read_bytes())!=expected or sha(agent.read_bytes())!=AGENT_SHA:raise ValueError('start.sh or agent changed since installation; manual restore required')
 info=start.stat();atomic(start,old,info);agent.unlink();print('Original start.sh restored; agent removed. Server remains stopped.')

def main():
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('backup',type=Path);p.add_argument('--stopped',action='store_true');p.add_argument('--backed-up',action='store_true');p.add_argument('--rollback',action='store_true');a=p.parse_args()
 if not a.stopped or (not a.rollback and not a.backed_up):raise ValueError('confirm stopped server, stopped restart loop, and complete backup')
 (rollback if a.rollback else install)(a.root,a.backup)
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,UnicodeError) as e:print('REFUSED:',e,file=sys.stderr);sys.exit(1)
