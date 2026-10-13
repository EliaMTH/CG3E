"""Smoke test of both HTML/CSS/JS catalogs in Chromium, no network calls.

Uses in-memory content because this environment blocks file:// navigation.
"""
import json
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]

def build(mode):
    name='build_citygml_owl.py' if mode=='full' else 'build_citygml.py'
    subprocess.run([sys.executable,str(ROOT/'scripts'/name),'--offline'],check=True,capture_output=True,text=True)
    assert json.loads((ROOT/'data/catalog.json').read_text())['mode']==mode

with sync_playwright() as pw:
    import shutil
    executable=shutil.which('chromium') or shutil.which('chromium-browser')
    browser=pw.chromium.launch(headless=True,executable_path=executable) if executable else pw.chromium.launch(headless=True)
    errors=[]
    template=(ROOT/'index.html').read_text().replace(
        '<link rel="stylesheet" href="assets/styles.css">',
        '<style>'+(ROOT/'assets/styles.css').read_text()+'</style>').replace(
        '<script defer src="data/catalog.js"></script>','').replace(
        '<script defer src="assets/app.js"></script>','')
    def load(target):
        target.set_content(template)
        target.add_script_tag(content=(ROOT/'data/catalog.js').read_text())
        target.add_script_tag(content=(ROOT/'assets/app.js').read_text())
    for mode in ['full','citygml']:
        build(mode)
        page=browser.new_page(viewport={'width':1365,'height':920})
        page.on('pageerror',lambda exc:errors.append(str(exc)))
        load(page)
        expect(page.locator('h1')).to_have_text('Building')
        expect(page.locator('#catalog-mode')).to_have_text('CityGML + OWL' if mode=='full' else 'Solo CityGML')
        if mode=='full':
            page.locator('#search').fill('BuildingQuality')
            expect(page.locator('.concept-item')).to_have_count(1)
            page.locator('.concept-item').click()
            expect(page.locator('h1')).to_have_text('BuildingQuality')
        else:
            page.locator('#search').fill('BuildingQuality')
            expect(page.locator('.concept-item')).to_have_count(0)
            assert page.locator('#family option[value="UISH"]').count()==0
            page.locator('#search').fill('BuildingPart')
            expect(page.locator('.concept-item')).to_have_count(1)
            page.locator('.concept-item').click()
            expect(page.locator('h1')).to_have_text('BuildingPart')
            page.locator('#home-link').click()
            expect(page.locator('h1')).to_have_text('Building')
            page.screenshot(path=str(ROOT/'docs/citygml-only.png'))
            mobile=browser.new_page(viewport={'width':390,'height':844},is_mobile=True)
            load(mobile)
            expect(mobile.locator('h1')).to_have_text('Building')
            assert mobile.evaluate('document.documentElement.scrollWidth')<=390
            mobile.screenshot(path=str(ROOT/'docs/citygml-mobile.png'))
            mobile.close()
        print('PASS browser',mode)
        page.close()
    assert not errors,errors
    browser.close()
print('PASS: nessun errore JavaScript, entrambe le modalita HTML in memoria funzionanti; file:// non testato')
