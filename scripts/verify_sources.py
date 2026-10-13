#!/usr/bin/env python3
"""Verify that all uploaded originals and downloaded cache files are unmodified."""
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
errors=[]
manifest=json.loads((ROOT/'sources/original-manifest.json').read_text())
entries={r['path']:r for r in manifest['files']}
lock=ROOT/'sources/download-lock.json'
if lock.exists():entries.update(json.loads(lock.read_text()))
for path,record in entries.items():
    p=ROOT/path
    if not p.exists():errors.append('MANCANTE: '+path);continue
    got=hashlib.sha256(p.read_bytes()).hexdigest()
    if got!=record['sha256']:errors.append('MODIFICATO: '+path)
if errors:
    print('\n'.join(errors));sys.exit(1)
print(f'OK: {len(entries)} file verificati con SHA-256.')
