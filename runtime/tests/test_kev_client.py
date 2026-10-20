"""The Kev client against the wire format of the real Kev server (kev/api.py, kev/serve.py). No weights, no GPU."""
import importlib.util
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import HTTPError

from guppi_runtime.selfdev.kev import KevProviderError, KevVerificationProvider
from guppi_runtime.runtime import GuppiRuntime
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]
ARCH = RUNTIME.parent / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
REAL_API = RUNTIME.parents[1] / 'kev-main' / 'kev-main' / 'kev' / 'api.py'
URL = 'http://127.0.0.1:8008/v1/systemone'

QUESTIONS = {'ok': {'type': 'noul', 'instructions': 'Do the tests pass?'},
             'dept': {'type': 'choice', 'instructions': 'Which team?', 'criteria': {'returns': 'refunds', 'billing': 'charges'}},
             'urgency': {'type': 'score', 'instructions': 'How urgent?', 'criteria': ['can wait', 'this week', 'today']}}


def good_answers():
    return {'ok': {'type': 'noul', 'noul': 0.93},
            'dept': {'type': 'choice', 'choice': 'returns', 'confidence': 0.4, 'probabilities': {'returns': 0.7, 'billing': 0.3}},
            'urgency': {'type': 'score', 'score': 1.3, 'legend': {'0': 'can wait', '1': 'this week', '2': 'today'}, 'confidence': 0.5,
                        'probabilities': {'0': 0.1, '1': 0.6, '2': 0.3}}}


def reply(body):
    class Response:
        def read(self): return body if isinstance(body, bytes) else json.dumps(body).encode()
    return lambda request, timeout: Response()


class ClientTests(unittest.TestCase):
    def provider(self, body=None, **kw):
        self.sent = []
        def opener(request, timeout):
            self.sent.append(request)
            return reply(body if body is not None else {'model': 'kev-latest', 'answers': good_answers(), 'usage': {'input_tokens': 101, 'output_tokens': 161}, 'latency_ms': 40})(request, timeout)
        return KevVerificationProvider(URL, enabled=True, opener=opener, **kw)

    def refused(self, body, code, questions=QUESTIONS):
        with self.assertRaises(KevProviderError, msg=str(body)[:80]) as ctx: self.provider(body).verify('state', questions)
        self.assertEqual(str(ctx.exception), code)

    # ---- request
    def test_the_request_has_the_servers_shape(self):
        self.provider().verify('Candidate passes.', QUESTIONS)
        payload = json.loads(self.sent[0].data.decode())
        self.assertEqual(set(payload), {'state', 'model', 'questions'})
        self.assertEqual((payload['model'], payload['state']), ('kev-latest', 'Candidate passes.'))
        self.assertIsInstance(payload['questions'], dict)                       # a dict keyed by question id, not a list
        self.assertEqual(payload['questions']['dept']['criteria'], {'returns': 'refunds', 'billing': 'charges'})
        self.assertEqual(self.sent[0].get_method(), 'POST')
        self.assertNotIn('Authorization', {k.title() for k in self.sent[0].headers})

    def test_list_form_is_converted_with_stable_ids(self):
        out = self.provider({'answers': {'q1': {'type': 'noul', 'noul': 0.2}, 'second': {'type': 'noul', 'noul': 0.8}}}).verify(
            's', [{'type': 'noul', 'question': 'First?'}, {'id': 'second', 'instructions': 'Second?'}])
        self.assertEqual(list(out['by_id']), ['q1', 'second'])
        sent = json.loads(self.sent[0].data.decode())['questions']
        self.assertEqual((sent['q1']['instructions'], sent['second']['type']), ('First?', 'noul'))
        self.assertEqual([a['noul'] for a in out['answers']], [0.2, 0.8])

    def test_the_bearer_key_is_sent_and_never_shown(self):
        provider = self.provider(api_key='s3cret-key')
        provider.verify('s', QUESTIONS)
        self.assertEqual(self.sent[0].get_header('Authorization'), 'Bearer s3cret-key')
        self.assertTrue(provider.status()['api_key_configured'])
        self.assertNotIn('s3cret-key', json.dumps(provider.status()))
        self.assertNotIn('s3cret-key', repr(provider.verify('s', QUESTIONS)['answers']))
        for bad_key in ('', None, 7):
            self.assertFalse(KevVerificationProvider(URL, enabled=True, api_key=bad_key).status()['api_key_configured'])

    def test_question_normalization_rules(self):
        norm = KevVerificationProvider.normalize_questions
        self.assertEqual(norm(QUESTIONS), QUESTIONS)
        bad = [[], {}, 'text', None, [1], [{'type': 'essay'}], [{'type': 'choice', 'instructions': 'x'}], [{'type': 'choice', 'criteria': {}}],
               [{'type': 'choice', 'criteria': ['a']}], [{'type': 'score', 'criteria': {}}], [{'type': 'score', 'criteria': []}], [{'type': 'noul', 'criteria': ['x']}],
               [{'id': 'same', 'type': 'noul'}, {'id': 'same', 'type': 'noul'}], [{'id': '1bad', 'type': 'noul'}], [{'id': 'has space', 'type': 'noul'}],
               [{'type': 'noul'}] * 33, [{'criteria': {'a': 'b'}}], {'x': 'not a dict'}, {'': {'type': 'noul'}}]
        for questions in bad:
            with self.assertRaises(ValueError, msg=str(questions)[:60]): norm(questions)
        with self.assertRaises(ValueError): self.provider().verify('', QUESTIONS)
        with self.assertRaises(ValueError): self.provider().verify('x' * 65537, QUESTIONS)
        with self.assertRaises(ValueError): self.provider().verify(['not text'], QUESTIONS)

    def test_disabled_provider_is_unavailable_and_sends_nothing(self):
        provider = KevVerificationProvider(URL, enabled=False, opener=lambda *a: self.fail('must not be called'))
        self.assertEqual(provider.verify('s', QUESTIONS), {'status': 'UNAVAILABLE', 'provider': 'kev', 'reason': 'kev_provider_disabled'})

    def test_only_loopback_http_is_accepted(self):
        for url in ('http://example.com/v1/systemone', 'https://127.0.0.1:8008/v1/systemone', 'http://127.0.0.1.evil.com/x', 'http://10.0.0.5:8008/x',
                    'ftp://127.0.0.1/x', 'http://0.0.0.0:8008/x', ''):
            with self.assertRaises(ValueError, msg=url): KevVerificationProvider(url, enabled=True)
        for url in ('http://127.0.0.1:8008/v1/systemone', 'http://localhost:8008/v1/systemone', 'http://[::1]:8008/v1/systemone'):
            KevVerificationProvider(url, enabled=True)

    # ---- response
    def test_a_valid_response_is_returned_as_a_model_assessment(self):
        out = self.provider().verify('s', QUESTIONS)
        self.assertEqual((out['status'], out['trust_level'], out['model']), ('ANSWERED', 'model_assessment', 'kev-latest'))
        self.assertEqual(out['usage'], {'input_tokens': 101, 'output_tokens': 161})
        self.assertEqual([a['type'] for a in out['answers']], ['noul', 'choice', 'score'])
        self.assertEqual(out['by_id']['dept']['choice'], 'returns')

    def test_usage_is_passed_on_only_when_it_is_whole_numbers(self):
        for usage, expected in (({'input_tokens': 5, 'output_tokens': 7, 'junk': 1}, {'input_tokens': 5, 'output_tokens': 7}),
                                ({'input_tokens': '5'}, {}), ('x', None), (None, None)):
            self.assertEqual(self.provider({'answers': good_answers(), 'usage': usage}).verify('s', QUESTIONS)['usage'], expected)

    def test_the_old_list_shape_is_not_what_kev_sends_and_is_refused(self):
        self.refused({'answers': [{'type': 'noul', 'noul': 0.5}] * 3}, 'kev_answer_set_mismatch')

    def test_answers_must_match_the_questions_exactly(self):
        missing = good_answers(); missing.pop('urgency')
        extra = {**good_answers(), 'surprise': {'type': 'noul', 'noul': 0.5}}
        for body in (missing, extra, {}, None, 'x', []):
            self.refused({'answers': body}, 'kev_answer_set_mismatch')
        wrong_type = good_answers(); wrong_type['ok'] = {'type': 'choice', 'choice': 'a', 'confidence': 0.1, 'probabilities': {'a': 1.0}}
        self.refused({'answers': wrong_type}, 'kev_answer_type_mismatch')
        self.refused({'answers': {**good_answers(), 'ok': 'yes'}}, 'kev_answer_type_mismatch')

    def test_numbers_must_be_probabilities(self):
        def with_(qid, **changes):
            answers = good_answers(); answers[qid] = {**answers[qid], **changes}; return {'answers': answers}
        for body in (with_('ok', noul=1.2), with_('ok', noul=-0.1), with_('ok', noul=True), with_('ok', noul='0.9'), with_('ok', noul=None),
                     with_('dept', choice='refunds'), with_('dept', choice=None), with_('dept', confidence=1.5), with_('dept', confidence=None),
                     with_('dept', probabilities={'returns': 0.7}), with_('dept', probabilities={'returns': 0.7, 'billing': 0.3, 'x': 0.0}),
                     with_('dept', probabilities={'returns': 0.9, 'billing': 0.3}), with_('dept', probabilities={'returns': 1.2, 'billing': -0.2}),
                     with_('dept', probabilities={'returns': True, 'billing': 0.0}), with_('dept', probabilities='x'),
                     with_('urgency', score=2.5), with_('urgency', score=-0.2), with_('urgency', score=False),
                     with_('urgency', probabilities={'0': 0.1, '1': 0.6}), with_('urgency', probabilities={'a': 0.1, 'b': 0.6, 'c': 0.3})):
            self.refused(body, 'kev_invalid_answer')

    def test_probability_tolerance_matches_the_servers_own_clients(self):
        near = good_answers(); near['dept']['probabilities'] = {'returns': 0.7, 'billing': 0.315}      # sum 1.015
        self.assertEqual(self.provider({'answers': near}).verify('s', QUESTIONS)['status'], 'ANSWERED')
        far = good_answers(); far['dept']['probabilities'] = {'returns': 0.7, 'billing': 0.33}          # sum 1.03
        self.refused({'answers': far}, 'kev_invalid_answer')

    def test_broken_bodies_are_errors_never_answers(self):
        self.refused([1, 2], 'kev_invalid_response')
        self.refused({'no': 'answers'}, 'kev_answer_set_mismatch')
        with self.assertRaises(KevProviderError) as ctx: self.provider(b'<html>proxy error</html>').verify('s', QUESTIONS)
        self.assertEqual(str(ctx.exception), 'kev_request_failed:JSONDecodeError')
        with self.assertRaises(KevProviderError) as ctx: self.provider(b'x' * (2 * 1024 * 1024 + 1)).verify('s', QUESTIONS)
        self.assertEqual(str(ctx.exception), 'kev_response_too_large')

    def test_transport_failures_name_themselves(self):
        def opener_for(exc): return lambda request, timeout: (_ for _ in ()).throw(exc)
        cases = [(HTTPError(URL, 401, 'no', {}, None), 'kev_unauthorized'), (HTTPError(URL, 500, 'boom', {}, None), 'kev_http_500'),
                 (HTTPError(URL, 422, 'bad', {}, None), 'kev_http_422'), (ConnectionRefusedError(), 'kev_request_failed:ConnectionRefusedError'),
                 (TimeoutError(), 'kev_request_failed:TimeoutError')]
        for exc, code in cases:
            with self.assertRaises(KevProviderError) as ctx: KevVerificationProvider(URL, enabled=True, opener=opener_for(exc)).verify('s', QUESTIONS)
            self.assertEqual(str(ctx.exception), code)


class LoopbackServerTests(unittest.TestCase):
    """A real HTTP round trip (urlopen, headers, status codes) against a stand-in that follows kev/serve.py."""

    def serve(self, *, key=None, handler_body=None):
        outer = self; outer.seen = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                outer.seen.append((self.path, self.headers.get('Authorization'), body))
                if key and self.headers.get('Authorization') != f'Bearer {key}':
                    payload, status = b'{"detail": "missing or invalid API key"}', 401
                else:
                    answers = {}
                    for qid, q in body['questions'].items():
                        if q['type'] == 'noul': answers[qid] = {'type': 'noul', 'noul': 0.9}
                        elif q['type'] == 'choice':
                            keys = list(q['criteria']); answers[qid] = {'type': 'choice', 'choice': keys[0], 'confidence': 0.0, 'probabilities': {k: round(1 / len(keys), 4) for k in keys}}
                        else:
                            n = len(q['criteria']); answers[qid] = {'type': 'score', 'score': 0.0, 'confidence': 0.0, 'legend': {}, 'probabilities': {str(i): round(1 / n, 4) for i in range(n)}}
                    payload, status = json.dumps({'model': body['model'], 'answers': answers, 'usage': {'input_tokens': 9, 'output_tokens': 4}, 'latency_ms': 1}).encode(), 200
                self.send_response(status); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(payload))); self.end_headers(); self.wfile.write(payload)

        server = HTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown); self.addCleanup(server.server_close)
        return f'http://127.0.0.1:{server.server_address[1]}/v1/systemone'

    def test_round_trip_on_an_open_server(self):
        out = KevVerificationProvider(self.serve(), enabled=True).verify('Shoes arrived late.', QUESTIONS)
        self.assertEqual(out['status'], 'ANSWERED')
        self.assertEqual((out['usage'], out['by_id']['ok']['noul']), ({'input_tokens': 9, 'output_tokens': 4}, 0.9))
        self.assertEqual(self.seen[0][0], '/v1/systemone')
        self.assertIsNone(self.seen[0][1])

    def test_round_trip_with_a_bearer_key(self):
        url = self.serve(key='abc123')
        self.assertEqual(KevVerificationProvider(url, enabled=True, api_key='abc123').verify('s', QUESTIONS)['status'], 'ANSWERED')
        with self.assertRaises(KevProviderError) as ctx: KevVerificationProvider(url, enabled=True).verify('s', QUESTIONS)
        self.assertEqual(str(ctx.exception), 'kev_unauthorized')
        with self.assertRaises(KevProviderError) as ctx: KevVerificationProvider(url, enabled=True, api_key='wrong').verify('s', QUESTIONS)
        self.assertEqual(str(ctx.exception), 'kev_unauthorized')

    def test_nothing_listening_is_a_clean_error(self):
        server = HTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler); port = server.server_address[1]; server.server_close()
        with self.assertRaises(KevProviderError) as ctx: KevVerificationProvider(f'http://127.0.0.1:{port}/v1/systemone', enabled=True, timeout=2).verify('s', QUESTIONS)
        self.assertTrue(str(ctx.exception).startswith('kev_request_failed:'))


@unittest.skipUnless(REAL_API.exists(), 'the Kev project folder is not next to the runtime')
class AgainstTheRealKevSchemaTests(unittest.TestCase):
    """Uses kev/api.py itself (pydantic models and answer builder) as the reference, when it can be imported."""

    @classmethod
    def setUpClass(cls):
        try: import pydantic  # noqa: F401
        except ImportError: raise unittest.SkipTest('pydantic is not installed here')
        spec = importlib.util.spec_from_file_location('kev_reference_api', REAL_API)
        cls.api = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.api)

    def test_our_requests_validate_against_the_servers_own_model(self):
        sent = []
        provider = KevVerificationProvider(URL, enabled=True, opener=lambda r, t: sent.append(r) or reply({'answers': good_answers()})(r, t))
        provider.verify('state text', QUESTIONS)
        request = self.api.SystemOneRequest.model_validate(json.loads(sent[0].data.decode()))
        self.assertEqual(list(request.questions), ['ok', 'dept', 'urgency'])
        # the old list-shaped request would have been rejected by the real server
        with self.assertRaises(Exception): self.api.SystemOneRequest.model_validate({'state': 's', 'questions': [{'type': 'noul'}]})

    def test_answers_built_by_the_real_code_pass_our_checks(self):
        request = self.api.SystemOneRequest.model_validate({'state': 's', 'questions': QUESTIONS})
        _, meta = self.api.to_record(request)
        probs = [[0.1, 0.9], [0.65, 0.35], [0.2, 0.5, 0.3]]
        answers = self.api.to_answers(probs, meta)
        out = KevVerificationProvider(URL, enabled=True, opener=reply({'model': 'kev-latest', 'answers': answers})).verify('s', QUESTIONS)
        self.assertEqual(out['status'], 'ANSWERED')
        self.assertEqual((out['by_id']['ok']['noul'], out['by_id']['dept']['choice']), (0.9, 'returns'))

    def test_every_combination_of_real_probabilities_is_accepted(self):
        request = self.api.SystemOneRequest.model_validate({'state': 's', 'questions': QUESTIONS})
        _, meta = self.api.to_record(request)
        for a in (0.0, 0.33, 1.0):
            probs = [[1 - a, a], [a, 1 - a], [a / 2, a / 2, 1 - a]]
            answers = self.api.to_answers(probs, meta)
            self.assertEqual(KevVerificationProvider(URL, enabled=True, opener=reply({'answers': answers})).verify('s', QUESTIONS)['status'], 'ANSWERED', a)


class RuntimeWiringTests(unittest.TestCase):
    def test_the_key_comes_from_the_environment_and_stays_out_of_every_report(self):
        old = os.environ.get('KEV_API_KEY'); os.environ['KEV_API_KEY'] = 'env-secret-777'
        try:
            with tempfile.TemporaryDirectory() as tmp:
                rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
                self.assertTrue(rt.kev.status()['api_key_configured'])
                self.assertEqual(rt.kev.endpoint, 'http://127.0.0.1:8008/v1/systemone')
                self.assertEqual(rt.kev.model, 'kev-latest')
                self.assertNotIn('env-secret-777', json.dumps(rt.boot(), default=str))
                self.assertNotIn('env-secret-777', json.dumps(rt.self_development.view(), default=str))
                self.assertFalse(rt.kev.enabled)
        finally:
            if old is None: os.environ.pop('KEV_API_KEY', None)
            else: os.environ['KEV_API_KEY'] = old

    def test_without_the_variable_there_is_no_key(self):
        old = os.environ.pop('KEV_API_KEY', None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self.assertFalse(GuppiRuntime(Path(tmp) / 'project', ARCH).kev.status()['api_key_configured'])
        finally:
            if old is not None: os.environ['KEV_API_KEY'] = old


if __name__ == '__main__':
    unittest.main()
