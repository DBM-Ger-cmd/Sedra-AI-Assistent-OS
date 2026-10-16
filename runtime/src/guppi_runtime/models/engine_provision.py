"""GUPPI's own llama.cpp engine, without LM Studio (2026-10-03, Captain: "nicht LM Studio, nur GUPPI").

The engine comes from the official llama.cpp release zips (github.com/ggml-org/llama.cpp, Windows CUDA build + its CUDA runtime zip).
Downloading is the Captain's decision and happens outside this module; this module only installs what was downloaded:

  1. every zip must match the SHA256 pinned in config/llama_server.yaml (`engine_assets`), so a different or altered file is refused,
  2. the zips are unpacked into a staging folder next to the target (never over an existing engine),
  3. `llama-server.exe` must be there; a manifest records the build, the zip hashes and the SHA256 of every unpacked file,
  4. only then the staging folder is renamed to engines/llama.cpp/<build>/ (one rename, so a half install is never used).

`verify_engine` is what the runtime calls before it uses the engine: manifest present, build as configured, llama-server.exe unchanged.
`verify_engine(full=True)` re-hashes every file (for the doctor; slower).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

MANIFEST = "guppi_engine.json"
BUILD_RE = re.compile(r"b\d{3,6}")
SHA_RE = re.compile(r"[0-9a-f]{64}")
DEFAULT_ROOT = Path(__file__).resolve().parents[4] / "engines"     # <GUPPI_Runtime>/engines, next to runtime/ and workspace/


class EngineError(ValueError):
    pass


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def engine_dir(root, build):
    if not isinstance(build, str) or not BUILD_RE.fullmatch(build):
        raise EngineError("engine_build_invalid")
    return Path(root) / "llama.cpp" / build


def _check_pins(assets):
    if not isinstance(assets, dict) or not assets:
        raise EngineError("engine_assets_missing")
    for name, digest in assets.items():
        if not isinstance(name, str) or not name.endswith(".zip") or "/" in name or "\\" in name:
            raise EngineError("engine_asset_name_invalid")
        if not isinstance(digest, str) or not SHA_RE.fullmatch(digest.removeprefix("sha256:")):
            raise EngineError("engine_asset_sha256_invalid")
    return {n: d.removeprefix("sha256:") for n, d in assets.items()}


def provision(download_dir, *, build, assets, root=DEFAULT_ROOT, now=None):
    """Install the pinned zips found in `download_dir` as engines/llama.cpp/<build>. Returns the manifest. Never overwrites."""
    pins = _check_pins(assets)
    target = engine_dir(root, build)
    if target.exists():
        raise EngineError("engine_already_installed")
    download_dir = Path(download_dir)
    zip_hashes = {}
    for name, expected in pins.items():
        path = download_dir / name
        if not path.is_file():
            raise EngineError(f"engine_asset_missing:{name}")
        actual = sha256_file(path)
        if actual != expected:
            raise EngineError(f"engine_asset_sha256_mismatch:{name}")
        zip_hashes[name] = actual
    staging = target.parent / f".staging-{build}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        for name in pins:
            with zipfile.ZipFile(download_dir / name) as z:
                for member in z.infolist():
                    # Flat release zips only: no absolute paths, no "..", nothing outside the staging folder.
                    rel = Path(member.filename)
                    if rel.is_absolute() or ".." in rel.parts or rel.drive:
                        raise EngineError("engine_zip_unsafe_path")
                z.extractall(staging)
        if not (staging / "llama-server.exe").is_file():
            raise EngineError("engine_llama_server_missing")
        files = {p.relative_to(staging).as_posix(): sha256_file(p) for p in sorted(staging.rglob("*")) if p.is_file()}
        manifest = {"build": build, "source": "github.com/ggml-org/llama.cpp/releases/tag/" + build, "zips": zip_hashes, "files": files,
                    "installed_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")}
        (staging / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        staging.rename(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return manifest


def verify_engine(root, build, *, full=False):
    """(ok, reason). Quick check: manifest + build + llama-server.exe hash. full=True re-hashes every recorded file."""
    try:
        target = engine_dir(root, build)
    except EngineError as exc:
        return False, str(exc)
    try:
        manifest = json.loads((target / MANIFEST).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, "engine_not_installed"
    except (OSError, ValueError):
        return False, "engine_manifest_unreadable"
    if manifest.get("build") != build or not isinstance(manifest.get("files"), dict):
        return False, "engine_manifest_mismatch"
    # A DLL planted next to llama-server.exe is loaded by it: a file that the manifest does not list fails the quick check too (cheap, the folder is flat).
    listed = {name.lower() for name in manifest["files"]} | {MANIFEST.lower()}
    for path in target.rglob("*"):
        if path.is_file() and path.relative_to(target).as_posix().lower() not in listed:
            return False, f"engine_unlisted_file:{path.relative_to(target).as_posix()}"
    names = manifest["files"] if full else {"llama-server.exe": manifest["files"].get("llama-server.exe")}
    for rel, digest in names.items():
        path = target / rel
        if not digest or not path.is_file():
            return False, f"engine_file_missing:{rel}"
        if sha256_file(path) != digest:
            return False, f"engine_file_changed:{rel}"
    return True, "ok"
