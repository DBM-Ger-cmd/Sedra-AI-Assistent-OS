"""Anschluss an den Lauf aus Spec 1 (Spec 7, D7.6, D7.8; G2-S7-f): vor dem ersten Modellaufruf der Modi `arbeit` und `bericht`
der Wissensblock als markierte Daten (`external_block`, `trust: 'untrusted'`) mit dem Systemsatz `SYSTEM_WISSEN`; nach der Antwort
die Zitatprüfung; aus der Antwort das optionale Feld `wissen_vorschlag`. Der Leser kommt aus dem `scope` des Laufs (Stufe =
`min(task.max_level, agent.permission_level)`, Projekt = `tasks.project_id`), die Route aus dem Anbieter des Versuchs (unbekannt
gilt als Cloud, A-9): Treffer mit Personenbezug gehen nie in einen Cloud-Weg (WIS-11). Ohne Treffer bleibt der Lauf, wie er war."""
from __future__ import annotations

from ..orchestra.runner import external_block
from . import ausgabe
from .speicher import leser as leser_von

MAX_FRAGE = 500


def frage_aus_aufgabe(task):
    """Titel und Beschreibung der Aufgabe, höchstens 500 Zeichen."""
    titel = str(task.get("title") or task.get("titel") or "").strip()
    text = str(task.get("description") or task.get("beschreibung") or "").strip()
    return (titel + ("\n" + text if text else ""))[:MAX_FRAGE]


def route_von(router, provider_ref):
    """`local` nur, wenn der Anbieter des Versuchs bekannt ist und keine Cloud-Route trägt; alles andere gilt als Cloud."""
    adapters = getattr(router, "adapters", None) or {}
    adapter = adapters.get(provider_ref) if isinstance(adapters, dict) and provider_ref else None
    if adapter is None:
        return "cloud"
    return "cloud" if getattr(adapter, "route", "local") == "cloud" else "local"


def leser_aus_scope(scope):
    """Der Leser des Laufs (D7.7): Agent mit Stufe und Projekt aus dem `scope`; fehlt die Stufe, gilt 0."""
    stufe = scope.get("level")
    return leser_von("agent", stufe if type(stufe) is int and 0 <= stufe <= 6 else 0, scope.get("project_id") or None, scope.get("agent_id"))


def kontext_nachrichten(speicher, frage, *, leser, route, mission_id):
    """([Systemsatz, Datenblock], Ergebnis) oder ([], Ergebnis|None): ohne Treffer kein Block. Treffer mit Personenbezug werden auf
    dem Cloud-Weg verworfen (`WIS_CLOUD_GEFILTERT`), nie gesendet."""
    k = speicher.konfig
    try:
        ergebnis = speicher.suche(frage, leser=leser, k=k.kontext_treffer, route=route, mission_id=mission_id, protokoll=False)
    except ValueError:
        return [], None
    treffer = list(ergebnis["treffer"])
    if route == "cloud":
        verworfen = [t["id"] for t in treffer if t["personenbezug"]]
        if verworfen:
            speicher.audit("WIS_CLOUD_GEFILTERT", {"mission_id": mission_id, "ids": verworfen})
            treffer = [t for t in treffer if not t["personenbezug"]]
    ergebnis = dict(ergebnis, treffer=treffer)
    if not treffer:
        return [], ergebnis
    marken = bool(getattr(k, "datamarking", False))
    records = ausgabe.datensaetze(treffer, je_treffer=k.je_treffer, gesamt=k.gesamt, hoechstens=k.kontext_treffer, datamarking=marken)
    block = external_block(records, max_chars=k.je_treffer)
    speicher.audit("WIS_KONTEXT", {"mission_id": mission_id, "ids": [t["id"] for t in treffer][:len(records)], "zeichen": len(block), "modus": ergebnis["modus"]})
    system = ausgabe.SYSTEM_WISSEN_MARKIERT if marken else ausgabe.SYSTEM_WISSEN
    return [{"role": "system", "content": system, "trust": "system"}, {"role": "user", "content": block, "trust": "untrusted"}], ergebnis


def block_ids(ergebnis):
    return {t["id"] for t in (ergebnis or {}).get("treffer") or []}


def nachrichten_mit(plan_messages, extra):
    """Die Nachrichten des Plans mit dem Wissensblock: der Systemsatz hinter den Systemnachrichten des Plans, der Block am Ende."""
    if not extra:
        return list(plan_messages)
    msgs = list(plan_messages)
    at = next((i for i, m in enumerate(msgs) if m.get("role") != "system"), len(msgs))
    return msgs[:at] + [extra[0]] + msgs[at:] + extra[1:]


def nachbereite(text, ergebnis, *, mission_id, audit):
    """Zitatprüfung (WIS-07): fremde IDs bekommen den Hinweis (`WIS_ZITAT_FREMD`), keine ID trotz Treffern die Fundstellen
    (`WIS_ZITAT_FEHLT`); ein Hinweis der Suche (Volltext, Abdeckung) hängt immer an."""
    ids = [t["id"] for t in (ergebnis or {}).get("treffer") or []]
    if text is None:
        return ausgabe.schlusstext(None, ids_im_block=ids, hinweis=(ergebnis or {}).get("hinweis"))
    belegt, fremd = ausgabe.pruefe_zitate(text, set(ids))
    if fremd:
        audit("WIS_ZITAT_FREMD", {"mission_id": mission_id, "ids": fremd})
    if ids and not belegt:
        audit("WIS_ZITAT_FEHLT", {"mission_id": mission_id, "ids": ids})
    return ausgabe.schlusstext(text, ids_im_block=ids, hinweis=(ergebnis or {}).get("hinweis"))


def nachbereite_ausgang(out, ergebnis, *, mission_id, audit):
    """`kommentar` und `nachricht` eines Laufergebnisses (`runner.outcome`) mit Zitatprüfung und Hinweis; nur wenn es Treffer gab."""
    if not ergebnis or not ergebnis.get("treffer"):
        return out
    out = dict(out)
    gleich = out.get("nachricht") == out.get("kommentar")
    if out.get("kommentar"):
        out["kommentar"] = nachbereite(out["kommentar"], ergebnis, mission_id=mission_id, audit=audit)
    if out.get("nachricht"):
        out["nachricht"] = out["kommentar"] if gleich else nachbereite(out["nachricht"], ergebnis, mission_id=mission_id, audit=audit)
    return out


def vorschlag_aus_antwort(speicher, antwort, *, scope, block_ids, leser):
    """Das Feld `wissen_vorschlag {titel, text, belege}` einer Antwort → `WissenSpeicher.vorschlagen`; ein falsch geformter oder
    abgewiesener Vorschlag lässt den Lauf nicht scheitern (`WIS_VORSCHLAG_VERWORFEN`)."""
    v = (antwort or {}).get("wissen_vorschlag") if isinstance(antwort, dict) else None
    if v is None:
        return None
    if not isinstance(v, dict) or not isinstance(v.get("titel"), str) or not isinstance(v.get("text"), str) or not isinstance(v.get("belege", []), list):
        speicher.audit("WIS_VORSCHLAG_VERWORFEN", {"mission_id": scope.get("mission_id"), "grund": "form"})
        return None
    try:
        return speicher.vorschlagen(titel=v["titel"], text=v["text"], belege=[str(b) for b in v.get("belege") or []], agent_id=scope.get("agent_id"),
                                    lauf_id=scope.get("run_id") or scope.get("mission_id"), aufgabe_id=scope.get("task_id"), block_ids=set(block_ids), leser=leser)
    except ValueError as exc:
        speicher.audit("WIS_VORSCHLAG_VERWORFEN", {"mission_id": scope.get("mission_id"), "grund": str(exc)})
        return None
