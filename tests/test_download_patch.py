"""Regression tests for the downloader patch. No network calls."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import download_dependencies as d
from rdflib import Graph

RDF = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
OWL = 'http://www.w3.org/2002/07/owl#'
URL = 'http://example.org/onto'
XML = f'''<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="{RDF}" xmlns:owl="{OWL}">
<owl:Ontology rdf:about="{URL}"/>
</rdf:RDF>'''.encode()
TTL = f'@prefix owl: <{OWL}> . <{URL}> a owl:Ontology .'.encode()


class DownloaderPatchTests(unittest.TestCase):
    def test_xml_has_no_turtle_warning(self):
        with self.assertNoLogs('rdflib', level='WARNING'):
            self.assertEqual(d.decode_payload(XML, URL, 'OWL', URL)[0], '.owl')

    def test_xml_is_only_parsed_as_xml(self):
        formats = []
        original = Graph.parse
        def track(graph, *args, **kwargs):
            formats.append(kwargs.get('format'))
            return original(graph, *args, **kwargs)
        with patch.object(Graph, 'parse', track):
            d.decode_payload(XML, URL, 'OWL', URL)
        self.assertEqual(formats, ['xml'])

    def test_turtle(self):
        self.assertEqual(d.decode_payload(TTL, URL, 'OWL', URL)[0], '.ttl')

    def test_turtle_starting_with_iri(self):
        value = f'<{URL}> <{RDF}type> <{OWL}Ontology> .'.encode()
        self.assertEqual(d.decode_payload(value, URL, 'OWL', URL)[0], '.ttl')

    def test_wrong_content_type_does_not_override_syntax(self):
        self.assertEqual(d.decode_payload(XML, URL, 'OWL', URL, 'text/turtle')[0], '.owl')
        self.assertEqual(d.decode_payload(TTL, URL, 'OWL', URL, 'application/rdf+xml')[0], '.ttl')

    def test_utf8_bom(self):
        self.assertEqual(d.decode_payload(b'\xef\xbb\xbf' + XML, URL, 'OWL', URL)[0], '.owl')

    def test_identity_error_not_masked(self):
        with self.assertRaisesRegex(ValueError, 'IRI/versionIRI non corrispondente'):
            d.decode_payload(TTL, URL, 'OWL', URL + '/different')

    def test_version_iri_accepted(self):
        value = TTL[:-1] + f'; <{OWL}versionIRI> <{URL}/1.1> .'.encode()
        self.assertEqual(d.decode_payload(value, URL, 'OWL', URL + '/1.1')[0], '.ttl')

    def test_html_rejected(self):
        with self.assertRaisesRegex(ValueError, 'HTML'):
            d.decode_payload(b'<!DOCTYPE html><html><body>Not an ontology</body></html>', URL, 'OWL', URL)

    def test_malformed_xml_reports_xml_error(self):
        with self.assertRaisesRegex(ValueError, 'RDF non valido .xml.'):
            d.decode_payload(b'<?xml version="1.0"?><rdf:RDF', URL, 'OWL', URL)

    def test_xsd_includes_remain_relative_to_source(self):
        value = b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:test"><xs:include schemaLocation="child.xsd"/></xs:schema>'
        suffix, namespace, dependencies = d.decode_payload(value, 'https://schemas.opengis.net/test/root.xsd', 'XSD', 'urn:test')
        self.assertEqual((suffix, namespace), ('.xsd', 'urn:test'))
        self.assertEqual(dependencies[0]['url'], 'https://schemas.opengis.net/test/child.xsd')

    def test_unknown_redirect_host_still_rejected(self):
        with self.assertRaises(ValueError):
            d.allowed('https://not-approved.example/ontology.ttl', d.DEFAULT_HOSTS)


if __name__ == '__main__':
    unittest.main()
