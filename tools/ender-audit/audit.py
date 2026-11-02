#!/usr/bin/env python3
"""Read-only, aggregate-only audit of an offline isolated server copy."""
import argparse, gzip, io, json, re, sqlite3, struct, sys, uuid
from collections import Counter, defaultdict
from pathlib import Path
MAX=64*1024*1024
class NBT:
 def __init__(self,b):self.b=io.BytesIO(b)
 def read(self,n):
  if n<0 or n>MAX:raise ValueError('invalid NBT length')
  b=self.b.read(n)
  if len(b)!=n:raise ValueError('truncated NBT')
  return b
 def u8(self):return self.read(1)[0]
 def i32(self):return struct.unpack('>i',self.read(4))[0]
 def name(self):return self.read(struct.unpack('>H',self.read(2))[0]).decode('utf8')
 def skip(self,t,depth=0):
  if depth>100:raise ValueError('NBT depth limit')
  if t in (1,2,3,4,5,6):self.read({1:1,2:2,3:4,4:8,5:4,6:8}[t])
  elif t==8:self.name()
  elif t in (7,11,12):
   n=self.i32();self.read(n*{7:1,11:4,12:8}[t])
  elif t==9:
   typ=self.u8();n=self.i32()
   if n<0 or n>1000000:raise ValueError('invalid NBT list')
   for _ in range(n):self.skip(typ,depth+1)
  elif t==10:
   while True:
    typ=self.u8()
    if typ==0:break
    self.name();self.skip(typ,depth+1)
  else:raise ValueError('unknown NBT type '+str(t))
 def slots(self):
  if self.u8()!=10:raise ValueError('root not compound')
  self.name(); result=None
  while True:
   t=self.u8()
   if t==0:break
   name=self.name()
   if name!='EnderItems':self.skip(t);continue
   if result is not None or t!=9:raise ValueError('duplicate or invalid EnderItems')
   element=self.u8();n=self.i32()
   if element not in (0,10) or n<0 or n>27 or (element==0 and n):raise ValueError('invalid EnderItems list')
   result=[]
   for _ in range(n):
    slot=None
    while True:
     typ=self.u8()
     if typ==0:break
     key=self.name()
     if key=='Slot' and typ==1:
      if slot is not None:raise ValueError('duplicate Slot')
      slot=self.u8()
     else:self.skip(typ)
    if slot is None or slot>26 or slot in result:raise ValueError('invalid ender slot')
    result.append(slot)
  return result or []

def read_slots(path):
 with gzip.open(path,'rb') as f:
  data=f.read(MAX+1)
  if len(data)>MAX:raise ValueError('NBT file too large')
 return NBT(data).slots()

def audit(root):
 root=root.resolve(strict=True)
 if root==Path('/root/RW_GRIEF').resolve():raise ValueError('audit a stopped isolated copy, not the live server')
 config=root/'plugins/NEnderChest/config.yml'
 if not config.is_file() or config.is_symlink():raise ValueError('missing regular NEnderChest config')
 config_text=config.read_text(encoding='utf8')
 for setting in ('itemsDatabase','playersDatabase'):
  matches=re.findall(r'(?m)^'+setting+r':\s*[\"\']?([^\"\'\s#]+)[\"\']?\s*(?:#.*)?$',config_text)
  if len(matches)!=1 or matches[0].lower()!='sqlite':raise ValueError('audit supports SQLite only: '+setting)
 db=root/'plugins/NEnderChest/items.db'; times=root/'plugins/NEnderChest/playerTimes.db'
 for f in (db,times):
  if not f.is_file() or f.is_symlink():raise ValueError('missing regular SQLite DB: '+str(f))
  for suffix in ('-wal','-shm','-journal'):
   if Path(str(f)+suffix).exists():raise ValueError('SQLite sidecar exists; create a clean offline snapshot: '+f.name+suffix)
 def query(f,sql):
  # immutable prevents SQLite from creating -shm; sidecars are refused above.
  with sqlite3.connect(f.as_uri()+'?mode=ro&immutable=1',uri=True) as c:return c.execute(sql).fetchall()
 rows=query(db,'SELECT player, slot FROM itemsTable'); bought=query(times,'SELECT playerName, rowNumber, forWipe, forever FROM playerTimes')
 items=defaultdict(set); duplicates=0
 for name,slot in rows:
  if not isinstance(name,str) or not isinstance(slot,int) or slot<0 or slot>=54:raise ValueError('invalid NEnderChest row')
  if slot in items[name]:duplicates+=1
  items[name].add(slot)
 counts=Counter(name for name,_,_,_ in bought); invalid_sizes=sum(1 for n in counts.values() if 27+9*n>54)
 usercache=root/'usercache.json'
 if not usercache.is_file() or usercache.is_symlink():raise ValueError('missing usercache.json; cannot map UUIDs to chest names')
 names=defaultdict(set)
 for entry in json.loads(usercache.read_text(encoding='utf8')):
  try:
   player_name=entry['name']
   if not isinstance(player_name,str) or not player_name: raise ValueError('invalid name')
   names[str(uuid.UUID(entry['uuid']))].add(player_name)
  except (ValueError,KeyError,TypeError):raise ValueError('invalid usercache entry')
 data=defaultdict(list)
 for directory in root.rglob('playerdata'):
  if directory.is_symlink() or not directory.is_dir() or 'plugins' in directory.relative_to(root).parts:continue
  for file in directory.glob('*.dat'):
   if file.is_symlink():raise ValueError('symlink playerdata not supported')
   try:id=str(uuid.UUID(file.stem))
   except ValueError:continue
   data[id].append(read_slots(file))
 result={'playerdata_uuids':len(data),'uuids_with_multiple_playerdata_files':sum(len(v)>1 for v in data.values()),'vanilla_chests_with_items':0,'unknown_or_ambiguous_names':0,'case_mismatch_to_nender_name':0,'both_stores_nonempty':0,'definitely_not_enough_slots_without_stacking':0,'nender_players_with_items':len(items),'purchased_rows_total':len(bought),'nender_invalid_size_players':invalid_sizes,'duplicate_nender_item_slots':duplicates,'nender_items_outside_unlocked_size':0}
 by_fold=defaultdict(set)
 for name in set(items)|set(counts):by_fold[name.casefold()].add(name)
 for name,slots in items.items():
  result['nender_items_outside_unlocked_size']+=sum(s>=27+9*counts[name] for s in slots)
 for id,entries in data.items():
  if len(entries)!=1:continue
  vanilla=entries[0]
  if not vanilla:continue
  result['vanilla_chests_with_items']+=1
  candidates=names.get(id,set())
  if len(candidates)!=1:result['unknown_or_ambiguous_names']+=1;continue
  name=next(iter(candidates));matches=by_fold[name.casefold()]
  if matches and matches!={name}:result['case_mismatch_to_nender_name']+=1;continue
  dest=items[name];capacity=27+9*counts[name]
  if dest:result['both_stores_nonempty']+=1
  if len(vanilla)>max(0,capacity-len(dest)):result['definitely_not_enough_slots_without_stacking']+=1
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('copy',type=Path);a=p.parse_args()
 print(json.dumps(audit(a.copy),ensure_ascii=False,indent=2))
 print('Only counts; no data moved. Review identity ambiguities, slot capacity and recovery before migration.')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,sqlite3.Error,json.JSONDecodeError) as e:print('REFUSED:',e,file=sys.stderr);sys.exit(1)
