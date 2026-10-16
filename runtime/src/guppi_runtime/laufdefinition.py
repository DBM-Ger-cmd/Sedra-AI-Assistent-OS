"""Frei anlegbare Läufe (Regelwerk Standardläufe, Abschnitt 10).

Eine Lauf-Definition ist eine JSON-Datei unter workspace/GUPPI_OS/redesign/laeufe/<name>.json. Sie beschreibt Auftrag,
Modell, Schreibbereich und Ausgaben. Der Vorarbeiter legt sie an (lauf_anlegen) und startet sie (lauf_starten).
Die sechs festen Läufe aus standardlaeufe.py und vorarbeiter.LAUFE bleiben unverändert.
"""
from __future__ import annotations
import json
import re
import sys
import time
from pathlib import Path

from . import cloud_settings
from .cloud_settings import CloudKeyStore, key_store_path
from .redesign_agent import run_redesign

ROOT = Path(__file__).resolve().parents[3] / "workspace" / "GUPPI_OS"
ART = ("bewerten", "bauen")
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")
MAX_TASK = 4000
MAX_LISTE = 20
PROVIDER = re.compile(r"^[a-z0-9_-]{2,30}$")
MODELL = re.compile(r"^[A-Za-z0-9._/-]{3,120}$")


def _rel(text):
    """Relativer Pfad innerhalb des Labors: kein absoluter Pfad, kein '..'."""
    text = str(text)
    if not text or text.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", text) or ".." in Path(text).parts:
        raise ValueError("pfad_unzulaessig:" + text[:60])
    return text.replace("\\", "/")


def pruefen(defn):
    """Prüft eine Definition und gibt die bereinigte Fassung zurück. Wirft ValueError mit Grund."""
    if not isinstance(defn, dict): raise ValueError("definition_kein_objekt")
    name = str(defn.get("name") or "")
    if not NAME.match(name): raise ValueError("name_unzulaessig")
    art = str(defn.get("art") or "bewerten")
    if art not in ART: raise ValueError("art_unbekannt")
    lab = _rel(defn.get("lab") or "")
    provider = str(defn.get("provider") or "nvidia")
    if not PROVIDER.match(provider): raise ValueError("provider_unzulaessig")
    model = str(defn.get("model") or "")
    if not MODELL.match(model): raise ValueError("modell_unzulaessig")
    task = str(defn.get("task") or "").strip()
    if not task: raise ValueError("auftrag_leer")
    if len(task) > MAX_TASK: raise ValueError("auftrag_zu_lang")
    allow = [_rel(x) for x in (defn.get("allow") or [])]
    outputs = [_rel(x) for x in (defn.get("outputs") or [])]
    if not allow: raise ValueError("schreibbereich_leer")
    if len(allow) > MAX_LISTE or len(outputs) > MAX_LISTE: raise ValueError("liste_zu_lang")
    for out in outputs:
        # eine Ausgabe liegt innerhalb des Schreibbereichs, wenn sie gleich ist oder in einem erlaubten Ordner liegt
        if not any(out == a or out.startswith(a.rstrip("/") + "/") for a in allow):
            raise ValueError("ausgabe_ausserhalb_schreibbereich")
    return {"name": name, "art": art, "beschreibung": str(defn.get("beschreibung") or "")[:300], "lab": lab,
            "provider": provider, "model": model, "task": task, "allow": allow, "outputs": outputs}


def _dir(root):
    return Path(root) / "redesign" / "laeufe"


def anlegen(root, defn):
    """Prüft und speichert eine neue Definition. Bestehende Namen werden nicht überschrieben."""
    clean = pruefen(defn)
    target = _dir(root) / (clean["name"] + ".json")
    if target.exists(): raise ValueError("name_vergeben")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return clean


def laden(root, name):
    if not NAME.match(str(name or "")): raise ValueError("name_unzulaessig")
    path = _dir(root) / (name + ".json")
    if not path.exists(): raise ValueError("lauf_unbekannt")
    return pruefen(json.loads(path.read_text(encoding="utf-8")))


def liste(root):
    out = []
    for path in sorted(_dir(root).glob("*.json")) if _dir(root).exists() else []:
        try:
            d = pruefen(json.loads(path.read_text(encoding="utf-8")))
            out.append({k: d[k] for k in ("name", "art", "beschreibung", "model", "lab")})
        except (ValueError, json.JSONDecodeError):
            out.append({"name": path.stem, "fehler": "ungueltig"})
    return out


class _Log:
    def __init__(self, path):
        self.path = path

    def append(self, event, component="", mission_id=None, payload=None, **_):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.strftime("%H:%M:%S"), "event": event, "component": component,
                                 "payload": payload or {}}, ensure_ascii=False) + "\n")


def ausfuehren(root, defn):
    """Führt eine geprüfte Definition aus. Ausgaben fehlen -> Status 'unvollstaendig' statt 'finished'."""
    import os
    box = Path(root) / "redesign" / defn["lab"]
    log = _Log(box / f"lauf_{defn['name']}.jsonl")
    config = cloud_settings.load_config(Path(root))
    store = CloudKeyStore(key_store_path(Path(root)))
    log.append("LAUF_START", payload={"model": defn["model"], "provider": defn["provider"], "allow": defn["allow"], "art": defn["art"]})
    try:
        res = run_redesign(config, defn["provider"], defn["model"], defn["task"], box, audit=log, environ=os.environ,
                           key_store=store, allow=defn["allow"])
    except Exception as exc:
        # Absturz: der Lauf bekommt trotzdem einen Abschluss, sonst wirkt er im Protokoll ewig wie „läuft“
        res = {"status": "fehler", "detail": f"{type(exc).__name__}:{str(exc)[:160]}", "turns": 0, "writes": []}
    fehlend = [o for o in defn["outputs"] if not (box / o).exists()]
    if res.get("status") == "finished" and fehlend:
        res["status"] = "unvollstaendig"
        res["fehlend"] = fehlend
    log.append("LAUF_ENDE", payload={k: v for k, v in res.items() if k != "summary"})
    return res


def main(argv):
    if len(argv) != 1:
        print("Aufruf: python -m guppi_runtime.laufdefinition <name>")
        return 2
    ausfuehren(ROOT, laden(ROOT, argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
