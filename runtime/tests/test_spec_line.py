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
        lines = build.spec_stamp_gate(self.project, "demo", False, self.bench, allow_host=True)
        self.assertIn("WARNING: spec stamp level host", lines[1])

    def test_a_host_stamp_stops_the_build_without_allow_host_stamp(self):
        build = devvm_build()
        self.run_check("--host-only", "--project", str(self.project))
        with self.assertRaises(SystemExit) as stop:
            build.spec_stamp_gate(self.project, "demo", False, self.bench)
        self.assertTrue(str(stop.exception).startswith("spec_stamp_host_only"))
        self.assertIn("spec_check.py demo --vm", str(stop.exception))
        self.assertTrue(build.parse_args(["proj", "--spec", "demo", "--allow-host-stamp"]).allow_host_stamp)

    def test_the_gate_runs_before_the_pidfile_and_the_run_log(self):
        text = (BENCH / "devvm_build.py").read_text(encoding="utf-8")
        self.assertLess(text.index("spec_stamp_gate(project, args.spec, args.skip_spec_stamp, allow_host=args.allow_host_stamp)"), text.index("if args.pidfile: Path(args.pidfile)"))
        self.assertIn('"--skip-spec-stamp"', text)


class SeedFieldTests(Base):
    """PIPE-10 (Captain 2026-10-21): the module field SEED of a spec."""
    def with_seed(self, files=None, seed="benchmarks/demo_seed"):
        (self.bench / "devvm_specs" / "demo.py").write_text(f'SEED = "{seed}"\n' + SPEC, encoding="utf-8")
        folder = self.bench / "demo_seed"
        if files is not None:
            folder.mkdir(exist_ok=True)
            for name, text in files.items(): (folder / name).write_text(text, encoding="utf-8")
        return folder

    def args(self, seed=None):
        return devvm_build().parse_args(["proj", "--spec", "demo"] + (["--seed", seed] if seed else []))

    def test_spec_check_reports_the_seed_and_the_stamp_binds_its_hash(self):
        folder = self.with_seed({"a.py": "x = 1\n", "b.py": "y = 2\n"})
        code, text = self.run_check("--vm", "--project", str(self.project), vm_env=fake_vm())
        self.assertEqual(code, 0, text)
        self.assertIn("seed     benchmarks/demo_seed (2 Dateien)", text)
        self.assertEqual(self.stamp()["seed_sha256"], spec_stamp.tree_sha256(folder)[0])
        self.assertIsNone(spec_stamp.check(self.project, "demo", self.bench)[0])
        (folder / "a.py").write_text("x = 3\n", encoding="utf-8")
        self.assertEqual(spec_stamp.check(self.project, "demo", self.bench)[0], "spec_changed_since_check")

    def test_spec_check_does_not_load_the_seed_into_the_vm_and_a_missing_folder_is_a_problem(self):
        self.with_seed(None)
        code, text = self.run_check("--vm", "--project", str(self.project), vm_env=fake_vm())
        self.assertEqual(code, 1)
        self.assertIn("seed_missing", text)
        self.assertFalse(spec_stamp.stamp_path(self.project, "demo").exists())

    def test_a_stamp_without_seed_sha256_is_stale(self):
        self.run_check("--vm", "--project", str(self.project), vm_env=fake_vm())
        stamp = self.stamp(); del stamp["seed_sha256"]
        spec_stamp.stamp_path(self.project, "demo").write_text(json.dumps(stamp), encoding="utf-8")
        self.assertEqual(spec_stamp.check(self.project, "demo", self.bench)[0], "spec_changed_since_check")

    def test_a_spec_without_seed_has_an_empty_seed_hash(self):
        self.run_check("--vm", "--project", str(self.project), vm_env=fake_vm())
        self.assertEqual(self.stamp()["seed_sha256"], "")

    def test_build_takes_the_seed_of_the_spec(self):
        folder = self.with_seed({"a.py": "x = 1\n"})
        args = self.args()
        lines = devvm_build().spec_seed_gate(args, "demo", self.bench)
        self.assertEqual(Path(args.seed), folder)
        self.assertIn("from SEED of the spec", lines[0])

    def test_a_given_seed_wins_with_a_log_line(self):
        self.with_seed({"a.py": "x = 1\n"})
        args = self.args("other_folder")
        lines = devvm_build().spec_seed_gate(args, "demo", self.bench)
        self.assertEqual(args.seed, "other_folder")
        self.assertIn("--seed other_folder wins over SEED benchmarks/demo_seed", lines[0])

    def test_a_missing_seed_folder_stops_the_build_with_seed_missing(self):
        self.with_seed(None)
        for given in (None, "other_folder"):
            with self.subTest(given=given):
                with self.assertRaises(SystemExit) as stop:
                    devvm_build().spec_seed_gate(self.args(given), "demo", self.bench)
                self.assertTrue(str(stop.exception).startswith("seed_missing"))

    def test_without_seed_field_nothing_changes(self):
        args = self.args()
        self.assertEqual(devvm_build().spec_seed_gate(args, "demo", self.bench), [])
        self.assertIsNone(args.seed)

    def test_the_seed_gate_runs_before_the_stamp_gate(self):
        text = (BENCH / "devvm_build.py").read_text(encoding="utf-8")
        self.assertLess(text.index("spec_seed_gate(args, args.spec)"), text.index("spec_stamp_gate(project, args.spec, args.skip_spec_stamp"))


class BuildLogbookTests(Base):
    def row(self, target, passed=(True, True), seconds=90.4):
        stages = [{"stage": f"s{i}", "hidden_passed": ok, "reworks": 1 if i == 0 else 0} for i, ok in enumerate(passed)]
        return {"hidden_passed": all(passed), "stages": stages, "seconds": seconds, "calls": 17, "agent_runs": 5, "escalations": 1, "exported_to": str(target)}

    def candidate(self):
        target = self.project / "cand"
        (target / "tests").mkdir(parents=True)
        (target / "mod.py").write_text("def double(x):\n    return x * 2\n", encoding="utf-8")
        (target / "NOTES.md").write_text("n\n" * 9, encoding="utf-8")
        (target / "tests" / "test_mod.py").write_text("x = 1\n" * 30, encoding="utf-8")
        return target

    def test_the_row_has_result_times_calls_reworks_and_the_line_quota(self):
        build = devvm_build()
        text, ref = build.logbook_entry("demo", self.row(self.candidate()), 123.6, self.bench)
        self.assertIn("Bau demo: bestanden, Stufen 2/2, Dauer 90 s, GPU-Lease 124 s, 17 Modellaufrufe in 5 Agentenläufen, Nacharbeiten 1", text)
        self.assertIn("Zeilen SEDRA (Kandidat) 2,", text)
        claude = len(SPEC.splitlines()) + 5
        self.assertIn(f"Zeilen Claude (Spec + Referenz) {claude}, Quote Claude/SEDRA {claude / 2:.1f}", text)
        self.assertEqual(ref, "devvm_candidates/demo")

    def test_a_failed_stage_shows_in_the_row_and_write_logbook_appends_a_valid_bau_row(self):
        build = devvm_build()
        book = self.project / "LOGBUCH.md"
        self.project.mkdir(exist_ok=True)
        book.write_text("| Zeit | Art | Text | Ref |\n", encoding="utf-8")
        line = build.write_logbook("demo", self.row(self.candidate(), passed=(True, False)), 5, file=book, bench_dir=self.bench)
        self.assertRegex(line, r"^\| \d{4}-\d\d-\d\d \d\d:\d\d \| BAU \| Bau demo: NICHT bestanden, Stufen 1/2")
        self.assertEqual(book.read_text(encoding="utf-8").splitlines()[-1], line)

    def test_no_logbook_is_an_option_and_the_write_comes_after_the_lease(self):
        self.assertTrue(devvm_build().parse_args(["proj", "--spec", "demo", "--no-logbook"]).no_logbook)
        text = (BENCH / "devvm_build.py").read_text(encoding="utf-8")
        self.assertLess(text.index("lease_seconds = time.monotonic() - lease_t0"), text.index("if not args.no_logbook"))
        self.assertLess(text.index("if not args.no_logbook"), text.index('log.say(f"DONE'))


class ProfileTests(unittest.TestCase):
    def parse(self, *argv):
        return devvm_build().parse_args(["proj", "--spec", "demo", *argv])

    def test_profile_standard_is_the_standard_command(self):
        a = self.parse("--profile", "standard")
        self.assertEqual((a.attempts, a.coder, a.all_models, a.context, a.tidy, a.reasoning, a.coder_ext), (1, "coder.local_primary", "coder.local_primary", "32768", True, "off", "all"))
        self.assertEqual(a.server_set, ["flash_attn=on", "kv_cache_type=q8_0", "ubatch=512"])
        self.assertEqual(a.self_check, "none")

    def test_profile_standard_self_check_can_be_overridden(self):
        self.assertEqual(self.parse("--profile", "standard", "--self-check", "full").self_check, "full")
        self.assertEqual(self.parse().self_check, "full")

    def test_profile_schnell_klein_is_standard_with_the_small_model(self):
        a = self.parse("--profile", "schnell-klein")
        self.assertEqual((a.attempts, a.coder, a.all_models, a.context, a.tidy, a.reasoning, a.coder_ext, a.self_check),
                         (1, "coder.llama_qwen35", "coder.llama_qwen35", "32768", True, "off", "all", "none"))
        self.assertEqual(a.server_set, ["flash_attn=on", "kv_cache_type=q8_0", "ubatch=512"])
        self.assertIn("Reserve, nicht Standard", " ".join(devvm_build().build_parser().format_help().split()))

    def test_single_flags_override_the_profile(self):
        a = self.parse("--profile", "standard", "--attempts", "2", "--context", "max", "--server-set", "ubatch=1024", "--reasoning", "auto")
        self.assertEqual((a.attempts, a.context, a.reasoning, a.coder), (2, "max", "auto", "coder.local_primary"))
        self.assertEqual(a.server_set, ["flash_attn=on", "kv_cache_type=q8_0", "ubatch=1024"])

    def test_without_profile_nothing_changes(self):
        a = self.parse()
        self.assertEqual((a.attempts, a.tidy, a.server_set, a.coder_ext), (2, False, [], None))

    def test_experimental_options_need_experimental(self):
        for argv in (["--plan-steps"], ["--fresh-rework"], ["--step-syntax-check"], ["--parallel-check"], ["--checker", "x"], ["--arbiter", "x"]):
            with self.subTest(argv=argv):
                with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                    self.parse(*argv)
                self.assertTrue(self.parse("--experimental", *argv).experimental)


    def test_options_of_finished_measurements_are_gone_and_the_used_ones_stay(self):
        for argv in (["--coder-ext-record"], ["--think-limit", "5"], ["--think-family", "qwen"], ["--no-lesson-proposals"]):
            with self.subTest(argv=argv):
                with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                    self.parse(*argv)
        a = self.parse("--mode", "solo", "--self-check", "none", "--rework", "1", "--seed", "s", "--review", "r", "--from-stage", "x", "--server-set", "ubatch=1", "--keep-going", "--only", "x",
                       "--require-s0", "--bg-jobs", "--skills", "--hidden-feedback", "--check-first", "--parallel", "2", "--reasoning-budget", "0", "--pidfile", "p", "--no-record", "--no-own-tests")
        self.assertEqual((a.mode, a.self_check, a.rework, a.parallel), ("solo", "none", 1, 2))

    def test_the_coder_extension_config_always_records_with_the_fixed_thinking_defaults(self):
        build = devvm_build()
        config = build.coder_ext_config(build.apply_mode_defaults(self.parse("--profile", "standard")))
        self.assertEqual((config["record"], config["think_limit"], config["family"], config["enabled"]), (True, 2000, "qwen", "all"))
        self.assertTrue(build.apply_mode_defaults(self.parse()).hidden_feedback)


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
