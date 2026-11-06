"""Aufruf des Umwandelns im eigenen Prozess (G2 K5 §2.3, D-K5-3): Zeitgrenze, begrenzte Ausgabe, Codes → Gründe für den Stand je Datei.

Gründe (stehen in `dateien.grund`, Sätze in `speicher.SAETZE`):
- `wis_hilfswerkzeug_fehlt` – weder MarkItDown noch (bei PDF) pypdf ist installiert; der Satz nennt den Befehl aus `config/hilfswerkzeuge.yaml`
- `wis_kein_text` – das Dokument hat keine Textschicht (gescannte PDF; Texterkennung kommt mit W5)
- `wis_umwandeln_zeitgrenze` – länger als die Zeitgrenze (Vorgabe 60 s)
- `wis_umwandeln_fehler` – das Werkzeug kam mit der Datei nicht zurecht, oder die Ausgabe war zu groß"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from . import umwandeln as umw

SKRIPT = Path(umw.__file__).resolve()
ZEITGRENZE_S = 60.0
AUSGABE_MAX = 20_000_000
ARTEN = umw.ARTEN


def markdown(path, *, zeitgrenze=ZEITGRENZE_S, ausgabe_max=AUSGABE_MAX, python=None, umgebung=None):
    """Der Text der Datei als Markdown; sonst ValueError mit einem der Gründe oben."""
    path = Path(path).resolve()
    with tempfile.TemporaryDirectory(prefix="sedra-umwandeln-") as leer:      # Arbeitsordner leer: nichts wird aus dem Ordner der Datei geladen
        try:
            r = subprocess.run([python or sys.executable, "-I", str(SKRIPT), str(path)], cwd=leer, capture_output=True, timeout=zeitgrenze,
                               env=umgebung, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise ValueError("wis_umwandeln_zeitgrenze") from None
        except OSError:
            raise ValueError("wis_umwandeln_fehler") from None
    if r.returncode == umw.FEHLT:
        raise ValueError("wis_hilfswerkzeug_fehlt")
    if r.returncode == umw.KEIN_TEXT:
        raise ValueError("wis_kein_text")
    if r.returncode != umw.OK or len(r.stdout) > ausgabe_max:
        raise ValueError("wis_umwandeln_fehler")
    return r.stdout.decode("utf-8", "replace")
