"""Fakes for the model scheduler tests (Spec 2): no model, no GPU, no process. A loader that records what it would load, a runtime that
says whether "its" server runs, and a resolution shaped like role_routing's."""
from pathlib import Path

import yaml

from guppi_runtime.jobs.model_scheduler import ModelScheduler, ModelSchedulerConfig
from guppi_runtime.jobs.testlab import TestLab
from guppi_runtime.models.model_loader import LoadError

RUNTIME = Path(__file__).resolve().parents[1]
CONFIG = RUNTIME / "config" / "model_scheduler.yaml"


def raw_config(**overrides):
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["model_scheduler"]
    raw["enabled"] = True
    raw.update(overrides)
    return raw


class Clock:
    """Epoch seconds for the test lab; 1792800000 is 2026-10-24T00:00:00Z."""
    def __init__(self, t=1792800000.0):
        self.t = t

    def __call__(self):
        return self.t


class FakeLoader:
    enabled = True

    def __init__(self):
        self.loaded, self.unloaded, self.fail = [], [], None

    def ensure(self, resolution):
        if self.fail:
            raise LoadError("provider_unavailable", self.fail)
        self.loaded.append((resolution["capability_id"], resolution.get("slots"), resolution["context_window"]))
        return {"identifier": resolution["model"], "context_length": resolution["context_window"], "action": "loaded", "estimate_gib": None}

    def unload(self, resolution):
        self.unloaded.append(resolution["capability_id"])
        return [resolution["model"]]


class FakeRuntime:
    def __init__(self):
        self.running = True

    def status(self):
        return {"running": self.running, "pid": 4242 if self.running else None}


class FakeAudit:
    def __init__(self):
        self.entries = []

    def append(self, event, component=None, payload=None, **_):
        self.entries.append((event, component, dict(payload or {})))

    def of(self, event):
        return [p for e, _, p in self.entries if e == event]


def resolution(recipe="main.local", slots=2, window=32768, vram_gb=8.0, kv_gb=1.0, placement="gpu", model="main-model"):
    """`kv_gb` is the KV cache of ALL slots, as role_routing estimates it (window x slots)."""
    return {"capability_id": recipe, "provider_ref": "llama-cpp-server", "model": model, "context_window": window, "slots": slots,
            "estimated_resources": {"ram_gb": 1.0, "vram_gb": vram_gb, "kv_cache_gb": kv_gb, "kv_cache_placement": placement, "complete": True},
            "independence_key": recipe, "capability_version": 1}


def make_scheduler(root, clock=None, *, pid=111, alive=None, **overrides):
    clock = clock or Clock()
    lab = TestLab(Path(root) / "testlab.db", clock=clock, alive=alive or (lambda p: True), pid=pid)
    loader, runtime, audit = FakeLoader(), FakeRuntime(), FakeAudit()
    profile = overrides.pop("profile", None)
    resources = overrides.pop("resources", None)
    sched = ModelScheduler(ModelSchedulerConfig(raw_config(**overrides)), lab, loader=loader, runtime=runtime, audit=audit,
                           resources=resources, profile=profile)
    return sched, lab, loader, runtime, audit, clock
