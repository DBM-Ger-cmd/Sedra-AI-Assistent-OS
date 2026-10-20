"""Phase 4 of the Context Manager: child manifests, assembly, fresh context, repair.

Rules this module exists to keep (docs/CONTEXT_MANAGER_CONTRACTS.md, sections 5, 7, 8):
 - A child job gets a manifest, never the parent's conversation. The builder has no parameter that could carry one.
 - Detail is fetched on demand through a caller-supplied retriever; artifacts are only referenced.
 - Every pin of a checkpoint reaches the next context (fresh context never forgets facts, limits or open errors).
 - Repair keeps the job id, uses a new attempt id, and is refused for a mutating attempt whose outcome is unknown.
It does not change job state; `job_repair.py` is the glue that does that through the supervisor.
"""
from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path

from ..jobs.context_manager import ContextError, _safe_id, collect_pins
from ..selfdev.development_contracts import canonical_digest, context_manifest
from ..core.util import append_lock, atomic_write_json, load_json, utcnow

TRIGGERS = frozenset({"context_overflow", "context_quality_degraded", "stagnation", "repetition", "manual"})
# Only a wish to the Control Master; the decision stays there.
WORKER_CHANGE_WISH = frozenset({"context_quality_degraded", "stagnation", "repetition"})
FINAL_JOB_STATES = frozenset({"REJECTED", "ROLLED_BACK", "ACTIVATED", "CANCELLED", "DEAD"})
LAYER_ORDER = ("L0", "L1", "L2", "L3", "L4", "L5")


class ContextAssembly:
    def __init__(self, manager, data_root):
        self.manager = manager
        root = Path(data_root)
        self.manifests_root = root / "context_manifests"
        self.repairs_root = root / "context_repairs"
        self.manifests_root.mkdir(parents=True, exist_ok=True)
        self.repairs_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _pin_key(pin):
        return (pin["kind"], json.dumps(pin["ref"], sort_keys=True), pin["digest"])

    def _unique_pins(self, pins):
        out, seen = [], set()
        for pin in pins:
            valid = self.manager.checkpoints._validate_pin(pin)     # a pin needs a checkable source, every time
            key = self._pin_key(valid)
            if key not in seen:
                seen.add(key)
                out.append(valid)
        return out

    @staticmethod
    def _verify_checkpoint(checkpoint):
        if not isinstance(checkpoint, dict) or "checkpoint_digest" not in checkpoint:
            raise ContextError("checkpoint_invalid", "not_a_checkpoint")
        unsigned = {k: v for k, v in checkpoint.items() if k != "checkpoint_digest"}
        if canonical_digest(unsigned) != checkpoint["checkpoint_digest"]:
            raise ContextError("checkpoint_digest_mismatch", checkpoint.get("checkpoint_id"))
        return checkpoint

    def _fixed_pieces(self, m, model_ref=None):
        """Layers L0, L1, L2 and the pins. Always present, never dropped."""
        policy = ["POLICIES AND LIMITS (always in force)"] + list(m["constraints"]) + [f"permissions: {json.dumps(m['permissions'], sort_keys=True)}"]
        contract = ["TASK CONTRACT", f"goal: {m['goal']}", f"current_task: {m['current_task']}",
                    f"acceptance_criteria: {json.dumps(m['acceptance_criteria'], ensure_ascii=False, sort_keys=True)}"]
        for title, key in (("open_questions", "open_questions"), ("relevant_decisions", "relevant_decisions"), ("known_failures", "known_failures")):
            if m[key]:
                contract.append(f"{title}:\n" + "\n".join(f"- {x}" for x in m[key]))
        pieces = [self.manager.piece("policy", "\n".join(policy), layer="L0", critical=True, safety=1, model_ref=model_ref),
                  self.manager.piece("contract", "\n".join(contract), layer="L1", critical=True, task=1, model_ref=model_ref)]
        if m.get("snapshot"):
            pieces.append(self.manager.piece("snapshot", "PROJECT SNAPSHOT\n" + m["snapshot"], layer="L2", critical=True, model_ref=model_ref))
        if m.get("pins"):
            lines = ["PINS (facts that must not be lost)"] + [
                f"- {p['pin_id']} [{p['kind']}] ref={json.dumps(p['ref'], sort_keys=True)} digest={p['digest'][:16]} {p['value']}".rstrip() for p in m["pins"]]
            pieces.append(self.manager.piece("pin", "\n".join(lines), layer="L2", critical=True, model_ref=model_ref))
        return pieces

    def _limits(self, budget):
        marks = self.manager.budget_manager.watermarks
        maximum = budget["max_input_tokens"]
        return int(marks["orange"] * maximum), int(marks["green"] * maximum)

    # ------------------------------------------------------------------ manifest
    def build_manifest(self, job, *, task, budget=None, parent_checkpoint=None, files=(), symbols=(), snapshot=None,
                       extra_pins=(), decisions=(), open_questions=(), known_failures=(), artifact_refs=(), approvals=(),
                       fresh=False, model_ref=None):
        """A job's starting context as references and structured facts. There is deliberately no `history` parameter."""
        if not isinstance(job, dict) or not isinstance(job.get("contract"), dict) or not job["contract"].get("contract_digest"):
            raise ContextError("manifest_invalid", "job_with_contract_required")
        job_id = _safe_id(job.get("job_id"), "job_id")
        contract = job["contract"]
        level = job.get("permission_level", contract.get("permission_level", 0))
        budget = deepcopy(budget) if budget is not None else self.manager.resolve_budget()
        carried_decisions, carried_failures, carried_artifacts, carried_pins, steps = [], [], [], [], []
        checkpoint_id, parent_manifest = None, None
        if parent_checkpoint is not None:
            cp = self._verify_checkpoint(parent_checkpoint)
            if cp["job_id"] not in {job_id, job.get("parent_job_id")}:
                raise ContextError("policy_denied", "checkpoint_from_unrelated_job")
            if int((cp.get("permission_state") or {}).get("level", 0) or 0) > int(level):
                raise ContextError("policy_denied", "checkpoint_permission_exceeds_job")   # a fresh context can lower rights, never raise them
            checkpoint_id, parent_manifest = cp["checkpoint_id"], cp.get("manifest_id")
            carried_decisions = [str(d.get("text") if isinstance(d, dict) else d)[:300] for d in cp["decisions"]]
            carried_failures = [f"{e.get('class', 'error')}: {e.get('summary', '')}"[:500] if isinstance(e, dict) else str(e)[:500] for e in cp["open_errors"]]
            carried_artifacts = [a if isinstance(a, str) else a.get("artifact_id") for a in cp["artifacts"]]
            carried_pins = cp["pins"]
            steps = [f"next: {s}"[:500] for s in cp["next_steps"]]
        evidence = self.manager.checkpoints.evidence
        records = evidence.list(job_id) if evidence is not None else []
        pins = self._unique_pins(list(collect_pins(job, evidence_records=records, approvals=approvals)) + list(carried_pins) + list(extra_pins))
        if snapshot is not None:
            if not isinstance(snapshot, str) or self.manager.estimate(snapshot, model_ref=model_ref) > budget.get("project_context_budget", 10 ** 9):
                raise ContextError("manifest_invalid", "snapshot_missing_or_larger_than_project_context_budget")
        layers = {"L0": [{"kind": "policy", "digest": canonical_digest({"constraints": contract.get("forbidden_actions", []), "level": level})}],
                  "L1": [{"kind": "contract", "digest": contract["contract_digest"]}],
                  "L2": ([{"kind": "snapshot"}] if snapshot else []) + [{"kind": "pins", "count": len(pins)}],
                  "L3": [{"kind": "file", "ref": f} for f in files] + [{"kind": "symbol", "ref": s} for s in symbols],
                  "L4": [], "L5": [{"kind": "artifact", "ref": a} for a in [*artifact_refs, *[x for x in carried_artifacts if x]]]}
        refs = list(dict.fromkeys([*artifact_refs, *[x for x in carried_artifacts if x]]))
        constraints = [f"forbidden: {a}" for a in contract.get("forbidden_actions", [])] + [f"max_permission_level: {level}"]
        fields = dict(goal=contract["objective"], current_task=task, budget=budget, constraints=constraints,
                      relevant_decisions=[*carried_decisions, *decisions], required_files=list(files), exact_symbols=list(symbols),
                      open_questions=[*steps, *open_questions], acceptance_criteria=contract.get("acceptance_criteria", []),
                      known_failures=[*carried_failures, *known_failures], permissions={"max_level": level}, artifact_refs=refs,
                      parent_job_id=job.get("parent_job_id"), checkpoint_id=checkpoint_id, parent_manifest_id=parent_manifest,
                      layers=layers, pins=pins, snapshot=snapshot)
        try:
            preview = context_manifest(**fields)
            fixed = sum(p["tokens_est"] for p in self._fixed_pieces(preview, model_ref))
            orange, _ = self._limits(budget)
            if fixed > orange:
                raise ContextError("minimum_context_exceeds_window", {"minimum_tokens": fixed, "limit": orange})
            manifest = context_manifest(**fields, token_estimate={"minimum": fixed, "method": "estimate"}, excluded=[])
        except ValueError as exc:          # a field was too long or malformed
            raise ContextError("manifest_invalid", str(exc)) from exc
        folder = self.manifests_root / job_id
        folder.mkdir(parents=True, exist_ok=True)
        atomic_write_json(folder / f"{manifest['manifest_id']}.json", manifest)
        if self.manager.audit:
            self.manager.audit.append("CONTEXT_MANIFEST_BUILT", component="context-manager",
                                      payload={"job_id": job_id, "manifest_id": manifest["manifest_id"], "manifest_digest": manifest["manifest_digest"],
                                               "parent_manifest_id": parent_manifest, "checkpoint_id": checkpoint_id, "fresh": bool(fresh),
                                               "pins": len(pins), "minimum_tokens": fixed})
        return manifest

    def load_manifest(self, job_id, manifest_id):
        record = load_json(self.manifests_root / _safe_id(job_id, "job_id") / f"{_safe_id(manifest_id, 'manifest_id')}.json")
        if record is None:
            raise ContextError("piece_not_found", manifest_id)
        self._verify_manifest(record)
        return record

    @staticmethod
    def _verify_manifest(manifest):
        if not isinstance(manifest, dict) or "manifest_digest" not in manifest:
            raise ContextError("manifest_invalid", "not_a_manifest")
        if canonical_digest({k: v for k, v in manifest.items() if k != "manifest_digest"}) != manifest["manifest_digest"]:
            raise ContextError("manifest_invalid", "digest_mismatch")

    # ------------------------------------------------------------------ assembly
    def assemble(self, manifest, *, retriever=None, model_ref=None):
        """Layers L0..L3 within the budget. Critical pieces are never dropped; an incomplete result says what is missing."""
        self._verify_manifest(manifest)
        budget = manifest["budget"]
        orange, green = self._limits(budget)
        pieces = self._fixed_pieces(manifest, model_ref)
        fixed_tokens = sum(p["tokens_est"] for p in pieces)
        if fixed_tokens > orange:
            raise ContextError("minimum_context_exceeds_window", {"minimum_tokens": fixed_tokens, "limit": orange})
        wanted = [("file", f) for f in manifest["required_files"]] + [("symbol", s) for s in manifest["exact_symbols"]]
        missing, truncated = [], []
        cap = max(256, int(budget.get("task_context_budget", 2048)) // max(1, len(wanted)))
        for kind, ref in wanted:
            text = retriever.fetch(kind, ref) if retriever is not None else None
            if not isinstance(text, str) or not text:
                missing.append({"kind": kind, "ref": ref})
                continue
            if self.manager.estimate(text, model_ref=model_ref) > cap:
                text = text[: int(cap * self.manager.config.code_cpt)] + f"\n[... truncated to about {cap} tokens; ask for the rest by reference]"
                truncated.append({"kind": kind, "ref": ref})
            pieces.append(self.manager.piece("file_excerpt" if kind == "file" else "symbol", f"{kind.upper()} {ref}\n{text}", layer="L3",
                                             ref={kind: ref}, task=1, file=1, model_ref=model_ref))
        if manifest["artifact_refs"]:
            note = "ARTIFACTS (not included; read parts on demand by reference)\n" + "\n".join(f"- {a}" for a in manifest["artifact_refs"])
            pieces.append(self.manager.piece("artifact_ref", note, layer="L5", model_ref=model_ref))
        kept, excluded = self.manager.trim_to_target(pieces, green)
        kept.sort(key=lambda p: LAYER_ORDER.index(p["layer"]))
        text = "\n\n".join(p["text"] for p in kept)
        total = sum(p["tokens_est"] for p in kept)
        return {"manifest_id": manifest["manifest_id"], "status": "INCOMPLETE" if missing else "READY", "pieces": kept, "text": text,
                "tokens": total, "excluded": excluded, "missing": missing, "truncated": truncated, "pins": deepcopy(manifest["pins"]),
                "allowed_artifacts": set(manifest["artifact_refs"]), "state": self.manager.budget_manager.health(total, budget)["state"]}

    # ------------------------------------------------------------------ fresh context
    def fresh_context(self, job, checkpoint, *, task, attempt_id="ATT-NONE", **kw):
        """New manifest from a checkpoint: policies and contract from the job, facts from the checkpoint's pins."""
        manifest = self.build_manifest(job, task=task, parent_checkpoint=checkpoint, fresh=True, **kw)
        have = {self._pin_key(p) for p in manifest["pins"]}
        lost = [p["pin_id"] for p in checkpoint["pins"] if self._pin_key(p) not in have]
        if lost:
            raise ContextError("manifest_invalid", {"pins_lost": lost})
        self.manager.metrics.bump(job["job_id"], attempt_id, fresh_context_count=1)
        return manifest

    # ------------------------------------------------------------------ repetition and repair
    def detect_repetition(self, history, threshold=None):
        """Same request or same error `threshold` times in a row. Pure; the caller decides what to do."""
        threshold = threshold or self.manager.config.repair_repeat_threshold
        for key, kind in (("request_digest", "request"), ("error_signature", "error")):
            run, last = 0, None
            for event in history:
                value = event.get(key) if isinstance(event, dict) else None
                run = run + 1 if value is not None and value == last else (1 if value is not None else 0)
                last = value
                if run >= threshold:
                    return {"trigger": "repetition", "kind": kind, "count": run, "value": value}
        return None

    def _repairs_used(self, job_id):
        path = self.repairs_root / f"{_safe_id(job_id, 'job_id')}.jsonl"
        if not path.exists():
            return 0
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if '"status": "started"' in line)

    def plan_repair(self, job, *, trigger, mutating):
        """Dry run: is a repair allowed, and what would it do?"""
        if trigger not in TRIGGERS:
            raise ContextError("unknown_repair_trigger", trigger)
        used, limit = self._repairs_used(job["job_id"]), self.manager.config.repair_max
        attempts = job.get("attempt_log") or []
        reason = None
        if job.get("state") in FINAL_JOB_STATES:
            reason = "job_is_final"
        elif attempts and attempts[-1].get("outcome") == "UNKNOWN" and mutating:
            reason = "unknown_outcome_of_mutating_attempt"
        elif used >= limit:
            reason = "repair_limit_reached"
        return {"possible": reason is None, "reason": reason, "repairs_used": used, "repairs_max": limit, "trigger": trigger,
                "steps": ["checkpoint", "drop_irrelevant", "reassemble_from_pins", "optional_other_worker"],
                "worker_change_requested": trigger in WORKER_CHANGE_WISH}

    def repair(self, job, *, trigger, task, checkpoint_source, mutating, **manifest_kw):
        """Checkpoint, rebuild a fresh manifest from it, and hand back a new attempt id. The job id stays."""
        job_id = _safe_id(job["job_id"], "job_id")
        plan = self.plan_repair(job, trigger=trigger, mutating=mutating)
        refuse = plan["reason"] if not plan["possible"] else ("no_checkpoint_source" if checkpoint_source is None else None)
        if refuse:
            if self.manager.audit:
                self.manager.audit.append("CONTEXT_REPAIR_REFUSED", component="context-manager", payload={"job_id": job_id, "trigger": trigger, "reason": refuse})
            raise ContextError("repair_not_possible", refuse)
        path = self.repairs_root / f"{job_id}.jsonl"
        with append_lock(path):                       # reserve the repair before doing the work, so races cannot exceed the limit
            if self._repairs_used(job_id) >= self.manager.config.repair_max:
                raise ContextError("repair_not_possible", "repair_limit_reached")
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"status": "started", "trigger": trigger, "at": utcnow()}) + "\n")
        attempts = job.get("attempt_log") or []
        current = attempts[-1]["attempt_id"] if attempts else "ATT-NONE"
        checkpoint = self.manager.checkpoint(job_id, current, reason=f"repair:{trigger}", **checkpoint_source())
        manifest = self.fresh_context(job, checkpoint, task=task, attempt_id=current, **manifest_kw)
        new_attempt = f"ATT-{uuid.uuid4().hex[:12].upper()}"
        with append_lock(path):
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"status": "done", "trigger": trigger, "checkpoint_id": checkpoint["checkpoint_id"],
                                         "manifest_id": manifest["manifest_id"], "attempt_id_new": new_attempt, "at": utcnow()}) + "\n")
        if self.manager.audit:
            self.manager.audit.append("CONTEXT_REPAIR", component="context-manager",
                                      payload={"job_id": job_id, "trigger": trigger, "checkpoint_id": checkpoint["checkpoint_id"],
                                               "manifest_id": manifest["manifest_id"], "attempt_id_new": new_attempt, "attempt_id_previous": current,
                                               "worker_change_requested": plan["worker_change_requested"]})
        return {**plan, "possible": True, "checkpoint": checkpoint, "new_manifest": manifest, "attempt_id_new": new_attempt,
                "preserves": {"job_id": job_id, "pins": [p["pin_id"] for p in manifest["pins"]],
                              "permission_state": deepcopy(checkpoint["permission_state"])}}
