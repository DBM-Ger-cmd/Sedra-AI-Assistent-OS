"""Machine-local folders behind placeholders (Captain 2026-10-12: no local paths in the repository).

Files in git name folders as placeholders such as `<modelle>\\unsloth\\x.gguf`. The real folders of THIS PC are in `runtime/config/local_paths.yaml`
(not in git, see .gitignore), for example:

    local_paths:
      modelle: 'E:\\Modelle\\lokale-modelle'

`expand` replaces every known `<name>`; an unknown or missing one stays as it is, so `unresolved` can tell the caller that the folder is not set up on
this PC (the GPU canary is then off, as on any other PC).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

FILE = Path(__file__).resolve().parents[2] / "config" / "local_paths.yaml"
TOKEN = re.compile(r"<([a-z][a-z0-9_-]{0,31})>")


def load(path=None):
    """{name: folder} of this PC; empty when the file is missing. A broken file raises ValueError (it is a configuration error, not a missing setup)."""
    path = Path(path or FILE)
    if not path.exists():
        return {}
    raw = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("local_paths") or {}
    if not isinstance(raw, dict) or any(not isinstance(k, str) or not TOKEN.fullmatch(f"<{k}>") or not isinstance(v, str) or not v for k, v in raw.items()):
        raise ValueError("local_paths_invalid")
    return dict(raw)


def expand(value, paths=None):
    """`value` with every known `<name>` replaced by its folder; anything else unchanged (non-strings too)."""
    if not isinstance(value, str):
        return value
    paths = load() if paths is None else paths
    return TOKEN.sub(lambda m: paths.get(m.group(1), m.group(0)), value)


def unresolved(value):
    """True when a string still holds a `<name>` placeholder after expand."""
    return isinstance(value, str) and TOKEN.search(value) is not None
