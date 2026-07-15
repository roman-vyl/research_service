from __future__ import annotations
import hashlib, json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'legacy_source/bbb/copy_manifest.json').read_text())
for item in manifest['files']:
 p=root/'legacy_source/bbb'/item['path']
 if not p.is_file(): raise SystemExit(f'missing: {item["path"]}')
 h=hashlib.sha256(p.read_bytes()).hexdigest()
 if h != item['sha256']: raise SystemExit(f'hash mismatch: {item["path"]}')
print(f'research_service legacy source: PASS ({len(manifest["files"])} files)')
