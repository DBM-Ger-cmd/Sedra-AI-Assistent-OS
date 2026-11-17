"""Lauf-Sicht (Schritt 5 des Produktplans): alle Läufe und offenen Gates im gemeinsamen Schema der Laufquelle. Nur lesen.

Quellen: die Live-Dateien je Lauf (`live.lesen`) und der Gate-Speicher der Missionen (`human_gates.pending`).
Keine Schreibrechte: nichts wird geändert, nichts freigegeben. Entscheidungen laufen weiter über den Guard.
Unbekannt bleibt unbekannt: eine veraltete oder fehlende Meldung ergibt `UNKNOWN`, nie einen Erfolg.
"""
from __future__ import annotations

from . import live

# Zustand der Live-Datei -> Status im Lauf-Schema. Wartet ein Lauf auf den Captain, ist es WAITING_APPROVAL.
ABBILDUNG = {'laeuft': 'RUNNING', 'wartet': 'WAITING', 'fehler': 'FAILED', 'fertig': 'COMPLETED'}
AKTIV = ('RUNNING', 'WAITING', 'WAITING_APPROVAL')


def status(satz):
    """Status eines Laufs (rein): veraltet heißt keine aktuelle Meldung, also UNKNOWN."""
    if satz.get('veraltet'):
        return 'UNKNOWN'
    if satz.get('zustand') == 'wartet' and satz.get('wartet_captain'):
        return 'WAITING_APPROVAL'
    return ABBILDUNG.get(satz.get('zustand'), 'UNKNOWN')


def lauf(satz):
    """Eine Live-Meldung im Lauf-Schema (rein)."""
    st = status(satz)
    verlauf = satz.get('verlauf') or []
    return {
        'id': satz.get('lauf') or satz.get('prozess'),
        'flow': satz.get('workflow_id') or satz.get('prozess'),
        'title': satz.get('prozess'),
        'revision': '?',
        'node': satz.get('schritt') or '',
        'status': st,
        'active': st in AKTIV,
        'echt': True,
        'source': 'Live-Datei',
        'started': verlauf[0].get('zeit') if verlauf else satz.get('gestartet') or '',
        'aktualisiert': satz.get('aktualisiert'),
        'text': satz.get('text'),
    }


def laeufe(projekt_root, *, jetzt=None):
    """Alle Läufe aus den Live-Dateien (nur lesen)."""
    return [lauf(s) for s in live.lesen(projekt_root, jetzt=jetzt)]


def gates(missions):
    """Offene Gates aus dem Gate-Speicher der Missionen (nur lesen). `run` ist die Lauf-ID, dieselbe wie in `laeufe`."""
    out = []
    for m in missions or []:
        mid = (m.get('identity') or {}).get('mission_id')
        for g in (m.get('human_gates') or {}).get('pending') or []:
            if not isinstance(g, dict) or not g.get('gate_id'):
                continue
            req = g.get('request') or {}
            out.append({
                'gate_id': g['gate_id'],
                'run': mid,
                'action': req.get('exact_action'),
                'targets': list(req.get('targets') or []),
                'risks': list(req.get('risks') or []),
                'rollback_available': bool(req.get('rollback_available')),
                'status': 'offen',
            })
    return out


def sicht(projekt_root, missions, *, jetzt=None):
    """Läufe und offene Gates in einer Antwort (nur lesen)."""
    return {'laeufe': laeufe(projekt_root, jetzt=jetzt), 'gates': gates(missions)}
