import json
import re


class RequestError(Exception):
    def __init__(self, status, text=""):
        super().__init__(text)
        self.status = status
        self.text = text


def garbage(text):
    if not isinstance(text, str):
        return True
    if not text.strip():
        return True
    if re.search(r"(.)\1{9,}", text):
        return True
    others = set(ch for ch in text if ch not in " \n\t")
    return len(others) <= 3


def repetition(text, min_repeats=5):
    if not text:
        return False
    counts = {}
    for line in text.split("\n"):
        key = line.strip()
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return any(count >= min_repeats for count in counts.values())


def long_text(size):
    words = []
    i = 0
    total = 0
    while total < size:
        word = "w%04d " % i
        words.append(word)
        total += len(word)
        i += 1
    return "".join(words)[:size]


def _echo_check(post, model, text):
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": 200 + len(text),
        "tool_choice": "required",
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "echo",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"}
                        },
                        "required": ["text"],
                    },
                },
            }
        ],
        "messages": [
            {
                "role": "user",
                "content": "Call the echo tool with the text: %s" % text,
            }
        ],
    }
    try:
        reply = post("/v1/chat/completions", body)
    except RequestError as e:
        return "error:%s" % e.status
    except Exception:
        return "error:connection"
    try:
        tool_calls = reply["choices"][0]["message"]["tool_calls"]
    except Exception:
        return "no_tool_call"
    if not tool_calls:
        return "no_tool_call"
    first = tool_calls[0]
    name = first.get("function", {}).get("name")
    if name != "echo":
        return "wrong_tool:%s" % name
    args = first.get("function", {}).get("arguments")
    try:
        data = json.loads(args)
    except Exception:
        return "bad_arguments"
    if not isinstance(data, dict):
        return "bad_arguments"
    if not isinstance(data.get("text"), str) or data["text"].rstrip() != text.rstrip():
        return "wrong_text"
    return "ok"


def tool_roundtrip(post, model):
    detail = _echo_check(post, model, "ping")
    return {"check": "tool_roundtrip", "ok": detail == "ok", "detail": detail}


def long_argument(post, model, size=6000):
    detail = _echo_check(post, model, long_text(size))
    return {"check": "long_argument", "ok": detail == "ok", "detail": detail}


def _answer_quality_detail(post, model):
    body = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": "Count from 1 to 5, one number per line.",
            }
        ],
    }
    try:
        reply = post("/v1/chat/completions", body)
    except RequestError as e:
        return "error:%s" % e.status
    except Exception:
        return "error:connection"
    try:
        text = reply["choices"][0]["message"]["content"]
    except Exception:
        text = ""
    if not isinstance(text, str):
        text = ""
    if garbage(text):
        return "garbage"
    if repetition(text):
        return "repetition"
    return "ok"


def answer_quality(post, model):
    detail = _answer_quality_detail(post, model)
    return {"check": "answer_quality", "ok": detail == "ok", "detail": detail}


def _window_detail(post, model, context, make_prompt):
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": 16,
        "messages": [
            {
                "role": "user",
                "content": make_prompt(int(context * 0.9)),
            }
        ],
    }
    try:
        post("/v1/chat/completions", body)
    except RequestError as e:
        return "fill_failed:%s" % e.status
    except Exception:
        return "fill_failed:connection"
    body["messages"][0]["content"] = make_prompt(int(context * 1.1))
    try:
        post("/v1/chat/completions", body)
    except RequestError as e:
        if e.status == 400:
            return "ok"
        return "wrong_status:%s" % e.status
    except Exception:
        return "error:connection"
    return "no_refusal"


def window(post, model, context, make_prompt):
    detail = _window_detail(post, model, context, make_prompt)
    return {"check": "window", "ok": detail == "ok", "detail": detail}


def _cache_detail(post, model, make_prompt):
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": 16,
        "messages": [
            {
                "role": "user",
                "content": make_prompt(2000),
            }
        ],
    }
    replies = []
    for _ in range(2):
        try:
            replies.append(post("/v1/chat/completions", body))
        except RequestError as e:
            return "error:%s" % e.status
        except Exception:
            return "error:connection"
    timings = replies[1].get("timings")
    if not isinstance(timings, dict):
        return "no_timings"
    cache_n = timings.get("cache_n")
    if not isinstance(cache_n, int) or isinstance(cache_n, bool):
        return "no_timings"
    if cache_n > 0:
        return "ok"
    return "no_cache_hit"


def cache(post, model, make_prompt):
    detail = _cache_detail(post, model, make_prompt)
    return {"check": "cache", "ok": detail == "ok", "detail": detail}


def run_all(post, model, context, make_prompt):
    checks = [
        tool_roundtrip(post, model),
        long_argument(post, model),
        answer_quality(post, model),
        window(post, model, context, make_prompt),
        cache(post, model, make_prompt),
    ]
    return {"ok": all(c["ok"] for c in checks), "checks": checks}
