"""Startet einen Redesign-Lauf in der Sandbox: python -m guppi_runtime.redesign_run <shell> [<shell> ...]

Jede Shell hat einen eigenen Auftrag, einen eigenen Dateibereich und ein eigenes Modell (Zuordnung in module_models der
Konfiguration, Modul „redesign_<shell>“). So lassen sich die Modelle an derselben Aufgabe vergleichen. Das Protokoll je Lauf
steht in redesign/lauf_<shell>.jsonl. Der Live-Code wird nie berührt; die Übernahme prüft der Vorarbeiter (ich) und der Captain.
"""
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

BASE_RULES = (
    "Regeln, die gelten: Farben nur über die Tokens in ui/tokens.css (--bg, --panel, --panel-2, --line, --text, --muted, --accent, "
    "--ok, --warn, --bad und ihre -bg und -line Varianten). Keine Hex-Werte in deiner Datei. Keine externen Schriften, Bilder oder "
    "Skripte aus dem Netz; Verläufe und Muster nur mit CSS oder inline SVG. Keine Datei länger als 400 Zeilen. Keine Änderung "
    "an Klassennamen oder IDs, die andere Skripte verwenden: lies die Skripte, die deine Datei benutzen, bevor du etwas umbenennst. "
    "Alles muss weiter funktionieren, auch ohne Bewegung (prefers-reduced-motion). Lies zuerst, dann schreibe die Datei vollständig "
    "neu, und beende mit finish und einer kurzen Zusammenfassung dessen, was du verändert hast und warum."
)

# id -> Modul, erlaubte Dateien, Auftrag
SHELLS = {
    "B": {
        "module": "redesign",
        "allow": ["shells/cockpit/shell.css"],
        "task": ("Phase B, Cockpit-Layout. Ändere ausschließlich shells/cockpit/shell.css. Ziel: eine schmale linke Navigation mit "
                 "Gruppen, eine Statusleiste oben, ein zentrales Raster für die Ansicht und eine rechte Detailspalte, die nur erscheint, "
                 "wenn etwas gewählt ist. Das Gespräch bleibt unten. " + BASE_RULES),
    },
    "retro": {
        "module": "redesign_retro",
        "allow": ["retro_desktop.html", "css/desktop.css", "js/desktop.js", "js/desk_drag.js"],
        "task": ("Overhaul der Retro-Oberfläche (Schreibtisch mit Fenstern, Taskleiste und Startmenü). Erlaubt sind nur "
                 "retro_desktop.html, css/desktop.css, js/desktop.js und js/desk_drag.js. Behalte den Retro-Charakter bei: Himmel, "
                 "sanfte Hügel und warme Beige-Töne, wie das SEDRA-Deck. Aber mache es hochwertig statt schlicht: "
                 "(1) Der Himmel und die Hügel werden mit mehrstufigen Verläufen und inline SVG gestaltet, ohne Bilddateien. "
                 "(2) Die Fensterrahmen bekommen eine klare Titelleiste mit Tiefe (ein feiner Schatten, ein heller Rand oben), "
                 "Knöpfe mit sauberen Hover- und Fokuszuständen. "
                 "(3) Die Taskleiste wird ruhiger: eine helle Kante oben, Schaltflächen mit klarem aktiv-Zustand, eine Uhr rechts. "
                 "(4) Das Startmenü bekommt Abstände, Gruppen mit feinen Trennlinien und Hover-Zustände. "
                 "(5) Die Symbole auf dem Schreibtisch werden einheitlich: gleiche Größe, Schatten, Beschriftung mit gutem Kontrast. "
                 "(6) Die Schrift bleibt die Systemschrift; die Größen folgen den Tokens (--size, --size-small). "
                 "(7) Bewegung nur bei Fenstern (kurzes Erscheinen) und Hover, alles aus bei prefers-reduced-motion. "
                 "Ändere in js/desktop.js nur Darstellungsdetails (Klassen, Reihenfolge), keine Logik. " + BASE_RULES),
    },
    "minimal": {
        "module": "redesign_minimal",
        "allow": ["shells/minimal/shell.css"],
        "task": ("Overhaul der Minimal-Shell: freie Fenster statt Reiter, Menüleiste oben, Ablage unten, Entscheidung rechts oben. "
                 "Ziel: ruhig, klar, mit viel Luft und sehr sparsamen Linien. Ändere ausschließlich shells/minimal/shell.css. "
                 "Die Fenster brauchen eine feine Titelleiste mit Schatten, die Menüleiste eine dünne Trennlinie, die Ablage eine "
                 "gleichmäßige Kachelung. " + BASE_RULES),
    },
    "paperclip": {
        "module": "redesign_paperclip",
        "allow": ["shells/paperclip/shell.css"],
        "task": ("Overhaul der Paperclip-Shell: Dashboard mit Posteingang, Organigramm und Issues, Navigation links, Gespräch als "
                 "Schublade. Ändere ausschließlich shells/paperclip/shell.css. Ziel: ein modernes Dashboard mit Karten mit leichter "
                 "Tiefe, klaren Abständen, einer deutlichen aktiven Navigation und einer Schublade mit weichem Übergang. "
                 + BASE_RULES),
    },
    "gateway-studio": {
        "module": "redesign_gateway_studio",
        "allow": ["shells/gateway-studio/shell.yaml", "shells/gateway-studio/shell.vorgabe.yaml"],
        "task": ("Überarbeitung der KI-GateWay-Studio-Shell: Anfrage prüfen, Freigabe, Entwurf, menschliche Prüfung. Ändere nur "
                 "shells/gateway-studio/shell.vorgabe.yaml (die Anordnung der Bereiche und die Beschriftungen, nicht die Schlüssel "
                 "der Verträge). Ziel: eine klare Reihenfolge der vier Schritte, deutliche Zustände (wartet, geprüft, verworfen). "
                 "Lies zuerst die Datei und die README der Shell. " + BASE_RULES),
    },
    "guppi-xp": {
        "module": "redesign_guppi_xp",
        "allow": ["shells/guppi-xp/shell.js"],
        "task": ("Overhaul der GUPPI-XP-Shell (Desktop aus Build 6: Fenster, Karten, Kommandozeile). Ändere nur shells/guppi-xp/shell.js, "
                 "und dort nur die Darstellung (Stile und Aufbau, keine Logik). Ziel: die Fenster wirken wie aus einer ruhigen "
                 "Oberfläche, mit einheitlichen Abständen und klaren Titelleisten. " + BASE_RULES),
    },
    "start": {
        "module": "redesign_start",
        "allow": ["shells/start/shell.css"],
        "task": ("Overhaul der Start-Übersicht: die Karten der Oberflächen mit Vorschaubild, Name, Beschreibung und Knöpfen. "
                 "Ändere ausschließlich shells/start/shell.css. Ziel: ein Raster mit gleichmäßigen Karten, Vorschaubilder mit "
                 "Rahmen und Schatten, eine klare Hervorhebung der laufenden Oberfläche, Knöpfe mit gutem Kontrast. " + BASE_RULES),
    },
}


class FileAudit:
    """Ein Audit-Ersatz für den Lauf: je Ereignis eine Zeile im Protokoll (ohne Inhalt von Prompts oder Dateien)."""
    def __init__(self, path):
        self.path = path

    def append(self, event, component="", mission_id=None, payload=None, **_):
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.strftime("%H:%M:%S"), "event": event, "component": component,
                                 "payload": payload or {}}, ensure_ascii=False) + "\n")


def run_one(shell_id, config, store):
    spec = SHELLS[shell_id]
    chosen = cloud_settings.module_model(config, spec["module"])
    if chosen is None:
        return {"shell": shell_id, "status": "no_model", "detail": f"kein Modell für das Modul {spec['module']} eingetragen"}
    provider, model = chosen
    sandbox = ROOT / "redesign" / "uix"
    log = ROOT / "redesign" / f"lauf_{shell_id}.jsonl"
    audit = FileAudit(log)
    audit.append("LAUF_START", component="redesign", payload={"shell": shell_id, "provider": provider, "model": model,
                                                              "allow": spec["allow"]})
    res = run_redesign(config, provider, model, spec["task"], sandbox, audit=audit, environ=os.environ, key_store=store,
                       allow=spec["allow"])
    audit.append("LAUF_ENDE", component="redesign", payload={k: v for k, v in res.items() if k != "summary"})
    return dict(res, shell=shell_id, model=model)


def main(argv=None):
    ids = argv or sys.argv[1:] or ["B"]
    unknown = [i for i in ids if i not in SHELLS]
    if unknown:
        print("unbekannt:", ", ".join(unknown), "| erlaubt:", ", ".join(SHELLS)); return 2
    config = cloud_settings.load_config(ROOT)
    store = CloudKeyStore(key_store_path(ROOT))
    for shell_id in ids:
        res = run_one(shell_id, config, store)
        print(json.dumps({k: v for k, v in res.items() if k != "summary"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
