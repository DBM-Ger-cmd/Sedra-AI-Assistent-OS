from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.models.tuning import digest
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH = sorted((Path(__file__).resolve().parents[2] / 'architecture').glob('GUPPI_Architecture_v*'))[-1]


class TuningCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.rt = GuppiRuntime(self.root, ARCH)
        self.manager = self.rt.model_runtime
        self.manager.catalog.add_allowed_root(self.root)
        self.model = self.root / 'test-Q4_K_M.gguf'
        self.model.write_bytes(b'fake model for unit tests only')
        self.rec = self.manager.catalog.register(self.model)
        self.axes = {'context': [512, 1024], 'batch_size': [32, 64],
                     'gpu_layers': [0], 'kv_precision': ['fp16']}
        self.tuning = self.manager.tuning

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, **kw):
        return self.tuning.plan(model_id=self.rec['id'], profile_id='safe-cpu-default', axes=self.axes, **kw)

    def fake_benchmark(self, **kw):
        profile = kw['profile_override']
        number = profile['context']['recommended'] + profile['batch_size']
        bm = {'benchmark_id': 'BM-' + str(number), 'created_at': 'unit-test',
              'provider': 'llama-cpp-server', 'managed_start': True,
              'profile_pass': {'effective_profile': profile},
              'hardware': {'fingerprint': self.manager.hardware.fingerprint()},
              'model': self.rec, 'qualification': {'status': 'PASS'},
              'metrics': {'median_tokens_per_second': number},
              'samples': [{'tokens_estimated': False}]}
        self.manager.benchmark.store.save(bm)
        return bm

    def test_plan_deterministic_bounded_and_pure(self):
        first = self.plan(max_candidates=2)
        self.assertEqual(first, self.plan(max_candidates=2))
        self.assertEqual(len(first['candidates']), 2)
        self.assertTrue(first['truncated'])
        self.assertFalse(self.tuning.root.exists())
        self.assertEqual(self.manager.profile_store.custom(), {})
        for c in first['candidates']:
            self.assertLessEqual(c['profile']['microbatch_size'], c['profile']['batch_size'])

    def test_invalid_axes_and_limits(self):
        for field, value in [('repeats', 100), ('max_candidates', 25), ('port', 80), ('warmups', -1), ('max_tokens', True)]:
            with self.subTest(field=field), self.assertRaises(ValueError): self.plan(**{field: value})
        for axes in [dict(self.axes, context=[999999]), dict(self.axes, kv_precision=['unsafe']),
                     dict(self.axes, gpu_layers=[-1]), dict(self.axes, unknown=[1])]:
            with self.subTest(axes=axes), self.assertRaises(ValueError):
                self.tuning.plan(model_id=self.rec['id'], axes=axes)

    def test_tampered_plan_and_changed_model_rejected(self):
        plan = self.plan()
        bad = deepcopy(plan); bad['candidates'][0]['profile']['batch_size'] = 1024
        with self.assertRaises(ValueError): self.tuning.validate(bad)
        self.model.write_bytes(b'same-length-model-content-xxxx')
        with self.assertRaises(ValueError): self.tuning.validate(plan)

    def test_gate_exact_digest_and_single_use(self):
        plan = self.plan(max_candidates=1)
        args = {'plan': plan}; mid = 'M-TUNING'
        pending = self.rt.tools.execute('model-runtime', mid, 'tuning_run', args)
        self.assertEqual(pending['status'], 'captain_required')
        token = self.rt.guard.approve(pending['gate'])
        other = self.plan(max_candidates=2)
        denied = self.rt.tools.execute('model-runtime', mid, 'tuning_run', {'plan': other}, token)
        self.assertEqual(denied['status'], 'captain_required')
        with patch.object(self.manager.benchmark, 'benchmark_managed_llamacpp', side_effect=self.fake_benchmark), \
             patch.object(self.manager.controller('llama-cpp-server'), 'status', return_value={'managed_running': False}):
            done = self.rt.tools.execute('model-runtime', mid, 'tuning_run', args, token)
        self.assertEqual(done['tuning']['status'], 'COMPLETED')
        replay = self.rt.tools.execute('model-runtime', mid, 'tuning_run', args, token)
        self.assertEqual(replay['status'], 'captain_required')
        self.assertEqual(self.manager.profile_store.known_good_records(), {})

    def test_rank_real_records_and_keep_profiles_unchanged(self):
        plan = self.plan()
        with patch.object(self.manager.benchmark, 'benchmark_managed_llamacpp', side_effect=self.fake_benchmark), \
             patch.object(self.manager.controller('llama-cpp-server'), 'status', return_value={'managed_running': False}):
            result = self.tuning.run(plan)
        self.assertEqual(result['recommended_benchmark_id'], 'BM-1088')
        self.assertEqual(len(result['results']), 4)
        self.assertEqual(self.tuning.history()[0]['run_id'], result['run_id'])
        self.assertEqual(self.manager.profile_store.custom(), {})

    def test_failure_limit_and_partial_history(self):
        with patch.object(self.manager.benchmark, 'benchmark_managed_llamacpp', side_effect=RuntimeError('startup failed')) as runner, \
             patch.object(self.manager.controller('llama-cpp-server'), 'status', return_value={'managed_running': False}):
            result = self.tuning.run(self.plan(max_failures=1))
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(result['status'], 'FAILURE_LIMIT')
        self.assertIsNone(result['recommended_benchmark_id'])
        self.assertEqual(self.tuning.history()[0]['results'][0]['status'], 'ERROR')

    def test_refuse_running_runtime(self):
        with patch.object(self.manager.controller('llama-cpp-server'), 'status', return_value={'managed_running': True}), self.assertRaises(RuntimeError):
            self.tuning.run(self.plan())

    def test_estimates_not_ranked(self):
        def estimated(**kw):
            bm = self.fake_benchmark(**kw); bm['samples'][0]['tokens_estimated'] = True
            self.manager.benchmark.store.save(bm); return bm
        with patch.object(self.manager.benchmark, 'benchmark_managed_llamacpp', side_effect=estimated), \
             patch.object(self.manager.controller('llama-cpp-server'), 'status', return_value={'managed_running': False}):
            result = self.tuning.run(self.plan())
        self.assertIsNone(result['recommended_benchmark_id'])

    def test_budget_prevents_next_candidate(self):
        with patch.object(self.manager.benchmark, 'benchmark_managed_llamacpp') as runner, \
             patch.object(self.manager.controller('llama-cpp-server'), 'status', return_value={'managed_running': False}), \
             patch('guppi_runtime.models.tuning.time.monotonic', side_effect=[0, 31]):
            result = self.tuning.run(self.plan(budget_seconds=30))
        runner.assert_not_called()
        self.assertEqual(result['status'], 'BUDGET_EXHAUSTED')

    def test_interrupt_is_persisted(self):
        with patch.object(self.manager.benchmark, 'benchmark_managed_llamacpp', side_effect=KeyboardInterrupt), \
             patch.object(self.manager.controller('llama-cpp-server'), 'status', return_value={'managed_running': False}), self.assertRaises(KeyboardInterrupt):
            self.tuning.run(self.plan())
        self.assertEqual(self.tuning.history()[0]['status'], 'INTERRUPTED')

    def test_policy_change_requires_new_plan(self):
        plan = self.plan()
        self.manager.benchmark.policy["request_timeout_seconds"] = 999
        with self.assertRaises(ValueError): self.tuning.validate(plan)

    def test_managed_failure_stops_runtime(self):
        ctl = self.manager.controller('llama-cpp-server')
        with patch.object(ctl, 'status', return_value={'managed_running': False}), \
             patch.object(ctl, 'start_server', return_value={'pid': None, 'endpoint': 'http://127.0.0.1:18080'}), \
             patch.object(ctl, 'stop_server') as stop, \
             patch.object(self.manager.benchmark, '_adapter'), \
             patch.object(self.manager.benchmark, '_wait_ready', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                self.manager.benchmark.benchmark_managed_llamacpp(model_id=self.rec['id'], profile_id='safe-cpu-default',
                                                                  profile_override=self.plan()['candidates'][0]['profile'])
        stop.assert_called_once()


if __name__ == '__main__': unittest.main()
