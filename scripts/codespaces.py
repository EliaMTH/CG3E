#!/usr/bin/env python3
"""Fissa nel dizionario i codeSpace delle code list compilate o modificate nel progetto.

  python scripts/codespaces.py --base https://example.org/citygml/codelists/ --version 1.0 --authority "Nome"

Per ogni lista trattata (senza --lists: le liste modificate, edited):
  codeSpace della lista e dei valori    <base><versione>/<Modulo>.<CodeList>.xml
  metadati authority e version          dai parametri; language da --language, se indicata
  identifier, dataType e namespace      nome della code list e namespace del suo modulo (data/catalog.json)

Le liste usate come sono pubblicate conservano il codeSpace della fonte. La politica
applicata è registrata in codeSpacePolicy. Il file è scritto con la serializzazione
di Salva nell'interfaccia; rieseguito con gli stessi argomenti non cambia nulla.
"""
from __future__ import annotations
import argparse
import copy
import json
import sys
from pathlib import Path
from urllib.parse import urlparse
import build_codelists
import exporters

SCHEMES = ('https', 'http', 'urn', 'tag')


class PolicyError(Exception):
    """Argomenti o dizionario non utilizzabili: il comando si ferma senza scrivere nulla."""


def module_namespaces(catalog):
    """Namespace di ogni modulo CityGML, dagli elementi degli schemi."""
    found = {}
    for node in catalog['nodes'].values():
        if node['family'] == 'CityGML' and '}element:' in node['id'] and node.get('namespace'):
            found.setdefault(node['module'], node['namespace'])
    return found


def check_arguments(base, version, authority):
    parsed = urlparse(base)
    if parsed.scheme not in SCHEMES:
        raise PolicyError(f'--base deve essere un URI assoluto ({", ".join(s + ":" for s in SCHEMES)}): {base}.')
    if parsed.scheme in ('http', 'https') and (not parsed.netloc or not base.endswith('/')):
        raise PolicyError(f'--base: un URL deve avere un host e terminare con "/": {base}.')
    if not version or '/' in version or any(c.isspace() for c in version):
        raise PolicyError(f'--version non valida: "{version}" (niente spazi né "/").')
    if not authority.strip():
        raise PolicyError('--authority non può essere vuota.')


def apply(dictionary, catalog, base, version, authority, language=None, lists=None, applied_at=None):
    """Applica la politica a una copia del dizionario. Restituisce (dizionario, trattate, non trattate)."""
    check_arguments(base, version, authority)
    result = copy.deepcopy(dictionary)
    code_lists = result['codeLists']
    unknown = sorted(set(lists or []) - set(code_lists))
    if unknown:
        raise PolicyError('Code list non presenti nel dizionario: ' + ', '.join(unknown) + '.')
    selected = sorted(lists) if lists else sorted(n for n, l in code_lists.items() if l.get('edited'))
    namespaces = module_namespaces(catalog)
    treated, skipped, problems = [], [], []
    for name in selected:
        lst = code_lists[name]
        if not any(exporters.is_real(v) for v in lst['values']):
            skipped.append(name)
            continue
        lang = language or (lst.get('metadata') or {}).get('language')
        if not lang:
            problems.append(f'{name}: lingua assente, indicala con --language')
            continue
        if lst['module'] not in namespaces:
            problems.append(f'{name}: namespace del modulo {lst["module"]} non trovato nel catalogo')
            continue
        space = f'{base}{version}/{lst["module"]}.{name}.xml'
        lst['identifier'] = name
        lst['codeSpace'] = space
        for value in lst['values']:
            value['codeSpace'] = space
        metadata = lst.setdefault('metadata', {})
        metadata.update(dataType=name, namespace=namespaces[lst['module']], language=lang, authority=authority, version=version)
        lst['edited'] = True
        treated.append(name)
    if problems:
        raise PolicyError('; '.join(problems) + '.')
    if treated:
        params = {'base': base, 'version': version, 'authority': authority}
        if language:
            params['language'] = language
        # Con gli stessi parametri la politica si estende alle nuove liste; con parametri diversi la sostituisce.
        previous = dictionary.get('codeSpacePolicy') or {}
        same = all(previous.get(k) == params.get(k) for k in ('base', 'version', 'authority', 'language'))
        names = sorted(set(treated) | set(previous.get('lists', []) if same else []))
        when = previous['appliedAt'] if same and names == previous.get('lists') else (applied_at or exporters.parse_exported_at()).isoformat()
        result['codeSpacePolicy'] = {**params, 'lists': names, 'appliedAt': when}
    return result, treated, skipped


def serialize(dictionary):
    """Stessa serializzazione di Salva nell'interfaccia (assets/app.js, serializeCodeLists)."""
    return build_codelists.serialize('CITYGML_CODELISTS', build_codelists.LOCAL_HEADER, dictionary).encode('utf-8')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', required=True, help='URI di base dei codeSpace, per esempio https://example.org/citygml/codelists/.')
    ap.add_argument('--version', required=True, help='Versione del dizionario, parte del codeSpace e dei metadati.')
    ap.add_argument('--authority', required=True, help='Autorità che mantiene le liste (metadati).')
    ap.add_argument('--language', help='Lingua dei valori (metadati); predefinita quella della lista.')
    ap.add_argument('--lists', help='Code list da trattare, separate da virgola; predefinite le liste modificate.')
    ap.add_argument('--dry-run', action='store_true', help='Mostra le modifiche senza scriverle.')
    ap.add_argument('--codelists', type=Path, help='Dizionario; predefinito codelists/codelists.js.')
    ap.add_argument('--applied-at', help='Data ISO 8601 con fuso orario da registrare; predefinita l\'ora corrente.')
    ap.add_argument('--root', type=Path, default=exporters.ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    path = args.codelists or args.root/'codelists/codelists.js'
    try:
        if not path.exists():
            raise PolicyError(f'Dizionario non trovato: {path}.')
        dictionary = exporters.read_json_assignment(path.read_text(encoding='utf-8'), exporters.DICTIONARY_VARIABLE)
        if dictionary.get('format') != 1:
            raise PolicyError(f'{path}: il dizionario non è nel formato 1.')
        catalog = json.loads((args.root/'data/catalog.json').read_text(encoding='utf-8'))
        lists = [n.strip() for n in args.lists.split(',') if n.strip()] if args.lists else None
        applied_at = exporters.parse_exported_at(args.applied_at) if args.applied_at else None
        result, treated, skipped = apply(dictionary, catalog, args.base, args.version, args.authority, args.language, lists, applied_at)
    except (PolicyError, exporters.ExportError) as exc:
        print(f'ERRORE: {exc}', file=sys.stderr)
        return 1
    for name in skipped:
        print(f'NON TRATTATA: {name}: nessun valore reale (solo segnaposto o vuota).')
    for name in treated:
        before, after = dictionary['codeLists'][name].get('codeSpace'), result['codeLists'][name]['codeSpace']
        print(f'{name}: {before or "(nessuno)"} -> {after}' if before != after else f'{name}: {after} (invariato)')
    if not treated:
        print('Nessuna lista da trattare: indica --lists o modifica una lista nell\'interfaccia.')
        return 0
    if result == dictionary:
        print('Nessuna modifica: il dizionario segue già la politica indicata.')
        return 0
    if args.dry_run:
        print('Prova: nessun file scritto.')
        return 0
    path.write_bytes(serialize(result))
    print(f'Scritto {path}: {len(treated)} liste trattate.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
