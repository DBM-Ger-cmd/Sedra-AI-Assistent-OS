"""The first crew: the DevVM build team (integration stage 5, third step).

Planner, coder and reviewer of the DevVM become a crew template: plan -> build -> review -> SEDRA's decision. The slots pin the digests of the registered role templates, so a changed template is
not silently used; the reviewer must be another instance and, when the models are known, another model than the coder. The template is written as a file and comes back through the same
strict import path as any other crew (`AgentManager.import_crews`); nothing here registers or starts anything.
"""
import os

import yaml

from .devvm_templates import _NoAliasDumper

EFFECT = {"planner": "proposal_only", "coder": "reversible_write", "reviewer": "read_only"}


def devvm_crew(registry):
    slots = []
    for role in ("planner", "coder", "reviewer"):
        entry = registry.get("template", f"sedra.devvm.{role}@1.0.0")
        if entry is None:
            raise ValueError(f"template_not_imported:{role}")
        slots.append({"id": role, "template_id": f"sedra.devvm.{role}", "template_version": "1.0.0", "template_sha256": entry["data"]["digest"].removeprefix("sha256:"),
                      "requirements": [{"id": f"sedra.devvm.{role}", "minimum_version": "1.0.0", "side_effect": EFFECT[role], "required": True}], "minimum_qualification": "VERIFIED", "exclusive": True})

    def step(sid, slot, depends, inp, out, kind="agent_step"):
        return {"id": sid, "kind": kind, "slot_id": slot, "depends_on": depends, "input_contract": inp, "output_contract": out, "on_failure": "rework" if kind == "agent_step" else "needs_review", "requires_pass": True}
    return {
        "schema_version": "sedra.crew-template/v1", "id": "sedra.crew.devvm_build", "version": "1.0.0", "purpose": "Plan, build and review a small module in the DevVM; SEDRA decides on the evidence",
        "slots": slots,
        "workflow": [step("planner_step", "planner", [], "sedra.devvm.task", "sedra.devvm.plan"), step("coder_step", "coder", ["planner_step"], "sedra.devvm.plan", "sedra.devvm.candidate"),
                     step("reviewer_step", "reviewer", ["coder_step"], "sedra.devvm.candidate", "sedra.devvm.review"),
                     step("sedra_acceptance", None, ["reviewer_step"], "sedra.devvm.review", "sedra.acceptance_decision", kind="system_decision")],
        "independence": [{"left_slot": "coder", "right_slot": "reviewer", "different_agent_instance": True, "separate_workspace": True}],
        "limits": {"max_iterations": 3, "max_wall_seconds": 10800, "resource_mode": "sequential"},
        "acceptance": {"authority": "sedra_officer", "bind_candidate_digest": True, "bind_evidence_digest": True, "captain_gate": "policy_required"},
        "initial_qualification": "DRAFT",
    }


def export_devvm_crew(folder, registry):
    target = os.path.join(folder, "devvm_build")
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, "crew.yaml"), "w", encoding="utf-8", newline="\n") as handle:
        yaml.dump(devvm_crew(registry), handle, Dumper=_NoAliasDumper, sort_keys=False, allow_unicode=True)
    return ["devvm_build"]
