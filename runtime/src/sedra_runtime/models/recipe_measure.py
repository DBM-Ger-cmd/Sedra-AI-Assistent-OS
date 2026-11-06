"""Measure a recipe instead of guessing it (Phase 9b).

A routing recipe carries three numbers the scheduler relies on: `measured_vram_gb` (observed at `measured_context`) and
`kv_cache_gb_per_1k_tokens` (how much that grows with the window). Until now they were measured by hand. This module measures them
with the real process: it loads the model the way the recipe says, tier by tier (the smallest window first), reads what the server
really applied, reads the GPU memory, optionally runs one short request (compute buffers grow while the model generates), and unloads.

It measures memory only. It does NOT prove that a window is stable: qwen3.5 loads at 65536 and still crashes with a 23k-token prompt.
`suggested.measured_maximum` is therefore only "the largest window that fits in memory"; the Captain decides what goes into `maximum`.

Nothing here changes a file by itself. `apply_measurements` returns new text for the three numeric lines of one recipe; the caller
(`benchmarks/measure_recipe.py --apply`) writes a backup first.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request

TOKENS_PER_ENTRY = 26          # the filler line below is about this many tokens (measured on qwen and gemma tokenizers)
KEYS = ("measured_context", "measured_vram_gb", "kv_cache_gb_per_1k_tokens")


class MeasureError(Exception):
    def __init__(self, code, detail=None):
        super().__init__(code if detail is None else f"{code}: {detail}")
        self.code = code
        self.detail = detail


def filler_prompt(tokens):
    """About `tokens` tokens of harmless, changing text (no repeated block a cache could collapse)."""
    entries = max(1, int(tokens) // TOKENS_PER_ENTRY)
    return "\n".join(f"Log entry {i}: unit {i % 97} reported value {(i * 7) % 1000} at tick {i * 3}." for i in range(entries))


def http_generate(endpoint, alias, prompt_tokens, timeout=300):
    """One short request through the OpenAI-compatible endpoint. Returns {"prompt_tokens"} or {"error"}; never raises."""
    body = {"model": alias, "messages": [{"role": "user", "content": filler_prompt(prompt_tokens) + "\n\nReply with the word OK."}],
            "max_tokens": 32, "temperature": 0, "reasoning_effort": "none"}
    req = urllib.request.Request(endpoint.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        return {"prompt_tokens": (data.get("usage") or {}).get("prompt_tokens")}
    except Exception as exc:
        return {"error": type(exc).__name__}


def _tiers_of(recipe, tiers):
    if tiers is None:
        tiers = ((recipe.get("profile") or {}).get("context") or {}).get("tiers")
    tiers = sorted({int(t) for t in tiers or []})
    if not tiers or any(t < 512 for t in tiers):
        raise MeasureError("no_valid_tiers")
    return tiers


def measure_recipe(recipe, runtime, read_vram, *, tiers=None, generate=None, probe_tokens=2048, settle_s=1.5, margin_gb=0.3,
                   baseline_max_gb=1.5, sleep=time.sleep, say=lambda line: None):
    """Load `recipe` at each tier and read the GPU. `runtime` needs loaded_models(), load_model(...) and unload_model(all_models=True);
    `read_vram()` returns GiB in use on the GPU; `generate(alias, tokens)` (optional) runs one short request and returns a dict."""
    server = (recipe.get("profile") or {}).get("server")
    if not isinstance(server, dict) or not server.get("gguf"):
        raise MeasureError("recipe_has_no_server_profile", recipe.get("id"))
    tiers = _tiers_of(recipe, tiers)
    if runtime.loaded_models():
        raise MeasureError("model_already_loaded", "unload it first; the baseline must be an idle GPU")
    baseline = read_vram()
    if baseline > baseline_max_gb:
        raise MeasureError("gpu_not_idle", f"{baseline:.2f} GiB in use before the first load (limit {baseline_max_gb}); close what uses the GPU")
    alias = str(recipe.get("model") or recipe.get("id"))
    rows, stopped = [], None
    for tier in tiers:
        row = {"context": tier}
        started = time.monotonic()
        try:
            runtime.load_model(alias, context_length=tier, gpu="max", identifier=alias, parallel=1, server=server)
        except Exception as exc:
            row.update(status="load_failed", error=str(exc)[:200])
            rows.append(row)
            try:
                runtime.unload_model(all_models=True)
            except Exception:
                pass
            stopped = f"load failed at {tier}"
            say(f"  ctx {tier:6d}: load failed ({row['error'][:80]})")
            break
        row["start_seconds"] = round(time.monotonic() - started, 1)
        sleep(settle_s)
        info = (runtime.loaded_models() or [{}])[0]
        row["applied_context"] = info.get("contextLength")
        row["spec_type"] = info.get("spec_type")
        row["kv_cache_type"] = info.get("kv_cache_type")
        row["vram_idle_gb"] = round(read_vram() - baseline, 2)
        row["status"] = "ok" if row["applied_context"] in (tier, None) else "context_mismatch"
        if generate is not None and row["status"] == "ok":
            probe = generate(alias, min(probe_tokens, max(256, tier // 2)))
            row["probe"] = probe
            sleep(0.5)
            after = round(read_vram() - baseline, 2)
            row["vram_after_probe_gb"] = after
            row["probe_growth_gb"] = round(max(0.0, after - row["vram_idle_gb"]), 2)
        runtime.unload_model(all_models=True)
        sleep(2)
        rows.append(row)
        say(f"  ctx {tier:6d}: idle {row['vram_idle_gb']:.2f} GiB" + (f", after probe {row['vram_after_probe_gb']:.2f}" if "vram_after_probe_gb" in row else "") + f" [{row['status']}]")
        if row["status"] != "ok":
            stopped = f"applied context differs at {tier}"
            break
    return {"recipe": recipe.get("id"), "model": alias, "baseline_gb": round(baseline, 2), "rows": rows, "stopped": stopped,
            "suggested": suggest(rows, margin_gb=margin_gb)}


def _peak(row):
    return max(row.get("vram_idle_gb", 0), row.get("vram_after_probe_gb", 0))


def suggest(rows, *, margin_gb=0.3):
    """The three numbers a recipe carries, from the rows that loaded cleanly. Empty when nothing did."""
    good = [r for r in rows if r.get("status") == "ok"]
    if not good:
        return {}
    first, last = good[0], good[-1]
    growth = max((r.get("probe_growth_gb", 0) for r in good), default=0)
    margin = max(margin_gb, round(growth * 1.5, 2))
    out = {"measured_context": first["context"], "measured_vram_gb": round(_peak(first) + margin, 2), "margin_gb": margin,
           "measured_maximum": last["context"],
           "note": "measured_maximum is only the largest window that fit in memory; stability under long prompts is not checked"}
    if len(good) >= 2 and last["context"] > first["context"]:
        rate = (_peak(last) - _peak(first)) / ((last["context"] - first["context"]) / 1000)
        if rate > 0:
            out["kv_cache_gb_per_1k_tokens"] = round(rate, 3)
    return out


def apply_measurements(text, recipe_id, suggested, *, today):
    """New file text with the measured numbers written into ONE recipe's block. Comments elsewhere are untouched; the trailing comment of
    a changed line is replaced by a note of when it was measured. Raises when the recipe or one of its three lines is not found."""
    lines = text.split("\n")
    start = next((i for i, l in enumerate(lines) if re.match(rf"^\s*-\s+id:\s*{re.escape(recipe_id)}\s*(#.*)?$", l)), None)
    if start is None:
        raise MeasureError("recipe_not_in_file", recipe_id)
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = next((i for i in range(start + 1, len(lines)) if re.match(rf"^ {{{indent}}}-\s+id:", lines[i])), len(lines))
    for key in KEYS:
        if key not in suggested:
            continue
        pattern = re.compile(rf"^(\s+{key}:\s*)([0-9.]+)(\s*#.*)?$")
        for i in range(start, end):
            m = pattern.match(lines[i])
            if m:
                lines[i] = f"{m.group(1)}{suggested[key]}        # measured {today} (recipe_measure)"
                break
        else:
            raise MeasureError("recipe_line_missing", f"{recipe_id}: {key}")
    return "\n".join(lines)
