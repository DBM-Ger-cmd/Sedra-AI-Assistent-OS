"""Does switching the thinking off (or capping it) make answers worse? A measurement, not a test: it talks to a real local model.

Tasks have a deterministic grader (no model judges a model). Each task runs once per variant at temperature 0:

    default      the model's own behaviour
    off          reasoning_effort = "none"
    budget256    thinking_budget_tokens = 256
    budget1024   thinking_budget_tokens = 1024

Calls go through GUPPI's own path (loader -> ControlMasterModule.model_call -> ModelRouter -> adapter), so what is measured is what a
job would get. The model is started the way its recipe says (provider and `profile.server` from the local routing overlay), by default
through GUPPI's own llama-server. It writes one JSON line per call and prints accuracy, output tokens, thinking and seconds per model,
category and variant. llama-server does not report thinking tokens, so the size of the thinking text (characters) is recorded too.

    python benchmarks/token_quality.py <project_dir_with_local_config> <results.jsonl> [model_key ...]

Limits worth knowing: 24 tasks, one sample each, temperature 0. Differences of one task are noise. A category with 4 to 6 tasks can
only show large effects.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

PROVIDER = "llama-cpp-server"
VARIANTS = {"default": {}, "off": {"reasoning_effort": "none"}, "budget256": {"thinking_budget_tokens": 256}, "budget1024": {"thinking_budget_tokens": 1024},
            # gpt-oss always thinks and knows no "none": its levels are low / medium / high
            "low": {"reasoning_effort": "low"}, "medium": {"reasoning_effort": "medium"}, "high": {"reasoning_effort": "high"}}
if os.environ.get("TQ_VARIANTS"):                  # e.g. TQ_VARIANTS=default,low,high
    VARIANTS = {k: VARIANTS[k] for k in os.environ["TQ_VARIANTS"].split(",")}


def _norm(text):
    return re.sub(r"[\s*_`]", "", (text or "").lower()).replace(",", "").replace(" ", "")


def has_all(*needles):
    def grade(answer):
        flat = _norm(answer)
        return all(_norm(n) in flat for n in needles)
    return grade


def tail_has(*options, width=220):
    def grade(answer):
        tail = _norm((answer or "")[-width:])
        return any(_norm(o) in tail for o in options)
    return grade


def verdict(expected):
    def grade(answer):
        words = re.findall(r"[A-Za-z]+", (answer or "").strip())
        return bool(words) and words[0].upper() == expected
    return grade


def json_equals(expected):
    def grade(answer):
        text = (answer or "").strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        try:
            return json.loads(text) == expected
        except ValueError:
            return False
    return grade


def three_bullets(answer):
    lines = [l for l in (answer or "").strip().splitlines() if l.strip()]
    return len(lines) == 3 and all(l.startswith("- ") for l in lines)


REVIEW = "You are a reviewer. Below is a short technical note. If it contains a factual error, reply FAIL followed by one sentence naming the error. If it is entirely correct, reply PASS followed by one sentence. The first word of your reply must be PASS or FAIL.\n\nNOTE:\n"
TASKS = [
    # summaries (reviewer / documentation / curator work)
    ("summary", "S1", "Summarise in two sentences, keeping every number and name: On 14 March 2024 the Lisbon team shipped version 4.2 of the router, cutting median latency from 180 ms to 95 ms. The change was led by Marta Silva.", has_all("4.2", "95", "Silva")),
    ("summary", "S2", "Summarise in two sentences, keeping every number and name: The archive holds 12,400 documents collected between 1998 and 2011 in the town of Brno, and was digitised by volunteers over three years.", has_all("12400", "Brno", "three")),
    ("summary", "S3", "Summarise in two sentences, keeping every name and cause: Server alpha-7 rebooted at 03:12 after a kernel panic caused by a faulty memory module; the module was replaced the next morning.", has_all("alpha-7", "kernel panic", "memory")),
    ("summary", "S4", "Summarise in two sentences, keeping every number and date: The council approved a budget of 2.4 million euros for the new library, with construction starting in September and finishing in late 2026.", has_all("2.4", "September", "2026")),
    # verification (verifier work): three notes with one seeded error, three correct
    ("verify", "V1-error", REVIEW + "SHA-256 produces a 128-bit digest, which is why it is widely used for hash chains.", verdict("FAIL")),
    ("verify", "V2-clean", REVIEW + "In a hash chain each entry stores the hash of the previous entry. Changing an old entry changes its hash and therefore breaks every later link.", verdict("PASS")),
    ("verify", "V3-error", REVIEW + "Python lists are immutable, so appending to a list always creates a new list object.", verdict("FAIL")),
    ("verify", "V4-clean", REVIEW + "In Python a tuple is immutable: its items cannot be reassigned after creation, although a mutable object stored inside a tuple can still be modified.", verdict("PASS")),
    ("verify", "V5-error", REVIEW + "HTTP status code 404 means that the server crashed with an internal error.", verdict("FAIL")),
    ("verify", "V6-clean", REVIEW + "A Git commit is identified by a hash of its contents, its parent commits and its metadata, so two commits with identical files but different parents have different IDs.", verdict("PASS")),
    # reasoning (planner / coder work)
    ("reason", "M1", "A shop sells pens at 3 for 2.40 euros. How much do 12 pens cost in euros? End with the final number.", tail_has("9.6", "9.60")),
    ("reason", "M2", "A train leaves at 9:40 and travels 150 km at 60 km/h, then waits 25 minutes, then travels 90 km at 45 km/h. At what time does it arrive? End with the time.", tail_has("14:35", "2:35")),
    ("reason", "M3", "A tank holds 480 liters. It is filled at 12 liters per minute for 15 minutes, then 20% of the content is drained. How many liters remain? End with the final number.", tail_has("144")),
    ("reason", "M4", "What is 17 times 23? End with the final number.", tail_has("391")),
    ("reason", "M5", "Anna is twice as old as Ben. In 6 years the sum of their ages will be 42. How old is Ben now? End with the final number.", tail_has("10")),
    ("reason", "M6", "A recipe needs 250 g of flour for 4 people. How many grams for 10 people? End with the final number.", tail_has("625")),
    # code reading
    ("code", "C1", "What does this Python code print? Reply with the output only at the end.\n\nprint(sum(range(1, 6)))", tail_has("15", width=40)),
    ("code", "C2", "What does this Python code print? Reply with the output only at the end.\n\nx = [1, 2, 3]\ny = x\ny.append(4)\nprint(len(x))", tail_has("4", width=40)),
    ("code", "C3", "What does this Python code print? Reply with the output only at the end.\n\nprint('abc'[::-1].upper())", tail_has("CBA", width=40)),
    ("code", "C4", "What does this Python code print? Reply with the output only at the end.\n\ndef f(n):\n    return n if n < 2 else f(n - 1) + f(n - 2)\nprint(f(7))", tail_has("13", width=40)),
    # format following (tool_operator work)
    ("format", "F1", "Reply with ONLY a JSON object with the keys name (the string GUPPI) and version (the integer 8).", json_equals({"name": "GUPPI", "version": 8})),
    ("format", "F2", "Reply with ONLY a JSON array holding the three smallest prime numbers.", json_equals([2, 3, 5])),
    ("format", "F3", "Reply with ONLY a JSON object: key ok is true and key items is the list a, b, c in reverse order.", json_equals({"ok": True, "items": ["c", "b", "a"]})),
    ("format", "F4", "Reply with exactly three lines, each starting with '- ', each naming one colour. Nothing else.", three_bullets),
]


def main(project_dir, results_path, models):
    """Takes the shared GPU lease (waits up to 30 minutes for another chat's run) and records every call in the test lab database."""
    from guppi_runtime.testlab import TestLab, default_path
    from guppi_runtime.gpu_preflight import clear_leftovers
    lab = TestLab(default_path(project_dir))
    owner = os.environ.get("TESTLAB_OWNER", "token_quality")
    with lab.lease(owner, f"token_quality {','.join(models)}", ttl_s=600, wait_s=1800, preflight=clear_leftovers):
        run_id = lab.start_run(owner, "quality", f"token_quality {','.join(models)}", {"models": models, "variants": list(VARIANTS), "tasks": len(TASKS)})
        try:
            _run(project_dir, results_path, models, lab, run_id)
        except BaseException:
            lab.finish_run(run_id, "failed")
            raise
        lab.finish_run(run_id)
    print(f"test lab run {run_id}: python benchmarks/testlab_cli.py summary {run_id}")


def _run(project_dir, results_path, models, lab, run_id):
    from guppi_runtime.runtime import GuppiRuntime
    tmp = Path(tempfile.mkdtemp())
    project = tmp / "GUPPI_OS"
    shutil.copytree(Path(project_dir) / "local_config", project / "local_config")
    arch = sorted((RUNTIME.parent / "architecture").glob("GUPPI_Architecture_v*"))[-1]
    rt = GuppiRuntime(project, architecture_root=arch)
    if not (rt.model_loader and rt.model_loader.enabled):
        sys.exit("model_loader is not enabled by the local switches")
    rt.model_router.adapters[PROVIDER].timeout = 600
    out = Path(results_path).open("a", encoding="utf-8")
    for model in models:
        recipe = next((r for r in rt.role_router.config.recipes if r["model"] == model and r["provider"] == PROVIDER), None)
        if recipe is None:
            sys.exit(f"no {PROVIDER} recipe for {model} in the routing overlay")
        resolution = {"model": model, "provider_ref": PROVIDER, "context_window": 8192, "estimated_resources": {},
                      "load_profile": {"gpu_layers": recipe["profile"].get("gpu_layers"), "server": recipe["profile"].get("server")}}
        rt.model_loader.evict_idle(set())
        print("loading", model, rt.model_loader.ensure(resolution), flush=True)
        for variant, extra in VARIANTS.items():
            for category, tid, prompt, grade in TASKS:
                request = {"provider": PROVIDER, "model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 3000, "temperature": 0,
                           "job_id": f"BENCH-{variant}", "attempt_id": tid, "role": "bench", **extra}
                started = time.time()
                reply = rt.control.model_call(f"BENCH-{variant}", request)
                seconds = time.time() - started
                result = reply.get("model_result") or {}
                usage = result.get("usage") or {}
                answer = result.get("content") or ""
                record = {"model": model, "variant": variant, "category": category, "task": tid, "status": reply.get("status"),
                          "correct": bool(reply.get("status") == "completed" and grade(answer)), "output_tokens": usage.get("output_tokens"),
                          "reasoning_tokens": usage.get("reasoning_tokens"), "reasoning_chars": result.get("reasoning_chars"), "seconds": round(seconds, 2), "truncated": bool(result.get("truncated")),
                          "empty": bool(result.get("empty_answer")), "error": str(reply.get("error"))[:160] if reply.get("status") != "completed" else None,
                          "answer_tail": answer[-160:]}
                out.write(json.dumps(record, ensure_ascii=False) + "\n"); out.flush()
                print(f"{model:24s} {variant:10s} {tid:9s} {'ok ' if record['correct'] else 'BAD'} out={record['output_tokens']} think={record['reasoning_tokens']} {seconds:.1f}s", flush=True)
        rt.model_loader.unload(resolution)
    summarise(results_path)


def summarise(results_path):
    rows = [json.loads(l) for l in Path(results_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    groups = defaultdict(list)
    for r in rows:
        groups[(r["model"], r["category"], r["variant"])].append(r)
        groups[(r["model"], "ALL", r["variant"])].append(r)
    print("\nmodel | category | variant | correct | avg output tokens | avg thinking chars | avg seconds | errors")
    for key in sorted(groups):
        g = groups[key]
        n = len(g)
        avg = lambda name: sum((x.get(name) or 0) for x in g) / n
        print(f"{key[0]} | {key[1]} | {key[2]} | {sum(x['correct'] for x in g)}/{n} | {avg('output_tokens'):.0f} | {avg('reasoning_chars'):.0f} | {avg('seconds'):.1f} | {sum(1 for x in g if x['status'] != 'completed')}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--summary":
        summarise(sys.argv[2])
    else:
        main(sys.argv[1], sys.argv[2], sys.argv[3:] or ["qwen3.5-9b-mtp", "google/gemma-4-12b-qat"])
