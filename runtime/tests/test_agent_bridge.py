import os
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.agent_manager.agent_contracts import ContractError
from guppi_runtime.agent_manager.agent_registry import Registry
from guppi_runtime.agent_manager.bridge import ACTION, AgentBridge, FakeRuntime
from guppi_runtime.core.guard import Guard

RULES = next(Path(__file__).resolve().parents[2].glob("architecture/*/core/guard/guard_rules.yaml"))
AGENT = "guppi.agent.coder@1.0.0"
OTHER = "guppi.agent.planner@1.0.0"
MISSION = "M-TEST-0001"
INPUT = "artifact://input/1"


class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = os.path.join(self.tmp.name, "manager.sqlite")
        self.guard = Guard(RULES, None, Path(self.tmp.name) / "tokens.json")
        self.registry = Registry(self.db)
        self.addCleanup(self.registry.close)
        self.registry.create("template", AGENT, {"preview": {"ok": True, "problems": []}})
        self.registry.create("template", OTHER, {"preview": {"ok": False, "problems": ["soul_hash"]}})
        self.runtime = FakeRuntime()
        self.bridge = AgentBridge(self.db, self.guard, self.runtime, self.registry)
        self.addCleanup(self.bridge.close)

    def token(self, agent=AGENT, mission=MISSION, input_ref=INPUT):
        binding = {"agent_ref": agent, "mission_id": mission, "input_ref": input_ref}
        gate = self.guard.create_gate(mission, ACTION, agent, request_binding=binding)
        return self.guard.approve(gate)

    def test_assignment_needs_a_guard_token(self):
        for bad in (None, {}, {"status": "active", "token_id": "APR-FAKE0000"}):
            with self.assertRaises(ContractError) as ctx:
                self.bridge.submit("c1", AGENT, MISSION, INPUT, bad)
            self.assertEqual(ctx.exception.code, "admission_refused")
        self.assertEqual(self.runtime.start_calls, 0)
        self.assertEqual(self.bridge.list(), [])

    def test_token_is_bound_to_agent_mission_and_input(self):
        for args in (("c1", AGENT, "M-OTHER", INPUT), ("c2", AGENT, MISSION, "artifact://input/2")):
            with self.assertRaises(ContractError) as ctx:
                self.bridge.submit(*args, self.token())
            self.assertEqual(ctx.exception.code, "admission_refused")
        with self.assertRaises(ContractError) as ctx:
            self.bridge.submit("c3", AGENT, MISSION, INPUT, self.token(agent=OTHER))
        self.assertEqual(ctx.exception.code, "admission_refused")
        self.assertEqual(self.runtime.start_calls, 0)

    def test_token_is_single_use(self):
        token = self.token()
        self.bridge.submit("c1", AGENT, MISSION, INPUT, token)
        with self.assertRaises(ContractError) as ctx:
            self.bridge.submit("c2", AGENT, MISSION, INPUT, token)
        self.assertEqual(ctx.exception.code, "admission_refused")
        self.assertEqual(self.runtime.start_calls, 1)

    def test_unknown_or_unimportable_agent_is_refused_before_the_guard(self):
        token = self.token()
        with self.assertRaises(ContractError) as ctx:
            self.bridge.submit("c1", "guppi.agent.nobody@1.0.0", MISSION, INPUT, token)
        self.assertEqual(ctx.exception.code, "agent_unknown")
        with self.assertRaises(ContractError) as ctx:
            self.bridge.submit("c2", OTHER, MISSION, INPUT, self.token(agent=OTHER))
        self.assertEqual(ctx.exception.code, "agent_not_importable")
        self.bridge.submit("c3", AGENT, MISSION, INPUT, token)

    def test_click_duplicate_starts_one_run(self):
        first = self.bridge.submit("c1", AGENT, MISSION, INPUT, self.token())
        again = self.bridge.submit("c1", AGENT, MISSION, INPUT, None)
        self.assertTrue(first["demo"] and not first["replayed"] and again["replayed"])
        self.assertEqual((first["assignment_id"], first["run_id"]), (again["assignment_id"], again["run_id"]))
        self.assertEqual(self.runtime.start_calls, 1)
        with self.assertRaises(ContractError) as ctx:
            self.bridge.submit("c1", AGENT, "M-OTHER", INPUT, None)
        self.assertEqual(ctx.exception.code, "command_conflict")

    def test_a_real_runtime_is_not_marked_demo(self):
        self.runtime.demo = False
        record = self.bridge.submit("c1", AGENT, MISSION, INPUT, self.token())
        self.assertFalse(record["demo"])
        self.assertFalse(self.bridge.get(record["assignment_id"])["demo"])
        self.assertTrue(self.bridge.submit("c1", AGENT, MISSION, INPUT, None)["replayed"])

    def test_older_database_without_demo_column_is_migrated_as_demo(self):
        import sqlite3
        db = sqlite3.connect(self.db)
        db.execute("DROP TABLE IF EXISTS assignments")
        db.execute("CREATE TABLE assignments (command_id TEXT PRIMARY KEY, request TEXT NOT NULL, assignment_id TEXT NOT NULL, run_id TEXT NOT NULL, agent_ref TEXT NOT NULL, mission_id TEXT NOT NULL, state TEXT NOT NULL, detail TEXT)")
        db.execute("INSERT INTO assignments VALUES ('old', 'r', 'asg-1', 'run-1', 'a', 'M', 'running', NULL)")
        db.commit(); db.close()
        migrated = AgentBridge(self.db, self.guard, self.runtime, self.registry)
        self.addCleanup(migrated.close)
        self.assertTrue(migrated.list()[0]["demo"])

    def test_certain_refusal_is_failed(self):
        self.runtime.start_error = "refused"
        record = self.bridge.submit("c1", AGENT, MISSION, INPUT, self.token())
        self.assertEqual(record["state"], "failed")

    def test_lost_answer_is_in_doubt_and_never_replayed(self):
        self.runtime.start_error = "timeout"
        record = self.bridge.submit("c1", AGENT, MISSION, INPUT, self.token())
        self.assertEqual(record["state"], "in_doubt")
        self.runtime.forget = True
        self.assertEqual(self.bridge.reconcile(), 0)
        self.assertEqual(self.bridge.get(record["assignment_id"])["state"], "in_doubt")
        self.bridge.submit("c1", AGENT, MISSION, INPUT, None)
        self.assertEqual(self.runtime.start_calls, 1)

    def test_reconcile_learns_the_real_outcome(self):
        self.runtime.start_error = "timeout"
        record = self.bridge.submit("c1", AGENT, MISSION, INPUT, self.token())
        self.runtime.finish()
        self.assertEqual(self.bridge.reconcile(), 1)
        self.assertEqual(self.bridge.get(record["assignment_id"])["state"], "succeeded")
        self.assertEqual(self.bridge.reconcile(), 0)

    def test_unknown_is_never_turned_into_failed(self):
        record = self.bridge.submit("c1", AGENT, MISSION, INPUT, self.token())
        self.runtime.forget = True
        self.bridge.reconcile()
        self.assertEqual(self.bridge.get(record["assignment_id"])["state"], "in_doubt")

    def test_result_and_log_survive_a_restart(self):
        record = self.bridge.submit("c1", AGENT, MISSION, INPUT, self.token())
        self.runtime.finish()
        self.bridge.close()
        reopened = AgentBridge(self.db, self.guard, self.runtime, self.registry)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get(record["assignment_id"])["state"], "running")
        reopened.reconcile()
        self.assertEqual(reopened.list()[0]["state"], "succeeded")
        self.assertEqual(reopened.submit("c1", AGENT, MISSION, INPUT, None)["replayed"], True)
        self.assertEqual(self.runtime.start_calls, 1)

    def test_crash_after_prepare_is_in_doubt_after_restart(self):
        record = self.bridge.submit("c1", AGENT, MISSION, INPUT, self.token())
        self.bridge._set("c1", "prepared", None)
        self.runtime.forget = True
        self.bridge.reconcile()
        self.assertEqual(self.bridge.get(record["assignment_id"])["state"], "in_doubt")


if __name__ == "__main__":
    unittest.main()
