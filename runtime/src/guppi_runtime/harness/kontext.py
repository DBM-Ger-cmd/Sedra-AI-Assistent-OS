"""Kontextfenster der Harness-Schleife (Captain 02.11.2026): schätzen, bevor gesendet wird, und rechtzeitig handeln – nie den rohen Serverfehler.

Drei Stufen vor jedem Modellaufruf (Anteile des Fensters, inklusive der Token, die die Antwort noch braucht):
  ab SICHERUNG_KUERZEN (90 %)  → der Verlauf wird stärker gekürzt (nur das Neueste bleibt ganz), gekürzte Stellen sind markiert
  ab SICHERUNG_ABSCHLUSS (95 %) → nach dem Kürzen noch zu voll: das Modell antwortet jetzt ohne Werkzeuge (Abschluss)
  ab SICHERUNG_ENDE (100 %)     → es passt auch dann nicht: die Antwort endet mit einem klaren Hinweis (neue Sitzung oder zusammenfassen)
Geschätzt wird vorsichtig (3 Zeichen je Token, gemessen waren 3,5 bei Code und Text); liegt von der letzten Antwort die echte Belegung vor, gilt sie plus das, was seither dazukam."""
from __future__ import annotations

import json

ZEICHEN_JE_TOKEN = 3.0
SCHEMA_ZEICHEN_JE_TOKEN = 4.0          # gemessen: 12 000 Zeichen Werkzeugschemas = rund 2 000 Token in der Vorlage von Gemma
KUERZEN_KEEP_LAST = 4
KUERZEN_MAX_CHARS = 300
SICHERUNG_KUERZEN = 0.90
SICHERUNG_ABSCHLUSS = 0.95
SICHERUNG_ENDE = 1.00
MARKE = ' […gekürzt – bei Bedarf neu lesen oder mit erinnern holen…] '


def _zeichen(messages):
    n = 0
    for m in messages:
        n += len(str(m.get('content') or ''))
        for c in m.get('tool_calls') or []:
            n += len(json.dumps(c, ensure_ascii=False))
    return n


def schaetzen(messages, schemas=None, reserve=0, letzte=None):
    """Geschätzte Token des nächsten Aufrufs samt `reserve` (Token der Antwort). `letzte`: {'belegt': echte Token des letzten Aufrufs samt Antwort,
    'anzahl': so viele Nachrichten standen damals schon im Verlauf} – dann zählt die echte Zahl plus nur das Neue."""
    schema = len(json.dumps(schemas, ensure_ascii=False)) / SCHEMA_ZEICHEN_JE_TOKEN if schemas else 0
    gesamt = _zeichen(messages) / ZEICHEN_JE_TOKEN + schema
    if letzte and letzte.get('belegt'):
        neu = messages[letzte['anzahl']:] if 0 <= letzte['anzahl'] <= len(messages) else messages
        gesamt = max(gesamt, letzte['belegt'] + _zeichen(neu) / ZEICHEN_JE_TOKEN)           # die Schätzung nach Zeichen darf die echte Zahl nie unterbieten
    return int(gesamt + reserve)


def pruefen(geschaetzt, fenster):
    """'ok' | 'kuerzen' | 'abschluss' | 'voll' – was vor dem Senden zu tun ist."""
    if not fenster:
        return 'ok'
    anteil = geschaetzt / fenster
    if anteil >= SICHERUNG_ENDE:
        return 'voll'
    if anteil >= SICHERUNG_ABSCHLUSS:
        return 'abschluss'
    if anteil >= SICHERUNG_KUERZEN:
        return 'kuerzen'
    return 'ok'


def hinweis_voll(geschaetzt, fenster):
    return (f'Das Kontextfenster ist fast voll (etwa {geschaetzt:,} von {fenster:,} Token). Beginne eine neue Sitzung, oder fasse das Gespräch '
            'in den Einstellungen (Agent → Gedanken der Modelle) zusammen und wähle ein größeres Fenster im Modell-Knopf.').replace(',', '.')
