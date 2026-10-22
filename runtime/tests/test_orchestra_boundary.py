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
# Spec 1 (D1.1, S1.H6): zweite Regel – die sieben reinen Module importieren nichts aus `guppi_runtime` und nicht `sqlite3`;
# einzig `runner` darf `chain` und `decompose` nutzen.
PURE = {"graphs": (), "cron": (), "wakeplan": (), "budgetcalc": (), "chain": (), "decompose": (), "runner": ("chain", "decompose")}


def _inside(name, groups):
    return any(name == g or name.startswith(g + ".") for g in groups)


def pure_ok(name, siblings):
    if any(name == P + "orchestra." + s for s in siblings):
        return True
    top = name.split(".")[0]
    return top != "guppi_runtime" and top != "sqlite3" and top in sys.stdlib_module_names


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

    def test_the_pure_modules_import_only_the_standard_library(self):
        found = sources()
        for name, siblings in PURE.items():
            module = P + "orchestra." + name
            self.assertIn(module, found)
            for imported in imports_of(found[module], module):
                with self.subTest(module=name, name=imported):
                    self.assertTrue(pure_ok(imported, siblings), f"{name} importiert {imported}")

    def test_the_second_rule_would_notice_sqlite_or_the_package(self):
        self.assertFalse(pure_ok("sqlite3", ()))
        self.assertFalse(pure_ok(P + "orchestra.store", ()))
        self.assertFalse(pure_ok(P + "core.guard", ()))
        self.assertFalse(pure_ok(P + "orchestra.board", ("chain", "decompose")))
        self.assertTrue(pure_ok(P + "orchestra.chain", ("chain", "decompose")))
        self.assertTrue(pure_ok("datetime", ()))

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
