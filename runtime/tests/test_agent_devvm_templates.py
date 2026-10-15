import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import hashlib
import os
import tempfile
import unittest

from guppi_runtime.agent_manager.devvm_templates import export_role_templates, role_template
from guppi_runtime.agent_manager.service import AgentManager
from guppi_runtime.devvm_tools import ROLE_TOOLS, SCHEMAS, SYSTEM, TERMINAL


class DevvmTemplatesTest(unittest.TestCase):
    def test_every_role_becomes_a_clean_unverified_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "t")
            self.assertEqual(export_role_templates(folder), list(ROLE_TOOLS))
            manager = AgentManager(os.path.join(tmp, "r.sqlite"))
            try:
                results = manager.import_templates(folder)
                self.assertEqual([r["status"] for r in results], ["created"] * len(ROLE_TOOLS))
                self.assertEqual([r["problems"] for r in results], [[]] * len(ROLE_TOOLS))
                listing = manager.list_templates()
                self.assertEqual([t["ref"] for t in listing], sorted(f"guppi.devvm.{r}@1.0.0" for r in ROLE_TOOLS))
                self.assertTrue(all(t["trust"] == "UNVERIFIED" and t["ok"] for t in listing))
                self.assertEqual(manager.import_templates(folder)[0]["status"], "unchanged")
            finally:
                manager.close()

    def test_nothing_is_invented(self):
        for role in ROLE_TOOLS:
            template, soul = role_template(role)
            self.assertEqual(soul.decode("utf-8"), SYSTEM[role])
            self.assertEqual([t["id"] for t in template["tools"]], list(ROLE_TOOLS[role]) + [TERMINAL[role]])
            self.assertEqual(template["permissions"]["tools_allowed"], [t["id"] for t in template["tools"]])
            self.assertTrue(all(len(t["sha256"]) == 64 for t in template["tools"]))
            self.assertEqual(template["soul"]["sha256"], hashlib.sha256(SYSTEM[role].encode("utf-8")).hexdigest())

    def test_only_the_coder_and_the_solo_developer_may_write_and_nobody_has_network_or_privileges(self):
        for role in ROLE_TOOLS:
            template, _ = role_template(role)
            perm = template["permissions"]
            self.assertEqual(perm["workspace_mode"] == "mission_write", role in ("coder", "solo"))
            self.assertEqual((perm["network_mode"], perm["external_write"], perm["privileged"]), ("deny", False, False))
            self.assertEqual(template["initial_qualification"], "DRAFT")
        self.assertIn("write_file", ROLE_TOOLS["coder"])
        self.assertIn("write_file", ROLE_TOOLS["solo"])
        self.assertTrue(all("write_file" not in ROLE_TOOLS[r] for r in ROLE_TOOLS if r not in ("coder", "solo")))


if __name__ == "__main__":
    unittest.main()
