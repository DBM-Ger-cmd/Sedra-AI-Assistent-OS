import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.devenv import assert_catalog, catalog_proofs

RUNTIME = Path(__file__).resolve().parents[1]
DEVENV = RUNTIME / "src" / "guppi_runtime" / "devenv"


def load_spec():
    loaded = importlib.util.spec_from_file_location("assert_catalog_spec", RUNTIME / "benchmarks" / "devvm_specs" / "assert_catalog.py")
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    return module


def run(code, folder):
    return subprocess.run([sys.executable, "-c", code], cwd=folder, capture_output=True, text=True, timeout=60)


class CatalogTests(unittest.TestCase):
    def test_the_hidden_tests_of_the_build_hold_for_the_installed_module(self):
        sys.modules["assert_catalog"], sys.modules["catalog_proofs"] = assert_catalog, catalog_proofs
        self.addCleanup(lambda: [sys.modules.pop(name, None) for name in ("assert_catalog", "catalog_proofs")])
        spec = load_spec()
        for stage in spec.STAGES[:-1]:
            for code in stage["hidden"].values():
                exec(compile(code, stage["name"], "exec"), {})
        exec(compile(spec.S4, "all", "exec"), {})

    def test_every_kind_passes_its_good_example_and_fails_its_mutants(self):
        self.assertEqual(assert_catalog.check_proofs(), [])

    def test_the_checks_of_form_and_purity_read_the_source_and_never_run_the_module_under_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "side.py").write_text("from pathlib import Path\nPath('marker.txt').write_text('ran')\n", encoding="utf-8")
            for kind in ("K12", "K14"):
                run(assert_catalog.generate(kind, module="side"), tmp)
            self.assertFalse(Path(tmp, "marker.txt").exists())

    def test_the_catalog_keeps_its_own_form_rules(self):
        for module in ("assert_catalog", "catalog_proofs"):
            done = run(assert_catalog.generate("K14", module=module), DEVENV)
            self.assertEqual(done.returncode, 0, module + ": " + done.stderr[-200:])


if __name__ == "__main__":
    unittest.main()
