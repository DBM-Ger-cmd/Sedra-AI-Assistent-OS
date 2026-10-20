"""Phase 8f: GUPPI starts and watches its own llama-server. No real process: popen and HTTP are replaced."""
import tempfile
import unittest
from pathlib import Path

import yaml

from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime, build_command, discover_backend
from guppi_runtime.models.model_loader import LoaderConfig, LoadError, ModelLoader
from guppi_runtime.models.runtime_control import RuntimeControlError
from guppi_runtime.models.role_routing import RoutingConfig
from test_model_loader import FakeController, inst
from test_role_routing import recipe, routing_raw
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]


class FakeProc:
    def __init__(self, argv, exit_after_polls=None, code=1):
        self.argv, self.pid = argv, 4242
        self.returncode, self.polls, self.exit_after, self.code = None, 0, exit_after_polls, code
        self.terminated = self.killed = False
        self.wait_raises = False

    def poll(self):
        if self.exit_after is not None and self.returncode is None:
            self.polls += 1
            if self.polls > self.exit_after: self.returncode = self.code
        return self.returncode

    def terminate(self): self.terminated = True; self.returncode = 1
    def kill(self): self.killed = True; self.returncode = -9
    def wait(self, timeout=None):
        if self.wait_raises and not self.killed: raise TimeoutError()
        return self.returncode


class Env:
    """A fake world: the server becomes healthy after `healthy_after` health polls, /props reports `n_ctx`."""
    def __init__(self, healthy_after=2, n_ctx=8192, busy=False):
        self.healthy_after, self.n_ctx, self.polls, self.busy, self.procs = healthy_after, n_ctx, 0, busy, []
        self.exit_after, self.never_healthy = None, False

    def popen(self, argv, **kw):
        proc = FakeProc(argv, self.exit_after); self.procs.append((proc, kw)); return proc

    def get_json(self, url, timeout=3):
        if url.endswith('/health'):
            self.polls += 1
            if self.busy: return 200, {}
            if not self.never_healthy and self.polls > self.healthy_after and self.procs and self.procs[-1][0].returncode is None: return 200, {}
            raise OSError('connection refused')
        if url.endswith('/props'): return 200, {'default_generation_settings': {'n_ctx': self.n_ctx}}
        raise OSError('unknown')


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.gguf = self.root / 'model.gguf'; self.gguf.write_bytes(b'GGUF')
        self.backend = self.root / '.lmstudio' / 'extensions' / 'backends' / 'llama.cpp-win-x86_64-nvidia-cuda12-avx2-2.49.0'
        self.backend.mkdir(parents=True); (self.backend / 'llama-server.exe').write_bytes(b'x')
        (self.backend.parent / 'vendor' / 'win-llama-cuda12-vendor-v2').mkdir(parents=True)
        self.env = Env()

    def config(self, **kw): return LlamaServerConfig({'enabled': True, **kw})

    def runtime(self, env=None, **kw):
        env = env or self.env
        return LlamaServerRuntime(self.config(**kw), self.root / 'state', popen=env.popen, get_json=env.get_json, sleep=lambda s: None,
                                  monotonic=self.clock(), home=self.root)

    @staticmethod
    def clock():
        t = [0.0]
        def now(): t[0] += 0.6; return t[0]
        return now

    def server(self, **kw): return {'gguf': str(self.gguf), 'kv_cache_type': 'q8_0', **kw}


class ConfigTest(Base):
    def test_shipped_file_is_valid_and_off(self):
        config = LlamaServerConfig.load(RUNTIME / 'config' / 'llama_server.yaml')
        self.assertFalse(config.enabled); self.assertEqual((config.port, config.backend_version, config.mtp, config.host), (8089, '2.49.0', True, '127.0.0.1'))

    def test_invalid_values_refuse_start(self):
        for bad in ({'enabled': 'yes'}, {'host': '0.0.0.0'}, {'host': 'example.com'}, {'port': 80}, {'port': True}, {'backend_version': '2.x'}, {'flash_attn': 'maybe'},
                    {'startup_timeout_s': 1}, {'log_dir': '../x'}, {'log_dir': '/abs'}, {'mtp': 1}, {'backend_dir': ''}, 'x'):
            with self.assertRaises(ValueError, msg=str(bad)): LlamaServerConfig(bad)
        with self.assertRaises(ValueError): LlamaServerConfig.load(Path(tempfile.gettempdir()) / 'nope_llama.yaml')


class DiscoveryTest(Base):
    def test_pinned_version_latest_and_explicit_directory(self):
        newer = self.backend.parent / 'llama.cpp-win-x86_64-nvidia-cuda12-avx2-2.50.1'; newer.mkdir(); (newer / 'llama-server.exe').write_bytes(b'x')
        (self.backend.parent / 'llama.cpp-win-x86_64-vulkan-avx2-9.9.9').mkdir()                      # other flavours are ignored
        backend, vendor = discover_backend(self.config(), self.root)
        self.assertEqual((backend.name.endswith('2.49.0'), vendor.name), (True, 'win-llama-cuda12-vendor-v2'))
        self.assertTrue(discover_backend(self.config(backend_version='latest'), self.root)[0].name.endswith('2.50.1'))
        self.assertEqual(discover_backend(self.config(backend_version='9.9'), self.root), (None, None))
        explicit = discover_backend(self.config(backend_dir=str(newer)), self.root)
        self.assertEqual(explicit[0], newer)
        self.assertEqual(discover_backend(self.config(backend_dir=str(self.root / 'missing')), self.root), (None, None))
        self.assertEqual(discover_backend(self.config(), self.root / 'nowhere'), (None, None))


class CommandTest(Base):
    def args(self, **kw):
        base = dict(gguf=self.gguf, context=8192, host='127.0.0.1', port=8089, alias='m')
        base.update(kw); return build_command('llama-server.exe', **base)

    def test_every_option_is_explicit_and_mtp_is_off_unless_asked(self):
        argv = self.args(kv_type='q8_0')
        for pair in (['-c', '8192'], ['-ngl', '99'], ['-np', '1'], ['-ctk', 'q8_0'], ['-ctv', 'q8_0'], ['-fa', 'on'], ['--host', '127.0.0.1'], ['--port', '8089'],
                     ['--alias', 'm'], ['--spec-type', 'none'], ['--reasoning', 'auto']):
            self.assertIn(pair[0], argv); self.assertEqual(argv[argv.index(pair[0]) + 1], pair[1])
        self.assertIn('--no-mmproj', argv); self.assertNotIn('--reasoning-budget', argv); self.assertIn('--no-webui', argv)
        self.assertEqual(self.args(spec_type='draft-mtp')[self.args(spec_type='draft-mtp').index('--spec-type') + 1], 'draft-mtp')
        budget = self.args(reasoning='on', reasoning_budget=512)
        self.assertEqual(budget[budget.index('--reasoning-budget') + 1], '512')

    def test_a_launcher_is_put_in_front_of_the_server_command_only_when_a_measurement_sets_it(self):
        env = Env(); rt = LlamaServerRuntime(self.config(), self.root / 's', popen=env.popen, get_json=env.get_json, sleep=lambda s: None, monotonic=self.clock(), home=self.root)
        rt.load_model('m', context_length=8192, gpu='max', server=self.server())
        plain = env.procs[-1][0].argv
        self.assertTrue(plain[0].endswith('llama-server.exe'))
        rt.unload_model(all_models=True)
        rt.launcher = ('sanitizer.exe', '--tool', 'memcheck')
        rt.load_model('m', context_length=8192, gpu='max', server=self.server())
        wrapped = env.procs[-1][0].argv
        self.assertEqual(wrapped[:3], ['sanitizer.exe', '--tool', 'memcheck'])
        self.assertEqual(wrapped[3:], plain)
        self.assertEqual(LlamaServerRuntime.launcher, ())

    def test_the_key_and_the_value_cache_can_have_different_types(self):
        argv = self.args(kv_type='f16', kv_type_k='q8_0')
        self.assertEqual((argv[argv.index('-ctk') + 1], argv[argv.index('-ctv') + 1]), ('q8_0', 'f16'))
        both = self.args(kv_type='q8_0')
        self.assertEqual((both[both.index('-ctk') + 1], both[both.index('-ctv') + 1]), ('q8_0', 'q8_0'))
        with self.assertRaises(ValueError): self.args(kv_type_k='q5_9')
        with self.assertRaises(ValueError): self.args(kv_type_v='nonsense')

    def test_host_ram_prompt_cache_is_explicit_only_when_asked(self):
        self.assertNotIn('--cache-ram', self.args())
        for value in (0, 2048, -1):
            argv = self.args(cache_ram=value); self.assertEqual(argv[argv.index('--cache-ram') + 1], str(value))
        for bad in (-2, 'x', True, 10 ** 9):
            with self.assertRaises(ValueError, msg=str(bad)): self.args(cache_ram=bad)
        self.assertNotIn('--ctx-checkpoints', self.args())
        argv = self.args(ctx_checkpoints=0); self.assertEqual(argv[argv.index('--ctx-checkpoints') + 1], '0')
        for bad in (-1, 65, 'x', True):
            with self.assertRaises(ValueError, msg=str(bad)): self.args(ctx_checkpoints=bad)

    def test_moe_expert_offload_is_explicit_only_when_asked(self):
        self.assertNotIn('--n-cpu-moe', self.args())
        self.assertNotIn('--n-cpu-moe', self.args(n_cpu_moe=0))
        argv = self.args(n_cpu_moe=30); self.assertEqual(argv[argv.index('--n-cpu-moe') + 1], '30')
        for bad in (-1, 1000, 'x', True, 1.5):
            with self.assertRaises(ValueError, msg=str(bad)): self.args(n_cpu_moe=bad)

    def test_ubatch_sets_physical_and_logical_batch(self):
        self.assertNotIn('-ub', self.args())
        argv = self.args(ubatch=2048); self.assertEqual((argv[argv.index('-b') + 1], argv[argv.index('-ub') + 1]), ('2048', '2048'))
        argv = self.args(ubatch=4096); self.assertEqual((argv[argv.index('-b') + 1], argv[argv.index('-ub') + 1]), ('4096', '4096'))
        argv = self.args(ubatch=256); self.assertEqual((argv[argv.index('-b') + 1], argv[argv.index('-ub') + 1]), ('2048', '256'))
        for bad in (63, 8193, '512', True, 1.5):
            with self.assertRaises(ValueError, msg=str(bad)): self.args(ubatch=bad)

    def test_no_mmap_only_when_asked(self):
        self.assertNotIn('--load-mode', self.args()); self.assertNotIn('--load-mode', self.args(mmap=True))
        argv = self.args(mmap=False); self.assertEqual(argv[argv.index('--load-mode') + 1], 'none')
        with self.assertRaises(ValueError): self.args(mmap='no')

    def test_reasoning_format_only_when_asked_and_valid(self):
        self.assertNotIn('--reasoning-format', self.args())
        argv = self.args(reasoning_format='none'); self.assertEqual(argv[argv.index('--reasoning-format') + 1], 'none')
        for bad in ('raw', '', 1):
            with self.assertRaises(ValueError, msg=str(bad)): self.args(reasoning_format=bad)

    def test_no_jinja_only_when_switched_off(self):
        self.assertNotIn('--no-jinja', self.args()); self.assertNotIn('--no-jinja', self.args(jinja=True))
        self.assertIn('--no-jinja', self.args(jinja=False))
        with self.assertRaises(ValueError): self.args(jinja='no')

    def test_mmproj_only_when_given_and_real(self):
        mm = self.root / 'mm.gguf'; mm.write_bytes(b'x')
        argv = self.args(mmproj=mm); self.assertEqual(argv[argv.index('--mmproj') + 1], str(mm)); self.assertNotIn('--no-mmproj', argv)
        with self.assertRaises(ValueError): self.args(mmproj=self.root / 'none.gguf')

    def test_bad_input_is_refused_before_anything_starts(self):
        for kw in ({'gguf': self.root / 'none.gguf'}, {'gguf': self.root / 'a.txt'}, {'context': 10}, {'context': True}, {'parallel': 0}, {'gpu_layers': -1},
                   {'kv_type': 'q3'}, {'spec_type': 'ngram-simple'}, {'reasoning': 'max'}, {'reasoning_budget': -5}, {'reasoning_budget': 'x'},
                   {'alias': 'a b'}, {'alias': '--evil'[:0] + 'x;rm'}, {'flash_attn': 'x'}):
            if 'gguf' in kw and kw['gguf'].name == 'a.txt': kw['gguf'].write_text('x')
            with self.assertRaises(ValueError, msg=str(kw)): self.args(**kw)


class LifecycleTest(Base):
    def test_start_waits_for_health_verifies_the_window_and_reports_the_instance(self):
        rt = self.runtime()
        out = rt.load_model('qwen', context_length=8192, gpu='max', identifier='qwen', parallel=1, server=self.server(mtp=True))
        self.assertIn('--spec-type', out['command'])
        self.assertEqual(rt.loaded_models(), [{'modelKey': 'qwen', 'identifier': 'qwen', 'contextLength': 8192, 'pid': 4242, 'kv_cache_type': 'q8_0', 'spec_type': 'draft-mtp'}])
        proc, kw = self.env.procs[-1]
        self.assertFalse(kw['shell']); self.assertEqual(Path(kw['cwd']), self.backend)
        self.assertTrue(str(self.backend) in kw['env']['PATH'] and 'vendor' in kw['env']['PATH'])           # CUDA libraries are found without touching the system
        self.assertTrue((self.root / 'state' / 'state.json').exists())

    def test_the_window_the_server_really_applies_wins_over_the_requested_one(self):
        self.env.n_ctx = 4096
        self.assertEqual(self.runtime().load_model('m', context_length=8192, server=self.server()) and self.runtime(self.env).loaded_models(), [])
        rt = self.runtime(Env(n_ctx=4096))
        rt.load_model('m', context_length=8192, server=self.server())
        self.assertEqual(rt.loaded_models()[0]['contextLength'], 4096)           # ModelLoader then sees the mismatch and refuses the start

    def test_a_dense_model_can_ask_for_a_number_of_gpu_layers(self):
        def layers(**server):
            env = Env(); rt = LlamaServerRuntime(self.config(), self.root / 's', popen=env.popen, get_json=env.get_json, sleep=lambda s: None, monotonic=self.clock(), home=self.root)
            argv = rt.load_model('m', context_length=8192, server=self.server(**server))['command']
            return argv[argv.index('-ngl') + 1]
        self.assertEqual((layers(), layers(n_gpu_layers=40), layers(n_gpu_layers=0)), ('99', '40', '0'))

    def test_mtp_needs_the_global_switch_and_the_recipe(self):
        def spec(rt_mtp, recipe_mtp, loader_flag=True):
            env = Env(); rt = LlamaServerRuntime(self.config(mtp=rt_mtp), self.root / 's', popen=env.popen, get_json=env.get_json, sleep=lambda s: None, monotonic=self.clock(), home=self.root)
            argv = rt.load_model('m', context_length=8192, mtp=loader_flag, server=self.server(mtp=recipe_mtp))['command']
            return argv[argv.index('--spec-type') + 1]
        self.assertEqual((spec(True, True), spec(True, False), spec(False, True), spec(False, False)), ('draft-mtp', 'none', 'none', 'none'))
        self.assertEqual(spec(True, True, loader_flag=False), 'draft-mtp')              # the loader's flag belongs to LM Studio's path and is ignored here

    def test_a_server_that_dies_while_starting_is_an_error_with_the_log_tail(self):
        self.env.exit_after = 1; self.env.never_healthy = True
        with self.assertRaises(RuntimeControlError) as ctx: self.runtime().load_model('m', context_length=8192, server=self.server())
        self.assertIn('server_exited_during_start', str(ctx.exception))
        self.assertEqual(self.runtime().loaded_models(), [])

    def test_a_server_that_never_gets_healthy_is_killed_after_the_timeout(self):
        self.env.never_healthy = True
        rt = self.runtime(startup_timeout_s=5)
        with self.assertRaises(RuntimeControlError) as ctx: rt.load_model('m', context_length=8192, server=self.server())
        self.assertIn('server_start_timeout', str(ctx.exception)); self.assertTrue(self.env.procs[-1][0].terminated)
        self.assertEqual(rt.loaded_models(), [])

    def test_a_foreign_server_on_the_port_is_never_taken_over_or_killed(self):
        rt = self.runtime(Env(busy=True))
        with self.assertRaises(RuntimeControlError) as ctx: rt.load_model('m', context_length=8192, server=self.server())
        self.assertIn('port_in_use', str(ctx.exception)); self.assertEqual(rt.loaded_models(), [])

    def test_one_server_at_a_time_and_unload_stops_it(self):
        rt = self.runtime()
        rt.load_model('m', context_length=8192, server=self.server())
        with self.assertRaises(RuntimeControlError): rt.load_model('m2', context_length=8192, server=self.server())
        with self.assertRaises(ValueError): rt.unload_model('other')
        rt.unload_model('m')
        proc = self.env.procs[-1][0]
        self.assertTrue(proc.terminated); self.assertEqual(rt.loaded_models(), []); self.assertFalse((self.root / 'state' / 'state.json').exists())
        self.assertEqual(rt.unload_model('m')['output'], 'nothing to stop')

    def test_a_process_that_will_not_stop_is_killed(self):
        rt = self.runtime()
        rt.load_model('m', context_length=8192, server=self.server())
        self.env.procs[-1][0].wait_raises = True
        rt.unload_model(all_models=True)
        self.assertTrue(self.env.procs[-1][0].killed)

    def test_a_crash_is_noticed_recorded_and_the_next_load_starts_again(self):
        rt = self.runtime()
        rt.load_model('m', context_length=8192, server=self.server())
        self.env.procs[-1][0].returncode = 3221225477                                   # the process died on its own
        self.assertEqual(rt.loaded_models(), [])
        self.assertEqual(rt.status()['last_exit']['code'], 3221225477); self.assertFalse(rt.status()['running'])
        rt.load_model('m', context_length=8192, server=self.server())
        self.assertEqual(len(rt.loaded_models()), 1)

    def test_inputs_and_estimate(self):
        rt = self.runtime()
        self.assertEqual(rt.load_model('m', context_length=8192, estimate_only=True), {'output': ''})
        with self.assertRaises(ValueError): rt.load_model('m', context_length=8192)                         # no server profile
        with self.assertRaises(ValueError): rt.load_model('m', context_length=8192, gpu='half', server=self.server())
        gone = LlamaServerRuntime(self.config(), self.root / 's2', home=self.root / 'nowhere')
        self.assertFalse(gone.available())
        with self.assertRaises(RuntimeControlError): gone.load_model('m', context_length=8192, server=self.server())

    def test_a_leftover_server_is_reported_not_killed(self):
        rt = self.runtime(Env(busy=True))
        (self.root / 'state').mkdir(); (self.root / 'state' / 'state.json').write_text('{}')
        self.assertTrue(rt.leftover())
        self.assertFalse(self.runtime().leftover())


class LoaderIntegrationTest(Base):
    """ModelLoader drives both providers through the same interface, picked by the recipe's provider."""
    def test_the_loader_starts_the_model_on_the_server_the_recipe_names_and_passes_its_profile(self):
        env = Env(); rt = LlamaServerRuntime(self.config(), self.root / 's', popen=env.popen, get_json=env.get_json, sleep=lambda s: None, monotonic=self.clock(), home=self.root)
        lm = FakeController()
        loader = ModelLoader(LoaderConfig({'enabled': True, 'check_estimate': True}), lm, controllers={'llama-cpp-server': rt})
        resolution = {'model': 'qwen', 'provider_ref': 'llama-cpp-server', 'context_window': 8192, 'estimated_resources': {'vram_gb': 6.0},
                      'load_profile': {'gpu_layers': 99, 'server': self.server(mtp=True)}}
        out = loader.ensure(resolution)
        self.assertEqual((out['action'], out['identifier'], out['context_length']), ('loaded', 'qwen', 8192))
        self.assertEqual(lm.calls, [])                                                         # LM Studio was never asked
        self.assertEqual(loader.ensure(resolution)['action'], 'reused')
        self.assertTrue(loader.loaded('qwen') and loader.resident_vram_gb(resolution) == 6.0)
        self.assertEqual(loader.unload(resolution), ['qwen']); self.assertFalse(loader.loaded('qwen'))

    def test_a_window_the_server_did_not_apply_fails_the_start_and_stops_the_server(self):
        env = Env(n_ctx=4096); rt = LlamaServerRuntime(self.config(), self.root / 's', popen=env.popen, get_json=env.get_json, sleep=lambda s: None, monotonic=self.clock(), home=self.root)
        loader = ModelLoader(LoaderConfig({'enabled': True}), FakeController(), controllers={'llama-cpp-server': rt})
        with self.assertRaises(LoadError) as ctx:
            loader.ensure({'model': 'm', 'provider_ref': 'llama-cpp-server', 'context_window': 8192, 'load_profile': {'server': self.server()}})
        self.assertIn('context_not_applied:4096', str(ctx.exception)); self.assertEqual(rt.loaded_models(), [])

    def test_a_failed_start_is_a_provider_failure_with_the_reason(self):
        env = Env(); env.exit_after = 0; env.never_healthy = True
        rt = LlamaServerRuntime(self.config(), self.root / 's', popen=env.popen, get_json=env.get_json, sleep=lambda s: None, monotonic=self.clock(), home=self.root)
        loader = ModelLoader(LoaderConfig({'enabled': True}), FakeController(), controllers={'llama-cpp-server': rt})
        with self.assertRaises(LoadError) as ctx:
            loader.ensure({'model': 'm', 'provider_ref': 'llama-cpp-server', 'context_window': 8192, 'load_profile': {'server': self.server()}})
        self.assertEqual(ctx.exception.code, 'provider_unavailable'); self.assertIn('server_exited_during_start', str(ctx.exception))

    def test_idle_models_of_every_provider_make_room(self):
        env = Env(); rt = LlamaServerRuntime(self.config(), self.root / 's', popen=env.popen, get_json=env.get_json, sleep=lambda s: None, monotonic=self.clock(), home=self.root)
        rt.load_model('qwen', context_length=8192, server=self.server())
        lm = FakeController([inst('org/gemma', 8192, key='org/gemma')])
        loader = ModelLoader(LoaderConfig({'enabled': True, 'evict_idle_models': True}), lm, controllers={'llama-cpp-server': rt})
        self.assertEqual(sorted(loader.evict_idle({'qwen'})), ['org/gemma'])                  # the one in use stays
        self.assertEqual(len(rt.loaded_models()), 1)
        self.assertEqual(sorted(loader.evict_idle(set())), ['qwen']); self.assertEqual(rt.loaded_models(), [])

    def test_without_a_provider_match_the_default_controller_is_used(self):
        lm = FakeController()
        loader = ModelLoader(LoaderConfig({'enabled': True}), lm, controllers={'llama-cpp-server': object()})
        loader.ensure({'model': 'm', 'provider_ref': 'lm-studio', 'context_window': 8192, 'load_profile': {'gpu_layers': 99}})
        self.assertEqual(lm.loaded[0]['modelKey'], 'm')


class RecipeTest(unittest.TestCase):
    def test_server_profile_is_validated_and_reaches_the_resolution(self):
        good = {'context': {'recommended': 8192, 'maximum': 8192}, 'gpu_layers': 99, 'server': {'gguf': 'x.gguf', 'kv_cache_type': 'q8_0', 'mtp': True, 'reasoning_budget': 512}}
        config = RoutingConfig(routing_raw([recipe('c.s', ['coder'], 'llama-cpp-server', 'f', 'w', model='m', profile=good)]))
        self.assertEqual(config.recipes[0]['profile']['server']['mtp'], True)
        for bad in ({'gguf': ''}, {}, {'gguf': 'x', 'extra_args': ['--evil']}, {'gguf': 'x', 'kv_cache_type': 'q3'}, {'gguf': 'x', 'mtp': 'yes'}, {'gguf': 'x', 'reasoning_budget': 'a'}, {'gguf': 'x', 'cache_ram': 'big'}, {'gguf': 'x', 'cache_ram': -7}, {'gguf': 'x', 'ctx_checkpoints': 99}, {'gguf': 'x', 'n_cpu_moe': -1}, {'gguf': 'x', 'n_gpu_layers': -1}, {'gguf': 'x', 'n_gpu_layers': True}, {'gguf': 'x', 'n_gpu_layers': '40'}, {'gguf': 'x', 'n_cpu_moe': True}, {'gguf': 'x', 'ubatch': 32}, {'gguf': 'x', 'mmap': 'off'}, {'gguf': 'x', 'flash_attn': 'maybe'}, {'gguf': 'x', 'ubatch': '2048'},
                    {'gguf': 'x', 'reasoning': 'max'}, 'x'):
            with self.assertRaises(ValueError, msg=str(bad)):
                RoutingConfig(routing_raw([recipe('c.s', ['coder'], 'p', 'f', 'w', profile=dict(good, server=bad))]))


if __name__ == '__main__':
    unittest.main()
