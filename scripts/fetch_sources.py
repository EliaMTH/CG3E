#!/usr/bin/env python3
"""Scarica dalle fonti ufficiali gli XSD di CityGML 3.0 e tutti i loro import.

Legge config/sources.json e segue ricorsivamente xs:import, xs:include e
xs:redefine. Ogni file e salvato in sources/<host>/<percorso>, con la stessa
struttura dell'URL, cosi gli schemaLocation relativi restano risolvibili.
Scrive sources/manifest.json (URL, data, Last-Modified, versione, SHA-256) e
sources/xml-catalog.xml per l'uso offline con strumenti XML.

Le richieste usano HTTPS; nel manifest resta l'URL http:// scritto negli schemi.
Nessun file viene accettato se non e uno xs:schema con il namespace atteso.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
import ssl
from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
XS = 'http://www.w3.org/2001/XMLSchema'
MAX_BYTES = 15 * 1024 * 1024
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
    parts = [part for part in p.path.split('/') if part not in ('', '.', '..')]
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


def download(opener, url, hosts, timeout):
    request = Request(transport(url), headers={'User-Agent': USER_AGENT})
    with opener.open(request, timeout=timeout) as response:
        final = check_host(response.geturl(), hosts)
        payload = response.read(MAX_BYTES + 1)
        headers = {'lastModified': response.headers.get('Last-Modified'), 'etag': response.headers.get('ETag')}
    if len(payload) > MAX_BYTES:
        raise ValueError('File oltre il limite di 15 MiB.')
    return final, payload, headers


def run(args):
    root = args.root.resolve()
    config = json.loads((root / 'config/sources.json').read_text(encoding='utf-8'))
    hosts = set(config['allowedHosts'])
    opener = build_opener(SafeRedirect(hosts), HTTPSHandler(context=tls_context()))
    queue = deque({'url': canonical(u), 'kind': 'xsd', 'namespace': None, 'from': 'config/sources.json'}
                  for u in config['schemas'])
    queue.extend({'url': canonical(u), 'kind': 'document', 'from': 'config/sources.json'} for u in config['documents'])
    entries, failures, seen = {}, [], set()
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
            elif payload[:500].lower().lstrip().startswith((b'<!doctype html', b'<html')):
                raise ValueError('Il server ha restituito HTML.')
            record['path'] = local_path(root, url).relative_to(root).as_posix()
            entries[url] = record
            print('OK', record['path'], flush=True)
        except Exception as exc:
            failures.append({'url': url, 'requestedBy': item['from'], 'error': f'{type(exc).__name__}: {exc}'})
            print('NON ACQUISITO', url, '-', type(exc).__name__, exc, file=sys.stderr, flush=True)
    previous = root / 'sources/manifest.json'
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
                'files': files, 'failures': failures}
    previous.parent.mkdir(parents=True, exist_ok=True)
    previous.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    write_xml_catalog(root, sorted({urlparse(r['url']).hostname for r in files}))
    print(f'{len(files)} file salvati in sources/; {len(failures)} non acquisiti.')
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
    args = ap.parse_args()
    raise SystemExit(run(args))


if __name__ == '__main__':
    main()
