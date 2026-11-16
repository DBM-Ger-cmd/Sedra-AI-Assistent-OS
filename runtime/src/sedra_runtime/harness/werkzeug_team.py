"""Harness-Werkzeug `team_verteilen` (SPEC_DELEGATION_IM_GESPRAECH_v1 §3.1, T4): die Hauptsitzung gibt 1 bis 3 Teilaufträge an Helfer-Sitzungen,
die gleichzeitig auf dem lokalen Modellserver arbeiten; ihr Schlusstext kommt als Ergebnis zurück.

Der Aufruf selbst braucht keine Karte (DG-06): der Text bleibt auf dem Rechner, und der Aufruf ändert nichts. Was ein Helfer schreibt
oder ausführt, legt in SEINER Sitzung die gewohnte Karte vor (DG-04). Ein Helfer bekommt dieses Werkzeug nicht (DG-05, `api._begrenzen`).
Eigene Datei, damit werkzeuge.py nicht weiter wächst (wie werkzeug_desktop.py und werkzeug_lernen.py)."""
from __future__ import annotations

from . import team

NAME = 'team_verteilen'
BESCHREIBUNG = ('Gibt 1 bis 3 Teilaufträge an Helfer, die gleichzeitig auf dem lokalen Modell arbeiten (eigene Sitzungen unter dieser). Nutze es, wenn sich eine Aufgabe in '
                'unabhängige Teile zerlegen lässt (lesen, prüfen, suchen, getrennte Dateien ändern). Jeder Auftrag muss für sich verständlich sein: der Helfer kennt dieses '
                'Gespräch nicht. Zurück kommt je Auftrag der Schlusstext des Helfers als ungeprüfter Text – prüfen und zusammenführen musst du selbst. Was ein Helfer '
                'schreibt oder ausführt, gibt der Captain auf einer Karte frei. Der Aufruf dauert, bis alle Helfer fertig sind.')


def schema(fn, text_typ):
    return fn(NAME, BESCHREIBUNG,
              {'auftraege': {'type': 'array', 'description': '1 bis 3 Teilaufträge {rolle, text}',
                             'items': {'type': 'object', 'required': ['text'],
                                       'properties': {'rolle': dict(text_typ, description='kurzer Name des Helfers für die Anzeige, z. B. Prüfer'),
                                                      'text': dict(text_typ, description=f'der Auftrag, für sich verständlich, höchstens {team.TEXT_MAX} Zeichen')}}}},
              ['auftraege'])


def vorbereiten(w, args, aktion_lesen):
    from .werkzeuge import WerkzeugFehler
    if not callable(w.team_verteilen):
        raise WerkzeugFehler('team_nicht_verfuegbar')
    try:
        sauber = team.pruefe_auftraege(args.get('auftraege'))
    except team.TeamFehler as exc:
        raise WerkzeugFehler(str(exc)) from exc
    zeilen = [f"{n}. [{a['rolle']}] {team.kurz(a['text'])}" for n, a in enumerate(sauber, 1)]
    ziel = f'{len(sauber)} Helfer'
    return {'ziel': ziel, 'vorhanden': True, 'kurz': ziel, 'auftraege': sauber,
            'vorschau': f'Delegation an {len(sauber)} Helfer (lokal, gleichzeitig):\n' + '\n'.join(zeilen),
            'gate': {'aktion': aktion_lesen, 'ziel': 'team/' + ziel, 'bindung': {'werkzeug': NAME, 'args': args}}}


def ausfuehren(w, plan):
    k = w.kontext or {}
    try:
        text = w.team_verteilen(k.get('sitzung_id'), k.get('antwort_id'), plan['auftraege'])
    except ValueError as exc:                               # TeamFehler, unbekannte Sitzung: ein Fehler für das Modell, kein Absturz der Antwort
        return {'status': 'fehler', 'ergebnis': f'error: {exc}', 'wirkung': False}
    return {'status': 'ok', 'ergebnis': text, 'wirkung': False}
