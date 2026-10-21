"""Smoke test of the HTML/CSS/JS catalog in Chromium, no network calls.

Loads page, styles, catalog, code list dictionary and script as in-memory
content; the File System Access API is replaced by a stub that records what
Save writes. The persistence of display options is checked on the real
index.html opened from file://. Writes docs/screenshot-desktop.png and
docs/screenshot-mobile.png.
"""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ['data/catalog.js', 'codelists/codelists.default.js', 'codelists/codelists.js', 'assets/app.js']

template = (ROOT/'index.html').read_text(encoding='utf-8')
for sheet in ('assets/styles.css', 'assets/styles-dark.css'):
    template = template.replace(f'<link rel="stylesheet" href="{sheet}">',
                                '<style>'+(ROOT/sheet).read_text(encoding='utf-8')+'</style>')
for script in SCRIPTS:
    template = template.replace(f'<script defer src="{script}"></script>', '')

STUB = '''window.__written = null;
window.showSaveFilePicker = async () => ({name: 'codelists.js',
  queryPermission: async () => 'granted', requestPermission: async () => 'granted',
  createWritable: async () => ({write: async text => { window.__written = text; }, close: async () => {}})});'''
# The write waits until the test calls window.__release().
DEFERRED = STUB.replace('window.__written = text;', 'window.__written = text; await new Promise(r => { window.__release = r; });') \
    + 'window.__release = null;'
FAILING = STUB.replace('window.__written = text;', "throw new Error('disco pieno');")


def load(page):
    page.set_content(template)
    for script in SCRIPTS:
        page.add_script_tag(content=(ROOT/script).read_text(encoding='utf-8'))


def search(page, text, expected):
    page.locator('#search').fill(text)
    expect(page.locator('.concept-item .item-name').first).to_contain_text(expected)


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    errors = []
    page = browser.new_page(viewport={'width': 1365, 'height': 920}, accept_downloads=True)
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    load(page)
    expect(page.locator('h1')).to_have_text('Building')
    expect(page.locator('#catalog-version')).to_have_text('CityGML 3.0.0 (OGC 21-006r2)')
    expect(page.locator('#codelist-count')).to_have_text('44/140')
    assert page.locator('#family option').count() == 3
    expect(page.locator('.item-hint')).to_have_count(0)

    # Categories and filters
    page.locator('#filters-btn').click()
    page.locator('#category').select_option('boundary')
    page.locator('#only-concrete').check()
    expect(page.locator('#results-count')).to_have_text('24')
    page.locator('#category').select_option('space')
    expect(page.locator('#results-count')).to_have_text('42')
    page.locator('#only-concrete').uncheck()
    page.locator('#category').select_option('codelist')
    expect(page.locator('#results-count')).to_have_text('140')
    page.locator('#category').select_option('codelistFilled')
    expect(page.locator('#results-count')).to_have_text('44')
    page.locator('#category').select_option('topLevel')
    expect(page.locator('#results-count')).to_have_text('20')
    page.locator('#category').select_option('')
    page.locator('#filters-btn').click()

    # Building: badges, inheritance, boundaries, code list values
    expect(page.locator('.badge', has_text='Spazio')).to_have_count(1)
    expect(page.locator('.badge', has_text='Primo livello')).to_have_count(1)
    expect(page.locator('.chain')).to_contain_text('gml:AbstractFeature')
    expect(page.locator('section', has_text='Superfici di confine ammesse')).to_contain_text('RoofSurface')
    expect(page.locator('section', has_text='Valori delle code list')).to_contain_text('gabled roof')
    page.locator('.tab', has_text='Standard').click()
    expect(page.locator('#tab-content')).to_contain_text('TopLevelFeatureType')
    expect(page.locator('#tab-content')).to_contain_text('/req/building/boundaries')

    # Code list page: values, usage, edit and revert
    search(page, 'RoofTypeValue', 'RoofTypeValue')
    page.locator('.concept-item').first.click()
    expect(page.locator('h1')).to_have_text('RoofTypeValue')
    page.locator('.tab', has_text='Panoramica').click()
    expect(page.locator('.cl-table tbody tr')).to_have_count(14)
    expect(page.locator('#tab-content')).to_contain_text('codeSpace="https://www.sig3d.org/codelists/citygml/building/3.0/RoofTypeValue">1000')
    expect(page.locator('#tab-content')).to_contain_text('Usata da')
    # The usage example follows the input at once, keeps the focus in the field, and is XML: & is escaped
    page.locator('[data-cl-field="code"]').first.fill('A&B')
    expect(page.locator('#cl-usage .source-block')).to_contain_text('RoofTypeValue">A&amp;B</bldg:roofType>')
    expect(page.locator('[data-cl-field="code"]').first).to_be_focused()
    expect(page.locator('#cl-state')).to_contain_text('modificata')
    page.locator('[data-cl-action="add"]').click()
    expect(page.locator('.cl-table tbody tr')).to_have_count(15)
    page.locator('[data-cl-field="code"]').last.fill('9000')
    expect(page.locator('#codelist-count')).to_contain_text('•')
    page.locator('[data-cl-action="revert"]').click()
    expect(page.locator('.cl-table tbody tr')).to_have_count(14)
    expect(page.locator('#codelist-count')).to_have_text('44/140')
    # The values that follow the codeSpace of the list follow its change; the export of the card has the local values
    page.locator('[data-cl-field="codeSpace"]').fill('https://example.org/roofs.xml')
    expect(page.locator('#cl-usage .source-block')).to_contain_text('codeSpace="https://example.org/roofs.xml"')
    with page.expect_download() as download:
        page.locator('[data-action="export"]').click()
    local = json.loads(Path(download.value.path()).read_text(encoding='utf-8'))['localCodeList']
    assert (local['normative'], local['saved'], len(local['values'])) == (False, False, 14), local
    assert {v['codeSpace'] for v in local['values']} == {'https://example.org/roofs.xml'}
    page.locator('[data-cl-action="revert"]').click()
    expect(page.locator('#codelist-count')).to_have_text('44/140')

    # Save through the File System Access API stub: same bytes as codelists.js
    page.evaluate(STUB)
    page.locator('[data-cl-action="save"]').click()
    page.wait_for_function('window.__written !== null')
    assert page.evaluate('window.__written') == (ROOT/'codelists/codelists.js').read_text(encoding='utf-8')

    # An edited value appears in the classes that use the code list, and in search
    page.locator('[data-cl-field="name"]').first.fill('tetto piano')
    page.locator('#home-link').click()
    expect(page.locator('section', has_text='Valori delle code list')).to_contain_text('tetto piano')
    search(page, 'tetto piano', 'RoofTypeValue')
    expect(page.locator('.item-hint').first).to_contain_text('tetto piano')
    page.evaluate('window.__written = null')
    search(page, 'RoofTypeValue', 'RoofTypeValue')
    page.locator('.concept-item').first.click()
    page.locator('[data-cl-action="save"]').click()
    page.wait_for_function('window.__written !== null')
    assert 'tetto piano' in page.evaluate('window.__written')
    expect(page.locator('#codelist-count')).to_have_text('44/140')

    # Edits made while the file is being written stay unsaved; Save and Reset wait for the write
    page.evaluate(DEFERRED)
    page.locator('[data-cl-action="save"]').click()
    page.wait_for_function('window.__release !== null')
    expect(page.locator('[data-cl-action="save"]')).to_be_disabled()
    expect(page.locator('[data-cl-action="reset"]')).to_be_disabled()
    page.locator('[data-cl-field="name"]').first.fill('durante il salvataggio')
    page.evaluate('window.__release()')
    expect(page.locator('[data-cl-action="save"]')).to_be_enabled()
    assert 'durante il salvataggio' not in page.evaluate('window.__written')
    expect(page.locator('#codelist-count')).to_contain_text('•')
    expect(page.locator('[data-cl-field="name"]').first).to_have_value('durante il salvataggio')
    page.evaluate(STUB)
    page.locator('[data-cl-action="save"]').click()
    page.wait_for_function('window.__written !== null')
    assert 'durante il salvataggio' in page.evaluate('window.__written')
    expect(page.locator('#codelist-count')).to_have_text('44/140')

    # A failed write keeps the edits unsaved
    page.locator('[data-cl-field="name"]').first.fill('non salvato')
    page.evaluate(FAILING)
    page.locator('[data-cl-action="save"]').click()
    expect(page.locator('#toast')).to_contain_text('Salvataggio non riuscito: disco pieno')
    expect(page.locator('#codelist-count')).to_contain_text('•')
    expect(page.locator('[data-cl-action="save"]')).to_be_enabled()
    page.evaluate(STUB)

    # A Reset whose write fails shows the initial state at once: table and data agree, editing goes on
    page.locator('[data-cl-action="add"]').click()
    expect(page.locator('.cl-table tbody tr')).to_have_count(15)
    page.evaluate(FAILING)
    page.once('dialog', lambda dialog: dialog.accept())
    page.locator('[data-cl-action="reset"]').click()
    expect(page.locator('#toast')).to_contain_text('Salvataggio non riuscito')
    expect(page.locator('.cl-table tbody tr')).to_have_count(14)
    page.locator('[data-cl-field="code"]').last.fill('1999')
    expect(page.locator('#codelist-count')).to_contain_text('•')
    page.evaluate(STUB)

    # Reset writes the initial state back (confirm dialog accepted)
    page.evaluate('window.__written = null')
    page.once('dialog', lambda dialog: dialog.accept())
    page.locator('[data-cl-action="reset"]').click()
    page.wait_for_function('window.__written !== null')
    assert 'tetto piano' not in page.evaluate('window.__written')
    assert page.evaluate('window.__written') == (ROOT/'codelists/codelists.js').read_text(encoding='utf-8')

    # Without the File System Access API Save downloads the file
    page.evaluate('window.showSaveFilePicker = undefined')
    with page.expect_download() as download:
        page.locator('[data-cl-action="save"]').click()
    assert download.value.suggested_filename == 'codelists.js'

    # Search by value and the Code list button
    search(page, 'footpath', 'TrafficAreaFunctionValue')
    page.locator('#search').fill('')
    page.locator('#codelists-btn').click()
    expect(page.locator('h1')).to_have_text('Code list')
    expect(page.locator('#content tbody tr')).to_have_count(140)
    page.locator('[data-cl-filter="values"]').click()
    expect(page.locator('#content tbody tr')).to_have_count(44)
    page.locator('[data-cl-filter="missing"]').click()
    expect(page.locator('#content tbody tr')).to_have_count(96)
    expect(page.locator('#content')).to_contain_text('HollowSpaceUsageValue')
    # Values with a codeSpace of their own show it under the code
    search(page, 'TrafficAreaFunctionValue', 'TrafficAreaFunctionValue')
    page.locator('.concept-item').first.click()
    expect(page.locator('.cl-table tbody tr').first).to_contain_text('https://ogc.org/citygml/3.0/codelists/gml/')
    # A value keeps its own codeSpace while the codeSpace of the list is edited, also when the two coincide for a
    # moment (paste, typing, deletion); a value added to the list follows it; the export has the expected URIs
    driving = 'https://ogc.org/citygml/3.0/codelists/gml/driving_lane'
    expect(page.locator('.cl-table tbody tr').first).to_contain_text(driving)
    page.locator('[data-cl-action="add"]').click()
    page.locator('[data-cl-field="code"]').last.fill('9000')
    codespace = page.locator('[data-cl-field="codeSpace"]')
    codespace.fill(driving)
    page.locator('#home-link').click()
    search(page, 'TrafficAreaFunctionValue', 'TrafficAreaFunctionValue')
    page.locator('.concept-item').first.click()
    expect(page.locator('.cl-table tbody tr').first).to_contain_text(driving)
    expect(page.locator('.cl-table tbody tr').last).not_to_contain_text('https://')
    codespace.press('End')
    codespace.press_sequentially('-v2')
    codespace.press('Backspace')
    codespace.press_sequentially('3')
    with page.expect_download() as download:
        page.locator('[data-action="export"]').click()
    local = json.loads(Path(download.value.path()).read_text(encoding='utf-8'))['localCodeList']
    initial = page.evaluate("window.CITYGML_CODELISTS.codeLists.TrafficAreaFunctionValue.values.map(v => v.codeSpace)")
    assert local['codeSpace'] == driving + '-v3', local['codeSpace']
    assert [v['codeSpace'] for v in local['values']] == initial + [driving + '-v3']
    page.locator('[data-cl-action="revert"]').click()
    expect(page.locator('#codelist-count')).to_have_text('44/140')

    # Classes without their own XSD type: usage example and encoding
    search(page, 'TemporalRelationTypeValue', 'TemporalRelationTypeValue')
    page.locator('.concept-item').first.click()
    expect(page.locator('.badge', has_text='Senza tipo XSD dedicato')).to_have_count(1)
    expect(page.locator('#tab-content')).to_contain_text('Nessuna proprietà degli schemi XSD ha questa code list come tipo: manca')
    expect(page.locator('#tab-content')).not_to_contain_text('Aggiungi almeno un valore')
    page.locator('.tab', has_text='Sorgente').click()
    expect(page.locator('#tab-content')).to_contain_text('il catalogo non registra come la codifica la rappresenta')
    search(page, 'HollowSpaceUsageValue', 'HollowSpaceUsageValue')
    page.locator('.concept-item').first.click()
    expect(page.locator('#tab-content')).to_contain_text('Aggiungi almeno un valore')
    search(page, 'RoofTypeValue', 'RoofTypeValue')
    page.locator('.concept-item').first.click()
    page.locator('.tab', has_text='Sorgente').click()
    expect(page.locator('#tab-content')).to_contain_text('roofType')
    expect(page.locator('#tab-content')).to_contain_text('gml:CodeType')
    expect(page.locator('#tab-content')).not_to_contain_text('non rappresenta')

    # Conceptual model: generalization, members of unions and basic types, constraints, encoding forms
    search(page, 'MeasureOrNilReasonList', 'MeasureOrNilReasonList')
    page.locator('.concept-item').first.click()
    expect(page.locator('.inheritance-box')).to_contain_text('GENERALIZZAZIONE NEL MODELLO CONCETTUALE')
    expect(page.locator('.inheritance-box')).to_contain_text('DoubleOrNilReasonList')
    expect(page.locator('section', has_text='Membri nel modello concettuale').locator('tbody tr')).to_have_count(2)
    search(page, 'CityModelMember', 'CityModelMember')
    page.locator('.concept-item').first.click()
    expect(page.locator('#tab-content')).to_contain_text('Unione: un valore è uno solo dei membri')
    expect(page.locator('section', has_text='Membri nel modello concettuale').locator('tbody tr')).to_have_count(5)
    expect(page.locator('.tab', has_text='Proprietà').locator('.count')).to_have_text('5')
    search(page, 'PointCloud', 'PointCloud')
    page.locator('.concept-item').first.click()
    expect(page.locator('section', has_text='Vincoli del modello concettuale')).to_contain_text('inlineOrExternalPointCloud')
    search(page, 'Role', 'Role')
    page.locator('.concept-item').first.click()
    expect(page.locator('section', has_text='Relazioni').locator('.badge', has_text='solo riferimento')).to_have_count(1)
    expect(page.locator('#tab-content')).to_contain_text('Describes the role the city object plays within the CityObjectGroup. (OGC 20-010)')
    page.locator('.tab', has_text='Standard').click()
    expect(page.locator('#tab-content')).to_contain_text('Membri nel modello concettuale')
    expect(page.locator('summary', has_text='Requisiti della codifica GML del modulo CityObjectGroup')).to_have_count(1)
    expect(page.locator('summary', has_text='Requisiti globali della codifica GML')).to_have_count(1)
    page.locator('.tab', has_text='Panoramica').click()
    page.locator('[data-property]', has_text='groupMember').first.click()
    expect(page.locator('#modal-body')).to_contain_text('/req/cityobjectgroup/reference B')
    page.locator('#close-modal').click()
    # Role is the association class of CityObjectGroup.groupMember: linked both ways in the UML model
    page.locator('.tab', has_text='Connessioni').click()
    expect(page.locator('section', has_text='Classe di associazione')).to_contain_text('il ruolo groupMember di CityObjectGroup')
    search(page, 'CityObjectGroup', 'CityObjectGroup')
    page.locator('.concept-item').first.click()
    page.locator('[data-level="uml"]').click()
    expect(page.locator('.uml-members tr').filter(has=page.locator('.prop-name', has_text=re.compile('^groupMember$')))).to_contain_text(
        'qualificato dalla classe di associazione Role')
    page.locator('[data-level="gml"]').click()
    search(page, 'CityModel', 'CityModel')
    page.locator('.concept-item').first.click()
    page.locator('.tab', has_text='Standard').click()
    expect(page.locator('tr', has_text='cityModelMember')).to_contain_text('alternative dell’unione come proprietà: cityObjectMember')

    # Property search: declaring class, concrete classes, class filters do not hide properties
    search(page, 'dateOfConstruction', 'dateOfConstruction')
    expect(page.locator('.property-item .item-hint')).to_have_text(['in AbstractConstruction (astratta)'])
    page.locator('.property-item').first.click()
    expect(page.locator('h1')).to_have_text('AbstractConstruction')
    expect(page.locator('#modal-title')).to_have_text('dateOfConstruction')
    expect(page.locator('#modal-body')).to_contain_text('Classi concrete con la proprietà')
    expect(page.locator('#modal-body')).to_contain_text('BuildingPart')
    expect(page.locator('#modal-body')).to_contain_text('Dettagli della codifica GML (schemi XSD)')
    page.locator('#close-modal').click()
    # The same result opens the details again; Back and Forward close and reopen them with the URL
    page.locator('.property-item').first.click()
    expect(page.locator('#modal-title')).to_have_text('dateOfConstruction')
    expect(page.locator('#modal')).to_be_visible()
    page.evaluate('history.back()')
    expect(page.locator('#modal')).to_be_hidden()
    assert 'prop=' not in page.evaluate('location.hash')
    page.evaluate('history.forward()')
    expect(page.locator('#modal')).to_be_visible()
    expect(page.locator('#modal-title')).to_have_text('dateOfConstruction')
    page.locator('#close-modal').click()
    page.locator('#filters-btn').click()
    page.locator('#only-concrete').check()
    search(page, 'lod2MultiSurface', 'lod2MultiSurface')
    expect(page.locator('.property-item .item-hint')).to_have_text(['in AbstractSpace (astratta)', 'in AbstractThematicSurface (astratta)'])
    page.locator('#only-concrete').uncheck()
    page.locator('#filters-btn').click()
    search(page, 'boundary', 'boundary')
    expect(page.locator('.property-item .item-hint').first).to_have_text('in AbstractSpace (astratta)')
    search(page, 'Building', 'Building')

    # Reading level: conceptual model and GML encoding of the same class, in the URL and in the export
    page.locator('#home-link').click()
    page.locator('[data-level="uml"]').click()
    expect(page).to_have_url(re.compile(r'tab=overview&level=uml$'))
    expect(page.locator('#tab-content')).to_contain_text('Livello: modello concettuale (OGC 20-010)')
    # Multiplicity of the UML model ('*' in figure 64), with the value of the data dictionary beside it
    part = page.locator('.uml-members tr').filter(has=page.locator('.prop-name', has_text=re.compile('^buildingPart$')))
    expect(part.locator('.multiplicity')).to_have_text('0..*')
    expect(part.locator('.badge', has_text='dizionario: 1..*')).to_have_count(1)
    page.locator('.tab', has_text='Proprietà').click()
    expect(page).to_have_url(re.compile(r'tab=properties&level=uml$'))
    with page.expect_download() as download:
        page.locator('[data-action="export"]').click()
    exported = json.loads(Path(download.value.path()).read_text(encoding='utf-8'))
    assert exported['level'] == 'uml'
    member = next(m for m in exported['visibleProperties'] if m['name'] == 'buildingPart')
    assert (member['multiplicity'], member['dictionaryMultiplicity']) == ('0..*', '1..*'), member
    page.locator('[data-level="gml"]').click()
    expect(page).to_have_url(re.compile(r'tab=properties$'))
    expect(page.locator('#tab-content tr').filter(has=page.locator('.prop-name-button', has_text=re.compile('^buildingPart$')))).to_contain_text('0..*')
    with page.expect_download() as download:
        page.locator('[data-action="export"]').click()
    assert json.loads(Path(download.value.path()).read_text(encoding='utf-8'))['level'] == 'gml'
    page.locator('.tab', has_text='Panoramica').click()

    # The same relation reads the same in both directions: buildingPart is a composition also seen from BuildingPart
    search(page, 'BuildingPart', 'BuildingPart')
    page.locator('.concept-item').first.click()
    page.locator('.tab', has_text='Connessioni').click()
    expect(page.locator('.connection-card small', has_text=re.compile('^buildingPart · '))).to_have_text('buildingPart · composizione · 0..*')
    # A generalization of the UML model that the data dictionary omits (figure 37)
    search(page, 'StringAttribute', 'StringAttribute')
    page.locator('.concept-item').first.click()
    page.locator('[data-level="uml"]').click()
    expect(page.locator('.inheritance-box')).to_contain_text('AbstractGenericAttribute')
    expect(page.locator('.inheritance-box')).to_contain_text('«Subclass of: None»')
    page.locator('[data-level="gml"]').click()
    # A restriction keeps the attributes of its base type: uom, required, of gml:QuantityExtent
    page.evaluate("location.hash = 'node=' + encodeURIComponent('xsd:{http://www.opengis.net/gml/3.2}element:QuantityExtent') + '&tab=properties'")
    expect(page.locator('h1')).to_have_text('QuantityExtent')
    expect(page.locator('#tab-content tr', has=page.locator('.prop-name-button', has_text=re.compile('^uom$')))).to_contain_text('MeasureOrNilReasonListType')
    page.locator('#home-link').click()

    # Destinations of boundary in the context of the visited class, apart from the schema candidates
    for name, expected, absent in [('BuildingUnit', 'Ammesse per BuildingUnit', 'RoofSurface'),
                                   ('PlantCover', 'non ammette superfici di confine per PlantCover', None)]:
        search(page, name, name)
        page.locator('.concept-item').first.click()
        page.locator('.tab', has_text='Proprietà').click()
        page.locator('.prop-name-button', has_text=re.compile('^boundary$')).first.click()
        expect(page.locator('.destinations > p').first).to_contain_text(expected)
        if absent:
            expect(page.locator('.destinations > p').first).not_to_contain_text(absent)
        expect(page.locator('.destinations summary')).to_contain_text('Elementi sostituibili negli schemi')
        page.locator('#close-modal').click()

    # TINRelief.tin, an anonymous property type towards gml:TriangulatedSurface, is among the geometries
    search(page, 'TINRelief', 'TINRelief')
    page.locator('.concept-item').first.click()
    page.locator('.tab', has_text='Proprietà').click()
    page.locator('.segment [data-kind="geometry"]').click()
    expect(page.locator('#property-results .prop-name-button', has_text=re.compile('^tin$'))).to_have_count(1)
    # The stereotype «TopLevelFeatureType», with the meaning given by OGC 20-010, and apart from it the member
    # of CityModelMember (data dictionary) and of CityModel (schemas) that admits the class
    row = lambda label: page.locator('.metadata-grid dt', has_text=label).locator('xpath=following-sibling::dd[1]')
    for ns, name, top, member, diverges in [
            ('http://www.opengis.net/citygml/building/3.0', 'Building', 'Sì: stereotipo «TopLevelFeatureType», uno dei componenti principali', 'cityObjectMember', False),
            ('http://www.opengis.net/citygml/appearance/3.0', 'Appearance', 'No: non ha lo stereotipo «TopLevelFeatureType»', 'appearanceMember', True),
            ('http://www.opengis.net/citygml/versioning/3.0', 'Version', 'No', 'versionMember', True),
            ('http://www.opengis.net/citygml/versioning/3.0', 'VersionTransition', 'No', 'versionTransitionMember', True),
            ('http://www.opengis.net/citygml/construction/3.0', 'WallSurface', 'No', 'cityObjectMember', True)]:
        page.evaluate(f"location.hash = 'node=' + encodeURIComponent('xsd:{{{ns}}}element:{name}') + '&tab=standard'")
        expect(page.locator('h1')).to_have_text(name)
        expect(row('Primo livello')).to_contain_text(top)
        members = row('Membro diretto di un CityModel')
        expect(members.locator('code').first).to_have_text(member)
        expect(members).to_contain_text('featureMember')
        expect(members).to_contain_text(f'core:{member}')
        expect(members).to_contain_text('«Only top-level features are allowed as direct members of a city model.»')
        expect(members.get_by_text('non coincidono')).to_have_count(1 if diverges else 0)
    # The reading level survives the Code list overview
    page.locator('#home-link').click()
    page.locator('[data-level="uml"]').click()
    page.locator('#codelists-btn').click()
    expect(page).to_have_url(re.compile(r'view=codelists&level=uml$'))
    page.locator('#home-link').click()
    expect(page).to_have_url(re.compile(r'level=uml$'))
    expect(page.locator('#tab-content')).to_contain_text('Livello: modello concettuale (OGC 20-010)')
    page.locator('[data-level="gml"]').click()
    page.locator('.tab', has_text='Panoramica').click()

    # Display options: theme and text size
    page.locator('#options-btn').click()
    expect(page.locator('#options-panel')).to_be_visible()
    page.locator('[data-theme-choice="dark"]').click()
    assert page.evaluate('document.documentElement.dataset.theme') == 'dark'
    background = page.evaluate('getComputedStyle(document.body).backgroundColor')
    assert sum(int(v) for v in background[background.index('(')+1:-1].split(',')[:3]) < 150, background
    page.locator('[data-font-step="1"]').click()
    expect(page.locator('#font-scale-value')).to_have_text('110%')
    assert page.evaluate('getComputedStyle(document.body).fontSize') == '15.4px'
    page.keyboard.press('Escape')
    expect(page.locator('#options-panel')).to_be_hidden()
    page.locator('#options-btn').click()
    page.locator('[data-theme-choice="light"]').click()
    page.locator('[data-font-step="-1"]').click()
    page.locator('h1').click()
    expect(page.locator('#options-panel')).to_be_hidden()
    assert page.evaluate('document.documentElement.dataset.theme') == 'light'
    assert page.evaluate('getComputedStyle(document.body).fontSize') == '14px'

    # Tabs and dialogs
    search(page, 'BuildingPart', 'BuildingPart')
    page.locator('.concept-item').first.click()
    expect(page.locator('h1')).to_have_text('BuildingPart')
    for tab in ('Proprietà', 'Connessioni', 'Standard', 'Sorgente'):
        page.locator('.tab', has_text=tab).click()
        expect(page.locator('.tab.active')).to_contain_text(tab)
    page.locator('#sources-btn').click()
    expect(page.locator('#modal-title')).to_have_text('Sorgenti')
    expect(page.locator('#modal-body')).to_contain_text('consultabile offline')
    expect(page.locator('#modal-body')).to_contain_text('Modello concettuale')
    expect(page.locator('#modal-body tr', has_text='Attributi e ruoli')).to_contain_text('3 senza corrispondenza')
    expect(page.locator('#modal-body')).to_contain_text('Codifica GML')
    expect(page.locator('#modal-body tr', has_text='codifica GML (Parte 2)')).to_contain_text('43 requisiti')
    expect(page.locator('#modal-body')).to_contain_text('divergono su 78 molteplicità e 10 generalizzazioni')
    expect(page.locator('#modal-body tr', has_text='Generalizzazioni')).to_contain_text('dizionario 123 · modello UML 132')
    expect(page.locator('#modal-body')).to_contain_text('Solo segnaposto')
    page.locator('#close-modal').click()
    page.locator('#about-btn').click()
    expect(page.locator('#modal-title')).to_have_text('Come leggere il catalogo')
    expect(page.locator('#modal-body')).to_contain_text('Spaces and Space Boundaries')
    expect(page.locator('#modal-body')).to_contain_text('dizionario locale')
    page.locator('#close-modal').click()
    page.locator('#search').fill('')
    page.locator('#home-link').click()
    expect(page.locator('h1')).to_have_text('Building')
    page.evaluate("document.querySelector('#content').scrollTop = 0")
    page.screenshot(path=str(ROOT/'docs/screenshot-desktop.png'))

    # Preferences persist across reloads of the real file:// page
    real = browser.new_page()
    real.on('pageerror', lambda exc: errors.append(str(exc)))
    real.goto((ROOT/'index.html').as_uri())
    real.locator('#options-btn').click()
    real.locator('[data-theme-choice="dark"]').click()
    real.locator('[data-font-step="1"]').click()
    real.reload()
    expect(real.locator('h1')).to_have_text('Building')
    assert real.evaluate('document.documentElement.dataset.theme') == 'dark'
    assert real.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--font-scale').trim()") == '1.1'
    real.evaluate('localStorage.clear()')
    real.close()

    mobile = browser.new_page(viewport={'width': 390, 'height': 844}, is_mobile=True)
    mobile.on('pageerror', lambda exc: errors.append(str(exc)))
    load(mobile)
    expect(mobile.locator('h1')).to_have_text('Building')
    assert mobile.evaluate('document.documentElement.scrollWidth') <= 390
    expect(mobile.locator('[data-level="uml"]')).to_be_visible()
    # The export of the card stays reachable on narrow screens
    expect(mobile.locator('[data-action="export"]')).to_be_visible()
    mobile.screenshot(path=str(ROOT/'docs/screenshot-mobile.png'))
    mobile.set_viewport_size({'width': 850, 'height': 844})
    expect(mobile.locator('[data-action="export"]')).to_be_visible()
    browser.close()
    assert not errors, errors
print('PASS: nessun errore JavaScript; navigazione, ricerca e dettagli delle proprietà, livelli GML e UML con le divergenze fra dizionario e modello, relazioni e classi di associazione, geometrie, destinazioni, code list (modifica dal vivo, codeSpace, esempio XML, salvataggio, reset anche fallito, download, export, panoramica), export su schermi stretti, opzioni di visualizzazione e riquadri funzionanti.')
