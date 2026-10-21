"""Browser test of the standard export, opened from file:// after extraction, no network calls.

Applies scripts/codespaces.py to RoofTypeValue in a copy of the dictionary,
exports the standard package with that dictionary, extracts it into a temporary
folder and opens index.html in Chromium: catalog, Sources panel, local links to
the OGC documents, the code list page with the new codeSpace, and Save, which
must write the same bytes as scripts/codespaces.py.
"""
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import codespaces as cs
import exporters as ex

WHEN = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
SPACE = 'https://example.org/citygml/codelists/1.0/Building.RoofTypeValue.xml'
STUB = '''window.__written = null;
window.showSaveFilePicker = async () => ({name: 'codelists.js',
  queryPermission: async () => 'granted', requestPermission: async () => 'granted',
  createWritable: async () => ({write: async text => { window.__written = text; }, close: async () => {}})});'''

inputs = ex.load(ROOT)
inputs.dictionary, _, _ = cs.apply(inputs.dictionary, inputs.catalog, 'https://example.org/citygml/codelists/', '1.0',
                                   'Comune di Prova', lists=['RoofTypeValue'], applied_at=WHEN)
inputs.dictionary_bytes = cs.serialize(inputs.dictionary)
package = ex.export_standard(inputs, WHEN).data

with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
    folder = Path(tmp)
    zipfile.ZipFile(BytesIO(package)).extractall(folder)
    browser = pw.chromium.launch(headless=True)
    errors = []
    page = browser.new_page(viewport={'width': 1365, 'height': 920})
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.add_init_script(STUB)
    page.route('http*://**', lambda route: route.abort())
    page.goto((folder/'index.html').as_uri())
    expect(page.locator('h1')).to_have_text('Building')
    expect(page.locator('#catalog-version')).to_have_text('CityGML 3.0.0 (OGC 21-006r2)')
    expect(page.locator('#codelist-count')).to_have_text('44/140')

    page.locator('#sources-btn').click()
    expect(page.locator('#modal-title')).to_have_text('Sorgenti')
    expect(page.locator('#modal-body')).to_contain_text('Codifica GML')
    links = page.locator('#modal-body a[href^="sources/"]').evaluate_all('as => as.map(a => a.getAttribute("href"))')
    assert links, 'nessun collegamento a sources/ nel riquadro Sorgenti'
    for href in links:
        assert (folder/href.split('#')[0]).exists(), href
    for document in ('sources/docs.ogc.org/is/20-010/20-010.html', 'sources/docs.ogc.org/is/21-006r2/21-006r2.html'):
        assert document in links, document
    page.locator('#close-modal').click()

    page.goto((folder/'index.html').as_uri() + '#node=uml:Building:RoofTypeValue')
    expect(page.locator('h1')).to_have_text('RoofTypeValue')
    expect(page.locator('[data-cl-field="codeSpace"]')).to_have_value(SPACE)
    expect(page.locator('.source-block').first).to_contain_text(f'codeSpace="{SPACE}"')
    expect(page.locator('.metadata-grid').first).to_contain_text('Comune di Prova')

    page.locator('[data-cl-action="save"]').first.click()
    page.wait_for_function('window.__written !== null')
    written = page.evaluate('window.__written')
    assert written.encode('utf-8') == inputs.dictionary_bytes, 'Salva scrive byte diversi da scripts/codespaces.py'
    browser.close()
    assert not errors, errors
print('PASS: pacchetto standard aperto da file:// senza errori JavaScript; riquadro Sorgenti e collegamenti locali; codeSpace di EXP-004 nella pagina della code list; Salva identico a scripts/codespaces.py.')
