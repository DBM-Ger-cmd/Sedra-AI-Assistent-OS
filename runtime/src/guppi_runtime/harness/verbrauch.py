"""Token-Verbrauch der Harness (Captain 02.11.2026): was eine Sitzung und der Tag an Token gebraucht haben – eingehend (was an das Modell ging, jeder Zug zählt
den ganzen Verlauf neu) und erzeugt (was das Modell geschrieben hat, Denken eingeschlossen). Es wird nur gezählt, aus den Zeilen `modell` der Sitzungsdateien; kein Inhalt."""
from __future__ import annotations

from datetime import datetime


def _zahl(x):
    return x if type(x) is int and x >= 0 else 0


def summe(eintraege, tag=None):
    """{antworten, zuege, ein, aus, modell_s, tok_s, letzte, kontext} über die Modellzeilen; mit `tag` ('JJJJ-MM-TT') nur die dieses Tages."""
    out = {'antworten': 0, 'zuege': 0, 'ein': 0, 'aus': 0, 'modell_s': 0.0, 'tok_s': None, 'letzte': None, 'kontext': None}
    aus_mit_zeit = 0
    for e in eintraege:
        if e.get('typ') != 'modell' or not isinstance(e.get('token'), dict):
            continue
        if tag and not str(e.get('zeit') or '').startswith(tag):
            continue
        ein, aus = _zahl(e['token'].get('ein')), _zahl(e['token'].get('aus'))
        out['antworten'] += 1
        out['zuege'] += _zahl(e.get('zuege'))
        out['ein'] += ein
        out['aus'] += aus
        s = e.get('modell_s')
        if isinstance(s, (int, float)) and s > 0:
            out['modell_s'] += s
            aus_mit_zeit += aus
        out['letzte'] = {'antwort_id': e.get('antwort_id'), 'ein': ein, 'aus': aus, 'zuege': _zahl(e.get('zuege')),
                         'tok_s': round(aus / s, 1) if isinstance(s, (int, float)) and s > 0 and aus else None}
        if isinstance(e.get('kontext'), list) and len(e['kontext']) == 2:
            out['kontext'] = {'belegt': _zahl(e['kontext'][0]), 'fenster': _zahl(e['kontext'][1])}
    out['modell_s'] = round(out['modell_s'], 1)
    if out['modell_s'] > 0 and aus_mit_zeit:
        out['tok_s'] = round(aus_mit_zeit / out['modell_s'], 1)
    return out


def heute():
    return datetime.now().astimezone().date().isoformat()
