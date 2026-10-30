#!/usr/bin/env python3
"""Export del vocabolario CityGML 3.0 in uso: parti comuni e i tre exporter.

Input: data/catalog.json, il dizionario delle code list salvato
(codelists/codelists.js) e sources/. Nessun accesso alla rete.

  city3d     JSON con le code list (Annex E di OGC 21-006r2) e codeListUse
  generator  zip con XSD ufficiali, dizionari GML e JSON, xml-catalog.xml e
             citygml-generator.json (struttura risolta e regole)
  standard   zip con l'explorer offline, le fonti e i dizionari GML e CSV

Il comando è scripts/export.py; formati e campi sono descritti in docs/EXPORT.md.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
FORMAT_VERSION = 1
GML_NS = 'http://www.opengis.net/gml/3.2'
CMD_NS = 'http://www.opengis.net/citygml/codelistmetadata/3.0'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
CATALOG_NS = 'urn:oasis:names:tc:entity:xmlns:xml:catalog'
GML_XSD = 'http://schemas.opengis.net/gml/3.2.1/gml.xsd'
CMD_XSD = 'http://schemas.opengis.net/citygml/codelistmetadata/3.0/codeListMetaData.xsd'
PROFILE_NS = 'http://www.opengis.net/citygml/profiles/base/3.0'
PROFILE_XSD = 'http://schemas.opengis.net/citygml/profiles/base/3.0/CityGML.xsd'
XS_NS = 'http://www.w3.org/2001/XMLSchema'
DRIVER = 'CityGML-ADE.xsd'
PLACEHOLDER = re.compile(r'^\{example-\d+\}$')
METADATA = ('dataType', 'namespace', 'language', 'authority', 'version')
SCHEMA_HOSTS = ('schemas.opengis.net', 'www.w3.org')
DICTIONARY_VARIABLE = 'CITYGML_CODELISTS'


class ExportError(Exception):
    """Input non utilizzabile: il comando si ferma senza scrivere nulla."""


@dataclass
class Inputs:
    root: Path
    catalog: dict
    manifest: dict
    dictionary: dict
    dictionary_bytes: bytes
    default_dictionary: dict | None


@dataclass
class Result:
    data: bytes
    summary: dict
    warnings: list = field(default_factory=list)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_json_assignment(text, variable):
    """Il valore JSON assegnato a window.<variable> in un file .js del progetto."""
    match = re.search(r'window\.%s\s*=\s*' % re.escape(variable), text)
    if not match:
        raise ExportError(f'window.{variable} non trovato.')
    try:
        return json.JSONDecoder().raw_decode(text, match.end())[0]
    except json.JSONDecodeError as exc:
        raise ExportError(f'window.{variable}: JSON non valido ({exc}).') from exc


def code_list_key(node):
    """Chiave di una code list nel dizionario: il nome qualificato, uguale al nome per le liste di CityGML
    (tade:EnergyClassValue per una lista di un'ADE)."""
    return node.get('qname') or node['name']


def load(root=ROOT, codelists=None):
    """Legge e controlla gli input. Solleva ExportError se catalogo, fonti o dizionario non sono coerenti."""
    root = Path(root).resolve()
    catalog = json.loads((root/'data/catalog.json').read_text(encoding='utf-8'))
    manifest = json.loads((root/'sources/manifest.json').read_text(encoding='utf-8'))
    records = {r['path']: r for r in manifest['files']}
    standard = catalog.get('standard') or {}
    used = list(catalog['files']) + [d for d in (standard.get('document'), (standard.get('encoding') or {}).get('document'),
                                                 standard.get('umlModel')) if d]
    stale = sorted(f['path'] for f in used if records.get(f['path'], {}).get('sha256') != f['sha256'])
    if stale:
        raise ExportError('data/catalog.json non corrisponde a sources/manifest.json per: ' + ', '.join(stale)
                          + '. Rigenera il catalogo con python scripts/build_catalog.py.')
    path = Path(codelists) if codelists else root/'codelists/codelists.js'
    if not path.exists():
        raise ExportError(f'Dizionario non trovato: {path}.')
    raw = path.read_bytes()
    dictionary = read_json_assignment(raw.decode('utf-8'), DICTIONARY_VARIABLE)
    if dictionary.get('format') != 1 or not isinstance(dictionary.get('codeLists'), dict):
        raise ExportError(f'{path}: il dizionario non è nel formato 1.')
    expected = {code_list_key(n) for n in catalog['nodes'].values() if n['kind'] == 'codelist'}
    found = set(dictionary['codeLists'])
    if found != expected:
        differences = [f'mancano {", ".join(sorted(expected - found))}' if expected - found else '',
                       f'non nel catalogo: {", ".join(sorted(found - expected))}' if found - expected else '']
        raise ExportError(f'{path}: le code list non corrispondono a quelle del catalogo ('
                          + '; '.join(d for d in differences if d) + '). Allinea il dizionario con python scripts/build_codelists.py --align'
                          + (' --prune' if found - expected else '') + '.')
    default_path = root/'codelists/codelists.default.js'
    default = (read_json_assignment(default_path.read_text(encoding='utf-8'), DICTIONARY_VARIABLE + '_DEFAULT')
               if default_path.exists() else None)
    return Inputs(root, catalog, manifest, dictionary, raw, default)


def source_file(inputs, path):
    """Byte di un file di sources/, controllati con lo SHA-256 del manifest."""
    record = next((r for r in inputs.manifest['files'] if r['path'] == path), None)
    if record is None:
        raise ExportError(f'{path} non è registrato in sources/manifest.json.')
    data = (inputs.root/path).read_bytes()
    if sha256(data) != record['sha256']:
        raise ExportError(f'{path} non corrisponde a sources/manifest.json: verifica con python scripts/verify_sources.py.')
    return data


def parse_exported_at(value=None):
    """Data dell'export in UTC, al secondo. Senza valore, l'ora corrente."""
    if value is None:
        return datetime.now(timezone.utc).replace(microsecond=0)
    try:
        when = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ExportError(f'--exported-at: data ISO 8601 non valida: {value}.') from exc
    if when.tzinfo is None:
        raise ExportError('--exported-at: indica il fuso orario, per esempio 2026-10-19T12:00:00Z.')
    when = when.astimezone(timezone.utc).replace(microsecond=0)
    if when.year < 1980:
        raise ExportError('--exported-at: la data deve essere successiva al 1980 (formato zip).')
    return when


# ---------------------------------------------------------------- dizionari (Annex E)

def is_real(value):
    """Un valore con codice e nome diverso da un segnaposto {example-N}."""
    return bool(value.get('code')) and not PLACEHOLDER.match(value.get('name') or '')


def list_state(lst):
    """Stato della lista, come nell'interfaccia."""
    if not lst['values']:
        return 'unavailable' if lst.get('unavailable') else 'empty'
    return 'placeholder' if all(PLACEHOLDER.match(v.get('name') or '') for v in lst['values']) else 'values'


def dictionary_records(dictionary):
    """{chiave: contenuto Annex E} per ogni code list con valori reali, in ordine di chiave. gml:id e nome del file
    usano il nome senza prefisso: un ':' non è ammesso in un xs:ID né nei nomi dei file su Windows."""
    records, problems = {}, []
    for name in sorted(dictionary['codeLists']):
        lst = dictionary['codeLists'][name]
        values = [v for v in lst['values'] if is_real(v)]
        if not values:
            continue
        meta = lst.get('metadata') or {}
        missing = [f for f in ('identifier', 'codeSpace') if not lst.get(f)] + [f'metadata.{k}' for k in METADATA if not meta.get(k)]
        if missing:
            problems.append(f'{name} ({", ".join(missing)})')
            continue
        records[name] = {
            'id': name.rsplit(':', 1)[-1], 'module': lst['module'], 'metadata': {k: meta[k] for k in METADATA},
            'description': lst.get('description') or '', 'identifier': lst['identifier'], 'codeSpace': lst['codeSpace'],
            'entries': [{'id': f'id{i}', 'description': v.get('description') or '', 'code': v['code'],
                         'codeSpace': v.get('codeSpace') or lst['codeSpace'], 'name': v.get('name') or ''}
                        for i, v in enumerate(values, 1)]}
    if problems:
        raise ExportError('Code list con valori ma senza i dati richiesti da Annex E: ' + '; '.join(problems)
                          + '. Completale con python scripts/codespaces.py.')
    return records


def file_name(record, extension):
    return f'{record["module"]}.{record["id"]}.{extension}'


def to_gml(record):
    """gml:Dictionary nella forma degli esempi OGC (OGC 21-006r2, Annex E §E.2.1)."""
    g, c = '{%s}' % GML_NS, '{%s}' % CMD_NS
    try:
        root = ET.Element(g+'Dictionary', nsmap={'gml': GML_NS, 'cmd': CMD_NS, 'xsi': XSI_NS})
        root.set(g+'id', record['id'])
        root.set('{%s}schemaLocation' % XSI_NS, f'{GML_NS} {GML_XSD} {CMD_NS} {CMD_XSD}')
        metadata = ET.SubElement(ET.SubElement(root, g+'metaDataProperty'), c+'CodeListMetaData')
        for key in METADATA:
            ET.SubElement(metadata, c+key).text = record['metadata'][key]
        ET.SubElement(root, g+'description').text = record['description']
        ET.SubElement(root, g+'identifier', codeSpace=record['codeSpace']).text = record['identifier']
        for entry in record['entries']:
            definition = ET.SubElement(ET.SubElement(root, g+'dictionaryEntry'), g+'Definition')
            definition.set(g+'id', entry['id'])
            ET.SubElement(definition, g+'description').text = entry['description']
            ET.SubElement(definition, g+'identifier', codeSpace=entry['codeSpace']).text = entry['code']
            ET.SubElement(definition, g+'name').text = entry['name']
    except ValueError as exc:
        raise ExportError(f'{record["id"]}: testo non rappresentabile in XML ({exc}).') from exc
    return ET.tostring(root, xml_declaration=True, encoding='UTF-8', pretty_print=True)


def to_json(record):
    """Struttura JSON di OGC 21-006r2, Annex E §E.2.3."""
    return {'Dictionary': {
        '@id': record['id'],
        'metaDataProperty': {'CodeListMetaData': dict(record['metadata'])},
        'description': record['description'],
        'identifier': {'@codeSpace': record['codeSpace'], '#text': record['identifier']},
        'dictionaryEntry': [{'Definition': {'@id': e['id'], 'description': e['description'],
                                            'identifier': {'@codeSpace': e['codeSpace'], '#text': e['code']},
                                            'name': e['name']}} for e in record['entries']]}}


def to_csv(record):
    """Struttura CSV di OGC 21-006r2, Annex E §E.2.2: separatore '|', righe Meta e Code.

    La terza colonna delle righe Code è il nome della voce: nell'esempio di Annex E
    'Code|1000|flat roof' corrisponde a gml:name dell'esempio GML.
    """
    out = io.StringIO()
    writer = csv.writer(out, delimiter='|', lineterminator='\r\n')
    meta = record['metadata']
    writer.writerow(['CodeType', 'Identifier', 'Description'])
    writer.writerow(['Meta', 'CityGML_DataType', record['module'], meta['dataType']])
    writer.writerow(['Meta', 'CityGML_Namespace', meta['namespace']])
    writer.writerow(['Meta', 'Language', meta['language']])
    writer.writerow(['Meta', 'Version', meta['version']])
    for entry in record['entries']:
        writer.writerow(['Code', entry['code'], entry['name']])
    return out.getvalue().encode('utf-8')


def dictionary_warnings(inputs, records, csv=False):
    """Avvisi che non fermano l'export. Con csv, anche quelli sui file CSV."""
    warnings = []
    default = (inputs.default_dictionary or {}).get('codeLists', {})
    for name, lst in sorted(inputs.dictionary['codeLists'].items()):
        if lst.get('edited') and name in records and lst.get('codeSpace') and lst['codeSpace'] == default.get(name, {}).get('codeSpace'):
            warnings.append(f'{name}: lista modificata con il codeSpace dell\'esempio OGC; per un codeSpace proprio usa python scripts/codespaces.py.')
        # A value written without a code is never exported: reported even when the whole list is left out.
        placeholders = sum(1 for v in lst['values'] if PLACEHOLDER.match(v.get('name') or ''))
        without_code = sum(1 for v in lst['values'] if not v.get('code') and not PLACEHOLDER.match(v.get('name') or ''))
        if without_code:
            warnings.append(f'{name}: {without_code} valori senza codice non esportati'
                            + ('' if name in records else '; nessun valore esportabile, la lista non è esportata') + '.')
        if name in records and placeholders:
            warnings.append(f'{name}: {placeholders} segnaposto non esportati.')
    for name, record in records.items():
        seen, repeated = set(), set()
        for entry in record['entries']:
            key = (entry['codeSpace'], entry['code'])
            (repeated if key in seen else seen).add(key)
        if repeated:
            warnings.append(f'{name}: codici ripetuti nello stesso codeSpace: ' + ', '.join(sorted(c for _, c in repeated)) + '.')
        ades = sorted({v['ade'] for v in inputs.dictionary['codeLists'][name]['values'] if v.get('ade') and is_real(v)})
        if csv and ades:
            warnings.append(f'{name}: il CSV di Annex E non riporta il codeSpace delle voci di {", ".join(ades)}; '
                            'il file GML lo conserva.')
    return warnings


# ---------------------------------------------------------------- validazione offline

class XmlCatalog(ET.Resolver):
    """Risolve URL con un catalogo OASIS XML (uri, system, rewriteURI, rewriteSystem), senza rete. Con files
    ({percorso: byte}, il contenuto di un pacchetto) catalogo e documenti si leggono da lì, non dal disco."""

    def __init__(self, path, files=None):
        super().__init__()
        self.files = files
        self.base = Path(path).resolve().parent if files is None else None
        self.exact, self.prefixes, self.unresolved = {}, [], []
        for entry in (ET.parse(str(path)).getroot() if files is None else ET.fromstring(files[str(path)])):
            tag = ET.QName(entry).localname
            if tag == 'uri':
                self.exact[entry.get('name')] = entry.get('uri')
            elif tag == 'system':
                self.exact[entry.get('systemId')] = entry.get('uri')
            elif tag in ('rewriteURI', 'rewriteSystem'):
                self.prefixes.append((entry.get('uriStartString') or entry.get('systemIdStartString'), entry.get('rewritePrefix')))
        self.prefixes.sort(key=lambda p: -len(p[0]))

    def target(self, url):
        """Percorso di un URL relativo al catalogo, o None se il catalogo non lo risolve."""
        if url in self.exact:
            return self.exact[url]
        for start, prefix in self.prefixes:
            if url.startswith(start):
                return prefix + url[len(start):]
        return None

    def lookup(self, url):
        """Percorso locale di un URL, o None se il catalogo non lo risolve."""
        target = self.target(url)
        return self.base/target if target is not None else None

    def resolve(self, url, pubid, context):
        target = self.target(url)
        if target is not None and self.files is None:
            return self.resolve_filename(str(self.base/target), context)
        if target in (self.files or {}):
            # L'URL resta la base del documento: anche i suoi import relativi passano dal catalogo.
            return self.resolve_string(self.files[target], context, base_url=url)
        if url.startswith(('http://', 'https://')):
            # Un documento vuoto al posto del download: la compilazione fallisce senza usare la rete.
            self.unresolved.append(url)
            return self.resolve_string('', context)
        return None


def compile_schema(catalog_path, imports, files=None):
    """XMLSchema che importa (namespace, URL) risolti con il catalogo OASIS indicato, senza rete. Con files
    catalogo e schemi sono quelli di un pacchetto in memoria (catalog_path è il percorso nel pacchetto)."""
    catalog = XmlCatalog(catalog_path, files)
    parser = ET.XMLParser(no_network=True, resolve_entities=False)
    parser.resolvers.add(catalog)
    body = ''.join(f'<xs:import namespace="{ns}" schemaLocation="{url}"/>' for ns, url in imports)
    doc = ET.fromstring(f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">{body}</xs:schema>', parser)
    try:
        schema = ET.XMLSchema(ET.ElementTree(doc))
    except ET.XMLSchemaParseError as exc:
        error = exc
    else:
        error = None
    if catalog.unresolved:
        raise ExportError(f'{catalog_path} non risolve: ' + ', '.join(sorted(set(catalog.unresolved))) + '.')
    if error:
        raise ExportError(f'Schemi non compilabili con {catalog_path}: {error}.')
    return schema


def validate_dictionaries(inputs, gml_files):
    """Valida i gml:Dictionary contro gml.xsd e codeListMetaData.xsd di sources/."""
    schema = compile_schema(inputs.root/'sources/xml-catalog.xml', [(GML_NS, GML_XSD), (CMD_NS, CMD_XSD)])
    for name, data in gml_files.items():
        doc = ET.fromstring(data, ET.XMLParser(no_network=True, resolve_entities=False))
        if not schema.validate(doc):
            raise ExportError(f'{name} non valida contro gli schemi: {schema.error_log.last_error}.')


# ---------------------------------------------------------------- catalogo

class View:
    """Accesso al catalogo per gli exporter: nomi qualificati, proprietà in ordine XML, corrispondenze UML."""

    def __init__(self, catalog):
        self.catalog = catalog
        self.nodes = catalog['nodes']
        self.props = {p['id']: p for n in self.nodes.values() for p in n['properties']}
        self.uml = {}
        self.uml_members = {}
        for n in self.nodes.values():
            for m in (n.get('uml') or {}).get('properties', []):
                entry = {'class': n['uml']['name'], 'member': m['name'], 'type': m.get('type'), 'multiplicity': m.get('multiplicity')}
                if m.get('dictionaryMultiplicity'):
                    entry['dictionaryMultiplicity'] = m['dictionaryMultiplicity']
                self.uml_members[m['id']] = entry
                if m.get('xsd'):
                    self.uml.setdefault(m['xsd'], entry)
        self.substitutes = {}
        for n in self.nodes.values():
            if n.get('substitution'):
                self.substitutes.setdefault(n['substitution'], []).append(n['id'])

    def qname(self, id_):
        return self.nodes[id_].get('qname') or self.nodes[id_]['name']

    @staticmethod
    def namespace(prop):
        """Namespace of the XML name of a property; None for an unqualified local attribute."""
        return prop['namespace']

    def concrete_elements(self):
        """Elementi concreti di CityGML e delle ADE: feature, oggetti e tipi di dato, esclusi astratti, tipi tecnici e ADE hook."""
        return sorted((n for n in self.nodes.values() if n['family'] in ('CityGML', 'ADE') and '}element:' in n['id'] and not n['abstract']
                       and not n.get('technical') and not n.get('external') and n['kind'] != 'ade'),
                      key=lambda n: (n['namespace'], n['name']))

    def xml_properties(self, node):
        """Proprietà di un elemento nell'ordine dell'XML: dal tipo base più lontano, poi a scendere.
        Una restrizione aggiunge gli attributi del tipo base che non dichiara di nuovo."""
        seen, result = set(), []
        for id_ in reversed([node['id'], *node['ancestors']]):
            owner = self.nodes[id_]
            for prop in owner['properties'] + [self.props[k] for k in owner.get('restrictionAttributes', [])]:
                key = (prop['qname'], prop['xmlKind'])
                if key not in seen:
                    seen.add(key)
                    result.append(prop)
        return result

    def substitution_chain(self, node):
        chain, current = [], node.get('substitution')
        while current and current in self.nodes and current not in chain:
            chain.append(current)
            current = self.nodes[current].get('substitution')
        return [self.qname(i) for i in chain]

    def candidates(self, targets):
        """Elementi concreti ammessi dagli schemi al posto delle destinazioni: le destinazioni stesse e il loro substitutionGroup."""
        found, stack = set(), list(targets)
        while stack:
            id_ = stack.pop()
            if id_ in found:
                continue
            found.add(id_)
            stack.extend(self.substitutes.get(id_, []))
        return sorted(self.qname(i) for i in found
                      if not self.nodes[i]['abstract'] and self.nodes[i]['kind'] != 'ade' and not self.nodes[i].get('external'))

    def uml_of(self, prop):
        return self.uml.get(prop['id']) or self.uml_members.get(prop.get('umlMember'))


def code_list_use(view):
    """Per ogni elemento concreto, le proprietà con code list, ereditate comprese."""
    entries = []
    for node in view.concrete_elements():
        for prop in view.xml_properties(node):
            if prop.get('codeList'):
                declared = view.nodes[prop['declaredIn']]
                entries.append({'element': node['name'], 'elementNamespace': node['namespace'],
                                'property': prop['name'], 'propertyNamespace': view.namespace(prop),
                                'codeList': code_list_key(view.nodes[prop['codeList']]),
                                'declaredIn': declared['name'], 'declaredInNamespace': declared['namespace'],
                                'multiplicity': prop['multiplicity']})
    return entries


def property_entry(view, prop):
    declared = view.nodes[prop['declaredIn']]
    # Destinazioni: elementi globali. Una proprietà dichiarata con xs:element/@ref ha come destinazione sé stessa.
    targets = [t for t in prop['targets'] if '}element:' in t and view.qname(t) != prop['qname']]
    entry = {'name': prop['name'], 'namespace': view.namespace(prop), 'qname': prop['qname'],
             'xmlKind': 'attribute' if 'attribute' in prop['xmlKind'] else 'element', 'group': prop['kind'],
             'minOccurs': prop['min'], 'maxOccurs': 'unbounded' if prop['max'] is None else prop['max'],
             'type': prop['typeName'] if prop.get('typeId') else None,
             'targets': [view.qname(t) for t in targets], 'candidates': view.candidates(targets),
             'declaredIn': declared.get('qname') or declared['name'], 'description': prop.get('description') or ''}
    if prop.get('choices'):
        entry['choices'] = [f'{entry["declaredIn"]}/{c}' for c in prop['choices']]
    for key in ('nillable', 'default', 'fixed'):
        if prop.get(key):
            entry[key] = prop[key]
    if prop.get('encoding'):
        entry['encoding'] = prop['encoding']
    if prop.get('codeList'):
        entry['codeList'] = code_list_key(view.nodes[prop['codeList']])
    uml = view.uml_of(prop)
    if uml:
        entry['uml'] = uml
    return entry


def choice_groups(view, node, props):
    """xs:choice groups of an element: occurrences in the type (repetitions of the enclosing groups included)
    and members. At every occurrence one member appears; with more occurrences the members can all appear."""
    groups = {}
    for id_ in reversed([node['id'], *node['ancestors']]):
        owner = view.nodes[id_]
        for c in owner['constraints']:
            if c['kind'] == 'xs:choice':
                low, high = c['occurs'].split('..')
                groups[f"{view.qname(id_)}/choice:{c['line']}"] = {'minOccurs': int(low), 'maxOccurs': 'unbounded' if high == '*' else int(high),
                                                                   'members': []}
    for p in props:
        for choice in p.get('choices', []):
            key = f"{view.qname(p['declaredIn'])}/{choice}"
            if key in groups:
                groups[key]['members'].append(p['qname'])
    return groups


def elements(view):
    result = []
    for n in view.concrete_elements():
        props = view.xml_properties(n)
        entry = {'name': n['name'], 'namespace': n['namespace'], 'qname': n['qname'], 'kind': n['kind'],
                 'type': n.get('xmlType'), 'spaceRole': n.get('spaceRole'), 'topLevel': bool(n.get('topLevel')),
                 'substitutionGroup': view.substitution_chain(n), 'description': n.get('description') or '',
                 'properties': [property_entry(view, p) for p in props]}
        groups = choice_groups(view, n, props)
        if groups:
            entry['choiceGroups'] = groups
        result.append(entry)
    return result


def document_label(document):
    return 'OGC ' + document['documentNumber']


def rules(view):
    """Regole che gli XSD non esprimono, ognuna con la sua fonte."""
    standard = view.catalog['standard']
    model, encoding = standard['document'], standard['encoding']['document']
    nodes = view.nodes
    def by_qname(items):
        return sorted(items, key=lambda i: (i.get('element') or i.get('space') or i.get('class') or '', i.get('property') or '', i.get('name') or ''))

    boundaries = []
    for n in nodes.values():
        ab = n.get('allowedBoundaries')
        if ab:
            boundaries.append({'space': view.qname(n['id']), 'namespace': n['namespace'], 'abstract': n['abstract'],
                               'none': ab['none'], 'ade': ab['ade'],
                               'written': [{'element': view.qname(i['id']), 'withSubclasses': i['withSubclasses']} for i in ab['items']],
                               'concrete': [view.qname(i) for i in ab['concrete']],
                               'source': {'document': document_label(model), 'requirement': ab['requirement'], 'table': ab['table'],
                                          'url': f'{model["url"]}#{ab["anchor"]}'}})

    def top_source(n):
        # Per un'ADE il primo livello viene dalla configurazione, non dal modello UML di OGC 20-010.
        if n['family'] == 'ADE':
            return {'ade': n['module'], 'configuration': 'config/sources.json'}
        return {'document': document_label(model), 'stereotype': n['uml']['stereotype'],
                'url': f'{model["url"]}#{n["uml"]["anchor"]}' if n['uml'].get('anchor') else model['url']}

    top = [{'element': view.qname(n['id']), 'namespace': n['namespace'], 'source': top_source(n)}
           for n in nodes.values() if n.get('topLevel')]

    def requirement_refs(prop):
        return [{'document': 'OGC ' + r['document'], 'requirement': r['id'], 'part': r.get('part'),
                 'url': f'{encoding["url"]}#{r["anchor"]}'} for r in prop.get('rules', [])]

    reference_only = [{'element': view.qname(p['declaredIn']), 'property': p['qname'],
                       'source': {'schemas': 'il tipo della proprietà ammette solo xlink:href', 'requirements': requirement_refs(p)}}
                      for p in view.props.values()
                      if p.get('encoding') and p['encoding']['allowsInline'] is False and p['encoding']['allowsReference']]

    constraints = []
    for n in nodes.values():
        uml = n.get('uml') or {}
        for c in uml.get('constraints', []):
            constraints.append({'class': uml['name'], 'xsd': None if n.get('umlOnly') else view.qname(n['id']),
                                'name': c['name'], 'text': c['text'],
                                'source': {'document': document_label(model), 'table': c.get('table'),
                                           'url': f'{model["url"]}#{uml["anchor"]}' if uml.get('anchor') else model['url']}})

    encoding_rules = []
    for r in standard['encoding']['requirements']:
        item = {k: r[k] for k in ('kind', 'title', 'id', 'module', 'text', 'parts', 'notes') if k in r}
        for k in ('targetType', 'dependencies'):
            if k in r:
                item[k] = r[k]
        item['properties'] = [{'element': view.qname(view.props[p['id']]['declaredIn']), 'property': view.props[p['id']]['qname'],
                               'part': p.get('part')} for p in r.get('properties', []) if p['id'] in view.props]
        item['source'] = {'document': 'OGC ' + r['document'], 'url': f'{encoding["url"]}#{r["anchor"]}'}
        encoding_rules.append(item)

    return {'allowedBoundaries': by_qname(boundaries), 'topLevel': by_qname(top), 'referenceOnly': by_qname(reference_only),
            'constraints': by_qname(constraints), 'encodingRules': encoding_rules}


# ---------------------------------------------------------------- intestazione e pacchetti

def document_reference(document):
    return {k: document.get(k) for k in ('documentNumber', 'title', 'version', 'approvalDate', 'url', 'sha256')}


def header(inputs, kind, when):
    catalog, dictionary = inputs.catalog, inputs.dictionary
    standard = catalog['standard']
    result = {'format': f'citygml-explorer/{kind}', 'formatVersion': FORMAT_VERSION, 'exportedAt': when.isoformat(),
              'schemas': catalog['sourceVersion'],
              'dictionary': {'sha256': sha256(inputs.dictionary_bytes),
                             'edited': sorted(n for n, l in dictionary['codeLists'].items() if l.get('edited')),
                             'codeSpacePolicy': dictionary.get('codeSpacePolicy')},
              'sources': {'conceptualModel': document_reference(standard['document']),
                          'encoding': document_reference(standard['encoding']['document']),
                          'schemaFiles': len(catalog['files']),
                          'codeListExamples': dictionary.get('source')}}
    # Solo con ADE: senza, l'intestazione resta quella di prima, byte per byte.
    if catalog.get('ades'):
        result['ades'] = [{'name': a['name'], 'prefix': a['prefix'], 'namespace': a['namespace'], 'version': a['schema']['version'],
                           'url': a['schema']['url'], 'sha256': a['schema']['sha256'], 'origin': a['origin']} for a in catalog['ades']]
    return result


def ade_label(ade):
    """Versione, schema e origine di un'ADE, per i README dei pacchetti."""
    origin = 'non pubblicata: copia locale' if ade['origin'] == 'local' else 'pubblicata'
    return f"versione {ade['schema']['version'] or '—'}, schema `{ade['schema']['url']}`, {origin}"


def dumps(obj):
    return (json.dumps(obj, indent=1, ensure_ascii=False) + '\n').encode('utf-8')


def zip_bytes(files, when):
    """Zip deterministico: ordine alfabetico, data dell'export, permessi fissi."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=when.timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name], compresslevel=9)
    return out.getvalue()


def with_manifest(files, kind, when):
    entries = [{'path': name, 'sha256': sha256(files[name]), 'bytes': len(files[name])} for name in sorted(files)]
    files['manifest.json'] = dumps({'format': f'citygml-explorer/{kind}-manifest', 'formatVersion': FORMAT_VERSION,
                                    'exportedAt': when.isoformat(), 'files': entries})
    return files


def code_list_index(inputs, records, folder):
    """Stato di ogni code list e, se esportata, file e codeSpace."""
    index = {}
    for name in sorted(inputs.dictionary['codeLists']):
        lst = inputs.dictionary['codeLists'][name]
        entry = {'module': lst['module'], 'state': list_state(lst),
                 'exportedValues': len(records[name]['entries']) if name in records else 0}
        if lst.get('edited'):
            entry['edited'] = True
        if name in records:
            entry['codeSpace'] = records[name]['codeSpace']
            entry['files'] = [f'{folder}/{file_name(records[name], ext)}' for ext in folder_extensions(folder)]
        index[name] = entry
    return index


def folder_extensions(folder):
    return ('xml', 'json') if folder == 'codelists' else ('xml', 'csv')


def ade_schema_files(inputs):
    """XSD delle ADE del catalogo, scelti per percorso: l'host di un'ADE può ospitare anche altri file."""
    return {path for ade in inputs.catalog.get('ades', []) for path in ade['files']}


def schema_files(inputs):
    """XSD ufficiali e avvertenze pubblicate con essi, dagli host degli schemi, e XSD delle ADE."""
    ade = ade_schema_files(inputs)
    return [r['path'] for r in sorted(inputs.manifest['files'], key=lambda r: r['path'])
            if r['path'].split('/')[1] in SCHEMA_HOSTS or r['path'] in ade]


def ade_folders(inputs):
    """Cartelle (host e percorso) degli XSD delle ADE, dagli URL del manifest."""
    ade = ade_schema_files(inputs)
    return sorted({r['url'].split('://', 1)[1].rsplit('/', 1)[0] + '/' for r in inputs.manifest['files'] if r['path'] in ade})


def package_catalog(records, hosts, folders=()):
    """xml-catalog.xml del pacchetto: URL degli schemi -> schemas/, codeSpace delle liste -> codelists/.

    Per un'ADE riscrive solo le cartelle dei suoi XSD (folders), non tutto il suo host.
    Risolve il codeSpace della lista, che per Annex E identifica la code list. I codeSpace
    propri dei singoli valori non sono risolti: negli esempi OGC alcuni sono condivisi fra liste.
    """
    root = ET.Element('{%s}catalog' % CATALOG_NS, nsmap={None: CATALOG_NS})
    for start in [f'{host}/' for host in hosts] + list(folders):
        for scheme in ('http', 'https'):
            ET.SubElement(root, '{%s}rewriteURI' % CATALOG_NS, uriStartString=f'{scheme}://{start}', rewritePrefix=f'schemas/{start}')
            ET.SubElement(root, '{%s}rewriteSystem' % CATALOG_NS, systemIdStartString=f'{scheme}://{start}', rewritePrefix=f'schemas/{start}')
    owners = {}
    for name, record in records.items():
        owners.setdefault(record['codeSpace'], []).append(name)
    shared = {s: o for s, o in owners.items() if len(o) > 1}
    if shared:
        raise ExportError('Code list con lo stesso codeSpace: '
                          + '; '.join(f'{s} ({", ".join(o)})' for s, o in sorted(shared.items()))
                          + '. Il codeSpace identifica la code list (OGC 21-006r2, Annex E).')
    for space, (name,) in sorted(owners.items()):
        ET.SubElement(root, '{%s}uri' % CATALOG_NS, name=space, uri=f'codelists/{file_name(records[name], "xml")}')
    return ET.tostring(root, xml_declaration=True, encoding='UTF-8', pretty_print=True)


def driver_imports(inputs):
    """(namespace, URL) che lo schema driver importa: CityGML.xsd e lo schema di ogni ADE."""
    return [(PROFILE_NS, PROFILE_XSD)] + [(a['namespace'], a['schema']['url']) for a in inputs.catalog.get('ades', [])]


def driver_schema(imports):
    """CityGML-ADE.xsd, generato da CG3E e non ufficiale. Con --schema, xmllint e lxml non seguono
    xsi:schemaLocation: un documento con elementi delle ADE si valida con uno schema che le importa."""
    xs = '{%s}' % XS_NS
    root = ET.Element(xs + 'schema', nsmap={'xs': XS_NS})
    ET.SubElement(ET.SubElement(root, xs + 'annotation'), xs + 'documentation').text = (
        'Generato da CityGML 3.0 Explorer, non ufficiale: importa CityGML 3.0 e le ADE del pacchetto, '
        'per validare i documenti che le usano.')
    for namespace, url in imports:
        ET.SubElement(root, xs + 'import', namespace=namespace, schemaLocation=url)
    return ET.tostring(root, xml_declaration=True, encoding='UTF-8', pretty_print=True)


# ---------------------------------------------------------------- exporter

def export_city3d(inputs, when):
    """EXP-001: un JSON con le code list (Annex E) e codeListUse."""
    view = View(inputs.catalog)
    records = dictionary_records(inputs.dictionary)
    code_lists = code_list_index(inputs, records, 'codelists')
    for name, entry in code_lists.items():
        entry.pop('files', None)
        entry.pop('codeSpace', None)
        if name in records:
            entry['Dictionary'] = to_json(records[name])['Dictionary']
    use = code_list_use(view)
    data = dumps({**header(inputs, 'city3d', when), 'codeLists': code_lists, 'codeListUse': use})
    return Result(data, {'codeLists': len(code_lists), 'withValues': len(records),
                         'values': sum(len(r['entries']) for r in records.values()), 'codeListUse': len(use)},
                  dictionary_warnings(inputs, records))


GENERATOR_README = '''# Pacchetto per il generatore di CityGML 3.0

Esportato da CityGML 3.0 Explorer il {date}.

## Contenuto

| Percorso | Contenuto | Formato |
| --- | --- | --- |
| `schemas/` | {schemas} XSD ufficiali di CityGML 3.0 e degli schemi importati (GML 3.2.1, ISO 19139, XLink, XML), invariati, con le avvertenze pubblicate insieme | XSD |
{ade_rows}| `codelists/` | {lists} code list con valori, in GML e in JSON | OGC 21-006r2, Annex E |
| `xml-catalog.xml` | URL degli schemi -> `schemas/`; `codeSpace` delle code list -> `codelists/` | catalogo OASIS XML |
| `citygml-generator.json` | `codeLists`, `codeListUse`, `elements` (struttura risolta degli XSD), `rules` (regole che gli XSD non esprimono, con la fonte) | `citygml-explorer/generator` |
| `manifest.json` | percorso e SHA-256 di ogni file | JSON |

## Versioni

- Schemi: {schemas_version}.
- Modello concettuale: {model} ({model_title}), approvato il {model_date}.
- Codifica GML: {encoding} ({encoding_title}), approvata il {encoding_date}.
- Dizionario delle code list: SHA-256 `{dictionary_sha}`; liste modificate rispetto agli esempi OGC: {edited}.
{ade_versions}
## Validare offline

{validation}

La validità di un file si verifica sempre contro `schemas/`: `citygml-generator.json` ne è una
vista risolta. Le regole in `rules` sono dati da leggere e non sono applicate dalla validazione XSD.
'''
VALIDATE_CITYGML = '''Lo schema completo di CityGML 3.0 è `schemas/schemas.opengis.net/citygml/profiles/base/3.0/CityGML.xsd`.
Gli import usano gli URL ufficiali, che `xml-catalog.xml` riconduce alle copie locali.

```text
XML_CATALOG_FILES=xml-catalog.xml xmllint --nonet --noout \\
  --schema schemas/schemas.opengis.net/citygml/profiles/base/3.0/CityGML.xsd file.gml
```'''
VALIDATE_ADE = '''Un documento con le ADE si valida con `CityGML-ADE.xsd`, che importa lo schema completo di CityGML 3.0
(`schemas/schemas.opengis.net/citygml/profiles/base/3.0/CityGML.xsd`) e gli schemi delle ADE. Con `--schema`
xmllint non segue `xsi:schemaLocation`: con il solo `CityGML.xsd` gli elementi delle ADE risultano inattesi.
Gli import usano gli URL ufficiali e quelli delle ADE, che `xml-catalog.xml` riconduce alle copie locali.

```text
XML_CATALOG_FILES=xml-catalog.xml xmllint --nonet --noout --schema CityGML-ADE.xsd file.gml
```'''


def export_generator(inputs, when):
    """EXP-002: zip con XSD, dizionari GML e JSON, xml-catalog.xml e citygml-generator.json."""
    view = View(inputs.catalog)
    records = dictionary_records(inputs.dictionary)
    files = {}
    paths, ade_paths, ades = schema_files(inputs), ade_schema_files(inputs), inputs.catalog.get('ades', [])
    for path in paths:
        files['schemas/' + path.removeprefix('sources/')] = source_file(inputs, path)
    gml = {}
    for name, record in records.items():
        gml[name] = files[f'codelists/{file_name(record, "xml")}'] = to_gml(record)
        files[f'codelists/{file_name(record, "json")}'] = dumps(to_json(record))
    validate_dictionaries(inputs, gml)
    files['xml-catalog.xml'] = package_catalog(records, sorted({p.split('/')[1] for p in paths if p not in ade_paths}), ade_folders(inputs))
    if ades:
        # Il driver deve compilare con i soli file del pacchetto: un import fuori dal pacchetto è un errore qui.
        files[DRIVER] = driver_schema(driver_imports(inputs))
        compile_schema('xml-catalog.xml', driver_imports(inputs), files)
    items = elements(view)
    use = code_list_use(view)
    files['citygml-generator.json'] = dumps({**header(inputs, 'generator', when),
                                             'codeLists': code_list_index(inputs, records, 'codelists'),
                                             'codeListUse': use, 'elements': items, 'rules': rules(view)})
    standard = inputs.catalog['standard']
    model, encoding = standard['document'], standard['encoding']['document']
    edited = [n for n, l in sorted(inputs.dictionary['codeLists'].items()) if l.get('edited')]
    ade_rows = ''.join(f"| `schemas/{folder}` | XSD dell'ADE {a['name']}, invariati | XSD |\n"
                       for a in ades for folder in sorted({p.removeprefix('sources/').rsplit('/', 1)[0] + '/' for p in a['files']}))
    if ades:
        ade_rows += f'| `{DRIVER}` | schema generato da CityGML 3.0 Explorer, non ufficiale: importa `CityGML.xsd` e gli schemi delle ADE | XSD |\n'
    files['README.md'] = GENERATOR_README.format(
        date=when.isoformat(), schemas=sum(p.endswith('.xsd') and p not in ade_paths for p in paths), lists=len(records),
        schemas_version=inputs.catalog['sourceVersion'], model=document_label(model), model_title=model['title'],
        model_date=model['approvalDate'], encoding=document_label(encoding), encoding_title=encoding['title'],
        encoding_date=encoding['approvalDate'], dictionary_sha=sha256(inputs.dictionary_bytes),
        edited=', '.join(edited) if edited else 'nessuna', ade_rows=ade_rows,
        ade_versions=''.join(f"- ADE {a['name']}: {ade_label(a)}, namespace `{a['namespace']}`.\n" for a in ades),
        validation=VALIDATE_ADE if ades else VALIDATE_CITYGML).encode('utf-8')
    with_manifest(files, 'generator', when)
    summary = {'files': len(files), 'schemas': sum(p.endswith('.xsd') for p in paths), 'codeLists': len(records),
               'elements': len(items), 'properties': sum(len(e['properties']) for e in items), 'codeListUse': len(use)}
    if ades:
        summary['ades'] = len(ades)
    return Result(zip_bytes(files, when), summary, dictionary_warnings(inputs, records))


EXPORT_README = '''# CityGML 3.0: lo standard in uso

Esportato da CityGML 3.0 Explorer il {date}.

## Come aprirlo

Estrai l'archivio in una cartella e apri `index.html` con un browser: la pagina funziona
offline, senza installare nulla. I collegamenti ai documenti OGC aprono le copie in `sources/`.

## Contenuto

| Percorso | Contenuto |
| --- | --- |
| `index.html`, `assets/`, `data/catalog.js` | l'explorer e il catalogo |
| `codelists/codelists.js` | il dizionario delle code list in uso |
| `codelists/codelists.default.js` | lo stato iniziale del dizionario: gli esempi OGC{default_ades} |
| `sources/` | le fonti ufficiali invariate, con `sources/manifest.json` (URL, data di download, SHA-256) |
| `dictionaries/` | le {lists} code list con valori come `gml:Dictionary` (`.xml`) e in CSV (`.csv`), nelle forme di OGC 21-006r2, Annex E |
| `manifest.json` | percorso e SHA-256 di ogni file del pacchetto |

## Versioni

| | |
| --- | --- |
| Schemi | {schemas_version} |
| Modello concettuale | {model}, {model_title}, versione {model_version}, approvato il {model_date} |
| Codifica GML | {encoding}, {encoding_title}, versione {encoding_version}, approvata il {encoding_date} |
| Download delle fonti | {retrieved} |
| Esempi OGC delle code list | {examples} |
{ade_rows}
## Dizionario delle code list

I valori delle code list non fanno parte dello standard: vanno definiti esternamente, e
l'attributo `codeSpace`, facoltativo, identifica la code list da cui un valore è preso
(OGC 21-006r2, Annex E).

- Code list con valori: {lists} su {total}.
- Modificate rispetto agli esempi OGC: {edited}.
- Politica dei `codeSpace`: {policy}.
'''


def export_standard(inputs, when):
    """EXP-003: zip con l'explorer offline, le fonti e i dizionari GML e CSV."""
    root = inputs.root
    records = dictionary_records(inputs.dictionary)
    files = {}
    for name in ('index.html', 'README.md', 'LICENSE-app.txt', 'codelists/codelists.default.js'):
        files[name] = (root/name).read_bytes()
    for path in sorted((root/'assets').iterdir()):
        if path.is_file():
            files['assets/' + path.name] = path.read_bytes()
    catalog_js = (root/'data/catalog.js').read_bytes()
    if read_json_assignment(catalog_js.decode('utf-8'), 'CITYGML_CATALOG') != inputs.catalog:
        raise ExportError('data/catalog.js non corrisponde a data/catalog.json: rigenera il catalogo con python scripts/build_catalog.py.')
    files['data/catalog.js'] = catalog_js
    files['codelists/codelists.js'] = inputs.dictionary_bytes
    for record in inputs.manifest['files']:
        files[record['path']] = source_file(inputs, record['path'])
    for name in ('sources/manifest.json', 'sources/xml-catalog.xml'):
        files[name] = (root/name).read_bytes()
    gml = {}
    for name, record in records.items():
        gml[name] = files[f'dictionaries/{file_name(record, "xml")}'] = to_gml(record)
        files[f'dictionaries/{file_name(record, "csv")}'] = to_csv(record)
    validate_dictionaries(inputs, gml)
    standard = inputs.catalog['standard']
    model, encoding = standard['document'], standard['encoding']['document']
    retrieved = sorted({r['retrievedAt'][:10] for r in inputs.manifest['files']})
    edited = [n for n, l in sorted(inputs.dictionary['codeLists'].items()) if l.get('edited')]
    policy = inputs.dictionary.get('codeSpacePolicy')
    source = inputs.dictionary.get('source') or {}
    files['EXPORT.md'] = EXPORT_README.format(
        date=when.isoformat(), lists=len(records), total=len(inputs.dictionary['codeLists']),
        schemas_version=inputs.catalog['sourceVersion'],
        model=document_label(model), model_title=model['title'], model_version=model['version'], model_date=model['approvalDate'],
        encoding=document_label(encoding), encoding_title=encoding['title'], encoding_version=encoding['version'],
        encoding_date=encoding['approvalDate'], retrieved=', '.join(retrieved),
        examples=f'{source.get("title", "")} {source.get("version", "")} ({source.get("baseUrl", "")})'.strip(),
        edited=', '.join(edited) if edited else 'nessuna',
        policy=(f'base `{policy["base"]}`, versione {policy["version"]}, autorità {policy["authority"]}, '
                f'applicata il {policy["appliedAt"]} a {", ".join(policy["lists"])}') if policy else 'non applicata: i codeSpace sono quelli degli esempi OGC',
        default_ades=' e i dizionari delle ADE' if inputs.catalog.get('ades') else '',
        ade_rows=''.join(f"| ADE {a['name']} | {ade_label(a)}, namespace `{a['namespace']}` |\n" for a in inputs.catalog.get('ades', [])),
    ).encode('utf-8')
    with_manifest(files, 'standard', when)
    return Result(zip_bytes(files, when), {'files': len(files), 'codeLists': len(records)}, dictionary_warnings(inputs, records, csv=True))


EXPORTERS = {'city3d': export_city3d, 'generator': export_generator, 'standard': export_standard}
