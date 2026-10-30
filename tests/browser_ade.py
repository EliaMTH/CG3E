"""Browser test of an ADE in the catalog, in Chromium, no network calls.

Builds in a temporary folder the catalog and the code list dictionary with the Test ADE of
tests/fixtures/ade (prepare() of tests/test_ade.py: project inputs copied, fetch without network)
and loads page, styles, catalog, dictionary and script as in-memory content, as
tests/browser_smoke.py does. The File System Access API is replaced by a stub that records what
Save writes.
"""
import sys
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests'))
from test_ade import element, prepare

SCRIPTS = ['data/catalog.js', 'codelists/codelists.default.js', 'codelists/codelists.js']
STUB = '''window.__written = null;
window.showSaveFilePicker = async () => ({name: 'codelists.js',
  queryPermission: async () => 'granted', requestPermission: async () => 'granted',
  createWritable: async () => ({write: async text => { window.__written = text; }, close: async () => {}})});'''
BUILDING = 'xsd:{http://www.opengis.net/citygml/building/3.0}element:Building'


def open_node(page, id_, tab='overview'):
    page.evaluate("([id, tab]) => { location.hash = '#' + new URLSearchParams({node: id, tab}).toString(); }", [id_, tab])


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    run = prepare(root)
    assert (run.fetch, run.verify, run.align.returncode) == (0, 0, 0), run.output + run.align.stderr
    template = (ROOT/'index.html').read_text(encoding='utf-8')
    for sheet in ('assets/styles.css', 'assets/styles-dark.css'):
        template = template.replace(f'<link rel="stylesheet" href="{sheet}">',
                                    '<style>'+(ROOT/sheet).read_text(encoding='utf-8')+'</style>')
    for script in SCRIPTS + ['assets/app.js']:
        template = template.replace(f'<script defer src="{script}"></script>', '')

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        errors = []
        page = browser.new_page(viewport={'width': 1365, 'height': 920})
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content(template)
        for script in SCRIPTS:
            page.add_script_tag(content=(root/script).read_text(encoding='utf-8'))
        page.add_script_tag(content=(ROOT/'assets/app.js').read_text(encoding='utf-8'))
        expect(page.locator('h1')).to_have_text('Building')

        # The ADE family of the schema filter, with its module
        expect(page.locator('#family option')).to_have_count(4)
        expect(page.locator('#family option[value="ADE"]')).to_have_text('ADE: TestADE')
        page.locator('#family').select_option('ADE')
        expect(page.locator('#module option[value="TestADE"]')).to_have_count(1)
        expect(page.locator('.concept-item', has_text='tade:Kiosk')).to_have_count(1)
        expect(page.locator('.concept-item', has_text='tade:EnergyClassValue')).to_have_count(1)
        page.locator('#family').select_option('CityGML')

        # An element of the ADE: badges and the Standard tab from the configuration
        open_node(page, element('Kiosk'))
        expect(page.locator('h1')).to_have_text('Kiosk')
        expect(page.locator('.badge', has_text='ADE TestADE')).to_have_count(1)
        expect(page.locator('.badge', has_text='Primo livello')).to_have_count(1)
        page.locator('.tab', has_text='Standard').click()
        for text in ('ADE di provenienza', 'https://example.org/cg3e/test-ade/1.0', 'copia locale',
                     'sì, secondo la configurazione', 'cityObjectMember'):
            expect(page.locator('#tab-content')).to_contain_text(text)
        open_node(page, element('BuildingProperties'), 'standard')
        expect(page.locator('#tab-content section', has_text='Code list dalla configurazione')).to_contain_text('tade:energyClass')
        expect(page.locator('#tab-content section', has_text='Code list dalla configurazione')).to_contain_text('tade:EnergyClassValue')

        # The ADE as a candidate of the ADE hook of Building
        open_node(page, BUILDING, 'properties')
        page.locator('[data-property]', has_text='adeOfAbstractBuilding').first.click()
        expect(page.locator('#modal-body')).to_contain_text('tade:BuildingProperties')
        page.locator('#close-modal').click()

        # A code list of the ADE: its dictionary, a value edited and saved under the qualified key
        open_node(page, 'ade:TestADE:EnergyClassValue')
        expect(page.locator('h1')).to_have_text('EnergyClassValue')
        for text in ('Code list dell’ADE', 'Dizionario dell’ADE', 'TestADE.EnergyClassValue.xml', 'non ancora pubblicato'):
            expect(page.locator('#tab-content')).to_contain_text(text)
        expect(page.locator('.cl-table tbody tr')).to_have_count(2)
        page.locator('[data-cl-field="name"]').first.fill('classe A modificata')
        page.evaluate(STUB)
        page.locator('[data-cl-action="save"]').click()
        page.wait_for_function('window.__written !== null')
        written = page.evaluate('window.__written')
        assert '"tade:EnergyClassValue"' in written and 'classe A modificata' in written

        # The values of the ADE in a CityGML code list: read-only, with their ADE, removable
        open_node(page, 'uml:Building:BuildingClassValue')
        rows = page.locator('.cl-table tbody tr', has=page.locator('.badge', has_text='TestADE'))
        expect(rows).to_have_count(2)
        expect(rows.locator('input')).to_have_count(0)
        expect(page.locator('#tab-content')).to_contain_text('Voci da ADE')
        expect(page.locator('#tab-content')).to_contain_text('TestADE (2)')
        rows.first.locator('[data-cl-action="delete"]').click()
        expect(page.locator('.cl-table tbody tr', has=page.locator('.badge', has_text='TestADE'))).to_have_count(1)
        page.locator('[data-cl-action="revert"]').click()

        # Sources: the schemas of the ADE in their own section
        page.locator('#sources-btn').click()
        expect(page.locator('#modal-title')).to_have_text('Sorgenti')
        expect(page.locator('#modal-body')).to_contain_text('Schemi ADE')
        expect(page.locator('#modal-body h3', has_text='ADE TestADE')).to_have_count(1)
        expect(page.locator('#modal-body')).to_contain_text('test-ade-meters.xsd')
        page.locator('#close-modal').click()

        assert errors == [], errors
        browser.close()
    print('browser_ade: OK')
