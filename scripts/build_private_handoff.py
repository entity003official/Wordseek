"""Explicit private handoff. Includes ALL project files; never use for public releases."""
import argparse
import dataclasses
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT.parents[1] / 'handoff' / 'Beyond-Words-Private-20260927'
STAGE = DEST / 'Beyond-Words'
def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def stage():
    if (STAGE / 'SOURCE-INVENTORY.json').exists():
        finish_stage()
        return
    private = ROOT / 'outputs/private-handoff'
    private.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))
    from backend.app.core.config import settings
    write_json(private / 'private-settings.json', {
        'resolved_settings': dataclasses.asdict(settings),
        'project_environment': {k:v for k,v in os.environ.items() if k.startswith('BEYOND_WORDS_')},
        'note': 'Captured in packaging process; service-only inherited environment cannot be read from this process. Do not copy absolute source-machine paths.',
    })
    credentials = '# 私密凭据汇总\n\n仅随私密包交接，不得公开。原始文件仍完整保存在 api-key。\n\n'
    for path in sorted((ROOT / 'api-key').rglob('*')):
        if path.is_file():
            credentials += f'## {path.relative_to(ROOT).as_posix()}\n\n```text\n{path.read_text(encoding="utf-8-sig", errors="replace")}\n```\n\n'
    (private / 'private-credentials.md').write_text(credentials, encoding='utf-8')
    freeze = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, check=True, text=True)
    (private / 'python-freeze.txt').write_text(freeze.stdout, encoding='utf-8')
    inventory = []
    for path in sorted(ROOT.rglob('*')):
        if path.is_file():
            rel = path.relative_to(ROOT)
            target = STAGE / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.stat().st_size == path.stat().st_size and target.stat().st_mtime_ns == path.stat().st_mtime_ns:
                pass
            elif not target.exists() and rel.parts[0] in {'.venv', 'node_modules'}:
                # Same-volume immutable dependencies can be linked for staging;
                # ZIP stores their actual bytes and has no link dependency.
                os.link(path, target)
            else:
                shutil.copy2(path, target)
            inventory.append({'path':rel.as_posix(), 'size':path.stat().st_size, 'sha256':digest(target)})
    write_json(STAGE / 'SOURCE-INVENTORY.json', {'source':str(ROOT), 'files':inventory, 'excluded_project_files':[]})
    finish_stage()

def finish_stage():
    inventory = json.loads((STAGE / 'SOURCE-INVENTORY.json').read_text(encoding='utf-8'))['files']
    runtime = STAGE / '.runtime'
    if not (runtime / 'python/python.exe').exists():
        shutil.copytree(Path(sys.base_prefix), runtime / 'python', copy_function=os.link, ignore=lambda directory, names: ['site-packages'] if Path(directory).name == 'Lib' else [])
    node = Path(os.environ['USERPROFILE']) / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node'
    (runtime / 'node').mkdir(parents=True, exist_ok=True)
    if not (runtime / 'node/node.exe').exists():
        os.link(node / 'bin/node.exe', runtime / 'node/node.exe')
    write_json(STAGE / 'HANDOFF_COPY.json', {'created_at':datetime.now().astimezone().isoformat(), 'platform':'Windows x64', 'node':'24.19.0', 'python':'3.12.14', 'source':str(ROOT), 'credentials_included':True})
    with sqlite3.connect(STAGE / 'backend/data/beyond_words_v1.db') as database:
        check = database.execute('PRAGMA integrity_check').fetchall()
        if check != [('ok',)]:
            raise RuntimeError('Copied SQLite integrity failed')
        tables=[r[0] for r in database.execute("select name from sqlite_master where type='table'")]
        counts={name:database.execute('select count(*) from "'+name+'"').fetchone()[0] for name in tables}
    write_json(STAGE / 'outputs/private-handoff/database-inventory.json', counts)
    write_json(DEST / 'stage-status.json', {'stage':str(STAGE), 'source_files':len(inventory), 'sqlite_integrity':'ok'})
    print(json.dumps({'stage':str(STAGE), 'source_files':len(inventory), 'sqlite_integrity':'ok'}), flush=True)

def pack():
    if not STAGE.exists():
        raise SystemExit('Stage missing')
    # Capture files created while the website was reopened (e.g. audio/logs).
    source = json.loads((STAGE/'SOURCE-INVENTORY.json').read_text(encoding='utf-8'))
    known = {item['path']:item for item in source['files']}
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        target = STAGE / rel
        mutable = rel.parts[0] not in {'.venv', 'node_modules'}
        if rel.as_posix() not in known or mutable:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            known[rel.as_posix()] = {'path':rel.as_posix(),'size':target.stat().st_size,'sha256':digest(target)}
    source['files'] = sorted(known.values(), key=lambda item:item['path'])
    write_json(STAGE/'SOURCE-INVENTORY.json',source)
    # The user may reopen the live website during copying. Refresh the database
    # with SQLite's online backup API, retaining the raw copied file as well.
    db_path = STAGE / 'backend/data/beyond_words_v1.db'
    raw_path = STAGE / 'outputs/private-handoff/source-database-raw.db'
    shutil.copy2(db_path, raw_path)
    snapshot = STAGE / 'outputs/private-handoff/consistent-database.db'
    with sqlite3.connect(ROOT / 'backend/data/beyond_words_v1.db') as live:
        with sqlite3.connect(snapshot) as target:
            live.backup(target)
            if target.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise RuntimeError('Online backup integrity failed')
    shutil.copy2(snapshot, db_path)
    # Every original source file remains covered; the canonical DB is replaced
    # by a transactionally consistent snapshot and its copied bytes retained.
    source=json.loads((STAGE/'SOURCE-INVENTORY.json').read_text(encoding='utf-8'))
    for item in source['files']:
        if item['path']=='backend/data/beyond_words_v1.db':
            item['raw_copy_sha256']=item['sha256']
            item['raw_copy_path']=raw_path.relative_to(STAGE).as_posix()
            item['sha256']=digest(db_path)
            item['size']=db_path.stat().st_size
            item['snapshot_method']='SQLite online backup after website restart'
    write_json(STAGE/'SOURCE-INVENTORY.json',source)
    for item in source['files']:
        if digest(STAGE/item['path']) != item['sha256']:
            raise RuntimeError('Staged source changed: '+item['path'])
    report={'source_files':len(source['files']), 'excluded_project_files':[], 'sqlite_integrity':'ok', 'browser_snapshot_included':True, 'archive_validation':'Every zipped byte stream is read back and checked against SHA-256 and size during packaging.'}
    write_json(STAGE/'PACKAGING-REPORT.json',report)
    files=[]
    for path in sorted(STAGE.rglob('*')):
        if path.is_file() and path != STAGE / 'MANIFEST.json':
            files.append({'path':path.relative_to(STAGE).as_posix(),'size':path.stat().st_size,'sha256':digest(path)})
    write_json(STAGE/'MANIFEST.json',{'algorithm':'SHA-256','files':files,'note':'Manifest excludes itself. SOURCE-INVENTORY covers every file copied from the source project.'})
    ready=DEST/'Beyond-Words-Ready-Private-20260927.zip'
    with zipfile.ZipFile(ready,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5,allowZip64=True) as z:
        for path in sorted(STAGE.rglob('*')):
            if path.is_file(): z.write(path,'Beyond-Words/'+path.relative_to(STAGE).as_posix())
    with zipfile.ZipFile(ready) as z:
        for item in files:
            with z.open('Beyond-Words/'+item['path']) as stream:
                actual=hashlib.file_digest(stream,'sha256').hexdigest()
            if actual!=item['sha256']: raise RuntimeError('Archive checksum mismatch: '+item['path'])
        if len(z.infolist())!=len(files)+1: raise RuntimeError('Archive file count mismatch')
    print(json.dumps({'ready_zip':str(ready),'bytes':ready.stat().st_size,'verified_files':len(files)+1}),flush=True)
    full=DEST/'Beyond-Words-Full-Private-20260927.zip'
    shutil.copy2(ready,full)
    originals=Path('C:/Users/biiqm/Documents/xwechat_files/wxid_lzpq05gr5vqp22_6a16/msg/file/2026-09')
    original_inventory=[]
    with zipfile.ZipFile(full,'a',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        for name in ['260924anker.zip','Beyond-Words-Evaluation-Data-20260926.zip','Beyond-Words-Source-Handoff-20260926.zip']:
            path=originals/name
            rel='Beyond-Words/original-inputs/'+name
            z.write(path,rel)
            original_inventory.append({'path':rel,'size':path.stat().st_size,'sha256':digest(path)})
        z.writestr('Beyond-Words/ORIGINAL-INPUTS-MANIFEST.json',json.dumps(original_inventory,indent=2))
    with zipfile.ZipFile(full) as z:
        bad=z.testzip()
        if bad: raise RuntimeError('Full archive CRC failed: '+bad)
        for item in original_inventory:
            with z.open(item['path']) as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=item['sha256']: raise RuntimeError('Original input mismatch')
    (DEST/'SHA256SUMS.txt').write_text(''.join(digest(p)+'  '+p.name+'\n' for p in [ready,full]),encoding='utf-8')
    shutil.copy2(STAGE/'00-先读我-私密交接说明.md',DEST/'00-先读我-私密交接说明.md')
    write_json(DEST/'VERIFIED.json',{'ready':{'file':ready.name,'bytes':ready.stat().st_size,'verified_files':len(files)+1},'full':{'file':full.name,'bytes':full.stat().st_size,'extra_original_archives':3},'all_checks':'passed'})
    print(json.dumps({'full_zip':str(full),'bytes':full.stat().st_size,'checks':'passed'}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['stage','pack'])
    args=parser.parse_args()
    stage() if args.action=='stage' else pack()
