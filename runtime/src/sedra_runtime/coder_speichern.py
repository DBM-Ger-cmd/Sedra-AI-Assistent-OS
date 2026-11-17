"""Speichern aus der App Coder (Entscheidung E4, 17.11.2026): nur als Antrag an die Freigaben.

Der Coder schreibt nie selbst. Er schickt Pfad und neuen Text; der Server legt einen Auftrag mit einer Freigabe an (genau diese Änderung an genau dieser
Datei, Zustand der Datei im Antrag festgehalten). Erst wenn der Captain in den Freigaben zustimmt, schreibt der Server über das Dateiwerkzeug.
Ändert sich die Datei bis dahin, gilt die Freigabe nicht. Hier stehen nur die Prüfungen und die Form der Antworten.
"""
from __future__ import annotations

import re

from . import coder_lesen

INHALT_MAX = 2_000_000        # Bytes (UTF-8): wie die Lesegrenze des Coders; das Dateiwerkzeug schreibt bis 4 MB
PFAD_MAX = coder_lesen.PFAD_MAX
AUFTRAG_RE = re.compile(r'^[A-Za-z0-9_-]{3,60}$')
KONTEXT = 'coder_speichern'


def pruefe(payload) -> tuple:
    """(projekt, pfad, inhalt) oder ValueError mit Kennwort."""
    if not isinstance(payload, dict):
        raise ValueError('invalid_payload')
    projekt, pfad, inhalt = payload.get('projekt'), payload.get('pfad'), payload.get('inhalt')
    if not isinstance(projekt, str) or not projekt or len(projekt) > 60 or any(c in projekt for c in '/\\?# '):
        raise ValueError('invalid_project')
    if not isinstance(pfad, str) or not pfad or len(pfad) > PFAD_MAX or '\x00' in pfad:
        raise ValueError('invalid_path')
    if not isinstance(inhalt, str) or '\x00' in inhalt:
        raise ValueError('invalid_content')
    if len(inhalt.encode('utf-8', errors='replace')) > INHALT_MAX:
        raise ValueError('content_too_large')
    if coder_lesen.pfad_gesperrt(pfad):
        raise ValueError('access_blocked')
    return projekt, pfad, inhalt


def auftrag_gueltig(mission_id) -> str:
    if not isinstance(mission_id, str) or not AUFTRAG_RE.match(mission_id):
        raise ValueError('invalid_mission')
    return mission_id


def zeilenenden(alt, neu) -> str:
    """Die Datei behält ihre Zeilenenden: war sie mit CRLF gespeichert und der Editor liefert nur LF, wird zurückgewandelt."""
    if '\r\n' in alt and '\r' not in neu:
        return neu.replace('\n', '\r\n')
    return neu


def zaehle(alt, neu) -> tuple:
    """(hinzu, weg): Zeilen, die neu dazukommen oder wegfallen (für den Hinweis in der Freigabe). Linear, auch für Dateien mit Hunderttausenden Zeilen."""
    from collections import Counter
    rest = Counter(alt.splitlines())
    hinzu = 0
    for z in neu.splitlines():
        if rest[z] > 0:
            rest[z] -= 1
        else:
            hinzu += 1
    return hinzu, sum(rest.values())


def zustand(m) -> str:
    """Stand eines Antrags aus dem Auftrag: wartet | abgelehnt | freigegeben | angewendet."""
    if (m.get('lifecycle') or {}).get('status') == 'closed' and (m.get('result') or {}).get('kind') in ('coder_speichern', 'coder_verwalten'):
        return 'angewendet'
    if (m.get('human_gates') or {}).get('pending'):
        return 'wartet'
    if (m.get('execution') or {}).get('approval_token'):
        return 'freigegeben'
    gates = (m.get('human_gates') or {}).get('resolved') or []
    if gates and (gates[-1].get('resolution') or {}).get('decision') == 'DENY':
        return 'abgelehnt'
    return 'wartet'
