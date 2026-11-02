#!/usr/bin/env python3
"""Make a staging candidate only. Never applies to a server."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'plugins/IRandomTeleport.jar'
EXPECTED = '9a58cb93bc5916a8e3300dca41dec1df3e23b66fb4f2ae99d1e300749c524593'
ENTRY = 'com/ilyapurtov/utils/ReflectionUtil.class'
HERE = Path(__file__).resolve().parent
JAVA = os.environ.get('JAVA', 'java')
ECJ = os.environ.get('ECJ')

def run(*cmd):
    subprocess.run(cmd, check=True)

def main():
    if len(sys.argv) != 2 or not ECJ:
        raise SystemExit('Usage: JAVA=/path/to/java ECJ=/path/to/ecj.jar python3 build.py /path/to/candidate.jar')
    output = Path(sys.argv[1]).resolve()
    if output == SOURCE.resolve() or ROOT / 'plugins' in output.parents:
        raise SystemExit('Refusing to write to plugins/')
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != EXPECTED:
        raise SystemExit('Baseline SHA mismatch')
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        run(JAVA, '-jar', ECJ, '-17', '-cp', str(ROOT / 'plugins/BLib.jar'), '-d', str(tmp), str(HERE / 'src/PatchTitle.java'))
        with zipfile.ZipFile(SOURCE) as src:
            names = src.namelist()
            if names.count(ENTRY) != 1 or len(set(names)) != len(names):
                raise SystemExit('Duplicate ZIP entries')
            old = tmp / 'old.class'; new = tmp / 'new.class'
            old.write_bytes(src.read(ENTRY))
            run(JAVA, '-cp', str(tmp) + os.pathsep + str(ROOT / 'plugins/BLib.jar'), 'PatchTitle', str(old), str(new))
            output.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(output, 'x') as dst:
                for info in src.infolist():
                    dst.writestr(info, new.read_bytes() if info.filename == ENTRY else src.read(info))
        with zipfile.ZipFile(SOURCE) as a, zipfile.ZipFile(output) as b:
            changed = [n for n in a.namelist() if a.read(n) != b.read(n)]
            assert changed == [ENTRY], changed
        # Compile against a minimal API interface and run with bytecode verification.
        run(JAVA, '-jar', ECJ, '-17', '-encoding', 'UTF-8', '-cp', str(output), '-d', str(tmp),
            str(HERE / 'stubs/org/bukkit/entity/Player.java'), str(HERE / 'stubs/com/ilyapurtov/IRandomTeleport.java'),
            str(HERE / 'test/TitleTest.java'))
        run(JAVA, '-Xverify:all', '-cp', str(tmp) + os.pathsep + str(output), 'TitleTest')
        print('STAGING ONLY:', output, 'sha256', hashlib.sha256(output.read_bytes()).hexdigest())

if __name__ == '__main__': main()
