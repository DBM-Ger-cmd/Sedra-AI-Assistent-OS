"""Spec 2, S2.H3: the facade `jobs/model_scheduler.py` and `config/model_scheduler.yaml`. No model, no GPU: a fake loader and runtime."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.jobs import slot_store
from guppi_runtime.jobs.model_scheduler import ModelScheduler, ModelSchedulerConfig, SchedulerError
from guppi_runtime.jobs.testlab import TestLab
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests
from model_scheduler_fakes import CONFIG, Clock, make_scheduler, raw_config, resolution

RUNTIME = Path(__file__).resolve().parents[1]
ARCH = RUNTIME.parent / "architecture" / "GUPPI_Architecture_v1.20_SELF_DEVELOPMENT"


class Resources:
    """The resource scheduler as the facade sees it: measured free VRAM, one reservation for the server, an audit of refusals."""
    enabled = True

    class config:
        vram_reserve_gb = 0.7

    def __init__(self, free=11.0, deny=None):
        self.free, self.deny = free, deny
        self.reserved, self.released, self.denied = [], [], []

    def measured_free_vram_gb(self):
        return self.free

    def audit_denied(self, job_id, reason, **values):
        self.denied.append((job_id, reason, values))

    def reserve(self, job_id, attempt_id, estimate, **_):
        if self.deny:
            return {"status": "DENIED", "reason": self.deny, "detail": {"need_gb": estimate["vram_gb"]}}
        self.reserved.append((job_id, attempt_id, estimate["vram_gb"]))
        return {"status": "GRANTED", "reservation": {"job_id": job_id}}

    def release_job(self, job_id):
        self.released.append(job_id)
        return 1


class ConfigTests(unittest.TestCase):
    def test_the_shipped_file_is_valid_off_and_carries_the_start_values(self):
        cfg = ModelSchedulerConfig.load(CONFIG)
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.priorities, {"captain": 7, "agent": 5, "routine": 3})
        self.assertEqual((cfg.vram_limit_gb, cfg.wait_max_s, cfg.queue_max, cfg.drain_max_s, cfg.slot_ttl_s), (11.5, 600, 6, 1800, 120))
        self.assertEqual(cfg.standard_slots, {"hauptmodell": 2, "hilfsmodell": 2})
        self.assertEqual(cfg.slots_cap_by_profile, {"quiet": 1, "ai-sustained": 1, "balanced": 2})
        self.assertEqual(cfg.plan(), {"age_after_s": 120, "age_cap": 5, "swap": "none", "queue_max": 6, "wait_max_s": 600})
        self.assertEqual([cfg.priority(o) for o in ("captain", "agent", "routine")], [7, 5, 3])

    def test_invalid_values_refuse_start(self):
        bad = [dict(enabled="yes"), dict(vram_limit_gb=0), dict(priorities={"captain": 8, "agent": 5, "routine": 3}),
               dict(priorities={"captain": 5, "agent": 5, "routine": 3}), dict(age_cap=7), dict(age_after_s=0), dict(swap="always"),
               dict(swap={"fallback": ""}), dict(slots_cap_by_profile={"quiet": 0}), dict(standard_slots={"hauptmodell": 9}),
               dict(standard_slots={"drittmodell": 2}), dict(restart={"max": -1}), dict(queue_max="6")]
        for overrides in bad:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                ModelSchedulerConfig(raw_config(**overrides))

    def test_the_overlay_may_change_only_five_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            overlay = Path(tmp) / "model_scheduler.yaml"
            overlay.write_text("model_scheduler:\n  swap: idle\n  queue_max: 2\n", encoding="utf-8")
            cfg = ModelSchedulerConfig.load(CONFIG, overlay)
            self.assertEqual((cfg.enabled, cfg.swap, cfg.queue_max, cfg.vram_limit_gb), (False, "idle", 2, 11.5))
            overlay.write_text("model_scheduler:\n  vram_limit_gb: 20\n", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                ModelSchedulerConfig.load(CONFIG, overlay)
            self.assertEqual(str(ctx.exception), "model_scheduler_config_invalid:overlay:vram_limit_gb")
            with self.assertRaises(ValueError) as ctx:
                ModelSchedulerConfig.load(Path(tmp) / "missing.yaml")
            self.assertEqual(str(ctx.exception), "model_scheduler_config_missing")


class Base(unittest.TestCase):
    overrides = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.make(**self.overrides)

    def make(self, **overrides):
        self.sched, self.lab, self.loader, self.runtime, self.audit, self.clock = make_scheduler(self.tmp.name, **overrides)
        self.addCleanup(self.sched._release_gpu)

    def server(self):
        with self.lab._db() as db:
            row = db.execute("SELECT * FROM slot_server").fetchone()
        return dict(row) if row else None

    def lease(self, run_id):
        with self.lab._db() as db:
            return dict(db.execute("SELECT * FROM slot_leases WHERE run_id=?", (run_id,)).fetchone())

    def start(self, job="SDJ-1", **kw):
        self.assertTrue(self.sched.take_for_job(job, 5)["granted"])
        return self.sched.ensure_server(resolution(**kw), run_id=job)


class ServerTests(Base):
    def test_the_first_run_starts_the_server_once_and_the_slots_fill_in_order(self):
        self.assertTrue(self.sched.take_for_job("SDJ-1", 5)["granted"])                 # off: exactly one starter
        self.assertEqual(self.sched.take_for_job("SDJ-2", 5), {"granted": False, "slot": None, "reason": "server_startet"})
        out = self.sched.ensure_server(resolution(), run_id="SDJ-1")
        self.assertEqual((out["action"], out["gen"], out["slots"]), ("started", 1, 2))
        self.assertEqual(self.loader.loaded, [("main.local", 2, 32768)])
        self.assertEqual(self.lab.holder()["owner"], "sedra-scheduler")
        server = self.server()
        self.assertEqual((server["state"], server["recipe"], server["slots"], server["context_per_slot"], server["pid"]), ("bereit", "main.local", 2, 32768, 4242))
        self.assertEqual(self.lease("SDJ-1")["server_gen"], 1)                       # the starter belongs to the new generation
        self.assertEqual(self.sched.take_for_job("SDJ-2", 5)["slot"], 2)
        self.assertEqual(self.sched.take_for_job("SDJ-3", 5)["reason"], "kein_slot")
        self.assertEqual(self.sched.ensure_server(resolution(), run_id="SDJ-2")["action"], "reused")
        self.assertEqual(len(self.loader.loaded), 1)
        self.assertEqual(self.audit.of("SLOT_SERVER_STARTED")[0]["vram_gb"], 9.0)    # 8 GB weights once + 2 x 0.5 GB KV

    def test_another_holder_of_the_gpu_lease_means_no_server_and_nothing_touched(self):
        other = TestLab(self.lab.path, clock=self.clock, alive=lambda p: True, pid=222)
        token = other.try_acquire("bench", "context ladder")
        self.assertTrue(self.sched.take_for_job("SDJ-1", 5)["granted"])
        with self.assertRaises(SchedulerError) as ctx:
            self.sched.ensure_server(resolution(), run_id="SDJ-1")
        self.assertEqual(ctx.exception.reason, "gpu_lease_busy:bench:context ladder")
        self.assertEqual((self.loader.loaded, self.server()), ([], None))
        other.release(token)
        with other.reserve("night-g", "G builds", priority=1):
            with self.assertRaises(SchedulerError) as ctx:
                self.sched.ensure_server(resolution(), run_id="SDJ-1")
            self.assertEqual(ctx.exception.reason, "gpu_lease_deferred:night-g")      # the night chain comes first (D2.12)

    def test_a_start_above_the_limit_is_refused_with_the_numbers_in_result_and_audit(self):
        self.sched.take_for_job("SDJ-1", 5)
        with self.assertRaises(SchedulerError) as ctx:
            self.sched.ensure_server(resolution(vram_gb=10.0, kv_gb=1.0), run_id="SDJ-1")
        self.assertEqual((ctx.exception.reason, ctx.exception.code), ("vram_insufficient", "hardware_pressure"))
        self.assertEqual(ctx.exception.detail, {"need_gb": 11.0, "measured_free_gb": None, "limit_gb": 11.5, "reserve_gb": 0.7, "reason": "limit"})
        denied = self.audit.of("RESOURCE_DENIED")[0]
        self.assertEqual((denied["reason"], denied["need_gb"], denied["limit_gb"], denied["measured_free_gb"]), ("vram_insufficient", 11.0, 11.5, None))
        self.assertIsNone(self.lab.holder())                                         # refused before the lease was taken
        self.assertEqual(self.loader.loaded, [])

    def test_the_measured_free_memory_counts_and_the_server_holds_one_reservation(self):
        res = Resources(free=9.5)
        self.make(resources=res)
        self.sched.take_for_job("SDJ-1", 5)
        with self.assertRaises(SchedulerError) as ctx:
            self.sched.ensure_server(resolution(), run_id="SDJ-1")                    # 9.0 needed, 9.5 - 0.7 free
        self.assertEqual(ctx.exception.detail["reason"], "frei")
        self.assertEqual(res.denied, [("server:main.local", "vram_insufficient",
                                       {"need_gb": 9.0, "measured_free_gb": 9.5, "limit_gb": 11.5, "reserve_gb": 0.7, "limit_reason": "frei"})])
        res.free = 11.0
        self.sched.ensure_server(resolution(), run_id="SDJ-1")
        self.sched.take_for_job("SDJ-2", 5)
        self.sched.ensure_server(resolution(), run_id="SDJ-2")
        self.assertEqual(res.reserved, [("server:main.local", "gen-1", 9.0)])        # weights once, KV per slot, one reservation for N runs
        self.sched.stop_server(force=True)
        self.assertEqual(res.released, ["server:main.local"])

    def test_a_failed_load_leaves_nothing_behind(self):
        res = Resources()
        self.make(resources=res)
        self.loader.fail = "load_failed:gguf"
        self.sched.take_for_job("SDJ-1", 5)
        with self.assertRaises(SchedulerError) as ctx:
            self.sched.ensure_server(resolution(), run_id="SDJ-1")
        self.assertEqual((ctx.exception.code, ctx.exception.reason), ("provider_unavailable", "load_failed:gguf"))
        self.assertEqual((self.server()["state"], self.lab.holder(), res.released), ("aus", None, ["server:main.local"]))
        self.assertEqual(self.lease("SDJ-1")["state"], "unterbrochen")
        self.assertEqual(self.audit.of("SLOT_SERVER_START_FAILED")[0]["reason"], "load_failed:gguf")
        refused = Resources(deny="job_limit")
        self.make(resources=refused)
        self.sched.take_for_job("SDJ-9", 5)
        with self.assertRaises(SchedulerError) as ctx:
            self.sched.ensure_server(resolution(), run_id="SDJ-9")
        self.assertEqual((ctx.exception.code, ctx.exception.reason, self.lab.holder()), ("hardware_pressure", "job_limit", None))

    def test_the_hardware_profile_limits_the_slot_leases_not_the_server(self):
        self.make(profile=lambda: "quiet")
        out = self.start()
        self.assertEqual((out["slots"], self.loader.loaded), (1, [("main.local", 2, 32768)]))
        self.assertEqual(self.sched.take_for_job("SDJ-2", 5)["reason"], "kein_slot")
        self.assertEqual(self.sched.view()["slots_cap"], 1)

    def test_stop_waits_for_active_runs_unless_forced(self):
        self.start()
        self.assertEqual(self.sched.stop_server(), {"status": "leases_active", "active": ["SDJ-1"]})
        self.assertEqual(self.sched.stop_server(force=True), {"status": "stopped", "interrupted": ["SDJ-1"]})
        self.assertEqual((self.server()["state"], self.loader.unloaded, self.lab.holder()), ("aus", ["main.local"], None))
        self.assertEqual(self.lease("SDJ-1")["state"], "unterbrochen")
        self.assertEqual(self.sched.stop_server(), {"status": "already_off", "interrupted": []})

    def test_a_crashed_server_interrupts_its_leases_and_the_fourth_crash_locks_it(self):
        for n in range(1, 5):
            with self.subTest(crash=n):
                job = f"SDJ-{n}"
                self.runtime.running = True
                self.assertEqual(self.start(job)["action"], "started")
                self.runtime.running = False
                with self.assertRaises(SchedulerError) as ctx:
                    self.sched.ensure_server(resolution(), run_id=job)
                self.assertEqual(ctx.exception.reason, "server_exited")
                self.assertEqual(self.lease(job)["state"], "unterbrochen")
                self.assertIsNone(self.lab.holder())
                self.clock.t += 60
        self.assertEqual(self.server()["state"], "gesperrt")
        self.assertEqual(len(self.audit.of("SLOT_SERVER_GESPERRT")), 1)
        self.assertEqual(self.sched.take_for_job("SDJ-9", 5)["reason"], "gesperrt")

    def test_a_lease_taken_over_by_another_process_locks_the_server_and_is_audited(self):
        self.start()
        token = self.sched._token
        other = TestLab(self.lab.path, clock=self.clock, alive=lambda p: p == 222, pid=222)     # sees our process as gone
        self.assertTrue(other.try_acquire("bench", "ladder"))
        self.assertFalse(self.lab.heartbeat(token))
        self.sched._lease_lost(token)                                               # what the heartbeat thread does on a refused beat
        server = self.server()
        self.assertEqual((server["state"], server["reason"], self.sched._token), ("gesperrt", "gpu_lease_lost", None))
        self.assertEqual(self.lease("SDJ-1")["state"], "unterbrochen")
        self.assertEqual(self.audit.of("SLOT_GPU_LEASE_LOST")[0]["holder"], "bench")
        self.assertEqual(self.sched.take_for_job("SDJ-2", 5)["reason"], "gesperrt")
        self.assertEqual(other.holder()["owner"], "bench")                         # the other process keeps what it took

    def test_reap_ends_the_leases_of_runs_that_cannot_ask_any_more(self):
        self.start()
        self.sched.take_for_job("SDJ-2", 5)
        self.sched.take_for_job("SDJ-3", 5)
        self.assertEqual(self.sched.reap({"SDJ-1"}), ["SDJ-2", "SDJ-3"])
        self.assertEqual(self.lease("SDJ-1")["state"], "aktiv")
        self.clock.t += 10_000                                                       # the clock alone frees nothing
        self.assertEqual(self.sched.reap({"SDJ-1"}), [])

    def test_a_job_whose_start_was_refused_goes_back_to_waiting_in_its_place(self):
        self.sched.take_for_job("SDJ-1", 5)
        self.clock.t += 5
        self.sched.take_for_job("SDJ-2", 5)
        self.sched.wait_for_job("SDJ-1", 5)
        lease = self.lease("SDJ-1")
        self.assertEqual((lease["state"], lease["slot"], lease["enqueued"]), ("wartend", None, "2026-10-24T00:00:00Z"))
        self.assertTrue(self.sched.take_for_job("SDJ-1", 5)["granted"])            # still first in line
        self.assertFalse(self.sched.take_for_job("SDJ-2", 5)["granted"])


class DirectTests(Base):
    def test_a_direct_call_takes_a_free_slot_and_gives_it_back(self):
        self.start()
        with self.sched.slot("chat", 7) as held:
            self.assertEqual(held["slot"], 2)
            self.assertEqual(len(self.sched.view()["belegt"]), 2)
        self.assertEqual(len(self.sched.view()["belegt"]), 1)
        self.assertEqual(self.sched._direct, set())

    def test_a_direct_call_never_waits_silently(self):
        self.start()
        self.sched.take_for_job("SDJ-2", 5)
        naps = []

        def nap(s):
            naps.append(s)
            self.clock.t += s
        with self.assertRaises(SchedulerError) as ctx:
            with self.sched.slot("chat", 7, wait_s=2, poll_s=1, sleep=nap):
                pass
        self.assertEqual((ctx.exception.reason, ctx.exception.detail, naps), ("slot_wait_timeout", {"grund": "kein_slot"}, [1, 1]))
        self.assertEqual(self.sched.view()["schlange"], [])                          # the given-up request is gone from the line

    def test_a_direct_call_cannot_start_the_server(self):
        with self.assertRaises(SchedulerError) as ctx:
            with self.sched.slot("chat", 7):
                pass
        self.assertEqual(ctx.exception.reason, "server_aus")
        self.assertEqual(self.sched.view()["belegt"], [])


class HandoverTests(Base):
    def setUp(self):
        super().setUp()
        self.bench = TestLab(self.lab.path, clock=self.clock, alive=lambda p: True, pid=222)

    def test_a_waiting_benchmark_gets_the_gpu_after_the_active_run_and_the_server_stays_off(self):
        self.start()
        self.bench.register_waiter("bench-ladder", "context ladder")
        self.assertEqual(self.sched.poll()["action"], "draining")
        self.assertEqual(self.sched.take_for_job("SDJ-2", 5)["reason"], "drain")     # no new slots while draining
        self.assertEqual(self.sched.view()["exklusiv"]["eigner"], "bench-ladder")
        self.sched.release("SDJ-1")
        self.assertEqual(self.sched.poll(), {"state": "exklusiv", "action": "handed_over", "owner": "bench-ladder"})
        self.assertEqual(self.loader.unloaded, ["main.local"])
        token = self.bench.try_acquire("bench-ladder", "context ladder")
        self.assertTrue(token)
        self.assertEqual(self.sched.take_for_job("SDJ-3", 5)["reason"], "exklusiv:bench-ladder")
        self.bench.clear_waiter("bench-ladder")
        self.assertEqual(self.sched.poll()["state"], "aus")
        self.assertEqual(self.loader.loaded, [("main.local", 2, 32768)])           # no rebuild on suspicion
        self.bench.release(token)

    def test_past_the_drain_limit_the_request_stays_and_no_run_is_killed(self):
        self.start()
        self.bench.register_waiter("bench", "x", ttl_s=100_000)
        self.sched.poll()
        self.clock.t += 1801
        self.assertEqual(self.sched.poll()["action"], "draining")
        self.sched.poll()
        self.assertEqual(len(self.audit.of("SLOT_DRAIN_OVERDUE")), 1)
        self.assertEqual(self.lease("SDJ-1")["state"], "aktiv")
        self.assertEqual(self.server()["state"], "drain")

    def test_an_idle_scheduler_hands_over_at_once_and_a_benchmark_that_gives_up_ends_the_drain(self):
        self.bench.register_waiter("bench", "x")
        self.assertEqual(self.sched.poll()["state"], "exklusiv")
        self.bench.clear_waiter("bench")
        self.assertEqual(self.sched.poll()["state"], "aus")
        self.start()
        self.bench.register_waiter("bench", "x")
        self.sched.poll()
        self.bench.clear_waiter("bench")
        self.assertEqual(self.sched.poll(), {"state": "bereit", "action": "handover_ended"})


class ViewTests(Base):
    def test_the_view_has_the_shape_of_spec_4(self):
        self.start()
        self.sched.take_for_job("SDJ-2", 3, agent_id="AGT-1")
        self.sched.take_for_job("SDJ-3", 5)
        view = self.sched.view()
        for key in ("gesamt", "belegt", "schlange", "modell", "warte_max_s", "server", "exklusiv", "warnung"):
            self.assertIn(key, view)
        self.assertEqual((view["gesamt"], view["modell"], view["warte_max_s"], view["exklusiv"], view["warnung"]), (2, "main.local", 600, None, None))
        self.assertEqual(view["server"], {"state": "bereit", "gen": 1, "recipe": "main.local", "slots": 2})
        self.assertEqual(len(view["belegt"]), 2)
        self.clock.t += 601                                                          # SDJ-3 waits longer than wait_max_s: one hint
        self.assertEqual(self.sched.view()["warnung"], {"art": "wartezeit", "run_id": "SDJ-3", "seit": "2026-10-24T00:00:00Z"})

    def test_off_means_nothing_answers(self):
        sched = ModelScheduler(ModelSchedulerConfig(raw_config(enabled=False)), self.lab)
        self.assertEqual(sched.view(), {"enabled": False, "error": None})
        for call in (lambda: sched.take_for_job("SDJ-1", 5), lambda: sched.ensure_server(resolution()), lambda: sched.poll(),
                     lambda: sched.release("SDJ-1"), lambda: sched.reap(set()), lambda: sched.stop_server()):
            with self.assertRaises(SchedulerError) as ctx:
                call()
            self.assertEqual(ctx.exception.reason, "model_scheduler_disabled")

    def test_a_test_lab_at_schema_1_refuses_the_scheduler(self):
        lab = TestLab(Path(self.tmp.name) / "old.db", clock=Clock())
        lab.schema, lab.schema_error = 1, "testlab_schema2_failed:OperationalError"
        with self.assertRaises(ValueError) as ctx:
            ModelScheduler(ModelSchedulerConfig(raw_config()), lab)
        self.assertEqual(str(ctx.exception), "testlab_schema2_failed:OperationalError")


class RuntimeWiringTests(unittest.TestCase):
    def runtime(self, overlay=None):
        from guppi_runtime.runtime import GuppiRuntime
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        project = Path(tmp.name) / "project"
        if overlay is not None:
            (project / "local_config").mkdir(parents=True)
            (project / "local_config" / "model_scheduler.yaml").write_text(overlay, encoding="utf-8")
        return GuppiRuntime(project, ARCH), project

    def test_off_by_default_one_worker_and_boot_says_so(self):
        rt, project = self.runtime()
        self.assertIsNone(rt.model_scheduler)
        self.assertEqual(rt.model_scheduler_status(), {"enabled": False, "error": None})
        self.assertEqual(rt.job_supervisor.config.workers, 1)
        self.assertIsNone(rt.job_supervisor.slots)
        self.assertFalse((project / "runtime_data" / "testlab" / "testlab.db").exists())     # off touches no test lab

    def test_an_invalid_overlay_keeps_it_off_and_says_why(self):
        rt, _ = self.runtime("model_scheduler:\n  poll_s: 1\n")
        self.assertIsNone(rt.model_scheduler)
        self.assertEqual(rt.model_scheduler_status(), {"enabled": False, "error": "model_scheduler_config_invalid:overlay:poll_s"})

    def test_switching_it_on_is_refused_until_s2h5(self):
        rt, project = self.runtime("model_scheduler:\n  enabled: true\n")
        self.assertIsNone(rt.model_scheduler)
        self.assertEqual(rt.model_scheduler_status(), {"enabled": False, "error": "model_scheduler_locked_until_s2h5"})
        self.assertEqual((rt.job_supervisor.config.workers, rt.job_supervisor.slots), (1, None))
        self.assertFalse((project / "runtime_data" / "testlab" / "testlab.db").exists())

    def test_built_directly_it_is_attached_to_the_supervisor(self):
        from guppi_runtime.jobs.testlab import default_path
        rt, project = self.runtime()
        from unittest import mock
        on = ModelSchedulerConfig(raw_config())
        with mock.patch("guppi_runtime.runtime.ModelSchedulerConfig.load", return_value=on):
            rt._configure_model_scheduler(project / "runtime_data")
        self.assertIs(rt.job_supervisor.slots, rt.model_scheduler)
        self.assertTrue(default_path(project).exists())
        status = rt.model_scheduler_status()
        self.assertEqual((status["enabled"], status["gesamt"], status["server"]["state"]), (True, 0, "aus"))


if __name__ == "__main__":
    unittest.main()
