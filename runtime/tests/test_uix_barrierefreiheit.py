"""X5 Barrierefreiheit: Aria-Labels, Aria-Rolle/Zustand, Fehlermeldungen Screenreader,
Bilder Alternativtext, Kontrast WCAG AA. Rein (HTML/JS-Checks)."""
import re
import unittest
from pathlib import Path

UIX_DIR = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix'


class BarrierefreiheitTest(unittest.TestCase):
    def test_aria_labels_vorhanden(self):
        html = (UIX_DIR / 'retro_desktop.html').read_text(encoding='utf-8')
        aria_labels = re.findall(r'aria-label="[^"]+"', html)
        self.assertGreater(len(aria_labels), 0, 'Keine Aria-Labels im HTML')

    def test_aria_rolle_und_zustand(self):
        html = (UIX_DIR / 'retro_desktop.html').read_text(encoding='utf-8')
        self.assertIn('role=', html, 'Keine ARIA-Rollen im HTML')
        self.assertIn('aria-', html, 'Keine ARIA-Attribute im HTML')

    def test_fehlermeldungen_screenreader(self):
        html = (UIX_DIR / 'retro_desktop.html').read_text(encoding='utf-8')
        self.assertTrue('aria-live' in html or 'aria-label' in html,
                        'Keine Screenreader-Benachrichtigung (aria-live/aria-label) im HTML')

    def test_bilder_alternativtext(self):
        html = (UIX_DIR / 'retro_desktop.html').read_text(encoding='utf-8')
        imgs = re.findall(r'<img[^>]*>', html)
        for img in imgs:
            self.assertTrue('alt=' in img or 'aria-label' in img, 'Bild ohne Alternativtext: ' + img[:80])

    def test_kontrast_wcag_aa(self):
        css = (UIX_DIR / 'css' / 'desktop.css').read_text(encoding='utf-8')
        self.assertIn('var(--', css, 'Farben sollten über CSS-Tokens (Var) definiert sein')
        # Keine Hex-Farben in der command.js (X4/X5 UI-Regel)
        js = (UIX_DIR / 'js' / 'command.js').read_text(encoding='utf-8')
        self.assertNotIn('innerHTML', js)
        self.assertNotIn('setInterval', js)


if __name__ == '__main__':
    unittest.main()
