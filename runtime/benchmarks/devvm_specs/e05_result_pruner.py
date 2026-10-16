"""E-05 (coder extension "prune old tool results", 2026-10-10): long old tool results (a file read 20 calls ago, a long test output) are sent again with every request and fill the
32k window until compaction at 60 % cuts everything at once (compact_history). `result_pruner.py` shortens them earlier and by rule, without a model: an older result that a later call
returned again word for word becomes a one-line note, and long results outside the last few keep head and tail. Unchanged messages stay the SAME objects (prompt cache, like stub_writes).
Ideas from deepseek-harness (compaction-tool-result-pruner) and Hermes (read dedup). Pure function, no file access. GUPPI builds it, Claude only wrote this file and the hidden tests.
Plan: <projekte>\\Guppy\\ERWEITERUNGSPLAN_CODER_2026-10-10.md."""

NOTES = '''# Notes for result_pruner
Pure Python 3 standard library, no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
`messages` is an OpenAI chat history: a list of dicts with "role" ("system", "user", "assistant", "tool") and "content"; tool messages also have "tool_call_id".
'''

COMMON = r'''
import copy
from result_pruner import prune

def tool(i, text):
    return {"role": "tool", "tool_call_id": f"c{i}", "content": text}
LONG = "\n".join(f"line {n}" for n in range(1, 101))
BODY
print("ok")
'''


def hidden(body):
    return COMMON.replace("BODY", body)


C1 = r"""
sysm, task = {"role": "system", "content": "s"}, {"role": "user", "content": "t"}
msgs = [sysm, task, {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]}, tool(1, LONG)] + [tool(i, f"short {i}") for i in range(2, 8)]
snap = copy.deepcopy(msgs)
out = prune(msgs)
assert msgs == snap and out is not msgs and len(out) == len(msgs)
assert all(out[i] is msgs[i] for i in range(len(msgs)) if i != 3)
cut = out[3]["content"].split("\n")
assert cut[:20] == [f"line {n}" for n in range(1, 21)]
assert cut[20] == "[... 70 lines cut: read the file again if you need them ...]"
assert cut[21:] == [f"line {n}" for n in range(91, 101)] and len(cut) == 31
assert out[3]["tool_call_id"] == "c1" and out[3]["role"] == "tool"
recent = [sysm, task, tool(1, LONG)] + [tool(i, "x") for i in range(2, 7)]
r = prune(recent)
assert r[2] is recent[2]
assert prune(recent, keep_last=5)[2]["content"] != LONG
small = "\n".join(f"l{n}" for n in range(40))
s = [tool(1, small)] + [tool(i, "x") for i in range(2, 9)]
assert prune(s)[0] is s[0]
s41 = [tool(1, small + "\nl40")] + [tool(i, "x") for i in range(2, 9)]
assert prune(s41)[0]["content"] != s41[0]["content"]
p = [tool(1, LONG)] + [tool(i, "x") for i in range(2, 9)]
c = prune(p, max_lines=10)[0]["content"].split("\n")
assert c[:5] == ["line 1", "line 2", "line 3", "line 4", "line 5"] and c[5] == "[... 93 lines cut: read the file again if you need them ...]" and c[6:] == ["line 99", "line 100"]
assert prune([]) == []
L30 = "\n".join(f"m{n}" for n in range(30))
q = [tool(1, L30)] + [tool(i, "x") for i in range(2, 9)]
assert prune(q, max_lines=10)[0]["content"].split("\n")[5] == "[... 23 lines cut: read the file again if you need them ...]"
L50 = "\n".join(f"m{n}" for n in range(50))
w = [tool(1, L50)] + [tool(i, "x") for i in range(2, 9)]
assert prune(w, max_lines=100)[0] is w[0]
for bad in ({"keep_last": -1}, {"keep_last": True}, {"max_lines": 3}, {"max_lines": "40"}):
    try:
        prune(msgs, **bad)
        raise AssertionError(bad)
    except ValueError:
        pass
odd = [{"role": "tool", "tool_call_id": "c1", "content": None}, {"role": "assistant", "content": LONG}] + [tool(i, "x") for i in range(2, 9)]
o = prune(odd)
assert o[0] is odd[0] and o[1] is odd[1]
"""

C2 = r"""
FILE = "def f():\n    return 1\n" * 20
msgs = [tool(1, FILE), tool(2, "short"), tool(3, FILE), tool(4, "x")]
snap = copy.deepcopy(msgs)
out = prune(msgs, keep_last=10)
assert msgs == snap
assert out[0]["content"] == "[same result as a later call]" and out[0]["tool_call_id"] == "c1"
assert out[1] is msgs[1] and out[2] is msgs[2] and out[3] is msgs[3]
tiny = [tool(1, "ok"), tool(2, "ok")]
t = prune(tiny, keep_last=10)
assert t[0] is tiny[0] and t[1] is tiny[1]
b201 = "y" * 201
b200 = "z" * 200
assert prune([tool(1, b201), tool(2, b201)], keep_last=10)[0]["content"] == "[same result as a later call]"
assert prune([tool(1, b200), tool(2, b200)], keep_last=10)[0] == tool(1, b200)
three = [tool(1, FILE), tool(2, FILE), tool(3, FILE)]
th = prune(three, keep_last=10)
assert [m["content"] for m in th] == ["[same result as a later call]", "[same result as a later call]", FILE]
both = [tool(1, LONG), tool(2, LONG)] + [tool(i, "x") for i in range(3, 10)]
bo = prune(both)
assert bo[0]["content"] == "[same result as a later call]"
assert bo[1]["content"].split("\n")[20] == "[... 70 lines cut: read the file again if you need them ...]"
assistant_same = [{"role": "assistant", "content": FILE}, {"role": "assistant", "content": FILE}]
a = prune(assistant_same, keep_last=10)
assert a[0] is assistant_same[0]
"""

STYLE = " No comments and no docstrings. Never modify the arguments (also not the message dicts). Put repeated checks into small private helpers."

STAGES = [
    {"name": "cut",
     "task": """Create `result_pruner.py` (Python 3 standard library only) with `prune(messages, keep_last=6, max_lines=40) -> list`: a shortened copy of an OpenAI chat history (a new list; `messages` and its dicts are never changed).
`keep_last` must be an int >= 0, `max_lines` an int >= 4 (a bool is not an int), otherwise ValueError.
Only TOOL messages (role "tool") with a str content are shortened, and only those that are NOT among the last `keep_last` tool messages of the history. Such a message whose content has more than max_lines lines (split on "\\n") becomes a copy of the message (all other keys kept) whose content is: the first max_lines // 2 lines, then the line "[... <k> lines cut: read the file again if you need them ...]", then the last max_lines // 4 lines, joined with "\\n" (k = the number of lines left out).
Every message that is not changed must be the SAME object in the result (the start of the history stays identical for the prompt cache of the server).""" + STYLE + """ Add `tests/test_result_pruner.py` (unittest) with your own tests.""",
     "hidden": {"hidden_e05_1.py": hidden(C1)}},
    {"name": "dedup",
     "task": """In the existing `result_pruner.py` extend `prune`: BEFORE cutting, every tool message whose content is a str of more than 200 characters and is exactly equal to the content of a LATER tool message becomes a copy with the content "[same result as a later call]" (all other keys kept). This applies to all tool messages, also within the last keep_last ones; the latest of equal results stays. Messages of other roles are never touched. Then the cutting rule works on the result as before (a replaced message is short and is not cut again). Unchanged messages stay the same objects.""" + STYLE + """ Add tests to `tests/test_result_pruner.py`.""",
     "hidden": {"hidden_e05_2.py": hidden(C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_result_pruner.py` and read `result_pruner.py` once more. Make sure no check is copied into several places, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_e05_full.py": hidden(C1 + C2)}},
]
