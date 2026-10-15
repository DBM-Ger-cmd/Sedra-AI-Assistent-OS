"""Lesson proposals after a run (E-11 part 2; Captain 2026-10-13: GUPPI builds it). After a build, the error texts of its failed attempts are searched for known mistakes that repeat from run to run
(a file name the sandbox refuses, a repeated placeholder, a module that does not exist in the VM, a syntax error); each known mistake becomes ONE proposed lesson card for the Captain to approve
(`guppi lessons approve`). Nothing is used before he approves it. Pure functions, nothing is written. GUPPI builds it; Claude only wrote this file, the hidden tests and the reference
(benchmarks/devvm_refs/lesson_proposer)."""

NOTES = '''# Notes for lesson_proposer
Python 3 standard library only (re), no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
The lesson texts are English exactly as written in the task (the hidden tests compare them).
'''

HEAD = r'''
from lesson_proposer import signatures, propose

CRED = "error: potential_credential_file"
PLACE = "src/tm.py holds [written: 1704 characters, they are in the file now]"
CUT = "wrote [...cut...] into the file"
MOD = "ModuleNotFoundError: No module named 'numpy.linalg'"
SYN = "  File \"a.py\", line 3\nSyntaxError: invalid syntax"
T_CRED = "Do not name files token, secret or password: the sandbox refuses them as credential files. Choose a neutral name such as usage_meter.py."
T_PLACE = "Never repeat a write call from your shortened history, its text is only a placeholder. Read the file with read_file and write the real content."
T_SYN = "A file with a syntax error cannot be imported. After every write call check_syntax on the file before you go on."
T_MOD = "The module 'numpy' is not available in the sandbox. Use only the Python standard library and the modules of the project."
'''

SIG = r'''
assert signatures(CRED) == ["reserved_name"]
assert signatures(PLACE) == ["placeholder_write"] and signatures(CUT) == ["placeholder_write"]
assert signatures(MOD) == ["missing_module"] and signatures(SYN) == ["syntax_error"]
assert signatures(CRED + "\n" + SYN + "\n" + MOD + "\n" + PLACE) == ["reserved_name", "placeholder_write", "missing_module", "syntax_error"]
for none in ["", "all fine", "AssertionError: 1 != 2", None, 5, ["x"]]:
    assert signatures(none) == [], none
assert signatures("ModuleNotFoundError: No module named 'a'\nModuleNotFoundError: No module named 'b'") == ["missing_module"]
assert signatures("[written: x characters") == []
print("ok")
'''

PROPOSE = r'''
r = propose([{"stage": "tokens", "text": CRED}], "run-1")
assert r == [{"text": T_CRED, "source": "run:run-1:tokens"}], r
r = propose([{"stage": "a", "text": PLACE}, {"stage": "b", "text": SYN}, {"stage": "c", "text": MOD}], "R")
assert [x["text"] for x in r] == [T_PLACE, T_SYN, T_MOD] and [x["source"] for x in r] == ["run:R:a", "run:R:b", "run:R:c"], r
r = propose([{"stage": "a", "text": CRED}, {"stage": "b", "text": CRED}, {"stage": "c", "text": CRED + "\n" + SYN}], "R")
assert [x["text"] for x in r] == [T_CRED, T_SYN] and r[0]["source"] == "run:R:a" and r[1]["source"] == "run:R:c", r
four = propose([{"stage": "s", "text": CRED + "\n" + PLACE + "\n" + MOD + "\n" + SYN}], "R")
assert [x["text"] for x in four] == [T_CRED, T_PLACE, T_MOD], four
mods = propose([{"stage": "s", "text": "ModuleNotFoundError: No module named 'requests'"}, {"stage": "t", "text": MOD}], "R")
assert [x["text"] for x in mods] == ["The module 'requests' is not available in the sandbox. Use only the Python standard library and the modules of the project.", T_MOD], mods
two = propose([{"stage": "s", "text": "ModuleNotFoundError: No module named 'aaa'" + chr(10) + "ModuleNotFoundError: No module named 'bbb.c'"}], "R")
assert [x["text"] for x in two] == ["The module 'aaa' is not available in the sandbox. Use only the Python standard library and the modules of the project.", "The module 'bbb' is not available in the sandbox. Use only the Python standard library and the modules of the project."], two
assert propose([{"stage": "s", "text": CRED}], "R", known=[T_CRED]) == []
assert propose([{"stage": "s", "text": CRED}], "R", known=["  do NOT name   files token, secret or password: the sandbox refuses them as credential files. choose a neutral name such as usage_meter.py. "]) == []
assert [x["text"] for x in propose([{"stage": "s", "text": CRED + SYN}], "R", known=[T_CRED])] == [T_SYN]
assert propose([], "R") == [] and propose(None, "R") == [] and propose("x", "R") == []
assert propose([{"stage": "s", "text": "all fine"}, 5, None, {"text": CRED}, {"stage": "s"}, {"stage": "s", "text": 7}], "R") == [{"text": T_CRED, "source": "run:R:?"}]
assert propose([{"stage": "s", "text": CRED}], "R", known=None) == [{"text": T_CRED, "source": "run:R:s"}]
fs = [{"stage": "s", "text": CRED}]; kn = [T_SYN]; propose(fs, "R", kn); assert fs == [{"stage": "s", "text": CRED}] and kn == [T_SYN]
assert all(20 <= len(x["text"]) <= 400 for x in propose([{"stage": "s", "text": CRED + PLACE + MOD + SYN}], "R", limit=10))
assert len(propose([{"stage": "s", "text": CRED + PLACE + MOD + SYN}], "R", limit=10)) == 4
assert len(propose([{"stage": "s", "text": CRED + PLACE + MOD + SYN}], "R", limit=2)) == 2
print("ok")
'''

STAGES = [
    {"name": "signatures",
     "task": """Create `lesson_proposer.py` (Python 3 standard library only) with `signatures(text) -> list of str`: the keys of the known mistakes that occur in the text (re.search each), in THIS order, each at most once:
1. "reserved_name": the text contains `potential_credential_file`.
2. "placeholder_write": the text contains `[written: ` followed by digits and ` characters`, or the text `[...cut...]`.
3. "missing_module": `ModuleNotFoundError: No module named '` followed by a module name.
4. "syntax_error": the text contains `SyntaxError`.
A text that is not a string gives [].""",
     "hidden": {"hidden_lp_1.py": HEAD + SIG}},
    {"name": "propose",
     "task": """Add `propose(failures, run_id, known=None, limit=3)` to `lesson_proposer.py` (keep everything else). failures: a list of dicts {"stage": str, "text": str} (anything else in the list, a non-list, or an entry without a string "text" is skipped; a missing or non-string "stage" counts as "?").
Each mistake of `signatures(text)` gives ONE lesson text (the same mistake in a later entry gives nothing new):
 - reserved_name: "Do not name files token, secret or password: the sandbox refuses them as credential files. Choose a neutral name such as usage_meter.py."
 - placeholder_write: "Never repeat a write call from your shortened history, its text is only a placeholder. Read the file with read_file and write the real content."
 - missing_module: "The module 'NAME' is not available in the sandbox. Use only the Python standard library and the modules of the project." where NAME is the part of the module name before the first dot; a different NAME is a different lesson, also when several modules are missing in the SAME text (one lesson for each, in the order they appear).
 - syntax_error: "A file with a syntax error cannot be imported. After every write call check_syntax on the file before you go on."
Result: a list of {"text": lesson, "source": "run:" + run_id + ":" + stage} in the order of first appearance (entries in order, mistakes in the order of `signatures`), at most `limit` entries.
`known`: texts of cards that exist already (or None); a lesson whose text equals one of them after lower-casing and collapsing every run of whitespace to one space (and stripping) is left out. Never modify the arguments.""",
     "hidden": {"hidden_lp_1.py": HEAD + SIG, "hidden_lp_2.py": HEAD + PROPOSE}},
]
