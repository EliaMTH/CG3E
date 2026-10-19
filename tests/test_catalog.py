"""Catalog and sources tests; run: python -m unittest discover -s tests -v"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from build_catalog import Builder, coverage, xid

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

    def by_name(self, name):
        return next(n for n in self.data['nodes'].values() if n['name'] == name and n['family'] == 'CityGML')

    def names(self, ids):
        return {self.data['nodes'][i]['name'] for i in ids}

    def test_conceptual_model_classes(self):
        nodes = self.data['nodes']
        top = {n['name'] for n in nodes.values() if n.get('topLevel')}
        self.assertEqual(top, {'Bridge', 'Building', 'CityFurniture', 'CityObjectGroup', 'GenericLogicalSpace',
                               'GenericOccupiedSpace', 'GenericThematicSurface', 'GenericUnoccupiedSpace', 'LandUse',
                               'OtherConstruction', 'PlantCover', 'Railway', 'ReliefFeature', 'Road',
                               'SolitaryVegetationObject', 'Square', 'Track', 'Tunnel', 'WaterBody', 'Waterway'})
        self.assertEqual(sum(n['kind'] == 'codelist' for n in nodes.values()), 140)
        roof = self.inherited(xid(BLDG, 'Building'))['roofType']
        self.assertEqual(roof['umlType'], 'RoofTypeValue')
        self.assertEqual(nodes[roof['codeList']]['name'], 'RoofTypeValue')
        self.assertIn('roof types', nodes[roof['codeList']]['description'])
        enum = nodes[xid(CORE, 'RelativeToTerrainType', 'type')]
        self.assertEqual(enum['uml']['name'], 'RelativeToTerrain')
        self.assertEqual(len(enum['literals']), 5)

    def test_allowed_boundaries(self):
        building = self.by_name('Building')['allowedBoundaries']
        self.assertEqual(self.names(building['concrete']), {'CeilingSurface', 'ClosureSurface', 'FloorSurface',
                         'GenericThematicSurface', 'GroundSurface', 'InteriorWallSurface', 'OuterCeilingSurface',
                         'OuterFloorSurface', 'RoofSurface', 'WallSurface'})
        self.assertTrue(building['ade'])
        self.assertEqual((building['table'], building['requirement']), ('Table 65', '/req/building/boundaries'))
        self.assertEqual(self.names(self.by_name('BuildingUnit')['allowedBoundaries']['concrete']),
                         {'ClosureSurface', 'GenericThematicSurface'})
        self.assertTrue(self.by_name('PlantCover')['allowedBoundaries']['none'])
        self.assertEqual(self.names(self.by_name('TrafficArea')['boundaryOf']), {'TrafficSpace'})
        self.assertNotIn('TrafficArea', self.names(building['concrete']))

    def test_aggregation_kinds_from_uml(self):
        self.assertEqual(self.inherited(xid(BLDG, 'Building'))['buildingPart']['aggregation'], 'composite')
        self.assertEqual(self.inherited(xid(TRAN, 'Road'))['section']['aggregation'], 'shared')
        self.assertEqual(self.inherited(xid(BLDG, 'Building'))['boundary']['aggregation'], 'none')

    def test_standard_sources_and_report(self):
        standard = self.data['standard']
        self.assertEqual(standard['document']['documentNumber'], '20-010')
        self.assertEqual(standard['document']['version'], '3.0.0')
        self.assertEqual(sum(r['kind'] == 'Requirement' for r in standard['requirements']), 50)
        self.assertEqual(sum(r['kind'] == 'Requirements class' for r in standard['requirements']), 18)
        self.assertEqual(standard['report']['xsdWithoutUml'], ['CodeListMetaData'])
        self.assertEqual(standard['report']['spacesWithoutBoundaryTable'], [])
        self.assertIn('Building', standard['modules'])
        self.assertTrue(any(c['title'] == 'Spaces and Space Boundaries' for c in standard['concepts']))

    def test_conceptual_hierarchy(self):
        nodes = self.data['nodes']
        uml = lambda id_: nodes[id_]['uml']['name']
        # Generalizations of the data dictionary that the schemas do not express with xs:extension.
        extra = {(n['uml']['name'], uml(p)) for n in nodes.values() if n.get('uml')
                 for p in n['uml']['parents'] if p not in n['ancestors']}
        self.assertEqual(extra, {('MeasureOrNilReasonList', 'DoubleOrNilReasonList'),
                                 ('TransformationMatrix2×2', 'DoubleList'), ('TransformationMatrix3×4', 'DoubleList'),
                                 ('TransformationMatrix4×4', 'DoubleList'), ('Color', 'DoubleBetween0and1List'),
                                 ('ColorPlusOpacity', 'DoubleBetween0and1List'), ('OtherRelationTypeValue', 'RelationTypeValue'),
                                 ('TemporalRelationTypeValue', 'RelationTypeValue'), ('TopologicalRelationTypeValue', 'RelationTypeValue')})
        for n in nodes.values():
            if n.get('uml'):
                self.assertNotIn(n['id'], n['uml']['parents'])
                for parent in n['uml']['parents']:
                    self.assertIn(n['id'], nodes[parent]['uml']['children'])
        self.assertEqual([uml(a) for a in self.by_name('MeasureOrNilReasonList')['uml']['ancestors']], ['DoubleOrNilReasonList'])
        self.assertEqual(self.by_name('AbstractFeature')['uml']['unresolvedParents'], ['AnyFeature'])
        self.assertEqual([uml(a) for a in self.by_name('Building')['uml']['ancestors']][:2], ['AbstractBuilding', 'AbstractConstruction'])
        self.assertEqual(self.data['warnings'], [])

    def test_conceptual_members(self):
        members = lambda name: {m['name']: m for m in self.by_name(name)['uml']['properties']}
        expected = {'CityModelMember': {'appearanceMember', 'cityObjectMember', 'featureMember', 'versionMember', 'versionTransitionMember'},
                    'Code': {'codeSpace'}, 'DoubleBetween0and1List': {'list'}, 'DoubleList': {'list'},
                    'DoubleOrNilReason': {'nilReason', 'value'}, 'DoubleOrNilReasonList': {'list'},
                    'MeasureOrNilReasonList': {'uom'}, 'NilReason': {'nilReasonEnumeration', 'URI'}}
        for name, names in expected.items():
            self.assertEqual(set(members(name)), names, name)
        nil = members('NilReason')
        self.assertEqual(nil['nilReasonEnumeration']['typeId'], self.by_name('NilReasonEnumeration')['id'])
        self.assertEqual((nil['URI']['type'], nil['URI']['typeId']), ('URI', None))
        self.assertIn(('NilReason', 'nilReasonEnumeration', 'umlMember'),
                      {(self.data['nodes'][i['source']]['name'], i['property'], i['kind']) for i in self.by_name('NilReasonEnumeration')['incoming']})
        part = members('Building')['buildingPart']
        self.assertEqual((part['multiplicity'], part['aggregation']), ('1..*', 'composite'))
        self.assertEqual(part['xsd'], next(p['id'] for p in self.by_name('Building')['properties'] if p['name'] == 'buildingPart'))
        self.assertTrue(part['id'].endswith('/uml:buildingPart'))

    def test_conceptual_constraints(self):
        nodes = self.data['nodes']
        rows = [(n['uml']['name'], c['name']) for n in nodes.values() if n.get('uml') for c in n['uml']['constraints']]
        self.assertEqual(len(rows), 12)
        for row in [('PointCloud', 'inlineOrExternalPointCloud'), ('TimeValuePair', 'singleValue'),
                    ('GenericTimeseries', 'dataTypeOfValue'), ('TabulatedFileTimeseries', 'columnNumberOrColumnName'),
                    ('AbstractReliefComponent', 'polygonGeometry')]:
            self.assertIn(row, rows)
        timeseries = self.by_name('GenericTimeseries')['uml']['constraints'][0]
        self.assertIn('then\nTimeValuePair->forAll', timeseries['text'])
        self.assertEqual(timeseries['table'], 'Table 283')
        color = self.by_name('ColorType')
        self.assertEqual(color['uml']['constraints'][0]['text'], 'inv: list->size() = 3')
        self.assertIn({'kind': 'length', 'value': '3', 'description': ''}, color['constraints'])

    def test_descriptions_from_data_dictionary(self):
        nodes = self.data['nodes']
        filled = {(n['name'], p['name']) for n in nodes.values() for p in n['properties'] if p.get('descriptionSource') == 'uml'}
        self.assertEqual(filled, {('AbstractCityObject', 'relatedTo'), ('CityObjectRelation', 'relationType'),
                                  ('CityObjectGroup', 'groupMember'), ('Role', 'role')})
        role = next(p for p in self.by_name('Role')['properties'] if p['name'] == 'role')
        self.assertEqual(role['description'], 'Describes the role the city object plays within the CityObjectGroup.')
        roof = self.inherited(xid(BLDG, 'Building'))['roofType']
        self.assertNotIn('descriptionSource', roof)
        self.assertTrue(roof['description'])

    def test_encoding_forms(self):
        nodes = self.data['nodes']
        forms = {(n['name'], p['name']): (p['encoding']['allowsInline'], p['encoding']['allowsReference'])
                 for n in nodes.values() if n['family'] == 'CityGML' and not n['technical'] for p in n['properties'] if 'encoding' in p}
        # The properties named by the /reference requirements of OGC 21-006r2, derived here from the schemas alone.
        self.assertEqual({k for k, v in forms.items() if v == (False, True)}, {
            ('AbstractCityObject', 'generalizesTo'), ('CityObjectRelation', 'relatedTo'), ('CityObjectGroup', 'parent'),
            ('Role', 'groupMember'), ('SensorConnection', 'sensorLocation'), ('TrafficSpace', 'predecessor'),
            ('TrafficSpace', 'successor'), ('VersionTransition', 'from'), ('VersionTransition', 'to'),
            ('Transaction', 'oldFeature'), ('Transaction', 'newFeature'), ('Version', 'versionMember')})
        self.assertEqual({k for k, v in forms.items() if v == (True, False)}, {
            ('AbstractCityObject', 'relatedTo'), ('ParameterizedTexture', 'textureParameterization'), ('CityObjectGroup', 'groupMember')})
        self.assertEqual(forms[('Building', 'buildingPart')], (True, True))
        self.assertNotIn(None, {x for v in forms.values() for x in v})
        version = next(p for p in self.by_name('Version')['properties'] if p['name'] == 'versionMember')
        self.assertEqual((version['link'], version['aggregation']), ('aggregation', 'shared'))
        self.assertFalse(any(p['typeName'] == '(inline/ref)' for n in nodes.values() for p in n['properties']))

    def test_nested_simple_lists(self):
        nodes = self.data['nodes']
        for name, item, facets in [('ColorType', 'DoubleBetween0and1Type', ['length']),
                                   ('ColorPlusOpacityType', 'DoubleBetween0and1Type', ['minLength', 'maxLength']),
                                   ('TransformationMatrix2x2Type', 'double', ['length']),
                                   ('TransformationMatrix3x4Type', 'double', ['length']),
                                   ('TransformationMatrix4x4Type', 'double', ['length'])]:
            constraints = self.by_name(name)['constraints']
            lists = [c for c in constraints if c['kind'] == 'xs:list']
            self.assertEqual([[nodes[t]['name'] for t in c['targets']] for c in lists], [[item]], name)
            self.assertEqual([c['kind'] for c in constraints if c['kind'] != 'xs:list'], facets, name)

    def test_coverage_of_the_data_dictionary(self):
        cov = self.data['standard']['coverage']
        self.assertEqual({k: (v['total'], v['represented'], len(v['excluded']), len(v['findings'])) for k, v in cov.items() if k != 'documents'},
                         {'classes': (426, 426, 14, 0), 'members': (552, 552, 0, 0), 'generalizations': (123, 122, 1, 0),
                          'constraints': (12, 12, 3, 0), 'simpleTypes': (5, 5, 0, 0)})
        members = cov['members']['xsd']
        self.assertEqual({k: len(v) for k, v in members.items()},
                         {'sameName': 518, 'inherited': 16, 'unionAlternatives': 1, 'classWithoutXsdType': 14, 'none': 3})
        self.assertEqual(members['none'], ['AbstractFeature.featureID', 'ImplicitGeometry.objectID', 'TexCoordGen.crs'])
        self.assertEqual(members['unionAlternatives'], ['CityModel.cityModelMember'])
        self.assertIn('BuildingRoom.boundary', members['inherited'])
        self.assertEqual({k: len(v) for k, v in cov['generalizations']['xsd'].items()}, {'xsExtension': 113, 'umlOnly': 9})
        self.assertEqual(cov['generalizations']['excluded'][0]['declaration'], 'AbstractFeature → AnyFeature')
        report = self.data['standard']['report']
        self.assertEqual(report['propertiesMappedToUnion'], ['CityModel.cityObjectMember', 'CityModel.appearanceMember',
                         'CityModel.versionMember', 'CityModel.versionTransitionMember', 'CityModel.featureMember'])
        self.assertEqual(len(report['propertiesWithoutUml']), 7)
        member = next(p for p in self.by_name('CityModel')['properties'] if p['name'] == 'cityObjectMember')
        self.assertEqual((member['umlType'], member['aggregation']), ('AbstractCityObject', 'composite'))
        self.assertTrue(member['umlMember'].endswith('/uml:cityModelMember'))
        room = next(m for m in self.by_name('BuildingRoom')['uml']['properties'] if m['name'] == 'boundary')
        self.assertEqual(room['xsdMapping']['rule'], 'inherited')
        self.assertEqual(self.data['nodes'][room['xsdMapping']['properties'][0].split('/property:')[0]]['name'], 'AbstractSpace')

    def test_gml_encoding_rules(self):
        standard = self.data['standard']
        encoding = standard['encoding']
        self.assertEqual((standard['document']['documentNumber'], encoding['document']['documentNumber']), ('20-010', '21-006r2'))
        kinds = [r['kind'] for r in encoding['requirements']]
        self.assertEqual({k: kinds.count(k) for k in set(kinds)}, {'Requirement': 43, 'Recommendation': 4, 'Requirements class': 18})
        self.assertEqual(encoding['unrecognized'], [])
        # Short identifiers repeat across the two parts: each rule keeps its document.
        self.assertIn('/req/building/boundaries', {r['id'] for r in standard['requirements']} & {r['id'] for r in encoding['requirements']})
        self.assertEqual({r['document'] for r in standard['requirements']}, {'20-010'})
        self.assertEqual({r['document'] for r in encoding['requirements']}, {'21-006r2'})
        rules = {r['id']: r for r in encoding['requirements']}
        self.assertEqual([p['label'] for p in rules['/req/global/alternativeaggregations']['parts']], ['A', 'B'])
        self.assertEqual(rules['http://www.opengis.net/spec/CityGML-2/3.0/req/core']['dependencies'],
                         ['core.xsd', 'http://www.opengis.net/spec/CityGML-1/3.0/req/req-class-core'])
        # The properties that the schemas allow only by reference are those named by the /reference rules.
        nodes = self.data['nodes']
        reference_only = {(n['name'], p['name']) for n in nodes.values() if n['family'] == 'CityGML' and not n['technical']
                          for p in n['properties'] if p.get('encoding') == {'allowsInline': False, 'allowsReference': True}}
        named = {(n['name'], p['name']) for n in nodes.values() for p in n['properties']
                 if any(r['id'].endswith('/reference') for r in p.get('rules', []))}
        self.assertEqual(reference_only, named)
        version = next(p for p in self.by_name('Version')['properties'] if p['name'] == 'versionMember')
        self.assertEqual(version['rules'], [{'document': '21-006r2', 'id': '/req/versioning/reference', 'part': 'E',
                                             'anchor': 'req_versioning_reference'}])
        documents = standard['coverage']['documents']
        self.assertEqual([(d['document'], d['acquired']) for d in documents], [('20-010', True), ('21-006r2', True)])
        self.assertEqual((documents[1]['linkedProperties'], documents[1]['unresolvedMentions'], documents[1]['unrecognizedTables']),
                         (15, [], []))

    def test_all_references_resolved_as_nodes(self):
        nodes = self.data['nodes']
        for node in nodes.values():
            for ref in node['parents']+node['children']+node['ancestors']:
                self.assertIn(ref, nodes)
            for prop in node['properties']:
                self.assertIn(prop['declaredIn'], nodes)
                for ref in prop['targets']:
                    self.assertIn(ref, nodes)
            uml = node.get('uml') or {}
            for ref in uml.get('parents', []) + uml.get('children', []) + uml.get('ancestors', []):
                self.assertIn(ref, nodes)
            for member in uml.get('properties', []):
                self.assertTrue(member['typeId'] is None or member['typeId'] in nodes)
            for incoming in node['incoming']:
                self.assertIn(incoming['source'], nodes)

    def test_catalog_js_matches_json(self):
        js = (ROOT/'data/catalog.js').read_text(encoding='utf-8')
        payload = js.split('window.CITYGML_CATALOG = ', 1)[1].rstrip().rstrip(';')
        self.assertEqual(json.loads(payload), self.data)


FORMS = '''<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:c="urn:city"
 xmlns:xlink="http://www.w3.org/1999/xlink" targetNamespace="urn:city">
<xs:attributeGroup name="Association"><xs:attribute ref="xlink:href"/></xs:attributeGroup>
<xs:complexType name="MemberType"><xs:sequence/></xs:complexType>
<xs:element name="Thing" type="xs:string"/>
<xs:complexType name="BothPropertyType"><xs:sequence minOccurs="0"><xs:element ref="c:Thing"/></xs:sequence>
 <xs:attributeGroup ref="c:Association"/></xs:complexType>
<xs:complexType name="InlinePropertyType"><xs:complexContent><xs:extension base="c:MemberType">
 <xs:sequence><xs:element ref="c:Thing"/></xs:sequence></xs:extension></xs:complexContent></xs:complexType>
<xs:complexType name="ReferencePropertyType"><xs:complexContent><xs:extension base="c:MemberType">
 <xs:sequence/><xs:attributeGroup ref="c:Association"/></xs:extension></xs:complexContent></xs:complexType>
<xs:complexType name="InheritedPropertyType"><xs:complexContent><xs:extension base="c:BothPropertyType">
 <xs:sequence/></xs:extension></xs:complexContent></xs:complexType>
<xs:complexType name="RestrictedPropertyType"><xs:complexContent><xs:restriction base="c:BothPropertyType">
 <xs:sequence/></xs:restriction></xs:complexContent></xs:complexType>
<xs:complexType name="UnresolvedPropertyType"><xs:complexContent><xs:extension base="c:Missing">
 <xs:sequence/></xs:extension></xs:complexContent></xs:complexType>
<xs:simpleType name="ColorType"><xs:restriction><xs:simpleType><xs:list itemType="xs:double"/></xs:simpleType>
 <xs:length value="3"/></xs:restriction></xs:simpleType>
<xs:simpleType name="DirectListType"><xs:list itemType="xs:int"/></xs:simpleType>
<xs:complexType name="HolderType"><xs:sequence>
 <xs:element name="pair"><xs:simpleType><xs:restriction><xs:simpleType><xs:list itemType="xs:double"/></xs:simpleType>
  <xs:length value="2"/></xs:restriction></xs:simpleType></xs:element>
 <xs:element name="names"><xs:simpleType><xs:list itemType="xs:string"/></xs:simpleType></xs:element>
</xs:sequence></xs:complexType>
</xs:schema>'''


class CoverageTests(unittest.TestCase):
    def test_findings_for_what_the_catalog_loses(self):
        def cls(name, attrs=(), parents=(), constraints=(), module='Core', stereotype='FeatureType'):
            return {'name': name, 'module': module, 'stereotype': stereotype, 'values': [], 'associations': {},
                    'attributes': {a: {'type': 'CharacterString', 'multiplicity': '1..1', 'definition': ''} for a in attrs},
                    'subclassOf': list(parents), 'constraints': list(constraints)}

        def node(id_, members, parents=(), constraints=(), ancestors=(), uml_only=False, xsd_constraints=()):
            return {'id': id_, 'umlOnly': uml_only, 'ancestors': list(ancestors), 'source': ['s.xsd'],
                    'constraints': list(xsd_constraints),
                    'uml': {'properties': members, 'parents': list(parents), 'constraints': list(constraints)}}
        rule = {'name': 'r', 'text': 'inv: true', 'table': 'Table 1'}
        classes = {'A': cls('A', ['a']), 'B': cls('B', ['b1', 'b2'], ['A'], [rule]), 'U': cls('U', ['x', 'y'], stereotype='Union'),
                   'C': cls('C', ['u'], ['A', 'GM_Object']), 'GM_Object': cls('GM_Object', module='ISO Classes')}
        nodes = {
            # Complete class, with the list of the schema
            'A': node('A', [{'name': 'a', 'xsd': 'A/property:a'}], xsd_constraints=[{'kind': 'xs:list', 'targets': [], 'line': 10}]),
            # Member, generalization and constraint lost by the catalog
            'B': node('B', [{'name': 'b1', 'xsd': 'B/property:b1'}]),
            'U': node('U', [{'name': 'x', 'xsd': None}, {'name': 'y', 'xsd': None}], uml_only=True),
            # Union-typed member encoded as alternatives: a mapping, not a finding
            'C': node('C', [{'name': 'u', 'xsd': None, 'xsdMapping': {'rule': 'unionAlternatives', 'properties': ['C/property:x']}}],
                      parents=['A'], ancestors=['A'])}
        cov = coverage(classes, nodes, {k: k for k in nodes}, lambda s: s, [('s.xsd', 10, 'xs:list'), ('s.xsd', 20, 'xs:union')])
        findings = {k: [f['declaration'] for f in v['findings']] for k, v in cov.items()}
        self.assertEqual(findings, {'classes': [], 'members': ['B.b2'], 'generalizations': ['B → A'],
                                    'constraints': ['B: r'], 'simpleTypes': ['s.xsd:20 xs:union']})
        self.assertEqual((cov['classes']['total'], cov['classes']['represented']), (4, 4))
        self.assertEqual([e['declaration'] for e in cov['classes']['excluded']], ['GM_Object'])
        self.assertEqual(cov['members']['xsd'], {'classWithoutXsdType': ['U.x', 'U.y'], 'sameName': ['A.a', 'B.b1'],
                                                 'unionAlternatives': ['C.u']})
        self.assertEqual((cov['generalizations']['total'], cov['generalizations']['represented']), (3, 1))
        self.assertEqual(cov['generalizations']['xsd'], {'xsExtension': ['C → A']})
        self.assertEqual([e['declaration'] for e in cov['generalizations']['excluded']], ['C → GM_Object'])


class SyntheticBuildTests(unittest.TestCase):
    def test_encoding_forms_and_simple_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root/'sources/example.org'
            folder.mkdir(parents=True)
            (folder/'forms.xsd').write_text(FORMS, encoding='utf-8')
            builder = Builder(root)
            builder.read_xsd()
            forms = lambda name: builder.content_forms(builder.types[('urn:city', name)][0])
            self.assertEqual(forms('BothPropertyType'), (True, True))
            self.assertEqual(forms('InlinePropertyType'), (True, False))
            self.assertEqual(forms('ReferencePropertyType'), (False, True))
            self.assertEqual(forms('InheritedPropertyType'), (True, True))
            # A restriction does not bring back the children of its base.
            self.assertEqual(forms('RestrictedPropertyType'), (False, True))
            self.assertEqual(forms('UnresolvedPropertyType'), (None, None))
            nodes = builder.nodes
            name = lambda ids: [nodes[i]['name'] for i in ids]
            color = nodes[xid('urn:city', 'ColorType', 'type')]['constraints']
            self.assertEqual([(c['kind'], c.get('value'), name(c.get('targets', []))) for c in color],
                             [('length', '3', []), ('xs:list', None, ['double'])])
            direct = nodes[xid('urn:city', 'DirectListType', 'type')]['constraints']
            self.assertEqual([(c['kind'], c['targets'], 'description' in c) for c in direct],
                             [('xs:list', [xid('http://www.w3.org/2001/XMLSchema', 'int', 'type')], False)])
            self.assertEqual(direct[0]['line'], FORMS.splitlines().index('<xs:simpleType name="DirectListType"><xs:list itemType="xs:int"/></xs:simpleType>') + 1)
            holder = {p['name']: nodes[p['targets'][0]] for p in nodes[xid('urn:city', 'HolderType', 'type')]['properties']}
            self.assertEqual([name(c['targets']) for c in holder['pair']['constraints'] if c['kind'] == 'xs:list'], [['double']])
            self.assertEqual([name(c['targets']) for c in holder['names']['constraints'] if c['kind'] == 'xs:list'], [['string']])


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
            self.assertEqual(data['warnings'], ['Documento del modello concettuale non disponibile in sources/: catalogo solo XSD.'])
            self.assertIsNone(data['standard'])


if __name__ == '__main__':
    unittest.main()
