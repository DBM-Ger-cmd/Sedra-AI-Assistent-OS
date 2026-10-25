"""Settings of the model scheduler (Spec 2, D2.11): config/model_scheduler.yaml plus the machine overlay local_config/model_scheduler.yaml."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

OVERLAY_KEYS = frozenset({"enabled", "swap", "queue_max", "wait_max_s", "slots_cap_by_profile"})
STANDARD_SLOT_KEYS = ("hauptmodell", "hilfsmodell")
# Until S2.H5 nothing calls `poll()` (waiting benchmarks would never be served) and uix_server still holds its own GPU lease (the
# scheduler would only see gpu_lease_busy). The loader therefore refuses `enabled: true`; tests build the config directly.
ENABLE_LOCK = "model_scheduler_locked_until_s2h5"


class ModelSchedulerConfig:
    """Validated settings (D2.11). Invalid values refuse start; nothing is clamped."""

    def __init__(self, raw):
        if not isinstance(raw, dict):
            raise ValueError("model_scheduler_config_invalid")
        self.raw = deepcopy(raw)
        self.enabled = raw.get("enabled", False)
        if not isinstance(self.enabled, bool):
            raise ValueError("model_scheduler_config_invalid:enabled")
        limit = raw.get("vram_limit_gb", 11.5)
        if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not 1 <= limit <= 1024:
            raise ValueError("model_scheduler_config_invalid:vram_limit_gb")
        self.vram_limit_gb = float(limit)
        prio = raw.get("priorities", {"captain": 7, "agent": 5, "routine": 3})
        if not isinstance(prio, dict) or set(prio) != {"captain", "agent", "routine"} \
                or any(type(v) is not int or not 0 <= v <= 7 for v in prio.values()) or not prio["captain"] > prio["agent"] > prio["routine"]:
            raise ValueError("model_scheduler_config_invalid:priorities")      # below critical.min_priority 8, Captain > Agent > Routine
        self.priorities = dict(prio)
        self.age_after_s = self._int(raw, "age_after_s", 120, 1, 86400)
        self.age_cap = self._int(raw, "age_cap", 5, 0, 9)
        if self.age_cap >= self.priorities["captain"]:
            raise ValueError("model_scheduler_config_invalid:age_cap")         # ageing never reaches the Captain's step
        self.wait_max_s = self._int(raw, "wait_max_s", 600, 0, 86400)
        self.queue_max = self._int(raw, "queue_max", 6, 0, 1000)
        self.offer_every_s = self._int(raw, "offer_every_s", 900, 1, 86400)
        self.drain_max_s = self._int(raw, "drain_max_s", 1800, 0, 86400)
        self.slot_ttl_s = self._int(raw, "slot_ttl_s", 120, 1, 86400)
        self.poll_s = self._int(raw, "poll_s", 2, 1, 3600)
        restart = raw.get("restart", {})
        garbage = raw.get("garbage", {})
        if not isinstance(restart, dict) or not isinstance(garbage, dict):
            raise ValueError("model_scheduler_config_invalid:restart")
        self.restart_max = self._int(restart, "max", 3, 0, 100, "restart.max")
        self.restart_window_s = self._int(restart, "window_s", 600, 1, 86400, "restart.window_s")
        self.garbage_count = self._int(garbage, "count", 2, 1, 100, "garbage.count")
        self.garbage_window_s = self._int(garbage, "window_s", 300, 1, 86400, "garbage.window_s")
        swap = raw.get("swap", "none")
        if not (swap in ("none", "idle") or (isinstance(swap, dict) and set(swap) == {"fallback"} and isinstance(swap["fallback"], str) and swap["fallback"])):
            raise ValueError("model_scheduler_config_invalid:swap")
        self.swap = deepcopy(swap)
        caps = raw.get("slots_cap_by_profile", {})
        if not isinstance(caps, dict) or any(not isinstance(k, str) or type(v) is not int or not 1 <= v <= 8 for k, v in caps.items()):
            raise ValueError("model_scheduler_config_invalid:slots_cap_by_profile")
        self.slots_cap_by_profile = dict(caps)
        standard = raw.get("standard_slots", {})
        if not isinstance(standard, dict) or set(standard) - set(STANDARD_SLOT_KEYS) or any(type(v) is not int or not 1 <= v <= 8 for v in standard.values()):
            raise ValueError("model_scheduler_config_invalid:standard_slots")
        self.standard_slots = dict(standard)

    @staticmethod
    def _int(section, key, default, low, high, name=None):
        value = section.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"model_scheduler_config_invalid:{name or key}")
        return value

    def plan(self):
        """The settings of the pure functions (slotplan, slot_store)."""
        return {"age_after_s": self.age_after_s, "age_cap": self.age_cap, "swap": deepcopy(self.swap),
                "queue_max": self.queue_max, "wait_max_s": self.wait_max_s}

    def priority(self, origin):
        """Captain 7, Agent 5, Routine 3 (G2-S2-12)."""
        if origin not in self.priorities:
            raise ValueError("origin_invalid")
        return self.priorities[origin]

    @classmethod
    def load(cls, path, overlay=None):
        """The repo file plus the machine overlay, which may change only `OVERLAY_KEYS` (D2.11)."""
        path = Path(path)
        if not path.exists():
            raise ValueError("model_scheduler_config_missing")
        try:
            raw = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("model_scheduler") or {}
        except yaml.YAMLError:
            raise ValueError("model_scheduler_config_invalid:yaml") from None
        if overlay is not None and Path(overlay).exists():
            try:
                extra = (yaml.safe_load(Path(overlay).read_text(encoding="utf-8")) or {}).get("model_scheduler") or {}
            except yaml.YAMLError:
                raise ValueError("model_scheduler_config_invalid:overlay") from None
            if not isinstance(extra, dict):
                raise ValueError("model_scheduler_config_invalid:overlay")
            for key in extra:
                if key not in OVERLAY_KEYS:
                    raise ValueError(f"model_scheduler_config_invalid:overlay:{key}")
            raw = {**raw, **extra}
        config = cls(raw)
        if config.enabled:
            raise ValueError(ENABLE_LOCK)
        return config
