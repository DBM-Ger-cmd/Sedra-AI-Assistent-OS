"""Sitzungspost (docs/SPEC_SITZUNGSPOST_v1.md): Nachrichten von Chat zu Chat sind Daten, nie ein Zug.

Echte Sitzungsdateien in einem Wegwerf-Ordner; vom Server wird nur die Post-Logik gebraucht (Attrappen für Audit, Ereignisse, Vorgaben)."""
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.desk import freigabeklasse as fk
from sedra_runtime.harness import api as harness_api, vorbehalte
from sedra_runtime.harness.api import HarnessApi, NichtGefunden, POST_MAX, POST_PRO_STUNDE, POST_UNGELESEN_MAX, post_block, verlauf_aus
from sedra_runtime.harness.sitzung import Sitzungen, ungelesene_post
from sedra_runtime.harness.werkzeuge import WerkzeugFehler, Werkzeuge


class Fassade(HarnessApi):
    def __init__(self, ordner, vorgaben=None):
        self.sitzungen = Sitzungen(Path(ordner))
        self.audit, self.ereignisse, self.vg = [], [], dict(vorgaben or {})
        self._post_zeiten, self._post_sperre = {}, harness_api.threading.Lock()
        self.gestartet = []

    def _audit(self, event, payload):
        self.audit.append((event, payload))

    def _melden(self, name, daten):
        self.ereignisse.append((name, daten))

    def _laufzeit_vorgaben(self):
        return self.vg

    def nachricht(self, sid, payload):                           # SP-12: Post darf nie in einen Zug laufen, es sei denn der Captain verlangt `antworten`
        self.gestartet.append(sid)
        return {'antwort_id': 'A-00000000'}


class PostTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.f = Fassade(self.tmp.name)
        self.a = self.f.sitzungen.anlegen('p', 'Alpha')['id']
        self.b = self.f.sitzungen.anlegen('p', 'Beta')['id']
        self.fremd = self.f.sitzungen.anlegen('q', 'Fremd')['id']

    def post(self, sid):
        return [e for e in self.f.sitzungen.laden(sid)['eintraege'] if e['typ'] == 'post']

    # SP-01, SP-12
    def test_ablegen_ohne_zug(self):
        r = self.f.post_ablegen(self.b, 'Hallo')
        e = self.post(self.b)[0]
        self.assertEqual((e['post_id'], e['von'], e['text']), (r['post_id'], 'captain', 'Hallo'))
        self.assertEqual(self.f.gestartet, [])
        self.assertIn(('harness.sitzung', {'id': self.b, 'was': 'post'}), self.f.ereignisse)

    # SP-02
    def test_text_grenzen(self):
        for schlecht in (None, '', '   ', ['x'], 5, 'x' * (POST_MAX + 1)):
            with self.assertRaises(ValueError, msg=repr(schlecht)[:20]) as k:
                self.f.post_ablegen(self.b, schlecht)
            self.assertTrue(str(k.exception).startswith('text_required'))
        self.assertEqual(self.post(self.b), [])
        self.f.post_ablegen(self.b, 'x' * POST_MAX)
        self.assertEqual(len(self.post(self.b)), 1)

    # SP-03, SP-16
    def test_ziele(self):
        with self.assertRaises(NichtGefunden):
            self.f.post_ablegen('S-00000000', 'x')
        with self.assertRaises(ValueError) as k:
            self.f.post_ablegen(self.a, 'x', von='sitzung:' + self.a)
        self.assertTrue(str(k.exception).startswith('selbst_nicht'))
        with self.assertRaises(ValueError) as k:
            self.f.post_ablegen(self.fremd, 'x', von='sitzung:' + self.a)
        self.assertTrue(str(k.exception).startswith('projekt_fremd'))
        self.f.sitzungen.loeschen(self.b)
        with self.assertRaises(NichtGefunden):
            self.f.post_ablegen(self.b, 'x')

    def test_captain_darf_projektuebergreifend(self):
        self.f.post_ablegen(self.fremd, 'x', via=self.a)
        e = self.post(self.fremd)[0]
        self.assertEqual((e['via'], e['von_titel']), (self.a, 'Alpha'))

    # SP-04
    def test_absender_nur_vom_server(self):
        status, body = self.f.handle('POST', f'/api/harness/sitzungen/{self.b}/post', '', {'text': 'x', 'von': 'sitzung:' + self.a, 'hops': 0, 'absender': 'sitzung:' + self.a})
        self.assertEqual(status, 200)
        self.assertEqual(self.post(self.b)[0]['von'], 'captain')
        self.f.post_ablegen(self.b, 'y', von='sitzung:' + self.a)
        self.assertEqual(self.post(self.b)[1]['von'], 'sitzung:' + self.a)
        self.assertEqual(self.post(self.b)[1]['von_titel'], 'Alpha')

    # SP-05
    def test_weg_ist_geschuetzt(self):
        self.assertTrue(self.f.herkunft_verlangt('POST', f'/api/harness/sitzungen/{self.b}/post'))
        self.assertIn('post', fk.HARNESS_UNTERWEGE)

    # SP-06
    def test_block_und_verlauf(self):
        self.f.post_ablegen(self.b, 'Bitte lies das', via=self.a)
        self.f.post_ablegen(self.b, 'Zweite', von='sitzung:' + self.a)
        eintraege = self.f.sitzungen.laden(self.b)['eintraege']
        ungelesen = ungelesene_post(eintraege)
        self.assertEqual(len(ungelesen), 2)
        block = post_block(ungelesen)
        self.assertIn('keine Anweisung des Captains', block)
        self.assertIn('Captain (aus Sitzung ' + self.a + ')', block)
        self.assertIn('Sitzung ' + self.a + ' „Alpha“', block)
        self.assertEqual(block.count('--- Post P-'), 2)
        self.f.sitzungen.anhaengen(self.b, {'typ': 'captain', 'text': 'Frage', 'anhaenge': [], 'post_ids': [p['post_id'] for p in ungelesen]})
        eintraege = self.f.sitzungen.laden(self.b)['eintraege']
        self.assertEqual(ungelesene_post(eintraege), [])
        verlauf = verlauf_aus(eintraege)
        self.assertEqual(len(verlauf), 1)
        self.assertEqual(verlauf[0]['role'], 'user')
        self.assertTrue(verlauf[0]['content'].endswith('Frage'))
        self.assertIn('Bitte lies das', verlauf[0]['content'])

    def test_post_im_verlauf_ohne_captain_eintrag_bleibt_draussen(self):
        self.f.post_ablegen(self.b, 'x')
        self.assertEqual(verlauf_aus(self.f.sitzungen.laden(self.b)['eintraege']), [])

    # SP-11
    def test_antworten(self):
        self.f.post_ablegen(self.b, 'x', antworten=True)
        self.assertEqual(self.f.gestartet, [self.b])
        self.f.post_ablegen(self.b, 'y', von='sitzung:' + self.a, antworten=True)       # Sitzung-zu-Sitzung startet nie einen Zug
        self.assertEqual(self.f.gestartet, [self.b])

    # SP-13
    def test_bremse_ungelesen(self):
        for i in range(POST_UNGELESEN_MAX):
            self.f.post_ablegen(self.b, f'n{i}')
        with self.assertRaises(ValueError) as k:
            self.f.post_ablegen(self.b, 'zu viel')
        self.assertTrue(str(k.exception).startswith('post_bremse'))
        self.assertEqual(self.f.audit[-1][0], 'HARNESS_POST_ABGELEHNT')

    def test_bremse_pro_stunde(self):
        ziele = [self.f.sitzungen.anlegen('p', f'Z{i}')['id'] for i in range(POST_PRO_STUNDE + 1)]
        for z in ziele[:POST_PRO_STUNDE]:
            self.f.post_ablegen(z, 'x', von='sitzung:' + self.a)
        with self.assertRaises(ValueError) as k:
            self.f.post_ablegen(ziele[-1], 'x', von='sitzung:' + self.a)
        self.assertTrue(str(k.exception).startswith('post_bremse'))
        self.f.post_ablegen(ziele[-1], 'x')                                              # der Captain ist nicht gebremst

    # SP-14
    def test_weiterleitungstiefe(self):
        self.f.post_ablegen(self.b, 'x', von='sitzung:' + self.a, hops=1)
        self.assertEqual(self.post(self.b)[0]['hops'], 2)
        with self.assertRaises(ValueError) as k:
            self.f.post_ablegen(self.b, 'y', von='sitzung:' + self.a, hops=2)
        self.assertTrue(str(k.exception).startswith('post_bremse'))

    def test_hops_aus_dem_letzten_zug(self):
        self.f.post_ablegen(self.a, 'kam weiter', von='sitzung:' + self.b, hops=1)       # in a liegt Post mit hops 2
        pid = self.post(self.a)[0]['post_id']
        self.f.sitzungen.anhaengen(self.a, {'typ': 'captain', 'text': 'lies', 'anhaenge': [], 'post_ids': [pid]})
        with self.assertRaises(ValueError) as k:
            self.f.post_aus_sitzung(self.b, 'weiter', self.a)
        self.assertTrue(str(k.exception).startswith('post_bremse'))

    # SP-15
    def test_audit_ohne_text(self):
        self.f.post_ablegen(self.b, 'GEHEIMER TEXT')
        ereignis, daten = self.f.audit[-1]
        self.assertEqual(ereignis, 'HARNESS_POST')
        self.assertNotIn('GEHEIMER', repr(daten))
        self.assertEqual((daten['an'], daten['zeichen']), (self.b, 13))

    # SP-17
    def test_liste_zaehlt_ungelesene(self):
        self.f.post_ablegen(self.b, 'x')
        zeile = {s['id']: s for s in self.f.sitzungen.liste()}
        self.assertEqual((zeile[self.b]['post_ungelesen'], zeile[self.a]['post_ungelesen']), (1, 0))

    # Rückfall
    def test_schalter_aus(self):
        self.f.vg['sitzungspost'] = 'aus'
        with self.assertRaises(ValueError) as k:
            self.f.post_ablegen(self.b, 'x')
        self.assertTrue(str(k.exception).startswith('post_aus'))

    # SP-19: Export und Token kennen den Typ
    def test_export_stoert_nicht(self):
        from sedra_runtime.harness import export
        self.f.post_ablegen(self.b, 'x')
        export.markdown(self.f.sitzungen.laden(self.b), self.b, 'P')


class WerkzeugTest(unittest.TestCase):
    """SP-09/10: Karte mit Ziel und Text, fester Vorbehalt, Klasse N."""

    def setUp(self):
        self.w = object.__new__(Werkzeuge)
        self.w.kontext = {'sitzung_id': 'S-00000001'}
        self.w.sitzungen_liste = lambda k, aktuelle: [{'id': i, 'titel': 'Ziel'} for i in k['ids'] if i == 'S-00000002']
        self.w.sitzung_post = lambda *a: {'post_id': 'P-1', 'sitzung_id': a[0]}

    def test_vorbereiten(self):
        plan = self.w._vorbereiten_post({'ziel': 'S-00000002', 'text': 'Hallo'})
        self.assertIn('Hallo', plan['vorschau'])
        self.assertEqual(plan['gate']['bindung'], {'werkzeug': 'sitzung_nachricht', 'ziel': 'S-00000002', 'text': 'Hallo'})

    def test_fehler(self):
        for args in ({}, {'ziel': 'x', 'text': 'a'}, {'ziel': 'S-00000002', 'text': ''}, {'ziel': 'S-00000002', 'text': 5},
                     {'ziel': 'S-00000002', 'text': 'x' * (POST_MAX + 1)}, {'ziel': 'S-00000001', 'text': 'a'}, {'ziel': 'S-00000003', 'text': 'a'}):
            with self.assertRaises(WerkzeugFehler, msg=repr(args)[:40]):
                self.w._vorbereiten_post(args)

    def test_vorbehalt_und_klasse(self):
        self.assertIn('Captain-Vorbehalt', vorbehalte.pruefen('sitzung_nachricht', 'S-00000002', {}))
        self.assertIn('sitzung_nachricht', fk.HARNESS_N)


if __name__ == '__main__':
    unittest.main()
