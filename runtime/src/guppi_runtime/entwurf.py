"""Entwürfe aus dem Gespräch mit einem Cloud-Modell: speichern und wieder lesen, nur im Entwurfsordner.

Ein Entwurf ist eine einzelne Datei (html, js oder css). Namen sind fest vorgegeben, Pfade werden nicht übernommen. Die Vorschau
läuft im Browser in einem isolierten Rahmen; hier liegt nur der Text."""
from __future__ import annotations
import re
import time
from pathlib import Path

NAME = re.compile(r"^[a-z0-9_-]{1,40}\.(html|js|css)$")
MAX_BYTES = 300_000


def folder(project_root):
    return Path(project_root) / "redesign" / "entwurf"


def new_name(ext="html"):
    return f"entwurf-{time.strftime('%Y%m%d-%H%M%S')}.{ext}"


def save(project_root, name, content):
    if not isinstance(name, str) or not NAME.match(name): raise ValueError("name_invalid")
    if not isinstance(content, str) or not content.strip(): raise ValueError("content_required")
    data = content.encode("utf-8")
    if len(data) > MAX_BYTES: raise ValueError("content_too_large")
    target = folder(project_root) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"name": name, "bytes": len(data)}


def read(project_root, name):
    if not isinstance(name, str) or not NAME.match(name): raise ValueError("name_invalid")
    target = folder(project_root) / name
    if not target.is_file(): raise ValueError("not_found")
    return {"name": name, "content": target.read_text(encoding="utf-8", errors="replace")}


def listing(project_root):
    base = folder(project_root)
    if not base.is_dir(): return []
    return sorted((p.name for p in base.iterdir() if p.is_file() and NAME.match(p.name)), reverse=True)[:50]
