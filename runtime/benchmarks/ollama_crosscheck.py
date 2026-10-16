r"""Cross-check: does the long-context CUDA crash also happen through Ollama (a different engine on the same GPU)? A measurement.

    .venv\Scripts\python.exe benchmarks/ollama_crosscheck.py <project_dir> <ollama_model> [--ctx 65536] [--probes 3] [--fill 0.85]

Captain 2026-10-03: "prüfe ob mit der ollama schnittstelle die fehler auch auftreten bei qwen". GUPPI's llama-server (llama.cpp b11371)
crashed with "CUDA error: an illegal memory access" + nvlddmkm events on qwen3-coder at 64k (2nd probe, ~55.8k tokens) and on
qwen3.5 at >= 23k. Same needle prompts as context_ladder.py, sent to Ollama's own /api/generate (raw ChatML, num_ctx per request).
If Ollama crashes the same way, the GPU/driver is the suspect; if not, llama.cpp's kernels are. Holds the GPU lease.
Result: runtime_data/measurements/ollama_crosscheck_<model>_<date>.json
"""
from __future__ import annotations

import argparse
import json
import os
import random
import string
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from context_ladder import RESERVE_GIB, driver_events_since, gpu_mib, haystack     # noqa: E402
from guppi_runtime.testlab import TestLab, default_path                           # noqa: E402

OLLAMA = "http://127.0.0.1:11434"


def generate(model, prompt, ctx, timeout=1800):
    body = json.dumps({"model": model, "prompt": f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n", "raw": True,
                       "stream": False, "keep_alive": "10m",
                       "options": {"num_ctx": ctx, "num_predict": 64, "temperature": 0}}).encode()
    req = urllib.request.Request(OLLAMA + "/api/generate", data=body, headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
        return {"text": data.get("response", ""), "prompt_tokens": data.get("prompt_eval_count"), "seconds": round(time.monotonic() - t0, 1)}
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}: {exc.read()[:300].decode('utf-8', 'replace')}", "seconds": round(time.monotonic() - t0, 1)}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}", "seconds": round(time.monotonic() - t0, 1)}


def unload(model):
    try:
        body = json.dumps({"model": model, "keep_alive": 0}).encode()
        urllib.request.urlopen(urllib.request.Request(OLLAMA + "/api/generate", data=body, headers={"Content-Type": "application/json"}), timeout=60).read()
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("model")
    ap.add_argument("--ctx", type=int, default=65536); ap.add_argument("--probes", type=int, default=3); ap.add_argument("--fill", type=float, default=0.85)
    args = ap.parse_args()
    project = Path(args.project)
    out = project / "runtime_data" / "measurements" / f"ollama_crosscheck_{args.model.replace(':', '_')}_{date.today().isoformat()}.json"
    rows, cpt = [], 2.4
    t0 = datetime.now()
    with TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "ollama_crosscheck"), f"ollama crosscheck {args.model}",
                                              ttl_s=1800, wait_s=3600):
        rng = random.Random(args.ctx)
        for i, where in enumerate((0.1, 0.5, 0.9, 0.3, 0.7)[:args.probes]):
            code = "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            vault = rng.randint(100, 999)
            question = f"\n\nQuestion: what is the access code for vault {vault}? Answer with the code only."
            prompt = haystack(int(args.ctx * args.fill * cpt) - len(question) - 200, f"The access code for vault {vault} is {code}.", where,
                              random.Random(f"{args.ctx}-{i}")) + question
            res = generate(args.model, prompt, args.ctx)
            if res.get("prompt_tokens"):
                cpt = max(1.5, min(6.0, len(prompt) / res["prompt_tokens"]))
            used, total = gpu_mib()
            res.update(where=where, free_gib=round((total - used) / 1024, 2),
                       result="error" if "error" in res else ("ok" if code in res.get("text", "") else "wrong"))
            res["text"] = res.get("text", "")[:120]
            rows.append(res)
            print(f"  probe {i + 1} @{int(where * 100)}%: {res['result']}  {res.get('prompt_tokens')} tokens  {res['seconds']} s  free {res['free_gib']} GiB"
                  f"  {res.get('error', '')}", flush=True)
            if res["result"] == "error":
                break
        unload(args.model)
        events = driver_events_since(t0)
    result = {"model": args.model, "ctx": args.ctx, "rows": rows, "driver_events": events, "reserve_gib": RESERVE_GIB}
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"  driver events {events}  -> {out.name}", flush=True)


if __name__ == "__main__":
    main()
