import re
from datetime import date

ID = re.compile(r"AAR-([0-9]{4}-[0-9]{2}-[0-9]{2})-[a-z0-9][a-z0-9-]{0,39}", re.ASCII)
BELEG = re.compile(r"A-[0-9A-F]{8}", re.ASCII)
DATUM = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", re.ASCII)
FELDER = ("id", "titel", "bericht", "regeln", "quelle", "belege")
QUELLEN = ("korrektur", "lob", "auftrag")
KOPF = "# Gelernte Regeln"


def _datum_ok(text):
    try:
        if not DATUM.fullmatch(text):
            return False
        date.fromisoformat(text)
        return True
    except ValueError:
        return False


def _id_ok(ident):
    m = ID.fullmatch(ident)
    return bool(m) and _datum_ok(m.group(1))


def antrag_pruefen(p):
    if not isinstance(p, dict):
        return None, ["antrag:typ"]
    fehler = []
    ident = p.get("id")
    if ident is None:
        fehler.append("id:fehlt")
    elif not isinstance(ident, str):
        fehler.append("id:typ")
    elif not _id_ok(ident):
        fehler.append("id:ungueltig")
    titel = p.get("titel")
    if titel is None:
        fehler.append("titel:fehlt")
    elif not isinstance(titel, str):
        fehler.append("titel:typ")
    elif not titel.strip() or len(titel.strip()) > 120 or "\n" in titel.strip() or "\r" in titel.strip():
        fehler.append("titel:ungueltig")
    bericht = p.get("bericht")
    if bericht is None:
        fehler.append("bericht:fehlt")
    elif not isinstance(bericht, str):
        fehler.append("bericht:typ")
    elif not bericht.strip() or len(bericht.strip().splitlines()) > 30:
        fehler.append("bericht:ungueltig")
    regeln = p.get("regeln")
    regeln_aus = []
    if regeln is not None:
        if not isinstance(regeln, list):
            fehler.append("regeln:typ")
        else:
            if len(regeln) > 5:
                fehler.append("regeln:ungueltig")
            for k, r in enumerate(regeln):
                t = r.strip() if isinstance(r, str) else ""
                if not t or len(t) > 200 or "\n" in t or "\r" in t:
                    fehler.append("regeln[%d]:ungueltig" % k)
                else:
                    regeln_aus.append(t)
    quelle = p.get("quelle")
    if quelle is None:
        fehler.append("quelle:fehlt")
    elif not isinstance(quelle, str):
        fehler.append("quelle:typ")
    elif quelle not in QUELLEN:
        fehler.append("quelle:ungueltig")
    belege = p.get("belege")
    belege_aus = []
    if belege is not None:
        if not isinstance(belege, list):
            fehler.append("belege:typ")
        else:
            for k, b in enumerate(belege):
                if not isinstance(b, str) or not BELEG.fullmatch(b):
                    fehler.append("belege[%d]:ungueltig" % k)
                else:
                    belege_aus.append(b)
    for k in sorted(str(k) for k in p if k not in FELDER):
        fehler.append(k + ":unbekannt")
    if fehler:
        return None, fehler
    return {"id": ident, "titel": titel.strip(), "bericht": bericht.strip(), "regeln": regeln_aus, "quelle": quelle, "belege": belege_aus}, []


def lessons_anhaengen(text, antrag_id, regeln, datum):
    if not isinstance(datum, str) or not _datum_ok(datum):
        raise ValueError("datum")
    if not isinstance(antrag_id, str) or not _id_ok(antrag_id):
        raise ValueError("id")
    alt = text if isinstance(text, str) else ""
    vorhanden = set(z.strip() for z in alt.splitlines())
    neu = []
    for r in regeln or []:
        if not isinstance(r, str) or not r.strip():
            continue
        zeile = "- %s: %s (Quelle: %s)" % (datum, r.strip(), antrag_id)
        if zeile not in vorhanden and zeile not in neu:
            neu.append(zeile)
    if not neu:
        return alt
    if not alt.strip():
        basis = KOPF + "\n\n"
    else:
        basis = alt.rstrip("\n") + "\n"
    return basis + "\n".join(neu) + "\n"


def _regelzeilen(text):
    return [z.strip() for z in (text or "").splitlines() if z.strip() and not z.lstrip().startswith("#")]


def lessons_budget(text, hinzu, grenze=25):
    if not isinstance(hinzu, int) or isinstance(hinzu, bool) or hinzu < 0:
        raise ValueError("hinzu")
    jetzt = _regelzeilen(text)
    danach = len(jetzt) + hinzu
    zu_viel = max(0, danach - grenze)
    return {"zeilen_jetzt": len(jetzt), "zeilen_danach": danach, "zu_viel": zu_viel, "archivieren": jetzt[:zu_viel]}
