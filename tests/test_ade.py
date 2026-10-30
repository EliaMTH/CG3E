"""An ADE from config/sources.json to the catalog, the code list dictionary and the exports, on the real
sources/ and on the Test ADE of tests/fixtures/ade (written after the cases of the Test ADE of OGC 21-006r2, Annex B).

The project inputs are copied into a temporary folder. fetch_sources.py runs with the network
disabled: it reuses sources/ and reads the ADE from its local folder.
"""
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from lxml import etree as ET
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import build_catalog
import exporters as ex
import fetch_sources
import verify_sources

NS = 'https://example.org/cg3e/test-ade/1.0'
BASE = 'https://example.org/cg3e/test-ade/'
TEST_ADE = {
    'name': 'TestADE', 'prefix': 'tade', 'namespace': NS, 'schema': BASE + '1.0/test-ade.xsd',
    'local': {'baseUrl': BASE, 'folder': 'ade'},
    'codeLists': {'baseUrl': BASE + '1.0/codelists/',
                  'files': ['TestADE.EnergyClassValue.xml', 'TestADE.MeterKindValue.xml', 'Building.BuildingClassValue.xml']},
    'codeListBindings': {'tade:BuildingProperties/tade:energyClass': 'EnergyClassValue',
                         'tade:BuildingProperties/tade:ownerType': 'OwnerTypeValue',
                         'tade:MeterType/tade:meterKind': 'MeterKindValue'},
    'topLevel': ['tade:Kiosk']}
INPUTS = ('config', 'sources', 'codelists', 'assets', 'index.html', 'README.md', 'LICENSE-app.txt')
ADE_FOLDER = 'sources/example.org/cg3e/test-ade/1.0/'
WHEN = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
PROFILE = 'http://www.opengis.net/citygml/profiles/base/3.0'
PROFILE_XSD = 'http://schemas.opengis.net/citygml/profiles/base/3.0/CityGML.xsd'


def unzip(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def element(name, namespace=NS):
    return f'xsd:{{{namespace}}}element:{name}'


def offline(*args, **kwargs):
    raise OSError('rete disattivata nel test')


def prepare(root):
    """The project with the Test ADE in root (an empty folder): inputs copied, fetch without network, verify,
    catalog and aligned dictionary. Also used by tests/browser_ade.py."""
    for name in INPUTS:
        (shutil.copytree if (ROOT/name).is_dir() else shutil.copy)(ROOT/name, root/name)
    shutil.copytree(ROOT/'tests/fixtures/ade', root/'ade')
    config = json.loads((root/'config/sources.json').read_text(encoding='utf-8'))
    config['ades'] = [TEST_ADE]
    (root/'config/sources.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    run, output = SimpleNamespace(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        with patch.object(fetch_sources, 'download', offline):
            run.fetch = fetch_sources.run(Namespace(root=root, timeout=1, reuse_local=True))
        run.manifest = json.loads((root/'sources/manifest.json').read_text(encoding='utf-8'))
        try:
            verify_sources.main(['--root', str(root)])
            run.verify = 0
        except SystemExit as exc:
            run.verify = exc.code
        run.catalog = build_catalog.Builder(root).build()
    # --prune: the copied dictionary may hold the lists of an ADE that the project configures and the copy does not
    run.align = subprocess.run([sys.executable, str(ROOT/'scripts/build_codelists.py'), '--root', str(root), '--align', '--prune'],
                               capture_output=True, text=True)
    run.output = output.getvalue()
    return run


class AdeBuildTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.tmp.name)
        run = prepare(root)
        cls.fetch_code, cls.manifest, cls.verify_code, cls.catalog, cls.align, cls.output = (
            run.fetch, run.manifest, run.verify, run.catalog, run.align, run.output)
        cls.inputs = ex.load(root)
        cls.nodes = cls.catalog['nodes']
        cls.real = json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
        cls.city3d = json.loads(ex.export_city3d(cls.inputs, WHEN).data)
        cls.generator_result = ex.export_generator(cls.inputs, WHEN)
        cls.package = unzip(cls.generator_result.data)
        cls.generator = json.loads(cls.package['citygml-generator.json'])
        with zipfile.ZipFile(io.BytesIO(cls.generator_result.data)) as archive:
            archive.extractall(root/'package')
        cls.standard_result = ex.export_standard(cls.inputs, WHEN)
        cls.standard = unzip(cls.standard_result.data)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def prop(self, owner, name):
        return next(p for p in self.nodes[owner]['properties'] if p['name'] == name)

    def test_sources_without_network(self):
        self.assertEqual((self.fetch_code, self.manifest['failures'], self.verify_code), (0, [], 0), self.output)
        local = sorted(r['path'] for r in self.manifest['files'] if r.get('origin') == 'local')
        self.assertEqual(local, [ADE_FOLDER + 'codelists/' + n for n in ('Building.BuildingClassValue.xml', 'TestADE.EnergyClassValue.xml',
                                                                         'TestADE.MeterKindValue.xml')]
                         + [ADE_FOLDER + 'test-ade-meters.xsd', ADE_FOLDER + 'test-ade.xsd'])
        # The other sources are reused as they are: the same records as the project manifest, apart from its ADEs
        project = {r['path']: r for r in json.loads((ROOT/'sources/manifest.json').read_text(encoding='utf-8'))['files']
                   if r.get('origin') != 'local'}
        self.assertEqual({r['path']: r['sha256'] for r in self.manifest['files'] if r.get('origin') != 'local'},
                         {p: r['sha256'] for p, r in project.items()})

    def test_family_module_and_category(self):
        hook = self.nodes[element('BuildingProperties')]
        self.assertEqual((hook['family'], hook['module'], hook['support'], hook['qname'], hook['kind']),
                         ('ADE', 'TestADE', False, 'tade:BuildingProperties', 'datatype'))
        self.assertEqual(hook['substitution'], element('ADEOfAbstractBuilding', 'http://www.opengis.net/citygml/building/3.0'))
        kiosk = self.nodes[element('Kiosk')]
        self.assertEqual((kiosk['kind'], kiosk['cityObject'], kiosk['spaceRole'], kiosk['topLevel']), ('feature', True, 'space', True))
        self.assertIn('xsd:{http://www.opengis.net/citygml/3.0}element:CityModel/property:cityObjectMember',
                      ' '.join(kiosk['cityModelMember']['gml']))
        self.assertEqual(self.nodes[f'xsd:{{{NS}}}type:RefurbishmentKindType']['kind'], 'enumeration')
        self.assertEqual(self.nodes[f'xsd:{{{NS}}}type:MeterType']['family'], 'ADE')
        # Without a configuration the namespace would be a support schema with module "1.0"
        self.assertEqual({n['family'] for n in self.nodes.values() if n.get('namespace') == NS}, {'ADE'})

    def test_code_lists_and_bindings(self):
        lists = {id_: n for id_, n in self.nodes.items() if id_.startswith('ade:')}
        self.assertEqual(sorted(lists), ['ade:TestADE:EnergyClassValue', 'ade:TestADE:MeterKindValue', 'ade:TestADE:OwnerTypeValue'])
        energy = lists['ade:TestADE:EnergyClassValue']
        self.assertEqual((energy['kind'], energy['family'], energy['module'], energy['qname'], energy['description'], energy['source']),
                         ('codelist', 'ADE', 'TestADE', 'tade:EnergyClassValue', 'Energy classes of a building.',
                          [ADE_FOLDER + 'codelists/TestADE.EnergyClassValue.xml']))
        self.assertEqual(lists['ade:TestADE:OwnerTypeValue']['description'], '')
        hook = element('BuildingProperties')
        self.assertEqual(self.prop(hook, 'energyClass')['codeList'], 'ade:TestADE:EnergyClassValue')
        self.assertEqual(self.prop(hook, 'ownerType')['codeList'], 'ade:TestADE:OwnerTypeValue')
        self.assertNotIn('codeList', self.prop(hook, 'heritageType'))
        # A binding on a type shared by two elements holds for its declaration, so for both elements
        for owner in (element('ElectricityMeter'), element('WaterMeter'), f'xsd:{{{NS}}}type:MeterType'):
            self.assertEqual(self.prop(owner, 'meterKind')['codeList'], 'ade:TestADE:MeterKindValue')
        self.assertEqual(sorted({i['source'] for i in self.nodes['ade:TestADE:MeterKindValue']['incoming']}),
                         sorted([element('ElectricityMeter'), element('WaterMeter'), f'xsd:{{{NS}}}type:MeterType']))
        self.assertEqual([w for w in self.catalog['warnings'] if 'ADE' in w],
                         ['ADE TestADE: tade:BuildingProperties/tade:heritageType è gml:CodeType senza code list in codeListBindings.'])

    def test_files_stats_and_ades(self):
        self.assertEqual(sorted(f['path'] for f in self.catalog['files'] if f.get('ade') == 'TestADE'),
                         [ADE_FOLDER + 'test-ade-meters.xsd', ADE_FOLDER + 'test-ade.xsd'])
        stats, real = self.catalog['stats'], self.real['stats']
        self.assertEqual((stats['adeFiles'], stats['citygmlFiles'], stats['dependencyFiles']), (2, real['citygmlFiles'], real['dependencyFiles']))
        schema = next(r for r in self.manifest['files'] if r['path'] == ADE_FOLDER + 'test-ade.xsd')
        self.assertEqual(self.catalog['ades'], [{
            'name': 'TestADE', 'prefix': 'tade', 'namespace': NS,
            'schema': {'url': BASE + '1.0/test-ade.xsd', 'path': ADE_FOLDER + 'test-ade.xsd', 'version': '1.0', 'sha256': schema['sha256']},
            'origin': 'local', 'files': [ADE_FOLDER + 'test-ade-meters.xsd', ADE_FOLDER + 'test-ade.xsd'],
            'codeLists': {'baseUrl': BASE + '1.0/codelists/', 'lists': ['EnergyClassValue', 'MeterKindValue', 'OwnerTypeValue'],
                          'extends': ['Building.BuildingClassValue']},
            'codeListBindings': dict(sorted(TEST_ADE['codeListBindings'].items())), 'topLevel': ['tade:Kiosk']}])

    def test_dictionary_aligned_with_the_ade(self):
        self.assertEqual(self.align.returncode, 0, self.align.stderr)
        for line in ('BuildingClassValue: aggiunte le voci di TestADE (2)', 'aggiunta la code list tade:EnergyClassValue',
                     'aggiunta la code list tade:MeterKindValue', 'aggiunta la code list tade:OwnerTypeValue'):
            self.assertIn(line, self.align.stdout.splitlines())
        lists = self.inputs.dictionary['codeLists']
        energy = lists['tade:EnergyClassValue']
        self.assertEqual((energy['module'], energy['ade'], [v['code'] for v in energy['values']]), ('TestADE', 'TestADE', ['A', 'B']))
        self.assertEqual(lists['tade:OwnerTypeValue']['values'], [])
        # The values of the ADE for a CityGML list follow the SIG3D ones, each with its codeSpace and its ADE
        building = lists['BuildingClassValue']['values']
        project = ex.read_json_assignment((ROOT/'codelists/codelists.js').read_text(encoding='utf-8'), ex.DICTIONARY_VARIABLE)
        self.assertEqual(building[:-2], [v for v in project['codeLists']['BuildingClassValue']['values'] if not v.get('ade')])
        self.assertEqual([(v['code'], v['codeSpace'], v['ade']) for v in building[-2:]],
                         [(c, BASE + '1.0/codelists/Building.BuildingClassValue.xml', 'TestADE') for c in ('T1', 'T2')])

    def test_dictionary_records_of_the_ade(self):
        records = ex.dictionary_records(self.inputs.dictionary)
        energy = records['tade:EnergyClassValue']
        self.assertEqual((energy['id'], energy['module'], ex.file_name(energy, 'xml')), ('EnergyClassValue', 'TestADE', 'TestADE.EnergyClassValue.xml'))
        self.assertEqual(energy['codeSpace'], BASE + '1.0/codelists/TestADE.EnergyClassValue.xml')
        self.assertNotIn('tade:OwnerTypeValue', records)
        self.assertEqual([e['codeSpace'] for e in records['BuildingClassValue']['entries']][-2:],
                         [BASE + '1.0/codelists/Building.BuildingClassValue.xml'] * 2)
        ex.validate_dictionaries(self.inputs, {n: ex.to_gml(r) for n, r in records.items()})
        csv_warning = ('BuildingClassValue: il CSV di Annex E non riporta il codeSpace delle voci di TestADE; il file GML lo conserva.')
        self.assertIn(csv_warning, ex.dictionary_warnings(self.inputs, records, csv=True))
        self.assertNotIn(csv_warning, ex.dictionary_warnings(self.inputs, records))

    def test_elements_and_candidates(self):
        items = {e['qname']: e for e in self.generator['elements']}
        self.assertEqual(sorted(q for q in items if q.startswith('tade:')),
                         ['tade:BuildingProperties', 'tade:Certification', 'tade:ElectricityMeter', 'tade:Kiosk', 'tade:WaterMeter'])
        props = lambda qname: {p['qname']: p for p in items[qname]['properties']}
        self.assertIn('tade:BuildingProperties', props('bldg:Building')['bldg:adeOfAbstractBuilding']['candidates'])
        self.assertIn('tade:Kiosk', props('core:CityModel')['core:cityObjectMember']['candidates'])
        kiosk = items['tade:Kiosk']
        self.assertEqual((kiosk['kind'], kiosk['topLevel'], kiosk['spaceRole']), ('feature', True, 'space'))
        self.assertEqual(props('tade:BuildingProperties')['tade:refurbishment']['type'], 'tade:RefurbishmentKindType')
        # Every CityGML or ADE candidate has its entry in elements; GML and xAL stay external references
        families = {n['qname']: n['family'] for n in self.nodes.values() if '}element:' in n['id']}
        candidates = {c for e in items.values() for p in e['properties'] for c in p['candidates']}
        self.assertEqual({c for c in candidates - set(items) if families.get(c) in ('CityGML', 'ADE')}, set())
        self.assertEqual({families[c] for c in candidates - set(items)}, {'Supporto'})

    def test_code_list_use(self):
        use = self.city3d['codeListUse']
        self.assertEqual(sorted((u['element'], u['property'], u['codeList']) for u in use if u['elementNamespace'] == NS), [
            ('BuildingProperties', 'energyClass', 'tade:EnergyClassValue'), ('BuildingProperties', 'ownerType', 'tade:OwnerTypeValue'),
            ('ElectricityMeter', 'meterKind', 'tade:MeterKindValue'), ('WaterMeter', 'meterKind', 'tade:MeterKindValue')])
        self.assertEqual(len(use), 158 + 4)
        self.assertEqual(self.generator['codeListUse'], use)
        self.assertTrue({u['codeList'] for u in use} <= set(self.city3d['codeLists']))
        energy = self.city3d['codeLists']['tade:EnergyClassValue']
        self.assertEqual((energy['module'], energy['state'], energy['exportedValues'], energy['Dictionary']['@id']),
                         ('TestADE', 'values', 2, 'EnergyClassValue'))
        self.assertEqual(self.city3d['codeLists']['tade:OwnerTypeValue'], {'module': 'TestADE', 'state': 'empty', 'exportedValues': 0})

    def test_header_and_rules(self):
        schema = next(r for r in self.manifest['files'] if r['path'] == ADE_FOLDER + 'test-ade.xsd')
        expected = [{'name': 'TestADE', 'prefix': 'tade', 'namespace': NS, 'version': '1.0', 'url': BASE + '1.0/test-ade.xsd',
                     'sha256': schema['sha256'], 'origin': 'local'}]
        self.assertEqual((self.city3d['ades'], self.generator['ades']), (expected, expected))
        top = self.generator['rules']['topLevel']
        self.assertIn({'element': 'tade:Kiosk', 'namespace': NS, 'source': {'ade': 'TestADE', 'configuration': 'config/sources.json'}}, top)
        self.assertEqual(len(top), 21)

    def test_generator_package(self):
        package = self.package
        self.assertEqual(sorted(n for n in package if n.startswith('schemas/example.org/')),
                         ['schemas/' + ADE_FOLDER.removeprefix('sources/') + n for n in ('test-ade-meters.xsd', 'test-ade.xsd')])
        self.assertEqual(len([n for n in package if n.startswith('schemas/') and n.endswith('.xsd')]), 78 + 2)
        # Only the folder of the ADE schemas is rewritten, not the whole host
        catalog = package['xml-catalog.xml'].decode('utf-8')
        self.assertIn('uriStartString="https://example.org/cg3e/test-ade/1.0/" rewritePrefix="schemas/example.org/cg3e/test-ade/1.0/"', catalog)
        self.assertNotIn('"http://example.org/"', catalog)
        self.assertTrue({'codelists/TestADE.EnergyClassValue.xml', 'codelists/TestADE.EnergyClassValue.json',
                         'codelists/TestADE.MeterKindValue.xml'} <= set(package))
        driver = ET.fromstring(package['CityGML-ADE.xsd'])
        self.assertEqual([(i.get('namespace'), i.get('schemaLocation')) for i in driver.iter('{http://www.w3.org/2001/XMLSchema}import')],
                         [(PROFILE, PROFILE_XSD), (NS, BASE + '1.0/test-ade.xsd')])
        readme = package['README.md'].decode('utf-8')
        for text in ('--schema CityGML-ADE.xsd', "| `schemas/example.org/cg3e/test-ade/1.0/` | XSD dell'ADE TestADE, invariati | XSD |",
                     '- ADE TestADE: versione 1.0, schema `https://example.org/cg3e/test-ade/1.0/test-ade.xsd`, non pubblicata: copia locale'):
            self.assertIn(text, readme)
        self.assertIn('78 XSD ufficiali', readme)
        self.assertEqual(ex.export_generator(self.inputs, WHEN).data, self.generator_result.data)

    def test_example_validates_offline_with_the_driver(self):
        folder = self.root/'package'
        catalog = ex.XmlCatalog(folder/'xml-catalog.xml')
        parser = ET.XMLParser(no_network=True, resolve_entities=False)
        parser.resolvers.add(catalog)
        driver = ET.XMLSchema(ET.parse(str(folder/'CityGML-ADE.xsd'), parser))
        example = ET.parse(str(ROOT/'tests/fixtures/ade/example.gml'))
        self.assertTrue(driver.validate(example), driver.error_log)
        self.assertEqual(catalog.unresolved, [])
        # With CityGML.xsd alone the elements of the ADE are not expected
        citygml = ex.compile_schema(folder/'xml-catalog.xml', [(PROFILE, PROFILE_XSD)])
        self.assertFalse(citygml.validate(example))
        self.assertIn('Kiosk', str(citygml.error_log.last_error))

    def test_standard_package(self):
        files = self.standard
        self.assertTrue({ADE_FOLDER + 'test-ade.xsd', ADE_FOLDER + 'codelists/TestADE.EnergyClassValue.xml',
                         'dictionaries/TestADE.EnergyClassValue.xml', 'dictionaries/TestADE.EnergyClassValue.csv'} <= set(files))
        readme = files['EXPORT.md'].decode('utf-8')
        self.assertIn('| ADE TestADE | versione 1.0, schema `https://example.org/cg3e/test-ade/1.0/test-ade.xsd`, non pubblicata', readme)
        self.assertIn('gli esempi OGC e i dizionari delle ADE', readme)
        self.assertIn('BuildingClassValue: il CSV di Annex E non riporta il codeSpace delle voci di TestADE; il file GML lo conserva.',
                      self.standard_result.warnings)

    def test_citygml_part_unchanged(self):
        citygml = lambda catalog: sorted(i for i, n in catalog['nodes'].items() if n['family'] == 'CityGML')
        self.assertEqual(citygml(self.catalog), citygml(self.real))
        # An ADE space has no boundary table in OGC 20-010 and is not reported as missing one
        self.assertEqual(self.catalog['standard']['report'].get('spacesWithoutBoundaryTable'), [])
        self.assertEqual([w for w in self.catalog['warnings'] if 'ADE' not in w], self.real['warnings'])


if __name__ == '__main__':
    unittest.main()
