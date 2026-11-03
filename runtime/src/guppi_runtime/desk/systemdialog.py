"""Fenster des Betriebssystems für Freigaben der Klasse H (SPEC_APPS_v1_O3PLUS_G9_G2 G9-05, G9-06).

Unter Windows `MessageBoxW` aus dem Server-Prozess in einem eigenen Thread (ctypes, keine neue Abhängigkeit). Der Server läuft in der
Sitzung des Captains (wie der Dateidialog `uix_server.model_pick`). Code in der Seite erreicht dieses Fenster nicht. Ohne Windows kein
Dialog (E6): dann gilt nur die Konsole. Tests setzen eine eigene Anzeige mit `setzen(...)`.
Prüfstelle (O3-02): Änderungen nur durch Claude mit Freigabe des Captains."""
from __future__ import annotations

import sys
import threading

MB_YESNO, MB_ICONWARNING, MB_TOPMOST, MB_SETFOREGROUND, MB_SYSTEMMODAL = 0x4, 0x30, 0x40000, 0x10000, 0x1000
IDYES = 6

_anzeige = None          # Tests: fn(titel, text) -> True | False | None (None = kein Dialog möglich)


def setzen(fn):
    """Für Tests: eine eigene Anzeige; None stellt die echte wieder her."""
    global _anzeige
    _anzeige = fn


def verfuegbar():
    return _anzeige is not None or sys.platform == 'win32'


def _windows(titel, text):
    import ctypes
    r = ctypes.windll.user32.MessageBoxW(None, text, titel, MB_YESNO | MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND | MB_SYSTEMMODAL)
    return r == IDYES


def zeigen(titel, text, antwort):
    """Zeigt den Dialog in einem eigenen Thread; `antwort(True|False)` nach dem Klick. Liefert False, wenn kein Dialog möglich ist."""
    fn = _anzeige
    if fn is None and sys.platform != 'win32':
        return False

    def lauf():
        try:
            ja = fn(titel, text) if fn is not None else _windows(titel, text)
        except Exception:
            return                                   # kein Dialog: die Konsole bleibt
        if ja is None:
            return
        antwort(bool(ja))
    threading.Thread(target=lauf, name='sedra-freigabe-dialog', daemon=True).start()
    return True
