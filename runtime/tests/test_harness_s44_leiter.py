"""S4.4 (Spec Freigaben S4, FS-20/FS-21): die Leiter auf der Karte – „Befristet“ (Aufgabe, 2 Stunden, 50 Aufrufe) und „Immer“ (nur ein Antrag an den
Katalog, nichts wird selbst geschrieben). Gleicher Aufbau wie die Sitzungs-Erlaubnis-Tests (echter Server mit Attrappen-Modell)."""
import unittest
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401  (Klasse H aus der Seite: im Test aus, wie in den anderen Servertests)
from sedra_runtime.desk import freigabeklasse
from sedra_runtime.harness import freigabe
from test_harness_bau_2026_11_01 import SitzungsErlaubnisServer as Basis
from test_uix_harness_api import anfrage, strom


class LeiterServer(Basis):
    def _karte(self):
        sid = self.sitzung([('calls', [('datei_schreiben', {'pfad': 'docs/eins.md', 'inhalt': 'eins\n'})]),
                            ('calls', [('datei_schreiben', {'pfad': 'docs/zwei.md', 'inhalt': 'zwei\n'})]),
                            ('text', 'Fertig.')])
        ev = self.senden(sid, 'Leg docs/eins.md und docs/zwei.md an')
        self.assertEqual(ev[-1][2]['ende'], 'wartet')
        kid = next(e[2] for e in ev if e[1] == 'karte')['karte_id']
        self.warte_threads()
        return sid, kid

    def test_befristet_legt_eine_aufgabe_an_und_spart_die_naechste_karte(self):
        sid, kid = self._karte()
        code, out = anfrage(self.url, 'POST', f'/api/harness/karten/{kid}', {'weg': 'befristet'})
        self.assertEqual(code, 200, out)
        self.assertEqual((out['weg'], out['ergebnis_status']), ('befristet', 'ok'))
        self.assertEqual((out['erlaubnis']['dauer'], out['erlaubnis']['muster']), ('befristet', 'docs/**'))
        self.assertIn('Befristet erlaubt: 2 Stunden, höchstens 50 Aufrufe', out['erlaubnis']['hinweis'])
        enden = [e[2] for e in strom(self.url, out['antwort_id']) if e[1] == 'werkzeug.ende']
        self.assertEqual([(x['status'], x['stufe']) for x in enden], [('ok', 'aufgabe')], 'die zweite Datei läuft über die befristete Erlaubnis ohne Karte')
        self.assertEqual((self.wurzel / 'docs' / 'zwei.md').read_text(encoding='utf-8'), 'zwei\n')
        self.assertIn(('erteilt', 'befristet', 'aufgabe'), [(p['aktion'], p['dauer'], p['herkunft']) for p in self.audit('HARNESS_ERLAUBNIS')])
        code, aufgaben = anfrage(self.url, 'GET', '/api/harness/aufgaben')
        self.assertEqual(code, 200, aufgaben)
        liste = aufgaben.get('aufgaben', aufgaben) if isinstance(aufgaben, dict) else aufgaben
        a = [x for x in liste if str(x.get('titel', '')).startswith('Befristet:')]
        self.assertEqual(len(a), 1)
        self.assertEqual((a[0]['ende']['max_aufrufe'], a[0]['sitzungen']), (50, [sid]))

    def test_immer_stellt_nur_einen_antrag_und_schreibt_den_katalog_nicht(self):
        sid, kid = self._karte()
        katalog = self.wurzel / 'runtime' / 'local_config' / 'freigabe_katalog.yaml'
        vorher = katalog.exists()
        code, out = anfrage(self.url, 'POST', f'/api/harness/karten/{kid}', {'weg': 'immer'})
        self.assertEqual(code, 200, out)
        self.assertEqual((out['weg'], out['ergebnis_status'], out['erlaubnis']['dauer']), ('immer', 'ok', 'immer'))
        self.assertIn('Antrag', out['erlaubnis']['hinweis'])
        self.assertEqual([(p['aktion'], p['dauer']) for p in self.audit('HARNESS_ERLAUBNIS')][-1:], [('erteilt', 'immer')])
        self.assertEqual(katalog.exists(), vorher, 'nichts wird selbst geschrieben')
        enden = [e[2] for e in strom(self.url, out['antwort_id']) if e[1] == 'werkzeug.ende']
        self.assertEqual([x['status'] for x in enden], ['wartet'], 'ohne Freigabe des Antrags bleibt die nächste Datei eine Karte')

    def test_gegenprobe_befristet_und_immer_gehen_durch_die_tuer_der_klasse_h(self):                      # FS-21
        for weg in ('befristet', 'immer'):
            sid, kid = self._karte()
            davor = len(self.audit('HARNESS_ERLAUBNIS'))
            with mock.patch('sedra_runtime.uix_server.UIXHub._freigabe_ausserhalb', lambda self: True):
                code, out = anfrage(self.url, 'POST', f'/api/harness/karten/{kid}', {'weg': weg})
            self.assertEqual(code, 400, out)
            self.assertIn('wartet_auf_bestaetigung', out['message'], weg)
            self.assertEqual(len(self.audit('HARNESS_ERLAUBNIS')), davor, 'nichts erteilt, solange die Bestätigung außerhalb des Browsers fehlt')
            break


for _name in [n for n in dir(Basis) if n.startswith('test_')]:
    setattr(LeiterServer, _name, None)           # die geerbten Tests laufen schon in ihrer eigenen Datei


class KlasseUndWegeTests(unittest.TestCase):
    def test_neue_wege_sind_bekannt_und_klasse_h(self):                    # FS-21
        for weg in ('befristet', 'immer'):
            self.assertIn(weg, freigabe.WEGE)
            self.assertIn(weg, freigabeklasse.WEGE)
            self.assertEqual(freigabeklasse.klasse('harness_freigabe', weg, {'werkzeug': 'datei_schreiben', 'ziel': 'docs/a.md'}), freigabeklasse.H)

    def test_gegenprobe_nicht_angeboten_bei_vorbehalt_warnkarte_verboten_modell(self):          # FS-20
        from sedra_runtime.harness import erlaubnis
        for extra in ({'vorbehalt': 'v'}, {'warnung': {'t': 1}}, {'stufe': 'verboten'}):
            self.assertFalse(erlaubnis.erlaubt_fuer_karte({'art': 'werkzeug', 'werkzeug': 'datei_schreiben', 'ziel': 'docs/a.md', **extra}))
        self.assertFalse(erlaubnis.erlaubt_fuer_karte({'art': 'werkzeug', 'werkzeug': 'modell_laden', 'ziel': 'x'}))

    def test_nur_der_captain_kann_befristet_oder_immer(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            karten = freigabe.Karten(Path(tmp))
            k = karten.anlegen({'sitzung_id': 'S-1', 'werkzeug': 'datei_schreiben', 'args': {}, 'ziel': 'docs/a.md', 'art': 'werkzeug', 'stufe': 'captain',
                                'regel': 'r', 'begruendung': 'b', 'vorbehalt': None, 'vorschau': '', 'gate': {}, 'warnung': None, 'an': 'captain'})
            for weg in ('befristet', 'immer'):
                with self.assertRaises(ValueError):
                    freigabe.beantworten(karten, k['karte_id'], weg, von='vorarbeiter:S-2', guard=None, werkzeuge_fuer=lambda c: None)


if __name__ == '__main__':
    unittest.main()
