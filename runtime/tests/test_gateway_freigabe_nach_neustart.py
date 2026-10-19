"""Eine GateWay-Freigabe muss auch nach einem Neustart der Oberfläche beantwortbar sein (die Merkliste der offenen Anfragen ist im Speicher)."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.models.base import BaseModelAdapter
from guppi_runtime.uix_server import UIXHub
from host_isolation import setUpModule, tearDownModule  # noqa: F401

ARCH = sorted((Path(__file__).resolve().parents[2] / 'architecture').glob('GUPPI_Architecture_v*'))[-1]
TEXT = 'Bitte eine kurze Übersicht für die Projektabstimmung. Nenne offene Punkte, ohne Termine zu erfinden.'


class StubLokal(BaseModelAdapter):
    id = 'stub-lokal'

    def health(self):
        return True

    def chat(self, messages, model=None, **kwargs):
        return {'provider': self.id, 'model': 'stub-1', 'content': 'Entwurf: offene Punkte sind offen.', 'usage': {}}


class FreigabeNachNeustart(unittest.TestCase):
    def test_die_freigabe_ist_nach_einem_neustart_noch_da_und_wird_angewendet(self):
        tmp = tempfile.TemporaryDirectory(prefix='gw-neustart-')
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / 'project'
        hub = UIXHub(root, ARCH)
        vid = hub.gateway_new({'titel': 'Test', 'wunsch': 'local'})['id']
        hub.gateway_pruefen({'id': vid, 'anfrage': TEXT, 'zweck': 'antwortentwurf', 'verantwortlich': 'Nutzer'})
        mid = hub.gateway_freigabe({'id': vid, 'weg': 'LOCAL_ONLY'})['mission_id']
        hub.close()

        # Neustart: eine neue Oberfläche auf demselben Projekt, die Merkliste ist leer
        hub2 = UIXHub(root, ARCH)
        self.addCleanup(hub2.close)
        hub2.runtime.model_router.register(StubLokal())
        self.assertEqual(hub2.gateway_get(vid)['freigabe_offen'], mid, 'der Knopf „Jetzt freigeben“ kennt die Mission')
        ids = [d['id'] for d in hub2.decisions_view()['items']]
        self.assertIn('request:' + mid, ids, 'die Freigabe steht in der Entscheidungsliste')
        out = hub2.decide({'id': 'request:' + mid, 'way': 'freigeben_und_anwenden'})
        self.assertEqual(out['status'], 'answered')
        self.assertEqual(hub2.gateway_get(vid)['zustand'], 'ENTWURF')


if __name__ == '__main__':
    unittest.main()
