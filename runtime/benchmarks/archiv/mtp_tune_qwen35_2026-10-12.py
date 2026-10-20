r"""Repoint and tune the recipe coder.llama_qwen35 onto the Q6_K file WITH the MTP head (Captain 2026-10-12: "stell das Rezept auf die Q6-MTP-Datei um und
optimiere es gleich dabei").

    .venv\Scripts\python.exe benchmarks/mtp_tune_qwen35_2026-10-12.py <project_dir>

1. Waits for the GPU lease (another session may hold it; nothing is stopped), then, holding it:
2. backs up local_config/role_routing.yaml and points coder.llama_qwen35 at unsloth\Qwen3.5-9B-MTP-GGUF\Qwen3.5-9B-Q6_K.gguf with the settings that ran stable
   on the same weights without MTP (night 2026-10-11: engine b11160, flash attention on, KV q8_0, ubatch 512, 1 slot, reasoning off) plus mtp: true.
   The recipe stays switched off (enabled: false); context limits are set by the Captain after the ladder.
3. Speed: MTP on vs off at a 32768 window, the same ~8k-token prompt of GUPPI source and a code-writing task (512 tokens), 2 runs each; tokens/s from
   the server's own timings, free GPU memory after the answer.
Then the context ladder runs separately (it holds the lease itself): benchmarks/context_ladder.py <project> coder.llama_qwen35 --probes 2 --tag mtp_q6.
Results: runtime_data/measurements/mtp_tune_qwen35_2026-10-12.json and the ladder file.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from context_ladder import gpu_mib                                                   # noqa: E402
from moe_sweep import source_text                                                    # noqa: E402
from guppi_runtime.models.gpu_preflight import clear_leftovers                              # noqa: E402
from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.local_paths import expand                                     # noqa: E402
from guppi_runtime.jobs.testlab import TestLab, default_path                             # noqa: E402
from guppi_runtime.core.util import atomic_write_text                                     # noqa: E402

RECIPE = "coder.llama_qwen35"
OLD_GGUF = expand(r"<modelle>\unsloth\Qwen3.5-9B-MTP-GGUF\Qwen3.5-9B-UD-Q4_K_XL.gguf")      # <modelle>: runtime/config/local_paths.yaml
NEW_GGUF = expand(r"<modelle>\unsloth\Qwen3.5-9B-MTP-GGUF\Qwen3.5-9B-Q6_K.gguf")
NEW_SHA = "8ae8fd04e30c5a4af3ef72654729fb0d7f33615cac1ba335dd88084a56287934"
OLD_SERVER = "server: {gguf: '" + OLD_GGUF + "', kv_cache_type: q8_0, mtp: true, reasoning: auto}"
NEW_SERVER = ("server: {gguf: '" + NEW_GGUF + "', kv_cache_type: q8_0, mtp: true, reasoning: 'off', ubatch: 512, flash_attn: 'on'}\n"
              "        # 2026-10-12 (Captain): Q6_K WITH MTP head (7.68 GB; the canary's Q6 without it has 7.46 GB). Settings of the stable night run of the same weights"
              " without MTP (b11160, FA on, KV q8_0, ubatch 512); measured: benchmarks/mtp_tune_qwen35_2026-10-12.py + context ladder tag mtp_q6.")
WINDOW = 32768
TASK = ("\n\nWrite a complete Python module `ring_buffer.py`: a fixed-size ring buffer class with push, pop, peek, __len__, __iter__ and a "
        "thread-safe variant using threading.Lock, plus unittest tests. Only the code.")


def repoint(project):
    path = project / "local_config" / "role_routing.yaml"
    text = path.read_text(encoding="utf-8")
    if NEW_GGUF in text and OLD_SERVER not in text:
        return "already_repointed"
    start = text.index(f"- id: {RECIPE}\n")
    end = text.index("\n    - id: ", start + 1)
    block = text[start:end]
    if block.count(OLD_SERVER) != 1:
        raise SystemExit("recipe block not as expected - nothing changed")
    new = (block.replace(OLD_SERVER, NEW_SERVER)
                .replace("weights_id: sha256:362f85a2d7dbc0259e926d5ac33ca0d0f17fd3753496d65bfd2106384c929d3f", f"weights_id: sha256:{NEW_SHA}")
                .replace("model_size_gb: 5.71", "model_size_gb: 7.16"))
    backup = path.with_name(path.name + ".bak-2026-10-12-before-q6-mtp")
    shutil.copy2(path, backup)
    updated = text[:start] + new + text[end:]
    yaml.safe_load(updated)                                   # must still parse before it replaces the real file
    path.with_name(path.name + ".tmp").unlink(missing_ok=True)
    try:
        atomic_write_text(path, updated)                      # rename, retried while a reader holds the file
    except PermissionError:
        # 2026-10-12 10:07: the rename was refused (a reader without FILE_SHARE_DELETE). Writing in place still works; the backup is above.
        with path.open("r+", encoding="utf-8", newline="") as stream:
            stream.write(updated); stream.truncate()
    if yaml.safe_load(path.read_text(encoding="utf-8")) != yaml.safe_load(updated):
        raise SystemExit("recipe file differs after writing - restore it from " + backup.name)
    return f"repointed (backup {backup.name})"


def one(runtime, alias, server, prompt):
    runtime.load_model(alias, context_length=WINDOW, gpu="max", identifier=alias, parallel=1, server=server)
    try:
        body = json.dumps({"model": alias, "max_tokens": 512, "temperature": 0.1,
                           "messages": [{"role": "user", "content": prompt + TASK}]}).encode()
        req = urllib.request.Request(runtime.endpoint + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=1800) as r:
            data = json.loads(r.read())
        used, total = gpu_mib()
        t = data.get("timings") or {}
        return {"prompt_tokens": (data.get("usage") or {}).get("prompt_tokens"), "gen_tokens": (data.get("usage") or {}).get("completion_tokens"),
                "prompt_tps": round(t.get("prompt_per_second") or 0, 1), "gen_tps": round(t.get("predicted_per_second") or 0, 1),
                "draft_n": t.get("draft_n"), "draft_accepted": t.get("draft_n_accepted"),
                "seconds": round(time.monotonic() - t0, 1), "free_gib": round((total - used) / 1024, 2)}
    finally:
        try:
            runtime.unload_model(all_models=True)
        except Exception:
            pass
        time.sleep(2)


def main():
    project = Path(sys.argv[1])
    out = project / "runtime_data" / "measurements" / "mtp_tune_qwen35_2026-10-12.json"
    result = {"recipe": RECIPE, "gguf": NEW_GGUF, "window": WINDOW, "rows": []}
    print(f"{time.strftime('%H:%M:%S')} waiting for the GPU lease", flush=True)
    with TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "claude_mtp_tune"), "repoint + MTP speed coder.llama_qwen35",
                                              ttl_s=1800, wait_s=6 * 3600, preflight=clear_leftovers):
        result["repoint"] = repoint(project)
        print(f"{time.strftime('%H:%M:%S')} {result['repoint']}", flush=True)
        recipes = {r["id"]: r for r in yaml.safe_load((project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))["role_routing"]["capabilities"]}
        recipe = recipes[RECIPE]
        config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled = True; config.mtp = True
        runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_mtptune_")))
        prompt = source_text(8000 * 3)
        for run in (1, 2):
            for mtp in (True, False):
                server = {**recipe["profile"]["server"], "mtp": mtp}
                try:
                    row = one(runtime, str(recipe["model"]), server, prompt)
                except Exception as exc:
                    row = {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}
                row.update(run=run, mtp=mtp)
                result["rows"].append(row)
                print(f"  run {run} mtp {mtp}: {row}", flush=True)
                out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"{time.strftime('%H:%M:%S')} DONE -> {out.name}", flush=True)


if __name__ == "__main__":
    main()
