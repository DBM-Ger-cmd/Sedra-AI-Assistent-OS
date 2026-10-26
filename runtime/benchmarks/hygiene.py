r"""Hygiene-Prüfung für die Arbeitsumgebung (Regel 2026-10-26: keine eigene Sedra-Kopie je Sitzung). Nur Anzeige, löscht nichts, außer mit --apply-temp.

    python benchmarks/hygiene.py                 # Bericht: unbekannte Ordner unter E:\Sedra Umgebung, Worktrees, Sedra-Reste im Temp-Ordner, laufende Sedra-Prozesse
    python benchmarks/hygiene.py --root "E:\Sedra Umgebung" --temp-hours 24
    python benchmarks/hygiene.py --apply-temp    # löscht NUR Temp-Ordner mit Sedra-Präfix (TEMP_PREFIXES), älter als --temp-hours

Was gilt als Kopie: ein Ordner unter --root, der nicht in ALLOWED steht (Name oder Präfix) und ein `.git`, `runtime` oder `GUPPI_OS` enthält.
Erlaubt sind die Installation, der Entwicklungsstand A1 und die Ablagen, die der Captain benannt hat; alles andere ist ein Befund.
Worktrees kommen nur von der App (git worktree list); Prüfung zeigt solche, deren Branch vollständig im Hauptbranch steht (aufräumbar)."""
import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ALLOWED = ('GUPPI_Runtime_v1.20', 'A1 Sedra Main Branch Entwicklungs umgebung', 'SEDRA_Build_024', 'Sedra_Engine_v1', 'Qwen3.5-9B-MTP-GGUF',
           '_Entwickler_Zip_', '_Aufraeumen_', 'Back Up', 'Alt', 'Entwickler_Archiv', 'Patches', 'Assets', 'paperclip-master', 'OpenSCAD')
TEMP_PREFIXES = ('gw-wissen', 'guppi_judge_src', 'guppi_devvm_build_rt', 'guppi-uix-check', 'guppi-uix-window', 'guppi_slotmeasure',
                 'orchestra-', 'hidden-', 'jobs-modules-', 'arbeitsplatz')
MARKERS = ('.git', 'runtime', 'GUPPI_OS')
MAIN = 'spec/agenten-orchestrierung'


def size_mb(path):
    return sum(f.stat().st_size for f in Path(path).rglob('*') if f.is_file()) / 1048576


def copies(root):
    out = []
    for folder in sorted(Path(root).iterdir()):
        if not folder.is_dir() or any(folder.name.startswith(a) for a in ALLOWED):
            continue
        if any((folder / m).exists() for m in MARKERS):
            out.append((folder, size_mb(folder)))
    return out


def worktrees(repo):
    done = subprocess.run(['git', 'worktree', 'list', '--porcelain'], cwd=repo, capture_output=True, text=True)
    items, current = [], {}
    for line in done.stdout.splitlines() + ['']:
        if not line.strip():
            if current:
                items.append(current)
            current = {}
        else:
            key, _, value = line.partition(' ')
            current[key] = value
    return items


def merged(repo, branch):
    done = subprocess.run(['git', 'rev-list', '--count', f'{MAIN}..{branch}'], cwd=repo, capture_output=True, text=True)
    return done.returncode == 0 and done.stdout.strip() == '0'


def temp_leftovers(hours):
    limit = time.time() - hours * 3600
    return [p for p in Path(tempfile.gettempdir()).iterdir() if p.is_dir() and p.name.startswith(TEMP_PREFIXES) and p.stat().st_mtime < limit]


def sedra_processes():
    if sys.platform != 'win32':
        return []
    cmd = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uix_server|uix_start|llama-server|guppi_runtime' -and $_.Name -match 'python|llama' }"
           " | ForEach-Object { \"$($_.ProcessId) $($_.Name) \" + $_.CommandLine.Substring(0, [Math]::Min(120, $_.CommandLine.Length)) }")
    done = subprocess.run(['powershell', '-NoProfile', '-Command', cmd], capture_output=True, text=True)
    return [l for l in done.stdout.splitlines() if l.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description='Hygiene der Arbeitsumgebung (nur Anzeige).')
    ap.add_argument('--root', default=r'E:\Sedra Umgebung')
    ap.add_argument('--repo', default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument('--temp-hours', type=float, default=24)
    ap.add_argument('--apply-temp', action='store_true')
    args = ap.parse_args(argv)
    findings = 0
    found = copies(args.root) if Path(args.root).is_dir() else []
    print(f'Kopien unter {args.root} (nicht in ALLOWED): {len(found)}')
    for folder, mb in found:
        print(f'  {folder.name}  {mb:,.0f} MB')
    findings += len(found)
    trees = [t for t in worktrees(args.repo) if Path(t['worktree']).resolve() != Path(args.repo).resolve()]
    cleanable = [t for t in trees if t.get('branch', '').startswith('refs/heads/') and merged(args.repo, t['branch'][11:])]
    print(f'Worktrees (ohne A1): {len(trees)}, davon vollständig gemergt und aufräumbar: {len(cleanable)}')
    for t in cleanable:
        print('  ', t['worktree'], t['branch'][11:])
    findings += len(cleanable)
    left = temp_leftovers(args.temp_hours)
    mb = sum(size_mb(p) for p in left)
    print(f'Sedra-Reste im Temp-Ordner (älter als {args.temp_hours:g} h): {len(left)} Ordner, {mb:,.0f} MB')
    findings += len(left)
    procs = sedra_processes()
    print(f'Laufende eigene Sedra-/llama-Prozesse: {len(procs)}')
    for p in procs:
        print('  ', p)
    if args.apply_temp:
        for p in left:
            shutil.rmtree(p, ignore_errors=True)
        print(f'{len(left)} Temp-Ordner gelöscht')
    return 0 if not findings else 1


if __name__ == '__main__':
    sys.exit(main())
