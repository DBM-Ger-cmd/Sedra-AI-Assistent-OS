"""Skill libraries by name (config/skill_library.yaml): build one from its sources, or find the folder of a built one.

    build_configured("core")          # counts of the import; sources and priority come from the file
    library_path("core")              # runtime/runtime_data/skill_library_core; a folder path is returned as it is

The sources are folders behind placeholders (<skillsets>, see local_paths.py); a placeholder that this PC does not define stops the build with a message instead of importing nothing."""
from __future__ import annotations

from pathlib import Path

import yaml

from .. import local_paths
from . import build_library

RUNTIME = Path(__file__).resolve().parents[3]
FILE = RUNTIME / "config" / "skill_library.yaml"


def load(path=None):
    data = (yaml.safe_load(Path(path or FILE).read_text(encoding="utf-8")) or {}).get("skill_library", {}).get("libraries") or {}
    if not isinstance(data, dict) or not data:
        raise ValueError("skill_library_config_invalid")
    return data


def library_path(value, config=None, runtime=RUNTIME):
    """The folder of a library: `value` is a configured name ("core") or already a folder path. A name that is not configured and is no existing folder raises KeyError."""
    libraries = config if config is not None else load()
    if value in libraries:
        return (Path(runtime) / libraries[value]["output"]).resolve()
    path = Path(value)
    if not path.is_absolute():
        path = Path(runtime) / path
    if (path / "index.json").is_file():
        return path.resolve()
    raise KeyError(value)


def build_configured(name, config=None, runtime=RUNTIME, paths=None):
    libraries = config if config is not None else load()
    if name not in libraries:
        raise KeyError(name)
    entry = libraries[name]
    sources = {}
    for label, folder in (entry.get("sources") or {}).items():
        expanded = local_paths.expand(folder, paths)
        if local_paths.unresolved(expanded):
            raise ValueError(f"source {label}: the folder placeholder in {folder!r} is not set in config/local_paths.yaml")
        if not Path(expanded).is_dir():
            raise ValueError(f"source {label}: folder not found ({expanded})")
        sources[label] = expanded
    if not sources:
        raise ValueError("no sources")
    return build_library(sources, Path(runtime) / entry["output"], source_name=name, license_name=entry.get("license", ""),
                         release=tuple(entry.get("release") or ()), priority=list(sources))
