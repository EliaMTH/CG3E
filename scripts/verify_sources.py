#!/usr/bin/env python3
"""Verifica sources/ rispetto a sources/manifest.json, senza rete.

Controlla che ogni file registrato esista con lo SHA-256 registrato, che non ci
siano XSD non registrati e che ogni import degli schemi sia disponibile in locale.
"""
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT/'sources/manifest.json').read_text(encoding='utf-8'))
    files = {f['path']: f for f in manifest['files']}
    urls = {f['url'] for f in manifest['files']}
    errors = []
    for path, record in files.items():
        p = ROOT/path
        if not p.exists():
            errors.append('MANCANTE: '+path)
        elif hashlib.sha256(p.read_bytes()).hexdigest() != record['sha256']:
            errors.append('MODIFICATO: '+path)
        for ref in record.get('references', []):
            if ref['url'] not in urls:
                errors.append(f'IMPORT NON LOCALE: {ref["url"]} (da {path})')
    for p in sorted((ROOT/'sources').rglob('*.xsd')):
        rel = p.relative_to(ROOT).as_posix()
        if rel not in files:
            errors.append('NON REGISTRATO: '+rel)
    for failure in manifest.get('failures', []):
        errors.append(f'NON ACQUISITO: {failure["url"]} ({failure["error"]})')
    if errors:
        print('\n'.join(errors))
        sys.exit(1)
    print(f'OK: {len(files)} file verificati con SHA-256; tutti gli import sono locali.')


if __name__ == '__main__':
    main()
