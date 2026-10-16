import json
import re

ECHO_TOOL = {"type": "function", "function": {"name": "echo", "description": "Repeat a text.",
                                              "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}}


class RequestError(Exception):
    def __init__(self, status, text=""):
        super().__init__(f"{status}: {text}")
        self.status, self.text = status, text


def garbage(text):
    if not isinstance(text, str) or not text.strip():
        return True
    return bool(re.search(r"(.)\1{9,}", text)) or len(set(text) - set(" \n\t")) <= 3


def repetition(text, min_repeats=5):
    counts = {}
    for line in (text or "").split("\n"):
        line = line.strip()
        if line:
            counts[line] = counts.get(line, 0) + 1
    return any(n >= min_repeats for n in counts.values())


def _result(name, detail):
    return {"check": name, "ok": detail == "ok", "detail": detail}


def _ask(post, body):
    try:
        return post("/v1/chat/completions", body), None
    except RequestError as exc:
        return None, f"error:{exc.status}"
    except Exception:
        return None, "error:connection"


def _call_detail(reply, expected):
    calls = (reply.get("choices") or [{}])[0].get("message", {}).get("tool_calls") or []
    if not calls:
        return "no_tool_call"
    function = calls[0].get("function") or {}
    if function.get("name") != "echo":
        return f"wrong_tool:{function.get('name')}"
    try:
        args = json.loads(function.get("arguments") or "")
    except ValueError:
        return "bad_arguments"
    if not isinstance(args, dict):
        return "bad_arguments"
    text = args.get("text")
    return "ok" if isinstance(text, str) and text.rstrip() == expected.rstrip() else "wrong_text"


def _echo(post, model, name, text):
    body = {"model": model, "temperature": 0, "max_tokens": 200 + len(text), "tool_choice": "required", "tools": [ECHO_TOOL],
            "messages": [{"role": "user", "content": f"Call the tool echo with exactly this text and nothing else:\n{text}"}]}
    reply, error = _ask(post, body)
    return _result(name, error or _call_detail(reply, text))


def long_text(size):
    return "".join(f"w{i:04d} " for i in range(size // 6 + 1))[:size]


def tool_roundtrip(post, model):
    return _echo(post, model, "tool_roundtrip", "ping")


def long_argument(post, model, size=6000):
    return _echo(post, model, "long_argument", long_text(size))


def answer_quality(post, model):
    reply, error = _ask(post, {"model": model, "temperature": 0, "max_tokens": 100,
                               "messages": [{"role": "user", "content": "Count from 1 to 5, one number per line."}]})
    if error:
        return _result("answer_quality", error)
    text = ((reply.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return _result("answer_quality", "garbage" if garbage(text) else "repetition" if repetition(text) else "ok")


def _fill(model, make_prompt, tokens):
    return {"model": model, "temperature": 0, "max_tokens": 8, "messages": [{"role": "user", "content": make_prompt(tokens)}]}


def window(post, model, context, make_prompt):
    reply, error = _ask(post, _fill(model, make_prompt, int(context * 0.9)))
    if error:
        return _result("window", "fill_failed:" + error.split(":", 1)[1])
    try:
        post("/v1/chat/completions", _fill(model, make_prompt, int(context * 1.1)))
    except RequestError as exc:
        return _result("window", "ok" if exc.status == 400 else f"wrong_status:{exc.status}")
    except Exception:
        return _result("window", "error:connection")
    return _result("window", "no_refusal")


def cache(post, model, make_prompt, tokens=2000):
    body = _fill(model, make_prompt, tokens)
    for _ in range(2):
        reply, error = _ask(post, body)
        if error:
            return _result("cache", error)
    timings = reply.get("timings")
    if not isinstance(timings, dict) or not isinstance(timings.get("cache_n"), int):
        return _result("cache", "no_timings")
    return _result("cache", "ok" if timings["cache_n"] > 0 else "no_cache_hit")


def run_all(post, model, context, make_prompt):
    checks = [tool_roundtrip(post, model), long_argument(post, model), answer_quality(post, model),
              window(post, model, context, make_prompt), cache(post, model, make_prompt)]
    return {"ok": all(c["ok"] for c in checks), "checks": checks}
