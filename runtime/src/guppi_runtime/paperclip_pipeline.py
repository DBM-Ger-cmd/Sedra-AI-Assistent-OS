"""Die Paperclip-Pipeline (Testlauf 16.10.2026): Bedarf → Auswahl → Varianten → Prüfung → Entscheidungsvorlage.

Jeder Schritt ist ein eigener Lauf mit eigenem Modell und eigenem Schreibbereich (Sandbox-Verfahren). Eingabe ist nur die
bereitgestellte Bedarfsdatei; die Modelle haben keinen Internetzugang. Die Vorlage wartet auf die Freigabe des Captains."""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

from . import cloud_settings
from .cloud_settings import CloudKeyStore, key_store_path
from .redesign_agent import run_redesign

ROOT = Path(__file__).resolve().parents[3] / "workspace" / "GUPPI_OS"
LAB = ROOT / "redesign" / "paperclip_lab"
COMMON = ("Keine Zahl, kein Objekt und keine Quelle, die nicht in in/bedarf.csv steht. Wo Daten fehlen, schreibe „unbekannt“. "
          "Lies zuerst, dann schreibe die Datei vollständig, und beende mit finish und einer Zusammenfassung.")

STEPS = [
    ("analyst", "nvidia/nemotron-3.5-super-vl-120b-a12b", ["out/bedarf_ranking.md", "out/auswahl.md"],
     "Du bist der Bedarfsanalyst. Lies in/bedarf.csv. Rankt die Objekte nach dem, was die Daten zeigen; jede Platzierung mit "
     "Zeilennummer begründen. Schreibe out/bedarf_ranking.md. Wähle das oberste Objekt und schreibe es mit Begründung in "
     "out/auswahl.md (erste Zeile: „Auswahl: <Objektname>“). " + COMMON),
    ("konstrukteur", "deepseek-ai/deepseek-v4.1-flash", ["out/objekte"],
     "Du bist der Konstrukteur. Lies out/auswahl.md und out/bedarf_ranking.md. Entwirf drei Variationen des gewählten Objekts als "
     "OpenSCAD-Quelltext, je eine Datei unter out/objekte/ (variante_1.scad, variante_2.scad, variante_3.scad). Parameter oben als "
     "Variablen (Maße in mm, Wandstärke, Befestigung), höchstens 200 Zeilen je Datei. Fehlende Maße: Standard angeben und als "
     "Annahme markieren. Nur Variationen des Objekts aus out/auswahl.md. " + COMMON),
    ("prüfer", "google/gemma-4-31b-it", ["out/pruefung.md"],
     "Du bist der Prüfer. Lies alle Dateien unter out/objekte/. Prüfe Syntax (Klammern, Semikola, Befehle), plausible Maße und "
     "Druckbarkeit (Mindestwandstärke, Überhänge). Schreibe jeden Fund mit Datei und Zeile in out/pruefung.md. " + COMMON),
    ("vorlage", "nvidia/nemotron-3-ultra-550b-a55b", ["out/entscheidung.md"],
     "Du schreibst die Entscheidungsvorlage für den Captain. Lies out/bedarf_ranking.md, out/auswahl.md, out/objekte/ und "
     "out/pruefung.md. Schreibe out/entscheidung.md mit: Empfehlung (welche Variante und warum), Begründung mit Bezug auf die "
     "Datenzeilen, offene Annahmen, Risiken. Der Status endet mit „wartet auf Freigabe durch den Captain“. " + COMMON),
]


class FileAudit:
    def __init__(self, path):
        self.path = path

    def append(self, event, component="", mission_id=None, payload=None, **_):
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.strftime("%H:%M:%S"), "event": event, "component": component,
                                 "payload": payload or {}}, ensure_ascii=False) + "\n")


def main(argv=None):
    if not (LAB / "in" / "bedarf.csv").is_file():
        print("keine Datenbasis: in/bedarf.csv fehlt"); return 2
    config = cloud_settings.load_config(ROOT)
    store = CloudKeyStore(key_store_path(ROOT))
    audit = FileAudit(LAB / "lauf_pipeline.jsonl")
    for name, model, allow, task in STEPS:
        audit.append("SCHRITT_START", component="paperclip", payload={"schritt": name, "model": model, "allow": allow})
        res = run_redesign(config, "nvidia", model, task, LAB, audit=audit, environ=os.environ, key_store=store, allow=allow)
        audit.append("SCHRITT_ENDE", component="paperclip", payload={k: v for k, v in res.items() if k != "summary"} | {"schritt": name})
        print(json.dumps({"schritt": name, "status": res.get("status"), "detail": res.get("detail", ""), "writes": res.get("writes", [])}, ensure_ascii=False))
        if res.get("status") != "finished":
            return 1                        # kein Weiterlauf auf unfertige Grundlage
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
