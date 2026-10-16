import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import os
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.agent_manager.agent_contracts import ContractError
from guppi_runtime.agent_manager.bootstrap import bootstrap
from guppi_runtime.agent_manager.devvm_crews import devvm_crew, export_devvm_crew
from guppi_runtime.agent_manager.devvm_templates import export_role_templates
from guppi_runtime.agent_manager.instances import InstanceService
from guppi_runtime.agent_manager.service import AgentManager
from guppi_runtime.agent_manager.view import agents_view
from guppi_runtime.agent_manager.crews import validate_crew

REF = "guppi.crew.devvm_build@1.0.0"


class CrewImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.templates = os.path.join(self.tmp.name, "templates")
        self.crews = os.path.join(self.tmp.name, "crews")
        os.makedirs(self.crews)
        export_role_templates(self.templates)
        self.manager = AgentManager(os.path.join(self.tmp.name, "registry.sqlite"))
        self.addCleanup(self.manager.close)
        self.manager.import_templates(self.templates)

    def test_the_devvm_crew_is_valid_and_imported_with_its_pins(self):
        crew = devvm_crew(self.manager.registry)
        self.assertEqual(validate_crew(crew), [])
        self.assertEqual([s["template_sha256"] for s in crew["slots"]], [self.manager.registry.get("template", f"guppi.devvm.{r}@1.0.0")["data"]["digest"].removeprefix("sha256:") for r in ("planner", "coder", "reviewer")])
        export_devvm_crew(self.crews, self.manager.registry)
        self.assertEqual(self.manager.import_crews(self.crews), [{"folder": "devvm_build", "key": REF, "status": "created", "problems": []}])
        self.assertEqual(self.manager.import_crews(self.crews)[0]["status"], "unchanged")
        self.assertEqual(self.manager.list_crews(), [{"ref": REF, "purpose": crew["purpose"], "slots": 3, "steps": 4, "problems": []}])

    def test_a_changed_template_and_a_missing_template_are_problems_not_substitutes(self):
        export_devvm_crew(self.crews, self.manager.registry)
        entry = self.manager.registry.get("template", "guppi.devvm.coder@1.0.0")
        self.manager.registry.update("template", "guppi.devvm.coder@1.0.0", {**entry["data"], "digest": "f" * 64}, entry["revision"])
        result = self.manager.import_crews(self.crews)[0]
        self.assertEqual((result["status"], result["problems"]), ("created", ["pin_mismatch:coder"]))
        other = AgentManager(os.path.join(self.tmp.name, "empty.sqlite"))
        self.addCleanup(other.close)
        self.assertEqual(sorted(other.import_crews(self.crews)[0]["problems"]), ["template_not_imported:coder", "template_not_imported:planner", "template_not_imported:reviewer"])

    def test_broken_yaml_and_invalid_ids_are_refused_and_a_defective_crew_is_registered_with_its_problems(self):
        for name, text in (("dup", "id: a\nid: b\n"), ("noid", "schema_version: guppi.crew-template/v1\nid: X\nversion: 1.0.0\n"), ("list", "- 1\n")):
            os.makedirs(os.path.join(self.crews, name))
            Path(self.crews, name, "crew.yaml").write_text(text, encoding="utf-8")
        rows = {r["folder"]: r for r in self.manager.import_crews(self.crews)}
        self.assertEqual({k: v["status"] for k, v in rows.items()}, {"dup": "refused", "noid": "refused", "list": "refused"})
        self.assertEqual(rows["dup"]["problems"], ["yaml_refused"])
        export_devvm_crew(self.crews, self.manager.registry)
        crew_file = Path(self.crews, "devvm_build", "crew.yaml")
        crew_file.write_text(crew_file.read_text(encoding="utf-8").replace("depends_on:\n  - planner_step", "depends_on:\n  - nowhere"), encoding="utf-8")
        row = [r for r in self.manager.import_crews(self.crews) if r["folder"] == "devvm_build"][0]
        self.assertEqual(row["key"], REF); self.assertIn("unknown_dependency", row["problems"])


class AssemblyOnInstancesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        bootstrap(self.project)
        self.manager = AgentManager(self.project / "runtime_data" / "agent_manager" / "registry.sqlite")
        self.addCleanup(self.manager.close)
        self.service = InstanceService(self.manager.registry, guard=None)

    def verified(self, role, model, ref=None):
        template = self.manager.registry.get("template", ref or f"guppi.devvm.{role}@1.0.0")["data"]
        self.manager.registry.create("agent", f"ins-{role}-{model}", {"template_ref": f"guppi.devvm.{role}@1.0.0", "template_digest": template["digest"], "purpose": "test", "model_key": model,
                                                                      "qualification": "VERIFIED", "lifecycle": "ACTIVE", "admission": {"valid": True, "revoked": False}, "stats": {"successes": 5, "runs": 5},
                                                                      "suite_runs": [], "review": None, "builder": None})

    def test_bootstrap_registers_the_crew_and_the_view_lists_it(self):
        self.assertEqual([c["ref"] for c in self.manager.list_crews()], [REF])
        view = agents_view(self.project / "runtime_data" / "agent_manager" / "registry.sqlite")
        self.assertEqual(view["crews"], [{"ref": REF, "purpose": self.manager.list_crews()[0]["purpose"], "slots": 3, "steps": 4, "problems": []}])

    def test_without_instances_every_slot_is_a_gap_and_with_verified_ones_the_crew_is_planned(self):
        plan = self.service.assemble(REF, {"cpu_cores": 8})
        self.assertEqual((plan["ok"], [g["reason"] for g in plan["gaps"]]), (False, ["no_candidate_for_pin"] * 3))
        self.verified("planner", "qwen3-coder")
        self.verified("coder", "qwen3-coder")
        self.verified("reviewer", "qwen3-coder")
        plan = self.service.assemble(REF, {"cpu_cores": 8})
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["gaps"][0]["reason"], "no_combination_satisfies_exclusivity_and_independence", "coder and reviewer on the same model are not independent")
        self.manager.registry.delete("agent", "ins-reviewer-qwen3-coder", self.manager.registry.get("agent", "ins-reviewer-qwen3-coder")["revision"])
        self.verified("reviewer", "swe-review-8b")
        plan = self.service.assemble(REF, {"cpu_cores": 8})
        self.assertTrue(plan["ok"], plan)
        self.assertEqual({k: v["agent_id"] for k, v in plan["assignments"].items()}, {"planner": "ins-planner-qwen3-coder", "coder": "ins-coder-qwen3-coder", "reviewer": "ins-reviewer-swe-review-8b"})

    def test_an_unknown_crew_is_refused(self):
        with self.assertRaises(ContractError) as ctx:
            self.service.assemble("guppi.crew.nobody@1.0.0", {})
        self.assertEqual(ctx.exception.code, "crew_unknown")


if __name__ == "__main__":
    unittest.main()
