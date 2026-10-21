"""Die Importgrenze des Pakets `orchestra/` (Spec 0, D3.1, G2-S0-08): es darf `guppi_runtime.core` und `guppi_runtime.jobs`
importieren, sonst nur die Standardbibliothek und `yaml` – auch nicht über Umwege. Nur so bleibt `runtime.py`, das `orchestra`
zusammenbaut, unter `test_core_boundary_src` grün."""
import sys
import unittest

from guppi_runtime.selfdev.core_boundary import chains, imports_of, violations
from test_core_boundary_src import P, sources

ORCHESTRA = [P + "orchestra"]
FORBIDDEN = [P + m for m in ("desk", "uix_server", "uix", "chat_tools", "agent_manager", "devenv", "devvm", "devvm_agents",
                             "devvm_evidence", "devvm_mcp", "devvm_style", "devvm_tools", "coder_ext", "models.cloud_api")]
ALLOWED_INSIDE = (P + "core", P + "jobs", P + "orchestra")


def _inside(name, groups):
    return any(name == g or name.startswith(g + ".") for g in groups)


class OrchestraBoundary(unittest.TestCase):
    def test_orchestra_imports_nothing_forbidden_not_even_through_other_modules(self):
        found = sources()
        self.assertIn(P + "orchestra.config", found)
        self.assertEqual(violations(found, ORCHESTRA, FORBIDDEN), [])
        self.assertEqual(chains(found, ORCHESTRA, FORBIDDEN), [], "die erste verbotene Einfuhr jeder Kette schneiden")

    def test_only_core_jobs_the_standard_library_and_yaml(self):
        found = sources()
        for module, text in found.items():
            if not _inside(module, ORCHESTRA):
                continue
            for name in imports_of(text, module):
                with self.subTest(module=module, name=name):
                    top = name.split(".")[0]
                    self.assertTrue(_inside(name, ALLOWED_INSIDE) or (top != "guppi_runtime" and (top in sys.stdlib_module_names or top == "yaml")),
                                    f"{module} importiert {name}")

    def test_the_package_init_imports_nothing(self):
        found = sources()
        self.assertEqual(imports_of(found[P + "orchestra"], P + "orchestra"), [])

    def test_the_check_would_notice_a_forbidden_import(self):
        found = sources()
        found[P + "orchestra.service"] += "\nfrom ..desk import kinds\n"
        self.assertEqual(violations(found, ORCHESTRA, FORBIDDEN), [(P + "orchestra.service", P + "desk")])
        found = sources()
        found[P + "orchestra.store"] += "\nfrom ..jobs.job_supervisor import JobSupervisor\n"
        found[P + "jobs.job_supervisor"] += "\nfrom ..agent_manager.instances import InstanceStore\n"
        self.assertTrue(chains(found, ORCHESTRA, FORBIDDEN), "auch über einen Umweg")


if __name__ == "__main__":
    unittest.main()
