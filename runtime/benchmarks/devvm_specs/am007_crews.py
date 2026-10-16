"""AM-007 (crew planning), the first module that GUPPI builds for itself on the Captain's rule "GUPPI does the main work" (2026-10-08). Claude's part is only this file: the task text per stage,
the hidden tests, and (outside this file) an independent reference implementation that passes them (`agent_manager/crews.py`, written by Claude on 2026-10-08 and now the reference of the suite).
Six small stages, each with its own hidden test, and a last stage "all". The workspace is seeded with the accepted `agent_contracts.py` and `agent_matcher.py` (GUPPI's own earlier builds).
Build only, no integration."""

NOTES = '''# Notes for crew_planner
Pure Python 3 standard library, no file or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code, short functions.
It imports `match` and `resource_fit` from `agent_matcher.py` (already in this workspace, do not change it) and may use `ContractError` from `agent_contracts.py` (do not change it).
The module only PLANS: it never starts or reserves anything. Same input must always give the same output, also when the candidates are given in another order.
'''

COMMON = r'''
import copy
import random
from crew_planner import IMPORTS

H = {"planner": "a" * 64, "coder": "b" * 64, "reviewer": "c" * 64}


def slot(sid, effect, qual="VERIFIED", exclusive=True):
    return {"id": sid, "template_id": f"guppi.devvm.{sid}", "template_version": "1.0.0", "template_sha256": H[sid], "minimum_qualification": qual, "exclusive": exclusive,
            "requirements": [{"id": f"guppi.devvm.{sid}", "minimum_version": "1.0.0", "side_effect": effect, "required": True}]}


def step(sid, slot_id, depends, inp, out, kind="agent_step"):
    return {"id": sid, "kind": kind, "slot_id": slot_id, "depends_on": depends, "input_contract": inp, "output_contract": out, "on_failure": "rework", "requires_pass": True}


CREW = {
    "schema_version": "guppi.crew-template/v1", "id": "guppi.crew.devvm_build", "version": "1.0.0", "purpose": "plan, build, review",
    "slots": [slot("planner", "proposal_only"), slot("coder", "reversible_write"), slot("reviewer", "read_only")],
    "workflow": [step("planner_step", "planner", [], "guppi.gap", "guppi.plan"), step("coder_step", "coder", ["planner_step"], "guppi.plan", "guppi.candidate"),
                 step("reviewer_step", "reviewer", ["coder_step"], "guppi.candidate", "guppi.review"),
                 step("acceptance", None, ["reviewer_step"], "guppi.review", "guppi.decision", kind="system_decision")],
    "independence": [{"left_slot": "coder", "right_slot": "reviewer", "different_agent_instance": True, "separate_workspace": True}],
    "limits": {"max_iterations": 3, "max_wall_seconds": 10800, "resource_mode": "sequential"},
    "acceptance": {"authority": "guppi_officer"}, "initial_qualification": "DRAFT",
}
SNAP = {"cpu_cores": 8, "ram_mib": 16000, "vram_mib": 8000, "disk_mib": 100000, "vm_slots": 4}


def inst(agent_id, role, effect, model, **kw):
    c = {"agent_id": agent_id, "lifecycle": "ACTIVE", "qualification": "VERIFIED", "admission": {"valid": True, "revoked": False}, "template_ref": f"guppi.devvm.{role}@1.0.0",
         "template_digest": H[role], "model_key": model, "capabilities": [{"id": f"guppi.devvm.{role}", "version": "1.0.0", "side_effect": effect}], "stats": {"successes": 8, "runs": 8},
         "available": "now", "resources": {}}
    c.update(kw)
    return c


def crew(**changes):
    c = copy.deepcopy(CREW)
    c.update(changes)
    return c


def pool():
    return [inst("ins-planner", "planner", "proposal_only", "qwen"), inst("ins-coder", "coder", "reversible_write", "qwen"), inst("ins-reviewer", "reviewer", "read_only", "gemma")]
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r"""
snap = copy.deepcopy(CREW)
assert validate_crew(CREW) == [] and CREW == snap
for bad in (None, [], "x", 5, ()):
    assert validate_crew(bad) == ["not_a_crew"], bad
assert "schema_version" in validate_crew(crew(schema_version="v2")) and "schema_version" in validate_crew({k: v for k, v in CREW.items() if k != "schema_version"})
assert "bad_id" in validate_crew(crew(id="X")) and "bad_id" in validate_crew(crew(id="ab")) and "bad_id" in validate_crew(crew(id=5))
assert validate_crew(crew(id="a" * 128)) == [] and "bad_id" in validate_crew(crew(id="a" * 129))
assert "bad_version" in validate_crew(crew(version="1.0")) and "bad_version" in validate_crew(crew(version="1.0.x")) and "bad_version" in validate_crew(crew(version=None))
assert "no_slots" in validate_crew(crew(slots=[])) and "no_slots" in validate_crew(crew(slots="x")) and "no_workflow" in validate_crew(crew(workflow=[])) and "no_workflow" in validate_crew(crew(workflow=None))
many = validate_crew(crew(schema_version="v2", id="X", version="1"))
assert many == sorted(set(many)) and {"schema_version", "bad_id", "bad_version"} <= set(many)
"""

C2 = r"""
def with_slot(index, **changes):
    slots = copy.deepcopy(CREW["slots"])
    slots[index] = {**slots[index], **changes}
    return crew(slots=slots)
assert "duplicate_slot" in validate_crew(crew(slots=CREW["slots"] + [CREW["slots"][0]]))
for key, value in (("template_sha256", "xyz"), ("template_sha256", "A" * 64), ("template_sha256", "a" * 63), ("template_version", "1.0"), ("template_id", "X")):
    assert "bad_slot_template" in validate_crew(with_slot(0, **{key: value})), (key, value)
for qual in ("DRAFT", "UNVERIFIED", "verified", None):
    assert "bad_slot_qualification" in validate_crew(with_slot(0, minimum_qualification=qual)), qual
for qual in ("VERIFIED", "PROVEN", "TRUSTED"):
    assert validate_crew(with_slot(0, minimum_qualification=qual)) == [], qual
assert "bad_slot_requirements" in validate_crew(with_slot(0, requirements=[]))
assert "bad_slot_requirements" in validate_crew(with_slot(0, requirements="x"))
assert "bad_slot_requirements" in validate_crew(with_slot(0, requirements=[{"id": "x.y.z", "minimum_version": "1.0.0", "side_effect": "teleport"}]))
assert "bad_slot_requirements" in validate_crew(with_slot(0, requirements=[{"minimum_version": "1.0.0", "side_effect": "read_only"}]))
assert "bad_slot_requirements" in validate_crew(with_slot(0, requirements=[{"id": "x.y.z", "minimum_version": "1", "side_effect": "read_only"}]))
assert "bad_slot" in validate_crew(with_slot(0, exclusive="yes")) and "bad_slot" in validate_crew(with_slot(0, id="X"))
assert "bad_slot" in validate_crew(crew(slots=["x"] + CREW["slots"][1:]))
assert validate_crew(with_slot(0, exclusive=False)) == []
"""

C3 = r"""
def with_steps(*steps):
    return crew(workflow=list(steps))
w = CREW["workflow"]
assert "unknown_slot" in validate_crew(with_steps(step("planner_step", "ghost", [], "guppi.gap", "guppi.plan"), *w[1:]))
assert "unknown_dependency" in validate_crew(with_steps(w[0], step("coder_step", "coder", ["nowhere"], "guppi.plan", "guppi.candidate"), *w[2:]))
assert "unknown_dependency" in validate_crew(with_steps(step("planner_step", "planner", ["planner_step"], "guppi.gap", "guppi.plan"), *w[1:]))
assert "duplicate_step" in validate_crew(crew(workflow=w + [w[0]]))
assert "cycle" in validate_crew(with_steps(step("planner_step", "planner", ["reviewer_step"], "guppi.review", "guppi.plan"), *w[1:]))
assert "contract_mismatch" in validate_crew(with_steps(w[0], step("coder_step", "coder", ["planner_step"], "something.else", "guppi.candidate"), *w[2:]))
assert "orphan_slot" in validate_crew(crew(slots=CREW["slots"] + [{**slot("reviewer", "read_only"), "id": "extra"}]))
assert "bad_step" in validate_crew(with_steps(*w[:3], step("acceptance", "reviewer", ["reviewer_step"], "guppi.review", "guppi.decision", kind="system_decision")))
assert "bad_step" in validate_crew(with_steps(*w[:3], step("acceptance", None, ["reviewer_step"], "guppi.review", "guppi.decision", kind="magic")))
assert "bad_step" in validate_crew(crew(workflow=["x"] + w[1:]))
assert "cycle" not in validate_crew(CREW) and "unknown_dependency" not in validate_crew(CREW)
snap = copy.deepcopy(CREW); validate_crew(crew(workflow=w + [w[0]])); assert CREW == snap
"""

C4 = r"""
def with_independence(*rules): return crew(independence=list(rules))
assert "bad_independence" in validate_crew(with_independence({"left_slot": "coder", "right_slot": "coder"}))
assert "bad_independence" in validate_crew(with_independence({"left_slot": "coder", "right_slot": "ghost"}))
assert "bad_independence" in validate_crew(with_independence("x"))
assert validate_crew(with_independence()) == [] and validate_crew({k: v for k, v in CREW.items() if k != "independence"}) == []
def with_limits(**changes): return crew(limits={**CREW["limits"], **changes})
for changes in ({"max_iterations": 0}, {"max_iterations": 11}, {"max_iterations": True}, {"max_iterations": "3"}, {"max_wall_seconds": 0}, {"max_wall_seconds": 1.5}, {"resource_mode": "fast"}):
    assert "bad_limits" in validate_crew(with_limits(**changes)), changes
assert validate_crew(with_limits(max_iterations=10, max_wall_seconds=1, resource_mode="parallel")) == []
assert "bad_limits" in validate_crew({k: v for k, v in CREW.items() if k != "limits"})
assert step_levels(CREW) == [["planner_step"], ["coder_step"], ["reviewer_step"], ["acceptance"]]
w = CREW["workflow"]
fan = crew(workflow=[step("planner_step", "planner", [], "g.a", "g.p"), step("coder_step", "coder", ["planner_step"], "g.p", "g.c"), step("reviewer_step", "reviewer", ["planner_step"], "g.p", "g.c"),
                     step("acceptance", None, ["coder_step", "reviewer_step"], "g.c", "g.d", kind="system_decision")])
assert step_levels(fan) == [["planner_step"], ["coder_step", "reviewer_step"], ["acceptance"]]
shuffled = crew(workflow=[fan["workflow"][3], fan["workflow"][2], fan["workflow"][1], fan["workflow"][0]])
assert step_levels(shuffled) == step_levels(fan)
for bad in (crew(slots=[]), crew(workflow=w + [w[0]]), None):
    try: step_levels(bad)
    except ValueError: pass
    else: raise AssertionError("an invalid crew has no levels")
"""

C5 = r"""
plan = assemble(CREW, pool(), SNAP)
assert plan["ok"] is True and set(plan) == {"ok", "crew", "problems", "order", "assignments", "gaps", "queued"}, plan
assert {k: v["agent_id"] for k, v in plan["assignments"].items()} == {"planner": "ins-planner", "coder": "ins-coder", "reviewer": "ins-reviewer"}
assert plan["crew"] == "guppi.crew.devvm_build@1.0.0" and plan["order"] == [["planner_step"], ["coder_step"], ["reviewer_step"], ["acceptance"]] and plan["gaps"] == [] and plan["problems"] == [] and plan["queued"] == []
assert all(set(v) == {"agent_id", "score"} and isinstance(v["score"], float) for v in plan["assignments"].values())
bad = assemble(crew(slots=[]), pool(), SNAP)
assert bad["ok"] is False and bad["assignments"] == {} and bad["problems"] == validate_crew(crew(slots=[])) and bad["order"] == []
missing = assemble(CREW, [c for c in pool() if c["agent_id"] != "ins-reviewer"], SNAP)
assert missing["ok"] is False and [(g["slot"], g["reason"]) for g in missing["gaps"]] == [("reviewer", "no_candidate_for_pin")] and missing["assignments"] == {}
weak = pool(); weak[2]["qualification"] = "UNVERIFIED"; weak[2]["admission"] = {"valid": False, "revoked": False}
plan = assemble(CREW, weak, SNAP)
assert (plan["gaps"][0]["slot"], plan["gaps"][0]["reason"]) == ("reviewer", "no_eligible_instance")
assert plan["gaps"][0]["excluded"] == [{"agent_id": "ins-reviewer", "reasons": ["admission_invalid", "qualification_too_low"]}]
changed = pool(); changed[1]["template_digest"] = "f" * 64
assert [(g["slot"], g["reason"]) for g in assemble(CREW, changed, SNAP)["gaps"]] == [("coder", "no_candidate_for_pin")]
other = pool(); other[1]["template_ref"] = "guppi.devvm.coder@2.0.0"
assert [(g["slot"], g["reason"]) for g in assemble(CREW, other, SNAP)["gaps"]] == [("coder", "no_candidate_for_pin")]
nothing = assemble(CREW, [], SNAP)
assert [g["slot"] for g in nothing["gaps"]] == ["planner", "coder", "reviewer"] and {g["reason"] for g in nothing["gaps"]} == {"no_candidate_for_pin"}
pc, cr, sn = copy.deepcopy(pool()), copy.deepcopy(CREW), dict(SNAP); assemble(cr, pc, sn); assert pc == pool() and cr == CREW and sn == SNAP
"""

C6 = r"""
all_in_one = [inst("ins-all", r, e, "qwen", capabilities=[{"id": f"guppi.devvm.{x}", "version": "1.0.0", "side_effect": ef} for x, ef in (("planner", "proposal_only"), ("coder", "reversible_write"), ("reviewer", "read_only"))],
                   template_ref=f"guppi.devvm.{r}@1.0.0", template_digest=H[r]) for r, e in (("planner", "proposal_only"), ("coder", "reversible_write"), ("reviewer", "read_only"))]
plan = assemble(CREW, all_in_one, SNAP)
assert plan["ok"] is False and plan["gaps"][0]["reason"] == "no_combination_satisfies_exclusivity_and_independence"
same_model = pool(); same_model[2]["model_key"] = "qwen"
plan = assemble(CREW, same_model, SNAP)
assert plan["ok"] is False and plan["gaps"][0]["reason"] == "no_combination_satisfies_exclusivity_and_independence" and plan["gaps"][0]["slot"] is None
alternative = same_model + [inst("ins-reviewer2", "reviewer", "read_only", "gemma", stats={"successes": 0, "runs": 0})]
plan = assemble(CREW, alternative, SNAP)
assert plan["ok"] is True and plan["assignments"]["reviewer"]["agent_id"] == "ins-reviewer2"
unknown = pool(); unknown[1]["model_key"] = None; unknown[2]["model_key"] = None
assert assemble(CREW, unknown, SNAP)["ok"] is True
extra = pool() + [inst("ins-coder2", "coder", "reversible_write", "deepseek", stats={"successes": 2, "runs": 8}), inst("ins-reviewer2", "reviewer", "read_only", "swe", stats={"successes": 9, "runs": 9})]
first = assemble(CREW, extra, SNAP)
for seed in range(6):
    shuffled = list(extra); random.Random(seed).shuffle(shuffled)
    assert assemble(CREW, shuffled, SNAP) == first, seed
pairs = pool() + [inst("ins-coder2", "coder", "reversible_write", "gemma", stats={"successes": 9, "runs": 9})]
plan = assemble(CREW, pairs, SNAP)
assert plan["ok"] is True and plan["assignments"]["coder"]["agent_id"] == "ins-coder"
fan = crew(workflow=[step("planner_step", "planner", [], "g.a", "g.p"), step("coder_step", "coder", ["planner_step"], "g.p", "g.c"), step("reviewer_step", "reviewer", ["planner_step"], "g.p", "g.c"),
                     step("acceptance", None, ["coder_step", "reviewer_step"], "g.c", "g.d", kind="system_decision")], limits={"max_iterations": 3, "max_wall_seconds": 100, "resource_mode": "parallel"})
heavy = pool()
for c in heavy: c["resources"] = {"vram_mib": 5000}
plan = assemble(fan, heavy, SNAP)
assert plan["ok"] is False and (plan["gaps"][0]["reason"], plan["gaps"][0]["level"]) == ("level_queued_resource", ["coder_step", "reviewer_step"]) and plan["queued"][0]["level"] == ["coder_step", "reviewer_step"]
assert assemble({**fan, "limits": {**fan["limits"], "resource_mode": "sequential"}}, heavy, SNAP)["ok"] is True
unknown_mem = assemble(fan, heavy, {**SNAP, "vram_mib": None})
assert unknown_mem["ok"] is False and unknown_mem["gaps"][0]["reason"] == "resources_not_available" and unknown_mem["queued"][0]["candidates"][0]["reason_code"] == "resource_unknown"
light = pool()
for c in light: c["resources"] = {"vram_mib": 3000}
assert assemble(fan, light, SNAP)["ok"] is True
"""

NAMES = "validate_crew, step_levels, assemble"
FULL = C1 + C2 + C3 + C4 + C5 + C6
STYLE = " No comments and no docstrings. Put repeated checks into small private helpers. Never modify the arguments."

STAGES = [
    {"name": "basics",
     "task": """In this workspace `agent_contracts.py` and `agent_matcher.py` already exist (do not change them). Create `crew_planner.py` (Python 3 standard library only). Add `validate_crew(crew) -> list`: it returns the SORTED list of UNIQUE problem codes (str) of a crew template and never raises; an empty list means the crew is usable.
A crew is a dict with the keys schema_version, id, version, purpose, slots, workflow, independence, limits, acceptance, initial_qualification. In this stage check only:
- `crew` is not a dict: return exactly ["not_a_crew"].
- schema_version is not exactly "guppi.crew-template/v1": "schema_version" (a missing key counts).
- id is not a str that fully matches `[a-z][a-z0-9_.-]{2,127}`: "bad_id".
- version is not a str of the form "<n>.<n>.<n>" (ASCII digits only): "bad_version".
- `slots` is missing, not a list or empty: "no_slots". `workflow` is missing, not a list or empty: "no_workflow".
Never modify the argument.""" + STYLE + """ Add `tests/test_crew_planner.py` (unittest) with your own tests.""",
     "hidden": {"hidden_c1.py": hidden("validate_crew", C1)}},
    {"name": "slots",
     "task": """In the existing `crew_planner.py` (keep the other functions) extend `validate_crew` with the checks of every slot in `crew["slots"]` (a list of dicts):
- a slot that is not a dict, or whose "id" is not a str matching `[a-z][a-z0-9_.-]{2,127}`, or whose "exclusive" is not a bool: "bad_slot".
- two slots with the same id: "duplicate_slot".
- "template_id" must match the same id pattern, "template_version" must be "<n>.<n>.<n>", "template_sha256" must be exactly 64 lowercase hex characters; otherwise "bad_slot_template".
- "minimum_qualification" must be one of "VERIFIED", "PROVEN", "TRUSTED": otherwise "bad_slot_qualification".
- "requirements" must be a non-empty list of dicts; each needs an "id" matching the id pattern, a "minimum_version" of the form "<n>.<n>.<n>" and a "side_effect" that is one of "read_only", "proposal_only", "preview", "reversible_write", "destructive_write", "external_side_effect", "privileged"; otherwise "bad_slot_requirements" (once).""" + STYLE + """ Add tests to `tests/test_crew_planner.py`.""",
     "hidden": {"hidden_c2.py": hidden("validate_crew", C2)}},
    {"name": "graph",
     "task": """In the existing `crew_planner.py` (keep the other functions) extend `validate_crew` with the checks of `crew["workflow"]` (a list of step dicts with id, kind, slot_id, depends_on, input_contract, output_contract, on_failure, requires_pass).
- a step that is not a dict, whose "id" does not match the id pattern, whose "kind" is not "agent_step" or "system_decision", or whose "depends_on" is not a list: "bad_step". A "system_decision" step whose "slot_id" is not None: "bad_step" too.
- two steps with the same id: "duplicate_step".
- an "agent_step" whose "slot_id" is not the id of a slot: "unknown_slot".
- a step that depends on an id that is not a step (also on itself): "unknown_dependency".
- for every dependency: the dependency's "output_contract" must equal the step's "input_contract", otherwise "contract_mismatch".
- when no step has an unknown dependency and the dependencies contain a cycle: "cycle".
- a slot that no "agent_step" uses: "orphan_slot".""" + STYLE + """ Add tests to `tests/test_crew_planner.py`.""",
     "hidden": {"hidden_c3.py": hidden("validate_crew", C3)}},
    {"name": "rules",
     "task": """In the existing `crew_planner.py` (keep the other functions) extend `validate_crew` and add `step_levels`.
`validate_crew`: `crew["independence"]` (optional; a missing key is fine) must be a list of dicts whose "left_slot" and "right_slot" are ids of slots and are not the same slot, otherwise "bad_independence". `crew["limits"]` must be a dict with "max_iterations" an int from 1 to 10 (a bool is not an int here),
"max_wall_seconds" an int >= 1 and "resource_mode" one of "sequential", "parallel", otherwise "bad_limits" (a missing limits counts).
`step_levels(crew) -> list of lists`: the workflow step ids in execution order as levels: a step belongs to the first level in which all its dependencies are done (they are in earlier levels); the ids inside a level are sorted alphabetically. It must give the same result for a workflow
given in another order. For a crew where `validate_crew` returns any problem raise `ValueError("invalid_crew:" + the codes joined by ",")`.""" + STYLE + """ Add tests to `tests/test_crew_planner.py`.""",
     "hidden": {"hidden_c4.py": hidden("validate_crew, step_levels", C4)}},
    {"name": "assemble_basic",
     "task": """In the existing `crew_planner.py` (keep the other functions) add `assemble(crew, candidates, snapshot) -> dict`. `candidates` are instance dicts for the matcher of `agent_matcher.py` (`match(requirement, candidates, snapshot)`): agent_id, lifecycle, qualification, admission, capabilities, stats, available, resources, plus "template_ref" (e.g. "guppi.devvm.coder@1.0.0") and "template_digest" (64 hex).
The result always has exactly the keys "ok", "crew", "problems", "order", "assignments", "gaps", "queued"; "crew" is "<id>@<version>" of the template (None when the template is not a dict); "problems" is `validate_crew(crew)`.
If there are problems: ok False, order [], assignments {}, gaps [], queued [], and nothing else is done. Otherwise "order" is `step_levels(crew)`.
For each slot (in the order in which the agent steps of the workflow use it, each slot once): the candidates for it are those whose template_ref equals "<template_id>@<template_version>" of the slot AND whose template_digest equals the slot's template_sha256. They are matched with `match` using the requirement
{"must": the slot's requirements as {"id", "minimum_version"} (a requirement with "required": False is left out), "can": [], "min_qualification": the slot's minimum_qualification, "effects_allowed": the sorted unique side_effects of the slot's requirements} and the snapshot.
A slot with no eligible instance is a gap: {"slot": id, "reason": R, "queued": <the matcher's queued list>, "excluded": [{"agent_id", "reasons": [the reason codes]}] from the matcher's excluded list, "missing_capabilities": the missing ids of the matcher's first gap or []}, where R is "no_candidate_for_pin" when no candidate passed the pin check,
else "resources_not_available" when the matcher queued some, else "no_eligible_instance". When there are gaps: ok False, assignments {}, "queued" is [{"slot": id, "candidates": the matcher's queued list}] for the gaps that have queued candidates, and return.
When every slot has an eligible instance and there is more than one possible combination, take for now the best scored eligible instance of each slot (the combination rules come in the next stage); ok True and "assignments" is {slot id: {"agent_id", "score"}} (score = the matcher's score).""" + STYLE + """ Add tests to `tests/test_crew_planner.py`.""",
     "hidden": {"hidden_c5.py": hidden("validate_crew, step_levels, assemble", C5)}},
    {"name": "assemble_global",
     "task": """In the existing `crew_planner.py` (keep the other functions) make `assemble` choose ONE combination for all slots together instead of the best instance per slot. Among the eligible instances of every slot choose the combination with the highest total score such that:
1. the same agent_id is never used in two slots that are both "exclusive": True;
2. for every rule of `crew["independence"]` the two slots get different agent_ids when the rule's "different_agent_instance" is true (a missing key counts as true), and when both chosen instances have a non-empty "model_key" those keys must differ;
3. ties in the total score (compare rounded to 6 decimals) go to the combination whose list of agent_ids, in the order of the slots, is smaller.
If no combination satisfies the rules: ok False, assignments {} and the gaps are [{"slot": None, "reason": "no_combination_satisfies_exclusivity_and_independence", "queued": [], "excluded": [], "missing_capabilities": []}].
With `crew["limits"]["resource_mode"] == "parallel"`: for every level of "order" add up the "resources" (only the keys cpu_cores, ram_mib, vram_mib, disk_mib, vm_slots, positive numbers) of the chosen instances of the agent steps of that level and check the sum with `resource_fit(sum, snapshot)`; when its state is not "ok" the result is ok False, assignments {},
the gaps are [{"slot": None, "reason": "level_" + the state, "queued": [], "excluded": [], "missing_capabilities": [], "level": the step ids of the level}] and "queued" is [{"level": the step ids, "reason": the state}]. With "sequential" no sum is checked.
The result must not depend on the order of `candidates`.""" + STYLE + """ Add tests to `tests/test_crew_planner.py`.""",
     "hidden": {"hidden_c6.py": hidden("validate_crew, step_levels, assemble", C6)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_crew_planner.py` and read `crew_planner.py` once more. Make sure that no check is copied into several functions, that the file has no comments and no docstrings, and that there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_full_c.py": hidden(NAMES, FULL)}},
]
