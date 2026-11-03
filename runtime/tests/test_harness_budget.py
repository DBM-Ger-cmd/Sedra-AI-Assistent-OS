"""Antwortbudget (03.11.2026, Log S-7753709B): verbraucht das Denken das ganze Budget eines Aufrufs und die Antwort bleibt leer, versucht SEDRA es einmal mit doppeltem Budget und
begrenztem Denken; das Budget ist wählbar; das heutige Datum steht im Systemprompt (sonst rät das Modell ein Datum)."""
import re
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.harness import schleife
from guppi_runtime.harness.api import OPTIONEN, HarnessApi
from guppi_runtime.harness.sitzung import Sitzungen
from guppi_runtime.harness.strom import Stroeme

from test_harness_schleife import MISSION, Attrappe, Box, Zug


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sitzungen = Sitzungen(Path(self.tmp.name))
        self.sid = self.sitzungen.anlegen('p')['id']
        self.antwort = Stroeme().anlegen(self.sid)

    def lauf(self, attrappe, **kw):
        return schleife.laufen(attrappe, MISSION, Box(), [{'role': 'user', 'content': 'Hallo'}], self.antwort, modell='m', sitzungen=self.sitzungen, sitzung_id=self.sid, **kw)

    def ereignisse(self):
        return [(e['event'], e['data']) for e in self.antwort.lesen(0, timeout=0)]


class DenkenFrisstBudget(Basis):
    def test_leere_antwort_wegen_des_denkens_bekommt_einen_zweiten_versuch_mit_mehr_budget_und_begrenztem_denken(self):
        a = Attrappe([Zug('', denken='x' * 50, finish='length'), Zug('Jetzt mit Antwort.')])
        out = self.lauf(a, max_tokens=2048)
        self.assertEqual(out['text'], 'Jetzt mit Antwort.')
        self.assertEqual(out['ende'], 'antwort')
        erster, zweiter = a.requests
        self.assertEqual(erster['max_tokens'], 2048)
        self.assertNotIn('thinking_budget_tokens', erster)
        self.assertEqual(zweiter['max_tokens'], 4096)                                        # doppeltes Budget
        self.assertEqual(zweiter['thinking_budget_tokens'], schleife.DENKEN_BUDGET)          # begrenztes Denken
        self.assertNotIn('tools', zweiter)                                                   # und ohne Werkzeuge, wie bisher
        self.assertIn(('denken.begrenzt', {'max_tokens': 4096, 'budget': schleife.DENKEN_BUDGET}), self.ereignisse())

    def test_ist_auch_der_zweite_versuch_leer_sagt_der_fehler_was_zu_tun_ist(self):
        a = Attrappe([Zug('', denken='x', finish='length'), Zug('', denken='y', finish='length')])
        out = self.lauf(a, max_tokens=2048)
        self.assertEqual(out['ende'], 'fehler')
        self.assertIn('Token-Grenze beim Denken erreicht', out['grund'])
        self.assertIn('zweiten Versuch', out['grund'])
        self.assertIn('Token und Gespräch', out['grund'])
        self.assertEqual(len(a.requests), 2)                                                 # nicht endlos weiter

    def test_das_budget_wird_nie_ueber_8192_verdoppelt_und_ein_gewaehltes_denken_bleibt(self):
        a = Attrappe([Zug('', finish='length'), Zug('ok')])
        self.lauf(a, max_tokens=8192)
        self.assertEqual(a.requests[1]['max_tokens'], 8192)
        b = Attrappe([Zug('', finish='length'), Zug('ok')])
        self.antwort = Stroeme().anlegen(self.sitzungen.anlegen('p')['id'])
        self.lauf(b, max_tokens=2048, denk_modus='aus')
        self.assertEqual(b.requests[1]['reasoning_effort'], 'none')                          # „aus“ bleibt aus, es wird nicht auf „begrenzt“ gedreht
        self.assertNotIn('thinking_budget_tokens', b.requests[1])

    def test_eine_normale_antwort_aendert_nichts(self):
        a = Attrappe([Zug('Gleich da.')])
        self.lauf(a, max_tokens=2048)
        self.assertEqual(a.requests[0]['max_tokens'], 2048)
        self.assertNotIn('denken.begrenzt', [n for n, _ in self.ereignisse()])


class OptionUndDatum(unittest.TestCase):
    def test_das_antwortbudget_ist_waehlbar(self):
        standard, erlaubt = OPTIONEN['antwort_budget']
        self.assertEqual((standard, erlaubt), ('2048', ('2048', '4096', '8192')))
        api = HarnessApi.__new__(HarnessApi)
        api._laufzeit_vorgaben = lambda: {'antwort_budget': '4096'}
        self.assertEqual(api._option('antwort_budget'), '4096')
        api._laufzeit_vorgaben = lambda: {'antwort_budget': '999999'}
        self.assertEqual(api._option('antwort_budget'), '2048')

    def test_das_datum_steht_im_systemprompt_mit_und_ohne_vorlage(self):
        for vorlage in (None, 'Du bist der MasterChat.'):
            s = schleife.system_prompt('P', [], vorlage, None, '2026-11-03')
            self.assertIn('Heute ist der 2026-11-03', s)
            self.assertNotIn('Heute ist der', schleife.system_prompt('P', [], vorlage))
        self.assertIn('Halte dein Denken kurz', schleife.system_prompt('P', [], None))
        from guppi_runtime.harness import verbrauch
        self.assertRegex(verbrauch.heute(), r'^\d{4}-\d{2}-\d{2}$')

    def test_der_masterchat_nimmt_das_datum_aus_dem_systemprompt(self):
        text = (Path(__file__).resolve().parents[1] / 'config' / 'harness_vorlagen' / 'masterchat.md').read_text(encoding='utf-8')
        self.assertIn('Heute ist der', text)
        self.assertIn('rate nie ein anderes', text)
        self.assertIn('Halte dein Denken kurz', text)


if __name__ == '__main__':
    unittest.main()
