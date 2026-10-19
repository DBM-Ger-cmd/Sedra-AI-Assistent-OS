import unittest
from unittest import mock

from guppi_runtime import labor
from guppi_runtime.models.base import ModelAdapterError


class Protokoll:
    """Das Logbuch für die Tests: der Cloudweg schreibt nur mit einem Logbuch (Befund G1)."""

    def append(self, event, **kw):
        pass


class FakeAdapter:
    def __init__(self, models, default_model=None, answers=None):
        self.id = 'nvidia'
        self.route = 'cloud'
        self.timeout = 60
        self.default_model = default_model
        self._models = models
        self._answers = answers or {}

    def fetch_models(self):
        return list(self._models)

    def chat(self, messages, model=None, **kwargs):
        self.last_max_tokens = kwargs.get('max_tokens')
        answer = self._answers.get(model, 'OK')
        if isinstance(answer, Exception):
            raise answer
        return {'content': answer}


def config(enabled=True, provider_enabled=True):
    return {'enabled': enabled, 'providers': {'nvidia': {'enabled': provider_enabled, 'kind': 'openai_compatible',
                                                         'base_url': 'https://x.test/v1', 'api_key': 'secret://nvidia/api-key'}}}


class ConnectionTest(unittest.TestCase):
    def test_switched_off_sends_nothing_and_says_why(self):
        with mock.patch.object(labor, 'provider_adapter', side_effect=AssertionError('no adapter may be built')):
            res = labor.connection_test(config(enabled=False), 'nvidia', audit=Protokoll())
        self.assertFalse(res['ok'])
        self.assertEqual(res['steps'][0]['step'], 'Einschalten')

    def test_first_working_model_ends_the_chain(self):
        fake = FakeAdapter(['a/x', 'nvidia/nemotron-3.5-super-vl-120b-a12b'], answers={'a/x': ModelAdapterError('cloud_api_http_404:nope')})
        with mock.patch.object(labor, 'provider_adapter', return_value=fake):
            res = labor.connection_test(config(), 'nvidia', audit=Protokoll())
        self.assertTrue(res['ok'])
        self.assertEqual(res['model'], 'nvidia/nemotron-3.5-super-vl-120b-a12b', 'a Free-Endpoint model is tried before the others')
        self.assertEqual(fake.last_max_tokens, labor.PING_MAX_TOKENS)

    def test_no_model_answers_gives_each_try_and_fails(self):
        fake = FakeAdapter(['a/x', 'b/y'], answers={'a/x': ModelAdapterError('cloud_api_http_404:x'), 'b/y': ''})
        with mock.patch.object(labor, 'provider_adapter', return_value=fake):
            res = labor.connection_test(config(), 'nvidia', audit=Protokoll())
        self.assertFalse(res['ok'])
        self.assertEqual(sum(1 for s in res['steps'] if s['step'].startswith('Testnachricht')), 2)

    def test_key_problem_is_shown_as_the_failing_step(self):
        fake = FakeAdapter([])
        fake.fetch_models = mock.Mock(side_effect=ModelAdapterError('secret_not_set:GUPPI_SECRET_NVIDIA_API_KEY'))
        with mock.patch.object(labor, 'provider_adapter', return_value=fake):
            res = labor.connection_test(config(), 'nvidia', audit=Protokoll())
        self.assertFalse(res['ok'])
        self.assertEqual(res['steps'][-1]['step'], 'Schlüssel und Anbieter')
        self.assertIn('GUPPI_SECRET_NVIDIA_API_KEY', res['steps'][-1]['detail'])


class CloudChatTest(unittest.TestCase):
    def test_switched_off_refuses_before_any_call(self):
        with mock.patch.object(labor, 'provider_adapter', side_effect=AssertionError('no call while off')):
            with self.assertRaises(ValueError) as ctx:
                labor.cloud_chat(config(enabled=False), 'nvidia', 'm', [{'role': 'user', 'content': 'hallo'}], audit=Protokoll())
        self.assertEqual(str(ctx.exception), 'cloud_off')

    def test_produktiv_blocks_personal_data_and_test_mode_replaces_it(self):
        seen = {}
        class Adapter(FakeAdapter):
            def chat(self, messages, model=None, **kwargs):
                seen['sent'] = messages
                return {'content': 'Antwort'}
        with mock.patch.object(labor, 'provider_adapter', return_value=Adapter([])):
            strict = labor.cloud_chat(config(), 'nvidia', 'm/x', [{'role': 'user', 'content': 'Schreib an max.mustermann@example.com'}], audit=Protokoll())
            self.assertEqual(strict['status'], 'blocked')
            self.assertNotIn('sent', seen)
            testing = dict(config(), modus='test')
            ok = labor.cloud_chat(testing, 'nvidia', 'm/x', [{'role': 'user', 'content': 'Schreib an max.mustermann@example.com'}], audit=Protokoll())
            self.assertEqual(ok['status'], 'completed')
            self.assertNotIn('max.mustermann@example.com', str(seen['sent']))

    def test_personal_data_is_not_sent_to_the_cloud(self):
        seen = {}

        class Adapter(FakeAdapter):
            def chat(self, messages, model=None, **kwargs):
                seen['sent'] = messages
                return {'content': 'Antwort'}

        with mock.patch.object(labor, 'provider_adapter', return_value=Adapter([])):
            res = labor.cloud_chat(config(), 'nvidia', 'm/x', [{'role': 'user', 'content': 'Schreib an max.mustermann@example.com'}], audit=Protokoll())
        self.assertEqual(res['status'], 'blocked', 'produktiv: personal data is not sent (Klaus, 16.10.2026)')
        self.assertNotIn('sent', seen, 'the adapter is never called')


class ModelTest(unittest.TestCase):
    def test_every_model_is_asked_once_and_counted(self):
        fake = FakeAdapter(['a/x', 'b/y', 'c/z'], answers={'b/y': ModelAdapterError('cloud_api_http_410:gone')})
        with mock.patch.object(labor, 'provider_adapter', return_value=fake):
            res = labor.model_test(config(), 'nvidia', audit=Protokoll())
        self.assertEqual((res['passed'], res['total']), (2, 3))
        self.assertEqual([r['model'] for r in res['results']], ['a/x', 'b/y', 'c/z'])
        self.assertEqual(fake.timeout, labor.TEST_TIMEOUT_S)

    def test_switched_off_runs_nothing(self):
        res = labor.model_test(config(provider_enabled=False), 'nvidia', audit=Protokoll())
        self.assertEqual(res['results'], [])
        self.assertFalse(res['ok'])


if __name__ == '__main__':
    unittest.main()
