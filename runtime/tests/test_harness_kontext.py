"""Kontextfenster (02.11.2026): vor dem Senden schätzen, bei 90 % stärker kürzen (mit Marke), bei 95 % ohne Werkzeuge abschließen, bei 100 % klar enden."""
import json
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.harness import kontext, schleife
from sedra_runtime.harness.sitzung import Sitzungen
from sedra_runtime.harness.strom import Stroeme

from test_harness_schleife import MISSION, Attrappe, Box, Zug, call


class SchaetzenTests(unittest.TestCase):
    def test_stufen(self):
        self.assertEqual([kontext.pruefen(n, 1000) for n in (100, 899, 900, 949, 950, 999, 1000, 2000)],
                         ['ok', 'ok', 'kuerzen', 'kuerzen', 'abschluss', 'abschluss', 'voll', 'voll'])
        self.assertEqual(kontext.pruefen(10 ** 9, None), 'ok')                          # ohne bekanntes Fenster nichts erzwingen

    def test_die_schaetzung_geht_nach_zeichen_und_beruecksichtigt_die_reserve(self):
        msgs = [{'role': 'user', 'content': 'x' * 3000}]
        self.assertEqual(kontext.schaetzen(msgs), 1000)
        self.assertEqual(kontext.schaetzen(msgs, reserve=500), 1500)
        self.assertGreater(kontext.schaetzen(msgs, schemas=[{'a': 'b' * 400}]), 1000)

    def test_die_echte_belegung_zaehlt_und_die_schaetzung_unterbietet_sie_nie(self):
        msgs = [{'role': 'user', 'content': 'x' * 300}, {'role': 'assistant', 'content': 'y' * 300}, {'role': 'tool', 'content': 'z' * 3000}]
        echt = {'belegt': 5000, 'anzahl': 2}                                              # 5000 echte Token bei 2 Nachrichten; dazu kommt das Ergebnis (3000 Zeichen)
        self.assertEqual(kontext.schaetzen(msgs, letzte=echt), 5000 + 1000)
        self.assertGreaterEqual(kontext.schaetzen(msgs, letzte={'belegt': 10, 'anzahl': 2}), 400)

    def test_der_hinweis_nennt_den_weg(self):
        h = kontext.hinweis_voll(66000, 65536)
        self.assertIn('66.000 von 65.536', h)
        self.assertIn('neue Sitzung', h)


class GrosseBox(Box):
    """Wie die Box der Schleifen-Tests, aber jedes Ergebnis ist groß."""
    def call(self, name, args):
        self.calls.append((name, args))
        return 'Ergebnis ' + 'lang ' * 800


class SchleifeKontext(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sitzungen = Sitzungen(Path(self.tmp.name))
        self.sid = self.sitzungen.anlegen('p')['id']
        self.antwort = Stroeme().anlegen(self.sid)
        self.box = GrosseBox()

    def lauf(self, attrappe, **kw):
        return schleife.laufen(attrappe, MISSION, self.box, [{'role': 'user', 'content': 'Hallo'}], self.antwort, modell='m',
                               sitzungen=self.sitzungen, sitzung_id=self.sid, **kw)

    def ereignisse(self):
        return [(e['event'], e['data']) for e in self.antwort.lesen(0, timeout=0)]

    def gross(self, n):
        return Zug('', calls=[call('zustand', {'n': n})])

    def test_kein_handeln_solange_es_passt(self):
        a = Attrappe([Zug('Kurz.')])
        self.lauf(a, fenster=65536)
        self.assertNotIn('kontext.gekuerzt', [n for n, _ in self.ereignisse()])

    def test_bei_neunzig_prozent_wird_gekuerzt_und_markiert_und_es_geht_weiter(self):
        a = Attrappe([self.gross(i) for i in range(5)] + [Zug('Fertig.')])
        out = self.lauf(a, fenster=4000, max_tokens=100)
        gekuerzt = [d for n, d in self.ereignisse() if n == 'kontext.gekuerzt']
        self.assertTrue(gekuerzt, 'es wurde gekürzt')
        self.assertLess(gekuerzt[0]['nachher'], gekuerzt[0]['vorher'])
        gesendet = json.dumps([r['messages'] for r in a.requests], ensure_ascii=False)
        self.assertIn(kontext.MARKE.strip()[:12], gesendet)                              # die gekürzte Stelle ist für das Modell erkennbar
        self.assertIn(out['ende'], ('antwort', 'fehler', 'erledigt', 'nur_plan'))

    def test_ist_es_auch_gekuerzt_zu_voll_endet_die_antwort_mit_klarem_hinweis_und_ohne_serveraufruf(self):
        a = Attrappe([Zug('Nie gesendet.')])
        out = self.lauf(a, fenster=300, max_tokens=2048)                                 # schon die Reserve sprengt das Fenster
        self.assertEqual(out['ende'], 'fehler')
        self.assertIn('Kontextfenster ist fast voll', out['grund'])
        self.assertEqual(a.requests, [], 'der Server wurde nicht belastet')
        self.assertEqual(self.sitzungen.laden(self.sid)['eintraege'][-1]['ende'], 'fehler')

    def test_der_fuellstand_steht_in_der_sitzungszeile(self):
        a = Attrappe([Zug('Antwort.', usage={'input_tokens': 1234, 'output_tokens': 5})])
        self.lauf(a, fenster=65536)
        self.assertEqual(self.sitzungen.laden(self.sid)['eintraege'][-1]['kontext'], [1234, 65536])


if __name__ == '__main__':
    unittest.main()
