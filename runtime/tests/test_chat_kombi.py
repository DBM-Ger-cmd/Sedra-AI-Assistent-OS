"""Lokal + KI im Gespräch: das lokale Modell entwirft, die Cloud prüft – in einem Fenster, beide Schritte durch den Inhaltsschutz."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guppi_runtime.models.base import BaseModelAdapter
from guppi_runtime.uix_server import UIXHub
from host_isolation import setUpModule, tearDownModule  # noqa: F401

ARCH = sorted((Path(__file__).resolve().parents[2] / 'architecture').glob('GUPPI_Architecture_v*'))[-1]
KEY_ENV = 'GUPPI_SECRET_TESTANBIETER_API_KEY'


class StubCloud(BaseModelAdapter):
    id = 'testanbieter'
    route = 'cloud'
    default_model = 'test-modell-1'

    def __init__(self):
        self.calls = []

    def health(self):
        return bool(os.environ.get(KEY_ENV))

    def chat(self, messages, model=None, **kwargs):
        self.calls.append(messages)
        return {'provider': self.id, 'model': model or self.default_model, 'content': 'Geprüft: offene Punkte sind offen.', 'usage': {}}


class LokalUndKI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kombi-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / 'project', ARCH)
        self.addCleanup(self.hub.close)
        self.cloud = StubCloud()
        self.hub.runtime.model_router.register(self.cloud)
        self.hub.content_guard.cloud_enabled = True
        env = mock.patch.dict(os.environ, {KEY_ENV: 'test-schluessel-nicht-echt'})
        env.start(); self.addCleanup(env.stop)

    def test_lokal_entwirft_und_die_cloud_prueft_in_einem_fenster(self):
        local = {'status': 'completed', 'reply': 'Lokaler Entwurf: Stand folgt.', 'model': 'stub-lokal'}
        cloud_ok = {'status': 'completed', 'reply': 'Geprüft: offene Punkte sind offen.'}
        with mock.patch.object(UIXHub, 'chat_reply', return_value=local),              mock.patch.object(UIXHub, 'chat_cloud', return_value=cloud_ok) as cloud:
            out = self.hub.chat_kombi({'text': 'Erstelle eine Übersicht für die Projektabstimmung.', 'provider': 'testanbieter',
                                       'model': 'test-modell-1'})
        self.assertEqual(out['status'], 'completed')
        self.assertEqual(out['local'], 'Lokaler Entwurf: Stand folgt.')
        self.assertEqual(out['cloud'], 'Geprüft: offene Punkte sind offen.')
        self.assertEqual(cloud.call_count, 1)
        sent = cloud.call_args[0][0]
        self.assertIn('Lokaler Entwurf: Stand folgt.', sent['text'], 'die Cloud bekommt den Entwurf des lokalen Modells')
        self.assertIn('Erstelle eine Übersicht', sent['text'], 'und die Aufgabe des Nutzers')

    def test_der_verlauf_geht_an_beide_seiten_fuer_die_naechste_runde(self):
        hist = [{'role': 'user', 'content': 'Erste Frage'}, {'role': 'assistant', 'content': 'Erste Antwort'}]
        local = {'status': 'completed', 'reply': 'Lokal 2.', 'model': 'stub-lokal'}
        cloud_ok = {'status': 'completed', 'reply': 'Cloud 2.'}
        with mock.patch.object(UIXHub, 'chat_reply', return_value=local) as lokal:
            with mock.patch.object(UIXHub, 'chat_cloud', return_value=cloud_ok) as cloud:
                self.hub.chat_kombi({'text': 'Und weiter?', 'history': hist, 'provider': 'testanbieter', 'model': 'test-modell-1'})
        self.assertEqual(lokal.call_args[0][0]['history'], hist)
        self.assertEqual(cloud.call_args[0][0]['history'], hist)

    def test_eine_sperre_der_cloud_laesst_den_lokalen_entwurf_stehen(self):
        from guppi_runtime.core.content_guard import ContentGuardStop
        local = {'status': 'completed', 'reply': 'Lokaler Entwurf.', 'model': 'stub-lokal'}
        with mock.patch.object(UIXHub, 'chat_reply', return_value=local),              mock.patch.object(UIXHub, 'chat_cloud', side_effect=ContentGuardStop(__import__('types').SimpleNamespace(status='WITHHELD', reasons=['SG_TEST']))):
            out = self.hub.chat_kombi({'text': 'Übersicht.', 'provider': 'testanbieter', 'model': 'test-modell-1'})
        self.assertEqual(out['status'], 'cloud_gesperrt')
        self.assertEqual(out['local'], 'Lokaler Entwurf.')
        self.assertIsNone(out['cloud'])

    def test_ohne_lokales_modell_sagt_es_und_ruft_die_cloud_nicht(self):
        with mock.patch.object(UIXHub, 'chat_reply', return_value={'status': 'no_model', 'message': 'Kein Modell geladen.'}):
            out = self.hub.chat_kombi({'text': 'Übersicht bitte.', 'provider': 'testanbieter', 'model': 'test-modell-1'})
        self.assertEqual(out['status'], 'no_local')
        self.assertEqual(self.cloud.calls, [])

    def test_ohne_modellwahl_gibt_es_einen_klaren_fehler(self):
        with self.assertRaisesRegex(ValueError, 'cloud_model_required'):
            self.hub.chat_kombi({'text': 'Übersicht bitte.'})


if __name__ == '__main__':
    unittest.main()
