"""Permission levels 0-6 as a ceiling above the Guard (Phase 6).

This is not a second rights system. The Guard decides every action; a level only limits which actions a job may ask for,
and a scope limits where it may act. The gate refuses first and asks the Guard second, so it can only ever say "no" more
often than the Guard, never "yes" where the Guard says no or asks for the Captain.
Contract: docs/JOB_SUPERVISOR_CONTRACTS.md section 9.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from .request_binding import digest

TOP_LEVEL = 6


class PermissionConfig:
    def __init__(self, raw):
        if not isinstance(raw, dict):
            raise ValueError("permission_config_invalid")
        names = raw.get("names") or {}
        if sorted(names) != list(range(7)) or any(not isinstance(v, str) or not v for v in names.values()):
            raise ValueError("permission_config_invalid:names")
        self.names = dict(names)
        self.actions = {}
        for action, spec in (raw.get("actions") or {}).items():
            if not isinstance(action, str) or not isinstance(spec, dict) or type(spec.get("level")) is not int or not 1 <= spec["level"] <= TOP_LEVEL \
                    or not isinstance(spec.get("path_scoped"), bool):
                raise ValueError(f"permission_config_invalid:action:{action}")
            self.actions[action] = {"level": spec["level"], "path_scoped": spec["path_scoped"]}
        never = raw.get("never_automatic") or []
        if not isinstance(never, list) or any(not isinstance(x, str) for x in never):
            raise ValueError("permission_config_invalid:never_automatic")
        self.never = frozenset(never)
        if self.never & set(self.actions):
            raise ValueError("permission_config_invalid:never_automatic_overlaps_actions")
        if not self.actions:
            raise ValueError("permission_config_invalid:no_actions")

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            raise ValueError("permission_config_missing")
        return cls((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("permission_levels") or {})


def _inside(path, roots):
    """True if `path` lies within one of `roots`. Compared after full resolution and case folding (Windows)."""
    try:
        target = os.path.normcase(str(Path(path).resolve()))
    except (OSError, ValueError, RuntimeError):
        return False
    for root in roots:
        base = os.path.normcase(str(Path(root).resolve()))
        try:
            if os.path.commonpath([target, base]) == base:
                return True
        except ValueError:                # different drives
            continue
    return False


class PermissionGate:
    def __init__(self, config, guard, *, audit=None):
        self.config, self.guard, self.audit = config, guard, audit

    # ---- facts
    def level_of(self, action):
        """None for a never-automatic action. An action nobody classified is treated as the highest level."""
        if action in self.config.never:
            return None
        spec = self.config.actions.get(action)
        return spec["level"] if spec else TOP_LEVEL

    def policy_hash(self):
        """Fingerprint of everything that decides what a job may do: this mapping and the Guard's rules."""
        return digest({"levels": self.config.actions, "never": sorted(self.config.never),
                       "guard_rules": getattr(self.guard, "rules", {}), "guard_defaults": getattr(self.guard, "defaults", {})})

    def binding(self, job, action, target):
        """What a Captain approval is tied to: this job, this contract, this action on this target at this level."""
        return {"job_id": job["job_id"], "action": action, "target": str(target), "permission_level": job.get("permission_level"),
                "contract_digest": (job.get("contract") or {}).get("contract_digest"), "policy_hash": job.get("policy_hash")}

    # ---- decision
    def check(self, job, action, target, *, token=None):
        """ALLOWED, APPROVAL_REQUIRED or DENIED. Denials carry a reason code; none of them asks anyone."""
        level = self.level_of(action)
        out = {"status": "DENIED", "reason": None, "level": level, "action": action, "target": str(target), "guard": None}

        def deny(reason):
            out["reason"] = reason
            if self.audit:
                self.audit.append("PERMISSION_DENIED", component="permission-gate", mission_id=job.get("job_id"),
                                  payload={"job_id": job.get("job_id"), "action": action, "target": str(target)[:300], "reason": reason,
                                           "level_required": level, "level_job": job.get("permission_level")})
            return out

        if level is None:
            return deny("never_automatic")
        job_level = job.get("permission_level")
        if type(job_level) is not int or not 0 <= job_level <= TOP_LEVEL:
            return deny("job_has_no_valid_permission_level")
        if level > job_level:
            return deny("permission_level_exceeds_job")
        if job.get("policy_hash") and job["policy_hash"] != self.policy_hash():
            return deny("policy_changed_since_job_start")        # rules may not change under a running job
        spec = self.config.actions.get(action)
        if spec and spec["path_scoped"]:
            roots = (job.get("scope") or {}).get("roots") or []
            if not roots:
                return deny("no_development_scope")              # fail closed: no scope, no path access
            if not _inside(target, roots):
                return deny("target_outside_scope")
        verdict = self.guard.evaluate(action, mission_id=job["job_id"], target=str(target))
        out["guard"] = verdict
        if verdict["decision"] == "BLOCK":
            return deny("guard_blocked")
        if verdict["decision"] == "ALLOW":
            out.update(status="ALLOWED", reason="guard_allows")
            return out
        if token is not None:
            checked = self.guard.check_token(token, mission_id=job["job_id"], action=action, target=str(target),
                                             request_binding=self.binding(job, action, target))
            if checked["authorized"]:
                out.update(status="ALLOWED", reason="captain_approved")      # the executor still spends the single-use token
                return out
            out["token_problem"] = checked["reason"]
        out.update(status="APPROVAL_REQUIRED", reason="guard_requires_captain")
        return out
