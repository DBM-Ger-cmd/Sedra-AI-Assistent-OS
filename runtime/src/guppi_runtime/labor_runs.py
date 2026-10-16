"""Die Läufe im KI Labor: was jeder Lauf tut, gelesen aus den Protokollen (redesign/lauf_*.jsonl und redesign/spec_lab/lauf_*.jsonl).

Nur Lesen. Es steht nichts Geheimes drin: Ereignisse, Modell, Anbieter, Zähler und die geschriebenen Pfade. Keine Prompts,
keine Dateiinhalte. Ein Lauf ohne Abschluss gilt als „läuft“."""
from __future__ import annotations
import json
from pathlib import Path


def _events(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def parse_run(path, kind):
    events = _events(path)
    start = next((e["payload"] for e in events if e.get("event") == "LAUF_START"), {})
    end = next((e["payload"] for e in reversed(events) if e.get("event") == "LAUF_ENDE"), None)
    writes = [e["payload"].get("path") for e in events if e.get("event") == "SANDBOX_WRITE"]
    return {
        "name": Path(path).stem.replace("lauf_", "", 1),
        "kind": kind,
        "model": start.get("model") or "",
        "provider": start.get("provider") or "",
        "allow": start.get("allow") or [],
        "status": (end or {}).get("status") or "läuft",
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
