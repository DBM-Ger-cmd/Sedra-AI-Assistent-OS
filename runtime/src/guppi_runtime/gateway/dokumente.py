"""Lesen der Dokumente, die ein Vorgang mitnehmen darf: .txt und .md (UTF-8) und .docx (Word, ohne Zusatzpaket).

Ein .docx ist ein ZIP-Archiv; der Text steht in `word/document.xml`. Gelesen wird nur dieser Teil, mit der Standardbibliothek.
Makros, Verknüpfungen, Bilder und Kopf-/Fußzeilen werden nicht gelesen. Alles, was sich nicht sauber lesen lässt, ist ein Fehler
(fail-closed, R-16): dann geht der Vorgang nicht weiter. Der gelesene Text läuft wie jedes andere Dokument durch den Inhaltsschutz.
.doc (das alte Binärformat) und .pdf werden nicht gelesen.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ENDUNGEN = ('.md', '.txt', '.docx')
MAX_XML_BYTES = 20 * 1024 * 1024          # entpackt; schützt vor übergroßen Archiven
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


class DokumentFehler(ValueError):
    """Die Datei lässt sich nicht lesen. Der Code ist `dokument_nicht_lesbar`, wie bisher für Textdateien."""

    def __init__(self):
        super().__init__('dokument_nicht_lesbar')


def lies_datei(path: Path) -> str:
    """Den Text einer Anhangdatei. Wirft DokumentFehler, wenn sie nicht lesbar ist oder die Endung nicht erlaubt ist."""
    endung = path.suffix.lower()
    if endung in ('.md', '.txt'):
        try:
            return path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            raise DokumentFehler()
    if endung == '.docx':
        return lies_docx(path)
    raise DokumentFehler()


def lies_docx(path: Path) -> str:
    """Absätze untereinander, Tabulator und Zeilenumbruch wie im Dokument. Kein Layout, keine Tabellenstruktur."""
    try:
        with zipfile.ZipFile(path) as archiv:
            info = archiv.getinfo('word/document.xml')
            if info.file_size > MAX_XML_BYTES:
                raise DokumentFehler()
            wurzel = ET.fromstring(archiv.read('word/document.xml'))
    except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError, RuntimeError, ValueError):   # RuntimeError: verschlüsseltes ZIP
        raise DokumentFehler()
    absaetze = []
    for absatz in wurzel.iter(W + 'p'):
        teile = []
        for el in absatz.iter():
            if el.tag == W + 't':
                teile.append(el.text or '')
            elif el.tag == W + 'tab':
                teile.append('\t')
            elif el.tag == W + 'br':
                teile.append('\n')
        absaetze.append(''.join(teile))
    return '\n'.join(absaetze).strip()
