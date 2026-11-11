"""Update einer eingebauten fremden App (AM3-13 bis AM3-15): Versionsvergleich, Datei-Diff mit Text-Diff, Hilfen für das Gate. Rein, nur Dateien lesen."""
from __future__ import annotations

import difflib
import re
from pathlib import Path

import yaml

TEXT_GRENZE = 50 * 1024          # AM3-14: Text-Diff für Dateien bis 50 KB
DIFF_ZEILEN = 200               # je Datei höchstens so viele Zeilen im Gate
_VERSION = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')


def version_hoeher(alt, neu) -> bool:
    a, n = _VERSION.match(str(alt)), _VERSION.match(str(neu))
    if not a or not n:
        return False
    return tuple(map(int, n.groups())) > tuple(map(int, a.groups()))


def manifest_normal(pfad: Path, key='tool') -> str:
    """Das Manifest, wie der Einbau es schreibt: Vertrauen COMMUNITY, einheitlich ausgegeben – so vergleichen Quelle und eingebaute Fassung gleich."""
    doc = yaml.safe_load(Path(pfad).read_text(encoding='utf-8'))
    if isinstance(doc, dict) and isinstance(doc.get(key), dict):
        doc[key]['trust'] = 'COMMUNITY'
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)


def datei_diff(alt_ordner: Path, neu_ordner: Path, alt_dateien, neu_dateien):
    """alt_dateien/neu_dateien: Listen {path, bytes, sha256} aus install.read_module. Liefert [{pfad, art: neu|entfernt|geaendert, bytes_alt, bytes_neu, sha_alt, sha_neu, text?}]."""
    alt = {d['path']: d for d in alt_dateien}
    neu = {d['path']: d for d in neu_dateien}
    erg = []
    for pfad in sorted(set(alt) | set(neu)):
        a, n = alt.get(pfad), neu.get(pfad)
        eintrag = {'pfad': pfad, 'bytes_alt': a and a['bytes'], 'bytes_neu': n and n['bytes'], 'sha_alt': a and a['sha256'], 'sha_neu': n and n['sha256']}
        if a is None:
            eintrag['art'] = 'neu'
        elif n is None:
            eintrag['art'] = 'entfernt'
        else:
            alt_text = _text(alt_ordner / pfad, pfad)
            neu_text = _text(neu_ordner / pfad, pfad)
            if pfad == 'tool.yaml':                          # beide Seiten in der Form des Einbaus, sonst wäre jedes Manifest „geändert“ (Vertrauen)
                alt_text, neu_text = manifest_normal(alt_ordner / pfad), manifest_normal(neu_ordner / pfad)
                eintrag['sha_neu'] = _sha_text(neu_text)
                eintrag['sha_alt'] = _sha_text(alt_text)
            if eintrag['sha_alt'] == eintrag['sha_neu']:
                continue
            eintrag['art'] = 'geaendert'
            if alt_text is not None and neu_text is not None and max(a['bytes'], n['bytes']) <= TEXT_GRENZE:
                zeilen = list(difflib.unified_diff(alt_text.splitlines(), neu_text.splitlines(), 'alt', 'neu', lineterm='', n=1))
                eintrag['text'] = zeilen[:DIFF_ZEILEN] + (['… (gekürzt)'] if len(zeilen) > DIFF_ZEILEN else [])
        erg.append(eintrag)
    return erg


def _text(pfad: Path, rel: str):
    try:
        return Path(pfad).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return None


def _sha_text(text):
    import hashlib
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()
