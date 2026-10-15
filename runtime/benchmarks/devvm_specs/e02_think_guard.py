"""E-02 (coder extension "thinking budget", 2026-10-10): `think_guard.py` measures how many tokens the model spent thinking in each answer and, when it thinks too long, first gives ONE
note to decide now and then switches thinking down for the rest of the run (Qwen: enable_thinking false; gpt-oss: reasoning_effort low). Run time is almost only generation
(memory guppi-solo-workflow), and llama-server cannot cut a non-streamed answer, so the guard acts between answers. Idea from little-coder (thinking-budget). Pure class, no file access.
GUPPI builds it, Claude only wrote this file and the hidden tests. Plan: <projekte>\\Guppy\\ERWEITERUNGSPLAN_CODER_2026-10-10.md."""

NOTES = '''# Notes for think_guard
Pure Python 3 standard library, no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
`data` is the parsed answer of an OpenAI-compatible chat server: {"choices": [{"message": {"content": ..., "reasoning_content": ...}}], "usage": {...}}; any part may be missing or of a wrong type.
'''

COMMON = r'''
import copy
from think_guard import IMPORTS

def ans(reasoning=None, details=None):
    usage = {"prompt_tokens": 10, "completion_tokens": 50}
    if details is not None:
        usage["completion_tokens_details"] = details
    msg = {"role": "assistant", "content": "x"}
    if reasoning is not None:
        msg["reasoning_content"] = reasoning
    return {"choices": [{"message": msg}], "usage": usage}
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r"""
assert reasoning_tokens(ans(details={"reasoning_tokens": 1234})) == 1234
assert reasoning_tokens(ans("a" * 4000, {"reasoning_tokens": 7})) == 7
assert reasoning_tokens(ans("a" * 4001)) == 1000
assert reasoning_tokens(ans("abc")) == 0
assert reasoning_tokens(ans("a" * 400, {"reasoning_tokens": True})) == 100
assert reasoning_tokens(ans("a" * 400, {"reasoning_tokens": -3})) == 100
assert reasoning_tokens(ans("a" * 400, "junk")) == 100
assert reasoning_tokens(ans()) == 0
assert reasoning_tokens(None) == 0 and reasoning_tokens({}) == 0 and reasoning_tokens({"choices": []}) == 0 and reasoning_tokens({"choices": "x", "usage": 5}) == 0
assert reasoning_tokens({"choices": [{"message": {"reasoning_content": 5}}]}) == 0
d = ans("a" * 800, {"reasoning_tokens": 9})
snap = copy.deepcopy(d)
reasoning_tokens(d)
assert d == snap
"""

C2 = r"""
OK = {"action": "ok", "text": None}
g = ThinkGuard(limit=1000, family="qwen")
assert g.feed(ans(details={"reasoning_tokens": 1000})) == OK and g.patch() == {}
first = g.feed(ans(details={"reasoning_tokens": 1500}))
assert first == {"action": "note", "text": "You thought for 1500 tokens. Stop deliberating: decide now and make the next tool call."}
assert g.patch() == {}
assert g.feed(ans(details={"reasoning_tokens": 200})) == OK
assert g.feed(ans(details={"reasoning_tokens": 3000})) == {"action": "think_less", "text": None}
assert g.patch() == {"chat_template_kwargs": {"enable_thinking": False}}
assert g.feed(ans(details={"reasoning_tokens": 5000})) == OK
p = g.patch()
p["chat_template_kwargs"]["enable_thinking"] = True
assert g.patch() == {"chat_template_kwargs": {"enable_thinking": False}}
o = ThinkGuard(limit=10, family="gptoss", max_notes=0)
assert o.feed(ans("a" * 400)) == {"action": "think_less", "text": None} and o.patch() == {"chat_template_kwargs": {"reasoning_effort": "low"}}
x = ThinkGuard(limit=10, family="other", max_notes=2)
assert x.feed(ans("a" * 400))["action"] == "note" and x.feed(ans("a" * 400))["action"] == "note"
assert x.feed(ans("a" * 400)) == {"action": "think_less", "text": None} and x.patch() == {}
assert ThinkGuard().limit == 2000 and ThinkGuard().family == "qwen" and ThinkGuard().max_notes == 1
for bad in ({"limit": 0}, {"limit": -5}, {"limit": True}, {"limit": 2.5}, {"family": "llama"}, {"max_notes": -1}, {"max_notes": True}):
    try:
        ThinkGuard(**bad)
        raise AssertionError(bad)
    except ValueError:
        pass
assert ThinkGuard(limit=5).feed(None) == OK
"""

STYLE = " No comments and no docstrings. Never modify the arguments. Put repeated checks into small private helpers."

STAGES = [
    {"name": "measure",
     "task": """Create `think_guard.py` (Python 3 standard library only) with `reasoning_tokens(data) -> int`: how many tokens the model spent thinking in the answer `data`.
Use data["usage"]["completion_tokens_details"]["reasoning_tokens"] when it is an int >= 0 (a bool is not an int). Otherwise estimate from the first choice: len(data["choices"][0]["message"]["reasoning_content"]) // 4 when that is a str. Otherwise 0.
Any missing part or part of the wrong type (data not a dict, choices not a non-empty list, usage or details not a dict ...) means "not available" and never raises.""" + STYLE + """ Add `tests/test_think_guard.py` (unittest) with your own tests.""",
     "hidden": {"hidden_e02_1.py": hidden("reasoning_tokens", C1)}},
    {"name": "guard",
     "task": """In the existing `think_guard.py` (keep `reasoning_tokens`) add a class `ThinkGuard(limit=2000, family="qwen", max_notes=1)` with the attributes `limit`, `family`, `max_notes`.
`limit` must be an int > 0, `max_notes` an int >= 0 (a bool is not an int), `family` one of "qwen", "gptoss", "other"; otherwise raise ValueError.
`feed(data) -> dict` judges one answer with n = reasoning_tokens(data):
- once the guard has switched to thinking less, every answer gives {"action": "ok", "text": None};
- n <= limit gives {"action": "ok", "text": None};
- n > limit while fewer than max_notes notes were given: count the note and return {"action": "note", "text": "You thought for <n> tokens. Stop deliberating: decide now and make the next tool call."};
- n > limit after that: switch to thinking less and return {"action": "think_less", "text": None}.
`patch() -> dict`: what the caller must add to EVERY following request: {} before the switch; after it {"chat_template_kwargs": {"enable_thinking": False}} for "qwen", {"chat_template_kwargs": {"reasoning_effort": "low"}} for "gptoss", {} for "other". Every call returns a new dict (changing it must not change the guard).""" + STYLE + """ Add tests to `tests/test_think_guard.py`.""",
     "hidden": {"hidden_e02_2.py": hidden("reasoning_tokens, ThinkGuard", C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_think_guard.py` and read `think_guard.py` once more. Make sure no check is copied into several places, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_e02_full.py": hidden("reasoning_tokens, ThinkGuard", C1 + C2)}},
]
