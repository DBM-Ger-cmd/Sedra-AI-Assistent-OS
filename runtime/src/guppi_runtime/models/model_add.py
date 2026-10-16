"""Add a model the short way (Captain 2026-10-14): pick a GGUF file, get a recipe proposed from the file itself, approve it, load it, test it.

Three pure parts, no process and no network:
- `gguf_info(path)` reads the GGUF header (metadata only: architecture, name, context length, layers, experts, quantization) and the file size.
- `propose_recipe(info, path, existing_ids, roles=None)` turns that into a recipe for `local_config/role_routing.yaml` with the defaults of
  MODELLE.md (flash attention on, KV q8_0, ubatch 512) and conservative context tiers; nothing is measured, so `measured_*` stay unset.
- `insert_recipe(text, recipe)` returns the overlay text with the recipe appended under `capabilities:` (comments and other lines untouched)
  and `recipe_yaml(recipe)` the block itself, so the Captain sees exactly what will be written.
The UIX server does the rest behind a gate: backup, write, validate with the real loader, reload the router, audit.
"""
from __future__ import annotations

import datetime
import json
import re
import struct
from pathlib import Path

GGUF_MAGIC = b"GGUF"
ROLES_DEFAULT = ["coder", "planner", "reviewer", "tester"]
TIERS = (4096, 8192, 16384, 32768, 65536, 131072)
DEFAULT_RECOMMENDED = 16384
MAX_HEADER_KV = 4096
MAX_STRING = 1 << 20
FILE_TYPES = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 7: "Q8_0", 8: "Q5_0", 9: "Q5_1", 10: "Q2_K", 11: "Q3_K_S", 12: "Q3_K_M", 13: "Q3_K_L", 14: "Q4_K_S",
              15: "Q4_K_M", 16: "Q5_K_S", 17: "Q5_K_M", 18: "Q6_K", 19: "IQ2_XXS", 20: "IQ2_XS", 21: "Q2_K_S", 22: "IQ3_XS", 23: "IQ3_XXS", 24: "IQ1_S",
              25: "IQ4_NL", 26: "IQ3_S", 27: "IQ3_M", 28: "IQ2_S", 29: "IQ2_M", 30: "IQ4_XS", 31: "IQ1_M", 32: "BF16"}


class GgufError(ValueError):
    pass


def _read(fh, fmt):
    size = struct.calcsize("<" + fmt)
    data = fh.read(size)
    if len(data) != size:
        raise GgufError("gguf_truncated")
    return struct.unpack("<" + fmt, data)


def _string(fh):
    (n,) = _read(fh, "Q")
    if n > MAX_STRING:
        raise GgufError("gguf_string_too_long")
    data = fh.read(n)
    if len(data) != n:
        raise GgufError("gguf_truncated")
    return data.decode("utf-8", errors="replace")


_SCALAR = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}


def _value(fh, kind, depth=0):
    if kind in _SCALAR:
        return _read(fh, _SCALAR[kind])[0]
    if kind == 8:
        return _string(fh)
    if kind == 9:
        if depth > 1:
            raise GgufError("gguf_nested_array")
        (item_kind, count) = _read(fh, "IQ")
        if count > 50_000_000:
            raise GgufError("gguf_array_too_long")
        if item_kind == 8 or count > 64:            # token tables: skip, only keep the length
            skipped = 0
            for _ in range(count):
                if item_kind == 8:
                    (n,) = _read(fh, "Q"); fh.seek(n, 1)
                elif item_kind in _SCALAR:
                    fh.seek(struct.calcsize(_SCALAR[item_kind]), 1)
                else:
                    _value(fh, item_kind, depth + 1)
                skipped += 1
            return {"array_length": skipped}
        return [_value(fh, item_kind, depth + 1) for _ in range(count)]
    raise GgufError(f"gguf_unknown_value_type:{kind}")


def gguf_info(path):
    """{name, architecture, context_length, block_count, expert_count, file_type, quantization, size_gb, version, path} from the header only."""
    p = Path(path)
    if p.suffix.lower() != ".gguf" or not p.is_file():
        raise GgufError("valid_gguf_model_required")
    meta = {}
    with p.open("rb") as fh:
        if fh.read(4) != GGUF_MAGIC:
            raise GgufError("gguf_magic_missing")
        (version,) = _read(fh, "I")
        if version not in (2, 3):
            raise GgufError(f"gguf_version_unsupported:{version}")
        (tensor_count, kv_count) = _read(fh, "QQ")
        if kv_count > MAX_HEADER_KV:
            raise GgufError("gguf_header_too_large")
        for _ in range(kv_count):
            key = _string(fh)
            (kind,) = _read(fh, "I")
            meta[key] = _value(fh, kind)
    arch = str(meta.get("general.architecture") or "unknown")
    get = lambda k: meta.get(f"{arch}.{k}")
    ft = meta.get("general.file_type")
    size_gb = round(p.stat().st_size / 2 ** 30, 2)
    return {"path": str(p), "name": str(meta.get("general.name") or p.stem), "architecture": arch, "version": version, "tensor_count": tensor_count,
            "context_length": int(get("context_length")) if isinstance(get("context_length"), int) else None,
            "block_count": int(get("block_count")) if isinstance(get("block_count"), int) else None,
            "expert_count": int(get("expert_count")) if isinstance(get("expert_count"), int) else 0,
            "file_type": ft, "quantization": FILE_TYPES.get(ft, str(ft) if ft is not None else None), "size_gb": size_gb,
            "size_label": str(meta.get("general.size_label") or ""), "basename": str(meta.get("general.basename") or "")}


def slug(text, limit=40):
    s = re.sub(r"[^a-z0-9._-]+", "-", str(text).lower()).strip("-._")
    s = re.sub(r"-{2,}", "-", s)
    return (s or "modell")[:limit].rstrip("-._") or "modell"


def unique_id(base, existing):
    cid = base
    n = 2
    while cid in existing:
        cid = f"{base}_{n}"; n += 1
    return cid


def propose_recipe(info, path, existing_ids=(), roles=None, today=None):
    """A recipe dict in the shape of config/role_routing.yaml. Conservative: context recommended 16k (or the model's maximum when smaller),
    tiers up to the model's maximum, flash attention on, KV q8_0, ubatch 512, every layer on the GPU, MoE experts on the GPU too (n_cpu_moe is
    the Captain's knob in the Modelle window). Enabled, because the Captain approves exactly this block before it is written."""
    roles = [r for r in (roles or ROLES_DEFAULT) if isinstance(r, str) and re.fullmatch(r"[a-z_]{2,40}", r)] or list(ROLES_DEFAULT)
    stem = slug(Path(path).stem)
    cid = unique_id(f"{roles[0]}.local_{re.sub(r'[^a-z0-9_]+', '_', stem)[:32].strip('_')}", set(existing_ids))
    maximum = info.get("context_length") or 32768
    maximum = max(2048, min(int(maximum), 262144))
    tiers = [t for t in TIERS if t <= maximum] or [maximum]
    recommended = min(DEFAULT_RECOMMENDED, tiers[-1])
    server = {"gguf": str(Path(path)), "kv_cache_type": "q8_0", "flash_attn": "on", "ubatch": 512}
    size = info.get("size_gb") or None
    return {"id": cid, "version": 1, "enabled": True, "roles": roles, "provider": "llama-cpp-server", "model": stem,
            "model_family": info.get("architecture") or "unknown", "weights_id": None, "location": "local",
            "requirements": {"min_ram_gb": 8, "min_vram_gb": 0}, "model_size_gb": size,
            "profile": {"context": {"recommended": recommended, "maximum": maximum, "tiers": tiers}, "gpu_layers": 99, "server": server},
            "permissions": {"max_level": 2}, "network": {"allowed": False}, "tests": ["capability_smoke_test"], "rollback": {"supported": True},
            "metadata": {"source": "captain_custom", "trust_level": "CAPTAIN_CUSTOM", "added_by": "uix",
                         "added_at": today or datetime.date.today().isoformat(), "gguf_name": info.get("name", ""), "quantization": info.get("quantization") or "",
                         "experts": info.get("expert_count", 0)}}


def _y(value):
    """One YAML scalar in flow style; strings are JSON-quoted when they could be read as something else (paths with backslashes, colons)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    s = str(value)
    return s if re.fullmatch(r"[A-Za-z0-9_./-]+", s) and s not in {"null", "true", "false", "yes", "no", "on", "off"} else json.dumps(s, ensure_ascii=False)


def _flow(d):
    return "{" + ", ".join(f"{k}: {_flow(v) if isinstance(v, dict) else ('[' + ', '.join(_y(x) for x in v) + ']' if isinstance(v, list) else _y(v))}" for k, v in d.items()) + "}"


def recipe_yaml(recipe, indent=4):
    """The block as it will stand in the overlay (one list item of `capabilities`, four spaces in like the shipped file)."""
    pad = " " * indent
    lines = [f"{pad}- id: {recipe['id']}"]
    for key in ("version", "enabled"):
        lines.append(f"{pad}  {key}: {_y(recipe[key])}")
    lines.append(f"{pad}  roles: [{', '.join(recipe['roles'])}]")
    for key in ("provider", "model", "model_family", "weights_id", "location"):
        lines.append(f"{pad}  {key}: {_y(recipe[key])}")
    lines.append(f"{pad}  requirements: {_flow(recipe['requirements'])}")
    lines.append(f"{pad}  model_size_gb: {_y(recipe['model_size_gb'])}")
    prof = recipe["profile"]
    lines.append(f"{pad}  profile:")
    lines.append(f"{pad}    context: {_flow(prof['context'])}")
    lines.append(f"{pad}    gpu_layers: {_y(prof['gpu_layers'])}")
    lines.append(f"{pad}    server: {_flow(prof['server'])}")
    for key in ("permissions", "network"):
        lines.append(f"{pad}  {key}: {_flow(recipe[key])}")
    lines.append(f"{pad}  tests: [{', '.join(recipe['tests'])}]")
    lines.append(f"{pad}  rollback: {_flow(recipe['rollback'])}")
    lines.append(f"{pad}  metadata: {_flow(recipe['metadata'])}")
    return "\n".join(lines) + "\n"


HEADER = "# Machine-local recipes of this PC (not in git). Added from the SEDRA desktop: Modelle -> Neues Modell. Changes need the Captain's gate.\nrole_routing:\n  capabilities:\n"


def insert_recipe(text, recipe):
    """The overlay text with the recipe appended to `capabilities:`; a missing file or section is created. Comments stay. Line ending follows the file."""
    block = recipe_yaml(recipe)
    if not text or not text.strip():
        return HEADER + block
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    cap = next((i for i, l in enumerate(lines) if re.match(r"  capabilities:\s*(#.*)?$", l.rstrip("\r\n"))), None)
    if cap is None:
        root = next((i for i, l in enumerate(lines) if l.rstrip("\r\n") == "role_routing:"), None)
        if root is None:
            raise ValueError("overlay_has_no_role_routing_section")
        body = text if text.endswith(("\n",)) else text + eol
        return body + "  capabilities:" + eol + block.replace("\n", eol)
    end = len(lines)
    for i in range(cap + 1, len(lines)):
        t = lines[i].rstrip("\r\n")
        if t.strip() and not t.lstrip().startswith("#") and (len(t) - len(t.lstrip())) <= 2:
            end = i; break
    while end > cap + 1 and not lines[end - 1].strip():
        end -= 1
    if not lines[end - 1].endswith(("\n", "\r\n")):
        lines[end - 1] += eol
    lines.insert(end, block.replace("\n", eol))
    return "".join(lines)
