"""Orchestrazione comune ai due comandi pubblici. Non lancia una webapp server.

La fase 1 costruisce un manifesto a partire dalle sorgenti attualmente presenti.
La fase 2 prova a recuperare SOLO gli import del profilo scelto.
La fase 3 rigenera il catalogo, anche se alcuni download sono falliti.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path
from build_catalog import Builder

ROOT = Path(__file__).resolve().parents[1]


def run(mode: str, argv=None):
    label = 'CityGML 3.0 + OWL' if mode == 'full' else 'CityGML 3.0 (solo XSD)'
    ap = argparse.ArgumentParser(description='Costruisci e attiva il catalogo '+label)
    ap.add_argument('--offline', action='store_true', help='Rigenera senza scaricare nulla (nessuna rete).')
    ap.add_argument('--verbose', action='store_true', help='Mostra tutti gli errori delle dipendenze.')
    ap.add_argument('--max-files', type=int, default=180, help='Limite di download per esecuzione (default 180).')
    ap.add_argument('--timeout', type=float, default=12, help='Timeout di ogni richiesta in secondi (default 12).')
    ap.add_argument('--w3c-editor-draft', action='store_true', help='Solo profilo completo: usa esplicitamente moduli W3C SSN draft.')
    ap.add_argument('--w3c-ref', default='gh-pages', help='Branch o commit dei moduli W3C in sviluppo.')
    ap.add_argument('--source-map', type=Path, default=None, help='Mappatura URL alternativa JSON validata dal downloader.')
    args = ap.parse_args(argv)
    if mode != 'full' and (args.w3c_editor_draft or args.source_map):
        ap.error('--w3c-editor-draft e --source-map sono disponibili solo nel profilo completo.')
    print('\n=== '+label+' ===', flush=True)
    print('FASE 1/3: indice e inventario degli import locali.', flush=True)
    Builder(ROOT,mode=mode).build()
    if not args.offline:
        print('FASE 2/3: scaricamento delle sole dipendenze mancanti del profilo.', flush=True)
        cmd=[sys.executable,str(ROOT/'scripts/download_dependencies.py'),
             '--root',str(ROOT),'--only','all' if mode=='full' else 'xsd',
             '--max-files',str(args.max_files),'--timeout',str(args.timeout)]
        if args.verbose:cmd.append('--verbose')
        if args.w3c_editor_draft:cmd.extend(['--w3c-editor-draft','--w3c-ref',args.w3c_ref])
        if args.source_map:cmd.extend(['--source-map',str(args.source_map.resolve())])
        result=subprocess.run(cmd, check=False)
        if result.returncode:
            print('AVVISO: alcuni import non acquisiti. Rigenero comunque il catalogo.',flush=True)
    else:
        print('FASE 2/3: salto download (--offline).',flush=True)
    print('FASE 3/3: rigenerazione e attivazione della modalita selezionata.',flush=True)
    data=Builder(ROOT,mode=mode).build()
    print('Catalogo ATTIVO:',label,flush=True)
    print('Apri index.html. File XSD mancanti e OWL irrisolti sono indicati nella sezione Sorgenti.',flush=True)
    return 0
