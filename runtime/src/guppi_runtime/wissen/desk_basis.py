"""Was die Wissensbasis braucht (SPEC_SHELL_WISSEN_v1 §4.2 bis §4.6), am Desk neben `desk_wissen.py`:

- der Objekttyp `wissen_abschnitt` (nur lesen, ID `W…`): ein Abschnitt mit dem davor und danach, für das Nachweis-Werkzeug
  `fundstelle`. Derselbe Rechtefilter wie die Suche (`fusion.sql_filter`); der Captain liest mit Stufe 6.
- das eigene Wissen des Captains (W-E3): Notizen als Markdown in `local_config/wissen/notizen/`, zwei Ordner (mit und ohne
  Personenbezug), eine Quelle „Notizen des Captains“ je Ordner, einmal freigegeben (ein Antrag, zwei Gates). Danach schreibt der
  Captain ohne Gate; jede Notiz geht sofort in den Abgleich. Audit `WIS_NOTIZ` ohne Inhalt (nur Aktion, Datei-Kennung, Zeichen).
- der Filter der Suche (§4.5): Quelle, Art, Projekt, Zeitraum – geprüft hier, angewendet im SQL vor dem Ranking (`suche.filter_sql`).
- die Zelle der Leiste (`/api/strip` → `wissen`, §4.3) und „Frag das Wissen“ im Gespräch (§4.6, `antwort_im_gespraech`).

Inhalte gehen nie ins Audit; Personenbezug nie in einen Cloud-Weg: das Gespräch bekommt `personenbezug: true` mit, die Oberfläche
sperrt dann den Cloud-Weg für diese Frage und der Verlauf merkt sich den Eintrag als `nur_lokal`."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import ausgabe, fusion, lauf
from .speicher import CAPTAIN, satz

KIND_ABSCHNITT = "wissen_abschnitt"
ID_MUSTER = re.compile(r"^W[0-9a-f]{10,16}$")
NOTIZEN = "local_config/wissen/notizen"
ORDNER = {True: "mit-personenbezug", False: "allgemein"}
NOTIZ_STUFE = 3
MAX_TITEL, MAX_TEXT = 160, 20000
SAETZE = {
    "wis_abschnitt_unbekannt": "Diesen Abschnitt gibt es nicht (mehr), oder er ist für dich nicht lesbar.",
    "wis_notiz_leer": "Titel und Text der Notiz fehlen.",
    "wis_notiz_zu_lang": "Die Notiz ist zu lang (Titel 160, Text 20 000 Zeichen).",
    "wis_notiz_unbekannt": "Diese Notiz gibt es nicht.",
    "wis_filter_ungueltig": "Der Filter der Suche ist ungültig (Quelle, Art, Projekt, Zeitraum JJJJ-MM-TT).",
}


def _satz(code):
    return SAETZE.get(str(code)) or satz(code)


def fehler(code):
    return {"status": "fehler", "code": str(code), "satz": _satz(code)}


# ---- Abschnitt mit Nachbarn (§4.2)
def abschnitt(sp, aid, leser=CAPTAIN):
    """Der Abschnitt `aid` mit Quelle, Stufe, Personenbezug und den Nachbarn in derselben Datei; `wis_abschnitt_unbekannt`, wenn
    es ihn nicht gibt oder der Leser ihn nicht lesen darf (dieselbe Antwort: kein Hinweis, dass es ihn gibt)."""
    aid = str(aid or "")
    if not ID_MUSTER.match(aid):
        raise ValueError("wis_abschnitt_unbekannt")
    where, params = fusion.sql_filter(leser, "local")
    with sp.lock:
        r = sp.db.execute("SELECT a.*, q.stufe AS q_stufe, q.projekt AS q_projekt, q.personenbezug AS q_pb, q.adapter AS q_adapter, q.wurzel AS q_wurzel, "
                          "q.pfad AS q_pfad FROM abschnitte a JOIN quellen q ON q.id = a.quelle WHERE a.id = ? AND " + where, (aid, *params)).fetchone()
        if r is None:
            raise ValueError("wis_abschnitt_unbekannt")
        nachbar = lambda op, ordnung: sp.db.execute(  # noqa: E731
            f"SELECT id, stelle, text FROM abschnitte WHERE quelle = ? AND datei = ? AND nr {op} ? ORDER BY nr {ordnung} LIMIT 1", (r["quelle"], r["datei"], r["nr"])).fetchone()
        vor, nach = nachbar("<", "DESC"), nachbar(">", "ASC")
    eintrag = lambda n: {"id": n["id"], "stelle": n["stelle"], "text": n["text"][:1200]} if n else None  # noqa: E731
    return {"id": r["id"], "quelle": r["quelle"], "datei": r["datei"], "stelle": r["stelle"], "datum": r["datum"], "text": r["text"],
            "stufe": r["q_stufe"], "projekt": r["q_projekt"], "personenbezug": bool(r["q_pb"]), "adapter": r["q_adapter"],
            "quelle_pfad": f"{r['q_wurzel']}/{r['q_pfad']}", "befunde": list(json.loads(r["befunde"] or "[]")),
            "davor": eintrag(vor), "danach": eintrag(nach)}


def abschnitt_object(a):
    return {"type": KIND_ABSCHNITT, "id": a["id"], "title": a["stelle"][:80], "state": "personenbezug" if a["personenbezug"] else "lesbar",
            "summary": f"{a['datei']} · Stand {str(a['datum'])[:10]} · Stufe {a['stufe']}", "actions": [], "links": [], "abschnitt": a}


# ---- Filter der Suche (§4.5)
DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ARTEN = ("markdown", "text", "logbuch", "knowledge", "arbeitsumfeld", "gateway", "vorschlag")


def filter_pruefen(f):
    """Der Filter als {quellen, arten, projekt, seit, bis} oder None; alles andere `wis_filter_ungueltig`."""
    if f in (None, {}):
        return None
    if not isinstance(f, dict) or set(f) - {"quellen", "arten", "projekt", "seit", "bis"}:
        raise ValueError("wis_filter_ungueltig")
    out = {}
    for key in ("quellen", "arten"):
        v = f.get(key)
        if v in (None, []):
            continue
        if not isinstance(v, list) or len(v) > 50 or not all(isinstance(x, str) and 0 < len(x) <= 40 for x in v):
            raise ValueError("wis_filter_ungueltig")
        if key == "arten" and any(x not in ARTEN for x in v):
            raise ValueError("wis_filter_ungueltig")
        out[key] = list(v)
    if f.get("projekt") not in (None, ""):
        if not isinstance(f["projekt"], str) or len(f["projekt"]) > 80:
            raise ValueError("wis_filter_ungueltig")
        out["projekt"] = f["projekt"]
    for key in ("seit", "bis"):
        if f.get(key) not in (None, ""):
            if not isinstance(f[key], str) or not DATUM.match(f[key]):
                raise ValueError("wis_filter_ungueltig")
            out[key] = f[key]
    return out or None


# ---- Notizen des Captains (§4.4, W-E3)
def _ordner(sp, personenbezug):
    p = sp.projekt_root / Path(*NOTIZEN.split("/")) / ORDNER[bool(personenbezug)]
    p.mkdir(parents=True, exist_ok=True)
    return p


def _quellen_bindung(sp):
    return [sp.pruefe_quelle({"adapter": "markdown", "wurzel": "projekt", "pfad": f"{NOTIZEN}/{ORDNER[pb]}", "muster": "*.md",
                              "stufe": NOTIZ_STUFE, "personenbezug": pb, "art": "ordner"}) for pb in (True, False) if _ordner(sp, pb)]


def _quelle_von(sp, personenbezug):
    qid = sp.quelle_id("projekt", f"{NOTIZEN}/{ORDNER[bool(personenbezug)]}", "markdown")
    q = sp.quelle(qid)
    return q if q and q["aktiv"] else None


def _antrag_offen(hub):
    from ..desk import gated
    try:
        missionen = hub.runtime.missions.list()
    except Exception:
        return None
    for m in reversed(missionen):
        req = (m.get("context") or {}).get(gated.CONTEXT) or {}
        if req.get("kind") == "wissen_quelle" and str((req.get("binding") or {}).get("describe", "")).startswith("Notizen des Captains") \
                and (m.get("human_gates") or {}).get("pending") and (m.get("lifecycle") or {}).get("status") != "closed":
            return m["identity"]["mission_id"]
    return None


def notizen_freigabe(hub, sp):
    """Ist „Notizen des Captains“ freigegeben? Sonst genau ein Antrag (ein Gate je Ordner) – ein offener wird nicht verdoppelt."""
    if _quelle_von(sp, True) and _quelle_von(sp, False):
        return None
    offen = _antrag_offen(hub)
    if offen:
        return "request:" + offen
    from ..desk import gated
    quellen = _quellen_bindung(sp)
    gates = [("wissen_quelle_freigeben", f"wissen_quelle:{q['wurzel']}/{q['pfad']}") for q in quellen]
    binding = {"quellen": quellen, "describe": "Notizen des Captains als Wissensquelle freigeben (einmal; danach ohne Gate)"}
    req = gated.request(hub, "wissen_quelle", gates[0][0], gates[0][1], binding, gates=gates,
                        risks=[f"Deine Notizen werden Wissen für Stufe ≥ {NOTIZ_STUFE}; mit Personenbezug bleiben sie lokal"])
    return "request:" + req["mission_id"]


def _slug(titel):
    s = re.sub(r"[^a-z0-9äöüß]+", "-", titel.lower()).strip("-")[:48]
    return s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss") or "notiz"


def _kennung(datei):
    return hashlib.sha256(datei.encode("utf-8")).hexdigest()[:12]


def _datei_pruefen(sp, datei):
    """Der relative Name einer Notiz (`allgemein/2026-10-27-lease.md`) → Pfad; alles außerhalb der zwei Ordner gibt es nicht."""
    datei = str(datei or "")
    teile = datei.split("/")
    if len(teile) != 2 or teile[0] not in ORDNER.values() or not re.match(r"^[a-z0-9-]{1,80}\.md$", teile[1]):
        raise ValueError("wis_notiz_unbekannt")
    p = sp.projekt_root / Path(*NOTIZEN.split("/")) / teile[0] / teile[1]
    if not p.is_file():
        raise ValueError("wis_notiz_unbekannt")
    return p


def _text_pruefen(args):
    titel, text = str(args.get("titel") or "").strip(), str(args.get("text") or "").strip()
    if not titel or not text:
        raise ValueError("wis_notiz_leer")
    if len(titel) > MAX_TITEL or len(text) > MAX_TEXT or "\n" in titel:
        raise ValueError("wis_notiz_zu_lang" if len(titel) > MAX_TITEL or len(text) > MAX_TEXT else "wis_notiz_leer")
    return titel, text


def _nach_dem_schreiben(hub, sp, aktion, datei, zeichen):
    sp.audit("WIS_NOTIZ", {"aktion": aktion, "datei": _kennung(datei), "zeichen": zeichen})
    antrag = notizen_freigabe(hub, sp)
    if antrag:
        return {"status": "beantragt", "decision_id": antrag, "datei": datei,
                "text": "Notiz gespeichert. „Notizen des Captains“ wartet einmal auf deine Freigabe im Posteingang; danach ist jede Notiz sofort findbar."}
    for pb in (True, False):
        q = _quelle_von(sp, pb)
        if q:
            try:
                sp.abgleich(q["id"])
            except ValueError as exc:
                sp.audit("WIS_DATEI_UEBERSPRUNGEN", {"quelle": q["id"], "datei": _kennung(datei), "grund": str(exc)})
    return {"status": "erledigt", "datei": datei, "text": "Notiz gespeichert und im Wissen – per Volltext sofort, hybrid nach dem nächsten Einbetten."}


def notiz_anlegen(hub, sp, args):
    titel, text = _text_pruefen(args)
    pb = bool(args.get("personenbezug", True))
    ordner = _ordner(sp, pb)
    tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    name = f"{tag}-{_slug(titel)}.md"
    n = 2
    while (ordner / name).exists():
        name = f"{tag}-{_slug(titel)}-{n}.md"; n += 1
    (ordner / name).write_text(f"# {titel}\n\n{text}\n", encoding="utf-8")
    return _nach_dem_schreiben(hub, sp, "anlegen", f"{ORDNER[pb]}/{name}", len(text))


def notiz_aendern(hub, sp, args):
    p = _datei_pruefen(sp, args.get("datei"))
    titel, text = _text_pruefen(args)
    p.write_text(f"# {titel}\n\n{text}\n", encoding="utf-8")
    return _nach_dem_schreiben(hub, sp, "aendern", str(args.get("datei")), len(text))


def notiz_loeschen(hub, sp, args):
    p = _datei_pruefen(sp, args.get("datei"))
    p.unlink()
    return _nach_dem_schreiben(hub, sp, "loeschen", str(args.get("datei")), 0)


def notizen(hub, sp, args):
    """Die Notizen beider Ordner: Datei, Titel (erste Zeile), Personenbezug, Stand, Zeichen; dazu, ob die Quelle freigegeben ist."""
    out = []
    for pb in (True, False):
        for p in sorted(_ordner(sp, pb).glob("*.md"), reverse=True):
            try:
                roh = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            erste, _, rest = roh.partition("\n")
            out.append({"datei": f"{ORDNER[pb]}/{p.name}", "titel": erste.lstrip("# ").strip()[:MAX_TITEL], "text": rest.strip()[:MAX_TEXT],
                        "personenbezug": pb, "stand": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    frei = bool(_quelle_von(sp, True) and _quelle_von(sp, False))
    return {"status": "erledigt", "notizen": out[:200], "freigegeben": frei, "antrag": None if frei else _antrag_offen(hub)}


# ---- Leiste (§4.3)
def strip_zelle(sp):
    """Die Zelle `wissen` von /api/strip; ohne Speicher keine Zelle (das Instrument sagt dann „aus“)."""
    if sp is None:
        return None
    st = sp.stand()
    p = round((st.get("abdeckung") or 0) * 100)
    offen = st.get("vorschlaege_offen") or 0
    hybrid = st.get("modus") == "hybrid"
    value = ("hybrid · " + str(p) + " %") if hybrid else "nur Volltext"
    hint = (f"{offen} {'Vorschlag wartet' if offen == 1 else 'Vorschläge warten'}" if offen else f"{st.get('abschnitte', 0)} Abschnitte aus {st.get('quellen', 0)} Quellen")
    return {"value": value, "hint": hint, "tone": "warn" if offen or not hybrid else "ok", "modus": st.get("modus"), "abdeckung": st.get("abdeckung"),
            "vorschlaege_offen": offen, "bereit": bool(st.get("bereit"))}


# ---- „Frag das Wissen“ im Gespräch (§4.6)
def kontext(sp, text, mission_id=None):
    """(Nachrichten für das Modell, Ergebnis der Suche) – nur lokal (der Captain liest mit Stufe 6), ohne Treffer ([], Ergebnis)."""
    extra, ergebnis = lauf.kontext_nachrichten(sp, str(text)[:lauf.MAX_FRAGE], leser=CAPTAIN, route="local", mission_id=mission_id)
    return [{"role": m["role"], "content": m["content"]} for m in extra], ergebnis


def ohne_modell(ergebnis):
    """Die Antwort ohne geladenes Modell: die Fundstellen selbst, ohne Satz drumherum."""
    treffer = (ergebnis or {}).get("treffer") or []
    if not treffer:
        return ausgabe.KEINE_TREFFER
    zeilen = ["Das habe ich im Wissen gefunden:"]
    for t in treffer:
        kurz = " ".join(str(t.get("text") or "").split())[:180]
        zeilen.append(f"[{t['id']}] {t.get('stelle') or t.get('datei')} ({t.get('datei')}): {kurz}")
    if (ergebnis or {}).get("hinweis"):
        zeilen.append(ergebnis["hinweis"])
    return "\n".join(zeilen)


def nachweis(ergebnis):
    """Was das Gespräch zur Antwort mitbekommt: die Kennungen und ob Personenbezug darin steckt (dann kein Cloud-Weg)."""
    treffer = (ergebnis or {}).get("treffer") or []
    return {"ids": [t["id"] for t in treffer], "personenbezug": any(t.get("personenbezug") for t in treffer), "modus": (ergebnis or {}).get("modus")}
