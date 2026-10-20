"""Which server setting makes a model stop emitting garbage (`<unused49><unused49>...`)? A repeated measurement, not a test.

Gemma 4 12B on GUPPI's llama-server sometimes turns to garbage output partway through a multi-turn session and stays broken until the server
restarts (see docs/PHASE9_STATUS.md). The fault is intermittent, so one run proves nothing. This tool runs the SAME session many times per
variant, each time on a freshly started server, and stops a run at the first garbage answer:

    python benchmarks/garbage_hunt.py <project_dir> [--runs 8] [--modules 14] [--variants baseline,cache_ram0,...] [--model google/gemma-4-12b-qat]

A variant is a set of server options (`profile.server` keys), the flash-attention setting, and extra request fields. The session is the
naive one from workingset_real_run.py (history grows, one fact is asked per module). It talks to the server directly over HTTP, so a
difference to the GUPPI-path runs is itself a result (`direct_baseline` against the 4-in-12 garbage runs seen through `model_call`).
It takes the shared GPU lease and writes one row per run to the test lab (task RUN, ok = the run stayed clean).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

GARBAGE = re.compile(r"(?:<unused\d+>){3,}")
VARIANTS = {
    "baseline": {},
    "cache_ram0": {"server": {"cache_ram": 0}},
    "no_checkpoints": {"server": {"ctx_checkpoints": 0}},
    "cache_prompt_off": {"request": {"cache_prompt": False}},
    "kv_q8": {"server": {"kv_cache_type": "q8_0"}},
    "flash_off": {"flash_attn": "off"},
}


def ask(endpoint, model, messages, extra, timeout=900):
    body = {"model": model, "messages": messages, "max_tokens": 60, "temperature": 0, "reasoning_effort": "none", **extra}
    req = urllib.request.Request(endpoint + "/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    data = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    message = data["choices"][0]["message"]
    return (message.get("content") or "").strip(), data["usage"]["prompt_tokens"], data["choices"][0]["finish_reason"]


def one_run(runtime, recipe, variant, modules):
    """Fresh server, naive session. Returns {"clean": bool, "first_bad": step or None, "wrong": n, "seconds": s}."""
    from workingset_real_run import SYSTEM, session
    server = {**recipe["profile"]["server"], **variant.get("server", {})}
    runtime.config.flash_attn = variant.get("flash_attn", "on")
    runtime.load_model("hunt", context_length=102400, gpu="max", identifier="hunt", parallel=1, server=server)
    started, history, first_bad, wrong = time.time(), [], None, 0
    try:
        for n, (tool_output, question, expected) in enumerate(session(modules)):
            if tool_output:
                history.append({"role": "user", "content": f"[tool result] {tool_output}"})
            messages = [{"role": "system", "content": SYSTEM}] + history + [{"role": "user", "content": question}]
            answer, tokens, finish = ask(runtime.endpoint, "hunt", messages, variant.get("request", {}))
            if GARBAGE.search(answer):
                first_bad = n
                break
            wrong += expected not in answer.replace(",", "")
            history += [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]
    finally:
        runtime.unload_model(all_models=True)
        time.sleep(2)
    return {"clean": first_bad is None, "first_bad": first_bad, "wrong": wrong, "seconds": round(time.time() - started, 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--runs", type=int, default=8)
    ap.add_argument("--modules", type=int, default=14)
    ap.add_argument("--model", default="google/gemma-4-12b-qat")
    ap.add_argument("--variants", default="baseline,cache_ram0,cache_prompt_off,kv_q8,flash_off")
    args = ap.parse_args()
    names = [v for v in args.variants.split(",") if v]
    unknown = [v for v in names if v not in VARIANTS]
    if unknown:
        sys.exit(f"unknown variants {unknown}; known: {sorted(VARIANTS)}")

    import yaml
    from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime
    from guppi_runtime.jobs.testlab import TestLab, default_path
    from guppi_runtime.models.gpu_preflight import clear_leftovers

    recipe = next(c for c in (yaml.safe_load((Path(args.project) / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))["role_routing"]["capabilities"])
                  if c.get("model") == args.model and c.get("provider") == "llama-cpp-server")
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml")
    config.enabled, config.mtp = True, False
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_hunt_")))
    lab = TestLab(default_path(args.project))
    owner = os.environ.get("TESTLAB_OWNER", "garbage_hunt")
    with lab.lease(owner, f"garbage hunt {args.model}", ttl_s=600, wait_s=1800, preflight=clear_leftovers):
        run_id = lab.start_run(owner, "garbage_hunt", f"{args.model} {args.runs}x{args.modules} {','.join(names)}", vars(args))
        try:
            for name in names:
                tally = {"clean": 0, "garbage": 0, "steps": []}
                for i in range(args.runs):
                    result = one_run(runtime, recipe, VARIANTS[name], args.modules)
                    tally["clean" if result["clean"] else "garbage"] += 1
                    if not result["clean"]:
                        tally["steps"].append(result["first_bad"])
                    lab.record(run_id, args.model, variant=name, task="RUN", ok=result["clean"], seconds=result["seconds"], first_bad=result["first_bad"], wrong=result["wrong"])
                    print(f"{name:18s} run {i + 1}/{args.runs}: {'clean' if result['clean'] else 'GARBAGE at step %s' % result['first_bad']} (wrong answers {result['wrong']}, {result['seconds']}s)", flush=True)
                print(f"== {name}: clean {tally['clean']}/{args.runs}, garbage {tally['garbage']} at steps {tally['steps']}\n", flush=True)
        except BaseException:
            lab.finish_run(run_id, "failed")
            raise
        finally:
            runtime.unload_model(all_models=True)
        lab.finish_run(run_id)
    print(f"test lab run {run_id}: python benchmarks/testlab_cli.py summary {run_id}")


if __name__ == "__main__":
    main()
