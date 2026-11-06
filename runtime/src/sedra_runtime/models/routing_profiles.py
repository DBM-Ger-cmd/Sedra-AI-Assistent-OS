"""Switchable model combinations for the role router (2026-10-03, Captain: "setze die Vorschläge in ein Profil um, damit man die
Modellkombination ändern kann").

A profile says, per purpose, which recipes the router should PREFER. Purposes are role names ("coder", "verifier", ...) plus "rework"
(the coder that repairs a candidate after a failed VM test). A purpose may carry sampling for that use (`reasoning_effort`,
`temperature`). Nothing here weakens a rule: every preferred recipe still goes through all router checks (enabled, trust, hardware,
health, independence); recipes that are not listed stay behind the listed ones as the fallback. A profile may name a recipe for a
role the recipe does not declare (e.g. gemma as coder) - that is the point of a combination - but only recipes that exist.

    local_config/routing_profiles.yaml
        active: standard
        profiles:
          standard:
            description: ...
            coder:    {prefer: [coder.local_primary]}
            rework:   {prefer: [coder.llama_gptoss], reasoning_effort: medium, temperature: 1.0}
            verifier: {prefer: [verifier.llama_gemma]}
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from ..core.util import atomic_write_text

NAME_RE = re.compile(r"[a-z][a-z0-9_-]{0,39}")
PURPOSE_KEYS = {"prefer", "reasoning_effort", "temperature"}
EFFORTS = {"none", "low", "medium", "high"}


class ProfileError(ValueError):
    pass


def _check_purpose(name, purpose, entry):
    if not isinstance(entry, dict) or set(entry) - PURPOSE_KEYS:
        raise ProfileError(f"routing_profile_invalid:{name}.{purpose}")
    prefer = entry.get("prefer", [])
    if not isinstance(prefer, list) or any(not isinstance(p, str) or not p for p in prefer) or len(set(prefer)) != len(prefer):
        raise ProfileError(f"routing_profile_invalid:{name}.{purpose}.prefer")
    if "reasoning_effort" in entry and entry["reasoning_effort"] not in EFFORTS:
        raise ProfileError(f"routing_profile_invalid:{name}.{purpose}.reasoning_effort")
    t = entry.get("temperature")
    if t is not None and (isinstance(t, bool) or not isinstance(t, (int, float)) or not 0 <= t <= 2):
        raise ProfileError(f"routing_profile_invalid:{name}.{purpose}.temperature")


class RoutingProfiles:
    def __init__(self, raw, path=None, known_ids=None):
        self.path = Path(path) if path else None
        raw = raw or {}
        if not isinstance(raw, dict) or set(raw) - {"active", "profiles"}:
            raise ProfileError("routing_profiles_invalid")
        profiles = raw.get("profiles") or {}
        if not isinstance(profiles, dict):
            raise ProfileError("routing_profiles_invalid:profiles")
        for name, prof in profiles.items():
            if not isinstance(name, str) or not NAME_RE.fullmatch(name) or not isinstance(prof, dict):
                raise ProfileError(f"routing_profile_invalid:{name}")
            for purpose, entry in prof.items():
                if purpose == "description":
                    if not isinstance(entry, str):
                        raise ProfileError(f"routing_profile_invalid:{name}.description")
                    continue
                if not NAME_RE.fullmatch(str(purpose)):
                    raise ProfileError(f"routing_profile_invalid:{name}.{purpose}")
                _check_purpose(name, purpose, entry)
                if known_ids is not None:
                    unknown = [p for p in entry.get("prefer", []) if p not in known_ids]
                    if unknown:
                        raise ProfileError(f"routing_profile_unknown_recipe:{name}.{purpose}:{unknown[0]}")
        active = raw.get("active")
        if active is not None and active not in profiles:
            raise ProfileError(f"routing_profile_active_unknown:{active}")
        self.profiles, self.active = profiles, active

    @classmethod
    def load(cls, path, known_ids=None):
        path = Path(path)
        if not path.exists():
            return cls({}, path, known_ids)          # no file: no profile, the router keeps its recipe order
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ProfileError("routing_profiles_unreadable") from exc
        return cls(raw, path, known_ids)

    def purpose(self, purpose):
        """The active profile's entry for a purpose ({"prefer": [...], ...}) or {}."""
        if not self.active:
            return {}
        return dict(self.profiles[self.active].get(purpose) or {})

    def prefer(self, purpose):
        return list(self.purpose(purpose).get("prefer") or [])

    def view(self):
        return {"active": self.active, "profiles": {n: {k: v for k, v in p.items()} for n, p in self.profiles.items()}}

    def use(self, name):
        """Make `name` the active profile and write it back (the rest of the file is kept as it is)."""
        if name not in self.profiles:
            raise ProfileError(f"routing_profile_unknown:{name}")
        if self.path is None:
            raise ProfileError("routing_profiles_have_no_file")
        text = self.path.read_text(encoding="utf-8")
        new, n = re.subn(r"(?m)^active:\s*\S+\s*$", f"active: {name}", text, count=1)
        if n == 0:
            new = f"active: {name}\n" + text
        atomic_write_text(self.path, new)
        self.active = name
        return self.view()
