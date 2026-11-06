"""Nachmessung der Suche (Spec 7, D7.11): je Suche des Captains ein Protokollsatz ohne Fragetext, später bewertet und abgeschlossen. Ein Teil
von `WissenSpeicher` (Mischklasse); das Protokoll wird immer atomar und unter `self.lock` geschrieben (Auflage 1, Prüfung F6)."""
from __future__ import annotations

import json

from .hilfen import _sha, lies_jsonl, schreibe_atomar

NACHMESSUNG = "nachmessung.jsonl"
URTEILE = ("getroffen", "nicht_getroffen", "ohne_antwort")


class NachmessungTeil:
    def _nachmessung_datei(self):
        return self.pfad.parent / NACHMESSUNG

    def _protokolliere(self, frage, ids, modus):
        try:
            with self.lock:                                                # lesen, anhängen, ersetzen als Ganzes: zwei Suchen verlieren keinen Satz
                p = self._nachmessung_datei()
                bisher = p.read_text(encoding="utf-8") if p.is_file() else ""
                if bisher and not bisher.endswith("\n"):
                    bisher += "\n"
                schreibe_atomar(p, bisher + json.dumps({"zeit": self.uhr(), "frage_sha256": _sha(frage), "ids": ids, "modus": modus}) + "\n")
        except OSError:                                                    # das Protokoll ist ein Nebenzweck: die Suche scheitert nicht daran
            pass

    def nachmessung(self):
        with self.lock:
            return lies_jsonl(self._nachmessung_datei())

    def nachmessung_bewerten(self, frage_sha256, urteil):
        if urteil not in URTEILE:
            raise ValueError("wis_nachmessung_urteil")
        with self.lock:                                                    # unter derselben Sperre wie `_protokolliere`: kein Satz geht verloren (F6)
            saetze = lies_jsonl(self._nachmessung_datei())
            for s in saetze:
                if s.get("frage_sha256") == frage_sha256:
                    s["urteil"] = urteil
            schreibe_atomar(self._nachmessung_datei(), "".join(json.dumps(s) + "\n" for s in saetze))
        return {"frage_sha256": frage_sha256, "urteil": urteil}

    def nachmessung_abschliessen(self):
        """Die bewerteten Fragen zählen, Ergebnis als Datei neben dem Speicher, Audit `WIS_NACHMESSUNG`; das Protokoll beginnt neu."""
        with self.lock:
            return self._nachmessung_abschliessen()

    def _nachmessung_abschliessen(self):
        saetze = lies_jsonl(self._nachmessung_datei())
        bewertet = [s for s in saetze if s.get("urteil") in URTEILE]
        getroffen = sum(1 for s in bewertet if s["urteil"] == "getroffen")
        beantwortbar = [s for s in bewertet if s["urteil"] != "ohne_antwort"]
        anteil = round(getroffen / len(beantwortbar), 4) if beantwortbar else None
        zeiten = [s.get("zeit") for s in saetze if s.get("zeit")]
        ergebnis = {"fragen": len(bewertet), "getroffen": getroffen, "anteil": anteil, "zeitraum": [min(zeiten), max(zeiten)] if zeiten else None, "saetze": bewertet}
        datum = self.uhr()[:10]
        ziel = self.pfad.parent / f"nachmessung_{datum}.json"
        schreibe_atomar(ziel, json.dumps(ergebnis, ensure_ascii=False, indent=1))
        p = self._nachmessung_datei()
        if p.is_file():
            p.unlink()
        self.audit("WIS_NACHMESSUNG", {"fragen": len(bewertet), "getroffen": getroffen, "anteil": anteil, "zeitraum": ergebnis["zeitraum"]})
        return dict(ergebnis, datei=ziel.name)
