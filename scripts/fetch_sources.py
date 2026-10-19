#!/usr/bin/env python3
"""Scarica dalle fonti ufficiali gli XSD di CityGML 3.0 e tutti i loro import.

Legge config/sources.json e segue ricorsivamente xs:import, xs:include e
xs:redefine degli schemi. Scarica anche i documenti elencati (testo, HTML o
zip), senza modificarli. Ogni file e salvato in sources/<host>/<percorso>, con
la stessa struttura dell'URL, cosi gli schemaLocation relativi restano risolvibili.
Scrive sources/manifest.json (URL, data, Last-Modified, versione, SHA-256) e
sources/xml-catalog.xml per l'uso offline con strumenti XML.

Le richieste usano HTTPS; per gli schemi il manifest registra l'URL http://
scritto negli schemi stessi. Uno schema e accettato solo se e uno xs:schema con
il namespace atteso; un documento solo se corrisponde al formato dichiarato.

Con --reuse-local i file gia presenti in sources/, con lo SHA-256 registrato nel
manifest, non vengono riscaricati: il manifest ne conserva URL, data di download
e intestazioni originali. Si scaricano solo i file nuovi o modificati localmente.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import sys
import zipfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
import ssl
from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
XS = 'http://www.w3.org/2001/XMLSchema'
MAX_BYTES = 64 * 1024 * 1024
USER_AGENT = 'CityGML-Explorer-fetch-sources/2.0'


def canonical(url):
    """Identita dell'URL come scritto negli schemi: schema http, senza frammento."""
    p = urlparse(url)
    return urlunparse(p._replace(scheme='http' if p.scheme == 'https' else p.scheme, fragment=''))


def transport(url):
    p = urlparse(url)
    return urlunparse(p._replace(scheme='https' if p.scheme == 'http' else p.scheme, fragment=''))


def check_host(url, hosts):
    p = urlparse(url)
    if p.scheme not in ('http', 'https') or p.hostname not in hosts or p.username or p.password:
        raise ValueError('Host non autorizzato: ' + url)
    return url


def local_path(root, url):
    p = urlparse(url)
    parts = [unquote(part) for part in p.path.split('/') if part not in ('', '.', '..')]
    if not parts:
        raise ValueError('URL senza percorso di file: ' + url)
    return root / 'sources' / p.hostname / Path(*parts)


class SafeRedirect(HTTPRedirectHandler):
    def __init__(self, hosts):
        super().__init__()
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return super().redirect_request(req, fp, code, msg, hdrs, check_host(newurl, self.hosts))


def tls_context():
    """Verifica TLS con il bundle certifi se installato, altrimenti con quello di sistema."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def parse_schema(payload, url, expected_namespace=None):
    """Restituisce (targetNamespace, version, riferimenti) di uno xs:schema."""
    head = payload[:500].lower()
    if b'<!doctype html' in head or b'<html' in head:
        raise ValueError('Il server ha restituito HTML, non uno schema.')
    root = ET.fromstring(payload, parser=ET.XMLParser(resolve_entities=False, no_network=True, load_dtd=False))
    if root.tag != '{' + XS + '}schema':
        raise ValueError('La radice non e xs:schema.')
    namespace = root.get('targetNamespace', '')
    if expected_namespace is not None and namespace != expected_namespace:
        raise ValueError(f'Namespace {namespace!r} diverso da quello richiesto {expected_namespace!r}.')
    refs = []
    for el in root:
        if not isinstance(el.tag, str):
            continue
        tag = ET.QName(el).localname
        if tag in ('import', 'include', 'redefine') and el.get('schemaLocation'):
            refs.append({'url': canonical(urljoin(url, el.get('schemaLocation'))), 'kind': 'xsd:' + tag,
                         'namespace': el.get('namespace', '') if tag == 'import' else namespace})
    return namespace, root.get('version'), refs


def check_document(payload, format_):
    """Controlla che un documento corrisponda al formato dichiarato in config/sources.json."""
    head = payload[:1000].lower().lstrip()
    is_html = head.startswith((b'<!doctype html', b'<html'))
    if format_ == 'text' and is_html:
        raise ValueError('Il server ha restituito HTML invece di un testo.')
    if format_ == 'html' and not is_html:
        raise ValueError('Il documento non e HTML.')
    if format_ == 'zip':
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                if archive.testzip() is not None:
                    raise ValueError('Archivio zip danneggiato.')
        except zipfile.BadZipFile as exc:
            raise ValueError('Il documento non e un archivio zip.') from exc
    if format_ == 'gml-dictionary':
        root = ET.fromstring(payload, parser=ET.XMLParser(resolve_entities=False, no_network=True, load_dtd=False))
        if root.tag != '{http://www.opengis.net/gml/3.2}Dictionary':
            raise ValueError('La radice non e gml:Dictionary.')
    if format_ not in ('text', 'html', 'zip', 'gml-dictionary'):
        raise ValueError('Formato di documento sconosciuto: ' + str(format_))


def download(opener, url, hosts, timeout):
    request = Request(transport(url), headers={'User-Agent': USER_AGENT})
    with opener.open(request, timeout=timeout) as response:
        final = check_host(response.geturl(), hosts)
        payload = response.read(MAX_BYTES + 1)
        headers = {'lastModified': response.headers.get('Last-Modified'), 'etag': response.headers.get('ETag')}
    if len(payload) > MAX_BYTES:
        raise ValueError('File oltre il limite di 64 MiB.')
    return final, payload, headers


def reusable(root, record):
    """Contenuto del file locale se coincide con lo SHA-256 registrato nel manifest, altrimenti None."""
    if not record:
        return None
    path = root / record['path']
    if not path.is_file():
        return None
    payload = path.read_bytes()
    return payload if hashlib.sha256(payload).hexdigest() == record['sha256'] else None


def run(args):
    root = args.root.resolve()
    config = json.loads((root / 'config/sources.json').read_text(encoding='utf-8'))
    hosts = set(config['allowedHosts'])
    opener = build_opener(SafeRedirect(hosts), HTTPSHandler(context=tls_context()))
    queue = deque({'url': canonical(u), 'kind': 'xsd', 'namespace': None, 'from': 'config/sources.json'}
                  for u in config['schemas'])
    for entry in config['documents']:
        entry = {'url': entry, 'format': 'text'} if isinstance(entry, str) else entry
        queue.append({'url': entry['url'], 'kind': 'document', 'format': entry.get('format', 'text'),
                      'role': entry.get('role'), 'from': 'config/sources.json'})
    samples = config.get('codeListSamples')
    for name in (samples or {}).get('files', []):
        queue.append({'url': samples['baseUrl'] + name, 'kind': 'document', 'format': 'gml-dictionary',
                      'role': 'codelist-sample', 'optional': True, 'from': 'config/sources.json'})
    entries, failures, unavailable, seen = {}, [], [], set()
    previous = root / 'sources/manifest.json'
    recorded = {}
    if getattr(args, 'reuse_local', False) and previous.exists():
        recorded = {r['url']: r for r in json.loads(previous.read_text(encoding='utf-8')).get('files', [])}
    while queue:
        item = queue.popleft()
        url = item['url']
        if url in seen:
            if url in entries and item['from'] not in entries[url]['requestedBy']:
                entries[url]['requestedBy'].append(item['from'])
            continue
        seen.add(url)
        try:
            check_host(url, hosts)
            kept = reusable(root, recorded.get(url))
            if kept is not None:
                payload = kept
                record = {**recorded[url], 'requestedBy': [item['from']], 'payload': payload}
            else:
                final, payload, headers = download(opener, url, hosts, args.timeout)
                record = {'url': url, 'downloadedFrom': final, 'kind': item['kind'],
                          'retrievedAt': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                          'lastModified': headers['lastModified'], 'etag': headers['etag'],
                          'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload),
                          'requestedBy': [item['from']], 'payload': payload}
            if item['kind'] == 'xsd':
                namespace, version, refs = parse_schema(payload, url, item['namespace'])
                record.update(targetNamespace=namespace, schemaVersion=version, references=refs)
                queue.extend({'url': r['url'], 'kind': 'xsd', 'namespace': r['namespace'], 'from': url} for r in refs)
            else:
                check_document(payload, item['format'])
                record['format'] = item['format']
                if item.get('role'):
                    record['role'] = item['role']
            record['path'] = local_path(root, url).relative_to(root).as_posix()
            entries[url] = record
            print('RIUSATO' if kept is not None else 'OK', record['path'], flush=True)
        except Exception as exc:
            problem = {'url': url, 'requestedBy': item['from'], 'error': f'{type(exc).__name__}: {exc}'}
            if item.get('optional'):
                unavailable.append(problem)
                print('NON DISPONIBILE ALLA FONTE', url, '-', type(exc).__name__, exc, flush=True)
            else:
                failures.append(problem)
                print('NON ACQUISITO', url, '-', type(exc).__name__, exc, file=sys.stderr, flush=True)
    old_paths = set()
    if previous.exists():
        old_paths = {f['path'] for f in json.loads(previous.read_text(encoding='utf-8')).get('files', [])}
    for record in entries.values():
        path = root / record['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(record.pop('payload'))
    new_paths = {r['path'] for r in entries.values()}
    for stale in sorted(old_paths - new_paths):
        (root / stale).unlink(missing_ok=True)
    files = sorted(entries.values(), key=lambda r: r['path'])
    manifest = {'generatedBy': 'scripts/fetch_sources.py', 'config': 'config/sources.json',
                'retrievedAt': max((r['retrievedAt'] for r in files), default=None),
                'files': files, 'failures': failures, 'unavailable': unavailable}
    previous.parent.mkdir(parents=True, exist_ok=True)
    previous.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    write_xml_catalog(root, sorted({urlparse(r['url']).hostname for r in files if r['kind'] == 'xsd'}))
    print(f'{len(files)} file salvati in sources/; {len(failures)} non acquisiti; '
          f'{len(unavailable)} facoltativi non disponibili alla fonte.')
    return 1 if failures else 0


def write_xml_catalog(root, hostnames):
    ns = 'urn:oasis:names:tc:entity:xmlns:xml:catalog'
    catalog = ET.Element('{%s}catalog' % ns, nsmap={None: ns})
    for host in hostnames:
        for scheme in ('http', 'https'):
            ET.SubElement(catalog, '{%s}rewriteURI' % ns, uriStartString=f'{scheme}://{host}/', rewritePrefix=f'{host}/')
            ET.SubElement(catalog, '{%s}rewriteSystem' % ns, systemIdStartString=f'{scheme}://{host}/', rewritePrefix=f'{host}/')
    (root / 'sources/xml-catalog.xml').write_bytes(ET.tostring(catalog, pretty_print=True, xml_declaration=True, encoding='UTF-8'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--timeout', type=float, default=30, help='Timeout di ogni richiesta in secondi (default 30).')
    ap.add_argument('--reuse-local', action='store_true',
                    help='Non riscarica i file presenti in sources/ con lo SHA-256 del manifest; scarica solo i nuovi.')
    args = ap.parse_args()
    raise SystemExit(run(args))


if __name__ == '__main__':
    main()
