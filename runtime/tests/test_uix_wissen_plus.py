"""Das Plus im Werkzeug „Wissen“, im echten Browser: Datei ziehen -> Eingang -> geführter Antrag ab Schritt 3 -> Freigabe -> Suche findet es.

Der Windows-Dialog selbst ist ein Fenster des Systems und wird hier nicht geöffnet; sein Ergebnis (kopierte Dateien in den Eingang) prüft
test_wissen_eingang.py mit einem ersetzten Aufruf. Hier: das Ziehen mit einer echten DataTransfer-Datei, Abbrechen räumt den Eingang auf.
"""
import unittest

from test_uix_wissen_v2 import WissenImCockpit, mit_quelle  # noqa: F401
from test_uix_dock_stufe2 import WARTE_MS

DROP = """async({name, text})=>{
  const dt = new DataTransfer();
  dt.items.add(new File([text], name, {type: 'text/markdown'}));
  const ziel = document.querySelector('.t-wissen-drop');
  ziel.dispatchEvent(new DragEvent('dragover', {dataTransfer: dt, bubbles: true, cancelable: true}));
  ziel.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true}));
}"""


class PlusImCockpit(WissenImCockpit):
    @classmethod
    def setUpClass(cls):
        import sys
        from test_uix_dock_stufe2 import BENCH, Basis
        sys.path.insert(0, str(BENCH))
        import uix_check
        orig = uix_check.start_server

        def vorbereiten(hub):
            mit_quelle(hub)
            cls.hub = hub
        uix_check.start_server = lambda say, shell=None, prepare=None: orig(say, shell=shell, prepare=vorbereiten, switches={'wissen': True})
        try:
            Basis.setUpClass.__func__(cls)
        finally:
            uix_check.start_server = orig

    def quellen(self, page):
        self.oeffnen(page, {'type': 'wissen', 'id': 'speicher', 'title': 'Wissen'})
        page.wait_for_selector('.t-wissen .t-wissen-tab', timeout=WARTE_MS)
        page.locator('.t-wissen-tab', has_text='Quellen').click()
        page.wait_for_selector('.t-wissen-plus-knopf', timeout=WARTE_MS)

    def eingaenge(self):
        ordner = self.hub.project_root / 'local_config' / 'wissen' / 'eingang'
        return sorted(p.name for p in ordner.iterdir()) if ordner.is_dir() else []

    def test_ziehen_fuehrt_zum_antrag_und_nach_der_freigabe_zur_suche(self):
        page = self.seite()
        self.quellen(page)
        page.get_by_role('button', name='Wissen hinzufügen', exact=True).first.click()
        page.wait_for_selector('.t-wissen-drop', timeout=WARTE_MS)
        page.evaluate(DROP, {'name': 'zebra.md', 'text': '# Zebrastreifen\n\nDer Zebrastreifenbeweis steht im Eingang des Wissens.\n'})
        page.wait_for_selector('.t-wissen-antrag', timeout=WARTE_MS)
        self.assertIn('Schritt 3 von 4', page.locator('.t-wissen-antrag').inner_text())
        self.assertEqual(len(self.eingaenge()), 1, 'die Datei liegt im Eingang des Projekts')
        page.get_by_role('button', name='Weiter', exact=True).click()
        page.get_by_role('button', name='Antrag stellen', exact=True).wait_for(timeout=WARTE_MS)
        self.assertIn('1 Datei im Eingang', page.locator('.t-wissen-antrag').inner_text())
        page.get_by_role('button', name='Antrag stellen', exact=True).click()
        page.wait_for_function("()=>!document.querySelector('.t-wissen-antrag')", timeout=WARTE_MS)
        # der Antrag wartet: bis zur Freigabe ist nichts im Wissen
        self.assertEqual(self.hub.runtime.wissen.suche('Zebrastreifenbeweis', leser={'art': 'captain', 'stufe': 6, 'projekt': None, 'agent_id': None},
                                                       k=3, route='local')['treffer'], [])
        offen = [x for x in self.hub.decisions_view()['items'] if 'zebra' in str(x).lower() or 'eingang' in str(x).lower()]
        self.assertTrue(offen, 'der Antrag steht im Posteingang')
        offen = offen[-1]
        self.hub.decide({'id': offen['id'], 'way': 'freigeben_und_anwenden'})
        treffer = self.hub.runtime.wissen.suche('Zebrastreifenbeweis', leser={'art': 'captain', 'stufe': 6, 'projekt': None, 'agent_id': None},
                                                k=3, route='local')['treffer']
        self.assertTrue(any('Zebrastreifenbeweis' in t['text'] for t in treffer))
        self.assertEqual(self.fehler, [])

    def test_abbrechen_raeumt_den_eingang_auf(self):
        page = self.seite()
        self.quellen(page)
        vorher = self.eingaenge()
        page.get_by_role('button', name='Wissen hinzufügen', exact=True).first.click()
        page.wait_for_selector('.t-wissen-drop', timeout=WARTE_MS)
        page.evaluate(DROP, {'name': 'weg.md', 'text': '# Weg\n\nDas wird nicht gebraucht.\n'})
        page.wait_for_selector('.t-wissen-antrag', timeout=WARTE_MS)
        self.assertEqual(len(self.eingaenge()), len(vorher) + 1)
        page.locator('.t-wissen-antrag').get_by_role('button', name='Abbrechen', exact=True).click()
        page.wait_for_function("()=>!document.querySelector('.t-wissen-antrag')", timeout=WARTE_MS)
        for _ in range(40):
            if self.eingaenge() == vorher:
                break
            page.wait_for_timeout(100)
        self.assertEqual(self.eingaenge(), vorher)

    def test_fremde_dateiart_wird_freundlich_abgelehnt(self):
        page = self.seite()
        self.quellen(page)
        page.get_by_role('button', name='Wissen hinzufügen', exact=True).first.click()
        page.wait_for_selector('.t-wissen-drop', timeout=WARTE_MS)
        page.evaluate(DROP, {'name': 'programm.exe', 'text': 'MZ'})
        page.wait_for_selector('.t-wissen-plus .s-note.bad', timeout=WARTE_MS)
        self.assertIn('nichts, was das Wissen lesen kann', page.locator('.t-wissen-plus .s-note.bad').inner_text())
        self.assertFalse(page.locator('.t-wissen-antrag').count())


if __name__ == '__main__':
    unittest.main()
