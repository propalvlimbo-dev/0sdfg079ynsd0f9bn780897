#!/usr/bin/env python3
"""Write a NEW staging pack only; never modify a live resource pack in place."""
import hashlib, json, sys, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def main():
 if len(sys.argv)!=3:raise SystemExit('Usage: python3 merge_staging_pack.py INPUT.zip NEW_OUTPUT.zip')
 inp=Path(sys.argv[1]).resolve(strict=True);out=Path(sys.argv[2]).resolve()
 if inp==out or out.exists():raise SystemExit('Output must be a new file')
 if out.is_relative_to((ROOT/'plugins').resolve()) or out.is_relative_to((ROOT/'rp').resolve()):raise SystemExit('Output must not be in server directories')
 base=HERE/'staging-assets'
 # This is the frozen v1 merger; the v2 assets are handled by accessories-upgrade/merge.py.
 if len([p for p in base.rglob('*') if p.is_file()])!=12:
  base=HERE.parent/'accessories-upgrade/previous/staging-assets'
 assets={p.relative_to(base).as_posix():p.read_bytes() for p in base.rglob('*') if p.is_file()}
 if len(assets)!=12:raise ValueError('Expected precisely 12 staging assets')
 with zipfile.ZipFile(inp) as old:
  names=old.namelist()
  if len(names)!=len(set(names)) or old.testzip():raise ValueError('Malformed or duplicate ZIP entries')
  if set(names)&set(assets):raise ValueError('Existing asset collision; no output created')
  atlas=json.loads(old.read('assets/minecraft/atlases/blocks.json'))
  if not any(x.get('type') in ('directory','minecraft:directory') and x.get('source')=='entity/models' and x.get('prefix')=='entity/models/' for x in atlas['sources']):raise ValueError('Required model texture atlas directory missing')
  for item in ('angel_wings','angel_halo'):
   if 'assets/reallyworld/items/'+item+'.json' not in names:raise ValueError('Existing accessory menu icons missing')
  for name,content in assets.items():
   if name.endswith('.json'):json.loads(content)
  try:
   with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED) as new:
    for info in old.infolist():new.writestr(info,old.read(info))
    for name,content in sorted(assets.items()):
     info=zipfile.ZipInfo(name,(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;new.writestr(info,content)
  except Exception:
   out.unlink(missing_ok=True);raise
 with zipfile.ZipFile(out) as result:
  if result.testzip():raise ValueError('Failed output CRC')
 print('STAGING ONLY:',out,'SHA-1',hashlib.sha1(out.read_bytes()).hexdigest())
if __name__=='__main__':main()
