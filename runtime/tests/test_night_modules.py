"""Modules GUPPI built in the night run of 2026-10-11 and that were integrated on 2026-10-12 (Captain approval 2026-10-11): each must still pass the FULL hidden
acceptance test of its spec (benchmarks/devvm_specs/<spec>.py, last stage). The hidden script imports the module by its plain name, so it runs in a subprocess with the
module's folder on the path; nothing else of GUPPI is loaded. Two one-line fixes by Claude are covered by assertions that were added to the specs afterwards:
layer_summary uses re.search (a real error text starts with "HTTPError: ..."), conn_check sends enough max_tokens for the 6000-character echo."""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
MODULES = {      # spec -> the installed module; its folder is taken from the module's real file (after the package split the old top-level name is only an alias)
    "e11_lesson_cards": "guppi_runtime.coder_ext.lesson_cards",
    "e06_bg_jobs": "guppi_runtime.coder_ext.bg_jobs",
    "e10_self_repo_guard": "guppi_runtime.coder_ext.self_repo_guard",   # Qwen3-Coder, second attempt 2026-10-12 with a review; one line by Claude (mixed path separators)
    "layer_summary": "guppi_runtime.devenv.layer_summary",
    "s0_conn_check": "guppi_runtime.devenv.conn_check",
    "mcp_shield": "guppi_runtime.devenv.mcp_shield",
    "core_boundary": "guppi_runtime.selfdev.core_boundary",
    "vm_process": "guppi_runtime.devenv.vm_process",      # 2026-10-13, built by GUPPI (second round after a review), the process starter of bg_jobs
    "lesson_proposer": "guppi_runtime.devenv.lesson_proposer",      # 2026-10-13, built by GUPPI after three reviews, proposes lesson cards from the errors of a build
}


def folder_of(module_name):
    return Path(importlib.import_module(module_name).__file__).parent


def full_hidden(spec):
    path = RUNTIME / "benchmarks" / "devvm_specs" / f"{spec}.py"
    loader = importlib.util.spec_from_file_location(f"spec_{spec}", path)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return list(module.STAGES[-1]["hidden"].items())[0]


class NightModules(unittest.TestCase):
    def test_each_module_passes_its_full_hidden_acceptance_test(self):
        for spec, module_name in MODULES.items():
            folder = folder_of(module_name)
            with self.subTest(spec=spec), tempfile.TemporaryDirectory() as tmp:
                name, code = full_hidden(spec)
                (Path(tmp) / name).write_text(code, encoding="utf-8")
                env = {**os.environ, "PYTHONPATH": str(folder)}
                done = subprocess.run([sys.executable, name], cwd=tmp, env=env, capture_output=True, text=True, timeout=120)
                self.assertEqual(done.returncode, 0, done.stderr[-800:])
                self.assertTrue(done.stdout.strip().endswith("ok"))

    def test_the_modules_import_inside_the_package(self):
        from guppi_runtime.devenv import conn_check
        from guppi_runtime.selfdev import core_boundary
        from guppi_runtime.devenv import layer_summary
        from guppi_runtime.devenv import mcp_shield
        from guppi_runtime.coder_ext import bg_jobs, lesson_cards, self_repo_guard
        self.assertTrue(callable(conn_check.run_all) and callable(core_boundary.chains) and callable(layer_summary.cell))
        self.assertTrue(callable(mcp_shield.untrusted) and hasattr(lesson_cards, "Cards") and hasattr(bg_jobs, "Jobs") and callable(self_repo_guard.check_shell))


if __name__ == "__main__":
    unittest.main()
