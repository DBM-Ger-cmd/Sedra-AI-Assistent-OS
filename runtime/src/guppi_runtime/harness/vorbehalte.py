"""Feste Captain-Vorbehalte der Harness-Shell (SPEC_HARNESS_SHELL_v1 HS-28, G2 §3.5, G3 Stufe 2 U3).

Im Code, nicht konfigurierbar: kein Katalog und (ab Stufe 3) keine Aufgaben-Freigabe macht einen dieser Aufrufe `frei`. Ein Vorbehalt heißt
immer Stufe `captain` – die Karte geht an den Captain. Diese Datei ist Harness-Code: SEDRA ändert sie nicht an sich selbst; die Liste
ändert nur Claude mit Captain-Gate. Ein Treffer liefert den Grund, sonst None."""
from __future__ import annotations

from .katalog import befehl_normal, passt, pfad_normal

PFADE = (
    ('**/local_config/**', 'Einstellungen des Captains (local_config)'),
    ('**/freigabe_katalog*.yaml', 'der Freigabe-Katalog selbst'),
    ('runtime/src/guppi_runtime/core/**', 'Kern: Guard, Inhaltsschutz, Missionen'),
    ('runtime/src/guppi_runtime/harness/freigabe.py', 'Harness-Code: Freigabe'),
    ('runtime/src/guppi_runtime/harness/vorbehalte.py', 'Harness-Code: Vorbehalte'),
    ('runtime/src/guppi_runtime/harness/befehl.py', 'Harness-Code: Befehle'),
    ('runtime/src/guppi_runtime/devenv/**', 'Bauumgebung (devenv)'),
    ('runtime/benchmarks/devvm_*', 'Bauskripte (devvm)'),
    ('architecture/**/guard/**', 'Regeln des Guard'),
    ('.git/**', 'das Git-Verzeichnis'),
    ('.git', 'das Git-Verzeichnis'),
)
BEFEHLE = ('git push', 'git branch -f', 'git reset --hard', 'del', 'rm', 'rmdir', 'remove-item', 'format', 'curl', 'wget',
           'invoke-webrequest', 'pip install', 'winget')
SCHREIBEN = ('datei_schreiben', 'datei_aendern')


def pruefen(werkzeug, ziel, args=None, vorhanden=False):
    """Der Grund des Vorbehalts – oder None. `ziel` ist der Pfad relativ zur Wurzel bzw. die Befehlszeile; `vorhanden` sagt, ob die Datei
    schon da ist (für „leer überschreiben“)."""
    if werkzeug == 'befehl':
        zeile = befehl_normal(ziel)
        for b in BEFEHLE:
            if zeile == b or zeile.startswith(b + ' '):
                return f'Captain-Vorbehalt: Befehl „{b}“ (Löschen, Netz, Installieren oder Git-Verlauf ändern)'
        return None
    if werkzeug not in SCHREIBEN:
        return None
    rel = pfad_normal(ziel)
    if rel.split('/')[0] == '..':
        return 'Captain-Vorbehalt: Pfad außerhalb des Projekts'
    for muster, was in PFADE:
        if passt(muster, werkzeug, rel):
            return f'Captain-Vorbehalt: {was}'
    if werkzeug == 'datei_schreiben' and vorhanden and not str((args or {}).get('inhalt') or '').strip():
        return 'Captain-Vorbehalt: eine vorhandene Datei leer überschreiben (kommt einem Löschen gleich)'
    return None
