"""Deckung einer Aufgaben-Freigabe (SPEC_HARNESS_SHELL_v1 HS-27, G2 Stufe 3 §4.2, G3 Stufe 3 N2/N3).

Rein: kein Dateizugriff, keine Uhr (`jetzt` wird mitgegeben), keine Ausnahme bei Müll. **Referenz von Claude** – N2 ist ein SEDRA-Bau dieser beiden
Funktionen (`deckt`, `zustand`); baut SEDRA sie nach und der Captain übernimmt, ersetzt der Bau diese Datei. Die Mustererkennung ist die des Katalogs:
`passt(muster, werkzeug, ziel)` wird mitgegeben (`katalog.passt`), hier gibt es kein zweites Verfahren."""
from __future__ import annotations

from datetime import datetime


def _zeit(wert):
    """Ein Zeitpunkt mit Zeitzone – oder None (kein Zeitpunkt, naiver Zeitpunkt, Müll)."""
    try:
        z = datetime.fromisoformat(wert) if isinstance(wert, str) else wert
    except ValueError:
        return None
    return z if isinstance(z, datetime) and z.tzinfo is not None else None


def _ende(a):
    e = a.get('ende') if isinstance(a, dict) else None
    return e if isinstance(e, dict) else {}


def zustand(aufgabe, jetzt):
    """Der Status der Aufgabe zum Zeitpunkt `jetzt`: `aktiv`, `abgelaufen`, `erschoepft` – oder der Status, der schon feststeht (`erledigt`,
    `zurueckgenommen` …). Ändert das Eingabeobjekt nicht."""
    if not isinstance(aufgabe, dict):
        return 'zurueckgenommen'
    status = aufgabe.get('status')
    if status != 'aktiv':
        return status if isinstance(status, str) else 'zurueckgenommen'
    ende = _ende(aufgabe)
    if ende.get('bis') is not None:
        bis, jetzt_z = _zeit(ende['bis']), _zeit(jetzt)
        if bis is None or jetzt_z is None or jetzt_z >= bis:
            return 'abgelaufen'
    maximum = ende.get('max_aufrufe')
    if maximum is not None:
        n = aufgabe.get('aufrufe')
        if not isinstance(maximum, int) or isinstance(maximum, bool) or not isinstance(n, int) or n >= maximum:
            return 'erschoepft'
    return 'aktiv'


def deckt(aufgaben, sitzung_id, werkzeug, ziel, jetzt, passt):
    """{aufgabe_id, eintrag} der Aufgabe, die diesen Aufruf deckt – oder None. Mehrere Treffer: frühestes Ende (ohne Ende zuletzt), dann kleinste ID."""
    treffer = []
    for a in aufgaben if isinstance(aufgaben, (list, tuple)) else ():
        try:
            if not isinstance(a, dict) or zustand(a, jetzt) != 'aktiv' or sitzung_id not in (a.get('sitzungen') or []):
                continue
            eintrag = next((e for e in a.get('erlaubt') or []
                            if isinstance(e, dict) and e.get('werkzeug') == werkzeug and isinstance(e.get('muster'), str)
                            and passt(e['muster'], werkzeug, ziel)), None)
        except Exception:
            continue
        if eintrag is not None:
            bis = _zeit(_ende(a).get('bis'))
            treffer.append((bis is None, bis.timestamp() if bis else 0.0, str(a.get('id')), a, eintrag))
    if not treffer:
        return None
    treffer.sort(key=lambda t: t[:3])
    return {'aufgabe_id': treffer[0][3].get('id'), 'eintrag': treffer[0][4]}
