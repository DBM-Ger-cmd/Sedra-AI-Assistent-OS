"""Spec 2: the second job on a running server (found by the agent run probe, 26.10.2026). The server holds the card and its own ledger entry
`server:<recipe>`; the role resolution of the second job (`load_check`) must not count them as a rival, or it ends in `hardware_pressure`."""
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import yaml

from guppi_runtime.jobs.resource_scheduler import ResourceConfig, ResourceScheduler
from guppi_runtime.runtime import GuppiRuntime
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests
from model_scheduler_fakes import make_scheduler, resolution

CONFIG = Path(__file__).resolve().parents[1] / "config" / "resource_scheduler.yaml"


def metric(value):
    return {"value": value, "unit": "GiB", "source": "test", "state": "valid"}


class Hardware:
    """A 16 GiB card; `used` is what the running server holds."""
    def __init__(self):
        self.used = 0.0
        self.profile = {"ram_reserve_gib": 2.0, "max_jobs": 2}

    def get_state(self, fresh=False):
        return deepcopy({"thermal_state": "NORMAL", "memory": {"total": metric(64.0), "available": metric(60.0)},
                         "gpus": [{"device_id": "GPU-0", "vram_total": metric(16.0), "vram_available": metric(16.0 - self.used)}]})

    def active_profile(self):
        return dict(self.profile)


class SecondJob(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["resource_scheduler"]
        raw.update(enabled=True, vram_reserve_gb=1.0)
        self.hw = Hardware()
        self.resources = ResourceScheduler(ResourceConfig(raw), self.hw, Path(tmp.name) / "ledger.json", clock=lambda: datetime(2026, 10, 26, 12, tzinfo=timezone.utc))
        self.sched, self.lab, self.loader, self.runtime, self.audit, self.clock = make_scheduler(tmp.name, resources=self.resources)
        self.addCleanup(self.sched._release_gpu)
        self.res = resolution()
        self.recipe = {"id": "main.local", "model": "main-model"}
        self.estimated = self.res["estimated_resources"]
        # what GuppiRuntime._resource_load_check reads; the loader says the model is on the card
        self.rt = SimpleNamespace(resource_scheduler=self.resources, model_scheduler=self.sched,
                                  model_loader=SimpleNamespace(enabled=True, loaded=lambda key: key == "main-model"))

    def check(self):
        return GuppiRuntime._resource_load_check(self.rt, self.recipe, self.estimated, {"exclusive": False})

    def start_server(self):
        self.assertTrue(self.sched.take_for_job("SDJ-1", 5)["granted"])
        self.sched.ensure_server(self.res, run_id="SDJ-1")
        self.hw.used = 9.2                                    # the card now holds the server

    def test_the_room_check_of_the_first_job_passes_on_a_free_card(self):
        self.assertIsNone(self.check())

    def test_the_server_is_not_a_rival_of_the_second_job(self):
        self.start_server()
        self.assertEqual(self.resources.explain(self.estimated, resident_vram_gb=8.0), "vram_insufficient")     # the defect: its own ledger entry counts
        self.assertEqual(self.sched.reservation_for("main.local"), "server:main.local")
        self.assertIsNone(self.check())

    def test_another_recipe_or_a_server_that_is_not_up_keeps_the_check_strict(self):
        self.assertIsNone(self.sched.reservation_for("main.local"))
        self.start_server()
        self.assertIsNone(self.sched.reservation_for("other.local"))
        self.recipe = {"id": "other.local", "model": "other-model"}
        self.assertIsNotNone(self.check())                    # a different model does not fit next to the server
        self.sched.stop_server(force=True)
        self.assertIsNone(self.sched.reservation_for("main.local"))

    def test_the_second_job_gets_its_slot_on_the_running_server(self):
        self.start_server()
        self.assertIsNone(self.check())
        self.assertTrue(self.sched.take_for_job("SDJ-2", 5)["granted"])
        out = self.sched.ensure_server(self.res, run_id="SDJ-2")
        self.assertEqual(out["action"], "reused")


if __name__ == "__main__":
    unittest.main()
