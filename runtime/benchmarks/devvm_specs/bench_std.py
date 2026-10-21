"""STANDARD BENCHMARK for model test runs (Captain 2026-10-09: the am008 test takes over an hour, a model test needs a short, fixed, repeatable task).

Four small stages, each with an independent hidden test, no own tests and no own check by the model (the hidden test is the only judge; `no_own_check`), so that the time is the model's work and not a test spiral:
  slug    create a small function with several edge cases (what a model must read carefully)
  fix     repair a seeded module (the tool `edit_file` and reading code: where the Cline analysis found most failures)
  extend  add a parser to the module of stage 1 (several edge cases in one sentence each)
  move    move a function to a new module and update the imports (a change that touches two files)
Seed files: benchmarks/bench_std_seed/ (ledger.py with the defects, util.py and main.py). Expected duration with a fast model: 10 to 20 minutes. Results with every model go to the comparison table.
Run: benchmarks/probes/stdbench_probe.py (several models one after the other) or devvm_build.py --spec bench_std --seed benchmarks/bench_std_seed --all-models <key> --rework 1 --tidy."""

SEED = "benchmarks/bench_std_seed"      # PIPE-10: devvm_build takes this folder as --seed when none is given
NOTES = '''# Notes
Pure Python 3 standard library. No comments and no docstrings. Do NOT write tests: an independent acceptance test judges your work. Change only what the task asks.
'''

TOP = '''
import subprocess
import sys
'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


C1 = hidden('''
assert slugify("Hello World") == "hello-world"
assert slugify("  Many   spaces  here ") == "many-spaces-here"
assert slugify("Caf\\u00e9 cr\\u00e8me!") == "cafe-creme"
assert slugify("a--b__c") == "a-b-c"
assert slugify("---x---") == "x"
assert slugify("") == "n-a" and slugify("!!!") == "n-a" and slugify("   ") == "n-a"
assert slugify("Hello World", max_len=5) == "hello"
assert slugify("Hello World", max_len=6) == "hello"
assert slugify("Hello World", max_len=7) == "hello-w"
assert slugify("abc", max_len=0) == "n-a"
assert slugify("x1 Y2") == "x1-y2" and slugify(None) == "n-a" and slugify(42) == "42"
''', "from textkit import slugify\n")

C2 = hidden('''
assert balance([]) == 0.0
assert balance([{"type": "credit", "amount": 10}, {"type": "debit", "amount": 4}]) == 6.0
assert balance([{"type": "debit", "amount": 5}]) == -5.0
assert balance([{"type": "credit", "amount": 0.1}, {"type": "credit", "amount": 0.2}]) == 0.3
assert balance([{"type": "credit", "amount": 1.005}, {"type": "debit", "amount": 0.001}]) == 1.0
for bad, message in (([{"type": "refund", "amount": 1}], "unknown type: refund"), ([{"type": "credit", "amount": -1}], "negative amount"), ([{"type": "debit", "amount": -0.5}], "negative amount")):
    try:
        balance(bad)
    except ValueError as exc:
        assert str(exc) == message, (str(exc), message)
    else:
        raise AssertionError("no ValueError for " + message)
entries = [{"type": "credit", "amount": 3}]
balance(entries)
assert entries == [{"type": "credit", "amount": 3}]
''', "from ledger import balance\n")

C3 = hidden('''
assert parse_kv("a = 1\\nb=two") == {"a": "1", "b": "two"}
assert parse_kv("# comment\\n\\n  x = y  \\n") == {"x": "y"}
assert parse_kv('name = "John Smith"') == {"name": "John Smith"}
assert parse_kv("k = v # not a comment") == {"k": "v # not a comment"}
assert parse_kv("a = 1\\na = 2") == {"a": "2"}
assert parse_kv("empty =") == {"empty": ""}
assert parse_kv("") == {} and parse_kv("   \\n#only") == {}
for text, line in (("a = 1\\nbroken line", 2), ("=novalue", 1), ("ok = 1\\n\\n  \\nnoequals", 4)):
    try:
        parse_kv(text)
    except ValueError as exc:
        assert str(exc) == "line %d" % line, (str(exc), line)
    else:
        raise AssertionError("no ValueError for line %d" % line)
assert parse_kv("a=1\\r\\nb=2\\r\\n") == {"a": "1", "b": "2"}
''', "from textkit import parse_kv, slugify\nassert slugify('A b') == 'a-b'\n")

C4 = hidden('''
import mathkit
import util
assert mathkit.clamp(5, 0, 3) == 3 and mathkit.clamp(-1, 0, 3) == 0 and mathkit.clamp(2, 0, 3) == 2
assert not hasattr(util, "clamp")
assert util.double(4) == 8
run = subprocess.run([sys.executable, "main.py"], capture_output=True, text=True, timeout=30)
assert run.returncode == 0, run.stderr
assert run.stdout.strip() == "3 8", run.stdout
source = open("main.py", encoding="utf-8").read()
assert "mathkit" in source and "from util import clamp" not in source
''', "")
C4 = TOP + C4

STAGES = [
    {"name": "slug", "no_own_check": True,
     "task": '''Create `textkit.py` with `slugify(text, max_len=None) -> str`.
- `text` is converted with `str(...)` first; None counts as the empty text.
- Letters are lower case; accented letters lose their accent (cafe for café, using unicodedata NFKD and dropping what is not ASCII).
- Every run of characters that are not ASCII letters or digits becomes ONE "-"; leading and trailing "-" are removed.
- When the result is empty it is "n-a".
- `max_len` (an int >= 0) cuts the result to at most that many characters and removes a trailing "-" of the cut text; a cut text that is empty gives "n-a". `max_len=None` cuts nothing.
Do not write tests. No comments and no docstrings.''',
     "hidden": {"hidden_s1.py": C1}},
    {"name": "fix", "no_own_check": True,
     "task": '''`ledger.py` (already in the workspace) has `balance(entries)` with defects. Fix it so that it does exactly this: `entries` is a list of dicts with "type" ("credit" or "debit") and "amount" (a number >= 0).
It returns the sum of the credits minus the sum of the debits, rounded to 2 decimals (an empty list gives 0.0). An amount below 0 raises `ValueError("negative amount")`; any other type raises `ValueError("unknown type: <type>")`. The argument is never modified.
Change only what is needed. Do not write tests. No comments and no docstrings.''',
     "hidden": {"hidden_s2.py": C2}},
    {"name": "extend", "no_own_check": True,
     "task": '''In the existing `textkit.py` (keep `slugify`) add `parse_kv(text) -> dict`: a small settings parser.
- Every line has the form `key = value` (white space around key and value is removed; the value may be empty).
- Empty lines, lines with only white space and lines that start with "#" (after white space) are ignored. A "#" inside a value is part of the value.
- A value in double quotes loses the quotes and keeps its inner spaces.
- A key that comes twice: the last one wins.
- Lines may end with "\\r\\n".
- Any other line (no "=", or an empty key) raises `ValueError("line N")` where N is the number of the line, counted from 1 over ALL lines.
Do not write tests. No comments and no docstrings.''',
     "hidden": {"hidden_s3.py": C3}},
    {"name": "move", "no_own_check": True,
     "task": '''The function `clamp` lives in `util.py` and `main.py` uses it. Move `clamp` to a new module `mathkit.py` (the code unchanged), remove it from `util.py` (the other functions of `util.py` stay) and change `main.py` so that it imports `clamp` from `mathkit` and still prints the same as before when run with `python3 main.py`.
Do not write tests. No comments and no docstrings.''',
     "hidden": {"hidden_s4.py": C4}},
]
