"""Read OGC 21-006r2 (CityGML 3.0 Part 2: GML Encoding Standard) stored in sources/.

read_document()  metadata of the front matter; requirements, recommendations,
                 permissions and requirements classes with their statement,
                 lettered parts and notes; the properties their text names
                 ("the X property (type: T) of the E element"). Conformance
                 classes and abstract tests are not rules and are skipped; a
                 rule table with an unexpected layout is listed as unrecognized.

Only extracts what the document states; linking with the catalog happens in
build_catalog.py. The layout differs from OGC 20-010 and is read on its own.
"""
from __future__ import annotations
import re
from lxml import html
from conceptual_model import cell_rows, text

RULE = re.compile(r'^(Requirement|Recommendation|Permission) (\d+)$')
SHORT_ID = re.compile(r'^/(?:req|rec|per)/([a-z]+)/\S+$')
CLASS_URI = re.compile(r'^http://www\.opengis\.net/spec/\S+/req/([a-z]+)$')
PART = re.compile(r'^[A-Z]$')
# The owner is the first capitalized word (a class name) after "of the", past any lowercase adjective.
MENTION = re.compile(r'\bthe (\w+) property(?: \(type: ([^)]+)\))? of (?:the|an?) (?:[a-z]+ )*([A-Z]\w*)')
METADATA = {'Submission Date': 'submissionDate', 'Approval Date': 'approvalDate', 'Publication Date': 'publicationDate',
            'External identifier of this OGC® document': 'identifier',
            'Internal reference number of this OGC® document': 'documentNumber', 'Version': 'version'}


def read_document(path):
    doc = html.parse(str(path)).getroot()
    result = {'metadata': read_metadata(doc), 'requirements': [], 'unrecognized': []}
    for table in doc.iter('table'):
        rows = cell_rows(table)
        if not rows or not rows[0]:
            continue
        head = text(rows[0][0])
        if head.lower() == 'requirements class':
            entry = read_class(table, rows)
        elif re.match(r'^(Requirement|Recommendation|Permission)\b', head):
            entry = read_rule(table, rows)
        else:
            continue
        if entry:
            result['requirements'].append(entry)
        else:
            result['unrecognized'].append({'head': head, 'anchor': table.get('id')})
    return result


def read_metadata(doc):
    """Title and the "Label: value" lines of the front matter (#preamble)."""
    metadata = {'title': text(doc.find('.//title')) if doc.find('.//title') is not None else ''}
    try:
        front = doc.get_element_by_id('preamble')
    except KeyError:
        return metadata
    for el in front.iter('p'):
        label, _, value = text(el).partition(': ')
        if label in METADATA and value:
            metadata.setdefault(METADATA[label], value.split()[0])
    return metadata


def read_rule(table, rows):
    title = text(rows[0][0])
    identifier = text(rows[0][1]) if len(rows[0]) > 1 else ''
    match, short = RULE.match(title), SHORT_ID.match(identifier)
    if not match or not short:
        return None
    statement, parts, notes = [], [], []
    for row in rows[1:]:
        cells = [text(c) for c in row]
        if len(cells) == 1:
            (notes if re.match(r'^Note\b', cells[0]) else statement).append(cells[0])
        elif len(cells) == 2 and PART.match(cells[0]):
            parts.append({'label': cells[0], 'text': cells[1]})
        else:
            return None
    mentions = [{'property': m.group(1), 'type': m.group(2), 'owner': m.group(3), 'part': label}
                for label, content in [(None, s) for s in statement] + [(p['label'], p['text']) for p in parts]
                for m in MENTION.finditer(content)]
    return {'kind': match.group(1), 'title': title, 'id': identifier, 'module': short.group(1),
            'text': statement, 'parts': parts, 'notes': notes, 'anchor': table.get('id'), 'mentions': mentions}


def read_class(table, rows):
    uri = text(rows[1][0]) if len(rows) > 1 and len(rows[1]) == 1 else ''
    match = CLASS_URI.match(uri)
    if not match:
        return None
    target, dependencies = None, []
    for row in rows[2:]:
        cells = [text(c) for c in row]
        if len(cells) == 2 and cells[0] == 'Target type':
            target = cells[1]
        elif len(cells) == 2 and cells[0] == 'Dependency':
            dependencies += [] if cells[1] == '-' else [cells[1]]
        else:
            return None
    return {'kind': 'Requirements class', 'title': 'Requirements class', 'id': uri, 'module': match.group(1),
            'text': [], 'parts': [], 'notes': [], 'targetType': target, 'dependencies': dependencies,
            'anchor': table.get('id'), 'mentions': []}
