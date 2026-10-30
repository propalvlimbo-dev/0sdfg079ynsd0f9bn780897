#!/usr/bin/env python3
"""Guarded partial plugin/config staging on an isolated server copy only."""
import argparse, difflib, hashlib, os, re, shutil, stat, sys, tempfile
from pathlib import Path
import free_preview

EXPECTED={
'plugins/CloudQuests.jar':'2f5a212549195ed362dc69f1afb572ecc1a7f6bdfd6cc272a9e2c07c29cd37fc',
'plugins/CloudEnchants.jar':'ce91ca2de7db60dfbd2d44a9adfa9f182394dea1cb61a4f2b0e09896e8241a9d',
'plugins/ElytrixRandomEgg.jar':'0cfb165df9074d5c0e9a6443b7985bc7c5d7f33272d9ae8262840250cbc0473b',
'plugins/DeluxeMenus/gui_menus/shop/spawners.yml':'e76a762a5a50c515e371df28ee6ff0373c974731c9de9893ce4fd0ab60a11770',
'plugins/DeluxeMenus/gui_menus/shop/endshop.yml':'e06e5bf06f572a68864c50e7b43fa0e93c981a5a590b59e9f2c9e04b69376101',
'plugins/ElytrixFree/gui.yml':'e3a579bfe5f7b058e4af8642c5911a4931679cbece3f9a4432953597ee461390',
'plugins/NClans/config.yml':'168927783849a7666afb37818deed50d4952cdbfe64e4f4f116f327934c3a8e5',
'plugins/nKits/Kits/nerum.yml':'e2fbc5a0d662d2d5ac46e247e7f552edbdfd69d0b6c48ce9b35f5beda40e94b4',
'plugins/EssentialsX-2.22.0.jar':'f276ab8d791ecd20fe8ce27861e537941b0bd76bfa5f33aad2cb87a0da1ad0bf',
'plugins/CakeSub-1.0-SNAPSHOT.jar':'a2181e3ef1dca46feb7e4c864d49a392b2f633ff70f300562992b7e911dc19cb',
'plugins/PlayerPoints-3.3.5.jar':'4b15ba1654463a3f7363dc3d9b7330d5675b800d55efe70631b32eed03669ac3',
'plugins/nKits-1.jar':'dbe87e3a3932468de0e5fea4b28279764c1c7565d1e8c1b4232b73dd7fa9e085',
'plugins/BCases.jar':'863998db61758100ee4f6307876658a7dca384a2fd4b86c9603a62bc34b75c11',
'plugins/ElytrixFree.jar':'1bb0d797c9546c750b9eb2c43a1c564cb2009ed614c41074798b77ae2739c376',
'plugins/DeluxeMenus-1.14.1-Release.jar':'3c2677d7f9312008c1f7ec106edca33ae382b9ae3041f59138509b8870d9db45',
}
NEW={
'plugins/CloudQuests.jar':'09497e03d490fbca5a34e25bf3d0f023a3748158b122e4b02ed4b713830ff2a8',
'plugins/CloudEnchants.jar':'cfb2760141543016de9a634c79a510cc62716f944d4c1d9c4b4cdfcef00bc242',
'plugins/ElytrixRandomEgg.jar':'e963a5ea3d020eb7c5666840bc0988db630854e18b8c7d46fdbb56c41f73e486',
'plugins/ElytrixGodPickup.jar':'4258370c512323798d51850ad80da36481fdc1f263c869dd013b04d24027af19',
}
SPAWNERS='plugins/DeluxeMenus/gui_menus/shop/spawners.yml'; END='plugins/DeluxeMenus/gui_menus/shop/endshop.yml'; CLAN='plugins/NClans/config.yml'; FREE='plugins/ElytrixFree/gui.yml'
old_egg="    - '[console] points take %player_name% 119'\n    - '[console] randomegg %player_name%'\n    - '[message] &#F8BEFBРиллики &7» &fУспешная покупка!'\n    - '[console] cashback give %player_name% 119'\n    - '[refresh]'"
new_egg="    - '[console] randomeggbuy %player_name%'\n    - '[refresh]'"
def sha(b):return hashlib.sha256(b).hexdigest()
def once(s,old,new):
 if s.count(old)!=1:raise ValueError('unexpected config structure')
 return s.replace(old,new,1)
def safe_path(root,rel):
 p=root
 for name in Path(rel).parts:
  p=p/name
  if p.is_symlink():raise ValueError('symlink not allowed: '+rel)
 if not p.resolve().is_relative_to(root):raise ValueError('path escapes root')
 return p

def changes(root,payload):
 original={}
 for rel,expected in EXPECTED.items():
  path=safe_path(root,rel)
  if not path.is_file():raise ValueError('missing file: '+rel)
  data=path.read_bytes()
  if sha(data)!=expected:raise ValueError('hash mismatch, no changes: '+rel)
  original[rel]=data
 if b'PROTECTION_ENVIRONMENTAL: 4' not in original['plugins/nKits/Kits/nerum.yml']:raise ValueError('unexpected nerum helmet')
 prizes=safe_path(root,'plugins/BCases/prizes.yml').read_text(encoding='utf8')
 for case in ('kits','donate','money'):
  if len(re.findall(r'(?m)^  '+case+r':\s*$',prizes))!=1:raise ValueError('missing or ambiguous case '+case)
 for kit in ('rabbit','hydra','cobra','god','angel','dragon'):
  if not safe_path(root,'plugins/nKits/Kits/'+kit+'.yml').is_file():raise ValueError('missing kit '+kit)
 for conflict in ('plugins/ElytrixGodPickup.jar','plugins/ElytrixGameplaySafety-test.jar','plugins/ElytrixGameplaySafety.jar'):
  if safe_path(root,conflict).exists():raise ValueError('conflicting plugin: '+conflict)
 updated={}
 for rel,digest in NEW.items():
  data=safe_path(payload,rel).read_bytes()
  if sha(data)!=digest:raise ValueError('invalid staged payload: '+rel)
  updated[rel]=data
 for rel in (SPAWNERS,END,CLAN,FREE):
  text=original[rel].decode('utf8')
  if rel==SPAWNERS:text=once(text,old_egg,new_egg)
  elif rel==END:text=once(text,"    - '&r&#aaaaaaЗащита V&r'","    - '&r&#aaaaaaЗащита IV&r'")
  elif rel==CLAN:text=once(text,'clanNameFormat: "&8[%clan%&8]"','clanNameFormat: "%clan%"')
  else:text=free_preview.rewrite(text)
  updated[rel]=text.encode('utf8')
 return original,updated

def stage(path,data,source=None):
 fd,name=tempfile.mkstemp(prefix='.elytrix-stage-',dir=path.parent)
 try:
  info=(source or path).stat();os.fchmod(fd,stat.S_IMODE(info.st_mode))
  if os.geteuid()==0:os.fchown(fd,info.st_uid,info.st_gid)
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  return Path(name)
 except BaseException:
  Path(name).unlink(missing_ok=True);raise

def main():
 p=argparse.ArgumentParser();p.add_argument('copy',type=Path);p.add_argument('--apply',action='store_true');p.add_argument('--stopped',action='store_true');a=p.parse_args()
 root=a.copy.resolve(strict=True);payload=Path(__file__).resolve().parent
 if root==Path('/root/RW_GRIEF').resolve():raise ValueError('live server forbidden; test on isolated copy')
 if a.apply and not a.stopped:raise ValueError('--stopped confirmation required')
 original,updated=changes(root,payload)
 for rel,data in updated.items():
  if rel in (SPAWNERS,END,CLAN,FREE):
   print(''.join(difflib.unified_diff(original[rel].decode().splitlines(keepends=True),data.decode().splitlines(keepends=True),fromfile=rel,tofile=rel+' (staging)')))
  else:print('TEST JAR:',rel)
 if not a.apply:print('Preview only; no files changed. Ender migration and Leaf tuning not included.');return
 backupbase=root/'elytrix-test-backups'
 if backupbase.is_symlink():raise ValueError('backup path is symlink')
 backupbase.mkdir(mode=0o700,exist_ok=True);os.chmod(backupbase,0o700);backup=Path(tempfile.mkdtemp(prefix='partial-',dir=backupbase));staged={};applied=[]
 try:
  for rel in updated:
   path=safe_path(root,rel)
   if rel in original:
    b=backup/rel;b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,b)
   staged[rel]=stage(path,updated[rel],root/'plugins/ElytrixRandomEgg.jar' if rel not in original else None)
  for rel,data in original.items():
   if safe_path(root,rel).read_bytes()!=data:raise ValueError('file changed during preparation: '+rel)
  for rel,tmp in staged.items():os.replace(tmp,safe_path(root,rel));applied.append(rel)
 except BaseException:
  for rel in reversed(applied):
   path=safe_path(root,rel)
   if rel in original:
    tmp=stage(path,original[rel]);os.replace(tmp,path)
   else:path.unlink(missing_ok=True)
  raise
 finally:
  for tmp in staged.values():tmp.unlink(missing_ok=True)
 print('Applied to test copy only. Backups:',backup)
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,UnicodeError) as e:print('REFUSED:',e,file=sys.stderr);sys.exit(1)
