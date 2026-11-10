"""Harness-Werkzeug `auftraege_verteilen`: Teilaufträge des Managers an den Hilfs-Coder in der Cloud, immer mit Karte des Captains."""
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.core.guard import Guard
from sedra_runtime.harness import katalog, vorlagen
from sedra_runtime.harness.freigabe import Karten, Kiste
from sedra_runtime.harness.werkzeuge import CLOUD, NAMEN, Werkzeuge, WerkzeugFehler

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'
AUFTRAG = {'typ': 'code_und_spec_des_baus', 'text': 'Schreibe eine Funktion, die zwei Zahlen addiert.'}


class CloudVerteilenTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.gesendet = []
        root = Path(t.name) / 'p'; root.mkdir()
        self.guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(t.name) / 'tokens.json')
        self.regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        self.w = Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': []}, guard=self.guard, mission_id='M-C', regeln=self.regeln, cloud_verteilen=self.senden)
        self.kiste = Kiste(self.w, regeln=self.regeln, guard=self.guard, audit=None, karten=Karten(Path(t.name) / 'k'), sitzung_id='S-00000001')

    def senden(self, auftraege):
        self.gesendet.append(auftraege)
        return [{'ok': True, 'typ': a['typ'], 'modell': 'anbieter/modell', 'sekunden': 1.5, 'antwort': 'ANTWORT ' + a['text'][:10]} for a in auftraege]

    def test_werkzeug_ist_bekannt_und_im_katalog(self):
        self.assertIn('auftraege_verteilen', NAMEN)
        self.assertIn('auftraege_verteilen', CLOUD)
        self.assertIn('auftraege_verteilen', katalog.WERKZEUGE)
        self.assertNotIn('auftraege_verteilen', katalog.OHNE_KARTE, 'der Text verlässt den Rechner: nie ohne Karte')
        self.assertIn('auftraege_verteilen', [s['function']['name'] for s in self.w.schemas()])

    def test_manager_vorlage_bietet_es_an(self):
        v = vorlagen.laden(Path(tempfile.mkdtemp()), 'manager')
        self.assertIn('auftraege_verteilen', v['werkzeuge'])

    def test_ohne_katalogregel_wartet_der_aufruf_auf_die_karte(self):
        r = self.kiste.aufruf('auftraege_verteilen', {'auftraege': [AUFTRAG]})
        self.assertEqual(r['status'], 'wartet')
        self.assertEqual(self.gesendet, [], 'vor der Freigabe geht nichts in die Cloud')
        self.assertIn('Cloud', r['karte']['vorschau'])
        self.assertIn('Schreibe eine Funktion', r['karte']['vorschau'], 'der Captain sieht den Text, der hinausgeht')

    def test_nach_der_freigabe_kommen_die_antworten_als_text(self):
        plan = self.w.vorbereiten('auftraege_verteilen', {'auftraege': [AUFTRAG, dict(AUFTRAG, text='zweiter Auftrag')]})
        gate = self.guard.create_gate(self.w.mission_id, plan['gate']['aktion'], plan['gate']['ziel'], request_binding=plan['gate']['bindung'], risks=[], rollback_available=False)
        out = self.w.ausfuehren('auftraege_verteilen', {}, token=self.guard.approve(gate), plan=plan)
        self.assertEqual(out['status'], 'ok')
        self.assertTrue(out['wirkung'])
        self.assertIn('Auftrag 2', out['ergebnis'])
        self.assertIn('fremder Text', out['ergebnis'])
        self.assertEqual(len(self.gesendet[0]), 2)

    def test_ohne_gueltiges_token_geht_nichts_hinaus(self):
        plan = self.w.vorbereiten('auftraege_verteilen', {'auftraege': [AUFTRAG]})
        out = self.w.ausfuehren('auftraege_verteilen', {}, token='gefaelscht', plan=plan)
        self.assertEqual(out['status'], 'fehler')
        self.assertEqual(self.gesendet, [])

    def test_abgelehnter_auftrag_steht_mit_grund_im_ergebnis(self):
        self.w.cloud_verteilen = lambda a: [{'ok': False, 'typ': 'persoenliche_daten', 'grund': 'Gesetz: nicht erlaubt'}]
        plan = self.w.vorbereiten('auftraege_verteilen', {'auftraege': [{'typ': 'persoenliche_daten', 'text': 'x'}]})
        gate = self.guard.create_gate(self.w.mission_id, plan['gate']['aktion'], plan['gate']['ziel'], request_binding=plan['gate']['bindung'], risks=[], rollback_available=False)
        out = self.w.ausfuehren('auftraege_verteilen', {}, token=self.guard.approve(gate), plan=plan)
        self.assertIn('nicht ausgeführt: Gesetz', out['ergebnis'])

    def test_eingabe_wird_geprueft(self):
        for bad in ({}, {'auftraege': []}, {'auftraege': 'text'}, {'auftraege': [{'typ': 'x'}]}, {'auftraege': [{'typ': 'x', 'text': '  '}]},
                    {'auftraege': [{'typ': 'x', 'text': 'y' * 12001}]}, {'auftraege': [AUFTRAG] * 6}):
            with self.assertRaises(WerkzeugFehler, msg=str(bad)[:50]):
                self.w.vorbereiten('auftraege_verteilen', bad)

    def test_ohne_kanal_ein_klarer_fehler(self):
        self.w.cloud_verteilen = None
        with self.assertRaises(WerkzeugFehler):
            self.w.vorbereiten('auftraege_verteilen', {'auftraege': [AUFTRAG]})


if __name__ == '__main__':
    unittest.main()
