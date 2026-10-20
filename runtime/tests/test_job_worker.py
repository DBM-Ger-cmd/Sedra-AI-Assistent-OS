"""Phase 8b: the worker loop, its heartbeat, failure reporting and the model handler."""
import tempfile
import threading
import time
import unittest
from pathlib import Path

from guppi_runtime.core.audit import AuditLog
from guppi_runtime.selfdev.development_contracts import development_contract
from guppi_runtime.jobs.job_supervisor import JobError, JobSupervisor, SupervisorConfig, SupervisorJobStore
from guppi_runtime.jobs.job_worker import HandlerError, Worker, degenerate_reason, model_text_handler
from guppi_runtime.models.model_loader import LoaderConfig, ModelLoader
from test_model_loader import FakeController, KEY, inst
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.audit = AuditLog(Path(self.tmp.name) / 'audit.jsonl')
        config = SupervisorConfig.load(RUNTIME / 'config' / 'job_supervisor.yaml'); config.enabled = True
        self.sup = JobSupervisor(SupervisorJobStore(Path(self.tmp.name) / 'jobs', self.audit), config, audit=self.audit)

    def job(self, role='reviewer', **kw):
        contract = development_contract(objective='probe', classification='E1', acceptance_criteria=[{'type': 'capability_smoke_test', 'id': 's'}],
                                        verification_plan=[{'type': 'deterministic_tests'}])
        job = self.sup.create_job(contract, requested_role=role, permission_level=1, **kw)
        self.sup.enqueue(job['job_id']); return job['job_id']

    def worker(self, handler, roles=('reviewer',), **kw):
        kw.setdefault('heartbeat_every', 0.05); kw.setdefault('idle_sleep_s', 0.01)
        return Worker(self.sup, 'w1', roles, handler, **kw)

    def state(self, job_id): return self.sup.store.load(job_id)


class RunOnceTest(Base):
    def test_idle_when_nothing_is_queued(self):
        self.assertEqual(self.worker(lambda *a: None).run_once()['status'], 'idle')

    def test_success_steps_the_job_forward_and_never_to_passed(self):
        job_id = self.job(); seen = {}
        def handler(job, attempt, ctx): seen.update(role=job['requested_role'], attempt=attempt['attempt_id']); return {'advance': ['TESTING', 'VERIFYING']}
        out = self.worker(handler).run_once()
        self.assertEqual((out['status'], out['job_id']), ('handled', job_id))
        job = self.state(job_id)
        self.assertEqual(job['state'], 'VERIFYING'); self.assertEqual(seen['attempt'], out['attempt_id'])
        # Never PASSED here (that needs the evidence gate), but no longer held either: parked, so the worker and the room are free.
        self.assertIsNone(job['worker']); self.assertTrue(job['supervisor_flags']['awaiting_verification'])
        self.assertEqual(out['released'], 'parked_for_verification')

    def test_a_finished_job_is_not_mistaken_for_a_lost_worker_later(self):
        # Before 2026-10-02: held after success, then reaped -> a read-only job ran again, a mutating one ended DEAD.
        from datetime import datetime, timedelta, timezone
        wall = [datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)]; mono = [1000.0]
        self.sup._now = lambda: wall[0]; self.sup._mono = lambda: mono[0]
        for role in ('reviewer', 'coder'):
            job_id = self.job(role=role)
            out = self.worker(lambda *a: {'advance': ['TESTING', 'VERIFYING']}, roles=(role,)).run_once()
            self.assertEqual(out['status'], 'handled')
            for _ in range(4): wall[0] += timedelta(seconds=120); mono[0] += 120; self.sup.reap()
            job = self.state(job_id)
            self.assertEqual((job['state'], job['attempt_log'][-1]['outcome']), ('VERIFYING', 'SUCCEEDED'), role)

    def test_the_next_job_is_not_blocked_by_a_finished_one(self):
        self.job(); second = self.job()
        w = self.worker(lambda *a: {'advance': ['TESTING', 'VERIFYING']})
        w.run_once()
        self.assertEqual(w.run_once()['job_id'], second)

    def test_unknown_advance_state_is_refused(self):
        self.job()
        with self.assertRaises(JobError): self.worker(lambda *a: {'advance': ['READY_FOR_ACCEPTANCE']}).run_once()

    def test_heartbeat_runs_while_a_slow_handler_works(self):
        job_id = self.job()
        # The handler works until it has seen the beats (bounded), instead of a fixed 0.4 s window: under load one beat can be
        # scheduled 300-500 ms late (measured 2026-10-03, no I/O step was slow), and a fixed window then fails although nothing is wrong.
        def slow(job, attempt, ctx):
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    if self.state(job_id)['heartbeat_seq'] >= 4: return
                except (OSError, ValueError): pass        # read raced the atomic replace; look again
                time.sleep(0.02)
        self.worker(slow).run_once()
        self.assertGreaterEqual(self.state(job_id)['heartbeat_seq'], 4)

    def test_exception_is_reported_and_the_job_is_queued_again_with_a_delay(self):
        job_id = self.job()
        def boom(job, attempt, ctx): raise ConnectionError('provider reset')
        out = self.worker(boom).run_once()
        self.assertEqual(out['status'], 'failed')
        job = self.state(job_id)
        self.assertEqual((job['state'], job['attempt_log'][-1]['outcome']), ('QUEUED', 'FAILED'))
        self.assertIsNone(job['worker'])

    def test_handler_error_code_is_the_reason(self):
        job_id = self.job()
        def refuse(job, attempt, ctx): raise HandlerError('policy_denied', 'nope')
        self.worker(refuse).run_once()
        job = self.state(job_id)
        self.assertEqual(job['attempt_log'][-1]['failure_class'], 'policy_denied')
        self.assertNotEqual(job['state'], 'QUEUED')                   # never retried, escalated

    def test_a_mutating_attempt_that_raised_after_changing_something_is_never_replayed(self):
        job_id = self.job(role='coder')
        def half(job, attempt, ctx): ctx.mark_mutated(); raise RuntimeError('died halfway')
        self.worker(half, roles=('coder',)).run_once()
        job = self.state(job_id)
        self.assertEqual(job['state'], 'DEAD')

    def test_cancel_during_the_handler_is_acknowledged(self):
        job_id = self.job()
        def handler(job, attempt, ctx): self.sup.cancel(job_id, requested_by='captain', reason='stop')
        out = self.worker(handler).run_once()
        self.assertEqual(out['status'], 'cancelled'); self.assertEqual(self.state(job_id)['state'], 'CANCELLED')

    def test_a_handler_that_ends_the_attempt_itself_is_not_a_lost_lease(self):
        job_id = self.job()
        def handler(job, attempt, ctx):
            with self.sup.store.mutate(job_id) as j: j['worker'] = None            # parked or completed by the handler itself
            time.sleep(0.2)
            return {'job_finished': True}
        out = self.worker(handler).run_once()
        self.assertEqual((out['status'], out['result']), ('handled', {'job_finished': True}))

    def test_a_lost_lease_ends_quietly(self):
        job_id = self.job()
        def handler(job, attempt, ctx):
            with self.sup.store.mutate(job_id) as j: j['worker'] = None          # as if the reaper had taken it away
            time.sleep(0.2)
        out = self.worker(handler).run_once()
        self.assertEqual(out['status'], 'lease_lost')

    def test_refused_start_does_not_call_the_handler(self):
        job_id = self.job()
        self.sup.resolver = lambda role, req, exclude, independent_of: (_ for _ in ()).throw(type('E', (Exception,), {'code': 'no_capability'})())
        called = []
        out = self.worker(lambda *a: called.append(1)).run_once()
        self.assertEqual(out['status'], 'resolution_failed'); self.assertEqual(called, [])


class LoopTest(Base):
    def test_loop_runs_jobs_in_order_then_idles_until_stopped(self):
        a, b = self.job(), self.job()
        order = []
        def handler(job, attempt, ctx): order.append(job['job_id']); self.sup.fail(job['job_id'], 'w1', reason_code='NO_HANDLER'); return None
        worker = self.worker(handler)
        t = threading.Thread(target=lambda: setattr(self, 'seen', worker.run_forever()))
        t.start(); time.sleep(0.5); worker.stop(); t.join(timeout=5)
        self.assertFalse(t.is_alive()); self.assertEqual(set(order), {a, b}); self.assertIn('idle', self.seen)

    def test_max_iterations_and_reaper_cadence(self):
        reaps = []
        original = self.sup.reap; self.sup.reap = lambda: (reaps.append(1), original())[1]
        clock = [100.0]
        worker = self.worker(lambda *a: None, reap_every=30, monotonic=lambda: clock[0], sleep=lambda s: None)
        self.assertEqual(worker.run_forever(max_iterations=3), ['idle', 'idle', 'idle']); self.assertEqual(len(reaps), 1)
        clock[0] += 31; worker.run_once(); self.assertEqual(len(reaps), 2)


class ModelHandlerTest(Base):
    def run_handler(self, reply, **kw):
        job_id = self.job(); calls = []
        def infer(jid, request): calls.append(request); return reply
        handler = model_text_handler(infer, lambda job: [{'role': 'user', 'content': job['contract']['objective']}], **kw)
        self.sup.resolver = lambda role, req, exclude, independent_of: {'role': role, 'provider_ref': 'lm-studio', 'capability_id': 'c', 'independence_key': 'k',
                                                                      'context_window': 8192, 'estimated_resources': {}, 'model': KEY}
        out = self.worker(handler).run_once()
        return out, self.state(job_id), calls

    def test_text_comes_back_and_the_request_names_the_prepared_instance(self):
        reply = {'status': 'completed', 'model_result': {'content': 'ok', 'usage': {'input_tokens': 3, 'output_tokens': 5}, 'model': KEY}}
        out, job, calls = self.run_handler(reply)
        self.assertEqual(out['result']['text'], 'ok'); self.assertEqual(job['state'], 'VERIFYING')
        self.assertEqual((calls[0]['model'], calls[0]['provider'], calls[0]['role']), (KEY, 'lm-studio', 'reviewer'))
        self.assertEqual(calls[0]['messages'][0]['content'], 'probe')

    def test_empty_or_truncated_answer_is_a_failure_not_a_result(self):
        for model_result in ({'content': '', 'empty_answer': True, 'truncated': True}, {'content': '   '}):
            out, job, _ = self.run_handler({'status': 'completed', 'model_result': model_result})
            self.assertEqual(out['status'], 'failed'); self.assertEqual(job['attempt_log'][-1]['failure_class'], 'validation_failure')

    def test_garbage_from_a_broken_server_is_a_provider_failure_and_stops_the_server(self):
        stopped, results = [], []
        for text in ('<unused49>' * 40, 'ok <unused49><unused49><unused49> ...', 'a' * 300):
            out, job, _ = self.run_handler({'status': 'completed', 'model_result': {'content': text}},
                                           on_degenerate=lambda attempt, reason: stopped.append(reason),
                                           on_result=lambda *a: results.append(a))
            self.assertEqual(out['status'], 'failed'); self.assertEqual(job['attempt_log'][-1]['failure_class'], 'runtime_crash')
        self.assertEqual(stopped, ['special_token_run', 'special_token_run', 'single_character_run'])
        self.assertEqual(results, [])                                  # garbage never becomes a stored turn

    def test_normal_text_is_not_mistaken_for_garbage(self):
        for text in ('<unused49> once is fine', '-' * 80, 'def f():\n    return [0, 0, 0]\n' * 20, 'ja'):
            self.assertIsNone(degenerate_reason(text), text)

    def test_a_failing_stop_hook_does_not_hide_the_failure(self):
        def boom(*a): raise RuntimeError('stop failed')
        out, job, _ = self.run_handler({'status': 'completed', 'model_result': {'content': '<unused1>' * 5}}, on_degenerate=boom)
        self.assertEqual(job['attempt_log'][-1]['failure_class'], 'runtime_crash')

    def test_server_that_died_under_the_request_is_a_runtime_crash_not_an_unavailable_provider(self):
        for error in ('ConnectionResetError: [WinError 10054] Eine vorhandene Verbindung wurde vom Remotehost geschlossen',
                      'RemoteDisconnected: Remote end closed connection without response', 'server_exited_during_request'):
            out, job, _ = self.run_handler({'status': 'failed', 'error': error})
            self.assertEqual(job['attempt_log'][-1]['failure_class'], 'runtime_crash', error)
        out, job, _ = self.run_handler({'status': 'failed', 'error': 'model not loaded'})
        self.assertEqual(job['attempt_log'][-1]['failure_class'], 'model_unavailable')

    def test_waiting_and_failed_replies(self):
        out, job, _ = self.run_handler({'status': 'waiting', 'reason_code': 'THERMAL_HOT'})
        self.assertEqual(job['attempt_log'][-1]['failure_class'], 'hardware_pressure')
        out, job, _ = self.run_handler({'status': 'failed', 'error': 'x'})
        self.assertEqual(job['attempt_log'][-1]['failure_class'], 'model_unavailable')


class EvictionTest(Base):
    """Two models that cannot share the card take turns: idle ones are unloaded only when a start was refused for room."""
    def setUp(self):
        super().setUp()
        self.pressure = [True]
        class Ctl(FakeController): pass
        self.ctl = Ctl([inst('org/other', 8192, key='org/other')])
        self.sup.loader = ModelLoader(LoaderConfig({'enabled': True, 'evict_idle_models': True}), self.ctl, audit=self.audit)
        def resolver(role, req, exclude, independent_of):
            if self.pressure[0] and self.ctl.loaded and any(i['modelKey'] == 'org/other' for i in self.ctl.loaded):
                raise type('E', (Exception,), {'code': 'hardware_pressure'})()
            return {'role': role, 'provider_ref': 'lm-studio', 'capability_id': 'c', 'independence_key': 'k', 'context_window': 8192,
                    'estimated_resources': {'vram_gb': 8.0}, 'model': KEY, 'load_profile': {'gpu_layers': 99}}
        self.sup.resolver = resolver

    def test_idle_model_is_evicted_once_and_the_start_succeeds(self):
        self.job(); out = self.worker(lambda *a: None).run_once()
        self.assertEqual(out['status'], 'handled'); self.assertEqual([i['modelKey'] for i in self.ctl.loaded], [KEY])

    def test_a_model_in_use_is_never_evicted(self):
        # a running attempt on org/other: the start stays refused
        first = self.job(); self.sup.claim('w9', ['reviewer'])
        with self.sup.store.mutate(first) as j:
            j['worker'].update(state='running'); j['attempt_log'].append({'attempt_id': 'A', 'outcome': 'RUNNING', 'model': 'org/other', 'model_identifier': 'org/other'})
        self.assertEqual(self.sup._models_in_use(), {'org/other'})
        self.assertEqual(self.sup.loader.evict_idle(self.sup._models_in_use()), [])
        self.assertEqual(len(self.ctl.loaded), 1)

    def test_eviction_is_off_by_default(self):
        loader = ModelLoader(LoaderConfig({'enabled': True}), self.ctl)
        self.assertEqual(loader.evict_idle(set()), []); self.assertEqual(len(self.ctl.loaded), 1)
        self.assertFalse(LoaderConfig({}).evict_idle_models)
        with self.assertRaises(ValueError): LoaderConfig({'evict_idle_models': 'yes'})


if __name__ == '__main__':
    unittest.main()
