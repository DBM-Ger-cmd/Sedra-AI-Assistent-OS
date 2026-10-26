"""Spec 2, OP-S2-18 (unlocked by the Captain 26.10.2026): the whole chain a real `enabled: true` start builds - the overlay through the loader, runtime
wiring, desk hub, poller, snapshot, strip, close. Only the server itself is faked. No model, no GPU."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guppi_runtime.uix_server import UIXHub
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests
from model_scheduler_fakes import FakeAudit, FakeLoader, FakeRuntime, resolution

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.17_RUNTIME_SYNC'


class Rehearsal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='sedra-')
        self.addCleanup(self.tmp.cleanup)
        project = Path(self.tmp.name) / 'project'
        (project / 'local_config').mkdir(parents=True)
        (project / 'local_config' / 'model_scheduler.yaml').write_text('model_scheduler:\n  enabled: true\n', encoding='utf-8')
        self.hub = UIXHub(project, ARCH)
        self.addCleanup(self.hub.close)
        self.rt = self.hub.runtime
        self.sched = self.rt.model_scheduler
        self.sched.loader, self.sched.runtime = FakeLoader(), FakeRuntime()          # no real server
        self.sched.audit = FakeAudit()
        self.addCleanup(self.sched._release_gpu)

    def test_the_loader_takes_the_overlay_and_there_is_no_lock_left(self):
        from guppi_runtime.jobs import model_scheduler_config as cfg
        self.assertFalse(hasattr(cfg, 'ENABLE_LOCK'))
        self.assertTrue(cfg.ModelSchedulerConfig.load(Path(__file__).resolve().parents[1] / 'config' / 'model_scheduler.yaml',
                                                     Path(self.tmp.name) / 'project' / 'local_config' / 'model_scheduler.yaml').enabled)

    def test_everything_a_real_start_builds_is_wired(self):
        rt = self.rt
        self.assertTrue(self.sched.enabled)
        self.assertIs(rt.job_supervisor.slots, self.sched)
        self.assertIs(rt.model_router.slot_guard.scheduler, self.sched)
        self.assertEqual(rt.model_scheduler_status()['enabled'], True)
        self.assertIsNotNone(self.sched.canary_invalidate)                           # gpu_canary.invalidate
        self.assertIs(self.hub._scheduler(), self.sched)
        self.assertEqual(rt.boot()['model_scheduler']['enabled'], True)

    def test_the_poller_takes_the_schedulers_step_and_the_snapshot_and_strip_carry_slots(self):
        with mock.patch.object(self.sched, 'poll', wraps=self.sched.poll) as poll:
            self.hub.poller.tick()
        poll.assert_called_once()
        snap = self.hub.desk_snapshot()
        self.assertIn('slots', snap)
        self.assertEqual(self.hub.strip_view()['slots']['value'], '0/0')
        self.assertIn('slots', self.hub.objects_view({'type': 'model'}))
        self.assertEqual(self.hub.decisions_view()['items'], [])

    def test_the_workshop_holds_no_lease_of_its_own_and_closing_the_window_stops_the_server(self):
        self.assertTrue(self.sched.take_for_job('SDJ-1', 5)['granted'])
        self.sched.ensure_server(resolution(), run_id='SDJ-1')
        self.sched.release('SDJ-1')
        self.assertIsNone(self.hub.gpu_token)
        self.assertEqual(self.sched.lab.holder()['owner'], self.sched.owner)
        self.hub.close()
        self.assertEqual(self.sched.loader.unloaded, ['main.local'])
        self.assertIsNone(self.sched.lab.holder())

    def test_closing_the_window_leaves_a_server_with_active_runs_alone(self):
        self.assertTrue(self.sched.take_for_job('SDJ-1', 5)['granted'])
        self.sched.ensure_server(resolution(), run_id='SDJ-1')
        self.hub.close()
        self.assertEqual(self.sched.loader.unloaded, [])

    def test_a_locked_server_is_unlocked_only_by_the_captain_and_not_by_entladen_or_close(self):
        self.sched._shutdown('gesperrt', reason='server_exited')
        self.assertEqual(self.sched.stop_server()['status'], 'gesperrt')
        with self.assertRaisesRegex(ValueError, 'server_gesperrt'):
            self.hub.unload_model({})
        self.hub.close()
        with self.sched._conn() as conn:
            self.assertEqual(self.sched._server(conn)['state'], 'gesperrt')

    def test_forcing_during_an_overdue_drain_stops_the_server_and_keeps_the_request(self):
        from guppi_runtime.jobs.testlab import TestLab
        bench = TestLab(self.sched.lab.path, clock=self.sched.lab.clock, alive=lambda p: True, pid=222)
        self.assertTrue(self.sched.take_for_job('SDJ-1', 5)['granted'])
        self.sched.ensure_server(resolution(), run_id='SDJ-1')
        bench.register_waiter('bench', 'x', ttl_s=100_000)
        self.assertEqual(self.sched.poll()['action'], 'draining')
        out = self.sched.stop_server(force=True)
        self.assertEqual((out['status'], out['interrupted']), ('stopped', ['SDJ-1']))
        with self.sched._conn() as conn:
            server = self.sched._server(conn)
        self.assertEqual((server['state'], server['owner']), ('exklusiv', 'bench'))   # the benchmark still gets the GPU
        self.assertTrue(bench.try_acquire('bench', 'x'))


if __name__ == '__main__':
    unittest.main()
