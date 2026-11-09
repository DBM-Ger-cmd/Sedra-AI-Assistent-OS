"""Die Fabrikhalle: was die Harness gerade tut (Läufe, Aufgaben) und was auf den Captain wartet (offene Freigaben), als eine schlanke Übersicht.

Reine Rechnung auf den Daten der Harness (`harness/lauf.py`, `harness/aufgabe.py`, `harness/freigabe.py`); nichts wird gestartet, gestoppt oder
freigegeben. Pfade, Befehlszeilen und Parameter der Läufe bleiben draußen, nur Name, Zustand, Fortschritt, Dauer und die letzte Zeile gehen an die
Oberfläche. Der Reiter Live der Workflow-Apps zeigt sie über das Verb `fabrik` (workflows/desk.py)."""
from __future__ import annotations

from datetime import datetime, timezone

LETZTE = 6                         # so viele beendete Läufe stehen unter den laufenden
MAX_TEXT = 140


def _zeit(text):
    try:
        z = datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return None
    return z if z.tzinfo else z.replace(tzinfo=timezone.utc)


def _kurz(text, n=MAX_TEXT):
    t = ' '.join(str(text or '').split())
    return t if len(t) <= n else t[:n - 1] + '…'


def lauf_schlank(lauf, jetzt):
    """Ein Lauf für die Anzeige (rein): ohne Pfade, Befehl und Parameter. `dauer_s` vom Start bis zum Ende, laufend bis jetzt."""
    start, ende = _zeit(lauf.get('gestartet')), _zeit(lauf.get('ende'))
    bis = ende or (jetzt if lauf.get('status') == 'laeuft' else None)
    fort = lauf.get('fortschritt') or {}
    prozent = fort.get('prozent')
    return {'id': lauf.get('id'), 'lauf': lauf.get('lauf'), 'name': _kurz(lauf.get('name') or lauf.get('lauf'), 80), 'status': lauf.get('status'),
            'gestartet': lauf.get('gestartet'), 'ende': lauf.get('ende'),
            'dauer_s': int((bis - start).total_seconds()) if start and bis else None,
            'prozent': int(prozent) if isinstance(prozent, (int, float)) and 0 <= prozent <= 100 else None,
            'text': _kurz(fort.get('text')), 'gpu': lauf.get('gpu'), 'aufgabe_id': lauf.get('aufgabe_id'), 'grund': _kurz(lauf.get('grund'), 80) if lauf.get('status') != 'laeuft' else None}


def aufgabe_schlank(a):
    return {'id': a.get('id'), 'titel': _kurz(a.get('titel'), 80), 'zweck': _kurz(a.get('zweck_anzeige') or a.get('zweck'), 120), 'projekt': a.get('projekt'),
            'rest_aufrufe': a.get('rest_aufrufe'), 'rest_min': a.get('rest_min'), 'aufrufe': a.get('aufrufe')}


def karte_schlank(k):
    """Eine offene Entscheidung des Posteingangs (desk/decisions: id, kind, title, created_at) oder eine Karte der Harness (karte_id, werkzeug, ziel)."""
    return {'karte_id': k.get('karte_id') or k.get('id'), 'werkzeug': k.get('werkzeug') or k.get('kind'), 'ziel': _kurz(k.get('ziel') or k.get('title'), 80),
            'begruendung': _kurz(k.get('begruendung') or k.get('summary'), 120), 'angelegt': k.get('angelegt') or k.get('created_at')}


def uebersicht(laeufe, aufgaben, karten, belegt=None, jetzt=None):
    """{'laeufe': {'laufend', 'zuletzt'}, 'aufgaben', 'freigaben': {'anzahl', 'neueste'}, 'belegung', 'zaehler'} (rein).
    `laeufe`: alle Läufe der Register, `aufgaben`: die aktiven Aufgaben (öffentlich), `karten`: alles, was im Posteingang auf den Captain wartet,
    `belegt`: der Lauf, der das Modell hält."""
    jetzt = jetzt or datetime.now(timezone.utc)
    schlank = [lauf_schlank(l, jetzt) for l in (laeufe or []) if isinstance(l, dict)]
    laufend = [l for l in schlank if l['status'] == 'laeuft']
    laufend.sort(key=lambda l: l.get('gestartet') or '')
    fertig = sorted((l for l in schlank if l['status'] != 'laeuft'), key=lambda l: l.get('ende') or l.get('gestartet') or '', reverse=True)[:LETZTE]
    karten = [karte_schlank(k) for k in (karten or []) if isinstance(k, dict)]
    karten.sort(key=lambda k: k.get('angelegt') or '', reverse=True)
    aufg = [aufgabe_schlank(a) for a in (aufgaben or []) if isinstance(a, dict)]
    return {'laeufe': {'laufend': laufend, 'zuletzt': fertig}, 'aufgaben': aufg, 'freigaben': {'anzahl': len(karten), 'neueste': karten[:3]},
            'belegung': ({'id': belegt.get('id'), 'name': _kurz(belegt.get('name') or belegt.get('lauf'), 80)} if isinstance(belegt, dict) else None),
            'zaehler': {'laeuft': len(laufend), 'aufgaben': len(aufg), 'freigaben': len(karten),
                        'fehler': sum(1 for l in fertig if l['status'] in ('fehler', 'verloren'))}}
