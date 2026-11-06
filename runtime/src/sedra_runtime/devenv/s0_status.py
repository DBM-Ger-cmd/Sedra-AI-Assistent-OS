"""S0 status per recipe (process "from the bottom up": a model is measured only when its server and connection are proven, docs/PROZESS_GUPPY_VON_UNTEN_2026-10-10.md).

benchmarks/connection_check.py stores the newest result of each recipe in runtime_data/measurements/s0/<recipe>.json together with a fingerprint of the settings that
matter for the connection (model file, KV types, flash attention, batch, offload, MTP, chat template, engine build). status() says whether that result still holds for the
settings a run is about to use: ok, missing, failed or settings_changed. Pure file reads; nothing is started here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

KEYS = ("kv_cache_type", "kv_cache_type_k", "kv_cache_type_v", "flash_attn", "ubatch", "n_cpu_moe", "n_gpu_layers", "mtp", "jinja", "mmap", "mmproj")


def fingerprint(server, engine_build):
    """A short hash of the connection-relevant settings; the model file counts by its name, not its folder."""
    picked = {k: server.get(k) for k in KEYS if server.get(k) is not None}
    picked["gguf"] = str(server.get("gguf") or "").replace("\\", "/").rsplit("/", 1)[-1]     # the file name, whatever the separator of the PC that wrote the recipe
    picked["engine"] = engine_build
    return hashlib.sha256(json.dumps(picked, sort_keys=True).encode()).hexdigest()[:16]


def result_path(project, recipe_id):
    return Path(project) / "runtime_data" / "measurements" / "s0" / f"{recipe_id}.json"


def save(project, recipe_id, result, server, engine_build):
    path = result_path(project, recipe_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**result, "fingerprint": fingerprint(server, engine_build), "engine_build": engine_build}, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def status(project, recipe_id, server, engine_build):
    """{"recipe", "state": ok | missing | failed | settings_changed, "measured_at"}."""
    path = result_path(project, recipe_id)
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"recipe": recipe_id, "state": "missing", "measured_at": None}
    if stored.get("fingerprint") != fingerprint(server, engine_build):
        state = "settings_changed"
    else:
        state = "ok" if stored.get("ok") else "failed"
    return {"recipe": recipe_id, "state": state, "measured_at": stored.get("measured_at")}
