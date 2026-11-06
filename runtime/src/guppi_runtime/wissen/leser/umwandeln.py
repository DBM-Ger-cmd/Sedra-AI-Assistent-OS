"""Umwandeln in einem EIGENEN Prozess (SPEC_WISSEN_KERN_v1 WK-20, G2 K5 §2.3, D-K5-3): PDF, Excel und PowerPoint zu Markdown über die
Hilfswerkzeuge – zuerst MarkItDown, für PDF sonst `pypdf` (nur Text). Sedra installiert nichts; fehlt beides, endet der Prozess mit
Code 3 und der Aufrufer vermerkt die Datei als `uebersprungen` mit dem Installationsbefehl.

Aufruf (nur von `leser/extern.py`): `python -I umwandeln.py <datei>`. Bewusst ohne Import von guppi_runtime: das Skript läuft isoliert
(-I: kein Benutzer-site, keine Umgebungsvariablen von Python), mit Zeitgrenze und begrenzter Ausgabe. Ausgabe: UTF-8 auf stdout.
Codes: 0 ok · 2 Fehler beim Lesen · 3 Hilfswerkzeug fehlt · 4 kein Text (z. B. gescannte PDF; Texterkennung kommt mit W5).
Nur für Tests: SEDRA_UMWANDELN_OHNE=markitdown,pypdf tut so, als fehlten diese Pakete."""
import os
import sys

OK, FEHLER, FEHLT, KEIN_TEXT = 0, 2, 3, 4
ARTEN = (".pdf", ".xlsx", ".pptx")


def _ohne():
    return {x.strip() for x in os.environ.get("SEDRA_UMWANDELN_OHNE", "").split(",") if x.strip()}


ROH = ("%PDF", "PK\x03\x04", "PK\x05\x06")                         # so beginnt die Datei selbst, nicht ihr Text


def mit_markitdown(pfad):
    if "markitdown" in _ohne():
        raise ImportError("markitdown")
    from markitdown import MarkItDown
    text = MarkItDown(enable_plugins=False).convert(pfad).text_content or ""
    if text.lstrip().startswith(ROH):                              # kaputte Datei: MarkItDown fällt auf „Text“ zurück und gibt die Rohbytes aus
        raise ValueError("rohdaten")
    return text


def mit_pypdf(pfad):
    if "pypdf" in _ohne():
        raise ImportError("pypdf")
    from pypdf import PdfReader
    leser = PdfReader(pfad)
    if leser.is_encrypted:
        raise ValueError("verschlüsselt")
    teile = []
    for i, seite in enumerate(leser.pages, 1):
        text = (seite.extract_text() or "").strip()
        if text:
            teile.append(f"## Seite {i}\n\n{text}")
    return "\n\n".join(teile)


def umwandeln(pfad):
    """(Code, Text oder Name des fehlenden Werkzeugs)."""
    endung = os.path.splitext(pfad)[1].lower()
    if endung not in ARTEN:
        return FEHLER, ""
    wege = [mit_markitdown] + ([mit_pypdf] if endung == ".pdf" else [])
    fehlend = []
    for weg in wege:
        try:
            text = weg(pfad)
        except ImportError:
            fehlend.append(weg.__name__.split("_", 1)[1])
            continue
        except Exception:                                          # ein Werkzeug scheitert an der Datei: das nächste versuchen
            fehlend.append("")
            continue
        return (OK, text) if text.strip() else (KEIN_TEXT, "")
    if any(fehlend) and all(fehlend):
        return FEHLT, ",".join(fehlend)
    return FEHLER, ""


def main(argv):
    if len(argv) != 2:
        return FEHLER
    code, text = umwandeln(argv[1])
    if code in (OK, FEHLT):
        sys.stdout.buffer.write(text.encode("utf-8", "replace"))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
