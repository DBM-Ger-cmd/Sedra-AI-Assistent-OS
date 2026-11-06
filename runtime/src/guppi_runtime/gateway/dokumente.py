"""Lesen der Dokumente, die ein Vorgang mitnehmen darf: .txt und .md (UTF-8) und .docx (Word, ohne Zusatzpaket).

Ein .docx ist ein ZIP-Archiv; der Text steht in `word/document.xml`. Gelesen wird nur dieser Teil, mit der Standardbibliothek.
Makros, Verknüpfungen, Bilder und Kopf-/Fußzeilen werden nicht gelesen. Alles, was sich nicht sauber lesen lässt, ist ein Fehler
(fail-closed, R-16): dann geht der Vorgang nicht weiter. Der gelesene Text läuft wie jedes andere Dokument durch den Inhaltsschutz.
.doc (das alte Binärformat) und .pdf werden nicht gelesen.
"""
from __future__ import annotations

from pathlib import Path

ENDUNGEN = ('.md', '.txt', '.docx')
# Grenzen und Lesen des Word-Archivs: wissen/leser/docx.py (MAX_XML_BYTES, nur word/document.xml)


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
    """Absätze untereinander, Tabulator und Zeilenumbruch wie im Dokument. Kein Layout, keine Tabellenstruktur.
    Der Leser liegt seit SPEC_WISSEN_KERN_v1 K5-3 im Kern (`wissen/leser/docx.py`); hier nur der Fehler des GateWay."""
    from ..wissen.leser import docx as docx_leser
    try:
        return docx_leser.text(path)
    except ValueError:
        raise DokumentFehler() from None
