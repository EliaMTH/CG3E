#!/usr/bin/env python3
"""Verifica sources/ rispetto a sources/manifest.json, senza rete.

Controlla che ogni file registrato esista con lo SHA-256 registrato, che non ci
siano XSD non registrati e che ogni import degli schemi sia disponibile in locale.
Per le copie di un'ADE locale (origin "local") segnala, senza errore, quando il file
nella cartella dell'ADE è cambiato o non c'è più.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)
    root = ap.parse_args(argv).root.resolve()
    manifest = json.loads((root/'sources/manifest.json').read_text(encoding='utf-8'))
    files = {f['path']: f for f in manifest['files']}
    urls = {f['url'] for f in manifest['files']}
    errors = []
    for path, record in files.items():
        p = root/path
        if not p.exists():
            errors.append('MANCANTE: '+path)
        elif hashlib.sha256(p.read_bytes()).hexdigest() != record['sha256']:
            errors.append('MODIFICATO: '+path)
        for ref in record.get('references', []):
            if ref['url'] not in urls:
                errors.append(f'IMPORT NON LOCALE: {ref["url"]} (da {path})')
        if record.get('origin') == 'local':
            source = root/record['localPath']
            if not source.exists():
                print(f'AVVISO: {path}: il file di origine {record["localPath"]} non c\'è più.')
            elif hashlib.sha256(source.read_bytes()).hexdigest() != record['sha256']:
                print(f'AVVISO: {path}: {record["localPath"]} è cambiato; per usarlo esegui python scripts/fetch_sources.py --reuse-local.')
    for p in sorted((root/'sources').rglob('*.xsd')):
        rel = p.relative_to(root).as_posix()
        if rel not in files:
            errors.append('NON REGISTRATO: '+rel)
    for failure in manifest.get('failures', []):
        errors.append(f'NON ACQUISITO: {failure["url"]} ({failure["error"]})')
    for missing in manifest.get('unavailable', []):
        print(f'INFO: file facoltativo non disponibile alla fonte: {missing["url"]}')
    if errors:
        print('\n'.join(errors))
        sys.exit(1)
    print(f'OK: {len(files)} file verificati con SHA-256; tutti gli import sono locali.')


if __name__ == '__main__':
    main()
