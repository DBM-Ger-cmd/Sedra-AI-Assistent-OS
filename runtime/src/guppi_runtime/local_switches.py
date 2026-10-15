"""Machine-local feature switches (Phase 8e).

The shipped configs keep every Phase 2-8 feature OFF, so a fresh package behaves like v1.20 and the shipped-config tests stay true.
The Captain turns features on for THIS machine in `<project>/local_config/switches.yaml`, next to the routing overlay. The file may
only flip the listed booleans of the listed sections; anything else is refused and the runtime starts without any switch applied
(it never half-applies a broken file) and says why.

    switches:
      job_supervisor:    {enabled: true}
      context_manager:   {enabled: true}
      resource_scheduler: {enabled: true}
      model_loader:      {enabled: true, evict_idle_models: true}
      llama_server:      {enabled: true, mtp: true}
      token_policy:      {enabled: true}

`role_routing` is switched in its own overlay (`local_config/role_routing.yaml`), which already exists for the recipes.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ALLOWED = {
    "job_supervisor": {"enabled"},
    "context_manager": {"enabled"},
    "resource_scheduler": {"enabled"},
    "model_loader": {"enabled", "evict_idle_models"},
    "llama_server": {"enabled", "mtp"},
    "token_policy": {"enabled"},
}


class LocalSwitches:
    def __init__(self, values=None, source=None):
        self.values = values or {}
        self.source = source

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            return cls()
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ValueError("local_switches_invalid:yaml") from exc
        if not isinstance(data, dict) or set(data) - {"switches"}:
            raise ValueError("local_switches_invalid:top_level")
        switches = data.get("switches") or {}
        if not isinstance(switches, dict):
            raise ValueError("local_switches_invalid:switches")
        clean = {}
        for section, item in switches.items():
            if section not in ALLOWED:
                raise ValueError(f"local_switches_invalid:unknown_section:{section}")
            if not isinstance(item, dict) or set(item) - ALLOWED[section]:
                raise ValueError(f"local_switches_invalid:unknown_key:{section}")
            for key, value in item.items():
                if not isinstance(value, bool):
                    raise ValueError(f"local_switches_invalid:not_boolean:{section}.{key}")
            clean[section] = dict(item)
        return cls(clean, str(path))

    def apply(self, section, key, shipped):
        """The machine's value if the file sets it, else the shipped one."""
        return self.values.get(section, {}).get(key, shipped)

    def summary(self):
        return {"source": self.source, "values": {k: dict(v) for k, v in self.values.items()}}
