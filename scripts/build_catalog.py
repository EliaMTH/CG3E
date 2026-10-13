#!/usr/bin/env python3
"""Build a strictly local XSD/OWL navigation index. Never fetches imports.

This is a structural explorer, NOT an XML validator, UML reverse-engineering
engine or OWL reasoner. All inferred display categories are explicitly labelled.
Run from any directory: python scripts/build_catalog.py
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse
from lxml import etree as ET
from rdflib import Graph, URIRef, BNode, Literal, RDF, RDFS, OWL, SKOS

ROOT = Path(__file__).resolve().parents[1]
XS = 'http://www.w3.org/2001/XMLSchema'
GML = 'http://www.opengis.net/gml/3.2'
NS = {'xs': XS}
PREFIXES = {
    XS: 'xs', GML: 'gml', 'http://www.opengis.net/citygml/3.0': 'core',
    'http://www.opengis.net/citygml/building/3.0': 'bldg',
    'http://www.opengis.net/citygml/construction/3.0': 'con',
    'http://www.opengis.net/citygml/transportation/3.0': 'tran',
    'urn:oasis:names:tc:ciq:xal:3': 'xal', 'urn:oasis:names:tc:ciq:ct:3': 'ct',
    'http://www.w3.org/1999/xlink': 'xlink'
}
MODULES = {'core': 'Core', 'building': 'Building', 'construction': 'Construction',
           'cityfurniture': 'CityFurniture', 'cityobjectgroup': 'CityObjectGroup',
           'waterbody': 'WaterBody', 'landuse': 'LandUse', 'pointcloud': 'PointCloud'}
GEOMETRY_TYPES = {'PointPropertyType', 'MultiPointPropertyType', 'CurvePropertyType',
 'MultiCurvePropertyType', 'SurfacePropertyType', 'MultiSurfacePropertyType',
 'SolidPropertyType', 'MultiSolidPropertyType', 'GeometryPropertyType',
 'GeometricComplexPropertyType', 'CompositeSurfacePropertyType', 'TinPropertyType',
 'TriangulatedSurfacePropertyType', 'PolygonPropertyType', 'LineStringPropertyType'}
# These names classify the UI section only. An external PropertyType is never
# converted into a guessed concrete geometry element.


def local(value):
    return str(value).rsplit('#', 1)[-1].rsplit('/', 1)[-1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def doc(el):
    if el is None:
        return ''
    return '\n\n'.join(' '.join(''.join(x.itertext()).split())
                       for x in el.findall('xs:annotation/xs:documentation', NS))


def qname(el, value, fallback=''):
    if not value:
        return None
    if ':' in value:
        pre, name = value.split(':', 1)
        return el.nsmap.get(pre, 'UNRESOLVED:' + pre), name
    return el.nsmap.get(None, fallback), value


def xid(ns, name, kind='element'):
    return f'xsd:{{{ns}}}{kind}:{name}'


def oid(iri):
    return 'owl:' + str(iri)


class Builder:
    def __init__(self, root, mode='full'):
        if mode not in ('citygml', 'full'):
            raise ValueError('Modalita sconosciuta: ' + str(mode))
        self.mode = mode
        self.root = root
        self.nodes = {}
        self.elements, self.types, self.groups, self.attrs = {}, {}, {}, {}
        self.type_alias = {}
        self.node_defs = {}
        self.files = []
        self.dependencies = []
        self.warnings = []
        self.graph = Graph()
        self.owl_source = defaultdict(set)
        self.owl_assertions = defaultdict(list)
        self.parser = ET.XMLParser(resolve_entities=False, no_network=True)

    def relative(self, p):
        return str(p.relative_to(self.root)).replace('\\', '/')

    def register_file(self, path, format_, namespace=''):
        record = {'path': self.relative(path), 'name': path.name, 'format': format_,
                  'namespace': namespace, 'original': 'original-voc' in path.parts,
                  'sha256': sha(path), 'bytes': path.stat().st_size}
        lock = self.root / 'sources/download-lock.json'
        if lock.exists():
            info = json.loads(lock.read_text()).get(record['path'], {})
            record.update({k: info[k] for k in ('url', 'retrievedAt') if k in info})
        self.files.append(record)
        return record

    def pretty_q(self, ns, name):
        prefix = PREFIXES.get(ns, ns.rstrip('/').rsplit('/', 2)[-2]
                              if 'citygml/' in ns else 'ext')
        return f'{prefix}:{name}'

    def category(self, ns):
        if 'opengis.net/citygml/' in ns:
            part = 'core' if ns.endswith('citygml/3.0') else ns.split('/')[-2]
            return MODULES.get(part, part[:1].upper()+part[1:]), 'CityGML', False
        if ns == XS:
            return 'XML Schema', 'Supporto', True
        if ns == GML:
            return 'GML', 'Supporto', True
        if ':xal:' in ns or ':ct:' in ns:
            return 'xAL', 'Supporto', True
        return local(ns) or 'XML', 'Supporto', True

    def base_node(self, id_, name, module, family, support, format_):
        return {'id': id_, 'name': name, 'label': name, 'module': module,
                'family': family, 'support': support, 'format': format_,
                'kind': 'class', 'description': '', 'abstract': False,
                'technical': False, 'external': False, 'properties': [],
                'parents': [], 'children': [], 'incoming': [], 'constraints': [],
                'bridges': [], 'source': [], 'annotations': [], 'axioms': []}

    def ensure_xsd(self, pair, kind='type'):
        if not pair:
            return None
        ns, name = pair
        id_ = self.type_alias.get(pair, xid(ns, name, kind)) if kind == 'type' else xid(ns, name, kind)
        if id_ in self.nodes:
            return id_
        module, family, support = self.category(ns)
        n = self.base_node(id_, name, module, family, support, 'XSD')
        n.update(namespace=ns, qname=self.pretty_q(ns, name), external=True,
                 kind='external', xmlType=self.pretty_q(ns, name), technical=True)
        if ns == XS:
            n.update(external=False, kind='datatype', description='Tipo predefinito XML Schema. La definizione normativa non e\u0300 riprodotta nel catalogo.',
                     builtin=True)
        self.nodes[id_] = n
        return id_

    def read_xsd(self):
        paths = sorted(self.root.glob('sources/original-voc/*.xsd')) + sorted(
            self.root.glob('sources/dependencies/citygml/**/*.xsd'))
        for path in paths:
            try:
                root = ET.parse(str(path), self.parser).getroot()
            except ET.XMLSyntaxError as exc:
                self.warnings.append(f'{self.relative(path)}: XML non valido: {exc}')
                continue
            if root.tag != '{'+XS+'}schema':
                continue
            namespace = root.get('targetNamespace', '')
            self.register_file(path, 'XSD', namespace)
            for prefix, ns in root.nsmap.items():
                if prefix and ns not in PREFIXES:
                    PREFIXES[ns] = prefix
            for el in root:
                if not isinstance(el.tag, str):
                    continue
                tag = ET.QName(el).localname
                if tag in ('import', 'include', 'redefine'):
                    self.dependencies.append({'from': self.relative(path), 'kind': 'xsd:'+tag,
                        'namespace': el.get('namespace', namespace), 'url': el.get('schemaLocation', '')})
                name = el.get('name')
                if not name:
                    continue
                target = self.elements if tag == 'element' else self.types if tag in ('complexType', 'simpleType') else self.groups if tag in ('group', 'attributeGroup') else self.attrs if tag == 'attribute' else None
                if target is not None:
                    key = (namespace, name)
                    if key in target:
                        self.warnings.append(f'Definizione duplicata: {key}; mantenuta la prima.')
                    else:
                        target[key] = (el, path)
        # Merge only the explicit element + its conventional, exclusively used Type.
        users = defaultdict(list)
        for pair, (el, path) in self.elements.items():
            if el.get('type'):
                users[qname(el, el.get('type'))].append(pair)
        for type_pair, els in users.items():
            if len(els) == 1 and type_pair[1] == els[0][1] + 'Type':
                self.type_alias[type_pair] = xid(*els[0])
        for pair, (el, path) in self.elements.items():
            ns, name = pair
            module, family, support = self.category(ns)
            n = self.base_node(xid(ns, name), name, module, family, support, 'XSD')
            typ = qname(el, el.get('type'))
            te = self.types.get(typ, (None, None))[0]
            inline = el.find('xs:complexType', NS)
            if te is None:
                te = inline
            if te is None:
                te = el.find('xs:simpleType', NS)
            n.update(namespace=ns, qname=self.pretty_q(ns, name),
                     xmlType=self.pretty_q(*typ) if typ else '(tipo anonimo)',
                     abstract=el.get('abstract') == 'true' or (te is not None and te.get('abstract') == 'true'),
                     description=doc(el) or doc(te), source=[self.relative(path)], line=el.sourceline,
                     xml=ET.tostring(el, encoding='unicode', pretty_print=True))
            if te is not None and te is not inline:
                n['xml'] += '\n' + ET.tostring(te, encoding='unicode', pretty_print=True)
            if name.startswith('ADEOf'):
                n['kind'] = 'ade'
            if te is not None and ET.QName(te).localname == 'simpleType':
                n['kind'] = 'datatype'
            if el.get('substitutionGroup'):
                n['substitutionPair'] = qname(el, el.get('substitutionGroup'))
            self.nodes[n['id']] = n
            self.node_defs[n['id']] = (te, path)
        for pair, (te, path) in self.types.items():
            if pair in self.type_alias:
                continue
            ns, name = pair
            module, family, support = self.category(ns)
            n = self.base_node(xid(ns, name, 'type'), name, module, family, support, 'XSD')
            n.update(namespace=ns, qname=self.pretty_q(ns, name), xmlType=self.pretty_q(ns, name),
                     description=doc(te), source=[self.relative(path)], line=te.sourceline,
                     xml=ET.tostring(te, encoding='unicode', pretty_print=True),
                     abstract=te.get('abstract') == 'true',
                     kind='datatype', technical=name.endswith('PropertyType'))
            self.nodes[n['id']] = n
            self.node_defs[n['id']] = (te, path)
        # Resolve all types after registry is complete; only extension is inheritance.
        for id_, (te, path) in list(self.node_defs.items()):
            n = self.nodes[id_]
            if 'substitutionPair' in n:
                n['substitution'] = self.ensure_xsd(n.pop('substitutionPair'), 'element')
            if te is None:
                continue
            ext = te.find('xs:complexContent/xs:extension', NS)
            if ext is None:
                ext = te.find('xs:simpleContent/xs:extension', NS)
            rest = te.find('xs:complexContent/xs:restriction', NS)
            if rest is None:
                rest = te.find('xs:simpleContent/xs:restriction', NS)
            if rest is None:
                rest = te.find('xs:restriction', NS)
            if ext is not None:
                parent = self.ensure_xsd(qname(ext, ext.get('base')))
                if parent:
                    n['parents'].append(parent)
                n['derivation'] = 'xs:extension'
            elif rest is not None:
                n['restrictedBase'] = self.ensure_xsd(qname(rest, rest.get('base')))
                n['derivation'] = 'xs:restriction'
            # Simple-type facets, lists and unions are not generalization edges.
            for facet in te.xpath('./xs:restriction/* | ./xs:simpleContent/xs:restriction/*', namespaces=NS):
                if facet.get('value') is not None:
                    n['constraints'].append({'kind': ET.QName(facet).localname, 'value': facet.get('value'), 'description': doc(facet)})
            for tag, attr in [('list', 'itemType'), ('union', 'memberTypes')]:
                item = te.find('xs:'+tag, NS)
                if item is not None:
                    ids = [self.ensure_xsd(qname(item, v)) for v in item.get(attr, '').split()]
                    n['constraints'].append({'kind': 'xs:'+tag, 'targets': ids})
            if any(c['kind'] == 'enumeration' for c in n['constraints']):
                n['kind'] = 'enumeration'
            owner_ns = n['namespace']
            container = ext if ext is not None else rest if rest is not None else te
            self.walk_fields(container, n, path, owner_ns)

    def wrapper_targets(self, el, visited=None):
        visited = set() if visited is None else set(visited)
        result = []
        # Published targetElement annotations resolve reference-only associations.
        for marker in el.findall('xs:annotation/xs:appinfo/{http://www.opengis.net/gml/3.2}targetElement', NS):
            pair = qname(marker, (marker.text or '').strip())
            if pair:
                result.append((self.ensure_xsd(pair, 'element'), 'gml:targetElement'))
        type_pair = qname(el, el.get('type'))
        wrapper = el.find('xs:complexType', NS)
        if type_pair and type_pair not in visited:
            visited.add(type_pair)
            if type_pair[1].endswith('PropertyType') and type_pair in self.types:
                wrapper = self.types[type_pair][0]
        if wrapper is not None:
            for child in wrapper.xpath('./xs:sequence/xs:element | ./xs:choice/xs:element | ./xs:complexContent/xs:extension/xs:sequence/xs:element | ./xs:complexContent/xs:extension/xs:choice/xs:element', namespaces=NS):
                if child.get('ref'):
                    result.append((self.ensure_xsd(qname(child, child.get('ref')), 'element'), 'xs:element/@ref nel contenitore'))
        return list(dict.fromkeys(result))

    def walk_fields(self, container, n, path, owner_ns, minimum=1, maximum=1, choices=None, groups_seen=None):
        choices = list(choices or [])
        groups_seen = set(groups_seen or set())
        for child in container:
            if not isinstance(child.tag, str):
                continue
            tag = ET.QName(child).localname
            if tag in ('sequence', 'all', 'choice'):
                lo = minimum * int(child.get('minOccurs', '1'))
                rawhi = child.get('maxOccurs', '1')
                hi = None if maximum is None or rawhi == 'unbounded' else maximum * int(rawhi)
                cs = list(choices)
                if tag == 'choice':
                    cs.append(f'choice:{child.sourceline}')
                    lo = 0  # Per-branch lower bound; group constraint is kept separately.
                    n['constraints'].append({'kind': 'xs:choice', 'value': f"{child.get('minOccurs','1')}..{child.get('maxOccurs','1')}", 'line': child.sourceline,
                         'description': 'Alternative XML: i singoli campi non sono requisiti indipendenti.'})
                self.walk_fields(child, n, path, owner_ns, lo, hi, cs, groups_seen)
            elif tag in ('group', 'attributeGroup') and child.get('ref'):
                pair = qname(child, child.get('ref'))
                if pair in groups_seen:
                    continue
                if pair in self.groups:
                    grp, gp = self.groups[pair]
                    rawhi = child.get('maxOccurs', '1')
                    hi = None if maximum is None or rawhi == 'unbounded' else maximum * int(rawhi)
                    self.walk_fields(grp, n, gp, pair[0], minimum * int(child.get('minOccurs','1')), hi, choices, groups_seen | {pair})
                else:
                    n['constraints'].append({'kind': 'gruppo esterno', 'value': self.pretty_q(*pair),
                        'description': 'Definizione non disponibile localmente; eventuali proprieta\u0300 del gruppo non sono espanse.'})
            elif tag in ('element', 'attribute'):
                self.add_field(child, n, path, owner_ns, tag, minimum, maximum, choices)
            elif tag in ('any', 'anyAttribute'):
                n['constraints'].append({'kind': 'xs:'+tag, 'value': child.get('namespace','##any'),
                    'description': 'processContents='+child.get('processContents','strict')})

    def add_field(self, el, n, path, owner_ns, tag, minimum, maximum, choices):
        ref = qname(el, el.get('ref'))
        name = el.get('name') or (ref[1] if ref else '(anonimo)')
        prefix = self.pretty_q(owner_ns, name)
        typ = qname(el, el.get('type'))
        resolved = self.elements.get(ref, (None, None))[0] if tag == 'element' else self.attrs.get(ref, (None, None))[0]
        if typ is None and resolved is not None:
            typ = qname(resolved, resolved.get('type'))
        targets = self.wrapper_targets(el) if tag == 'element' else []
        if not targets and ref and tag == 'element':
            targets = [(self.ensure_xsd(ref, 'element'), 'xs:element/@ref')]
        inline = el.find('xs:complexType', NS)
        st = el.find('xs:simpleType', NS)
        if inline is not None and not targets:
            # Anonymous data structures get a real navigable local node, not discarded.
            aid = n['id'] + '/anonymous:' + name + ':' + str(el.sourceline)
            an = self.base_node(aid, n['name']+'.'+name, n['module'], n['family'], n['support'], 'XSD')
            an.update(kind='datatype', technical=True, namespace=owner_ns, qname=prefix,
                      description=doc(el), source=[self.relative(path)], line=el.sourceline,
                      xml=ET.tostring(inline, encoding='unicode', pretty_print=True), anonymous=True)
            self.nodes[aid] = an
            ex = inline.find('xs:complexContent/xs:extension', NS)
            if ex is None:
                ex = inline.find('xs:simpleContent/xs:extension', NS)
            if ex is not None:
                an['parents'] = [self.ensure_xsd(qname(ex, ex.get('base')))]
                an['derivation'] = 'xs:extension'
            self.walk_fields(ex if ex is not None else inline, an, path, owner_ns)
            targets = [(aid, 'tipo complesso anonimo')]
        if st is not None and not targets:
            aid = n['id']+'/anonymous:'+name+':'+str(el.sourceline)
            an = self.base_node(aid, n['name']+'.'+name, n['module'], n['family'], n['support'], 'XSD')
            an.update(kind='datatype', technical=True, namespace=owner_ns, qname=prefix, anonymous=True,
                      source=[self.relative(path)], line=el.sourceline, description=doc(el),
                      xml=ET.tostring(st, encoding='unicode', pretty_print=True))
            for facet in st.xpath('./xs:restriction/*[@value]', namespaces=NS):
                an['constraints'].append({'kind': ET.QName(facet).localname, 'value': facet.get('value')})
            if any(c['kind'] == 'enumeration' for c in an['constraints']):
                an['kind'] = 'enumeration'
            self.nodes[aid] = an
            targets = [(aid, 'tipo semplice anonimo')]
        target_ids = [a for a,b in targets]
        datatype = self.ensure_xsd(typ) if typ else None
        if not target_ids and datatype:
            target_ids = [datatype]
        kind = 'attribute'
        if tag == 'element' and targets:
            kind = 'association' if any(self.nodes[t]['kind'] in ('class','ade','external') for t in target_ids) else 'attribute'
        if re.match(r'^lod[0-3]', name) or (typ and typ[0] == GML and typ[1] in GEOMETRY_TYPES):
            kind = 'geometry'
        if name.startswith('adeOf'):
            kind = 'ade'
        if tag == 'attribute':
            kind = 'xmlAttribute'
        if tag == 'attribute':
            lo, hi = (1, 1) if el.get('use') == 'required' else (0, 0) if el.get('use') == 'prohibited' else (0, 1)
        else:
            lo = minimum * int(el.get('minOccurs','1'))
            raw = el.get('maxOccurs','1')
            hi = None if maximum is None or raw == 'unbounded' else maximum * int(raw)
        p = {'id': n['id']+'/property:'+name+':'+str(el.sourceline), 'name': name, 'qname': prefix,
             'kind': kind, 'xmlKind': 'xs:'+tag, 'description': doc(el) or doc(resolved),
             'targets': target_ids, 'typeId': datatype, 'typeName': self.pretty_q(*typ) if typ else '(inline/ref)',
             'multiplicity': f"{lo}..{'*' if hi is None else hi}", 'min': lo, 'max': hi,
             'declaredIn': n['id'], 'source': self.relative(path), 'line': el.sourceline,
             'choices': choices, 'nillable': el.get('nillable') == 'true',
             'default': el.get('default'), 'fixed': el.get('fixed'),
             'targetEvidence': [b for a,b in targets],
             'xml': ET.tostring(el, encoding='unicode', pretty_print=True)}
        n['properties'].append(p)

    def owl_category(self, iri):
        if str(iri).startswith('http://uish/ontology'):
            return 'UISH Building', 'UISH', False
        if str(iri).startswith('http://www.uish.org/'):
            return 'UISH Sensors', 'UISH', False
        if '/CityGML/3.0/' in str(iri) or '/CityOWL/' in str(iri):
            return 'CityOWL '+str(iri).split('/')[-1].split('#')[0].capitalize(), 'CityOWL', False
        if 'obolibrary.org/obo/' in str(iri):
            return 'Unit Ontology', 'Supporto', True
        if '/sosa/' in str(iri) or '/ssn/' in str(iri):
            return 'SOSA / SSN', 'Supporto', True
        if 'geosparql' in str(iri):
            return 'GeoSPARQL', 'Supporto', True
        return 'RDF / OWL', 'Supporto', True

    def ensure_owl(self, iri):
        if not isinstance(iri, URIRef):
            return None
        id_ = oid(iri)
        if id_ not in self.nodes:
            mod, fam, support = self.owl_category(iri)
            n = self.base_node(id_, local(iri), mod, fam, support, 'OWL')
            n.update(iri=str(iri), namespace=str(iri).rsplit('#',1)[0], qname=local(iri),
                     external=True, kind='external')
            if str(iri).startswith(XS + '#'):
                n.update(kind='datatype', external=False, builtin=True, module='XML Schema', description='Tipo di dato XML Schema usato come datatype RDF; definizione normativa non riprodotta.')
            self.nodes[id_] = n
        return id_

    def expression(self, value, seen=None):
        seen = set(seen or [])
        if isinstance(value, URIRef):
            return {'ref': self.ensure_owl(value)}
        if isinstance(value, Literal):
            return {'literal': str(value), 'datatype': str(value.datatype or ''), 'language': value.language or ''}
        if value in seen or len(seen) > 25:
            return {'note': 'riferimento ricorsivo'}
        seen.add(value)
        data = []
        for p, o in sorted(self.graph.predicate_objects(value), key=lambda x:(str(x[0]),str(x[1]))):
            if p in (OWL.unionOf, OWL.intersectionOf, OWL.oneOf, OWL.members, OWL.distinctMembers):
                try:
                    data.append({'predicate': local(p), 'items': [self.expression(v, seen) for v in self.graph.items(o)]})
                except ValueError:
                    data.append({'predicate': local(p), 'value': {'note':'lista RDF non valida'}})
            else:
                data.append({'predicate': local(p), 'value': self.expression(o, seen)})
        return {'expression': data}

    def read_owl(self):
        if self.mode == 'citygml':
            return
        paths = sorted(p for p in self.root.glob('sources/original-voc/*')
                       if p.suffix.lower() in ('.owl','.ttl','.rdf'))
        paths += sorted(p for p in self.root.glob('sources/dependencies/owl/**/*')
                        if p.suffix.lower() in ('.owl','.ttl','.rdf'))
        for path in paths:
            try:
                g = Graph().parse(str(path), format='turtle' if path.suffix == '.ttl' else 'xml')
            except Exception as exc:
                self.warnings.append(f'{self.relative(path)}: RDF non valido: {exc}')
                continue
            ontology = next(g.subjects(RDF.type, OWL.Ontology), None)
            self.register_file(path, 'OWL', str(ontology or ''))
            for imported in g.objects(None, OWL.imports):
                self.dependencies.append({'from': self.relative(path), 'kind': 'owl:imports', 'url': str(imported), 'namespace': str(imported)})
            for s,p,o in g:
                self.graph.add((s,p,o))
                if isinstance(s, URIRef):
                    self.owl_source[str(s)].add(self.relative(path))
                    self.owl_assertions[str(s)].append((p,o))
        g = self.graph
        allowed = (OWL.Class, RDFS.Class, RDFS.Datatype, OWL.ObjectProperty,
                   OWL.DatatypeProperty, OWL.AnnotationProperty, OWL.NamedIndividual)
        subjects = sorted({s for typ in allowed for s in g.subjects(RDF.type,typ) if isinstance(s, URIRef)}, key=str)
        for s in subjects:
            id_ = self.ensure_owl(s)
            n = self.nodes[id_]
            types = set(g.objects(s, RDF.type))
            kind = 'objectProperty' if OWL.ObjectProperty in types else 'dataProperty' if OWL.DatatypeProperty in types else 'annotationProperty' if OWL.AnnotationProperty in types else 'datatype' if RDFS.Datatype in types else 'class' if OWL.Class in types or RDFS.Class in types else 'individual' if OWL.NamedIndividual in types else 'class'
            labels = list(g.objects(s, SKOS.prefLabel)) + list(g.objects(s,RDFS.label))
            labels.sort(key=lambda x: (0 if getattr(x,'language','') == 'en' else 1 if getattr(x,'language','') == 'it' else 2, str(x)))
            descs = list(g.objects(s, SKOS.definition)) + list(g.objects(s,RDFS.comment))
            descs += list(g.objects(s, URIRef('http://purl.org/dc/terms/description')))
            n.update(external=False, kind=kind, label=str(labels[0]) if labels else n['name'],
                     description='\n\n'.join(dict.fromkeys(map(str,descs))), source=sorted(self.owl_source[str(s)]),
                     rdfTypes=sorted(map(str,types)), functional=OWL.FunctionalProperty in types)
            for p,o in sorted(g.predicate_objects(s), key=lambda po:(str(po[0]),str(po[1]))):
                if isinstance(o, Literal):
                    n['annotations'].append({'predicate':str(p),'value':str(o),'language':o.language or ''})
            n['parents'] = [self.ensure_owl(o) for o in g.objects(s,RDFS.subClassOf) if isinstance(o,URIRef)]
            n['derivation'] = 'rdfs:subClassOf'
            for pred in (RDFS.subClassOf, OWL.equivalentClass, OWL.disjointWith, OWL.disjointUnionOf):
                for o in g.objects(s,pred):
                    if pred == RDFS.subClassOf and isinstance(o,URIRef):
                        continue
                    n['axioms'].append({'predicate':str(pred),'value':self.expression(o)})
            if kind in ('objectProperty','dataProperty','annotationProperty'):
                n['domains'] = [self.expression(o) for o in g.objects(s,RDFS.domain)]
                n['ranges'] = [self.expression(o) for o in g.objects(s,RDFS.range)]
                n['superProperties'] = [self.ensure_owl(o) for o in g.objects(s,RDFS.subPropertyOf) if isinstance(o,URIRef)]
                n['inverseOf'] = [self.ensure_owl(o) for o in g.objects(s,OWL.inverseOf) if isinstance(o,URIRef)]
            # Blank-node closure in Turtle, preserving local restrictions as written.
            sub = Graph()
            for pre, ns in g.namespaces():
                sub.bind(pre,ns)
            pending, seen = [s], set()
            while pending:
                item = pending.pop()
                if item in seen:
                    continue
                seen.add(item)
                for p,o in g.predicate_objects(item):
                    sub.add((item,p,o))
                    if isinstance(o,BNode):
                        pending.append(o)
            n['xml'] = sub.serialize(format='turtle')
        # Attach globally declared domain relations, WITHOUT pretending validation semantics.
        for n in list(self.nodes.values()):
            if n['format'] != 'OWL' or n['kind'] not in ('objectProperty','dataProperty','annotationProperty'):
                continue
            for domain in n.get('domains',[]):
                if 'ref' not in domain:
                    continue
                dn = self.nodes[domain['ref']]
                dn['properties'].append({'id':n['id']+'/domain:'+dn['id'], 'propertyId':n['id'],
                    'name':n['name'], 'label':n['label'], 'kind':'attribute' if n['kind'] == 'dataProperty' else 'association',
                    'description':n['description'], 'targets':[v['ref'] for v in n.get('ranges',[]) if 'ref' in v],
                    'rangeExpressions':[v for v in n.get('ranges',[]) if 'ref' not in v],
                    'typeName':'rdfs:range', 'multiplicity':None, 'functional':n.get('functional',False),
                    'declaredIn':dn['id'], 'source':n['source'][0] if n['source'] else '',
                    'semantics':'rdfs:domain', 'xml':n.get('xml','')})

    def connect(self):
        cfg = json.loads((self.root/'config/navigation-bridges.json').read_text())
        for bridge in (cfg['bridges'] if self.mode == 'full' else []):
            a = xid(bridge['xsdNamespace'], bridge['xsdElement'])
            b = self.ensure_owl(URIRef(bridge['owlIri']))
            if a in self.nodes:
                self.nodes[a]['bridges'].append({'target':b, 'evidence':bridge['evidence']})
                self.nodes[b]['bridges'].append({'target':a, 'evidence':bridge['evidence']})
        for n in list(self.nodes.values()):
            for p in n['parents']:
                if p in self.nodes:
                    self.nodes[p]['children'].append(n['id'])
            for prop in n['properties']:
                for target in prop['targets']:
                    if target in self.nodes:
                        self.nodes[target]['incoming'].append({'source':n['id'], 'property':prop['name'], 'kind':prop['kind'], 'multiplicity':prop.get('multiplicity'), 'id':prop['id']})
        for n in self.nodes.values():
            n['ancestors'] = self.ancestors(n['id'])
            n['children'].sort(key=lambda id_:self.nodes[id_]['name'].lower())
            n['incompleteInheritance'] = any(self.nodes[a]['external'] for a in n['ancestors'])
        self.resolve_dependencies()

    def ancestors(self, id_, seen=None):
        seen = set(seen or [])
        if id_ in seen:
            self.warnings.append('Ciclo di ereditarieta\u0300: '+id_)
            return []
        seen.add(id_)
        result = []
        for parent in self.nodes[id_]['parents']:
            if parent in seen:
                self.warnings.append('Ciclo di ereditarieta\u0300: '+parent)
                continue
            if parent not in result:
                result.append(parent)
            if parent in self.nodes:
                for other in self.ancestors(parent,seen):
                    if other not in result:
                        result.append(other)
        return result

    def resolve_dependencies(self):
        # Use namespace+basename for XSD; OWL identity/versionIRI, not mere filename.
        for dep in self.dependencies:
            files = []
            if dep['kind'].startswith('xsd:'):
                filename = Path(urlparse(dep['url']).path).name
                files = [f['path'] for f in self.files if f['format']=='XSD' and f['name']==filename and f['namespace']==dep['namespace']]
            else:
                wanted = dep['url'].removesuffix('.ttl').rstrip('/')
                iris = {dep['url'], wanted, wanted+'.ttl'}
                for iri in iris:
                    iri_ref = URIRef(iri)
                    files += sorted(self.owl_source.get(iri,[])) if (iri_ref,RDF.type,OWL.Ontology) in self.graph else []
                    for ontology in self.graph.subjects(OWL.versionIRI,iri_ref):
                        files += sorted(self.owl_source.get(str(ontology),[]))
            dep['status'] = 'local' if files else 'missing'
            dep['localPaths'] = sorted(set(files))
        catalog = ET.Element('{urn:oasis:names:tc:entity:xmlns:xml:catalog}catalog', nsmap={None:'urn:oasis:names:tc:entity:xmlns:xml:catalog'})
        done=set()
        for d in self.dependencies:
            if d['status'] == 'local' and d['url'].startswith(('http:','https:')) and d['url'] not in done:
                done.add(d['url'])
                ET.SubElement(catalog,'{urn:oasis:names:tc:entity:xmlns:xml:catalog}uri',name=d['url'],uri=d['localPaths'][0].removeprefix('sources/'))
        (self.root/('sources/xml-catalog-'+self.mode+'.xml')).write_bytes(ET.tostring(catalog,pretty_print=True,xml_declaration=True,encoding='UTF-8'))

    def build(self):
        self.read_xsd()
        self.read_owl()
        self.connect()
        missing = list({d['url']:d for d in self.dependencies if d['status']=='missing'}.values())
        stats = {'nodes':len(self.nodes), 'defined':sum(not n['external'] for n in self.nodes.values()),
                 'external':sum(n['external'] for n in self.nodes.values()),
                 'files':len(self.files),'originalFiles':sum(f['original'] for f in self.files),
                 'addedFiles':sum(not f['original'] for f in self.files),
                 'properties':sum(len(n['properties']) for n in self.nodes.values()),
                 'missingDependencies':len(missing)}
        data = {'schemaVersion':1, 'title':'CityGML Explorer', 'sourceVersion':'CityGML 3.0', 'mode':self.mode,
                'nodes':self.nodes, 'files':self.files, 'dependencies':self.dependencies,
                'warnings':sorted(set(self.warnings)), 'stats':stats,
                'initialId':xid('http://www.opengis.net/citygml/building/3.0','Building')}
        (self.root/'data').mkdir(exist_ok=True)
        text = json.dumps(data,ensure_ascii=True,separators=(',',':'))
        (self.root/('data/catalog-'+self.mode+'.json')).write_text(text,encoding='utf-8')
        (self.root/'data/catalog.json').write_text(text,encoding='utf-8')
        (self.root/'data/catalog.js').write_text('/* Generated by scripts/build_catalog.py. Do not edit. */\nwindow.CITYGML_CATALOG = '+text+';\n',encoding='utf-8')
        manifest=json.dumps({'mode':self.mode,'files':self.files,
            'dependencies':self.dependencies,'missing':missing},indent=2,ensure_ascii=False)
        (self.root/('sources/dependency-manifest-'+self.mode+'.json')).write_text(manifest,encoding='utf-8')
        (self.root/'sources/dependency-manifest.json').write_text(manifest,encoding='utf-8')
        (self.root/'data/active-mode.json').write_text(json.dumps({
            'mode':self.mode,'description':'CityGML + OWL' if self.mode=='full' else 'Solo CityGML (XSD)'
        },indent=2),encoding='utf-8')
        print(json.dumps(stats,indent=2))
        print('Warnings:',len(data['warnings']))
        return data


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--mode', choices=('citygml','full'), default='citygml')
    args = ap.parse_args()
    Builder(args.root.resolve(),mode=args.mode).build()


if __name__ == '__main__':
    main()
