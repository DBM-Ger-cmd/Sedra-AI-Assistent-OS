"""Erkenntnisse aus einem Transkript (Fisch, 19.10.2026) – der SEDRA-KI-Zugang nach VoiceBrief: aus dem Gespräch werden Zusammenfassung,
Entscheidungen, offene Fragen und Aufgaben. Die Erkenntnis ist an die Fassung gebunden, aus der sie kam (VoiceBrief: Wissen hängt an
der Eingabe-Version); eine neue Fassung macht sie nicht falsch, aber alt – das Werkzeug zeigt es. Rein: Nachricht hin, Blöcke zurück."""
from __future__ import annotations

import re

MAX_ZEICHEN = 60_000
BLOECKE = ('ZUSAMMENFASSUNG', 'ENTSCHEIDUNGEN', 'OFFENE FRAGEN', 'AUFGABEN')
SCHLUESSEL = {'ZUSAMMENFASSUNG': 'zusammenfassung', 'ENTSCHEIDUNGEN': 'entscheidungen', 'OFFENE FRAGEN': 'offen', 'AUFGABEN': 'aufgaben'}

SYSTEM = (
    'Du bist SEDRA und liest ein Transkript eines Gesprächs. Du erfindest nichts: nur, was im Transkript steht. Antworte auf Deutsch '
    'in genau diesen vier Blöcken, jeder beginnt mit seinem Namen und einem Doppelpunkt in einer eigenen Zeile:\n'
    'ZUSAMMENFASSUNG: drei bis sechs Sätze, worum es ging.\n'
    'ENTSCHEIDUNGEN: je Zeile ein „- “, was entschieden wurde; „- keine“ wenn nichts.\n'
    'OFFENE FRAGEN: je Zeile ein „- “, was offen blieb oder unklar ist; „- keine“ wenn nichts.\n'
    'AUFGABEN: je Zeile ein „- “, was jemand tun soll, mit Wer und Bis-wann, falls genannt; „- keine“ wenn nichts.\n'
    'Platzhalter wie [PERSON_1] oder [FIRMA_2] lässt du stehen, wie sie sind.'
)


def nachricht(t, cues):
    text = ' '.join(c['text'] for c in cues)
    if not text.strip(): raise ValueError('transkript_leer')
    if len(text) > MAX_ZEICHEN: text = text[:MAX_ZEICHEN] + ' …'
    return f"Titel: {t['titel']}\nSprache: {t['sprache']}\nTranskript:\n{text}"


def _liste(block):
    out = []
    for z in block.split('\n'):
        z = re.sub(r'^\s*[-•*]\s*', '', z).strip()
        if z and z.lower() not in ('keine', 'keine.', '–', '-'): out.append(z[:400])
    return out[:40]


def lesen(text):
    """Die vier Blöcke aus der Antwort; fehlt ein Block, bleibt er leer – es wird nichts dazuerfunden."""
    text = str(text or '').replace('\r\n', '\n')
    pos = []
    for name in BLOECKE:
        m = re.search(r'^\s*\**' + re.escape(name) + r'\**\s*:\s*', text, re.M | re.I)
        if m: pos.append((m.start(), m.end(), name))
    pos.sort()
    out = {'zusammenfassung': '', 'entscheidungen': [], 'offen': [], 'aufgaben': []}
    for i, (start, end, name) in enumerate(pos):
        block = text[end:pos[i + 1][0] if i + 1 < len(pos) else len(text)].strip()
        k = SCHLUESSEL[name]
        out[k] = ' '.join(block.split())[:2000] if k == 'zusammenfassung' else _liste(block)
    if not pos: out['zusammenfassung'] = ' '.join(text.split())[:2000]
    return out
