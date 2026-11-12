"""Berechtigung der Zugänge (SPEC_APPS_v1_AM4_DIENSTE AM4-01 bis AM4-03, AM4-08): `mcp` (der Zugang der Modelle) und die Dienste (`dienst:<id>`) lesen und rufen nur, was ihnen gewährt ist; `cli` bleibt
unbeschränkt (der Captain tippt selbst). Rein: aus dem Eintrag und dem Körper der Anfrage wird ein Fehlercode oder None.

Ehrliche Grenze (AM4 §1): Auf dem Host ist das Ordnung und Nachweis, keine Sicherheitsgrenze gegen ein Programm unter demselben Windows-Konto, das die Token-Dateien lesen kann."""
from __future__ import annotations

MCP_VORGABE = {'lesen': 'alle', 'verben': []}          # AM4-02: lesen alle Typen, Verben keine
ALLE = 'alle'
SATZ_HOST = 'Jedes Programm unter deinem Windows-Konto kann diesen Zugang nutzen: Der Token liegt in einer Datei, die dasselbe Konto lesen kann. Die Berechtigung ist Ordnung und Nachweis, keine Sicherheitsgrenze gegen ein solches Programm.'


def eintrag_normal(e):
    """Ein Eintrag aus der Datei oder dem Manifest (`lesen`: 'alle' oder Liste von Typen, `verben`: Liste von `typ.verb`) in eine feste Form."""
    e = e if isinstance(e, dict) else {}
    lesen = e.get('lesen', ALLE)
    lesen = ALLE if lesen == ALLE else sorted({str(x) for x in lesen if isinstance(x, str)}) if isinstance(lesen, list) else []
    verben = sorted({str(x) for x in e.get('verben', []) if isinstance(x, str)}) if isinstance(e.get('verben', []), list) else []
    return {'lesen': lesen, 'verben': verben}


def pruefe(eintrag, path, payload):
    """None = in Ordnung; sonst `typ_nicht_gewaehrt` (POST /api/objects) oder `verb_nicht_gewaehrt` (POST /api/actions)."""
    e = eintrag_normal(eintrag)
    p = payload if isinstance(payload, dict) else {}
    typ = str(p.get('type') or '').strip()
    if path == '/api/objects':
        return None if e['lesen'] == ALLE or typ in e['lesen'] else 'typ_nicht_gewaehrt'
    if path == '/api/actions':
        verb = str(p.get('verb') or '').strip()
        return None if f'{typ}.{verb}' in e['verben'] else 'verb_nicht_gewaehrt'
    return None


def aus_rechten(rechte):
    """Der Eintrag eines Dienstes aus `rechte:` seines Manifests (AM3-01): `lesen` (Typen) und `verben`; ohne Angabe nichts."""
    r = rechte if isinstance(rechte, dict) else {}
    return {'lesen': [x for x in (r.get('lesen') or []) if isinstance(x, str)], 'verben': [x for x in (r.get('verben') or []) if isinstance(x, str)]}


def faehigkeit_in_eintrag(eintrag, faehigkeit):
    """Ob eine Fähigkeit (`lesen:<typ>`, `verb:<typ.verb>`) im Eintrag steht (für die Anzeige)."""
    e = eintrag_normal(eintrag)
    art, _, rest = str(faehigkeit).partition(':')
    if art == 'lesen':
        return e['lesen'] == ALLE or rest in e['lesen']
    return art == 'verb' and rest in e['verben']
