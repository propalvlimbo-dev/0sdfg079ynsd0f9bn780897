#!/usr/bin/env python3
"""Build a non-production candidate, preserving original ZIP entries."""
import hashlib, os, subprocess, sys, tempfile, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
BASE=ROOT/'plugins/ElytrixFree.jar'; ENTRY='pw/elytrix/elytrixfree/FreeMenu.class'
EXPECTED='1bb0d797c9546c750b9eb2c43a1c564cb2009ed614c41074798b77ae2739c376'
JAVA=os.environ.get('JAVA','java'); ECJ=os.environ.get('ECJ')
def run(*cmd): subprocess.run(cmd,check=True)
def main():
    if len(sys.argv)!=2 or not ECJ: raise SystemExit('JAVA=/path/java ECJ=/path/ecj.jar python3 build.py /tmp/candidate.jar')
    dest=Path(sys.argv[1]).resolve()
    if ROOT/'plugins' in dest.parents or dest==BASE.resolve(): raise SystemExit('Refusing to write into plugins')
    if hashlib.sha256(BASE.read_bytes()).hexdigest()!=EXPECTED: raise SystemExit('Original SHA mismatch')
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td); classes=tmp/'classes'; classes.mkdir()
        stubs=[str(x) for x in (HERE/'stubs').rglob('*.java')]
        run(JAVA,'-jar',ECJ,'-21','-encoding','UTF-8','-proc:none','-d',str(classes),*stubs,str(HERE/'src/pw/elytrix/elytrixfree/CaseDependencyGuard.java'),str(HERE/'test/pw/elytrix/elytrixfree/GuardTest.java'))
        run(JAVA,'-Xverify:all','-cp',str(classes),'pw.elytrix.elytrixfree.GuardTest')
        run(JAVA,'-jar',ECJ,'-21','-proc:none','-cp',str(ROOT/'plugins/BLib.jar'),'-d',str(classes),str(HERE/'src/PatchFree.java'),str(HERE/'src/VerifyFree.java'))
        with zipfile.ZipFile(BASE) as src:
            names=src.namelist()
            if len(names)!=len(set(names)) or names.count(ENTRY)!=1: raise ValueError('Unexpected zip structure')
            old=tmp/'old.class'; new=tmp/'new.class'; old.write_bytes(src.read(ENTRY))
            run(JAVA,'-cp',str(classes)+os.pathsep+str(ROOT/'plugins/BLib.jar'),'PatchFree',str(old),str(new))
            run(JAVA,'-Xverify:all','-cp',str(classes)+os.pathsep+str(ROOT/'plugins/BLib.jar'),'VerifyFree',str(new))
            guard='pw/elytrix/elytrixfree/CaseDependencyGuard.class'
            if guard in names: raise ValueError('Guard already exists')
            with zipfile.ZipFile(dest,'x') as out:
                for info in src.infolist(): out.writestr(info,new.read_bytes() if info.filename==ENTRY else src.read(info))
                info=zipfile.ZipInfo(guard,(2020,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED
                out.writestr(info,(classes/guard).read_bytes())
        with zipfile.ZipFile(BASE) as a,zipfile.ZipFile(dest) as b:
            assert [n for n in a.namelist() if a.read(n)!=b.read(n)]==[ENTRY]
            assert set(b.namelist())-set(a.namelist())=={guard}
        print('candidate',dest,hashlib.sha256(dest.read_bytes()).hexdigest())
if __name__=='__main__': main()
