"""GUPPI reproduction harness (runs in GUPPI's VM before the real test command; always exits 0, the verdict is unittest's).

Captain 2026-10-03 ("Reproduktionsschritt bauen"): the local coders could not find a bug from a bare test failure such as
"'Port out of range 0-65535' != 'uix_url_not_allowed'" - they did not know WHICH input caused it or WHERE in their code. This
harness runs every test of tests/ one by one and, for each failing test, prints what the code under test really did inside each
`assertRaises`: the input (the assertion's msg), the exception it raised or that it raised none, and the line of the code under test
that raised it. Lines start with "REPRO" so GUPPI's rework keeps them as feedback. Standard library only; reads and writes nothing.
"""
import os
import sys
import traceback
import unittest
from unittest import case

ROOT = os.getcwd()
MAX_LINES = 60
captured = []
_original_exit = case._AssertRaisesContext.__exit__


def _code_frames(tb):
    """Frames of the code under test: inside the project, outside tests/ and outside this harness."""
    frames = []
    for f in traceback.extract_tb(tb):
        path = os.path.abspath(f.filename)
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        if path.startswith(ROOT) and not rel.startswith("tests/") and not rel.startswith(".."):
            frames.append(f"{rel}:{f.lineno}: {(f.line or '').strip()}")
    return frames[-3:]


def _recording_exit(self, exc_type, exc_value, tb):
    expected = getattr(self.expected, "__name__", None) or ",".join(getattr(e, "__name__", str(e)) for e in self.expected)
    record = {"input": self.msg, "expected": expected}
    if exc_type is None:
        record["got"] = "no exception"
    else:
        record["got"] = f"{exc_type.__name__}: {exc_value}"
        record["where"] = _code_frames(tb)
    captured.append(record)
    return _original_exit(self, exc_type, exc_value, tb)


def _tests(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _tests(item)
        else:
            yield item


def main():
    case._AssertRaisesContext.__exit__ = _recording_exit
    sys.path.insert(0, ROOT)
    lines = []
    try:
        suite = unittest.defaultTestLoader.discover("tests")      # like `python -m unittest discover -s tests`
    except Exception as exc:
        print(f"REPRO could not load the tests: {type(exc).__name__}: {exc}")
        return 0
    for test in _tests(suite):
        captured.clear()
        result = unittest.TestResult()
        test.run(result)
        problems = result.failures + result.errors
        if not problems:
            continue
        text = problems[0][1].strip().splitlines()
        summary = next((l for l in text if l.startswith(("AssertionError", "Error", "Exception")) or ": " in l and l.split(":")[0].endswith("Error")), text[-1])
        lines.append(f"REPRO {test.id()}: {summary.strip()}")
        for rec in captured:
            where = (" at " + " <- ".join(reversed(rec["where"]))) if rec.get("where") else ""
            lines.append(f"REPRO   input {rec['input']}: expected {rec['expected']}, got {rec['got']}{where}")
        if result.errors:
            tb_lines = [l for l in problems[0][1].splitlines() if l.strip().startswith("File ") and "/tests/" not in l.replace("\\", "/")]
            lines.extend(f"REPRO   {l.strip()}" for l in tb_lines[-3:])
    print("\n".join(lines[:MAX_LINES]) if lines else "REPRO all tests pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
