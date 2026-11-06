"""Werkzeug „Wissen“ v2 im Cockpit, im echten Browser (SPEC_WERKZEUG_WISSEN_v2 §3, WZ1–WZ3, §3.8).

Die Suche ist die Startansicht; ein Reiterwechsel ändert die Werkbank-Zeile der Shell (object.actions); „Ins Gespräch“ setzt die Kennung
ins Eingabefeld des Gesprächs; die Frage liegt nach dem Neuladen wieder im Feld, aber nie im Browser-Speicher.
"""
import unittest

from test_uix_dock_stufe2 import WARTE_MS, Basis, bis_wahr

# Unter Last (run_tests --jobs 4 --slow auf 2 Kernen) reichten feste Pausen nicht (UIX-Check 05.11.2026): gewartet wird auf Zustände
# bis WARTE_MS; den Start meldet uix_check.wait_until_started selbst, wenn er ausbleibt. Die Prüfungen danach sind unverändert.
ERGEBNIS = "()=>!!document.querySelector('.t-wissen-ergebnis, .t-wissen .s-empty, .t-wissen .s-note.bad')"


def warte(page, bedingung, ms=WARTE_MS, arg=None):
    """Wartet, bis `bedingung` (JS) gilt; bleibt sie aus, entscheidet die folgende Prüfung mit ihrer eigenen Meldung."""
    try:
        page.wait_for_function(bedingung, arg=arg, timeout=ms, polling=250)
    except Exception:
        pass


def ruhig(page, sel, ruhe_ms=600, ms=WARTE_MS):
    """Wartet, bis das Werkzeug unter `sel` `ruhe_ms` lang nicht neu gezeichnet hat (MutationObserver).
    Gemessen (05.11.2026): kurz nach dem ersten Zeichnen zeichnet „Wissen“ in der Wissensbasis gelegentlich noch einmal und ersetzt dabei
    das Suchfeld – ein schon getippter Text ist dann fort, Enter sucht mit leerer Frage („Die Frage enthält kein Suchwort.“, 1 von 4 Läufen
    der ganzen Datei, ohne Last). Die feste Pause von 1500 ms hatte das bisher meist überdeckt."""
    page.evaluate("""(sel)=>{ window.__ruhe = Date.now(); const el = document.querySelector(sel);
        if(el && !el.__beob){ el.__beob = new MutationObserver(()=>{ window.__ruhe = Date.now(); }); el.__beob.observe(el, {childList: true, subtree: true}); } }""", sel)
    warte(page, "(r)=>Date.now() - window.__ruhe >= r", ms=ms, arg=ruhe_ms)


NOTIZ = "# Werkbank\n\n## Lease\n\nVor dem Laden die Lease des Testlabors holen. Der Index braucht volle Abdeckung.\n"


def mit_quelle(hub):
    """Eine freigegebene Quelle im Prüfprojekt, damit die Suche Treffer hat (Antrag → Freigabe, wie auf dem PC)."""
    (hub.project_root / 'notizen').mkdir(parents=True, exist_ok=True)
    (hub.project_root / 'notizen' / 'werkbank.md').write_text(NOTIZ, encoding='utf-8')
    out = hub.act({'type': 'wissen', 'verb': 'quelle_beantragen', 'args': {'adapter': 'markdown', 'wurzel': 'projekt', 'pfad': 'notizen/werkbank.md', 'stufe': 1}})['result']
    hub.decide({'id': out['decision_id'], 'way': 'freigeben_und_anwenden'})


class WissenImCockpit(Basis):
    @classmethod
    def setUpClass(cls):
        import sys
        from test_uix_dock_stufe2 import BENCH
        sys.path.insert(0, str(BENCH))
        import uix_check
        orig = uix_check.start_server
        uix_check.start_server = lambda say, shell=None, prepare=None: orig(say, shell=shell, prepare=mit_quelle, switches={'wissen': True})
        try:
            super().setUpClass()
        finally:
            uix_check.start_server = orig

    def wissen(self, page):
        self.oeffnen(page, {'type': 'wissen', 'id': 'speicher', 'title': 'Wissen'})
        page.wait_for_selector('.t-wissen', timeout=WARTE_MS)
        warte(page, "()=>document.querySelectorAll('.t-wissen .t-wissen-tab').length > 0")
        self.assertGreater(page.locator('.t-wissen .t-wissen-tab').count(), 0, 'der Schalter wissen ist im Prüfprojekt an')

    ZEILE = "()=>[...document.querySelectorAll('.dk-group')].map(g=>(g.querySelector('.dk-verbs')||{}).innerText||'').join(' | ')"

    def zeile(self, page):
        return page.evaluate(self.ZEILE)

    def test_suche_ist_start_und_der_reiter_aendert_die_werkbank(self):
        page = self.seite()
        self.wissen(page)
        warte(page, "()=>!!document.querySelector('.t-wissen-tab.on')")
        self.assertEqual(page.evaluate("()=>document.querySelector('.t-wissen-tab.on').dataset.ansicht"), 'suche')
        warte(page, f"()=>({self.ZEILE})().includes('Neue Suche')")
        self.assertIn('Neue Suche', self.zeile(page))
        page.locator('.t-wissen-tab', has_text='Quellen').click()
        # statt 700 ms: die Werkbank-Zeile hat gewechselt (object.actions); beide Prüfungen darunter bleiben
        warte(page, f"()=>{{ const t = ({self.ZEILE})(); return t.includes('Quelle beantragen') && !t.includes('Neue Suche'); }}")
        self.assertIn('Quelle beantragen', self.zeile(page))
        self.assertNotIn('Neue Suche', self.zeile(page))
        self.assertEqual(self.fehler, [])

    def test_frage_bleibt_ueber_das_neuladen_aber_nicht_im_browser(self):
        page = self.seite()
        self.wissen(page)
        ruhig(page, '.t-wissen')                     # erst tippen, wenn das Werkzeug nicht mehr zeichnet (siehe ruhig)
        page.fill('.t-wissen input.t-wissen-frage', 'Lease Index Abdeckung')
        page.press('.t-wissen input.t-wissen-frage', 'Enter')
        warte(page, ERGEBNIS)                                                  # statt 1500 ms: die Suche hat geantwortet
        self.assertTrue(page.evaluate(ERGEBNIS), 'Enter hat gesucht')
        treffer = page.locator('.t-wissen-treffer').count()
        self.assertGreater(treffer, 0, 'die Quelle des Prüfprojekts hat Treffer')
        if treffer:
            page.locator('.t-wissen-treffer').first.locator('button', has_text='Ins Gespräch').click()
            warte(page, r"()=>/\[W[0-9a-f]+\]/.test((document.querySelector('.t-talk-in input, .t-talk-in textarea')||{}).value||'')")   # statt 400 ms
            self.assertRegex(page.evaluate("()=>(document.querySelector('.t-talk-in input, .t-talk-in textarea')||{}).value||''"), r'\[W[0-9a-f]+\]')
        # statt 800 ms: die Ablage schreibt gebündelt (höchstens einmal je Sekunde, lifecycle.js) – warten, bis die Frage auf dem Server liegt
        bis_wahr(page, "async()=>{ const r = await (await fetch('/api/ablage/lesen', {method: 'POST', body: JSON.stringify({objekt: 'wissen:speicher'}),"
                    " headers: {'Content-Type': 'application/json', 'X-SEDRA-Tool': 'wissen', 'X-GUPPI-Token': decodeURIComponent(location.hash.slice(1))}})).json();"
                    " return JSON.stringify((r && r.werte) || {}).includes('Lease Index Abdeckung'); }")
        page.reload(); self.uix.wait_until_started(page, shell='cockpit')
        page.wait_for_selector('.t-wissen input.t-wissen-frage', timeout=WARTE_MS)
        warte(page, "()=>document.querySelector('.t-wissen input.t-wissen-frage').value !== ''")      # statt 1500 ms: die Frage kommt aus der Ablage nach
        self.assertEqual(page.input_value('.t-wissen input.t-wissen-frage'), 'Lease Index Abdeckung')
        gespeichert = page.evaluate("()=>JSON.stringify(Object.assign({}, localStorage)) + JSON.stringify(Object.assign({}, sessionStorage))")
        self.assertNotIn('Lease Index', gespeichert)
        self.assertEqual(self.fehler, [])



class Wissensbasis(WissenImCockpit):
    """SPEC_SHELL_WISSEN_v1 W1, W3, W7, W8: die Shell aus Vorgabe – Orte, Start in der Suche, Fundstelle daneben, Gespräch aus dem Wissen."""
    SHELL = 'wissensbasis'

    @classmethod
    def setUpClass(cls):
        import sys
        from test_uix_dock_stufe2 import BENCH
        sys.path.insert(0, str(BENCH))
        import uix_check
        orig = uix_check.start_server
        uix_check.start_server = lambda say, shell=None, prepare=None: orig(say, shell='wissensbasis', prepare=mit_quelle, switches={'wissen': True})
        try:
            Basis.setUpClass.__func__(cls)
        finally:
            uix_check.start_server = orig

    def seite(self):
        page = self.browser.new_page(viewport={'width': 1400, 'height': 900})
        self.fehler = []
        page.on('pageerror', lambda e: self.fehler.append(str(e)))
        self.addCleanup(page.close)
        # statt 1500 ms: der Start genau dieser Shell, dann ihre Orte
        page.goto(self.url); self.uix.wait_until_started(page, shell=self.SHELL)
        warte(page, "()=>!!document.querySelector('.fr-orte, [aria-label=Orte]')")
        return page

    def test_suche_fundstelle_und_gespraech(self):
        page = self.seite()
        self.assertEqual(page.evaluate("()=>window.sedraBoot.ctx.manifest.shell.id"), 'wissensbasis')
        orte = page.evaluate("()=>document.querySelector('.fr-orte, [aria-label=Orte]').innerText")
        for ort in ('Wissen · Suche', 'Wissen · Quellen', 'Wissen · Eigenes', 'Logbuch'):
            self.assertIn(ort, orte)
        page.wait_for_selector('.t-wissen input.t-wissen-frage', timeout=WARTE_MS)
        warte(page, "()=>!!document.querySelector('.t-wissen-tab.on') && ((document.querySelector('.t-fundstelle')||{}).innerText||'').includes('Wähle einen Treffer')")
        self.assertEqual(page.evaluate("()=>document.querySelector('.t-wissen-tab.on').dataset.ansicht"), 'suche')
        self.assertIn('Wähle einen Treffer', page.evaluate("()=>(document.querySelector('.t-fundstelle')||{}).innerText||''"))
        ruhig(page, '.t-wissen')                     # statt 1500 ms (vorher in seite()): erst tippen, wenn das Werkzeug nicht mehr zeichnet
        page.fill('.t-wissen input.t-wissen-frage', 'Lease')
        page.press('.t-wissen input.t-wissen-frage', 'Enter')
        warte(page, "()=>document.querySelectorAll('.t-wissen-treffer').length > 0")        # statt 1200 ms: die Treffer stehen
        page.locator('.t-wissen-treffer').first.locator('button', has_text='Fundstelle').click()
        # statt 900 ms: die Fundstelle hat ihren Text nachgeladen (vorher steht „Lese …“ dort)
        warte(page, "()=>((document.querySelector('.t-fundstelle')||{}).innerText||'').includes('Vor dem Laden die Lease') && !!document.querySelector('.t-fundstelle mark')")
        self.assertIn('Vor dem Laden die Lease', page.evaluate("()=>document.querySelector('.t-fundstelle').innerText"))
        self.assertGreater(page.locator('.t-fundstelle mark').count(), 0)
        feld = page.locator('.t-talk-in input, .t-talk-in textarea').first
        feld.fill('Wann hole ich die Lease?'); feld.press('Enter')
        # statt 1500 ms: die Antwort mit dem Verweis steht im Gespräch
        warte(page, "()=>{ const l = document.querySelector('.t-talk-log'); return !!l && l.innerText.includes('Das habe ich im Wissen gefunden') && !!l.querySelector('.t-wissen-zitat'); }")
        log = page.evaluate("()=>document.querySelector('.t-talk-log').innerText")
        self.assertIn('Das habe ich im Wissen gefunden', log)
        self.assertGreater(page.locator('.t-talk-log .t-wissen-zitat').count(), 0, 'die Kennung ist ein Verweis')
        self.assertEqual(self.fehler, [])

    def test_frage_bleibt_ueber_das_neuladen_aber_nicht_im_browser(self):
        self.skipTest('im Cockpit geprüft (WissenImCockpit)')

    def test_suche_ist_start_und_der_reiter_aendert_die_werkbank(self):
        self.skipTest('im Cockpit geprüft (WissenImCockpit)')


if __name__ == '__main__':
    unittest.main()
