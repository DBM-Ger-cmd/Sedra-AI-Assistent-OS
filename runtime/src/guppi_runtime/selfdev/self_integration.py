"""Take a self-developed E1 capability into GUPPI's own code. Narrow on purpose (2026-10-02).

candidate_acceptance.py writes into managed projects only; this is the one path into GUPPI itself:
  - only for a mission whose self-development job is E1 and passes `acceptance_refusal` (READY_FOR_ACCEPTANCE, verified PASS,
    independent reviewer) and whose VM tests are real and verified (`test_qualification`);
  - only NEW files, only in guppi_runtime/capabilities/, never a test file, never an existing file (create-exclusive);
  - every integration and every rollback needs its own Captain gate bound to the exact plan (file names, contents, hashes);
  - rollback removes only files that still have the integrated hash; an unknown outcome is REVIEW_REQUIRED, never replayed.
"""
import hashlib
import os
import re
from pathlib import Path

from ..candidate_acceptance import close_after_take_over, linked_job, test_qualification
from ..tuning import digest
from ..util import utcnow

CAPABILITY_DIR = Path(__file__).resolve().parents[1] / "capabilities"
_MODULE_NAME = re.compile(r"[a-z][a-z0-9_]{1,63}\.py")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def preview(rt, mission, resolution="integrate"):
    mid = mission["identity"]["mission_id"]
    previous = mission["execution"].get("self_integration")
    job = linked_job(rt, mid)
    if job is None: raise ValueError("self_development_job_required")
    if resolution == "integrate":
        if previous: raise ValueError("integration_already_started")
        if job["contract"]["classification"] != "E1": raise ValueError("only_e1_capabilities_integrate_automatically")
        refusal = rt.self_development.acceptance_refusal(job)
        if refusal: raise ValueError(refusal)
        evidence = dict(test_qualification(rt, mission), development_job=job["job_id"])
        changes = mission["plan"]["steps"][0]["binding"]["inputs"]["changes"]
        files = []
        for change in changes:
            rel = change["path"].replace("\\", "/")
            if rel.startswith("tests/") or "/" in rel: raise ValueError("only_top_level_modules_integrate")
            if not _MODULE_NAME.fullmatch(rel) or rel == "__init__.py": raise ValueError("invalid_capability_module_name")
            target = CAPABILITY_DIR / rel
            if target.exists(): raise ValueError(f"capability_module_exists:{rel}")      # never overwrite GUPPI code
            raw = change["content"].encode("utf-8")
            files.append({"module": rel, "target": str(target), "after_sha256": _sha(raw), "content": change["content"]})
        if not files: raise ValueError("nothing_to_integrate")
    elif resolution == "rollback":
        if not previous or previous.get("status") != "APPLIED": raise ValueError("confirmed_integration_required")
        if previous.get("rollback"): raise ValueError("rollback_already_started")
        files = []
        for rec in previous["plan"]["files"]:
            target = Path(rec["target"])
            if not target.is_file() or _sha(target.read_bytes()) != rec["after_sha256"]: raise ValueError(f"module_changed_after_integration:{rec['module']}")
            files.append({"module": rec["module"], "target": rec["target"], "after_sha256": rec["after_sha256"]})
        evidence = {"integration_digest": previous["plan_digest"], "development_job": job["job_id"]}
    else:
        raise ValueError("unsupported_integration_resolution")
    plan = {"schema": 1, "mission_id": mid, "resolution": resolution, "capability_dir": str(CAPABILITY_DIR), "files": files, "evidence": evidence}
    plan["plan_digest"] = digest(plan)
    return plan


def apply(rt, mission, plan, token=None):
    mid = mission["identity"]["mission_id"]
    resolution = plan.get("resolution") if isinstance(plan, dict) else None
    if preview(rt, mission, resolution) != plan: raise ValueError("integration_plan_changed")
    action = "self_integration" if resolution == "integrate" else "self_integration_rollback"
    target = action + ":" + plan["plan_digest"]
    verdict = rt.guard.evaluate(action, mission_id=mid, target=target)
    if verdict["decision"] == "BLOCK": return {"status": "blocked", "guard": verdict}
    if verdict["decision"] != "ALLOW" and not rt.guard.authorize(token, mission_id=mid, action=action, target=target, request_binding=plan)["authorized"]:
        risks = ["Adds new modules to GUPPI's own code (guppi_runtime/capabilities); nothing imports them automatically"] if resolution == "integrate" \
            else ["Removes the integrated capability modules"]
        return {"status": "captain_required", "gate": rt.guard.create_gate(mid, action, target, risks=risks, rollback_available=resolution == "integrate", request_binding=plan)}
    job_id = plan["evidence"]["development_job"]
    if resolution == "integrate":
        record = {"status": "RUNNING", "plan": plan, "plan_digest": plan["plan_digest"], "completed": [], "started_at": utcnow()}
        mission["execution"]["self_integration"] = record
        rt.self_development.mark_activation(job_id, "started")
    else:
        record = mission["execution"]["self_integration"]
        record["rollback"] = {"status": "RUNNING", "plan": plan, "completed": [], "started_at": utcnow()}
        record = record["rollback"]
    rt.missions.save(mission)           # the record (with the full plan) is written before any file is touched
    try:
        for rec in plan["files"]:
            path = Path(rec["target"])
            if path.parent.resolve() != CAPABILITY_DIR: raise ValueError("target_outside_capability_dir")
            if resolution == "integrate":
                with open(path, "xb") as stream:          # create-exclusive: an existing file is never replaced
                    stream.write(rec["content"].encode("utf-8")); stream.flush(); os.fsync(stream.fileno())
                if _sha(path.read_bytes()) != rec["after_sha256"]: raise ValueError("written_module_verification_failed")
            else:
                if _sha(path.read_bytes()) != rec["after_sha256"]: raise ValueError("module_changed_before_rollback")
                path.unlink()
            record["completed"].append(rec["module"]); rt.missions.save(mission)
            rt.audit.append("SELF_INTEGRATION_FILE", component="self-integration", mission_id=mid,
                            payload={"resolution": resolution, "module": rec["module"], "sha256": rec["after_sha256"]})
        record["status"] = "APPLIED" if resolution == "integrate" else "ROLLED_BACK"; record["finished_at"] = utcnow()
        rt.missions.save(mission)
        rt.self_development.mark_activation(job_id, "applied" if resolution == "integrate" else "rolled_back")
        close_after_take_over(rt, mission, "applied" if resolution == "integrate" else "rolled_back", "self_integration")
        return {"status": "completed", "integration": record}
    except Exception as exc:
        record["status"] = "REVIEW_REQUIRED"; record["error"] = f"{type(exc).__name__}:{exc}"; rt.missions.save(mission)
        return {"status": "failed", "integration": record, "reason": "partial_or_unknown_effect_requires_review"}


def command(rt, mid, operation, plan=None):
    """CLI entry: integrate-preview | integrate | rollback-preview | rollback."""
    with rt.missions.execution_lock(mid):
        mission = rt.missions.load(mid)
        if operation in {"integrate-preview", "rollback-preview"}:
            return {"status": "completed", "plan": preview(rt, mission, "integrate" if operation == "integrate-preview" else "rollback")}
        if operation not in {"integrate", "rollback"}: raise ValueError("unsupported_integration_operation")
        token = mission["execution"].get("approval_token")
        out = apply(rt, mission, plan, token)
        if out.get("gate"):
            gate = out["gate"]
            if not any(g["request"] == gate["request"] for g in mission["human_gates"]["pending"]): mission["human_gates"]["pending"].append(gate)
        if token and token.get("status") == "used": mission["execution"].pop("approval_token", None)
        rt.missions.save(mission)
        return out
