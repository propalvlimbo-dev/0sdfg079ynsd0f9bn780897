#!/usr/bin/env python3
"""Exercise the archive installer against isolated fake VDS directories."""
from pathlib import Path
import os, subprocess, tempfile, zipfile

repo = Path(__file__).resolve().parents[3]
patch = repo / 'elytrix-freakmodel-patch.zip'
installer = repo / 'tools/freakmodel-fix/install_wing_patch.sh'
model = 'plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_angel_wings'
config_text = '# retain this\nurl: "http://example.invalid:8085/pack"\nsha1: "old-sha"\nenabled: true\n'

def make_fixture(root):
    server = root/'server'; web = root/'web'; backups = root/'private-backups'
    def write(base, path, data):
        target=base/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        return target
    write(server,'plugins/ElytrixFreakModel.jar',b'original jar')
    write(server,'plugins/ModelEngine/blueprints/elytrix_angel_wings.bbmodel',b'original blueprint')
    write(server,'rp/Elytrix-RP-1.21.zip',b'original server rp')
    write(web,'Elytrix-RP-1.21.zip',b'original served rp')
    write(server,model+'/left_wing_inner.json',b'old left')
    write(server,model+'/right_wing_inner.json',b'old right')
    unrelated=write(server,'plugins/ModelEngine/resource pack/assets/other/untouched.json',b'other plugin')
    actual_config=write(root,'custom-live-config.yml',config_text.encode())
    config=server/'plugins/ElytrixRP/config.yml';config.parent.mkdir(parents=True);config.symlink_to(actual_config)
    env=dict(os.environ, ELYTRIX_SERVER_ROOT=str(server),ELYTRIX_RP_DIR=str(web),ELYTRIX_BACKUP_ROOT=str(backups))
    return server,web,backups,config,unrelated,env

def run(env, archive=patch):
    return subprocess.run(['bash',str(installer),str(archive)],env=env,capture_output=True,text=True)

with tempfile.TemporaryDirectory() as td:
    root=Path(td); server,web,backups,config,unrelated,env=make_fixture(root/'valid')
    result=run(env);assert result.returncode==0,(result.stdout,result.stderr)
    assert config.is_symlink(), 'must not replace a symlinked live config'
    assert config.read_text()==config_text.replace('old-sha','d6701c4da33bd86b3fa25732f2bad882cdbecf7d')
    assert unrelated.read_bytes()==b'other plugin'
    with zipfile.ZipFile(patch) as archive:
        for path in ['plugins/ElytrixFreakModel.jar','plugins/ModelEngine/blueprints/elytrix_angel_wings.bbmodel',
                     model+'/left_wing_inner.json',model+'/right_wing_inner.json','rp/Elytrix-RP-1.21.zip']:
            assert (server/path).read_bytes()==archive.read(path),path
        assert (web/'Elytrix-RP-1.21.zip').read_bytes()==archive.read('rp/Elytrix-RP-1.21.zip')
    saved=list(backups.iterdir());assert len(saved)==1
    assert (saved[0]/'ElytrixRP-config.yml').read_text()==config_text
    assert (saved[0]/'ElytrixFreakModel.jar').read_bytes()==b'original jar'
    assert (saved[0]/'served-resource-pack.zip').read_bytes()==b'original served rp'
    assert saved[0].stat().st_mode & 0o777 == 0o700
    assert run(env).returncode==0, 'reinstall should be safe'
    assert len(list(backups.iterdir()))==2

    server,web,backups,config,_,env=make_fixture(root/'invalid-config')
    config.write_text(config_text+'sha1: second\n')
    result=run(env);assert result.returncode!=0
    assert (server/'plugins/ElytrixFreakModel.jar').read_bytes()==b'original jar'
    assert not backups.exists(), 'preflight failure must not create a backup or change files'

    server,web,backups,config,_,env=make_fixture(root/'tampered')
    bad=root/'tampered.zip'
    with zipfile.ZipFile(patch) as old,zipfile.ZipFile(bad,'w') as new:
        for info in old.infolist():
            data=old.read(info.filename)
            if info.filename=='plugins/ElytrixFreakModel.jar':data+=b'tampered'
            new.writestr(info,data)
    result=run(env,bad);assert result.returncode!=0
    assert (server/'plugins/ElytrixFreakModel.jar').read_bytes()==b'original jar'
    assert config.read_text()==config_text and not backups.exists()
print('Installer tests passed (preservation, backup, reinstall, failed preflight, checksum).')
