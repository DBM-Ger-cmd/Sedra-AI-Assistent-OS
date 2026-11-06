"""Zieht den Namenswechsel in einem Branch nach, der auf dem Stand VOR dem Wechsel aufbaut.

Ablauf für einen Branch mit alten Namen: `git merge main` (die Umbenennungen werden erkannt), dann

    python -I -B runtime/benchmarks/namen_nachziehen.py            ersetzt den alten Namen in Inhalt und Dateinamen
    python -I -B runtime/benchmarks/namen_nachziehen.py --dry      zeigt nur, was geändert würde

und danach `python benchmarks/run_tests.py all`. Verlauf bleibt unverändert: Logbuch, docs/historie, concept_review, datierte
Berichte (`*_JJJJ-MM-TT*`) und `.sha256`-Dateien. Prüfsummen danach mit den Werkzeugen des Repositorys neu erzeugen.
Der alte Name steht hier zerlegt, damit die Suche nach ihm in main leer bleibt.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_G = ''.join(('GUP', 'PI'))
ERSETZUNG = ((_G, 'SEDRA'), (_G.capitalize(), 'Sedra'), (_G.lower(), 'sedra'))
VERLAUF_PREFIX = ('docs/LOGBUCH_AGENT_MANAGER.md', 'docs/historie/', 'concept_review/')
DATIERT = re.compile(r'(^|/)[^/]*_20\d\d-\d\d-\d\d[^/]*$')
DOPPELT = re.compile(r'\b(SEDRA|Sedra|sedra)( / |/| und | and |-)\1\b')


def verlauf(rel: str) -> bool:
    return rel.startswith(VERLAUF_PREFIX) or rel.endswith('.sha256') or (rel.startswith('docs/') and DATIERT.search(rel) is not None)


def neu(text: str) -> str:
    for alt, ersatz in ERSETZUNG:
        text = text.replace(alt, ersatz)
    return DOPPELT.sub(r'\1', text)


def dateien(root: Path) -> list[str]:
    try:
        out = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], check=True, capture_output=True).stdout
        return [f for f in out.decode('utf-8').split('\0') if f]
    except (OSError, subprocess.CalledProcessError):
        return [p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '.git' not in p.parts]


def nachziehen(root: Path, dry: bool = False) -> dict:
    root = Path(root)
    namen = dateien(root)
    inhalt, umbenannt = [], []
    for rel in namen:
        if verlauf(rel):
            continue
        p = root / rel
        if p.is_file() and p.stat().st_size <= 5_000_000:
            raw = p.read_bytes()
            if b'\0' not in raw[:4096]:
                try:
                    text = raw.decode('utf-8')
                except UnicodeDecodeError:
                    text = None
                if text is not None and re.search(_G, text, re.I):
                    ergebnis = neu(text)
                    if ergebnis != text:
                        inhalt.append(rel)
                        if not dry:
                            p.write_bytes(ergebnis.encode('utf-8'))
    for rel in namen:
        if verlauf(rel) or not re.search(_G, rel, re.I):
            continue
        ziel = neu(rel)
        if ziel != rel:
            umbenannt.append((rel, ziel))
            if not dry:
                (root / ziel).parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(['git', '-C', str(root), 'mv', rel, ziel], check=True, capture_output=True)
    return {'inhalt_geaendert': inhalt, 'umbenannt': umbenannt}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--root', default=str(REPO))
    a = ap.parse_args()
    r = nachziehen(Path(a.root), a.dry)
    print(f'Inhalt geändert: {len(r["inhalt_geaendert"])} Dateien, umbenannt: {len(r["umbenannt"])}' + (' (Probelauf)' if a.dry else ''))
