"""Dateiverwaltung aus der App Coder (Ausbau): neuer Ordner, Umbenennen, Löschen, jeweils nur als Antrag an die Freigaben (wie das Speichern, E4).

Der Coder verändert nie selbst etwas. Der Server legt einen Auftrag mit einer Freigabe an (genau diese Änderung, Zustand der Pfade im Antrag);
erst nach der Zustimmung des Captains führt er sie über das Dateiwerkzeug aus. Gelöscht werden nur Dateien und leere Ordner, nie ein ganzer Baum.
"""
from __future__ import annotations

from . import coder_lesen

KONTEXT = 'coder_verwalten'
ARTEN = ('ordner', 'umbenennen', 'loeschen')
# Ordner, die der Coder nie anfasst (Git-Daten, Abhängigkeiten, Zwischenspeicher)
GESCHUETZT = frozenset({'.git', '__pycache__', 'node_modules', '.venv', '.mypy_cache', '.pytest_cache'})


def _pfad(wert) -> str:
    if not isinstance(wert, str) or not wert or len(wert) > coder_lesen.PFAD_MAX or '\x00' in wert:
        raise ValueError('invalid_path')
    teile = [t for t in wert.replace('\\', '/').split('/') if t not in ('', '.')]
    if not teile or '..' in teile or ':' in wert or wert.startswith(('/', '\\')):
        raise ValueError('invalid_path')
    if coder_lesen.pfad_gesperrt(wert) or any(t in GESCHUETZT for t in teile):
        raise ValueError('access_blocked')
    return '/'.join(teile)


def pruefe(payload) -> tuple:
    """(art, projekt, pfad, ziel) oder ValueError mit Kennwort. `ziel` nur beim Umbenennen."""
    if not isinstance(payload, dict):
        raise ValueError('invalid_payload')
    art, projekt = payload.get('art'), payload.get('projekt')
    if art not in ARTEN:
        raise ValueError('invalid_kind')
    if not isinstance(projekt, str) or not projekt or len(projekt) > 60 or any(c in projekt for c in '/\\?# '):
        raise ValueError('invalid_project')
    pfad = _pfad(payload.get('pfad'))
    ziel = _pfad(payload.get('ziel')) if art == 'umbenennen' else None
    if art == 'umbenennen' and ziel == pfad:
        raise ValueError('keine_aenderung')
    return art, projekt, pfad, ziel
