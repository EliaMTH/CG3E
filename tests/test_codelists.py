"""Tests of scripts/build_codelists.py and of the shipped code list dictionary."""
import hashlib
import json
import shutil
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


ADE_BASE = 'https://example.org/cg3e/test-ade/1.0/codelists/'
DOOR_TERMS = f'''<?xml version="1.0" encoding="utf-8"?>
<gml:Dictionary xmlns:gml="http://www.opengis.net/gml/3.2" gml:id="DoorClassValue">
 <gml:identifier codeSpace="{ADE_BASE}Construction.DoorClassValue.xml">DoorClassValue</gml:identifier>
 <gml:dictionaryEntry><gml:Definition gml:id="id1"><gml:identifier>D1</gml:identifier><gml:name>door D1</gml:name></gml:Definition></gml:dictionaryEntry>
</gml:Dictionary>'''


def ade_project(tmp, extension='Construction.DoorClassValue.xml'):
    """project() with the Test ADE: a list with a dictionary, one without, and values for a CityGML list."""
    root = project(tmp)
    folder = root/'sources/example.org/cg3e/test-ade/1.0/codelists'
    folder.mkdir(parents=True)
    energy = (ROOT/'tests/fixtures/ade/1.0/codelists/TestADE.EnergyClassValue.xml').read_text(encoding='utf-8')
    manifest = json.loads((root/'sources/manifest.json').read_text())
    for name, content in (('TestADE.EnergyClassValue.xml', energy), (extension, DOOR_TERMS)):
        (folder/name).write_text(content, encoding='utf-8')
        manifest['files'].append({'url': ADE_BASE + name, 'path': (folder/name).relative_to(root).as_posix(), 'role': 'ade-codelist',
                                  'retrievedAt': '2026-01-02T00:00:00+00:00', 'sha256': hashlib.sha256(content.encode()).hexdigest()})
    (root/'sources/manifest.json').write_text(json.dumps(manifest))
    config = json.loads((root/'config/sources.json').read_text())
    config['ades'] = [{'name': 'TestADE', 'prefix': 'tade', 'namespace': 'https://example.org/cg3e/test-ade/1.0',
                       'schema': 'https://example.org/cg3e/test-ade/1.0/test-ade.xsd',
                       'codeLists': {'baseUrl': ADE_BASE, 'files': ['TestADE.EnergyClassValue.xml', extension]},
                       'codeListBindings': {'tade:BuildingProperties/tade:ownerType': 'OwnerTypeValue'}}]
    (root/'config/sources.json').write_text(json.dumps(config))
    return root


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


class AdeTests(unittest.TestCase):
    def test_ade_lists_and_values_for_citygml_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            lists = bc.build(ade_project(tmp))['codeLists']
        energy = lists['tade:EnergyClassValue']
        self.assertEqual((energy['module'], energy['ade'], energy['identifier'], [v['code'] for v in energy['values']]),
                         ('TestADE', 'TestADE', 'EnergyClassValue', ['A', 'B']))
        self.assertEqual(lists['tade:OwnerTypeValue'], {'module': 'TestADE', 'ade': 'TestADE', 'values': [], 'placeholder': False})
        # Values for a CityGML list: marked with the ADE, with the codeSpace of its dictionary; the list is no longer placeholder-only
        door = lists['DoorClassValue']
        self.assertEqual(door['values'][-1], {'code': 'D1', 'codeSpace': ADE_BASE + 'Construction.DoorClassValue.xml',
                                              'name': 'door D1', 'description': '', 'ade': 'TestADE'})
        self.assertFalse(door['placeholder'])
        self.assertNotIn('ade', door)

    def test_values_only_for_an_existing_citygml_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = ade_project(tmp, extension='Building.DoorClassValue.xml')
            with self.assertRaisesRegex(bc.ade_config.ConfigError, 'DoorClassValue non è una code list del modulo Building'):
                bc.build(root)

    def test_align_adds_and_prune_removes_only_ade_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = ade_project(tmp)
            default = bc.build(root)
            config = json.loads((root/'config/sources.json').read_text())
            del config['ades']
            (root/'config/sources.json').write_text(json.dumps(config))
            plain = bc.build(root)
        working = {**plain, 'kind': 'local'}
        working['codeLists']['RoofTypeValue']['values'][0]['name'] = 'edited name'
        aligned, changes = bc.align(working, default)
        self.assertEqual(changes, ['DoorClassValue: aggiunte le voci di TestADE (1)', 'aggiunta la code list tade:EnergyClassValue',
                                   'aggiunta la code list tade:OwnerTypeValue'])
        self.assertEqual(aligned['codeLists']['RoofTypeValue']['values'][0]['name'], 'edited name')
        self.assertEqual(aligned['codeLists']['DoorClassValue']['values'][-1]['code'], 'D1')
        self.assertEqual(bc.align(aligned, default), (aligned, []))
        # A value of the ADE deleted by hand comes back with the next --align
        deleted = bc.align(aligned, default)[0]
        deleted['codeLists']['DoorClassValue']['values'].pop()
        self.assertEqual(bc.align(deleted, default)[1], ['DoorClassValue: aggiunte le voci di TestADE (1)'])
        # Without the ADE: nothing removed without prune, its lists and values removed with it
        self.assertEqual(bc.align(aligned, plain)[1], [])
        pruned, changes = bc.align(aligned, plain, prune=True)
        self.assertEqual(changes, ['tolta la code list tade:EnergyClassValue', 'tolta la code list tade:OwnerTypeValue',
                                   'DoorClassValue: tolte le voci di ADE non più configurate (1)'])
        self.assertEqual(pruned['codeLists'], {**plain['codeLists'], 'RoofTypeValue': aligned['codeLists']['RoofTypeValue']})

    def test_command_aligns_only_when_asked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            script = [sys.executable, str(ROOT/'scripts/build_codelists.py'), '--root', str(root)]
            subprocess.run(script, check=True, capture_output=True)
            working = root/'codelists/codelists.js'
            before = working.read_bytes()
            ade_project_root = ade_project(tempfile.mkdtemp(dir=tmp))
            for name in ('config/sources.json', 'sources/manifest.json'):
                (root/name).write_bytes((ade_project_root/name).read_bytes())
            shutil.copytree(ade_project_root/'sources/example.org', root/'sources/example.org')
            run = subprocess.run(script, check=True, capture_output=True, text=True)
            self.assertIn('allinealo con --align', run.stdout)
            self.assertEqual(working.read_bytes(), before)
            self.assertEqual(subprocess.run(script + ['--prune'], capture_output=True).returncode, 2)
            run = subprocess.run(script + ['--align'], check=True, capture_output=True, text=True)
            self.assertIn('aggiunta la code list tade:EnergyClassValue', run.stdout)
            self.assertIn('tade:EnergyClassValue', load_js(working)['codeLists'])
            run = subprocess.run(script + ['--align'], check=True, capture_output=True, text=True)
            self.assertIn('già allineato', run.stdout)


def citygml_lists(data):
    """The 140 code lists of CityGML, each with its own values: without the lists and the values of the ADEs."""
    return {n: [v for v in l['values'] if not v.get('ade')] for n, l in data['codeLists'].items() if not l.get('ade')}


class ShippedDictionaryTests(unittest.TestCase):
    def test_default_dictionary(self):
        data = load_js(ROOT/'codelists/codelists.default.js')
        lists, own = data['codeLists'], citygml_lists(data)
        self.assertEqual(len(own), 140)
        self.assertEqual(sum(1 for values in own.values() if values and not bc.placeholder_only(values)), 44)
        self.assertEqual(sum(1 for values in own.values() if bc.placeholder_only(values)), 95)
        self.assertEqual([n for n, l in lists.items() if l.get('unavailable')], ['HollowSpaceUsageValue'])
        self.assertIn({'code': '1030', 'codeSpace': 'https://www.sig3d.org/codelists/citygml/building/3.0/RoofTypeValue',
                       'name': 'gabled roof', 'description': 'gabled roof'}, lists['RoofTypeValue']['values'])

    def test_lists_match_catalog_code_lists(self):
        catalog = json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
        keys = {n.get('qname') or n['name'] for n in catalog['nodes'].values() if n['kind'] == 'codelist'}
        self.assertEqual(set(load_js(ROOT/'codelists/codelists.default.js')['codeLists']), keys)

    def test_working_copy_is_valid(self):
        data = load_js(ROOT/'codelists/codelists.js')
        self.assertEqual(data['kind'], 'local')
        self.assertEqual(len(citygml_lists(data)), 140)
        for name, entry in data['codeLists'].items():
            for value in entry['values']:
                self.assertEqual(set(value) - {'ade'}, {'code', 'codeSpace', 'name', 'description'}, name)


if __name__ == '__main__':
    unittest.main()
