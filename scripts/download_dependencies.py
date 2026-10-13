#!/usr/bin/env python3
"""Download explicit XSD and OWL dependencies, recursively, to a local cache.

Original files are NEVER changed. A download is accepted only after parsing and
namespace/ontology-identity checks. HTTP endpoints are upgraded to HTTPS; this
changes transport, not namespace identifiers. Failed or unsupported imports stay
in download-report.json. No credentials, npm or browser extensions are required.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from lxml import etree as ET
from rdflib import Graph, RDF, OWL

ROOT=Path(__file__).resolve().parents[1]
XS='http://www.w3.org/2001/XMLSchema'
DEFAULT_HOSTS={
    'schemas.opengis.net','www.opengis.net','defs.opengis.net','www.w3.org',
    'opengeospatial.github.io','w3c.github.io',
    'dataset-dl.liris.cnrs.fr','def.isotc211.org','shapechange.net',
    'purl.obolibrary.org','raw.githubusercontent.com','github.com',
    'www.ontologydesignpatterns.org','ontologydesignpatterns.org',
    'purl.org','www.purl.org','w3id.org','standards.iso.org'
}
MAX_BYTES=15*1024*1024

# Document locations only. They NEVER change ontology IRIs or bypass checks.
GEOSPARQL_11 = 'http://www.opengis.net/ont/geosparql/1.1'
GEOSPARQL_11_DOCUMENT = 'https://opengeospatial.github.io/ogc-geosparql/geosparql11/geo.ttl'
W3C_CORE_FILES = {
    '': '', 'common': '-common', 'act': '-actuation',
    'obs': '-observation', 'sam': '-sampling', 'deprecated': '-deprecated',
}
W3C_REPO = 'https://raw.githubusercontent.com/w3c/sdw-sosa-ssn/'



def identity(uri):
    """Document aliases, not namespace equivalence: strip known syntax suffixes."""
    return re.sub(r'\.(ttl|owl|rdf)$','',str(uri)).rstrip('/')


def transport(uri):
    p=urlparse(uri)
    return urlunparse(p._replace(scheme='https' if p.scheme=='http' else p.scheme,fragment=''))


def allowed(uri, hosts):
    p=urlparse(uri)
    if p.scheme not in ('http','https') or p.hostname not in hosts or p.username or p.password:
        raise ValueError('Host o schema non autorizzato: '+uri)
    return uri


class SafeRedirect(HTTPRedirectHandler):
    def __init__(self, hosts):
        super().__init__(); self.hosts=hosts
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return super().redirect_request(req,fp,code,msg,hdrs,allowed(transport(newurl),self.hosts))


def rdf_format(payload, content_type=''):
    """Choose a parser from the document, not by trying Turtle on XML.

    The XML probe uses lxml with network access and entity expansion disabled.
    Turtle starting with an IRI such as <https://example.org/onto> is not XML.
    A misleading HTTP Content-Type must not override recognizable syntax.
    """
    try:
        root = ET.fromstring(payload, parser=ET.XMLParser(
            resolve_entities=False, no_network=True, load_dtd=False))
        if ET.QName(root).localname.lower() == 'html':
            raise ValueError('Il server ha restituito HTML, non un vocabolario.')
        return 'xml'
    except ET.XMLSyntaxError:
        pass
    text = payload.decode('utf-8-sig', errors='replace').lstrip()
    if text.startswith('<?xml') or re.match(r'<(?:rdf:RDF|owl:Ontology)(?:\s|>)', text):
        return 'xml'  # A malformed XML document must fail as XML, not as Turtle.
    if re.match(r'(?:@prefix|@base|PREFIX|BASE)\b', text, re.I) or text.startswith(('<', '#', '[')):
        return 'turtle'
    mime = content_type.split(';', 1)[0].strip().lower()
    return 'xml' if mime in ('application/rdf+xml', 'application/xml', 'text/xml') else 'turtle'


def decode_payload(payload, url, kind, expected, content_type=''):
    if b'<!doctype html' in payload[:500].lower() or b'<html' in payload[:500].lower():
        raise ValueError('Il server ha restituito HTML, non un vocabolario.')
    if kind == 'XSD':
        root = ET.fromstring(payload, parser=ET.XMLParser(resolve_entities=False, no_network=True))
        if root.tag != '{' + XS + '}schema':
            raise ValueError('La radice non e xs:schema.')
        actual = root.get('targetNamespace', '')
        if expected and actual and actual != expected:
            raise ValueError('Namespace diverso da quello richiesto: ' + actual)
        imports = []
        for el in root:
            if isinstance(el.tag, str) and ET.QName(el).localname in ('import', 'include', 'redefine') and el.get('schemaLocation'):
                imports.append({'url': urljoin(url, el.get('schemaLocation')), 'kind': 'XSD',
                                'namespace': el.get('namespace', actual)})
        return '.xsd', actual, imports
    fmt = rdf_format(payload, content_type)
    try:
        g = Graph().parse(data=payload, format=fmt, publicID=url)
    except Exception as exc:
        raise ValueError('RDF non valido (' + fmt + '): ' + str(exc)) from exc
    # Check ontology identity AFTER parsing; never mask this error by retrying
    # another serialization, and never substitute a similarly named ontology.
    ontologies = set(g.subjects(RDF.type, OWL.Ontology))
    ids = {identity(s) for s in ontologies}
    ids |= {identity(v) for s in ontologies for v in g.objects(s, OWL.versionIRI)}
    if expected and identity(expected) not in ids:
        raise ValueError('IRI/versionIRI non corrispondente. Richiesto: ' + str(expected)
                         + '; dichiarati: ' + str(sorted(ids)))
    imports = [{'url': str(v), 'kind': 'OWL', 'namespace': str(v)} for v in g.objects(None, OWL.imports)]
    return '.ttl' if fmt == 'turtle' else '.owl', sorted(ids)[0] if ids else '', imports


def load_source_map(path):
    """Read explicit IRI -> URL lists. Host and identity checks still apply."""
    if path is None:
        return {}
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('--source-map deve contenere un oggetto JSON IRI -> URL.')
    result = {}
    for iri, locations in data.items():
        if isinstance(locations, str):
            locations = [locations]
        if not isinstance(locations, list) or not all(isinstance(u, str) for u in locations):
            raise ValueError('Ogni IRI in --source-map deve avere una lista di URL.')
        if any(urlparse(u).scheme not in ('http', 'https') for u in locations):
            raise ValueError('La mappa accetta solo URL HTTP/HTTPS; non file locali.')
        result[identity(iri)] = [transport(u) for u in locations]
    return result


def w3c_draft_document(iri, ref='gh-pages'):
    """Curated core-module names from the W3C repository, not a namespace rewrite.

    Only the 2023 edition is mapped. The 2017 edition and unknown paths are not
    redirected to the draft. Graph identity is verified after every download.
    """
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', ref) or ref in ('.', '..'):
        raise ValueError('--w3c-ref deve essere un nome di branch semplice o un commit SHA.')
    match = re.fullmatch(r'http://www\.w3\.org/ns/(sosa|ssn)(?:/(.*))?', identity(iri))
    if not match:
        return None
    family, module = match.group(1), match.group(2) or ''
    if module == '2023':
        module = ''
    elif module.startswith('2023/'):
        module = module[5:]
    if module not in W3C_CORE_FILES:
        return None
    filename = family + W3C_CORE_FILES[module] + '.ttl'
    return W3C_REPO + ref + '/ssn/rdf/ontology/core/' + filename


def candidate_urls(url, kind, *, w3c_editor_draft=False, w3c_ref='gh-pages', source_map=None):
    u = transport(url)
    candidates = list((source_map or {}).get(identity(url), []))
    if kind == 'OWL' and w3c_editor_draft:
        draft = w3c_draft_document(url, w3c_ref)
        if draft:
            # Keep this module family on a consistent repository revision instead
            # of accepting the older, unversioned SSN document first.
            candidates.append(draft)
            # Do not fall back to unversioned endpoints that may serve SSN 2017.
            return list(dict.fromkeys(candidates))
    candidates.append(u)
    if kind == 'OWL' and identity(url) == GEOSPARQL_11:
        candidates.append(GEOSPARQL_11_DOCUMENT)
    if kind == 'OWL' and not re.search(r'\.(ttl|owl|rdf)$', u):
        candidates.extend([u.rstrip('/')+'.ttl', u.rstrip('/')+'.rdf', u.rstrip('/')+'.owl'])
    return list(dict.fromkeys(candidates))


def cache_path(root,url,suffix,kind="XSD"):
    p=urlparse(url)
    # Deliberately preserve URL directory structure for relative schema includes.
    parts=[re.sub(r'[^A-Za-z0-9_.-]','_',part) for part in p.path.split('/') if part not in ('','.','..')]
    if not parts:parts=['index']
    if not parts[-1].endswith(suffix):parts[-1]+=suffix
    if p.query:parts[-1]=hashlib.sha256(url.encode()).hexdigest()[:12]+'-'+parts[-1]
    # Two isolated dependency sets: mode citygml never reads OWL files.
    folder = 'owl' if kind == 'OWL' else 'citygml'
    return root/'sources'/'dependencies'/folder/p.hostname/Path(*parts)


def run(args):
    root=args.root.resolve()
    manifest_path=root/'sources/dependency-manifest.json'
    if not manifest_path.exists():
        raise ValueError('Esegui prima scripts/build_catalog.py.')
    manifest=json.loads(manifest_path.read_text())
    files=manifest['files']
    queue=deque({'url':d['url'],'kind':'XSD' if d['kind'].startswith('xsd:') else 'OWL',
                 'namespace':d.get('namespace',''),'from':d['from']}
                for d in manifest['dependencies'] if d['status']=='missing' and (args.only=='all' or args.only==('xsd' if d['kind'].startswith('xsd:') else 'owl')))
    source_map=load_source_map(getattr(args,'source_map',None))
    draft_enabled=getattr(args,'w3c_editor_draft',False)
    w3c_ref=getattr(args,'w3c_ref','gh-pages')
    if draft_enabled:
        w3c_draft_document('http://www.w3.org/ns/ssn/obs/',w3c_ref)
        print('AVVISO: sorgenti W3C in sviluppo abilitate; revisione '+w3c_ref+'. Non SSN 2017.',file=sys.stderr)
    hosts=DEFAULT_HOSTS|set(args.allow_host)
    opener=build_opener(SafeRedirect(hosts))
    lock_path=root/'sources/download-lock.json'
    lock=json.loads(lock_path.read_text()) if lock_path.exists() else {}
    seen=set();records=[];count=0
    while queue:
        item=queue.popleft();url=item['url'];key=identity(url)
        if key in seen:continue
        seen.add(key)
        # Reuse original, already-resolved schema/ontology files instead of replacing them.
        local=[]
        if item['kind']=='XSD':
            local=[f['path'] for f in files if f['format']=='XSD' and f['name']==Path(urlparse(url).path).name and f['namespace']==item['namespace']]
        else:
            local=[f['path'] for f in files if f['format']=='OWL' and identity(f['namespace'])==key]
        if local:
            records.append({**item,'status':'already-local','paths':local});continue
        if args.dry_run:
            print(item['kind'],url);records.append({**item,'status':'planned'});continue
        if count>=args.max_files:
            records.append({**item,'status':'not-attempted','error':'Raggiunto --max-files'});continue
        count+=1
        found=next(((p,v) for p,v in lock.items() if identity(v.get('requestedUrl',''))==key and (root/p).exists()),None)
        if found and not args.refresh:
            path_str,meta=found
            payload=(root/path_str).read_bytes()
            digest=hashlib.sha256(payload).hexdigest()
            if digest!=meta['sha256']:
                records.append({**item,'status':'failed','error':'Hash della cache non corrispondente: '+path_str});continue
            queue.extend(meta.get('imports',[]));records.append({**item,'status':'cached','path':path_str});continue
        errors=[];success=False
        for candidate in candidate_urls(url,item['kind'],w3c_editor_draft=draft_enabled,
                                        w3c_ref=w3c_ref,source_map=source_map):
            try:
                allowed(candidate,hosts)
                headers={'Accept':'application/xml,text/xml;q=0.9' if item['kind']=='XSD' else 'text/turtle,application/rdf+xml;q=0.9',
                         'User-Agent':'CityGML-Explorer-dependency-fetcher/1.2'}
                with opener.open(Request(candidate,headers=headers),timeout=args.timeout) as r:
                    final=allowed(r.geturl(),hosts)
                    content_type=r.headers.get('Content-Type','')
                    payload=r.read(MAX_BYTES+1)
                if len(payload)>MAX_BYTES:raise ValueError('File oltre il limite di 15 MiB.')
                suffix,namespace,imports=decode_payload(payload,final,item['kind'],item['namespace'],content_type)
                path=cache_path(root,url,suffix,kind=item['kind']);path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(payload)
                relative=str(path.relative_to(root)).replace('\\','/')
                is_w3c_draft = candidate.startswith(W3C_REPO) and '/ssn/rdf/ontology/core/' in candidate
                lock[relative]={'requestedUrl':url,'url':final,'sha256':hashlib.sha256(payload).hexdigest(),
                                'retrievedAt':datetime.now(timezone.utc).isoformat(),'imports':imports,
                                'namespace':namespace,'format':item['kind'],'contentType':content_type,
                                'sourcePolicy':'w3c-editor-draft' if is_w3c_draft else 'identity-checked',
                                'repositoryRef':w3c_ref if is_w3c_draft else None}
                records.append({**item,'status':'downloaded','path':relative,'actualUrl':final,
                                'sourcePolicy':lock[relative]['sourcePolicy']})
                print('OK',relative, '[W3C editor draft]' if is_w3c_draft else '')
                queue.extend(imports)
                files.append({'path':relative,'name':path.name,'namespace':namespace,'format':item['kind'],'contentType':content_type})
                success=True;break
            except Exception as exc:
                errors.append(candidate+' : '+type(exc).__name__+': '+str(exc))
        if not success:
            print('NON ACQUISITO',url,file=sys.stderr)
            details=errors if getattr(args,'verbose',False) else errors[-1:]
            for detail in details:
                print('  '+detail,file=sys.stderr)
            if not getattr(args,'verbose',False):
                print('  Tutti i tentativi: sources/download-report.json (oppure --verbose).',file=sys.stderr)
            records.append({**item,'status':'failed','errors':errors})
        lock_path.write_text(json.dumps(lock,indent=2),encoding='utf-8')
    if not args.dry_run:
        lock_path.write_text(json.dumps(lock,indent=2),encoding='utf-8')
        (root/'sources/download-report.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    failed=sum(r['status'] in ('failed','not-attempted') for r in records)
    print(f'{len(records)} dipendenze analizzate; {failed} non acquisite.')
    if not args.dry_run:print('Ora rigenera il catalogo con build_citygml.py o build_citygml_owl.py.')
    return 1 if failed else 0


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--dry-run',action='store_true',help='Elenca gli import mancanti senza rete o scritture.')
    ap.add_argument('--only',choices=('all','xsd','owl'),default='all')
    ap.add_argument('--timeout',type=float,default=15)
    ap.add_argument('--max-files',type=int,default=180)
    ap.add_argument('--verbose',action='store_true',help='Mostra tutte le cause dei download falliti.')
    ap.add_argument('--w3c-editor-draft',action='store_true',help='Usa esplicitamente i moduli SOSA/SSN 2023 del repository W3C in sviluppo; conserva controlli IRI e hash.')
    ap.add_argument('--w3c-ref',default='gh-pages',help='Branch o commit W3C per --w3c-editor-draft; default gh-pages. Non aggiorna file gia in cache.')
    ap.add_argument('--source-map',type=Path,help='JSON con IRI -> URL di documenti alternativi; non modifica gli IRI e non disabilita i controlli.')
    ap.add_argument('--refresh',action='store_true',help='Aggiorna intenzionalmente la cache; gli hash cambieranno.')
    ap.add_argument('--allow-host',action='append',default=[],help='Autorizza un ulteriore host di download pubblico.')
    args=ap.parse_args()
    try:sys.exit(run(args))
    except (OSError,ValueError) as exc:print('ERRORE:',exc,file=sys.stderr);sys.exit(2)


if __name__=='__main__':main()
