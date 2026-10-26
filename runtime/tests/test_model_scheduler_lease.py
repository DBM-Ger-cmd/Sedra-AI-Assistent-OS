"""Spec 2, S2.H5, SCH-11 (G2-S2-05): every start and every call of a local model runs through the scheduler - workshop, job and direct call. No model,
no GPU: the scheduler's fakes and a bare workshop hub."""
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from guppi_runtime.models.base import ModelAdapterError
from guppi_runtime.models.router import ModelRouter
from guppi_runtime.models.slot_guard import SlotGuard
from guppi_runtime.uix_server import UIXHub
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests
from model_scheduler_fakes import make_scheduler, resolution


class FakeAdapter:
    """A local llama adapter that records what the scheduler showed while the request ran."""

    def __init__(self, sched=None, id="llama-cpp-server", route="local"):
        self.sched, self.seen, self.kwargs, self.id, self.route = sched, [], [], id, route

    def health(self):
        return True

    def chat(self, messages, model=None, **kwargs):
        self.kwargs.append(kwargs)
        if self.sched is not None:
            self.seen.append([(b["run_id"], b["prioritaet"]) for b in self.sched.view()["belegt"]])
        return {"content": "ok", "model": model or "m"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sched, self.lab, self.loader, self.runtime, self.audit, self.clock = make_scheduler(self.tmp.name)
        self.addCleanup(self.sched._release_gpu)

    def start(self, job="SDJ-1", **kw):
        self.assertTrue(self.sched.take_for_job(job, 5)["granted"])
        return self.sched.ensure_server(resolution(**kw), run_id=job)

    def router(self, adapter):
        router = ModelRouter()
        router.register(adapter)
        router.slot_guard = SlotGuard(self.sched, wait_s=0)
        return router


MSG = [{"role": "user", "content": "hi"}]


class RouterHookTests(Base):
    def test_a_direct_call_takes_a_slot_around_the_request_and_gives_it_back(self):
        self.start()
        adapter = FakeAdapter(self.sched)
        self.assertEqual(self.router(adapter).chat("M-1", MSG)["content"], "ok")
        self.assertEqual(len(adapter.seen[0]), 2)                                    # the starter's lease and the direct call's
        self.assertTrue(adapter.seen[0][1][0].startswith("direkt-"))
        self.assertEqual(len(self.sched.view()["belegt"]), 1)
        self.assertEqual(self.sched._direct, set())
        self.assertEqual(adapter.kwargs, [{}])                                       # run_id and slot_owner never reach the provider

    def test_the_captain_chat_has_priority_7_everybody_else_5(self):
        self.start()
        adapter = FakeAdapter(self.sched)
        router = self.router(adapter)
        router.chat("M-1", MSG, slot_owner="captain-chat")
        router.chat("M-1", MSG)
        self.assertEqual([seen[1][1] for seen in adapter.seen], [7, 5])

    def test_a_mission_that_already_holds_a_lease_takes_nothing_more(self):
        self.start()
        adapter = FakeAdapter(self.sched)
        router = self.router(adapter)
        router.chat("M-1", MSG, run_id="SDJ-1")
        router.chat("SDJ-1", MSG)                                                    # the mission id is the job id
        self.assertEqual(adapter.seen, [[("SDJ-1", 5)], [("SDJ-1", 5)]])

    def test_waiting_longer_than_wait_s_is_a_clear_error_with_the_reason(self):
        self.start()
        self.sched.take_for_job("SDJ-2", 5)                                           # both slots taken
        adapter = FakeAdapter(self.sched)
        with self.assertRaisesRegex(ModelAdapterError, "^slot_wait_timeout:kein_slot$"):
            self.router(adapter).chat("M-1", MSG)
        self.assertEqual(adapter.seen, [])                                           # the request never went out
        self.assertEqual(self.sched.view()["schlange"], [])

    def test_a_call_cannot_start_the_server(self):
        with self.assertRaisesRegex(ModelAdapterError, "^server_aus$"):
            self.router(FakeAdapter(self.sched)).chat("M-1", MSG)
        self.assertEqual(self.loader.loaded, [])

    def test_off_cloud_and_other_adapters_are_untouched(self):
        self.start()
        plain, adapter = ModelRouter(), FakeAdapter(self.sched)                       # slot_guard is None: as before
        plain.register(adapter)
        plain.chat("M-1", MSG)
        self.assertEqual(adapter.seen, [[("SDJ-1", 5)]])
        for other in (FakeAdapter(self.sched, id="cloud-x", route="cloud"), FakeAdapter(self.sched, id="lmstudio")):
            self.router(other).chat("M-1", MSG, provider=other.id)
            self.assertEqual(other.seen, [[("SDJ-1", 5)]])

    def test_a_disabled_scheduler_adds_nothing(self):
        sched, *_ = make_scheduler(self.tmp.name + "-off", enabled=False)
        adapter, router = FakeAdapter(), ModelRouter()
        router.register(adapter)
        router.slot_guard = SlotGuard(sched, wait_s=0)
        self.assertEqual(router.chat("M-1", MSG)["content"], "ok")


class FakeRoleRouter:
    def resolve_recipe(self, recipe_id):
        return resolution(recipe=recipe_id)


class WorkshopTests(Base):
    """`model laden` / `entladen` of the workshop with the scheduler on: no lease and no beat of the UIX process (D2.6)."""

    def setUp(self):
        super().setUp()
        audit = SimpleNamespace(append=lambda *a, **k: None)
        self.rt = SimpleNamespace(model_scheduler=self.sched, role_router=FakeRoleRouter(), model_loader=self.loader, audit=audit,
                                  llama_server=None, project_root=Path(self.tmp.name))
        hub = object.__new__(UIXHub)
        hub.runtime, hub.lab, hub.model_lock = self.rt, self.lab, threading.Lock()
        hub.gpu_token, hub._beat_stop = None, None
        hub._start_lease_beat = lambda: self.fail("the workshop must not start a lease beat of its own")
        self.hub = hub

    def test_load_goes_through_ensure_server_and_the_hub_holds_no_lease(self):
        out = self.hub.load_model({"recipe_id": "main.local"})
        self.assertEqual((out["recipe_id"], out["action"]), ("main.local", "loaded"))
        self.assertEqual(self.loader.loaded, [("main.local", 2, 32768)])
        self.assertEqual(self.lab.holder()["owner"], self.sched.owner)               # the scheduler holds `gpu`, not 'guppi-uix'
        self.assertIsNone(self.hub.gpu_token)
        self.assertTrue(self.hub._lease_is_mine(self.lab.holder()))
        self.assertEqual(self.audit.of("SLOT_SERVER_STARTED")[0]["asked_by"], "werkstatt")
        self.assertEqual(self.hub.load_model({"recipe_id": "main.local"})["action"], "reused")
        self.assertEqual(len(self.loader.loaded), 1)

    def test_a_refusal_of_the_scheduler_reaches_the_captain_as_its_reason(self):
        self.assertTrue(self.lab.try_acquire("benchmark", "context ladder"))
        with self.assertRaisesRegex(ValueError, "^gpu_lease_busy:benchmark:context ladder$"):
            self.hub.load_model({"recipe_id": "main.local"})
        self.assertEqual(self.loader.loaded, [])

    def test_unload_hints_at_active_runs_and_only_erzwingen_interrupts_them(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "^leases_active:SDJ-1$"):
            self.hub.unload_model({})
        self.assertEqual(self.loader.unloaded, [])
        out = self.hub.unload_model({"erzwingen": True})
        self.assertEqual((out["status"], out["interrupted"]), ("unloaded", ["SDJ-1"]))
        self.assertEqual(self.loader.unloaded, ["main.local"])
        self.assertIsNone(self.lab.holder())                                          # lease given back
        with self.lab._db() as db:
            self.assertEqual(db.execute("SELECT state FROM slot_leases WHERE run_id='SDJ-1'").fetchone()["state"], "unterbrochen")

    def test_unload_without_runs_stops_the_server_at_once(self):
        self.hub.load_model({"recipe_id": "main.local"})
        self.assertEqual(self.hub.unload_model({})["status"], "unloaded")
        self.assertIsNone(self.lab.holder())

    def test_another_recipe_replaces_the_running_one_only_without_active_runs(self):
        from guppi_runtime import uix_server
        real = uix_server.time.sleep
        uix_server.time.sleep = lambda s: None
        self.addCleanup(lambda: setattr(uix_server.time, "sleep", real))
        self.start()
        with self.assertRaisesRegex(ValueError, "^leases_active:SDJ-1$"):
            self.hub.load_model({"recipe_id": "other.local"})
        self.sched.release("SDJ-1")
        self.hub.load_model({"recipe_id": "other.local"})
        self.assertEqual((self.loader.unloaded, self.loader.loaded[-1][0]), (["main.local"], "other.local"))

    def test_without_the_scheduler_the_workshop_keeps_its_own_path(self):
        self.rt.model_scheduler = None
        self.assertIsNone(self.hub._scheduler())
        off, *_ = make_scheduler(self.tmp.name + "-off", enabled=False)
        self.rt.model_scheduler = off
        self.assertIsNone(self.hub._scheduler())                                       # present but off: as before (D2.1)

    def test_the_runtime_wires_the_guard_next_to_the_supervisor(self):
        import inspect
        from guppi_runtime import runtime
        source = inspect.getsource(runtime.GuppiRuntime._configure_model_scheduler).replace(" ", "")
        self.assertIn("self.model_router.slot_guard=SlotGuard(", source)
        self.assertIn("job_supervisor.slots=self.model_scheduler", source)


if __name__ == "__main__":
    unittest.main()
