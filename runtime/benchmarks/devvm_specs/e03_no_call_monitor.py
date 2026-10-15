"""E-03 (coder extension "answers without a tool call", 2026-10-10): today an answer without a native tool call ends a DevVM run at once (stopped_by no_tool_call), although the model
often only wrote the call as JSON text, answered empty, emitted garbage (Gemma <unused49>) or only thought. `no_call_monitor.py` classifies such an answer, extracts tool calls written
as JSON text, and gives up to N correction messages before the run really stops. Repetition inside an answer is NOT part of it (RunawayGuard exists), nor <tool_call> tags
(model_tools.parse_calls reads them). Ideas from little-coder (quality-monitor, output-parser) and Hermes (empty_response_guard). Pure functions and one class, no file access.
GUPPI builds it, Claude only wrote this file and the hidden tests. Plan: <projekte>\\Guppy\\ERWEITERUNGSPLAN_CODER_2026-10-10.md."""

NOTES = '''# Notes for no_call_monitor
Pure Python 3 standard library (json, re), no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
A message is the assistant message of an OpenAI-compatible chat answer: {"content": str or None, "reasoning_content": str (optional), "tool_calls": list (optional)}.
'''

COMMON = r'''
import copy
from no_call_monitor import IMPORTS

TOOLS = ("read_file", "edit_file", "submit_result")
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r"""
fenced = 'I will read it.\n```json\n{"name": "read_file", "arguments": {"path": "a.py"}}\n```\n'
assert extract_calls(fenced, TOOLS) == [("read_file", {"path": "a.py"})]
assert extract_calls('```\n{"name": "edit_file", "parameters": {"path": "a.py", "old": "x", "new": "y"}}\n```', TOOLS) == [("edit_file", {"path": "a.py", "old": "x", "new": "y"})]
assert extract_calls('  {"name": "submit_result"}  ', TOOLS) == [("submit_result", {})]
two = '```json\n[{"name": "read_file", "arguments": {"path": "a.py"}}, {"name": "read_file", "arguments": {"path": "b.py"}}]\n```'
assert extract_calls(two, TOOLS) == [("read_file", {"path": "a.py"}), ("read_file", {"path": "b.py"})]
both = '```json\n{"name": "read_file", "arguments": {"path": "a.py"}}\n```\nthen\n```json\n{"name": "submit_result", "arguments": {"summary": "s"}}\n```'
assert extract_calls(both, TOOLS) == [("read_file", {"path": "a.py"}), ("submit_result", {"summary": "s"})]
assert extract_calls('```json\n{"name": "rm_rf", "arguments": {}}\n```', TOOLS) == []
assert extract_calls('```json\n{"name": "read_file", "arguments": "a.py"}\n```', TOOLS) == []
assert extract_calls('```json\n{broken\n```', TOOLS) == []
assert extract_calls('```python\nprint(1)\n```', TOOLS) == []
assert extract_calls("I am done.", TOOLS) == [] and extract_calls(None, TOOLS) == [] and extract_calls("", TOOLS) == []
assert extract_calls('```json\n{"name": "read_file", "arguments": {"path": "a.py"}}\n```', ()) == []
assert classify({"content": "", "tool_calls": [{"id": "1"}]}, TOOLS) == "call"
assert classify({"content": "", "tool_calls": []}, TOOLS) == "empty"
assert classify({"content": None}, TOOLS) == "empty" and classify({"content": "  \n "}, TOOLS) == "empty" and classify({}, TOOLS) == "empty" and classify(None, TOOLS) == "empty"
assert classify({"content": "", "reasoning_content": "let me think"}, TOOLS) == "thinking_only"
assert classify({"content": "<unused49><unused49>"}, TOOLS) == "garbage"
assert classify({"content": "ok so <unused12> here"}, TOOLS) == "garbage"
assert classify({"content": fenced}, TOOLS) == "text_call"
assert classify({"content": "The function is finished."}, TOOLS) == "prose"
m = {"content": fenced, "tool_calls": []}
snap = copy.deepcopy(m)
classify(m, TOOLS)
assert m == snap
"""

C2 = r"""
CONT = {"kind": "call", "action": "continue", "calls": [], "text": None}
mon = NoCallMonitor(TOOLS)
assert mon.max_corrections == 2 and mon.terminal == "submit_result"
assert mon.feed({"content": "", "tool_calls": [{"id": "1"}]}) == CONT
r = mon.feed({"content": "", "tool_calls": []})
assert r == {"kind": "empty", "action": "correct", "calls": [], "text": "Your answer was empty. Continue the task: make the next tool call."}
r = mon.feed({"content": "All done, the code works."})
assert r == {"kind": "prose", "action": "correct", "calls": [], "text": "Do not answer in text. Use a tool call: continue the work, or call submit_result when everything is done."}
assert mon.feed({"content": "<unused49>"}) == {"kind": "garbage", "action": "stop", "calls": [], "text": None}
mon2 = NoCallMonitor(TOOLS, max_corrections=1, terminal="submit_plan")
assert mon2.feed({"content": "", "reasoning_content": "hmm"}) == {"kind": "thinking_only", "action": "correct", "calls": [], "text": "You only thought and did not act. Make the next tool call now."}
assert mon2.feed({"content": '```json\n{"name": "read_file", "arguments": {"path": "a.py"}}\n```'}) == {"kind": "text_call", "action": "run", "calls": [("read_file", {"path": "a.py"})], "text": None}
assert mon2.feed({"content": "<unused3>"}) == {"kind": "garbage", "action": "correct", "calls": [], "text": "Your answer was unreadable. Continue the task with a normal tool call."}
assert mon2.feed({"content": "text"})["action"] == "stop"
assert mon2.feed({"content": "", "tool_calls": [{"id": "1"}]}) == CONT
assert mon2.feed({"content": "text"}) == {"kind": "prose", "action": "correct", "calls": [], "text": "Do not answer in text. Use a tool call: continue the work, or call submit_plan when everything is done."}
for bad in ({"max_corrections": -1}, {"max_corrections": True}, {"max_corrections": 1.5}):
    try:
        NoCallMonitor(TOOLS, **bad)
        raise AssertionError(bad)
    except ValueError:
        pass
"""

STYLE = " No comments and no docstrings. Never modify the arguments. Put repeated checks into small private helpers."

STAGES = [
    {"name": "classify",
     "task": """Create `no_call_monitor.py` (Python 3 standard library only) with:
- `extract_calls(content, tool_names) -> list`: tool calls an AI model wrote as JSON TEXT instead of a real tool call, as [(name, arguments_dict)] in the order they appear. Candidates: the body of every Markdown code fence whose language is empty or "json" (```json ... ``` or ``` ... ```); if there is no such fence, the whole content stripped. A candidate is parsed with json.loads (invalid JSON is skipped silently); it may be one object or a list of objects. An object counts when its "name" is one of `tool_names` and its arguments (key "arguments", else key "parameters", missing = {}) are a dict. content that is not a str gives [].
- `classify(message, tool_names) -> str`: "call" when message["tool_calls"] is a non-empty list; otherwise with content = message["content"] (a non-str counts as ""): "garbage" when content contains <unusedN> (N = digits); "text_call" when extract_calls finds at least one call; "empty" when content is empty or only white space and there is no non-blank str "reasoning_content"; "thinking_only" when content is blank but reasoning_content is not; else "prose". A message that is not a dict counts as {}.""" + STYLE + """ Add `tests/test_no_call_monitor.py` (unittest) with your own tests.""",
     "hidden": {"hidden_e03_1.py": hidden("extract_calls, classify", C1)}},
    {"name": "monitor",
     "task": """In the existing `no_call_monitor.py` (keep everything) add a class `NoCallMonitor(tool_names, max_corrections=2, terminal="submit_result")` with the attributes `max_corrections` and `terminal`; max_corrections must be an int >= 0 (a bool is not an int), otherwise ValueError.
`feed(message) -> dict` with the keys "kind" (= classify(message, tool_names)), "action", "calls", "text":
- kind "call": {"action": "continue", "calls": [], "text": None} and the count of corrections in a row starts again at 0;
- kind "text_call": {"action": "run", "calls": extract_calls(content, tool_names), "text": None} (the caller runs these calls) and the count starts again at 0;
- any other kind: if fewer than max_corrections corrections were given in a row, count one and return {"action": "correct", "calls": [], "text": TEXT}; otherwise {"action": "stop", "calls": [], "text": None}.
TEXT per kind: empty = "Your answer was empty. Continue the task: make the next tool call."; garbage = "Your answer was unreadable. Continue the task with a normal tool call."; thinking_only = "You only thought and did not act. Make the next tool call now."; prose = "Do not answer in text. Use a tool call: continue the work, or call <terminal> when everything is done." (with the terminal of this monitor).""" + STYLE + """ Add tests to `tests/test_no_call_monitor.py`.""",
     "hidden": {"hidden_e03_2.py": hidden("extract_calls, classify, NoCallMonitor", C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_no_call_monitor.py` and read `no_call_monitor.py` once more. Make sure no check is copied into several places, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_e03_full.py": hidden("extract_calls, classify, NoCallMonitor", C1 + C2)}},
]
