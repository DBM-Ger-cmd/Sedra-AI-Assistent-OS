"""Auto-Update Teil 2: Herunterladen eines Release-Tags aus dem öffentlichen GitHub-Repository.

Nur Tags `vX.Y.Z`, nur in einen eigenen, leeren Ordner unter local_config/update/staging. Entpackt wird ohne Links,
ohne Pfade nach außen und mit einer Größengrenze. Geprüft wird danach in update_anwenden (Manifest und Rechte)."""
from __future__ import annotations

import re
import shutil
import stat
import urllib.request
import zipfile
from pathlib import Path

from .update_anwenden import UpdateFehler
from .version import REPO

TAG = re.compile(r'^v\d+\.\d+\.\d+$')
MAX_BYTES = 200 * 1024 * 1024
MAX_ENTPACKT = 400 * 1024 * 1024
TIMEOUT = 60


def _url(tag: str) -> str:
    return f'https://github.com/{REPO}/archive/refs/tags/{tag}.zip'


def staging_ordner(root: Path, tag: str) -> Path:
    """Ein neuer, leerer Ordner für genau diesen Tag. Ein alter Versuch wird entfernt."""
    ziel = Path(root) / 'local_config' / 'update' / 'staging' / tag
    if ziel.exists():
        shutil.rmtree(ziel)
    ziel.mkdir(parents=True)
    return ziel


def _sicher_zip(zf: zipfile.ZipFile) -> None:
    gesamt = 0
    for info in zf.infolist():
        name = info.filename
        if name.startswith(('/', '\\')) or '..' in name.replace('\\', '/').split('/') or ':' in name:
            raise UpdateFehler(f'archiv_pfad_nicht_erlaubt:{name}')
        if stat.S_ISLNK(info.external_attr >> 16):
            raise UpdateFehler(f'archiv_link_nicht_erlaubt:{name}')
        gesamt += info.file_size
        if gesamt > MAX_ENTPACKT:
            raise UpdateFehler('archiv_zu_gross')


def herunterladen(root: Path, tag: str, holen=None) -> Path:
    """Lädt den Tag und entpackt ihn nach staging/<tag>. Gibt den Ordner des Stands zurück (ohne den GitHub-Oberordner).

    `holen(url) -> bytes` ist für Tests austauschbar; ohne Angabe wird GitHub gelesen."""
    if not TAG.match(tag or ''):
        raise UpdateFehler('tag_ungueltig')
    holen = holen or _netz_holen
    daten = holen(_url(tag))
    if len(daten) > MAX_BYTES:
        raise UpdateFehler('download_zu_gross')
    ziel = staging_ordner(root, tag)
    archiv = ziel.parent / f'{tag}.zip'
    archiv.write_bytes(daten)
    try:
        with zipfile.ZipFile(archiv) as zf:
            _sicher_zip(zf)
            zf.extractall(ziel / 'entpackt')
    except zipfile.BadZipFile:
        raise UpdateFehler('archiv_defekt')
    finally:
        archiv.unlink(missing_ok=True)
    oberordner = [p for p in (ziel / 'entpackt').iterdir() if p.is_dir()]
    if len(oberordner) != 1:
        raise UpdateFehler('archiv_struktur_unerwartet')
    stand = oberordner[0]
    # Der Stand liegt im Staging-Ordner selbst; der Zwischenordner wird entfernt.
    for p in stand.iterdir():
        shutil.move(str(p), str(ziel / p.name))
    shutil.rmtree(ziel / 'entpackt')
    return ziel


def _netz_holen(url: str) -> bytes:
    if not url.startswith('https://github.com/'):
        raise UpdateFehler('quelle_nicht_erlaubt')
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as antwort:
            return antwort.read(MAX_BYTES + 1)
    except OSError:
        raise UpdateFehler('nicht_erreichbar')
