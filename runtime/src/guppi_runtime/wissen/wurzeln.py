"""Freigegebene Ordner für das Wissen (SPEC_WISSEN_KERN_v1 WK-21, G2 K5 §2.1, Entscheidung D-K5-1): außerhalb von `repo` und `projekt`
darf eine Sammlung nur unter einem Ordner liegen, den der Captain in `local_config/wissen_wurzeln.yaml` eingetragen hat. Die Datei liegt
unter `local_config/**` und ist damit fester Vorbehalt der Harness – ein Modell kann sie nicht ändern. Dieselbe Liste kann die Sandbox lesen.

    wurzeln:
      - {id: kunden, pfad: '<projekte>/Kunden', name: Kundenakten, personenbezug: 1, stufe: 2}

In `quellen.wurzel` steht eine solche Wurzel als `w:<id>`. `personenbezug` und `stufe` sind Untergrenzen für Sammlungen darin (ein Antrag
darf strenger sein, nie lockerer). Rein bis auf das Lesen der Datei: keine Datenbank, kein Audit. Eine kaputte Datei heißt: keine äußeren
Wurzeln und ein Satz in `probleme` – nie ein Absturz des Speichers."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

import yaml

DATEI = ("local_config", "wissen_wurzeln.yaml")
PRAEFIX = "w:"
ID = re.compile(r"[a-z0-9][a-z0-9-]{1,39}")
MAX = 50


@dataclass(frozen=True)
class Wurzel:
    id: str
    pfad: Path
    name: str
    personenbezug: int = 0
    stufe: int = 1

    @property
    def schluessel(self):
        return PRAEFIX + self.id

    def oeffentlich(self):
        """Was ein Modell sehen darf: Kennung und Name, nie der Pfad."""
        return {"wurzel": self.schluessel, "name": self.name, "personenbezug": self.personenbezug, "stufe": self.stufe}


def _absolut(pfad):
    return Path(pfad).is_absolute() or PureWindowsPath(pfad).is_absolute()


def pruefen(doc):
    """(Wurzeln nach Kennung, Probleme) aus dem gelesenen YAML. Ein fehlerhafter Eintrag fällt einzeln weg und steht in den Problemen."""
    if doc in (None, {}):
        return {}, []
    liste = doc.get("wurzeln") if isinstance(doc, dict) else None
    if not isinstance(liste, list):
        return {}, ["wurzeln fehlt oder ist keine Liste"]
    out, probleme = {}, []
    for i, e in enumerate(liste[:MAX]):
        wo = f"Eintrag {i + 1}"
        if not isinstance(e, dict):
            probleme.append(wo + ": kein Objekt"); continue
        wid, pfad = str(e.get("id") or ""), str(e.get("pfad") or "").strip()
        if not ID.fullmatch(wid):
            probleme.append(wo + ": id nur a-z 0-9 - (2 bis 40 Zeichen)"); continue
        if wid in out:
            probleme.append(wo + f": id {wid} doppelt"); continue
        if not pfad or not _absolut(pfad):
            probleme.append(wo + f" ({wid}): pfad muss absolut sein"); continue
        stufe, pb = e.get("stufe", 1), e.get("personenbezug", 0)
        if type(stufe) is not int or not 0 <= stufe <= 6:
            probleme.append(wo + f" ({wid}): stufe 0 bis 6"); continue
        if pb not in (0, 1, True, False):
            probleme.append(wo + f" ({wid}): personenbezug 0 oder 1"); continue
        p = Path(pfad)
        if not p.is_dir():
            probleme.append(wo + f" ({wid}): Ordner nicht gefunden"); continue
        out[wid] = Wurzel(wid, p.resolve(), str(e.get("name") or wid)[:60], int(bool(pb)), stufe)
    if len(liste) > MAX:
        probleme.append(f"mehr als {MAX} Einträge – der Rest gilt nicht")
    return out, probleme


def lesen(projekt_root):
    """Die Wurzeln dieses Rechners: (dict id → Wurzel, Probleme). Fehlt die Datei, gibt es keine äußeren Wurzeln und keine Probleme."""
    datei = Path(projekt_root).joinpath(*DATEI)
    if not datei.is_file():
        return {}, []
    try:
        doc = yaml.safe_load(datei.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        return {}, ["wissen_wurzeln.yaml nicht lesbar: " + (str(exc) or type(exc).__name__)[:160]]
    return pruefen(doc)


def kennung(wurzel_text):
    """'w:kunden' → 'kunden', sonst None."""
    w = str(wurzel_text or "")
    return w[len(PRAEFIX):] if w.startswith(PRAEFIX) and ID.fullmatch(w[len(PRAEFIX):]) else None
