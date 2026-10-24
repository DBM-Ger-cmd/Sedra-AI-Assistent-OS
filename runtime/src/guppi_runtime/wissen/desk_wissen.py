"""Der Wissensspeicher am Desk (Spec 7, D7.7 bis D7.9; G2-S7-g, -j, -m, -u): Erweiterung in `desk/extensions.MODULES` mit
`register`, `start` und `snapshot`. Typen `wissen` (ein Objekt `speicher`), `wissen_quelle` und `wissen_vorschlag`; Typ-Verben
`suche` und `nachfuehren` (ohne Gate), `quelle_beantragen` und `erstbestueckung` (Antrag über `desk/gated.py`, ein Gate je Quelle);
an der Quelle `abschalten` und `stufe_heraufsetzen` (nur enger, ohne Gate), am Vorschlag `zuruecknehmen`. Wer liest, bestimmt der
Server: der Captain als `Leser('captain', 6, None)`; Argumente mit `leser`, `stufe` oder `projekt` in `suche` werden abgewiesen.

Die Applier `wissen_quelle` (`_quelle_freigeben`) und `wissen_vorschlag` (`_vorschlag_aufnehmen`, `on_reject` `_vorschlag_abgelehnt`)
laufen erst nach „Freigeben und anwenden“. Ohne Schalter `wissen` stehen die drei Typen als Platzhalter (Objekt `speicher` im Zustand
`aus`, Listen leer, Verben `unknown_object_type`), damit die Seite sagt, warum sie leer ist (UIX-02), statt 400 zu antworten."""
from __future__ import annotations

from ..desk import gated  # noqa: F401 (Antrag mit Gate, D7.8)
from ..desk.actions import Verb
from . import adapter as adapter_mod
from . import aufnahme
from . import speicher as speicher_mod
from .speicher import CAPTAIN, satz

KIND_QUELLE = "wissen_quelle"
KIND_VORSCHLAG = "wissen_vorschlag"
TYPES = ("wissen", KIND_QUELLE, KIND_VORSCHLAG)
TITLES = {"wissen": "Wissen", KIND_QUELLE: "Wissensquelle", KIND_VORSCHLAG: "Wissensvorschlag"}
SPEICHER = "speicher"
ANTRAG = "Antrag liegt im Posteingang"


def speicher_von(hub):
    """Die Instanz der Runtime oder None (Schalter aus, Konfiguration kaputt)."""
    return getattr(getattr(hub, "runtime", None), "wissen", None)


def _need(hub):
    sp = speicher_von(hub)
    if sp is None:
        raise ValueError("unknown_object_type")
    return sp


def _fehler(code):
    return {"status": "fehler", "code": str(code), "satz": satz(code)}


def _obj(typ, oid, title, state, summary, links=(), **felder):
    out = {"type": typ, "id": oid, "title": title, "state": state, "summary": summary, "actions": [], "links": list(links)}
    out.update(felder)
    return out


# ---- Objekte
def speicher_object(sp):
    st = sp.stand()
    state = "neuaufbau" if st["neuaufbau"] and st["bereit"] else st["modus"]
    summary = f"{st['abschnitte']} Abschnitte aus {st['quellen']} Quellen · Abdeckung {round(st['abdeckung'] * 100)} % · {st['modus']}"
    return _obj("wissen", SPEICHER, "Wissen", state, summary, stand=st, saetze={k: satz(k) for k in ("wissen_aus",)})


def quelle_object(q):
    state = "aktiv" if q["aktiv"] else "aus"
    summary = f"{q['adapter']} · Stufe {q['stufe']} · {q['projekt'] or 'alle Projekte'} · {q['abschnitte']} Abschnitte" + (" · Personenbezug" if q["personenbezug"] else "")
    return _obj(KIND_QUELLE, q["id"], f"{q['wurzel']}/{q['pfad']}", state, summary, aktiv=bool(q["aktiv"]), adapter=q["adapter"], wurzel=q["wurzel"], pfad=q["pfad"],
                muster=q["muster"], stufe=q["stufe"], projekt=q["projekt"], personenbezug=bool(q["personenbezug"]), abschnitte=q["abschnitte"], stand=q["stand"],
                freigabe_gate=q["freigabe_gate"], erstellt=q["erstellt"])


def vorschlag_object(v):
    summary = f"von {v['agent_id'] or '?'} · Stufe {v['vorschlag_stufe']} · {len(v['belege'])} Belege" + (" · Personenbezug" if v["personenbezug"] else "")
    links = [{"type": "agent", "id": v["agent_id"]}] if v.get("agent_id") else []
    if v.get("aufgabe_id"):
        links.append({"type": "issue", "id": v["aufgabe_id"]})
    return _obj(KIND_VORSCHLAG, v["id"], v["titel"], v["status"], summary, links, text=v["text"], belege=v["belege"], agent_id=v["agent_id"], lauf_id=v["lauf_id"],
                aufgabe_id=v["aufgabe_id"], stufe=v["vorschlag_stufe"], projekt=v["vorschlag_projekt"], personenbezug=bool(v["personenbezug"]), hash=v["hash"],
                mission_id=v.get("mission_id"), erstellt=v["erstellt"], entschieden=v.get("entschieden"))


def aus_object(hub):
    grund = getattr(getattr(hub, "runtime", None), "wissen_error", None)
    return _obj("wissen", SPEICHER, "Wissen", "aus", satz("wissen_aus") + (" " + str(grund) if grund else ""), stand=None, grund=grund)


def wissen_read(hub, oid):
    if oid != SPEICHER:
        return None
    sp = speicher_von(hub)
    return speicher_object(sp) if sp is not None else aus_object(hub)


def wissen_listing(hub, payload):
    sp = speicher_von(hub)
    return [speicher_object(sp) if sp is not None else aus_object(hub)]


def quelle_read(hub, oid):
    sp = speicher_von(hub)
    q = sp.quelle(oid) if sp is not None else None
    return quelle_object(q) if q else None


def quelle_listing(hub, payload):
    sp = speicher_von(hub)
    return [quelle_object(q) for q in sp.quellen()] if sp is not None else []


def vorschlag_read(hub, oid):
    sp = speicher_von(hub)
    v = sp.vorschlag(oid) if sp is not None else None
    return vorschlag_object(v) if v else None


def vorschlag_listing(hub, payload):
    sp = speicher_von(hub)
    if sp is None:
        return []
    status = (payload or {}).get("status", "offen") or None
    return [vorschlag_object(v) for v in sp.vorschlaege(status)]


def _extra(hub, payload):
    sp = speicher_von(hub)
    return {"quelle": {"zustand": "bereit" if sp is not None else "aus", "grund": getattr(getattr(hub, "runtime", None), "wissen_error", None),
                       "takt": {"laeuft": bool(sp is not None and getattr(sp, "takt_thread", None) is not None and sp.takt_thread.is_alive())}}}


# ---- Verben am Typ wissen
def _suche(hub, oid, args):
    sp = _need(hub)
    if any(k in args for k in ("leser", "stufe", "projekt", "agent_id")):
        return _fehler("wis_leser_vom_server")
    frage = str(args.get("frage") or "")
    k = args.get("k", sp.konfig.k)
    try:
        return {"status": "erledigt", **sp.suche(frage, leser=CAPTAIN, k=k if type(k) is int else sp.konfig.k, route="local")}
    except ValueError as exc:
        return _fehler(exc)


def _nachfuehren(hub, oid, args):
    sp = _need(hub)
    try:
        return {"status": "erledigt", **aufnahme.nachfuehren(sp)}
    except ValueError as exc:
        return _fehler(exc)


def _bindung(sp, args, vorgabe=None):
    b = dict(vorgabe or {})
    for key in ("adapter", "wurzel", "pfad", "muster", "stufe", "projekt", "personenbezug", "art"):
        if key in args:
            b[key] = args[key]
    if "stufe" in b and type(b["stufe"]) is not int:
        try:
            b["stufe"] = int(b["stufe"])
        except (TypeError, ValueError):
            raise ValueError("wis_stufe_ungueltig")
    q = sp.pruefe_quelle(b)
    q["describe"] = f"Wissensquelle freigeben: {q['wurzel']}/{q['pfad']} ({q['adapter']}, Stufe {q['stufe']}" + (", Personenbezug)" if q["personenbezug"] else ")")
    return q


def _ziel(q):
    return f"wissen_quelle:{q['wurzel']}/{q['pfad']}"


def _quelle_beantragen(hub, oid, args):
    """Ein Antrag für eine Quelle (WIS-02): Gate `wissen_quelle_freigeben`, Bindung = die geprüfte Quelle."""
    sp = _need(hub)
    try:
        q = _bindung(sp, args)
    except ValueError as exc:
        return _fehler(exc)
    req = gated.request(hub, KIND_QUELLE, "wissen_quelle_freigeben", _ziel(q), q, risks=[f"Inhalt wird Wissen für Stufe ≥ {q['stufe']}"], rollback_available=True)
    return {"status": "beantragt", "decision_id": "request:" + req["mission_id"], "text": ANTRAG}


def _erstbestueckung(hub, oid, args):
    """Die Erstbestückung (G1-S7-b, G2-S7-l, -m): ein Antrag mit einem Gate je Quelle; `decide` gibt alle frei."""
    sp = _need(hub)
    quellen, gates = [], []
    for vorgabe in adapter_mod.ERSTBESTUECKUNG:
        try:
            q = _bindung(sp, {}, vorgabe)
        except ValueError:
            continue                                      # eine Quelle, die es auf diesem Rechner nicht gibt, fehlt im Antrag
        quellen.append(q)
        gates.append(("wissen_quelle_freigeben", _ziel(q)))
    if not quellen:
        return _fehler("wis_speicher_nicht_lesbar")
    binding = {"quellen": quellen, "describe": f"Erstbestückung des Wissensspeichers: {len(quellen)} Quellen freigeben"}
    req = gated.request(hub, KIND_QUELLE, gates[0][0], gates[0][1], binding, gates=gates, risks=["Doku, Logbuch und die drei Speicher werden Wissen für Stufe ≥ 1"])
    return {"status": "beantragt", "decision_id": "request:" + req["mission_id"], "text": ANTRAG, "quellen": len(quellen)}


def _nachmessung_bewerten(hub, oid, args):
    sp = _need(hub)
    try:
        return {"status": "erledigt", **sp.nachmessung_bewerten(str(args.get("frage_sha256") or ""), str(args.get("urteil") or ""))}
    except ValueError as exc:
        return _fehler(exc)


def _nachmessung_abschliessen(hub, oid, args):
    sp = _need(hub)
    out = sp.nachmessung_abschliessen()
    out.pop("saetze", None)
    return {"status": "erledigt", **out}


def _nachmessung(hub, oid, args):
    return {"status": "erledigt", "saetze": _need(hub).nachmessung()}


# ---- Verben an Quelle und Vorschlag (nur enger, ohne Gate)
def _abschalten(hub, oid, args):
    try:
        return {"status": "erledigt", "quelle": quelle_object(_need(hub).quelle_aendern(oid, aktiv=False))}
    except ValueError as exc:
        return _fehler(exc)


def _stufe_herauf(hub, oid, args):
    sp = _need(hub)
    try:
        stufe = int(args.get("stufe"))
    except (TypeError, ValueError):
        return _fehler("wis_stufe_ungueltig")
    try:
        return {"status": "erledigt", "quelle": quelle_object(sp.quelle_aendern(oid, stufe=stufe))}
    except ValueError as exc:
        return _fehler(exc)


def _neu_beantragen(hub, oid, args):
    """Weiter machen (Stufe herab, Projekt, Personenbezug, wieder einschalten): ein neuer Antrag mit den Werten der Quelle plus `args`."""
    sp = _need(hub)
    q = sp.quelle(oid)
    if q is None:
        return _fehler("wis_quelle_unbekannt")
    return _quelle_beantragen(hub, None, {**{k: q[k] for k in ("adapter", "wurzel", "pfad", "muster", "stufe", "projekt", "personenbezug", "art")}, **args})


def _zuruecknehmen(hub, oid, args):
    try:
        return {"status": "erledigt", **_need(hub).vorschlag_zuruecknehmen(oid)}
    except ValueError as exc:
        return _fehler(exc)


# ---- Applier (desk/gated.py)
def _antrag_von(hub, kind, binding):
    """(mission_id, gate_id) des Antrags, dessen Bindung gerade angewendet wird: der Applier bekommt nur die Bindung, die Quelle
    trägt aber Gate und Mission ihrer Freigabe (D7.2). Ohne passenden Antrag `wis_antrag_unbekannt`: dann entsteht nichts."""
    missionen = hub.runtime.missions.list()                       # ein Lesefehler bricht den Applier ab, statt ohne Freigabe-ID anzulegen
    for m in reversed(missionen):
        req = (m.get("context") or {}).get(gated.CONTEXT) or {}
        if req.get("kind") != kind or req.get("binding") != binding or (m.get("lifecycle") or {}).get("status") == "closed":
            continue                                           # ein früherer, abgelehnter Antrag mit gleicher Bindung zählt nicht
        gates = (m.get("human_gates") or {}).get("resolved") or (m.get("human_gates") or {}).get("pending") or []
        gate_id = gates[0].get("gate_id") if gates else None
        if not gate_id:
            raise ValueError("wis_antrag_unbekannt")
        return m["identity"]["mission_id"], gate_id
    raise ValueError("wis_antrag_unbekannt")                          # nie still mit „gated“ als Freigabe (G4-Auflage 6, Prüfung F8)


def _quelle_freigeben(hub, binding):
    """Applier `wissen_quelle`: eine Quelle oder (Erstbestückung) mehrere; danach ein Abgleich der neuen Quellen."""
    sp = _need(hub)
    mission_id, gate = _antrag_von(hub, KIND_QUELLE, binding)
    quellen = binding.get("quellen") or [binding]
    out = []
    for q in quellen:
        out.append(sp.quelle_freigeben(q, gate_id=gate, mission_id=mission_id))
    for q in out:
        try:
            sp.abgleich(q["id"])
        except ValueError as exc:
            sp.audit("WIS_DATEI_UEBERSPRUNGEN", {"quelle": q["id"], "datei": q["pfad"], "grund": str(exc)})
    return {"quellen": [q["id"] for q in out]}


def _vorschlag_aufnehmen(hub, binding):
    """Applier `wissen_vorschlag`: Vorschlag noch offen und Hash gleich, sonst `binding_stale` (Antrag ohne Wirkung)."""
    mission_id, gate = _antrag_von(hub, KIND_VORSCHLAG, binding)
    return _need(hub).vorschlag_aufnehmen(binding, gate_id=gate, mission_id=mission_id)


def _vorschlag_abgelehnt(hub, binding):
    sp = speicher_von(hub)
    if sp is None:
        return None
    try:
        return sp.vorschlag_ablehnen(str(binding.get("vorschlag_id") or ""))
    except ValueError:
        return None


def vorschlag_beantragen(hub, vorschlag):
    """Vorschlag → Antrag (D7.8 Schritt 2); gibt die Missions-ID zurück. Wird als `speicher.beantrage` eingehängt."""
    binding = {"vorschlag_id": vorschlag["id"], "hash": vorschlag["hash"], "stufe": vorschlag["stufe"], "projekt": vorschlag.get("projekt"),
               "personenbezug": vorschlag.get("personenbezug", 0), "describe": f"Wissen aufnehmen: {vorschlag.get('titel', vorschlag['id'])[:120]}"}
    req = gated.request(hub, KIND_VORSCHLAG, "wissen_vorschlag_aufnehmen", "wissen_vorschlag:" + vorschlag["id"], binding,
                        risks=[f"Text eines Agenten wird Wissen für Stufe ≥ {vorschlag['stufe']}"], rollback_available=True)
    return req["mission_id"]


# ---- Register, Start, Schnappschuss
def register(registry, hub):
    sp = speicher_von(hub)
    if sp is None:                                             # Platzhalter: die Seite sagt „aus“, kein 400
        for name, read, listing in (("wissen", wissen_read, wissen_listing), (KIND_QUELLE, quelle_read, quelle_listing), (KIND_VORSCHLAG, vorschlag_read, vorschlag_listing)):
            registry.register(registry.Kind(name, TITLES[name], read, listing, source="wissen", placeholder=True, extra=_extra))
        return list(TYPES)
    kinds = [
        registry.Kind("wissen", TITLES["wissen"], wissen_read, wissen_listing, source="wissen", extra=_extra, type_verbs=[
            Verb("suche", "Suchen", _suche), Verb("nachfuehren", "Nachführen", _nachfuehren),
            Verb("quelle_beantragen", "Quelle beantragen", _quelle_beantragen, needs_gate=True),
            Verb("erstbestueckung", "Erstbestückung beantragen", _erstbestueckung, needs_gate=True),
            Verb("nachmessung", "Nachmessung lesen", _nachmessung), Verb("nachmessung_bewerten", "Nachmessung bewerten", _nachmessung_bewerten),
            Verb("nachmessung_abschliessen", "Nachmessung abschließen", _nachmessung_abschliessen)]),
        registry.Kind(KIND_QUELLE, TITLES[KIND_QUELLE], quelle_read, quelle_listing, source="wissen", extra=_extra, verbs=[
            Verb("abschalten", "Abschalten", _abschalten, when=lambda o: o.get("aktiv")),
            Verb("stufe_heraufsetzen", "Stufe heraufsetzen", _stufe_herauf, when=lambda o: o.get("aktiv") and o.get("stufe", 6) < 6),
            Verb("neu_beantragen", "Neu beantragen", _neu_beantragen, needs_gate=True)]),
        registry.Kind(KIND_VORSCHLAG, TITLES[KIND_VORSCHLAG], vorschlag_read, vorschlag_listing, source="wissen", extra=_extra, verbs=[
            Verb("zuruecknehmen", "Zurücknehmen", _zuruecknehmen, when=lambda o: o.get("state") == "freigegeben")]),
    ]
    for kind in kinds:
        registry.register(kind)
    gated.register_applier(KIND_QUELLE, _quelle_freigeben, registry=registry)
    gated.register_applier(KIND_VORSCHLAG, _vorschlag_aufnehmen, on_reject=_vorschlag_abgelehnt, registry=registry)
    sp.beantrage = lambda vorschlag: vorschlag_beantragen(hub, vorschlag)
    return list(TYPES)


def start(hub):
    """Der Takt (D7.3): nur mit Schalter `wissen.takt`; `wis_takt_busy`, wenn ein anderer Prozess ihn hält."""
    sp = speicher_von(hub)
    if sp is None or not sp.konfig.takt_an:
        return None
    if getattr(sp, "takt_thread", None) is None:
        sp.takt_thread = aufnahme.start(sp, sp.pfad.parent / aufnahme.LOCK, sp.konfig.takt_intervall_s)
        alt = sp.schliessen

        def schliessen():
            aufnahme.stop(sp.takt_thread)
            alt()
        sp.schliessen = schliessen
    return sp.takt_thread


def snapshot(hub):
    sp = speicher_von(hub)
    if sp is None:
        return {}
    try:
        return {"wissen": sp.stand()}
    except Exception:
        return {}
