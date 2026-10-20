r"""Install GUPPI's own llama.cpp engine from already downloaded release zips (no download here; that is the Captain's decision).

    .venv\Scripts\python.exe benchmarks/engine_install.py <download_dir> [--verify]

Reads engine_build and the SHA256 pins (engine_assets) from config/llama_server.yaml, checks every zip, unpacks into a staging
folder and renames it to <GUPPI_Runtime>/engines/llama.cpp/<build>/ with a manifest of file hashes (guppi_runtime/models/engine_provision.py).
--verify only re-checks an installed engine (every file). Afterwards: engine_source: guppi in config/llama_server.yaml.
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
from guppi_runtime.models.engine_provision import DEFAULT_ROOT, provision, verify_engine  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("download_dir", nargs="?"); ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    raw = (yaml.safe_load((RUNTIME / "config" / "llama_server.yaml").read_text(encoding="utf-8")) or {})["llama_server"]
    root = Path(raw["engine_root"]) if raw.get("engine_root") else DEFAULT_ROOT
    if not args.verify:
        manifest = provision(args.download_dir, build=raw["engine_build"], assets=raw["engine_assets"], root=root)
        print(json.dumps({"installed": raw["engine_build"], "files": len(manifest["files"]), "zips": manifest["zips"]}, indent=2))
    print("verify:", verify_engine(root, raw["engine_build"], full=True))


if __name__ == "__main__":
    main()
