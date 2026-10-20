import os
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.selfdev.acceptance_suite import candidate_hash, host_runner, load_suite, run_suite, write_suite
from guppi_runtime.agent_manager.agent_contracts import ContractError
from guppi_runtime.agent_manager.agent_registry import Registry
from guppi_runtime.agent_manager.instances import InstanceService, promotion_gaps
from guppi_runtime.core.audit import AuditLog
from guppi_runtime.core.guard import Guard

ARCHITECTURE = sorted((Path(__file__).resolve().parents[2] / "architecture").glob("GUPPI_Architecture_v*"))[-1]
REF = "guppi.agent.demo@1.0.0"
CRITERIA = [{"id": "calc.add", "description": "add", "script": "t_add.py", "text": "from calc import add\nassert add(1, 2) == 3\n"},
            {"id": "calc.neg", "description": "neg", "script": "t_neg.py", "text": "from calc import add\nassert add(-1, 1) == 0\n"}]
GOOD = {"calc.py": "def add(a, b):\n    return a + b\n"}
BAD = {"calc.py": "def add(a, b):\n    return a - b\n"}
REQUIREMENT = {"must": [{"id": "code.write", "minimum_version": "1.0.0"}], "can": [], "min_qualification": "VERIFIED", "effects_allowed": ["reversible_write"]}


class InstanceCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.registry = Registry(os.path.join(self.tmp.name, "registry.sqlite"))
        self.addCleanup(self.registry.close)
        self.audit = AuditLog(Path(self.tmp.name) / "audit.jsonl")
        self.guard = Guard(ARCHITECTURE / "core" / "guard" / "guard_rules.yaml", self.audit, Path(self.tmp.name) / "tokens.json")
        template = {"role": "Demo", "capabilities": [{"id": "code.write", "version": "1.2.0", "side_effect": "reversible_write"}],
                    "verification": {"suite_id": "calc.demo", "suite_version": "1", "required_cases": ["calc.add", "calc.neg"]}}
        self.registry.create("template", REF, {"template": template, "preview": {"ok": True, "problems": []}, "trust": "UNVERIFIED", "digest": "d" * 64})
        self.registry.create("template", "guppi.agent.bad@1.0.0", {"template": {}, "preview": {"ok": False, "problems": ["soul_hash"]}, "trust": "UNVERIFIED", "digest": "e" * 64})
        self.service = InstanceService(self.registry, self.guard, self.audit)
        self.suite = write_suite(os.path.join(self.tmp.name, "suite"), "calc.demo", "1", CRITERIA, GOOD)

    def events(self):
        return [__import__("json").loads(line)["event_type"] for line in (Path(self.tmp.name) / "audit.jsonl").read_text(encoding="utf-8").splitlines()]

    def hire(self, purpose="build small modules", mission="M-1"):
        gate = self.service.instantiation_gate(REF, purpose, mission)
        return gate, self.guard.approve(gate)

    def instance(self):
        gate, token = self.hire()
        return self.service.instantiate(gate, token)["instance_id"]

    def promotable(self, files=GOOD, reviewer="gemma", builder="qwen3-coder"):
        instance_id = self.instance()
        run = run_suite(self.suite, files, host_runner())
        self.service.record_suite_run(instance_id, run, builder)
        self.service.record_review(instance_id, reviewer, "PASS", run["candidate_hash"])
        return instance_id, run


class InstantiationTest(InstanceCase):
    def test_a_gate_is_needed_and_the_instance_starts_unverified_without_admission(self):
        gate, token = self.hire()
        record = self.service.instantiate(gate, token)
        self.assertEqual((record["qualification"], record["lifecycle"], record["admission"]), ("UNVERIFIED", "ACTIVE", {"valid": False, "revoked": False}))
        self.assertTrue(record["instance_id"].startswith("ins-"))
        self.assertEqual(self.registry.get("agent", record["instance_id"])["data"]["template_ref"], REF)
        self.assertTrue({"AGENT_INSTANTIATION_PROPOSED", "CAPTAIN_GATE_APPROVED", "AGENT_INSTANTIATED"} <= set(self.events()))

    def test_no_token_a_used_token_or_a_token_for_another_purpose_creates_nothing(self):
        gate, token = self.hire()
        for bad in (None, {}, {"status": "active", "token_id": "APR-FAKE0000"}):
            with self.assertRaises(ContractError) as ctx:
                self.service.instantiate(gate, bad)
            self.assertEqual(ctx.exception.code, "admission_refused")
        gate["agent_manager"]["purpose"] = "something else entirely"
        with self.assertRaises(ContractError):
            self.service.instantiate(gate, token)
        self.assertEqual(self.registry.list("agent"), [])
        gate["agent_manager"]["purpose"] = "build small modules"
        self.service.instantiate(gate, token)
        with self.assertRaises(ContractError):
            self.service.instantiate(gate, token)
        self.assertEqual(len(self.registry.list("agent")), 1)

    def test_unknown_or_unclean_templates_and_bad_purposes_get_no_gate(self):
        for ref, purpose, code in (("guppi.agent.nobody@1.0.0", "build small modules", "agent_unknown"), ("guppi.agent.bad@1.0.0", "build small modules", "agent_not_importable"), (REF, "x", "bad_purpose"), (REF, 5, "bad_purpose")):
            with self.assertRaises(ContractError) as ctx:
                self.service.instantiation_gate(ref, purpose, "M-1")
            self.assertEqual(ctx.exception.code, code)


class PromotionTest(InstanceCase):
    def test_gaps_walk_from_nothing_to_nothing(self):
        instance_id = self.instance()
        self.assertEqual(self.service.gaps(instance_id, decision=True), ["independent_review_missing", "suite_not_run"])
        run = run_suite(self.suite, BAD, host_runner())
        self.service.record_suite_run(instance_id, run, "qwen3-coder")
        self.assertEqual(self.service.gaps(instance_id, decision=True), ["case_not_passed:calc.add", "case_not_passed:calc.neg", "independent_review_missing"])
        run = run_suite(self.suite, GOOD, host_runner())
        self.service.record_suite_run(instance_id, run, "qwen3-coder")
        self.assertEqual(self.service.gaps(instance_id, decision=True), ["independent_review_missing"])
        self.service.record_review(instance_id, "qwen3-coder", "PASS", run["candidate_hash"])
        self.assertEqual(self.service.gaps(instance_id, decision=True), ["independent_review_missing"], "the builder cannot review itself")
        self.service.record_review(instance_id, "gemma", "FAIL", run["candidate_hash"])
        self.assertEqual(self.service.gaps(instance_id, decision=True), ["independent_review_missing"])
        self.service.record_review(instance_id, "gemma", "PASS", "0" * 64)
        self.assertEqual(self.service.gaps(instance_id, decision=True), ["independent_review_missing"], "a review of other files does not count")
        self.service.record_review(instance_id, "gemma", "PASS", run["candidate_hash"])
        self.assertEqual(self.service.gaps(instance_id, decision=True), [])
        self.assertEqual(self.service.gaps(instance_id), ["guppi_decision_missing"])

    def test_promotion_needs_the_gate_and_sets_verified_with_an_admission(self):
        instance_id, run = self.promotable()
        gate = self.service.promotion_gate(instance_id, "M-2")
        self.assertEqual((gate["request"]["exact_action"], gate["request"]["targets"]), ("agent.promote", [instance_id]))
        self.assertTrue(any(run["candidate_hash"][:12] in risk for risk in gate["request"]["risks"]))
        with self.assertRaises(ContractError) as ctx:
            self.service.promote(gate, None)
        self.assertEqual(ctx.exception.code, "admission_refused")
        self.assertEqual(self.registry.get("agent", instance_id)["data"]["qualification"], "UNVERIFIED")
        promoted = self.service.promote(gate, self.guard.approve(gate))
        data = promoted["data"]
        self.assertEqual((data["qualification"], data["admission"]["valid"], data["admission"]["suite"]), ("VERIFIED", True, run["suite"]))
        self.assertIn("AGENT_PROMOTED", self.events())

    def test_a_failing_suite_or_a_missing_review_refuses_even_the_gate(self):
        instance_id, _ = self.promotable(files=BAD)
        with self.assertRaises(ContractError) as ctx:
            self.service.promotion_gate(instance_id, "M-2")
        self.assertEqual(ctx.exception.code, "promotion_gaps")
        self.assertIn("case_not_passed:calc.add", str(ctx.exception))

    def test_a_token_is_bound_to_the_run_the_reviewer_and_the_instance(self):
        instance_id, run = self.promotable()
        gate = self.service.promotion_gate(instance_id, "M-2")
        token = self.guard.approve(gate)
        newer = run_suite(self.suite, {**GOOD, "calc.py": GOOD["calc.py"] + "\n"}, host_runner())
        self.service.record_suite_run(instance_id, newer, "qwen3-coder")
        self.service.record_review(instance_id, "gemma", "PASS", newer["candidate_hash"])
        with self.assertRaises(ContractError) as ctx:
            self.service.promote(gate, token)
        self.assertEqual(ctx.exception.code, "admission_refused")

    def test_revoking_needs_no_gate_and_quarantines(self):
        instance_id, _ = self.promotable()
        gate = self.service.promotion_gate(instance_id, "M-2")
        self.service.promote(gate, self.guard.approve(gate))
        revoked = self.service.revoke(instance_id, "found a problem")["data"]
        self.assertEqual((revoked["admission"]["valid"], revoked["admission"]["revoked"], revoked["lifecycle"]), (False, True, "QUARANTINED"))
        self.assertIn("AGENT_ADMISSION_REVOKED", self.events())

    def test_the_shared_rule_has_no_gap_only_with_everything(self):
        declared = {"suite_id": "s", "required_cases": ["a"]}
        run = {"suite": "suite:s@1#abc", "results": [{"criterion_id": "a", "status": "PASS"}]}
        review = {"verdict": "PASS", "reviewer": "x", "builder": "y"}
        self.assertEqual(promotion_gaps(declared, run, review, True), [])
        self.assertEqual(promotion_gaps(None, run, review, True), ["no_suite_declared"])
        self.assertEqual(promotion_gaps(declared, run, {**review, "reviewer": "y"}, True), ["independent_review_missing"])


class MatcherOnInstancesTest(InstanceCase):
    def snapshot(self):
        return {"cpu_cores": 8, "ram_mib": 16000}

    def test_unverified_instances_are_excluded_and_a_promoted_one_is_eligible(self):
        instance_id, _ = self.promotable()
        result = self.service.match(REQUIREMENT, self.snapshot())
        self.assertEqual(result["eligible"], [])
        self.assertEqual([r["reason_code"] for r in result["excluded"][0]["reasons"]], ["admission_invalid", "qualification_too_low"])
        gate = self.service.promotion_gate(instance_id, "M-2")
        self.service.promote(gate, self.guard.approve(gate))
        result = self.service.match(REQUIREMENT, self.snapshot())
        self.assertEqual([e["agent_id"] for e in result["eligible"]], [instance_id])
        self.assertEqual(result["excluded"], [])
        self.service.record_outcome(instance_id, True)
        self.service.record_outcome(instance_id, False)
        self.assertEqual(self.registry.get("agent", instance_id)["data"]["stats"], {"successes": 1, "runs": 2})

    def test_a_revoked_instance_drops_out_again(self):
        instance_id, _ = self.promotable()
        gate = self.service.promotion_gate(instance_id, "M-2")
        self.service.promote(gate, self.guard.approve(gate))
        self.service.revoke(instance_id, "x")
        result = self.service.match(REQUIREMENT, self.snapshot())
        self.assertEqual(result["eligible"], [])
        self.assertEqual([r["reason_code"] for r in result["excluded"][0]["reasons"]][:2], ["lifecycle", "admission_revoked"])


if __name__ == "__main__":
    unittest.main()
