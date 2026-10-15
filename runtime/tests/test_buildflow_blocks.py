import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
SPECS = RUNTIME / "benchmarks" / "devvm_specs"
BLOCKS = ("gate_bar", "buildflow_core", "review_report", "adopt_plan")


def load_spec(name):
    loaded = importlib.util.spec_from_file_location("spec_" + name, SPECS / (name + ".py"))
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    return module


class BlockTests(unittest.TestCase):
    def test_the_hidden_tests_of_each_build_hold_for_the_installed_module(self):
        for name in BLOCKS:
            with self.subTest(block=name):
                sys.modules[name] = importlib.import_module("guppi_runtime.devenv." + name)
                self.addCleanup(sys.modules.pop, name, None)
                for code in load_spec(name).STAGES[-1]["hidden"].values():
                    exec(compile(code, name, "exec"), {})

    def test_the_review_does_not_depend_on_removed_parts_of_ast(self):
        from guppi_runtime.devenv.review_report import findings_from_source
        self.assertEqual(findings_from_source("a.py", "print(1)\n"), [])
        self.assertEqual([f["kind"] for f in findings_from_source("a.py", "f()\nimport os\n")], ["late_import", "unused_import"])

    def test_the_task_keeps_its_texts_as_texts(self):
        from guppi_runtime.devenv.buildflow_core import new_task
        task = new_task("T", "s", now="2026-10-14T08:00:00", seed=5, review=None, from_stage=7)
        self.assertEqual((task["seed"], task["review"], task["from_stage"]), ("5", "None", "7"))

    def test_the_adoption_plan_refuses_a_shim_and_names_the_missing_test(self):
        from guppi_runtime.devenv.adopt_plan import plan_adoption
        plan = plan_adoption(["x.py", "old.py"], "d", ["d/old.py"], ["d/old.py"])
        self.assertEqual([e["action"] for e in plan["entries"]], ["refuse", "create"])
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["tests"], [{"module": "d/x.py", "test": "runtime/tests/test_x.py", "exists": False}])


if __name__ == "__main__":
    unittest.main()


class BuildRequestImport(unittest.TestCase):
    def test_the_adopted_module_imports_with_the_package_catalog(self):
        from guppi_runtime.devenv import build_request
        self.assertTrue(callable(build_request.validate_request))


class SpecStandardsImport(unittest.TestCase):
    def test_the_adopted_module_imports_and_checks_a_request(self):
        from guppi_runtime.devenv import spec_standards
        self.assertTrue(callable(spec_standards.check_request))
