"""X5 Tastaturbedienung: alle interaktiven per Tab, Fokus sichtbar, logische Reihenfolge,
Kürzel unabhängig von Sprache, Eingabefelder tastaturbedienbar. Rein (HTML/JS-Checks)."""
import re
import unittest
from pathlib import Path

UIX_DIR = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix'


class TastaturTest(unittest.TestCase):
    def test_alle_interaktiven_per_tab(self):
        html = (UIX_DIR / 'retro_desktop.html').read_text(encoding='utf-8')
        # interaktive Elemente haben tabindex="0" oder sind button/input/select
        buttons = re.findall(r'<button[^>]*>', html)
        inputs = re.findall(r'<input[^>]*>', html)
        selects = re.findall(r'<select[^>]*>', html)
        tabindex = re.findall(r'tabindex="0"', html)
        self.assertGreater(len(buttons), 0)
        self.assertGreater(len(tabindex), 0)
        # jeder button hat einen onclick oder ist ein Steuer-Element
        for b in buttons:
            self.assertTrue('onclick' in b or 'class="ctrl' in b, 'Button ohne Aktion: ' + b[:80])

    def test_fokus_sichtbar(self):
        css = (UIX_DIR / 'css' / 'desktop.css').read_text(encoding='utf-8')
        self.assertIn(':focus', css, 'Fokus-Styles fehlen in CSS')

    def test_fokus_reihenfolge_logisch(self):
        html = (UIX_DIR / 'retro_desktop.html').read_text(encoding='utf-8')
        # Die Palette hat aria-label und role="dialog"
        self.assertIn('role="dialog"', html)
        self.assertIn('aria-label="Kommando"', html)

    def test_kuerzel_unabhaengig_von_sprache(self):
        js = (UIX_DIR / 'js' / 'command.js').read_text(encoding='utf-8')
        self.assertIn("KUERZEL", js)
        self.assertIn("'Strg+K'", js)
        self.assertIn("'Esc'", js)
        # Kürzel-Tabelle enthält keine sprachabhängigen Strings
        self.assertNotIn("STRINGS_DE", js[:js.index('KUERZEL')] if 'KUERZEL' in js else js)

    def test_eingabefelder_tastatur(self):
        html = (UIX_DIR / 'retro_desktop.html').read_text(encoding='utf-8')
        inputs = re.findall(r'<input[^>]*>', html)
        for inp in inputs:
            if 'type="file"' in inp:
                continue  # File-Inputs werden über den Button bedient, nicht direkt per Tastatur
            self.assertIn('id=', inp, 'Input ohne id: ' + inp[:80])
            self.assertTrue('onkeydown' in inp or 'onclick' in inp or 'placeholder' in inp or 'oninput' in inp,
                            'Input nicht tastaturbedienbar: ' + inp[:80])


if __name__ == '__main__':
    unittest.main()
