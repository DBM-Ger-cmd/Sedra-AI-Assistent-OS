r"""S0 connection check per recipe (process "from the bottom up", docs/PROZESS_GUPPY_VON_UNTEN_2026-10-10.md): before a model is measured, prove its server and connection.

    .venv\Scripts\python.exe benchmarks/connection_check.py <project_dir> <recipe_id> [<recipe_id> ...] [--context 32768] [--set KEY=VALUE ...]

--set changes a server setting for this check only (the recipe file is not touched), e.g. --set flash_attn=on --set kv_cache_type=q8_0 --set ubatch=512; the stored S0 state
then holds for exactly these settings (devvm_build compares them with its own --server-set).

For each recipe the server is started exactly as the recipe says (GUPPI's own runtime, GPU canary included), then the checks of guppi_runtime.conn_check run against it
(tool call round trip, 6000-character argument unchanged, answer without garbage or repetition, 90 % window works and 110 % is refused with HTTP 400, prompt cache hit).
Results: runtime_data/measurements/connection_check_<recipe>_<date>.json and one line per recipe. Holds the GPU lease for the whole run. Nothing is changed in any recipe.
conn_check.py was built by GUPPI (night run 2026-10-11); this driver is Claude's.
"""
import argparse
import json
import os
import random
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.conn_check import RequestError, run_all                          # noqa: E402
from guppi_runtime.gpu_preflight import clear_leftovers                              # noqa: E402
from guppi_runtime.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.s0_status import save as save_s0                                  # noqa: E402
from guppi_runtime.testlab import TestLab, default_path                             # noqa: E402

WORDS = "amber basalt cedar delta ember falcon garnet harbor indigo juniper kestrel lumen marble nimbus onyx pebble quartz raven sierra tundra".split()


def poster(endpoint, alias):
    def post(path, body):
        data = json.dumps({**body, "model": alias}).encode()
        req = urllib.request.Request(endpoint + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=900) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise RequestError(exc.code, exc.read().decode("utf-8", "replace")[:300])
    return post


def prompt_maker(endpoint):
    """make_prompt(n): a text of about n tokens of this model. The length is measured with the server's own /tokenize and corrected twice (2026-10-12: a fixed
    words-per-token guess gave 48,600 tokens for 29,500 and the 90 % window was refused for the wrong reason)."""
    def count(text):
        req = urllib.request.Request(endpoint + "/tokenize", data=json.dumps({"content": text}).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return len(json.loads(resp.read())["tokens"])

    def make(n):
        rng = random.Random(n)
        words = [rng.choice(WORDS) for _ in range(max(1, n))]
        size = max(1, n // 2)
        for _ in range(3):
            got = count(" ".join(words[:size]))
            size = max(1, min(len(words), int(size * n / max(1, got))))
        return " ".join(words[:size])
    return make


def check(runtime, recipe, context, server=None):
    alias = str(recipe.get("model") or recipe["id"])
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        runtime.load_model(alias, context_length=context, gpu="max", identifier=alias, parallel=1, server=server or recipe["profile"]["server"])
    except Exception as exc:
        return {"recipe": recipe["id"], "ok": False, "load_error": str(exc)[:300], "checks": [], "context": context, "measured_at": started}
    try:
        out = run_all(poster(runtime.endpoint, alias), alias, context, prompt_maker(runtime.endpoint))
        return {"recipe": recipe["id"], "model": alias, "context": context, "measured_at": started, **out}
    finally:
        runtime.unload_model(all_models=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("recipes", nargs="+"); ap.add_argument("--context", type=int, default=32768)
    ap.add_argument("--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE")
    args = ap.parse_args()
    from devvm_build import server_settings
    overrides = server_settings(args.overrides)
    project = Path(args.project)
    recipes = {r["id"]: r for r in yaml.safe_load((project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))["role_routing"]["capabilities"]}
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_conncheck_")))
    out_dir = project / "runtime_data" / "measurements"; out_dir.mkdir(parents=True, exist_ok=True)
    with TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "connection_check"), f"S0 connection check {','.join(args.recipes)}", ttl_s=1800, wait_s=7200,
                                              preflight=clear_leftovers):
        for rid in args.recipes:
            recipe = recipes.get(rid)
            if not recipe or recipe.get("provider") != "llama-cpp-server":
                print(f"{rid:28s} not a llama-cpp-server recipe, skipped", flush=True); continue
            server = {**recipe["profile"]["server"], **overrides}
            result = check(runtime, recipe, args.context, server)
            result["overrides"] = overrides
            (out_dir / f"connection_check_{rid}_{date.today().isoformat()}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            save_s0(project, rid, result, server, config.engine_build)      # the S0 state that devvm_build reads (s0_status)
            details = " ".join(f"{c['check']}={c['detail']}" for c in result["checks"]) or result.get("load_error", "")
            print(f"{rid:28s} {'OK  ' if result['ok'] else 'FAIL'} {details}", flush=True)


if __name__ == "__main__":
    main()
