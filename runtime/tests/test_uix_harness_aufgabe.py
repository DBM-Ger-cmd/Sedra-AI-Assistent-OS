"""N3 der Harness-Shell Stufe 3 (mit Server, ohne Modell): Aufgaben-Freigabe im Ablauf – Aufruf in der Aufgabe ohne Karte, außerhalb mit Karte,
Zähler, Rücknahme, andere Sitzung, `verboten`, harter Vorbehalt, Warnkarte; Wege `aufgaben`. Ersetzt werden nur `geladen` und `execute` (Modell)."""
import json
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.uix_server import UIXHub, make_server
from test_uix_harness_api import ARCH, MODELL, anfrage, strom
from test_uix_harness_freigabe import Skript

ERSTER = 'docs/log.md'


class AufgabeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-aufgabe-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        (cls.wurzel / 'docs' / 'local_config').mkdir(parents=True)
        (cls.wurzel / '.env').write_text('GEHEIM=1\n', encoding='utf-8')
        projekt = Path(cls.tmp.name) / 'project'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'harness_projekte.yaml').write_text(
            f"projekte:\n  - id: pruef\n    name: Prüfprojekt\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [docs/**]\n", encoding='utf-8')
        cls.hub = UIXHub(projekt, ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def setUp(self):
        (self.wurzel / 'docs' / 'log.md').write_text('# Logbuch\n| a | b |\n', encoding='utf-8')
        (self.wurzel / 'docs' / 'andere.md').write_text('alt\n', encoding='utf-8')
        (self.wurzel / 'docs' / 'gross.md').write_text(''.join(f'Zeile {i}\n' for i in range(100)), encoding='utf-8')
        self.hub.harness.geladen = lambda: (MODELL, None)

    def sitzung(self, zuege=()):
        self.modell = Skript(zuege)
        self.hub.harness.execute = self.modell
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef'})
        self.assertEqual(code, 200, kopf)
        return kopf['id']

    def aufgabe(self, sitzungen, erlaubt, **ende):
        code, a = anfrage(self.url, 'POST', '/api/harness/aufgaben',
                          {'titel': 'Test', 'projekt': 'pruef', 'sitzungen': sitzungen, 'erlaubt': erlaubt, 'ende': ende or {'max_aufrufe': 5}})
        self.assertEqual(code, 200, a)
        return a

    def senden(self, sid, text='los'):
        code, out = anfrage(self.url, 'POST', f'/api/harness/sitzungen/{sid}/nachricht', {'text': text})
        self.assertEqual(code, 200, out)
        return strom(self.url, out['antwort_id'])

    def box(self, sid):
        return self.hub.harness._kiste(self.hub.harness._sitzung(sid))[0]

    def audit(self, event):
        rows = [json.loads(l) for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
        return [r['payload'] for r in rows if r['event_type'] == event]

    @staticmethod
    def aendern(pfad=ERSTER, neu='| c | d |'):
        return ('datei_aendern', {'pfad': pfad, 'alt': '| a | b |' if pfad == ERSTER else 'alt', 'neu': neu})

    def test_aufruf_in_der_aufgabe_laeuft_ohne_karte(self):
        sid = self.sitzung([('calls', [self.aendern()]), ('text', 'Eingetragen.')])
        a = self.aufgabe([sid], [{'werkzeug': 'datei_aendern', 'muster': ERSTER}])
        ev = self.senden(sid, 'Trag c d ein')
        self.assertFalse(any(e[1] == 'karte' for e in ev))
        ende = next(e[2] for e in ev if e[1] == 'werkzeug.ende')
        self.assertEqual((ende['status'], ende['stufe'], ende['regel']), ('ok', 'aufgabe', 'aufgabe:' + a['id']))
        self.assertEqual(ev[-1][2]['ende'], 'erledigt')
        self.assertEqual((self.wurzel / ERSTER).read_text(encoding='utf-8'), '# Logbuch\n| c | d |\n')
        self.assertIn('aufgabe:' + a['id'], [p['approved_by'] for p in self.audit('HARNESS_APPROVED_BY')])
        _c, neu = anfrage(self.url, 'GET', '/api/harness/aufgaben/' + a['id'])
        self.assertEqual((neu['aufrufe'], neu['rest_aufrufe']), (1, 4))

    def test_ausserhalb_andere_sitzung_zaehler_und_ruecknahme_gehen_zur_karte(self):
        sid = self.sitzung()
        fremd = self.sitzung()
        a = self.aufgabe([sid], [{'werkzeug': 'datei_aendern', 'muster': ERSTER}], max_aufrufe=1)
        aid = a['id']
        # außerhalb der Liste → Karte
        r = self.box(sid).aufruf(*self.aendern('docs/andere.md', 'neu'))
        self.assertEqual((r['status'], r['stufe']), ('wartet', 'captain'))
        # andere Sitzung → Karte
        r = self.box(fremd).aufruf(*self.aendern())
        self.assertEqual(r['status'], 'wartet')
        # die letzte erlaubte Verwendung läuft, die nächste ist wieder eine Karte (Zähler erreicht)
        r = self.box(sid).aufruf(*self.aendern())
        self.assertEqual((r['status'], r['stufe']), ('ok', 'aufgabe'))
        _c, neu = anfrage(self.url, 'GET', '/api/harness/aufgaben/' + aid)
        self.assertEqual(neu['status'], 'erschoepft')
        (self.wurzel / ERSTER).write_text('# Logbuch\n| a | b |\n', encoding='utf-8')
        r = self.box(sid).aufruf(*self.aendern())
        self.assertEqual(r['status'], 'wartet')
        # Rücknahme
        b = self.aufgabe([sid], [{'werkzeug': 'datei_aendern', 'muster': ERSTER}])
        self.assertEqual(self.box(sid).aufruf(*self.aendern())['stufe'], 'aufgabe')
        (self.wurzel / ERSTER).write_text('# Logbuch\n| a | b |\n', encoding='utf-8')
        code, z = anfrage(self.url, 'POST', f"/api/harness/aufgaben/{b['id']}/zuruecknehmen", {'grund': 'Test'})
        self.assertEqual((code, z['status']), (200, 'zurueckgenommen'))
        self.assertEqual(self.box(sid).aufruf(*self.aendern())['status'], 'wartet')
        self.assertIn('HARNESS_AUFGABE_ZURUECKGENOMMEN', [e for e in self._ereignisse()])

    def _ereignisse(self):
        rows = [json.loads(l) for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
        return [r['event_type'] for r in rows]

    def test_verboten_vorbehalt_und_warnkarte_werden_nie_gedeckt(self):
        sid = self.sitzung()
        self.aufgabe([sid], [{'werkzeug': 'datei_lesen', 'muster': '**'}, {'werkzeug': 'datei_schreiben', 'muster': 'docs/local_config/**'},
                             {'werkzeug': 'datei_schreiben', 'muster': 'docs/gross.md'}, {'werkzeug': 'datei_aendern', 'muster': 'docs/gross.md'}])
        box = self.box(sid)
        r = box.aufruf('datei_lesen', {'pfad': '.env'})
        self.assertEqual((r['status'], r['stufe']), ('verboten', 'verboten'))
        r = box.aufruf('datei_schreiben', {'pfad': 'docs/local_config/x.md', 'inhalt': 'a'})
        self.assertEqual(r['status'], 'wartet')
        self.assertEqual((r['stufe'], r['regel']), ('captain', 'vorbehalt'))
        # Ersetzung einer langen Datei: erst Hinweis, dann Karte mit Warnkasten – die Aufgabe deckt auch das nicht
        r = box.aufruf('datei_schreiben', {'pfad': 'docs/gross.md', 'inhalt': 'x\n'})
        self.assertEqual(r['status'], 'hinweis')
        r = box.aufruf('datei_schreiben', {'pfad': 'docs/gross.md', 'inhalt': 'x\n'})
        self.assertEqual(r['status'], 'wartet')
        self.assertTrue(r['karte']['warnung'])
        self.assertEqual((self.wurzel / 'docs' / 'gross.md').read_text(encoding='utf-8').count('\n'), 100)

    def test_cloud_modell_wird_nicht_gedeckt(self):
        sid = self.sitzung()
        self.aufgabe([sid], [{'werkzeug': 'datei_aendern', 'muster': ERSTER}])
        box = self.box(sid)
        box._box.lokal = False                       # die Kiste hinter der Begrenzung
        self.assertEqual(box.aufruf(*self.aendern())['status'], 'wartet')
        box._box.lokal = True
        self.assertEqual(box.aufruf(*self.aendern())['stufe'], 'aufgabe')

    def test_wege_und_fehler(self):
        sid = self.sitzung()
        code, body = anfrage(self.url, 'POST', '/api/harness/aufgaben', {'titel': 'x', 'projekt': 'pruef', 'sitzungen': [sid],
                                                                          'erlaubt': [{'werkzeug': 'datei_aendern', 'muster': ERSTER}], 'ende': {}})
        self.assertEqual((code, body['code'].split(':')[0]), (400, 'ende_fehlt'))
        code, body = anfrage(self.url, 'POST', '/api/harness/aufgaben', {'titel': 'x', 'projekt': 'pruef', 'sitzungen': ['S-00000000'],
                                                                          'erlaubt': [{'werkzeug': 'datei_aendern', 'muster': ERSTER}], 'ende': {'max_aufrufe': 1}})
        self.assertEqual((code, body['code'].split(':')[0]), (400, 'sitzung_unbekannt'))
        code, body = anfrage(self.url, 'POST', '/api/harness/aufgaben', {'titel': 'x', 'projekt': 'gibt-es-nicht', 'sitzungen': [sid],
                                                                          'erlaubt': [{'werkzeug': 'datei_aendern', 'muster': ERSTER}], 'ende': {'max_aufrufe': 1}})
        self.assertEqual(code, 400)
        self.assertEqual(anfrage(self.url, 'GET', '/api/harness/aufgaben/T-00000000')[0], 404)
        a = self.aufgabe([sid], [{'werkzeug': 'befehl', 'muster': 'git *'}])
        self.assertTrue(a['warnungen'], 'ein weites Muster ist beim Captain erlaubt, mit Warnung')
        self.assertEqual(a['von'], 'captain')
        code, liste = anfrage(self.url, 'GET', '/api/harness/aufgaben')
        self.assertIn(a['id'], [x['id'] for x in liste['aufgaben']])
        self.assertEqual(anfrage(self.url, 'POST', f"/api/harness/aufgaben/{a['id']}/zuruecknehmen", {})[0], 200)
        self.assertEqual(anfrage(self.url, 'POST', f"/api/harness/aufgaben/{a['id']}/zuruecknehmen", {})[0], 400, 'zweimal zurücknehmen geht nicht')


if __name__ == '__main__':
    unittest.main()
