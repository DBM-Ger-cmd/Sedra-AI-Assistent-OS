import hashlib
import re
from datetime import date

ID = re.compile(r"[A-Za-z0-9_-]{8,64}", re.ASCII)
DATUM = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", re.ASCII)
FELDER = ("id", "name", "zweck", "aktionen", "wissensquellen", "geprueft_am")
KLASSE = "external_side_effect"


def _text(wert, pfad, fehler, laenge, einzeilig=False):
    if wert is None:
        fehler.append(pfad + ":fehlt")
        return None
    if not isinstance(wert, str):
        fehler.append(pfad + ":typ")
        return None
    t = wert.strip()
    if not t or len(t) > laenge or (einzeilig and ("\n" in t or "\r" in t)):
        fehler.append(pfad + ":ungueltig")
        return None
    return t


def _liste(wert, pfad, fehler):
    if wert is None:
        return []
    if not isinstance(wert, list):
        fehler.append(pfad + ":typ")
        return []
    aus = []
    for k, x in enumerate(wert):
        if not isinstance(x, str) or not x.strip() or len(x.strip()) > 100:
            fehler.append("%s[%d]:ungueltig" % (pfad, k))
        else:
            aus.append(x.strip())
    return aus


def agent_pruefen(a):
    if not isinstance(a, dict):
        return None, ["agent:typ"]
    fehler = []
    ident = a.get("id")
    if ident is None:
        fehler.append("id:fehlt")
    elif not isinstance(ident, str):
        fehler.append("id:typ")
    elif not ID.fullmatch(ident):
        fehler.append("id:ungueltig")
    name = _text(a.get("name"), "name", fehler, 60)
    zweck = _text(a.get("zweck"), "zweck", fehler, 200, True)
    aktionen = _liste(a.get("aktionen"), "aktionen", fehler)
    quellen = _liste(a.get("wissensquellen"), "wissensquellen", fehler)
    gepr = a.get("geprueft_am")
    if gepr is None:
        fehler.append("geprueft_am:fehlt")
    elif not isinstance(gepr, str):
        fehler.append("geprueft_am:typ")
    else:
        try:
            if not DATUM.fullmatch(gepr):
                raise ValueError
            date.fromisoformat(gepr)
        except ValueError:
            fehler.append("geprueft_am:ungueltig")
    for k in sorted(str(k) for k in a if k not in FELDER):
        fehler.append(k + ":unbekannt")
    if fehler:
        return None, fehler
    return {"id": ident, "name": name, "zweck": zweck, "aktionen": aktionen, "wissensquellen": quellen, "geprueft_am": gepr}, []


def agenten_pruefen(doc):
    if not isinstance(doc, dict) or "agenten" not in doc:
        return None, ["agenten:fehlt"]
    roh = doc["agenten"]
    if not isinstance(roh, list):
        return None, ["agenten:typ"]
    fehler, aus, gesehen = [], [], set()
    for i, a in enumerate(roh):
        p = "agenten[%d]" % i
        if not isinstance(a, dict):
            fehler.append(p + ":typ")
            continue
        agent, fe = agent_pruefen(a)
        ident = a.get("id")
        if isinstance(ident, str) and ID.fullmatch(ident):
            if ident in gesehen:
                fe = ["id:doppelt"] + fe
            gesehen.add(ident)
        fehler.extend(p + "." + x for x in fe)
        aus.append(agent)
    if fehler:
        return None, fehler
    return aus, []


def wirkung(agent):
    aktionen = list(agent.get("aktionen") or [])
    vermerke = []
    if aktionen:
        vermerke.append("wirkt bei Langdock, nicht im Audit von SEDRA sichtbar: " + ", ".join(aktionen))
    return {"klasse": KLASSE, "vermerke": vermerke}


def karten_zeilen(agent):
    w = wirkung(agent)
    return ["Langdock-Agent: " + agent["name"], "Zweck: " + agent["zweck"], "Wirkung: " + w["klasse"] + " - Daten gehen an Langdock hinaus"] + w["vermerke"]


def zulaessig(agent, nur_ohne_aktionen=True):
    if nur_ohne_aktionen and agent.get("aktionen"):
        return False, "agent_hat_aktionen"
    return True, ""


def antwort_kennzeichnen(name, text):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name")
    if not isinstance(text, str):
        raise ValueError("antwort")
    return {"herkunft": "Langdock-Agent " + name.strip(), "text": text, "fremd": True, "loest_verb_aus": False}


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def audit_payload(agent_id, frage, antwort, token, dauer):
    if not isinstance(agent_id, str) or not agent_id:
        raise ValueError("agent")
    if not isinstance(frage, str):
        raise ValueError("frage")
    if not isinstance(antwort, str):
        raise ValueError("antwort")
    t = token if isinstance(token, int) and not isinstance(token, bool) and token >= 0 else None
    d = round(float(dauer), 3) if isinstance(dauer, (int, float)) and not isinstance(dauer, bool) and dauer >= 0 else None
    return {"agent": agent_id, "hash_frage": _hash(frage), "hash_antwort": _hash(antwort), "token": t, "dauer": d}
