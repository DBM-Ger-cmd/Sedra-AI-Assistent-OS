"""Background job test (Captain 2026-10-13: "die Spec dafuer", the shell tools of the coder against a real model). With --bg-jobs the coder has shell_start, shell_log and shell_stop. The seed
(benchmarks/devvm_seeds/bg_report) holds `crunch.py`, a calculation that takes about 50 seconds (three parts of 15 seconds, then it prints `TOTAL <number>`); a normal VM run
(run_python) is killed after 30 seconds, so the number can only be had from a background job (the build raises the VM limit for --bg-jobs to 100 s in its own copy of the sandbox
config) or by re-writing the loop without the waiting. The second part of the task (summary.py) is pure logic that the coder can write while the job runs. The hidden test judges only
the files; whether the job tools were used shows in the journal of the run (tool_counts: shell_start, shell_log). Run with --seed benchmarks/devvm_seeds/bg_report --bg-jobs.
Claude wrote the seed, this file, the hidden test and the reference (benchmarks/devvm_refs/bg_report)."""

NOTES = '''# Notes for the background report
The workspace holds crunch.py (do not change it). Standard library only, no comments and no docstrings in new code.
You have the tools shell_start, shell_log and shell_stop: a command started with shell_start runs in the background in the VM, you are woken when it exits or prints a line that matches wake_match,
and shell_log shows what it printed. run_python is killed after a shorter time than crunch.py needs.
'''

TEST = r'''
import ast, os

summary = __import__("summary")
s = summary.summarize
assert s([3, 1, 2]) == {"count": 3, "mean": 2.0, "median": 2, "min": 1, "max": 3}, s([3, 1, 2])
assert s([4, 1, 3, 2]) == {"count": 4, "mean": 2.5, "median": 2.5, "min": 1, "max": 4}, s([4, 1, 3, 2])
assert s([1, 2, 2, 10]) == {"count": 4, "mean": 3.75, "median": 2.0, "min": 1, "max": 10}
assert s([2.5]) == {"count": 1, "mean": 2.5, "median": 2.5, "min": 2.5, "max": 2.5}
assert s([1, True, "x", None, 3, 5.0]) == {"count": 3, "mean": 3.0, "median": 3, "min": 1, "max": 5.0}, s([1, True, "x", None, 3, 5.0])
assert s((7, 9)) == {"count": 2, "mean": 8.0, "median": 8.0, "min": 7, "max": 9}
assert s([1, 2, 4]) == {"count": 3, "mean": 2.33, "median": 2, "min": 1, "max": 4}
for empty in ([], [True, "a"], None, "abc", 5, {}):
    assert s(empty) is None, empty
before = [3, 1, 2]; s(before); assert before == [3, 1, 2]

assert os.path.isfile("crunch_total.txt"), "crunch_total.txt is missing"
assert open("crunch_total.txt", encoding="utf-8").read().strip() == "EXPECTED", open("crunch_total.txt", encoding="utf-8").read()
source = open("crunch.py", encoding="utf-8").read()
ast.parse(source)
assert "time.sleep(15)" in source and "TOTAL" in source, "crunch.py was changed"
print("ok")
'''.replace("EXPECTED", "694753599")

STAGES = [
    {"name": "all",
     "task": """The workspace holds `crunch.py`, a slow calculation: it takes about 50 seconds and prints, as its last line, `TOTAL <number>`. Do two things.
1. Create `crunch_total.txt` with ONLY that number (digits, then a newline). Do not change `crunch.py`. A normal run_python is killed after 30 seconds, so start the calculation in the BACKGROUND with `shell_start` (command `python3 crunch.py`, wake_match `TOTAL`), keep working, and read its output with `shell_log` when it wakes you.
2. While the calculation runs, create `summary.py` with `summarize(values) -> dict or None` for a list or tuple of numbers:
- Only ints and floats count; bool, str, None and everything else in the list is skipped. Any argument that is not a list or tuple, and a list without a counted number, give None.
- The result is {"count": how many numbers counted, "mean": their mean rounded to 2 decimals (round()), "median": the middle number of the sorted numbers (for an even count the mean of the two middle ones, as a float), "min": the smallest, "max": the largest}.
- The argument is never changed. No comments and no docstrings.""",
     "hidden": {"hidden_bg_1.py": TEST}},
]
