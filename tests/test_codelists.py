"""Tests of scripts/build_codelists.py and of the shipped code list dictionary."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import build_codelists as bc

BASE = 'https://data.ogc.org/citygml-swg/CodeList_Examples_3.0.0/'
CURRENT = '''<?xml version="1.0" encoding="utf-8"?>
<gml:Dictionary xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:cmd="http://www.opengis.net/citygml/codelistmetadata/3.0" gml:id="RoofTypeValue">
 <gml:metaDataProperty><cmd:CodeListMetaData><cmd:dataType>RoofTypeValue</cmd:dataType><cmd:authority>SIG3D</cmd:authority><cmd:version>1.0</cmd:version></cmd:CodeListMetaData></gml:metaDataProperty>
 <gml:description></gml:description>
 <gml:identifier codeSpace="https://example.org/RoofTypeValue">RoofTypeValue</gml:identifier>
 <gml:dictionaryEntry><gml:Definition gml:id="id1"><gml:description>gabled roof</gml:description>
  <gml:identifier codeSpace="https://example.org/RoofTypeValue">1030</gml:identifier><gml:name>gabled roof</gml:name></gml:Definition></gml:dictionaryEntry>
</gml:Dictionary>'''
OLDER = '''<?xml version="1.0" encoding="utf-8"?>
<gml:Dictionary xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:cmd="http://www.opengis.net/citygml/codelist-metadata" gml:id="id9">
 <gml:metaDataProperty><cmd:CodeListMetaData><cmd:dataType>doorclassvalue</cmd:dataType><cmd:authority>TBD</cmd:authority></cmd:CodeListMetaData></gml:metaDataProperty>
 <gml:description>Automatically generated examples</gml:description>
 <gml:identifier codeSpace="https://example.org/doorclassvalue">Construction.DoorClassValue</gml:identifier>
 <gml:dictionaryEntry><gml:Definition gml:id="id10"><gml:identifier codeSpace="https://example.org/{example-1}">9991</gml:identifier>
  <gml:description>{example 1}</gml:description><gml:name>{example-1}</gml:name></gml:Definition></gml:dictionaryEntry>
</gml:Dictionary>'''


def project(tmp):
    """A minimal project: config, manifest and two downloaded examples, one list unavailable."""
    root = Path(tmp)
    files = {'Building.RoofTypeValue.xml': CURRENT, 'Construction.DoorClassValue.xml': OLDER}
    folder = root/'sources/data.ogc.org/citygml-swg/CodeList_Examples_3.0.0'
    folder.mkdir(parents=True)
    records = []
    for name, content in files.items():
        (folder/name).write_text(content, encoding='utf-8')
        records.append({'url': BASE + name, 'path': (folder/name).relative_to(root).as_posix(), 'role': 'codelist-sample',
                        'retrievedAt': '2026-01-01T00:00:00+00:00', 'sha256': hashlib.sha256(content.encode()).hexdigest()})
    (root/'config').mkdir()
    (root/'config/sources.json').write_text(json.dumps({'codeListSamples': {
        'baseUrl': BASE, 'files': sorted(files) + ['Tunnel.HollowSpaceUsageValue.xml']}}))
    (root/'sources/manifest.json').write_text(json.dumps({'files': records, 'unavailable': [
        {'url': BASE + 'Tunnel.HollowSpaceUsageValue.xml'}]}))
    return root


def load_js(path):
    text = path.read_text(encoding='utf-8')
    return json.loads(text.split(' = ', 1)[1].rstrip().rstrip(';'))


class BuildTests(unittest.TestCase):
    def test_reads_both_formats_and_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = bc.build(project(tmp))
        lists = data['codeLists']
        roof = lists['RoofTypeValue']
        self.assertEqual((roof['module'], roof['codeSpace'], roof['placeholder']), ('Building', 'https://example.org/RoofTypeValue', False))
        self.assertEqual(roof['values'], [{'code': '1030', 'codeSpace': 'https://example.org/RoofTypeValue',
                                           'name': 'gabled roof', 'description': 'gabled roof'}])
        self.assertEqual(roof['metadata']['authority'], 'SIG3D')
        door = lists['DoorClassValue']
        self.assertTrue(door['placeholder'])
        self.assertEqual(door['metadata']['metadataNamespace'], 'http://www.opengis.net/citygml/codelist-metadata')
        hollow = lists['HollowSpaceUsageValue']
        self.assertEqual((hollow['unavailable'], hollow['availableAtSource'], hollow['values']), (True, False, []))
        self.assertEqual(data['source']['reference'], 'OGC 21-006r2, Annex E (informative)')

    def test_working_copy_is_kept_unless_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            script = [sys.executable, str(ROOT/'scripts/build_codelists.py'), '--root', str(root)]
            subprocess.run(script, check=True, capture_output=True)
            working = root/'codelists/codelists.js'
            self.assertEqual(load_js(working)['kind'], 'local')
            self.assertEqual(load_js(root/'codelists/codelists.default.js')['kind'], 'default')
            working.write_text('window.CITYGML_CODELISTS = {"edited": true};\n', encoding='utf-8')
            subprocess.run(script, check=True, capture_output=True)
            self.assertIn('"edited": true', working.read_text(encoding='utf-8'))
            subprocess.run(script + ['--reset'], check=True, capture_output=True)
            self.assertEqual(load_js(working)['kind'], 'local')
            self.assertIn('RoofTypeValue', load_js(working)['codeLists'])


class ShippedDictionaryTests(unittest.TestCase):
    def test_default_dictionary(self):
        data = load_js(ROOT/'codelists/codelists.default.js')
        lists = data['codeLists']
        self.assertEqual(len(lists), 140)
        self.assertEqual(sum(1 for l in lists.values() if l['values'] and not l['placeholder']), 44)
        self.assertEqual(sum(1 for l in lists.values() if l['placeholder']), 95)
        self.assertEqual([n for n, l in lists.items() if l.get('unavailable')], ['HollowSpaceUsageValue'])
        self.assertIn({'code': '1030', 'codeSpace': 'https://www.sig3d.org/codelists/citygml/building/3.0/RoofTypeValue',
                       'name': 'gabled roof', 'description': 'gabled roof'}, lists['RoofTypeValue']['values'])

    def test_lists_match_catalog_code_lists(self):
        catalog = json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
        names = {n['name'] for n in catalog['nodes'].values() if n['kind'] == 'codelist'}
        self.assertEqual(set(load_js(ROOT/'codelists/codelists.default.js')['codeLists']), names)

    def test_working_copy_is_valid(self):
        data = load_js(ROOT/'codelists/codelists.js')
        self.assertEqual(data['kind'], 'local')
        self.assertEqual(len(data['codeLists']), 140)
        for name, entry in data['codeLists'].items():
            for value in entry['values']:
                self.assertEqual(set(value), {'code', 'codeSpace', 'name', 'description'}, name)


if __name__ == '__main__':
    unittest.main()
