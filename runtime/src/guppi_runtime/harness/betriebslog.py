"""Betriebslog der Harness (Captain 05.11.2026: die Info-Liste soll ein Log werden, in dem auch frühere Verläufe bleiben und das in die Wissensdatenbank einläuft).

Aus dem Audit-Log (Quelle der Wahrheit, bleibt unverändert) schreibt dieses Modul die wichtigen Ereignisse in Klartext in eine Markdown-Datei je Tag unter
`<Projekt>/runtime_data/harness/betriebslog/JJJJ-MM-TT.md`. Die Dateien wachsen nur (angehängt); ein Merkzettel (`_stand.json`) hält fest, bis zu welchem Ereignis gesichert ist.
Der Ordner ist die Quelle für die Wissensdatenbank (Adapter `markdown`, Wurzel `projekt`; der Captain gibt sie im Posteingang frei). Rauschen (Modellaufrufe, Oberflächenereignisse)
kommt nicht hinein, nur Modelle, Fehler, Freigaben und Neustarts – die gleiche Einteilung wie die Info-Seite (`info._art`)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import info

ORDNER = ('runtime_data', 'harness', 'betriebslog')
STAND = '_stand.json'
TAG = re.compile(r'20[0-9]{2}-[01][0-9]-[0-3][0-9]')
QUELLE_PFAD = '/'.join(ORDNER)                              # so steht der Ordner in der Quelle der Wissensdatenbank (Wurzel „projekt“)
MAX_NEU = 5000                                              # höchstens so viele Ereignisse je Durchlauf, ein riesiger Rückstand wird in Schritten abgearbeitet


def ordner(projekt_root):
    return Path(projekt_root).joinpath(*ORDNER)


def _zeit(e):
    return str(e.get('timestamp') or '')


def _wichtig(e):
    return info._art(e.get('event_type') or '') != 'sonst' or e.get('event_type') == 'BOOT_STARTED'


def _stand_lesen(pfad):
    try:
        return str(json.loads((pfad / STAND).read_text(encoding='utf-8')).get('bis') or '')
    except (OSError, ValueError):
        return ''


def sichern(audit_pfad, projekt_root):
    """Neue wichtige Ereignisse seit dem Merkzettel in die Tagesdateien anhängen; gibt {'neu': Anzahl, 'tage': [..]} zurück. Wirft ValueError, wenn das Audit-Log nicht lesbar ist."""
    ziel = ordner(projekt_root)
    ziel.mkdir(parents=True, exist_ok=True)
    bis = _stand_lesen(ziel)
    neu = [e for e in info._lesen(audit_pfad) if _zeit(e) > bis][:MAX_NEU]
    if not neu:
        return {'neu': 0, 'tage': []}
    je_tag, letzte = {}, bis
    for e in neu:
        letzte = max(letzte, _zeit(e))
        if _wichtig(e):
            je_tag.setdefault(_zeit(e)[:10], []).append('- %s %s' % (_zeit(e)[11:19], info.klartext(e)))
    for tag, zeilen in je_tag.items():
        if not TAG.fullmatch(tag):
            continue
        datei = ziel / (tag + '.md')
        kopf = '' if datei.exists() else '# Betriebslog %s\n\nWas Sedra an diesem Tag getan hat (Zeiten in UTC): Modelle, Fehler, Freigaben, Neustarts.\n\n' % tag
        with datei.open('a', encoding='utf-8', newline='\n') as f:
            f.write(kopf + '\n'.join(zeilen) + '\n')
    (ziel / STAND).write_text(json.dumps({'bis': letzte}), encoding='utf-8')
    return {'neu': sum(len(z) for z in je_tag.values()), 'tage': sorted(je_tag)}


def tage(projekt_root):
    """Die gesicherten Tage, neueste zuerst, mit Anzahl der Zeilen."""
    out = []
    for p in sorted(ordner(projekt_root).glob('*.md'), reverse=True):
        if TAG.fullmatch(p.stem):
            try:
                out.append({'tag': p.stem, 'zeilen': sum(1 for z in p.read_text(encoding='utf-8').splitlines() if z.startswith('- '))})
            except OSError:
                continue
    return out


def tag_lesen(projekt_root, tag):
    """Der Text eines Tages; der Tag muss die Form JJJJ-MM-TT haben (kein Pfad von außen)."""
    if not TAG.fullmatch(str(tag or '')):
        raise ValueError('tag_ungueltig')
    try:
        return (ordner(projekt_root) / (tag + '.md')).read_text(encoding='utf-8')
    except OSError:
        raise ValueError('tag_unbekannt')
