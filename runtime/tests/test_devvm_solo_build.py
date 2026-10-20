import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import importlib
import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "benchmarks"))
sys.path.insert(0, str(RUNTIME / "src"))

from devvm_build import NO_TESTS, without_test_duty  # noqa: E402


class WithoutTestDutyTest(unittest.TestCase):
    def test_the_three_phrases_of_the_specs_are_removed_and_the_ban_is_added_once(self):
        task = "Create `a.py`. No comments. Add `tests/test_a.py` (unittest) with your own tests."
        self.assertEqual(without_test_duty(task), "Create `a.py`. No comments." + NO_TESTS)
        self.assertEqual(without_test_duty("Do it. Add tests to `tests/test_a.py`."), "Do it." + NO_TESTS)
        self.assertEqual(without_test_duty("Run the whole test file `tests/test_a.py` and read `a.py` once more."), "Read `a.py` once more." + NO_TESTS)
        self.assertEqual(without_test_duty("Do not write tests. Nothing else."), "Do not write tests. Nothing else.")

    def test_no_stage_of_any_spec_keeps_a_test_file_duty(self):
        names = ["am002_contracts", "am003_registry", "am004_import", "am005_matcher", "am006_style", "am007_crews", "am008_meter", "am009_collector", "am010_comments", "bench_std"]
        checked = 0
        for name in names:
            try:
                spec = importlib.import_module(f"devvm_specs.{name}")
            except ImportError:
                continue
            for stage in getattr(spec, "STAGES", []):
                text = without_test_duty(stage["task"])
                self.assertNotIn("tests/test_", text, f"{name}.{stage['name']}")
                checked += 1
        self.assertGreater(checked, 20)


if __name__ == "__main__":
    unittest.main()


class SoloIsTheStandardTests(unittest.TestCase):
    def parse(self, *argv):
        import argparse, devvm_build
        args = argparse.Namespace(mode='solo', rework=None, hidden_feedback=False, tidy=False, no_own_tests=False)
        for k, v in zip(argv[::2], argv[1::2]): setattr(args, k, v)
        return devvm_build.apply_mode_defaults(args)

    def test_solo_gets_the_solo_workflow(self):
        a = self.parse()
        self.assertEqual((a.rework, a.hidden_feedback, a.tidy, a.no_own_tests), (3, True, True, True))
        self.assertEqual(self.parse('rework', 1).rework, 1)

    def test_other_modes_keep_their_defaults(self):
        a = self.parse('mode', 'escalating')
        self.assertEqual((a.rework, a.hidden_feedback, a.no_own_tests), (0, False, False))

    def test_the_build_script_defaults_to_solo(self):
        import re
        text = (Path(__file__).resolve().parents[1] / 'benchmarks' / 'devvm_build.py').read_text(encoding='utf-8')
        self.assertIn('"--mode", default="solo"', text)


class SnapshotTests(unittest.TestCase):
    def test_a_passed_stage_leaves_a_folder_that_can_seed_the_next_stage(self):
        import tempfile
        from devvm_build import export_snapshot
        from guppi_runtime.devenv.devvm import DevWorkspace
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as proj:
            ws = DevWorkspace(Path(tmp), "M-SNAP0001", policy={"max_files": 20, "max_file_bytes": 8000, "max_input_bytes": 20000}); ws.create()
            ws.write("a.py", "x = 1\n"); ws.write("tests/t.py", "y = 2\n")
            folder = export_snapshot(ws, proj, "am_demo", "20261010_120000", "rules")
            self.assertEqual(folder, Path(proj) / "runtime_data" / "devvm_snapshots" / "am_demo" / "20261010_120000" / "after_rules")
            self.assertEqual((folder / "a.py").read_text(encoding="utf-8"), "x = 1\n"); self.assertEqual((folder / "tests" / "t.py").read_text(encoding="utf-8"), "y = 2\n")


class BuildReviewTests(unittest.TestCase):
    """Review 2026-10-12 of devvm_build.py: stage selection, seed reading, stop after a failed stage, the real window."""
    STAGES = [{"name": "a", "hidden": {"h1.py": ""}}, {"name": "b", "hidden": {"h2.py": ""}}, {"name": "c", "host_hidden": {"h3.js": ""}}]

    def test_stage_selection_and_unknown_names(self):
        from devvm_build import select_stages
        names = lambda **kw: [s["name"] for s in select_stages(self.STAGES, **kw)]
        self.assertEqual(names(), ["a", "b", "c"])
        self.assertEqual(names(only="b"), ["b"])
        self.assertEqual(names(from_stage="b"), ["b", "c"])
        for kw in ({"only": "x"}, {"from_stage": "x"}, {"only": "a", "from_stage": "b"}):
            with self.assertRaises(SystemExit, msg=kw):
                select_stages(self.STAGES, **kw)
        with self.assertRaises(SystemExit):
            select_stages(self.STAGES + [{"name": "blind"}])

    def test_seed_leaves_out_pycache_and_binary_files(self):
        import tempfile
        from devvm_build import seed_files
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pkg" / "__pycache__").mkdir(parents=True)
            (root / "pkg" / "a.py").write_text("x = 1\n", encoding="utf-8")
            (root / "pkg" / "__pycache__" / "a.cpython-314.pyc").write_bytes(b"\x00\xff\xfe")
            (root / "blob.bin").write_bytes(b"\xff\xfe\x00\x81")
            (root / "NOTES.md").write_text("old notes", encoding="utf-8")
            files, skipped = seed_files(root)
        self.assertEqual(files, [("pkg/a.py", "x = 1\n")])
        self.assertEqual(sorted(skipped), ["blob.bin", "pkg/__pycache__/a.cpython-314.pyc"])

    def test_a_skipped_stage_counts_as_not_passed_so_the_stage_count_stays_comparable(self):
        from devvm_build import skipped_row
        row = skipped_row({"name": "c"})
        self.assertEqual((row["stage"], row["hidden_passed"], row["skipped"]), ("c", False, True))
        rows = [{"hidden_passed": True}, {"hidden_passed": False}, row]
        self.assertEqual((sum(1 for r in rows if r["hidden_passed"]), len(rows)), (1, 3))

    def test_resume_hint_names_the_failed_stage_and_the_snapshot(self):
        from types import SimpleNamespace
        from devvm_build import resume_hint
        hint = resume_hint(SimpleNamespace(spec="e06_bg_jobs"), "poll", Path("snap/after_table"))
        self.assertIn("--spec e06_bg_jobs --from-stage poll", hint)
        self.assertIn(str(Path("snap/after_table")), hint)
        self.assertNotIn("--seed", resume_hint(SimpleNamespace(spec="x"), "a", None))

    def test_the_window_is_the_one_the_server_loads_and_falls_back_when_unknown(self):
        from unittest import mock
        import devvm_build
        loader = mock.Mock(); loader.window.return_value = 131072
        with mock.patch.object(devvm_build.bench.hunt, "model_spec", lambda key, project: {"alias": "m", "context": 16384}):
            self.assertEqual(devvm_build.coder_window(loader, "coder.x", Path("."), 32768), 131072)
        with mock.patch.object(devvm_build.bench.hunt, "model_spec", side_effect=StopIteration):
            self.assertEqual(devvm_build.coder_window(loader, "nope", Path("."), 32768), 32768)


class RecipeWindowCapTests(unittest.TestCase):
    """The window cap comes from the recipe itself; a second recipe of the same model must not lift it (coder.llama_qwen35 16k vs coder.lmstudio_qwen 64k)."""
    def test_cap_by_recipe_id_and_fallback_by_model_name(self):
        import tempfile
        import devvm_agents_bench as bench
        yaml_text = ("role_routing:\n  capabilities:\n"
                     "  - {id: coder.llama_qwen35, model: qwen3.5-9b-mtp, profile: {context: {maximum: 16384}}}\n"
                     "  - {id: coder.lmstudio_qwen, model: qwen3.5-9b-mtp, profile: {context: {maximum: 65536}}}\n")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "local_config").mkdir(); (Path(tmp) / "local_config" / "role_routing.yaml").write_text(yaml_text, encoding="utf-8")
            self.assertEqual(bench.recipe_context_maximum(tmp, "qwen3.5-9b-mtp", "coder.llama_qwen35"), 16384)
            self.assertEqual(bench.recipe_context_maximum(tmp, "qwen3.5-9b-mtp"), 65536)
            self.assertEqual(bench.recipe_context_maximum(tmp, "qwen3.5-9b-mtp", "coder.unknown"), 65536)
            self.assertIsNone(bench.recipe_context_maximum(tmp, "other"))
