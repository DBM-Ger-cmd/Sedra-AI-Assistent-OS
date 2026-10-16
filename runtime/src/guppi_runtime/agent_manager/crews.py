"""Crew templates and crew assembly (AM-009).

A crew template names slots (a template, its pinned digest, the capabilities and minimum qualification the slot needs) and a workflow (a graph of steps with contracts between them) and the
independence rules between slots. This module checks such a template (`validate_crew`), orders it (`step_levels`) and assembles a crew from the real instances (`assemble`): every slot is
matched on its own by the matcher, then ONE combination is chosen for all slots together, because a slot that fits alone may not fit with the others:

  * the same instance never fills two exclusive slots;
  * an independence rule (builder and reviewer) needs different instances and, when both model keys are known, different models;
  * an instance whose template digest differs from the slot's pin is not a candidate for it;
  * with resource_mode "parallel" the resource needs of the steps of one level are added up and must fit the free resources.

The result is a plan that only recommends: nothing is reserved or started here. It is deterministic and does not depend on the order of the candidates.
"""
import re

from .agent_matcher import match, resource_fit

SCHEMA = "guppi.crew-template/v1"
ID = re.compile(r"[a-z][a-z0-9_.\-]{2,127}")
SEMVER = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
HEX64 = re.compile(r"[0-9a-f]{64}")
QUALIFICATIONS = ("VERIFIED", "PROVEN", "TRUSTED")
EFFECTS = ("read_only", "proposal_only", "preview", "reversible_write", "destructive_write", "external_side_effect", "privileged")
KINDS = ("agent_step", "system_decision")
MODES = ("sequential", "parallel")
RESOURCES = ("cpu_cores", "ram_mib", "vram_mib", "disk_mib", "vm_slots")


def _text(value, pattern):
    return isinstance(value, str) and bool(pattern.fullmatch(value))


def _slot_problems(slot):
    if not isinstance(slot, dict):
        return ["bad_slot"]
    out = []
    if not _text(slot.get("id"), ID):
        out.append("bad_slot")
    if not (_text(slot.get("template_id"), ID) and _text(slot.get("template_version"), SEMVER) and _text(slot.get("template_sha256"), HEX64)):
        out.append("bad_slot_template")
    if slot.get("minimum_qualification") not in QUALIFICATIONS:
        out.append("bad_slot_qualification")
    if not isinstance(slot.get("exclusive"), bool):
        out.append("bad_slot")
    requirements = slot.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        out.append("bad_slot_requirements")
    else:
        for requirement in requirements:
            ok = isinstance(requirement, dict) and _text(requirement.get("id"), ID) and _text(requirement.get("minimum_version"), SEMVER) and requirement.get("side_effect") in EFFECTS
            if not ok:
                out.append("bad_slot_requirements")
    return out


def _has_cycle(depends):
    state = {}

    def visit(node):
        if state.get(node) == 2:
            return False
        if state.get(node) == 1:
            return True
        state[node] = 1
        found = any(visit(parent) for parent in depends.get(node, ()) if parent in depends)
        state[node] = 2
        return found
    return any(visit(node) for node in depends)


def validate_crew(crew):
    """The sorted unique problem codes of a crew template (empty = usable). Never raises."""
    if not isinstance(crew, dict):
        return ["not_a_crew"]
    out = set()
    if crew.get("schema_version") != SCHEMA:
        out.add("schema_version")
    if not _text(crew.get("id"), ID):
        out.add("bad_id")
    if not _text(crew.get("version"), SEMVER):
        out.add("bad_version")
    slots = crew.get("slots")
    slot_ids = []
    if not isinstance(slots, list) or not slots:
        out.add("no_slots")
    else:
        for slot in slots:
            out.update(_slot_problems(slot))
            if isinstance(slot, dict) and isinstance(slot.get("id"), str):
                slot_ids.append(slot["id"])
        if len(set(slot_ids)) != len(slot_ids):
            out.add("duplicate_slot")
    workflow = crew.get("workflow")
    steps = {}
    if not isinstance(workflow, list) or not workflow:
        out.add("no_workflow")
    else:
        for step in workflow:
            if not isinstance(step, dict) or not _text(step.get("id"), ID) or step.get("kind") not in KINDS or not isinstance(step.get("depends_on"), list):
                out.add("bad_step")
                continue
            if step["id"] in steps:
                out.add("duplicate_step")
            steps[step["id"]] = step
            if step["kind"] == "agent_step" and step.get("slot_id") not in slot_ids:
                out.add("unknown_slot")
            if step["kind"] == "system_decision" and step.get("slot_id") is not None:
                out.add("bad_step")
        depends = {}
        for sid, step in steps.items():
            parents = [p for p in step["depends_on"] if isinstance(p, str)]
            if any(p not in steps for p in parents) or sid in parents:
                out.add("unknown_dependency")
            depends[sid] = parents
            for parent in parents:
                if parent in steps and steps[parent].get("output_contract") != step.get("input_contract"):
                    out.add("contract_mismatch")
        if "unknown_dependency" not in out and _has_cycle(depends):
            out.add("cycle")
        used = {s.get("slot_id") for s in steps.values() if s.get("kind") == "agent_step"}
        if any(sid not in used for sid in slot_ids):
            out.add("orphan_slot")
    for rule in crew.get("independence") if isinstance(crew.get("independence"), list) else []:
        if not isinstance(rule, dict) or rule.get("left_slot") not in slot_ids or rule.get("right_slot") not in slot_ids or rule.get("left_slot") == rule.get("right_slot"):
            out.add("bad_independence")
    limits = crew.get("limits")
    if not isinstance(limits, dict) or type(limits.get("max_iterations")) is not int or not 1 <= limits["max_iterations"] <= 10 or type(limits.get("max_wall_seconds")) is not int \
            or limits["max_wall_seconds"] < 1 or limits.get("resource_mode") not in MODES:
        out.add("bad_limits")
    return sorted(out)


def step_levels(crew):
    """The workflow steps in execution order, as levels: a step is in the first level in which all its dependencies are done. Steps of one level may run at the same time."""
    problems = validate_crew(crew)
    if problems:
        raise ValueError("invalid_crew:" + ",".join(problems))
    steps = {s["id"]: s for s in crew["workflow"]}
    done, levels = set(), []
    while len(done) < len(steps):
        level = sorted(sid for sid, step in steps.items() if sid not in done and all(p in done for p in step["depends_on"]))
        levels.append(level)
        done.update(level)
    return levels


def _requirement(slot):
    return {"must": [{"id": r["id"], "minimum_version": r["minimum_version"]} for r in slot["requirements"] if r.get("required", True)], "can": [],
            "min_qualification": slot["minimum_qualification"], "effects_allowed": sorted({r["side_effect"] for r in slot["requirements"]})}


def _pinned(slot, candidates):
    wanted = f"{slot['template_id']}@{slot['template_version']}"
    return [c for c in candidates if c.get("template_ref") == wanted and c.get("template_digest") == slot["template_sha256"]]


def _independent(rules, picks, models):
    for rule in rules:
        left, right = picks.get(rule["left_slot"]), picks.get(rule["right_slot"])
        if left is None or right is None:
            continue
        if rule.get("different_agent_instance", True) and left == right:
            return False
        if models.get(left) and models.get(left) == models.get(right):
            return False
    return True


def _search(order, options, rules, models, slots):
    """Highest total score over the combinations that satisfy the exclusivity and independence rules; ties go to the smaller agent ids."""
    best = [None]

    def walk(index, picks, total):
        if index == len(order):
            total = round(total, 6)
            if best[0] is None or total > best[0][0] or (total == best[0][0] and [picks[s] for s in order] < [best[0][1][s] for s in order]):
                best[0] = (total, dict(picks))
            return
        slot_id = order[index]
        for candidate in options[slot_id]:
            agent = candidate["agent_id"]
            if slots[slot_id].get("exclusive") and any(slots[other].get("exclusive") and chosen == agent for other, chosen in picks.items()):
                continue
            picks[slot_id] = agent
            if _independent(rules, picks, models):
                walk(index + 1, picks, total + candidate["score"])
            del picks[slot_id]
    walk(0, {}, 0.0)
    return best[0]


def assemble(crew, candidates, snapshot):
    """Plans a crew from `candidates` (the instances in the matcher's shape, plus template_ref, template_digest, model_key and resources). Returns
    {"ok", "crew", "problems", "order", "assignments": {slot: {"agent_id", "score"}}, "gaps", "queued"}."""
    problems = validate_crew(crew)
    ref = f"{crew.get('id')}@{crew.get('version')}" if isinstance(crew, dict) else None
    plan = {"ok": False, "crew": ref, "problems": problems, "order": [], "assignments": {}, "gaps": [], "queued": []}
    if problems:
        return plan
    plan["order"] = step_levels(crew)
    slots = {s["id"]: s for s in crew["slots"]}
    steps = {s["id"]: s for s in crew["workflow"]}
    order = list(dict.fromkeys(steps[sid]["slot_id"] for level in plan["order"] for sid in level if steps[sid]["kind"] == "agent_step"))
    options = {}
    for slot_id in order:
        pool = _pinned(slots[slot_id], candidates)
        result = match(_requirement(slots[slot_id]), pool, snapshot)
        options[slot_id] = sorted(result["eligible"], key=lambda e: (-e["score"], e["agent_id"]))
        if not options[slot_id]:
            reason = "no_candidate_for_pin" if not pool else ("resources_not_available" if result["queued"] else "no_eligible_instance")
            plan["gaps"].append({"slot": slot_id, "reason": reason, "queued": result["queued"], "excluded": [{"agent_id": e["agent_id"], "reasons": [r["reason_code"] for r in e["reasons"]]} for e in result["excluded"]],
                                 "missing_capabilities": (result["gaps"][0]["missing_capabilities"] if result["gaps"] else [])})
    if plan["gaps"]:
        plan["queued"] = [{"slot": g["slot"], "candidates": g["queued"]} for g in plan["gaps"] if g["queued"]]
        return plan
    models = {c["agent_id"]: c.get("model_key") for c in candidates}
    rules = crew.get("independence") if isinstance(crew.get("independence"), list) else []
    found = _search(order, options, rules, models, slots)
    if found is None:
        plan["gaps"].append({"slot": None, "reason": "no_combination_satisfies_exclusivity_and_independence", "queued": [], "excluded": [], "missing_capabilities": []})
        return plan
    picks = found[1]
    by_agent = {c["agent_id"]: c for c in candidates}
    scores = {slot_id: next(e["score"] for e in options[slot_id] if e["agent_id"] == picks[slot_id]) for slot_id in order}
    if crew["limits"]["resource_mode"] == "parallel":
        for level in plan["order"]:
            need = {}
            for sid in level:
                step = steps[sid]
                if step["kind"] == "agent_step":
                    for key, value in (by_agent[picks[step["slot_id"]]].get("resources") or {}).items():
                        need[key] = need.get(key, 0) + (value if isinstance(value, (int, float)) and value > 0 else 0)
            fit = resource_fit({k: v for k, v in need.items() if k in RESOURCES}, snapshot)
            if fit["state"] != "ok":
                plan["gaps"].append({"slot": None, "reason": "level_" + fit["state"], "queued": [], "excluded": [], "missing_capabilities": [], "level": level})
                plan["queued"].append({"level": level, "reason": fit["state"]})
                return plan
    plan["assignments"] = {slot_id: {"agent_id": picks[slot_id], "score": scores[slot_id]} for slot_id in order}
    plan["ok"] = True
    return plan
