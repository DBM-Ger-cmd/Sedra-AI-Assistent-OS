"""Orte der Oberfläche aus einer Quelle (AM2-01 bis AM2-05, SPEC_APPS_v1_AM2_ORTE_UND_GRUNDFUNKTIONEN).

`uix/ui/orte_kern.json` hält die Kernorte und die reservierten Wörter; `chat_tools.PLACES` und der Browser (`ui/places.js`) lesen daraus. Eine App bringt im
Manifest ein Feld `ort` mit: Name, Wörter, Objekt. Hier steht die Prüfung des Feldes und das Zusammensetzen je Shell. Rein, ohne Netz."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

DATEI = Path(__file__).resolve().parents[1] / 'uix' / 'ui' / 'orte_kern.json'
ORT_ID = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')
WORT = re.compile(r'^[a-zäöüß0-9][a-zäöüß0-9 -]{0,28}[a-zäöüß0-9]$')
ORT_KEYS = {'id', 'label', 'hint', 'words', 'object', 'symbol'}
OBJECT_KEYS = {'type', 'id', 'title', 'view'}
SYMBOLE = ('★', '●', '■', '▲', '◆', '✎', '☰', '⚙', '✉', '☎', '⌂', '♪')      # feste Liste (AM2-02): kein Bild, nur ein Zeichen


@lru_cache(maxsize=1)
def _lesen():
    return json.loads(DATEI.read_text(encoding='utf-8'))


def kern() -> list:
    return [dict(o) for o in _lesen()['orte']]


def reservierte_woerter() -> set:
    """Wörter, die eine App nicht beanspruchen darf: die der Kernorte und die der Satzmuster (Auftrag, Frage, Öffnen)."""
    d = _lesen()
    erg = {w for o in d['orte'] for w in o.get('words') or []}
    for liste in d['woerter'].values():
        erg.update(liste)
    return erg


def kern_ids() -> set:
    return {o['id'] for o in _lesen()['orte']}


def pruefe_ort(ort, handles, tool_id) -> list:
    """AM2-02/03: Fehlercodes des Feldes `ort` (leer = in Ordnung)."""
    if ort is None:
        return []
    if not isinstance(ort, dict):
        return ['ort_ungueltig']
    fehler = []
    if set(ort) - ORT_KEYS:
        fehler.append('ort_unbekanntes_feld:' + sorted(set(ort) - ORT_KEYS)[0])
    oid = ort.get('id')
    if not isinstance(oid, str) or not ORT_ID.match(oid):
        fehler.append('ort_id_ungueltig')
    elif oid in kern_ids():
        fehler.append('ort_id_belegt')
    label, hint = ort.get('label'), ort.get('hint', '')
    if not isinstance(label, str) or not 1 <= len(label) <= 40:
        fehler.append('ort_label_ungueltig')
    if not isinstance(hint, str) or len(hint) > 80:
        fehler.append('ort_hint_ungueltig')
    words = ort.get('words')
    if not isinstance(words, list) or not 1 <= len(words) <= 12 or not all(isinstance(w, str) and 2 <= len(w) <= 30 and WORT.match(w) for w in words):
        fehler.append('ort_words_ungueltig')
    else:
        belegt = reservierte_woerter()
        fehler.extend('ort_wort_reserviert:' + w for w in words if w in belegt)
    sym = ort.get('symbol')
    if sym is not None and sym not in SYMBOLE:
        fehler.append('ort_symbol_ungueltig')
    obj = ort.get('object')
    if not isinstance(obj, dict) or set(obj) - OBJECT_KEYS or not isinstance(obj.get('type'), str) or not isinstance(obj.get('id'), str):
        fehler.append('ort_object_ungueltig')
    elif not any(isinstance(h, str) and h.partition(':')[0] == obj['type'] for h in (handles or [])):
        fehler.append('ort_object_nicht_in_handles')
    elif any(not isinstance(obj.get(k), str) for k in ('title', 'view') if k in obj):
        fehler.append('ort_object_ungueltig')
    return fehler


def zusammensetzen(apps) -> tuple[list, list]:
    """Kernorte plus die Orte der Apps. `apps`: Liste von (werkzeug_id, ort) in fester Reihenfolge, schon geprüft.
    Eine Ort-id, die zwei Apps tragen, gilt für keine (die Prüfung im Gateway weist beide ab, hier zur Sicherheit); ein Wort, das zwei Apps beanspruchen,
    gilt für keine – beide Orte bleiben, die Meldung `ort_wort_doppelt:<wort>` geht in die Warnungen. Liefert (orte, warnungen)."""
    zaehler = {}
    for _tid, o in apps:
        for w in set(o.get('words') or []):
            zaehler[w] = zaehler.get(w, 0) + 1
    doppelt = sorted(w for w, n in zaehler.items() if n > 1)
    orte = kern()
    gesehen = {o['id'] for o in orte}
    for tid, o in apps:
        if o['id'] in gesehen:
            continue
        gesehen.add(o['id'])
        eintrag = {'id': o['id'], 'label': o['label'], 'hint': o.get('hint', ''), 'words': [w for w in o['words'] if w not in doppelt],
                   'object': dict(o['object']), 'app': tid}
        if o.get('symbol'):
            eintrag['symbol'] = o['symbol']
        orte.append(eintrag)
    return orte, ['ort_wort_doppelt:' + w for w in doppelt]
