from __future__ import annotations
from copy import deepcopy


class HardwareModelPass:
    """Validate a model runtime profile against the detected host hardware.

    The pass is deliberately conservative. It returns an effective runtime
    configuration and warnings; it never mutates or persists the source profile.
    """

    SAFE_CONTEXT_CAPS = {
        "cpu_small": 4096,
        "cpu_16plus": 8192,
        "cpu_32plus": 16384,
        "cpu_64plus": 32768,
        "nvidia_small": 8192,
        "nvidia_6_8": 16384,
        "nvidia_10_12": 32768,
        "nvidia_16plus": 65536,
        "nvidia_24plus": 131072,
        "apple_unified_small": 8192,
        "apple_unified_16plus": 16384,
        "apple_unified_32plus": 32768,
        "apple_unified_64plus": 65536,
    }

    def __init__(self, snapshot):
        self.snapshot = snapshot

    def evaluate(self, profile: dict, model_size_gb: float | None = None, verifier_size_gb: float | None = None) -> dict:
        if not isinstance(profile, dict):
            raise ValueError("profile_required")
        p = deepcopy(profile)
        warnings = []
        adjustments = []
        hw = self.snapshot
        hw_class = getattr(hw, "hardware_class", "unknown")

        # Resolve CPU thread auto setting while retaining headroom for GUPPI.
        threads = p.get("cpu_threads", "auto")
        if threads == "auto":
            total = max(1, int(getattr(hw, "cpu_threads", 1) or 1))
            resolved = total if total <= 4 else max(1, total - 2)
            p["cpu_threads"] = resolved
            adjustments.append({"field": "cpu_threads", "from": "auto", "to": resolved})
        else:
            p["cpu_threads"] = max(1, min(int(threads), int(getattr(hw, "cpu_threads", 1) or 1)))

        context = p.setdefault("context", {})
        requested_max = int(context.get("maximum", context.get("recommended", 4096)) or 4096)
        cap = self.SAFE_CONTEXT_CAPS.get(hw_class, 4096)
        effective_max = min(requested_max, cap)
        if effective_max != requested_max:
            adjustments.append({"field": "context.maximum", "from": requested_max, "to": effective_max})
            warnings.append("context_clamped_to_hardware_safe_cap")
        context["maximum"] = effective_max
        recommended = int(context.get("recommended", effective_max) or effective_max)
        context["recommended"] = min(recommended, effective_max)

        # No discrete/local GPU: force CPU execution and CPU KV cache.
        gpu_vendor = getattr(hw, "gpu_vendor", None)
        has_accelerator = bool(gpu_vendor) and gpu_vendor in {"NVIDIA", "Apple"}
        if not has_accelerator:
            old = p.get("gpu_layers", 0)
            if old != 0:
                adjustments.append({"field": "gpu_layers", "from": old, "to": 0})
            p["gpu_layers"] = 0
            kv = p.setdefault("kv_cache", {})
            if kv.get("placement") not in {None, "cpu"}:
                adjustments.append({"field": "kv_cache.placement", "from": kv.get("placement"), "to": "cpu"})
            kv["placement"] = "cpu"

        reserve = float(p.get("memory_reserve_gb", 3) or 3)
        ram = getattr(hw, "ram_gb", None)
        vram = getattr(hw, "vram_gb", None)
        fit = "unknown"
        gpu_fit = "unknown"
        if model_size_gb is not None and ram is not None:
            # Conservative overhead for runtime buffers and metadata. KV cache is
            # handled indirectly by the context cap rather than pretending to know
            # exact architecture-dependent memory consumption.
            need = float(model_size_gb) * 1.20 + reserve
            fit = bool(need <= float(ram))
            if not fit:
                warnings.append("model_may_not_fit_system_memory")
        if model_size_gb is not None and vram is not None and gpu_vendor == "NVIDIA":
            gpu_fit = bool(float(model_size_gb) * 1.15 <= float(vram) * 0.90)
            if not gpu_fit and p.get("gpu_layers") in {"all", 999, 9999}:
                warnings.append("full_gpu_offload_not_recommended")

        verification = p.get("verification") if isinstance(p.get("verification"), dict) else {}
        execution_mode = verification.get("execution_mode", "SWAP_MODE")
        if execution_mode not in {"DUAL_LOADED", "SWAP_MODE", "CPU_GPU_SPLIT"}:
            warnings.append("unknown_execution_mode")
            execution_mode = "SWAP_MODE"
            verification["execution_mode"] = execution_mode
            p["verification"] = verification
        pair_fit = "unknown"
        pair_need = None
        if model_size_gb is not None and verifier_size_gb is not None and ram is not None:
            primary = float(model_size_gb) * 1.20
            verifier = float(verifier_size_gb) * 1.20
            pair_need = (primary + verifier if execution_mode == "DUAL_LOADED" else max(primary, verifier)) + reserve
            pair_fit = bool(pair_need <= float(ram))
            if not pair_fit: warnings.append("model_pair_may_not_fit_system_memory")
        incompatible = fit is False or pair_fit is False
        if incompatible:
            match_level, preset_status = "INCOMPATIBLE", "REJECTED"
        elif warnings:
            match_level, preset_status = "DEGRADED", "ADAPTED"
        elif adjustments:
            match_level, preset_status = "COMPATIBLE", "ADAPTED"
        else:
            match_level, preset_status = "OPTIMAL", "VALIDATED"
        return {
            "hardware_class": hw_class,
            "source_profile": profile,
            "effective_profile": p,
            "adjustments": adjustments,
            "warnings": warnings,
            "fit": {
                "system_memory": fit,
                "full_gpu": gpu_fit,
                "pair_system_memory": pair_fit,
                "pair_memory_need_gb": pair_need,
                "model_size_gb": model_size_gb,
                "verifier_size_gb": verifier_size_gb,
                "ram_gb": ram,
                "vram_gb": vram,
                "memory_reserve_gb": reserve,
            },
            "context_limits": {
                "model_maximum": context.get("model_maximum"),
                "safe_maximum": cap,
                "recommended": context["recommended"],
                "effective_maximum": context["maximum"],
            },
            "execution_mode": execution_mode,
            "match_level": match_level,
            "preset_status": preset_status,
            "status": "REVIEW" if incompatible else "PASS",
        }
