"""Role -> capability -> provider resolution and provider health (Phase 5).

GUPPI asks for a role with requirements; the Control Master resolves it here, against declarative recipes in
config/role_routing.yaml. This module
 - never names a provider or model (they are data in the recipes),
 - never loosens a requirement or a policy while looking for an alternative,
 - treats a missing or unprovable independence key as "not independent", never as "independent",
 - changes nothing unless `role_routing.enabled` is true.
Contract: docs/JOB_SUPERVISOR_CONTRACTS.md sections 8 and 9.
"""
from __future__ import annotations

import re
import threading
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from ..models.hardware_pass import HardwareModelPass
from ..core.util import append_lock, atomic_write_json, load_json, utcnow

TRUST_LEVELS = ("BUILT_IN", "KNOWN_GOOD", "CAPTAIN_CUSTOM", "GUPPI_GENERATED", "EXTERNAL_UNVERIFIED")
NEVER_IN_POLICY = frozenset({"GUPPI_GENERATED", "EXTERNAL_UNVERIFIED"})
NETWORK_RANK = {"denied": 0, "local": 1, "allowed": 2}            # higher = looser
DATA_RANK = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}   # higher = stricter
REQUIREMENT_KEYS = frozenset({"offline_preferred", "max_vram_gb", "max_ram_gb", "filesystem_scope", "network", "test_required",
                              "data_class", "context_min_tokens", "exclusive", "permission_level"})
RESOLUTION_CODES = ("no_capability", "requirements_unmet", "policy_denied", "hardware_pressure", "provider_unavailable")
HEALTH_STATES = ("HEALTHY", "DEGRADED", "COOLDOWN", "UNAVAILABLE")
# Failure classes that are the provider's fault. Policy, test, validation and context failures are not.
PROVIDER_FAULTS = frozenset({"transient_provider_error", "timeout", "rate_limit", "runtime_crash", "model_unavailable"})
ID_RE = re.compile(r"[a-z][a-z0-9_.-]{0,80}")


class ResolutionError(Exception):
    def __init__(self, code, detail=None):
        considered = (detail or {}).get("considered") or []
        profile_changed = code == "hardware_pressure" and any(c.get("reason") == "hardware_profile_changed" for c in considered)
        super().__init__(code + ":hardware_profile_changed" if profile_changed else code)   # the window explains this one in its own words
        self.code = code
        self.detail = detail


# --------------------------------------------------------------------------- configuration

class RoutingConfig:
    def __init__(self, raw):
        if not isinstance(raw, dict):
            raise ValueError("role_routing_config_invalid")
        self.enabled = raw.get("enabled", False)
        if not isinstance(self.enabled, bool):
            raise ValueError("role_routing_config_invalid:enabled")
        policy = raw.get("policy") or {}
        levels = policy.get("allowed_trust_levels", ["BUILT_IN", "KNOWN_GOOD", "CAPTAIN_CUSTOM"])
        if not isinstance(levels, list) or not levels or any(x not in TRUST_LEVELS for x in levels):
            raise ValueError("role_routing_config_invalid:allowed_trust_levels")
        if NEVER_IN_POLICY & set(levels):
            raise ValueError("role_routing_config_invalid:untrusted_levels_cannot_be_allowed")
        self.allowed_trust = frozenset(levels)
        self.cloud_allowed = policy.get("cloud_allowed", False)
        if not isinstance(self.cloud_allowed, bool):
            raise ValueError("role_routing_config_invalid:cloud_allowed")
        health = raw.get("provider_health") or {}
        self.degraded_after = self._int(health, "degraded_after", 2, 1, 100)
        self.cooldown_after = self._int(health, "cooldown_after", 3, 1, 100)
        self.base_cooldown_s = self._int(health, "base_cooldown_s", 30, 1, 86400)
        self.max_cooldown_s = self._int(health, "max_cooldown_s", 600, 1, 86400 * 7)
        if self.degraded_after > self.cooldown_after or self.base_cooldown_s > self.max_cooldown_s:
            raise ValueError("role_routing_config_invalid:provider_health_order")
        caps = raw.get("capabilities") or []
        if not isinstance(caps, list):
            raise ValueError("role_routing_config_invalid:capabilities")
        self.recipes, seen = [], set()
        for item in caps:
            recipe = self._recipe(item)
            if recipe["id"] in seen:
                raise ValueError(f"role_routing_config_invalid:duplicate_capability:{recipe['id']}")
            seen.add(recipe["id"])
            self.recipes.append(recipe)

    @staticmethod
    def _int(section, key, default, low, high):
        value = section.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"role_routing_config_invalid:{key}")
        return value

    @staticmethod
    def _number(section, key, default, low=0):
        value = section.get(key, default)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < low:
            raise ValueError(f"role_routing_config_invalid:{key}")
        return float(value)

    def _recipe(self, item):
        if not isinstance(item, dict):
            raise ValueError("role_routing_config_invalid:capability")
        cid = item.get("id")
        if not isinstance(cid, str) or not ID_RE.fullmatch(cid):
            raise ValueError("role_routing_config_invalid:capability_id")
        fail = lambda why: ValueError(f"role_routing_config_invalid:{cid}:{why}")
        roles = item.get("roles")
        if not isinstance(roles, list) or not roles or any(not isinstance(r, str) or not r for r in roles):
            raise fail("roles")
        for key in ("provider", "model_family"):
            if not isinstance(item.get(key), str) or not item[key]:
                raise fail(key)
        for key in ("model", "weights_id"):
            if item.get(key) is not None and not isinstance(item[key], str):
                raise fail(key)
        location = item.get("location", "local")
        if location not in {"local", "cloud"}:
            raise fail("location")
        requirements = item.get("requirements") or {}
        permissions = item.get("permissions") or {}
        level = permissions.get("max_level", 0)
        if type(level) is not int or not 0 <= level <= 6:
            raise fail("permissions.max_level")
        network = item.get("network") or {}
        if not isinstance(network.get("allowed", False), bool):
            raise fail("network.allowed")
        metadata = item.get("metadata") or {}
        trust = metadata.get("trust_level")
        if trust not in TRUST_LEVELS:
            raise fail("metadata.trust_level")
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise fail("enabled")
        profile = item.get("profile") or {}
        if not isinstance(profile, dict):
            raise fail("profile")
        tiers = (profile.get("context") or {}).get("tiers") if isinstance(profile.get("context"), dict) else None
        if tiers is not None and (not isinstance(tiers, list) or not tiers or any(type(t) is not int or t <= 0 for t in tiers) or tiers != sorted(set(tiers))):
            raise fail("profile.context.tiers")
        server = profile.get("server")
        if server is not None:
            # How a GUPPI-managed local server is started for this recipe (see its runtime module). Structured, never free-form.
            if (not isinstance(server, dict) or set(server) - {"gguf", "kv_cache_type", "mmproj", "reasoning", "reasoning_budget", "mtp", "cache_ram", "ctx_checkpoints", "n_cpu_moe", "n_gpu_layers", "reasoning_format", "jinja", "ubatch", "mmap", "flash_attn", "slots"}
                    or server.get("reasoning_format", "auto") not in {"none", "deepseek", "deepseek-legacy", "auto"}
                    or not isinstance(server.get("jinja", True), bool)
                    or not isinstance(server.get("gguf"), str) or not server["gguf"]
                    or server.get("kv_cache_type", "f16") not in {"f16", "bf16", "q8_0", "q4_0"}
                    or server.get("reasoning", "auto") not in {"auto", "on", "off"}
                    or (server.get("reasoning_budget") is not None and (type(server["reasoning_budget"]) is not int or not -1 <= server["reasoning_budget"] <= 65536))
                    or not isinstance(server.get("mtp", False), bool)
                    or (server.get("ctx_checkpoints") is not None and (type(server["ctx_checkpoints"]) is not int or not 0 <= server["ctx_checkpoints"] <= 64))
                    or (server.get("n_gpu_layers") is not None and (type(server["n_gpu_layers"]) is not int or not 0 <= server["n_gpu_layers"] <= 999))
                    or (server.get("n_cpu_moe") is not None and (type(server["n_cpu_moe"]) is not int or not 0 <= server["n_cpu_moe"] <= 999))
                    or (server.get("slots") is not None and (type(server["slots"]) is not int or not 1 <= server["slots"] <= 8))
                    or not isinstance(server.get("mmap", True), bool)
                    or server.get("flash_attn", "on") not in {"on", "off", "auto"}
                    or (server.get("ubatch") is not None and (type(server["ubatch"]) is not int or not 64 <= server["ubatch"] <= 8192))
                    or (server.get("cache_ram") is not None and (type(server["cache_ram"]) is not int or not -1 <= server["cache_ram"] <= 262144))
                    or (server.get("mmproj") is not None and not isinstance(server["mmproj"], str))):
                raise fail("profile.server")
        per_slots = (profile.get("context") or {}).get("per_slots") if isinstance(profile.get("context"), dict) else None
        if per_slots is not None:
            # Window PER SLOT as measured for N slots ({N: window}); the numbers 1..8 (also above the recipe's own slot count: the measurement for 3 or 4 slots
            # is kept while the default stays at 2, 26.10.2026), never above the maximum, on a tier if tiers exist.
            maximum = (profile.get("context") or {}).get("maximum")
            if (not isinstance(per_slots, dict) or not per_slots
                    or any(type(n) is not int or not 1 <= n <= 8 or type(w) is not int or w <= 0 for n, w in per_slots.items())
                    or (type(maximum) is int and any(w > maximum for w in per_slots.values()))
                    or (tiers and any(w not in tiers for w in per_slots.values()))):
                raise fail("profile.context.per_slots")
        measured_context = item.get("measured_context")
        if measured_context is not None and (type(measured_context) is not int or measured_context <= 0):
            raise fail("measured_context")
        return {"id": cid, "version": item.get("version", 1), "enabled": enabled, "roles": list(roles), "provider": item["provider"],
                "model": item.get("model"), "model_family": item["model_family"], "weights_id": item.get("weights_id"), "location": location,
                "min_ram_gb": self._number(requirements, "min_ram_gb", 0), "min_vram_gb": self._number(requirements, "min_vram_gb", 0),
                "model_size_gb": self._number(item, "model_size_gb", None, low=0.001), "profile": deepcopy(profile),
                # KV cache depends on the model architecture, so it is declared per model, never guessed. None = unknown.
                "kv_cache_gb_per_1k_tokens": self._number(item, "kv_cache_gb_per_1k_tokens", None, low=0),
                # VRAM actually observed after loading this model with the profile's context. Never estimated lower than this.
                "measured_vram_gb": self._number(item, "measured_vram_gb", None, low=0),
                # The context window `measured_vram_gb` was observed at; with a KV rate it gives VRAM for any other window.
                "measured_context": measured_context,
                "max_level": level, "network_allowed": bool(network.get("allowed", False)), "tests": list(item.get("tests") or []),
                "rollback": bool((item.get("rollback") or {}).get("supported", False)), "source": str(metadata.get("source", "")),
                "trust_level": trust}

    @classmethod
    def load(cls, path, local_path=None):
        """The shipped file, optionally overlaid by a machine-specific file that lives with the project, not with the package.

        The overlay may change `enabled`, `policy` and `provider_health` keys, and add or replace capabilities by `id`. It is
        validated exactly like the shipped file, so it cannot allow untrusted levels or break a recipe.
        """
        path = Path(path)
        if not path.exists():
            raise ValueError("role_routing_config_missing")
        raw = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("role_routing") or {}
        if local_path is not None and Path(local_path).exists():
            try:
                local = (yaml.safe_load(Path(local_path).read_text(encoding="utf-8")) or {}).get("role_routing") or {}
            except yaml.YAMLError as exc:
                raise ValueError("role_routing_local_config_unreadable") from exc
            if not isinstance(local, dict) or set(local) - {"enabled", "policy", "provider_health", "capabilities"}:
                raise ValueError("role_routing_local_config_invalid")
            raw = dict(raw)
            for key in ("policy", "provider_health"):
                if key in local:
                    if not isinstance(local[key], dict):
                        raise ValueError(f"role_routing_local_config_invalid:{key}")
                    raw[key] = {**(raw.get(key) or {}), **local[key]}
            if "enabled" in local:
                raw["enabled"] = local["enabled"]
            if "capabilities" in local:
                if not isinstance(local["capabilities"], list) or any(not isinstance(c, dict) or "id" not in c for c in local["capabilities"]):
                    raise ValueError("role_routing_local_config_invalid:capabilities")
                replaced = {c["id"]: c for c in local["capabilities"]}
                merged = [replaced.pop(c.get("id"), c) for c in (raw.get("capabilities") or [])]
                raw["capabilities"] = merged + list(replaced.values())
        return cls(raw)


def _moe_offloaded(recipe):
    """True when the recipe keeps MoE expert weights in host RAM (server option `n_cpu_moe`)."""
    n = ((recipe.get("profile") or {}).get("server") or {}).get("n_cpu_moe")
    return type(n) is int and n > 0


def independence_key(recipe):
    """Family plus exact weights. Without a weights id there is nothing to compare, so no key."""
    return f"{recipe['model_family']}:{recipe['weights_id']}" if recipe.get("weights_id") else None


def check_independence(builder_key, verifier_key):
    """INDEPENDENT only when both identities are known and differ. Unknown is never independent."""
    if not builder_key or not verifier_key:
        return "UNVERIFIABLE"
    return "SAME" if builder_key == verifier_key else "INDEPENDENT"


# --------------------------------------------------------------------------- provider health

class ProviderHealth:
    """HEALTHY / DEGRADED / COOLDOWN / UNAVAILABLE per provider, persisted, with exponential cooldown.

    Only provider faults count (see PROVIDER_FAULTS). A cooldown that ends leaves the provider DEGRADED for one trial:
    a success makes it HEALTHY, another fault starts a longer cooldown.
    """

    def __init__(self, config, path=None, *, audit=None, clock=None):
        self.config, self.audit = config, audit
        self.path = Path(path) if path else None
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._memory = {}
        self._mem_lock = threading.RLock()

    # -- storage
    def _locked(self):
        return append_lock(self.path) if self.path else self._mem_lock

    def _read(self):
        if self.path is None:
            return self._memory
        try:
            data = load_json(self.path, {}) or {}
        except (ValueError, OSError):
            data = {}
        return data if isinstance(data, dict) else {}

    def _write(self, data):
        if self.path is None:
            self._memory = data
        else:
            atomic_write_json(self.path, data)

    def _entry(self, data, ref):
        return data.setdefault(ref, {"state": "HEALTHY", "consecutive_faults": 0, "cooldown_until": None, "cooldown_started": None, "last_class": None,
                                     "last_change": None, "faults_total": 0, "successes_total": 0})

    def _effective(self, entry, now):
        if entry["state"] == "COOLDOWN":
            until = datetime.fromisoformat(entry["cooldown_until"]) if entry["cooldown_until"] else now
            started = datetime.fromisoformat(entry["cooldown_started"]) if entry.get("cooldown_started") else None
            # The cooldown is over when its end has passed, or when the clock is found BEFORE its start (set backwards).
            # Ending early only grants one trial; a rewound clock must never keep a provider frozen.
            if now >= until or (started is not None and now < started):
                return "DEGRADED"
            return "COOLDOWN"
        return entry["state"]

    def _changed(self, ref, old, new, failure_class=None):
        if old != new and self.audit:
            self.audit.append("PROVIDER_HEALTH_CHANGED", component="role-routing",
                              payload={"provider_ref": ref, "from": old, "to": new, "failure_class": failure_class})

    # -- queries
    def state(self, ref):
        entry = self._read().get(ref)
        return "HEALTHY" if not entry else self._effective(entry, self._clock())

    def allows(self, ref):
        """Selectable now? DEGRADED is allowed (it is the trial after a cooldown)."""
        return self.state(ref) in {"HEALTHY", "DEGRADED"}

    def view(self):
        now = self._clock()
        return {ref: {**entry, "effective_state": self._effective(entry, now)} for ref, entry in self._read().items()}

    # -- reports
    def report_success(self, ref):
        with self._locked():
            data = self._read(); entry = self._entry(data, ref)
            old = self._effective(entry, self._clock())
            entry.update(state="HEALTHY", consecutive_faults=0, cooldown_until=None, last_change=utcnow())
            entry["successes_total"] += 1
            self._write(data)
        self._changed(ref, old, "HEALTHY")
        return "HEALTHY"

    def report_failure(self, ref, failure_class, *, retry_after_s=None):
        if failure_class not in PROVIDER_FAULTS:
            return self.state(ref)                         # not this provider's fault: no punishment
        now = self._clock()
        with self._locked():
            data = self._read(); entry = self._entry(data, ref)
            old = self._effective(entry, now)
            entry["consecutive_faults"] += 1; entry["faults_total"] += 1; entry["last_class"] = failure_class; entry["last_change"] = utcnow()
            cfg, n = self.config, entry["consecutive_faults"]
            trial_failed = entry["state"] == "COOLDOWN" and old == "DEGRADED"   # the one trial after a cooldown went wrong
            if failure_class == "model_unavailable":
                entry.update(state="UNAVAILABLE", cooldown_until=None)
            elif failure_class == "rate_limit":
                wait = min(max(int(retry_after_s or cfg.base_cooldown_s), 1), cfg.max_cooldown_s)
                entry.update(state="COOLDOWN", cooldown_until=(now + timedelta(seconds=wait)).isoformat(), cooldown_started=now.isoformat())
            elif failure_class == "runtime_crash" or trial_failed or n >= cfg.cooldown_after:
                steps = max(n - cfg.cooldown_after, 0) + (1 if trial_failed else 0)
                wait = min(cfg.base_cooldown_s * (2 ** steps), cfg.max_cooldown_s)
                entry.update(state="COOLDOWN", cooldown_until=(now + timedelta(seconds=wait)).isoformat(), cooldown_started=now.isoformat())
            elif n >= cfg.degraded_after:
                entry.update(state="DEGRADED")
            new = self._effective(entry, now)
            self._write(data)
        self._changed(ref, old, new, failure_class)
        return new

    def probe(self, ref, ok):
        """A health check result for a provider marked UNAVAILABLE: success allows one trial (DEGRADED)."""
        now = self._clock()
        with self._locked():
            data = self._read(); entry = self._entry(data, ref)
            old = self._effective(entry, now)
            if ok and entry["state"] == "UNAVAILABLE":
                entry.update(state="DEGRADED", cooldown_until=None, last_change=utcnow())
            self._write(data)
            new = self._effective(entry, now)
        self._changed(ref, old, new)
        return new


# --------------------------------------------------------------------------- resolution

class RoleRouter:
    def __init__(self, config, *, snapshot=None, health=None, audit=None, load_check=None, clock=None, profiles=None):
        self.config, self.snapshot, self.health, self.audit = config, snapshot, health, audit
        self.profiles = profiles            # routing_profiles.RoutingProfiles: the Captain's switchable model combination, or None
        self.load_check = load_check        # callable(recipe, estimated_resources, requirements) -> None | reason string
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def enabled(self):
        return self.config.enabled

    def recipes_for(self, role, purpose=None):
        """Recipes that declare the role, plus those the active profile prefers for this purpose (e.g. gemma as coder)."""
        prefer = set(self.prefer(role, purpose))
        return [r for r in self.config.recipes if role in r["roles"] or r["id"] in prefer]

    def prefer(self, role, purpose=None):
        return self.profiles.prefer(purpose or role) if self.profiles is not None else []

    # -- requirements
    @staticmethod
    def normalize(requirements):
        requirements = dict(requirements or {})
        unknown = sorted(set(requirements) - REQUIREMENT_KEYS)
        if unknown:
            raise ResolutionError("requirements_unmet", {"unsupported_requirements": unknown})   # never ignore what we cannot honour
        out = {"offline_preferred": True, "max_vram_gb": None, "max_ram_gb": None, "filesystem_scope": None, "network": "denied",
               "test_required": False, "data_class": "internal", "context_min_tokens": 0, "exclusive": False, "permission_level": 0}
        out.update(requirements)
        bad = []
        if out["network"] not in NETWORK_RANK: bad.append("network")
        if out["data_class"] not in DATA_RANK: bad.append("data_class")
        if type(out["permission_level"]) is not int or not 0 <= out["permission_level"] <= 6: bad.append("permission_level")
        if type(out["context_min_tokens"]) is not int or out["context_min_tokens"] < 0: bad.append("context_min_tokens")
        for key in ("max_vram_gb", "max_ram_gb"):
            if out[key] is not None and (isinstance(out[key], bool) or not isinstance(out[key], (int, float)) or out[key] < 0): bad.append(key)
        for key in ("offline_preferred", "test_required", "exclusive"):
            if not isinstance(out[key], bool): bad.append(key)
        if bad:
            raise ResolutionError("requirements_unmet", {"invalid_requirements": bad})
        return out

    # -- one candidate
    def _evaluate(self, recipe, req, *, exclude, independent_of, captain_cloud_approved, now):
        def no(category, reason): return {"capability_id": recipe["id"], "provider_ref": recipe["provider"], "category": category, "reason": reason}
        if not recipe["enabled"]:
            return None, no("static", "recipe_disabled")
        if recipe["trust_level"] not in self.config.allowed_trust:
            return None, no("policy", f"trust_level_not_allowed:{recipe['trust_level']}")
        if recipe["location"] == "cloud":
            if not self.config.cloud_allowed: return None, no("policy", "cloud_not_allowed")
            if not captain_cloud_approved: return None, no("policy", "cloud_needs_captain_approval")
            if DATA_RANK[req["data_class"]] >= DATA_RANK["confidential"]: return None, no("policy", "data_class_forbids_cloud")
        if req["network"] == "denied" and recipe["network_allowed"]:
            return None, no("policy", "network_not_denied")
        if req["network"] == "local" and recipe["location"] != "local":
            return None, no("policy", "location_not_local")
        if req["permission_level"] > recipe["max_level"]:
            return None, no("policy", "permission_level_exceeds_capability")
        snap = self.snapshot
        for need, cap, label in ((recipe["min_ram_gb"], req["max_ram_gb"], "ram"), (recipe["min_vram_gb"], req["max_vram_gb"], "vram")):
            if cap is not None and need and need > cap:
                return None, no("static", f"{label}_requirement_exceeds_limit")
        host = {"ram": getattr(snap, "ram_gb", None), "vram": getattr(snap, "vram_gb", None)}
        if recipe["location"] == "local":
            if host["ram"] is not None and recipe["min_ram_gb"] and host["ram"] < recipe["min_ram_gb"]:
                return None, no("static", "host_ram_below_minimum")
            if recipe["min_vram_gb"] and (host["vram"] or 0) < recipe["min_vram_gb"]:
                return None, no("static", "host_vram_below_minimum")
        context = int(((recipe["profile"].get("context") or {}).get("maximum")) or 0) or None
        working_context = int(((recipe["profile"].get("context") or {}).get("recommended")) or 0) or context   # what the job will actually run with
        if snap is not None and recipe["location"] == "local" and recipe["profile"]:
            result = HardwareModelPass(snap).evaluate(recipe["profile"], recipe["model_size_gb"])
            if result["status"] == "REVIEW":
                return None, no("static", "hardware_incompatible")
            context = result["context_limits"]["effective_maximum"]
            working_context = result["context_limits"]["recommended"]
        measured_max = int(((recipe["profile"].get("context") or {}).get("measured_maximum")) or 0) or None
        if measured_max and context is not None and context < measured_max:
            # The generic hardware-class cap is a rule of thumb; a window that was really loaded and measured on this machine
            # (declared by the Captain in the overlay) may raise it, but never above the recipe's own maximum.
            context = min(measured_max, int(((recipe["profile"].get("context") or {}).get("maximum")) or measured_max))
            # Die gemessene Grenze hebt auch das Fenster, das der Nutzer gewählt hat (context_recommended), sonst bliebe die
            # Schutzkappe des Hardware-Checks (32768) als Wunsch stehen, obwohl 64k gemessen und freigegeben ist.
            declared = int(((recipe["profile"].get("context") or {}).get("recommended")) or 0)
            if declared: working_context = min(declared, context)
        slots = int(((recipe["profile"].get("server") or {}).get("slots")) or 1)
        if slots > 1:
            # N slots share one server: the window each slot gets is the one MEASURED for N (no guessing); without it the start is refused.
            per_slot = ((recipe["profile"].get("context") or {}).get("per_slots") or {}).get(slots)
            if per_slot is None:
                return None, no("static", "slots_not_measured")
            context = min(context, per_slot) if context is not None else per_slot
            working_context = min(working_context, per_slot) if working_context else per_slot
        if req["context_min_tokens"] and (context is None or context < req["context_min_tokens"]):
            return None, no("static", "context_capacity")
        tiers = (recipe["profile"].get("context") or {}).get("tiers")
        loaded_context = None
        if tiers:
            # Context is a cost (VRAM, time): load the smallest tier that holds what the job needs, not the biggest that fits.
            need_tokens = max(req["context_min_tokens"] or 0, working_context or 0)
            fitting = [t for t in tiers if need_tokens <= t <= (context or 0)]
            if not fitting:
                return None, no("static", "context_capacity")
            loaded_context = fitting[0]
        key = independence_key(recipe)
        if recipe["provider"] in exclude or (key and key in exclude):
            return None, no("excluded", "excluded_by_caller")
        if independent_of:
            if any(k is None for k in independent_of) or key is None:
                return None, no("static", "independence_unverifiable")
            if key in independent_of:
                return None, no("static", "not_independent")
        if self.health is not None:
            state = self.health.state(recipe["provider"])
            if state in {"COOLDOWN", "UNAVAILABLE"}:
                return None, no("unavailable", f"provider_{state.lower()}")
        rate = recipe["kv_cache_gb_per_1k_tokens"]
        kv_context = (loaded_context or working_context)
        kv_context = kv_context * slots if kv_context else kv_context       # every slot holds its own window in the KV cache
        kv = round(rate * (kv_context or 0) / 1000, 3) if rate is not None and kv_context else None
        measured_context = recipe["measured_context"]
        if recipe["measured_vram_gb"] is not None and rate is not None and measured_context and kv_context:
            # The measurement already contains the KV cache of `measured_context`; only the difference is added on top.
            kv = round(max(0.0, rate * (kv_context - measured_context) / 1000), 3)
        placement = (recipe["profile"].get("kv_cache") or {}).get("placement") or ("gpu" if recipe["min_vram_gb"] else "cpu")
        size, layers = recipe["model_size_gb"], recipe["profile"].get("gpu_layers")
        gpu_resident = bool(size) and layers not in (None, 0, "0")            # weights live in VRAM, so they must be counted there
        if gpu_resident:
            ram_gb, vram_gb = recipe["min_ram_gb"] or round(size * 0.15, 2), max(recipe["min_vram_gb"], round(size * 1.05, 2))
            if recipe["measured_vram_gb"] is not None:
                if _moe_offloaded(recipe):
                    # Expert weights of the first n_cpu_moe layers stay in host RAM, so `size * 1.05` overstates VRAM; only the
                    # measurement (taken with that same offload) knows the real number.
                    vram_gb = recipe["measured_vram_gb"]
                else:
                    vram_gb = max(vram_gb, recipe["measured_vram_gb"])  # a measurement beats a rule of thumb, but only upwards
        else:
            ram_gb, vram_gb = (round(size * 1.2, 2) if size else recipe["min_ram_gb"]), recipe["min_vram_gb"]
        estimated = {"ram_gb": ram_gb, "vram_gb": vram_gb, "kv_cache_gb": kv, "kv_cache_placement": placement,
                     "complete": recipe["model_size_gb"] is not None and kv is not None}      # False = the numbers are declared minimums, not an estimate
        if self.load_check is not None:
            reason = self.load_check(recipe, estimated, req)
            if reason:
                return None, no("pressure", str(reason)[:200])
        return {"recipe": recipe, "context": loaded_context or context, "estimated": estimated, "key": key, "slots": slots}, None

    # -- resolution
    def _resolution(self, role, recipe, best, req, considered, purpose, alternatives=None):
        return {"role": role, "provider_ref": recipe["provider"], "capability_id": recipe["id"], "capability_version": recipe["version"],
                "model": recipe["model"], "context_window": best["context"], "slots": best.get("slots", 1), "estimated_resources": best["estimated"],
                "independence_key": best["key"], "health_state": self.health.state(recipe["provider"]) if self.health else "HEALTHY",
                "permission_level_allowed": recipe["max_level"], "trust_level": recipe["trust_level"], "location": recipe["location"],
                "requirements": req, "reason": "best_available" if alternatives is None else "named_by_captain", "considered": considered,
                "load_profile": {"gpu_layers": recipe["profile"].get("gpu_layers"),
                                 **({"server": recipe["profile"]["server"]} if recipe["profile"].get("server") else {})},
                "alternatives": alternatives if alternatives is not None else [],
                "profile": getattr(self.profiles, "active", None), "purpose": purpose or role,
                "sampling": {k: v for k, v in (self.profiles.purpose(purpose or role) if self.profiles is not None else {}).items() if k != "prefer"}}

    def resolve_recipe(self, recipe_id, requirements=None):
        """The resolution for one NAMED recipe (the Captain picked a model in the UIX), through the same checks as resolve_role
        (policy, hardware, window). Raises ResolutionError when the recipe is unknown or not viable. Audited like a role resolution."""
        recipe = next((r for r in self.config.recipes if r["id"] == recipe_id), None)
        if recipe is None:
            raise ResolutionError("no_capability", {"recipe": recipe_id})
        role = recipe["roles"][0] if recipe["roles"] else "coder"
        req = self.normalize(requirements)
        ok, why = self._evaluate(recipe, req, exclude=set(), independent_of=[], captain_cloud_approved=False, now=self._clock())
        if not ok:
            self._failed(role, self._error_code([why]), [why])
            raise ResolutionError(self._error_code([why]), {"recipe": recipe_id, "considered": [why]})
        resolution = self._resolution(role, recipe, ok, req, [], None, alternatives=[])
        if self.audit:
            self.audit.append("ROLE_RESOLVED", component="role-routing",
                              payload={"role": role, "capability_id": recipe["id"], "provider_ref": recipe["provider"], "health_state": resolution["health_state"], "rejected": []})
        return resolution

    def resolve_role(self, role, requirements=None, *, exclude=(), independent_of=(), captain_cloud_approved=False, quiet=False,
                     purpose=None):
        """`quiet` skips the audit entry; used by probes such as `key_for_role` that do not start any work. `purpose` (e.g. "rework")
        picks the active profile's preference for that use instead of the role's own."""
        if not self.config.enabled:
            raise ResolutionError("no_capability", {"reason": "role_routing_disabled"})
        req = self.normalize(requirements)
        exclude = set(exclude or ())
        independent_of = list(independent_of or ())
        now = self._clock()
        recipes = self.recipes_for(role, purpose)
        preferred = self.prefer(role, purpose)
        considered, viable = [], []
        for recipe in recipes:
            ok, why = self._evaluate(recipe, req, exclude=exclude, independent_of=independent_of,
                                     captain_cloud_approved=captain_cloud_approved, now=now)
            if ok:
                viable.append(ok)
            else:
                considered.append(why)
        if not recipes:
            if not quiet: self._failed(role, "no_capability", considered)
            raise ResolutionError("no_capability", {"role": role, "considered": []})
        if not viable:
            code = self._error_code(considered)
            if not quiet: self._failed(role, code, considered)
            raise ResolutionError(code, {"role": role, "considered": considered})
        def rank(candidate):
            recipe = candidate["recipe"]
            health = {"HEALTHY": 0, "DEGRADED": 1}.get(self.health.state(recipe["provider"]) if self.health else "HEALTHY", 2)
            locality = (0 if recipe["location"] == "local" else 1) if req["offline_preferred"] else 0
            pref = preferred.index(recipe["id"]) if recipe["id"] in preferred else len(preferred)
            return (health, locality, pref, recipes.index(recipe))
        best = sorted(viable, key=rank)[0]
        recipe = best["recipe"]
        resolution = self._resolution(role, recipe, best, req, considered, purpose)
        resolution["alternatives"] = [c["recipe"]["id"] for c in viable if c is not best]
        if self.audit and not quiet:
            self.audit.append("ROLE_RESOLVED", component="role-routing",
                              payload={"role": role, "capability_id": recipe["id"], "provider_ref": recipe["provider"], "health_state": resolution["health_state"],
                                       "rejected": [{"capability_id": c["capability_id"], "reason": c["reason"]} for c in considered]})
        return resolution

    def key_for_role(self, role, requirements=None, **kw):
        """Independence key of the capability this role would resolve to now, or None if it cannot be resolved or proven."""
        try:
            return self.resolve_role(role, requirements, quiet=True, **kw)["independence_key"]
        except ResolutionError:
            return None

    @staticmethod
    def _error_code(considered):
        categories = {c["category"] for c in considered}
        if categories == {"policy"}:
            return "policy_denied"                      # every candidate was refused by policy
        if "pressure" in categories:
            return "hardware_pressure"
        if categories & {"unavailable", "excluded"}:
            return "provider_unavailable"
        return "requirements_unmet"

    def _failed(self, role, code, considered):
        if self.audit:
            self.audit.append("ROLE_RESOLUTION_FAILED", component="role-routing",
                              payload={"role": role, "code": code, "rejected": [{"capability_id": c["capability_id"], "reason": c["reason"]} for c in considered]})

    def resolve_fallback(self, previous, failure_class, requirements=None, *, exclude=(), independent_of=(), captain_cloud_approved=False):
        """Another provider for the same role. Never a way around a refusal, never with looser requirements."""
        if failure_class == "policy_denied":
            raise ResolutionError("policy_denied", {"reason": "fallback_never_bypasses_policy"})
        was = previous["requirements"]
        req = self.normalize(requirements if requirements is not None else was)
        if NETWORK_RANK[req["network"]] > NETWORK_RANK[was["network"]] or DATA_RANK[req["data_class"]] < DATA_RANK[was["data_class"]] \
                or req["permission_level"] > was["permission_level"]:
            raise ResolutionError("policy_denied", {"reason": "fallback_loosens_requirements"})
        return {**self.resolve_role(previous["role"], req, exclude=set(exclude or ()) | {previous["provider_ref"]},
                                    independent_of=independent_of, captain_cloud_approved=captain_cloud_approved), "fallback_of": previous["capability_id"]}

    def view(self):
        return {"schema": 1, "enabled": self.config.enabled, "policy": {"allowed_trust_levels": sorted(self.config.allowed_trust),
                                                                          "cloud_allowed": self.config.cloud_allowed},
                "capabilities": [{"id": r["id"], "enabled": r["enabled"], "roles": r["roles"], "provider": r["provider"], "location": r["location"],
                                  "trust_level": r["trust_level"], "has_independence_key": independence_key(r) is not None} for r in self.config.recipes],
                "provider_health": self.health.view() if self.health else {}}
