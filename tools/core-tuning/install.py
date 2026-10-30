#!/usr/bin/env python3
"""Apply a narrow, reversible experiment without replacing live YAML files."""
import argparse
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def require_regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Нет обычного файла или это символьная ссылка: {path}')


def running_java_in(root):
    # Do not print command lines or secrets. Check again immediately before applying.
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            if (p / 'comm').read_text().strip() != 'java':
                continue
            if Path(os.readlink(p / 'cwd')).resolve() == root:
                return p.name
        except (OSError, ValueError):
            continue
    return None


def transform_start(text):
    for flag in ('Xms', 'Xmx'):
        # Conservative: comments and duplicate flags also cause a refusal.
        if len(re.findall(r'(?<!\S)-' + flag + r'[^\s\\]*', text)) != 1:
            raise ValueError(f'Ожидался ровно один флаг -{flag} в start.sh.')
    mx = re.compile(r'(?m)^[ \t]*-Xmx10G[ \t]*\\[ \t]*\r?$')
    ms = re.compile(r'(?m)^([ \t]*)-Xms(10|8)G([ \t]*\\[ \t]*)(\r?)$')
    if len(mx.findall(text)) != 1 or len(ms.findall(text)) != 1:
        raise ValueError('Ожидались отдельные строки -Xms10G/-Xms8G и -Xmx10G.')
    return ms.sub(lambda m: m.group(1) + '-Xms8G' + m.group(3) + m.group(4), text)


def transform_paper(text):
    # Inspect only the unique top-level misc mapping; no YAML serialization,
    # which could discard comments or expose/overwrite the Velocity secret.
    sections = list(re.finditer(r'(?m)^misc:[ \t]*(?:#.*)?\r?$', text))
    if len(sections) != 1:
        raise ValueError('В paper-global.yml ожидался ровно один раздел misc.')
    start = sections[0].end()
    next_section = re.search(r'(?m)^[^ \t\r\n#][^\r\n]*:', text[start:])
    end = start + next_section.start() if next_section else len(text)
    block = text[start:end]
    key = re.compile(r'(?m)^  compression-level:[^\r\n]*\r?$')
    if len(key.findall(block)) != 1:
        raise ValueError('В misc ожидался ровно один compression-level.')
    value = re.compile(r'(?m)^(  compression-level:[ \t]*)(6|1)([ \t]*(?:#[^\r\n]*)?)(\r?)$')
    if len(value.findall(block)) != 1:
        raise ValueError('Ожидался misc.compression-level 6 или 1.')
    block = value.sub(lambda m: m.group(1) + '1' + m.group(3) + m.group(4), block)
    return text[:start] + block + text[end:]


def stage(path, data):
    fd, name = tempfile.mkstemp(prefix='.elytrix-tune-', dir=path.parent)
    try:
        info = path.stat()
        os.fchmod(fd, stat.S_IMODE(info.st_mode))
        if os.geteuid() == 0:
            os.fchown(fd, info.st_uid, info.st_gid)
        with os.fdopen(fd, 'wb') as stream:
            fd = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return Path(name)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        Path(name).unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='/root/RW_GRIEF', help='папка игрового сервера')
    args = parser.parse_args()
    root = Path(args.root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Папка игрового сервера не найдена.')
    pid = running_java_in(root)
    if pid:
        raise ValueError(f'Игровая Java ещё запущена (PID {pid}). Остановите её и автозапуск перед установкой.')
    paths = [root / 'start.sh', root / 'config' / 'paper-global.yml']
    for path in paths:
        require_regular(path)
    original = {path: path.read_bytes() for path in paths}
    modified = {
        paths[0]: transform_start(original[paths[0]].decode('utf-8')).encode('utf-8'),
        paths[1]: transform_paper(original[paths[1]].decode('utf-8')).encode('utf-8'),
    }
    changed = [path for path in paths if original[path] != modified[path]]
    if not changed:
        print('Параметры уже установлены; изменений не требуется.')
        return

    backup_root = root / 'elytrix-config-backups'
    if backup_root.is_symlink():
        raise ValueError('Папка резервных копий не должна быть символьной ссылкой.')
    backup_root.mkdir(mode=0o700, exist_ok=True)
    # Enforce private permissions: paper-global.yml can contain a proxy secret.
    os.chmod(backup_root, 0o700)
    backup = Path(tempfile.mkdtemp(prefix='core-', dir=backup_root))
    os.chmod(backup, 0o700)
    staged = {}
    applied = []
    try:
        for path in changed:
            relative = path.relative_to(root)
            copy = backup / relative
            copy.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(path, copy)
            staged[path] = stage(path, modified[path])
        if paths[0] in staged:
            subprocess.run(['bash', '-n', str(staged[paths[0]])], check=True)
        pid = running_java_in(root)
        if pid:
            raise ValueError(f'Игровая Java запустилась во время подготовки (PID {pid}); установка отменена.')
        for path in changed:
            if path.read_bytes() != original[path]:
                raise ValueError(f'Файл изменился во время подготовки: {path}; установка отменена.')
        for path in changed:
            os.replace(staged[path], path)
            applied.append(path)
    except BaseException:
        for path in reversed(applied):
            restore = stage(path, original[path])
            os.replace(restore, path)
        raise
    finally:
        for path in staged.values():
            path.unlink(missing_ok=True)
    print('Установлено: start.sh: Xms8G / Xmx10G; Paper misc.compression-level: 1.')
    print(f'Резервные копии изменённых файлов: {backup}')
    print('Запускайте сервер через start.sh. Если он запускается иначе, измените фактическую команду запуска отдельно.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, UnicodeError, subprocess.CalledProcessError) as exc:
        print(f'ОШИБКА: {exc}', file=sys.stderr)
        sys.exit(1)
