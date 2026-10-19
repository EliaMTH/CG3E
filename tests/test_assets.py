"""Tests of the generated stylesheet and of the CSS conventions it relies on."""
import re
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import build_dark_theme as dt


class DarkThemeTests(unittest.TestCase):
    def test_generated_file_is_current(self):
        self.assertEqual((ROOT/'assets/styles-dark.css').read_text(encoding='utf-8'), dt.build(ROOT),
                         'Esegui python scripts/build_dark_theme.py dopo aver modificato assets/styles.css.')

    def test_variables_are_not_rewritten(self):
        css = (ROOT/'assets/styles-dark.css').read_text(encoding='utf-8')
        self.assertNotIn('var(--#', css)
        self.assertIn('html[data-theme="dark"]{--ink:', css)

    def test_colour_transformation(self):
        self.assertEqual(dt.COLOR.sub(dt.dark, '#ffffff'), '#1a1a1a')
        self.assertEqual(dt.COLOR.sub(dt.dark, 'background:var(--white);color:white'), 'background:var(--white);color:#1a1a1a')
        self.assertTrue(dt.COLOR.sub(dt.dark, '#fff8').endswith('88'))

    def test_shadows_and_backdrop_are_kept(self):
        css = dt.emit(dt.parse('a{box-shadow:0 1px 2px #000;color:#000}dialog::backdrop{background:#182f2655}'))
        self.assertEqual(css, 'html[data-theme="dark"] a{color:#ebebeb}')


class FontScaleTests(unittest.TestCase):
    def test_every_font_size_follows_the_scale(self):
        css = (ROOT/'assets/styles.css').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'font(?:-size)?:\d+(?:\.\d+)?px', css), [])


if __name__ == '__main__':
    unittest.main()
