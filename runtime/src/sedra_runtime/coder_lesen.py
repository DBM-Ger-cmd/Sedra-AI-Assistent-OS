"""Lese-Sicht für die App Coder (SPEC_APP_CODER_RUNDE5_LESE_ROUTEN, Routen R1 bis R3, Entscheidungen E1 bis E3 vom 17.11.2026).

Nur lesen, nichts anlegen, nichts ändern. Die Funktionen bekommen fertige Antworten der vorhandenen Wege (`project_files`, `project_file`) und
filtern sie. Hier steht nur das, was der Coder zusätzlich braucht:
- die Sperrliste (E3): Dateien und Ordner mit Schlüsseln, Zugangsdaten oder lokaler Konfiguration erscheinen weder in Listen noch als Inhalt,
- die Zerlegung des Pfades aus der Adresse (`/api/uix/coder/dateien/<projekt>/<pfad, url-codiert>`),
- die Form der Antworten (`quelle: ok | fehlt`, nie ein absoluter Pfad, nie ein Schlüssel).
"""
from __future__ import annotations

from urllib.parse import unquote

PRAEFIX_DATEIEN = '/api/uix/coder/dateien'
PRAEFIX_DATEI = '/api/uix/coder/datei'
PFAD_MAX = 300
LISTE_MAX = 300

# E3: ganze Namen, Endungen und Namensteile, die nie angezeigt werden (Groß-/Kleinschreibung egal)
GESPERRT_NAMEN = frozenset({'local_config', '.ssh', '.aws', '.gnupg', '.kube', '.docker', 'id_rsa', 'id_ed25519', '.netrc', '.npmrc', '.pypirc'})
GESPERRT_ENDUNGEN = ('.key', '.pem', '.pfx', '.p12', '.keystore', '.jks', '.kdbx', '.crt', '.cer', '.der')
GESPERRT_TEILE = ('secret', 'credential', 'passwd', 'password', 'private_key', 'api_key', 'apikey')


def gesperrt(name) -> bool:
    n = str(name).lower()
    if n in GESPERRT_NAMEN or n.startswith('.env') or n.startswith('id_rsa') or n.startswith('id_ed25519'):
        return True
    return n.endswith(GESPERRT_ENDUNGEN) or any(t in n for t in GESPERRT_TEILE)


def pfad_gesperrt(pfad) -> bool:
    """Ein Pfad ist gesperrt, sobald ein Teil gesperrt ist (auch ein Ordner weiter oben)."""
    return any(gesperrt(t) for t in str(pfad).replace('\\', '/').split('/') if t)


def zerlege(adresse, praefix):
    """('/api/uix/coder/dateien/PRJ-1/src%2Fmain.py', praefix) -> ('PRJ-1', 'src/main.py'). Ohne Pfad: ''. Ungültig: ValueError."""
    rest = adresse[len(praefix):].lstrip('/')
    teile = rest.split('/', 1)
    projekt = unquote(teile[0])
    pfad = unquote(teile[1]) if len(teile) > 1 else ''
    if not projekt or len(projekt) > 60 or any(c in projekt for c in '/\\?# '):
        raise ValueError('invalid_project')
    if len(pfad) > PFAD_MAX or '\x00' in pfad:
        raise ValueError('invalid_path')
    return projekt, pfad


def projekte(liste) -> dict:
    """R1: Kennung und Anzeigename. Kein workspace_path, nie ein Ordner des Rechners."""
    eintraege = [{'id': p.get('project_id'), 'name': p.get('display_name')} for p in (liste or []) if p.get('project_id')]
    if not eintraege:
        return {'quelle': 'fehlt', 'projekte': [], 'anzahl': 0, 'grund': 'kein Projekt angelegt'}
    return {'quelle': 'ok', 'projekte': eintraege[:50], 'anzahl': len(eintraege)}


def dateien(pfad, antwort) -> dict:
    """R2: die Antwort von `project_files` ohne gesperrte Einträge."""
    if pfad_gesperrt(pfad):
        raise ValueError('access_blocked')
    sichtbar = [e for e in antwort.get('entries', []) if not gesperrt(e.get('name', ''))]
    return {'quelle': 'ok', 'pfad': antwort.get('path', ''), 'eintraege': sichtbar[:LISTE_MAX],
            'gekuerzt': bool(antwort.get('truncated')) or len(sichtbar) > LISTE_MAX, 'ausgeblendet': len(antwort.get('entries', [])) - len(sichtbar)}


def datei(pfad, antwort) -> dict:
    """R3: Text, `binary` oder `too_large` von `project_file`; gesperrte Pfade wurden schon vorher abgelehnt."""
    if pfad_gesperrt(pfad):
        raise ValueError('access_blocked')
    aus = {'quelle': 'ok', 'pfad': antwort.get('path', '')}
    if antwort.get('binary'):
        aus['binary'] = True
    elif antwort.get('too_large'):
        aus['too_large'] = True
    else:
        aus['inhalt'] = antwort.get('content', '')
        aus['bytes'] = antwort.get('bytes', 0)
    return aus


# ---- R4 (E2): Git-Status, nur lesen. Eine feste Form, kein Schreibweg, kein Aufruf mit Eingaben von außen.
PRAEFIX_AENDERUNGEN = '/api/uix/coder/aenderungen'
PRAEFIX_SPEICHERN = '/api/uix/coder/speichern'          # E4: GET …/speichern/<auftrag> = Stand eines Antrags (coder_speichern.py)
GIT_ZEITLIMIT = 2.0
GIT_ZEILEN_MAX = 300
# feste Argumente: -z (Pfade unverändert), --no-renames, keine Sperrdatei im Index; fsmonitor und Hooks bleiben aus (eine fremde .git/config führt nichts aus)
GIT_ARGS = ['-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=NUL', 'status', '--porcelain=v1', '-b', '-z', '--no-renames', '--untracked-files=normal']


def git_zeilen(roh) -> tuple:
    """Ausgabe von `git status --porcelain=v1 -b -z` -> (zweig, [(code, pfad)]). Der Code ist 'U' (neu) oder 'M' (geändert, gelöscht, …)."""
    teile = [t for t in str(roh).split('\x00') if t]
    zweig, eintraege = '', []
    for t in teile:
        if t.startswith('## '):
            kopf = t[3:]
            zweig = kopf.split('...')[0].split(' ')[0]
            if kopf.startswith('No commits yet on '):
                zweig = kopf[len('No commits yet on '):].split('...')[0]
            elif kopf.startswith('HEAD (no branch)'):
                zweig = 'HEAD'
            continue
        if len(t) < 4:
            continue
        xy, pfad = t[:2], t[3:]
        eintraege.append(('U' if xy in ('??', 'A ', ' A', 'AM') else 'M', pfad))
    return zweig, eintraege


def aenderungen(werkordner, lauf=None) -> dict:
    """R4: Zweig und geänderte Dateien des Projektordners. `lauf(args, ordner)` führt Git aus (Standard: subprocess, fester Aufruf, 2 s).
    Kein Git-Ordner, Git fehlt, Zeitüberschreitung oder Fehler: `quelle: fehlt` mit Kennwort, nie ein Pfad des Rechners."""
    from pathlib import Path
    ordner = Path(werkordner)
    if not (ordner / '.git').exists():
        return {'quelle': 'fehlt', 'grund': 'kein_git', 'eintraege': [], 'anzahl': 0, 'zweig': ''}
    try:
        roh = (lauf or _git_lauf)(GIT_ARGS, ordner)
    except Exception as exc:
        return {'quelle': 'fehlt', 'grund': 'git_zeit' if type(exc).__name__ == 'TimeoutExpired' else 'git_fehler', 'eintraege': [], 'anzahl': 0, 'zweig': ''}
    zweig, alle = git_zeilen(roh)
    sichtbar = [{'pfad': p.replace('\\', '/'), 'status': c} for c, p in alle if not pfad_gesperrt(p)]
    return {'quelle': 'ok', 'zweig': zweig[:80], 'eintraege': sichtbar[:GIT_ZEILEN_MAX], 'anzahl': len(sichtbar),
            'gekuerzt': len(sichtbar) > GIT_ZEILEN_MAX, 'ausgeblendet': len(alle) - len(sichtbar)}


def _git_lauf(args, ordner):
    import os
    import subprocess
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    r = subprocess.run(['git', '-C', str(ordner), *args], capture_output=True, timeout=GIT_ZEITLIMIT, env=env, shell=False)
    if r.returncode != 0:
        raise RuntimeError('git_failed')
    return r.stdout.decode('utf-8', errors='replace')
