"""Befehlszeile für den Übergang der Namen: `python -m sedra_runtime.umzug --root <Installationsordner>`.

Benennt einen alten Projektordner um und sichert veraltete Programm- und Architekturordner (siehe legacy_names).
Ein Fehler (etwa weil ein Prozess den Ordner noch hält) bricht ab, ohne etwas halb zu verändern, und gibt Code 3 zurück.
"""
from __future__ import annotations

import argparse
import sys

from .legacy_names import umziehen


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--root', required=True, help='Installationsordner (enthält runtime, workspace, architecture)')
    args = p.parse_args(argv)
    try:
        for zeile in umziehen(args.root):
            print(zeile)
    except OSError as exc:
        print(f'Umzug nicht möglich ({exc}). Läuft noch ein SEDRA oder ein Modellserver, der den Ordner hält? Beenden und erneut starten.', file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
