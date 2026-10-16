"""S0 connection check (process "from the bottom up", 2026-10-11): before a model is measured, its server and connection must be proven: a tool call comes back, a long
argument arrives unchanged, the answer is no garbage or repetition, a 90 % window works and an over-full one is refused cleanly, the prompt cache hits. `conn_check.py` holds these
checks against an injected `post` function, so they are pure logic; the benchmark that runs them per recipe comes after acceptance. GUPPI builds it (model comparison 2026-10-11),
Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/s0_conn_check). Process: docs/PROZESS_GUPPY_VON_UNTEN_2026-10-10.md (S0)."""

NOTES = '''# Notes for conn_check
Pure Python 3 standard library (json, re), no file, process or network access of its own: requests go through the injected `post(path, body) -> dict` (an OpenAI-style chat
completion reply). post raises conn_check.RequestError(status, text) for an HTTP error; any other exception counts as a lost connection.
Every check returns {"check": <name>, "ok": <detail == "ok">, "detail": <text>}. No comments and no docstrings, never modify the arguments, small private helpers instead of copied code.
'''

COMMON = r'''
import json
from conn_check import IMPORTS

LONG = long_text(6000)
L100 = long_text(100)

class Server:
    def __init__(self, mode="good", ctx=1000, cache_n=5, fail=None):
        self.mode, self.ctx, self.cache_n, self.fail, self.bodies = mode, ctx, cache_n, fail, []
    def __call__(self, path, body):
        assert path == "/v1/chat/completions", path
        self.bodies.append(json.loads(json.dumps(body)))
        if self.fail == "500":
            raise RequestError(500, "boom")
        if self.fail == "conn":
            raise ConnectionResetError("reset")
        content = body["messages"][-1]["content"]
        if content.startswith("FILL "):
            n = int(content.split()[1])
            if n > self.ctx:
                if self.mode == "no_refusal":
                    return {"choices": [{"message": {"content": "x"}}]}
                if self.mode == "wrong_status":
                    raise RequestError(500, "x")
                raise RequestError(400, "exceeds the context size")
            if self.mode == "fill_fails":
                raise RequestError(413, "x")
            reply = {"choices": [{"message": {"content": "ok"}}]}
            if self.mode != "no_timings":
                same = sum(1 for b in self.bodies if b == self.bodies[-1])
                reply["timings"] = {"cache_n": 0 if self.mode == "no_cache" or same < 2 else self.cache_n}
            return reply
        if body.get("tools"):
            assert body["tools"][0]["function"]["name"] == "echo"
            want = LONG if LONG in content else L100 if L100 in content else "ping"
            assert body.get("max_tokens", 0) >= 200 + len(want), "max_tokens too small for the echo"
            assert body.get("tool_choice") == "required", "the echo checks must force a tool call"
            if self.mode == "no_call":
                return {"choices": [{"message": {"content": "I will not."}}]}
            name = "shell" if self.mode == "wrong_tool" else "echo"
            text = {"wrong_text": want[:-2], "rstrip": want.rstrip(), "number": 5}.get(self.mode, want)
            args = {"bad_args": "{bad", "list_args": "[1]"}.get(self.mode, json.dumps({"text": text}))
            return {"choices": [{"message": {"content": "", "tool_calls": [{"type": "function", "function": {"name": name, "arguments": args}}]}}]}
        text = {"garbage": "GGGGGGGGGGGGGGGG", "repeat": "hello there\n" * 5}.get(self.mode, "1\n2\n3\n4\n5")
        return {"choices": [{"message": {"content": text}}]}

def mp(n):
    return f"FILL {n} " + "x " * 3

def res(name, detail):
    return {"check": name, "ok": detail == "ok", "detail": detail}
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


I1 = "RequestError, garbage, repetition, long_text, tool_roundtrip, long_argument"
I2 = I1 + ", answer_quality, window, cache, run_all"

C1 = r"""
for t in ("", "   \n", None, 5, "GGGGGGGGGG", "aaaaaaaaa", "abab abab", "1 2 3"):
    assert garbage(t) is True, t
for t in ("hello world", "1\n2\n3\n4\n5", "def f(x): return x"):
    assert garbage(t) is False, t
assert repetition("a\na\na\na\na") is True and repetition("a\na\na\na") is False
assert repetition("a\n a \na\na\na") is True and repetition("x\nx\nx", 3) is True
assert repetition("\n\n\n\n\n\n") is False and repetition(None) is False and repetition("") is False
assert len(LONG) == 6000 and LONG.startswith("w0000 w0001 ") and long_text(12) == "w0000 w0001 " and long_text(5) == "w0000"
e = RequestError(400, "too long")
assert e.status == 400 and e.text == "too long" and isinstance(e, Exception)
s = Server()
assert tool_roundtrip(s, "m") == res("tool_roundtrip", "ok")
b = s.bodies[-1]
assert b["model"] == "m" and b["temperature"] == 0 and b["tools"][0]["function"]["name"] == "echo" and "ping" in b["messages"][-1]["content"]
for mode, detail in (("no_call", "no_tool_call"), ("wrong_tool", "wrong_tool:shell"), ("bad_args", "bad_arguments"), ("list_args", "bad_arguments"), ("wrong_text", "wrong_text")):
    assert tool_roundtrip(Server(mode), "m") == res("tool_roundtrip", detail), mode
assert tool_roundtrip(Server(fail="500"), "m") == res("tool_roundtrip", "error:500")
assert tool_roundtrip(Server(fail="conn"), "m") == res("tool_roundtrip", "error:connection")
s = Server()
assert long_argument(s, "m") == res("long_argument", "ok") and LONG in s.bodies[-1]["messages"][-1]["content"]
assert long_argument(Server("wrong_text"), "m") == res("long_argument", "wrong_text")
assert long_argument(Server("rstrip"), "m") == res("long_argument", "ok")
assert long_argument(Server("number"), "m") == res("long_argument", "wrong_text")
s = Server()
assert long_argument(s, "m", 100) == res("long_argument", "ok") and LONG not in s.bodies[-1]["messages"][-1]["content"]
assert long_argument(Server(fail="conn"), "m") == res("long_argument", "error:connection")
"""

C2 = r"""
assert answer_quality(Server(), "m") == res("answer_quality", "ok")
assert answer_quality(Server("garbage"), "m") == res("answer_quality", "garbage")
assert answer_quality(Server("repeat"), "m") == res("answer_quality", "repetition")
assert answer_quality(Server(fail="500"), "m") == res("answer_quality", "error:500")
s = Server(ctx=1000)
assert window(s, "m", 1000, mp) == res("window", "ok")
assert [b["messages"][-1]["content"] for b in s.bodies] == [mp(900), mp(1100)]
assert window(Server("no_refusal"), "m", 1000, mp) == res("window", "no_refusal")
assert window(Server("wrong_status"), "m", 1000, mp) == res("window", "wrong_status:500")
assert window(Server("fill_fails"), "m", 1000, mp) == res("window", "fill_failed:413")
assert window(Server(ctx=1000), "m", 2000, mp) == res("window", "fill_failed:400")
assert window(Server(fail="conn"), "m", 1000, mp) == res("window", "fill_failed:connection")
s = Server(ctx=100000)
assert cache(s, "m", mp) == res("cache", "ok")
assert len(s.bodies) == 2 and s.bodies[0] == s.bodies[1] and s.bodies[0]["messages"][-1]["content"] == mp(2000)
assert cache(Server("no_cache", ctx=100000), "m", mp) == res("cache", "no_cache_hit")
assert cache(Server("no_timings", ctx=100000), "m", mp) == res("cache", "no_timings")
assert cache(Server(fail="500"), "m", mp) == res("cache", "error:500")
r = run_all(Server(ctx=10000), "m", 10000, mp)
assert r["ok"] is True and [c["check"] for c in r["checks"]] == ["tool_roundtrip", "long_argument", "answer_quality", "window", "cache"]
r = run_all(Server("no_call", ctx=10000), "m", 10000, mp)
assert r["ok"] is False and r["checks"][0]["detail"] == "no_tool_call" and r["checks"][1]["detail"] == "no_tool_call" and r["checks"][2]["ok"] is True and r["checks"][4]["ok"] is True
r = run_all(Server(fail="conn"), "m", 10000, mp)
assert r["ok"] is False and len(r["checks"]) == 5 and all(not c["ok"] for c in r["checks"])
"""

STAGES = [
    {"name": "basics",
     "task": """Create `conn_check.py` (Python 3 standard library only):
- class `RequestError(Exception)` with `__init__(self, status, text="")` that keeps `.status` and `.text`.
- `garbage(text) -> bool`: True when text is not a str, or is empty after strip(), or contains one character repeated 10 or more times in a row (regex (.)\\1{9,}), or has at most 3 different characters when space, newline and tab are not counted.
- `repetition(text, min_repeats=5) -> bool`: True when one non-empty line (compared after strip()) appears min_repeats or more times in text split at "\\n"; False for None or "".
- `long_text(size) -> str`: the words "w0000 ", "w0001 ", "w0002 ", ... (f"w{i:04d} ") joined and cut to exactly size characters.
- Every check below returns {"check": name, "ok": detail == "ok", "detail": detail}. A request is post("/v1/chat/completions", body). When post raises RequestError the detail is "error:<status>"; any other exception gives "error:connection".
- `tool_roundtrip(post, model)`: one request with body keys "model": model, "temperature": 0, "max_tokens": 200 + len(text) or more (numbered words take about one token per character), "tool_choice": "required", "tools": [one function tool named "echo" with one string parameter "text"], "messages": [one user message whose content asks to call echo with the text and CONTAINS the text "ping"]. Then look at reply["choices"][0]["message"]["tool_calls"]: none or empty -> "no_tool_call"; the first call's function name is not "echo" -> "wrong_tool:<name>"; its "arguments" string is not JSON for a dict -> "bad_arguments"; the dict's "text" is not a str or differs from the expected text after rstrip() of both (a model drops a trailing space) -> "wrong_text"; else "ok". Name "tool_roundtrip".
- `long_argument(post, model, size=6000)`: the same with the text long_text(size) instead of "ping" (the user message contains it), name "long_argument".
No comments and no docstrings, never modify the arguments, small private helpers instead of copied code (both echo checks share one helper). Add `tests/test_conn_check.py` (unittest) with your own tests.""",
     "hidden": {"hidden_s0_1.py": hidden(I1, C1)}},
    {"name": "checks",
     "task": """Add to `conn_check.py` (same result dict and error rules as before):
- `answer_quality(post, model)`: a request without tools, "temperature": 0, a user message asking to count from 1 to 5, one number per line. The reply text is choices[0].message.content (missing -> ""). garbage(text) -> "garbage", else repetition(text) -> "repetition", else "ok". Name "answer_quality".
- `window(post, model, context, make_prompt)`: make_prompt(n) returns a user text of about n tokens. First request: "temperature": 0, a small "max_tokens", one user message with content make_prompt(int(context * 0.9)). If it fails, the detail is "fill_failed:<status>" (or "fill_failed:connection"). Then the same with make_prompt(int(context * 1.1)): it must be refused with RequestError status 400 -> "ok"; another status -> "wrong_status:<status>"; another exception -> "error:connection"; no error at all -> "no_refusal". Name "window".
- `cache(post, model, make_prompt)`: the same body twice (one user message make_prompt(2000), "temperature": 0, a small "max_tokens"); an error -> "error:<status>" / "error:connection". In the SECOND reply, "timings" must be a dict with an int "cache_n", else "no_timings"; cache_n > 0 -> "ok", else "no_cache_hit". Name "cache".
- `run_all(post, model, context, make_prompt) -> dict`: {"ok": all checks ok, "checks": [tool_roundtrip, long_argument, answer_quality, window, cache]} in this order; a failed check never stops the others.
Add tests to `tests/test_conn_check.py`.""",
     "hidden": {"hidden_s0_2.py": hidden(I2, C1 + C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_conn_check.py` and read `conn_check.py` once more. Make sure no request or error handling is copied into several places, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_s0_full.py": hidden(I2, C1 + C2)}},
]
