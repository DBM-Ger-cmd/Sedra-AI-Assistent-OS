"""Die Läufe im KI Labor: was jeder Lauf tut, gelesen aus den Protokollen (redesign/lauf_*.jsonl und redesign/spec_lab/lauf_*.jsonl).

Nur Lesen. Es steht nichts Geheimes drin: Ereignisse, Modell, Anbieter, Zähler und die geschriebenen Pfade. Keine Prompts,
keine Dateiinhalte. Ein Lauf ohne Abschluss gilt als „läuft“, solange das Protokoll frisch ist; danach als „abgebrochen“."""
from __future__ import annotations
import json
import time
from pathlib import Path


def _events(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


STILL_MIN = 15          # ohne Abschluss und ohne neuen Eintrag so lange, dann gilt der Lauf als abgebrochen


def _status(end, path):
    """Ein Abschluss gilt. Ohne Abschluss: „läuft“, solange das Protokoll frisch ist, sonst „abgebrochen“."""
    if end: return end.get("status") or "beendet"
    age_min = (time.time() - Path(path).stat().st_mtime) / 60
    return "läuft" if age_min < STILL_MIN else "abgebrochen"


def parse_run(path, kind):
    events = _events(path)
    start = next((e["payload"] for e in events if e.get("event") == "LAUF_START"), {})
    end = next((e["payload"] for e in reversed(events) if e.get("event") == "LAUF_ENDE"), None)
    writes = [e["payload"].get("path") for e in events if e.get("event") == "SANDBOX_WRITE"]
    fehlend = (end or {}).get("fehlend") or []
    return {
        "name": Path(path).stem.replace("lauf_", "", 1),
        "kind": kind,
        "model": start.get("model") or "",
        "provider": start.get("provider") or "",
        "allow": start.get("allow") or [],
        "status": _status(end, path),
        "fehlend": fehlend,
        "detail": (end or {}).get("detail") or "",
        "turns": (end or {}).get("turns"),
        "calls": sum(1 for e in events if e.get("event") == "SG_MODEL_CALL"),
        "blocked": sum(1 for e in events if e.get("event") == "SG_BLOCKED"),
        "writes": [w for w in writes if w],
        "last": events[-1].get("t") if events else "",
        "events": len(events),
    }


def list_runs(project_root):
    """Alle Läufe, Umbau-Läufe zuerst. Fehlt der Ordner, gibt es keine Läufe (keine Ausnahme)."""
    base = Path(project_root) / "redesign"
    runs = []
    for path in sorted(base.glob("lauf_*.jsonl")):
        runs.append(parse_run(path, "Umbau"))
    for path in sorted((base / "spec_lab").glob("lauf_*.jsonl")) if (base / "spec_lab").is_dir() else []:
        runs.append(parse_run(path, "Spec"))
    return runs
