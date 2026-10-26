"""Werkzeug „Wissen“ v2 im Cockpit, im echten Browser (SPEC_WERKZEUG_WISSEN_v2 §3, WZ1–WZ3, §3.8).

Die Suche ist die Startansicht; ein Reiterwechsel ändert die Werkbank-Zeile der Shell (object.actions); „Ins Gespräch“ setzt die Kennung
ins Eingabefeld des Gesprächs; die Frage liegt nach dem Neuladen wieder im Feld, aber nie im Browser-Speicher.
"""
import unittest

from test_uix_dock_stufe2 import Basis


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
        page.wait_for_selector('.t-wissen', timeout=5000)
        self.assertGreater(page.locator('.t-wissen .t-wissen-tab').count(), 0, 'der Schalter wissen ist im Prüfprojekt an')

    def zeile(self, page):
        return page.evaluate("()=>[...document.querySelectorAll('.dk-group')].map(g=>(g.querySelector('.dk-verbs')||{}).innerText||'').join(' | ')")

    def test_suche_ist_start_und_der_reiter_aendert_die_werkbank(self):
        page = self.seite()
        self.wissen(page)
        self.assertEqual(page.evaluate("()=>document.querySelector('.t-wissen-tab.on').dataset.ansicht"), 'suche')
        self.assertIn('Neue Suche', self.zeile(page))
        page.locator('.t-wissen-tab', has_text='Quellen').click(); page.wait_for_timeout(700)
        self.assertIn('Quelle beantragen', self.zeile(page))
        self.assertNotIn('Neue Suche', self.zeile(page))
        self.assertEqual(self.fehler, [])

    def test_frage_bleibt_ueber_das_neuladen_aber_nicht_im_browser(self):
        page = self.seite()
        self.wissen(page)
        page.fill('.t-wissen input.t-wissen-frage', 'Lease Index Abdeckung')
        page.press('.t-wissen input.t-wissen-frage', 'Enter'); page.wait_for_timeout(1500)
        self.assertTrue(page.evaluate("()=>!!document.querySelector('.t-wissen-ergebnis, .t-wissen .s-empty, .t-wissen .s-note.bad')"), 'Enter hat gesucht')
        treffer = page.locator('.t-wissen-treffer').count()
        self.assertGreater(treffer, 0, 'die Quelle des Prüfprojekts hat Treffer')
        if treffer:
            page.locator('.t-wissen-treffer').first.locator('button', has_text='Ins Gespräch').click(); page.wait_for_timeout(400)
            self.assertRegex(page.evaluate("()=>(document.querySelector('.t-talk-in input, .t-talk-in textarea')||{}).value||''"), r'\[W[0-9a-f]+\]')
        page.wait_for_timeout(800)                                             # die Ablage bündelt (500 ms)
        page.reload(); self.uix.wait_until_started(page); page.wait_for_timeout(1500)
        page.wait_for_selector('.t-wissen input.t-wissen-frage', timeout=5000)
        self.assertEqual(page.input_value('.t-wissen input.t-wissen-frage'), 'Lease Index Abdeckung')
        gespeichert = page.evaluate("()=>JSON.stringify(Object.assign({}, localStorage)) + JSON.stringify(Object.assign({}, sessionStorage))")
        self.assertNotIn('Lease Index', gespeichert)
        self.assertEqual(self.fehler, [])



if __name__ == '__main__':
    unittest.main()
