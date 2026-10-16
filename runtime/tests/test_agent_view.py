import os
import sqlite3
import tempfile
import unittest

from guppi_runtime.agent_manager.agent_registry import Registry
from guppi_runtime.agent_manager.view import agents_view


class AgentsViewTest(unittest.TestCase):
    def test_missing_database_is_an_empty_demo_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            view = agents_view(os.path.join(tmp, "none.sqlite"))
            self.assertEqual((view["templates"], view["assignments"], view["demo"]), ([], [], True))
            self.assertFalse(os.path.exists(os.path.join(tmp, "none.sqlite")))

    def test_templates_and_assignments_are_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "r.sqlite")
            reg = Registry(path)
            reg.create("template", "a.b.c@1.0.0", {"template": {"role": "Coder"}, "preview": {"ok": False, "problems": ["soul_hash"]}, "trust": "UNVERIFIED"})
            reg.create("agent", "x", {"ignored": True})
            reg.close()
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE assignments (command_id TEXT, request TEXT, assignment_id TEXT, run_id TEXT, agent_ref TEXT, mission_id TEXT, state TEXT, detail TEXT)")
            db.execute("INSERT INTO assignments VALUES ('c', 'r', 'asg-1', 'run-1', 'a.b.c@1.0.0', 'M-1', 'in_doubt', 'x')")
            db.commit(); db.close()
            view = agents_view(path)
            self.assertEqual(view["templates"], [{"ref": "a.b.c@1.0.0", "role": "Coder", "trust": "UNVERIFIED", "ok": False, "problems": ["soul_hash"]}])
            self.assertEqual(view["assignments"][0]["state"], "in_doubt")
            self.assertTrue(view["assignments"][0]["demo"] and view["demo"], "an assignment without a demo column (older database) counts as demo")
            db = sqlite3.connect(path)
            db.execute("ALTER TABLE assignments ADD COLUMN demo INTEGER NOT NULL DEFAULT 1")
            db.execute("UPDATE assignments SET demo = 0")
            db.commit(); db.close()
            real = agents_view(path)
            self.assertFalse(real["demo"] or real["assignments"][0]["demo"])

    def test_view_cannot_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "r.sqlite")
            Registry(path).close()
            before = os.path.getmtime(path)
            agents_view(path)
            self.assertEqual(os.path.getmtime(path), before)


if __name__ == "__main__":
    unittest.main()
