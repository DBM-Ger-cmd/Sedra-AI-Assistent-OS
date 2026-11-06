"""Minimalpaket fuer den USB-Stick (K:\\SEDRA): Liste lesen, Python-Importhuelle ermitteln, kopieren, Manifest schreiben.

Keine Verknuepfungen (exFAT kennt keine Junctions und Symlinks): jede Quelle wird als echte Datei oder echter Ordner kopiert.
Die Liste steht in `stick_liste.txt` neben diesem Skript. Zeilen:
    repo <pfad>        aus diesem Repository (Ordner mit / am Ende)
    bestand <pfad>     aus dem Hauptcheckout (nicht in git: Engine, portables Python)
    modul <name>       ein Python-Modul mit allen statischen Importen (sedra_runtime.*)
    <quelle> <pfad> -> <ziel>   umbenannt kopieren
Aufruf (Bau-PC):  python -I -B runtime/benchmarks/stick_paket.py --repo <worktree> --bestand <hauptcheckout> --ziel K:\\SEDRA
Nur pruefen:      ... --pruefen        (fehlende Importe und fehlende Dateien melden, nichts kopieren)
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PAKET = "sedra_runtime"
AUSSCHLUSS = {"__pycache__", ".pytest_cache", "local_paths.yaml", "local_config", ".git"}
SCHREIBEN = {"STICK_MANIFEST.json"}
HERE = Path(__file__).resolve().parent


def liste(pfad):
    """Zeilen der Liste als (art, quelle, ziel) mit art in repo|bestand|modul; Leerzeilen und # werden ausgelassen."""
    eintraege = []
    for nr, zeile in enumerate(Path(pfad).read_text(encoding="utf-8").splitlines(), 1):
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        teile = zeile.split()
        if teile[0] == "modul":
            eintraege.append(("modul", teile[1], teile[1]))
        elif teile[0] in ("repo", "bestand") and len(teile) in (2, 4):
            ziel = teile[3] if len(teile) == 4 and teile[2] == "->" else teile[1]
            eintraege.append((teile[0], teile[1], ziel))
        else:
            raise ValueError(f"stick_liste.txt Zeile {nr}: {zeile!r}")
    return eintraege


def modul_datei(src, name):
    """Datei eines Moduls im Paket (name.py oder name/__init__.py), sonst None."""
    teile = name.split(".")
    datei = Path(src, *teile).with_suffix(".py")
    if datei.is_file():
        return datei
    paket = Path(src, *teile, "__init__.py")
    return paket if paket.is_file() else None


def closure(src, einstiegs):
    """Alle Dateien, die die Einstiegsmodule (und ihre Eltern-Pakete) brauchen. `src` enthaelt den Ordner sedra_runtime."""
    src = Path(src)
    bekannt, offen, dateien = set(), list(einstiegs), set()
    while offen:
        name = offen.pop()
        if name in bekannt:
            continue
        bekannt.add(name)
        teile = name.split(".")
        for n in range(1, len(teile)):
            init = Path(src, *teile[:n], "__init__.py")
            if init.is_file():
                dateien.add(init)
        datei = modul_datei(src, name)
        if datei is None:
            raise FileNotFoundError(f"Modul fehlt im Quellbaum: {name}")
        dateien.add(datei)
        offen.extend(_import_namen(datei, name, src) - bekannt)
    return sorted(dateien)


def _import_namen(datei, name, src):
    baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
    paket = name if datei.name == "__init__.py" else name.rsplit(".", 1)[0]
    namen = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            namen.update(a.name for a in knoten.names if a.name.split(".")[0] == PAKET)
        elif isinstance(knoten, ast.ImportFrom):
            if knoten.level:
                basis = paket.split(".")[: len(paket.split(".")) - (knoten.level - 1)]
                ziel = ".".join(basis + ([knoten.module] if knoten.module else []))
            else:
                ziel = knoten.module or ""
            if ziel.split(".")[0] != PAKET:
                continue
            namen.add(ziel)
            namen.update(f"{ziel}.{a.name}" for a in knoten.names)
    return {n for n in namen if modul_datei(src, n) is not None}


def _kopierbar(pfad):
    return not any(teil in AUSSCHLUSS for teil in pfad.parts) and not pfad.name.endswith(".pyc")


def _ist_verknuepfung(pfad):
    return pfad.is_symlink() or getattr(pfad, "is_junction", lambda: False)()


def _sammeln(quelle_wurzel, rel):
    """Dateien unter quelle_wurzel/rel; ein Ordner nimmt alle echten Dateien (ohne Ausschluss), Verknuepfungen brechen ab."""
    ziel = Path(quelle_wurzel, rel)
    if not ziel.exists():
        raise FileNotFoundError(f"fehlt: {ziel}")
    if ziel.is_file():
        return [ziel]
    ausgabe = []
    for pfad in sorted(ziel.rglob("*")):
        if _ist_verknuepfung(pfad):
            raise RuntimeError(f"Verknuepfung im Paket nicht erlaubt: {pfad}")
        if pfad.is_file() and _kopierbar(pfad.relative_to(quelle_wurzel)):
            ausgabe.append(pfad)
    return ausgabe


def plan(eintraege, repo, bestand):
    """{ziel_relativ: quelldatei} fuer alle Eintraege. Module kommen aus dem Repository unter runtime/src."""
    quelle = {"repo": Path(repo), "bestand": Path(bestand)}
    paare = {}
    modul_namen = [e[1] for e in eintraege if e[0] == "modul"]
    for art, pfad, ziel in eintraege:
        if art == "modul":
            continue
        wurzel = quelle[art]
        base = wurzel / pfad
        if base.is_file():
            paare[Path(ziel).as_posix()] = base
            continue
        for datei in _sammeln(wurzel, pfad):
            paare[(Path(ziel) / datei.relative_to(base)).as_posix()] = datei
    src = Path(repo, "runtime", "src")
    for datei in closure(src, modul_namen):
        paare["runtime/src/" + datei.relative_to(src).as_posix()] = datei
    return {k: v for k, v in paare.items() if _kopierbar(Path(k))}


def manifest(ziel, eintraege_dateien, stand):
    """STICK_MANIFEST.json: Pfad, Groesse, SHA-256 je Datei."""
    eintraege = []
    for rel in sorted(eintraege_dateien):
        pfad = Path(ziel, rel)
        eintraege.append({"pfad": rel.replace(os.sep, "/"), "groesse": pfad.stat().st_size, "sha256": _hash(pfad)})
    daten = {"schema": 1, "stand": stand, "dateien": eintraege}
    Path(ziel, "STICK_MANIFEST.json").write_text(json.dumps(daten, indent=1, ensure_ascii=False), encoding="utf-8")
    return daten


def _hash(pfad):
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def kopieren(paare, ziel):
    """Kopiert alle Paare nach `ziel`. Gibt die relativen Pfade zurueck."""
    ziel = Path(ziel)
    rel = []
    for schluessel, datei in sorted(paare.items()):
        dst = Path(ziel, schluessel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(datei, dst)
        rel.append(schluessel)
    return rel


def _stand(repo):
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unbekannt"


def main(argv=None):
    p = argparse.ArgumentParser(description="SEDRA-Minimalpaket fuer den Stick")
    p.add_argument("--repo", required=True)
    p.add_argument("--bestand", required=True)
    p.add_argument("--ziel", required=True)
    p.add_argument("--liste", default=str(HERE / "stick_liste.txt"))
    p.add_argument("--pruefen", action="store_true")
    a = p.parse_args(argv)
    paare = plan(liste(a.liste), a.repo, a.bestand)
    if a.pruefen:
        print(f"{len(paare)} Dateien im Plan")
        for schluessel in sorted(paare):
            print(schluessel)
        return 0
    rel = kopieren(paare, a.ziel)
    daten = manifest(a.ziel, rel, _stand(a.repo))
    print(f"{len(daten['dateien'])} Dateien, {sum(d['groesse'] for d in daten['dateien'])} Byte, Manifest STICK_MANIFEST.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
