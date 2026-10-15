from __future__ import annotations
from pathlib import Path
import shutil, yaml
from ..model_catalog import ModelCatalog
from ..hardware_pass import HardwareModelPass
from ..models.runtime_control import LMStudioRuntimeController, LlamaCppRuntimeController
from ..benchmark import ModelBenchmarkRunner
from ..tuning import TuningManager


class ModelRuntimeManager:
    def __init__(self, config_path: Path, data_root: Path, portable_root: Path, hardware, profile_store, audit=None, runner=None):
        self.config_path = Path(config_path)
        self.data_root = Path(data_root)
        self.portable_root = Path(portable_root).resolve()
        self.hardware = hardware
        self.profile_store = profile_store
        self.audit = audit
        cfg = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) if self.config_path.exists() else {}
        cfg = cfg or {}
        runtimes = cfg.get("model_runtimes", {})
        portable_cfg = cfg.get("portable", {})
        model_dir = self.portable_root / portable_cfg.get("models_dir", "models")
        model_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = ModelCatalog(self.data_root / "models" / "catalog.json", [model_dir])
        self.hardware_pass = HardwareModelPass(hardware)

        lm = runtimes.get("lm-studio", {})
        lc = runtimes.get("llama-cpp-server", {})
        self.controllers = {}
        if lm.get("enabled", True):
            self.controllers["lm-studio"] = LMStudioRuntimeController(lm.get("executable"), runner=runner, endpoint=lm.get("endpoint", "http://127.0.0.1:1234"), enabled=True)
        if lc.get("enabled", True):
            self.controllers["llama-cpp-server"] = LlamaCppRuntimeController(lc.get("executable"), runner=runner, endpoint=lc.get("endpoint", "http://127.0.0.1:8080"))
        self.config = cfg
        self.benchmark = ModelBenchmarkRunner(self, hardware, profile_store, self.data_root, audit, self.config_path.parent / "benchmark_policy.yaml")

        self.tuning = TuningManager(self)

    @property
    def portable_models_dir(self):
        return self.catalog.allowed_roots[0]

    def status(self):
        return {
            "portable_root": str(self.portable_root),
            "portable_models_dir": str(self.portable_models_dir),
            "providers": {pid: ctl.status() for pid, ctl in self.controllers.items()},
            "catalog_count": len(self.catalog.list()),
        }

    def scan_portable(self):
        found = self.catalog.scan(self.portable_models_dir)
        self.catalog.prune_missing()
        if self.audit:
            self.audit.append("MODEL_CATALOG_SCANNED", component="model-runtime", payload={"count": len(found)})
        return found

    def model_list(self):
        return self.catalog.list()

    def profile_for(self, profile_id=None, model_size_gb=None, *, model_id=None, runtime=None, verifier_size_gb=None):
        if profile_id:
            profile = self.profile_store.all().get(profile_id)
            if not profile: raise KeyError("unknown_profile_id")
        else:
            profile = self.profile_store.select_for_hardware(self.hardware.hardware_class, hardware_fingerprint=self.hardware.fingerprint(), model_id=model_id, runtime=runtime)
        hw=getattr(self,"hardware_manager",None)
        if hw: profile=hw.constrain_runtime_profile(profile)
        return self.hardware_pass.evaluate(profile, model_size_gb=model_size_gb, verifier_size_gb=verifier_size_gb)

    def controller(self, provider):
        ctl = self.controllers.get(provider)
        if not ctl: raise KeyError("unknown_model_runtime_provider")
        return ctl

    def provider_models(self, provider):
        ctl = self.controller(provider)
        if provider == "lm-studio":
            return ctl.list_models()
        return self.model_list()

    def loaded_models(self, provider):
        ctl = self.controller(provider)
        if provider == "lm-studio": return ctl.loaded_models()
        return []

    def import_model(self, source_path, filename=None):
        src = Path(source_path).resolve()
        if not src.exists() or not src.is_file() or src.suffix.lower() != ".gguf":
            raise ValueError("valid_gguf_source_required")
        name = filename or src.name
        if Path(name).name != name or not name.lower().endswith(".gguf"):
            raise ValueError("invalid_portable_model_filename")
        dst = (self.portable_models_dir / name).resolve()
        dst.relative_to(self.portable_models_dir)
        if dst.exists():
            raise FileExistsError("portable_model_already_exists")
        shutil.copy2(src, dst)
        return self.catalog.register(dst)

    def remove_model(self, model_id):
        rec = self.catalog.get(model_id)
        path = Path(rec["path"]).resolve()
        path.relative_to(self.portable_models_dir)
        if path.exists():
            path.unlink()
        self.catalog.prune_missing()
        return {"removed": True, "model_id": model_id, "path": str(path)}

    def runtime_action(self, provider, action, args=None):
        args = args or {}
        if provider == "portable":
            if action == "import_model": return self.import_model(args.get("source_path"), args.get("filename"))
            if action == "remove_model": return self.remove_model(args.get("model_id"))
            raise ValueError("unsupported_portable_action")
        ctl = self.controller(provider)
        hw=getattr(self,"hardware_manager",None)
        if hw and action in {"load_model", "start_server", "server_start"}: hw.preflight()
        if provider == "lm-studio":
            mapping = {
                "daemon_up": lambda: ctl.daemon_up(),
                "daemon_down": lambda: ctl.daemon_down(),
                "server_start": lambda: ctl.server_start(args.get("port", 1234)),
                "server_stop": lambda: ctl.server_stop(),
                "load_model": lambda: ctl.load_model(args.get("model_key"), context_length=args.get("context_length"), gpu=args.get("gpu"), identifier=args.get("identifier"), estimate_only=bool(args.get("estimate_only", False))),
                "unload_model": lambda: ctl.unload_model(args.get("model_key"), all_models=bool(args.get("all", False))),
            }
            if action not in mapping: raise ValueError("unsupported_lmstudio_action")
            return mapping[action]()
        if provider == "llama-cpp-server":
            if action in {"prepare_start", "start_server"}:
                model_id = args.get("model_id")
                rec = self.catalog.get(model_id)
                pass_result = self.profile_for(args.get("profile_id"), rec.get("size_gb"), model_id=rec.get("id"), runtime=provider)
                if pass_result["status"] == "REVIEW" and not bool(args.get("force", False)):
                    raise RuntimeError("hardware_model_pass_requires_review")
                if action == "prepare_start":
                    command = ctl.build_start_command(Path(rec["path"]), pass_result["effective_profile"], port=args.get("port", 8080))
                    return {"command": command, "profile_pass": pass_result, "model": rec}
                log_path = self.data_root / "models" / "logs" / f"{model_id}.log"
                result = ctl.start_server(Path(rec["path"]), pass_result["effective_profile"], port=args.get("port", 8080), log_path=log_path)
                return {**result, "profile_pass": pass_result, "model": rec}
            if action == "stop_server":
                return ctl.stop_server()
            raise ValueError("unsupported_llamacpp_action")
        raise ValueError("unsupported_provider")
