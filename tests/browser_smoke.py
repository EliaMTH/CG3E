"""Smoke test of the HTML/CSS/JS catalog in Chromium, no network calls.

Loads page, styles, catalog, code list dictionary and script as in-memory
content, so the browser's file:// policy is not exercised. The File System
Access API is replaced by a stub that records what Save writes. Writes
docs/screenshot-desktop.png and docs/screenshot-mobile.png.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ['data/catalog.js', 'codelists/codelists.default.js', 'codelists/codelists.js', 'assets/app.js']

template = (ROOT/'index.html').read_text(encoding='utf-8').replace(
    '<link rel="stylesheet" href="assets/styles.css">',
    '<style>'+(ROOT/'assets/styles.css').read_text(encoding='utf-8')+'</style>')
for script in SCRIPTS:
    template = template.replace(f'<script defer src="{script}"></script>', '')

STUB = '''window.__written = null;
window.showSaveFilePicker = async () => ({name: 'codelists.js',
  queryPermission: async () => 'granted', requestPermission: async () => 'granted',
  createWritable: async () => ({write: async text => { window.__written = text; }, close: async () => {}})});'''


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
    page.locator('[data-cl-action="add"]').click()
    expect(page.locator('.cl-table tbody tr')).to_have_count(15)
    page.locator('[data-cl-field="code"]').last.fill('9000')
    expect(page.locator('#codelist-count')).to_contain_text('•')
    page.locator('[data-cl-action="revert"]').click()
    expect(page.locator('.cl-table tbody tr')).to_have_count(14)
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
    expect(page.locator('#results-count')).to_have_text('96')
    page.locator('#category').select_option('')
    page.locator('#filters-btn').click()

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
    page.screenshot(path=str(ROOT/'docs/screenshot-desktop.png'))

    mobile = browser.new_page(viewport={'width': 390, 'height': 844}, is_mobile=True)
    mobile.on('pageerror', lambda exc: errors.append(str(exc)))
    load(mobile)
    expect(mobile.locator('h1')).to_have_text('Building')
    assert mobile.evaluate('document.documentElement.scrollWidth') <= 390
    mobile.screenshot(path=str(ROOT/'docs/screenshot-mobile.png'))
    browser.close()
    assert not errors, errors
print('PASS: nessun errore JavaScript; navigazione, code list (modifica, salvataggio, reset, download) e riquadri funzionanti (file:// non testato).')
