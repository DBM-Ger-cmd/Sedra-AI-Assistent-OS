import json
import tempfile
import unittest
from pathlib import Path
import env_skip

from guppi_runtime.agent_manager.agent_contracts import ContractError
from guppi_runtime.agent_manager.agent_registry import Registry
from guppi_runtime.agent_manager.bridge import FakeRuntime
from guppi_runtime.agent_manager.cli import Manager

ARCHITECTURE = sorted((Path(__file__).resolve().parents[2] / "architecture").glob("GUPPI_Architecture_v*"))[-1]
AGENT = "guppi.devvm.coder@1.0.0"


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "project"
        (self.project / "runtime_data" / "agent_manager").mkdir(parents=True)
        reg = Registry(str(self.project / "runtime_data" / "agent_manager" / "registry.sqlite"))
        reg.create("template", AGENT, {"preview": {"ok": True, "problems": []}})
        reg.create("template", "guppi.devvm.bad@1.0.0", {"preview": {"ok": False, "problems": ["soul_hash"]}})
        reg.close()
        self.runtime = FakeRuntime()
        self.manager = Manager(self.project, Path(self.tmp.name), ARCHITECTURE, runtime=self.runtime)
        self.addCleanup(self.manager.close)

    def events(self):
        path = self.project / "runtime_data" / "audit" / "events.jsonl"
        return [json.loads(line)["event_type"] for line in path.read_text(encoding="utf-8").splitlines()]

    def test_propose_shows_what_it_allows_and_does_not_approve(self):
        gate = self.manager.propose(AGENT, "M-1", "am_demo")
        self.assertEqual((gate["status"], gate["request"]["exact_action"], gate["request"]["targets"]), ("pending", "agent.assign", [AGENT]))
        self.assertTrue(any("GPU" in risk for risk in gate["request"]["risks"]))
        with self.assertRaises(ContractError) as ctx:
            self.manager.submit(gate["gate_id"])
        self.assertEqual(ctx.exception.code, "not_approved")
        self.assertEqual(self.runtime.start_calls, 0)
        self.assertIn("AGENT_ASSIGNMENT_PROPOSED", self.events())

    def test_unknown_or_unclean_template_gets_no_gate(self):
        for agent in ("guppi.devvm.nobody@1.0.0", "guppi.devvm.bad@1.0.0"):
            with self.assertRaises(ContractError):
                self.manager.propose(agent, "M-1", "am_demo")

    def test_full_path_approve_submit_status_and_replay(self):
        gate = self.manager.propose(AGENT, "M-1", "am_demo")
        self.manager.approve(gate["gate_id"])
        record = self.manager.submit(gate["gate_id"])
        self.assertEqual((record["state"], record["demo"], record["agent_ref"]), ("running", True, AGENT))
        again = self.manager.submit(gate["gate_id"])
        self.assertTrue(again["replayed"])
        self.assertEqual(self.runtime.start_calls, 1)
        self.runtime.finish()
        status = self.manager.status()
        self.assertEqual((status["reconciled"], status["assignments"][0]["state"]), (1, "succeeded"))
        self.assertTrue({"AGENT_ASSIGNMENT_PROPOSED", "CAPTAIN_GATE_APPROVED", "AGENT_ASSIGNMENT_SUBMITTED"} <= set(self.events()))

    def test_rejected_gate_cannot_be_submitted_or_approved_again(self):
        gate = self.manager.propose(AGENT, "M-1", "am_demo")
        self.manager.reject(gate["gate_id"])
        for call in (self.manager.submit, self.manager.approve):
            with self.assertRaises(ContractError):
                call(gate["gate_id"])
        self.assertEqual(self.runtime.start_calls, 0)

    def test_stop_ends_a_running_assignment_and_records_a_known_outcome(self):
        gate = self.manager.propose(AGENT, "M-1", "am_demo")
        self.manager.approve(gate["gate_id"])
        record = self.manager.submit(gate["gate_id"])
        stopped = self.manager.stop(record["assignment_id"], "Captain said so")
        self.assertEqual((stopped["state"], stopped["was_running"]), ("failed", True))
        self.assertIn("stopped: Captain said so", stopped["detail"])
        self.assertIn("AGENT_RUN_STOPPED", self.events())
        with self.assertRaises(ContractError) as ctx:
            self.manager.stop(record["assignment_id"], "again")
        self.assertEqual(ctx.exception.code, "not_running")
        with self.assertRaises(ContractError) as ctx:
            self.manager.stop("asg-000000000000", "x")
        self.assertEqual(ctx.exception.code, "assignment_unknown")

    def test_gate_ids_cannot_reach_other_files(self):
        for bad in ("HG-../../x", "../x", "HG-", "x"):
            with self.assertRaises(ContractError):
                self.manager.submit(bad)


class CrewFlowTest(unittest.TestCase):
    """The whole way: template -> gate -> instance -> suite in the runner -> independent review -> gap check -> gate -> VERIFIED -> matcher -> view."""

    def setUp(self):
        from guppi_runtime.acceptance_suite import write_suite
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "project"
        (self.project / "runtime_data" / "agent_manager").mkdir(parents=True)
        template = {"role": "Coder", "capabilities": [{"id": "code.write", "version": "1.2.0", "side_effect": "reversible_write"}],
                    "verification": {"suite_id": "calc.demo", "suite_version": "1", "required_cases": ["calc.add"]}}
        reg = Registry(str(self.project / "runtime_data" / "agent_manager" / "registry.sqlite"))
        reg.create("template", AGENT, {"template": template, "preview": {"ok": True, "problems": []}, "trust": "UNVERIFIED", "digest": "a" * 64})
        reg.close()
        write_suite(str(self.project / "acceptance" / "suites" / "calc"), "calc.demo", "1",
                    [{"id": "calc.add", "description": "add", "script": "t_add.py", "text": "from calc import add\nassert add(1, 2) == 3\n"}], {"calc.py": "def add(a, b):\n    return a + b\n"})
        self.candidate = Path(self.tmp.name) / "candidate"
        self.candidate.mkdir()
        (self.candidate / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        self.manager = Manager(self.project, Path(self.tmp.name), ARCHITECTURE, runtime=FakeRuntime())
        self.addCleanup(self.manager.close)

    def approved(self, gate):
        self.manager.approve(gate["gate_id"])
        return gate["gate_id"]

    @env_skip.needs_dulwich
    def test_from_template_to_a_matched_verified_instance_with_every_gate_in_the_audit(self):
        from guppi_runtime.acceptance_suite import host_runner
        gate = self.manager.hire(AGENT, "build small modules", "M-1")
        self.assertEqual(self.manager.registry.list("agent"), [])
        with self.assertRaises(ContractError):
            self.manager.create(gate["gate_id"])
        instance = self.manager.create(self.approved(gate))
        iid = instance["instance_id"]
        self.assertEqual(self.manager.instances.gaps(iid, decision=True), ["independent_review_missing", "suite_not_run"])
        run = self.manager.suite(iid, "calc", self.candidate, "qwen3-coder", runner=host_runner())
        self.assertTrue(run["passed"])
        with self.assertRaises(ContractError) as ctx:
            self.manager.propose_promotion(iid, "M-2")
        self.assertEqual(ctx.exception.code, "promotion_gaps")
        self.manager.review(iid, "qwen3-coder", "PASS")
        with self.assertRaises(ContractError):
            self.manager.propose_promotion(iid, "M-2")
        self.manager.review(iid, "gemma", "PASS")
        promotion = self.manager.propose_promotion(iid, "M-2")
        with self.assertRaises(ContractError):
            self.manager.promote(promotion["gate_id"])
        data = self.manager.promote(self.approved(promotion))["data"]
        self.assertEqual((data["qualification"], data["admission"]["valid"]), ("VERIFIED", True))
        requirement = {"must": [{"id": "code.write", "minimum_version": "1.0.0"}], "can": [], "min_qualification": "VERIFIED", "effects_allowed": ["reversible_write"]}
        self.assertEqual([e["agent_id"] for e in self.manager.instances.match(requirement, {"cpu_cores": 4})["eligible"]], [iid])
        self.manager.instances.revoke(iid, "test")
        self.assertEqual(self.manager.instances.match(requirement, {"cpu_cores": 4})["eligible"], [])
        events = [json.loads(line)["event_type"] for line in (self.project / "runtime_data" / "audit" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        for name in ("AGENT_INSTANTIATION_PROPOSED", "CAPTAIN_GATE_APPROVED", "AGENT_INSTANTIATED", "AGENT_SUITE_RUN", "AGENT_REVIEW_RECORDED", "AGENT_PROMOTION_PROPOSED", "AGENT_PROMOTED", "AGENT_ADMISSION_REVOKED"):
            self.assertIn(name, events)

    @env_skip.needs_dulwich
    def test_the_view_shows_the_instance_with_its_state(self):
        from guppi_runtime.acceptance_suite import host_runner
        from guppi_runtime.agent_manager.view import agents_view
        gate = self.manager.hire(AGENT, "build small modules", "M-1")
        iid = self.manager.create(self.approved(gate))["instance_id"]
        self.manager.suite(iid, "calc", self.candidate, "qwen3-coder", runner=host_runner())
        view = agents_view(self.project / "runtime_data" / "agent_manager" / "registry.sqlite")
        row = view["instances"][0]
        self.assertEqual((row["instance_id"], row["template_ref"], row["qualification"], row["admission"], row["revoked"], row["suite_passed"], row["suite_total"], row["review"]),
                         (iid, AGENT, "UNVERIFIED", False, False, 1, 1, None))
        self.assertTrue(row["suite"].startswith("suite:calc.demo@1#"))

    @env_skip.needs_dulwich
    def test_an_incomplete_candidate_and_unknown_suites_are_refused(self):
        gate = self.manager.hire(AGENT, "build small modules", "M-1")
        iid = self.manager.create(self.approved(gate))["instance_id"]
        (self.candidate / "calc.py").unlink()
        with self.assertRaises(ContractError) as ctx:
            self.manager.suite(iid, "calc", self.candidate, "qwen3-coder")
        self.assertEqual(ctx.exception.code, "candidate_incomplete")
        with self.assertRaises(Exception):
            self.manager.suite(iid, "../escape", self.candidate, "qwen3-coder")


if __name__ == "__main__":
    unittest.main()
