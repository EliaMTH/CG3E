"""Offline tests. RDF fixtures are synthetic, NOT official ontology copies."""
import argparse
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import download_dependencies as d

OWL = 'http://www.w3.org/2002/07/owl#'
GEO = d.GEOSPARQL_11
OBS = 'http://www.w3.org/ns/ssn/obs/'
COMMON = 'http://www.w3.org/ns/ssn/common/'
ISO = 'http://def.isotc211.org/iso19150/-2/2012/base'


def ontology(iri, imports=(), version=None):
    text = f'@prefix owl: <{OWL}> . <{iri}> a owl:Ontology'
    if version:
        text += f'; owl:versionIRI <{version}>'
    for value in imports:
        text += f'; owl:imports <{value}>'
    return (text + ' .').encode()


class FakeResponse:
    def __init__(self, url, payload):
        self.url, self.payload = url, payload
        self.headers = {'Content-Type': 'text/turtle'}
    def geturl(self):
        return self.url
    def read(self, size):
        return self.payload[:size]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, documents):
        self.documents, self.called = documents, []
    def open(self, request, timeout=None):
        url = request.full_url
        self.called.append(url)
        if url not in self.documents:
            raise HTTPError(url, 404, 'Fixture not found', {}, None)
        item = self.documents[url]
        if isinstance(item, tuple):
            final, body = item
        else:
            final, body = url, item
        return FakeResponse(final, body)


class RoutesTests(unittest.TestCase):
    def test_ogc_redirect_is_authorized(self):
        d.allowed(d.GEOSPARQL_11_DOCUMENT, d.DEFAULT_HOSTS)
        result = d.SafeRedirect(d.DEFAULT_HOSTS).redirect_request(
            Request('https://www.opengis.net/ont/geosparql/1.1'), None, 302,
            'Found', {}, d.GEOSPARQL_11_DOCUMENT)
        self.assertEqual(result.full_url, d.GEOSPARQL_11_DOCUMENT)

    def test_unknown_redirect_still_blocked(self):
        with self.assertRaises(ValueError):
            d.SafeRedirect(d.DEFAULT_HOSTS).redirect_request(
                Request('https://www.opengis.net/ont/geosparql/1.1'), None,
                302, 'Found', {}, 'https://untrusted.invalid/file.ttl')

    def test_draft_disabled_by_default(self):
        self.assertFalse(any(d.W3C_REPO in u for u in d.candidate_urls(OBS, 'OWL')))

    def test_exact_w3c_observation_filename(self):
        expected = d.W3C_REPO + 'gh-pages/ssn/rdf/ontology/core/ssn-observation.ttl'
        self.assertEqual(d.w3c_draft_document(OBS), expected)
        self.assertEqual(d.candidate_urls(OBS, 'OWL', w3c_editor_draft=True)[0], expected)

    def test_draft_root_cannot_fall_back_to_legacy_endpoint(self):
        urls = d.candidate_urls('http://www.w3.org/ns/ssn/', 'OWL', w3c_editor_draft=True)
        self.assertEqual(len(urls), 1)
        self.assertTrue(urls[0].startswith(d.W3C_REPO))

    def test_transitive_common_and_sosa_modules(self):
        for iri, filename in ((COMMON, 'ssn-common.ttl'),
                ('http://www.w3.org/ns/sosa/obs/', 'sosa-observation.ttl'),
                ('http://www.w3.org/ns/sosa/common/', 'sosa-common.ttl')):
            self.assertTrue(d.w3c_draft_document(iri).endswith('/' + filename))

    def test_versioned_2023_module(self):
        self.assertEqual(d.w3c_draft_document('http://www.w3.org/ns/ssn/2023/obs/'),
                         d.w3c_draft_document(OBS))

    def test_2017_is_never_mapped_to_draft(self):
        self.assertIsNone(d.w3c_draft_document('http://www.w3.org/ns/ssn/2017/'))

    def test_unknown_module_not_guessed(self):
        self.assertIsNone(d.w3c_draft_document('http://www.w3.org/ns/ssn/unknown/'))

    def test_pinned_revision(self):
        sha = 'abcdef1234567890'
        self.assertIn('/' + sha + '/', d.w3c_draft_document(OBS, sha))
        with self.assertRaises(ValueError):
            d.w3c_draft_document(OBS, '../../escape')

    def test_geosparql11_mirror_not_next(self):
        urls = d.candidate_urls(GEO, 'OWL')
        self.assertIn(d.GEOSPARQL_11_DOCUMENT, urls)
        self.assertFalse(any('geosparql-next' in u for u in urls))
        self.assertNotIn(d.GEOSPARQL_11_DOCUMENT,
                         d.candidate_urls('http://www.opengis.net/ont/geosparql', 'OWL'))

    def test_iso_iri_not_rewritten(self):
        self.assertTrue(all('/iso19150/-2/' in u for u in d.candidate_urls(ISO, 'OWL')))

    def test_source_map_changes_location_not_identity(self):
        urls = d.candidate_urls(ISO, 'OWL', source_map={ISO: ['https://example.org/base.ttl']})
        self.assertEqual(urls[0], 'https://example.org/base.ttl')
        with self.assertRaisesRegex(ValueError, 'IRI/versionIRI'):
            d.decode_payload(ontology('http://example.org/wrong'), urls[0], 'OWL', ISO)

    def test_source_map_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'map.json'
            path.write_text(json.dumps({ISO: 'https://example.org/base.ttl'}))
            self.assertEqual(d.load_source_map(path)[ISO], ['https://example.org/base.ttl'])
            path.write_text(json.dumps({ISO: ['file:///etc/passwd']}))
            with self.assertRaises(ValueError):
                d.load_source_map(path)

    def test_old_ssn_not_accepted_as_observation(self):
        with self.assertRaisesRegex(ValueError, 'IRI/versionIRI'):
            d.decode_payload(ontology('http://www.w3.org/ns/ssn'),
                             'https://www.w3.org/ns/ssn/obs/', 'OWL', OBS)

    def test_version_iri_must_belong_to_ontology(self):
        value = ontology('http://example.org/wrong') + (
            f' <http://example.org/not-an-ontology> <{OWL}versionIRI> <{OBS}> .').encode()
        with self.assertRaisesRegex(ValueError, 'IRI/versionIRI'):
            d.decode_payload(value, 'https://example.org/file.ttl', 'OWL', OBS)


class DownloadFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'sources').mkdir()
        self.args = argparse.Namespace(root=self.root, only='owl', allow_host=[],
            dry_run=False, max_files=180, refresh=False, timeout=1, verbose=True,
            w3c_editor_draft=False, w3c_ref='gh-pages', source_map=None)
    def tearDown(self):
        self.tmp.cleanup()
    def manifest(self, *iris):
        value = {'files': [], 'dependencies': [
            {'url': iri, 'namespace': iri, 'kind': 'owl:imports',
             'status': 'missing', 'from': 'sources/original.owl'} for iri in iris]}
        (self.root / 'sources/dependency-manifest.json').write_text(json.dumps(value))
    def run_fake(self, docs):
        opener = FakeOpener(docs)
        with patch.object(d, 'build_opener', return_value=opener), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = d.run(self.args)
        return status, opener
    def test_successful_ogc_redirect_preserves_requested_iri(self):
        self.manifest(GEO)
        body = ontology('http://www.opengis.net/ont/geosparql', version=GEO)
        status, opener = self.run_fake({d.transport(GEO): (d.GEOSPARQL_11_DOCUMENT, body)})
        self.assertEqual(status, 0)
        lock = json.loads((self.root / 'sources/download-lock.json').read_text())
        meta = next(iter(lock.values()))
        self.assertEqual(meta['requestedUrl'], GEO)
        self.assertEqual(meta['url'], d.GEOSPARQL_11_DOCUMENT)
        self.assertEqual(meta['sha256'], hashlib.sha256(body).hexdigest())
    def test_draft_and_transitive_module_with_provenance(self):
        self.manifest(OBS)
        self.args.w3c_editor_draft = True
        status, _ = self.run_fake({
            d.w3c_draft_document(OBS): ontology(OBS, [COMMON]),
            d.w3c_draft_document(COMMON): ontology(COMMON)})
        self.assertEqual(status, 0)
        lock = json.loads((self.root / 'sources/download-lock.json').read_text())
        self.assertEqual(len(lock), 2)
        self.assertEqual({v['sourcePolicy'] for v in lock.values()}, {'w3c-editor-draft'})
        self.assertEqual({v['requestedUrl'] for v in lock.values()}, {OBS, COMMON})
    def test_wrong_ssn_never_written(self):
        self.manifest(OBS)
        status, _ = self.run_fake({u: ontology('http://www.w3.org/ns/ssn')
                                  for u in d.candidate_urls(OBS, 'OWL')})
        self.assertEqual(status, 1)
        self.assertEqual(json.loads((self.root / 'sources/download-lock.json').read_text()), {})
        self.assertFalse((self.root / 'sources/dependencies').exists())
    def test_iso_404_remains_missing_not_stubbed(self):
        self.manifest(ISO)
        status, _ = self.run_fake({})
        self.assertEqual(status, 1)
        report = json.loads((self.root / 'sources/download-report.json').read_text())
        self.assertEqual(report[0]['status'], 'failed')
        self.assertEqual(len(report[0]['errors']), 4)
        self.assertFalse((self.root / 'sources/dependencies').exists())
    def test_existing_cache_and_originals_not_overwritten(self):
        self.manifest(GEO)
        body = ontology('http://www.opengis.net/ont/geosparql', version=GEO)
        self.assertEqual(self.run_fake({d.transport(GEO): body})[0], 0)
        original = self.root / 'sources/user-file.owl'
        original.write_bytes(b'original contents')
        status, opener = self.run_fake({})
        self.assertEqual(status, 0)
        self.assertEqual(opener.called, [])
        self.assertEqual(original.read_bytes(), b'original contents')


if __name__ == '__main__':
    unittest.main()
