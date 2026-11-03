"""Harness-Projekte (G2 §3.1, D-E3): Name, Wurzel und Schreibbereich.

Gelesen aus `local_config/harness_projekte.yaml` des SEDRA-Projekts, falls vorhanden (Vorlage: runtime/config/harness_projekte.beispiel.yaml);
sonst gilt das Standard-Projekt „Sedra Entwicklung“ = Wurzel dieses Repos, Schreibbereich runtime/**, docs/**, redesign/**. `local_config/`
ändert nur der Captain. Der Schreibbereich wirkt ab Stufe 2 (Werkzeuge mit Wirkung).

P0 M3 (1.11.2026, Harness-Vergleich 31.10., E-A8): dazu die **Laufzeitdatei** `runtime_data/harness/projekte.yaml` – Ordner, die der Captain
über „Ordner öffnen“ (Antrag mit Gate) hinzugefügt hat, und die Vorgaben `rezept_standard`/`projekt_standard`. Sie wird hier geschrieben
(atomar, Sicherung `.bak-<zeit>`), liegt im Vorbehalt `**/runtime_data/harness/**` (das Modell kommt nicht heran) und braucht keinen Neustart."""
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


def _captain(projekt_root: Path):
    pfad = Path(projekt_root) / 'local_config' / DATEI
    if not pfad.is_file():
        return [dict(STANDARD, schreibbereich=list(STANDARD['schreibbereich']))]
    try:
        doc = yaml.safe_load(pfad.read_text(encoding='utf-8'))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ProjektFehler(f'datei_unlesbar: {type(exc).__name__}') from exc
    return pruefen(doc)


def laden(projekt_root: Path):
    """Die Harness-Projekte: die des Captains (Datei oder Standard) und danach die der Laufzeitdatei (`quelle: laufzeit`).
    Kaputt → ProjektFehler (kein stiller Rückfall); eine doppelte ID in der Laufzeitdatei verliert gegen die des Captains."""
    out = _captain(projekt_root)
    ids = {p['id'] for p in out}
    for p in laufzeit_laden(projekt_root)['projekte']:
        if p['id'] not in ids:
            out.append(dict(p, quelle='laufzeit'))
            ids.add(p['id'])
    return out


# ---- P0 M3: Laufzeitdatei
LAUFZEIT = Path('runtime_data') / 'harness' / 'projekte.yaml'
VORGABEN = ('rezept_standard', 'projekt_standard', 'gedanken_zurueck', 'gedaechtnis_reichweite', 'verlauf_zusammenfassen',
            'lese_grenze', 'verlauf_laenge', 'zusammen_ab', 'kontext_sicherung', 'denken', 'antwort_budget')


def laufzeit_pfad(projekt_root: Path):
    return Path(projekt_root) / LAUFZEIT


def laufzeit_laden(projekt_root: Path):
    """{projekte, vorgaben} aus der Laufzeitdatei; fehlt sie: leer. Kaputt → ProjektFehler mit Grund."""
    pfad = laufzeit_pfad(projekt_root)
    leer = {'projekte': [], 'vorgaben': {k: None for k in VORGABEN}}
    if not pfad.is_file():
        return leer
    try:
        doc = yaml.safe_load(pfad.read_text(encoding='utf-8')) or {}
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ProjektFehler(f'laufzeitdatei_unlesbar: {type(exc).__name__}') from exc
    if not isinstance(doc, dict):
        raise ProjektFehler('laufzeitdatei_unlesbar: kein Abschnitt')
    projekte = pruefen({'projekte': doc.get('projekte')}) if doc.get('projekte') else []
    v = doc.get('vorgaben') or {}
    vorgaben = {k: (str(v[k])[:200] if isinstance(v, dict) and v.get(k) else None) for k in VORGABEN}
    return {'projekte': projekte, 'vorgaben': vorgaben}


def laufzeit_schreiben(projekt_root: Path, daten):
    """Schreibt {projekte, vorgaben} atomar; eine vorhandene Datei bekommt eine Sicherung `.bak-<zeit>` (nie löschen). Gibt {datei, sicherung}."""
    import os
    from datetime import datetime
    pfad = laufzeit_pfad(projekt_root)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    sicherung = None
    if pfad.is_file():
        sicherung = pfad.with_name(pfad.name + '.bak-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
        sicherung.write_bytes(pfad.read_bytes())
    doc = {'projekte': [{'id': p['id'], 'name': p['name'], 'wurzel': p['wurzel'], 'schreibbereich': list(p['schreibbereich'])} for p in daten.get('projekte') or []],
           'vorgaben': {k: (daten.get('vorgaben') or {}).get(k) for k in VORGABEN}}
    text = '# Laufzeitdatei der Harness (P0 M3): über „Ordner öffnen“ hinzugefügte Projekte und Vorgaben. Geschrieben vom Server nach Freigabe; nicht von Hand nötig.\n' + \
           yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    tmp = pfad.with_suffix('.tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, pfad)
    return {'datei': str(pfad), 'sicherung': str(sicherung) if sicherung else None}


def id_aus(name, vergeben=()):
    """Eine Projekt-ID aus dem Ordnernamen: klein, a–z 0–9 -, eindeutig (…-2, …-3)."""
    roh = re.sub(r'[^a-z0-9]+', '-', str(name or '').casefold()).strip('-')[:32] or 'projekt'
    if roh[0] not in 'abcdefghijklmnopqrstuvwxyz0123456789':
        roh = 'p-' + roh
    kandidat, n = roh, 2
    while kandidat in set(vergeben):
        kandidat = f'{roh[:28]}-{n}'; n += 1
    return kandidat


def neues_projekt(wurzel, name=None, schreibbereich=None, vergeben=(), sperrzonen=()):
    """Prüft die Eingabe von „Ordner öffnen“ und liefert den Projekt-Eintrag – oder ProjektFehler. `sperrzonen`: Ordner, die kein Projekt werden
    (das SEDRA-Projekt mit local_config, sein runtime_data). Ein Projekt darf Unterordner des Repos sein, nur nicht local_config/ oder runtime_data/."""
    if not isinstance(wurzel, str) or not wurzel.strip():
        raise ProjektFehler('wurzel_fehlt: ein vollständiger Pfad zu einem vorhandenen Ordner')
    p = Path(wurzel.strip())
    if not p.is_absolute() or not p.is_dir():
        raise ProjektFehler('wurzel_ungueltig: ein vorhandener Ordner mit vollständigem Pfad')
    p = p.resolve()
    for zone in sperrzonen:
        z = Path(zone).resolve()
        if p == z or z in p.parents:
            raise ProjektFehler(f'wurzel_gesperrt: {z.name}/ wird kein Projekt (Einstellungen und Ablage des Captains)')
    bereich = schreibbereich if schreibbereich else ['**']
    if not isinstance(bereich, list) or not bereich or not all(_muster_ok(m) for m in bereich):
        raise ProjektFehler('schreibbereich_ungueltig: nur Muster relativ zur Wurzel, ohne „..“')
    name = str(name or p.name or 'Projekt').strip()[:80]
    return {'id': id_aus(p.name, vergeben), 'name': name, 'wurzel': str(p), 'schreibbereich': [str(m).replace('\\', '/') for m in bereich]}


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
