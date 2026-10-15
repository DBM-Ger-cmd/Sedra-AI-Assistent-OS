"""AM-009 (Guppy meter collector, 2026-10-08): turns `git log --numstat` text and the list of candidate folders into the records of `code_meter` ({"date", "author", "added"}).
Pure functions, no git call and no file access (a thin shell around them comes later). Two small stages with hidden tests written outside the models and a last stage "all". GUPPI builds it, Claude only wrote this file and the reference."""

NOTES = '''# Notes for code_collector
Pure Python 3 standard library, no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
A record is {"date": "YYYY-MM-DD", "author": "guppi" or "claude", "added": int > 0}.
'''

COMMON = r'''
import copy
from code_collector import IMPORTS

LOG = "@2026-10-08\n10\t2\tsrc/a.py\n5\t0\tsrc/b.py\n-\t-\timg/logo.png\n\n@2026-10-07\n7\t1\tsrc/a.py\n3\t3\tarchiv/old.py\n"
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r"""
assert records_from_numstat(LOG) == [{"date": "2026-10-07", "author": "claude", "added": 10}, {"date": "2026-10-08", "author": "claude", "added": 15}]
assert records_from_numstat(LOG, guppi_paths={"src/b.py"}) == [{"date": "2026-10-07", "author": "claude", "added": 10}, {"date": "2026-10-08", "author": "claude", "added": 10}, {"date": "2026-10-08", "author": "guppi", "added": 5}]
assert records_from_numstat(LOG, ignore_prefixes=("archiv/", "img/")) == [{"date": "2026-10-07", "author": "claude", "added": 7}, {"date": "2026-10-08", "author": "claude", "added": 15}]
assert records_from_numstat("") == [] and records_from_numstat("\n\n") == [] and records_from_numstat(None) == []
two = "@2026-10-08\n4\t0\ta.py\n@2026-10-08\n6\t0\ta.py\n"
assert records_from_numstat(two) == [{"date": "2026-10-08", "author": "claude", "added": 10}]
junk = "5\t0\tbefore_any_header.py\n@not-a-date\n9\t0\tx.py\n@2026-10-09\nabc\t0\ty.py\n1\t2\n2\t0\t\n0\t5\tz.py\n8\t0\tok.py\n"
assert records_from_numstat(junk) == [{"date": "2026-10-09", "author": "claude", "added": 8}]
assert records_from_numstat("@2026-10-08\n1\t0\ta b.py\n") == [{"date": "2026-10-08", "author": "claude", "added": 1}]
assert records_from_numstat("@2026-10-08\r\n3\t0\ta.py\r\n") == [{"date": "2026-10-08", "author": "claude", "added": 3}]
g = {"src/b.py"}
snap = copy.deepcopy(g)
records_from_numstat(LOG, guppi_paths=g)
assert g == snap
"""

C2 = r"""
E = [{"spec": "am008_meter", "attempt": "attempt_01_20261008_113043", "lines": 400}, {"spec": "am008_meter", "attempt": "attempt_02_20261008_150000", "lines": 450},
     {"spec": "am007_crews", "attempt": "attempt_01_20261007_090000", "lines": 300}, {"spec": "am006_style", "attempt": "salvaged_20261007_1411", "lines": 90}]
snap = copy.deepcopy(E)
out = candidate_records(E)
assert E == snap
assert out == [{"date": "2026-10-07", "author": "guppi", "added": 300}, {"date": "2026-10-08", "author": "guppi", "added": 450}]
tie = [{"spec": "s", "attempt": "attempt_01_20261008_100000", "lines": 5}, {"spec": "s", "attempt": "attempt_02_20261008_100000", "lines": 9}]
assert candidate_records(tie) == [{"date": "2026-10-08", "author": "guppi", "added": 9}]
two = [{"spec": "a", "attempt": "attempt_01_20261008_100000", "lines": 5}, {"spec": "b", "attempt": "attempt_01_20261008_110000", "lines": 6}]
assert candidate_records(two) == [{"date": "2026-10-08", "author": "guppi", "added": 11}]
bad = ["x", None, {}, {"spec": "s", "attempt": "attempt_01_20261399_100000", "lines": 5}, {"spec": "s", "attempt": "attempt_01_20261008_100000", "lines": -1},
       {"spec": "s", "attempt": "attempt_01_20261008_100000", "lines": True}, {"spec": "s", "attempt": "attempt_01_20261008_100000", "lines": 0}, {"spec": 5, "attempt": "attempt_01_20261008_100000", "lines": 3},
       {"spec": "s", "attempt": 7, "lines": 3}]
assert candidate_records(bad) == [] and candidate_records(bad + two) == candidate_records(two)
assert candidate_records([]) == [] and candidate_records(None) == []
late_bad = [{"spec": "s", "attempt": "attempt_01_20261008_100000", "lines": 5}, {"spec": "s", "attempt": "attempt_02_20261008_120000", "lines": -3}]
assert candidate_records(late_bad) == [{"date": "2026-10-08", "author": "guppi", "added": 5}]
"""

STYLE = " No comments and no docstrings. Never modify the arguments. Put repeated checks into small private helpers."

STAGES = [
    {"name": "numstat",
     "task": """Create `code_collector.py` (Python 3 standard library only) with `records_from_numstat(text, guppi_paths=(), ignore_prefixes=()) -> list`. `text` is the output of `git log --numstat --pretty=format:@%ad --date=short`: a header line "@YYYY-MM-DD" starts a commit, the following lines are "<added>\\t<removed>\\t<path>" (tab separated; a path may contain spaces),
a binary file has "-" instead of the numbers, blank lines are separators, lines may end with "\\r\\n". `text` that is not a str counts as empty.
Count the ADDED lines per (date, author) over all commits: the author is "guppi" when the path is in `guppi_paths` (any iterable of exact paths), otherwise "claude". Skip silently: a path that starts with one of the `ignore_prefixes` (any iterable of str), binary lines, a line that does not have exactly the form
number TAB number TAB non-empty path, numstat lines before the first valid header, and all lines after a header whose date `datetime.date.fromisoformat` rejects (until the next valid header). Return only entries with added > 0 as [{"date", "author", "added"}] sorted by date and then author.""" + STYLE + """ Add `tests/test_code_collector.py` (unittest) with your own tests.""",
     "hidden": {"hidden_k1.py": hidden("records_from_numstat", C1)}},
    {"name": "candidates",
     "task": """In the existing `code_collector.py` (keep the other function) add `candidate_records(entries) -> list`. `entries` is an iterable of {"spec": str, "attempt": str, "lines": int} for build candidates of GUPPI; an attempt folder name ends with "_YYYYMMDD_HHMMSS" (for example "attempt_01_20261008_113043" or "salvaged_20261007_1411" which has no seconds and is NOT valid).
Skip silently every entry that is not a dict, has a spec or attempt that is not a str, an attempt without a valid date and time suffix (the date must be a real calendar date), or lines that is not an int > 0 (a bool is not an int). Per spec only the LATEST valid attempt counts (latest timestamp; on equal timestamps the attempt name that sorts later).
Return [{"date": "YYYY-MM-DD" of that attempt, "author": "guppi", "added": the lines}] with the lines of all specs on the same date added up, sorted by date.""" + STYLE + """ Add tests to `tests/test_code_collector.py`.""",
     "hidden": {"hidden_k2.py": hidden("records_from_numstat, candidate_records", C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_code_collector.py` and read `code_collector.py` once more. Make sure no check is copied into several functions, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_full_k.py": hidden("records_from_numstat, candidate_records", C1 + C2)}},
]
