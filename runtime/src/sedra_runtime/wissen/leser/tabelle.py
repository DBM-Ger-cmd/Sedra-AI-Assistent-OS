"""CSV ohne Zusatzpaket (SPEC_WISSEN_KERN_v1 WK-20, G2 K5 §2.3): Trennzeichen erkennen (, ; Tab |), erste Zeile als Kopf, je Zeile
„Spalte: Wert; Spalte: Wert“. Je BLOCK Zeilen ein Abschnitt unter „## Zeilen a–b“, damit die Fundstelle sagt, wo es steht.
Kodierung UTF-8 (mit oder ohne BOM), sonst Windows-1252 (so speichert Excel unter Windows). Leere Werte fallen weg.
Nicht lesbar → ValueError('wis_csv_nicht_lesbar')."""
from __future__ import annotations

import csv
import io
from pathlib import Path

BLOCK = 25
SPALTEN_MAX = 50
WERT_MAX = 500
FEHLER = 'wis_csv_nicht_lesbar'


def _dekodieren(roh: bytes) -> str:
    try:
        return roh.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            return roh.decode('cp1252')
        except UnicodeDecodeError:
            raise ValueError(FEHLER) from None


def _trenner(probe: str) -> str:
    try:
        return csv.Sniffer().sniff(probe, delimiters=',;\t|').delimiter
    except csv.Error:
        zahlen = {t: probe.count(t) for t in (';', ',', '\t', '|')}
        return max(zahlen, key=zahlen.get) if any(zahlen.values()) else ','


def markdown(path: Path) -> str:
    path = Path(path)
    try:
        text = _dekodieren(path.read_bytes())
    except OSError:
        raise ValueError(FEHLER) from None
    if not text.strip():
        return ''
    try:
        zeilen = list(csv.reader(io.StringIO(text), delimiter=_trenner(text[:65536])))
    except csv.Error:
        raise ValueError(FEHLER) from None
    zeilen = [z for z in zeilen if any(c.strip() for c in z)]
    if not zeilen:
        return ''
    kopf = [(c.strip() or f'Spalte {i + 1}')[:80] for i, c in enumerate(zeilen[0][:SPALTEN_MAX])]
    daten = zeilen[1:]
    teile = ['# ' + path.name, 'Spalten: ' + ', '.join(kopf)]
    for start in range(0, len(daten), BLOCK):
        block = daten[start:start + BLOCK]
        teile.append(f'## Zeilen {start + 2}–{start + 1 + len(block)}')
        for z in block:
            paare = [f'{kopf[i] if i < len(kopf) else f"Spalte {i + 1}"}: {" ".join(w.split())[:WERT_MAX]}' for i, w in enumerate(z[:SPALTEN_MAX]) if w.strip()]
            teile.append('- ' + '; '.join(paare))
    return '\n\n'.join(teile)
