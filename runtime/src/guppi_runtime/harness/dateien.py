"""Dateiauswahl für „+“ und „@“ im Eingabefeld (SPEC_HARNESS_SHELL_v1 Stufe 6, HS-82 bis HS-85).

Der Captain hängt Dateien des Projekts an, indem er sie aus einer Liste wählt; die Nachricht bekommt dann `@pfad`. Dieser Weg **nennt nur Namen** (kein Inhalt) und nur das, was die Einstufung
von `datei_lesen` zulässt: was der Katalog verbietet oder ein fester Vorbehalt trifft, erscheint nicht. Er bleibt im Projektordner, folgt keinen Verknüpfungen und überspringt Ordner, in
denen nie etwas anzuhängen ist (.git, Umgebungen, Laufzeitdaten)."""
from __future__ import annotations

import os
from pathlib import Path

from . import freigabe
from .vorschau import VorschauFehler, _norm

UEBERSPRINGEN = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'runtime_data', 'engines', '.claude', '.idea', '.pytest_cache', '.mypy_cache'}
LIMIT = 40
BESUCHT_MAX = 8000


def _erlaubt(regeln, rel):
    e = freigabe.einstufung(regeln, 'datei_lesen', {}, {'ziel': rel, 'vorhanden': True})
    return e['stufe'] != 'verboten' and not e.get('vorbehalt')


def liste(wurzel, regeln, ordner='', q='', limit=LIMIT, besucht_max=BESUCHT_MAX):
    """{ordner, eintraege: [{pfad, art, groesse}], gekuerzt}. `q` sucht im ganzen Projekt (Teil des Pfads, ohne Groß/Klein), sonst werden die Einträge von `ordner` gezeigt."""
    basis = Path(wurzel).resolve()
    rel_ordner = _norm(ordner) if str(ordner or '').strip() not in ('', '.', '/') else ''
    start = (basis / rel_ordner).resolve()
    try:
        start.relative_to(basis)
    except ValueError:
        raise VorschauFehler('pfad_ausserhalb: relativ zur Projektwurzel, ohne „..“') from None
    if not start.is_dir():
        return {'ordner': rel_ordner, 'eintraege': [], 'gekuerzt': False}
    out, gekuerzt = [], False
    q = str(q or '').strip().lower()
    if q:
        besucht = 0
        for pfad, ordner_namen, dateien in os.walk(start):
            ordner_namen[:] = sorted(n for n in ordner_namen if n not in UEBERSPRINGEN and not (Path(pfad) / n).is_symlink())
            for name in sorted(dateien):
                besucht += 1
                rel = (Path(pfad) / name).relative_to(basis).as_posix()
                if q in rel.lower() and _erlaubt(regeln, rel):
                    out.append({'pfad': rel, 'art': 'datei', 'groesse': _groesse(basis / rel)})
                    if len(out) >= limit:
                        return {'ordner': rel_ordner, 'eintraege': out, 'gekuerzt': True}
                if besucht >= besucht_max:
                    return {'ordner': rel_ordner, 'eintraege': out, 'gekuerzt': True}
        return {'ordner': rel_ordner, 'eintraege': out, 'gekuerzt': False}
    kinder = sorted(start.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    for p in kinder:
        if p.name in UEBERSPRINGEN or p.is_symlink():
            continue
        rel = p.relative_to(basis).as_posix()
        if p.is_dir():
            out.append({'pfad': rel, 'art': 'ordner', 'groesse': None})
        elif p.is_file() and _erlaubt(regeln, rel):
            out.append({'pfad': rel, 'art': 'datei', 'groesse': _groesse(p)})
        if len(out) >= limit * 5:
            gekuerzt = True
            break
    return {'ordner': rel_ordner, 'eintraege': out, 'gekuerzt': gekuerzt}


def _groesse(p):
    try:
        return p.stat().st_size
    except OSError:
        return None
