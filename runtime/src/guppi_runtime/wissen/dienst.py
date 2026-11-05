"""Der Kerndienst Wissen (SPEC_WISSEN_KERN_v1 WK-01 bis WK-06, G2 K1 §2): **ein** Weg, auf dem alle das Wissen fragen – der Agentenlauf
(`wissen.lauf`), das Gespräch der alten Shells (`wissen.desk_basis`) und der Chat von One Sedra (`harness`). Hier und nur hier stehen der
Cloud-Filter bei Personenbezug (WIS-11), der Datenblock als fremde Daten (`trust: untrusted`, WIS-08) und die Zitatprüfung (WIS-07).

Der Leser kommt immer vom Aufrufer auf der Server-Seite (`speicher.leser`), nie aus den Argumenten eines Modells; die Route kommt aus dem
Anbieter (unbekannt gilt als Cloud, A-9). Ohne Speicher (Schalter `wissen` aus) gibt `fragen` die Art `aus` zurück, nie eine Ausnahme;
ein Fehler der Suche wird die Art `fehler` mit dem deutschen Satz. Audit nur über `speicher.audit` (`component='wissen'`), nie Text aus
Fragen oder Quellen (WK-06)."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..orchestra.runner import external_block
from . import ausgabe

MAX_FRAGE = 500
K_MAX = 20
SATZ_AUS = "Das Wissen ist abgeschaltet (Schalter „wissen“ in den Einstellungen unter System)."
ROUTEN = ("local", "cloud")


@dataclass(frozen=True)
class Antwort:
    """Das Ergebnis einer Frage an das Wissen. `art`: hybrid | volltext | aus | fehler. `ergebnis`: das Ergebnis der Suche nach dem
    Cloud-Filter (für `block` und `nachbereiten`), None bei `aus` und `fehler`."""
    art: str
    treffer: list = field(default_factory=list)
    hinweis: str | None = None
    ergebnis: dict | None = None
    code: str | None = None

    @property
    def ids(self):
        return [t["id"] for t in self.treffer]


def _satz(code):
    from .speicher import satz                                   # erst hier: dienst bleibt ohne sqlite-Teil importierbar
    return satz(code)


def fragen(speicher, frage, *, leser, route, filter=None, k=None, mission_id=None, protokoll=False):
    """Fragt das Wissen: Rechtefilter und Filter vor dem Ranking (in `suche`), danach der Cloud-Filter als zweite Sperre."""
    if speicher is None:
        return Antwort("aus", hinweis=SATZ_AUS, code="wissen_aus")
    if route not in ROUTEN:
        route = "cloud"                                           # A-9: was nicht sicher lokal ist, gilt als Cloud
    if k is None:
        k = speicher.konfig.kontext_treffer
    k = max(1, min(int(k), K_MAX))
    try:                                                           # die Länge prüft die Suche (`wis_anfrage_zu_lang`); kürzen ist Sache des Aufrufers
        ergebnis = speicher.suche(frage,leser=leser, k=k, route=route, mission_id=mission_id, protokoll=protokoll, filter=filter)
    except ValueError as exc:
        code = str(exc) or type(exc).__name__
        return Antwort("fehler", hinweis=_satz(code), code=code)
    treffer = list(ergebnis.get("treffer") or [])
    if route == "cloud":
        verworfen = [t["id"] for t in treffer if t.get("personenbezug")]
        if verworfen:
            speicher.audit("WIS_CLOUD_GEFILTERT", {"mission_id": mission_id, "ids": verworfen})
            treffer = [t for t in treffer if not t.get("personenbezug")]
    ergebnis = dict(ergebnis, treffer=treffer)
    return Antwort(ergebnis.get("modus") or "volltext", treffer, ergebnis.get("hinweis"), ergebnis)


def systemsatz(speicher):
    """Der feste Satz über den Datenblock – je Konfiguration immer derselbe (damit der Anfang des Prompts gleich bleibt, G2 §3.4)."""
    marken = bool(getattr(getattr(speicher, "konfig", None), "datamarking", False))
    return ausgabe.SYSTEM_WISSEN_MARKIERT if marken else ausgabe.SYSTEM_WISSEN


def block(speicher, antwort, *, mission_id=None):
    """[Systemsatz, Datenblock] für das Modell oder [] ohne Treffer. Der Block trägt `trust: untrusted` (WIS-08)."""
    if antwort is None or not antwort.treffer:
        return []
    k = speicher.konfig
    marken = bool(getattr(k, "datamarking", False))
    records = ausgabe.datensaetze(antwort.treffer, je_treffer=k.je_treffer, gesamt=k.gesamt, hoechstens=k.kontext_treffer, datamarking=marken)
    inhalt = external_block(records, max_chars=k.je_treffer)
    speicher.audit("WIS_KONTEXT", {"mission_id": mission_id, "ids": antwort.ids[:len(records)], "zeichen": len(inhalt), "modus": antwort.art})
    return [{"role": "system", "content": systemsatz(speicher), "trust": "system"}, {"role": "user", "content": inhalt, "trust": "untrusted"}]


def aus_ergebnis(ergebnis):
    """Eine Antwort aus einem Ergebnis der Suche (für Aufrufer, die das Ergebnis schon haben, z. B. `lauf.nachbereite`)."""
    if not ergebnis:
        return None
    return Antwort(ergebnis.get("modus") or "volltext", list(ergebnis.get("treffer") or []), ergebnis.get("hinweis"), ergebnis)


def nachbereiten(text, antwort, *, audit, mission_id=None, weitere_ids=()):
    """Zitatprüfung (WIS-07): fremde `[W…]` bekommen den Hinweis (`WIS_ZITAT_FREMD`), keine Kennung trotz Treffern die Fundstellen
    (`WIS_ZITAT_FEHLT`); der Hinweis der Suche (Volltext, Abdeckung) hängt an. `audit`: `speicher.audit`. `weitere_ids`: Kennungen, die
    das Modell im selben Zug auf anderem Weg bekam (Werkzeug `wissen_suchen`)."""
    ids = list(dict.fromkeys([*(antwort.ids if antwort else []), *weitere_ids]))
    hinweis = antwort.hinweis if antwort is not None and antwort.ergebnis is not None else None
    if text is None:
        return ausgabe.schlusstext(None, ids_im_block=ids, hinweis=hinweis)
    belegt, fremd = ausgabe.pruefe_zitate(text, set(ids))
    if fremd:
        audit("WIS_ZITAT_FREMD", {"mission_id": mission_id, "ids": fremd})
    if ids and not belegt:
        audit("WIS_ZITAT_FEHLT", {"mission_id": mission_id, "ids": ids})
    return ausgabe.schlusstext(text, ids_im_block=ids, hinweis=hinweis)


def route_aus_anbieter(anbieter, router=None):
    """`local` nur, wenn der Anbieter bekannt ist und keine Cloud-Route trägt; alles andere gilt als Cloud (A-9). Ohne Router zählt der
    Name: der lokale Modellserver der Harness (`llama-cpp-server`) ist lokal."""
    if router is None:
        return "local" if anbieter == "llama-cpp-server" else "cloud"
    adapters = getattr(router, "adapters", None) or {}
    adapter = adapters.get(anbieter) if isinstance(adapters, dict) and anbieter else None
    if adapter is None:
        return "cloud"
    return "cloud" if getattr(adapter, "route", "local") == "cloud" else "local"
