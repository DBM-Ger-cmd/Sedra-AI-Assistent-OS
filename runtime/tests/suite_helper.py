"""Runs the hidden scripts of a stored acceptance suite against the integrated modules (the imports are pointed at guppi_runtime.agent_manager). The suites live under
workspace/GUPPI_OS/acceptance/suites (not in the repository); without the suite the test is skipped, with an unreadable or changed suite it fails."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.acceptance_suite import SuiteError, load_suite

RUNTIME = Path(__file__).resolve().parents[1]
SUITES = RUNTIME.parent / "workspace" / "GUPPI_OS" / "acceptance" / "suites"
MODULES = ("agent_contracts", "agent_registry", "agent_import", "agent_matcher", "code_meter", "code_collector")
MODULE_HOME = {"crew_planner": "guppi_runtime.agent_manager.crews", "comment_archive": "guppi_runtime.comment_archive"}


def make_suite_case(suite_name):
    folder = SUITES / suite_name

    class SuiteCase(unittest.TestCase):
        suite = None

        @classmethod
        def setUpClass(cls):
            if not folder.is_dir():
                raise unittest.SkipTest(f"the stored suite {suite_name} is not on this machine")
            try:
                cls.suite = load_suite(str(folder))
            except SuiteError as exc:
                raise AssertionError(f"suite {suite_name} is refused: {exc}") from None

        def test_every_criterion_passes_against_the_integrated_modules(self):
            for criterion in self.suite.criteria:
                script, text = self.suite.scripts[criterion["id"]]
                for name in MODULES:
                    text = text.replace(f"from {name} import", f"from guppi_runtime.agent_manager.{name} import")
                for name, home in MODULE_HOME.items():
                    text = text.replace(f"from {name} import", f"from {home} import")
                with tempfile.TemporaryDirectory() as tmp:
                    Path(tmp, script).write_text(text, encoding="utf-8")
                    run = subprocess.run([sys.executable, script], cwd=tmp, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(RUNTIME / "src")}, timeout=180)
                self.assertEqual(run.returncode, 0, f"{criterion['id']}: {(run.stdout + run.stderr)[-500:]}")

    SuiteCase.__name__ = f"Acceptance_{suite_name}"
    return SuiteCase
