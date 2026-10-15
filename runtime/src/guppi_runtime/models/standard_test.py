"""Standardtest: finds good context settings for the loaded model.

Criteria the Captain can pick: stabilitaet (no errors or timeouts), tokens (generation speed, tokens per second), lesen_schreiben
(prompt speed = reading the text, generation speed = writing it) and coder (small coding tasks; the answer must parse as Python and
define the asked function). Durations: schnell 5 min, standard 15 min, langzeit 90 min. The test changes the context only by a
reload of the GUPPI llama-server; it never changes a recipe. The result is a recommendation, applied only after the Captain approves it.

Pure logic here: the caller passes `post(path, body)` (the llama-server HTTP call), `reload(context)` (restarts the model with that
context) and a clock, so the whole test can be run with fakes.
"""
from __future__ import annotations

import ast
import re
import statistics
import time

DURATIONS = {"schnell": 300, "standard": 900, "langzeit": 5400}
CRITERIA = ("stabilitaet", "tokens", "lesen_schreiben", "coder")
CRITERIA_LABELS = {"stabilitaet": "Stabilität", "tokens": "Token-Geschwindigkeit", "lesen_schreiben": "Lesen und Schreiben",
                   "coder": "Coder-Leistung"}
MAX_ERRORS = 3                       # more failed calls in one context: the context counts as unstable and the test goes on
READ_PROMPT_WORDS = 1500              # the long text for the reading speed
WRITE_TOKENS = 128
CODE_TOKENS = 400

CODER_TASKS = [
    ("Schreibe eine Python-Funktion fib(n), die die n-te Fibonacci-Zahl liefert. Antworte nur mit Code.", "fib"),
    ("Schreibe eine Python-Funktion reverse_words(s), die die Wörter eines Satzes umkehrt. Antworte nur mit Code.", "reverse_words"),
    ("Schreibe eine Python-Funktion is_prime(n), die True liefert, wenn n eine Primzahl ist. Antworte nur mit Code.", "is_prime"),
]


def contexts_for(duration, tiers, recommended):
    """Which contexts a duration tests. schnell: the recommended one; standard: three steps; langzeit: all steps up to 65536."""
    tiers = sorted(int(t) for t in tiers)
    if duration == "schnell":
        return [recommended] if recommended in tiers else tiers[:1]
    if duration == "standard":
        return [t for t in tiers if 16384 <= t <= 65536][:3] or tiers[:3]
    return [t for t in tiers if t <= 65536]


def plan(duration, criteria, tiers, recommended):
    """What the test will do: duration, criteria, contexts and the seconds for each context."""
    if duration not in DURATIONS: raise ValueError("duration_unknown")
    crit = [c for c in criteria if c in CRITERIA]
    if not crit: raise ValueError("criteria_required")
    contexts = contexts_for(duration, tiers, recommended)
    if not contexts: raise ValueError("no_contexts")
    per = DURATIONS[duration] // len(contexts)
    return {"duration": duration, "seconds": DURATIONS[duration], "criteria": crit,
            "trials": [{"context": c, "seconds": per} for c in contexts]}


def _timings(data):
    t = data.get("timings") or {}
    return t.get("predicted_per_second"), t.get("prompt_per_second")


def _code_ok(text, name):
    """The answer holds a Python function with the asked name. Code is parsed, never executed."""
    block = re.search(r"```(?:python)?\s*(.*?)```", text or "", re.S)
    code = block.group(1) if block else (text or "")
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    return any(isinstance(n, ast.FunctionDef) and n.name == name for n in ast.walk(tree))


def measure(post, trial_seconds, criteria, clock=time.monotonic, read_text=None):
    """Runs the checks of one context until its time is used up. post(path, body) returns the llama-server JSON."""
    end = clock() + trial_seconds
    gen, prompt, coder = [], [], []
    errors, calls = 0, 0
    read_text = read_text or ("Der Text wiederholt sich. " * READ_PROMPT_WORDS)
    while clock() < end:
        if "lesen_schreiben" in criteria or "tokens" in criteria or "stabilitaet" in criteria:
            calls += 1
            try:
                data = post("/completion", {"prompt": read_text if "lesen_schreiben" in criteria else "Erzähle kurz von einem Hafen.",
                                            "n_predict": WRITE_TOKENS, "temperature": 0.2})
                tps, pps = _timings(data)
                if tps: gen.append(tps)
                if pps and "lesen_schreiben" in criteria: prompt.append(pps)
            except Exception:
                errors += 1
                if errors > MAX_ERRORS: break
        if "coder" in criteria:
            for task, name in CODER_TASKS:
                if clock() >= end: break
                calls += 1
                try:
                    data = post("/completion", {"prompt": task + "\n", "n_predict": CODE_TOKENS, "temperature": 0.2})
                    coder.append(_code_ok(data.get("content", ""), name))
                except Exception:
                    errors += 1
                    if errors > MAX_ERRORS: break
            if errors > MAX_ERRORS: break
    return {"calls": calls, "errors": errors,
            "tokens_per_s": round(statistics.median(gen), 1) if gen else None,
            "read_per_s": round(statistics.median(prompt), 1) if prompt else None,
            "coder_pass": round(sum(coder) / len(coder), 2) if coder else None,
            "stable": errors <= MAX_ERRORS}


def run(test_plan, post, reload, clock=time.monotonic, on_progress=None):
    """Runs every trial in order. reload(context) restarts the model with that context and returns True when it is up."""
    results = []
    for trial in test_plan["trials"]:
        ctx = trial["context"]
        if on_progress: on_progress({"context": ctx, "state": "lade"})
        if not reload(ctx):
            results.append({"context": ctx, "status": "nicht_geladen"})
            continue
        if on_progress: on_progress({"context": ctx, "state": "misst"})
        measured = measure(post, trial["seconds"], test_plan["criteria"], clock=clock)
        results.append({"context": ctx, "status": "ok", **measured})
    return {"duration": test_plan["duration"], "criteria": test_plan["criteria"], "results": results, "recommendation": recommend(results, test_plan["criteria"])}


def recommend(results, criteria):
    """Best context per chosen criterion, and one overall pick: stable first, then the sum of the normalised scores."""
    usable = [r for r in results if r.get("status") == "ok" and r.get("stable")]
    if not usable:
        return {"context": None, "reason": "Kein Kontext war stabil genug."}
    def best(key):
        cands = [r for r in usable if r.get(key) is not None]
        return max(cands, key=lambda r: r[key])["context"] if cands else None
    per = {}
    if "tokens" in criteria: per["tokens"] = best("tokens_per_s")
    if "lesen_schreiben" in criteria: per["lesen_schreiben"] = best("read_per_s")
    if "coder" in criteria: per["coder"] = best("coder_pass")
    # overall: each criterion counts once; a context gets a point for every criterion it wins or ties
    score = {r["context"]: 0 for r in usable}
    for key, winner in per.items():
        if winner is not None: score[winner] += 1
    overall = max(score, key=lambda c: (score[c], -c))
    return {"context": overall, "per_criterion": per, "reason": "stabil und in den gewählten Kriterien vorn" if len(usable) else ""}
