"""F0-06B: Autoritative Versionsquelle und reproduzierbare Release-Hashes.

Erzeugt Release-Metadaten, die Version, Git-Commit, Manifest-Hash und
Build-Datum verknüpfen. BUILD.txt ist historischer Buildstand und wird
nicht als aktuelle Versionsquelle behandelt (siehe Register-F0-06B-Notiz).

Das Modul ist rein (kein Netz, keine Git-Schreiboperationen). Es liest
nur den aktuellen Git-Commit für das Metadaten-Objekt; das Schreiben von
Tags/Commits bleibt beim Updater/Captain.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .update_anwenden import (_programmdateien, manifest_erzeugen,
                              manifest_lesen, PRUEFBEREICHE)


def _git_head(root: Path) -> str:
    """Aktueller Git-Commit (kurzer Hash) des Repositories."""
    out = subprocess.run(
        ['git', '-C', str(root), 'rev-parse', 'HEAD'],
        capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        return 'unbekannt'
    return out.stdout.strip()


def _manifest_hash(root: Path) -> str:
    """SHA-256 über das erzeugte Manifest aller Prüfbereiche."""
    manifest_text = manifest_erzeugen(root)
    return hashlib.sha256(manifest_text.encode('utf-8')).hexdigest()


def release_meta(root: Path | str, version: str) -> dict[str, Any]:
    """Erzeugt ein Release-Metadaten-Objekt (autoritative Versionsquelle).

    Felder:
      - version: Semantische Versionsnummer (z. B. '1.22.3')
      - commit: Aktueller Git-Commit (voller SHA-1)
      - commit_kurz: Kurzer Commit-Hash (erste 12 Zeichen)
      - manifest_hash: SHA-256 über das Release-Manifest
      - build_datum: ISO-8601 Zeitstempel (UTC)
      - pruefbereiche: Liste der in das Manifest einbezogenen Verzeichnisse
      - dateien: Anzahl der Programmdateien im Manifest
    """
    root = Path(root)
    manifest_text = manifest_erzeugen(root)
    dateien = manifest_lesen(manifest_text)
    commit = _git_head(root)
    return {
        'version': version,
        'commit': commit,
        'commit_kurz': commit[:12],
        'manifest_hash': _manifest_hash(root),
        'build_datum': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'pruefbereiche': list(PRUEFBEREICHE),
        'dateien': len(dateien),
    }


def validate_release_meta(meta: dict[str, Any], root: Path | str) -> list[str]:
    """Prüft Konsistenz eines Release-Metadaten-Objekts mit dem aktuellen Stand.

    Gibt eine Fehlerliste zurück (leer = konsistent):
      - version muss mit sedra_runtime.version.VERSION übereinstimmen
      - commit muss mit dem aktuellen Git-HEAD übereinstimmen
      - manifest_hash muss mit dem aktuell erzeugten Manifest übereinstimmen
    """
    root = Path(root)
    errors: list[str] = []

    from .version import VERSION as code_version
    if meta.get('version') != code_version:
        errors.append(
            f"version_inkonsistent: Meta '{meta.get('version')}' != Code '{code_version}'"
        )

    commit = _git_head(root)
    if meta.get('commit') != commit:
        errors.append(
            f"commit_inkonsistent: Meta '{meta.get('commit')}' != Git '{commit}'"
        )

    manifest_text = manifest_erzeugen(root)
    manifest_hash = hashlib.sha256(manifest_text.encode('utf-8')).hexdigest()
    if meta.get('manifest_hash') != manifest_hash:
        errors.append(
            f"manifest_hash_inkonsistent: Meta '{meta.get('manifest_hash')}' != Aktuell '{manifest_hash}'"
        )

    return errors


def schreibe_release_meta(meta: dict[str, Any], pfad: Path | str) -> None:
    """Schreibt ein Release-Metadaten-Objekt als JSON (sortiert, deterministisch)."""
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True),
        encoding='utf-8',
    )


def lese_release_meta(pfad: Path | str) -> dict[str, Any]:
    """Liest ein Release-Metadaten-Objekt aus einer JSON-Datei."""
    pfad = Path(pfad)
    return json.loads(pfad.read_text(encoding='utf-8'))


__all__ = [
    'release_meta',
    'validate_release_meta',
    'schreibe_release_meta',
    'lese_release_meta',
]
