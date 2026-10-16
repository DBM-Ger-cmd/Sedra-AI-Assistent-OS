"""E-04 (coder extension "record and replay", 2026-10-10): `replay_log.py` records the real answers of the model server during a run and plays them back later without a GPU,
so that harness changes (E-01, E-02, E-03 ...) can be tested on real model behaviour without the lease. Ideas from deepseek-harness (llm-replay) and StarNet (replay provider).
Wraps the `post(body)` function of the tool loop; no file access (the caller stores the JSONL text). GUPPI builds it, Claude only wrote this file and the hidden tests.
Plan: <projekte>\\Guppy\\ERWEITERUNGSPLAN_CODER_2026-10-10.md."""

NOTES = '''# Notes for replay_log
Pure Python 3 standard library (json, hashlib, copy), no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
`post(body)` is a function that takes a request dict (OpenAI chat format) and returns the parsed answer dict of the model server.
'''

COMMON = r'''
import copy
from replay_log import IMPORTS

B1 = {"model": "m", "messages": [{"role": "user", "content": "hi"}], "tools": [], "max_tokens": 100, "cache_prompt": True}
B2 = {"model": "m", "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "x"}], "tools": [], "max_tokens": 100, "cache_prompt": True}
R1 = {"choices": [{"message": {"role": "assistant", "content": "a"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5}}
R2 = {"choices": [{"message": {"role": "assistant", "content": "b"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 7}}
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r"""
k1 = request_key(B1)
assert isinstance(k1, str) and len(k1) == 64 and all(c in "0123456789abcdef" for c in k1)
assert request_key(dict(B1)) == k1
assert request_key({**B1, "cache_prompt": False}) == k1 and request_key({k: v for k, v in B1.items() if k != "cache_prompt"}) == k1
assert request_key({"tools": [], "max_tokens": 100, "messages": B1["messages"], "model": "m"}) == k1
assert request_key(B2) != k1 and request_key({**B1, "max_tokens": 101}) != k1
answers = iter([R1, R2])
seen = []
def post(body):
    seen.append(body)
    return next(answers)
rec = Recorder(post)
snap = copy.deepcopy(B1)
out = rec(B1)
assert out == R1 and B1 == snap and seen == [B1]
rec(B2)
assert rec.records == [{"key": k1, "response": R1, "sent": B1["messages"]}, {"key": request_key(B2), "response": R2, "sent": [B2["messages"][1]]}]
B1["messages"][0]["content"] = "edited later"
assert rec.records[0]["sent"] == [{"role": "user", "content": "hi"}]
B1["messages"][0]["content"] = "hi"
short = Recorder(lambda body: R1)
short(B2)
short(B1)
short({"model": "m"})
assert [r["sent"] for r in short.records] == [B2["messages"], B1["messages"], []]
out["choices"][0]["message"]["content"] = "changed"
assert rec.records[0]["response"] == {"choices": [{"message": {"role": "assistant", "content": "a"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5}}
def boom(body):
    raise TimeoutError("server gone")
bad = Recorder(boom)
try:
    bad(B1)
    raise AssertionError("must raise")
except TimeoutError:
    pass
assert bad.records == [{"key": k1, "error": "TimeoutError: server gone", "sent": B1["messages"]}]
text = dumps(rec.records + bad.records)
assert isinstance(text, str) and text.count("\n") == 3 and text.endswith("\n")
assert loads(text) == rec.records + bad.records
assert loads("\n" + text + "\n\n") == rec.records + bad.records
assert dumps([]) == "" and loads("") == []
try:
    loads(text + "{broken\n")
    raise AssertionError("must raise")
except ValueError as exc:
    assert "line 4" in str(exc)
u = Recorder(lambda body: {"choices": [{"message": {"content": "\u00e4\u00f6\u00fc"}}]})
u(B1)
assert "\u00e4\u00f6\u00fc" in dumps(u.records)
"""

C2 = r"""
recs = [{"key": request_key(B1), "response": R1}, {"key": request_key(B2), "response": R2}]
snap = copy.deepcopy(recs)
p = Player(recs)
a = p(B1)
assert a == R1 and p.used == 1
a["choices"][0]["message"]["content"] = "zzz"
assert recs == snap
assert p(B2) == R2 and p.used == 2 and p.mismatches == 0
try:
    p(B1)
    raise AssertionError("must raise")
except ReplayExhausted:
    pass
q = Player(recs)
try:
    q(B2)
    raise AssertionError("must raise")
except ReplayMismatch as exc:
    assert "request 1" in str(exc)
assert q.used == 0
loose = Player(recs, strict=False)
assert loose(B2) == R1 and loose.mismatches == 1 and loose.used == 1
assert loose(B2) == R2 and loose.mismatches == 1
e = Player([{"key": request_key(B1), "error": "TimeoutError: server gone"}])
try:
    e(B1)
    raise AssertionError("must raise")
except ReplayedError as exc:
    assert "TimeoutError: server gone" in str(exc)
assert e.used == 1
assert issubclass(ReplayExhausted, RuntimeError) and issubclass(ReplayMismatch, RuntimeError) and issubclass(ReplayedError, RuntimeError)
answers = iter([R1, R2])
rec = Recorder(lambda body: next(answers))
rec(B1); rec(B2)
again = Player(loads(dumps(rec.records)))
assert again(B1) == R1 and again(B2) == R2
assert Player([]).used == 0
"""

STYLE = " No comments and no docstrings. Never modify the arguments. Put repeated checks into small private helpers."

STAGES = [
    {"name": "record",
     "task": """Create `replay_log.py` (Python 3 standard library only) with:
- `request_key(body) -> str`: the sha256 hex digest of the request dict `body` WITHOUT its key "cache_prompt", serialized with json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":")) and encoded as UTF-8. Equal requests give equal keys, the order of the keys does not matter.
- class `Recorder(post)`: calling the recorder with a body calls `post(body)`, appends {"key": request_key(body), "response": a deep copy of the answer} to the list attribute `records` and returns the answer. When post raises, it appends {"key": ..., "error": "<exception class name>: <message>"} and raises the same exception again. Later changes of the returned answer must not change `records`. Every record also gets "sent": a deep copy of the messages of this request that the previous request of the same Recorder did not have (first request: all of body["messages"]; later: body["messages"][n:] with n = the number of messages of the previous request, or all of them when the new request has fewer than n; a body without a list under "messages" gives [] and counts as 0 messages).
- `dumps(records) -> str`: JSON Lines, one record per line (json.dumps with ensure_ascii=False), every line ends with "\\n"; [] gives "".
- `loads(text) -> list`: the records back; blank lines are skipped; a line that is not valid JSON raises ValueError whose message contains "line <n>" (n = the 1-based line number in text).""" + STYLE + """ Add `tests/test_replay_log.py` (unittest) with your own tests.""",
     "hidden": {"hidden_e04_1.py": hidden("request_key, Recorder, dumps, loads", C1)}},
    {"name": "play",
     "task": """In the existing `replay_log.py` (keep everything) add three exception classes `ReplayExhausted`, `ReplayMismatch`, `ReplayedError` (all subclasses of RuntimeError) and a class `Player(records, strict=True)` that is used instead of `post`:
calling the player with a body returns the NEXT record in order (a deep copy of its "response"; the records given to the constructor are never changed). Attributes: `used` (how many records were handed out) and `mismatches` (0 at start).
- No record left: raise ReplayExhausted.
- The key of the record differs from request_key(body): with strict=True raise ReplayMismatch whose message contains "request <n>" (n = the 1-based number of this request) and do NOT count it as used; with strict=False add 1 to `mismatches` and hand the record out anyway.
- A record with "error" instead of "response": count it as used and raise ReplayedError whose message contains the recorded error text.""" + STYLE + """ Add tests to `tests/test_replay_log.py`.""",
     "hidden": {"hidden_e04_2.py": hidden("request_key, Recorder, dumps, loads, Player, ReplayExhausted, ReplayMismatch, ReplayedError", C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_replay_log.py` and read `replay_log.py` once more. Make sure no check is copied into several places, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_e04_full.py": hidden("request_key, Recorder, dumps, loads, Player, ReplayExhausted, ReplayMismatch, ReplayedError", C1 + C2)}},
]
