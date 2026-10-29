#!/usr/bin/env python3
"""Build the local navigation index of CityGML 3.0 from the sources in sources/.

The XSD schemas give the structure; the Conceptual Model sources (OGC 20-010
document and UML model, read by conceptual_model.py) add what the encoding
omits: stereotypes, code lists, allowed boundaries, requirements. The GML
Encoding document (OGC 21-006r2, read by encoding_document.py) adds the
encoding rules that the schemas do not express. Never fetches
anything (see scripts/fetch_sources.py). This is a structural explorer, NOT an
XML validator. Run from any directory: python scripts/build_catalog.py
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from lxml import etree as ET
import ades as ade_config
import build_codelists
import conceptual_model
import encoding_document

ROOT = Path(__file__).resolve().parents[1]
XS = 'http://www.w3.org/2001/XMLSchema'
GML = 'http://www.opengis.net/gml/3.2'
CORE = 'http://www.opengis.net/citygml/3.0'
XLINK = 'http://www.w3.org/1999/xlink'
XML_NS = 'http://www.w3.org/XML/1998/namespace'
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
    'http://www.w3.org/1999/xlink': 'xlink', XML_NS: 'xml'
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
        # The prefix xml is bound by definition and never declared (Namespaces in XML).
        return el.nsmap.get(pre, XML_NS if pre == 'xml' else 'UNRESOLVED:' + pre), name
    return el.nsmap.get(None, fallback), value


def xid(ns, name, kind='element'):
    return f'xsd:{{{ns}}}{kind}:{name}'


def canonical(url):
    p = urlparse(url)
    return urlunparse(p._replace(scheme='http' if p.scheme == 'https' else p.scheme, fragment=''))


def union_alternative(cls, name, classes, norm):
    """(member, alternative) when name is an alternative of the Union type of a member of cls."""
    for member, m in {**cls['attributes'], **cls['associations']}.items():
        union = classes.get(norm(m.get('type') or m.get('target') or ''))
        if union and union['stereotype'] == 'Union':
            alternative = union['attributes'].get(name) or union['associations'].get(name)
            if alternative:
                return member, alternative
    return None


def coverage(classes, nodes, uml_node, norm, simple_declarations=(), model=None):
    """The conceptual model of OGC 20-010 and the lists and unions of the CityGML schemas against the catalog.

    Classes, members and constraints are those of the data dictionary; generalizations those of the
    data dictionary and of the UML model (XMI), with the count of each source in 'declaredBy'.
    For every dimension: declarations in the source (total), present in the
    catalog (represented), outside the catalog with the reason (excluded) and
    findings for what is missing. 'xsd' tells how the encoding represents the
    declarations; its categories come from the schemas, never from a list of names.
    'divergences' lists where the data dictionary and the UML model state different things.
    """
    dims = {d: {'total': 0, 'represented': 0, 'excluded': [], 'findings': [], 'xsd': defaultdict(list)}
            for d in ('classes', 'members', 'generalizations', 'associationClasses', 'constraints', 'simpleTypes')}
    dims['generalizations']['declaredBy'] = {'dictionary': 0, 'model': 0}
    divergences = {'multiplicities': [], 'generalizations': []}

    def missing(dim, declaration, expected):
        dims[dim]['findings'].append({'declaration': declaration, 'expected': expected, 'outcome': 'unresolved'})

    for name, cls in sorted(classes.items()):
        label = cls['name']
        if cls['module'] in (None, 'ISO Classes'):
            reason = 'classe ISO citata dal documento, fuori dal vocabolario CityGML'
            dims['classes']['excluded'].append({'declaration': label, 'reason': reason})
            dims['constraints']['excluded'] += [{'declaration': f"{label}: {c['name'] or c['text']}", 'reason': reason}
                                                for c in cls.get('constraints', [])]
            continue
        id_ = uml_node.get(name)
        node = nodes.get(id_) if id_ else None
        uml = (node or {}).get('uml') or {}
        dims['classes']['total'] += 1
        if uml:
            dims['classes']['represented'] += 1
            dims['classes']['xsd']['withoutXsdType' if node.get('umlOnly') else 'sameName'].append(label)
        else:
            missing('classes', label, 'classe nel catalogo')
        present = {m['name']: m for m in uml.get('properties', [])}
        for member in list(cls['attributes']) + list(cls['associations']):
            dims['members']['total'] += 1
            m = present.get(member)
            if m is None:
                missing('members', f'{label}.{member}', 'membro nella classe del catalogo')
                continue
            dims['members']['represented'] += 1
            rule = ('classWithoutXsdType' if node.get('umlOnly') else 'sameName' if m.get('xsd')
                    else m['xsdMapping']['rule'] if m.get('xsdMapping') else 'none')
            dims['members']['xsd'][rule].append(f'{label}.{member}')
            if m.get('dictionaryMultiplicity'):
                divergences['multiplicities'].append({'declaration': f'{label}.{member}', 'dictionary': m['dictionaryMultiplicity'],
                                                      'model': m['multiplicity']})
        dictionary = cls.get('subclassOf', [])
        stated = (model or {}).get('generalizations', {}).get(name) or {'parents': []}
        listed, drawn = {norm(s) for s in dictionary}, {norm(s) for s in stated['parents']}
        if 'dictionaryParents' in uml:
            divergences['generalizations'].append({'declaration': label, 'dictionary': dictionary, 'model': stated['parents']})
        for parent in dictionary + [s for s in stated['parents'] if norm(s) not in listed]:
            dims['generalizations']['total'] += 1
            dims['generalizations']['declaredBy']['dictionary'] += norm(parent) in listed
            dims['generalizations']['declaredBy']['model'] += norm(parent) in drawn
            declaration = f'{label} → {parent}'
            parent_id = uml_node.get(norm(parent))
            if parent_id is None:
                if classes.get(norm(parent), {}).get('module') == 'ISO Classes':
                    dims['generalizations']['excluded'].append({'declaration': declaration, 'reason': 'superclasse ISO, fuori dal vocabolario CityGML'})
                else:
                    missing('generalizations', declaration, 'superclasse nel catalogo')
            elif parent_id in uml.get('parents', []):
                dims['generalizations']['represented'] += 1
                dims['generalizations']['xsd']['xsExtension' if parent_id in node.get('ancestors', []) else 'umlOnly'].append(declaration)
            else:
                missing('generalizations', declaration, 'generalizzazione nel catalogo')
        kept = {(c['name'], c['text']) for c in uml.get('constraints', [])}
        for c in cls.get('constraints', []):
            dims['constraints']['total'] += 1
            if (c['name'], c['text']) in kept:
                dims['constraints']['represented'] += 1
            else:
                missing('constraints', f"{label}: {c['name'] or c['text']}", 'vincolo nella classe del catalogo')
    # Roles qualified by an association class of the UML model, linked to the class in the catalog.
    for name, roles in sorted((model or {}).get('associationClasses', {}).items()):
        linked = set(((nodes.get(uml_node.get(name)) or {}).get('uml') or {}).get('associationOf', []))
        for owner, role in roles:
            dims['associationClasses']['total'] += 1
            if uml_node.get(owner) and f'{uml_node[owner]}/uml:{role}' in linked:
                dims['associationClasses']['represented'] += 1
            else:
                missing('associationClasses', f'{name} → {owner}.{role}', 'ruolo collegato alla classe di associazione')
    recorded = {(n['source'][0], c.get('line')) for n in nodes.values() if n.get('source')
                for c in n['constraints'] if c['kind'] in ('xs:list', 'xs:union')}
    for path, line, kind in simple_declarations:
        dims['simpleTypes']['total'] += 1
        if (path, line) in recorded:
            dims['simpleTypes']['represented'] += 1
        else:
            missing('simpleTypes', f'{path}:{line} {kind}', 'lista o unione fra i vincoli di un nodo')
    for d in dims.values():
        d['xsd'] = {k: v for k, v in sorted(d['xsd'].items())}
    dims['divergences'] = divergences
    return dims


def document_coverage(standard):
    """Normative documents: acquired, rules extracted, rules linked to the properties they name."""
    kinds = lambda rules: {k: sum(r['kind'] == k for r in rules) for k in sorted({r['kind'] for r in rules})}
    result = [{'document': standard['document'].get('documentNumber'), 'role': 'conceptual-model-document', 'acquired': True,
               'rules': kinds(standard['requirements'])}]
    encoding = standard.get('encoding')
    entry = {'document': (encoding or {}).get('document', {}).get('documentNumber'), 'role': 'gml-encoding-document',
             'acquired': encoding is not None}
    if encoding:
        entry.update(rules=kinds(encoding['requirements']),
                     unrecognizedTables=[t['anchor'] or t['head'] for t in encoding['unrecognized']],
                     linkedProperties=len({p['id'] for r in encoding['requirements'] for p in r['properties']}),
                     unresolvedMentions=[m for r in encoding['requirements'] for m in r.get('unresolvedMentions', [])])
    result.append(entry)
    return result


class Builder:
    def __init__(self, root):
        self.root = root
        self.nodes = {}
        self.elements, self.types, self.groups, self.attrs = {}, {}, {}, {}
        # elementFormDefault and attributeFormDefault of every schema document, by path.
        self.forms = {}
        self.type_alias = {}
        self.node_defs = {}
        self.files = []
        self.dependencies = []
        self.warnings = []
        self.simple_declarations = []
        self.parser = ET.XMLParser(resolve_entities=False, no_network=True)
        manifest = root / 'sources/manifest.json'
        records = json.loads(manifest.read_text(encoding='utf-8'))['files'] if manifest.exists() else []
        self.provenance = {r['path']: r for r in records}
        self.roles = {r['role']: r for r in records if r.get('role')}
        self.standard = None
        self.path_by_url = {r['url']: r['path'] for r in records}
        # ADEs of config/sources.json: their prefix wins over the first one found in the schemas.
        self.ades = ade_config.read(root)
        self.ade_of = {ade.namespace: ade for ade in self.ades}
        for ade in self.ades:
            PREFIXES[ade.namespace] = ade.prefix

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
        if namespace in self.ade_of:
            record['ade'] = self.ade_of[namespace].name
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
        if ns in self.ade_of:
            return self.ade_of[ns].name, 'ADE', False
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
            self.forms[path] = (root.get('elementFormDefault', 'unqualified'), root.get('attributeFormDefault', 'unqualified'))
            if record['citygml']:
                self.simple_declarations += [(record['path'], item.sourceline, 'xs:'+ET.QName(item).localname)
                                             for item in root.iter('{'+XS+'}list', '{'+XS+'}union')]
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
            # A complex type gets its category from its derivation in classify(), as an element does.
            n.update(namespace=ns, qname=self.pretty_q(ns, name), xmlType=self.pretty_q(ns, name),
                     description=doc(te), source=[self.relative(path)], line=te.sourceline,
                     xml=ET.tostring(te, encoding='unicode', pretty_print=True),
                     abstract=te.get('abstract') == 'true',
                     kind='class' if ET.QName(te).localname == 'complexType' else 'datatype',
                     technical=name.endswith('PropertyType'))
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
            n['constraints'].extend(self.simple_structure(te))
            if any(c['kind'] == 'enumeration' for c in n['constraints']):
                n['kind'] = 'enumeration'
            owner_ns = n['namespace']
            container = ext if ext is not None else rest if rest is not None else te
            self.walk_fields(container, n, path, owner_ns)

    def simple_structure(self, st):
        """xs:list and xs:union of a simpleType, also inside the anonymous base of its xs:restriction."""
        result = []
        for item in st.xpath('./xs:list | ./xs:union | ./xs:restriction/xs:simpleType/xs:list | ./xs:restriction/xs:simpleType/xs:union', namespaces=NS):
            tag = ET.QName(item).localname
            ids = [self.ensure_xsd(qname(item, v)) for v in item.get('itemType' if tag == 'list' else 'memberTypes', '').split()]
            entry = {'kind': 'xs:'+tag, 'targets': ids, 'line': item.sourceline}
            notes = []
            if item.getparent() is not st:
                notes.append('Nel tipo base anonimo della restrizione: le faccette della restrizione valgono per la lista.')
            anonymous = len(item.findall('xs:simpleType', NS))
            if anonymous:
                notes.append(f'{anonymous} tipi anonimi non espansi.')
            if notes:
                entry['description'] = ' '.join(notes)
            result.append(entry)
        return result

    def content_forms(self, te, seen=frozenset()):
        """(inline, reference) for a property type: whether the object can be a child element, and whether
        xlink:href can point to it. None where part of the definition is not available locally.

        Followed through xs:extension; an xs:restriction keeps only its own content model.
        """
        if te is None:
            return None, None
        ext = te.find('xs:complexContent/xs:extension', NS)
        rest = te.find('xs:complexContent/xs:restriction', NS)
        body = ext if ext is not None else rest if rest is not None else te
        inline, reference = self.own_content(body, seen), self.has_href(body, seen)
        derived = ext if ext is not None else rest
        if derived is not None:
            base = qname(derived, derived.get('base'))
            if base in seen:
                return inline, reference
            base_inline, base_reference = self.content_forms(self.types.get(base, (None,))[0], seen | {base})
            reference = True if reference or base_reference else None if None in (reference, base_reference) else False
            if ext is not None:
                inline = True if inline or base_inline else None if None in (inline, base_inline) else False
        return inline, reference

    def own_content(self, body, seen):
        if body.xpath('./xs:sequence//xs:element | ./xs:choice//xs:element | ./xs:all//xs:element | ./xs:sequence//xs:any | ./xs:choice//xs:any', namespaces=NS):
            return True
        result = False
        for ref in body.xpath('./xs:group | ./xs:sequence//xs:group | ./xs:choice//xs:group', namespaces=NS):
            pair = qname(ref, ref.get('ref'))
            if pair not in self.groups:
                result = None
            elif pair not in seen and self.own_content(self.groups[pair][0], seen | {pair}):
                return True
        return result

    def has_href(self, body, seen):
        result = False
        for attr in body.xpath('./xs:attribute[@ref] | ./xs:attributeGroup[@ref]', namespaces=NS):
            pair = qname(attr, attr.get('ref'))
            if ET.QName(attr).localname == 'attribute':
                if pair == (XLINK, 'href') and attr.get('use') != 'prohibited':
                    return True
            elif pair not in self.groups:
                result = None
            elif pair not in seen and self.has_href(self.groups[pair][0], seen | {pair}):
                return True
        return result

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
                    # Occurrences of the choice in the type, repetitions of the enclosing groups included.
                    occurs = f"{lo}..{'*' if hi is None else hi}"
                    lo = 0  # Per-branch lower bound; group constraint is kept separately.
                    n['constraints'].append({'kind': 'xs:choice', 'value': f"{child.get('minOccurs','1')}..{child.get('maxOccurs','1')}",
                         'occurs': occurs, 'line': child.sourceline,
                         'description': 'Alternative XML: a ogni occorrenza della scelta compare uno solo dei campi; '
                                        'con più occorrenze i campi possono comparire tutti, in qualsiasi ordine fra loro.'})
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
        # Namespace of the XML name: the referenced declaration's for @ref; for a local declaration, the
        # target namespace when qualified (form, elementFormDefault, attributeFormDefault), else none.
        if ref:
            namespace = ref[0]
        else:
            element_form, attribute_form = self.forms.get(path, ('unqualified', 'unqualified'))
            form = el.get('form') or (element_form if tag == 'element' else attribute_form)
            namespace = owner_ns if form == 'qualified' else None
        prefix = self.pretty_q(namespace, name) if namespace else name
        typ = qname(el, el.get('type'))
        resolved = self.elements.get(ref, (None, None))[0] if tag == 'element' else self.attrs.get(ref, (None, None))[0]
        # nillable, default and fixed belong to the global declaration of a reference; an attribute
        # reference may set its own default or fixed value.
        declaration = resolved if ref and resolved is not None else el
        value = lambda key: el.get(key) if el.get(key) is not None else declaration.get(key)
        if typ is None and resolved is not None:
            typ = qname(resolved, resolved.get('type'))
        targets = self.wrapper_targets(el) if tag == 'element' else []
        # Only a property element wraps the object; an element that is the object itself has no encoding choice.
        wrapper = bool(targets)
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
            an['constraints'].extend(self.simple_structure(st))
            if any(c['kind'] == 'enumeration' for c in an['constraints']):
                an['kind'] = 'enumeration'
            self.nodes[aid] = an
            targets = [(aid, 'tipo semplice anonimo')]
        target_ids = [a for a,b in targets]
        forms = self.content_forms(inline if inline is not None else self.types.get(typ, (None,))[0]) if link and wrapper else None
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
        p = {'id': n['id']+'/property:'+name+':'+str(el.sourceline), 'name': name, 'qname': prefix, 'namespace': namespace,
             'kind': kind, 'xmlKind': 'xs:'+tag, 'description': doc(el) or doc(resolved),
             'targets': target_ids, 'typeId': datatype, 'typeName': self.pretty_q(*typ) if typ else '(tipo anonimo)',
             'multiplicity': f"{lo}..{'*' if hi is None else hi}", 'min': lo, 'max': hi,
             'declaredIn': n['id'], 'source': self.relative(path), 'line': el.sourceline,
             'choices': choices, 'nillable': tag == 'element' and declaration.get('nillable') == 'true',
             'default': value('default'), 'fixed': value('fixed'),
             'targetEvidence': [b for a,b in targets], 'link': link if kind == 'association' else None,
             'xml': ET.tostring(el, encoding='unicode', pretty_print=True)}
        if kind == 'association' and forms:
            p['encoding'] = {'allowsInline': forms[0], 'allowsReference': forms[1]}
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
        uses = {}
        for n in self.nodes.values():
            kept = self.kept_attributes(n['id'], uses)
            if kept:
                n['restrictionAttributes'] = [p['id'] for p in kept]
        self.classify()
        self.apply_ades()
        self.enrich()
        for n in list(self.nodes.values()):
            for prop in n['properties']:
                for target in prop['targets'] + ([prop['codeList']] if prop.get('codeList') else []):
                    if target in self.nodes:
                        self.nodes[target]['incoming'].append({'source':n['id'], 'property':prop['name'], 'kind':prop['kind'], 'link':prop['link'], 'multiplicity':prop.get('multiplicity'), 'id':prop['id']})
            # Members of the conceptual model without an XSD property of the same name.
            for member in (n.get('uml') or {}).get('properties', []):
                if not member['xsd'] and member['typeId'] in self.nodes:
                    self.nodes[member['typeId']]['incoming'].append({'source':n['id'], 'property':member['name'], 'kind':'umlMember', 'link':None, 'multiplicity':member['multiplicity'], 'id':member['id']})
        self.resolve_dependencies()

    def kept_attributes(self, id_, uses, seen=frozenset()):
        """Attribute uses that a restriction keeps from its base type (XML Schema 1.0 Part 1, 3.4.2): those of
        the base, inherited ones included, that the restriction neither declares again nor prohibits. The
        content model of a restriction is declared again in full and is not inherited."""
        n = self.nodes[id_]
        base = n.get('restrictedBase')
        if not base or base not in self.nodes or id_ in seen:
            return []
        declared = {(p['namespace'], p['name']) for p in n['properties'] if p['xmlKind'] == 'xs:attribute'}
        return [p for p in self.attribute_uses(base, uses, seen | {id_}) if (p['namespace'], p['name']) not in declared]

    def attribute_uses(self, id_, uses, seen=frozenset()):
        """All the attribute uses of a type: its own, those of its xs:extension bases and those kept by restrictions."""
        if id_ in uses:
            return uses[id_]
        result, names = [], set()
        for owner in [id_, *self.nodes[id_]['ancestors']]:
            if owner not in self.nodes:
                continue
            own = [p for p in self.nodes[owner]['properties'] if p['xmlKind'] == 'xs:attribute']
            for p in own + self.kept_attributes(owner, uses, seen):
                if (p['namespace'], p['name']) not in names:
                    names.add((p['namespace'], p['name']))
                    result.append(p)
        uses[id_] = result
        return result

    def derivation(self, id_):
        """The node and the types it derives from, by xs:extension and by xs:restriction.

        A restriction does not bring the properties of its base (see ancestors), but the derived
        type stays a type of the base: a gml:Definition, restriction of gml:AbstractGMLType, is a GML object.
        """
        found, stack = set(), [id_]
        while stack:
            x = stack.pop()
            if x in found or x not in self.nodes:
                continue
            found.add(x)
            stack.extend(self.nodes[x]['parents'])
            if self.nodes[x].get('restrictedBase'):
                stack.append(self.nodes[x]['restrictedBase'])
        return found

    def classify(self):
        """Categories derived from the type derivation (xs:extension and xs:restriction), never from names.

        feature   derives from gml:AbstractFeature
        object    derives from gml:AbstractGML, not from gml:AbstractFeature
        datatype  neither: a structure of values without its own identity
        A city object descends from core:AbstractCityObject; its spaceRole is
        'space' or 'boundary' when it descends from core:AbstractSpace or
        core:AbstractSpaceBoundary.
        """
        feature, gml_object = xid(GML, 'AbstractFeature'), xid(GML, 'AbstractGML')
        city, space, boundary = (xid(CORE, name) for name in ('AbstractCityObject', 'AbstractSpace', 'AbstractSpaceBoundary'))
        for n in self.nodes.values():
            line = self.derivation(n['id'])
            if n['kind'] == 'class':
                n['kind'] = 'feature' if feature in line else 'object' if gml_object in line else 'datatype'
            n['cityObject'] = n['kind'] == 'feature' and city in line
            n['spaceRole'] = ('space' if space in line else 'boundary' if boundary in line else None) if n['cityObject'] else None
        identity = ('feature', 'object', 'ade', 'external')
        geometry = {xid(GML, 'AbstractGeometry'), xid(GML, 'AbstractGeometryType', 'type')}
        for n in self.nodes.values():
            for p in n['properties']:
                if p['kind'] != 'association':
                    continue
                if not any(self.nodes[t]['kind'] in identity for t in p['targets'] if t in self.nodes):
                    p['kind'], p['link'] = 'attribute', None
                    p.pop('encoding', None)
                elif all(t in self.nodes and self.derivation(t) & geometry for t in p['targets']):
                    # A GML geometry reached through an anonymous or unlisted property type, e.g. TINRelief.tin
                    p['kind'], p['link'] = 'geometry', None
                    p.pop('encoding', None)

    def apply_ades(self):
        """Code lists, bindings and top-level elements of the ADEs in config/sources.json (scripts/ades.py): the
        schemas of an ADE say neither which code list a gml:CodeType property uses nor which classes are top-level.
        A binding holds for the XSD declaration of the property, so for every element and type that contains it."""
        modules = {n['module'].lower() for n in self.nodes.values() if n['family'] != 'ADE'}
        for ade in self.ades:
            if ade.name.lower() in modules:
                raise ade_config.ConfigError(f'ADE {ade.name}: il nome coincide con un modulo del catalogo.')
            clash = sorted(ns for ns, prefix in PREFIXES.items() if prefix == ade.prefix and ns != ade.namespace)
            if clash:
                raise ade_config.ConfigError(f'ADE {ade.name}: il prefisso {ade.prefix} è già usato per {", ".join(clash)}.')
            own = [n for n in self.nodes.values() if n.get('namespace') == ade.namespace and not n['external']]
            if not own:
                self.warnings.append(f'ADE {ade.name}: nessuno schema con namespace {ade.namespace} in sources/; '
                                     'esegui python scripts/fetch_sources.py.')
            lists = {}
            for name in ade.lists():
                id_ = f'ade:{ade.name}:{name}'
                n = self.base_node(id_, name, ade.name, 'ADE', False)
                n.update(kind='codelist', namespace=ade.namespace, qname=f'{ade.prefix}:{name}', ancestors=[],
                         incompleteInheritance=False, cityObject=False, spaceRole=None)
                url = ade.dictionary(name)
                path = self.path_by_url.get(url) if url else None
                if path and (self.root/path).exists():
                    try:
                        n.update(description=build_codelists.read_dictionary(self.root/path)['description'], source=[path])
                    except (ValueError, ET.LxmlError) as exc:
                        self.warnings.append(f'{path}: dizionario non leggibile ({exc}).')
                elif url:
                    self.warnings.append(f'ADE {ade.name}: il dizionario di {name} non è in sources/; esegui python scripts/fetch_sources.py.')
                self.nodes[id_] = n
                lists[name] = id_
            declarations, owners = {}, [n for n in own if not n.get('anonymous')]
            for key, name in sorted(ade.bindings.items()):
                owner, prop = key.split('/', 1)
                found = next((p for n in owners if n['qname'] == owner for id_ in [n['id'], *n['ancestors']] if id_ in self.nodes
                              for p in self.nodes[id_]['properties'] if p['qname'] == prop), None)
                if found is None:
                    self.warnings.append(f'ADE {ade.name}: collegamento {key}: proprietà non trovata negli schemi.')
                    continue
                declarations[(found['source'], found['line'], found['qname'])] = lists[name]
            for n in self.nodes.values():
                for p in n['properties']:
                    if (p['source'], p['line'], p['qname']) in declarations:
                        p['codeList'] = declarations[(p['source'], p['line'], p['qname'])]
            reported = set()
            for n in own:
                for p in n['properties']:
                    declaration = (p['source'], p['line'], p['qname'])
                    if p['typeName'] == 'gml:CodeType' and not p.get('codeList') and declaration not in reported:
                        reported.add(declaration)
                        self.warnings.append(f'ADE {ade.name}: {n["qname"]}/{p["qname"]} è gml:CodeType senza code list in codeListBindings.')
            for q in ade.top_level:
                n = next((n for n in own if n['qname'] == q and '}element:' in n['id'] and n['kind'] == 'feature'), None)
                if n is None:
                    self.warnings.append(f'ADE {ade.name}: topLevel {q}: nessuna feature dell\'ADE con questo nome.')
                else:
                    n['topLevel'] = True

    def ade_entries(self):
        """The ADEs of the catalog, for the interface and the exporters."""
        result = []
        for ade in self.ades:
            record = self.provenance.get(self.path_by_url.get(canonical(ade.schema)), {})
            result.append({'name': ade.name, 'prefix': ade.prefix, 'namespace': ade.namespace,
                           'schema': {'url': ade.schema, 'path': record.get('path'), 'version': record.get('schemaVersion'),
                                      'sha256': record.get('sha256')},
                           'origin': 'local' if ade.local_base else 'remote',
                           'files': sorted(f['path'] for f in self.files if f.get('ade') == ade.name),
                           'codeLists': {'baseUrl': ade.code_list_base, 'lists': ade.lists(),
                                         'extends': sorted(f'{module}.{name}' for module, name, _ in ade.extensions())},
                           'codeListBindings': dict(sorted(ade.bindings.items())), 'topLevel': ade.top_level})
        return result

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
        norm = lambda name: name.replace('×', 'x')
        stated = (conceptual_model.read_xmi(self.root/uml_record['path']) if uml_record and (self.root/uml_record['path']).exists()
                  else {'members': {}, 'generalizations': {}, 'associationClasses': {}})
        # The UML model, by class name normalized as the data dictionary.
        model = {'members': {(norm(c), m): v for (c, m), v in stated['members'].items()},
                 'generalizations': {norm(c): v for c, v in stated['generalizations'].items()},
                 'associationClasses': {norm(c): [(norm(o), r) for o, r in roles] for c, roles in stated['associationClasses'].items()}}
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
        self.conceptual_classes(classes, uml_node, norm, model)
        self.city_model_members(uml_node)
        for n in self.nodes.values():
            if not n.get('uml') or n.get('umlOnly'):
                continue
            cls = classes[norm(n['uml']['name'])]
            for p in n['properties']:
                role = p['name']
                declared = cls['attributes'].get(role) or cls['associations'].get(role)
                if declared is None:
                    union = union_alternative(cls, role, classes, norm)
                    if union:
                        role, declared = union
                        p['umlMember'] = f"{n['id']}/uml:{role}"
                        report['propertiesMappedToUnion'].append(f"{n['name']}.{p['name']}")
                if declared is None:
                    report['propertiesWithoutUml'].append(f"{n['name']}.{p['name']}")
                else:
                    p['umlType'] = declared.get('type') or declared.get('target')
                    p['umlTypeId'] = uml_node.get(norm(p['umlType']))
                    if classes.get(norm(p['umlType']), {}).get('stereotype') == 'CodeList':
                        p['codeList'] = p['umlTypeId']
                    # The schema documentation wins; the data dictionary fills only an empty one.
                    if not p['description'].strip() and declared.get('definition'):
                        p['description'], p['descriptionSource'] = declared['definition'], 'uml'
                if p['kind'] == 'association' and model['members']:
                    kind = model['members'].get((norm(n['uml']['name']), role), {}).get('aggregation')
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
            'modules': doc['modules'], 'concepts': doc['concepts'], 'topLevelMembers': doc['topLevelMembers'],
            'requirements':[{**r, 'document': '20-010'} for r in doc['requirements']],
            'report': {k: v for k, v in sorted(report.items())},
            'coverage': coverage(classes, self.nodes, uml_node, norm, self.simple_declarations, model),
        }
        self.standard['encoding'] = self.encoding_rules()
        self.standard['coverage']['documents'] = document_coverage(self.standard)

    def conceptual_classes(self, classes, uml_node, norm, model):
        """Generalizations, members and constraints of every class.

        Definitions, types, stereotypes and constraints come from the data dictionary of OGC 20-010;
        multiplicities and generalizations from the UML model (XMI), as drawn in the figures of the
        document. Where the dictionary states something else, its value stays beside the model's:
        dictionaryMultiplicity on the member, dictionaryParents on the class.

        Kept under 'uml', apart from the XSD fields: parents/children/ancestors
        never mix the two hierarchies. A name that is not a class of the
        catalog (ISO types) stays as text, without a link.
        """
        for name, id_ in uml_node.items():
            cls, n = classes[name], self.nodes[id_]
            dictionary = cls.get('subclassOf', [])
            stated = model['generalizations'].get(name)
            listed = {norm(s) for s in dictionary}
            declared = dictionary + [s for s in (stated or {}).get('parents', []) if norm(s) not in listed]
            parents = [(s, uml_node.get(norm(s))) for s in declared]
            xsd = {p['name']: p['id'] for p in n['properties']}
            members = []
            for kind, group, key in (('attribute', 'attributes', 'type'), ('association', 'associations', 'target')):
                for member, m in cls[group].items():
                    type_ = m.get(key) or ''
                    drawn = model['members'].get((name, member), {})
                    entry = {'id': f"{id_}/uml:{member}", 'name': member, 'kind': kind, 'type': type_,
                             'typeId': uml_node.get(norm(type_)), 'multiplicity': drawn.get('multiplicity') or m.get('multiplicity'),
                             'definition': m.get('definition', ''), 'xsd': xsd.get(member)}
                    if drawn.get('multiplicity') and m.get('multiplicity') and drawn['multiplicity'] != m['multiplicity']:
                        entry['dictionaryMultiplicity'] = m['multiplicity']
                    if classes.get(norm(type_), {}).get('stereotype') == 'CodeList':
                        entry['codeList'] = True
                    if kind == 'association' and drawn.get('aggregation'):
                        entry['aggregation'] = drawn['aggregation']
                    if drawn.get('associationClass') and uml_node.get(norm(drawn['associationClass'])):
                        entry['associationClass'] = uml_node[norm(drawn['associationClass'])]
                    if not entry['xsd'] and not n.get('umlOnly'):
                        mapping = self.member_mapping(n, member, classes.get(norm(type_)))
                        if mapping:
                            entry['xsdMapping'] = mapping
                    members.append(entry)
            n['uml'].update(definition=cls.get('definition', ''), parents=[p for s, p in parents if p and p != id_],
                            unresolvedParents=[s for s, p in parents if not p],
                            children=[], properties=members, constraints=cls.get('constraints', []))
            # Compared on the classes of the model file: an ISO superclass outside it is not a divergence.
            if stated is not None and {norm(s) for s in stated['parents']} != {s for s in listed if s in model['generalizations']}:
                n['uml']['dictionaryParents'] = dictionary
        # An association class qualifies the roles of its association: linked both ways.
        for name, roles in model['associationClasses'].items():
            if name in uml_node:
                self.nodes[uml_node[name]]['uml']['associationOf'] = [f'{uml_node[owner]}/uml:{role}' for owner, role in roles
                                                                    if owner in uml_node]
        for id_ in uml_node.values():
            for parent in self.nodes[id_]['uml']['parents']:
                self.nodes[parent]['uml']['children'].append(id_)
        for id_ in uml_node.values():
            n = self.nodes[id_]
            n['uml']['children'].sort(key=lambda c: self.nodes[c]['name'].lower())
            n['uml']['ancestors'] = self.ancestors(id_, parents_of=lambda x: x['uml']['parents'],
                                                   label='Ciclo di generalizzazione UML: ')

    def city_model_members(self, uml_node):
        """Where a class can be a direct member of a CityModel, at both levels. Conceptual model: the attributes
        of the union CityModelMember typed by the class or by one of its UML superclasses. GML encoding: the
        elements of CityModel whose content admits the element through its substitution groups."""
        union = (self.nodes.get(uml_node.get('CityModelMember')) or {}).get('uml', {}).get('properties', [])
        city_model = self.nodes.get(xid(CORE, 'CityModel'))
        members = [p for p in (city_model or {}).get('properties', []) if p['kind'] == 'association']
        for n in self.nodes.values():
            if n['family'] not in ('CityGML', 'ADE'):
                continue
            heads, head = [], n['id']
            while head in self.nodes and head not in heads:
                heads.append(head)
                head = self.nodes[head].get('substitution')
            types = [n['id'], *n['uml'].get('ancestors', [])] if n.get('uml') else []
            # Nearest type first: cityObjectMember before featureMember for a Building.
            found = {'uml': [m['id'] for m in sorted((m for m in union if m.get('typeId') in types), key=lambda m: types.index(m['typeId']))],
                     'gml': [p['id'] for p in sorted((p for p in members if set(heads) & set(p['targets'])),
                                                     key=lambda p: min(heads.index(t) for t in p['targets'] if t in heads))]}
            if found['uml'] or found['gml']:
                n['cityModelMember'] = found

    def encoding_rules(self):
        """Rules of OGC 21-006r2, apart from those of OGC 20-010 (short identifiers coincide, e.g.
        /req/building/boundaries). A property named by a rule ("the X property ... of the E element")
        gets the rule in 'rules'; a name that is not an element or property of the catalog stays listed
        in 'unresolvedMentions'."""
        record = self.roles.get('gml-encoding-document')
        if not record or not (self.root/record['path']).exists():
            self.warnings.append('Documento della codifica GML (OGC 21-006r2) non disponibile in sources/: requisiti di codifica assenti.')
            return None
        part2 = encoding_document.read_document(self.root/record['path'])
        number = part2['metadata'].get('documentNumber')
        if not part2['requirements']:
            self.warnings.append(f"{record['path']}: nessun requisito riconosciuto; la struttura del documento è cambiata.")
        for table in part2['unrecognized']:
            self.warnings.append(f"{record['path']}: tabella {table['head']!r} ({table['anchor']}) con struttura non riconosciuta.")
        elements = {}
        for n in self.nodes.values():
            if n['family'] == 'CityGML' and '}element:' in n['id'] and not n.get('anonymous'):
                elements.setdefault(n['name'], n)
        for rule in part2['requirements']:
            rule['document'] = number
            rule['properties'], unresolved = [], []
            for m in rule.pop('mentions'):
                n = elements.get(m['owner'])
                prop = next((p for id_ in [n['id']] + n['ancestors'] if id_ in self.nodes
                             for p in self.nodes[id_]['properties'] if p['name'] == m['property']), None) if n else None
                if prop is None:
                    unresolved.append(f"{m['owner']}.{m['property']}")
                    continue
                link = {'document': number, 'id': rule['id'], 'part': m['part'], 'anchor': rule['anchor']}
                if link not in prop.setdefault('rules', []):
                    prop['rules'].append(link)
                rule['properties'].append({'id': prop['id'], 'part': m['part']})
            if unresolved:
                rule['unresolvedMentions'] = unresolved
        return {'document': {**part2['metadata'], 'path': record['path'], 'url': record['url'],
                             'retrievedAt': record['retrievedAt'], 'lastModified': record.get('lastModified'),
                             'sha256': record['sha256']},
                'requirements': part2['requirements'], 'unrecognized': part2['unrecognized']}

    def member_mapping(self, n, member, type_cls):
        """Correspondence derived from the schemas for a UML member without a property of the same name:
        a property of the same name inherited through xs:extension, or the properties named after the
        alternatives of the member's Union type. None when the schemas give no such evidence."""
        for ancestor in n['ancestors']:
            for p in self.nodes[ancestor]['properties'] if ancestor in self.nodes else []:
                if p['name'] == member:
                    return {'rule': 'inherited', 'properties': [p['id']]}
        if type_cls and type_cls['stereotype'] == 'Union':
            alternatives = [p['id'] for p in n['properties'] if p['name'] in type_cls['attributes'] or p['name'] in type_cls['associations']]
            if alternatives:
                return {'rule': 'unionAlternatives', 'properties': alternatives}
        return None

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
        # The tables are those of the conceptual model: an ADE space is not expected to have one.
        report['spacesWithoutBoundaryTable'] = sorted(n['name'] for n in self.nodes.values() if n['family'] == 'CityGML'
                                                      and n.get('spaceRole') == 'space' and not n['abstract'] and 'allowedBoundaries' not in n)

    def ancestors(self, id_, seen=None, parents_of=lambda n: n['parents'], label=None):
        label = label or 'Ciclo di ereditarietà: '
        seen = set(seen or [])
        if id_ in seen:
            self.warnings.append(label+id_)
            return []
        seen.add(id_)
        result = []
        for parent in parents_of(self.nodes[id_]):
            if parent in seen:
                self.warnings.append(label+parent)
                continue
            if parent not in result:
                result.append(parent)
            if parent in self.nodes:
                for other in self.ancestors(parent, seen, parents_of, label):
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
        if self.ades:
            stats['adeFiles'] = sum(bool(f.get('ade')) for f in self.files)
            stats['dependencyFiles'] -= stats['adeFiles']
        data = {'schemaVersion':1, 'title':'CityGML 3.0 Explorer',
                'sourceVersion':'CityGML 3.0.0 (OGC 21-006r2)',
                'nodes':self.nodes, 'files':self.files, 'dependencies':self.dependencies, 'standard':self.standard,
                'warnings':sorted(set(self.warnings)), 'stats':stats,
                'initialId':xid('http://www.opengis.net/citygml/building/3.0','Building')}
        if self.ades:
            data['ades'] = self.ade_entries()
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
    try:
        Builder(args.root.resolve()).build()
    except ade_config.ConfigError as exc:
        print('ERRORE:', exc, file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
