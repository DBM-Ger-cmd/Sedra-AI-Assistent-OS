"""Fork-Version als ZIP (Lieferung ohne Push, Regel des Captains): der Repo-Stand HEAD (git archive, ohne .git), PRUEFSUMMEN.sha256 und
PACKAGE_CHECKSUMS.sha256 neu berechnet.  python benchmarks/fork_zip.py <ziel.zip> [repo-ordner]  – vorher committen."""
import hashlib, io, subprocess, sys, zipfile
from pathlib import Path
REPO = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1])
head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
raw = subprocess.run(['git', 'archive', '--format=zip', 'HEAD'], cwd=REPO, capture_output=True, check=True).stdout
src = zipfile.ZipFile(io.BytesIO(raw))
names = [n for n in src.namelist() if not n.endswith('/') and n not in ('PRUEFSUMMEN.sha256', 'PACKAGE_CHECKSUMS.sha256')]
lines = []
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
    for n in sorted(names):
        data = src.read(n)
        z.writestr('Sedra-AI-Assistent-OS-harness-stufe-4/' + n, data)
        lines.append(f'{hashlib.sha256(data).hexdigest()}  {n}')
    sums = '\n'.join(lines) + '\n'
    z.writestr('Sedra-AI-Assistent-OS-harness-stufe-4/PRUEFSUMMEN.sha256', sums)
    z.writestr('Sedra-AI-Assistent-OS-harness-stufe-4/PACKAGE_CHECKSUMS.sha256', sums)
print(OUT, head, len(names), 'Dateien', OUT.stat().st_size // 1024, 'KB')
