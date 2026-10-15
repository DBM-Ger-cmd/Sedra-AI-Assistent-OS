"""Phase 0.3: the development job store must not lose updates (finding F-3)."""
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from guppi_runtime.audit import AuditLog
from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.self_development import DevelopmentJobStore
from guppi_runtime.util import append_lock
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
SRC = str(Path(__file__).resolve().parents[1] / 'src')

PROC = """
import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from guppi_runtime.self_development import DevelopmentJobStore
store = DevelopmentJobStore(Path(sys.argv[2]))
for _ in range(int(sys.argv[4])):
    with store.mutate(sys.argv[3]) as job:
        job['attempts'] = int(job.get('attempts', 0)) + 1
"""


class JobStoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.rt = GuppiRuntime(Path(self.tmp.name) / 'project', ARCH)
        self.sd = self.rt.self_development
        out = self.sd.start('job_store_lock_probe', evidence=[{'source': 'test'}], target_type='skill')
        self.job_id = out['job']['job_id']
        self.store = self.sd.jobs

    def test_new_jobs_start_with_revision_after_first_save(self):
        self.assertGreaterEqual(self.store.load(self.job_id)['rev'], 1)

    def test_stale_copy_cannot_overwrite_newer_record(self):
        stale = self.store.load(self.job_id)
        with self.store.mutate(self.job_id) as fresh:
            fresh['attempts'] = 7
        stale['attempts'] = 1
        with self.assertRaises(ValueError) as ctx:
            self.store.save(stale)
        self.assertEqual(str(ctx.exception), 'stale_job_record')
        self.assertEqual(self.store.load(self.job_id)['attempts'], 7)

    def test_failed_transition_on_stale_copy_leaves_copy_unchanged(self):
        stale = self.store.load(self.job_id)
        before = (stale['state'], stale['last_progress'])
        with self.store.mutate(self.job_id) as fresh:
            fresh['attempts'] = 3
        with self.assertRaises(ValueError):
            self.store.transition(stale, 'READY')
        self.assertEqual((stale['state'], stale['last_progress']), before)
        self.assertEqual(self.store.load(self.job_id)['state'], 'PLANNING')

    def test_heartbeat_from_stale_copy_keeps_concurrent_state_change(self):
        worker_copy = self.store.load(self.job_id)
        self.sd.prepare_development_environment(self.job_id, {'execution_ready': True})  # PLANNING -> READY
        self.store.heartbeat(worker_copy, 'worker-1', lease_until='2099-01-01T00:00:00+00:00', marker='m1')
        now = self.store.load(self.job_id)
        self.assertEqual(now['state'], 'READY')
        self.assertEqual(now['lease']['worker_id'], 'worker-1')
        self.assertEqual(worker_copy['state'], 'READY')  # caller's copy refreshed in place

    def test_mutate_discards_changes_when_block_raises(self):
        with self.assertRaises(RuntimeError):
            with self.store.mutate(self.job_id) as job:
                job['attempts'] = 99
                raise RuntimeError('boom')
        self.assertEqual(self.store.load(self.job_id).get('attempts'), 0)

    def test_threads_do_not_lose_updates(self):
        errors = []

        def run():
            try:
                for _ in range(10):
                    with self.store.mutate(self.job_id) as job:
                        job['attempts'] = int(job.get('attempts', 0)) + 1
            except Exception as exc:  # pragma: no cover
                errors.append(repr(exc))

        threads = [threading.Thread(target=run) for _ in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.store.load(self.job_id)['attempts'], 80)

    def test_processes_do_not_lose_updates(self):
        procs = [subprocess.Popen([sys.executable, '-c', PROC, SRC, str(self.store.root), self.job_id, '10'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
        for p in procs:
            _, err = p.communicate(timeout=120)
            self.assertEqual(p.returncode, 0, err.decode(errors='replace'))
        self.assertEqual(self.store.load(self.job_id)['attempts'], 40)

    def test_manager_calls_serialize_with_heartbeats(self):
        errors = []
        stop = threading.Event()

        def beat():
            try:
                job = self.store.load(self.job_id)
                while not stop.is_set():
                    self.store.heartbeat(job, 'worker-1')
            except Exception as exc:  # pragma: no cover
                errors.append(repr(exc))

        t = threading.Thread(target=beat); t.start()
        try:
            self.sd.assign_roles(self.job_id, ['coder', 'tester'])
            self.sd.checkpoint(self.job_id, summary='mid-flight', next_steps=['x'])
            self.sd.prepare_development_environment(self.job_id, {'execution_ready': True})
        finally:
            stop.set(); t.join()
        self.assertEqual(errors, [])
        job = self.store.load(self.job_id)
        self.assertEqual(job['state'], 'READY')
        self.assertEqual(job['roles'], ['coder', 'tester'])
        self.assertEqual(job['checkpoint']['summary'], 'mid-flight')
        self.assertEqual(job['lease']['worker_id'], 'worker-1')

    def test_record_written_by_v120_without_revision_is_still_usable(self):
        path = self.store.path(self.job_id)
        data = json.loads(path.read_text(encoding='utf-8'))
        data.pop('rev', None)
        path.write_text(json.dumps(data), encoding='utf-8')
        self.sd.assign_roles(self.job_id, ['planner'])
        self.assertEqual(self.store.load(self.job_id)['roles'], ['planner'])
        self.assertEqual(self.store.load(self.job_id)['rev'], 1)

    def test_nested_lock_in_same_thread_does_not_deadlock(self):
        with append_lock(self.store.root / 'store', timeout=2):
            with append_lock(self.store.root / 'store', timeout=2):
                pass
        with self.store.mutate(self.job_id) as job:
            self.store.heartbeat(job, 'w')  # mutate inside mutate, same thread

    def test_learning_store_survives_concurrent_writers(self):
        sd = self.sd
        job_ids = []
        for n in range(6):
            job_id = sd.start(f'learn_probe_{n}', evidence=[{'source': 'test'}], target_type='skill')['job']['job_id']
            with sd.jobs.mutate(job_id) as job:  # shortcut to a verified job; the state machine is tested elsewhere
                job['state'] = 'READY_FOR_ACCEPTANCE'
                job['verification'] = {'result': 'PASS', 'verification_digest': 'd' * 64}
            job_ids.append(job_id)
        errors = []

        def run(job_id):
            try:
                sd.record_capability_learning(job_id)
            except Exception as exc:  # pragma: no cover
                errors.append(repr(exc))

        threads = [threading.Thread(target=run, args=(j,)) for j in job_ids]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])
        data = json.loads(sd.learning_path.read_text(encoding='utf-8'))
        self.assertEqual(sorted(data['capabilities']), [f'learn_probe_{n}' for n in range(6)])

    def test_audit_chain_stays_valid_after_concurrent_transitions(self):
        self.sd.prepare_development_environment(self.job_id, {'execution_ready': True})
        self.assertTrue(AuditLog(self.rt.audit.path).verify_chain())


if __name__ == '__main__':
    unittest.main()
