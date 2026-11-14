"""X4 Harness-Shell: Browser-Test für die Befehlspalette (Strg+K).

Läuft nur mit `SEDRA_BROWSER=1` (und playwright + Browser). Prüft im echten Browser:
1. Strg+K öffnet die Palette (`.hs-palette` sichtbar, nicht hidden).
2. Suche filtert die Zeilen.
3. „Einstellungen“ öffnet den echten Einstellungs-Reiter (Reiter-ID `einstellungen:`),
   nicht einen leeren Reiter.

Muster wie `test_uix_harness_browser.py` (N10/N11, `uix_check.start_server`).
"""
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.uix_server import UIXHub, make_server
from test_uix_harness_api import ARCH, MODELL, anfrage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
import uix_check  # noqa: E402

KATALOG = """freigabe_katalog:
  version: 1
  regeln:
    - {id: lesen-alles, werkzeug: [datei_lesen, dateien_auflisten, suchen], muster: ['**'], stufe: frei, begruendung: Lesen ändert nichts.}
    - {id: schreiben-docs, werkzeug: [datei_schreiben, datei_aendern], muster: ['docs/**'], stufe: vorarbeiter, begruendung: Dokumente prüft der Vorarbeiter.}
"""


@unittest.skipUnless(os.environ.get('SEDRA_BROWSER') == '1', 'Browser-Durchlauf nur mit SEDRA_BROWSER=1')
class PaletteBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('playwright fehlt')
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-palette-browser-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        (cls.wurzel / 'docs').mkdir(parents=True)
        (cls.wurzel / 'runtime').mkdir()
        projekt = Path(cls.tmp.name) / 'project'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'freigabe_katalog.yaml').write_text(KATALOG, encoding='utf-8')
        (projekt / 'local_config' / 'uix.yaml').write_text('uix:\n  shell: harness\n', encoding='utf-8')
        (projekt / 'local_config' / 'harness_projekte.yaml').write_text(
            f"projekte:\n  - id: pruef\n    name: Prüfprojekt\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [docs/**]\n", encoding='utf-8')
        cls.hub = UIXHub(projekt, ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def sitzung(self):
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef', 'vorlage': 'vorarbeiter'})
        self.assertEqual(code, 200, kopf)
        return kopf['id']

    def test_strg_k_oeffnet_palette_und_einstellungen(self):
        from playwright.sync_api import sync_playwright
        api = self.hub.harness
        api.geladen = lambda: (MODELL, None)
        sid = self.sitzung()
        with sync_playwright() as pw:
            browser = uix_check.launch(pw, 'auto', False)
            try:
                page = browser.new_context(viewport={'width': 1400, 'height': 860}).new_page()
                fehler = []
                page.on('console', lambda m: fehler.append(m.text) if m.type == 'error' else None)
                page.on('pageerror', lambda e: fehler.append(str(e)))
                page.goto(self.url)
                uix_check.wait_until_started(page)
                page.wait_for_selector(f'.hs-sz[data-sitzung="{sid}"]', state='attached', timeout=15000)
                if page.locator('.hs-seite-zu').count():
                    page.keyboard.press('Control+b')
                page.wait_for_selector(f'.hs-sz[data-sitzung="{sid}"]', timeout=15000)

                # ---- 1) Strg+K öffnet die Palette ----
                page.keyboard.press('Control+k')
                palette = page.locator('.hs-palette')
                self.assertTrue(palette.count() > 0, 'Palette-Overlay fehlt im DOM')
                self.assertFalse(palette.get_attribute('hidden'), 'Palette ist nach Strg+K noch hidden')
                self.assertTrue(palette.is_visible(), 'Palette ist nach Strg+K nicht sichtbar')

                # ---- 2) Suche filtert ----
                page.fill('.pal-box input', 'einstellungen')
                page.wait_for_timeout(200)
                zeilen = page.locator('.pal-row')
                self.assertTrue(zeilen.count() > 0, 'Keine Zeilen nach Suche')
                gefunden = False
                for i in range(zeilen.count()):
                    label = zeilen.nth(i).locator('b').inner_text()
                    if 'Einstellungen' in label:
                        gefunden = True
                        break
                self.assertTrue(gefunden, 'Einstellungen-Zeile nicht in der gefilterten Palette')

                # ---- 3) Einstellungen öffnet den echten Reiter (Reiter-ID einstellungen:) ----
                zeilen.nth(0).locator('b').click() if gefunden else None
                page.wait_for_timeout(500)
                # Der Einstellungs-Reiter sollte aktiv sein (Reiter-ID beginnt mit einstellungen:)
                self.assertTrue(
                    page.locator('.hs-reiter .hs-reiter-aktiv[data-id^="einstellungen:"]').count() > 0
                    or page.locator('.hs-einst').count() > 0,
                    'Einstellungen-Reiter nicht geöffnet (erwartet Reiter-ID einstellungen:)'
                )
                self.assertEqual(len(fehler), 0, 'Browser-Konsole-Fehler: ' + str(fehler[:3]))
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
