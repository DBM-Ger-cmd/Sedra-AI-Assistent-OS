"""How a model call spends tokens (Phase 8c). The window decides what MAY fit; this decides what a call SHOULD cost.

Measured on this PC's LM Studio (2026-10-01, same prompt, two models):

                                         qwen3.5-9b   gemma-4-12b
    provider default (thinking on)       1342 out     489 out      most of it hidden reasoning
    reasoning_effort = "none"              77 out      65 out      same answer length, no thinking
    reasoning_effort = "low"             1408 out     418 out      no reliable effect
    enable_thinking=false / "/no_think"   887 / 703   586 / 424    not reliable either

So the one lever that works on both is `reasoning_effort: "none"`. It is a per-role decision, because judging work (verify,
plan, code) may need the thinking. Whether answers get worse without it is NOT measured here; the policy only makes the choice
explicit and per role, and records what each call really cost.

  - plan():     reasoning effort and output budget for a call, and a refusal when the input alone leaves no room in the window.
  - escalate(): one bounded second try when the answer was cut off by the output limit (never a blind resend of the same request).
Nothing here calls a model, reads a file other than its config, or changes the window.
"""
from __future__ import annotations

from pathlib import Path

import yaml

EFFORTS = frozenset({"none", "low", "medium", "high"})
ROLE_DEFAULT = "__role__"


class TokenBudgetError(Exception):
    """`code` is a failure reason the supervisor classifies (context_overflow: reduce the context, do not resend)."""
    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


def _int(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"token_policy_invalid:{name}")
    return value


def _effort(value, name):
    if value is not None and value not in EFFORTS:
        raise ValueError(f"token_policy_invalid:{name}")
    return value


class TokenPolicyConfig:
    def __init__(self, raw):
        if not isinstance(raw, dict):
            raise ValueError("token_policy_invalid")
        self.enabled = raw.get("enabled", False)
        if not isinstance(self.enabled, bool):
            raise ValueError("token_policy_invalid:enabled")
        base = {"reasoning_effort": None, "reasoning_budget_tokens": None, "max_output_tokens": 1024, "output_cap": 4096}
        self.default = self._role(raw.get("default") or {}, base, "default")
        self.roles = {}
        for role, item in (raw.get("roles") or {}).items():
            if not isinstance(role, str) or not isinstance(item, dict):
                raise ValueError("token_policy_invalid:roles")
            self.roles[role] = self._role(item, self.default, f"roles.{role}")
        esc = raw.get("escalation") or {}
        self.max_escalations = _int(esc.get("max_retries", 1), "escalation.max_retries", 0, 3)
        factor = esc.get("factor", 2)
        if type(factor) not in (int, float) or isinstance(factor, bool) or not 1 < factor <= 8:
            raise ValueError("token_policy_invalid:escalation.factor")
        self.factor = float(factor)
        self.min_output_tokens = _int(raw.get("min_output_tokens", 128), "min_output_tokens", 1, 4096)

    @staticmethod
    def _role(item, base, name):
        unknown = set(item) - {"reasoning_effort", "reasoning_budget_tokens", "max_output_tokens", "output_cap"}
        if unknown:
            raise ValueError(f"token_policy_invalid:{name}:{sorted(unknown)}")
        out = dict(base)
        if "reasoning_effort" in item:
            out["reasoning_effort"] = _effort(item["reasoning_effort"], f"{name}.reasoning_effort")
        if "reasoning_budget_tokens" in item:
            value = item["reasoning_budget_tokens"]
            out["reasoning_budget_tokens"] = None if value is None else _int(value, f"{name}.reasoning_budget_tokens", 16, 65536)
        if "max_output_tokens" in item:
            out["max_output_tokens"] = _int(item["max_output_tokens"], f"{name}.max_output_tokens", 16, 131072)
        if "output_cap" in item:
            out["output_cap"] = _int(item["output_cap"], f"{name}.output_cap", 16, 131072)
        if out["max_output_tokens"] > out["output_cap"]:
            raise ValueError(f"token_policy_invalid:{name}:max_output_tokens_above_cap")
        return out

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            raise ValueError("token_policy_missing")
        return cls((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("token_policy") or {})


class TokenPolicy:
    def __init__(self, config):
        self.config = config

    @property
    def enabled(self):
        return self.config.enabled

    def for_role(self, role):
        return dict(self.config.roles.get(role) or self.config.default)

    def plan(self, role, input_tokens, window, *, reasoning_effort=ROLE_DEFAULT, max_output_tokens=None):
        """{"reasoning_effort", "max_tokens", "input_tokens", "window", "output_cap"}; raises TokenBudgetError when nothing fits."""
        if type(input_tokens) is not int or input_tokens < 0 or type(window) is not int or window <= 0:
            raise TokenBudgetError("validation_failure", "input_tokens_and_window_required")
        rule = self.for_role(role)
        room = window - input_tokens
        if room < self.config.min_output_tokens:
            # The input alone fills the window. Asking anyway only produces a cut-off answer; the context has to shrink first.
            raise TokenBudgetError("context_overflow", {"input_tokens": input_tokens, "window": window, "room": room})
        want = rule["max_output_tokens"] if max_output_tokens is None else max_output_tokens
        effort = rule["reasoning_effort"] if reasoning_effort == ROLE_DEFAULT else _effort(reasoning_effort, "reasoning_effort")
        cap = min(rule["output_cap"], room)
        budget = rule["reasoning_budget_tokens"] if effort != "none" else None          # nothing to cap when thinking is off
        return {"reasoning_effort": effort, "thinking_budget_tokens": budget, "max_tokens": max(self.config.min_output_tokens, min(want, cap)),
                "input_tokens": input_tokens, "window": window, "output_cap": cap}

    def escalate(self, plan, attempt_number):
        """A bigger output budget for ONE more try after a cut-off, or None (limit reached, or no room left)."""
        if attempt_number >= self.config.max_escalations:
            return None
        bigger = min(int(plan["max_tokens"] * self.config.factor), plan["output_cap"])
        if bigger <= plan["max_tokens"]:
            return None
        return dict(plan, max_tokens=bigger)
