"""Tests of scripts/codespaces.py (codeSpace delle code list proprie)."""
import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import codespaces as cs
import exporters as ex

WHEN = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
BASE = 'https://example.org/citygml/codelists/'
BLDG = 'http://www.opengis.net/citygml/building/3.0'
TUN = 'http://www.opengis.net/citygml/tunnel/3.0'
SIG3D = 'https://www.sig3d.org/codelists/citygml/building/3.0/'
CATALOG = {'nodes': {
    'b': {'id': 'xsd:{%s}element:Building' % BLDG, 'family': 'CityGML', 'module': 'Building', 'namespace': BLDG},
    't': {'id': 'xsd:{%s}element:Tunnel' % TUN, 'family': 'CityGML', 'module': 'Tunnel', 'namespace': TUN}}}


def sig3d(name, codes, **extra):
    space = SIG3D + name
    return {'module': 'Building', 'identifier': name, 'codeSpace': space, 'description': '',
            'metadata': {'dataType': name, 'namespace': BLDG, 'language': 'en-US', 'authority': 'SIG3D', 'version': '1.0',
                         'metadataNamespace': 'http://www.opengis.net/citygml/codelistmetadata/3.0'},
            'values': [{'code': c, 'codeSpace': space, 'name': f'v{c}', 'description': ''} for c in codes], **extra}


def dictionary():
    placeholder = sig3d('BuildingClassValue', ['9991'], edited=True)
    placeholder['values'][0]['name'] = '{example-1}'
    return {'format': 1, 'kind': 'local', 'codeLists': {
        'RoofTypeValue': sig3d('RoofTypeValue', ['1000', '1010'], edited=True),
        'BuildingFunctionValue': sig3d('BuildingFunctionValue', ['1000']),
        'BuildingClassValue': placeholder,
        'HollowSpaceUsageValue': {'module': 'Tunnel', 'url': 'https://data.ogc.org/x', 'unavailable': True, 'values': [
            {'code': 'h1', 'codeSpace': None, 'name': 'locale tecnico', 'description': ''}], 'placeholder': False, 'edited': True}}}


class PolicyTests(unittest.TestCase):

    def apply(self, data=None, **kwargs):
        params = {'base': BASE, 'version': '1.0', 'authority': 'Comune', 'language': 'it', 'applied_at': WHEN, **kwargs}
        return cs.apply(data or dictionary(), CATALOG, params.pop('base'), params.pop('version'), params.pop('authority'),
                        params.pop('language'), params.pop('lists', None), params.pop('applied_at'))

    def test_edited_lists_by_default(self):
        original = dictionary()
        result, treated, skipped = self.apply(original)
        self.assertEqual(treated, ['HollowSpaceUsageValue', 'RoofTypeValue'])
        self.assertEqual(skipped, ['BuildingClassValue'])
        roof = result['codeLists']['RoofTypeValue']
        space = BASE + '1.0/Building.RoofTypeValue.xml'
        self.assertEqual(roof['codeSpace'], space)
        self.assertEqual({v['codeSpace'] for v in roof['values']}, {space})
        self.assertEqual({k: roof['metadata'][k] for k in ex.METADATA},
                         {'dataType': 'RoofTypeValue', 'namespace': BLDG, 'language': 'it', 'authority': 'Comune', 'version': '1.0'})
        for name in ('BuildingFunctionValue', 'BuildingClassValue'):
            self.assertEqual(json.dumps(result['codeLists'][name]), json.dumps(original['codeLists'][name]))
        self.assertEqual(result['codeSpacePolicy'], {'base': BASE, 'version': '1.0', 'authority': 'Comune', 'language': 'it',
                                                     'lists': ['HollowSpaceUsageValue', 'RoofTypeValue'],
                                                     'appliedAt': '2026-10-19T12:00:00+00:00'})
        self.assertNotIn('codeSpacePolicy', original)

    def test_list_without_metadata_is_completed(self):
        result, _, _ = self.apply()
        hollow = result['codeLists']['HollowSpaceUsageValue']
        self.assertEqual((hollow['identifier'], hollow['codeSpace']), ('HollowSpaceUsageValue', BASE + '1.0/Tunnel.HollowSpaceUsageValue.xml'))
        self.assertEqual(hollow['metadata']['namespace'], TUN)
        # Ora esportabile secondo Annex E
        self.assertIn('HollowSpaceUsageValue', ex.dictionary_records(result))

    def test_language_is_required_when_the_list_has_none(self):
        with self.assertRaisesRegex(cs.PolicyError, 'HollowSpaceUsageValue: lingua assente'):
            self.apply(language=None)
        result, treated, _ = self.apply(language=None, lists=['RoofTypeValue'])
        self.assertEqual(result['codeLists']['RoofTypeValue']['metadata']['language'], 'en-US')
        self.assertNotIn('language', result['codeSpacePolicy'])

    def test_explicit_lists(self):
        result, treated, _ = self.apply(lists=['BuildingFunctionValue'])
        self.assertEqual(treated, ['BuildingFunctionValue'])
        self.assertTrue(result['codeLists']['BuildingFunctionValue']['edited'])
        with self.assertRaisesRegex(cs.PolicyError, 'non presenti nel dizionario: Nessuna'):
            self.apply(lists=['Nessuna'])

    def test_idempotent_and_extended(self):
        first, _, _ = self.apply(lists=['RoofTypeValue'])
        again, _, _ = self.apply(first, lists=['RoofTypeValue'], applied_at=datetime(2027, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(again, first)
        extended, _, _ = self.apply(first, lists=['BuildingFunctionValue'], applied_at=datetime(2027, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(extended['codeSpacePolicy']['lists'], ['BuildingFunctionValue', 'RoofTypeValue'])
        replaced, _, _ = self.apply(first, version='2.0', lists=['BuildingFunctionValue'])
        self.assertEqual(replaced['codeSpacePolicy']['lists'], ['BuildingFunctionValue'])
        self.assertEqual(replaced['codeLists']['RoofTypeValue']['codeSpace'], BASE + '1.0/Building.RoofTypeValue.xml')

    def test_arguments(self):
        for base, message in (('example.org/', 'URI assoluto'), ('https://example.org/x', 'terminare con "/"'),
                              ('ftp://example.org/', 'URI assoluto')):
            with self.assertRaisesRegex(cs.PolicyError, message):
                self.apply(base=base)
        for base in ('urn:example:citygml:', 'tag:example.org,2026:codelists/'):
            result, _, _ = self.apply(base=base, lists=['RoofTypeValue'])
            self.assertEqual(result['codeLists']['RoofTypeValue']['codeSpace'], base + '1.0/Building.RoofTypeValue.xml')
        with self.assertRaisesRegex(cs.PolicyError, '--version'):
            self.apply(version='1 0')

    def test_serialization_is_the_one_of_save(self):
        app = (ROOT/'assets/app.js').read_text(encoding='utf-8')
        header = re.search(r"function serializeCodeLists\(obj\) \{\s*return '(.*?)\\n", app).group(1)
        result, _, _ = self.apply()
        text = cs.serialize(result).decode('utf-8')
        self.assertTrue(text.startswith(header + '\nwindow.CITYGML_CODELISTS = {\n "format": 1,'))
        self.assertNotIn('\r', text)
        self.assertTrue(text.endswith('\n};\n'))
        self.assertEqual(ex.read_json_assignment(text, 'CITYGML_CODELISTS'), result)


class CommandTests(unittest.TestCase):

    def run_command(self, path, *extra):
        return subprocess.run([sys.executable, str(ROOT/'scripts/codespaces.py'), '--codelists', str(path), '--base', BASE,
                               '--version', '1.0', '--authority', 'Comune', '--lists', 'RoofTypeValue',
                               '--applied-at', '2026-10-19T12:00:00Z', *extra], capture_output=True, text=True)

    def test_dry_run_and_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'codelists.js'
            path.write_bytes((ROOT/'codelists/codelists.js').read_bytes())
            before = path.read_bytes()
            run = self.run_command(path, '--dry-run')
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('RoofTypeValue: ' + SIG3D + 'RoofTypeValue -> ' + BASE + '1.0/Building.RoofTypeValue.xml', run.stdout)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(self.run_command(path).returncode, 0)
            written = path.read_bytes()
            data = ex.read_json_assignment(written.decode('utf-8'), 'CITYGML_CODELISTS')
            self.assertEqual(data['codeLists']['RoofTypeValue']['codeSpace'], BASE + '1.0/Building.RoofTypeValue.xml')
            original = ex.read_json_assignment(before.decode('utf-8'), 'CITYGML_CODELISTS')
            changed = [n for n in data['codeLists'] if data['codeLists'][n] != original['codeLists'][n]]
            self.assertEqual(changed, ['RoofTypeValue'])
            run = self.run_command(path)
            self.assertIn('Nessuna modifica', run.stdout)
            self.assertEqual(path.read_bytes(), written)

    def test_error_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'codelists.js'
            path.write_bytes((ROOT/'codelists/codelists.js').read_bytes())
            before = path.read_bytes()
            run = self.run_command(path, '--base', 'example.org')
            self.assertEqual(run.returncode, 1)
            self.assertIn('ERRORE: --base', run.stderr)
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
