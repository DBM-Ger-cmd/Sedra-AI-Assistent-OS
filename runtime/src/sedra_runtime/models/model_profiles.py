from __future__ import annotations
from pathlib import Path
from copy import deepcopy
import yaml
from ..core.util import utcnow


class ModelProfileStore:
    def __init__(self, builtin_path: Path, custom_path: Path | None = None, known_good_path: Path | None = None):
        self.builtin_path = Path(builtin_path)
        self.custom_path = Path(custom_path) if custom_path else None
        self.known_good_path = Path(known_good_path) if known_good_path else None

    def _load(self, path):
        if not path or not Path(path).exists():
            return {}
        return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    def presets(self):
        data = self._load(self.builtin_path)
        return data.get("hardware_model_profiles", {}).get("presets", {})

    def custom(self):
        data = self._load(self.custom_path)
        return data.get("custom_profiles", {}) if self.custom_path else {}

    def known_good_records(self):
        data = self._load(self.known_good_path)
        return data.get("known_good_profiles", {}) if self.known_good_path else {}

    def known_good(self):
        out = {}
        for pid, rec in self.known_good_records().items():
            if isinstance(rec, dict) and isinstance(rec.get("profile"), dict):
                out[pid] = deepcopy(rec["profile"])
        return out

    def all(self):
        out = dict(self.presets())
        out.update(self.known_good())
        out.update(self.custom())
        return out

    def select_for_hardware(self, hardware_class, *, hardware_fingerprint=None, model_id=None, runtime=None):
        if hardware_fingerprint and model_id:
            candidates = []
            for pid, rec in self.known_good_records().items():
                if rec.get("hardware", {}).get("fingerprint") != hardware_fingerprint:
                    continue
                if rec.get("model", {}).get("id") != model_id:
                    continue
                if runtime and rec.get("runtime") != runtime:
                    continue
                if rec.get("status") != "confirmed":
                    continue
                candidates.append((float(rec.get("score", 0) or 0), str(rec.get("confirmed_at", "")), pid, rec))
            if candidates:
                candidates.sort(reverse=True)
                return deepcopy(candidates[0][3]["profile"])

        presets = self.presets()
        exact = [p for p in presets.values() if hardware_class in p.get("hardware_classes", [])]
        if exact:
            return deepcopy(exact[0])
        return deepcopy(presets.get("safe-cpu-default"))

    def save_custom(self, profile_id: str, profile: dict):
        if not self.custom_path:
            raise ValueError("custom_path_required")
        if not profile_id or profile_id in self.presets() or profile_id in self.known_good_records():
            raise ValueError("invalid_or_reserved_profile_id")
        self._validate_profile(profile)
        data = self._load(self.custom_path)
        data.setdefault("custom_profiles", {})[profile_id] = profile
        self.custom_path.parent.mkdir(parents=True, exist_ok=True)
        self.custom_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return profile

    def save_known_good(self, profile_id: str, record: dict):
        if not self.known_good_path:
            raise ValueError("known_good_path_required")
        if not profile_id or profile_id in self.presets() or profile_id in self.custom():
            raise ValueError("invalid_or_reserved_profile_id")
        if not isinstance(record, dict) or not isinstance(record.get("profile"), dict):
            raise ValueError("known_good_record_required")
        self._validate_profile(record["profile"])
        rec = deepcopy(record)
        rec.setdefault("status", "confirmed")
        rec.setdefault("confirmed_at", utcnow())
        data = self._load(self.known_good_path)
        data.setdefault("schema", 1)
        data.setdefault("known_good_profiles", {})[profile_id] = rec
        self.known_good_path.parent.mkdir(parents=True, exist_ok=True)
        self.known_good_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return rec

    def _validate_profile(self, profile):
        required = {"runtime", "model", "quantization", "context", "memory_reserve_gb"}
        missing = sorted(required - set(profile))
        if missing:
            raise ValueError("missing_profile_fields:" + ",".join(missing))
        context = profile.get("context")
        if not isinstance(context, dict):
            raise ValueError("invalid_context_profile")
        recommended = int(context.get("recommended", 0) or 0); maximum = int(context.get("maximum", 0) or 0)
        if recommended <= 0 or maximum <= 0 or recommended > maximum:
            raise ValueError("invalid_context_limits")
        verification = profile.get("verification")
        if verification is not None:
            if not isinstance(verification, dict) or verification.get("provider") != "kev":
                raise ValueError("invalid_verification_profile")
            if not isinstance(verification.get("model"), str) or not verification["model"].startswith("Kev-"):
                raise ValueError("invalid_kev_model_profile")
            if verification.get("execution_mode", "SWAP_MODE") not in {"DUAL_LOADED", "SWAP_MODE", "CPU_GPU_SPLIT"}:
                raise ValueError("invalid_model_pair_execution_mode")
