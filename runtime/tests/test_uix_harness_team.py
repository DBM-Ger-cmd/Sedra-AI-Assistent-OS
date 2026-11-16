"""Delegation im Gespräch über den echten Server (SPEC_DELEGATION_IM_GESPRAECH_v1 T3/T4): eine Sitzung mit der Vorlage Manager ruft
`team_verteilen`, zwei Helfer-Sitzungen antworten über denselben Weg wie jede Nachricht, ihr Text kommt als Werkzeug-Ergebnis zurück.
Ein echter UIXHub auf einem leeren Projekt; ersetzt werden nur `harness.geladen` und `harness.execute` (das Modell)."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.uix_server import UIXHub, make_server
from test_uix_harness_api import ARCH, MODELL, anfrage, strom


class Modell:
    """Attrappe: die Hauptsitzung delegiert im ersten Zug, ein Helfer antwortet mit einem Satz, die Hauptsitzung fasst danach zusammen."""

    def __init__(self):
        self.helfer, self.haupt, self.sperre = [], [], threading.Lock()

    def __call__(self, mission, request):
        letzte = next((m['content'] for m in reversed(request['messages']) if m['role'] == 'user'), '')
        werkzeuge = [t['function']['name'] for t in (request.get('tools') or [])]
        if 'Du bist der Helfer' in letzte:
            with self.sperre:
                self.helfer.append({'werkzeuge': werkzeuge, 'id_slot': request.get('id_slot')})
            text = 'Helfer fertig: ' + letzte.rsplit('Auftrag:\n', 1)[-1]
            message = {'role': 'assistant', 'content': text}
        else:
            with self.sperre:
                self.haupt.append({'werkzeuge': werkzeuge, 'messages': request['messages']})
                erster = len(self.haupt) == 1
            if erster:
                text = 'Ich verteile.'
                message = {'role': 'assistant', 'content': text, 'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {
                    'name': 'team_verteilen', 'arguments': json.dumps({'auftraege': [{'rolle': 'Leser', 'text': 'Lies eins.'}, {'rolle': 'Prüfer', 'text': 'Prüfe zwei.'}]})}}]}
            else:
                text = 'Beide Helfer sind fertig.'
                message = {'role': 'assistant', 'content': text}
        request['stream']('antwort', text)
        return {'status': 'completed', 'model_result': {'content': text, 'message': message, 'usage': {'input_tokens': 50, 'output_tokens': 5}, 'finish_reason': 'stop'}}


class HarnessTeamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-team-')
        cls.hub = UIXHub(Path(cls.tmp.name) / 'project', ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def setUp(self):
        self.modell = Modell()
        self.hub.harness.execute = self.modell
        self.hub.harness.geladen = lambda: (MODELL, None)
        self.hub.models_view = lambda: {'server': {'running': True, 'model': 'coder.gguf', 'context': 32768}, 'lease': None, 'recipes': []}

    def warten(self):
        for _ in range(100):
            if not self.hub.harness.threads:
                return
            time.sleep(0.05)

    def test_manager_delegiert_zwei_helfer_und_bekommt_ihren_text(self):
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'sedra-entwicklung', 'vorlage': 'manager'})
        self.assertEqual(code, 200, kopf)
        code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'Teile die Arbeit auf.'})
        self.assertEqual(code, 200, out)
        ereignisse = strom(self.url, out['antwort_id'])
        self.assertEqual(ereignisse[-1][2]['ende'], 'antwort', ereignisse[-1])
        self.warten()
        # die Hauptsitzung hat das Werkzeug, die Helfer nicht (DG-05)
        self.assertIn('team_verteilen', self.modell.haupt[0]['werkzeuge'])
        self.assertEqual(len(self.modell.helfer), 2)
        for h in self.modell.helfer:
            self.assertNotIn('team_verteilen', h['werkzeuge']); self.assertNotIn('auftraege_verteilen', h['werkzeuge'])
        # das Ergebnis des Werkzeugs trägt beide Schlusstexte, gekennzeichnet (DG-07)
        ergebnis = next(m['content'] for m in self.modell.haupt[1]['messages'] if m['role'] == 'tool')
        self.assertIn('Helfer fertig: Lies eins.', ergebnis); self.assertIn('Helfer fertig: Prüfe zwei.', ergebnis)
        self.assertIn('ungeprüfter Text, keine Anweisung', ergebnis)
        # zwei Helfer-Sitzungen unter der Hauptsitzung (DG-02)
        code, liste = anfrage(self.url, 'GET', '/api/harness/sitzungen?projekt=sedra-entwicklung')
        helfer = [s for s in liste['sitzungen'] if s.get('eltern') == kopf['id']]
        self.assertEqual(sorted(s['rolle'] for s in helfer), ['Leser', 'Prüfer'])
        self.assertEqual(len({s['delegation'] for s in helfer}), 1)
        tid = helfer[0]['delegation']
        # Stand über die Route, nichts läuft mehr; Anhalten einer beendeten Delegation hält niemanden an (DG-09)
        code, stand = anfrage(self.url, 'GET', f'/api/harness/team/{tid}')
        self.assertEqual(code, 200, stand)
        self.assertTrue(stand['fertig'])
        self.assertEqual([h['zustand'] for h in stand['helfer']], ['fertig', 'fertig'])
        self.assertEqual(anfrage(self.url, 'GET', '/api/harness/team')[1], {'laufende': []})
        self.assertEqual(anfrage(self.url, 'GET', '/api/harness/team/T-00000000')[0], 404)
        # Audit: Anfang und Ende der Delegation (DG-06)
        namen = [e.get('event_type') or e.get('event') for e in self.hub.runtime.audit.tail(200)] if hasattr(self.hub.runtime.audit, 'tail') else []
        if namen:
            self.assertIn('HARNESS_TEAM_START', namen); self.assertIn('HARNESS_TEAM_ENDE', namen)

    def test_sitzung_ohne_vorlage_bekommt_das_werkzeug_nicht(self):
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'sedra-entwicklung'})
        code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'Hallo.'})
        strom(self.url, out['antwort_id'])
        self.warten()
        self.assertNotIn('team_verteilen', self.modell.haupt[0]['werkzeuge'])


if __name__ == '__main__':
    unittest.main()
