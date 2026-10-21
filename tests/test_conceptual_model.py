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
<div id="_relationships"><h3>6.2.3. Relationships between CityGML objects</h3>
<p>Objects form hierarchies. Some feature types are marked with the stereotype «TopLevelFeatureType». Only top-level features are allowed as direct members of a city model. Tools filter by them.</p></div>
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
<div id="TransformationMatrix2x2-section"><p>Table 230 — Metadata of TransformationMatrix2×2 (BasicType)</p>
<table><tr><th>Definition:</th><td>A 2 by 2 matrix.</td></tr><tr><th>Subclass of:</th><td>DoubleList</td></tr></table></div>
<div id="RelativeToTerrain-section"><p>Table 9 — Values of RelativeToTerrain (Enumeration)</p>
<table><tr><th>Literal value</th><th>Definition</th></tr><tr><td>entirelyAboveTerrain</td><td>Above.</td></tr></table></div>
</body></html>'''

# Shaped like the export of Enterprise Architect: the multiplicity '*' of an association end is written as
# lower -1 / upper -1 in the model and as '*' in the connector of the extension, which repeats some identifiers.
XMI = '''<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmlns:xmi="http://schema.omg.org/spec/XMI/2.1" xmlns:uml="http://schema.omg.org/spec/UML/2.1">
<uml:Model xmi:type="uml:Model" name="EA_Model">
<packagedElement xmi:type="uml:Class" xmi:id="B" name="Building">
  <ownedAttribute xmi:type="uml:Property" xmi:id="B_roof" name="roofType"><type xmi:idref="R"/>
    <lowerValue xmi:type="uml:LiteralInteger" value="0"/><upperValue xmi:type="uml:LiteralInteger" value="1"/></ownedAttribute>
  <ownedAttribute xmi:type="uml:Property" xmi:id="B_part" name="buildingPart" association="A1" aggregation="composite"><type xmi:idref="P"/>
    <lowerValue xmi:type="uml:LiteralUnlimitedNatural" value="-1"/><upperValue xmi:type="uml:LiteralUnlimitedNatural" value="-1"/></ownedAttribute>
  <generalization xmi:type="uml:Generalization" xmi:id="G1" general="AB"/>
</packagedElement>
<packagedElement xmi:type="uml:Class" xmi:id="AB" name="AbstractBuilding">
  <generalization xmi:type="uml:Generalization" xmi:id="G2" general="OUTSIDE"/>
</packagedElement>
<packagedElement xmi:type="uml:Class" xmi:id="P" name="BuildingPart"/>
<packagedElement xmi:type="uml:Association" xmi:id="A1"><memberEnd xmi:idref="B_part"/><memberEnd xmi:idref="A1_src"/>
  <ownedEnd xmi:type="uml:Property" xmi:id="A1_src" association="A1" aggregation="none"><type xmi:idref="B"/></ownedEnd></packagedElement>
<packagedElement xmi:type="uml:DataType" xmi:id="S" name="GenericAttributeSet">
  <ownedAttribute xmi:type="uml:Property" xmi:id="S_ga" name="genericAttribute" association="A2" aggregation="composite"><type xmi:idref="GA"/>
    <lowerValue xmi:type="uml:LiteralInteger" value="1"/><upperValue xmi:type="uml:LiteralUnlimitedNatural" value="-1"/></ownedAttribute>
</packagedElement>
<packagedElement xmi:type="uml:DataType" xmi:id="GA" name="AbstractGenericAttribute"/>
<packagedElement xmi:type="uml:Association" xmi:id="A2"><memberEnd xmi:idref="S_ga"/><memberEnd xmi:idref="A2_src"/>
  <ownedEnd xmi:type="uml:Property" xmi:id="A2_src" association="A2" aggregation="none"><type xmi:idref="S"/></ownedEnd></packagedElement>
<packagedElement xmi:type="uml:Class" xmi:id="G" name="CityObjectGroup">
  <ownedAttribute xmi:type="uml:Property" xmi:id="G_member" name="groupMember" association="R1" aggregation="shared"><type xmi:idref="P"/>
    <lowerValue xmi:type="uml:LiteralUnlimitedNatural" value="-1"/><upperValue xmi:type="uml:LiteralUnlimitedNatural" value="-1"/></ownedAttribute>
</packagedElement>
<packagedElement xmi:type="uml:AssociationClass" xmi:id="R1" name="Role"><memberEnd xmi:idref="G_member"/><memberEnd xmi:idref="R1_src"/>
  <ownedEnd xmi:type="uml:Property" xmi:id="R1_src" association="R1" aggregation="none"><type xmi:idref="G"/></ownedEnd>
  <ownedAttribute xmi:type="uml:Property" xmi:id="R1_role" name="role">
    <lowerValue xmi:type="uml:LiteralInteger" value="0"/><upperValue xmi:type="uml:LiteralInteger" value="1"/></ownedAttribute>
</packagedElement>
</uml:Model>
<xmi:Extension extender="Enterprise Architect"><connectors>
  <connector xmi:idref="A1"><source xmi:idref="B"><model name="Building"/><role/><type multiplicity="1" aggregation="composite"/></source>
    <target xmi:idref="P"><model name="BuildingPart"/><role name="buildingPart"/><type multiplicity="*" aggregation="none"/></target></connector>
  <connector xmi:idref="A2"><source xmi:idref="S"><model name="GenericAttributeSet"/><role/><type multiplicity="0..1" aggregation="composite"/></source>
    <target xmi:idref="GA"><model name="AbstractGenericAttribute"/><role name="genericAttribute"/><type multiplicity="1..*" aggregation="none"/></target></connector>
  <connector xmi:idref="C_R1"><source xmi:idref="G"><model name="CityObjectGroup"/><role/><type multiplicity="*" aggregation="shared"/></source>
    <target xmi:idref="P"><model name="BuildingPart"/><role name="groupMember"/><type multiplicity="*" aggregation="none"/></target>
    <extendedProperties associationclass="R1"/></connector>
</connectors><diagrams><Association xmi:id="A1"/><Generalization xmi:id="G1"/></diagrams></xmi:Extension></xmi:XMI>'''


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

    def test_anchor_of_a_name_with_multiplication_sign(self):
        matrix = self.doc['classes']['TransformationMatrix2×2']
        self.assertEqual((matrix['anchor'], matrix['subclassOf']), ('TransformationMatrix2x2-section', ['DoubleList']))

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
        self.assertEqual(self.doc['concepts'], [{'number': '6.2.3', 'title': 'Relationships between CityGML objects', 'anchor': '_relationships', 'level': 3},
                                                {'number': '6.4.1', 'title': 'Spaces and Space Boundaries', 'anchor': '_spaces', 'level': 3}])

    def test_sentence_on_the_members_of_a_city_model(self):
        self.assertEqual(self.doc['topLevelMembers'], {'number': '6.2.3', 'title': 'Relationships between CityGML objects', 'anchor': '_relationships',
                                                       'text': 'Only top-level features are allowed as direct members of a city model.'})


class XmiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'xmi.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr(cm.INTEGRATED, XMI)
            cls.model = cm.read_xmi(path)

    def test_members_by_owner_and_name(self):
        self.assertEqual(self.model['members'], {
            ('Building', 'roofType'): {'multiplicity': '0..1'},
            # '*' in the model, lower -1 in the XMI: read from the connector, as drawn
            ('Building', 'buildingPart'): {'multiplicity': '0..*', 'aggregation': 'composite'},
            ('GenericAttributeSet', 'genericAttribute'): {'multiplicity': '1..*', 'aggregation': 'composite'},
            # End of an association class; its own attribute 'role' is an attribute, not an end
            ('CityObjectGroup', 'groupMember'): {'multiplicity': '0..*', 'aggregation': 'shared', 'associationClass': 'Role'},
            ('Role', 'role'): {'multiplicity': '0..1'}})
        self.assertEqual(self.model['associationClasses'], {'Role': [('CityObjectGroup', 'groupMember')]})

    def test_generalizations(self):
        generalizations = self.model['generalizations']
        self.assertEqual(generalizations['Building'], {'parents': ['AbstractBuilding'], 'unresolved': 0})
        # A superclass outside the file (an ISO class) stays unresolved, without a name
        self.assertEqual(generalizations['AbstractBuilding'], {'parents': [], 'unresolved': 1})
        self.assertEqual(generalizations['BuildingPart'], {'parents': [], 'unresolved': 0})

    def test_multiplicity_notation(self):
        self.assertEqual([cm.multiplicity(n) for n in ('*', '1', '0..1', '1..*', '', None)],
                         ['0..*', '1..1', '0..1', '1..*', None, None])


if __name__ == '__main__':
    unittest.main()
