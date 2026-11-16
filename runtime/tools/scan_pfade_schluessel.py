"""Scan nach lokalen Pfaden und Schluesseln in Dateien (Hardening 16.11.2026, Punkt F).

    python tools/scan_pfade_schluessel.py                 # die seit main geaenderten und neuen (getrackten) Dateien des Repos
    python tools/scan_pfade_schluessel.py datei1 datei2   # bestimmte Dateien

Meldet je Treffer Datei:Zeile und die Art (nie den Wert). Exit-Code 1 bei Treffern, sonst 0. Liest nur, aendert nichts."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PFAD = re.compile(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/](?:Users|Sedra|Dokumente|Documents|Program)[^\s"\']*|(?<![\w.])/(?:Users|home)/[A-Za-z0-9_.-]+/|\\\\[A-Za-z0-9_.-]+\\[A-Za-z0-9$_.-]+')
SCHLUESSEL = re.compile(r'sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|xox[bap]-[A-Za-z0-9-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY|nvapi-[A-Za-z0-9_-]{20,}|'
                        r'(?i:api[_-]?key|secret|passwort|password|token)\s*[:=]\s*["\']?[A-Za-z0-9+/_-]{24,}')
BINAER = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.zip', '.gguf', '.sqlite', '.pdf', '.woff', '.woff2', '.pyc'}


def dateien(wurzel: Path, basis: str):
    out = subprocess.run(['git', '-C', str(wurzel), 'diff', '--name-only', '--diff-filter=AM', basis], capture_output=True, text=True).stdout.split()
    neu = subprocess.run(['git', '-C', str(wurzel), 'ls-files', '--others', '--exclude-standard'], capture_output=True, text=True).stdout.split()
    return [wurzel / n for n in dict.fromkeys(out + neu)]


def scan(pfade):
    treffer = []
    for p in pfade:
        if p.suffix.lower() in BINAER or not p.is_file():
            continue
        try:
            zeilen = p.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            continue
        for i, z in enumerate(zeilen, 1):
            for art, muster in (('lokaler Pfad', PFAD), ('Schluessel', SCHLUESSEL)):
                if muster.search(z):
                    treffer.append((str(p), i, art))
    return treffer


def main(argv):
    wurzel = Path(subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True).stdout.strip() or '.')
    pfade = [Path(a) for a in argv] if argv else dateien(wurzel, 'main')
    t = scan(pfade)
    for datei, zeile, art in t:
        print(f'{datei}:{zeile}: {art}')
    print(f'{len(pfade)} Dateien geprueft, {len(t)} Treffer')
    return 1 if t else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
