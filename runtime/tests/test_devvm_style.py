import env_skip; env_skip.need_dulwich()   # whole module needs the DevVM git (dulwich); skipped with reason where it is missing
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.acceptance_suite import SuiteError, load_suite
from guppi_runtime.devvm import DevWorkspace
from guppi_runtime.devvm_style import StyleError, snapshot, strip_comments, style_report, tidy

RUNTIME = Path(__file__).resolve().parents[1]
SUITE = RUNTIME.parent / "workspace" / "GUPPI_OS" / "acceptance" / "suites" / "am006_style"
POLICY = {'max_files': 30, 'max_file_bytes': 20000, 'max_input_bytes': 40000}


@unittest.skipUnless(SUITE.is_dir(), "the stored suite am006-style is not on this machine")
class SuiteParityTest(unittest.TestCase):
    """devvm_style is the reference of the suite am006-style: every hidden script of the suite passes against it."""

    def test_every_criterion_of_the_stored_suite_passes_against_this_module(self):
        try:
            suite = load_suite(str(SUITE))
        except SuiteError as exc:
            self.skipTest(str(exc))
        for criterion in suite.criteria:
            script, text = suite.scripts[criterion["id"]]
            text = text.replace("from agent_contracts import ContractError", "from guppi_runtime.devvm_style import StyleError as ContractError").replace("from style_check import", "from guppi_runtime.devvm_style import")
            with tempfile.TemporaryDirectory() as tmp:
                Path(tmp, script).write_text(text, encoding="utf-8")
                run = subprocess.run([sys.executable, script], cwd=tmp, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(RUNTIME / "src")}, timeout=120)
            self.assertEqual(run.returncode, 0, f"{criterion['id']}: {run.stdout}{run.stderr}")


class StripTest(unittest.TestCase):
    def test_comments_and_docstrings_go_and_the_code_stays_identical(self):
        source = ('"""module doc"""\nimport os  # keep os\n\n# a comment line\ndef f(x):\n    """Doc."""\n    y = x + 1  # trailing\n    s = "# not a comment"\n    return y, s\n\n\n'
                  'class K:\n    """doc"""\n\n    def m(self):\n        """only a docstring"""\n\n    def n(self):\n        # only a comment\n        return 1\n')
        cleaned = strip_comments(source)
        self.assertNotIn("#", cleaned.replace('"# not a comment"', ""))
        self.assertNotIn("Doc.", cleaned); self.assertNotIn("module doc", cleaned); self.assertNotIn("only a docstring", cleaned)
        self.assertIn('s = "# not a comment"', cleaned)
        namespace = {}
        exec(compile(cleaned, "x", "exec"), namespace)
        self.assertEqual(namespace["f"](1), (2, "# not a comment")); self.assertIsNone(namespace["K"]().m()); self.assertEqual(namespace["K"]().n(), 1)
        self.assertEqual(strip_comments(cleaned), cleaned)

    def test_a_function_that_has_only_a_docstring_keeps_a_pass(self):
        cleaned = strip_comments("def f():\n    '''only'''\n")
        self.assertIn("pass", cleaned)
        compile(cleaned, "x", "exec")

    def test_shebang_and_encoding_lines_stay_and_broken_source_is_returned_unchanged(self):
        text = "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\nx = 1  # c\n"
        self.assertTrue(strip_comments(text).startswith("#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n"))
        broken = "def f(:\n    # c\n"
        self.assertEqual(strip_comments(broken), broken)
        with self.assertRaises(StyleError):
            strip_comments(None)

    def test_the_result_is_never_longer_than_the_source_and_keeps_line_structure_of_code(self):
        source = "import os\n\n\ndef f():\n    # note\n    return os.sep\n"
        self.assertEqual(strip_comments(source), "import os\n\n\ndef f():\n    return os.sep\n")


class TidyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = DevWorkspace(Path(self.tmp.name), "M-STYLE001", policy=dict(POLICY))
        self.ws.create()

    def test_new_files_are_cleaned_helpers_are_deleted_and_tests_and_seeds_are_untouched(self):
        self.ws.write("agent_contracts.py", "# seed comment\nx = 1\n")
        before = snapshot(self.ws)
        self.ws.write("style_check.py", '"""doc"""\n# c\ndef f():\n    return 1\n')
        self.ws.write("debug_duplicates.py", "print(1)\n")
        self.ws.write("test_debug.py", "print(2)\n")
        self.ws.write("test_style_check.py", "# my test\nassert True\n")
        self.ws.write("tests/test_style_check.py", "# in tests\nassert True\n")
        self.ws.write("run_tests.py", "pass\n")
        self.ws.write("notes.txt", "keep\n")
        out = tidy(self.ws, before, expected={"style_check"})
        self.assertEqual(sorted(out["deleted"]), ["debug_duplicates.py", "run_tests.py", "test_debug.py"])
        self.assertEqual(out["stripped"], ["style_check.py"])
        self.assertEqual(self.ws.read("style_check.py"), "def f():\n    return 1\n")
        self.assertEqual(self.ws.read("agent_contracts.py"), "# seed comment\nx = 1\n")
        self.assertIn("# my test", self.ws.read("test_style_check.py")); self.assertIn("# in tests", self.ws.read("tests/test_style_check.py"))
        self.assertTrue(set(self.ws.tree()) >= {"notes.txt", "test_style_check.py", "tests/test_style_check.py"})

    def test_a_file_the_model_changed_is_cleaned_but_an_untouched_one_is_not(self):
        self.ws.write("a.py", "# old\nx = 1\n")
        self.ws.write("b.py", "# old\ny = 2\n")
        before = snapshot(self.ws)
        self.ws.write("a.py", "# old\nx = 3\n")
        out = tidy(self.ws, before, expected=set())
        self.assertEqual(out["stripped"], ["a.py"]); self.assertEqual(self.ws.read("a.py"), "x = 3\n"); self.assertEqual(self.ws.read("b.py"), "# old\ny = 2\n")

    def test_what_needs_thought_is_reported_not_changed(self):
        before = snapshot(self.ws)
        body = "".join(f"    v{i} = {i}\n" for i in range(45))
        block = "    a = load()\n    b = clean(a)\n    c = split(b)\n    return save(c)\n"
        self.ws.write("m.py", "def big():\n" + body + "    return v0\n\n\ndef one():\n" + block + "\n\ndef two():\n" + block)
        out = tidy(self.ws, before, expected={"m"})
        self.assertEqual(out["report"]["m.py"]["violations"], ["duplicate_code", "long_function"])
        self.assertEqual(out["report"]["m.py"]["long_functions"][0]["name"], "big")
        self.assertIn("v44 = 44", self.ws.read("m.py"))

    def test_a_syntax_error_is_left_alone_and_does_not_stop_the_tidy(self):
        before = snapshot(self.ws)
        self.ws.write("bad.py", "def f(:\n    # c\n")
        out = tidy(self.ws, before, expected={"bad"})
        self.assertEqual((out["stripped"], out["report"]), ([], {})); self.assertIn("# c", self.ws.read("bad.py"))


class ReportTest(unittest.TestCase):
    def test_the_report_has_the_documented_shape(self):
        self.assertEqual(style_report("def f(x):\n    return x\n"), {"ok": True, "lines": {"total": 2, "blank": 0, "comment": 0, "code": 2}, "functions": [{"name": "f", "lines": 2}], "duplicates": [], "violations": []})


if __name__ == "__main__":
    unittest.main()
