import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
errors = []
for item in manifest['files']:
    path = root / item['path']
    if not path.is_file() or path.stat().st_size != item['size']:
        errors.append(item['path'])
        continue
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != item['sha256']:
        errors.append(item['path'])
print(json.dumps({'checked': len(manifest['files']), 'mismatches': errors}, ensure_ascii=True))
raise SystemExit(1 if errors else 0)
