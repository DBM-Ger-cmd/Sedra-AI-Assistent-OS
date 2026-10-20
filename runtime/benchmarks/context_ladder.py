"""Safe maximum context window per model on THIS PC (a measurement, not a test). Captain's rule (2026-10-03): safe, and as large as possible.

    .venv\\Scripts\\python.exe benchmarks/context_ladder.py <project_dir> <recipe_id> [<recipe_id> ...] [--max 131072] [--probes 3]

For each recipe (a llama-cpp-server recipe in local_config/role_routing.yaml, started exactly as the recipe says) the window climbs a
ladder (8k, 16k, 24k, 32k, 48k, 64k, 96k, 128k; never above the model's trained context or --max). A rung counts as SAFE only if all hold:
  - the server starts with exactly that window,
  - at least 1 GiB of GPU memory stays free after loading (the same reserve the resource scheduler keeps),
  - <probes> different prompts that fill ~85 % of the window each get a correct answer: a random code hidden at 10 / 50 / 90 % of the
    text must be found ("needle in a haystack"); no HTTP error, no empty answer, no garbage, the server still alive afterwards,
  - no new NVIDIA driver error events (Windows System log, nvlddmkm) while the rung ran.
The ladder stops at the first rung that fails; the safe maximum is the largest rung below it. Results: runtime_data/measurements/
context_ladder_<recipe>_<date>.json. Nothing is changed in any recipe; that is the Captain's decision after reading the results.
Holds the GPU lease (with the usual leftover clean-up) for the whole run.

--set KEY=VALUE changes a server setting for THIS measurement only (the recipe file is not touched), e.g. --set kv_cache_type=f16;
--from <rung> skips the lower rungs (counted as already measured); --tag <name> goes into the result file name.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import string
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.models.gpu_preflight import clear_leftovers                              # noqa: E402
from guppi_runtime.jobs.job_worker import degenerate_reason                              # noqa: E402
from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.models.openai_local import split_harmony                         # noqa: E402
from guppi_runtime.jobs.testlab import TestLab, default_path                             # noqa: E402

LADDER = (8192, 16384, 24576, 32768, 49152, 65536, 98304, 131072)
RESERVE_GIB = 1.0
FILL = 0.85
WORDS = ("amber", "basalt", "cedar", "delta", "ember", "falcon", "garnet", "harbor", "indigo", "juniper", "kestrel", "lumen", "marble",
         "nimbus", "onyx", "pebble", "quartz", "raven", "sierra", "tundra", "umber", "violet", "willow", "xenon", "yarrow", "zephyr")


def gpu_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, check=True).stdout.split(",")
    return int(out[0]), int(out[1])


def driver_events_since(moment):
    """Number of nvlddmkm events (13 = graphics exception, 153 = GPU error) in the System log since `moment`, or None if unreadable."""
    script = ("$e=@(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='nvlddmkm';StartTime=[datetime]'%s'} "
              "-ErrorAction SilentlyContinue); $e.Count" % moment.strftime("%Y-%m-%dT%H:%M:%S"))
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=60)
        return int(out.stdout.strip().splitlines()[-1])
    except Exception:
        return None


def haystack(n_chars, needle, where, rng):
    """Deterministic filler of about n_chars characters with `needle` placed at fraction `where` of the text."""
    parts, size = [], 0
    while size < n_chars:
        s = (f"Record {rng.randint(1000, 99999)}: the {rng.choice(WORDS)} {rng.choice(WORDS)} in sector {rng.randint(1, 900)} "
             f"measured {rng.randint(1, 9999)} units on day {rng.randint(1, 365)}. ")
        parts.append(s); size += len(s)
    at = max(1, int(len(parts) * where))
    parts.insert(at, f"\nIMPORTANT: remember this. {needle}\n")
    return "".join(parts)


def ask(endpoint, alias, prompt, timeout=900):
    body = json.dumps({"model": alias, "messages": [{"role": "user", "content": prompt}], "max_tokens": 2048, "temperature": 0,
                       "reasoning_effort": "low"}).encode()
    req = urllib.request.Request(endpoint + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}: {exc.read()[:300].decode('utf-8', 'replace')}", "seconds": round(time.monotonic() - started, 1)}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}", "seconds": round(time.monotonic() - started, 1)}
    msg = data["choices"][0]["message"]
    content = msg.get("content") or ""
    harmony = split_harmony(content)
    if harmony is not None:
        content = harmony[0]
    return {"content": content, "finish": data["choices"][0].get("finish_reason"), "usage": data.get("usage") or {},
            "seconds": round(time.monotonic() - started, 1)}


def trained_context(runtime):
    """The model's trained context window as the server reports it, or None."""
    for path in ("/v1/models", "/props"):
        try:
            with urllib.request.urlopen(runtime.endpoint + path, timeout=10) as resp:
                data = json.loads(resp.read())
        except Exception:
            continue
        for item in (data.get("data") or [data]):
            meta = item.get("meta") or item
            value = meta.get("n_ctx_train")
            if isinstance(value, int) and value > 0:
                return value
    return None


def rung(runtime, alias, server, tier, probes, chars_per_token, say):
    row = {"context": tier, "probes": []}
    t0 = datetime.now()
    try:
        runtime.load_model(alias, context_length=tier, gpu="max", identifier=alias, parallel=1, server=server)
    except Exception as exc:
        row.update(status="load_failed", error=str(exc)[:300])
        return row, chars_per_token
    try:
        info = (runtime.loaded_models() or [{}])[0]
        row["applied_context"] = info.get("contextLength")
        used, total = gpu_mib()
        row["vram_used_gib"], row["vram_free_gib"] = round(used / 1024, 2), round((total - used) / 1024, 2)
        if row["applied_context"] not in (tier, None):
            row["status"] = "context_mismatch"; return row, chars_per_token
        if row["vram_free_gib"] < RESERVE_GIB:
            row["status"] = "over_reserve"; return row, chars_per_token
        rng = random.Random(tier)
        for i, where in enumerate((0.1, 0.5, 0.9)[:probes]):
            code = "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            vault = rng.randint(100, 999)
            needle = f"The access code for vault {vault} is {code}."
            question = f"\n\nQuestion: what is the access code for vault {vault}? Answer with the code only."
            for _ in range(3):
                n_chars = int(tier * FILL * chars_per_token) - len(question) - 200
                prompt = haystack(n_chars, needle, where, random.Random(f"{tier}-{i}")) + question
                out = ask(runtime.endpoint, alias, prompt)
                # Too long for this tokenizer: a sizing miss of this tool, not a failure of the model. Recalibrate from the
                # server's own count and build the prompt again (2026-10-03: gemma needs ~2.5 characters per token, gpt-oss ~3.4).
                counted = re.search(r'"n_prompt_tokens":(\d+)', out.get("error") or "")
                if not counted:
                    break
                chars_per_token = max(1.0, len(prompt) / int(counted.group(1)) * 0.97)
            used_tokens = (out.get("usage") or {}).get("prompt_tokens")
            if used_tokens:   # calibrate the filler to this model's tokenizer for the next prompts
                chars_per_token = max(1.5, min(6.0, len(prompt) / used_tokens))
            probe = {"where": where, "prompt_tokens": used_tokens, "seconds": out.get("seconds"), "finish": out.get("finish")}
            if "error" in out:
                probe["result"] = "error"; probe["detail"] = out["error"]
            elif not out["content"].strip():
                probe["result"] = "empty"
            elif degenerate_reason(out["content"]):
                probe["result"] = "garbage"; probe["detail"] = out["content"][:120]
            elif code not in out["content"]:
                probe["result"] = "wrong"; probe["detail"] = out["content"][:120]
            else:
                probe["result"] = "ok"
            alive = bool(runtime.loaded_models())
            if not alive:
                probe["result"] = probe["result"] if probe["result"] != "ok" else "server_died"
            # Free memory again after the answer: llama-server allocates compute buffers on the first big prompt, so the value right
            # after loading was too optimistic (2026-10-03: gpt-oss 64k passed at load and then ran with 0.84 GiB free).
            used, total = gpu_mib()
            row["vram_free_min_gib"] = min(row.get("vram_free_min_gib", 99.0), round((total - used) / 1024, 2))
            if probe["result"] == "ok" and row["vram_free_min_gib"] < RESERVE_GIB:
                probe["result"] = "over_reserve_while_working"
            row["probes"].append(probe)
            say(f"      probe {i + 1} @{int(where * 100)}%: {probe['result']}  {used_tokens} tokens  {out.get('seconds')} s")
            if probe["result"] != "ok":
                break
        _, total = gpu_mib()
        events = driver_events_since(t0)
        row["driver_events"] = events
        bad = [p for p in row["probes"] if p["result"] != "ok"]
        row["status"] = ("probe_failed" if bad else "driver_errors" if events else "ok")
        return row, chars_per_token
    finally:
        try:
            runtime.unload_model(all_models=True)
        except Exception:
            pass
        time.sleep(2)


def ladder(runtime, recipe, *, max_ctx, probes, say, start=0, overrides=None):
    server = {**recipe["profile"]["server"], **(overrides or {})}
    alias = str(recipe.get("model") or recipe["id"])
    rows, safe, cpt, trained = [], None, 2.4, None      # start cautious; the first probe calibrates to the model's tokenizer
    for tier in LADDER:
        if tier < start:
            safe = tier
            continue
        if tier > max_ctx or (trained and tier > trained):
            break
        say(f"  ctx {tier:6d}:")
        row, cpt = rung(runtime, alias, server, tier, probes, cpt, say)
        if trained is None and row.get("status") not in ("load_failed",):
            try:
                runtime.load_model(alias, context_length=4096, gpu="max", identifier=alias, parallel=1, server=server)
                trained = trained_context(runtime)
            except Exception:
                trained = None
            finally:
                runtime.unload_model(all_models=True)
        rows.append(row)
        say(f"    -> {row['status']}  (free {row.get('vram_free_gib')} GiB at load, {row.get('vram_free_min_gib')} working, driver events {row.get('driver_events')})")
        if row["status"] != "ok":
            break
        safe = tier
    return {"recipe": recipe["id"], "model": alias, "server": {k: v for k, v in server.items() if k != "gguf"}, "trained_context": trained,
            "overrides": overrides or {}, "started_at_rung": start or None, "reserve_gib": RESERVE_GIB, "fill": FILL, "rows": rows, "safe_max_context": safe,
            "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("recipes", nargs="+")
    ap.add_argument("--max", type=int, default=131072); ap.add_argument("--probes", type=int, default=3, choices=(1, 2, 3))
    ap.add_argument("--from", dest="start", type=int, default=0, choices=(0,) + LADDER)
    ap.add_argument("--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    overrides = {}
    for item in args.overrides:
        key, _, value = item.partition("=")
        overrides[key.strip()] = value if value.strip().lower() in ("on", "off", "auto") else (yaml.safe_load(value) if value else None)   # YAML reads off as False
    project = Path(args.project)
    recipes = {r["id"]: r for r in (yaml.safe_load((project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))
                                    or {})["role_routing"]["capabilities"]}
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled, config.mtp = True, True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_ladder_")))
    out_dir = project / "runtime_data" / "measurements"; out_dir.mkdir(parents=True, exist_ok=True)
    lab = TestLab(default_path(project))
    with lab.lease(os.environ.get("TESTLAB_OWNER", "context_ladder"), f"context ladder {','.join(args.recipes)}", ttl_s=1800, wait_s=1800,
                   preflight=clear_leftovers):
        for rid in args.recipes:
            recipe = recipes.get(rid)
            if not recipe or recipe.get("provider") != "llama-cpp-server":
                print(f"== {rid}: not a llama-cpp-server recipe, skipped", flush=True); continue
            print(f"== {rid} ({recipe.get('model')})", flush=True)
            result = ladder(runtime, recipe, max_ctx=args.max, probes=args.probes, say=lambda s: print(s, flush=True), start=args.start,
                            overrides=overrides)
            tag = f"_{args.tag}" if args.tag else ""
            target = out_dir / f"context_ladder_{rid}{tag}_{date.today().isoformat()}.json"
            target.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"  SAFE MAX: {result['safe_max_context']}  (trained {result['trained_context']})  -> {target.name}", flush=True)


if __name__ == "__main__":
    main()
