#!/usr/bin/env python3
"""Esporta il vocabolario CityGML 3.0 in uso.

  python scripts/export.py city3d    --out citygml-codelists.city3d.json
  python scripts/export.py generator --out citygml-generator.zip
  python scripts/export.py standard  --out citygml-explorer.zip

city3d     code list (OGC 21-006r2, Annex E) e codeListUse, per l'editor di City3D
generator  XSD ufficiali, dizionari GML e JSON, xml-catalog.xml e
           citygml-generator.json, per costruire file CityGML
standard   explorer offline con fonti e dizionari GML e CSV, da consegnare a una persona

Legge data/catalog.json, il dizionario salvato (codelists/codelists.js) e
sources/. Se gli input non sono coerenti si ferma senza scrivere nulla. Con
--exported-at fisso l'output è identico byte per byte. Formati: docs/EXPORT.md.
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
import exporters


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('exporter', choices=sorted(exporters.EXPORTERS))
    ap.add_argument('--out', type=Path, required=True, help='File da scrivere.')
    ap.add_argument('--codelists', type=Path, help='Dizionario delle code list; predefinito codelists/codelists.js.')
    ap.add_argument('--exported-at', help='Data ISO 8601 con fuso orario, per un output riproducibile; predefinita l\'ora corrente.')
    ap.add_argument('--root', type=Path, default=exporters.ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.out.is_dir():
        print(f'ERRORE: --out indica una cartella: {args.out}.', file=sys.stderr)
        return 1
    try:
        when = exporters.parse_exported_at(args.exported_at)
        inputs = exporters.load(args.root, args.codelists)
        result = exporters.EXPORTERS[args.exporter](inputs, when)
    except exporters.ExportError as exc:
        print(f'ERRORE: {exc}', file=sys.stderr)
        return 1
    for warning in result.warnings:
        print(f'AVVISO: {warning}', file=sys.stderr)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    partial = args.out.with_name(args.out.name + '.partial')
    partial.write_bytes(result.data)
    os.replace(partial, args.out)
    details = ', '.join(f'{k} {v}' for k, v in result.summary.items())
    print(f'Scritto {args.out} ({len(result.data)} byte; {details}).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
