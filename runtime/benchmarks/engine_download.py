r"""Erststart: holt GUPPI's llama.cpp-Engine von GitHub (offizielle Release), prüft jede Datei gegen die SHA256-Pins aus
config/llama_server.yaml (engine_assets) und installiert sie nach <GUPPI_Runtime>/engines/llama.cpp/<engine_build>/.

    portable\python\current\python.exe -I -B benchmarks\engine_download.py [--ja]

Ohne --ja fragt das Skript vorher nach (Download ca. 625 MB). Danach werden die Zip-Dateien wieder gelöscht.
Bereits installierte und geprüfte Engine: nichts wird geladen.
"""
import argparse
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
from guppi_runtime.models.engine_provision import DEFAULT_ROOT, provision, verify_engine  # noqa: E402

URL = "https://github.com/ggml-org/llama.cpp/releases/download/{build}/{name}"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(url, target):
    with urllib.request.urlopen(url, timeout=120) as resp, open(target, "wb") as out:
        shutil.copyfileobj(resp, out, length=1 << 20)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ja", action="store_true", help="ohne Rückfrage laden (der Erststart fragt selbst)")
    args = ap.parse_args()
    raw = (yaml.safe_load((RUNTIME / "config" / "llama_server.yaml").read_text(encoding="utf-8")) or {})["llama_server"]
    build, assets = raw["engine_build"], raw["engine_assets"]
    root = Path(raw["engine_root"]) if raw.get("engine_root") else DEFAULT_ROOT
    ok, reason = verify_engine(root, build, full=True)
    if ok:
        print(f"Engine {build} ist schon installiert und geprüft.")
        return 0
    if not args.ja:
        answer = input(f"Engine {build} von GitHub laden (ca. 625 MB, Prüfsummen werden geprüft)? Zum Laden JA eingeben: ")
        if answer.strip() != "JA":
            print("Abgebrochen.")
            return 1
    staging = RUNTIME / "portable" / "downloads" / "engine"
    staging.mkdir(parents=True, exist_ok=True)
    try:
        for name, digest in assets.items():
            path = staging / name
            if not (path.is_file() and sha256(path) == digest.removeprefix("sha256:")):
                print(f"Lade {name} ...", flush=True)
                fetch(URL.format(build=build, name=name), path)
            if sha256(path) != digest.removeprefix("sha256:"):
                raise SystemExit(f"Prüfsumme stimmt nicht: {name}")
        manifest = provision(staging, build=build, assets=assets, root=root)
        print(f"Engine {build} installiert: {len(manifest['files'])} Dateien.")
        print("Prüfung:", verify_engine(root, build, full=True))
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
