"""Phase 8a: the resolved context window is the one the provider really applies."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.core.audit import AuditLog
from guppi_runtime.selfdev.development_contracts import development_contract
from guppi_runtime.jobs.job_supervisor import JobSupervisor, SupervisorConfig, SupervisorJobStore
from guppi_runtime.models.model_loader import LoadError, LoaderConfig, ModelLoader, gpu_argument, parse_estimate_gib
from guppi_runtime.models.runtime_control import LMStudioRuntimeController, RuntimeControlError
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]
KEY = 'org/model-a'
ESTIMATE_TEXT = 'Model: x\nContext Length: 8.192\nGPU Offload: 100%\nEstimated GPU Memory:   8.67 GiB\nEstimated Total Memory: 8.67 GiB\n'


class FakeController:
    """Behaves like LM Studio as measured: a second load of the same key adds `<key>:2` instead of replacing."""
    def __init__(self, loaded=None, estimate=ESTIMATE_TEXT, fail_load=False, ignore_context=None):
        self.loaded = list(loaded or [])
        self.estimate = estimate; self.fail_load = fail_load; self.ignore_context = ignore_context
        self.calls = []

    def loaded_models(self):
        return [dict(i) for i in self.loaded]

    def unload_model(self, key=None, *, all_models=False):
        self.calls.append(('unload', key))
        self.loaded = [i for i in self.loaded if i['identifier'] != key]
        return {}

    def load_model(self, key, *, context_length=None, gpu=None, identifier=None, estimate_only=False, yes=False, parallel=None, mtp=None, server=None):
        self.calls.append(('estimate' if estimate_only else 'load', key, context_length, gpu, identifier, yes, parallel, mtp))
        if estimate_only:
            return {'output': self.estimate}
        if self.fail_load: raise RuntimeControlError('command_failed:1:boom')
        ident = identifier or key
        if any(i['identifier'] == ident for i in self.loaded):
            n = 2
            while any(i['identifier'] == f'{ident}:{n}' for i in self.loaded): n += 1
            ident = f'{ident}:{n}'
        self.loaded.append({'modelKey': key, 'identifier': ident, 'contextLength': self.ignore_context or context_length})
        return {'output': 'ok'}


def inst(identifier, ctx, key=KEY): return {'modelKey': key, 'identifier': identifier, 'contextLength': ctx}
def resolution(ctx=8192, vram=8.26, gpu=99): return {'model': KEY, 'context_window': ctx, 'estimated_resources': {'vram_gb': vram}, 'load_profile': {'gpu_layers': gpu}}
def loader(controller, **cfg): return ModelLoader(LoaderConfig({'enabled': True, 'check_estimate': True, **cfg}), controller)


class ParsingTest(unittest.TestCase):
    def test_estimate_units_and_garbage(self):
        self.assertAlmostEqual(parse_estimate_gib(ESTIMATE_TEXT), 8.67)
        self.assertAlmostEqual(parse_estimate_gib('Estimated GPU Memory: 2048 MiB'), 2.0)
        self.assertAlmostEqual(parse_estimate_gib('Estimated GPU Memory: 1,5 GB'), 1.5)
        for text in (None, '', 'no number here', 'Estimated GPU Memory: lots'): self.assertIsNone(parse_estimate_gib(text))

    def test_gpu_argument_never_guesses(self):
        self.assertEqual([gpu_argument(x) for x in (99, 'max', 'all', 0, 'off')], ['max', 'max', 'max', 'off', 'off'])
        self.assertIsNone(gpu_argument(None)); self.assertIsNone(gpu_argument(20)); self.assertIsNone(gpu_argument('half'))

    def test_config_is_strict_and_off_by_default(self):
        self.assertFalse(LoaderConfig({}).enabled); self.assertFalse(LoaderConfig({}).check_estimate); self.assertEqual(LoaderConfig({}).parallel, 1); self.assertFalse(LoaderConfig({}).mtp)
        for bad in ({'enabled': 'yes'}, {'on_context_mismatch': 'maybe'}, {'check_estimate': 1}, {'mtp': 'no'}, {'parallel': 0}, {'parallel': True}, {'estimate_slack_gb': -1}, {'estimate_slack_gb': True}, 'x'):
            with self.assertRaises(ValueError): LoaderConfig(bad)
        self.assertFalse(LoaderConfig.load(RUNTIME / 'config' / 'model_loader.yaml').enabled)


class ControllerTest(unittest.TestCase):
    def test_yes_flag_only_when_asked(self):
        seen = []
        class Runner:
            def run(self, argv, *, timeout=30): seen.append(argv); return ''
        ctl = LMStudioRuntimeController('lms', runner=Runner())
        ctl.load_model('m', context_length=4096, gpu='max', identifier='m')
        ctl.load_model('m', context_length=4096, yes=True, parallel=1)
        self.assertNotIn('--yes', seen[0]); self.assertIn('--yes', seen[1])
        self.assertNotIn('--parallel', seen[0]); self.assertEqual(seen[1][seen[1].index('--parallel') + 1], '1')
        ctl.load_model('m', mtp=False); ctl.load_model('m', mtp=True)
        self.assertIn('--no-speculative-draft-mtp', seen[2]); self.assertIn('--speculative-draft-mtp', seen[3]); self.assertNotIn('--speculative-draft-mtp', seen[2])
        self.assertFalse(any('mtp' in a for a in seen[0]))                      # not given: not sent


class EnsureTest(unittest.TestCase):
    def test_loads_with_context_gpu_identifier_and_yes_then_verifies(self):
        ctl = FakeController(); out = loader(ctl).ensure(resolution())
        self.assertEqual(out, {'identifier': KEY, 'context_length': 8192, 'action': 'loaded', 'estimate_gib': 8.67})
        self.assertIn(('load', KEY, 8192, 'max', KEY, True, 1, False), ctl.calls)       # MTP explicitly off
        self.assertEqual(ctl.loaded, [inst(KEY, 8192)])

    def test_exact_instance_is_reused_without_any_command(self):
        ctl = FakeController([inst(KEY, 8192)]); out = loader(ctl).ensure(resolution())
        self.assertEqual(out['action'], 'reused'); self.assertEqual(ctl.calls, [])

    def test_wrong_context_is_unloaded_first_so_no_second_instance_appears(self):
        ctl = FakeController([inst(KEY, 4096)]); out = loader(ctl).ensure(resolution())
        self.assertEqual(out['action'], 'reloaded')
        self.assertEqual([c[0] for c in ctl.calls], ['estimate', 'unload', 'load'])
        self.assertEqual(ctl.loaded, [inst(KEY, 8192)])                 # one instance, named after the key

    def test_stale_twin_is_removed_even_when_the_twin_has_the_right_context(self):
        ctl = FakeController([inst(KEY, 4096), inst(KEY + ':2', 8192)]); out = loader(ctl).ensure(resolution())
        self.assertEqual(ctl.loaded, [inst(KEY, 8192)]); self.assertEqual(out['identifier'], KEY)

    def test_refuse_policy_leaves_everything_alone(self):
        ctl = FakeController([inst(KEY, 4096)])
        with self.assertRaises(LoadError) as ctx: loader(ctl, on_context_mismatch='refuse').ensure(resolution())
        self.assertIn('loaded_with_other_context', str(ctx.exception)); self.assertEqual(ctl.calls, [])

    def test_other_models_are_never_touched(self):
        other = inst('org/other', 2048, key='org/other')
        ctl = FakeController([other, inst(KEY, 4096)]); loader(ctl).ensure(resolution())
        self.assertIn(other, ctl.loaded); self.assertNotIn(('unload', 'org/other'), ctl.calls)

    def test_similar_key_is_not_confused_with_the_model(self):
        ctl = FakeController([inst('org/model-a2', 8192, key='org/model-a2')]); out = loader(ctl).ensure(resolution())
        self.assertEqual(out['action'], 'loaded')

    def test_estimate_above_reservation_refuses_before_anything_is_loaded(self):
        ctl = FakeController()
        with self.assertRaises(LoadError) as ctx: loader(ctl).ensure(resolution(vram=6.0))      # LM Studio says 8.67
        self.assertEqual(ctx.exception.code, 'hardware_pressure')
        self.assertEqual([c[0] for c in ctl.calls], ['estimate'])

    def test_estimate_within_slack_is_fine_and_missing_estimate_is_no_veto(self):
        loader(FakeController()).ensure(resolution(vram=8.3))                                  # 8.67 <= 8.3 + 0.5
        out = loader(FakeController(estimate='garbage')).ensure(resolution(vram=1.0))
        self.assertIsNone(out['estimate_gib'])
        out = loader(FakeController(), check_estimate=False).ensure(resolution(vram=1.0))
        self.assertIsNone(out['estimate_gib'])

    def test_failed_load_is_a_provider_failure(self):
        with self.assertRaises(LoadError) as ctx: loader(FakeController(fail_load=True)).ensure(resolution())
        self.assertEqual(ctx.exception.code, 'provider_unavailable')

    def test_context_not_applied_is_detected_and_cleaned_up(self):
        ctl = FakeController(ignore_context=4096)
        with self.assertRaises(LoadError) as ctx: loader(ctl).ensure(resolution())
        self.assertIn('context_not_applied:4096', str(ctx.exception)); self.assertEqual(ctl.loaded, [])

    def test_disabled_and_bad_resolutions(self):
        with self.assertRaises(LoadError): ModelLoader(LoaderConfig({}), FakeController()).ensure(resolution())
        for bad in ({'model': None, 'context_window': 8192}, {'model': KEY, 'context_window': 0}, {'model': KEY, 'context_window': True}, {'model': KEY}):
            with self.assertRaises(LoadError): loader(FakeController()).ensure(bad)

    def test_unlisting_failure_is_a_provider_failure(self):
        class Broken(FakeController):
            def loaded_models(self): raise RuntimeControlError('lms_cli_not_found')
        with self.assertRaises(LoadError): loader(Broken()).ensure(resolution())

    def test_unload_frees_only_this_model(self):
        other = inst('org/other', 2048, key='org/other')
        ctl = FakeController([other, inst(KEY, 8192)])
        self.assertEqual(loader(ctl).unload({'model': KEY}), [KEY]); self.assertEqual(ctl.loaded, [other])


class ClearStaleTest(unittest.TestCase):
    def test_stale_and_twin_instances_of_this_model_go_other_models_stay(self):
        other = inst('org/other', 2048, key='org/other')
        ctl = FakeController([other, inst(KEY, 4096), inst(KEY + ':2', 8192)])
        self.assertEqual(loader(ctl).clear_stale(resolution()), [KEY, KEY + ':2']); self.assertEqual(ctl.loaded, [other])

    def test_nothing_to_do_when_reusable_or_not_loaded_or_disabled(self):
        for loaded in ([], [inst(KEY, 8192)]):
            ctl = FakeController(loaded); self.assertEqual(loader(ctl).clear_stale(resolution()), []); self.assertEqual(ctl.calls, [])
        ctl = FakeController([inst(KEY, 4096)])
        self.assertEqual(ModelLoader(LoaderConfig({}), ctl).clear_stale(resolution()), []); self.assertEqual(ctl.calls, [])

    def test_refuse_policy_raises_before_anything_is_touched(self):
        ctl = FakeController([inst(KEY, 4096)])
        with self.assertRaises(LoadError): loader(ctl, on_context_mismatch='refuse').clear_stale(resolution())
        self.assertEqual(ctl.calls, [])


class ResidentTest(unittest.TestCase):
    def test_advisory_and_credit_only_for_what_would_really_be_reused(self):
        self.assertTrue(loader(FakeController([inst(KEY, 4096)])).loaded(KEY)); self.assertFalse(loader(FakeController()).loaded(KEY))
        self.assertEqual(loader(FakeController([inst(KEY, 8192)])).resident_vram_gb(resolution()), 8.26)
        for ctl in (FakeController(), FakeController([inst(KEY, 4096)]), FakeController([inst(KEY, 8192), inst(KEY + ':2', 8192)])):
            self.assertEqual(loader(ctl).resident_vram_gb(resolution()), 0.0)
        self.assertEqual(ModelLoader(LoaderConfig({}), FakeController([inst(KEY, 8192)])).resident_vram_gb(resolution()), 0.0)


class SupervisorIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.audit = AuditLog(root / 'audit.jsonl')
        config = SupervisorConfig.load(RUNTIME / 'config' / 'job_supervisor.yaml'); config.enabled = True
        self.released = []
        class Scheduler:
            enabled = True
            def __init__(s): s.reserved = []; s.credit = []
            def reserve(s, job_id, attempt_id, estimate, exclusive=False, resident_vram_gb=0.0):
                s.credit.append(resident_vram_gb); s.reserved.append(job_id); return {'status': 'GRANTED', 'reservation': {'reservation_id': 'RSV-T'}}
            def release_job(s, job_id): s.reserved.remove(job_id); self_released.append(job_id)
        self_released = self.released
        self.scheduler = Scheduler()
        self.sup = JobSupervisor(SupervisorJobStore(root / 'jobs', self.audit), config, audit=self.audit, scheduler=self.scheduler)
        self.sup.resolver = lambda role, req, exclude, independent_of: dict(resolution(), role=role, provider_ref='lm-studio', capability_id='c1',
                                                                          independence_key='k', context_window=8192, estimated_resources={'vram_gb': 8.26})

    def start(self, controller, **cfg):
        self.sup.loader = loader(controller, **cfg)
        contract = development_contract(objective='x', classification='E1', acceptance_criteria=[{'type': 'capability_smoke_test', 'id': 's'}], verification_plan=[{'type': 'deterministic_tests'}])
        job = self.sup.create_job(contract, requested_role='coder', permission_level=1)
        self.sup.enqueue(job['job_id']); self.sup.claim('w1', ['coder'])
        return job['job_id'], self.sup.confirm_start(job['job_id'], 'w1')

    def test_started_attempt_records_what_the_worker_must_call(self):
        _, res = self.start(FakeController())
        self.assertEqual(res['status'], 'running')
        attempt = res['job']['attempt_log'][-1]
        self.assertEqual((attempt['model'], attempt['model_identifier'], attempt['loaded_context']), (KEY, KEY, 8192))
        self.assertEqual(self.released, [])

    def test_failed_load_fails_the_start_without_blaming_the_provider_and_releases_the_room(self):
        job_id, res = self.start(FakeController(fail_load=True))
        self.assertEqual(res['status'], 'resolution_failed'); self.assertEqual(res['code'], 'provider_unavailable')
        attempt = res['job']['attempt_log'][-1]
        self.assertIsNone(attempt['provider_ref']); self.assertEqual(attempt['reservation_id'], None)
        self.assertEqual(self.released, [job_id]); self.assertEqual(self.scheduler.reserved, [])

    def test_stale_instance_is_gone_before_the_room_is_reserved(self):
        ctl = FakeController([inst(KEY, 4096)]); seen = []
        original = self.scheduler.reserve
        self.scheduler.reserve = lambda *a, **k: (seen.append(list(ctl.loaded)), original(*a, **k))[1]
        _, res = self.start(ctl)
        self.assertEqual(seen, [[]]); self.assertEqual(res['status'], 'running'); self.assertEqual(ctl.loaded, [inst(KEY, 8192)])

    def test_a_model_that_is_already_loaded_is_not_counted_twice(self):
        _, res = self.start(FakeController([inst(KEY, 8192)]))
        self.assertEqual(res['status'], 'running'); self.assertEqual(self.scheduler.credit, [8.26])

    def test_refused_mismatch_fails_before_any_reservation(self):
        ctl = FakeController([inst(KEY, 4096)])
        job_id, res = self.start(ctl, on_context_mismatch='refuse')
        self.assertEqual(res['code'], 'provider_unavailable'); self.assertEqual(self.scheduler.reserved, []); self.assertEqual(ctl.calls, [])

    def test_estimate_refusal_is_hardware_pressure(self):
        self.sup.resolver = lambda role, req, exclude, independent_of: dict(resolution(vram=6.0), role=role, provider_ref='lm-studio', capability_id='c1',
                                                                          independence_key='k', context_window=8192, estimated_resources={'vram_gb': 6.0})
        _, res = self.start(FakeController())
        self.assertEqual(res['code'], 'hardware_pressure')

    def test_no_loader_means_nothing_changes(self):
        self.sup.loader = None
        contract = development_contract(objective='x', classification='E1', acceptance_criteria=[{'type': 'capability_smoke_test', 'id': 's'}], verification_plan=[{'type': 'deterministic_tests'}])
        job = self.sup.create_job(contract, requested_role='coder', permission_level=1)
        self.sup.enqueue(job['job_id']); self.sup.claim('w1', ['coder'])
        res = self.sup.confirm_start(job['job_id'], 'w1')
        self.assertEqual(res['status'], 'running'); self.assertIsNone(res['job']['attempt_log'][-1]['loaded_context'])


if __name__ == '__main__':
    unittest.main()
