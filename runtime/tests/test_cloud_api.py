import io
import json
import unittest
from unittest import mock
from urllib.error import HTTPError

from guppi_runtime.models import cloud_api
from guppi_runtime.models.base import ModelAdapterError
from guppi_runtime.models.cloud_api import (CloudAnthropicAdapter, CloudOpenAICompatibleAdapter, build_cloud_adapters,
                                            resolve_secret, require_https_url, secret_env_name)
from guppi_runtime.models.router import ModelRouter
from guppi_runtime.core.content_guard import ContentGuard, ContentGuardStop

KEY = {'GUPPI_SECRET_NVIDIA_API_KEY': 'test-key-not-real'}


def openai_adapter(environ=KEY, model='m-test'):
    return CloudOpenAICompatibleAdapter('nvidia', 'https://api.example.test/v1', 'secret://nvidia/api-key', model, environ=environ)


def anthropic_adapter(environ=None):
    return CloudAnthropicAdapter('anthropic', 'https://api.anthropic.example.test', 'secret://anthropic/api-key', 'claude-test',
                                 environ=environ or {'GUPPI_SECRET_ANTHROPIC_API_KEY': 'test-key-not-real'})


class SecretTest(unittest.TestCase):
    def test_reference_maps_to_environment_name(self):
        self.assertEqual(secret_env_name('secret://nvidia/api-key'), 'GUPPI_SECRET_NVIDIA_API_KEY')

    def test_invalid_reference_is_refused(self):
        for bad in ('nvidia/api-key', 'secret://nvidia', 'secret://Nvidia/API KEY', '', None):
            with self.assertRaises(ModelAdapterError): secret_env_name(bad)

    def test_missing_secret_names_the_variable_but_no_value(self):
        with self.assertRaises(ModelAdapterError) as ctx:
            resolve_secret('secret://nvidia/api-key', environ={})
        self.assertEqual(str(ctx.exception), 'secret_not_set:GUPPI_SECRET_NVIDIA_API_KEY')

    def test_present_secret_is_read_from_environment(self):
        self.assertEqual(resolve_secret('secret://nvidia/api-key', environ=KEY), 'test-key-not-real')


class HttpsOnlyTest(unittest.TestCase):
    def test_cloud_needs_https(self):
        for bad in ('http://api.example.test/v1', 'http://127.0.0.1:1234/v1', 'ftp://x', 'nonsense'):
            with self.assertRaises(ModelAdapterError): require_https_url(bad)

    def test_https_is_accepted_and_trailing_slash_removed(self):
        self.assertEqual(require_https_url('https://api.example.test/v1/'), 'https://api.example.test/v1')


class BuildTest(unittest.TestCase):
    def test_switched_off_builds_nothing(self):
        cfg = {'enabled': False, 'providers': {'nvidia': {'enabled': True, 'kind': 'openai_compatible',
                                                          'base_url': 'https://x.test/v1', 'api_key': 'secret://nvidia/api-key'}}}
        self.assertEqual(build_cloud_adapters(cfg, environ=KEY), [])

    def test_only_enabled_providers_are_built(self):
        cfg = {'enabled': True, 'providers': {
            'nvidia': {'enabled': True, 'kind': 'openai_compatible', 'base_url': 'https://x.test/v1',
                       'api_key': 'secret://nvidia/api-key', 'default_model': 'm'},
            'anthropic': {'enabled': False, 'kind': 'anthropic', 'base_url': 'https://a.test', 'api_key': 'secret://anthropic/api-key'}}}
        adapters = build_cloud_adapters(cfg, environ=KEY)
        self.assertEqual([a.id for a in adapters], ['nvidia'])
        self.assertEqual(adapters[0].route, 'cloud')

    def test_unknown_kind_and_http_url_are_config_errors(self):
        with self.assertRaises(ValueError):
            build_cloud_adapters({'enabled': True, 'providers': {'x': {'enabled': True, 'kind': 'ftp'}}})
        with self.assertRaises(ValueError):
            build_cloud_adapters({'enabled': True, 'providers': {'x': {'enabled': True, 'kind': 'openai_compatible',
                                                                       'base_url': 'http://x.test', 'api_key': 'secret://x/k'}}})


class OpenAICompatibleTest(unittest.TestCase):
    def test_request_carries_key_and_model_and_maps_answer(self):
        seen = {}

        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(req, timeout):
            seen['url'] = req.full_url
            seen['auth'] = req.get_header('Authorization')
            seen['body'] = json.loads(req.data.decode('utf-8'))
            seen['timeout'] = timeout
            body = {'choices': [{'message': {'content': 'pong'}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 3, 'completion_tokens': 1}}
            return Resp(json.dumps(body).encode('utf-8'))

        with mock.patch.object(cloud_api, 'urlopen', side_effect=fake_urlopen):
            out = openai_adapter().chat([{'role': 'user', 'content': 'ping'}], temperature=0.2)
        self.assertEqual(seen['url'], 'https://api.example.test/v1/chat/completions')
        self.assertEqual(seen['auth'], 'Bearer test-key-not-real')
        self.assertEqual(seen['body']['model'], 'm-test')
        self.assertEqual(seen['body']['temperature'], 0.2)
        self.assertFalse(seen['body']['stream'])
        self.assertEqual(out['content'], 'pong')
        self.assertEqual(out['usage'], {'input_tokens': 3, 'output_tokens': 1})
        self.assertEqual(out['provider'], 'nvidia')

    def test_local_only_options_are_refused_not_dropped(self):
        with self.assertRaises(ModelAdapterError) as ctx:
            openai_adapter().chat([{'role': 'user', 'content': 'x'}], tools=[{'type': 'function'}])
        self.assertEqual(str(ctx.exception), 'cloud_option_unsupported:tools')

    def test_no_model_is_an_error_not_a_guess(self):
        with self.assertRaises(ModelAdapterError) as ctx:
            openai_adapter(model=None).chat([{'role': 'user', 'content': 'x'}])
        self.assertEqual(str(ctx.exception), 'cloud_model_required')

    def test_http_error_hides_body_and_key(self):
        err = HTTPError('https://api.example.test/v1/chat/completions', 401, 'nope', None, io.BytesIO(b'key test-key-not-real echoed'))
        with mock.patch.object(cloud_api, 'urlopen', side_effect=err):
            with self.assertRaises(ModelAdapterError) as ctx:
                openai_adapter().chat([{'role': 'user', 'content': 'x'}])
        self.assertEqual(str(ctx.exception), 'cloud_api_http_401')
        self.assertNotIn('test-key-not-real', str(ctx.exception))

    def test_health_needs_key_and_model_and_makes_no_request(self):
        with mock.patch.object(cloud_api, 'urlopen', side_effect=AssertionError('no network in health')):
            self.assertTrue(openai_adapter().health())
            self.assertFalse(openai_adapter(environ={}).health())
            self.assertFalse(openai_adapter(model=None).health())


class AnthropicTest(unittest.TestCase):
    def test_system_goes_to_its_own_field_and_stop_reason_maps(self):
        seen = {}

        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(req, timeout):
            seen['headers'] = {k.lower(): v for k, v in req.header_items()}
            seen['body'] = json.loads(req.data.decode('utf-8'))
            body = {'content': [{'type': 'text', 'text': 'Hallo'}], 'stop_reason': 'max_tokens',
                    'usage': {'input_tokens': 5, 'output_tokens': 2}}
            return Resp(json.dumps(body).encode('utf-8'))

        msgs = [{'role': 'system', 'content': 'Sei knapp.'}, {'role': 'user', 'content': 'Hi'}]
        with mock.patch.object(cloud_api, 'urlopen', side_effect=fake_urlopen):
            out = anthropic_adapter().chat(msgs)
        self.assertEqual(seen['body']['system'], 'Sei knapp.')
        self.assertEqual(seen['body']['messages'], [{'role': 'user', 'content': 'Hi'}])
        self.assertEqual(seen['body']['max_tokens'], cloud_api.DEFAULT_ANTHROPIC_MAX_TOKENS)
        self.assertEqual(seen['headers']['x-api-key'], 'test-key-not-real')
        self.assertEqual(seen['headers']['anthropic-version'], cloud_api.ANTHROPIC_VERSION)
        self.assertEqual(out['content'], 'Hallo')
        self.assertEqual(out['finish_reason'], 'length')
        self.assertTrue(out['truncated'])
        self.assertEqual(out['usage'], {'input_tokens': 5, 'output_tokens': 2})


class RouterTest(unittest.TestCase):
    class Local:
        id = 'local'
        route = 'local'
        def health(self): return True

    def test_default_choice_never_picks_cloud(self):
        router = ModelRouter()
        router.register(openai_adapter())
        with self.assertRaises(ModelAdapterError):
            router.choose()
        router.register(self.Local())
        self.assertEqual(router.choose().id, 'local')

    def test_named_cloud_provider_is_reachable_on_purpose(self):
        router = ModelRouter()
        router.register(openai_adapter())
        self.assertEqual(router.choose('nvidia').id, 'nvidia')


class GuardTest(unittest.TestCase):
    def test_cloud_call_is_blocked_while_switch_is_off(self):
        guard = ContentGuard(cloud_enabled=False)
        called = []
        with self.assertRaises(ContentGuardStop) as ctx:
            guard.call([{'role': 'user', 'content': 'Schreibe ein Gedicht.'}], model='m', route='cloud',
                       complete=lambda msgs: called.append(msgs) or 'x')
        self.assertIn('SG_CLOUD_DISABLED', ctx.exception.result.reasons)
        self.assertEqual(called, [])

    def test_personal_data_is_pseudonymized_before_cloud(self):
        guard = ContentGuard(cloud_enabled=True)
        sent = []
        guard.call([{'role': 'user', 'content': 'Kontakt: max.mustermann@example.com bitte antworten.'}], model='m',
                   route='cloud', complete=lambda msgs: sent.append(msgs) or 'ok')
        self.assertEqual(len(sent), 1)
        outgoing = json.dumps(sent[0], ensure_ascii=False)
        self.assertNotIn('max.mustermann@example.com', outgoing)

    def test_personal_data_stays_allowed_locally(self):
        guard = ContentGuard(cloud_enabled=False)
        out = guard.call([{'role': 'user', 'content': 'Kontakt: max.mustermann@example.com bitte antworten.'}], model='m',
                         route='local', complete=lambda msgs: 'ok')
        self.assertEqual(out.status, 'OK')


class SettingsTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from guppi_runtime import cloud_settings
        self.cs = cloud_settings
        self.root = Path(tempfile.mkdtemp(prefix='cloud-settings-'))
        self.store = cloud_settings.CloudKeyStore(cloud_settings.key_store_path(self.root))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def test_default_view_is_off_and_shows_no_key(self):
        v = self.cs.view(self.root, self.store, environ={})
        self.assertFalse(v['enabled'])
        self.assertTrue(all(not p['enabled'] for p in v['providers']))
        self.assertTrue(all(p['key'] == 'fehlt' for p in v['providers']))

    def test_env_key_is_reported_as_state_only(self):
        v = self.cs.view(self.root, self.store, environ={'GUPPI_SECRET_NVIDIA_API_KEY': 'test-key-not-real'})
        nvidia = next(p for p in v['providers'] if p['id'] == 'nvidia')
        self.assertEqual(nvidia['key'], 'umgebung')
        self.assertNotIn('test-key-not-real', repr(v))

    def test_save_writes_only_known_fields_and_turns_master_on(self):
        v = self.cs.save(self.root, {'enabled': True, 'providers': {'nvidia': {'enabled': True, 'default_model': 'meta/test-model',
                                                                              'base_url': 'https://integrate.example.test/v1/'}}})
        self.assertTrue(v['enabled'])
        cfg = self.cs.load_config(self.root)
        self.assertTrue(cfg['enabled'])
        self.assertEqual(cfg['providers']['nvidia']['default_model'], 'meta/test-model')
        self.assertEqual(cfg['providers']['nvidia']['base_url'], 'https://integrate.example.test/v1')
        self.assertEqual(cfg['providers']['nvidia']['api_key'], 'secret://nvidia/api-key')     # the reference, never a value

    def test_save_refuses_unknown_provider_and_insecure_url(self):
        with self.assertRaises(ValueError): self.cs.save(self.root, {'enabled': True, 'providers': {'evil': {'enabled': True}}})
        with self.assertRaises(ValueError):
            self.cs.save(self.root, {'enabled': True, 'providers': {'nvidia': {'base_url': 'http://x.example.test/v1'}}})
        with self.assertRaises(ValueError):
            self.cs.save(self.root, {'enabled': True, 'providers': {'nvidia': {'default_model': 'bad model; rm -rf'}}})
        with self.assertRaises(ValueError): self.cs.save(self.root, {'enabled': 'yes', 'providers': {}})

    def test_key_value_must_be_one_token(self):
        for bad in ('', 'short', 'has space in it', 5, 'x' * 401):
            with self.assertRaises(ValueError): self.cs.check_key_value(bad)
        self.assertEqual(self.cs.check_key_value('  abcdefgh12345  '), 'abcdefgh12345')

    def test_key_store_refuses_outside_windows(self):
        if self.cs.CloudKeyStore.available(): self.skipTest('Windows: the DPAPI path is used')
        with self.assertRaises(ValueError): self.store.set('nvidia', 'abcdefgh12345')

    def test_signature_changes_when_a_setting_changes(self):
        before = self.cs.signature(self.root, self.store, {})
        self.cs.save(self.root, {'enabled': True, 'providers': {}})
        self.assertNotEqual(before, self.cs.signature(self.root, self.store, {}))


if __name__ == '__main__':
    unittest.main()
