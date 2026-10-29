"""T6 der Harness-Shell: die Wege unter /api/harness/ über HTTP (G2 §4), mit einer Attrappe des Modells.

Ein echter UIXHub auf einem leeren Projekt; ersetzt werden nur `harness.geladen` (welches Modell läuft) und `harness.execute`
(control.execute). Geprüft wird der ganze Ablauf, dass /api/status während einer Antwort sofort antwortet (K3) und die Schleife
hub.lock nie hält, und die Grenzen (8000 Zeichen, kein Modell)."""
import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.uix_server import UIXHub, make_server

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
MODELL = [{'identifier': 'coder', 'modelKey': 'coder.gguf', 'contextLength': 32768}]


def anfrage(url, method, path, body=None, headers=None, timeout=30):
    parts = urlsplit(url)
    c = http.client.HTTPConnection(parts.hostname, parts.port, timeout=timeout)
    try:
        h = {'X-GUPPI-Token': parts.fragment, **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body); h['Content-Type'] = 'application/json'
        c.request(method, path, body=data, headers=h)
        res = c.getresponse()
        raw = res.read().decode('utf-8')
        try:
            return res.status, json.loads(raw or 'null')
        except ValueError:
            return res.status, raw
    finally:
        c.close()


def strom(url, aid, last=None):
    """Liest den SSE-Strom einer Antwort bis `ende`; [(id, event, data)]."""
    parts = urlsplit(url)
    c = http.client.HTTPConnection(parts.hostname, parts.port, timeout=20)
    h = {'X-GUPPI-Token': parts.fragment}
    if last is not None: h['Last-Event-ID'] = str(last)
    c.request('GET', f'/api/harness/antworten/{aid}/strom', headers=h)
    res = c.getresponse()
    assert res.status == 200, res.status
    out, block = [], {}
    while True:
        line = res.fp.readline().decode('utf-8')
        if not line:
            break
        line = line.rstrip('\n')
        if not line:
            if 'event' in block:
                out.append((int(block['id']), block['event'], json.loads(block['data'])))
                if block['event'] == 'ende': break
            block = {}
            continue
        if line.startswith(':'):
            continue
        key, _, value = line.partition(': ')
        block[key] = value
    c.close()
    return out


class Modell:
    """Attrappe von control.execute: streamt Wörter über `stream` und liefert das Ergebnis; ruft beim ersten Zug ein Werkzeug."""

    def __init__(self, hub):
        self.hub, self.requests, self.halten, self.weiter, self.lock_gehalten = hub, [], False, threading.Event(), []

    def __call__(self, mission, request):
        self.requests.append(request)
        self.lock_gehalten.append(self.hub.lock._is_owned())
        if self.halten:
            self.weiter.wait(10)
        erster = len(self.requests) == 1 and request.get('tools')
        text = 'Ich sehe nach.' if erster else 'Das Modell coder läuft.'
        for w in text.split(' '):
            request['stream']('antwort', w + ' ')
        message = {'role': 'assistant', 'content': text}
        if erster:
            message['tool_calls'] = [{'id': 'c1', 'type': 'function', 'function': {'name': 'get_model_status', 'arguments': '{}'}}]
        return {'status': 'completed', 'model_result': {'content': text, 'message': message, 'usage': {'input_tokens': 50, 'output_tokens': 5}, 'finish_reason': 'stop'}}


class HarnessApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-api-')
        cls.hub = UIXHub(Path(cls.tmp.name) / 'project', ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def setUp(self):
        self.modell = Modell(self.hub)
        self.hub.harness.execute = self.modell
        self.hub.harness.geladen = lambda: (MODELL, None)
        self.hub.models_view = lambda: {'server': {'running': True, 'model': 'coder.gguf', 'context': 32768}, 'lease': None, 'recipes': []}

    def neue_sitzung(self, **kw):
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'sedra-entwicklung', **kw})
        self.assertEqual(code, 200, kopf)
        return kopf

    def test_projekte_standard(self):
        code, body = anfrage(self.url, 'GET', '/api/harness/projekte')
        self.assertEqual(code, 200)
        self.assertEqual(body['projekte'][0]['id'], 'sedra-entwicklung')
        self.assertIsNone(body['fehler'])

    def test_ganzer_ablauf(self):
        kopf = self.neue_sitzung()
        self.assertRegex(kopf['id'], r'^S-[0-9A-F]{8}$')
        self.assertTrue(kopf['mission_id'])
        code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'Welches Modell läuft?'})
        self.assertEqual(code, 200, out)
        self.assertRegex(out['antwort_id'], r'^A-[0-9A-F]{8}$')
        ereignisse = strom(self.url, out['antwort_id'])
        namen = [e[1] for e in ereignisse]
        self.assertEqual(namen[0], 'zug.start')
        self.assertIn('werkzeug.start', namen)
        self.assertFalse(out['live'], 'nichts bestätigt = scharf (G-04): Text erst nach dem Urteil (D-E2)')
        self.assertNotIn('text.ungeprueft', namen)
        self.assertEqual(ereignisse[-1][2]['ende'], 'antwort')
        self.assertEqual([e[0] for e in ereignisse], list(range(1, len(ereignisse) + 1)))
        # Wiederaufnahme ab einer Nummer
        spaeter = strom(self.url, out['antwort_id'], last=3)
        self.assertEqual(spaeter[0][0], 4)
        for _ in range(50):                      # der Thread schreibt die Sitzung vor `ende`; das Aufräumen danach kurz abwarten
            if not self.hub.harness.threads: break
            time.sleep(0.05)
        code, s = anfrage(self.url, 'GET', f"/api/harness/sitzungen/{kopf['id']}")
        self.assertEqual(code, 200)
        self.assertEqual([e['typ'] for e in s['eintraege']], ['captain', 'titel', 'werkzeug', 'modell'])
        self.assertEqual(s['titel'], 'Welches Modell läuft?')
        self.assertEqual(s['eintraege'][-1]['text'], 'Ich sehe nach.\n\nDas Modell coder läuft.')
        self.assertIsNone(s['laeuft'])
        self.assertFalse(any(self.modell.lock_gehalten), 'die Schleife hält hub.lock nie (K3)')
        self.assertTrue(all(r['slot_owner'] == 'captain-chat' and r['provider'] == 'llama-cpp-server' for r in self.modell.requests))
        code, liste = anfrage(self.url, 'GET', '/api/harness/sitzungen?projekt=sedra-entwicklung')
        self.assertIn(kopf['id'], [x['id'] for x in liste['sitzungen']])

    def test_live_text_im_modus_beobachten(self):
        guard = self.hub.runtime.model_router.content_guard
        alt = guard.mode
        guard.set_mode('beobachten')
        self.addCleanup(guard.set_mode, alt)
        kopf = self.neue_sitzung()
        _code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'Hallo'})
        self.assertTrue(out['live'])
        namen = [e[1] for e in strom(self.url, out['antwort_id'])]
        self.assertIn('text.ungeprueft', namen)
        self.assertLess(namen.index('text.ungeprueft'), namen.index('text.geprueft'))

    def test_status_antwortet_sofort_waehrend_einer_antwort(self):
        kopf = self.neue_sitzung()
        self.modell.halten = True
        code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'Langsam bitte'})
        self.assertEqual(code, 200, out)
        try:
            for _ in range(100):
                if self.modell.requests: break
                time.sleep(0.02)
            start = time.monotonic()
            code, _ = anfrage(self.url, 'GET', '/api/status')
            self.assertEqual(code, 200)
            self.assertLess(time.monotonic() - start, 5, 'K3: keine Sperre anderer Wege während einer Antwort')
            code, liste = anfrage(self.url, 'GET', '/api/harness/sitzungen')
            self.assertEqual(liste['laufend'].get(kopf['id']), out['antwort_id'])
            code, zweite = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'noch eine'})
            self.assertEqual((code, zweite.get('code')), (400, 'antwort_laeuft'))
        finally:
            self.modell.weiter.set()
        strom(self.url, out['antwort_id'])

    def test_stopp(self):
        kopf = self.neue_sitzung()
        self.modell.halten = True
        code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'Stopp gleich'})
        for _ in range(100):
            if self.modell.requests: break
            time.sleep(0.02)
        code, body = anfrage(self.url, 'POST', f"/api/harness/antworten/{out['antwort_id']}/stopp", {})
        self.assertEqual((code, body['gestoppt']), (200, True))
        self.modell.weiter.set()
        ereignisse = strom(self.url, out['antwort_id'])
        self.assertEqual(ereignisse[-1][2]['ende'], 'abgebrochen')

    def test_text_laenger_als_8000_zeichen(self):
        kopf = self.neue_sitzung()
        code, body = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'x' * 8001})
        self.assertEqual(code, 400)
        self.assertEqual(body['code'], 'text_required')
        code, _ = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': '   '})
        self.assertEqual(code, 400)

    def test_kein_modell(self):
        self.hub.harness.geladen = lambda: ([], 'gguf fehlt')
        kopf = self.neue_sitzung()
        code, body = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'Hallo'})
        self.assertEqual(code, 200)
        self.assertEqual(body['status'], 'kein_modell')
        self.assertIn('Kein Modell geladen', body['grund'])
        self.assertIn('gguf fehlt', body['grund'])
        self.assertEqual(self.modell.requests, [])

    def test_titel_aendern_und_loeschen(self):
        kopf = self.neue_sitzung(titel='alt')
        code, s = anfrage(self.url, 'PATCH', f"/api/harness/sitzungen/{kopf['id']}", {'titel': 'neu'})
        self.assertEqual((code, s['titel']), (200, 'neu'))
        code, body = anfrage(self.url, 'DELETE', f"/api/harness/sitzungen/{kopf['id']}")
        self.assertEqual(code, 200, body)
        self.assertTrue(body['verschoben'].startswith('geloescht/'))
        code, _ = anfrage(self.url, 'GET', f"/api/harness/sitzungen/{kopf['id']}")
        self.assertEqual(code, 404)
        ordner = self.hub.project_root / 'runtime_data' / 'harness' / 'sitzungen' / 'geloescht'
        self.assertTrue((ordner / (kopf['id'] + '.jsonl')).is_file(), 'nichts wird wirklich gelöscht')

    def test_sitzungs_mission_ist_keine_offene_aufgabe(self):
        """Altfehler der Chat-Sitzungen: jede hing als offene Aufgabe im Cockpit. Die Harness-Mission ist nur Träger für Audit und Nutzung."""
        kopf = self.neue_sitzung()
        mid = kopf['mission_id']
        code, missions = anfrage(self.url, 'GET', '/api/missions')
        eintrag = next(m for m in missions if m['mission_id'] == mid)
        self.assertFalse(eintrag['offen'])
        _code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'Hallo'})
        strom(self.url, out['antwort_id'])
        self.assertTrue(self.modell.requests, 'die geschlossene Mission trägt die Modellaufrufe weiter')
        for _ in range(50):
            if not self.hub.harness.threads: break
            time.sleep(0.05)
        anfrage(self.url, 'DELETE', f"/api/harness/sitzungen/{kopf['id']}")
        self.assertEqual(self.hub.runtime.missions.load(mid)['lifecycle']['status'], 'archived')

    def test_ohne_token_kein_zugang(self):
        parts = urlsplit(self.url)
        for method in ('GET', 'PATCH', 'DELETE'):
            c = http.client.HTTPConnection(parts.hostname, parts.port, timeout=10)
            c.request(method, '/api/harness/sitzungen')
            self.assertEqual(c.getresponse().status, 403, method)
            c.close()

    def test_unbekannte_wege_und_vorlage(self):
        self.assertEqual(anfrage(self.url, 'GET', '/api/harness/antworten/A-00000000/strom')[0], 404)
        self.assertEqual(anfrage(self.url, 'GET', '/api/harness/sitzungen/S-00000000')[0], 404)
        self.assertEqual(anfrage(self.url, 'GET', '/api/harness/irgendwas')[0], 404)
        code, body = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'sedra-entwicklung', 'vorlage': 'gibt-es-nicht'})
        self.assertEqual((code, body['code']), (400, 'vorlage_unbekannt'))

    def test_ereignisse_auf_dem_gemeinsamen_strom(self):
        vorher = self.hub.events.last_id
        kopf = self.neue_sitzung()
        _code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'Hallo'})
        strom(self.url, out['antwort_id'])
        for _ in range(50):
            namen = [e['event'] for e in self.hub.events.since(vorher)[0]]
            if namen.count('harness.antwort') >= 2: break
            time.sleep(0.05)
        self.assertIn('harness.sitzung', namen)
        self.assertEqual(namen.count('harness.antwort'), 2, 'läuft und fertig')


if __name__ == '__main__':
    unittest.main()
