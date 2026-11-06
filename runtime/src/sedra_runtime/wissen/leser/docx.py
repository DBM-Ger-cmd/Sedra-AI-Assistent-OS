"""Word (.docx) ohne Zusatzpaket (SPEC_WISSEN_KERN_v1 WK-20; vorher nur im GateWay, `gateway/dokumente.py`, das jetzt von hier liest).

Ein .docx ist ein ZIP-Archiv; gelesen wird nur `word/document.xml`, höchstens MAX_XML_BYTES entpackt (Schutz vor übergroßen Archiven).
Makros, Verknüpfungen, Bilder, Kopf- und Fußzeilen bleiben ungelesen. Zwei Formen:
- `text(pfad)`: Absätze untereinander, Tabulator und Zeilenumbruch wie im Dokument (so las das GateWay bisher; unverändert).
- `markdown(pfad)`: für das Wissen – Überschriften (Formatvorlage „Heading n“/„Überschrift n“/„Title“) werden zu Markdown-Köpfen,
  Tabellen zu Zeilen „Zelle | Zelle“, damit `zerlegen.zerlege_markdown` Stellen mit Überschriftenpfad bildet.
Nicht lesbar → ValueError('wis_docx_nicht_lesbar')."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

MAX_XML_BYTES = 20 * 1024 * 1024
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
KOPF = re.compile(r'(?:heading|berschrift|titel|title)\s*(\d?)', re.IGNORECASE)
ZELLE_MAX = 500
FEHLER = 'wis_docx_nicht_lesbar'


def _wurzel(path: Path):
    try:
        with zipfile.ZipFile(path) as archiv:
            info = archiv.getinfo('word/document.xml')
            if info.file_size > MAX_XML_BYTES:
                raise ValueError(FEHLER)
            return ET.fromstring(archiv.read('word/document.xml'))
    except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError, RuntimeError, ValueError):   # RuntimeError: verschlüsseltes ZIP
        raise ValueError(FEHLER) from None


def _lauftext(absatz):
    teile = []
    for el in absatz.iter():
        if el.tag == W + 't':
            teile.append(el.text or '')
        elif el.tag == W + 'tab':
            teile.append('\t')
        elif el.tag == W + 'br':
            teile.append('\n')
    return ''.join(teile)


def text(path: Path) -> str:
    """Absätze untereinander (die Form des GateWay)."""
    return '\n'.join(_lauftext(a) for a in _wurzel(Path(path)).iter(W + 'p')).strip()


def _ebene(absatz):
    stil = absatz.find(f'{W}pPr/{W}pStyle')
    wert = stil.get(W + 'val') if stil is not None else ''
    m = KOPF.match(wert or '')
    if not m:
        return 0
    return min(int(m.group(1) or 1), 6)


def _tabelle(tbl):
    zeilen = []
    for tr in tbl.iter(W + 'tr'):
        zellen = [' '.join(_lauftext(p) for p in tc.iter(W + 'p')).strip()[:ZELLE_MAX] for tc in tr.findall(W + 'tc')]
        if any(zellen):
            zeilen.append(' | '.join(zellen))
    return '\n'.join(zeilen)


def markdown(path: Path) -> str:
    """Der Inhalt als Markdown: Köpfe aus den Formatvorlagen, Absätze, Tabellen als Zeilen."""
    body = _wurzel(Path(path)).find(W + 'body')
    if body is None:
        raise ValueError(FEHLER)
    bloecke = []
    for el in body:
        if el.tag == W + 'p':
            t = _lauftext(el).strip()
            if not t:
                continue
            ebene = _ebene(el)
            bloecke.append(('#' * ebene + ' ' + ' '.join(t.split())) if ebene else t)
        elif el.tag == W + 'tbl':
            t = _tabelle(el)
            if t:
                bloecke.append(t)
    return '\n\n'.join(bloecke)
