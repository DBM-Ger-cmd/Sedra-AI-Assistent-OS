"""Spec-Lauf: Modelle entwerfen eine Shell nur aus der Spezifikation (python -m guppi_runtime.spec_lab <name> [<name> ...]).

Jedes Modell bekommt einen eigenen Arbeitsordner mit genau zwei Dateien: der Spezifikation und den Tokens. Es gibt keinen Zugriff
auf bestehende Shells, damit das Ergebnis aus der Beschreibung entsteht und nicht aus Nachahmung. Geschrieben wird nur unter
shells/spec/ im eigenen Ordner. Der Lauf nutzt denselben Inhaltsschutz wie jeder Cloudaufruf."""
from __future__ import annotations
import json
import os
import shutil
import sys
import time
from pathlib import Path

from . import cloud_settings
from .cloud_settings import CloudKeyStore, key_store_path
from .redesign_agent import run_redesign

ROOT = Path(__file__).resolve().parents[3] / "workspace" / "GUPPI_OS"
LIVE_TOKENS = Path(__file__).resolve().parent / "uix" / "ui" / "tokens.css"
SPEC = ROOT / "redesign" / "spec_lab" / "SPEC.md"

MODELS = {
    "nemotron-super": "nvidia/nemotron-3.5-super-vl-120b-a12b",
    "deepseek": "deepseek-ai/deepseek-v4.1-flash",
    "gemma": "google/gemma-4-31b-it",
}
TASK = ("Lies SPEC.md vollständig und setze die Spezifikation um. Entwirf die Shell in drei Dateien unter shells/spec/: "
        "shell.yaml, shell.js und shell.css. Schreibe nur dort. Die Tokens findest du in ui/tokens.css. Beende mit finish.")


class FileAudit:
    def __init__(self, path):
        self.path = path

    def append(self, event, component="", mission_id=None, payload=None, **_):
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.strftime("%H:%M:%S"), "event": event, "component": component,
                                 "payload": payload or {}}, ensure_ascii=False) + "\n")


def prepare(name):
    """Der Arbeitsordner des Modells: nur SPEC.md und ui/tokens.css, sonst nichts."""
    box = ROOT / "redesign" / "spec_lab" / name
    if box.exists(): shutil.rmtree(box)
    (box / "ui").mkdir(parents=True)
    shutil.copy(LIVE_TOKENS, box / "ui" / "tokens.css")
    shutil.copy(SPEC, box / "SPEC.md")
    (box / "shells" / "spec").mkdir(parents=True)
    return box


def run_one(name, config, store):
    model = MODELS[name]
    box = prepare(name)
    log = ROOT / "redesign" / "spec_lab" / f"lauf_{name}.jsonl"
    audit = FileAudit(log)
    audit.append("LAUF_START", component="spec-lab", payload={"name": name, "model": model, "provider": "nvidia", "allow": ["shells/spec"]})
    res = run_redesign(config, "nvidia", model, TASK, box, audit=audit, environ=os.environ, key_store=store, allow=["shells/spec"])
    audit.append("LAUF_ENDE", component="spec-lab", payload={k: v for k, v in res.items() if k != "summary"})
    return dict(res, name=name, model=model, box=str(box))


def main(argv=None):
    names = argv or sys.argv[1:]
    unknown = [n for n in names if n not in MODELS]
    if not names or unknown:
        print("erlaubt:", ", ".join(MODELS)); return 2
    config = cloud_settings.load_config(ROOT)
    store = CloudKeyStore(key_store_path(ROOT))
    for name in names:
        res = run_one(name, config, store)
        print(json.dumps({k: v for k, v in res.items() if k != "summary"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
