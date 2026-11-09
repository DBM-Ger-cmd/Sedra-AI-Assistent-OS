"""Der Manager wählt das Cloud-Modell je Aufgabentyp aus den Ergebnissen des Fähigkeitstests (benchmarks/modell_faehigkeiten.py).

Ein Modell kommt nur in Frage, wenn es für den Aufgabentyp den zugehörigen Test bestanden hat. Das feste Berater-Modell
(config/manager/berater.yaml) wird bevorzugt, wenn es in Frage kommt.
"""
import json
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[3] / "config" / "manager"
# Aufgabentyp (gesetze.yaml) -> Prüfung im Fähigkeitstest
PRUEFUNG = {
    "code_und_spec_des_baus": "code",
    "text_und_recherche_ohne_personenbezug": "folgen",
    "3d_anfrage": "obj_wuerfel",
}


def letzter_bericht(ordner):
    dateien = sorted(Path(ordner).glob("faehigkeiten_*.json"))
    if not dateien:
        return []
    return json.loads(dateien[-1].read_text(encoding="utf-8"))


def festes_modell():
    pfad = CONFIG / "berater.yaml"
    if not pfad.exists():
        return None
    return (yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}).get("berater", {}).get("modell")


def waehle_modell(aufgabe_typ, ordner):
    """Gibt den Modellnamen zurück oder None. Keine Wahl ohne belegten Test."""
    pruefung = PRUEFUNG.get(aufgabe_typ)
    if pruefung is None:
        return None
    bestanden = [e["modell"] for e in letzter_bericht(ordner)
                 if e.get("aufgaben", {}).get(pruefung, {}).get("ok")]
    if not bestanden:
        return None
    fest = festes_modell()
    return fest if fest in bestanden else bestanden[0]
