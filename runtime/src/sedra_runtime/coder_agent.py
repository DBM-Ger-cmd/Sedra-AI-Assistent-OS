"""Agenten-Anbindung der App Coder (nur Antworten, kein Schreibweg): Prüfung der Eingabe, Dateikontext, Nachrichten.

Der Coder darf ein Modell fragen (lokal oder über eine eingeschaltete Cloud-Anbindung) und bekommt Text zurück. Das Modell kann nichts
anlegen, ändern oder ausführen; Änderungen kommen als Vorschlag im Text. Dateien, die als Kontext mitgehen, werden über dieselben Wege
gelesen wie im Explorer, also mit Sperrliste (coder_lesen.py). Der Text der Frage und der Dateien kommt nie ins Audit.
"""
from __future__ import annotations

import re

from . import coder_lesen

TEXT_MAX = 4000
DATEIEN_MAX = 5
DATEI_ZEICHEN = 6000
GESAMT_ZEICHEN = 16000
VERLAUF_MAX = 8
ANTWORT_TOKEN = 1500
ROUTEN = ('lokal', 'cloud')
MODI = ('plan', 'act')
ANBIETER = re.compile(r'^[a-z0-9-]{1,40}$')

SYSTEM = ('Du bist ein Programmier-Assistent in der Entwicklungsoberfläche Sedra IDE. Du kannst Dateien nur lesen, die dir als Kontext mitgegeben '
          'werden, und du kannst nichts speichern, ausführen oder ändern. Schlage Änderungen als Text vor (kurze Codeblöcke mit Dateiname), '
          'der Mensch übernimmt sie selbst. Antworte auf Deutsch, knapp und konkret. Wenn dir Dateien fehlen, sag welche.')
MODUS_HINWEIS = {
    'plan': 'Modus Plan: erst einen kurzen Plan in Schritten nennen, noch keinen fertigen Code.',
    'act': 'Modus Act: den Vorschlag direkt ausarbeiten (Codeblöcke), weiterhin ohne etwas zu speichern.',
}


def pruefe(payload) -> dict:
    """Eingabe prüfen und in eine feste Form bringen. Fehler nur als Kennwort."""
    if not isinstance(payload, dict):
        raise ValueError('invalid_payload')
    projekt = str(payload.get('projekt') or '').strip()
    if not projekt or len(projekt) > 60 or any(c in projekt for c in '/\\?# '):
        raise ValueError('invalid_project')
    text = str(payload.get('text') or '').strip()
    if not text or len(text) > TEXT_MAX:
        raise ValueError('text_invalid')
    route = str(payload.get('route') or 'lokal')
    if route not in ROUTEN:
        raise ValueError('invalid_route')
    modus = str(payload.get('modus') or 'plan')
    if modus not in MODI:
        raise ValueError('invalid_mode')
    anbieter = str(payload.get('provider') or '')
    modell = str(payload.get('model') or '')
    if route == 'cloud' and (not ANBIETER.match(anbieter) or not modell or len(modell) > 120):
        raise ValueError('cloud_choice_invalid')
    dateien = payload.get('dateien') or []
    if not isinstance(dateien, list) or len(dateien) > DATEIEN_MAX or not all(isinstance(d, str) and 0 < len(d) <= coder_lesen.PFAD_MAX for d in dateien):
        raise ValueError('invalid_files')
    verlauf = payload.get('history') or []
    if not isinstance(verlauf, list) or len(verlauf) > 20:
        raise ValueError('invalid_history')
    turns = []
    for h in verlauf[-VERLAUF_MAX:]:
        if not isinstance(h, dict) or h.get('role') not in ('user', 'assistant') or not isinstance(h.get('content'), str):
            raise ValueError('invalid_history')
        turns.append({'role': h['role'], 'content': h['content'][:TEXT_MAX]})
    return {'projekt': projekt, 'text': text, 'route': route, 'modus': modus, 'provider': anbieter, 'model': modell,
            'dateien': list(dict.fromkeys(dateien)), 'history': turns}


def kontext(pfade, lese):
    """Dateitext als Kontext. `lese(pfad)` ist die Lese-Funktion mit Sperrliste und wirft bei Fehlern. Gibt (Text, belegt, ausgelassen) zurück;
    belegt: Pfad, Zeichen, gekuerzt. ausgelassen: Pfad und Grund (gesperrt, binaer, zu_gross, nicht_lesbar, kein_platz)."""
    teile, belegt, aus, rest = [], [], [], GESAMT_ZEICHEN
    for pfad in pfade:
        if coder_lesen.pfad_gesperrt(pfad):
            aus.append({'pfad': pfad, 'grund': 'gesperrt'})
            continue
        if rest <= 0:
            aus.append({'pfad': pfad, 'grund': 'kein_platz'})
            continue
        try:
            r = lese(pfad)
        except Exception:
            aus.append({'pfad': pfad, 'grund': 'nicht_lesbar'})
            continue
        if r.get('binary'):
            aus.append({'pfad': pfad, 'grund': 'binaer'})
            continue
        if r.get('too_large'):
            aus.append({'pfad': pfad, 'grund': 'zu_gross'})
            continue
        inhalt = str(r.get('inhalt') or '')
        grenze = min(DATEI_ZEICHEN, rest)
        gekuerzt = len(inhalt) > grenze
        inhalt = inhalt[:grenze]
        rest -= len(inhalt)
        teile.append('--- Datei: ' + pfad + (' (gekürzt)' if gekuerzt else '') + ' ---\n' + inhalt)
        belegt.append({'pfad': pfad, 'zeichen': len(inhalt), 'gekuerzt': gekuerzt})
    return '\n\n'.join(teile), belegt, aus


def nachrichten(p, kontext_text):
    system = SYSTEM + ' ' + MODUS_HINWEIS[p['modus']]
    frage = (kontext_text + '\n\n--- Frage ---\n' if kontext_text else '') + p['text']
    return [{'role': 'system', 'content': system}, *p['history'], {'role': 'user', 'content': frage}]


def modelle(cfg_view, geladen) -> dict:
    """Welche Wege es gibt, nur Namen und Zustand. `cfg_view` ist cloud_settings.view(...), `geladen` die Liste geladener lokaler Modelle."""
    lokal = [str(m.get('identifier') or m.get('modelKey') or '') for m in (geladen or []) if isinstance(m, dict)]
    lokal = [m for m in lokal if m]
    cloud = []
    if cfg_view.get('enabled'):
        for pr in cfg_view.get('providers', []):
            if pr.get('enabled') and pr.get('status') == 'bereit' and pr.get('default_model'):
                cloud.append({'id': pr['id'], 'modell': str(pr['default_model'])})
    return {'lokal': {'bereit': bool(lokal), 'modell': lokal[0] if lokal else None}, 'cloud': {'an': bool(cfg_view.get('enabled')), 'anbieter': cloud}}
