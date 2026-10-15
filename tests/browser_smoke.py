"""Smoke test of the HTML/CSS/JS catalog in Chromium, no network calls.

Loads page, styles, catalog and script as in-memory content, so the browser's
file:// policy is not exercised. Writes docs/screenshot-desktop.png and
docs/screenshot-mobile.png.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT = Path(__file__).resolve().parents[1]

template = (ROOT/'index.html').read_text(encoding='utf-8').replace(
    '<link rel="stylesheet" href="assets/styles.css">',
    '<style>'+(ROOT/'assets/styles.css').read_text(encoding='utf-8')+'</style>').replace(
    '<script defer src="data/catalog.js"></script>', '').replace(
    '<script defer src="assets/app.js"></script>', '')


def load(page):
    page.set_content(template)
    page.add_script_tag(content=(ROOT/'data/catalog.js').read_text(encoding='utf-8'))
    page.add_script_tag(content=(ROOT/'assets/app.js').read_text(encoding='utf-8'))


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    errors = []
    page = browser.new_page(viewport={'width': 1365, 'height': 920})
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    load(page)
    expect(page.locator('h1')).to_have_text('Building')
    expect(page.locator('#catalog-version')).to_have_text('CityGML 3.0.0 (OGC 21-006r2)')
    assert page.locator('#family option').count() == 3
    page.locator('#filters-btn').click()
    page.locator('#category').select_option('boundary')
    page.locator('#only-concrete').check()
    expect(page.locator('#results-count')).to_have_text('24')
    page.locator('#category').select_option('space')
    expect(page.locator('#results-count')).to_have_text('42')
    page.locator('#category').select_option('')
    page.locator('#only-concrete').uncheck()
    page.locator('#filters-btn').click()
    expect(page.locator('.badge', has_text='Spazio')).to_have_count(1)
    expect(page.locator('.chain')).to_contain_text('gml:AbstractFeature')
    page.locator('#search').fill('BuildingPart')
    expect(page.locator('.concept-item')).to_have_count(1)
    page.locator('.concept-item').click()
    expect(page.locator('h1')).to_have_text('BuildingPart')
    for tab in ('Proprietà', 'Connessioni', 'Sorgente'):
        page.locator('.tab', has_text=tab).click()
        expect(page.locator('.tab.active')).to_contain_text(tab)
    page.locator('#sources-btn').click()
    expect(page.locator('#modal-title')).to_have_text('Sorgenti')
    expect(page.locator('#modal-body')).to_contain_text('consultabile offline')
    page.locator('#close-modal').click()
    page.locator('#about-btn').click()
    expect(page.locator('#modal-title')).to_have_text('Come leggere il catalogo')
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
print('PASS: nessun errore JavaScript; pagina, schede, ricerca e riquadri funzionanti (file:// non testato).')
