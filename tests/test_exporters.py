"""Tests of scripts/exporters.py and scripts/export.py (city3d, generator, standard)."""
import copy
import csv
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from lxml import etree as ET, html
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import exporters as ex

WHEN = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
BLDG = 'http://www.opengis.net/citygml/building/3.0'
CORE = 'http://www.opengis.net/citygml/3.0'
TRAN = 'http://www.opengis.net/citygml/transportation/3.0'
GML = 'http://www.opengis.net/gml/3.2'
PROFILE = 'http://www.opengis.net/citygml/profiles/base/3.0'
PROFILE_XSD = 'http://schemas.opengis.net/citygml/profiles/base/3.0/CityGML.xsd'


def annex_e_examples():
    """Blocchi di esempio di OGC 21-006r2, Annex E, dalla copia locale del documento."""
    doc = html.parse(str(ROOT/'sources/docs.ogc.org/is/21-006r2/21-006r2.html'))
    section = doc.getroot().get_element_by_id('annex-codelist-usage').getparent()
    return [pre.text_content() for pre in section.iter('pre')]


def keys(obj):
    """Struttura delle chiavi di un JSON, senza i valori."""
    if isinstance(obj, dict):
        return {k: keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [keys(obj[0])] if obj else []
    return None


def unzip(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def dictionary_with(**lists):
    """Dizionario sintetico con le liste indicate, nel formato di codelists/codelists.js."""
    return {'format': 1, 'codeLists': lists}


def code_list(module, code_space, values, **extra):
    meta = {'dataType': extra.pop('dataType', 'X'), 'namespace': BLDG, 'language': 'en-US', 'authority': 'SIG3D', 'version': '1.0'}
    return {'module': module, 'identifier': extra.pop('identifier', 'X'), 'codeSpace': code_space, 'description': '',
            'metadata': meta, 'values': values, **extra}


def value(code, name, code_space=None, description=''):
    return {'code': code, 'codeSpace': code_space, 'name': name, 'description': description}


class DictionaryTests(unittest.TestCase):
    """Serializzazione delle code list nelle forme di Annex E."""

    @classmethod
    def setUpClass(cls):
        cls.inputs = ex.load(ROOT)
        cls.records = ex.dictionary_records(cls.inputs.dictionary)
        cls.examples = annex_e_examples()

    def test_lists_with_real_values(self):
        lists = self.inputs.dictionary['codeLists']
        self.assertEqual(len(self.records), 44)
        self.assertEqual(sum(len(r['entries']) for r in self.records.values()), 2295)
        self.assertNotIn('DoorClassValue', self.records)  # solo segnaposto
        self.assertNotIn('HollowSpaceUsageValue', self.records)  # non pubblicata alla fonte
        self.assertEqual(ex.list_state(lists['DoorClassValue']), 'placeholder')
        self.assertEqual(ex.list_state(lists['HollowSpaceUsageValue']), 'unavailable')
        for record in self.records.values():
            for entry in record['entries']:
                self.assertNotRegex(entry['name'], ex.PLACEHOLDER)

    def test_gml_has_the_form_of_the_ogc_examples(self):
        record = self.records['RoofTypeValue']
        root = ET.fromstring(ex.to_gml(record))
        g = '{%s}' % GML
        self.assertEqual(root.tag, g+'Dictionary')
        self.assertEqual(root.get(g+'id'), 'RoofTypeValue')
        self.assertEqual([ET.QName(c).localname for c in root][:3], ['metaDataProperty', 'description', 'identifier'])
        meta = root.find(f'{g}metaDataProperty/{{{ex.CMD_NS}}}CodeListMetaData')
        self.assertEqual([ET.QName(c).localname for c in meta], list(ex.METADATA))
        self.assertEqual(root.find(g+'identifier').get('codeSpace'), 'https://www.sig3d.org/codelists/citygml/building/3.0/RoofTypeValue')
        first = root.find(f'{g}dictionaryEntry/{g}Definition')
        self.assertEqual(first.get(g+'id'), 'id1')
        self.assertEqual([ET.QName(c).localname for c in first], ['description', 'identifier', 'name'])
        self.assertEqual((first.find(g+'identifier').text, first.find(g+'name').text), ('1000', 'flat roof'))
        # Stessi codici, nomi e codeSpace del file d'esempio OGC da cui la lista deriva
        sample = ET.parse(str(ROOT/'sources/data.ogc.org/citygml-swg/CodeList_Examples_3.0.0/Building.RoofTypeValue.xml')).getroot()
        triple = lambda r: [(d.find(g+'identifier').get('codeSpace'), d.find(g+'identifier').text, d.find(g+'name').text) for d in r.iter(g+'Definition')]
        self.assertEqual(triple(root), triple(sample))

    def test_gml_dictionaries_validate_offline(self):
        ex.validate_dictionaries(self.inputs, {n: ex.to_gml(r) for n, r in self.records.items()})

    def test_schemas_are_never_fetched(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp)/'catalog.xml'
            empty.write_text(f'<catalog xmlns="{ex.CATALOG_NS}"/>', encoding='utf-8')
            with self.assertRaisesRegex(ex.ExportError, 'gml.xsd'):
                ex.compile_schema(empty, [(GML, ex.GML_XSD)])

    def test_json_follows_annex_e(self):
        example = json.loads(self.examples[3])
        produced = ex.to_json(self.records['RoofTypeValue'])
        self.assertEqual(keys(produced), keys(example))
        self.assertEqual(produced['Dictionary']['dictionaryEntry'][0]['Definition']['identifier']['#text'], '1000')

    def test_csv_follows_annex_e(self):
        example = [row.split('|') for row in self.examples[1].strip().splitlines()]
        rows = list(csv.reader(io.StringIO(ex.to_csv(self.records['RoofTypeValue']).decode('utf-8')), delimiter='|'))
        self.assertEqual(rows[0], example[0])
        self.assertEqual([r[:2] for r in rows[1:5]], [r[:2] for r in example[1:5]])
        self.assertEqual(rows[1], ['Meta', 'CityGML_DataType', 'Building', 'RoofTypeValue'])
        self.assertEqual(rows[5], ['Code', '1000', 'flat roof'])
        self.assertTrue(all(r[0] == 'Code' for r in rows[5:]))

    def test_values_keep_their_own_code_space(self):
        record = self.records['TrafficAreaFunctionValue']
        spaces = {e['codeSpace'] for e in record['entries']}
        self.assertEqual(len(spaces), len(record['entries']))
        self.assertNotIn(record['codeSpace'], spaces)

    def test_values_without_code_space_take_the_list_one(self):
        records = ex.dictionary_records(dictionary_with(X=code_list('Building', 'urn:x', [value('1', 'a'), value('2', 'b', 'urn:y')])))
        self.assertEqual([e['codeSpace'] for e in records['X']['entries']], ['urn:x', 'urn:y'])

    def test_placeholders_and_values_without_code_are_not_exported(self):
        lst = code_list('Building', 'urn:x', [value('9991', '{example-1}'), value('', 'senza codice'), value('1', 'reale')])
        records = ex.dictionary_records(dictionary_with(X=lst))
        self.assertEqual([(e['id'], e['code']) for e in records['X']['entries']], [('id1', '1')])

    def test_missing_metadata_stops_the_export(self):
        lst = code_list('Tunnel', None, [value('1', 'a')])
        lst['metadata'].pop('authority')
        with self.assertRaisesRegex(ex.ExportError, r'X \(codeSpace, metadata\.authority\).*codespaces\.py'):
            ex.dictionary_records(dictionary_with(X=lst))

    def test_xml_incompatible_text_is_an_error(self):
        records = ex.dictionary_records(dictionary_with(X=code_list('Building', 'urn:x', [value('1', 'a\x01')])))
        with self.assertRaisesRegex(ex.ExportError, 'X: testo non rappresentabile'):
            ex.to_gml(records['X'])

    def test_warnings(self):
        inputs = copy.copy(self.inputs)
        inputs.dictionary = copy.deepcopy(self.inputs.dictionary)
        inputs.dictionary['codeLists']['RoofTypeValue']['edited'] = True
        warnings = ex.dictionary_warnings(inputs, ex.dictionary_records(inputs.dictionary))
        self.assertTrue(any(w.startswith('RoofTypeValue: lista modificata con il codeSpace') for w in warnings))
        self.assertIn('BuildingFurnitureFunctionValue: codici ripetuti nello stesso codeSpace: 1270, 2200.', warnings)


class InputTests(unittest.TestCase):
    """Controlli iniziali: nessun file scritto se gli input non sono coerenti."""

    def fake_root(self, folder, catalog_sha='aaa', manifest_sha='aaa', fmt=1):
        root = Path(folder)
        for sub in ('data', 'sources', 'codelists'):
            (root/sub).mkdir()
        (root/'data/catalog.json').write_text(json.dumps({'files': [{'path': 'sources/a.xsd', 'sha256': catalog_sha}],
                                                          'standard': {}, 'nodes': {}}), encoding='utf-8')
        (root/'sources/manifest.json').write_text(json.dumps({'files': [{'path': 'sources/a.xsd', 'sha256': manifest_sha}]}), encoding='utf-8')
        (root/'codelists/codelists.js').write_text('window.CITYGML_CODELISTS = ' + json.dumps({'format': fmt, 'codeLists': {}}) + ';\n', encoding='utf-8')
        return root

    def test_stale_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fake_root(tmp, catalog_sha='bbb')
            with self.assertRaisesRegex(ex.ExportError, 'non corrisponde a sources/manifest.json per: sources/a.xsd'):
                ex.load(root)
            out = root/'out.json'
            run = subprocess.run([sys.executable, str(ROOT/'scripts/export.py'), 'city3d', '--out', str(out), '--root', str(root)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            self.assertIn('ERRORE: data/catalog.json non corrisponde', run.stderr)
            self.assertFalse(out.exists())

    def test_dictionary_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ex.ExportError, 'non è nel formato 1'):
                ex.load(self.fake_root(tmp, fmt=2))

    def test_dictionary_must_match_catalog_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fake_root(tmp)
            (root/'codelists/codelists.js').write_text('window.CITYGML_CODELISTS = {"format": 1, "codeLists": {"Nuova": {}}};', encoding='utf-8')
            with self.assertRaisesRegex(ex.ExportError, 'non nel catalogo: Nuova'):
                ex.load(root)

    def test_source_file_must_match_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fake_root(tmp)
            (root/'sources/a.xsd').write_bytes(b'<x/>')
            inputs = ex.Inputs(root, {}, json.loads((root/'sources/manifest.json').read_text()), {}, b'', None)
            with self.assertRaisesRegex(ex.ExportError, 'non corrisponde a sources/manifest.json'):
                ex.source_file(inputs, 'sources/a.xsd')

    def test_exported_at(self):
        self.assertEqual(ex.parse_exported_at('2026-10-19T14:00:00+02:00').isoformat(), '2026-10-19T12:00:00+00:00')
        self.assertEqual(ex.parse_exported_at('2026-10-19T12:00:00Z'), WHEN)
        with self.assertRaisesRegex(ex.ExportError, 'fuso orario'):
            ex.parse_exported_at('2026-10-19T12:00:00')


class City3dAndGeneratorTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.inputs = ex.load(ROOT)
        cls.city3d_result = ex.export_city3d(cls.inputs, WHEN)
        cls.city3d = json.loads(cls.city3d_result.data)
        cls.generator_result = ex.export_generator(cls.inputs, WHEN)
        cls.package = unzip(cls.generator_result.data)
        cls.generator = json.loads(cls.package['citygml-generator.json'])
        cls.manifest = {r['path']: r for r in cls.inputs.manifest['files']}

    def test_city3d(self):
        doc = self.city3d
        self.assertEqual((doc['format'], doc['formatVersion'], doc['exportedAt']), ('citygml-explorer/city3d', 1, '2026-10-19T12:00:00+00:00'))
        self.assertEqual(doc['schemas'], 'CityGML 3.0.0 (OGC 21-006r2)')
        self.assertEqual(len(doc['codeLists']), 140)
        with_values = {n: l for n, l in doc['codeLists'].items() if 'Dictionary' in l}
        self.assertEqual(len(with_values), 44)
        self.assertEqual(doc['codeLists']['DoorClassValue'], {'module': 'Construction', 'state': 'placeholder'})
        self.assertEqual(doc['codeLists']['HollowSpaceUsageValue'], {'module': 'Tunnel', 'state': 'unavailable'})
        roof = doc['codeLists']['RoofTypeValue']
        self.assertEqual((roof['module'], roof['state']), ('Building', 'values'))
        self.assertEqual(keys({'Dictionary': roof['Dictionary']}), keys(json.loads(annex_e_examples()[3])))
        traffic = doc['codeLists']['TrafficAreaFunctionValue']['Dictionary']['dictionaryEntry']
        self.assertTrue(all(e['Definition']['identifier']['@codeSpace'].startswith('https://ogc.org/citygml/3.0/codelists/gml/') for e in traffic))
        self.assertNotIn('{example-', self.city3d_result.data.decode('utf-8'))

    def test_code_list_use(self):
        use = self.city3d['codeListUse']
        self.assertEqual(len(use), 158)
        self.assertEqual(len({(u['element'], u['elementNamespace']) for u in use}), 63)
        self.assertEqual(len({u['codeList'] for u in use}), 136)
        self.assertEqual(len({(u['elementNamespace'], u['element'], u['propertyNamespace'], u['property']) for u in use}), len(use))
        self.assertTrue({u['codeList'] for u in use} <= set(self.city3d['codeLists']))
        self.assertIn({'element': 'TrafficArea', 'elementNamespace': TRAN, 'property': 'function', 'propertyNamespace': TRAN,
                       'codeList': 'TrafficAreaFunctionValue', 'declaredIn': 'TrafficArea', 'declaredInNamespace': TRAN,
                       'multiplicity': '0..*'}, use)
        self.assertIn({'element': 'Building', 'elementNamespace': BLDG, 'property': 'roofType', 'propertyNamespace': BLDG,
                       'codeList': 'RoofTypeValue', 'declaredIn': 'AbstractBuilding', 'declaredInNamespace': BLDG,
                       'multiplicity': '0..1'}, use)
        self.assertEqual(self.generator['codeListUse'], use)

    def test_deterministic(self):
        self.assertEqual(ex.export_city3d(self.inputs, WHEN).data, self.city3d_result.data)
        self.assertEqual(ex.export_generator(self.inputs, WHEN).data, self.generator_result.data)

    def test_generator_files(self):
        package = self.package
        for name in ('README.md', 'manifest.json', 'citygml-generator.json', 'xml-catalog.xml'):
            self.assertIn(name, package)
        schemas = [n for n in package if n.startswith('schemas/') and n.endswith('.xsd')]
        self.assertEqual(len(schemas), 78)
        for name in (n for n in package if n.startswith('schemas/')):
            self.assertEqual(hashlib.sha256(package[name]).hexdigest(), self.manifest['sources/' + name.removeprefix('schemas/')]['sha256'])
        self.assertIn('schemas/schemas.opengis.net/citygml/xAL/3.0/OASIS_COPYRIGHT_NOTICE.txt', package)
        self.assertEqual(len([n for n in package if n.startswith('codelists/')]), 88)
        manifest = json.loads(package['manifest.json'])
        self.assertEqual({e['path'] for e in manifest['files']}, set(package) - {'manifest.json'})
        for entry in manifest['files']:
            self.assertEqual(entry['sha256'], hashlib.sha256(package[entry['path']]).hexdigest())

    def test_generator_elements(self):
        items = {e['qname']: e for e in self.generator['elements']}
        self.assertEqual(len(items), 107)
        self.assertEqual(sum(len(e['properties']) for e in items.values()), 3483)
        building = items['bldg:Building']
        self.assertEqual(building['substitutionGroup'][:2], ['bldg:AbstractBuilding', 'con:AbstractConstruction'])
        names = [p['qname'] for p in building['properties']]
        self.assertEqual(names[0], 'gml:metaDataProperty')
        self.assertLess(names.index('core:lod0MultiSurface'), names.index('core:lod1Solid'))
        self.assertLess(names.index('core:lod1Solid'), names.index('bldg:function'))
        self.assertEqual(names[-2:], ['bldg:buildingPart', 'bldg:adeOfBuilding'])
        function = building['properties'][names.index('bldg:function')]
        self.assertEqual((function['codeList'], function['minOccurs'], function['maxOccurs']), ('BuildingFunctionValue', 0, 'unbounded'))
        self.assertEqual(function['uml'], {'class': 'AbstractBuilding', 'member': 'function', 'type': 'BuildingFunctionValue', 'multiplicity': '0..*'})
        boundary = building['properties'][names.index('core:boundary')]
        self.assertIn('tran:TrafficArea', boundary['candidates'])
        self.assertEqual(building['properties'][names.index('gml:description')]['targets'], [])
        city_model = items['core:CityModel']
        members = [p for p in city_model['properties'] if p.get('choices')]
        self.assertEqual({tuple(p['choices']) for p in members}, {('core:CityModel/choice:936',)})
        self.assertEqual(len(members), 5)

    def test_generator_rules(self):
        rules = self.generator['rules']
        boundaries = {r['space']: r for r in rules['allowedBoundaries']}
        self.assertEqual(len(boundaries['bldg:Building']['concrete']), 10)
        self.assertEqual(boundaries['bldg:Building']['source']['requirement'], '/req/building/boundaries')
        self.assertTrue(boundaries['veg:PlantCover']['none'])
        self.assertEqual(boundaries['veg:PlantCover']['concrete'], [])
        self.assertEqual(len(rules['topLevel']), 20)
        self.assertEqual(len(rules['referenceOnly']), 12)
        self.assertTrue(all(r['source']['requirements'] and r['source']['requirements'][0]['requirement'].endswith('/reference')
                            for r in rules['referenceOnly']))
        self.assertEqual(len(rules['constraints']), 12)
        self.assertEqual(len(rules['encodingRules']), 65)
        self.assertTrue(all(r['source']['url'].startswith('https://docs.ogc.org/is/21-006r2/21-006r2.html#') for r in rules['encodingRules']))

    def test_generator_xml_catalog_resolves_code_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in self.package.items():
                (Path(tmp)/name).parent.mkdir(parents=True, exist_ok=True)
                (Path(tmp)/name).write_bytes(data)
            catalog = ex.XmlCatalog(Path(tmp)/'xml-catalog.xml')
            for name, entry in self.generator['codeLists'].items():
                if 'codeSpace' in entry:
                    local = catalog.lookup(entry['codeSpace'])
                    self.assertEqual(local, Path(tmp)/entry['files'][0])
                    self.assertEqual(ET.parse(str(local)).getroot().get('{%s}id' % GML), name)

    def test_building_built_from_the_package_validates_offline(self):
        """Un CityModel con un Building costruito con le sole informazioni del pacchetto."""
        package, gen = self.package, self.generator
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name, data in package.items():
                (folder/name).parent.mkdir(parents=True, exist_ok=True)
                (folder/name).write_bytes(data)
            entry = gen['codeLists']['BuildingFunctionValue']
            dictionary = json.loads((folder/entry['files'][1]).read_text(encoding='utf-8'))['Dictionary']
            first = dictionary['dictionaryEntry'][0]['Definition']['identifier']
            building = next(e for e in gen['elements'] if e['qname'] == 'bldg:Building')
            square = '0 0 0 10 0 0 10 10 0 0 10 0 0 0 0'
            faces = [square, '0 0 0 0 10 0 0 10 5 0 0 5 0 0 0']
            contents = {
                'core:lod0MultiSurface': f'<gml:MultiSurface><gml:surfaceMember><gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>{square}</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon></gml:surfaceMember></gml:MultiSurface>',
                'core:lod1Solid': '<gml:Solid><gml:exterior><gml:Shell>' + ''.join(
                    f'<gml:surfaceMember><gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>{f}</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon></gml:surfaceMember>'
                    for f in faces) + '</gml:Shell></gml:exterior></gml:Solid>',
                'bldg:function': first['#text'],
            }
            props = {p['qname']: p for p in building['properties']}
            self.assertIn('gml:MultiSurface', props['core:lod0MultiSurface']['candidates'])
            self.assertIn('gml:Solid', props['core:lod1Solid']['candidates'])

            def city_model(values):
                parts = []
                for prop in building['properties']:  # ordine delle proprietà dal pacchetto
                    if prop['qname'] in values:
                        attribute = f' codeSpace="{first["@codeSpace"]}"' if prop.get('codeList') else ''
                        parts.append(f'<{prop["qname"]}{attribute}>{values[prop["qname"]]}</{prop["qname"]}>')
                return ET.fromstring(f'<core:CityModel xmlns:core="{CORE}" xmlns:bldg="{BLDG}" xmlns:tran="{TRAN}" xmlns:gml="{GML}" gml:id="cm1">'
                                     f'<core:cityObjectMember><bldg:Building gml:id="b1">{"".join(parts)}</bldg:Building>'
                                     '</core:cityObjectMember></core:CityModel>')
            schema = ex.compile_schema(folder/'xml-catalog.xml', [(PROFILE, PROFILE_XSD)])
            self.assertTrue(schema.validate(city_model(contents)), schema.error_log)
            self.assertEqual(entry['codeSpace'], first['@codeSpace'])
            building['properties'].reverse()
            self.assertFalse(schema.validate(city_model(contents)))  # l'ordine conta
            building['properties'].reverse()
            # Valido per gli schemi, ma non ammesso dalla tabella dei confini di OGC 20-010
            wrong = city_model({**contents, 'core:boundary': '<tran:TrafficArea gml:id="t1"/>'})
            self.assertTrue(schema.validate(wrong), schema.error_log)
            allowed = next(r for r in gen['rules']['allowedBoundaries'] if r['space'] == 'bldg:Building')
            self.assertNotIn('tran:TrafficArea', allowed['concrete'])


class StandardTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.inputs = ex.load(ROOT)
        cls.result = ex.export_standard(cls.inputs, WHEN)
        cls.package = unzip(cls.result.data)

    def test_files(self):
        package = self.package
        for name in ('EXPORT.md', 'manifest.json', 'index.html', 'assets/app.js', 'assets/styles.css', 'assets/styles-dark.css',
                     'data/catalog.js', 'codelists/codelists.js', 'codelists/codelists.default.js', 'sources/manifest.json',
                     'sources/xml-catalog.xml', 'README.md', 'LICENSE-app.txt'):
            self.assertIn(name, package)
        for record in self.inputs.manifest['files']:
            self.assertEqual(hashlib.sha256(package[record['path']]).hexdigest(), record['sha256'])
        self.assertEqual(package['codelists/codelists.js'], self.inputs.dictionary_bytes)
        for excluded in ('scripts/', 'tests/', 'config/', 'docs/', 'tickets/', 'data/catalog.json'):
            self.assertFalse(any(n.startswith(excluded) for n in package), excluded)
        self.assertEqual(len([n for n in package if n.startswith('dictionaries/')]), 88)

    def test_dictionaries_validate_with_the_package_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in self.package.items():
                if name.startswith('sources/schemas.opengis.net/') or name.startswith('sources/www.w3.org/') or name == 'sources/xml-catalog.xml':
                    (Path(tmp)/name).parent.mkdir(parents=True, exist_ok=True)
                    (Path(tmp)/name).write_bytes(data)
            schema = ex.compile_schema(Path(tmp)/'sources/xml-catalog.xml', [(GML, ex.GML_XSD), (ex.CMD_NS, ex.CMD_XSD)])
            for name in (n for n in self.package if n.startswith('dictionaries/') and n.endswith('.xml')):
                self.assertTrue(schema.validate(ET.fromstring(self.package[name])), name)
        rows = self.package['dictionaries/Building.RoofTypeValue.csv'].decode('utf-8').splitlines()
        self.assertEqual(rows[0], 'CodeType|Identifier|Description')

    def test_export_notes(self):
        text = self.package['EXPORT.md'].decode('utf-8')
        for expected in ('CityGML 3.0.0 (OGC 21-006r2)', 'OGC 20-010', '2021-06-04', 'OGC 21-006r2', '2023-05-10',
                         'Download delle fonti', 'Modificate rispetto agli esempi OGC: nessuna', 'non applicata', '2026-10-19T12:00:00+00:00'):
            self.assertIn(expected, text)

    def test_deterministic(self):
        self.assertEqual(ex.export_standard(self.inputs, WHEN).data, self.result.data)


if __name__ == '__main__':
    unittest.main()
