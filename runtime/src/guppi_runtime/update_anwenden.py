"""Auto-Update Teil 2 (docs/PLAN_ISOLATION_UND_UPDATE_2026-10-19.md, Abschnitt 4.2 und 4.3).

Ein Release wird nur übernommen, wenn es vollständig geprüft ist:
  * Jede Datei des Stands steht im Manifest `release/MANIFEST.sha256` (Format wie `sha256sum`) und stimmt in der Prüfsumme.
    Fehlt eine Datei oder kommt eine hinzu, wird abgebrochen.
  * Nur Dateien unter PRUEFBEREICHE werden übernommen; Pfade mit `..`, absolute Pfade und Rückwärtsschrägstriche werden abgelehnt.
  * Ändert ein Release Rechte eines Moduls (Routen, Vertrauensstufe), wird jede Änderung einzeln genannt. Die Übernahme braucht
    eine Bestätigung, die genau diese Liste trägt (Schlüssel = Hash der Liste). Ohne sie wird nichts geschrieben.
  * Vor dem Überschreiben entsteht eine vollständige Sicherung; `zurueck` stellt die letzte Sicherung wieder her.
Geschützte Ordner (local_config, workspace, runtime_data, portable, Modelle) liegen außerhalb der Prüfbereiche und werden nie berührt.
Wirkung erst nach dem Neustart von SEDRA."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

PRUEFBEREICHE = ('runtime/src/guppi_runtime/', 'runtime/config/')
MANIFEST = 'release/MANIFEST.sha256'
ZEILE = re.compile(r'^([0-9a-f]{64})  (\S.*)$')


class UpdateFehler(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _programmdateien(root: Path) -> dict:
    """Relativer Pfad (mit /) → SHA-256 aller Dateien in den Prüfbereichen, ohne Zwischenstände."""
    out = {}
    for bereich in PRUEFBEREICHE:
        base = Path(root) / bereich.rstrip('/')
        if not base.is_dir():
            continue
        for p in sorted(base.rglob('*')):
            if not p.is_file() or p.is_symlink() or '__pycache__' in p.parts or p.suffix == '.pyc':
                continue
            out[p.relative_to(root).as_posix()] = _sha(p)
    return out


def manifest_erzeugen(root: Path) -> str:
    """Das Manifest für einen Release-Stand. Wird beim Taggen aus dem Repository erzeugt, nicht zur Laufzeit."""
    return ''.join(f'{sha}  {rel}\n' for rel, sha in _programmdateien(root).items())


def manifest_lesen(text: str) -> dict:
    out = {}
    for n, zeile in enumerate(text.splitlines(), 1):
        if not zeile.strip():
            continue
        m = ZEILE.match(zeile)
        if not m:
            raise UpdateFehler(f'manifest_zeile_{n}_ungueltig')
        rel = m.group(2)
        if rel.startswith('/') or '..' in rel.split('/') or '\\' in rel or not rel.startswith(PRUEFBEREICHE):
            raise UpdateFehler(f'manifest_pfad_nicht_erlaubt:{rel}')
        out[rel] = m.group(1)
    if not out:
        raise UpdateFehler('manifest_leer')
    return out


def _modul_rechte(root: Path) -> dict:
    """{'tool:gateway': {'api': set, 'trust': str}, 'shell:cockpit': …} aus den Manifesten der Module."""
    out = {}
    base = Path(root) / 'runtime' / 'src' / 'guppi_runtime' / 'uix'
    for art, datei, wurzel in (('tool', 'tool.yaml', 'tools'), ('shell', 'shell.yaml', 'shells')):
        if not (base / wurzel).is_dir():
            continue
        for p in sorted((base / wurzel).glob('*/' + datei)):
            try:
                doc = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
            except (OSError, yaml.YAMLError):
                raise UpdateFehler(f'modul_manifest_unlesbar:{p.parent.name}')
            body = doc.get(art) or {}
            out[f'{art}:{p.parent.name}'] = {'api': set(body.get('api') or []), 'trust': str(body.get('trust') or '')}
    return out


def rechteaenderungen(alt_root: Path, neu_root: Path) -> list:
    """Jede Rechteänderung als eigener Satz, so wie der Captain sie bestätigt. Leer, wenn sich nichts ändert."""
    alt, neu = _modul_rechte(alt_root), _modul_rechte(neu_root)
    saetze = []
    for name in sorted(set(alt) | set(neu)):
        if name not in alt:
            saetze.append(f'{name}: neues Modul')
            continue
        if name not in neu:
            saetze.append(f'{name}: Modul entfällt')
            continue
        a, b = alt[name], neu[name]
        for route in sorted(b['api'] - a['api']):
            saetze.append(f'{name}: neue Route {route}')
        for route in sorted(a['api'] - b['api']):
            saetze.append(f'{name}: Route entzogen {route}')
        if a['trust'] != b['trust']:
            saetze.append(f'{name}: Vertrauensstufe {a["trust"] or "–"} → {b["trust"] or "–"}')
    return saetze


def rechte_schluessel(saetze: list) -> str:
    """Der Schlüssel, mit dem der Captain genau diese Liste bestätigt. Leer, wenn keine Rechte berührt werden."""
    if not saetze:
        return ''
    return hashlib.sha256('\n'.join(saetze).encode('utf-8')).hexdigest()


def plan(staging: Path, root: Path, manifest_text: str) -> dict:
    """Prüft einen entpackten Release-Stand gegen das Manifest und gegen die laufende Installation. Schreibt nichts."""
    staging, root = Path(staging), Path(root)
    erwartet = manifest_lesen(manifest_text)
    stand = _programmdateien(staging)
    if set(stand) != set(erwartet):
        fehlt = sorted(set(erwartet) - set(stand))
        zu_viel = sorted(set(stand) - set(erwartet))
        raise UpdateFehler('dateien_passen_nicht:' + ','.join((fehlt + zu_viel)[:3]))
    for rel, sha in erwartet.items():
        if stand[rel] != sha:
            raise UpdateFehler(f'pruefsumme_falsch:{rel}')
    aktuell = _programmdateien(root)
    geaendert = sorted(r for r in erwartet if aktuell.get(r) != erwartet[r])
    entfaellt = sorted(r for r in aktuell if r not in erwartet)
    rechte = rechteaenderungen(root, staging)
    return {'dateien_geaendert': geaendert, 'dateien_entfallen': entfaellt, 'rechte': rechte,
            'rechte_schluessel': rechte_schluessel(rechte), 'anzahl': len(erwartet)}


def sichern(root: Path, version: str) -> Path:
    """Vollständige Sicherung der Programmdateien unter local_config/update/sicherung/<Zeit>_<Version>."""
    zeit = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    ziel = Path(root) / 'local_config' / 'update' / 'sicherung' / f'{zeit}_{version}'
    dateien = _programmdateien(root)
    for rel in dateien:
        datei = ziel / rel
        datei.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(root) / rel, datei)
    (ziel / 'SICHERUNG.json').write_text(json.dumps({'version': version, 'erstellt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                                                    'dateien': sorted(dateien)}, ensure_ascii=False, indent=2), encoding='utf-8')
    return ziel


def anwenden(staging: Path, root: Path, manifest_text: str, rechte_bestaetigung: str, version: str) -> dict:
    """Übernimmt den geprüften Stand. Ohne Bestätigung der genau vorgelegten Rechteliste wird nichts geschrieben."""
    p = plan(staging, root, manifest_text)
    if p['rechte_schluessel'] != (rechte_bestaetigung or ''):
        raise UpdateFehler('rechte_nicht_bestaetigt')
    sicherung = sichern(root, version)
    for rel in p['dateien_geaendert']:
        ziel = Path(root) / rel
        ziel.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(staging) / rel, ziel)
    for rel in p['dateien_entfallen']:
        (Path(root) / rel).unlink(missing_ok=True)
    vermerk = {'version': version, 'sicherung': sicherung.name, 'uebernommen': datetime.now(timezone.utc).isoformat(timespec='seconds'),
               'rechte': p['rechte'], 'wirkt': 'nach dem Neustart von SEDRA'}
    (Path(root) / 'local_config' / 'update').mkdir(parents=True, exist_ok=True)
    (Path(root) / 'local_config' / 'update' / 'stand.json').write_text(json.dumps(vermerk, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'status': 'uebernommen', 'geaendert': len(p['dateien_geaendert']), 'entfallen': len(p['dateien_entfallen']),
            'sicherung': sicherung.name, 'wirkt': 'nach dem Neustart'}


def zurueck(root: Path) -> dict:
    """Stellt die letzte Sicherung wieder her. Dateien, die das Update neu brachte, werden entfernt."""
    base = Path(root) / 'local_config' / 'update' / 'sicherung'
    letzte = sorted(p for p in base.iterdir() if (p / 'SICHERUNG.json').is_file()) if base.is_dir() else []
    if not letzte:
        raise UpdateFehler('keine_sicherung')
    sicherung = letzte[-1]
    info = json.loads((sicherung / 'SICHERUNG.json').read_text(encoding='utf-8'))
    for rel in _programmdateien(root):
        if rel not in info['dateien']:
            (Path(root) / rel).unlink(missing_ok=True)
    for rel in info['dateien']:
        ziel = Path(root) / rel
        ziel.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sicherung / rel, ziel)
    return {'status': 'zurueckgesetzt', 'version': info['version'], 'wirkt': 'nach dem Neustart von SEDRA'}
