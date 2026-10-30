"""N10/N11 der Harness-Shell Stufe 3: Browser-Durchlauf mit Modell-Attrappe (P-10, kein Modell).

Läuft nur mit `SEDRA_BROWSER=1` (und playwright + Browser): ein echter Browser verlangsamt die Gruppe `harness` und ist unter Last empfindlich, deshalb
nicht im Standardlauf. Szenarien: (A) Karte an den Vorarbeiter → er entscheidet → die Karte im Verlauf zeigt es; (B) Aufgabe anlegen → Aufruf ohne Karte
(Schild, Werkzeugzeile „aufgabe“) → Rücknahme → der nächste Aufruf braucht wieder eine Karte; (C) Lauf in der Taskleiste mit Fortschritt → Ende:
Knopf blinkt einmal und bleibt markiert, auch nach dem Neuladen, bis er angeklickt wird → Reiter „Lauf“ mit der Ausgabe."""
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.uix_server import UIXHub, make_server
from test_uix_harness_api import ARCH, MODELL
from test_uix_harness_freigabe import Skript
from test_harness_lauf import SKRIPT
from test_uix_harness_lauf import typen
from guppi_runtime.harness import lauf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))

KATALOG = """freigabe_katalog:
  version: 1
  regeln:
    - {id: lesen-alles, werkzeug: [datei_lesen, dateien_auflisten, suchen], muster: ['**'], stufe: frei, begruendung: Lesen ändert nichts.}
    - {id: schreiben-docs, werkzeug: [datei_schreiben, datei_aendern], muster: ['docs/**'], stufe: vorarbeiter, begruendung: Dokumente prüft der Vorarbeiter.}
"""
NOTIZ = 'docs/notiz.md'
GROESSEN = ((1400, 860), (1024, 700))


@unittest.skipUnless(os.environ.get('SEDRA_BROWSER') == '1', 'Browser-Durchlauf nur mit SEDRA_BROWSER=1')
class BrowserDurchlauf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import playwright  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('playwright fehlt')
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-browser-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        (cls.wurzel / 'docs').mkdir(parents=True)
        (cls.wurzel / 'runtime').mkdir()
        (cls.wurzel / 'runtime' / 'probe.py').write_text(SKRIPT, encoding='utf-8')
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

    def sitzung(self, vorlage):
        from test_uix_harness_api import anfrage
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef', 'vorlage': vorlage})
        self.assertEqual(code, 200, kopf)
        return kopf['id']

    def text(self):
        return (self.wurzel / NOTIZ).read_text(encoding='utf-8').strip()

    def test_durchlauf_in_beiden_groessen(self):
        import uix_check
        from playwright.sync_api import sync_playwright
        api = self.hub.harness
        api.geladen = lambda: (MODELL, None)
        with sync_playwright() as pw:
            browser = uix_check.launch(pw, 'auto', False)
            try:
                for breite, hoehe in GROESSEN:
                    with self.subTest(groesse=f'{breite}x{hoehe}'):
                        self.durchlauf(browser, breite, hoehe)
            finally:
                browser.close()

    def durchlauf(self, browser, breite, hoehe):
        import uix_check
        api = self.hub.harness
        (self.wurzel / NOTIZ).write_text('start\n', encoding='utf-8')
        api.vorarbeiter._schreiben({'projekte': {}, 'entscheidungen': {}})
        v, b = self.sitzung('vorarbeiter'), self.sitzung('bauagent')
        api.vorarbeiter.ernennen('pruef', v)
        page = browser.new_context(viewport={'width': breite, 'height': hoehe}).new_page()
        fehler = []
        page.on('console', lambda m: fehler.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: fehler.append(str(e)))
        page.goto(self.url)
        uix_check.wait_until_started(page)
        page.wait_for_selector(f'.hs-sz[data-sitzung="{v}"]', state='attached', timeout=15000)
        if page.locator('.hs-seite-zu').count():                 # unter 1100 px klappt die Seitenleiste von selbst zu (HS-05)
            page.keyboard.press('Control+b')
        page.wait_for_selector(f'.hs-sz[data-sitzung="{v}"]', timeout=15000)
        self.assertIn('⚑', page.inner_text(f'.hs-sz[data-sitzung="{v}"]'), 'der Vorarbeiter ist in der Seitenleiste markiert')

        def schreibe(sid, zug, neu):
            api.execute = Skript([('calls', [('datei_aendern', {'pfad': NOTIZ, 'alt': self.text(), 'neu': neu})]), ('text', 'Fertig.')])
            page.click(f'.hs-sz[data-sitzung="{sid}"] .hs-sz-haupt')
            page.fill('.hs-feld', zug)
            page.press('.hs-feld', 'Enter')

        # ---- A: Karte an den Vorarbeiter, er entscheidet
        schreibe(b, 'Ändere die Notiz', 'A')
        page.wait_for_selector('.hs-karte[data-karte]', timeout=20000)
        self.assertIn('Beim Vorarbeiter', page.inner_text('.hs-karte[data-karte] .hs-karte-an'))
        karte = [k for k in api.karten.alle('offen') if k['sitzung_id'] == b][0]
        self.assertEqual(karte['an'], 'vorarbeiter')
        box = api._kiste(api._sitzung(v))[0]
        r = box.aufruf('freigabe_entscheiden', {'karte_id': karte['karte_id'], 'weg': 'erlauben', 'begruendung': 'Nur die Notiz ändert sich, sonst nichts.',
                                                'vorschau_hash': karte['vorschau_hash']})
        self.assertEqual(r['status'], 'ok', r)
        page.wait_for_function("()=>/Erlaubt \\(Vorarbeiter\\)/.test(document.querySelector('.hs-karte[data-karte]').innerText)", timeout=15000)
        self.assertIn('Begründung: Nur die Notiz', page.inner_text('.hs-karte[data-karte]'))
        self.assertEqual(self.text(), 'A')

        # ---- B: Aufgabe anlegen, Aufruf ohne Karte, Rücknahme, wieder eine Karte
        page.click('text=⛨ Aufgaben')
        page.wait_for_selector('.hs-auf-form', timeout=10000)
        page.fill('.hs-auf-form input[aria-label="Zweck"]', 'Die Notiz bis zu dreimal ohne Karte pflegen')
        page.fill('.hs-auf-form input[aria-label="Titel"]', 'Notiz pflegen')
        page.check(f'.hs-auf-form input[value="{b}"]')
        page.fill('.hs-auf-form textarea', f'datei_aendern {NOTIZ}')
        page.fill('.hs-auf-form input[aria-label="Höchstens so viele Aufrufe"]', '3')
        page.click('.hs-auf-form button:has-text("Freigeben")')
        page.wait_for_selector('.hs-auf-aktiv', timeout=15000)
        self.assertIn('Rest 3 Aufrufe', page.inner_text('.hs-auf-aktiv'))
        karten_vorher = len(api.karten.alle())
        schreibe(b, 'Nochmal ändern', 'B')
        page.wait_for_selector('.hs-wz-stufe.aufgabe', timeout=20000)
        self.assertEqual(self.text(), 'B')
        self.assertEqual(len(api.karten.alle()), karten_vorher, 'innerhalb der Aufgabe keine neue Karte')
        self.assertIn('Aufgabe T-', page.inner_text('.hs-schild'))
        page.click('text=⛨ Aufgaben')
        page.wait_for_selector('.hs-auf-aktiv', timeout=10000)
        page.click('.hs-auf-aktiv button:has-text("Zurücknehmen")')
        page.wait_for_function("()=>!document.querySelector('.hs-auf-aktiv button')", timeout=15000)
        schreibe(b, 'Und noch einmal', 'C')
        page.wait_for_selector('.hs-karte[data-karte]:not(.entschieden)', timeout=20000)
        self.assertEqual(len(api.karten.alle()), karten_vorher + 1, 'nach der Rücknahme gibt es wieder eine Karte')
        self.assertEqual(self.text(), 'B', 'nach der Rücknahme wartet der Aufruf auf eine Karte')
        # Freigaben in der Statusleiste: die neue Karte hat die Zelle markiert (HS-33)
        page.wait_for_selector('.hs-zelle[data-zelle="decisions"].neu', timeout=8000)

        # ---- C: Lauf mit Fortschritt, Ende, Benachrichtigung
        api._lauf_typen = typen()
        typ = api._lauf_typen['probe']
        def neuer_lauf():
            return api.laeufe.starten(typ, lauf.argv_bauen(typ, {'n': '15'}, self.wurzel), parameter={'n': '15'}, sitzung_id=v)
        l1 = neuer_lauf()
        page.wait_for_selector(f'.hs-app.lauf.laeuft[data-lauf="{l1["id"]}"]', timeout=15000)
        page.wait_for_function(r"()=>/Probe \d+ %/.test(document.querySelector('.hs-app.lauf').innerText)", timeout=15000)
        page.wait_for_function("()=>document.querySelector('.hs-app.lauf.neu.blinkt')", timeout=30000)      # endet: blinkt einmal und ist markiert
        self.assertIn('✓', page.inner_text('.hs-app.lauf'))
        page.wait_for_timeout(2500)
        self.assertEqual(page.locator('.hs-app.lauf.neu').count(), 1, 'markiert, bis er angeklickt wird')
        self.assertEqual(page.locator('.hs-app.lauf.blinkt').count(), 0, 'das Blinken war einmalig')
        page.click('.hs-app.lauf.neu')
        page.wait_for_selector('.hs-lauf-log', timeout=10000)
        self.assertIn('15/15', page.inner_text('.hs-lauf-log'))
        self.assertEqual(page.locator('.hs-app.lauf.neu').count(), 0, 'angeklickt: Markierung weg')
        l2 = neuer_lauf()                                                # unangesehen bleibt nach dem Neuladen markiert
        for _ in range(100):
            if api.laeufe.laden(l2['id'])['status'] != 'laeuft': break
            page.wait_for_timeout(200)
        page.reload()
        uix_check.wait_until_started(page)
        page.wait_for_selector(f'.hs-app.lauf.neu[data-lauf="{l2["id"]}"]', timeout=15000)
        self.assertEqual(fehler, [], 'keine Konsolenfehler')
        # nichts ragt waagerecht heraus (HS-05)
        self.assertLessEqual(page.evaluate('()=>document.documentElement.scrollWidth - document.documentElement.clientWidth'), 0)
        page.context.close()


if __name__ == '__main__':
    unittest.main()
