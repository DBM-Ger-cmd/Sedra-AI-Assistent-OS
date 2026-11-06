"""Gemerkte Vorgaben für Fundstellen im GateWay (Spezifikation docs/SPEC_GATEWAY_ARBEITSSTRECKE_2026-10-19.md, Abschnitt 5.3).

Eine gemerkte Vorgabe gilt global für alle Dokumente. Sie wirkt nie still: Sie wird in der Vorschau als Vorschlag gezeigt, der
Nutzer bestätigt ihn beim Speichern. Gespeichert wird nur Text, Art, Platzhalter-Typ und Datum – keine Dokumente.
Die Datei liegt unter local_config/gateway und ist nicht in git."""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

ARTEN = ('ersetzen', 'behalten', 'entfernen')
TYPEN = ('PERSON', 'EMAIL', 'PHONE', 'CUSTOMER_ID', 'COMPANY', 'TERM', 'ADDRESS', 'ORT')
MAX_EINTRAEGE = 500
MAX_TEXT = 200


class VorgabeFehler(ValueError):
    pass


def _datei(root: Path) -> Path:
    return Path(root) / 'local_config' / 'gateway' / 'vorgaben_text.json'


def laden(root: Path) -> list:
    p = _datei(root)
    if not p.is_file(): return []
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except ValueError:
        raise VorgabeFehler('vorgaben_unlesbar')           # nie still leer überschreiben
    return [e for e in (data.get('vorgaben') or []) if isinstance(e, dict)]


def _schreiben(root: Path, eintraege: list):
    p = _datei(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.' + secrets.token_hex(4) + '.tmp')
    tmp.write_text(json.dumps({'schema': 1, 'vorgaben': eintraege}, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(p)


def merken(root: Path, text: str, typ: str, art: str, platzhalter: str = '', angelegt_von: str = 'Captain') -> dict:
    """Eine Vorgabe merken. Gleicher Text und gleicher Typ ersetzen die alte Vorgabe, sie entsteht nicht doppelt."""
    text = ' '.join(str(text or '').split())
    if not text or len(text) > MAX_TEXT: raise VorgabeFehler('text_ungueltig')
    if typ not in TYPEN: raise VorgabeFehler('typ_unbekannt')
    if art not in ARTEN: raise VorgabeFehler('art_unbekannt')
    eintraege = laden(root)
    eintraege = [e for e in eintraege if not (e.get('text', '').casefold() == text.casefold() and e.get('typ') == typ)]
    if len(eintraege) >= MAX_EINTRAEGE: raise VorgabeFehler('zu_viele_vorgaben')
    eintrag = {'id': secrets.token_hex(4), 'text': text, 'typ': typ, 'art': art, 'platzhalter': str(platzhalter or ''),
               'datum': datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'), 'angelegt_von': angelegt_von}
    eintraege.append(eintrag)
    _schreiben(root, eintraege)
    return eintrag


def loeschen(root: Path, vid: str) -> bool:
    eintraege = laden(root)
    neu = [e for e in eintraege if e.get('id') != str(vid)]
    if len(neu) == len(eintraege): return False
    _schreiben(root, neu)
    return True


def vorschlaege(eintraege: list, fundstellen: list) -> dict:
    """Je Fundstelle die gemerkte Vorgabe, die passt (gleicher Text ohne Groß/Klein, gleicher Typ), als {id: vorgabe}."""
    nach = {(e.get('typ'), str(e.get('text', '')).casefold()): e for e in eintraege}
    out = {}
    for f in fundstellen:
        e = nach.get((f.get('typ'), str(f.get('text', '')).casefold()))
        if e: out[f['id']] = {'id': e['id'], 'art': e['art'], 'platzhalter': e.get('platzhalter', ''), 'datum': e.get('datum', '')}
    return out
