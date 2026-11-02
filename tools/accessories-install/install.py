#!/usr/bin/env python3
"""Experimental accessory installer: only works with the checked server snapshot."""
import argparse, hashlib, json, os, re, shlex, stat, subprocess, sys, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path
import core_safety

HERE=Path(__file__).resolve().parent
OLD_JAR='528956e976cbc4655bff35f97b2cef1b6f21ba63fbb4fa2953a21287b840ead6'
NEW_JAR='4792252b1c6da30a9d2fdbdb0b71e81ae8262d69011de10815bc9a5ac90f8a38'
ME_JAR='d24b7d4e865f5453cb2947ec87bd3549e571c7d7927cd22e0c6927b03426090d'
BLUEPRINT='c01f40d344854f252454c3ae26c7e8622625fbe920232c2216e8e461c8905e1a'
def sha(data): return hashlib.sha256(data).hexdigest()
def existing_regular(path):
    path=Path(path)
    for p in [path,*path.parents]:
        if p.is_symlink(): raise ValueError('symbolic link in path: '+str(p))
    if not path.is_file():raise ValueError('missing required file: '+str(path))
    return path

def atomic(path,data,mode,uid,gid):
    fd,tmp=tempfile.mkstemp(prefix='.elytrix-accessory-',dir=path.parent)
    try:
        os.fchmod(fd,mode)
        if os.geteuid()==0:os.fchown(fd,uid,gid)
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def settings(text):
    # Only accept unambiguous simple scalar keys and the expected generator mode.
    for key, expected in [('Namespace','modelengine'),('Texture-Path','entity/models'),('Use-New-Rotation','false'),('Merge-Item-Models','false')]:
        found=re.findall(r'^[ \t]*'+re.escape(key)+r'[ \t]*:[ \t]*([^#\r\n]+)',text,re.M)
        if len(found)!=1 or found[0].strip().strip('"\'').lower()!=expected.lower():
            raise ValueError('ModelEngine config requires '+key+': '+expected+' (or format is unrecognized)')

def rp_config(old,new_sha):
    text=old.decode('utf-8')
    pat=r'(?m)^([ \t]*sha1[ \t]*:[ \t]*)(["\']?[0-9a-fA-F]{40}["\']?|["\']["\']|)([ \t]*(?:\#.*)?)$'
    if len(re.findall(r'(?m)^[ \t]*sha1[ \t]*:',text))!=1:raise ValueError('ElytrixRP sha1 entry must be unique')
    text,n=re.subn(pat,lambda m:m.group(1)+'"'+new_sha+'"'+m.group(3),text)
    if n!=1:raise ValueError('unsupported ElytrixRP sha1 format')
    return text.encode('utf-8')

def verify_dependencies(root):
    found=[]
    for jar in (root/'plugins').glob('*.jar'):
        if jar.is_symlink():raise ValueError('plugin JAR is a symlink: '+str(jar))
        try:
            with zipfile.ZipFile(jar) as z:
                if 'plugin.yml' not in z.namelist():continue
                text=z.read('plugin.yml').decode('utf8',errors='replace')
                if re.search(r'(?im)^name:\s*["\']?ModelEngine["\']?\s*$',text):found.append(jar)
                if jar.name!='ElytrixFreakModel.jar' and re.search(r'(?i)\baccessories\b|аксессуары',text):
                    raise ValueError('possible accessories command conflict in '+jar.name)
        except zipfile.BadZipFile:raise ValueError('unreadable plugin jar: '+str(jar))
    if len(found)!=1 or sha(existing_regular(found[0]).read_bytes())!=ME_JAR:raise ValueError('need exact ModelEngine 4.1.0 JAR used in test')

def install(root,served,backup_base):
    root=root.resolve(strict=True); served=existing_regular(served).absolute(); backup_base=backup_base.resolve(strict=True)
    if not root.is_dir() or not backup_base.is_dir() or backup_base==root or backup_base.is_relative_to(root):raise ValueError('backup directory must exist outside server root')
    core_safety.check_stopped(root)
    jar=existing_regular(root/'plugins/ElytrixFreakModel.jar')
    conf=existing_regular(root/'plugins/ElytrixRP/config.yml')
    local_rp=existing_regular(root/'rp/Elytrix-RP-1.21.zip')
    if served==local_rp:raise ValueError('server and served resource pack paths must be separate files')
    meconfig=existing_regular(root/'plugins/ModelEngine/config.yml')
    settings(meconfig.read_text(encoding='utf8'))
    verify_dependencies(root)
    for name in ('elytrix_angel_wings','elytrix_angel_halo'):
        existing_regular(root/'plugins/ModelEngine/blueprints'/f'{name}.bbmodel')
    blueprint=root/'plugins/ModelEngine/blueprints/elytrix_kaneki_tentacles.bbmodel'
    existing_regular(blueprint.parent/'elytrix_angel_wings.bbmodel')
    if blueprint.exists() or blueprint.is_symlink():raise ValueError('tentacle blueprint already exists; refusing to overwrite')
    if sha(jar.read_bytes())!=OLD_JAR:raise ValueError('ElytrixFreakModel.jar SHA-256 is not expected 3.2.10; no files changed')
    candidate=existing_regular(HERE/'ElytrixFreakModel.jar').read_bytes();model=existing_regular(HERE/'elytrix_kaneki_tentacles.bbmodel').read_bytes()
    if sha(candidate)!=NEW_JAR or sha(model)!=BLUEPRINT:raise ValueError('package content hash mismatch')
    oldpack=local_rp.read_bytes()
    if served.read_bytes()!=oldpack:raise ValueError('server and served resource packs differ; refusing to overwrite either')
    with tempfile.TemporaryDirectory() as td:
        merged=Path(td)/'merged.zip'
        subprocess.run([sys.executable,str(HERE/'merge_staging_pack.py'),str(local_rp),str(merged)],check=True)
        newpack=merged.read_bytes()
    newsha=hashlib.sha1(newpack).hexdigest();newconfig=rp_config(conf.read_bytes(),newsha)
    # Install plugin last: the server and all restart wrappers must stay stopped.
    items=[(blueprint,model),(local_rp,newpack),(served,newpack),(conf,newconfig),(jar,candidate)]
    backup=backup_base/('accessories-test-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));backup.mkdir(mode=0o700)
    manifest=[]
    for i,(path,new) in enumerate(items):
        old=None if path==blueprint else path.read_bytes()
        info=(jar if old is None else path).stat()
        if old is not None:
            b=backup/('original-'+str(i));b.write_bytes(old);b.chmod(0o600)
            if b.read_bytes()!=old:raise ValueError('backup verification failed')
        manifest.append({'path':str(path),'old_sha':None if old is None else sha(old),'new_sha':sha(new),'mode':stat.S_IMODE(info.st_mode),'uid':info.st_uid,'gid':info.st_gid,'backup':('original-'+str(i)) if old is not None else None})
    (backup/'manifest.json').write_text(json.dumps({'root':str(root),'served':str(served),'files':manifest},indent=2));(backup/'manifest.json').chmod(0o600)
    print('Private backup:',backup,flush=True)
    done=[]
    try:
        core_safety.check_stopped(root)
        for record,(path,new) in zip(manifest,items):
            if path.is_symlink() or (path.exists() and (record['old_sha'] is None or sha(path.read_bytes())!=record['old_sha'])) or (not path.exists() and record['old_sha'] is not None):raise ValueError('file changed during staging: '+str(path))
            mode=0o644 if path==served or path==blueprint else record['mode']
            atomic(path,new,mode,record['uid'],record['gid']);done.append(record)
        print('Installed TEST accessory plugin, blueprint and both resource packs. RP SHA-1:',newsha)
        print('Server has not been started. Backup for rollback:',backup)
        cmd=[sys.executable,str(HERE/'install.py'),str(root),str(served),str(backup),'--stopped','--rollback']
        print('Rollback command (stop server and restart loop first):',shlex.join(cmd))
    except BaseException:
        for record in reversed(done):
            try:restore_one(record,backup)
            except Exception as e:print('ROLLBACK FAILED:',record['path'],e,file=sys.stderr)
        print('Installation failed. Backup:',backup,file=sys.stderr)
        raise

def restore_one(r,backup):
    path=Path(r['path'])
    if r['old_sha'] is None:path.unlink()
    else:
        data=(backup/r['backup']).read_bytes()
        if sha(data)!=r['old_sha']:raise ValueError('backup corrupt')
        atomic(path,data,r['mode'],r['uid'],r['gid'])

def rollback(root,served,backup):
    root=root.resolve(strict=True);served=existing_regular(served).absolute();backup=backup.resolve(strict=True)
    core_safety.check_stopped(root)
    m=json.loads(existing_regular(backup/'manifest.json').read_text())
    expected={str(root/'plugins/ElytrixFreakModel.jar'),str(root/'plugins/ElytrixRP/config.yml'),str(root/'rp/Elytrix-RP-1.21.zip'),str(root/'plugins/ModelEngine/blueprints/elytrix_kaneki_tentacles.bbmodel'),str(served)}
    if m['root']!=str(root) or m['served']!=str(served) or {x['path'] for x in m['files']}!=expected or len(m['files'])!=5:raise ValueError('backup paths do not match this server')
    for r in m['files']:
        p=existing_regular(Path(r['path']))
        if sha(p.read_bytes())!=r['new_sha']:raise ValueError('file changed since installation; manual rollback needed: '+str(p))
        if r['backup'] is not None:
            if not re.fullmatch(r'original-[0-9]',r['backup']) or sha(existing_regular(backup/r['backup']).read_bytes())!=r['old_sha']:raise ValueError('backup missing or corrupt')
    for r in reversed(m['files']):restore_one(r,backup)
    print('Prior files restored; server remains stopped. Choices saved in player PDC were not deleted.')

def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('served',type=Path);p.add_argument('backup',type=Path);p.add_argument('--stopped',action='store_true');p.add_argument('--backed-up',action='store_true');p.add_argument('--rollback',action='store_true');a=p.parse_args()
    if not a.stopped or (not a.rollback and not a.backed_up):raise ValueError('confirm server and restart loop stopped, and full backup made')
    (rollback if a.rollback else install)(a.root,a.served,a.backup)
if __name__=='__main__':
    try:main()
    except (OSError,ValueError,zipfile.BadZipFile,subprocess.SubprocessError) as e:print('REFUSED:',e,file=sys.stderr);sys.exit(1)
