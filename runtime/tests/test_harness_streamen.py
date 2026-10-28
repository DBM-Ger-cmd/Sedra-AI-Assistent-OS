"""T1 der Harness-Shell (SPEC_HARNESS_SHELL_v1_G3_STUFE1): Streamen mit Rückruf `on_delta` im lokalen Adapter, durchgereicht von Router und Control.

Ein kleiner Attrappen-Server spricht die OpenAI-Form: mit `stream` als SSE in Teilstücken, ohne `stream` als ganze Antwort mit derselben
`message` – so lässt sich prüfen, dass beide Wege dieselbe Nachricht liefern."""
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from guppi_runtime.models.base import BaseModelAdapter
from guppi_runtime.models.llamacpp import LlamaCppServerAdapter
from guppi_runtime.models.recording import SAMPLING_KEYS
from guppi_runtime.models.router import ModelRouter
from guppi_runtime.modules.control import ControlMasterModule

MESSAGES = [{'role': 'user', 'content': 'go'}]
TOOLS = [{'type': 'function', 'function': {'name': 'zustand', 'parameters': {'type': 'object', 'properties': {}}}}]

# Zwei Werkzeugaufrufe, deren Name und Argumente über mehrere Teilstücke verteilt kommen (wie llama-server sie schickt)
CALL_EVENTS = [
    {'choices': [{'delta': {'reasoning_content': 'erst '}, 'finish_reason': None}]},
    {'choices': [{'delta': {'reasoning_content': 'nachdenken'}, 'finish_reason': None}]},
    {'choices': [{'delta': {'content': 'Ich '}, 'finish_reason': None}]},
    {'choices': [{'delta': {'content': 'schaue nach.'}, 'finish_reason': None}]},
    {'choices': [{'delta': {'tool_calls': [{'index': 0, 'id': 'call_a', 'type': 'function', 'function': {'name': 'zust', 'arguments': ''}}]}, 'finish_reason': None}]},
    {'choices': [{'delta': {'tool_calls': [{'index': 0, 'function': {'name': 'and', 'arguments': '{"was":'}}]}, 'finish_reason': None}]},
    {'choices': [{'delta': {'tool_calls': [{'index': 1, 'id': 'call_b', 'type': 'function', 'function': {'name': 'modelle', 'arguments': '{}'}}]}, 'finish_reason': None}]},
    {'choices': [{'delta': {'tool_calls': [{'index': 0, 'function': {'arguments': ' "gpu"}'}}]}, 'finish_reason': None}]},
    {'choices': [{'delta': {}, 'finish_reason': 'tool_calls'}]},
    {'choices': [], 'usage': {'prompt_tokens': 12, 'completion_tokens': 7}},
]
WHOLE_MESSAGE = {'role': 'assistant', 'content': 'Ich schaue nach.',
                 'tool_calls': [{'id': 'call_a', 'type': 'function', 'function': {'name': 'zustand', 'arguments': '{"was": "gpu"}'}},
                                {'id': 'call_b', 'type': 'function', 'function': {'name': 'modelle', 'arguments': '{}'}}]}


class Attrappe:
    """OpenAI-förmiger Server auf 127.0.0.1. `events` als SSE (mit `stream`), sonst `whole` als eine Antwort. `endless` streamt ohne Ende."""

    def __init__(self, events=None, whole=None, endless=False):
        outer = self
        self.events, self.whole, self.endless = events or [], whole, endless
        self.payloads, self.client_left, self.sent = [], threading.Event(), 0

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass

            def do_GET(self):
                body = json.dumps({'data': [{'id': 'm'}]}).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body))); self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get('Content-Length') or 0)
                outer.payloads.append(json.loads(self.rfile.read(length) or b'{}'))
                if not outer.payloads[-1].get('stream'):
                    body = json.dumps({'choices': [{'message': outer.whole, 'finish_reason': 'tool_calls'}], 'usage': {'prompt_tokens': 12, 'completion_tokens': 7}}).encode()
                    self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body))); self.end_headers()
                    self.wfile.write(body); return
                self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
                try:
                    if outer.endless:
                        while outer.sent < 2_000_000:
                            data = ('data: ' + json.dumps({'choices': [{'delta': {'content': 'wort '}, 'finish_reason': None}]}) + '\n\n').encode()
                            self.wfile.write(data); self.wfile.flush(); outer.sent += len(data)
                            time.sleep(0.002)
                    else:
                        for event in outer.events:
                            self.wfile.write(('data: ' + json.dumps(event) + '\n\n').encode()); self.wfile.flush()
                        self.wfile.write(b'data: [DONE]\n\n'); self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                    outer.client_left.set()

        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.httpd.server_port}'

    def close(self):
        self.httpd.shutdown(); self.httpd.server_close()


class AdapterTests(unittest.TestCase):
    def serve(self, **kw):
        server = Attrappe(**kw)
        self.addCleanup(server.close)
        return server, LlamaCppServerAdapter(server.url, timeout=10)

    def test_text_und_denken_kommen_in_reihenfolge(self):
        server, adapter = self.serve(events=CALL_EVENTS[:4] + [{'choices': [{'delta': {}, 'finish_reason': 'stop'}]}])
        seen = []
        out = adapter.chat(MESSAGES, model='m', on_delta=lambda k, s: seen.append((k, s)))
        self.assertEqual(seen, [('denken', 'erst '), ('denken', 'nachdenken'), ('antwort', 'Ich '), ('antwort', 'schaue nach.')])
        self.assertEqual(out['content'], 'Ich schaue nach.')
        self.assertEqual(out['finish_reason'], 'stop')
        self.assertTrue(server.payloads[0]['stream'], 'mit on_delta wird gestreamt, auch ohne stream_guard')

    def test_zwei_werkzeugaufrufe_in_teilstuecken_ergeben_dieselbe_message_wie_ohne_streamen(self):
        server, adapter = self.serve(events=CALL_EVENTS, whole=WHOLE_MESSAGE)
        pieces = []
        streamed = adapter.chat(MESSAGES, model='m', tools=TOOLS, on_delta=lambda k, s: pieces.append(k))
        whole = adapter.chat(MESSAGES, model='m', tools=TOOLS)
        self.assertFalse(server.payloads[1].get('stream'))
        self.assertEqual(streamed['message'], whole['message'])
        self.assertEqual(streamed['message']['tool_calls'][0]['function'], {'name': 'zustand', 'arguments': '{"was": "gpu"}'})
        self.assertEqual(pieces.count('werkzeug'), 4)
        self.assertEqual(streamed['usage'], {'input_tokens': 12, 'output_tokens': 7})
        self.assertEqual(streamed['finish_reason'], 'tool_calls')

    def test_ohne_werkzeuge_keine_message_wie_bisher(self):
        _server, adapter = self.serve(events=CALL_EVENTS[2:4])
        out = adapter.chat(MESSAGES, model='m', on_delta=lambda k, s: None)
        self.assertIsNone(out['message'])

    def test_wirft_on_delta_wird_die_verbindung_geschlossen(self):
        server, adapter = self.serve(endless=True)
        count = [0]

        def stopp(kanal, stueck):
            count[0] += 1
            if count[0] >= 5: raise RuntimeError('stopp')
        started = time.monotonic()
        out = adapter.chat(MESSAGES, model='m', on_delta=stopp)
        self.assertEqual(out['finish_reason'], 'abgebrochen')
        self.assertIn('stopp', out['stopped'])
        self.assertEqual(out['content'], 'wort ' * 5)
        self.assertTrue(server.client_left.wait(5), 'der Server merkt, dass der Leser weg ist')
        self.assertLess(time.monotonic() - started, 5)

    def test_kein_aufrufbarer_rueckruf_wird_abgelehnt(self):
        _server, adapter = self.serve(events=CALL_EVENTS)
        with self.assertRaises(Exception):
            adapter.chat(MESSAGES, model='m', on_delta='nein')


class Fake(BaseModelAdapter):
    def __init__(self, aid, route='local'):
        self.id, self.route, self.seen = aid, route, []

    def health(self): return True

    def chat(self, messages, model=None, **kwargs):
        self.seen.append(dict(kwargs))
        if kwargs.get('on_delta'): kwargs['on_delta']('antwort', 'hallo')
        return {'provider': self.id, 'model': model, 'content': 'hallo', 'usage': None, 'finish_reason': 'stop'}


class DurchreichenTests(unittest.TestCase):
    def test_router_reicht_on_delta_nur_an_lokale_adapter(self):
        router = ModelRouter()
        local, cloud = Fake('lokal'), Fake('wolke', route='cloud')
        router.register(local); router.register(cloud)
        got = []
        router.chat('M-1', MESSAGES, provider='lokal', on_delta=lambda k, s: got.append(s))
        router.chat('M-1', MESSAGES, provider='wolke', on_delta=lambda k, s: got.append(s))
        self.assertEqual(got, ['hallo'])
        self.assertIn('on_delta', local.seen[0])
        self.assertNotIn('on_delta', cloud.seen[0])

    def test_on_delta_geht_nicht_in_die_aufzeichnung(self):
        self.assertNotIn('on_delta', SAMPLING_KEYS)
        self.assertNotIn('stream', SAMPLING_KEYS)

    def test_control_reicht_den_rueckruf_durch_und_nicht_in_die_pruefsumme(self):
        router = ModelRouter()
        local = Fake('lokal')
        router.register(local)
        with tempfile.TemporaryDirectory() as tmp:
            control = ControlMasterModule(Path(tmp), guard=None, artifacts=None, model_router=router)
            mission = {'identity': {'mission_id': 'M-1'}, 'plan_revision': 0}
            got = []
            out = control.execute(mission, {'action': 'model_inference', 'provider': 'lokal', 'messages': MESSAGES,
                                            'slot_owner': 'captain-chat', 'stream': lambda k, s: got.append((k, s))})
            self.assertEqual(out['status'], 'completed', out)
            self.assertEqual(got, [('antwort', 'hallo')])
            # ohne Rückruf: dieselben Schlüssel wie bisher
            control.execute(mission, {'action': 'model_inference', 'provider': 'lokal', 'messages': MESSAGES})
            self.assertNotIn('on_delta', local.seen[1])


if __name__ == '__main__':
    unittest.main()
