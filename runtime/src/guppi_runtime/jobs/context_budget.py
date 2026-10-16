"""Local-first context budgeting for small and medium model operation."""
from __future__ import annotations
from copy import deepcopy


class ContextBudgetManager:
    DEFAULT_WATERMARKS = {"green": 0.55, "yellow": 0.70, "orange": 0.85}
    # Smallest window from which EVERY larger window builds a default budget. Measured, not derived: the split is not
    # monotonic just above the floor (3133 builds, 3134-3137, 3139 and 3144 do not), so the true floor is 3145.
    # tests/test_role_routing.py checks the whole range.
    MIN_CONTEXT_WINDOW = 3145

    def __init__(self, watermarks=None):
        self.watermarks = dict(self.DEFAULT_WATERMARKS)
        if watermarks:
            self.watermarks.update(watermarks)
        values = [self.watermarks[k] for k in ("green", "yellow", "orange")]
        if not all(isinstance(x, (int, float)) for x in values) or not (0 < values[0] < values[1] < values[2] < 1):
            raise ValueError("invalid_context_watermarks")

    def build_budget(self, context_window, *, reserved_output_tokens=None, reserved_reasoning_tokens=0,
                     system_budget=None, project_context_budget=None, task_context_budget=None,
                     tool_result_budget=None, recent_history_budget=None, safety_margin=None):
        window = int(context_window)
        if window < 1024:
            raise ValueError("context_window_too_small")
        defaults_only = all(v is None for v in (reserved_output_tokens, system_budget, project_context_budget, task_context_budget,
                                                tool_result_budget, recent_history_budget, safety_margin)) and not reserved_reasoning_tokens
        if defaults_only and window < self.MIN_CONTEXT_WINDOW:
            # Below this the fixed floors of the default split cannot fit; say so once, plainly (finding F-9).
            raise ValueError("context_window_too_small")
        reserved_output_tokens = int(reserved_output_tokens if reserved_output_tokens is not None else max(512, min(8192, window // 8)))
        safety_margin = int(safety_margin if safety_margin is not None else max(512, min(8192, window // 10)))
        reserved_reasoning_tokens = int(reserved_reasoning_tokens or 0)
        available = window - reserved_output_tokens - safety_margin - reserved_reasoning_tokens
        if available <= 0:
            raise ValueError("context_reservations_exceed_window")
        defaults = {
            "system_budget": max(256, int(available * 0.12)),
            "project_context_budget": max(256, int(available * 0.20)),
            "task_context_budget": max(256, int(available * 0.42)),
            "tool_result_budget": max(256, int(available * 0.16)),
            "recent_history_budget": max(128, int(available * 0.10)),
        }
        overrides = {
            "system_budget": system_budget,
            "project_context_budget": project_context_budget,
            "task_context_budget": task_context_budget,
            "tool_result_budget": tool_result_budget,
            "recent_history_budget": recent_history_budget,
        }
        for key, value in overrides.items():
            if value is not None:
                defaults[key] = int(value)
        if any(v < 0 for v in defaults.values()) or sum(defaults.values()) > available:
            raise ValueError("context_subbudgets_exceed_available_tokens")
        return {
            "schema": 1,
            "context_window": window,
            "max_input_tokens": window - reserved_output_tokens,
            "reserved_output_tokens": reserved_output_tokens,
            "reserved_reasoning_tokens": reserved_reasoning_tokens,
            "safety_margin": safety_margin,
            **defaults,
            "watermarks": deepcopy(self.watermarks),
        }

    def health(self, used_tokens, budget):
        maximum = int(budget.get("max_input_tokens", 0) or 0)
        used = max(0, int(used_tokens))
        if maximum <= 0:
            raise ValueError("invalid_context_budget")
        ratio = used / maximum
        if ratio < self.watermarks["green"]:
            state, actions = "GREEN", []
        elif ratio < self.watermarks["yellow"]:
            state, actions = "YELLOW", ["trim_tool_outputs", "avoid_irrelevant_history"]
        elif ratio < self.watermarks["orange"]:
            state, actions = "ORANGE", ["checkpoint", "compact_completed_work", "artifact_offload"]
        else:
            state, actions = "RED", ["checkpoint", "context_rebuild", "fresh_task_context", "block_large_tool_dump"]
        return {"state": state, "used_tokens": used, "max_input_tokens": maximum, "fill_ratio": ratio, "actions": actions}
