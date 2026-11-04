"""Rückfall der Gesprächs-Zusammenfassung ohne Modell (Plan CPU-Hilfswerkzeuge, F3): bleibt die Antwort des Modells leer (`zusammenfassung_leer`, 03.11.2026),
wächst der Verlauf sonst ungebremst weiter. Dann steht an der Stelle ein **Auszug**: je Nachricht der erste Satz, die des Captains etwas länger, ohne Deutung.
Rein, nur Standardbibliothek. Der Text sagt selbst, dass er ein Auszug ist, damit das Modell ihn nicht für eine Zusammenfassung hält."""
from __future__ import annotations

import re

KOPF = '[Auszug ohne Modell: die ersten Sätze der früheren Nachrichten, keine Zusammenfassung – Einzelheiten stehen im Verlauf und im Gedächtnis]'
SATZ_ENDE = re.compile(r'(?<=[.!?])\s+|\n+')
LAENGE = {'captain': 220, 'modell': 140}


def erster_satz(text, grenze):
    """Der erste Satz (oder die erste Zeile) des Textes, auf `grenze` Zeichen gekürzt; Leerraum zusammengezogen."""
    t = str(text or '').strip()
    if not t: return ''
    satz = SATZ_ENDE.split(t, maxsplit=1)[0].strip()
    satz = ' '.join(satz.split())
    return satz if len(satz) <= grenze else satz[:grenze - 1].rstrip() + '…'


def auszug(bisher, nachrichten, maximal=1800):
    """Der Auszug: Kopf, dann die bisherige Zusammenfassung (falls es eine gibt, ohne ihren alten Kopf), dann je neue Nachricht eine Zeile.
    Ist es zu lang, fallen die ältesten Zeilen weg – die neuesten bleiben. Immer höchstens `maximal` Zeichen."""
    alt = [z for z in str(bisher or '').splitlines() if z.strip() and z.strip() != KOPF]
    neu = []
    for e in nachrichten or []:
        art = 'captain' if e.get('typ') == 'captain' else 'modell'
        satz = erster_satz(e.get('text'), LAENGE[art])
        if satz: neu.append(('Captain' if art == 'captain' else 'SEDRA') + ': ' + satz)
    zeilen = alt + ['- ' + z for z in neu]
    while zeilen and len('\n'.join([KOPF] + zeilen)) > maximal:
        zeilen.pop(0)
    return '\n'.join([KOPF] + zeilen)[:maximal]
