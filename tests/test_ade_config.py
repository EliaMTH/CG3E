"""Tests of scripts/ades.py: the "ades" section of config/sources.json."""
import copy
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import ades

BASE = 'https://example.org/cg3e/test-ade/'
ADE = {'name': 'TestADE', 'prefix': 'tade', 'namespace': 'https://example.org/cg3e/test-ade/1.0',
       'schema': BASE + '1.0/test-ade.xsd',
       'local': {'baseUrl': BASE, 'folder': 'ade'},
       'codeLists': {'baseUrl': BASE + '1.0/codelists/',
                     'files': ['TestADE.EnergyClassValue.xml', 'Building.BuildingClassValue.xml']},
       'codeListBindings': {'tade:BuildingProperties/tade:energyClass': 'EnergyClassValue',
                            'tade:BuildingProperties/tade:ownerType': 'OwnerTypeValue'},
       'topLevel': ['tade:Kiosk']}


def parse(*entries):
    return ades.parse(Path('/r'), {'ades': list(entries)})


def changed(**fields):
    entry = copy.deepcopy(ADE)
    entry.update(fields)
    return entry


class ParseTests(unittest.TestCase):
    def test_without_section(self):
        self.assertEqual(ades.parse(Path('/r'), {}), [])

    def test_valid_entry(self):
        [ade] = parse(ADE)
        self.assertEqual((ade.name, ade.prefix, ade.namespace), ('TestADE', 'tade', 'https://example.org/cg3e/test-ade/1.0'))
        self.assertEqual(ade.lists(), ['EnergyClassValue', 'OwnerTypeValue'])
        self.assertEqual(ade.dictionary('EnergyClassValue'), BASE + '1.0/codelists/TestADE.EnergyClassValue.xml')
        self.assertIsNone(ade.dictionary('OwnerTypeValue'))
        self.assertEqual(ade.extensions(), [('Building', 'BuildingClassValue', BASE + '1.0/codelists/Building.BuildingClassValue.xml')])
        self.assertEqual(ade.top_level, ['tade:Kiosk'])

    def test_local_file_for_both_schemes(self):
        [ade] = parse(ADE)
        for url in ('http://example.org/cg3e/test-ade/1.0/test-ade.xsd', 'https://example.org/cg3e/test-ade/1.0/test-ade.xsd'):
            path, shown = ade.local_file(url)
            self.assertEqual(path.as_posix(), '/r/ade/1.0/test-ade.xsd')
            self.assertEqual(shown, 'ade/1.0/test-ade.xsd')
        self.assertIsNone(ade.local_file('http://schemas.opengis.net/citygml/3.0/core.xsd'))
        self.assertEqual(ade.local_file(BASE + '../1.0/./x.xsd')[1], 'ade/1.0/x.xsd')
        self.assertIsNone(parse(changed(local=None))[0].local_file(ADE['schema']))

    def test_errors(self):
        cases = [
            (changed(name='Building'), 'coincide con un modulo'),
            (changed(name='Test.ADE'), 'solo lettere'),
            (changed(prefix='xml'), 'prefisso non valido'),
            (changed(namespace='http://www.opengis.net/citygml/building/3.0'), 'non di CityGML'),
            (changed(namespace='http://www.opengis.net/gml/3.2'), 'non di CityGML'),
            (changed(schema='ftp://example.org/a.xsd'), 'URL http o https'),
            (changed(schema='https://example.org/elsewhere/a.xsd'), 'non è sotto local.baseUrl'),
            (changed(local={'baseUrl': 'https://example.org/cg3e', 'folder': 'ade'}), 'terminare con /'),
            (changed(codeLists={'baseUrl': 'https://example.org/other/', 'files': []}), 'codeLists.baseUrl non è sotto'),
            (changed(codeLists={'baseUrl': BASE, 'files': ['EnergyClassValue.xml']}), '<Modulo>.<Lista>.xml'),
            (changed(codeLists={'baseUrl': BASE, 'files': ['Other.EnergyClassValue.xml']}), 'modulo di CityGML'),
            (changed(codeListBindings={'BuildingProperties/energyClass': 'EnergyClassValue'}), 'collegamento non nella forma'),
            (changed(codeListBindings={'tade:BuildingProperties/tade:energyClass': 'tade:EnergyClassValue'}), 'nome di code list non valido'),
            (changed(topLevel=['bldg:Building']), 'topLevel'),
        ]
        for entry, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ades.ConfigError, message):
                parse(entry)

    def test_unique_names_prefixes_and_namespaces(self):
        other = changed(name='Other', prefix='oth', namespace='urn:other', local=None, codeLists=None,
                        codeListBindings={}, topLevel=[], schema='https://example.org/other.xsd')
        self.assertEqual(len(parse(ADE, other)), 2)
        for field, value in (('name', 'testade'), ('prefix', 'tade'), ('namespace', ADE['namespace'])):
            with self.subTest(field=field), self.assertRaisesRegex(ades.ConfigError, 'già usato'):
                parse(ADE, {**other, field: value})


if __name__ == '__main__':
    unittest.main()
