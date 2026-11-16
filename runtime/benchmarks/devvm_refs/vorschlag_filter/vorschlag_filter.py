import json
import re

FUELLWOERTER = {"der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "und", "oder", "mit", "für", "fuer", "bitte", "mal", "mach", "ist", "sind", "wie", "was", "wo", "wir", "ich", "du", "zu", "in", "im", "auf", "von", "bei", "nach", "noch", "auch", "jetzt", "dann", "nicht", "kann", "kannst", "soll", "sollst", "mir", "uns"}


def frage_schluessel(frage):
    if not isinstance(frage, str):
        return ""
    woerter = re.findall(r"[0-9a-zäöüß]+", frage.lower())
    return " ".join(w for w in woerter if len(w) >= 3 and w not in FUELLWOERTER)


def korrigierte_lobe(saetze):
    letzte, lob_gesehen = {}, set()
    for s in saetze if isinstance(saetze, list) else []:
        if not isinstance(s, dict) or s.get("urteil") not in ("lob", "korrektur"):
            continue
        k = frage_schluessel(s.get("frage"))
        if not k:
            continue
        letzte[k] = s["urteil"]
        if s["urteil"] == "lob":
            lob_gesehen.add(k)
    return set(k for k, u in letzte.items() if u == "korrektur" and k in lob_gesehen)


def ausblenden_zeile(frage, aus=True):
    if not frage_schluessel(frage):
        raise ValueError("frage")
    return json.dumps({"frage": frage, "aus": bool(aus)}, ensure_ascii=False) + "\n"


def ausgeblendet_lesen(text):
    weg = set()
    if not isinstance(text, str):
        return weg
    for zeile in text.splitlines():
        try:
            d = json.loads(zeile)
        except (ValueError, RecursionError):
            continue
        if not isinstance(d, dict) or not isinstance(d.get("aus"), bool):
            continue
        k = frage_schluessel(d.get("frage"))
        if not k:
            continue
        if d["aus"]:
            weg.add(k)
        else:
            weg.discard(k)
    return weg


def vorschlaege_filtern(vorschlaege, korrigiert, ausgeblendet):
    sperre = set(korrigiert or ()) | set(ausgeblendet or ())
    aus = []
    for v in vorschlaege if isinstance(vorschlaege, list) else []:
        if not isinstance(v, dict):
            continue
        k = frage_schluessel(v.get("frage"))
        if k and k not in sperre:
            aus.append(v)
    return aus
