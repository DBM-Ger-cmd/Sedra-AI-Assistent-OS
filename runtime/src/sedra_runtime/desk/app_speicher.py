"""Speicher der Gewährungen fremder Apps (AM3-05): eine Datei des Kerns, `local_config/apps/berechtigung.yaml`.

Form: `{apps: {<id>: {vertrauen, manifest_sha256, aktiv, gewaehrt: [..]}}}`. Die Bausteine für den einzelnen Eintrag liegen in `berechtigung.py`;
hier nur Lesen und atomares Schreiben. Ein unlesbarer Inhalt zählt als „keine Gewährung“ (die App wird dann nicht geladen), er wird nie geraten."""
from __future__ import annotations

import hashlib
import os
import re
import threading
from pathlib import Path

import yaml

APP_ID = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')
_SPERRE = threading.Lock()


def datei(project_root) -> Path:
    return Path(project_root) / 'local_config' / 'apps' / 'berechtigung.yaml'


def manifest_hash(pfad) -> str | None:
    """sha256 der Bytes von tool.yaml – so bindet die Gewährung an genau diese Fassung (AM3-06)."""
    try:
        return hashlib.sha256(Path(pfad).read_bytes()).hexdigest()
    except OSError:
        return None


def lesen(project_root) -> dict:
    """{id: eintrag}; fehlende oder kaputte Datei → {}."""
    try:
        doc = yaml.safe_load(datei(project_root).read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}
    apps = doc.get('apps') if isinstance(doc, dict) else None
    if not isinstance(apps, dict):
        return {}
    return {k: v for k, v in apps.items() if isinstance(k, str) and APP_ID.match(k) and isinstance(v, dict)}


def _doc(project_root) -> dict:
    try:
        doc = yaml.safe_load(datei(project_root).read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}
    return doc if isinstance(doc, dict) else {}


def schreiben(project_root, apps: dict) -> None:
    ziel = datei(project_root)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    rest = {k: v for k, v in _doc(project_root).items() if k != 'apps'}          # `zugaenge` (AM4) bleibt erhalten
    text = yaml.safe_dump({**rest, 'apps': apps}, allow_unicode=True, sort_keys=True)
    tmp = ziel.with_name(ziel.name + '.tmp')
    with _SPERRE:
        tmp.write_text(text, encoding='utf-8')
        os.replace(tmp, ziel)


def zugaenge_lesen(project_root) -> dict:
    """AM4-01: {zugang: {lesen, verben}} (`mcp`, `cli`); fehlt die Datei oder der Schlüssel, ist es leer."""
    z = _doc(project_root).get('zugaenge')
    return {k: v for k, v in z.items() if k in ('mcp', 'cli') and isinstance(v, dict)} if isinstance(z, dict) else {}


def zugang_schreiben(project_root, name: str, eintrag: dict) -> None:
    if name not in ('mcp', 'cli'):
        raise ValueError('zugang_unbekannt')
    doc = _doc(project_root)
    z = doc.get('zugaenge') if isinstance(doc.get('zugaenge'), dict) else {}
    z[name] = eintrag
    doc['zugaenge'] = z
    ziel = datei(project_root)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with _SPERRE:
        tmp = ziel.with_name(ziel.name + '.tmp')
        tmp.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=True), encoding='utf-8')
        os.replace(tmp, ziel)


def aendern(project_root, app_id: str, funktion):
    """Liest, wendet `funktion(eintrag_oder_None) -> eintrag_oder_None` an (None = Eintrag entfernen) und schreibt zurück; liefert den neuen Eintrag."""
    if not isinstance(app_id, str) or not APP_ID.match(app_id):
        raise ValueError('id')
    apps = lesen(project_root)
    neu = funktion(apps.get(app_id))
    if neu is None:
        apps.pop(app_id, None)
    else:
        apps[app_id] = neu
    schreiben(project_root, apps)
    return neu
