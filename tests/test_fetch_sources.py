"""Tests of scripts/fetch_sources.py with simulated responses. No network calls."""
import json
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


if __name__ == '__main__':
    unittest.main()
