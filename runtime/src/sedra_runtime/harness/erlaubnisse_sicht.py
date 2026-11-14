"""S4.1 (SPEC_FREIGABEN_S4_v1, FS-01 bis FS-04): alle Erlaubnisse als ein Datensatz – nur eine Sicht.

Es entsteht keine neue Ablage und keine neue Prüfung. Die drei bestehenden Ablagen bleiben, wie sie sind:
- Sitzungs-Erlaubnis: Eintrag `erlaubnis` im Sitzungs-JSONL (`harness/erlaubnis.py`),
- Aufgabe: `runtime_data/harness/aufgaben/T-*.json` (`harness/aufgabe.py`),
- Katalogregel mit Stufe `frei` (`local_config/freigabe_katalog.yaml`, `harness/katalog.py`).
Sie werden hier nur gelesen und in dieselbe Form gebracht: was (Werkzeug und Muster), wo (Projekt, Sitzungen), wie lange (Sitzung,
befristet, immer), warum, Herkunft. Über die Deckung entscheiden weiter `erlaubnis.deckt`, `aufgabe_deckung` und der Katalog; diese
Datei erteilt, ändert und löscht nichts. Rein: keine Dateien, kein Zustand, kein Audit."""
from __future__ import annotations

STATUS = ('aktiv', 'beendet', 'alle')
ARTEN = ('sitzung', 'aufgabe', 'katalog')          # Reihenfolge in der Liste


def _was(werkzeug, muster):
    return {'werkzeug': werkzeug, 'muster': muster}


def aus_sitzung(kopf, e):
    """Eine Sitzungs-Erlaubnis (Eintrag aus `erlaubnis.aktive`) mit dem Kopf ihrer Sitzung."""
    kid = str(e.get('karte_id') or '')
    von = 'vorlage' if kid.startswith('V-') else 'captain'          # Vorlage-Erlaubnisse tragen die Karten-ID `V-<vorlage>-<n>`
    return {'id': f"{kopf.get('id')}:{kid}", 'art': 'sitzung', 'was': [_was(e.get('werkzeug'), e.get('muster'))],
            'wo': {'projekt': kopf.get('projekt'), 'sitzungen': [kopf.get('id')]},
            'dauer': {'art': 'sitzung', 'bis': None, 'max_aufrufe': None}, 'warum': None,
            'herkunft': {'von': von, 'karte_id': kid or None, 'vorlage': kopf.get('vorlage') if von == 'vorlage' else None},
            'seit': e.get('zeit'), 'status': 'aktiv', 'status_roh': 'aktiv'}


def aus_aufgabe(a):
    """Eine Aufgabe (`Aufgaben.alle`). Der Vorschlag des Vorarbeiters trägt `vorschlag_von`."""
    ende = a.get('ende') or {}
    roh = a.get('status')
    return {'id': a.get('id'), 'art': 'aufgabe', 'was': [_was(e.get('werkzeug'), e.get('muster')) for e in a.get('erlaubt') or () if isinstance(e, dict)],
            'wo': {'projekt': a.get('projekt'), 'sitzungen': list(a.get('sitzungen') or ())},
            'dauer': {'art': 'befristet', 'bis': ende.get('bis'), 'max_aufrufe': ende.get('max_aufrufe')},
            'warum': a.get('zweck') or a.get('titel'),
            'herkunft': {'von': 'vorarbeiter' if a.get('vorschlag_von') else 'captain', 'karte_id': None, 'vorlage': None},
            'seit': a.get('angelegt'), 'status': 'aktiv' if roh == 'aktiv' else 'beendet', 'status_roh': roh,
            'aufrufe': a.get('aufrufe'), 'titel': a.get('titel')}


def aus_katalog(r):
    """Eine Katalogregel mit Stufe `frei`: Erlaubnis ohne Ende, nur zur Anzeige (FS-02)."""
    werkzeuge = r.get('werkzeug') if isinstance(r.get('werkzeug'), list) else [r.get('werkzeug')]
    muster = r.get('muster') if isinstance(r.get('muster'), list) else [r.get('muster')]
    return {'id': f"K:{r.get('id')}", 'art': 'katalog', 'was': [_was(w, m) for w in werkzeuge for m in muster],
            'wo': {'projekt': None, 'sitzungen': None},
            'dauer': {'art': 'immer', 'bis': None, 'max_aufrufe': None}, 'warum': r.get('begruendung'),
            'herkunft': {'von': 'captain', 'karte_id': None, 'vorlage': None, 'regel': r.get('id')},
            'seit': None, 'status': 'aktiv', 'status_roh': 'aktiv'}


def sammeln(sitzungen, aufgaben, katalog_regeln, *, projekt=None, sitzung=None, status='aktiv'):
    """{'erlaubnisse': [...], 'anzahl', 'nach_art'} aus den drei Ablagen.

    `sitzungen`: Liste von {'kopf', 'erlaubnisse'} (Rückgabe von `Sitzungen.laden`), `aufgaben`: `Aufgaben.alle()`, `katalog_regeln`:
    die Regeln aus `katalog.laden`. Filter: `projekt` und `sitzung` (die Katalogregeln gelten überall und bleiben immer in der Liste),
    `status` aktiv (Vorgabe), beendet oder alle."""
    if status not in STATUS:
        raise ValueError('status_unbekannt: ' + ', '.join(STATUS))
    out = []
    for s in sitzungen or ():
        kopf = (s or {}).get('kopf') or {}
        if (projekt and kopf.get('projekt') != projekt) or (sitzung and kopf.get('id') != sitzung):
            continue
        out.extend(aus_sitzung(kopf, e) for e in (s.get('erlaubnisse') or ()) if isinstance(e, dict))
    for a in aufgaben or ():
        if (projekt and a.get('projekt') != projekt) or (sitzung and sitzung not in (a.get('sitzungen') or ())):
            continue
        out.append(aus_aufgabe(a))
    for r in katalog_regeln or ():
        if isinstance(r, dict) and r.get('stufe') == 'frei':
            out.append(aus_katalog(r))
    if status != 'alle':
        out = [e for e in out if e['status'] == status]
    rang = {art: n for n, art in enumerate(ARTEN)}
    out.sort(key=lambda e: (rang[e['art']], str(e.get('seit') or '')), reverse=False)
    return {'erlaubnisse': out, 'anzahl': len(out), 'nach_art': {art: sum(1 for e in out if e['art'] == art) for art in ARTEN}}
