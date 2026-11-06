"""Token-Verbrauch (02.11.2026): Zelle „Token“ und Seite „Token und Gespräch“ lesen GET /api/harness/token; gezählt wird aus den Modellzeilen der Sitzungen."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sedra_runtime.harness import schleife, verbrauch
from sedra_runtime.harness.api import HarnessApi
from sedra_runtime.harness.sitzung import Sitzungen
from sedra_runtime.harness.strom import Stroeme

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


class CacheMessung(unittest.TestCase):
    """Cache-Messung (05.11.2026): wie viel der Eingabe der Prompt-Cache des Modellservers gespart hat – gemessen aus dem, was der Server meldet, nie geraten."""

    def test_zug_aus_timings_oder_usage_sonst_nichts(self):
        self.assertEqual(schleife.cache_messung({'input_tokens': 1000}, {'cache_n': 900, 'prompt_n': 100, 'prompt_ms': 50.5}), (900, 100, 50.5))
        self.assertEqual(schleife.cache_messung({'input_tokens': 1000, 'cached_tokens': 400}, None), (400, 600, 0.0), 'ohne timings die Angabe der usage')
        self.assertEqual(schleife.cache_messung({'input_tokens': 1000, 'cached_tokens': 400}, {'cache_n': 10, 'prompt_n': 20}), (10, 20, 0.0), 'timings gehen vor')
        for usage, timings in (({'input_tokens': 1000}, None), ({}, {}), ({'input_tokens': 10, 'cached_tokens': 99}, None), (None, {'cache_n': 5}), ({'input_tokens': 5}, {'cache_n': True, 'prompt_n': 1})):
            self.assertIsNone(schleife.cache_messung(usage, timings), str((usage, timings)))

    def test_adapter_normalisiert_die_timings(self):
        from sedra_runtime.models import openai_local
        self.assertEqual(openai_local.normalize_timings({'cache_n': 5, 'prompt_n': 7, 'prompt_ms': 1.234, 'predicted_ms': 9, 'fremd': 1}), {'cache_n': 5, 'prompt_n': 7, 'prompt_ms': 1.2, 'predicted_ms': 9.0})
        for schlecht in (None, {}, 'x', {'cache_n': -1}, {'cache_n': True}, {'prompt_ms': 'a'}):
            self.assertIsNone(openai_local.normalize_timings(schlecht), str(schlecht))

    def test_anteil_und_summe(self):
        self.assertEqual((verbrauch.anteil(900, 100), verbrauch.anteil(0, 0), verbrauch.anteil(0, 50), verbrauch.anteil(None, None)), (90, None, 0, None))
        e1 = dict(modell('2026-11-05T10:00:00+01:00', 3000, 100, 2, aid='A-1'), cache={'aus_cache': 1800, 'neu': 1200, 'zuege': 2, 'prompt_ms': 10.0})
        e2 = dict(modell('2026-11-05T10:05:00+01:00', 4000, 100, 1, aid='A-2'), cache={'aus_cache': 3900, 'neu': 100, 'zuege': 1, 'prompt_ms': 5.0})
        e3 = modell('2026-11-05T10:06:00+01:00', 500, 10, aid='A-3')                                  # alte Zeile ohne Messung
        s = verbrauch.summe([e1, e2, e3])
        self.assertEqual((s['aus_cache'], s['neu_gerechnet'], s['cache_zuege'], s['cache_anteil']), (5700, 1300, 3, 81))
        self.assertIsNone(verbrauch.summe([e3])['cache_anteil'], 'nichts gemessen: keine Zahl')

    def test_schleife_zaehlt_den_cache_je_zug_und_meldet_ihn(self):
        class Messung(Attrappe):
            def __call__(self, mission, request):
                out = super().__call__(mission, request)
                if out['status'] == 'completed':
                    out['model_result']['timings'] = {'cache_n': 800, 'prompt_n': 200, 'prompt_ms': 12.0} if len(self.requests) > 1 else {'cache_n': 0, 'prompt_n': 1000, 'prompt_ms': 90.0}
                return out
        with tempfile.TemporaryDirectory() as t:
            sitzungen = Sitzungen(Path(t))
            sid = sitzungen.anlegen('p')['id']
            antwort = Stroeme().anlegen(sid)
            a = Messung([Zug('Ich schaue nach.', calls=[call('zustand', {'was': 'gpu'})], usage={'input_tokens': 1000, 'output_tokens': 1}), Zug('Fertig.', usage={'input_tokens': 1000, 'output_tokens': 5})])
            out = schleife.laufen(a, MISSION, Box(), [{'role': 'user', 'content': 'Hallo'}], antwort, modell='m', sitzungen=sitzungen, sitzung_id=sid)
            self.assertEqual((out['cache']['aus_cache'], out['cache']['neu'], out['cache']['zuege'], out['cache']['prompt_ms']), (800, 1200, 2, 102.0))
            zeile = [e for e in sitzungen.laden(sid)['eintraege'] if e['typ'] == 'modell'][-1]
            self.assertEqual(zeile['cache']['aus_cache'], 800, 'die Messung steht in der Sitzungszeile (daraus rechnen Token-Seite und Zelle)')
            ende = [e['data'] for e in antwort.lesen(0, timeout=0) if e['event'] == 'ende'][-1]
            self.assertEqual(ende['cache']['zuege'], 2)

    def test_ohne_meldung_des_servers_steht_keine_messung_da(self):
        with tempfile.TemporaryDirectory() as t:
            sitzungen = Sitzungen(Path(t))
            sid = sitzungen.anlegen('p')['id']
            antwort = Stroeme().anlegen(sid)
            out = schleife.laufen(Attrappe([Zug('Hallo.')]), MISSION, Box(), [{'role': 'user', 'content': 'Hi'}], antwort, modell='m', sitzungen=sitzungen, sitzung_id=sid)
            self.assertIsNone(out['cache'])
            self.assertNotIn('cache', [e for e in sitzungen.laden(sid)['eintraege'] if e['typ'] == 'modell'][-1])
