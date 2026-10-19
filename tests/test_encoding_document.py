"""Tests of scripts/encoding_document.py on a synthetic document shaped like OGC 21-006r2."""
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import encoding_document as ed

DOCUMENT = '''<html><head><meta charset="utf-8"><title>CityGML Part 2</title></head><body class="book">
<div id="header"></div><div id="content"><div id="preamble"><div class="sectionbody">
<p>Approval Date: 2023-05-10</p><p>Publication Date: 2023-06-20</p>
<p>External identifier of this OGC® document: http://www.opengis.net/doc/IS/CityGML-2/3.0</p>
<p>Internal reference number of this OGC® document: 21-006r2</p><p>Version: 3.0</p></div></div>
<div class="sect1">
<table id="core-requirements-class"><tbody>
<tr><td><p>Requirements Class</p></td></tr>
<tr><td><p>http://www.opengis.net/spec/CityGML-2/3.0/req/core</p></td></tr>
<tr><td><p>Target type</p></td><td><p>Implementations of the CityGML 3.0 Conceptual Model using GML encodings</p></td></tr>
<tr><td><p>Dependency</p></td><td><p>core.xsd</p></td></tr>
<tr><td><p>Dependency</p></td><td><p>http://www.opengis.net/spec/CityGML-1/3.0/req/req-class-core</p></td></tr></tbody></table>
<table id="req_core_reference"><tbody>
<tr><td><p><strong>Requirement  8</strong></p></td><td><p><strong>/req/core/reference</strong></p></td></tr>
<tr><td colspan="2"><p>The following properties only allow to reference other features:</p></td></tr>
<tr><td><p>A</p></td><td><p>If the <em>generalizesTo</em> property (type: <em>gml:ReferenceType</em>) of the <em>AbstractCityObject</em>
 element is not null, it SHALL contain an XLink reference.</p></td></tr>
<tr><td><p>B</p></td><td><p>A ring SHALL be referenced by the target property of the embracing ParameterizedTexture element.</p></td></tr>
<tr><td colspan="2"><p>Note: The XLink points to a feature of the same document or of another one.</p></td></tr></tbody></table>
<table id="rec_core_crs"><tbody>
<tr><td><p>Recommendation 1</p></td><td><p>/rec/core/crs</p></td></tr>
<tr><td colspan="2"><p>A document SHOULD use a single CRS.</p></td></tr></tbody></table>
<table id="req_core_odd"><tbody>
<tr><td><p>Requirement 9</p></td><td><p>/req/core/odd</p></td></tr>
<tr><td><p>Unexpected</p></td><td><p>layout</p></td></tr></tbody></table>
<table id="conf_core"><tbody><tr><td><p>Conformance Class</p></td></tr>
<tr><td><p>http://www.opengis.net/spec/CityGML-2/3.0/conf/core</p></td></tr></tbody></table>
<table id="ats_core_reference"><tbody><tr><td><p>Abstract Test 1</p></td></tr>
<tr><td><p>Test ID:</p></td><td><p>/conf/core/reference</p></td></tr></tbody></table>
</div></div></body></html>'''


class EncodingDocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = Path(cls.tmp.name)/'part2.html'
        path.write_text(DOCUMENT, encoding='utf-8')
        cls.doc = ed.read_document(path)
        cls.rules = {r['id']: r for r in cls.doc['requirements']}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_metadata(self):
        self.assertEqual(self.doc['metadata'], {'title': 'CityGML Part 2', 'approvalDate': '2023-05-10', 'publicationDate': '2023-06-20',
                                                'identifier': 'http://www.opengis.net/doc/IS/CityGML-2/3.0',
                                                'documentNumber': '21-006r2', 'version': '3.0'})

    def test_rules_but_not_conformance_tests(self):
        self.assertEqual(list(self.rules), ['http://www.opengis.net/spec/CityGML-2/3.0/req/core', '/req/core/reference', '/rec/core/crs'])
        self.assertEqual(self.doc['unrecognized'], [{'head': 'Requirement 9', 'anchor': 'req_core_odd'}])

    def test_requirement_parts_notes_and_mentions(self):
        rule = self.rules['/req/core/reference']
        self.assertEqual((rule['kind'], rule['title'], rule['module'], rule['anchor']),
                         ('Requirement', 'Requirement 8', 'core', 'req_core_reference'))
        self.assertEqual(rule['text'], ['The following properties only allow to reference other features:'])
        self.assertEqual([p['label'] for p in rule['parts']], ['A', 'B'])
        self.assertEqual(rule['notes'], ['Note: The XLink points to a feature of the same document or of another one.'])
        self.assertEqual(rule['mentions'], [
            {'property': 'generalizesTo', 'type': 'gml:ReferenceType', 'owner': 'AbstractCityObject', 'part': 'A'},
            {'property': 'target', 'type': None, 'owner': 'ParameterizedTexture', 'part': 'B'}])
        self.assertEqual(self.rules['/rec/core/crs']['kind'], 'Recommendation')

    def test_requirements_class(self):
        cls = self.rules['http://www.opengis.net/spec/CityGML-2/3.0/req/core']
        self.assertEqual((cls['kind'], cls['module'], cls['anchor']), ('Requirements class', 'core', 'core-requirements-class'))
        self.assertEqual(cls['dependencies'], ['core.xsd', 'http://www.opengis.net/spec/CityGML-1/3.0/req/req-class-core'])
        self.assertTrue(cls['targetType'].startswith('Implementations'))


if __name__ == '__main__':
    unittest.main()
