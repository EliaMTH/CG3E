"""Tests of scripts/fetch_sources.py with simulated responses. No network calls."""
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
import fetch_sources as f

XSD = 'http://www.w3.org/2001/XMLSchema'
ADE_BASE = 'https://example.org/cg3e/test-ade/'


def schema(namespace, *refs):
    body = ''.join(refs)
    return f'<xs:schema xmlns:xs="{XSD}" targetNamespace="{namespace}" version="1.0">{body}</xs:schema>'.encode()


class HelperTests(unittest.TestCase):
    def test_canonical_and_transport(self):
        self.assertEqual(f.canonical('https://schemas.opengis.net/a.xsd#x'), 'http://schemas.opengis.net/a.xsd')
        self.assertEqual(f.transport('http://schemas.opengis.net/a.xsd'), 'https://schemas.opengis.net/a.xsd')

    def test_local_path_mirrors_url(self):
        path = f.local_path(Path('/r'), 'http://schemas.opengis.net/citygml/3.0/core.xsd')
        self.assertEqual(path.as_posix(), '/r/sources/schemas.opengis.net/citygml/3.0/core.xsd')

    def test_unknown_host_rejected(self):
        with self.assertRaises(ValueError):
            f.check_host('https://example.com/a.xsd', {'schemas.opengis.net'})

    def test_relative_include_resolved_against_document(self):
        payload = schema('urn:a', '<xs:include schemaLocation="b.xsd"/>', '<xs:import namespace="urn:c" schemaLocation="../c/c.xsd"/>')
        namespace, version, refs = f.parse_schema(payload, 'http://schemas.opengis.net/x/a.xsd', 'urn:a')
        self.assertEqual((namespace, version), ('urn:a', '1.0'))
        self.assertEqual(refs[0], {'url': 'http://schemas.opengis.net/x/b.xsd', 'kind': 'xsd:include', 'namespace': 'urn:a'})
        self.assertEqual(refs[1], {'url': 'http://schemas.opengis.net/c/c.xsd', 'kind': 'xsd:import', 'namespace': 'urn:c'})

    def test_namespace_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Namespace'):
            f.parse_schema(schema('urn:other'), 'http://schemas.opengis.net/a.xsd', 'urn:a')

    def test_html_rejected(self):
        with self.assertRaisesRegex(ValueError, 'HTML'):
            f.parse_schema(b'<!DOCTYPE html><html></html>', 'http://schemas.opengis.net/a.xsd')

    def test_document_formats(self):
        f.check_document(b'Plain text', 'text')
        f.check_document(b'<!DOCTYPE html><html></html>', 'html')
        with self.assertRaisesRegex(ValueError, 'HTML'):
            f.check_document(b'<!DOCTYPE html><html></html>', 'text')
        with self.assertRaisesRegex(ValueError, 'non e HTML'):
            f.check_document(b'Plain text', 'html')
        with self.assertRaisesRegex(ValueError, 'zip'):
            f.check_document(b'not a zip', 'zip')
        f.check_document(b'<gml:Dictionary xmlns:gml="http://www.opengis.net/gml/3.2"/>', 'gml-dictionary')
        with self.assertRaisesRegex(ValueError, 'gml:Dictionary'):
            f.check_document(b'<root/>', 'gml-dictionary')

    def test_non_schema_rejected(self):
        with self.assertRaisesRegex(ValueError, 'xs:schema'):
            f.parse_schema(b'<root/>', 'http://schemas.opengis.net/a.xsd')


class RunTests(unittest.TestCase):
    def test_follows_imports_and_writes_manifest(self):
        documents = {
            'http://schemas.opengis.net/m/main.xsd': schema('urn:main', '<xs:import namespace="urn:dep" schemaLocation="../d/dep.xsd"/>'),
            'http://schemas.opengis.net/d/dep.xsd': schema('urn:dep'),
            'http://schemas.opengis.net/ReadMe.txt': b'Read me',
        }

        def fake_download(opener, url, hosts, timeout):
            return f.transport(url), documents[url], {'lastModified': 'Wed, 09 Apr 2025 01:48:37 GMT', 'etag': None}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'config').mkdir()
            (root/'config/sources.json').write_text(json.dumps({
                'allowedHosts': ['schemas.opengis.net'],
                'schemas': ['http://schemas.opengis.net/m/main.xsd'],
                'documents': ['http://schemas.opengis.net/ReadMe.txt']}))
            with patch.object(f, 'download', fake_download):
                self.assertEqual(f.run(Namespace(root=root, timeout=1)), 0)
            manifest = json.loads((root/'sources/manifest.json').read_text())
            paths = {r['path'] for r in manifest['files']}
            self.assertEqual(paths, {'sources/schemas.opengis.net/m/main.xsd',
                                     'sources/schemas.opengis.net/d/dep.xsd',
                                     'sources/schemas.opengis.net/ReadMe.txt'})
            dep = next(r for r in manifest['files'] if r['path'].endswith('dep.xsd'))
            self.assertEqual(dep['requestedBy'], ['http://schemas.opengis.net/m/main.xsd'])
            self.assertEqual(dep['targetNamespace'], 'urn:dep')
            self.assertEqual((root/'sources/schemas.opengis.net/d/dep.xsd').read_bytes(), documents['http://schemas.opengis.net/d/dep.xsd'])
            self.assertIn('rewriteURI', (root/'sources/xml-catalog.xml').read_text())

    def test_reuse_local_downloads_only_new_or_changed_files(self):
        documents = {
            'http://schemas.opengis.net/m/main.xsd': schema('urn:main', '<xs:import namespace="urn:dep" schemaLocation="../d/dep.xsd"/>'),
            'http://schemas.opengis.net/d/dep.xsd': schema('urn:dep'),
            'http://schemas.opengis.net/ReadMe.txt': b'Read me',
            'http://schemas.opengis.net/New.txt': b'New document',
        }
        calls = []

        def fake_download(opener, url, hosts, timeout):
            calls.append(url)
            return f.transport(url), documents[url], {'lastModified': None, 'etag': None}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'config').mkdir()
            config = {'allowedHosts': ['schemas.opengis.net'], 'schemas': ['http://schemas.opengis.net/m/main.xsd'],
                      'documents': ['http://schemas.opengis.net/ReadMe.txt']}
            (root/'config/sources.json').write_text(json.dumps(config))
            with patch.object(f, 'download', fake_download):
                self.assertEqual(f.run(Namespace(root=root, timeout=1)), 0)
            before = {r['url']: r for r in json.loads((root/'sources/manifest.json').read_text())['files']}
            config['documents'].append('http://schemas.opengis.net/New.txt')
            (root/'config/sources.json').write_text(json.dumps(config))
            (root/'sources/schemas.opengis.net/d/dep.xsd').write_bytes(b'edited locally')
            calls.clear()
            with patch.object(f, 'download', fake_download):
                self.assertEqual(f.run(Namespace(root=root, timeout=1, reuse_local=True)), 0)
            self.assertEqual(sorted(calls), ['http://schemas.opengis.net/New.txt', 'http://schemas.opengis.net/d/dep.xsd'])
            after = {r['url']: r for r in json.loads((root/'sources/manifest.json').read_text())['files']}
            main = 'http://schemas.opengis.net/m/main.xsd'
            self.assertEqual(after[main], before[main])
            self.assertEqual((root/'sources/schemas.opengis.net/d/dep.xsd').read_bytes(), documents['http://schemas.opengis.net/d/dep.xsd'])
            self.assertEqual(len(after), 4)

    def test_missing_code_list_sample_is_unavailable_not_failure(self):
        dictionary = b'<gml:Dictionary xmlns:gml="http://www.opengis.net/gml/3.2"/>'
        base = 'https://data.ogc.org/citygml-swg/CodeList_Examples_3.0.0/'

        def fake_download(opener, url, hosts, timeout):
            if url.endswith('Missing.Value.xml'):
                raise OSError('HTTP Error 404')
            return url, dictionary, {'lastModified': None, 'etag': None}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'config').mkdir()
            (root/'config/sources.json').write_text(json.dumps({
                'allowedHosts': ['data.ogc.org'], 'schemas': [], 'documents': [],
                'codeListSamples': {'baseUrl': base, 'files': ['Building.RoofTypeValue.xml', 'Missing.Value.xml']}}))
            with patch.object(f, 'download', fake_download):
                self.assertEqual(f.run(Namespace(root=root, timeout=1)), 0)
            manifest = json.loads((root/'sources/manifest.json').read_text())
            self.assertEqual(manifest['failures'], [])
            self.assertEqual([u['url'] for u in manifest['unavailable']], [base + 'Missing.Value.xml'])
            sample = manifest['files'][0]
            self.assertEqual((sample['role'], sample['format']), ('codelist-sample', 'gml-dictionary'))

    def test_failure_is_reported(self):
        def fake_download(opener, url, hosts, timeout):
            raise OSError('offline')

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'config').mkdir()
            (root/'config/sources.json').write_text(json.dumps({
                'allowedHosts': ['schemas.opengis.net'],
                'schemas': ['http://schemas.opengis.net/m/main.xsd'], 'documents': []}))
            with patch.object(f, 'download', fake_download):
                self.assertEqual(f.run(Namespace(root=root, timeout=1)), 1)
            manifest = json.loads((root/'sources/manifest.json').read_text())
            self.assertEqual(manifest['files'], [])
            self.assertEqual(manifest['failures'][0]['url'], 'http://schemas.opengis.net/m/main.xsd')


class LocalAdeTests(unittest.TestCase):
    """An ADE read from a local folder (tests/fixtures/ade): no network, host not allowed."""

    # The schemas that the Test ADE imports, as small stand-ins.
    IMPORTS = {'http://schemas.opengis.net/citygml/3.0/core.xsd': schema('http://www.opengis.net/citygml/3.0'),
               'http://schemas.opengis.net/citygml/building/3.0/building.xsd': schema('http://www.opengis.net/citygml/building/3.0'),
               'http://schemas.opengis.net/gml/3.2.1/gml.xsd': schema('http://www.opengis.net/gml/3.2')}

    def setUp(self):
        self.calls = []
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT/'tests/fixtures/ade', self.root/'ade')
        (self.root/'config').mkdir()
        self.config = {'allowedHosts': ['schemas.opengis.net'], 'schemas': [], 'documents': [], 'ades': [{
            'name': 'TestADE', 'prefix': 'tade', 'namespace': 'https://example.org/cg3e/test-ade/1.0',
            'schema': ADE_BASE + '1.0/test-ade.xsd', 'local': {'baseUrl': ADE_BASE, 'folder': 'ade'},
            'codeLists': {'baseUrl': ADE_BASE + '1.0/codelists/',
                          'files': ['TestADE.EnergyClassValue.xml', 'Building.BuildingClassValue.xml']}}]}

    def tearDown(self):
        self.tmp.cleanup()

    def run_fetch(self):
        def fake_download(opener, url, hosts, timeout):
            self.calls.append(url)
            return f.transport(url), self.IMPORTS[url], {'lastModified': None, 'etag': None}
        (self.root/'config/sources.json').write_text(json.dumps(self.config))
        with patch.object(f, 'download', fake_download):
            code = f.run(Namespace(root=self.root, timeout=1))
        return code, json.loads((self.root/'sources/manifest.json').read_text())

    def test_local_copy_without_network(self):
        code, manifest = self.run_fetch()
        self.assertEqual((code, manifest['failures']), (0, []))
        self.assertEqual(sorted(self.calls), sorted(self.IMPORTS))
        local = {r['path']: r for r in manifest['files'] if r.get('origin') == 'local'}
        folder = 'sources/example.org/cg3e/test-ade/1.0/'
        self.assertEqual(sorted(local), [folder + 'codelists/Building.BuildingClassValue.xml',
                                         folder + 'codelists/TestADE.EnergyClassValue.xml',
                                         folder + 'test-ade-meters.xsd', folder + 'test-ade.xsd'])
        schema_record = local[folder + 'test-ade.xsd']
        self.assertEqual((schema_record['url'], schema_record['localPath'], schema_record['targetNamespace']),
                         ('http://example.org/cg3e/test-ade/1.0/test-ade.xsd', 'ade/1.0/test-ade.xsd', 'https://example.org/cg3e/test-ade/1.0'))
        self.assertEqual(local[folder + 'test-ade-meters.xsd']['requestedBy'], ['http://example.org/cg3e/test-ade/1.0/test-ade.xsd'])
        self.assertEqual({local[folder + 'codelists/' + n]['role'] for n in ('TestADE.EnergyClassValue.xml', 'Building.BuildingClassValue.xml')},
                         {'ade-codelist'})
        self.assertEqual((self.root/folder/'test-ade.xsd').read_bytes(), (self.root/'ade/1.0/test-ade.xsd').read_bytes())
        self.assertIn('uriStartString="http://example.org/"', (self.root/'sources/xml-catalog.xml').read_text())

    def test_unchanged_copy_keeps_its_record_and_removed_ade_is_deleted(self):
        _, before = self.run_fetch()
        _, again = self.run_fetch()
        local = lambda manifest: [r for r in manifest['files'] if r.get('origin') == 'local']
        self.assertEqual(local(again), local(before))
        (self.root/'ade/1.0/test-ade-meters.xsd').write_text((self.root/'ade/1.0/test-ade-meters.xsd').read_text() + '\n')
        _, changed = self.run_fetch()
        meters = lambda manifest: next(r for r in manifest['files'] if r['path'].endswith('test-ade-meters.xsd'))
        self.assertNotEqual(meters(changed)['sha256'], meters(before)['sha256'])
        del self.config['ades']
        code, removed = self.run_fetch()
        self.assertEqual((code, local(removed)), (0, []))
        self.assertEqual([p for p in (self.root/'sources').rglob('*') if p.is_file() and 'example.org' in p.as_posix()], [])

    def test_missing_local_file_is_a_failure(self):
        self.config['ades'][0]['codeLists']['files'].append('TestADE.Missing.xml')
        code, manifest = self.run_fetch()
        self.assertEqual(code, 1)
        self.assertEqual([p['url'] for p in manifest['failures']], [ADE_BASE + '1.0/codelists/TestADE.Missing.xml'])
        self.assertIn('ade/1.0/codelists/TestADE.Missing.xml', manifest['failures'][0]['error'])

    def test_configuration_error_writes_nothing(self):
        self.config['ades'][0]['name'] = 'Building'
        (self.root/'config/sources.json').write_text(json.dumps(self.config))
        self.assertEqual(f.run(Namespace(root=self.root, timeout=1)), 1)
        self.assertFalse((self.root/'sources').exists())


if __name__ == '__main__':
    unittest.main()
