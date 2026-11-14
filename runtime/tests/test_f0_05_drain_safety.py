"""F0-05: never release a worker's shared resources after a join timeout.

These tests intentionally use in-memory SQLite and blocked threads. No live
models, network actions, global job states or leases are modified.
"""
from __future__ import annotations

import sqlite3
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from sedra_runtime.desk.orchestra_runner import WorkerPool
from sedra_runtime.orchestra.service import Orchestra
from sedra_runtime.runtime import SedraRuntime


class SlowPool:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.stops = Mock()
        self.pool = WorkerPool.__new__(WorkerPool)
        self.pool.workers = [SimpleNamespace(stop=self.stops)]
        self.pool.threads = []
        self.pool._stop_requested = False

    def start(self):
        def blocked():
            self.entered.set()
            self.release.wait(timeout=4)
        thread = threading.Thread(target=blocked, name="f0-05-inflight", daemon=True)
        self.pool.threads = [thread]
        thread.start()
        assert self.entered.wait(timeout=1)
        return thread

    def finish(self, thread):
        self.release.set()
        thread.join(timeout=1)


class WorkerPoolDrainTest(unittest.TestCase):
    def test_timeout_preserves_live_thread_for_retry(self):
        slow = SlowPool()
        thread = slow.start()
        try:
            self.assertFalse(slow.pool.stop(wait_s=0.01))
            self.assertEqual(slow.pool.threads, [thread])
            self.assertTrue(thread.is_alive())
            self.assertTrue(slow.pool._stop_requested)
            self.assertEqual(slow.stops.call_count, 1)
        finally:
            slow.finish(thread)
        self.assertTrue(slow.pool.stop(wait_s=0.05))
        self.assertEqual(slow.pool.threads, [])
        with self.assertRaisesRegex(RuntimeError, "worker_pool_stopping"):
            slow.pool.start()

    def test_stop_with_no_workers_is_safe_and_idempotent(self):
        pool = WorkerPool.__new__(WorkerPool)
        pool.workers = []
        pool.threads = []
        pool._stop_requested = False
        self.assertTrue(pool.stop(wait_s=0))
        self.assertTrue(pool.stop(wait_s=0))


class OrchestraDrainTest(unittest.TestCase):
    @staticmethod
    def orchestra(pool):
        orch = Orchestra.__new__(Orchestra)
        orch.conn = sqlite3.connect(":memory:")
        orch._stopping = False
        orch.tick_thread = None
        orch.worker_pool = pool
        return orch

    def test_close_waits_for_live_worker_before_sqlite_close(self):
        slow = SlowPool()
        thread = slow.start()
        orch = self.orchestra(slow.pool)
        try:
            result = orch.close(wait_s=0.01)
            self.assertEqual(result['status'], 'SHUTDOWN_PENDING')
            self.assertEqual(result['grund'], 'stop_tick_timeout')
            self.assertEqual(orch.conn.execute("SELECT 1").fetchone()[0], 1)
            self.assertIs(orch.worker_pool, slow.pool)
            self.assertTrue(orch._stopping)
            self.assertEqual(orch.run_blocked(), "orchestra_stopping")
            with self.assertRaisesRegex(RuntimeError, "orchestra_stopping"):
                orch.start_tick()
        finally:
            slow.finish(thread)
        result = orch.close(wait_s=0.05)
        self.assertEqual(result['status'], 'DRAINED')
        self.assertIsNone(orch.worker_pool)
        with self.assertRaises(sqlite3.ProgrammingError):
            orch.conn.execute("SELECT 1")

    def test_tick_timeout_keeps_handle_and_connection(self):
        orch = self.orchestra(None)
        entered = threading.Event()
        release = threading.Event()
        stop = threading.Event()

        def blocked_tick():
            entered.set()
            release.wait(timeout=4)

        thread = threading.Thread(target=blocked_tick, name="f0-05-tick", daemon=True)
        thread.stop = stop
        orch.tick_thread = thread
        thread.start()
        self.assertTrue(entered.wait(timeout=1))
        try:
            self.assertFalse(orch.stop_tick(wait_s=0.01))
            self.assertTrue(stop.is_set())
            self.assertIs(orch.tick_thread, thread)
            self.assertEqual(orch.conn.execute("SELECT 1").fetchone()[0], 1)
        finally:
            release.set()
            thread.join(timeout=1)
        orch.close(wait_s=0.05)
        self.assertIsNone(orch.tick_thread)


class RuntimeOwnershipTest(unittest.TestCase):
    def test_wissen_waits_when_orchestra_is_still_draining(self):
        rt = SedraRuntime.__new__(SedraRuntime)
        rt._close_lock = threading.Lock()
        rt._closed_services = set()
        rt.orchestra = Mock()
        rt.orchestra.close.side_effect = [
            {'status': 'SHUTDOWN_PENDING', 'grund': 'stop_tick_timeout'},
            {'status': 'DRAINED'},
        ]
        rt.wissen = Mock()
        result = rt.close()
        self.assertEqual(result['status'], 'SHUTDOWN_PENDING')
        rt.wissen.schliessen.assert_not_called()
        self.assertEqual(rt._closed_services, set())
        result = rt.close()
        self.assertEqual(result['status'], 'DRAINED')
        rt.close()
        self.assertEqual(rt.orchestra.close.call_count, 2)
        rt.wissen.schliessen.assert_called_once_with()
        self.assertEqual(rt._closed_services, {'orchestra', 'wissen'})


if __name__ == "__main__":
    unittest.main()
