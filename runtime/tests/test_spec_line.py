"""Line L1 to L3 of the build tools (Captain 2026-10-20): spec_check --vm writes a stamp, devvm_build refuses without it, stage size limits, one standard profile.
No GPU, no model, no real microVM: the VM is a fake that runs the commands with the host python in a temporary folder."""
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"
sys.path.insert(0, str(BENCH.parent / "src"))
sys.path.insert(0, str(BENCH))


def load(name):
    loaded = importlib.util.spec_from_file_location(name, BENCH / f"{name}.py")
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    return module


spec_check = load("spec_check")
import spec_stamp  # noqa: E402

SPEC = '''NOTES = "pure python"
STAGES = [
    {"name": "one", "task": "double(x)", "hidden": {"hidden_1.py": "from mod import double\\nassert double(2) == 4\\nassert double(0) == 0\\nprint('ok')\\n"}},
    {"name": "two", "task": "half(x)", "hidden": {"hidden_1.py": "from mod import double\\nassert double(2) == 4\\nassert double(0) == 0\\nprint('ok')\\n",
                                                  "hidden_2.py": "from mod import half\\nassert half(4) == 2\\nprint('ok')\\n"}},
]
'''


def fake_vm(python="3.12.3", fail_marker=None):
    """vm_env replacement: vm_copy runs every command with the host python in a fresh folder (the tree plus the extra files). `python` is what the VM reports
    as its version; a test file that contains fail_marker fails (a python the reference does not run on)."""
    def env(project, tool_root, bg_jobs=False, mission="M", prefix="P"):
        def vm_copy(ws, commands, extra):
            with tempfile.TemporaryDirectory() as tmp:
                for path in ws.tree():
                    (Path(tmp) / path).parent.mkdir(parents=True, exist_ok=True); (Path(tmp) / path).write_text(ws.read(path), encoding="utf-8")
                for path, text in extra.items():
                    (Path(tmp) / path).parent.mkdir(parents=True, exist_ok=True); (Path(tmp) / path).write_text(text, encoding="utf-8")
                outputs = []
                for command in commands:
                    source = (Path(tmp) / command[1]).read_text(encoding="utf-8")
                    if fail_marker and fail_marker in source:
                        return {"status": "failed", "output": "AttributeError: module 'ast' has no attribute 'Str'"}
                    done = subprocess.run([sys.executable] + command[1:], cwd=tmp, capture_output=True, text=True)
                    out = done.stdout.replace("python " + sys.version.split()[0], "python " + python) + done.stderr
                    outputs.append(out)
                    if done.returncode != 0:
                        return {"status": "failed", "output": "\n".join(outputs)}
                return {"status": "completed", "output": "\n".join(outputs)}
        return None, vm_copy
    return env


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.bench = Path(tmp.name) / "benchmarks"; self.project = Path(tmp.name) / "project"
        (self.bench / "devvm_specs").mkdir(parents=True); (self.bench / "devvm_refs" / "demo").mkdir(parents=True)
        (self.bench / "devvm_specs" / "demo.py").write_text(SPEC, encoding="utf-8")
        (self.bench / "devvm_refs" / "demo" / "mod.py").write_text("def double(x):\n    return x * 2\n\ndef half(x):\n    return x // 2\n", encoding="utf-8")
        patch = mock.patch.object(spec_check, "BENCH", self.bench); patch.start(); self.addCleanup(patch.stop)

    def run_check(self, *argv, vm_env=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = spec_check.main(["demo", *argv], vm_env=vm_env)
        return code, out.getvalue()

    def stamp(self):
        return json.loads(spec_stamp.stamp_path(self.project, "demo").read_text(encoding="utf-8"))


class SpecCheckVmTests(Base):
    def test_vm_check_writes_a_vm_stamp_with_hashes_and_the_vm_python(self):
        code, text = self.run_check("--vm", "--project", str(self.project), vm_env=fake_vm("3.12.3"))
        self.assertEqual(code, 0, text)
        self.assertIn("vm lint  ok (python 3.12.3)", text)
        self.assertIn("vm ref   one ok | two ok", text)
        stamp = self.stamp()
        self.assertEqual((stamp["level"], stamp["result"], stamp["python"], stamp["ref_files"]), ("vm", "ok", "3.12.3", 1))
        self.assertEqual(stamp["spec_sha256"], spec_stamp.file_sha256(self.bench / "devvm_specs" / "demo.py"))
        self.assertEqual(spec_stamp.check(self.project, "demo", self.bench), (None, stamp))

    def test_a_failure_in_the_vm_is_result_problems_and_takes_an_old_stamp_away(self):
        self.run_check("--vm", "--project", str(self.project), vm_env=fake_vm())
        code, text = self.run_check("--vm", "--project", str(self.project), vm_env=fake_vm(fail_marker="half(4)"))
        self.assertEqual(code, 1)
        self.assertIn("vm ref   one ok | two FAIL", text)
        self.assertIn("stamp    removed", text)
        self.assertEqual(spec_stamp.check(self.project, "demo", self.bench)[0], "spec_not_checked")

    def test_a_vm_that_cannot_start_writes_no_stamp(self):
        def broken(*a, **k): raise OSError("microsandbox not installed")
        code, text = self.run_check("--vm", "--project", str(self.project), vm_env=broken)
        self.assertEqual(code, 1)
        self.assertIn("the microVM could not run: OSError", text)
        self.assertFalse(spec_stamp.stamp_path(self.project, "demo").exists())

    def test_host_only_writes_a_weaker_stamp_and_a_plain_check_writes_none(self):
        self.assertEqual(self.run_check()[0], 0)
        self.assertFalse(spec_stamp.stamp_path(self.project, "demo").exists())
        code, text = self.run_check("--host-only", "--project", str(self.project))
        self.assertEqual(code, 0); self.assertIn("WEAKER", text)
        self.assertEqual(self.stamp()["level"], "host")

    def test_vm_needs_a_project_and_excludes_host_only(self):
        with self.assertRaises(SystemExit): self.run_check("--vm")
        with self.assertRaises(SystemExit): self.run_check("--vm", "--host-only", "--project", str(self.project))

    def test_the_stamp_goes_stale_when_spec_or_reference_change(self):
        self.run_check("--vm", "--project", str(self.project), vm_env=fake_vm())
        (self.bench / "devvm_refs" / "demo" / "mod.py").write_text("def double(x):\n    return 2 * x\n\ndef half(x):\n    return x // 2\n", encoding="utf-8")
        self.assertEqual(spec_stamp.check(self.project, "demo", self.bench)[0], "spec_changed_since_check")
        self.run_check("--vm", "--project", str(self.project), vm_env=fake_vm())
        self.assertIsNone(spec_stamp.check(self.project, "demo", self.bench)[0])
        (self.bench / "devvm_specs" / "demo.py").write_text(SPEC + "\n# changed\n", encoding="utf-8")
        self.assertEqual(spec_stamp.check(self.project, "demo", self.bench)[0], "spec_changed_since_check")


def devvm_build():
    import env_skip
    env_skip.need_dulwich()
    import devvm_build as module
    return module


class BuildNeedsAStampTests(Base):
    def test_no_stamp_stops_the_build_with_spec_not_checked(self):
        build = devvm_build()
        with self.assertRaises(SystemExit) as stop:
            build.spec_stamp_gate(self.project, "demo", False, self.bench)
        self.assertTrue(str(stop.exception).startswith("spec_not_checked"))

    def test_a_changed_spec_stops_the_build_with_spec_changed_since_check(self):
        build = devvm_build()
        self.run_check("--vm", "--project", str(self.project), vm_env=fake_vm())
        self.assertIn("spec stamp: vm ok", build.spec_stamp_gate(self.project, "demo", False, self.bench)[0])
        (self.bench / "devvm_specs" / "demo.py").write_text(SPEC + "\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as stop:
            build.spec_stamp_gate(self.project, "demo", False, self.bench)
        self.assertTrue(str(stop.exception).startswith("spec_changed_since_check"))

    def test_skip_spec_stamp_builds_with_a_warning_and_a_host_stamp_warns(self):
        build = devvm_build()
        self.assertIn("WARNING: --skip-spec-stamp", build.spec_stamp_gate(self.project, "demo", True, self.bench)[0])
        self.run_check("--host-only", "--project", str(self.project))
        lines = build.spec_stamp_gate(self.project, "demo", False, self.bench)
        self.assertIn("WARNING: spec stamp level host", lines[1])

    def test_the_gate_runs_before_the_pidfile_and_the_run_log(self):
        text = (BENCH / "devvm_build.py").read_text(encoding="utf-8")
        self.assertLess(text.index("spec_stamp_gate(project, args.spec, args.skip_spec_stamp)"), text.index("if args.pidfile: Path(args.pidfile)"))
        self.assertIn('"--skip-spec-stamp"', text)


class StageSizeTests(unittest.TestCase):
    def test_new_checks_are_counted_against_the_stage_before(self):
        spec = type("S", (), {"STAGES": [
            {"name": "a", "hidden": {"h1.py": "assert 1\nassert 2\nwith raises(ValueError):\n    pass\n"}},
            {"name": "b", "hidden": {"h1.py": "assert 1\nassert 2\nwith raises(ValueError):\n    pass\n", "h2.py": "assert 3\nself.assertRaises(KeyError, f)\n"}},
            {"name": "c", "host_hidden": {"h.cjs": "assert.equal(1, 1);\nassert(true);\n"}}]})
        self.assertEqual(spec_check.stage_sizes(spec), [("a", 3, 3), ("b", 5, 2), ("c", 2, 0)])

    def test_more_than_20_warns_and_more_than_30_is_an_error(self):
        errors, warnings = spec_check.size_problems([("a", 20, 20), ("b", 41, 21), ("c", 71, 30), ("d", 102, 31)])
        self.assertEqual([e.split(":")[0] for e in errors], ["stage d"])
        self.assertEqual([w.split(":")[0] for w in warnings], ["stage b", "stage c"])

    def test_a_too_large_stage_makes_the_result_not_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            bench = Path(tmp); (bench / "devvm_specs").mkdir(); (bench / "devvm_refs" / "big").mkdir(parents=True)
            body = "".join(f"assert {i} == {i}\\n" for i in range(31))
            (bench / "devvm_specs" / "big.py").write_text(f'NOTES = "n"\nSTAGES = [{{"name": "all", "task": "t", "hidden": {{"h.py": "{body}"}}}}]\n', encoding="utf-8")
            out = io.StringIO()
            with mock.patch.object(spec_check, "BENCH", bench), contextlib.redirect_stdout(out):
                code = spec_check.main(["big"])
        self.assertEqual(code, 1)
        self.assertIn("size     all 31", out.getvalue())
        self.assertIn("split the stage", out.getvalue())


if __name__ == "__main__":
    unittest.main()
