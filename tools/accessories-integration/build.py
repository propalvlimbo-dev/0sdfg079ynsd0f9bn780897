#!/usr/bin/env python3
"""Build a mock-tested, non-production accessory integration candidate."""
import hashlib, os, subprocess, sys, tempfile, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
BASE=ROOT/'plugins/ElytrixFreakModel.jar'; ENTRY='pw/elytrix/freakmodel/ElytrixFreakModelPlugin.class'
EXPECTED='528956e976cbc4655bff35f97b2cef1b6f21ba63fbb4fa2953a21287b840ead6'
JAVA=os.environ.get('JAVA','java');ECJ=os.environ.get('ECJ')
def run(*x):subprocess.run(x,check=True)
def main():
 if len(sys.argv)!=2 or not ECJ:raise SystemExit('JAVA=/path/java ECJ=/path/ecj.jar python3 build.py /tmp/accessory-candidate.jar')
 dest=Path(sys.argv[1]).resolve()
 if ROOT/'plugins' in dest.parents:raise SystemExit('Refusing to write into plugins')
 if hashlib.sha256(BASE.read_bytes()).hexdigest()!=EXPECTED:raise SystemExit('Unexpected original plugin SHA256')
 with tempfile.TemporaryDirectory() as td:
  t=Path(td);cls=t/'classes';cls.mkdir();src=HERE/'src'
  stubs=[str(p) for p in (HERE/'stubs').rglob('*.java')]
  run(JAVA,'-jar',ECJ,'-21','-encoding','UTF-8','-proc:none','-cp',str(ROOT/'plugins/BLib.jar'),'-d',str(cls),*stubs,str(src/'pw/elytrix/freakmodel/AccessoryController.java'),str(src/'PatchAccessory.java'),str(src/'VerifyAccessory.java'),str(HERE/'test/AccessoryTest.java'))
  run(JAVA,'-Xverify:all','-cp',str(cls),'pw.elytrix.freakmodel.AccessoryTest')
  # the mocks are built from our own stubs, so they cannot notice a stub that lies
  # about the engine (that is how v25 shipped an invokeinterface on a class).
  run(sys.executable,str(HERE/'verify_engine.py'),str(cls),str(ROOT/'plugins/ModelEngine-4.1.0.jar'))
  with zipfile.ZipFile(BASE) as original:
   names=original.namelist()
   if len(names)!=len(set(names)) or names.count(ENTRY)!=1 or names.count('plugin.yml')!=1:raise ValueError('unexpected original ZIP')
   old=t/'old.class'; new=t/'new.class';old.write_bytes(original.read(ENTRY));cp=str(cls)+os.pathsep+str(ROOT/'plugins/BLib.jar')
   run(JAVA,'-cp',cp,'PatchAccessory',str(old),str(new));run(JAVA,'-Xverify:all','-cp',cp,'VerifyAccessory',str(new))
   y=original.read('plugin.yml').decode('utf8')
   if y.count('\npermissions:\n')!=1 or '\n  accessories:' in y or 'elytrixaccessories.admin:' in y:raise ValueError('plugin metadata unexpected')
   if 'version: 3.2.10' not in y:raise ValueError('unexpected plugin version')
   y=y.replace('version: 3.2.10','version: 3.8.0',1)
   y=y.replace('\npermissions:\n','\n  accessories:\n    description: Меню аксессуаров\n    aliases: [аксессуары]\npermissions:\n  elytrixaccessories.admin:\n    description: Применение аксессуаров\n    default: op\n  elytrixaccessories.use:\n    description: Аксессуары для донат-группы media\n    default: false\n',1).encode('utf8')
   added=[p for p in (cls/'pw/elytrix/freakmodel').glob('AccessoryController*.class')]
   expected={'AccessoryController.class','AccessoryController$Holder.class','AccessoryController$Crawl.class','AccessoryController$Pet.class'}
   if {p.name for p in added}!=expected:raise ValueError('Unexpected helper classes')
   with zipfile.ZipFile(dest,'x') as out:
    for info in original.infolist():out.writestr(info,new.read_bytes() if info.filename==ENTRY else y if info.filename=='plugin.yml' else original.read(info))
    for p in sorted(added):
     n='pw/elytrix/freakmodel/'+p.name
     if n in names:raise ValueError('Helper already exists')
     info=zipfile.ZipInfo(n,(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;out.writestr(info,p.read_bytes())
  with zipfile.ZipFile(BASE) as a,zipfile.ZipFile(dest) as b:
   assert {n for n in a.namelist() if a.read(n)!=b.read(n)}=={ENTRY,'plugin.yml'}
   assert set(b.namelist())-set(a.namelist())=={'pw/elytrix/freakmodel/AccessoryController.class','pw/elytrix/freakmodel/AccessoryController$Holder.class','pw/elytrix/freakmodel/AccessoryController$Crawl.class','pw/elytrix/freakmodel/AccessoryController$Pet.class'}
 print('Mock-tested candidate only:',dest,hashlib.sha256(dest.read_bytes()).hexdigest())
if __name__=='__main__':main()
