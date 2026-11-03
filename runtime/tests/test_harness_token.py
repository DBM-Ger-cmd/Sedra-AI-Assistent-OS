"""Token-Verbrauch (02.11.2026): Zelle „Token“ und Seite „Token und Gespräch“ lesen GET /api/harness/token; gezählt wird aus den Modellzeilen der Sitzungen."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from guppi_runtime.harness import schleife, verbrauch
from guppi_runtime.harness.api import HarnessApi
from guppi_runtime.harness.sitzung import Sitzungen
from guppi_runtime.harness.strom import Stroeme

from test_harness_schleife import MISSION, Attrappe, Box, Zug, call


def modell(zeit, ein, aus, zuege=1, modell_s=None, kontext=None, aid='A-00000001'):
    e = {'typ': 'modell', 'antwort_id': aid, 'zeit': zeit, 'text': 'x', 'token': {'ein': ein, 'aus': aus}, 'zuege': zuege}
    if modell_s is not None:
        e['modell_s'] = modell_s
    if kontext:
        e['kontext'] = kontext
    return e


class SummeTests(unittest.TestCase):
    def test_summe_zaehlt_nur_modellzeilen_mit_token(self):
        eintraege = [{'typ': 'captain', 'text': 'hallo'}, modell('2026-11-02T10:00:00+01:00', 3000, 200, 2, 10.0, [2500, 65536], 'A-1'),
                     {'typ': 'werkzeug', 'name': 'x'}, modell('2026-11-02T10:05:00+01:00', 4000, 300, 1, 5.0, [3100, 65536], 'A-2'),
                     {'typ': 'modell', 'antwort_id': 'A-3', 'text': 'alt, ohne Zahlen'}]
        s = verbrauch.summe(eintraege)
        self.assertEqual((s['antworten'], s['zuege'], s['ein'], s['aus']), (2, 3, 7000, 500))
        self.assertEqual(s['modell_s'], 15.0)
        self.assertEqual(s['tok_s'], round(500 / 15.0, 1))
        self.assertEqual(s['letzte'], {'antwort_id': 'A-2', 'ein': 4000, 'aus': 300, 'zuege': 1, 'tok_s': 60.0})
        self.assertEqual(s['kontext'], {'belegt': 3100, 'fenster': 65536})

    def test_ohne_zeit_kein_tempo_und_ohne_zahlen_nichts(self):
        s = verbrauch.summe([modell('2026-11-02T10:00:00+01:00', 100, 10)])
        self.assertIsNone(s['tok_s'])
        self.assertIsNone(s['letzte']['tok_s'])
        leer = verbrauch.summe([])
        self.assertEqual((leer['antworten'], leer['ein'], leer['letzte']), (0, 0, None))

    def test_ein_tag_zaehlt_nur_dessen_zeilen_und_kaputte_werte_sind_null(self):
        e = [modell('2026-11-01T23:59:00+01:00', 100, 10), modell('2026-11-02T00:01:00+01:00', 200, 20)]
        self.assertEqual(verbrauch.summe(e, '2026-11-02')['ein'], 200)
        k = verbrauch.summe([{'typ': 'modell', 'token': {'ein': 'viel', 'aus': -5}, 'zuege': 'x'}])
        self.assertEqual((k['ein'], k['aus'], k['zuege']), (0, 0, 0))


class SchleifeModellzeit(unittest.TestCase):
    def test_die_modellzeit_steht_in_der_sitzungszeile(self):
        with tempfile.TemporaryDirectory() as tmp:
            sitzungen = Sitzungen(Path(tmp))
            sid = sitzungen.anlegen('p')['id']
            antwort = Stroeme().anlegen(sid)
            uhr = iter(x * 2.0 for x in range(1, 50))                              # jeder Aufruf der Uhr = 2 s später
            schleife.laufen(Attrappe([Zug('Antwort.', usage={'input_tokens': 100, 'output_tokens': 20})]), MISSION, Box(), [{'role': 'user', 'content': 'Hallo'}], antwort,
                            modell='m', sitzungen=sitzungen, sitzung_id=sid, clock=lambda: next(uhr))
            zeile = [e for e in sitzungen.laden(sid)['eintraege'] if e['typ'] == 'modell'][-1]
            self.assertGreater(zeile['modell_s'], 0)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sitzungen = Sitzungen(Path(self.tmp.name))
        self.api = HarnessApi.__new__(HarnessApi)
        self.api.sitzungen = self.sitzungen
        self.api._laufzeit_vorgaben = lambda: {'gedanken_zurueck': 'kurz'}
        heute = datetime.now().astimezone().replace(microsecond=0).isoformat()
        self.a = self.sitzungen.anlegen('p')['id']
        self.b = self.sitzungen.anlegen('p')['id']
        self.sitzungen.anhaengen(self.a, modell(heute, 1000, 100, 2, 4.0, [900, 65536], 'A-A'))
        self.sitzungen.anhaengen(self.b, modell(heute, 2000, 300, 1, 6.0, [1500, 65536], 'A-B'))
        self.sitzungen.anhaengen(self.b, modell('2020-01-01T10:00:00+01:00', 9999, 999, 1, 1.0, None, 'A-ALT'))     # vor Jahren: zählt nicht zu heute

    def test_die_sitzung_und_der_tag_und_die_vorgaben(self):
        out = self.api.token_stand(self.a)
        self.assertEqual((out['sitzung']['ein'], out['sitzung']['aus']), (1000, 100))
        h = out['heute']
        self.assertEqual((h['antworten'], h['sitzungen'], h['ein'], h['aus']), (2, 2, 3000, 400))
        self.assertEqual(h['tok_s'], round(400 / 10.0, 1))
        self.assertEqual(out['vorgaben']['gedanken_zurueck'], 'kurz')
        self.assertEqual(out['vorgaben']['verlauf_zusammenfassen'], 'auto')
        self.assertEqual(self.api.token_stand('')['sitzung'], None)                           # ohne Sitzung nur der Tag

    def test_eine_unbekannte_sitzung_ist_ein_fehler_mit_grund(self):
        with self.assertRaises(Exception):
            self.api.token_stand('S-00000000')


if __name__ == '__main__':
    unittest.main()
