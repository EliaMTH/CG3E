"""Regression and isolation tests; run: python -m unittest discover -s tests -v"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_catalog import Builder,xid,oid,XS,GML
from download_dependencies import cache_path


class ModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.xsd=json.loads((ROOT/'data/catalog-citygml.json').read_text())
        cls.full=json.loads((ROOT/'data/catalog-full.json').read_text())
        cls.building=xid('http://www.opengis.net/citygml/building/3.0','Building')

    def test_originals_unmodified(self):
        import zipfile
        with zipfile.ZipFile('/mnt/data/voc.zip') if Path('/mnt/data/voc.zip').exists() else DummyZip() as orig:
            manifest=json.loads((ROOT/'sources/original-manifest.json').read_text())
            self.assertEqual(len(manifest['files']),25)
            for record in manifest['files']:
                path=ROOT/record['path']
                self.assertTrue(path.exists())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),record['sha256'])
                if isinstance(orig,zipfile.ZipFile):self.assertEqual(path.read_bytes(),orig.read(path.name))

    def test_cgml_only_has_no_owl(self):
        self.assertEqual(self.xsd['mode'],'citygml')
        self.assertTrue(all(n['format'] == 'XSD' for n in self.xsd['nodes'].values()))
        self.assertTrue(all(f['format'] == 'XSD' for f in self.xsd['files']))
        self.assertTrue(all(d['kind'].startswith('xsd:') for d in self.xsd['dependencies']))
        self.assertTrue(all(not n['bridges'] for n in self.xsd['nodes'].values()))
        self.assertEqual(len(self.xsd['files']),22)
        self.assertEqual(self.xsd['stats']['missingDependencies'],2)

    def test_full_has_owl_and_bridges(self):
        self.assertEqual(self.full['mode'],'full')
        self.assertEqual(len(self.full['files']),25)
        self.assertIn(oid('http://uish/ontology#BuildingQuality'),self.full['nodes'])
        self.assertTrue(self.full['nodes'][xid('http://www.opengis.net/citygml/building/3.0','ADEOfBuilding')]['bridges'])
        self.assertFalse(self.xsd['nodes'][xid('http://www.opengis.net/citygml/building/3.0','ADEOfBuilding')]['bridges'])

    def test_building_in_both(self):
        for data in (self.xsd,self.full):
            b=data['nodes'][self.building]
            self.assertEqual(b['parents'],[xid('http://www.opengis.net/citygml/building/3.0','AbstractBuilding')])
            self.assertEqual({p['name'] for p in b['properties']},{'buildingPart','adeOfBuilding'})
            p=next(p for p in b['properties'] if p['name']=='buildingPart')
            self.assertEqual(p['multiplicity'],'0..*')
            self.assertIn(xid('http://www.opengis.net/citygml/building/3.0','BuildingPart'),p['targets'])

    def test_all_references_resolved_as_nodes(self):
        for data in (self.xsd,self.full):
            nodes=data['nodes']
            for node in nodes.values():
                for ref in node['parents']+node['children']+node['ancestors']:
                    self.assertIn(ref,nodes)
                for prop in node['properties']:
                    self.assertIn(prop['declaredIn'],nodes)
                    for ref in prop['targets']:self.assertIn(ref,nodes)
                for bridge in node['bridges']:self.assertIn(bridge['target'],nodes)

    def test_modes_written_to_distinct_download_folders(self):
        a=cache_path(ROOT,'https://schemas.opengis.net/gml/3.2.1/gml.xsd','.xsd',kind='XSD')
        b=cache_path(ROOT,'https://www.w3.org/ns/ssn/obs/','.ttl',kind='OWL')
        self.assertTrue(a.is_relative_to(ROOT/'sources/dependencies/citygml'))
        self.assertTrue(b.is_relative_to(ROOT/'sources/dependencies/owl'))


class DummyZip:
    def __enter__(self):return self
    def __exit__(self,*args):pass

class SyntheticModeTests(unittest.TestCase):
    def test_loader_isolation_with_both_dependency_directories_populated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            orig=root/'sources/original-voc';orig.mkdir(parents=True)
            xc=root/'sources/dependencies/citygml';xc.mkdir(parents=True)
            ow=root/'sources/dependencies/owl';ow.mkdir(parents=True)
            (orig/'sample.xsd').write_text('''<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:city"><xs:element name="Building" type="xs:string"/></xs:schema>''')
            (xc/'tech.xsd').write_text('''<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:technical"><xs:element name="Point" type="xs:string"/></xs:schema>''')
            (orig/'test.owl').write_text('''<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:owl="http://www.w3.org/2002/07/owl#"><owl:Ontology rdf:about="urn:base"/><owl:Class rdf:about="urn:base#Quality"/></rdf:RDF>''')
            (ow/'other.ttl').write_text('@prefix owl: <http://www.w3.org/2002/07/owl#> . <urn:extra> a owl:Ontology . <urn:extra#M> a owl:Class .')
            (root/'config').mkdir();(root/'config/navigation-bridges.json').write_text('{"bridges":[]}')
            only=Builder(root,mode='citygml').build()
            self.assertEqual(len(only['files']),2)
            self.assertTrue(all(n['format']=='XSD' for n in only['nodes'].values()))
            full=Builder(root,mode='full').build()
            self.assertEqual(len(full['files']),4)
            self.assertIn(oid('urn:extra#M'),full['nodes'])
            self.assertEqual(json.loads((root/'data/catalog.json').read_text())['mode'],'full')


if __name__=='__main__':unittest.main()
