import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"
sys.path.insert(0, str(BENCH.parent / "src"))


def load(name):
    loaded = importlib.util.spec_from_file_location(name, BENCH / f"{name}.py")
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    return module


spec_check, logbook, ab_queue = load("spec_check"), load("logbook"), load("archiv/ab_queue")      # archived with line L1 (2026-10-20)


class SpecCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.tree = Path(self.tmp.name, "ref"); self.tree.mkdir()
        (self.tree / "mod.py").write_text("def double(x):\n    return x * 2\n", encoding="utf-8")

    def test_lint_finds_missing_pieces_and_warns_about_or(self):
        spec = SimpleNamespace(NOTES="", STAGES=[{"name": "a", "task": "t", "hidden": {"h.py": "assert 1 or 2\n"}}, {"name": "a", "task": ""}])
        problems, warnings = spec_check.lint(spec)
        self.assertIn("no NOTES text", problems); self.assertIn("stage name twice: a", problems)
        self.assertTrue(any("no hidden test" in p for p in problems)); self.assertTrue(any("`or`" in w for w in warnings))
        clean = SimpleNamespace(NOTES="n", STAGES=[{"name": "a", "task": "t", "hidden": {"h.py": "assert 1\n"}}])
        self.assertEqual(spec_check.lint(clean), ([], []))

    def test_run_stage_runs_in_a_copy_and_names_the_failing_line(self):
        stage = {"name": "s", "hidden": {"hidden_a.py": "from mod import double\nassert double(2) == 4\nassert double(3) == 7\n"}}
        [(file, ok, tail)] = spec_check.run_stage(self.tree, stage)
        self.assertFalse(ok); self.assertEqual(tail[0], "line 3: assert double(3) == 7")
        good = {"name": "s", "hidden": {"hidden_a.py": "from mod import double\nassert double(2) == 4\n"}}
        self.assertTrue(spec_check.run_stage(self.tree, good)[0][1]); self.assertFalse((self.tree / "hidden_a.py").exists())

    def test_node_tests_are_run_too_and_never_pass_silently(self):
        # 2026-10-13: a stage with only host_hidden (JS) reported ok because only the python tests ran; three specs looked proven while their tests failed
        import shutil
        (self.tree / "mod.js").write_text("function triple(x) { return x * 3; }\n", encoding="utf-8")
        head = 'const fs=require("fs"),vm=require("vm"),assert=require("assert");const box={};vm.createContext(box);vm.runInContext(fs.readFileSync("mod.js","utf8"),box);'
        stage = {"name": "js", "host_hidden": {"hidden_a.cjs": head + "assert.strictEqual(box.triple(2), 6);\nassert.strictEqual(box.triple(3), 10);\nconsole.log('ok');\n"}}
        [(file, ok, tail)] = spec_check.run_stage(self.tree, stage)
        self.assertEqual(file, "hidden_a.cjs"); self.assertFalse(ok)
        if shutil.which("node"):
            self.assertTrue(any("AssertionError" in t for t in tail), tail)
            good = {"name": "js", "host_hidden": {"hidden_a.cjs": head + "assert.strictEqual(box.triple(2), 6);\nconsole.log('ok');\n"}}
            self.assertTrue(spec_check.run_stage(self.tree, good)[0][1]); self.assertFalse((self.tree / "hidden_a.cjs").exists())
        else:
            self.assertIn("node is not installed", tail[0])
        both = {"name": "mix", "hidden": {"h.py": "from mod import double\nassert double(2) == 4\n"}, "host_hidden": stage["host_hidden"]}
        self.assertEqual([f for f, _, _ in spec_check.run_stage(self.tree, both)], ["h.py", "hidden_a.cjs"])

    def test_a_missing_tree_fails_the_tests_instead_of_raising(self):
        stage = {"name": "s", "hidden": {"h.py": "import mod\n"}}
        self.assertFalse(spec_check.run_stage(None, stage)[0][1])


class LogbookTests(unittest.TestCase):
    def test_row_uses_the_given_clock_and_refuses_bad_input(self):
        drive = chr(69)
        row = logbook.make_row("BAU", "a | b\nc", "ref", now=datetime(2026, 10, 13, 9, 5))
        self.assertEqual(row, "| 2026-10-13 09:05 | BAU | a / b c | ref |")
        self.assertIn("(nachgetragen)", logbook.make_row("BAU", "x", late=True))
        for art in logbook.PLACEHOLDERS:      # the literal placeholder of the usage line is refused (2026-10-14: three rows said ART)
            with self.assertRaises(ValueError): logbook.make_row(art, "x")
        self.assertEqual(logbook.ARTS, ("ENTSCHEIDUNG", "SPEC", "BAU", "INTEGRATION", "MESSUNG", "FEHLER", "AENDERUNG", "DOKU", "RECHERCHE", "HINWEIS"))
        for art in logbook.ARTS: self.assertIn(f"| {art} |", logbook.make_row(art, "x"))
        self.assertIn("| AENDERUNG |", logbook.make_row("ÄNDERUNG", "x"))      # umlaut taken as AENDERUNG (V2)
        for art in ("UMBAU", "AUDIT", "bau", "ÖL"):      # a word outside the fixed list stops, and the message names the list
            with self.assertRaises(ValueError) as stop: logbook.make_row(art, "x")
            if art != "bau": self.assertIn("allowed: ENTSCHEIDUNG, SPEC, BAU", str(stop.exception))
        for art, text in (("bau", "x"), ("BAU", ""), ("BAU", "see " + drive + ":" + chr(92) + "x"), ("BAU", "see " + drive + ":/Users/a"), ("B", "x")):
            with self.assertRaises(ValueError): logbook.make_row(art, text)

    def test_the_command_line_stops_on_an_unknown_kind_and_names_the_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp, "b.md"); book.write_text("# t\n", encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(logbook.main(["add", "UMBAU", "x", "--file", str(book)]), 2)
                self.assertEqual(logbook.main(["add", "ÄNDERUNG", "x", "--file", str(book)]), 0)
            self.assertIn("allowed: ENTSCHEIDUNG, SPEC, BAU, INTEGRATION, MESSUNG, FEHLER, AENDERUNG, DOKU, RECHERCHE, HINWEIS", err.getvalue())
            self.assertEqual(len(book.read_text(encoding="utf-8").splitlines()), 2)

    def test_append_keeps_the_line_ending_of_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            crlf, lf = Path(tmp, "a.md"), Path(tmp, "b.md")
            crlf.write_bytes(b"# t\r\n| x |"); lf.write_bytes(b"# t\n")
            logbook.append(crlf, "| row |"); logbook.append(lf, "| row |")
            self.assertEqual(crlf.read_bytes(), b"# t\r\n| x |\r\n| row |\r\n"); self.assertEqual(lf.read_bytes(), b"# t\n| row |\n")


class AbQueueTests(unittest.TestCase):
    def test_tool_counts_counts_the_calls_of_the_answers_not_the_history(self):
        call = lambda name, args: {"function": {"name": name, "arguments": args}}
        record = {"sent": [{"tool_calls": [call("skill_read", "{}")]}], "response": {"choices": [{"message": {"tool_calls": [call("skill_search", "{}"), call("skill_read", '{"id": "x", "brief": true}')]}}]}}
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "01.jsonl").write_text(json.dumps(record) + "\nnot json\n", encoding="utf-8")
            counts = ab_queue.tool_counts(tmp)
        self.assertEqual((counts["skill_search"], counts["skill_read"], counts["brief"]), (1, 1, 1))

    def test_report_shows_the_stage_matrix_per_arm(self):
        row = lambda ok: {"exit": 0, "passed": sum(ok.values()), "seconds": 10.0, "calls": 5, "exported_to": None, "stage_results": ok}
        summary = {"tag": "t", "spec": "s", "recipe": "r", "pairs": 2, "arms": {"A": [row({"a": False, "b": True}), row({"a": False, "b": False})], "B": [row({"a": True, "b": True})]}}
        text = ab_queue.report_text(summary, ["a", "b"], Path("none"))
        self.assertIn("A1: exit 0  1/2  -+", text); self.assertIn("A per stage: a 0/2, b 1/2   all stages 1/4", text); self.assertIn("B per stage: a 1/1, b 1/1   all stages 2/2", text)

    def test_arm_argument_and_queue_end_marker(self):
        self.assertEqual(ab_queue.parse_arm('B=--skills "some dir/x"'), ("B", ["--skills", "some dir/x"]))
        self.assertEqual(ab_queue.parse_arm("A="), ("A", []))
        with self.assertRaises(Exception): ab_queue.parse_arm("=x")
        self.assertEqual(ab_queue.FINISHED, "ab queue finished")


if __name__ == "__main__":
    unittest.main()
