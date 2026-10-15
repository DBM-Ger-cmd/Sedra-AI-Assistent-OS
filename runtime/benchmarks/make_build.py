r"""Package a build: clean the tree copy, write the checksum file, zip it, and (optionally) a patch against the previous package.

    .venv\Scripts\python.exe benchmarks/make_build.py --out <folder> [--previous <folder of the previous package>] [--bump]

Reads BUILD.txt at the repository root (build number, date, version). --bump raises the number and sets today's date before packaging.
Excludes what .gitignore excludes (engines, workspace, runtime_data, .venv, portable, caches, models, secrets) and .git. The zip is named
GUPPI_Runtime_v<version>_Build_<nnn>_<date>.zip; PACKAGE_CHECKSUMS.sha256 inside lists every file. Exit code 0 when the zip verifies."""
import argparse
import datetime
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "engines", "workspace", "archiv", "runtime_data", "portable", "node_modules"}
EXCLUDE_SUFFIXES = {".pyc", ".sqlite", ".sqlite-journal", ".log", ".lock", ".gguf", ".zip", ".tar", ".token"}
EXCLUDE_NAMES = {"tokens.json", ".env", "local_paths.yaml"}


def read_build(path):
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" in line:
            k, v = line.split(":", 1); data[k.strip()] = v.strip()
    return data


def write_build(path, data):
    path.write_text("".join(f"{k}: {v}\n" for k, v in data.items()), encoding="utf-8")


def wanted(rel):
    parts = rel.parts
    if any(p in EXCLUDE_DIRS for p in parts[:-1]): return False
    name = parts[-1]
    if name in EXCLUDE_NAMES or name.startswith(".env.") or ".bak-" in name or ".model-original-" in name: return False
    return Path(name).suffix not in EXCLUDE_SUFFIXES


def collect(root):
    return sorted(p for p in root.rglob("*") if p.is_file() and wanted(p.relative_to(root)))


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--previous", help="folder with the previous package's tree (a patch previous -> this build is written next to the zip)")
    ap.add_argument("--bump", action="store_true")
    args = ap.parse_args(argv)
    build_file = ROOT / "BUILD.txt"
    info = read_build(build_file)
    if args.bump:
        info["build"] = str(int(info.get("build", "0")) + 1); info["date"] = datetime.date.today().isoformat(); write_build(build_file, info)
    number, date, version = int(info["build"]), info["date"], info.get("version", "1.20")
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    name = f"GUPPI_Runtime_v{version}_Build_{number:03d}_{date}"
    with tempfile.TemporaryDirectory(prefix="guppi-build-") as tmp:
        tree = Path(tmp) / ROOT.name
        files = collect(ROOT)
        for p in files:
            rel = p.relative_to(ROOT); (tree / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, tree / rel)
        checks = tree / "PACKAGE_CHECKSUMS.sha256"
        checks.write_text("".join(f"{sha256(tree / p.relative_to(ROOT))}  {p.relative_to(ROOT).as_posix()}\n" for p in files), encoding="utf-8")
        zip_path = out / f"{name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(tree.rglob("*")):
                if p.is_file(): z.write(p, p.relative_to(tree.parent).as_posix())
        if args.previous:
            prev = Path(args.previous)
            patch = out / f"{name}.patch"
            with patch.open("w", encoding="utf-8") as f:
                # the previous folder may be a working tree (runtime_data, portable wheels, logs): the patch only covers what a package holds
                skip = [arg for d in sorted(EXCLUDE_DIRS) for arg in ("-x", d)] + [arg for suf in sorted(EXCLUDE_SUFFIXES) for arg in ("-x", "*" + suf)]
                subprocess.run(["diff", "-ruN", "--strip-trailing-cr", *skip, str(prev), str(tree)], stdout=f, text=True)
        with zipfile.ZipFile(zip_path) as z:
            bad = z.testzip()
    print(f"build {number} ({date}) -> {zip_path} sha256 {sha256(zip_path)} files {len(files)}" + (f" corrupt {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
