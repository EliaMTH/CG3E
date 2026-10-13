#!/usr/bin/env python3
"""Read the existing dependency report. Does not download or modify anything."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    path = args.root / 'sources/download-report.json'
    try:
        records = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(records, list):
            raise ValueError('Il report deve essere una lista JSON.')
    except (OSError, ValueError) as exc:
        parser.exit(2, f'Impossibile leggere {path}: {exc}\n')
    failed = [r for r in records if r.get('status') in ('failed', 'not-attempted')]
    print(f'Report: {path}\nImport non acquisiti: {len(failed)}')
    for record in failed:
        print('\n' + record.get('url', '(URL non disponibile)'))
        if record.get('from'):
            print('  Richiesto da: ' + record['from'])
        errors = record.get('errors') or [record.get('error', 'Dettaglio non registrato.')]
        for error in errors:
            print('  ' + str(error))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
