"""Einzige Stelle, die die alten Namen kennt: Übergang für Installationen vor 1.23.0.

Der alte Name steht hier nur, damit bestehende Installationen, Umgebungsvariablen und Projektordner
beim ersten Start sauber umziehen. Neuer Code benutzt ausschließlich die SEDRA-Namen.

Aufruf beim Start: `python -m sedra_runtime.legacy_names --root <Installationsordner>`.
Es wird nichts gelöscht: Alte Ordner, die ersetzt wurden, wandern in `local_config/update/sicherung/alt_namen`.
"""
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

_ALT = ''.join(('GUP', 'PI'))
_ALT_KLEIN = _ALT.lower()

PROJEKTORDNER_ALT = _ALT + '_OS'
PROJEKTORDNER_NEU = 'SEDRA_OS'
PAKET_ALT = _ALT_KLEIN + '_runtime'
PAKET_NEU = 'sedra_runtime'
ARCHITEKTUR_ALT = _ALT + '_Architecture_'
ARCHITEKTUR_NEU = 'SEDRA_Architecture_'


def env_aliase(env=None) -> list[str]:
    """Kopiert alte Variablen `<ALT>_X` nach `SEDRA_X`, wenn die neue fehlt. Gibt die neu gesetzten Namen zurück."""
    env = os.environ if env is None else env
    gesetzt = []
    for name in list(env):
        if name.startswith(_ALT + '_'):
            neu = 'SEDRA_' + name[len(_ALT) + 1:]
            if neu not in env:
                env[neu] = env[name]
                gesetzt.append(neu)
    return gesetzt


def _sichern(quelle: Path, sicherung: Path) -> Path:
    sicherung.mkdir(parents=True, exist_ok=True)
    ziel = sicherung / quelle.name
    n = 1
    while ziel.exists():
        n += 1
        ziel = sicherung / f'{quelle.name}_{n}'
    shutil.move(str(quelle), str(ziel))
    return ziel


def umziehen(root) -> list[str]:
    """Benennt den Projektordner um und sichert veraltete Ordner. Gibt eine Liste der Schritte zurück."""
    root = Path(root)
    schritte: list[str] = []
    sicherung = root / 'local_config' / 'update' / 'sicherung' / 'alt_namen'

    alt = root / 'workspace' / PROJEKTORDNER_ALT
    neu = root / 'workspace' / PROJEKTORDNER_NEU
    if alt.is_dir() and not neu.exists():
        alt.rename(neu)
        schritte.append(f'Projektordner umbenannt: workspace/{PROJEKTORDNER_ALT} -> workspace/{PROJEKTORDNER_NEU}')
    elif alt.is_dir() and neu.exists():
        schritte.append(f'Hinweis: workspace/{PROJEKTORDNER_ALT} und workspace/{PROJEKTORDNER_NEU} existieren beide, nichts verschoben.')

    paket_alt = root / 'runtime' / 'src' / PAKET_ALT
    if paket_alt.is_dir() and (root / 'runtime' / 'src' / PAKET_NEU).is_dir():
        ziel = _sichern(paket_alt, sicherung)
        schritte.append(f'Altes Programmpaket gesichert: {ziel.relative_to(root).as_posix()}')

    arch = root / 'architecture'
    if arch.is_dir():
        for ordner in sorted(arch.iterdir()):
            if ordner.is_dir() and ordner.name.startswith(ARCHITEKTUR_ALT):
                neuer = arch / (ARCHITEKTUR_NEU + ordner.name[len(ARCHITEKTUR_ALT):])
                if neuer.is_dir():
                    ziel = _sichern(ordner, sicherung)
                    schritte.append(f'Alter Architekturordner gesichert: {ziel.relative_to(root).as_posix()}')
    return schritte


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--root', required=True, help='Installationsordner (enthält runtime, workspace, architecture)')
    args = p.parse_args(argv)
    for zeile in umziehen(args.root):
        print(zeile)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
