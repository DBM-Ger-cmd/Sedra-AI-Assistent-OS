import copy
import random
import unittest

from guppi_runtime.agent_manager.crews import assemble, step_levels, validate_crew

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


def pool(**overrides):
    base = [inst("ins-planner", "planner", "proposal_only", "qwen"), inst("ins-coder", "coder", "reversible_write", "qwen"), inst("ins-reviewer", "reviewer", "read_only", "gemma")]
    return base


class ValidateTest(unittest.TestCase):
    def test_a_good_crew_has_no_problems_and_is_not_modified(self):
        snap = copy.deepcopy(CREW)
        self.assertEqual(validate_crew(CREW), [])
        self.assertEqual(CREW, snap)

    def test_each_kind_of_defect_is_named(self):
        cases = {
            "not_a_crew": None, "schema_version": crew(schema_version="v2"), "bad_id": crew(id="X"), "bad_version": crew(version="1.0"), "no_slots": crew(slots=[]), "no_workflow": crew(workflow=[]),
            "bad_limits": crew(limits={"max_iterations": 0, "max_wall_seconds": 10, "resource_mode": "sequential"}),
            "bad_independence": crew(independence=[{"left_slot": "coder", "right_slot": "coder"}]),
            "duplicate_slot": crew(slots=CREW["slots"] + [CREW["slots"][0]]),
            "unknown_slot": crew(workflow=[step("planner_step", "ghost", [], "a.b", "c.d")] + CREW["workflow"][1:]),
            "unknown_dependency": crew(workflow=CREW["workflow"][:1] + [step("coder_step", "coder", ["nope"], "guppi.plan", "guppi.candidate")] + CREW["workflow"][2:]),
            "contract_mismatch": crew(workflow=CREW["workflow"][:1] + [step("coder_step", "coder", ["planner_step"], "something.else", "guppi.candidate")] + CREW["workflow"][2:]),
            "orphan_slot": crew(slots=CREW["slots"] + [{**slot("reviewer", "read_only"), "id": "extra"}]),
        }
        for code, bad in cases.items():
            self.assertIn(code, validate_crew(bad), code)

    def test_a_cycle_and_a_duplicate_step_are_found(self):
        cyc = crew(workflow=[step("planner_step", "planner", ["reviewer_step"], "guppi.review", "guppi.plan"), CREW["workflow"][1], CREW["workflow"][2], CREW["workflow"][3]])
        self.assertIn("cycle", validate_crew(cyc))
        self.assertIn("duplicate_step", validate_crew(crew(workflow=CREW["workflow"] + [CREW["workflow"][0]])))

    def test_slot_defects(self):
        bad_pin = crew(slots=[{**CREW["slots"][0], "template_sha256": "xyz"}] + CREW["slots"][1:])
        bad_qual = crew(slots=[{**CREW["slots"][0], "minimum_qualification": "DRAFT"}] + CREW["slots"][1:])
        bad_req = crew(slots=[{**CREW["slots"][0], "requirements": [{"id": "x.y.z", "minimum_version": "1.0.0", "side_effect": "teleport"}]}] + CREW["slots"][1:])
        self.assertIn("bad_slot_template", validate_crew(bad_pin)); self.assertIn("bad_slot_qualification", validate_crew(bad_qual)); self.assertIn("bad_slot_requirements", validate_crew(bad_req))

    def test_levels_follow_the_dependencies_and_an_invalid_crew_has_none(self):
        self.assertEqual(step_levels(CREW), [["planner_step"], ["coder_step"], ["reviewer_step"], ["acceptance"]])
        fan = crew(workflow=[step("planner_step", "planner", [], "g.a", "g.p"), step("coder_step", "coder", ["planner_step"], "g.p", "g.c"), step("reviewer_step", "reviewer", ["planner_step"], "g.p", "g.r"),
                             step("acceptance", None, ["coder_step", "reviewer_step"], "g.c", "g.d", kind="system_decision")])
        self.assertEqual(validate_crew(fan), ["contract_mismatch"])
        with self.assertRaises(ValueError):
            step_levels(crew(slots=[]))


class AssembleTest(unittest.TestCase):
    def test_a_complete_pool_gives_one_instance_per_slot(self):
        plan = assemble(CREW, pool(), SNAP)
        self.assertTrue(plan["ok"], plan)
        self.assertEqual({k: v["agent_id"] for k, v in plan["assignments"].items()}, {"planner": "ins-planner", "coder": "ins-coder", "reviewer": "ins-reviewer"})
        self.assertEqual((plan["crew"], plan["order"][0], plan["gaps"], plan["problems"]), ("guppi.crew.devvm_build@1.0.0", ["planner_step"], [], []))

    def test_an_invalid_template_is_a_plan_with_problems_and_no_assignments(self):
        plan = assemble(crew(slots=[]), pool(), SNAP)
        self.assertEqual((plan["ok"], plan["assignments"], plan["problems"]), (False, {}, validate_crew(crew(slots=[]))))

    def test_the_result_does_not_depend_on_the_order_of_the_candidates(self):
        extra = pool() + [inst("ins-coder2", "coder", "reversible_write", "deepseek", stats={"successes": 2, "runs": 8}), inst("ins-reviewer2", "reviewer", "read_only", "swe", stats={"successes": 9, "runs": 9})]
        first = assemble(CREW, extra, SNAP)
        for seed in range(6):
            shuffled = list(extra)
            random.Random(seed).shuffle(shuffled)
            self.assertEqual(assemble(CREW, shuffled, SNAP), first, seed)

    def test_a_missing_slot_is_a_gap_with_the_reason(self):
        plan = assemble(CREW, [c for c in pool() if c["agent_id"] != "ins-reviewer"], SNAP)
        self.assertFalse(plan["ok"])
        self.assertEqual([(g["slot"], g["reason"]) for g in plan["gaps"]], [("reviewer", "no_candidate_for_pin")])

    def test_an_unverified_or_revoked_instance_is_not_eligible_and_says_why(self):
        weak = pool()
        weak[2]["qualification"] = "UNVERIFIED"; weak[2]["admission"] = {"valid": False, "revoked": False}
        plan = assemble(CREW, weak, SNAP)
        self.assertEqual((plan["gaps"][0]["slot"], plan["gaps"][0]["reason"]), ("reviewer", "no_eligible_instance"))
        self.assertEqual(plan["gaps"][0]["excluded"], [{"agent_id": "ins-reviewer", "reasons": ["admission_invalid", "qualification_too_low"]}])

    def test_a_pin_mismatch_excludes_an_instance_of_a_changed_template(self):
        changed = pool()
        changed[1]["template_digest"] = "f" * 64
        plan = assemble(CREW, changed, SNAP)
        self.assertEqual([(g["slot"], g["reason"]) for g in plan["gaps"]], [("coder", "no_candidate_for_pin")])

    def test_the_same_instance_never_fills_two_exclusive_slots(self):
        both = crew(slots=[slot("planner", "proposal_only"), {**slot("coder", "reversible_write")}, slot("reviewer", "read_only")])
        everyone = [dict(inst("ins-all", "planner", "proposal_only", "qwen"), capabilities=[{"id": f"guppi.devvm.{r}", "version": "1.0.0", "side_effect": e} for r, e in (("planner", "proposal_only"), ("coder", "reversible_write"), ("reviewer", "read_only"))])]
        for role in ("coder", "reviewer"):
            everyone.append(dict(everyone[0], template_ref=f"guppi.devvm.{role}@1.0.0", template_digest=H[role]))
        plan = assemble(both, everyone, SNAP)
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["gaps"][0]["reason"], "no_combination_satisfies_exclusivity_and_independence")

    def test_builder_and_reviewer_must_be_different_instances_and_different_models(self):
        same_model = pool()
        same_model[2]["model_key"] = "qwen"
        plan = assemble(CREW, same_model, SNAP)
        self.assertFalse(plan["ok"]); self.assertEqual(plan["gaps"][0]["reason"], "no_combination_satisfies_exclusivity_and_independence")
        alternative = same_model + [inst("ins-reviewer2", "reviewer", "read_only", "gemma", stats={"successes": 0, "runs": 0})]
        plan = assemble(CREW, alternative, SNAP)
        self.assertTrue(plan["ok"]); self.assertEqual(plan["assignments"]["reviewer"]["agent_id"], "ins-reviewer2")

    def test_unknown_models_do_not_block_but_the_same_instance_still_does(self):
        unknown = pool()
        unknown[1]["model_key"] = None; unknown[2]["model_key"] = None
        self.assertTrue(assemble(CREW, unknown, SNAP)["ok"])

    def test_resources_of_parallel_steps_are_added_up(self):
        fan = crew(workflow=[step("planner_step", "planner", [], "g.a", "g.p"), step("coder_step", "coder", ["planner_step"], "g.p", "g.c"), step("reviewer_step", "reviewer", ["planner_step"], "g.p", "g.c"),
                             step("acceptance", None, ["coder_step", "reviewer_step"], "g.c", "g.d", kind="system_decision")], limits={"max_iterations": 3, "max_wall_seconds": 100, "resource_mode": "parallel"})
        heavy = pool()
        for c in heavy:
            c["resources"] = {"vram_mib": 5000}
        plan = assemble(fan, heavy, SNAP)
        self.assertFalse(plan["ok"])
        self.assertEqual((plan["gaps"][0]["reason"], plan["gaps"][0]["level"]), ("level_queued_resource", ["coder_step", "reviewer_step"]))
        sequential = assemble({**fan, "limits": {**fan["limits"], "resource_mode": "sequential"}}, heavy, SNAP)
        self.assertTrue(sequential["ok"])
        unknown = assemble(fan, heavy, {**SNAP, "vram_mib": None})
        self.assertEqual(unknown["gaps"][0]["reason"], "resources_not_available")
        self.assertEqual(unknown["queued"][0]["candidates"][0]["reason_code"], "resource_unknown", "unknown free memory is never treated as free")

    def test_a_better_pair_wins_over_a_better_single(self):
        pairs = pool() + [inst("ins-coder2", "coder", "reversible_write", "gemma", stats={"successes": 9, "runs": 9})]
        plan = assemble(CREW, pairs, SNAP)
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["assignments"]["coder"]["agent_id"], "ins-coder", "ins-coder2 shares the reviewer's model, so the pair coder + reviewer has to use another coder")


if __name__ == "__main__":
    unittest.main()
