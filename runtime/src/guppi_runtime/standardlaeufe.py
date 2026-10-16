"""Standardläufe aus unseren Gesprächen (16.10.2026): Cockpit-Umbau, Seedrache, OmniRoute-Bewertung.

Jeder Lauf ist ein fester Auftrag mit festem Modell und festem Schreibbereich. Die Vorarbeiter-Liste ruft sie über den Namen auf."""
from __future__ import annotations
import json
import os
import time
from pathlib import Path

from . import cloud_settings
from .cloud_settings import CloudKeyStore, key_store_path
from .redesign_agent import run_redesign

ROOT = Path(__file__).resolve().parents[3] / "workspace" / "GUPPI_OS"


class _Log:
    def __init__(self, path):
        self.path = path

    def append(self, event, component="", mission_id=None, payload=None, **_):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.strftime("%H:%M:%S"), "event": event, "component": component, "payload": payload or {}}, ensure_ascii=False) + "\n")


def _run(name, lab, model, task, allow):
    config = cloud_settings.load_config(ROOT)
    store = CloudKeyStore(key_store_path(ROOT))
    box = ROOT / "redesign" / lab
    log = _Log(box / f"lauf_{name}.jsonl")
    log.append("LAUF_START", payload={"model": model, "provider": "nvidia", "allow": allow})
    res = run_redesign(config, "nvidia", model, task, box, audit=log, environ=os.environ, key_store=store, allow=allow)
    log.append("LAUF_ENDE", payload={k: v for k, v in res.items() if k != "summary"})
    return res


DRACHE_TASK = ("Entwirf den gesamten blauen Seedrachen als eine Datei drache.js: Körper mit Schuppen, Rückenkamm, Kopf mit "
               "beweglichem Unterkiefer und Zähnen, Kiemen, vier Paddelflossen, große Schwanzflosse, Leuchtpunkte, Bläschen. "
               "Schnittstelle sedraDrache.mount(container) mit Promise und stop(). three@0.160.0 über jsdelivr. Keine Hex-Farben. "
               "Höchstens 380 Zeilen. Beende mit finish.")
OMNI_TASK = ("Prüfe, ob das Projekt OmniRoute als Shell und Werkzeuge in SEDRA umsetzbar ist. Lies source/README.md, "
             "source/package.json, source/docs/architecture. Schreibe out/bewertung.md mit: was es ist, nützliche Funktionen als "
             "SEDRA-Werkzeuge mit Quelle, eine Shell-Idee, Aufwand und Risiken (Lizenz MIT, Schlüssel, Gateway-Rolle), eine Empfehlung. "
             "Ändere keinen Code. Beende mit finish.")


def drache():
    return _run("drache", "drache_lab", "nvidia/nemotron-3.5-super-vl-120b-a12b", DRACHE_TASK, ["drache.js"])


def omni():
    return _run("omni", "omni_lab", "nvidia/nemotron-3.5-super-vl-120b-a12b", OMNI_TASK, ["out"])


STANDARD = {"drache": drache, "omni": omni}
