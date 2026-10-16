"""Crew instances, and what lets one become VERIFIED (integration stage 5, second step).

A template is only a description. An instance is a template that GUPPI hired: it has an id, a qualification (UNVERIFIED at the start), a lifecycle and an admission. Two decisions exist and
both go through a Captain gate of the Guard (decision D05, only the Guard admits):

  agent.instantiate  target = the template reference, bound to the template digest and the purpose; creates the instance as UNVERIFIED without any admission
  agent.promote      target = the instance id, bound to the suite run (suite label, candidate hash) and the reviewer; sets VERIFIED and a valid admission

`promote` is refused unless the acceptance suite the template declares was run for the instance and every required case PASSED, and an independent review (another model than the builder)
said PASS. An admission can be revoked at once without a gate (taking rights away needs no approval). Everything is stored in the registry (kind "agent") with command ids, so a click repeated
or a crash in the middle never creates a second instance or a second promotion.
"""
from .agent_contracts import ContractError, make_id
from .agent_matcher import match
from .crews import assemble

INSTANTIATE = "agent.instantiate"
PROMOTE = "agent.promote"
MAX_RUNS = 20


def promotion_gaps(declared, run, review, decision):
    """The gaps between an instance and VERIFIED. `declared` is the template's `verification` block, `run` the result of `acceptance_suite.run_suite`, `review` the stored independent review
    (or None), `decision` whether a Guard-approved decision exists. An empty list means VERIFIED may be granted."""
    if not isinstance(declared, dict) or not isinstance(declared.get("suite_id"), str):
        return ["no_suite_declared"]
    gaps = []
    if not isinstance(run, dict) or not isinstance(run.get("results"), list):
        gaps.append("suite_not_run")
    else:
        label = str(run.get("suite"))
        if not label.startswith(f"suite:{declared['suite_id']}@"):
            gaps.append("wrong_suite")
        elif declared.get("suite_version") and not label.startswith(f"suite:{declared['suite_id']}@{declared['suite_version']}#"):
            gaps.append("wrong_suite_version")
        status = {r.get("criterion_id"): r.get("status") for r in run["results"] if isinstance(r, dict)}
        required = declared.get("required_cases") if isinstance(declared.get("required_cases"), list) and declared["required_cases"] else sorted(status)
        if not required:
            gaps.append("no_cases")
        gaps += [f"case_not_passed:{case}" for case in required if status.get(case) != "PASS"]
    if not (isinstance(review, dict) and review.get("verdict") == "PASS" and review.get("reviewer") and review.get("reviewer") != review.get("builder")):
        gaps.append("independent_review_missing")
    if not decision:
        gaps.append("guppi_decision_missing")
    return sorted(set(gaps))


class InstanceService:
    def __init__(self, registry, guard, audit=None):
        self.registry, self.guard, self.audit = registry, guard, audit

    def _event(self, name, mission_id, payload):
        if self.audit:
            self.audit.append(name, component="agent_manager", mission_id=mission_id, actor="claude", payload=payload)

    def _template(self, ref):
        entry = self.registry.get("template", ref) if isinstance(ref, str) and ref else None
        if entry is None:
            raise ContractError("agent_unknown", "no such template")
        if not entry["data"]["preview"]["ok"]:
            raise ContractError("agent_not_importable", "the import preview of this template has problems")
        return entry["data"]

    def _instance(self, instance_id):
        entry = self.registry.get("agent", instance_id) if isinstance(instance_id, str) and instance_id else None
        if entry is None:
            raise ContractError("instance_unknown", "no such instance")
        return entry

    def instantiation_gate(self, template_ref, purpose, mission_id, model_key=None):
        data = self._template(template_ref)
        if not isinstance(purpose, str) or not 3 <= len(purpose) <= 200:
            raise ContractError("bad_purpose", "purpose must be 3 to 200 characters")
        risks = ["creates a crew instance, UNVERIFIED and WITHOUT admission: it cannot be assigned to a run until it is promoted", "no process, VM or model is started"]
        if model_key is not None and not (isinstance(model_key, str) and 2 <= len(model_key) <= 60):
            raise ContractError("bad_model_key", "model_key must be 2 to 60 characters")
        gate = self.guard.create_gate(mission_id, INSTANTIATE, template_ref, risks=risks, rollback_available=True,
                                      request_binding={"template_ref": template_ref, "template_digest": data["digest"], "purpose": purpose, "model_key": model_key})
        gate["agent_manager"] = {"purpose": purpose, "model_key": model_key}
        self._event("AGENT_INSTANTIATION_PROPOSED", mission_id, {"gate_id": gate["gate_id"], "template": template_ref})
        return gate

    def instantiate(self, gate, token):
        ref = gate["request"]["targets"][0]
        purpose = gate["agent_manager"]["purpose"]
        data = self._template(ref)
        model_key = gate["agent_manager"].get("model_key")
        binding = {"template_ref": ref, "template_digest": data["digest"], "purpose": purpose, "model_key": model_key}
        decision = self.guard.authorize(token, mission_id=gate["mission_id"], action=INSTANTIATE, target=ref, request_binding=binding)
        if not decision.get("authorized"):
            raise ContractError("admission_refused", str(decision.get("reason")))
        instance_id = make_id("ins", {"gate": gate["gate_id"], "template": ref})
        record = {"template_ref": ref, "template_digest": data["digest"], "purpose": purpose, "model_key": model_key, "qualification": "UNVERIFIED", "lifecycle": "ACTIVE",
                  "admission": {"valid": False, "revoked": False}, "stats": {"successes": 0, "runs": 0}, "suite_runs": [], "review": None, "builder": None}
        self.registry.command(f"cmd-{instance_id}", "create", "agent", instance_id, record)
        self._event("AGENT_INSTANTIATED", gate["mission_id"], {"instance": instance_id, "template": ref})
        return {"instance_id": instance_id, **record}

    def record_suite_run(self, instance_id, run, builder):
        """Stores a suite run (summary only) for the instance and names the model that built the candidate (needed for the independence rule)."""
        entry = self._instance(instance_id)
        summary = {"suite": run["suite"], "suite_digest": run["suite_digest"], "candidate_hash": run["candidate_hash"], "results": [{"criterion_id": r["criterion_id"], "status": r["status"]} for r in run["results"]]}
        data = {**entry["data"], "suite_runs": (entry["data"]["suite_runs"] + [summary])[-MAX_RUNS:], "builder": str(builder)}
        return self.registry.update("agent", instance_id, data, entry["revision"])

    def record_review(self, instance_id, reviewer, verdict, candidate_hash):
        """An independent review of the candidate named by `candidate_hash` (the one of the latest suite run); it only counts when the reviewer is another model than the builder."""
        entry = self._instance(instance_id)
        if verdict not in ("PASS", "FAIL"):
            raise ContractError("bad_verdict", str(verdict))
        data = {**entry["data"], "review": {"reviewer": str(reviewer), "builder": entry["data"]["builder"], "verdict": verdict, "candidate_hash": candidate_hash}}
        return self.registry.update("agent", instance_id, data, entry["revision"])

    def gaps(self, instance_id, decision=False):
        entry = self._instance(instance_id)
        data = entry["data"]
        template = self._template(data["template_ref"])["template"]
        run = data["suite_runs"][-1] if data["suite_runs"] else None
        review = data["review"] if data["review"] and run and data["review"].get("candidate_hash") == run["candidate_hash"] else None
        return promotion_gaps(template.get("verification"), run, review, decision)

    def promotion_gate(self, instance_id, mission_id):
        gaps = self.gaps(instance_id, decision=True)
        if gaps:
            raise ContractError("promotion_gaps", ", ".join(gaps))
        data = self._instance(instance_id)["data"]
        run = data["suite_runs"][-1]
        risks = [f"VERIFIED and a valid admission for {instance_id}", f"based on {run['suite']} (all required cases PASS) for candidate {run['candidate_hash'][:12]} and an independent review by {data['review']['reviewer']}",
                 "assignments can then start runs for this instance; revoking is possible at any time without a gate"]
        gate = self.guard.create_gate(mission_id, PROMOTE, instance_id, risks=risks, rollback_available=True,
                                      request_binding={"instance_id": instance_id, "suite": run["suite"], "candidate_hash": run["candidate_hash"], "reviewer": data["review"]["reviewer"]})
        self._event("AGENT_PROMOTION_PROPOSED", mission_id, {"gate_id": gate["gate_id"], "instance": instance_id})
        return gate

    def promote(self, gate, token):
        instance_id = gate["request"]["targets"][0]
        entry = self._instance(instance_id)
        data = entry["data"]
        if self.gaps(instance_id, decision=True):
            raise ContractError("promotion_gaps", ", ".join(self.gaps(instance_id, decision=True)))
        run = data["suite_runs"][-1]
        binding = {"instance_id": instance_id, "suite": run["suite"], "candidate_hash": run["candidate_hash"], "reviewer": data["review"]["reviewer"]}
        decision = self.guard.authorize(token, mission_id=gate["mission_id"], action=PROMOTE, target=instance_id, request_binding=binding)
        if not decision.get("authorized"):
            raise ContractError("admission_refused", str(decision.get("reason")))
        admission = {"valid": True, "revoked": False, "gate_id": gate["gate_id"], "suite": run["suite"], "candidate_hash": run["candidate_hash"]}
        updated = self.registry.update("agent", instance_id, {**data, "qualification": "VERIFIED", "admission": admission}, entry["revision"])
        self._event("AGENT_PROMOTED", gate["mission_id"], {"instance": instance_id, "suite": run["suite"]})
        return updated

    def revoke(self, instance_id, reason):
        """Takes the admission away and quarantines the instance. Needs no gate: removing rights is always allowed."""
        entry = self._instance(instance_id)
        data = {**entry["data"], "admission": {**entry["data"]["admission"], "valid": False, "revoked": True, "reason": str(reason)[:200]}, "lifecycle": "QUARANTINED"}
        updated = self.registry.update("agent", instance_id, data, entry["revision"])
        self._event("AGENT_ADMISSION_REVOKED", None, {"instance": instance_id, "reason": str(reason)[:200]})
        return updated

    def record_outcome(self, instance_id, succeeded):
        """Counts a finished run for the success rate of the matcher; an uncertain run is never counted (call it only with a known outcome)."""
        entry = self._instance(instance_id)
        stats = dict(entry["data"]["stats"])
        stats["runs"] += 1
        stats["successes"] += 1 if succeeded else 0
        return self.registry.update("agent", instance_id, {**entry["data"], "stats": stats}, entry["revision"])

    def assemble(self, crew_ref, snapshot):
        """Plans a crew of the registered crew template `crew_ref` from the real instances (crews.assemble); only recommends."""
        entry = self.registry.get("crew", crew_ref) if isinstance(crew_ref, str) and crew_ref else None
        if entry is None:
            raise ContractError("crew_unknown", "no such crew template")
        return assemble(entry["data"]["crew"], self.candidates(), snapshot)

    def match(self, requirement, snapshot):
        """The matcher over the real instances: an instance without a valid admission, or not VERIFIED when the requirement asks for it, is excluded with its reasons."""
        return match(requirement, self.candidates(), snapshot)

    def candidates(self, available="now"):
        """The instances in the shape the matcher expects (agent_matcher.match); the capabilities and resource needs come from the template."""
        out = []
        for entry in self.registry.list("agent"):
            data = entry["data"]
            template = self.registry.get("template", data["template_ref"])
            template_data = template["data"]["template"] if template else {}
            runtime = template_data.get("runtime") if isinstance(template_data.get("runtime"), dict) else {}
            out.append({"agent_id": entry["key"], "lifecycle": data["lifecycle"], "qualification": data["qualification"], "admission": data["admission"],
                        "template_ref": data["template_ref"], "template_digest": str(data["template_digest"]).removeprefix("sha256:"), "model_key": data.get("model_key") or runtime.get("model_profile_id"),
                        "capabilities": template_data.get("capabilities") if isinstance(template_data.get("capabilities"), list) else [], "stats": data["stats"], "available": available,
                        "resources": (template_data.get("resources") if isinstance(template_data.get("resources"), dict) else {})})
        return out
