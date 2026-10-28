"""Harness-Projekte (G2 §3.1, D-E3): Name, Wurzel und Schreibbereich.

Gelesen aus `local_config/harness_projekte.yaml` des SEDRA-Projekts, falls vorhanden (Vorlage: runtime/config/harness_projekte.beispiel.yaml);
sonst gilt das Standard-Projekt „Sedra Entwicklung“ = Wurzel dieses Repos, Schreibbereich runtime/**, docs/**, redesign/**. Hier wird
nichts geschrieben – `local_config/` ändert nur der Captain. In Stufe 1 nutzt nur die Anzeige und der Systemprompt die Projekte; der
Schreibbereich wirkt ab Stufe 2 (Werkzeuge mit Wirkung)."""
from __future__ import annotations

import re
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

import yaml

DATEI = 'harness_projekte.yaml'
REPO = Path(__file__).resolve().parents[4]          # harness → guppi_runtime → src → runtime → Repo
STANDARD = {'id': 'sedra-entwicklung', 'name': 'Sedra Entwicklung', 'wurzel': str(REPO),
            'schreibbereich': ['runtime/**', 'docs/**', 'redesign/**']}
ID = re.compile(r'[a-z0-9][a-z0-9-]{0,39}')


class ProjektFehler(ValueError):
    """Die Datei ist ungültig; der Text nennt den Grund (für die Oberfläche und das Audit)."""


def _muster_ok(muster):
    if not isinstance(muster, str) or not muster.strip():
        return False
    p = muster.replace('\\', '/')
    return not (p.startswith('/') or re.match(r'^[A-Za-z]:', p) or '..' in PurePosixPath(p).parts)


def pruefen(doc):
    """Die Projekte aus einer gelesenen Datei – oder ProjektFehler mit Grund."""
    if not isinstance(doc, dict) or not isinstance(doc.get('projekte'), list) or not doc['projekte']:
        raise ProjektFehler('projekte_liste_fehlt: die Datei braucht „projekte:“ mit mindestens einem Eintrag')
    out, ids = [], set()
    for n, p in enumerate(doc['projekte'], 1):
        if not isinstance(p, dict):
            raise ProjektFehler(f'projekt_{n}_kein_eintrag')
        pid = p.get('id')
        if not isinstance(pid, str) or not ID.fullmatch(pid):
            raise ProjektFehler(f'projekt_{n}_id_ungueltig: kleine Buchstaben, Ziffern und Bindestrich')
        if pid in ids:
            raise ProjektFehler(f'projekt_{pid}_doppelt')
        ids.add(pid)
        wurzel = p.get('wurzel')
        if not isinstance(wurzel, str) or not Path(wurzel).is_absolute() or not Path(wurzel).is_dir():
            raise ProjektFehler(f'projekt_{pid}_wurzel_ungueltig: ein vorhandener Ordner mit vollständigem Pfad')
        bereich = p.get('schreibbereich') or []
        if not isinstance(bereich, list) or not all(_muster_ok(m) for m in bereich):
            raise ProjektFehler(f'projekt_{pid}_schreibbereich_ungueltig: nur Muster relativ zur Wurzel, ohne „..“')
        out.append({'id': pid, 'name': str(p.get('name') or pid)[:80], 'wurzel': str(Path(wurzel).resolve()),
                    'schreibbereich': [m.replace('\\', '/') for m in bereich]})
    return out


def laden(projekt_root: Path):
    """Die Harness-Projekte. Fehlt die Datei: das Standard-Projekt. Ist sie kaputt: ProjektFehler (kein stiller Rückfall)."""
    pfad = Path(projekt_root) / 'local_config' / DATEI
    if not pfad.is_file():
        return [dict(STANDARD, schreibbereich=list(STANDARD['schreibbereich']))]
    try:
        doc = yaml.safe_load(pfad.read_text(encoding='utf-8'))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ProjektFehler(f'datei_unlesbar: {type(exc).__name__}') from exc
    return pruefen(doc)


def relativ(projekt, pfad):
    """Der Pfad relativ zur Projektwurzel (mit /) – oder None, wenn er außerhalb liegt (auch über '..' oder einen anderen Laufwerksbuchstaben)."""
    wurzel = Path(projekt['wurzel']).resolve()
    p = Path(pfad)
    if not p.is_absolute():
        p = wurzel / p
    try:
        return p.resolve().relative_to(wurzel).as_posix()
    except ValueError:
        return None


def im_schreibbereich(projekt, pfad):
    rel = relativ(projekt, pfad)
    if rel is None or rel == '.':
        return False
    return any(fnmatchcase(rel.lower(), m.lower()) or (m.endswith('/**') and rel.lower().startswith(m[:-2].lower()))
               for m in projekt['schreibbereich'])
