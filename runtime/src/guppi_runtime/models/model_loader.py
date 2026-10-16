"""Make the context window GUPPI resolved the one the provider really uses (Phase 8a).

Measured on a real LM Studio (2026-10-01): the chat API has no context parameter, so a model that is loaded lazily gets
LM Studio's own default (qwen: 9.8 GiB instead of 8.3 GiB at 8192). `lms load` a second time with another context does
not replace the first instance, it adds `<key>:2`; requests for `<key>` keep going to the OLD instance, and both together
filled the 12 GB card. So loading must be explicit, and an existing instance with the wrong context must be unloaded first.

This module only plans and checks. It talks to LM Studio through the existing controller (`lms` CLI, no network, no
download) and never decides which model to use (the role router does) or whether there is room (the scheduler does).
It is off by default and only called by the supervisor after a reservation was granted.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from ..models.runtime_control import RuntimeControlError

GPU_ALL = {"max", "all", "99", "100"}


class LoadError(Exception):
    """`code` is a failure-class reason code the supervisor already understands."""
    def __init__(self, code, reason=None):
        super().__init__(f"{code}:{reason}" if reason else code)
        self.code = code
        self.reason = reason


class LoaderConfig:
    def __init__(self, raw):
        if not isinstance(raw, dict):
            raise ValueError("loader_config_invalid")
        self.enabled = raw.get("enabled", False)
        if not isinstance(self.enabled, bool):
            raise ValueError("loader_config_invalid:enabled")
        self.on_context_mismatch = raw.get("on_context_mismatch", "reload")
        if self.on_context_mismatch not in {"reload", "refuse"}:
            raise ValueError("loader_config_invalid:on_context_mismatch")
        self.evict_idle_models = raw.get("evict_idle_models", False)
        if not isinstance(self.evict_idle_models, bool):
            raise ValueError("loader_config_invalid:evict_idle_models")
        parallel = raw.get("parallel", 1)
        if type(parallel) is not int or not 1 <= parallel <= 8:
            raise ValueError("loader_config_invalid:parallel")
        self.parallel = parallel
        self.mtp = raw.get("mtp", False)
        if not isinstance(self.mtp, bool):
            raise ValueError("loader_config_invalid:mtp")
        self.check_estimate = raw.get("check_estimate", False)
        if not isinstance(self.check_estimate, bool):
            raise ValueError("loader_config_invalid:check_estimate")
        slack = raw.get("estimate_slack_gb", 0.5)
        if type(slack) not in (int, float) or isinstance(slack, bool) or not 0 <= slack <= 16:
            raise ValueError("loader_config_invalid:estimate_slack_gb")
        self.estimate_slack_gb = float(slack)

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            raise ValueError("loader_config_missing")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(data.get("model_loader") or {})


def gpu_argument(gpu_layers):
    """Recipe `gpu_layers` -> `lms --gpu`. Anything unclear is left to LM Studio (None) instead of guessed."""
    if gpu_layers is None:
        return None
    text = str(gpu_layers).strip().lower()
    if text in GPU_ALL:
        return "max"
    if text in {"0", "off"}:
        return "off"
    return None


_ESTIMATE = re.compile(r"Estimated GPU Memory:\s*([0-9]+(?:[.,][0-9]+)?)\s*(GiB|MiB|GB|MB)", re.I)


def parse_estimate_gib(text):
    """GPU memory LM Studio says the load would need, in GiB, or None. Never a guess."""
    match = _ESTIMATE.search(text or "")
    if not match:
        return None
    value = float(match.group(1).replace(",", "."))
    unit = match.group(2).lower()
    return value / 1024 if unit in {"mib", "mb"} else value


class ModelLoader:
    def __init__(self, config, controller, audit=None, controllers=None):
        """`controller` is the default provider's controller; `controllers` maps a provider id (the recipe's `provider`, which
        arrives as `resolution["provider_ref"]`) to its controller. Both expose loaded_models / load_model / unload_model."""
        self.config = config
        self.controller = controller
        self.controllers = dict(controllers or {})
        self.audit = audit

    def _ctl(self, resolution):
        return self.controllers.get((resolution or {}).get("provider_ref"), self.controller)

    def _all_controllers(self):
        seen, out = set(), []
        for ctl in [self.controller, *self.controllers.values()]:
            if id(ctl) not in seen:
                seen.add(id(ctl)); out.append(ctl)
        return out

    @property
    def enabled(self):
        return self.config.enabled

    def _audit(self, event, **payload):
        if self.audit:
            self.audit.append(event, component="model-loader", payload=payload)

    def _instances(self, key, ctl=None):
        """Loaded instances of exactly this model key: `<key>`, `<key>:2`, ..."""
        out = []
        for item in (ctl or self.controller).loaded_models() or []:
            ident = item.get("identifier") or item.get("modelKey")
            if item.get("modelKey") == key or ident == key or (isinstance(ident, str) and re.fullmatch(re.escape(key) + r":\d+", ident)):
                out.append({"identifier": ident, "context": item.get("contextLength")})
        return out

    def _validate(self, resolution):
        key, want = resolution.get("model"), resolution.get("context_window")
        if not isinstance(key, str) or not key or type(want) is not int or want <= 0:
            raise LoadError("provider_unavailable", "resolution_has_no_model_or_context")
        return key, want

    def _list(self, key, ctl=None):
        try:
            return self._instances(key, ctl)
        except (RuntimeControlError, ValueError, OSError) as exc:
            raise LoadError("provider_unavailable", f"cannot_list_loaded_models:{type(exc).__name__}") from exc

    @staticmethod
    def _reusable(instances, key, want):
        """Reuse only when exactly one instance exists, it has the wanted window and it is the one requests for `<key>` reach."""
        return len(instances) == 1 and instances[0]["context"] == want and instances[0]["identifier"] == key

    def evict_idle(self, in_use):
        """Unload every loaded model that no running attempt uses, so a model that does not fit next to it can start.
        Off unless `evict_idle_models` is set: a model the Captain loaded for their own chat is 'idle' too."""
        if not self.config.enabled or not self.config.evict_idle_models:
            return []
        busy = set(in_use or ())
        done = []
        for ctl in self._all_controllers():                # one card, several providers: idle models of every provider give room
            try:
                items = ctl.loaded_models() or []
            except (RuntimeControlError, ValueError, OSError):
                continue
            for item in items:
                key, ident = item.get("modelKey"), item.get("identifier") or item.get("modelKey")
                if key in busy or ident in busy or not ident:
                    continue
                try:
                    ctl.unload_model(ident)
                    done.append(ident)
                except (RuntimeControlError, ValueError, OSError):
                    continue                               # one that stays loaded only makes the next check say "no room"
        if done:
            self._audit("MODEL_IDLE_EVICTED", identifiers=done, kept=sorted(busy))
        return done

    def loaded(self, key):
        """Is any instance of this model loaded? Advisory (role resolution); a listing failure says 'no', the binding steps re-check."""
        for ctl in self._all_controllers():
            try:
                if self._instances(key, ctl):
                    return True
            except (RuntimeControlError, ValueError, OSError):
                continue
        return False

    def resident_vram_gb(self, resolution):
        """VRAM an already loaded, reusable instance holds (the job will use it as it is). Its real size is not reported by
        LM Studio, so the resolved estimate stands in; 0 when nothing would be reused."""
        if not self.config.enabled:
            return 0.0
        try:
            key, want = self._validate(resolution)
            if not self._reusable(self._instances(key, self._ctl(resolution)), key, want):
                return 0.0
        except (LoadError, RuntimeControlError, ValueError, OSError):
            return 0.0
        return float((resolution.get("estimated_resources") or {}).get("vram_gb") or 0.0)

    def clear_stale(self, resolution):
        """Step 1, BEFORE the reservation: the VRAM a stale instance of this very model holds would otherwise be measured as
        'not free' and the start refused for room that is about to be given back. Only instances of THIS model are touched,
        and only when the job needs this model with another window anyway."""
        if not self.config.enabled:
            return []
        key, want = self._validate(resolution)
        ctl = self._ctl(resolution)
        instances = self._list(key, ctl)
        if not instances or self._reusable(instances, key, want):
            return []
        if self.config.on_context_mismatch == "refuse":
            raise LoadError("provider_unavailable", f"loaded_with_other_context:{instances[0]['context']}")
        done = []
        for item in instances:
            try:
                ctl.unload_model(item["identifier"])
            except (RuntimeControlError, ValueError, OSError) as exc:
                raise LoadError("provider_unavailable", f"unload_failed:{type(exc).__name__}") from exc
            done.append(item["identifier"])
        self._audit("MODEL_STALE_UNLOADED", model=key, wanted_context=want, identifiers=done)
        return done

    def ensure(self, resolution):
        """Return {"identifier", "context_length", "action", "estimate_gib"} or raise LoadError. Idempotent."""
        if not self.config.enabled:
            raise LoadError("provider_unavailable", "model_loader_disabled")
        key, want = self._validate(resolution)
        profile = resolution.get("load_profile") or {}
        ctl = self._ctl(resolution)
        instances = self._list(key, ctl)
        exact = [i for i in instances if i["context"] == want]
        wrong = [i for i in instances if i["context"] != want]
        if self._reusable(instances, key, want):
            self._audit("MODEL_LOAD_REUSED", model=key, context_length=want)
            return {"identifier": key, "context_length": want, "action": "reused", "estimate_gib": None}
        if wrong and self.config.on_context_mismatch == "refuse":
            raise LoadError("provider_unavailable", f"loaded_with_other_context:{wrong[0]['context']}")
        estimate = None
        if self.config.check_estimate:
            estimate = self._estimate(key, want, profile, ctl)
            need = (resolution.get("estimated_resources") or {}).get("vram_gb")
            if estimate is not None and need is not None and estimate > need + self.config.estimate_slack_gb:
                # What was reserved is smaller than what LM Studio itself says the load needs. Do not start it.
                raise LoadError("hardware_pressure", f"estimate_{estimate:.2f}_gib_exceeds_reservation_{need:.2f}")
        for item in exact + wrong:               # unload stale or duplicate instances of THIS model only
            try:
                ctl.unload_model(item["identifier"])
            except (RuntimeControlError, ValueError, OSError) as exc:
                raise LoadError("provider_unavailable", f"unload_failed:{type(exc).__name__}") from exc
        extra = {"server": profile["server"]} if profile.get("server") else {}       # a managed server needs to know the model file etc.
        try:
            ctl.load_model(key, context_length=want, gpu=gpu_argument(profile.get("gpu_layers")), identifier=key, yes=True,
                           parallel=self.config.parallel, mtp=self.config.mtp, **extra)
        except (RuntimeControlError, ValueError, OSError) as exc:
            detail = str(exc)[:160] if isinstance(exc, RuntimeControlError) else type(exc).__name__
            raise LoadError("provider_unavailable", f"load_failed:{detail}") from exc
        after = [i for i in self._instances(key, ctl) if i["identifier"] == key]
        if not after or after[0]["context"] != want:
            # LM Studio accepted the command but is not serving what was asked for. Better a failed start than a wrong window.
            for item in self._instances(key, ctl):
                try:
                    ctl.unload_model(item["identifier"])
                except Exception:
                    pass
            raise LoadError("provider_unavailable", f"context_not_applied:{after[0]['context'] if after else None}")
        action = "reloaded" if wrong else "loaded"
        self._audit("MODEL_LOADED", model=key, context_length=want, action=action, estimate_gib=estimate)
        return {"identifier": key, "context_length": want, "action": action, "estimate_gib": estimate}

    def _estimate(self, key, want, profile, ctl=None):
        try:
            out = (ctl or self.controller).load_model(key, context_length=want, gpu=gpu_argument(profile.get("gpu_layers")), estimate_only=True)
        except (RuntimeControlError, ValueError, OSError):
            return None                                   # no estimate is not a veto
        return parse_estimate_gib((out or {}).get("output"))

    def unload(self, resolution):
        """Free what `ensure` loaded. Separate and explicit: the supervisor decides when an attempt is over."""
        key = resolution.get("model")
        ctl = self._ctl(resolution)
        done = []
        for item in self._instances(key, ctl):
            ctl.unload_model(item["identifier"])
            done.append(item["identifier"])
        if done:
            self._audit("MODEL_UNLOADED", model=key, identifiers=done)
        return done
