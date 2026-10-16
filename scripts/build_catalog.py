#!/usr/bin/env python3
"""Build the local navigation index of CityGML 3.0 from the sources in sources/.

The XSD schemas give the structure; the Conceptual Model sources (OGC 20-010
document and UML model, read by conceptual_model.py) add what the encoding
omits: stereotypes, code lists, allowed boundaries, requirements. Never fetches
anything (see scripts/fetch_sources.py). This is a structural explorer, NOT an
XML validator. Run from any directory: python scripts/build_catalog.py
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from lxml import etree as ET
import conceptual_model

ROOT = Path(__file__).resolve().parents[1]
XS = 'http://www.w3.org/2001/XMLSchema'
GML = 'http://www.opengis.net/gml/3.2'
CORE = 'http://www.opengis.net/citygml/3.0'
NS = {'xs': XS}
# Property types that GML defines for members of a collection: in CityGML 3.0
# every property in this form is an aggregation of the UML model.
MEMBER_TYPES = {(GML, 'AbstractFeatureMemberType'), (GML, 'AbstractMemberType')}
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
           'waterbody': 'WaterBody', 'landuse': 'LandUse', 'pointcloud': 'PointCloud',
           'codelistmetadata': 'CodeListMetaData'}
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


def canonical(url):
    p = urlparse(url)
    return urlunparse(p._replace(scheme='http' if p.scheme == 'https' else p.scheme, fragment=''))


class Builder:
    def __init__(self, root):
        self.root = root
        self.nodes = {}
        self.elements, self.types, self.groups, self.attrs = {}, {}, {}, {}
        self.type_alias = {}
        self.node_defs = {}
        self.files = []
        self.dependencies = []
        self.warnings = []
        self.parser = ET.XMLParser(resolve_entities=False, no_network=True)
        manifest = root / 'sources/manifest.json'
        records = json.loads(manifest.read_text(encoding='utf-8'))['files'] if manifest.exists() else []
        self.provenance = {r['path']: r for r in records}
        self.roles = {r['role']: r for r in records if r.get('role')}
        self.standard = None
        self.path_by_url = {r['url']: r['path'] for r in records}

    def relative(self, p):
        return str(p.relative_to(self.root)).replace('\\', '/')

    def register_file(self, path, namespace=''):
        rel = self.relative(path)
        info = self.provenance.get(rel, {})
        record = {'path': rel, 'name': path.name, 'namespace': namespace,
                  'citygml': rel.startswith('sources/schemas.opengis.net/citygml/'),
                  'url': info.get('url', ''), 'retrievedAt': info.get('retrievedAt', ''),
                  'lastModified': info.get('lastModified', ''), 'schemaVersion': info.get('schemaVersion'),
                  'sha256': sha(path), 'bytes': path.stat().st_size}
        if info and info.get('sha256') != record['sha256']:
            self.warnings.append(f'{rel}: SHA-256 diverso da sources/manifest.json.')
        if not info:
            self.warnings.append(f'{rel}: file non registrato in sources/manifest.json.')
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

    def base_node(self, id_, name, module, family, support):
        return {'id': id_, 'name': name, 'label': name, 'module': module,
                'family': family, 'support': support,
                'kind': 'class', 'description': '', 'abstract': False,
                'technical': False, 'external': False, 'properties': [],
                'parents': [], 'children': [], 'incoming': [], 'constraints': [],
                'source': []}

    def ensure_xsd(self, pair, kind='type'):
        if not pair:
            return None
        ns, name = pair
        id_ = self.type_alias.get(pair, xid(ns, name, kind)) if kind == 'type' else xid(ns, name, kind)
        if id_ in self.nodes:
            return id_
        module, family, support = self.category(ns)
        n = self.base_node(id_, name, module, family, support)
        n.update(namespace=ns, qname=self.pretty_q(ns, name), external=True,
                 kind='external', xmlType=self.pretty_q(ns, name), technical=True)
        if ns == XS:
            n.update(external=False, kind='datatype', description='Tipo predefinito XML Schema. La definizione normativa non è riprodotta nel catalogo.',
                     builtin=True)
        self.nodes[id_] = n
        return id_

    def read_xsd(self):
        for path in sorted(self.root.glob('sources/**/*.xsd')):
            try:
                root = ET.parse(str(path), self.parser).getroot()
            except ET.XMLSyntaxError as exc:
                self.warnings.append(f'{self.relative(path)}: XML non valido: {exc}')
                continue
            if root.tag != '{'+XS+'}schema':
                continue
            namespace = root.get('targetNamespace', '')
            record = self.register_file(path, namespace)
            for prefix, ns in root.nsmap.items():
                if prefix and ns not in PREFIXES:
                    PREFIXES[ns] = prefix
            for el in root:
                if not isinstance(el.tag, str):
                    continue
                tag = ET.QName(el).localname
                if tag in ('import', 'include', 'redefine'):
                    location = el.get('schemaLocation', '')
                    target = canonical(urljoin(record['url'], location)) if record['url'] and location else location
                    self.dependencies.append({'from': record['path'], 'kind': 'xsd:'+tag,
                        'namespace': el.get('namespace', namespace), 'url': target})
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
            n = self.base_node(xid(ns, name), name, module, family, support)
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
            n = self.base_node(xid(ns, name, 'type'), name, module, family, support)
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
                        'description': 'Definizione non disponibile localmente; eventuali proprietà del gruppo non sono espanse.'})
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
        # Form of the link, read from the XSD; kept only if classify() confirms an association.
        link = None
        if targets:
            member = inline.find('xs:complexContent/xs:extension', NS) if inline is not None else None
            if member is not None and qname(member, member.get('base')) in MEMBER_TYPES:
                link = 'aggregation'
            elif typ == (GML, 'ReferenceType'):
                link = 'reference'
            else:
                link = 'association'
        if inline is not None and not targets:
            # Anonymous data structures get a real navigable local node, not discarded.
            aid = n['id'] + '/anonymous:' + name + ':' + str(el.sourceline)
            an = self.base_node(aid, n['name']+'.'+name, n['module'], n['family'], n['support'])
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
            an = self.base_node(aid, n['name']+'.'+name, n['module'], n['family'], n['support'])
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
        if tag == 'element' and link:
            kind = 'association'  # Confirmed or reverted by classify() once the hierarchy is known.
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
             'targetEvidence': [b for a,b in targets], 'link': link if kind == 'association' else None,
             'xml': ET.tostring(el, encoding='unicode', pretty_print=True)}
        n['properties'].append(p)

    def connect(self):
        for n in list(self.nodes.values()):
            for p in n['parents']:
                if p in self.nodes:
                    self.nodes[p]['children'].append(n['id'])
        for n in self.nodes.values():
            n['ancestors'] = self.ancestors(n['id'])
            n['children'].sort(key=lambda id_:self.nodes[id_]['name'].lower())
            n['incompleteInheritance'] = any(self.nodes[a]['external'] for a in n['ancestors'])
        self.classify()
        self.enrich()
        for n in list(self.nodes.values()):
            for prop in n['properties']:
                for target in prop['targets'] + ([prop['codeList']] if prop.get('codeList') else []):
                    if target in self.nodes:
                        self.nodes[target]['incoming'].append({'source':n['id'], 'property':prop['name'], 'kind':prop['kind'], 'link':prop['link'], 'multiplicity':prop.get('multiplicity'), 'id':prop['id']})
        self.resolve_dependencies()

    def classify(self):
        """Categories derived from the xs:extension hierarchy, never from names.

        feature   descends from gml:AbstractFeature
        object    descends from gml:AbstractGML, not from gml:AbstractFeature
        datatype  neither: a structure of values without its own identity
        A city object descends from core:AbstractCityObject; its spaceRole is
        'space' or 'boundary' when it descends from core:AbstractSpace or
        core:AbstractSpaceBoundary.
        """
        feature, gml_object = xid(GML, 'AbstractFeature'), xid(GML, 'AbstractGML')
        city, space, boundary = (xid(CORE, name) for name in ('AbstractCityObject', 'AbstractSpace', 'AbstractSpaceBoundary'))
        for n in self.nodes.values():
            line = {n['id'], *n['ancestors']}
            if n['kind'] == 'class':
                n['kind'] = 'feature' if feature in line else 'object' if gml_object in line else 'datatype'
            n['cityObject'] = n['kind'] == 'feature' and city in line
            n['spaceRole'] = ('space' if space in line else 'boundary' if boundary in line else None) if n['cityObject'] else None
        identity = ('feature', 'object', 'ade', 'external')
        for n in self.nodes.values():
            for p in n['properties']:
                if p['kind'] == 'association' and not any(self.nodes[t]['kind'] in identity for t in p['targets'] if t in self.nodes):
                    p['kind'], p['link'] = 'attribute', None

    def enrich(self):
        """Add what the Conceptual Model states and the XSD encoding omits.

        Classes are matched by name: the XSD element name equals the UML class
        name; an XSD enumeration or basic type is the UML name plus 'Type'.
        Everything that does not match is listed in standard.report.
        """
        doc_record, uml_record = self.roles.get('conceptual-model-document'), self.roles.get('uml-model')
        if not doc_record or not (self.root/doc_record['path']).exists():
            self.warnings.append('Documento del modello concettuale non disponibile in sources/: catalogo solo XSD.')
            return
        doc = conceptual_model.read_document(self.root/doc_record['path'])
        xmi = conceptual_model.read_xmi(self.root/uml_record['path']) if uml_record and (self.root/uml_record['path']).exists() else {}
        norm = lambda name: name.replace('×', 'x')
        classes = {norm(k): v for k, v in doc['classes'].items()}
        uml_node, report = {}, defaultdict(list)
        candidates = [n for n in self.nodes.values() if n['family'] == 'CityGML' and not n.get('anonymous')
                      and not n['technical'] and not n['external']]
        for exact in (True, False):
            for n in candidates:
                if n.get('uml'):
                    continue
                name = n['name'] if exact else (n['name'][:-4] if n['name'].endswith('Type') else None)
                if name not in classes or name in uml_node:
                    continue
                cls = classes[name]
                n['uml'] = {'name': cls['name'], 'stereotype': cls['stereotype'], 'anchor': cls['anchor'], 'package': cls['module']}
                n['topLevel'] = cls['stereotype'] == 'TopLevelFeatureType'
                if cls['values']:
                    n['literals'] = cls['values']
                uml_node[name] = n['id']
        report['xsdWithoutUml'] = sorted(n['name'] for n in candidates if not n.get('uml'))
        kinds = {'CodeList': 'codelist', 'BasicType': 'basictype', 'Union': 'union', 'DataType': 'datatype'}
        for name, cls in sorted(classes.items()):
            if name in uml_node or cls['stereotype'] not in kinds or cls['module'] in (None, 'ISO Classes'):
                continue
            id_ = f"uml:{cls['module']}:{name}"
            n = self.base_node(id_, cls['name'], cls['module'], 'CityGML', False)
            n.update(kind=kinds[cls['stereotype']], description=cls.get('definition', ''), source=[doc_record['path']],
                     qname=cls['name'], namespace='', umlOnly=True, ancestors=[], incompleteInheritance=False,
                     cityObject=False, spaceRole=None, topLevel=False,
                     uml={'name': cls['name'], 'stereotype': cls['stereotype'], 'anchor': cls['anchor'], 'package': cls['module']})
            if cls['values']:
                n['literals'] = cls['values']
            self.nodes[id_] = n
            uml_node[name] = id_
        for n in self.nodes.values():
            if not n.get('uml') or n.get('umlOnly'):
                continue
            cls = classes[norm(n['uml']['name'])]
            for p in n['properties']:
                declared = cls['attributes'].get(p['name']) or cls['associations'].get(p['name'])
                if declared is None:
                    report['propertiesWithoutUml'].append(f"{n['name']}.{p['name']}")
                else:
                    p['umlType'] = declared.get('type') or declared.get('target')
                    p['umlTypeId'] = uml_node.get(norm(p['umlType']))
                    if classes.get(norm(p['umlType']), {}).get('stereotype') == 'CodeList':
                        p['codeList'] = p['umlTypeId']
                if p['kind'] == 'association' and xmi:
                    kind = xmi.get((n['uml']['name'], p['name']))
                    if kind:
                        p['aggregation'] = kind
                    else:
                        report['associationsWithoutXmi'].append(f"{n['name']}.{p['name']}")
        self.allowed_boundaries(doc['boundaries'], uml_node, norm, report)
        commit = re.search(r'/([0-9a-f]{40})/', uml_record['url']) if uml_record else None
        self.standard = {
            'document': {**doc['metadata'], 'documentNumber': '20-010', 'path': doc_record['path'], 'url': doc_record['url'],
                         'retrievedAt': doc_record['retrievedAt'], 'lastModified': doc_record.get('lastModified'),
                         'sha256': doc_record['sha256']},
            'umlModel': {'path': uml_record['path'], 'url': uml_record['url'], 'retrievedAt': uml_record['retrievedAt'],
                         'sha256': uml_record['sha256'], 'commit': commit.group(1) if commit else None,
                         'member': conceptual_model.INTEGRATED} if uml_record else None,
            'modules': doc['modules'], 'concepts': doc['concepts'], 'requirements': doc['requirements'],
            'report': {k: v for k, v in sorted(report.items())},
        }

    def allowed_boundaries(self, rows, uml_node, norm, report):
        """Tables /req/<module>/boundaries of OGC 20-010, expanded where they say 'and all subclasses'."""
        def descendants(id_):
            found, stack = [], list(self.nodes[id_]['children'])
            while stack:
                child = stack.pop()
                if child not in found:
                    found.append(child)
                    stack.extend(self.nodes[child]['children'])
            return found
        for space, row in sorted(rows.items()):
            space_id = uml_node.get(norm(space))
            if space_id is None:
                report['boundaryRowsWithoutXsd'].append(space)
                continue
            items, resolved = [], []
            for item in row['allowed']:
                class_id = uml_node.get(norm(item['class']))
                if class_id is None:
                    report['boundaryClassesWithoutXsd'].append(item['class'])
                    continue
                items.append({'id': class_id, 'withSubclasses': item['withSubclasses']})
                for id_ in [class_id] + (descendants(class_id) if item['withSubclasses'] else []):
                    if id_ not in resolved:
                        resolved.append(id_)
            concrete = sorted((id_ for id_ in resolved if not self.nodes[id_]['abstract']), key=lambda id_: self.nodes[id_]['name'])
            self.nodes[space_id]['allowedBoundaries'] = {'items': items, 'concrete': concrete, 'ade': row['ade'], 'none': row['none'],
                                                          'requirement': row['requirement'], 'table': row['table'], 'anchor': row['anchor']}
        for n in self.nodes.values():
            if n.get('allowedBoundaries') and not n['abstract']:
                for id_ in n['allowedBoundaries']['concrete']:
                    self.nodes[id_].setdefault('boundaryOf', []).append(n['id'])
        report['spacesWithoutBoundaryTable'] = sorted(n['name'] for n in self.nodes.values()
                                                      if n.get('spaceRole') == 'space' and not n['abstract'] and 'allowedBoundaries' not in n)

    def ancestors(self, id_, seen=None):
        seen = set(seen or [])
        if id_ in seen:
            self.warnings.append('Ciclo di ereditarietà: '+id_)
            return []
        seen.add(id_)
        result = []
        for parent in self.nodes[id_]['parents']:
            if parent in seen:
                self.warnings.append('Ciclo di ereditarietà: '+parent)
                continue
            if parent not in result:
                result.append(parent)
            if parent in self.nodes:
                for other in self.ancestors(parent,seen):
                    if other not in result:
                        result.append(other)
        return result

    def resolve_dependencies(self):
        # An import is local when its absolute URL is a file listed in sources/manifest.json.
        present = {f['path'] for f in self.files}
        for dep in self.dependencies:
            path = self.path_by_url.get(dep['url'])
            dep['status'] = 'local' if path in present else 'missing'
            dep['localPath'] = path if path in present else None

    def build(self):
        self.read_xsd()
        self.connect()
        missing = list({d['url']:d for d in self.dependencies if d['status']=='missing'}.values())
        stats = {'nodes':len(self.nodes), 'defined':sum(not n['external'] for n in self.nodes.values()),
                 'codeLists':sum(n['kind']=='codelist' for n in self.nodes.values()),
                 'topLevel':sum(bool(n.get('topLevel')) for n in self.nodes.values()),
                 'external':sum(n['external'] for n in self.nodes.values()),
                 'files':len(self.files),'citygmlFiles':sum(f['citygml'] for f in self.files),
                 'dependencyFiles':sum(not f['citygml'] for f in self.files),
                 'properties':sum(len(n['properties']) for n in self.nodes.values()),
                 'missingDependencies':len(missing)}
        data = {'schemaVersion':1, 'title':'CityGML 3.0 Explorer',
                'sourceVersion':'CityGML 3.0.0 (OGC 21-006r2)',
                'nodes':self.nodes, 'files':self.files, 'dependencies':self.dependencies, 'standard':self.standard,
                'warnings':sorted(set(self.warnings)), 'stats':stats,
                'initialId':xid('http://www.opengis.net/citygml/building/3.0','Building')}
        (self.root/'data').mkdir(exist_ok=True)
        text = json.dumps(data,ensure_ascii=True,separators=(',',':'))
        (self.root/'data/catalog.json').write_text(text,encoding='utf-8')
        (self.root/'data/catalog.js').write_text('/* Generated by scripts/build_catalog.py. Do not edit. */\nwindow.CITYGML_CATALOG = '+text+';\n',encoding='utf-8')
        print(json.dumps(stats,indent=2))
        if self.standard:
            print('Confronto con il modello concettuale:', json.dumps({k: len(v) for k, v in self.standard['report'].items()}))
        print('Warnings:',len(data['warnings']))
        return data


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=ROOT)
    args = ap.parse_args()
    Builder(args.root.resolve()).build()


if __name__ == '__main__':
    main()
