"""Gemerkter Zustand der App Coder (Ausbau): gewähltes Projekt, Chat-Verlauf, offene Anträge, Schriftgröße.

Der Rahmen des Coders hat keinen eigenen Speicher; damit nach dem Schließen nichts verloren geht, liegt ein kleiner Zustand auf dem Server
(`local_config/coder_zustand.json`, nur lokal, nie im Projekt). Hier steht nur die Prüfung: eine feste Liste von Feldern mit Grenzen,
alles andere wird verworfen. Dateitext wird nie gemerkt, nur Namen und der Chat, den du selbst geschrieben hast.
"""
from __future__ import annotations

import re

from . import coder_lesen

SCHRIFT = (10, 24)
CHAT_MAX = 40
VERLAUF_MAX = 16
ANTRAEGE_MAX = 20
TEXT_MAX = 4000
NAME_MAX = 80
ARTEN = ('speichern', 'ordner', 'umbenennen', 'loeschen')
AUFTRAG_RE = re.compile(r'^[A-Za-z0-9_-]{3,60}$')
LEER = {'projekt': '', 'schrift': 13, 'weg': '', 'chat': [], 'verlauf': [], 'antraege': []}


def _text(wert, grenze) -> str:
    return wert[:grenze] if isinstance(wert, str) else ''


def bereinige(roh) -> dict:
    """Aus beliebigem Eingang einen gültigen Zustand machen: unbekannte Felder und Ungültiges fallen weg, nie ein Fehler."""
    z = {'projekt': '', 'schrift': LEER['schrift'], 'weg': '', 'chat': [], 'verlauf': [], 'antraege': []}
    if not isinstance(roh, dict):
        return z
    p = roh.get('projekt')
    if isinstance(p, str) and 0 < len(p) <= 60 and not any(c in p for c in '/\\?# '):
        z['projekt'] = p
    s = roh.get('schrift')
    if isinstance(s, int) and not isinstance(s, bool) and SCHRIFT[0] <= s <= SCHRIFT[1]:
        z['schrift'] = s
    z['weg'] = _text(roh.get('weg'), NAME_MAX)
    for e in (roh.get('chat') if isinstance(roh.get('chat'), list) else [])[-CHAT_MAX:]:
        if isinstance(e, dict) and isinstance(e.get('text'), str):
            z['chat'].append({'von': _text(e.get('von'), NAME_MAX), 'ich': bool(e.get('ich')), 'text': _text(e.get('text'), TEXT_MAX)})
    for e in (roh.get('verlauf') if isinstance(roh.get('verlauf'), list) else [])[-VERLAUF_MAX:]:
        if isinstance(e, dict) and e.get('role') in ('user', 'assistant') and isinstance(e.get('content'), str):
            z['verlauf'].append({'role': e['role'], 'content': _text(e['content'], TEXT_MAX)})
    for e in (roh.get('antraege') if isinstance(roh.get('antraege'), list) else [])[-ANTRAEGE_MAX:]:
        if not isinstance(e, dict) or e.get('art') not in ARTEN or not isinstance(e.get('id'), str) or not AUFTRAG_RE.match(e['id']):
            continue
        pfad = _text(e.get('pfad'), coder_lesen.PFAD_MAX)
        if not pfad or coder_lesen.pfad_gesperrt(pfad):
            continue
        ziel = _text(e.get('ziel'), coder_lesen.PFAD_MAX) or None
        z['antraege'].append({'id': e['id'], 'art': e['art'], 'pfad': pfad, 'ziel': ziel})
    return z
