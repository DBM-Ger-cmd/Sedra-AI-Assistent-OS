"""Fortschritt eines Laufs aus den letzten Zeilen seiner Ausgabe (SPEC_HARNESS_SHELL_v1 HS-31, G2 Stufe 3 §6.3, G3 Stufe 3 N8).

Rein. **Referenz von Claude** – N8 ist der SEDRA-Pilot dieser einen Funktion über die Harness; übernimmt der Captain den Bau, ersetzt er diese Datei.
`lauf.fortschritt_aus` benutzt dieses Modul. Regeln: `zeilen` (zwei Zahlen n/m → Prozent), `prozent` (eine Zahl), `text` (letzte nicht leere Zeile)."""
import re


def _kurz(zeile):
    return zeile if len(zeile) <= 80 else zeile[:79] + "…"


def fortschritt_aus(zeilen, regel):
    if not isinstance(regel, dict):
        return None
    art = regel.get("art")
    gefiltert = [z.strip() for z in (zeilen if isinstance(zeilen, (list, tuple)) else []) if isinstance(z, str) and z.strip()]
    if art == "text":
        return {"prozent": None, "text": _kurz(gefiltert[-1]) if gefiltert else ""}
    if art not in ("zeilen", "prozent"):
        return None
    try:
        muster = re.compile(regel.get("regex"))
    except (TypeError, re.error):
        return None
    for zeile in reversed(gefiltert):
        treffer = muster.search(zeile)
        if not treffer:
            continue
        try:
            if art == "zeilen":
                gesamt = float(treffer.group(2))
                if gesamt <= 0:
                    continue
                prozent = float(treffer.group(1)) / gesamt * 100
            else:
                prozent = float(treffer.group(1))
            return {"prozent": max(0, min(100, int(prozent))), "text": _kurz(zeile)}
        except (ValueError, IndexError, TypeError, OverflowError):
            continue
    return None
