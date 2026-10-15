r"""Which model REPAIRS best, and how much do GUPPI's knowledge-base lessons help? (a measurement, not a test)

    .venv\Scripts\python.exe benchmarks/rework_bench.py <project_dir> [--models coder.local_primary,coder.llama_gptoss,verifier.llama_gemma]
        [--seeds 2]

Captain 2026-10-03: "mit gefüllter Wissensdatenbank - wäre ein kleineres, stabileres Modell besser als Prüfer / Coder?" -> measure it.
Five small repair tasks of the kind the local coders failed that day (uix_window): a validator whose contract names one exact error,
a buggy version, the failing test output and GUPPI's REPRO lines (input, exception, line) - exactly what a real rework sees.
Every model repairs every task `seeds` times WITHOUT and WITH the matching lessons (knowledge.lessons_for). Sampling per model comes
from the routing profile purpose "rework" if that recipe is preferred there, else the coder defaults (temperature 0.1).

Grading is static (the answer is parsed, never executed on this host): per task one or two AST checks that the cause is fixed
(e.g. "parsed.port is read inside try/except ValueError that raises the documented error"). Results:
runtime_data/measurements/rework_bench_<date>.json. Holds the GPU lease.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
from datetime import date
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.gpu_preflight import clear_leftovers                              # noqa: E402
from guppi_runtime.knowledge import KnowledgeStore                                   # noqa: E402
from guppi_runtime.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.models.openai_local import split_harmony                         # noqa: E402
from guppi_runtime.routing_profiles import RoutingProfiles                          # noqa: E402
from guppi_runtime.testlab import TestLab, default_path                             # noqa: E402


def _try_guarded(fn, attr_or_call, exc_name, message):
    """True if, inside `fn`, the node that matches `attr_or_call` sits in a Try whose handler catches `exc_name` and raises `message`."""
    for t in ast.walk(fn):
        if not isinstance(t, ast.Try):
            continue
        body_hit = any(attr_or_call(n) for b in t.body for n in ast.walk(b))
        handler_ok = any((h.type is None or exc_name in ast.unparse(h.type)) and message in ast.unparse(h) for h in t.handlers)
        if body_hit and handler_ok:
            return True
    return False


def _fn(tree, name):
    return next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name), None)


TASKS = [
    {"id": "regex_trailing_newline", "fn": "check_id",
     "code": 'import re\n\n\ndef check_id(s):\n    """Return s if it is 1-12 lower-case letters, else raise ValueError("bad_id")."""\n'
             '    if not re.match(r"^[a-z]{1,12}$", s):\n        raise ValueError("bad_id")\n    return s\n',
     "failure": "AssertionError: ValueError not raised : 'abc\\n'",
     "repro": "REPRO   input 'abc\\n': expected ValueError, got no exception",
     "checks": {"no_dollar_match": lambda f: not any(isinstance(n, ast.Call) and ast.unparse(n.func) in ("re.match", "re.search")
                                                        and n.args and isinstance(n.args[0], ast.Constant) and str(n.args[0].value).endswith("$")
                                                        for n in ast.walk(f)) or "\\Z" in ast.unparse(f)}},
    {"id": "urlparse_port", "fn": "check_url",
     "code": 'from urllib.parse import urlparse\n\n\ndef check_url(url):\n    """Return url if it is http://127.0.0.1:<1..65535>/, else raise ValueError("url_not_allowed")."""\n'
             '    parsed = urlparse(url)\n    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path != "/":\n'
             '        raise ValueError("url_not_allowed")\n    port = parsed.port\n    if port is None or not 1 <= port <= 65535:\n'
             '        raise ValueError("url_not_allowed")\n    return url\n',
     "failure": "AssertionError: 'Port out of range 0-65535' != 'url_not_allowed'",
     "repro": "REPRO   input 'http://127.0.0.1:65536/': expected ValueError, got ValueError: Port out of range 0-65535 at mod.py:9: port = parsed.port",
     "checks": {"port_guarded": lambda f: _try_guarded(f, lambda n: isinstance(n, ast.Attribute) and n.attr == "port", "ValueError", "url_not_allowed")}},
    {"id": "int_conversion", "fn": "parse_count",
     "code": 'def parse_count(text):\n    """Return int(text) if it is a whole number 0..1000, else raise ValueError("bad_count")."""\n'
             '    n = int(text)\n    if not 0 <= n <= 1000:\n        raise ValueError("bad_count")\n    return n\n',
     "failure": "AssertionError: \"invalid literal for int() with base 10: 'x1'\" != 'bad_count'",
     "repro": "REPRO   input 'x1': expected ValueError, got ValueError: invalid literal for int() with base 10: 'x1' at mod.py:3: n = int(text)",
     "checks": {"int_guarded": lambda f: _try_guarded(f, lambda n: isinstance(n, ast.Call) and ast.unparse(n.func) == "int", "ValueError", "bad_count")}},
    {"id": "dict_key", "fn": "get_setting",
     "code": 'def get_setting(settings, key):\n    """Return settings[key]; a missing key raises LookupError("setting_missing")."""\n    return settings[key]\n',
     "failure": "AssertionError: LookupError not raised as LookupError('setting_missing'): KeyError('port')",
     "repro": "REPRO   input 'port': expected LookupError, got KeyError: 'port' at mod.py:3: return settings[key]",
     "checks": {"key_handled": lambda f: _try_guarded(f, lambda n: isinstance(n, ast.Subscript), "KeyError", "setting_missing")
                or ("setting_missing" in ast.unparse(f) and (" in settings" in ast.unparse(f) or ".get(" in ast.unparse(f)))}},
    {"id": "isoformat_date", "fn": "parse_day",
     "code": 'from datetime import date\n\n\ndef parse_day(text):\n    """Return date.fromisoformat(text) for YYYY-MM-DD, else raise ValueError("bad_day")."""\n'
             '    return date.fromisoformat(text)\n',
     "failure": "AssertionError: \"Invalid isoformat string: '2026-13-01'\" != 'bad_day'",
     "repro": "REPRO   input '2026-13-01': expected ValueError, got ValueError: month must be in 1..12 at mod.py:6: return date.fromisoformat(text)",
     "checks": {"fromisoformat_guarded": lambda f: _try_guarded(f, lambda n: isinstance(n, ast.Call) and ast.unparse(n.func).endswith("fromisoformat"),
                                                                 "ValueError", "bad_day")}},
]


def prompt_for(task, lessons):
    body = (f"Fix this Python module. Its contract (the docstring) is correct and the tests are correct.\n\n```python\n{task['code']}```\n\n"
            f"The tests fail:\n{task['failure']}\n\nGUPPI reproduced the failure in its VM:\n{task['repro']}\n")
    if lessons:
        body += "\nLessons from GUPPI's knowledge base that match this code:\n" + "\n".join(f"- {l}" for l in lessons) + "\n"
    return body + "\nAnswer with the complete fixed module in one ```python block."


def ask(endpoint, alias, prompt, sampling):
    req_body = {"model": alias, "messages": [{"role": "user", "content": prompt}], "max_tokens": 6000,
                "temperature": sampling.get("temperature", 0.1)}
    if sampling.get("reasoning_effort"):
        req_body["reasoning_effort"] = sampling["reasoning_effort"]
    req = urllib.request.Request(endpoint + "/v1/chat/completions", data=json.dumps(req_body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            data = json.loads(r.read())
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}", "seconds": round(time.monotonic() - t0, 1)}
    content = data["choices"][0]["message"].get("content") or ""
    h = split_harmony(content)
    return {"content": h[0] if h is not None else content, "finish": data["choices"][0].get("finish_reason"),
            "seconds": round(time.monotonic() - t0, 1)}


def grade(task, text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text or "", flags=re.S)
    code = blocks[-1] if blocks else (text or "")
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"parses": False}, False
    fn = _fn(tree, task["fn"])
    if fn is None:
        return {"parses": True, "function_present": False}, False
    checks = {"parses": True, "function_present": True, **{k: bool(c(fn)) for k, c in task["checks"].items()}}
    return checks, all(checks.values())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--models", default="coder.local_primary,coder.llama_gptoss,verifier.llama_gemma")
    ap.add_argument("--seeds", type=int, default=2)
    args = ap.parse_args()
    project = Path(args.project)
    recipes = {r["id"]: r for r in yaml.safe_load((project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))["role_routing"]["capabilities"]}
    profiles = RoutingProfiles.load(project / "local_config" / "routing_profiles.yaml")
    knowledge = KnowledgeStore(project / "runtime_data" / "knowledge" / "records.jsonl")
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_rework_")))
    out = project / "runtime_data" / "measurements" / f"rework_bench_{date.today().isoformat()}.json"
    result = {"tasks": [t["id"] for t in TASKS], "seeds": args.seeds, "models": {}}
    with TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "rework_bench"), "rework bench", ttl_s=1800, wait_s=3600,
                                              preflight=clear_leftovers):
        for rid in args.models.split(","):
            recipe = recipes[rid]
            alias = str(recipe.get("model") or rid)
            sampling = {k: v for k, v in profiles.purpose("rework").items() if k != "prefer"} if rid in profiles.prefer("rework") else {}
            print(f"== {rid} ({alias}) sampling {sampling or 'coder default'}", flush=True)
            rows = []
            runtime.load_model(alias, context_length=16384, gpu="max", identifier=alias, parallel=1, server=recipe["profile"]["server"])
            try:
                for task in TASKS:
                    lessons = [r["content"]["summary"] for r in knowledge.lessons_for(task["code"] + task["repro"])]
                    for with_lessons in (False, True):
                        for seed in range(args.seeds):
                            res = ask(runtime.endpoint, alias, prompt_for(task, lessons if with_lessons else []), sampling)
                            checks, ok = grade(task, res.get("content")) if "error" not in res else ({"error": res["error"]}, False)
                            rows.append({"task": task["id"], "lessons": with_lessons, "lessons_available": len(lessons), "seed": seed,
                                         "fixed": ok, "checks": checks, "seconds": res.get("seconds"), "finish": res.get("finish"),
                                         "answer": (res.get("content") or "")[:4000]})
                            print(f"   {task['id']:24s} lessons={'yes' if with_lessons else 'no '} #{seed}: {'FIXED' if ok else 'not fixed'}  "
                                  f"{res.get('seconds')} s {res.get('finish') or res.get('error', '')}", flush=True)
            finally:
                runtime.unload_model(all_models=True); time.sleep(2)
            summary = {flag: f"{sum(r['fixed'] for r in rows if r['lessons'] == flag)}/{sum(1 for r in rows if r['lessons'] == flag)}"
                       for flag in (False, True)}
            result["models"][rid] = {"model": alias, "sampling": sampling, "without_lessons": summary[False], "with_lessons": summary[True], "rows": rows}
            print(f"  -> {rid}: without lessons {summary[False]}, with lessons {summary[True]}", flush=True)
            out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"  DONE -> {out.name}", flush=True)


if __name__ == "__main__":
    main()
