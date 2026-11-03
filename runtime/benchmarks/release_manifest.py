"""Release-Manifest fuer den Updater: `release/MANIFEST.sha256` aus einem Commit erzeugen und einen Tag pruefen.

Der Updater laedt das Zip eines Tags vX.Y.Z von GitHub und verlangt darin `release/MANIFEST.sha256`
(`uix_server.update_vorschau`, `update_anwenden.plan`): jede Datei unter runtime/src/guppi_runtime/ und runtime/config/
muss darin stehen und stimmen, sonst bricht er ab. Erzeugt wird das Manifest aus dem **Commit** (git archive), nicht aus
dem Arbeitsbaum - dort liegen local_paths.yaml, .bak-Dateien und __pycache__, die nicht ins Release gehoeren.
Die Datei gilt nur fuer den Stand, den der Tag bekommt; auf main veraltet sie mit dem naechsten Commit. Vor jedem Tag neu erzeugen.

Aufruf (im Repository):
    python -I -B runtime/benchmarks/release_manifest.py               Manifest aus HEAD nach release/MANIFEST.sha256 schreiben
    python -I -B runtime/benchmarks/release_manifest.py --rev <rev>   ... aus einem anderen Commit
    python -I -B runtime/benchmarks/release_manifest.py --pruefen v1.22.0
                                                                       den Tag pruefen wie der Updater (Manifest vorhanden, vollstaendig, stimmt)
Ablauf eines Release steht in docs/BETRIEB.md, Abschnitt "Release".
"""
from __future__ import annotations

import argparse
import io
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime" / "src"))

from guppi_runtime.update_anwenden import MANIFEST, UpdateFehler, manifest_erzeugen, plan  # noqa: E402


def auspacken(repo: Path, rev: str, ziel: Path) -> None:
    """Der Stand eines Commits wie im Tag-Zip von GitHub (git archive), ohne Arbeitsbaum."""
    daten = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", rev], check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(daten)) as tf:
        for m in tf.getmembers():
            if m.issym() or m.islnk() or m.name.startswith("/") or ".." in Path(m.name).parts:
                raise UpdateFehler(f"archiv_eintrag_nicht_erlaubt:{m.name}")
        try:
            tf.extractall(ziel, filter="data")       # ab Python 3.12 (und Sicherheits-Updates von 3.11)
        except TypeError:
            tf.extractall(ziel)


def erzeugen(repo: Path, rev: str = "HEAD") -> tuple[str, int]:
    """(Manifest-Text, Anzahl). Prueft das Ergebnis gleich mit plan() gegen den eigenen Stand."""
    with tempfile.TemporaryDirectory() as tmp:
        stand = Path(tmp)
        auspacken(repo, rev, stand)
        text = manifest_erzeugen(stand)
        p = plan(stand, stand, text)
    return text, p["anzahl"]


def pruefen(repo: Path, rev: str) -> dict:
    """Prueft einen Stand (Tag oder Commit) wie der Updater: Manifest vorhanden, Dateien vollstaendig, Pruefsummen stimmen."""
    with tempfile.TemporaryDirectory() as tmp:
        stand = Path(tmp)
        auspacken(repo, rev, stand)
        manifest = stand / MANIFEST
        if not manifest.is_file():
            raise UpdateFehler("update_manifest_fehlt")
        p = plan(stand, stand, manifest.read_text(encoding="utf-8"))
    return {"rev": rev, "anzahl": p["anzahl"]}


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--repo", default=str(REPO))
    a.add_argument("--rev", default="HEAD")
    a.add_argument("--pruefen", metavar="REV", help="Tag oder Commit pruefen, nichts schreiben")
    args = a.parse_args(argv)
    repo = Path(args.repo).resolve()
    try:
        if args.pruefen:
            r = pruefen(repo, args.pruefen)
            print(f"{r['rev']}: Manifest vorhanden und stimmig, {r['anzahl']} Dateien.")
            return 0
        text, n = erzeugen(repo, args.rev)
    except (UpdateFehler, subprocess.CalledProcessError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    ziel = repo / MANIFEST
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(text, encoding="utf-8", newline="\n")
    print(f"{MANIFEST}: {n} Dateien aus {args.rev}. Jetzt committen und genau diesen Commit taggen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
