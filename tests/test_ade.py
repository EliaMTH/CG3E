"""An ADE from config/sources.json to the catalog, on the real sources/ and on the Test ADE of
tests/fixtures/ade (written after the cases of the Test ADE of OGC 21-006r2, Annex B).

The project inputs are copied into a temporary folder. fetch_sources.py runs with the network
disabled: it reuses sources/ and reads the ADE from its local folder.
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import build_catalog
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


def element(name, namespace=NS):
    return f'xsd:{{{namespace}}}element:{name}'


def offline(*args, **kwargs):
    raise OSError('rete disattivata nel test')


class AdeBuildTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.tmp.name)
        for name in INPUTS:
            (shutil.copytree if (ROOT/name).is_dir() else shutil.copy)(ROOT/name, root/name)
        shutil.copytree(ROOT/'tests/fixtures/ade', root/'ade')
        config = json.loads((root/'config/sources.json').read_text(encoding='utf-8'))
        config['ades'] = [TEST_ADE]
        (root/'config/sources.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
        cls.output = io.StringIO()
        with contextlib.redirect_stdout(cls.output), contextlib.redirect_stderr(cls.output):
            with patch.object(fetch_sources, 'download', offline):
                cls.fetch_code = fetch_sources.run(Namespace(root=root, timeout=1, reuse_local=True))
            cls.manifest = json.loads((root/'sources/manifest.json').read_text(encoding='utf-8'))
            try:
                verify_sources.main(['--root', str(root)])
                cls.verify_code = 0
            except SystemExit as exc:
                cls.verify_code = exc.code
            cls.catalog = build_catalog.Builder(root).build()
        cls.nodes = cls.catalog['nodes']
        cls.real = json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def prop(self, owner, name):
        return next(p for p in self.nodes[owner]['properties'] if p['name'] == name)

    def test_sources_without_network(self):
        self.assertEqual((self.fetch_code, self.manifest['failures'], self.verify_code), (0, [], 0), self.output.getvalue())
        local = sorted(r['path'] for r in self.manifest['files'] if r.get('origin') == 'local')
        self.assertEqual(local, [ADE_FOLDER + 'codelists/' + n for n in ('Building.BuildingClassValue.xml', 'TestADE.EnergyClassValue.xml',
                                                                         'TestADE.MeterKindValue.xml')]
                         + [ADE_FOLDER + 'test-ade-meters.xsd', ADE_FOLDER + 'test-ade.xsd'])
        # The other sources are reused as they are: the same records as the project manifest
        project = {r['path']: r for r in json.loads((ROOT/'sources/manifest.json').read_text(encoding='utf-8'))['files']}
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

    def test_citygml_part_unchanged(self):
        citygml = lambda catalog: sorted(i for i, n in catalog['nodes'].items() if n['family'] == 'CityGML')
        self.assertEqual(citygml(self.catalog), citygml(self.real))
        # An ADE space has no boundary table in OGC 20-010 and is not reported as missing one
        self.assertEqual(self.catalog['standard']['report'].get('spacesWithoutBoundaryTable'), [])
        self.assertEqual([w for w in self.catalog['warnings'] if 'ADE' not in w], self.real['warnings'])


if __name__ == '__main__':
    unittest.main()
