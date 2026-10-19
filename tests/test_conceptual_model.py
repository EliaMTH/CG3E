"""Tests of scripts/conceptual_model.py on synthetic documents shaped like OGC 20-010."""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import conceptual_model as cm

DOCUMENT = '''<html><head><meta charset="utf-8"><title>CityGML Part 1</title></head><body>
<div><span>Approval Date:</span><span>2021-06-04</span></div>
<div>Version: 3.0.0 Additional Formats: PDF</div>
<h1 id="toc0">I. Abstract</h1>
<h1 id="toc6">6. Overview</h1>
<div id="_spaces"><h3>6.4.1. Spaces and Space Boundaries</h3></div>
<h1 id="toc7">7. CityGML UML Model</h1>
<h2 id="toc45">7.17. Building</h2>
<table id="req_building_boundaries" class="recommend"><thead><tr><th><p>Requirement 43</p></th></tr></thead>
<tbody><tr><td><p>/req/building/boundaries</p></td></tr><tr><td><p>Table 65 lists the allowed boundaries.</p></td></tr></tbody></table>
<p>Table 65 — Building space classes and their allowed thematic surface boundaries</p>
<table id="building-boundaries-table"><tr><th>Space class</th><th>Allowed space boundaries</th></tr>
<tr><td>Building</td><td><ul><li>Construction::AbstractConstructionSurface and all subclasses, i.e.<ul><li>Construction::RoofSurface</li><li>Construction::WallSurface</li></ul></li>
<li>Core::ClosureSurface</li><li>possible classes from ADEs</li></ul></td></tr>
<tr><td>BuildingFurniture</td><td><p>No boundaries allowed</p></td></tr></table>
<h1 id="toc47">8. CityGML Data Dictionary</h1>
<h2>8.17. Building</h2>
<div id="_building"><p>Table 666 — Metadata of Building (ApplicationSchema)</p>
<table><tr><th>Definition:</th><td>The Building package.</td></tr></table></div>
<div id="Building-section"><h4>8.17.1.3. Building</h4>
<p>Table 673 — Metadata of Building (TopLevelFeatureType)</p>
<table><tr><th>Definition:</th><td>A Building is a construction.</td></tr><tr><th>Subclass of:</th><td>AbstractBuilding</td></tr></table>
<p>Table 675 — Attributes of Building (TopLevelFeatureType)</p>
<table><tr><th>Attribute</th><th>Value type and multiplicity</th><th>Definition</th></tr>
<tr><td>roofType</td><td>RoofTypeValue [0..1]</td><td>Indicates the shape of the roof.</td></tr></table></div>
<div id="Color-section"><p>Table 237 — Metadata of Color (BasicType)</p>
<table><tr><th>Definition:</th><td>Color is a list of values.</td></tr><tr><th>Subclass of:</th><td>DoubleBetween0and1List</td></tr>
<tr><th>Constraint:</th><td><p><tt>lengthOfList</tt>:</p><pre>inv: list-&gt;size() = 3 or<br/>list-&gt;size() = 4</pre></td></tr>
<tr><th>Constraint:</th><td><p><tt>notEmpty</tt>:</p><pre>inv: list-&gt;notEmpty()</pre></td></tr>
<tr><th>Unknown label:</th><td>Not a constraint.</td></tr></table></div>
<div id="RelativeToTerrain-section"><p>Table 9 — Values of RelativeToTerrain (Enumeration)</p>
<table><tr><th>Literal value</th><th>Definition</th></tr><tr><td>entirelyAboveTerrain</td><td>Above.</td></tr></table></div>
</body></html>'''

XMI = '''<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmlns:xmi="http://schema.omg.org/spec/XMI/2.1" xmlns:uml="http://schema.omg.org/spec/UML/2.1">
<uml:Model><packagedElement xmi:type="uml:Class" xmi:id="B" name="Building"/>
<packagedElement xmi:type="uml:Class" xmi:id="P" name="BuildingPart"/>
<packagedElement xmi:type="uml:Association" xmi:id="A1">
  <ownedEnd xmi:type="uml:Property" name="buildingPart" aggregation="composite"><type xmi:idref="P"/></ownedEnd>
  <ownedEnd xmi:type="uml:Property" aggregation="none"><type xmi:idref="B"/></ownedEnd>
</packagedElement></uml:Model></xmi:XMI>'''


class DocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = Path(cls.tmp.name)/'doc.html'
        path.write_text(DOCUMENT, encoding='utf-8')
        cls.doc = cm.read_document(path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_metadata(self):
        self.assertEqual(self.doc['metadata']['approvalDate'], '2021-06-04')
        self.assertEqual(self.doc['metadata']['version'], '3.0.0')

    def test_class_separate_from_package(self):
        building = self.doc['classes']['Building']
        self.assertEqual(building['stereotype'], 'TopLevelFeatureType')
        self.assertEqual(building['definition'], 'A Building is a construction.')
        self.assertEqual(building['subclassOf'], ['AbstractBuilding'])
        self.assertEqual(building['anchor'], 'Building-section')
        self.assertIn('Building', self.doc['packages'])
        self.assertEqual(building['attributes']['roofType'], {'type': 'RoofTypeValue', 'multiplicity': '0..1',
                                                              'definition': 'Indicates the shape of the roof.'})

    def test_constraints_kept_as_a_list(self):
        color = self.doc['classes']['Color']
        self.assertEqual(color['constraints'], [
            {'name': 'lengthOfList', 'text': 'inv: list->size() = 3 or\nlist->size() = 4', 'table': 'Table 237'},
            {'name': 'notEmpty', 'text': 'inv: list->notEmpty()', 'table': 'Table 237'}])
        self.assertEqual(color['subclassOf'], ['DoubleBetween0and1List'])
        self.assertEqual(color['definition'], 'Color is a list of values.')
        self.assertEqual(self.doc['classes']['Building']['constraints'], [])

    def test_enumeration_values(self):
        self.assertEqual(self.doc['classes']['RelativeToTerrain']['values'], [{'value': 'entirelyAboveTerrain', 'definition': 'Above.'}])

    def test_boundaries(self):
        row = self.doc['boundaries']['Building']
        self.assertEqual(row['allowed'], [
            {'class': 'AbstractConstructionSurface', 'withSubclasses': True, 'listed': ['RoofSurface', 'WallSurface']},
            {'class': 'ClosureSurface', 'withSubclasses': False, 'listed': []}])
        self.assertTrue(row['ade'])
        self.assertEqual((row['table'], row['requirement']), ('Table 65', '/req/building/boundaries'))
        self.assertTrue(self.doc['boundaries']['BuildingFurniture']['none'])

    def test_requirements_modules_and_concepts(self):
        self.assertEqual(self.doc['requirements'], [{'kind': 'Requirement', 'title': 'Requirement 43', 'id': '/req/building/boundaries',
                                                     'module': 'building', 'text': ['Table 65 lists the allowed boundaries.'],
                                                     'anchor': 'req_building_boundaries'}])
        self.assertEqual(self.doc['modules'], {'Building': {'number': '7.17', 'anchor': 'toc45'}})
        self.assertEqual(self.doc['concepts'], [{'number': '6.4.1', 'title': 'Spaces and Space Boundaries', 'anchor': '_spaces', 'level': 3}])


class XmiTests(unittest.TestCase):
    def test_aggregation_by_owner_and_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'xmi.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr(cm.INTEGRATED, XMI)
            self.assertEqual(cm.read_xmi(path), {('Building', 'buildingPart'): 'composite'})


if __name__ == '__main__':
    unittest.main()
