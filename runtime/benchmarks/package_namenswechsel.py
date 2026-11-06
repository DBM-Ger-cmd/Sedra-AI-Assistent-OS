"""Baut das Umstiegspaket auf die SEDRA-Namen aus einem Commit (Standard HEAD): ZIP mit Manifest und Installer.

    python -I -B runtime/benchmarks/package_namenswechsel.py --output <Ordner>/SEDRA-1.23.0-Namenswechsel.zip [--rev HEAD]

Enthalten: runtime/src/sedra_runtime, runtime/config (ohne local_paths.yaml und .bak-Dateien), die Architekturordner, die drei
Startskripte, INSTALL_NAMENSWECHSEL.py, release/MANIFEST_NAMENSWECHSEL.sha256 und LIESMICH.md. Das Paket kommt aus dem Commit,
nicht aus dem Arbeitsbaum. Es verändert nichts, committet, taggt und pusht nicht.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PRAEFIXE = ('runtime/src/sedra_runtime/', 'runtime/config/', 'architecture/SEDRA_Architecture_')
WURZEL = ('START_SEDRA.bat', 'start_sedra.sh', 'START_SEDRA.command')


def lokal_behalten(rel: str) -> bool:
    return rel == 'runtime/config/local_paths.yaml' or '.bak-' in Path(rel).name


def git(*args) -> bytes:
    return subprocess.run(['git', '-C', str(REPO), *args], check=True, capture_output=True).stdout


def bauen(output: Path, rev: str = 'HEAD') -> dict:
    output = Path(output).resolve()
    commit = git('rev-parse', rev).decode().strip()
    namen = [n for n in git('ls-tree', '-r', '-z', '--name-only', commit).decode('utf-8').split('\0') if n]
    programm = [n for n in namen if (n.startswith(PRAEFIXE) or n in WURZEL) and not lokal_behalten(n)
                and '__pycache__' not in n and not n.endswith('.pyc')]
    zusatz = ['release/install_namenswechsel.py', 'docs/NAMENSWECHSEL_SEDRA_2026-11-06.md']
    with tempfile.TemporaryDirectory(prefix='sedra-namenswechsel-') as tmp:
        wurzel = Path(tmp) / 'SEDRA-Namenswechsel'
        wurzel.mkdir()
        daten = git('archive', '--format=tar', commit, *programm, *zusatz)
        with tarfile.open(fileobj=io.BytesIO(daten)) as tar:
            tar.extractall(wurzel, filter='data')
        manifest = ''.join(f'{hashlib.sha256((wurzel / n).read_bytes()).hexdigest()}  {n}\n' for n in sorted(programm))
        (wurzel / 'release').mkdir(exist_ok=True)
        (wurzel / 'release/MANIFEST_NAMENSWECHSEL.sha256').write_text(manifest, encoding='utf-8', newline='\n')
        (wurzel / 'release/install_namenswechsel.py').replace(wurzel / 'INSTALL_NAMENSWECHSEL.py')
        (wurzel / 'docs/NAMENSWECHSEL_SEDRA_2026-11-06.md').replace(wurzel / 'LIESMICH.md')
        (wurzel / 'docs').rmdir()
        (wurzel / 'release/PAKET.json').write_text(json.dumps({'commit': commit, 'dateien': len(programm)}, indent=2), encoding='utf-8')
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(wurzel.rglob('*')):
                if p.is_file():
                    zf.write(p, p.relative_to(wurzel.parent).as_posix())
    summe = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{summe}  {output.name}\n', encoding='ascii')
    return {'datei': str(output), 'sha256': summe, 'dateien': len(programm), 'commit': commit}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--output', required=True)
    ap.add_argument('--rev', default='HEAD')
    a = ap.parse_args()
    print(json.dumps(bauen(Path(a.output), a.rev), indent=2))
