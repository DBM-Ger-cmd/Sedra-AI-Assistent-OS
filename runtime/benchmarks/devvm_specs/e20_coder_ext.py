"""E-20 (coder extensions, ONE integration layer, Captain 2026-10-10 "build separately, integrate together"): `coder_ext.py` holds `CoderExtensions`, the single object the core
talks to. It switches the accepted modules on and off and offers exactly the hook calls of the three hook points: before a tool call (E-01), after a tool call (E-01, E-08, E-09, E-07),
after every model answer (E-02, E-03, E-04, E-05). The module stays PURE: the core passes file texts and answers in and applies what comes back (the ~20 lines in devvm_tools /
model_tools / devvm_agents and the `--coder-ext` flag are a separate step after acceptance, with the Captain's approval).

Seed: the workspace starts with the ACCEPTED modules (read_tracker, fuzzy_edit, replay_log, think_guard, no_call_monitor, syntax_note, result_pruner, tool_cards) and Claude's
data file coder_cards.py (folder benchmarks/devvm_seeds/coder_ext/, put together after acceptance). GUPPI builds coder_ext.py, Claude only wrote this file, coder_cards.py and the hidden tests.
Plan: <projekte>\\Guppy\\ERWEITERUNGSPLAN_CODER_2026-10-10.md."""

NOTES = '''# Notes for coder_ext
Pure Python 3 standard library plus the modules that are already in the workspace (read them, do not change them): read_tracker.py (ReadTracker), fuzzy_edit.py (apply),
replay_log.py (Recorder, Player), think_guard.py (ThinkGuard), no_call_monitor.py (NoCallMonitor), syntax_note.py (note), result_pruner.py (prune), tool_cards.py (CardPicker)
and coder_cards.py (RULES, CARDS). No file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
A tool name is one of read_file, write_file, append_file, edit_file, delete_file, move_file, ...; `args` is the dict of arguments of the call (paths already cleaned).
'''

COMMON = r'''
import copy
from coder_ext import IMPORTS

L = "".join(f"x{i} = {i}\n" for i in range(1, 301))
A = "a = 1\nb = 2\n"
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r"""
from coder_cards import CARDS
NO = {"refuse": None, "note": None}
assert ALL == ("e01", "e02", "e03", "e04", "e05", "e07", "e08", "e09")
assert parse_enabled("all") == frozenset(ALL) and parse_enabled(" E01, e08 ,,") == frozenset({"e01", "e08"})
assert parse_enabled("") == frozenset() and parse_enabled(None) == frozenset() and parse_enabled("none") == frozenset()
try:
    parse_enabled("e01,e99")
    raise AssertionError("must raise")
except ValueError as exc:
    assert "e99" in str(exc)
assert shown_range(L, None, None) == (1, 150) and shown_range(L, 151, None) == (151, 300) and shown_range(L, 100, 120) == (100, 120)
assert shown_range(L, 290, 400) == (290, 300) and shown_range(L, 0, 10) == (1, 10) and shown_range(L, 1, 500) == (1, 150)
assert shown_range(A, None, None) == (1, 2) and shown_range(A, 1, 1) == (1, 1) and shown_range(L, True, 5) == (1, 5)
off = CoderExtensions("")
assert off.enabled == frozenset() and not off.is_on("e01")
assert off.before_tool("edit_file", {"path": "a.py", "old": "a", "new": "b"}, A) == NO
assert off.after_tool("edit_file", {"path": "a.py"}, False, "error: old was not found.", A) == ""
assert off.edit_fallback(A, "a  = 1", "a = 9") is None
x = CoderExtensions("e01")
assert x.before_tool("edit_file", {"path": "a.py", "old": "a = 1", "new": "a = 2"}, A) == {"refuse": 'edit_file refused: you have not read a.py in this run. Read it first with read_file {"path": "a.py"}, then copy old exactly from what you read.', "note": None}
assert x.before_tool("append_file", {"path": "a.py", "content": "c = 3\n"}, A)["refuse"].startswith("append_file refused: you have not read a.py")
assert x.before_tool("edit_file", {"path": "new.py", "old": "a", "new": "b"}, None) == NO
assert x.before_tool("write_file", {"path": "new.py", "content": A}, None) == NO
assert x.before_tool("write_file", {"path": "a.py", "content": A}, A) == {"refuse": "write_file refused: a.py exists and you have not read it. Read it with read_file first, or change it with edit_file.", "note": None}
assert x.after_tool("read_file", {"path": "a.py"}, True, A, A) == ""
assert x.before_tool("edit_file", {"path": "a.py", "old": "a = 1", "new": "a = 2"}, A) == NO
assert x.before_tool("write_file", {"path": "a.py", "content": "z = 0\n"}, A) == NO
B = "a = 5\nb = 2\n"
assert x.before_tool("edit_file", {"path": "a.py", "old": "b = 2", "new": "b = 3"}, B) == {"refuse": None, "note": "(note: a.py changed since you last read it; the edit was applied because old still matched)"}
assert x.before_tool("write_file", {"path": "a.py", "content": "z"}, B)["refuse"] == "write_file refused: a.py changed since you read it. Read it again first."
x.after_tool("read_file", {"path": "big.py"}, True, "[lines 1-150 of 300 ...]", L)
assert x.before_tool("write_file", {"path": "big.py", "content": "z"}, L)["refuse"] == "write_file refused: you have only seen lines 1-150 of big.py (300 lines). Read the rest first, or change it with edit_file."
x.after_tool("read_file", {"path": "big.py", "start": 200, "end": 210}, True, "...", L)
assert x.before_tool("write_file", {"path": "big.py", "content": "z"}, L)["refuse"] == "write_file refused: you have only seen lines 1-150, 200-210 of big.py (300 lines). Read the rest first, or change it with edit_file."
x.after_tool("read_file", {"path": "big.py", "start": 151}, True, "...", L)
assert x.before_tool("write_file", {"path": "big.py", "content": "z"}, L) == NO
x.after_tool("write_file", {"path": "w.py", "content": A}, True, "created w.py", A)
assert x.before_tool("edit_file", {"path": "w.py", "old": "a", "new": "b"}, A) == NO
x.after_tool("edit_file", {"path": "w.py", "old": "a = 1", "new": "a = 7"}, True, "edited w.py", "a = 7\nb = 2\n")
assert x.before_tool("edit_file", {"path": "w.py", "old": "b = 2", "new": "b = 8"}, "a = 7\nb = 2\n") == NO
x.after_tool("move_file", {"source": "w.py", "destination": "v.py"}, True, "moved", None)
assert x.before_tool("edit_file", {"path": "v.py", "old": "b", "new": "c"}, "a = 7\nb = 2\n") == NO
assert x.before_tool("edit_file", {"path": "w.py", "old": "b", "new": "c"}, "a = 7\nb = 2\n")["refuse"] is not None
x.after_tool("delete_file", {"path": "v.py"}, True, "deleted v.py", None)
assert x.before_tool("edit_file", {"path": "v.py", "old": "b", "new": "c"}, "a = 7\nb = 2\n")["refuse"] is not None
x.after_tool("read_file", {"path": "q.py"}, False, "error: file_not_found", None)
assert x.before_tool("edit_file", {"path": "q.py", "old": "b", "new": "c"}, A)["refuse"] is not None
assert x.before_tool("list_dir", {}, None) == NO and x.before_tool("edit_file", "junk", A) == NO and x.before_tool("edit_file", {"path": 5}, A) == NO
f = CoderExtensions("e08")
T = "def f(x):\n    if x:\n        return 1\n"
assert f.edit_fallback(T, "if x:\n    return 1", "if x:\n    return 2") == {"text": "def f(x):\n    if x:\n        return 2\n", "strategy": "indentation"}
assert f.edit_fallback(T, "return 9", "x") is None and f.edit_fallback(T, "x", "x") is None
s = CoderExtensions("e09")
assert s.after_tool("write_file", {"path": "a.py", "content": "def f(:\n"}, True, "created a.py", "def f(:\n").startswith("syntax error in a.py line 1: ")
assert s.after_tool("edit_file", {"path": "a.py"}, True, "edited a.py", "x = 1\n") == ""
assert s.after_tool("read_file", {"path": "a.py"}, True, "def f(:\n", "def f(:\n") == ""
assert s.after_tool("write_file", {"path": "a.py"}, False, "error: too long", "def f(:\n") == ""
c = CoderExtensions("e07")
assert c.after_tool("edit_file", {"path": "a.py"}, False, "error: old was not found. The most similar ...", A) == CARDS["edit_not_found"]
assert c.after_tool("edit_file", {"path": "a.py"}, False, "error: old was not found.", A) == ""
assert c.after_tool("move_file", {}, False, "error: source is required", None) == CARDS["missing_arg"]
assert c.after_tool("edit_file", {"path": "a.py"}, True, "edited a.py", A) == ""
own = CoderExtensions("e07", cards={"k": "MY CARD"}, rules=[("edit_file", "boom", "k")])
assert own.after_tool("edit_file", {}, False, "error: boom", None) == "MY CARD"
both = CoderExtensions("e09,e07")
assert both.after_tool("write_file", {"path": "a.py"}, True, "created", "def f(:\n").count("\n") >= 1
args = {"path": "a.py", "old": "a", "new": "b"}
snap = copy.deepcopy(args)
CoderExtensions("all").before_tool("edit_file", args, A)
assert args == snap
"""

C2 = r"""
def ans(content="", calls=None, reasoning_tokens=None):
    msg = {"role": "assistant", "content": content}
    if calls is not None:
        msg["tool_calls"] = calls
    usage = {"prompt_tokens": 10}
    if reasoning_tokens is not None:
        usage["completion_tokens_details"] = {"reasoning_tokens": reasoning_tokens}
    return {"choices": [{"message": msg, "finish_reason": "stop"}], "usage": usage}
CALL = [{"id": "1", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]
off = CoderExtensions("")
assert off.after_answer(ans(calls=CALL), True) == {"notes": [], "action": "continue", "calls": []}
assert off.after_answer(ans("done"), False) == {"notes": [], "action": "stop", "calls": []}
assert off.request_patch() == {}
t = CoderExtensions("e02", think_limit=100, family="qwen")
assert t.after_answer(ans(calls=CALL, reasoning_tokens=500), True) == {"notes": ["You thought for 500 tokens. Stop deliberating: decide now and make the next tool call."], "action": "continue", "calls": []}
assert t.request_patch() == {}
assert t.after_answer(ans(calls=CALL, reasoning_tokens=500), True)["notes"] == []
assert t.request_patch() == {"chat_template_kwargs": {"enable_thinking": False}}
m = CoderExtensions("e03", tool_names=("read_file", "submit_result"), max_corrections=1, terminal="submit_result")
assert m.after_answer(ans(calls=CALL), True)["action"] == "continue"
r = m.after_answer(ans('```json\n{"name": "read_file", "arguments": {"path": "a.py"}}\n```'), False)
assert r == {"notes": [], "action": "run", "calls": [("read_file", {"path": "a.py"})]}
r = m.after_answer(ans(""), False)
assert r == {"notes": ["Your answer was empty. Continue the task: make the next tool call."], "action": "correct", "calls": []}
assert m.after_answer(ans("I am done."), False) == {"notes": [], "action": "stop", "calls": []}
both = CoderExtensions("e02,e03", think_limit=10, tool_names=("read_file",))
r = both.after_answer(ans("", reasoning_tokens=50), False)
assert r["action"] == "correct" and r["notes"] == ["You thought for 50 tokens. Stop deliberating: decide now and make the next tool call.", "Your answer was empty. Continue the task: make the next tool call."]
assert off.after_answer(None, False) == {"notes": [], "action": "stop", "calls": []}
assert m.after_answer({"choices": []}, False)["action"] in ("correct", "stop")
LONG = "\n".join(f"line {n}" for n in range(100))
msgs = [{"role": "tool", "tool_call_id": f"c{i}", "content": LONG if i == 0 else "x"} for i in range(9)]
p = CoderExtensions("e05", prune_at=0.5, window=1000)
assert p.prune(msgs, 400) is msgs
pr = p.prune(msgs, 600)
assert pr is not msgs and pr[0]["content"] != LONG and pr[1] is msgs[1]
assert CoderExtensions("").prune(msgs, 10 ** 9) is msgs
seen = []
def post(body):
    seen.append(body)
    return ans("hi")
assert off.wrap_post(post) is post and CoderExtensions("e04").wrap_post(post) is post
rec = CoderExtensions("e04")
wp = rec.wrap_post(post, mode="record")
assert wp({"model": "m", "messages": []}) == ans("hi") and rec.records() == wp.records and len(rec.records()) == 1
pl = CoderExtensions("e04").wrap_post(None, mode="replay", records=rec.records())
assert pl({"model": "m", "messages": []}) == ans("hi")
assert off.wrap_post(post, mode="record") is post and off.records() == []
for bad in ({"mode": "tape"},):
    try:
        CoderExtensions("e04").wrap_post(post, **bad)
        raise AssertionError(bad)
    except ValueError:
        pass
for bad in ({"prune_at": 0}, {"prune_at": 1.5}, {"window": 0}, {"think_limit": 0}, {"family": "x"}, {"max_corrections": -1}):
    try:
        CoderExtensions("all", **bad)
        raise AssertionError(bad)
    except ValueError:
        pass
"""

STYLE = " No comments and no docstrings. Never modify the arguments. Put repeated checks into small private helpers."

_OLD_STAGES = [      # first cut, 2026-10-10: the "tools" stage was too big for one 32k conversation (both attempts failed, runs ended by the turn limit); replaced by STAGES at the end
    {"name": "tools",
     "task": """Create `coder_ext.py` (Python 3 standard library plus the modules already in the workspace, see NOTES.md) with:
- `ALL = ("e01", "e02", "e03", "e04", "e05", "e07", "e08", "e09")` and `parse_enabled(text) -> frozenset`: "all" gives all of ALL; otherwise a comma-separated list, items stripped and lower-cased, empty items ignored; "", None and "none" give frozenset(); an unknown item raises ValueError naming it.
- `shown_range(text, start, end, per_read=150) -> (first, last)`: the lines read_file actually shows (same rule as the toolbox): n = len(text.splitlines()); if n <= per_read and start and end are both None: (1, n). Otherwise (start/end that are not an int count as None, a bool is not an int) first = max(1, start) or 1, last = min(n, end or first + per_read - 1, first + per_read - 1).
- class `CoderExtensions(enabled="", think_limit=2000, family="qwen", max_corrections=2, terminal="submit_result", tool_names=(), prune_at=0.5, window=32768, cards=None, rules=None)`: attribute `enabled` = parse_enabled(enabled), `is_on(key)`. It creates a ReadTracker when e01 is on and a CardPicker(cards or coder_cards.CARDS, rules or coder_cards.RULES) when e07 is on (the other parameters are for the next stage; store them).
- `before_tool(name, args, current) -> {"refuse": str or None, "note": str or None}` with current = the text of the file args["path"] right now, None when it does not exist. Only with e01 on, args a dict and args["path"] a str, otherwise {"refuse": None, "note": None}:
  edit_file / append_file on an existing file: tracker.check_edit -> "unread": refuse "<name> refused: you have not read <path> in this run. Read it first with read_file {"path": "<path>"}, then copy old exactly from what you read."; "changed": note "(note: <path> changed since you last read it; the edit was applied because old still matched)".
  write_file on an existing file: tracker.check_overwrite -> "unread": "write_file refused: <path> exists and you have not read it. Read it with read_file first, or change it with edit_file."; "changed": "write_file refused: <path> changed since you read it. Read it again first."; "partial": "write_file refused: you have only seen lines <ranges> of <path> (<n> lines). Read the rest first, or change it with edit_file." with ranges = tracker.seen as "a-b" joined by ", " ("none" when empty) and n = lines of current.
- `edit_fallback(text, old, new) -> dict or None`: with e08 on, fuzzy_edit.apply(text, old, new) when it returns a "text"; otherwise None.
- `after_tool(name, args, ok, result, current) -> str` with current = the text of the file after the call (None when missing): the text to append to the tool result ("" for nothing), parts joined with "\\n". With e01 on and ok: read_file -> note_read(path, current, *shown_range(current, args.get("start"), args.get("end"))); write_file / append_file -> note_write; edit_file -> note_edit; delete_file -> forget(path); move_file -> move(source, destination). With e09 on, ok and name in write_file / append_file / edit_file: syntax_note.note(path, current) when not None. With e07 on and not ok: the CardPicker card for (name, result) when not None. Wrong argument types never raise.""" + STYLE + """ Add `tests/test_coder_ext.py` (unittest) with your own tests.""",
     "hidden": {"hidden_e20_1.py": hidden("ALL, parse_enabled, shown_range, CoderExtensions", C1)}},
    {"name": "answers",
     "task": """In the existing `coder_ext.py` (keep everything) the CoderExtensions constructor checks its parameters (ValueError): think_limit int > 0, family one of "qwen", "gptoss", "other", max_corrections int >= 0 (a bool is not an int), 0 < prune_at < 1, window int > 0. It creates a ThinkGuard(think_limit, family) when e02 is on and a NoCallMonitor(tool_names, max_corrections, terminal) when e03 is on. Add:
- `after_answer(data, has_calls) -> {"notes": list of str, "action": str, "calls": list}` for one parsed model answer `data` (any part may be missing; never raises): with e02 on, think.feed(data); its "note" text goes into notes. Then: has_calls true -> action "continue", calls []. Else with e03 on: monitor.feed(the first choice's message, {} when missing) -> action and calls from it, its text (when not None) appended to notes. Else (e03 off) action "stop", calls [].
- `request_patch() -> dict`: think.patch() with e02 on, else {}.
- `prune(messages, prompt_tokens) -> list`: with e05 on and prompt_tokens > prune_at * window: result_pruner.prune(messages); otherwise the SAME list object.
- `wrap_post(post, mode=None, records=None)`: mode None, or e04 off: `post` itself. With e04 on: "record" -> a replay_log.Recorder(post) (remember it), "replay" -> replay_log.Player(records or []). With e04 on, any other mode raises ValueError.
- `records() -> list`: the records of the remembered Recorder ([] when there is none).""" + STYLE + """ Add tests to `tests/test_coder_ext.py`.""",
     "hidden": {"hidden_e20_2.py": hidden("ALL, parse_enabled, shown_range, CoderExtensions", C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_coder_ext.py` and read `coder_ext.py` once more. Do not change the other modules. Make sure no check is copied into several places, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_e20_full.py": hidden("ALL, parse_enabled, shown_range, CoderExtensions", C1 + C2)}},
]


C1A = r"""
NO = {"refuse": None, "note": None}
assert ALL == ("e01", "e02", "e03", "e04", "e05", "e07", "e08", "e09")
assert parse_enabled("all") == frozenset(ALL) and parse_enabled(" E01, e08 ,,") == frozenset({"e01", "e08"})
assert parse_enabled("") == frozenset() and parse_enabled(None) == frozenset() and parse_enabled("none") == frozenset()
try:
    parse_enabled("e01,e99")
    raise AssertionError("must raise")
except ValueError as exc:
    assert "e99" in str(exc)
assert shown_range(L, None, None) == (1, 150) and shown_range(L, 151, None) == (151, 300) and shown_range(L, 100, 120) == (100, 120)
assert shown_range(L, 290, 400) == (290, 300) and shown_range(L, 0, 10) == (1, 10) and shown_range(L, 1, 500) == (1, 150)
assert shown_range(A, None, None) == (1, 2) and shown_range(A, 1, 1) == (1, 1) and shown_range(L, True, 5) == (1, 5)
off = CoderExtensions("")
assert off.enabled == frozenset() and not off.is_on("e01") and off.tracker is None and off.cards is None
on = CoderExtensions("e01,e07")
assert on.is_on("e01") and on.is_on("e07") and not on.is_on("e08")
from read_tracker import ReadTracker
from tool_cards import CardPicker
assert isinstance(on.tracker, ReadTracker) and isinstance(on.cards, CardPicker)
assert CoderExtensions("e08").tracker is None
"""

C1B = r"""
x = CoderExtensions("e01")
assert x.before_tool("edit_file", {"path": "a.py", "old": "a = 1", "new": "a = 2"}, A) == {"refuse": 'edit_file refused: you have not read a.py in this run. Read it first with read_file {"path": "a.py"}, then copy old exactly from what you read.', "note": None}
assert x.before_tool("append_file", {"path": "a.py", "content": "c = 3\n"}, A)["refuse"].startswith("append_file refused: you have not read a.py")
assert x.before_tool("edit_file", {"path": "new.py", "old": "a", "new": "b"}, None) == NO
assert x.before_tool("write_file", {"path": "new.py", "content": A}, None) == NO
assert x.before_tool("write_file", {"path": "a.py", "content": A}, A) == {"refuse": "write_file refused: a.py exists and you have not read it. Read it with read_file first, or change it with edit_file.", "note": None}
x.tracker.note_read("a.py", A)
assert x.before_tool("edit_file", {"path": "a.py", "old": "a = 1", "new": "a = 2"}, A) == NO
assert x.before_tool("write_file", {"path": "a.py", "content": "z = 0\n"}, A) == NO
B = "a = 5\nb = 2\n"
assert x.before_tool("edit_file", {"path": "a.py", "old": "b = 2", "new": "b = 3"}, B) == {"refuse": None, "note": "(note: a.py changed since you last read it; the edit was applied because old still matched)"}
assert x.before_tool("write_file", {"path": "a.py", "content": "z"}, B)["refuse"] == "write_file refused: a.py changed since you read it. Read it again first."
x.tracker.note_read("big.py", L, 1, 150)
assert x.before_tool("write_file", {"path": "big.py", "content": "z"}, L)["refuse"] == "write_file refused: you have only seen lines 1-150 of big.py (300 lines). Read the rest first, or change it with edit_file."
x.tracker.note_read("big.py", L, 200, 210)
assert x.before_tool("write_file", {"path": "big.py", "content": "z"}, L)["refuse"] == "write_file refused: you have only seen lines 1-150, 200-210 of big.py (300 lines). Read the rest first, or change it with edit_file."
assert x.before_tool("list_dir", {}, None) == NO and x.before_tool("edit_file", "junk", A) == NO and x.before_tool("edit_file", {"path": 5}, A) == NO
x.tracker.note_read("p.py", L, 10, 5)
assert x.before_tool("write_file", {"path": "p.py", "content": "z"}, L)["refuse"] == "write_file refused: you have only seen lines none of p.py (300 lines). Read the rest first, or change it with edit_file."
assert CoderExtensions("").before_tool("edit_file", {"path": "a.py", "old": "a", "new": "b"}, A) == NO
f = CoderExtensions("e08")
T = "def f(x):\n    if x:\n        return 1\n"
assert f.edit_fallback(T, "if x:\n    return 1", "if x:\n    return 2") == {"text": "def f(x):\n    if x:\n        return 2\n", "strategy": "indentation"}
assert f.edit_fallback(T, "return 9", "x") is None and f.edit_fallback(T, "x", "x") is None
assert CoderExtensions("").edit_fallback(T, "if x:\n    return 1", "if x:\n    return 2") is None
"""

SIZE = " Keep coder_ext.py small (about 150 lines in the end): methods directly on the class, no module-level copies of them, call the modules instead of re-implementing them."

STAGES = [
    {"name": "config",
     "task": """Create `coder_ext.py` (Python 3 standard library plus the modules already in the workspace, see NOTES.md; read only the parts of them you need) with:
- `ALL = ("e01", "e02", "e03", "e04", "e05", "e07", "e08", "e09")` and `parse_enabled(text) -> frozenset`: "all" gives all of ALL; otherwise a comma-separated list, items stripped and lower-cased, empty items ignored; "", None and "none" give frozenset(); an unknown item raises ValueError naming it.
- `shown_range(text, start, end, per_read=150) -> (first, last)`: the lines read_file shows. n = len(text.splitlines()); if n <= per_read and start and end are both None: (1, n). Otherwise (start/end that are not an int count as None, a bool is not an int) first = max(1, start) or 1 when start is None, last = min(n, end (or first + per_read - 1 when None), first + per_read - 1).
- class `CoderExtensions(enabled="", think_limit=2000, family="qwen", max_corrections=2, terminal="submit_result", tool_names=(), prune_at=0.5, window=32768, cards=None, rules=None)`: attribute `enabled` = parse_enabled(enabled); method `is_on(key)`; attribute `tracker` = read_tracker.ReadTracker() when e01 is on, else None; attribute `cards` = tool_cards.CardPicker(cards or coder_cards.CARDS, rules or coder_cards.RULES) when e07 is on, else None. Store the other parameters as attributes of the same name (later stages use them).""" + STYLE + SIZE + """ Add `tests/test_coder_ext.py` (unittest) with your own tests.""",
     "hidden": {"hidden_e20_a.py": hidden("ALL, parse_enabled, shown_range, CoderExtensions", C1A)}},
    {"name": "before",
     "task": """In the existing `coder_ext.py` add two methods to CoderExtensions (keep everything):
- `before_tool(name, args, current) -> {"refuse": str or None, "note": str or None}`; `current` = the text of the file args["path"] right now, None when it does not exist. Return {"refuse": None, "note": None} unless e01 is on, args is a dict, args["path"] is a str and current is not None. Then:
  * name "edit_file" or "append_file": v = self.tracker.check_edit(path, current). v "unread": refuse = "<name> refused: you have not read <path> in this run. Read it first with read_file {"path": "<path>"}, then copy old exactly from what you read." v "changed": note = "(note: <path> changed since you last read it; the edit was applied because old still matched)".
  * name "write_file": v = self.tracker.check_overwrite(path, current). "unread": refuse = "write_file refused: <path> exists and you have not read it. Read it with read_file first, or change it with edit_file."; "changed": "write_file refused: <path> changed since you read it. Read it again first."; "partial": "write_file refused: you have only seen lines <ranges> of <path> (<n> lines). Read the rest first, or change it with edit_file." where ranges = self.tracker.seen(path) written as "a-b" joined by ", " ("none" when empty) and n = len(current.splitlines()).
  * any other name: nothing.
- `edit_fallback(text, old, new) -> dict or None`: when e08 is on and fuzzy_edit.apply(text, old, new) returns a dict with "text", return that dict; otherwise None.""" + STYLE + SIZE + """ Add tests to `tests/test_coder_ext.py`.""",
     "hidden": {"hidden_e20_b.py": hidden("ALL, parse_enabled, shown_range, CoderExtensions", C1A + C1B)}},
    {"name": "after",
     "task": """In the existing `coder_ext.py` add one method to CoderExtensions (keep everything):
`after_tool(name, args, ok, result, current) -> str`: the EXTRA text the toolbox appends to the tool result `result` ("" for nothing). It NEVER contains `result` itself. `current` = the text of the file after the call (None when it does not exist); args that is not a dict counts as {}; wrong types never raise. Collect parts in this order and join them with "\\n":
1. bookkeeping, only with e01 on and ok true (no part is added): "read_file" with current a str: self.tracker.note_read(path, current, *shown_range(current, args.get("start"), args.get("end"))); "write_file" or "append_file": self.tracker.note_write(path, current); "edit_file": self.tracker.note_edit(path, current); "delete_file": self.tracker.forget(path); "move_file": self.tracker.move(args.get("source"), args.get("destination")).
2. with e09 on, ok true and name in write_file / append_file / edit_file: syntax_note.note(path, current) when it is not None.
3. with e07 on and ok false: self.cards.after(name, result) when it is not None.""" + STYLE + SIZE + """ Add tests to `tests/test_coder_ext.py`.""",
     "hidden": {"hidden_e20_c.py": hidden("ALL, parse_enabled, shown_range, CoderExtensions", C1)}},
    _OLD_STAGES[1],
    {**_OLD_STAGES[2], "hidden": {"hidden_e20_full.py": hidden("ALL, parse_enabled, shown_range, CoderExtensions", C1A + C1B + C1 + C2)}},
]
