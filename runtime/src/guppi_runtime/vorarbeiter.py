"""Vorarbeiter-Aktionen für das Entwurfsfenster (Freigabe des Captains, 16.10.2026): dieselben Befugnisse für Cloud- und lokale Modelle.

Feste Liste, keine freien Befehle. Jede Aktion wird protokolliert (Aktion, Ergebnis, ohne Inhalte)."""
from __future__ import annotations
import os
import subprocess
import sys
import time
from pathlib import Path

from . import labor_runs
from .redesign_review import review

LAUFE = {
    "shells": ["-m", "guppi_runtime.redesign_run", "retro", "minimal", "paperclip", "gateway-studio", "guppi-xp", "start"],
    "spec": ["-m", "guppi_runtime.spec_lab", "nemotron-super", "deepseek", "gemma"],
    "pipeline": ["-m", "guppi_runtime.paperclip_pipeline"],
    "cockpit": ["-m", "guppi_runtime.redesign_run", "B"],
    "drache": ["-m", "guppi_runtime.standardlaeufe", "drache"],
    "omni": ["-m", "guppi_runtime.standardlaeufe", "omni"],
}
PRUEFBAR = {"drache_lab", "paperclip_lab"}
SPERRE_S = 6 * 3600           # ein Lauf je Art, nicht doppelt starten


def _lock(project_root, art):
    return Path(project_root) / "redesign" / "vorarbeiter" / f"{art}.lock"


def aktion(project_root, name, args, audit=None):
    args = args if isinstance(args, dict) else {}
    if name == "lauf_status":
        runs = labor_runs.list_runs(project_root)
        ergebnis = {"laeufe": [{k: r[k] for k in ("kind", "name", "status", "model", "calls", "writes")} for r in runs]}
    elif name == "lauf_starten":
        art = str(args.get("lauf") or "")
        if art not in LAUFE: raise ValueError("lauf_unbekannt")
        lock = _lock(project_root, art)
        if lock.exists() and time.time() - lock.stat().st_mtime < SPERRE_S: raise ValueError("lauf_laeuft_schon")
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        src = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(src))
        subprocess.Popen([sys.executable, "-B", *LAUFE[art]], env=env, cwd=str(src),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ergebnis = {"gestartet": art}
    elif name == "pruefen":
        ordner = str(args.get("ordner") or "")
        if ordner not in PRUEFBAR: raise ValueError("ordner_unbekannt")
        befunde = review(Path(project_root) / "redesign" / ordner)
        ergebnis = {"befunde": [{"datei": f, "regel": r, "hinweis": h} for f, r, h in befunde][:40]}
    else:
        raise ValueError("aktion_unbekannt")
    if audit is not None:
        audit.append("VORARBEITER_AKTION", component="vorarbeiter", payload={"aktion": name, "args": {k: str(v)[:40] for k, v in args.items()}})
    return ergebnis
