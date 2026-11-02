#!/usr/bin/env python3
"""Merge accessory assets into a new pack, preserving all unrelated content."""
import hashlib,json,sys,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
FONT='assets/minecraft/font/default.json'
GLYPH='ꏠ'
PROVIDER={'type':'bitmap','file':'reallyworld:gui/title/elytrix_accessories.png','ascent':26,'height':32,'chars':[GLYPH]}
def assets(d):return {p.relative_to(d).as_posix():p.read_bytes() for p in d.rglob('*') if p.is_file()}
def make(inp,out,mode):
 if mode not in ('fresh','upgrade'):raise ValueError('invalid mode')
 inp=Path(inp).resolve(strict=True);out=Path(out).resolve()
 if inp==out or out.exists():raise ValueError('output must be new')
 fresh=assets(HERE/'staging-assets');old=assets(HERE/'previous-assets')
 if len(fresh)!=13 or len(old)!=12 or not set(old).issubset(fresh):raise ValueError('unexpected asset manifest')
 with zipfile.ZipFile(inp) as zin:
  names=zin.namelist()
  if len(names)!=len(set(names)) or zin.testzip():raise ValueError('bad resource pack ZIP')
  if mode=='fresh' and set(names)&set(fresh):raise ValueError('existing asset collision')
  if mode=='upgrade':
   for n,data in old.items():
    if n not in names or zin.read(n)!=data:raise ValueError('previous accessory resource is missing or changed: '+n)
   if (set(names)&set(fresh))-set(old):raise ValueError('new resource collision')
  atlas=json.loads(zin.read('assets/minecraft/atlases/blocks.json'))
  if not any(x.get('type') in ('directory','minecraft:directory') and x.get('source')=='entity/models' and x.get('prefix')=='entity/models/' for x in atlas['sources']):raise ValueError('model texture atlas not found')
  for icon in ('angel_wings','angel_halo'):
   if 'assets/reallyworld/items/'+icon+'.json' not in names:raise ValueError('existing wings/halo icons not found')
  font=json.loads(zin.read(FONT));providers=font['providers']
  for required in 'ꈁꀀꈂꌀꀁꈃ':
   if not any(any(required in row for row in p.get('chars',[])) or required in p.get('advances',{}) for p in providers):raise ValueError('missing existing menu resourcepack glyph: '+required)
  for p in providers:
   if any(GLYPH in row for row in p.get('chars',[])) or GLYPH in p.get('advances',{}):raise ValueError('accessory font character is already in use')
  providers.insert(0,PROVIDER);fontbytes=(json.dumps(font,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf8')
  for n,data in fresh.items():
   if n.endswith('.json'):json.loads(data)
  try:
   with zipfile.ZipFile(out,'x') as zout:
    for info in zin.infolist():
     n=info.filename;zout.writestr(info,fontbytes if n==FONT else fresh[n] if n in fresh else zin.read(info))
    for n in sorted(set(fresh)-set(names)):
     i=zipfile.ZipInfo(n,(2020,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;zout.writestr(i,fresh[n])
  except BaseException:
   out.unlink(missing_ok=True);raise
 with zipfile.ZipFile(out) as z:
  if z.testzip():raise ValueError('output pack CRC failure')
 print('Prepared resource pack SHA-1:',hashlib.sha1(out.read_bytes()).hexdigest())
if __name__=='__main__':
 if len(sys.argv)!=4:raise SystemExit('Usage: merge.py INPUT NEW_OUTPUT fresh|upgrade')
 make(*sys.argv[1:])
