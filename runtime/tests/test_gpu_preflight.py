import tempfile
import unittest
from pathlib import Path

from guppi_runtime.models import gpu_preflight as gp
from guppi_runtime.jobs.testlab import TestLab
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

OURS = {"name": "llama-server.exe", "path": r"C:\Users\x\.lmstudio\extensions\backends\llama.cpp-win-x86_64-nvidia-cuda12-avx2-2.50.0\llama-server.exe",
        "cmd": "llama-server.exe -m a.gguf --port 8089 --no-webui --alias gpt-oss-20b --spec-type none"}
LMS = {**OURS, "cmd": "llama-server.exe -m a.gguf --port 8089"}                       # LM Studio's own launch: no GUPPI signature
GAME = {"name": "game.exe", "path": r"C:\Games\game.exe", "cmd": "game.exe"}


class Fake:
    """Replaces the module's process and GPU probes. `vram` is a list: each read pops the next value (the last one repeats)."""
    def __init__(self, monkey, listener=None, procs=None, servers=None, vram=(0.7,), users=()):
        self.stopped, self.vram, self.users = [], list(vram), list(users)
        info = procs or {}
        monkey(gp, "listener_pid", lambda port, run=None: listener)
        monkey(gp, "process_info", lambda pid, run=None: info.get(pid))
        monkey(gp, "guppi_llama_servers", lambda run=None: dict(servers or {}))
        monkey(gp, "vram_used_gb", lambda run=None: self.vram.pop(0) if len(self.vram) > 1 else self.vram[0])
        monkey(gp, "gpu_users", lambda run=None: self.users)
        monkey(gp, "_stop", lambda pid, run=None: self.stopped.append(pid))


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.patches = []
        self.addCleanup(lambda: [setattr(m, n, v) for m, n, v in self.patches])
        self.now = [0.0]

    def monkey(self, mod, name, value):
        self.patches.append((mod, name, getattr(mod, name))); setattr(mod, name, value)

    def run_clear(self, **kw):
        return gp.clear_leftovers(say=lambda *_: None, sleep=lambda s: self.now.__setitem__(0, self.now[0] + s), monotonic=lambda: self.now[0], **kw)

    def test_clean_card_stops_nothing(self):
        fake = Fake(self.monkey)
        self.assertEqual(self.run_clear(), 0.7); self.assertEqual(fake.stopped, [])

    def test_leftover_guppi_server_on_the_port_is_stopped(self):
        fake = Fake(self.monkey, listener=10, procs={10: OURS}, servers={10: OURS}, vram=(9.0, 0.7))
        self.assertEqual(self.run_clear(), 0.7); self.assertEqual(fake.stopped, [10])

    def test_orphan_without_listener_is_stopped_too(self):
        fake = Fake(self.monkey, servers={20: OURS})
        self.run_clear(); self.assertEqual(fake.stopped, [20])

    def test_foreign_process_on_the_port_is_refused_and_never_stopped(self):
        fake = Fake(self.monkey, listener=30, procs={30: GAME})
        with self.assertRaisesRegex(gp.GpuNotClean, "game.exe"): self.run_clear()
        self.assertEqual(fake.stopped, [])

    def test_lm_studio_engine_on_the_port_is_not_taken_for_ours(self):
        fake = Fake(self.monkey, listener=40, procs={40: LMS})
        with self.assertRaises(gp.GpuNotClean): self.run_clear()
        self.assertEqual(fake.stopped, [])

    def test_busy_card_without_a_guppi_server_is_refused_with_the_users_named(self):
        Fake(self.monkey, vram=(8.0,), users=["999, game.exe, [N/A]"])
        with self.assertRaisesRegex(gp.GpuNotClean, "game.exe"): self.run_clear(settle_s=3)

    def test_signature_check(self):
        self.assertTrue(gp.is_guppi_server(OURS)); self.assertFalse(gp.is_guppi_server(LMS)); self.assertFalse(gp.is_guppi_server(None))

    def test_own_engine_server_is_recognised_but_only_with_the_signature(self):
        own = {**OURS, "path": r"<projekte>\Guppy\GUPPI_Runtime_v1.20\engines\llama.cpp\b11371\llama-server.exe"}
        self.assertTrue(gp.is_guppi_server(own))
        self.assertFalse(gp.is_guppi_server({**own, "cmd": "llama-server.exe -m a.gguf --port 8089"}))
        self.assertFalse(gp.is_guppi_server({**own, "path": r"C:\tools\llama-server.exe"}))


class SchedulerServerTests(unittest.TestCase):
    """B-6 (Spec 2, D2.7): a llama-server whose pid stands in slot_server.pid is the scheduler's, not a leftover."""
    def setUp(self):
        self.patches = []
        self.addCleanup(lambda: [setattr(m, n, v) for m, n, v in self.patches])
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.lab = TestLab(Path(self.tmp.name) / "lab" / "testlab.db", alive=lambda p: True)

    monkey = PreflightTests.monkey

    def run_clear(self, **kw):
        return gp.clear_leftovers(say=lambda *_: None, sleep=lambda s: None, **kw)

    def serve(self, state="bereit", pid=20):
        from guppi_runtime.jobs import slot_store
        conn = self.lab.connect()
        try:
            slot_store.set_server(conn, "2026-10-24T00:00:00Z", state, recipe="main.local", slots=2, pid=pid)
        finally:
            conn.close()

    def test_a_server_of_the_scheduler_is_spared_and_the_orphan_is_stopped(self):
        fake = Fake(self.monkey, servers={20: OURS, 21: OURS}); self.serve()
        self.run_clear(lab=self.lab); self.assertEqual(fake.stopped, [21])

    def test_after_the_server_is_off_the_same_pid_is_a_leftover_again(self):
        fake = Fake(self.monkey, servers={20: OURS}); self.serve("aus")
        self.run_clear(lab=self.lab); self.assertEqual(fake.stopped, [20])

    def test_the_scheduler_server_on_the_port_refuses_the_run_and_is_not_stopped(self):
        fake = Fake(self.monkey, listener=20, procs={20: OURS}, servers={20: OURS}); self.serve("drain")
        with self.assertRaisesRegex(gp.GpuNotClean, "scheduler"): self.run_clear(lab=self.lab)
        self.assertEqual(fake.stopped, [])

    def test_explicit_protected_pids_and_a_lab_without_slot_tables(self):
        fake = Fake(self.monkey, servers={30: OURS}); self.run_clear(protected=[30]); self.assertEqual(fake.stopped, [])
        old = TestLab(Path(self.tmp.name) / "old.db", alive=lambda p: True); old.schema = 1
        self.assertEqual(gp.scheduler_server_pids(old), set())

    def test_the_lease_hands_itself_to_the_hook(self):
        fake = Fake(self.monkey, servers={20: OURS, 21: OURS}); self.serve()
        with self.lab.lease("bench", "x", preflight=gp.clear_leftovers):
            pass
        self.assertEqual(fake.stopped, [21])


class LeaseHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.lab = TestLab(Path(self.tmp.name) / "lab" / "testlab.db", alive=lambda p: True)

    def test_hook_runs_while_the_lease_is_held(self):
        seen = []
        with self.lab.lease("chat-1", "x", preflight=lambda owner: seen.append((owner, self.lab.holder()["owner"]))):
            pass
        self.assertEqual(seen, [("chat-1", "chat-1")]); self.assertIsNone(self.lab.holder())

    def test_a_failing_hook_releases_the_lease_and_is_recorded(self):
        def refuse(owner): raise gp.GpuNotClean("busy")
        with self.assertRaises(gp.GpuNotClean):
            with self.lab.lease("chat-1", "x", preflight=refuse): self.fail("block must not run")
        self.assertIsNone(self.lab.holder())
        self.assertIn("preflight_failed", [e["kind"] for e in self.lab.events()])


if __name__ == "__main__":
    unittest.main()
