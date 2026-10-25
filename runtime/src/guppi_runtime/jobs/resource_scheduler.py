"""Reservations for RAM, VRAM and KV cache (Phase 7).

The hardware manager only counts running model calls (`max_jobs`) and checks thermal state and a RAM reserve. It cannot say
"this job needs 6 GB more VRAM, and 8.5 GB are already promised". This scheduler can, with a persistent ledger:

  granted  only if  (a) capacity - reserve - already_reserved >= request        (the ledger: what has been promised)
                and (b) measured_available - reserve >= request                 (the world: what is really free)
  and      thermal state allows work, the job limit is not reached, and an exclusive holder is respected.

It never reads telemetry itself (it asks the hardware manager), never picks a model (the role router does), and never
starts or stops anything. Reservations are ended by state, not by the clock: the supervisor releases them when an attempt
ends, and `reconcile` drops those of jobs that are no longer running. A wall clock that jumps cannot free a live job's room.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ..core.util import append_lock, atomic_write_json, load_json

BAD_THERMAL = frozenset({"HOT", "CRITICAL", "SENSOR_FAULT", "RECOVERY"})


class LedgerUnreadable(RuntimeError):
    """The reservation file exists but cannot be read. Distinct from a hardware error: it must not look like an empty ledger."""


class ResourceConfig:
    def __init__(self, raw):
        if not isinstance(raw, dict):
            raise ValueError("resource_config_invalid")
        self.enabled = raw.get("enabled", False)
        if not isinstance(self.enabled, bool):
            raise ValueError("resource_config_invalid:enabled")
        self.vram_reserve_gb = self._num(raw, "vram_reserve_gb", 1.0, 0, 1024)
        self.ram_reserve_gb = self._num(raw, "ram_reserve_gb", None, 0, 4096)
        self.warm_max = raw.get("warm_max_reservations", 1)
        if type(self.warm_max) is not int or not 1 <= self.warm_max <= 64:
            raise ValueError("resource_config_invalid:warm_max_reservations")
        self.unknown_vram = raw.get("unknown_vram_telemetry", "deny")
        if self.unknown_vram not in {"deny", "declared_only"}:
            raise ValueError("resource_config_invalid:unknown_vram_telemetry")

    @staticmethod
    def _num(section, key, default, low, high):
        value = section.get(key, default)
        if value is None and default is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
            raise ValueError(f"resource_config_invalid:{key}")
        return float(value)

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            raise ValueError("resource_config_missing")
        return cls((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("resource_scheduler") or {})


def _value(metric):
    """A telemetry metric's number, or None when the collector marked it unavailable."""
    if isinstance(metric, dict) and metric.get("state") == "valid" and isinstance(metric.get("value"), (int, float)):
        return float(metric["value"])
    return None


def need_of(estimate):
    """RAM and VRAM a job needs. KV cache counts where the profile puts it. Unknown KV is not zero: it is flagged."""
    ram, vram = float(estimate.get("ram_gb") or 0), float(estimate.get("vram_gb") or 0)
    kv = estimate.get("kv_cache_gb")
    if kv:
        if estimate.get("kv_cache_placement") == "cpu":
            ram += float(kv)
        else:
            vram += float(kv)
    return {"ram_gb": round(ram, 3), "vram_gb": round(vram, 3), "complete": kv is not None and estimate.get("complete", True)}


class ResourceScheduler:
    def __init__(self, config, hardware, path, *, audit=None, clock=None):
        self.config, self.hardware, self.audit = config, hardware, audit
        self.path = Path(path)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def enabled(self):
        return self.config.enabled

    # ---- ledger
    def _read(self):
        try:
            data = load_json(self.path, {"reservations": []}) or {"reservations": []}
        except (ValueError, OSError):
            raise LedgerUnreadable("resource_ledger_unreadable")    # an unreadable ledger must not look like an empty one
        return data["reservations"] if isinstance(data, dict) and isinstance(data.get("reservations"), list) else []

    def _write(self, reservations):
        atomic_write_json(self.path, {"schema": 1, "reservations": reservations})

    def reservations(self):
        return self._read()

    # ---- facts about the host
    def _host(self, fresh):
        state = self.hardware.get_state(fresh=fresh)
        profile = self.hardware.active_profile()
        memory = state.get("memory") or {}
        gpus = []
        for gpu in state.get("gpus") or []:
            total, free = _value(gpu.get("vram_total")), _value(gpu.get("vram_available"))
            if total is not None and free is not None:
                gpus.append({"device_id": gpu.get("device_id"), "total": total, "available": free})
        ram_reserve = self.config.ram_reserve_gb if self.config.ram_reserve_gb is not None else float(profile.get("ram_reserve_gib") or 0)
        return {"thermal": state.get("thermal_state"), "ram_total": _value(memory.get("total")), "ram_available": _value(memory.get("available")),
                "gpus": gpus, "ram_reserve": ram_reserve, "max_jobs": int(profile.get("max_jobs") or 1)}

    @staticmethod
    def _committed(reservations, key, device=None):
        return sum(r.get(key, 0) for r in reservations if device is None or r.get("device_id") == device)

    def _decide(self, estimate, *, exclusive, reservations, host, resident_vram_gb=0.0):
        """None if it fits, else (reason, detail). Pure: reads the host picture and the ledger, changes nothing.

        `resident_vram_gb`: VRAM that the very model this request is for already holds on the card (an instance the provider
        keeps loaded and the job will reuse). The measurement counts it as used, but it is not a second copy to fit: it is
        credited to the MEASURED side only, never above the request. The ledger (what has been promised) stays untouched."""
        need = need_of(estimate)
        cfg = self.config
        if host["thermal"] in BAD_THERMAL:
            return f"thermal_{host['thermal'].lower()}", {}
        cap = 1 if exclusive else host["max_jobs"]
        if host["thermal"] == "WARM":
            cap = min(cap, cfg.warm_max)
        if reservations and (exclusive or any(r.get("exclusive") for r in reservations)):
            return ("exclusive_conflict" if exclusive else "exclusive_held"), {"holders": [r["job_id"] for r in reservations]}
        if len(reservations) >= max(cap, 1):
            return "job_limit", {"limit": cap, "reserved": len(reservations)}
        if need["ram_gb"] > 0:
            if host["ram_total"] is None or host["ram_available"] is None:
                return "telemetry_unavailable_ram", {}
            if host["ram_total"] - host["ram_reserve"] - self._committed(reservations, "ram_gb") < need["ram_gb"]:
                return "ram_ledger", {"need_gb": need["ram_gb"], "promised_gb": round(self._committed(reservations, "ram_gb"), 3)}
            if host["ram_available"] - host["ram_reserve"] < need["ram_gb"]:
                return "ram_measured", {"need_gb": need["ram_gb"], "available_gb": host["ram_available"]}
        device = None
        if need["vram_gb"] > 0:
            if not host["gpus"]:
                if cfg.unknown_vram == "deny":
                    return "no_gpu_telemetry_for_vram_request", {}
            else:
                best = None
                for gpu in host["gpus"]:
                    ledger_free = gpu["total"] - cfg.vram_reserve_gb - self._committed(reservations, "vram_gb", gpu["device_id"])
                    measured_free = gpu["available"] + min(max(float(resident_vram_gb or 0.0), 0.0), need["vram_gb"]) - cfg.vram_reserve_gb
                    free = min(ledger_free, measured_free)
                    if free >= need["vram_gb"] and (best is None or free > best[0]):
                        best = (free, gpu)
                if best is None:
                    top = max(min(g["total"] - cfg.vram_reserve_gb - self._committed(reservations, "vram_gb", g["device_id"]), g["available"] - cfg.vram_reserve_gb)
                              for g in host["gpus"])
                    measured = max(g["available"] for g in host["gpus"])
                    return "vram_insufficient", {"need_gb": need["vram_gb"], "best_free_gb": round(top, 3), "measured_free_gb": round(measured, 3)}
                device = best[1]["device_id"]
        return None, {"device": device, "need": need}

    @staticmethod
    def _headroom(host, reservations, cfg):
        gpus = [{"device_id": g["device_id"], "free_gb": round(min(g["total"] - cfg.vram_reserve_gb - sum(r.get("vram_gb", 0) for r in reservations if r.get("device_id") == g["device_id"]),
                                                              g["available"] - cfg.vram_reserve_gb), 3)} for g in host["gpus"]]
        ram = None
        if host["ram_total"] is not None and host["ram_available"] is not None:
            ram = round(min(host["ram_total"] - host["ram_reserve"] - sum(r.get("ram_gb", 0) for r in reservations), host["ram_available"] - host["ram_reserve"]), 3)
        return {"ram_free_gb": ram, "gpus": gpus}

    # ---- advisory
    def explain(self, estimate, *, exclusive=False, resident_vram_gb=0.0):
        """Would this fit right now? A reason string or None. Reserves nothing; reading may be a few seconds old."""
        if not self.config.enabled:
            return None
        try:
            reason, _ = self._decide(estimate, exclusive=exclusive, reservations=self._read(), host=self._host(fresh=False), resident_vram_gb=resident_vram_gb)
        except LedgerUnreadable as exc:
            return str(exc)
        except Exception as exc:               # an advisory check must never break role resolution, and must not say "fits" blindly
            return "hardware_profile_changed" if str(exc) == "active_profile_hardware_changed" else "hardware_state_unavailable"
        return reason

    # ---- binding
    def reserve(self, job_id, attempt_id, estimate, *, exclusive=False, resident_vram_gb=0.0):
        if not self.config.enabled:
            return {"status": "GRANTED", "reservation": None, "reason": "scheduler_disabled", "headroom": None, "alternatives": []}
        with append_lock(self.path):
            try:
                current = self._read()
            except LedgerUnreadable as exc:    # an unreadable ledger is not an empty one: promise nothing
                self._audit("RESOURCE_DENIED", job_id, reason=str(exc))
                return {"status": "DENIED", "reservation": None, "reason": str(exc), "detail": {}, "headroom": None, "alternatives": ["queue"]}
            reservations = [r for r in current if r["job_id"] != job_id]            # a job holds one reservation; a stale one of an earlier attempt is replaced
            try:
                host = self._host(fresh=True)
            except Exception as exc:           # no picture of the host, no promise
                reason = "hardware_profile_changed" if str(exc) == "active_profile_hardware_changed" else "hardware_state_unavailable"
                self._audit("RESOURCE_DENIED", job_id, reason=reason)
                return {"status": "DENIED", "reservation": None, "reason": reason, "detail": {}, "headroom": None, "alternatives": ["queue"]}
            outcome, detail = self._decide(estimate, exclusive=exclusive, reservations=reservations, host=host, resident_vram_gb=resident_vram_gb)
            headroom = self._headroom(host, reservations, self.config)
            if outcome is not None:
                self._audit("RESOURCE_DENIED", job_id, reason=outcome, **self._values(detail))     # the numbers, not only the reason (SCH-03)
                alternatives = ["queue"] + (["smaller_model_or_cpu_offload"] if outcome.startswith(("vram", "ram", "no_gpu")) else [])
                return {"status": "DENIED", "reservation": None, "reason": outcome, "detail": detail, "headroom": headroom, "alternatives": alternatives}
            need = detail["need"]
            record = {"reservation_id": f"RSV-{uuid.uuid4().hex[:12].upper()}", "job_id": job_id, "attempt_id": str(attempt_id)[:64],
                      "ram_gb": need["ram_gb"], "vram_gb": need["vram_gb"], "device_id": detail["device"], "kv_cache_gb": estimate.get("kv_cache_gb"),
                      "estimate_complete": bool(need["complete"]), "exclusive": bool(exclusive), "created_at": self._clock().isoformat()}
            self._write(reservations + [record])
        self._audit("RESOURCE_RESERVED", job_id, ram_gb=record["ram_gb"], vram_gb=record["vram_gb"], device_id=record["device_id"],
                    estimate_complete=record["estimate_complete"], exclusive=record["exclusive"])
        return {"status": "GRANTED", "reservation": record, "reason": "fits", "headroom": headroom, "alternatives": []}

    @staticmethod
    def _values(detail):
        return {k: v for k, v in (detail or {}).items() if k.endswith("_gb") or k in ("limit", "reserved")}

    def audit_denied(self, job_id, reason, **values):
        """A refusal decided outside the ledger (the model scheduler's VRAM limit, SCH-03), audited like one of ours with its numbers."""
        self._audit("RESOURCE_DENIED", job_id, reason=reason, **values)

    def measured_free_vram_gb(self):
        """The most free VRAM one GPU reports right now (fresh reading), or None when disabled or unknown. Reserves nothing."""
        if not self.config.enabled:
            return None
        try:
            gpus = self._host(fresh=True)["gpus"]
        except Exception:
            return None
        return round(max(g["available"] for g in gpus), 3) if gpus else None

    def release_job(self, job_id):
        """Give a job's room back. Safe to call any number of times."""
        if not self.config.enabled:
            return 0
        with append_lock(self.path):
            current = self._read()
            kept = [r for r in current if r["job_id"] != job_id]
            if len(kept) != len(current):
                self._write(kept)
        if len(kept) != len(current):
            self._audit("RESOURCE_RELEASED", job_id, count=len(current) - len(kept))
        return len(current) - len(kept)

    def reconcile(self, live_job_ids):
        """Drop reservations of jobs that are not running any more (crash, lost worker, finished elsewhere)."""
        if not self.config.enabled:
            return []
        live = set(live_job_ids)
        with append_lock(self.path):
            current = self._read()
            stale = [r for r in current if r["job_id"] not in live]
            if stale:
                self._write([r for r in current if r["job_id"] in live])
        for r in stale:
            self._audit("RESOURCE_RELEASED", r["job_id"], count=1, reason="job_no_longer_running")
        return [r["job_id"] for r in stale]

    def refresh(self):
        """Read the host again, past every cache. Called right after a model left the card, so the next check sees the room."""
        if not self.config.enabled:
            return False
        try:
            self.hardware.get_state(fresh=True)
            return True
        except Exception:
            return False

    def view(self):
        out = {"schema": 1, "enabled": self.config.enabled, "vram_reserve_gb": self.config.vram_reserve_gb}
        try:
            reservations = self._read()
            out["reservations"] = reservations
            out["headroom"] = self._headroom(self._host(fresh=False), reservations, self.config) if self.config.enabled else None
        except Exception as exc:                  # a status view must never raise
            out["error"] = type(exc).__name__
        return out

    def _audit(self, event, job_id, **payload):
        if self.audit:
            self.audit.append(event, component="resource-scheduler", mission_id=job_id, payload={"job_id": job_id, **payload})
