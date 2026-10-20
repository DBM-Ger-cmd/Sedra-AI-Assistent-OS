from __future__ import annotations
from pathlib import Path
import hashlib, re
from ..core.util import atomic_write_json, load_json, utcnow


_QUANT_RE = re.compile(r"(?i)(?:^|[._-])((?:I?Q)[0-9][A-Z0-9_\-]*)(?:[._-]|$)")
_PARAM_RE = re.compile(r"(?i)(?:^|[._-])(\d+(?:\.\d+)?B)(?:[._-]|$)")


class ModelCatalog:
    def __init__(self, catalog_path: Path, allowed_roots=None):
        self.catalog_path = Path(catalog_path)
        self.allowed_roots = [Path(p).resolve() for p in (allowed_roots or [])]
        self._data = load_json(self.catalog_path, {"schema": 1, "models": {}}) or {"schema": 1, "models": {}}
        self._data.setdefault("schema", 1)
        self._data.setdefault("models", {})

    def add_allowed_root(self, root: Path):
        r = Path(root).resolve()
        if r not in self.allowed_roots:
            self.allowed_roots.append(r)

    def _validate_path(self, path: Path) -> Path:
        p = Path(path).resolve()
        if self.allowed_roots:
            ok = False
            for root in self.allowed_roots:
                try:
                    p.relative_to(root)
                    ok = True
                    break
                except ValueError:
                    pass
            if not ok:
                raise PermissionError("model_path_outside_allowed_roots")
        return p

    @staticmethod
    def _metadata(path: Path) -> dict:
        name = path.name
        q = _QUANT_RE.search(name)
        params = _PARAM_RE.search(name)
        size_bytes = path.stat().st_size
        fingerprint = hashlib.sha256(f"{name}|{size_bytes}".encode("utf-8")).hexdigest()[:20]
        return {
            "id": f"GGUF-{fingerprint.upper()}",
            "name": path.stem,
            "filename": name,
            "path": str(path),
            "format": "gguf",
            "size_bytes": size_bytes,
            "size_gb": round(size_bytes / (1024 ** 3), 3),
            "quantization": q.group(1).upper() if q else None,
            "parameters_hint": params.group(1).upper() if params else None,
            "registered_at": utcnow(),
        }

    def register(self, path: Path) -> dict:
        p = self._validate_path(path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError("model_file_not_found")
        if p.suffix.lower() != ".gguf":
            raise ValueError("unsupported_model_format")
        rec = self._metadata(p)
        self._data["models"][rec["id"]] = rec
        self._save()
        return rec

    def scan(self, root: Path | None = None, max_files: int = 5000) -> list[dict]:
        roots = [self._validate_path(root)] if root else list(self.allowed_roots)
        found = []
        count = 0
        for base in roots:
            if not base.exists():
                continue
            for p in base.rglob("*.gguf"):
                if count >= max_files:
                    raise RuntimeError("model_scan_limit_exceeded")
                if p.is_file() and not p.is_symlink():
                    found.append(self.register(p))
                    count += 1
        return found

    def list(self) -> list[dict]:
        return sorted(self._data["models"].values(), key=lambda x: (x.get("name") or "").lower())

    def get(self, model_id: str) -> dict:
        rec = self._data["models"].get(model_id)
        if not rec:
            raise KeyError("unknown_model_id")
        return dict(rec)

    def prune_missing(self) -> int:
        missing = [mid for mid, rec in self._data["models"].items() if not Path(rec["path"]).exists()]
        for mid in missing:
            self._data["models"].pop(mid, None)
        if missing:
            self._save()
        return len(missing)

    def _save(self):
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.catalog_path, self._data)
