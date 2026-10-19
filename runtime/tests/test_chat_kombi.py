"""Lokal + KI im Gespräch: das lokale Modell entwirft, die Cloud prüft – in einem Fenster, beide Schritte durch den Inhaltsschutz."""
import types
import unittest
from pathlib import Path
from unittest import mock

from guppi_runtime.core.content_guard import ContentGuardStop
from guppi_runtime.uix_server import UIXHub
from host_isolation import setUpModule, tearDownModule  # noqa: F401
import tempfile

ARCH = sorted((Path(__file__).resolve().parents[2] / 'architecture').glob('GUPPI_Architecture_v*'))[-1]
LOKAL = {'status': 'completed', 'reply': 'Lokaler Entwurf: Stand folgt.', 'model': 'stub-lokal'}
CLOUD_OK = {'status': 'completed', 'reply': 'Geprüft: offene Punkte sind offen.'}


class LokalUndKI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kombi-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)

    def kombi(self, cloud, text='Erstelle eine Übersicht.', history=None):
        payload = {'text': text, 'provider': 'testanbieter', 'model': 'test-modell-1'}
        if history is not None:
            payload['history'] = history
        with mock.patch.object(UIXHub, 'chat_reply', return_value=LOKAL) as lokal:
            with mock.patch.object(UIXHub, 'chat_cloud', **cloud) as cl:
                out = self.hub.chat_kombi(payload)
        return out, lokal, cl

    def test_lokal_entwirft_und_die_cloud_prueft_in_einem_fenster(self):
        out, _, cloud = self.kombi({'return_value': CLOUD_OK})
        self.assertEqual(out['status'], 'completed')
        self.assertEqual(out['local'], 'Lokaler Entwurf: Stand folgt.')
        self.assertEqual(out['cloud'], 'Geprüft: offene Punkte sind offen.')
        self.assertEqual(cloud.call_count, 1)
        sent = cloud.call_args[0][0]
        self.assertIn('Lokaler Entwurf: Stand folgt.', sent['text'], 'die Cloud bekommt den Entwurf des lokalen Modells')
        self.assertIn('Erstelle eine Übersicht', sent['text'], 'und die Aufgabe des Nutzers')

    def test_eine_sperre_als_ergebnis_laesst_den_lokalen_entwurf_stehen(self):
        # labor.cloud_chat meldet eine Sperre als Ergebnis, nicht als Ausnahme
        out, _, _ = self.kombi({'return_value': {'status': 'blocked', 'reasons': ['SG_PERSONAL_CLOUD']}})
        self.assertEqual(out['status'], 'cloud_gesperrt')
        self.assertEqual(out['local'], 'Lokaler Entwurf: Stand folgt.')
        self.assertIsNone(out['cloud'])
        self.assertEqual(out['reasons'], ['SG_PERSONAL_CLOUD'])

    def test_eine_ausnahme_der_cloud_wird_ebenfalls_als_sperre_gemeldet(self):
        exc = ContentGuardStop(types.SimpleNamespace(status='WITHHELD', reasons=['SG_TEST']))
        out, _, _ = self.kombi({'side_effect': exc})
        self.assertEqual(out['status'], 'cloud_gesperrt')
        self.assertEqual(out['local'], 'Lokaler Entwurf: Stand folgt.')

    def test_ein_cloud_fehler_laesst_den_lokalen_entwurf_stehen(self):
        out, _, _ = self.kombi({'return_value': {'status': 'failed', 'reasons': []}})
        self.assertEqual(out['status'], 'cloud_fehler')
        self.assertEqual(out['local'], 'Lokaler Entwurf: Stand folgt.')

    def test_der_verlauf_geht_an_beide_seiten_fuer_die_naechste_runde(self):
        hist = [{'role': 'user', 'content': 'Erste Frage'}, {'role': 'assistant', 'content': 'Erste Antwort'}]
        out, lokal, cloud = self.kombi({'return_value': CLOUD_OK}, text='Und weiter?', history=hist)
        self.assertEqual(lokal.call_args[0][0]['history'], hist)
        self.assertEqual(cloud.call_args[0][0]['history'], hist)

    def test_ohne_lokales_modell_sagt_es_und_ruft_die_cloud_nicht(self):
        with mock.patch.object(UIXHub, 'chat_reply', return_value={'status': 'no_model', 'message': 'Kein Modell geladen.'}):
            with mock.patch.object(UIXHub, 'chat_cloud') as cloud:
                out = self.hub.chat_kombi({'text': 'Übersicht bitte.', 'provider': 'testanbieter', 'model': 'test-modell-1'})
        self.assertEqual(out['status'], 'no_local')
        self.assertEqual(cloud.call_count, 0)

    def test_ohne_modellwahl_gibt_es_einen_klaren_fehler(self):
        with self.assertRaisesRegex(ValueError, 'cloud_model_required'):
            self.hub.chat_kombi({'text': 'Übersicht bitte.'})


if __name__ == '__main__':
    unittest.main()
