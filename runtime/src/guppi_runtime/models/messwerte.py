"""Gemessene Speicherwerte je Rezept und Einstellung (SPEC_DYNAMISCHE_REZEPTE_v1 DR-07).

Nach einem Ladevorgang merkt SEDRA, wie viel VRAM und RAM die Einstellung (Lagen im RAM, Kontext) wirklich gebraucht hat; die Auswahl der Aufteilung bevorzugt solche Messwerte vor der
Rechnung. Gespeichert wird nur unter `runtime_data` (atomar, höchstens MAX Einträge, die ältesten fallen heraus) – nie im Rezept, das nur der Captain ändert."""
from __future__ import annotations

import threading
from pathlib import Path

from ..core.util import atomic_write_json, load_json, utcnow

MAX = 200


class Messwerte:
    def __init__(self, pfad):
        self.pfad = Path(pfad)
        self._sperre = threading.Lock()

    def _lesen(self):
        try:
            doc = load_json(self.pfad)
        except Exception:
            return []
        eintraege = doc.get("eintraege") if isinstance(doc, dict) else None
        return [e for e in eintraege if isinstance(e, dict)] if isinstance(eintraege, list) else []

    def fuer(self, rezept_id):
        """{(lagen, kontext): {vram_gb, ram_gb}} – der jüngste Wert je Einstellung."""
        out = {}
        with self._sperre:
            for e in self._lesen():
                try:
                    if e["rezept"] == rezept_id and type(e["lagen"]) is int and type(e["kontext"]) is int:
                        out[(e["lagen"], e["kontext"])] = {"vram_gb": float(e["vram_gb"]), "ram_gb": float(e["ram_gb"])}
                except (KeyError, TypeError, ValueError):
                    continue
        return out

    def merken(self, rezept_id, lagen, kontext, vram_gb, ram_gb):
        """Trägt einen Messwert ein; unsinnige Werte (kein Zahl, nicht über 0) werden nicht gemerkt. True, wenn gemerkt."""
        try:
            vram, ram = float(vram_gb), float(ram_gb)
        except (TypeError, ValueError):
            return False
        if not (vram > 0 and ram > 0) or type(lagen) is not int or type(kontext) is not int:
            return False
        eintrag = {"rezept": str(rezept_id), "lagen": lagen, "kontext": kontext, "vram_gb": round(vram, 3), "ram_gb": round(ram, 3), "zeit": utcnow()}
        with self._sperre:
            alle = [e for e in self._lesen() if not (e.get("rezept") == eintrag["rezept"] and e.get("lagen") == lagen and e.get("kontext") == kontext)]
            alle.append(eintrag)
            self.pfad.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(self.pfad, {"schema": 1, "eintraege": alle[-MAX:]})
        return True
