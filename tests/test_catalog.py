"""Catalog and sources tests; run: python -m unittest discover -s tests -v"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from build_catalog import Builder, xid

BLDG = 'http://www.opengis.net/citygml/building/3.0'
CON = 'http://www.opengis.net/citygml/construction/3.0'
CORE = 'http://www.opengis.net/citygml/3.0'
TRAN = 'http://www.opengis.net/citygml/transportation/3.0'


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
        cls.manifest = json.loads((ROOT/'sources/manifest.json').read_text(encoding='utf-8'))

    def test_all_citygml_modules_present(self):
        citygml = [f for f in self.data['files'] if f['citygml']]
        self.assertEqual(len(citygml), 22)
        self.assertEqual({f['schemaVersion'] for f in citygml if 'opengis.net/citygml' in f['namespace']}, {'3.0.0'})

    def test_every_import_is_local(self):
        self.assertEqual(self.data['stats']['missingDependencies'], 0)
        self.assertEqual(self.data['stats']['external'], 0)
        self.assertTrue(all(d['status'] == 'local' for d in self.data['dependencies']))

    def test_files_match_manifest(self):
        records = {f['path']: f for f in self.manifest['files']}
        for f in self.data['files']:
            self.assertIn(f['path'], records)
            self.assertEqual(f['sha256'], records[f['path']]['sha256'])
            self.assertEqual(f['sha256'], hashlib.sha256((ROOT/f['path']).read_bytes()).hexdigest())
            self.assertTrue(f['url'].startswith('http://'))
            self.assertTrue(f['retrievedAt'])

    def test_building(self):
        b = self.data['nodes'][xid(BLDG, 'Building')]
        self.assertEqual(b['parents'], [xid(BLDG, 'AbstractBuilding')])
        self.assertEqual({p['name'] for p in b['properties']}, {'buildingPart', 'adeOfBuilding'})
        p = next(p for p in b['properties'] if p['name'] == 'buildingPart')
        self.assertEqual(p['multiplicity'], '0..*')
        self.assertIn(xid(BLDG, 'BuildingPart'), p['targets'])

    def inherited(self, node_id):
        nodes, result = self.data['nodes'], {}
        for id_ in [node_id] + nodes[node_id]['ancestors']:
            for p in nodes[id_]['properties']:
                result.setdefault(p['name'], p)
        return result

    def test_categories_from_hierarchy(self):
        nodes = self.data['nodes']
        expected = {xid(BLDG, 'Building'): 'feature', xid(CORE, 'Address'): 'feature',
                    xid(CORE, 'ImplicitGeometry'): 'object', xid(CORE, 'CityObjectRelation'): 'object',
                    xid(CON, 'Height'): 'datatype', xid(CORE, 'Occupancy'): 'datatype',
                    xid('http://www.opengis.net/gml/3.2', 'name'): 'datatype'}
        for id_, kind in expected.items():
            self.assertEqual(nodes[id_]['kind'], kind, id_)
        citygml = [n for n in nodes.values() if n['family'] == 'CityGML']
        self.assertEqual(sum(n['kind'] == 'feature' for n in citygml), 114)
        self.assertEqual(sum(n['kind'] == 'object' for n in citygml), 4)
        self.assertEqual(sum(n['kind'] == 'enumeration' for n in citygml), 13)

    def test_spaces_and_boundaries(self):
        nodes = self.data['nodes']
        concrete = [n for n in nodes.values() if n['cityObject'] and not n['abstract']]
        self.assertEqual(len(concrete), 66)
        self.assertEqual(sum(n['spaceRole'] == 'space' for n in concrete), 42)
        self.assertEqual(sum(n['spaceRole'] == 'boundary' for n in concrete), 24)
        self.assertEqual(nodes[xid(BLDG, 'Building')]['spaceRole'], 'space')
        self.assertEqual(nodes[xid(CON, 'RoofSurface')]['spaceRole'], 'boundary')
        self.assertFalse(nodes[xid(CORE, 'Address')]['cityObject'])

    def test_relations_and_link_forms(self):
        props = self.inherited(xid(BLDG, 'Building'))
        relations = {name for name, p in props.items() if p['kind'] == 'association'}
        self.assertEqual(relations, {'buildingPart', 'buildingConstructiveElement', 'buildingInstallation',
                                     'buildingRoom', 'buildingFurniture', 'buildingSubdivision', 'address',
                                     'pointCloud', 'boundary', 'generalizesTo', 'relatedTo', 'appearance', 'dynamizer'})
        for name in ('height', 'occupancy', 'area', 'externalReference', 'genericAttribute', 'name', 'boundedBy'):
            self.assertEqual(props[name]['kind'], 'attribute', name)
            self.assertIsNone(props[name]['link'], name)
        self.assertEqual(props['buildingPart']['link'], 'aggregation')
        self.assertEqual(props['boundary']['link'], 'association')
        self.assertEqual(props['generalizesTo']['link'], 'reference')
        traffic = self.inherited(xid(TRAN, 'TrafficSpace'))
        self.assertEqual(traffic['predecessor']['link'], 'reference')
        self.assertEqual(traffic['clearanceSpace']['link'], 'aggregation')

    def test_all_references_resolved_as_nodes(self):
        nodes = self.data['nodes']
        for node in nodes.values():
            for ref in node['parents']+node['children']+node['ancestors']:
                self.assertIn(ref, nodes)
            for prop in node['properties']:
                self.assertIn(prop['declaredIn'], nodes)
                for ref in prop['targets']:
                    self.assertIn(ref, nodes)

    def test_catalog_js_matches_json(self):
        js = (ROOT/'data/catalog.js').read_text(encoding='utf-8')
        payload = js.split('window.CITYGML_CATALOG = ', 1)[1].rstrip().rstrip(';')
        self.assertEqual(json.loads(payload), self.data)


class SyntheticBuildTests(unittest.TestCase):
    def test_import_resolution_uses_manifest_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root/'sources/example.org/schema'
            folder.mkdir(parents=True)
            main = folder/'main.xsd'
            main.write_text('<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:city">'
                            '<xs:import namespace="urn:part" schemaLocation="part.xsd"/>'
                            '<xs:import namespace="urn:absent" schemaLocation="http://example.org/absent.xsd"/>'
                            '<xs:element name="Building" type="xs:string"/></xs:schema>')
            part = folder/'part.xsd'
            part.write_text('<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:part">'
                            '<xs:element name="Part" type="xs:string"/></xs:schema>')
            records = [{'path': p.relative_to(root).as_posix(), 'url': 'http://example.org/schema/'+p.name,
                        'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'retrievedAt': '2026-01-01T00:00:00+00:00'}
                       for p in (main, part)]
            (root/'sources/manifest.json').write_text(json.dumps({'files': records}))
            data = Builder(root).build()
            status = {d['url']: d['status'] for d in data['dependencies']}
            self.assertEqual(status['http://example.org/schema/part.xsd'], 'local')
            self.assertEqual(status['http://example.org/absent.xsd'], 'missing')
            self.assertEqual(data['stats']['missingDependencies'], 1)
            self.assertEqual(data['warnings'], [])


if __name__ == '__main__':
    unittest.main()
