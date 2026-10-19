"""Read the CityGML 3.0 Conceptual Model sources stored in sources/.

read_document()  OGC 20-010 (HTML): data dictionary, allowed space boundaries,
                 requirements, chapter structure and document metadata.
read_xmi()       UML model (XMI in the official zip): aggregation kind of every
                 association end.

Both functions only extract what the sources state; matching with the XSD
classes happens in build_catalog.py.
"""
from __future__ import annotations
import re
import zipfile
from lxml import etree as ET
from lxml import html

CAPTION = re.compile(r'^Table\s+\S+\s+\W\s+(Metadata|Attributes|Associations|Values) of (\S+) \((\w+)\)$')
CLASS_REF = re.compile(r'\b([A-Z][A-Za-z]+)::([A-Za-z_]+)')
TYPED = re.compile(r'^(.*?)\s*\[([^\]]+)\]$')
REQ_ID = re.compile(r'^(/(?:req|rec|per)/[A-Za-z]+/\S+|http://www\.opengis\.net/spec/CityGML-1/3\.0/req/req-class-\S+)$')


def text(el):
    return ' '.join(el.text_content().split())


def cell_rows(table):
    return [[c for c in tr if isinstance(c.tag, str) and c.tag in ('td', 'th')] for tr in table.iter('tr')]


def rows(table):
    return [[text(c) for c in cells] for cells in cell_rows(table)]


def lines(el):
    """Text of an element keeping the line breaks (<br>, paragraphs): OCL is written on several lines."""
    copy = html.fromstring(html.tostring(el))
    for br in copy.iter('br'):
        br.tail = '\n' + (br.tail or '')
    for block in copy.iter('p', 'pre', 'div'):
        block.tail = '\n' + (block.tail or '')
    return '\n'.join(' '.join(line.split()) for line in copy.text_content().split('\n') if line.strip())


def read_constraint(cell, caption):
    """A Constraint row of a Metadata table: name (when written as "name:" in <tt>) and original text."""
    body = lines(cell)
    name = cell.find('.//tt')
    label = name.text_content().strip() if name is not None else None
    if label and body.startswith(label + ':'):
        body = body[len(label) + 1:].strip()
    return {'name': label, 'text': body, 'table': ' '.join(caption.split()[:2])}


def next_table(el):
    el = el.getnext()
    while el is not None and el.tag != 'table':
        el = el.getnext()
    return el


def read_document(path):
    doc = html.parse(str(path)).getroot()
    result = {'classes': {}, 'packages': {}, 'boundaries': {}, 'requirements': [], 'modules': {}, 'concepts': [],
              'metadata': read_metadata(doc)}
    chapter = section = module = None
    current = None
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        if el.tag in ('h1', 'h2', 'h3'):
            title = text(el)
            number = title.split(' ', 1)[0]
            if el.tag == 'h1':
                chapter = number
            if el.tag == 'h2':
                section = title
            anchor = el.get('id') or el.getparent().get('id')
            if chapter == '6.' and el.tag in ('h2', 'h3') and anchor:
                result['concepts'].append({'number': number.rstrip('.'), 'title': title.split(' ', 1)[1], 'anchor': anchor,
                                           'level': int(el.tag[1])})
            if chapter == '7.' and el.tag == 'h2' and el.get('id') and number not in ('7.1.',):
                result['modules'][title.split(' ', 1)[1]] = {'number': number.rstrip('.'), 'anchor': el.get('id')}
            if chapter == '8.' and el.tag == 'h2':
                module = title.split(' ', 1)[1]
            continue
        if el.tag == 'p' and chapter == '8.':
            match = CAPTION.match(text(el))
            table = next_table(el) if match else None
            if table is None:
                continue
            what, name, stereotype = match.groups()
            # A package (ApplicationSchema) can share its name with a class, e.g. Building.
            target = result['packages'] if stereotype == 'ApplicationSchema' else result['classes']
            current = target.setdefault(name, {'name': name, 'module': module, 'stereotype': stereotype,
                                                           'attributes': {}, 'associations': {}, 'values': [], 'constraints': []})
            body = rows(table)
            if what == 'Metadata':
                # Rows are "Label:" / value; the label is the cell ending with a colon.
                info = {}
                for r, cells in zip(body, cell_rows(table)):
                    if len(r) == 2:
                        first = r[0].endswith(':')
                        label, value = (r[0], r[1]) if first else (r[1], r[0])
                        if label == 'Constraint:':
                            # A table can hold several constraints: a list, never overwritten.
                            current['constraints'].append(read_constraint(cells[1] if first else cells[0], match.group(0)))
                        else:
                            info[label.rstrip(':')] = value
                current['definition'] = info.get('Definition', '')
                current['subclassOf'] = [s for s in info.get('Subclass of', '').split(', ') if s and s != 'None']
            elif what == 'Attributes':
                for name_, typed, definition in (r for r in body[1:] if len(r) == 3):
                    t = TYPED.match(typed)
                    current['attributes'][name_] = {'type': t.group(1) if t else typed, 'multiplicity': t.group(2) if t else None,
                                                     'definition': definition}
            elif what == 'Associations':
                for role, typed, definition in (r for r in body[1:] if len(r) == 3):
                    t = TYPED.match(typed)
                    current['associations'][role] = {'target': t.group(1) if t else typed,
                                                     'multiplicity': t.group(2) if t else None, 'definition': definition}
            elif what == 'Values':
                current['values'] = [{'value': r[0], 'definition': r[1]} for r in body[1:] if len(r) == 2]
        if el.tag == 'table':
            table_id = el.get('id') or ''
            if table_id.endswith('-boundaries-table'):
                read_boundaries(el, table_id, result)
            elif 'recommend' in (el.get('class') or ''):
                requirement = read_requirement(el)
                if requirement:
                    result['requirements'].append(requirement)
    anchors = {e.get('id') for e in doc.iter() if isinstance(e.tag, str) and e.get('id')}
    for name, cls in result['classes'].items():
        cls['anchor'] = name + '-section' if name + '-section' in anchors else None
    return result


def read_boundaries(table, table_id, result):
    caption = table.getprevious()
    while caption is not None and not text(caption).startswith('Table'):
        caption = caption.getprevious()
    label = text(caption).split(' ')[:2] if caption is not None else []
    module = table_id.removesuffix('-boundaries-table')
    for tr in list(table.iter('tr'))[1:]:
        cells = [c for c in tr if isinstance(c.tag, str) and c.tag in ('td', 'th')]
        if len(cells) != 2:
            continue
        space = text(cells[0])
        # Top-level list items only: nested lists repeat the subclasses already listed in their parent item.
        items = [li for li in cells[1].iter('li') if not any(a.tag == 'li' for a in li.iterancestors())] or [cells[1]]
        allowed, ade, none = [], False, False
        for item in items:
            # Join text nodes with spaces: nested list items must not run together.
            content = ' '.join(' '.join(item.itertext()).split())
            if content.lower().startswith('no boundaries allowed'):
                none = True
                continue
            if 'classes from ADEs' in content:
                ade = True
            refs = CLASS_REF.findall(content)
            if not refs:
                continue
            subclasses = bool(re.search(r'and (all|the) subclasses', content))
            main = refs[0][1]
            allowed.append({'class': main, 'withSubclasses': subclasses,
                            'listed': [cls for _, cls in refs[1:]] if subclasses else []})
            if not subclasses:
                allowed.extend({'class': cls, 'withSubclasses': False, 'listed': []} for _, cls in refs[1:])
        result['boundaries'][space] = {'allowed': allowed, 'ade': ade, 'none': none, 'module': module,
                                       'table': ' '.join(label), 'anchor': table_id,
                                       'requirement': f'/req/{module}/boundaries'}


def read_requirement(table):
    title = text(table.find('.//th')) if table.find('.//th') is not None else ''
    kind = re.sub(r'\s+[A-Z]?\.?\d[\d.]*$', '', title)
    if kind not in ('Requirement', 'Requirements class', 'Recommendation', 'Permission'):
        return None
    paragraphs = [text(p) for p in table.iter('p')]
    identifier = next((p for p in paragraphs if REQ_ID.match(p)), None)
    if identifier is None:
        return None
    body = [p for p in paragraphs if p not in (title, identifier)]
    module = re.search(r'/(?:req|rec|per)/([a-z]+)/', identifier) or re.search(r'req-class-([a-z]+)$', identifier)
    return {'kind': kind, 'title': title, 'id': identifier, 'module': module.group(1) if module else None,
            'text': body, 'anchor': table.get('id')}


def read_metadata(doc):
    """Title, version, number and dates from the front matter (before the Abstract)."""
    metadata = {'title': text(doc.find('.//title')) if doc.find('.//title') is not None else ''}
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        if el.get('id') == 'toc0':
            break
        if el.tag not in ('p', 'div', 'span', 'b', 'strong', 'td', 'th', 'dt', 'dd'):
            continue
        label = text(el)
        if label in ('Submission Date:', 'Approval Date:', 'Publication Date:') and el.getnext() is not None:
            key = label.rstrip(':').split()[0].lower() + 'Date'
            metadata.setdefault(key, text(el.getnext()))
        match = re.search(r'Version:\s*([\d.]+)', label)
        if match and len(label) < 80:
            metadata.setdefault('version', match.group(1))
        match = re.search(r'Document number:\s*([\w-]+)', label)
        if match:
            metadata.setdefault('documentNumber', match.group(1))
        match = re.search(r'External identifier of this OGC.{0,3} document:\s*(\S+)', label)
        if match:
            metadata.setdefault('identifier', match.group(1))
    return metadata


XMI = '{http://schema.omg.org/spec/XMI/2.1}'
INTEGRATED = 'XMI Files/OGC CityGML 3.0/Integrated/CityGML_3.0.xml'


def read_xmi(zip_path):
    """Return {(owner class, role name): 'composite' | 'shared' | 'none'} for every association end."""
    with zipfile.ZipFile(zip_path) as archive:
        root = ET.fromstring(archive.read(INTEGRATED), parser=ET.XMLParser(resolve_entities=False, no_network=True, huge_tree=True))
    classes = {el.get(XMI + 'id'): el for el in root.iter()
               if isinstance(el.tag, str) and el.get(XMI + 'type') in ('uml:Class', 'uml:DataType')}
    owned = {}
    for cls in classes.values():
        for attr in cls:
            if attr.tag == 'ownedAttribute' and attr.get('association'):
                owned.setdefault(attr.get('association'), []).append(attr)
    rank = {None: 0, 'none': 0, 'shared': 1, 'composite': 2}
    result = {}
    for assoc in root.iter():
        if not isinstance(assoc.tag, str) or assoc.get(XMI + 'type') != 'uml:Association':
            continue
        ends = [e for e in assoc if e.get(XMI + 'type') == 'uml:Property'] + owned.get(assoc.get(XMI + 'id'), [])
        if len(ends) != 2:
            continue
        kind = max((e.get('aggregation') for e in ends), key=lambda k: rank.get(k, 0)) or 'none'
        for i, end in enumerate(ends):
            other = ends[1 - i]
            end_type, other_type = end.find('type'), other.find('type')
            if not end.get('name') or end_type is None or other_type is None:
                continue
            owner = classes.get(other_type.get(XMI + 'idref'))
            if owner is not None and owner.get('name'):
                result[(owner.get('name'), end.get('name'))] = kind
    return result
