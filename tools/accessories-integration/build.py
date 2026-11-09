#!/usr/bin/env python3
"""Build and verify ElytrixFreakModel v3.26.0 with 4-section menu (Спина/Шапки/Питомцы/Ауры), Аура сердечек & Аура бабочек, Крылья Зевса, Круг Сатаны spinning halo, raining Дождевое облако, Мини-Роузи, Милый котёнок & Меллстрой shoulder pets."""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = ROOT / 'plugins/ElytrixFreakModel.jar'
ENTRY = 'pw/elytrix/freakmodel/ElytrixFreakModelPlugin.class'
TARGET_VERSION = '3.27.0'
JAVA = os.environ.get('JAVA', 'java')
ECJ = os.environ.get('ECJ')


def run(*cmd):
    subprocess.run(cmd, check=True)


def main():
    if len(sys.argv) != 2 or not ECJ:
        raise SystemExit('JAVA=/path/java ECJ=/path/ecj.jar python3 build.py /tmp/ElytrixFreakModel-candidate.jar')
    dest = Path(sys.argv[1]).resolve()
    if ROOT / 'plugins' in dest.parents:
        raise SystemExit('Refusing to write directly into plugins/')

    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        cls = t / 'classes'
        cls.mkdir()
        src = HERE / 'src'
        stubs = [str(p) for p in (HERE / 'stubs').rglob('*.java')]

        run(
            JAVA, '-jar', ECJ, '-21', '-encoding', 'UTF-8', '-proc:none',
            '-cp', str(ROOT / 'plugins/BLib.jar'),
            '-d', str(cls),
            *stubs,
            str(src / 'pw/elytrix/freakmodel/AccessoryController.java'),
            str(src / 'PatchAccessory.java'),
            str(src / 'VerifyAccessory.java'),
            str(HERE / 'test/AccessoryTest.java'),
        )
        run(JAVA, '-Xverify:all', '-cp', str(cls), 'pw.elytrix.freakmodel.AccessoryTest')
        run(sys.executable, str(HERE / 'verify_engine.py'), str(cls), str(ROOT / 'plugins/ModelEngine-4.1.0.jar'))

        with zipfile.ZipFile(BASE) as original:
            names = original.namelist()
            if names.count(ENTRY) != 1 or names.count('plugin.yml') != 1:
                raise ValueError('unexpected original ZIP layout')

            old_entry = t / 'old.class'
            new_entry = t / 'new.class'
            old_entry.write_bytes(original.read(ENTRY))
            cp = str(cls) + os.pathsep + str(ROOT / 'plugins/BLib.jar')

            # Idempotent: if BASE is unpatched v3.2.10, run PatchAccessory; if already patched v3.9+, verify directly!
            already_patched = subprocess.run(
                [JAVA, '-Xverify:all', '-cp', cp, 'VerifyAccessory', str(old_entry)],
                capture_output=True,
            ).returncode == 0
            if already_patched:
                new_entry.write_bytes(old_entry.read_bytes())
            else:
                run(JAVA, '-cp', cp, 'PatchAccessory', str(old_entry), str(new_entry))
                run(JAVA, '-Xverify:all', '-cp', cp, 'VerifyAccessory', str(new_entry))

            yml = original.read('plugin.yml').decode('utf-8')
            yml = re.sub(r'^version:\s*\S+', f'version: {TARGET_VERSION}', yml, count=1, flags=re.M)
            if '\n  accessories:' not in yml:
                yml = yml.replace(
                    '\npermissions:\n',
                    '\n  accessories:\n    description: Магазин и гардероб 3D-аксессуаров за риллики\n    aliases: [аксессуары, acc, акс]\n'
                    'permissions:\n  elytrixaccessories.admin:\n    description: Применение аксессуаров\n    default: op\n'
                    '  elytrixaccessories.use:\n    description: Аксессуары\n    default: true\n',
                    1,
                )
            else:
                yml = re.sub(
                    r'(\n  accessories:\n(?:    .*\n)*?    aliases:\s*)\[[^\]]*\]',
                    r'\1[аксессуары, acc, акс]',
                    yml,
                    count=1,
                )
                yml = yml.replace(
                    '  elytrixaccessories.use:\n    description: Аксессуары для донат-группы media\n    default: false\n',
                    '  elytrixaccessories.use:\n    description: Магазин и гардероб 3D-аксессуаров\n    default: true\n',
                    1,
                )
                yml = yml.replace(
                    '    description: Меню аксессуаров\n',
                    '    description: Магазин и гардероб 3D-аксессуаров за риллики\n',
                    1,
                )
            yml_bytes = yml.encode('utf-8')

            added = sorted((cls / 'pw/elytrix/freakmodel').glob('AccessoryController*.class'))
            if not any(p.name == 'AccessoryController.class' for p in added):
                raise ValueError('AccessoryController.class missing')

            with zipfile.ZipFile(dest, 'x') as out:
                for info in original.infolist():
                    if info.filename.startswith('pw/elytrix/freakmodel/AccessoryController'):
                        continue
                    if info.filename == ENTRY:
                        out.writestr(info, new_entry.read_bytes())
                    elif info.filename == 'plugin.yml':
                        out.writestr(info, yml_bytes)
                    else:
                        out.writestr(info, original.read(info.filename))
                for p in added:
                    zname = 'pw/elytrix/freakmodel/' + p.name
                    zinfo = zipfile.ZipInfo(zname, (2026, 11, 2, 0, 0, 0))
                    zinfo.compress_type = zipfile.ZIP_DEFLATED
                    out.writestr(zinfo, p.read_bytes())

    print('Built & verified candidate:', dest, hashlib.sha256(dest.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
