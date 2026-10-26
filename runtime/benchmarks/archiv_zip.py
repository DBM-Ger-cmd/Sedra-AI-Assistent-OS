r"""Archiv der alten Installation als Zip (Umzug nach A1, U2-12): `E:\Sedra Umgebung\Entwickler_Archiv\GUPPI_Runtime_v1.20.Archiv.zip` mit Manifest, verifiziert. Löscht NICHTS.

    python benchmarks/archiv_zip.py                      Trockenlauf: zählt, prüft Platz und Ruhe, startet nichts
    python benchmarks/archiv_zip.py --go                 Zip und Manifest erzeugen, gegen das Manifest und den Ordner verifizieren (Captain-Gate)
    python benchmarks/archiv_zip.py --verify             vorhandenes Zip erneut prüfen (Zip gegen Manifest; Ordner gegen Manifest, wenn er noch da ist)
    optionen: --source <Ordner>  --target-dir <Ordner>  --name GUPPI_Runtime_v1.20.Archiv  --level 6  --exclude <relativer Pfad> (wiederholbar)  --no-checks (nur Tests)

Ablauf von --go: Prüfungen (kein Prozess aus dem Ordner, Port 8089 frei, kein llama-server, GPU-Lease frei, genug Platz, Ziel noch nicht vorhanden) -> Zip in `<name>.zip.part` und Manifest
(`path,size,sha256`, ein Durchgang: derselbe Lesevorgang schreibt und hasht) -> Zip gegen das Manifest (jede Datei neu gelesen und gehasht, keine fehlt, keine zu viel, `testzip`) -> Umbenennen
in `<name>.zip` -> Ordner gegen das Manifest (hat sich seit dem Packen etwas geändert?) -> `<name>.ergebnis.json`. Vorhandene Zieldateien werden nie überschrieben.
Das Löschen des Ordners ist ein eigener Schritt des Captains (Papierkorb-Limit von E: beachten); dieses Werkzeug löscht nie."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = r"E:\Sedra Umgebung\GUPPI_Runtime_v1.20"
DEFAULT_DIR = r"E:\Sedra Umgebung\Entwickler_Archiv"
DEFAULT_NAME = "GUPPI_Runtime_v1.20.Archiv"
CHUNK = 1 << 20


def long(path):
    """Erweiterter Pfad für Windows (lange Namen)."""
    p = os.path.abspath(str(path))
    return "\\\\?\\" + p if os.name == "nt" and not p.startswith("\\\\?\\") else p


def listing(source, excludes=()):
    """[(relativer Pfad mit /, absoluter Pfad)] aller Dateien, sortiert; Links werden nicht verfolgt."""
    root = Path(source)
    out = []
    for base, dirs, files in os.walk(long(root)):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(base, name)
            rel = os.path.relpath(full, long(root)).replace("\\", "/")
            if any(rel == e or rel.startswith(e.rstrip("/") + "/") for e in excludes):
                continue
            out.append((rel, full))
    out.sort(key=lambda x: x[0])
    return out


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def build(files, zip_part, manifest_part, level, say):
    rows = []
    total = sum(os.path.getsize(f) for _, f in files)
    done, started, last = 0, time.time(), time.time()
    with zipfile.ZipFile(long(zip_part), "w", zipfile.ZIP_DEFLATED, compresslevel=level, allowZip64=True) as zf:
        for rel, full in files:
            st = os.stat(full)
            stamp = time.localtime(max(st.st_mtime, 315532800))
            info = zipfile.ZipInfo(rel, date_time=stamp[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info._compresslevel = level
            info.external_attr = 0o644 << 16
            h = hashlib.sha256()
            with open(full, "rb") as src, zf.open(info, "w", force_zip64=True) as dst:
                while True:
                    block = src.read(CHUNK)
                    if not block:
                        break
                    h.update(block)
                    dst.write(block)
            rows.append((rel, st.st_size, h.hexdigest()))
            done += st.st_size
            if time.time() - last > 15:
                last = time.time()
                say(f"  gepackt {done / 2 ** 30:.2f} von {total / 2 ** 30:.2f} GB, {len(rows)} von {len(files)} Dateien, {time.time() - started:.0f} s")
    with open(long(manifest_part), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path", "size", "sha256"])
        w.writerows(rows)
    return rows


def read_manifest(path):
    with open(long(path), encoding="utf-8", newline="") as f:
        rd = csv.reader(f)
        next(rd)
        return [(p, int(s), h) for p, s, h in rd]


def verify_zip(zip_path, rows, say=print):
    problems = []
    want = {p: (s, h) for p, s, h in rows}
    try:
        zf = zipfile.ZipFile(long(zip_path))
    except Exception as exc:
        return [f"Zip nicht lesbar: {str(exc)[:120]}"]
    with zf:
        try:
            bad = zf.testzip()
        except Exception as exc:
            bad = f"(Lesefehler: {str(exc)[:80]})"
        if bad:
            problems.append(f"testzip: beschädigt {bad}")
        names = set(zf.namelist())
        problems += [f"fehlt im Zip: {p}" for p in sorted(set(want) - names)[:20]]
        problems += [f"zu viel im Zip: {p}" for p in sorted(names - set(want))[:20]]
        for i, p in enumerate(sorted(set(want) & names)):
            h = hashlib.sha256()
            size = 0
            try:
                with zf.open(p) as f:
                    while True:
                        block = f.read(CHUNK)
                        if not block:
                            break
                        h.update(block)
                        size += len(block)
            except Exception as exc:
                problems.append(f"nicht lesbar: {p} ({str(exc)[:60]})")
                continue
            if (size, h.hexdigest()) != want[p]:
                problems.append(f"Prüfsumme weicht ab: {p}")
            if (i + 1) % 5000 == 0:
                say(f"  Zip geprüft: {i + 1} Dateien")
    return problems


def verify_source(source, rows, excludes=(), say=print):
    problems = []
    want = {p: (s, h) for p, s, h in rows}
    have = dict(listing(source, excludes))
    problems += [f"im Ordner neu seit dem Packen: {p}" for p in sorted(set(have) - set(want))[:20]]
    problems += [f"im Ordner fehlt: {p}" for p in sorted(set(want) - set(have))[:20]]
    for i, p in enumerate(sorted(set(want) & set(have))):
        if os.path.getsize(have[p]) != want[p][0] or sha_file(have[p]) != want[p][1]:
            problems.append(f"Ordner weicht vom Manifest ab: {p}")
        if (i + 1) % 5000 == 0:
            say(f"  Ordner geprüft: {i + 1} Dateien")
    return problems


def free_gb(path):
    """Freier Platz des Laufwerks; existiert der Ordner noch nicht, zählt der nächste vorhandene Elternordner."""
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    return shutil.disk_usage(str(p)).free / 2 ** 30


def checks(source, target_dir, needed_gb):
    """Probleme, die den Lauf verbieten."""
    problems = []
    if os.name == "nt":
        cmd = (f"@(Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{Path(source).name}*' -and $_.Name -match 'python|llama|cmd' }}).Count; "
               "@(Get-NetTCPConnection -State Listen -LocalPort 8089 -ErrorAction SilentlyContinue).Count; @(Get-Process llama-server -ErrorAction SilentlyContinue).Count")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout.split()
        names = ["Prozesse aus dem Ordner", "Port 8089 belegt", "llama-server läuft"]
        problems += [f"{n}: {c}" for n, c in zip(names, out) if c != "0"]
    try:
        sys.path.insert(0, str(RUNTIME / "src"))
        from guppi_runtime.jobs.testlab import TestLab, default_path
        holder = TestLab(default_path(Path(source) / "workspace" / "GUPPI_OS")).holder()
        if holder and not holder.get("stale"):
            problems.append(f"GPU-Lease belegt von {holder.get('owner')}")
    except Exception as exc:
        problems.append(f"GPU-Lease nicht prüfbar: {str(exc)[:80]}")
    free = free_gb(target_dir)
    if free < needed_gb * 1.2:
        problems.append(f"zu wenig Platz auf dem Ziel: {free:.1f} GB frei, gebraucht etwa {needed_gb * 1.2:.1f} GB")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--target-dir", default=DEFAULT_DIR)
    ap.add_argument("--name", default=DEFAULT_NAME)
    ap.add_argument("--level", type=int, default=6)
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--no-checks", action="store_true", help="nur für Tests: Prozess-, Port- und Lease-Prüfung auslassen")
    args = ap.parse_args(argv)
    target = Path(args.target_dir)
    zip_path, man_path, res_path = target / f"{args.name}.zip", target / f"{args.name}.manifest.csv", target / f"{args.name}.ergebnis.json"
    say = lambda s: print(s, flush=True)  # noqa: E731
    if args.verify:
        rows = read_manifest(man_path)
        problems = verify_zip(zip_path, rows, say)
        if Path(args.source).is_dir():
            problems += verify_source(args.source, rows, args.exclude, say)
        else:
            say("Ordner nicht mehr vorhanden: nur das Zip wurde gegen das Manifest geprüft.")
        say(f"Prüfung: {len(rows)} Dateien, {len(problems)} Probleme")
        for p in problems[:30]:
            say("  " + p)
        return 0 if not problems else 3
    files = listing(args.source, args.exclude)
    size = sum(os.path.getsize(f) for _, f in files)
    say(f"Quelle {args.source}: {len(files)} Dateien, {size / 2 ** 30:.2f} GB (ohne Ausschlüsse {args.exclude or 'keine'})")
    say(f"Ziel   {zip_path} (+ {man_path.name}, {res_path.name}); Schätzung {size / 2 ** 20 / 15 / 60 / 3:.0f} bis {size / 2 ** 20 / 5 / 60 / 3:.0f} min Packen (dazu zwei Prüfdurchgänge)")
    problems = [] if args.no_checks else checks(args.source, target, size / 2 ** 30)
    for p in (zip_path, man_path, res_path, Path(str(zip_path) + ".part")):
        if p.exists():
            problems.append(f"Ziel vorhanden (wird nie überschrieben): {p.name}")
    if args.no_checks:
        free = free_gb(target)
        if free < size / 2 ** 30 * 1.2:
            problems.append("zu wenig Platz")
    for p in problems:
        say("PROBLEM: " + p)
    if not args.go:
        say("Trockenlauf: nichts erzeugt. Mit --go nach dem Signal des Captains.")
        return 1 if problems else 0
    if problems:
        return 2
    target.mkdir(parents=True, exist_ok=True)
    part, man_part = Path(str(zip_path) + ".part"), Path(str(man_path) + ".part")
    t0 = time.time()
    rows = build(files, part, man_part, args.level, say)
    say(f"Zip geschrieben: {os.path.getsize(long(part)) / 2 ** 30:.2f} GB in {time.time() - t0:.0f} s; prüfe gegen das Manifest ...")
    problems = verify_zip(part, rows, say)
    if problems:
        say("FEHLER in der Verifikation, Zip bleibt als .part liegen:")
        for p in problems[:30]:
            say("  " + p)
        return 3
    os.replace(long(man_part), long(man_path))
    os.replace(long(part), long(zip_path))
    say("Zip gegen Manifest: 0 Probleme; prüfe den Ordner gegen das Manifest ...")
    src_problems = verify_source(args.source, rows, args.exclude, say)
    result = {"zip": str(zip_path), "manifest": str(man_path), "source": args.source, "files": len(rows), "bytes_source": size, "bytes_zip": os.path.getsize(long(zip_path)),
              "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seconds": round(time.time() - t0), "zip_vs_manifest_problems": 0,
              "source_vs_manifest_problems": len(src_problems), "source_problems": src_problems[:30], "excluded": args.exclude}
    res_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    say(json.dumps({k: result[k] for k in ("files", "bytes_source", "bytes_zip", "seconds", "zip_vs_manifest_problems", "source_vs_manifest_problems")}, ensure_ascii=False))
    say("Fertig. Der Ordner wurde NICHT gelöscht; das ist der Schritt des Captains.")
    return 0 if not src_problems else 4


if __name__ == "__main__":
    sys.exit(main())
