"""Kleine Hilfen des Wissensspeichers ohne Zustand: Prüfsumme, Inhaltsschutz-Befunde je Abschnitt und das atomare Schreiben von Dateien."""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from ..core.content_policy import KEY_FORMATS, ScanFailure, scan_content

HART = ("PAN_CVV_V1",)                                                    # A-1: dieselben Klassen wie ContentGuard._finish


def _sha(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def befunde_von(text):
    """(hart, weich): Regel-IDs des Inhaltsschutzes je Abschnitt; harte Funde sperren die Aufnahme (D7.3), ein Scannerfehler auch."""
    try:
        hits = scan_content(text)
    except ScanFailure as exc:
        return [str(exc)], []
    hart, weich = [], []
    for h in hits:
        r = h.rule_id.split(":", 1)[0]
        ziel = hart if (r in HART or r in KEY_FORMATS or r.startswith("INVISIBLE_BLOCK")) else weich
        if r not in ziel:
            ziel.append(r)
    return hart, weich


def schreibe_atomar(pfad, text):
    """Ganze Datei in eine Nachbardatei schreiben und mit `os.replace` an die Stelle setzen: ein Abbruch lässt die alte oder die neue Datei, nie eine halbe."""
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    try:
        modus = os.stat(pfad).st_mode & 0o777                          # `mkstemp` legt mit 0600 an: die Rechte der alten Datei bleiben
    except OSError:
        modus = 0o644
    fd, tmp = tempfile.mkstemp(dir=str(pfad.parent), prefix=pfad.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, modus)
        os.replace(tmp, pfad)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
