"""Zustand der Cloud-Modelle aus den echten Anfragen (Captain-Vorgabe 16.10.2026).

Jede Anfrage an ein Cloud-Modell merkt sich: antwortet es, und wie schnell. Es werden keine eigenen Testanfragen
geschickt, damit nichts zusätzlich kostet. Die Auswahl zeigt den letzten Stand:
  gruen   antwortet, unter SCHNELL_MS
  gelb    antwortet, aber langsam
  rot     die letzte Anfrage kam nicht durch
  grau    noch keine Anfrage
"""
from __future__ import annotations
import json
import time
from pathlib import Path

SCHNELL_MS = 5000
DATEI = Path("local_config") / "modell_zustand.json"


def _pfad(project_root):
    return Path(project_root) / DATEI


def _lesen(project_root):
    try:
        return json.loads(_pfad(project_root).read_text(encoding="utf-8"))
    except Exception:
        return {}


def ampel(eintrag):
    if not eintrag: return "grau"
    if not eintrag.get("ok"): return "rot"
    return "gruen" if int(eintrag.get("ms") or 0) < SCHNELL_MS else "gelb"


def merken(project_root, provider, model, ok, ms):
    """Eine Anfrage festhalten. Ein Fehler beim Schreiben darf die Antwort nicht verhindern."""
    try:
        daten = _lesen(project_root)
        daten[f"{provider}|{model}"] = {"ok": bool(ok), "ms": int(ms), "zeit": time.strftime("%Y-%m-%d %H:%M:%S")}
        pfad = _pfad(project_root); pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def fuer_anbieter(project_root, provider):
    """Zustand je Modell eines Anbieters: {modell: {ampel, ms, zeit}}."""
    daten = _lesen(project_root)
    out = {}
    for schluessel, eintrag in daten.items():
        pid, _, model = schluessel.partition("|")
        if pid == provider:
            out[model] = {"ampel": ampel(eintrag), "ms": eintrag.get("ms"), "zeit": eintrag.get("zeit")}
    return out
