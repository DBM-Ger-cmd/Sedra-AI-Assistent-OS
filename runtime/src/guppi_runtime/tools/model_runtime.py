from __future__ import annotations
from .base import BaseTool, ToolValidationError


class ModelRuntimeTool(BaseTool):
    id = "model-runtime"
    version = "0.2.0"
    supported_operations = {
        "status", "scan", "list_models", "hardware_pass", "provider_models", "loaded_models",
        "benchmark_list", "known_good_list", "tuning_plan", "tuning_list", "tuning_run", "benchmark", "promote_known_good", "runtime_action",
    }

    READ_OPS = {"status", "scan", "list_models", "hardware_pass", "provider_models", "loaded_models", "benchmark_list", "known_good_list", "tuning_plan", "tuning_list"}

    def __init__(self, root, manager, guard=None, audit=None):
        super().__init__(root, guard, audit)
        self.manager = manager

    def health(self):
        return True

    def execute(self, mission_id, operation, args=None, approval_token=None):
        args = args or {}
        if operation not in self.supported_operations:
            raise ToolValidationError("unsupported_model_runtime_operation")
        if operation in self.READ_OPS:
            return self._read(operation, args)
        if operation == "tuning_run":
            plan = self.manager.tuning.validate(args.get("plan"))
            target = "tuning:" + plan["plan_digest"]
            auth = self._guarded(mission_id, "model_runtime_control", target, approval_token, ["Runs up to %s local benchmark candidates; no automatic promotion" % len(plan["candidates"])],request_binding={"operation":operation,"args":args})
            if auth: return auth
            try:
                return {"status": "completed", "tuning": self.manager.tuning.run(plan)}
            except Exception as exc:
                self._audit("EXECUTION_FAILED", mission_id, {"operation": "tuning_run", "error": str(exc)})
                return {"status": "failed", "error": f"{type(exc).__name__}:{exc}"}
        if operation == "benchmark":
            managed = bool(args.get("managed_start", False))
            if managed:
                target = f"benchmark:{args.get('provider')}:{args.get('model_id') or args.get('model') or 'runtime'}"
                auth = self._guarded(mission_id, "model_runtime_control", target, approval_token, ["Starts a local model runtime for benchmark execution"],request_binding={"operation":operation,"args":args})
                if auth: return auth
            try:
                if managed:
                    result = self.manager.benchmark.benchmark_managed_llamacpp(
                        model_id=args.get("model_id"), profile_id=args.get("profile_id"), prompt=args.get("prompt") or None,
                        repeats=args.get("repeats",3), warmups=args.get("warmups",1), max_tokens=args.get("max_tokens",128),
                        port=args.get("port",18080), keep_running=bool(args.get("keep_running",False)))
                else:
                    kw = dict(model=args.get("model"), model_id=args.get("model_id"), profile_id=args.get("profile_id"), repeats=args.get("repeats",3), warmups=args.get("warmups",1), max_tokens=args.get("max_tokens",128))
                    if args.get("prompt") is not None: kw["prompt"] = args.get("prompt")
                    result = self.manager.benchmark.benchmark_active(args.get("provider"), **kw)
                return {"status":"completed","benchmark":result}
            except Exception as exc:
                self._audit("EXECUTION_FAILED", mission_id, {"operation":"benchmark","error":str(exc)})
                return {"status":"failed","error":f"{type(exc).__name__}:{exc}"}
        if operation == "promote_known_good":
            target = f"known-good:{args.get('benchmark_id')}"
            auth = self._guarded(mission_id, "model_profile_promote", target, approval_token, ["Changes automatic model/runtime profile selection for matching hardware"],request_binding={"operation":operation,"args":args})
            if auth: return auth
            try:
                result = self.manager.benchmark.promote_known_good(args.get("benchmark_id"), args.get("profile_id"))
                return {"status":"completed","known_good":result}
            except Exception as exc:
                return {"status":"failed","error":f"{type(exc).__name__}:{exc}"}

        provider = str(args.get("provider") or "")
        action = str(args.get("action") or "")
        params = args.get("params") or {}
        discriminator = params.get("model_id") or params.get("model_key") or params.get("source_path") or "runtime"
        target = f"{provider}:{action}:{discriminator}"
        auth = self._guarded(mission_id, "model_runtime_control", target, approval_token, ["Starts/stops or changes a local model runtime"],request_binding={"operation":operation,"args":args})
        if auth: return auth
        try:
            result = self.manager.runtime_action(provider, action, params)
            self._audit("EXECUTION_COMPLETED", mission_id, {"operation": operation, "provider": provider, "action": action})
            return {"status": "completed", "provider": provider, "action": action, "result": result}
        except Exception as exc:
            self._audit("EXECUTION_FAILED", mission_id, {"operation": operation, "provider": provider, "action": action, "error": str(exc)})
            return {"status": "failed", "error": f"{type(exc).__name__}:{exc}"}

    def _guarded(self, mission_id, action, target, approval_token, risks, request_binding=None):
        verdict = self.guard.evaluate(action, mission_id=mission_id, target=target)
        if verdict["decision"] == "BLOCK":
            return {"status":"blocked","guard":verdict}
        if verdict["decision"] == "CAPTAIN_REQUIRED":
            auth = self.guard.authorize(approval_token, mission_id=mission_id, action=action, target=target,request_binding=request_binding)
            if not auth["authorized"]:
                gate = self.guard.create_gate(mission_id, action, target, risks=risks, rollback_available=True,request_binding=request_binding)
                return {"status":"captain_required","guard":verdict,"gate":gate}
        return None

    def _read(self, operation, args):
        if operation == "tuning_plan": return {"status": "completed", "plan": self.manager.tuning.plan(**args)}
        if operation == "tuning_list": return {"status": "completed", "runs": self.manager.tuning.history()}
        if operation == "status": return {"status": "completed", "runtime": self.manager.status()}
        if operation == "scan": return {"status": "completed", "models": self.manager.scan_portable()}
        if operation == "list_models": return {"status": "completed", "models": self.manager.model_list()}
        if operation == "hardware_pass": return {"status": "completed", "profile_pass": self.manager.profile_for(args.get("profile_id"), args.get("model_size_gb"), model_id=args.get("model_id"), runtime=args.get("runtime"))}
        if operation == "provider_models": return {"status": "completed", "models": self.manager.provider_models(args.get("provider"))}
        if operation == "loaded_models": return {"status": "completed", "models": self.manager.loaded_models(args.get("provider"))}
        if operation == "benchmark_list": return {"status":"completed","benchmarks":self.manager.benchmark.store.list()}
        if operation == "known_good_list": return {"status":"completed","profiles":self.manager.profile_store.known_good_records()}
        raise ToolValidationError("unsupported_model_runtime_read_operation")
