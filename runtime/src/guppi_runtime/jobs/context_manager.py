"""GUPPI Context Manager, v1 (Phase 3): measure, budget, offload, checkpoint, react to watermarks.

Contract: docs/CONTEXT_MANAGER_CONTRACTS.md. Context is a resource like RAM or VRAM; the goal is the
smallest sufficient context, never the smallest context. This module
 - reuses `ContextBudgetManager` (the only budget formula),
 - never changes job state, picks a model, or loosens a policy,
 - keeps critical facts as structured records (pins), never only in prose,
 - does nothing unless `context_manager.enabled` is true in config/job_supervisor.yaml.
Child isolation, fresh-context assembly and repair belong to Phase 4.
"""
from __future__ import annotations

import json
import math
import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ..context_budget import ContextBudgetManager
from ..development_contracts import canonical_digest
from ..util import append_lock, atomic_write_json, load_json, sha256_bytes, utcnow

SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
STATES = ("GREEN", "YELLOW", "ORANGE", "RED")
LAYERS = ("L0", "L1", "L2", "L3", "L4", "L5")
PIN_KINDS = frozenset({"policy_hash", "approval", "test_result", "code_change", "hash", "path", "security_decision", "constraint"})
PIN_REF_KEYS = ("evidence_id", "gate_id", "token_id", "path", "artifact_id", "job_id")
# Share of the inline limit that stays acceptable per watermark state (YELLOW: halve, ORANGE: quarter, RED: eighth).
INLINE_FACTOR = {"GREEN": 1.0, "YELLOW": 0.5, "ORANGE": 0.25, "RED": 0.125}
KNOWN_ACTIONS = frozenset({"trim_tool_outputs", "avoid_irrelevant_history", "checkpoint", "compact_completed_work",
                           "artifact_offload", "context_rebuild", "fresh_task_context", "block_large_tool_dump"})


class ContextError(Exception):
    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


def _safe_id(value, name):
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ContextError(f"invalid_{name}")
    return value


# --------------------------------------------------------------------------- configuration

class ContextConfig:
    def __init__(self, raw):
        if not isinstance(raw, dict):
            raise ValueError("context_config_invalid")
        self.enabled = raw.get("enabled", False)
        if not isinstance(self.enabled, bool):
            raise ValueError("context_config_invalid:enabled")
        self.default_window = self._int(raw, "default_context_window", 8192, 1024, 10_000_000)
        marks = raw.get("watermarks") or {}
        self.watermarks = {"green": 0.55, "yellow": 0.70, "orange": 0.85}
        self.watermarks.update(marks)
        ContextBudgetManager(self.watermarks)       # reuses the existing validation (ascending, 0 < x < 1)
        est = raw.get("estimator") or {}
        self.code_cpt = self._num(est, "code_chars_per_token", 3.0, 0.5, 20)
        self.prose_cpt = self._num(est, "prose_chars_per_token", 3.5, 0.5, 20)
        self.safety_factor = self._num(est, "safety_factor", 1.15, 1.0, 5.0)
        self.calibrate_after = self._int(est, "calibrate_after", 20, 1, 100000)
        self.inline_max_tokens = self._int(raw, "tool_output_inline_max_tokens", 1500, 16, 1_000_000)
        self.max_offload_bytes = self._int(raw, "max_offload_bytes", 64 * 1024 * 1024, 1024, 2 ** 34)
        self.artifact_read_max_bytes = self._int(raw, "artifact_read_max_bytes", 65536, 1, 16 * 1024 * 1024)
        self.checkpoint_max_tokens = self._int(raw, "checkpoint_max_tokens", 3000, 200, 100000)
        self.stale_after_s = self._int(raw, "stale_after_s", 3600, 1, 10 ** 8)
        repair = raw.get("repair") or {}
        self.repair_max = self._int(repair, "max_per_job", 2, 0, 20)
        self.repair_repeat_threshold = self._int(repair, "repeat_threshold", 3, 2, 100)
        weights = raw.get("relevance_weights") or {}
        defaults = {"task": 3, "file": 3, "decision": 2, "safety": 4, "pinned": 4, "recency": 1, "done_penalty": 2}
        self.weights = {k: self._num(weights, k, v, 0, 1000) for k, v in defaults.items()}

    @staticmethod
    def _int(section, key, default, low, high):
        value = section.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"context_config_invalid:{key}")
        return value

    @staticmethod
    def _num(section, key, default, low, high):
        value = section.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
            raise ValueError(f"context_config_invalid:{key}")
        return float(value)

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            raise ValueError("context_config_missing")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(data.get("context_manager") or {})


# --------------------------------------------------------------------------- redaction

_SECRET = re.compile(r"""(?ix)
    (\b["']?(?:password|passwd|secret|token|api[_-]?key|apikey|credentials?)["']?\s*[:=]\s*)
    ("[^"]*"|'[^']*'|[^\s,;]+)""")


def redact_text(text):
    """Mask `key=value` pairs for sensitive keys. Heuristic: it catches the common shapes, not every secret."""
    return _SECRET.sub(lambda m: m.group(1) + "***REDACTED***", text)


# --------------------------------------------------------------------------- token estimation

class TokenEstimator:
    """Pessimistic estimates. Provider `usage` always wins; estimates only guard the way in."""

    # Chat templates add tokens around every message and once per request. Measured on a real server (2 probes, one prompt of
    # 33 characters): provider usage was 17 (one model) and 23 (another) input tokens, while 8 per message gave an estimate of 21,
    # BELOW the second number. These constants are a first correction from very little evidence; the per-model calibration is
    # what is supposed to replace them.
    MESSAGE_OVERHEAD = 12
    REQUEST_OVERHEAD = 8

    def __init__(self, config, calibration_path=None):
        self.config = config
        self.path = Path(calibration_path) if calibration_path else None
        self._cal = {}
        if self.path and self.path.exists():
            try:
                loaded = load_json(self.path, {}) or {}
                self._cal = {k: v for k, v in loaded.items() if isinstance(v, dict) and type(v.get("samples")) is int and isinstance(v.get("max_ratio"), (int, float))}
            except (ValueError, OSError):
                self._cal = {}

    @staticmethod
    def detect_kind(text):
        sample = text[:20000]
        if not sample:
            return "prose"
        symbols = sum(1 for c in sample if not (c.isalnum() or c.isspace()))
        return "code" if symbols / len(sample) > 0.2 else "prose"

    def raw_units(self, text, kind="auto"):
        if not isinstance(text, str):
            raise ContextError("text_required")
        kind = self.detect_kind(text) if kind == "auto" else kind
        cpt = self.config.code_cpt if kind == "code" else self.config.prose_cpt
        return len(text) / cpt          # Unicode characters, not bytes

    def factor(self, model_ref=None):
        cal = self._cal.get(model_ref) if model_ref else None
        if not cal:
            return self.config.safety_factor
        measured = float(cal["max_ratio"])
        if cal["samples"] < self.config.calibrate_after:
            return max(self.config.safety_factor, measured)   # may rise at once, never relax early
        return max(1.0, measured * 1.05)                      # relaxed, but never below the worst measurement

    def estimate(self, text, *, kind="auto", model_ref=None):
        return math.ceil(self.raw_units(text, kind) * self.factor(model_ref))

    def estimate_messages(self, messages, *, kind="auto", model_ref=None):
        """Returns {raw_units, estimate}. `raw_units` is what calibration compares against provider usage."""
        if not isinstance(messages, list):
            raise ContextError("messages_required")
        raw = float(self.REQUEST_OVERHEAD)
        for message in messages:
            content = message.get("content", "") if isinstance(message, dict) else ""
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            raw += self.raw_units(content, kind) + self.MESSAGE_OVERHEAD
        return {"raw_units": raw, "estimate": math.ceil(raw * self.factor(model_ref))}

    def observe(self, model_ref, raw_units, usage_tokens):
        """Compare an estimate with the provider's number. Returns the measured ratio (usage / raw)."""
        if not model_ref or raw_units <= 0 or type(usage_tokens) is not int or usage_tokens < 0:
            return None
        ratio = usage_tokens / raw_units
        key = str(model_ref)[:200]
        if self.path is None:
            cal = self._cal.setdefault(key, {"samples": 0, "max_ratio": 0.0})
            cal["samples"] += 1; cal["max_ratio"] = max(cal["max_ratio"], ratio)
            return ratio
        with append_lock(self.path):
            stored = load_json(self.path, {}) or {}
            cal = stored.setdefault(key, {"samples": 0, "max_ratio": 0.0})
            cal["samples"] += 1; cal["max_ratio"] = max(float(cal["max_ratio"]), ratio)
            atomic_write_json(self.path, stored)
            self._cal = stored
        return ratio


# --------------------------------------------------------------------------- metrics

class MetricsRecorder:
    """One line per attempt and per counter event, in `runtime_data/context_metrics/<job>.jsonl`.

    Kept out of the hash-chained audit on purpose (high frequency). One audit event per job, at the end.
    """

    COUNTERS = ("compaction_count", "checkpoint_count", "fresh_context_count", "tool_output_offloaded_bytes", "estimated_tokens_saved")

    def __init__(self, root, audit=None):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True); self.audit = audit

    def path(self, job_id):
        return self.root / f"{_safe_id(job_id, 'job_id')}.jsonl"

    def _append(self, job_id, record):
        path = self.path(job_id)
        with append_lock(path):
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def record_attempt(self, job_id, attempt_id, *, role=None, model_ref=None, usage=None, estimate_tokens=None,
                       context_window=None, peak_fill=None, provider_cost=None, estimator_ratio=None):
        provider = isinstance(usage, dict) and type(usage.get("input_tokens")) is int and type(usage.get("output_tokens")) is int
        if provider:
            inp, out, cached = usage["input_tokens"], usage["output_tokens"], usage.get("cached_tokens")
        else:
            inp, out, cached = estimate_tokens, None, None   # an estimate is labelled as one; output is unknown, not zero
        error = None
        if provider and estimate_tokens:
            error = usage["input_tokens"] / estimate_tokens
        record = {"kind": "attempt", "schema": 1, "job_id": job_id, "attempt_id": str(attempt_id)[:64], "role": role,
                  "model_ref": model_ref, "recorded_at": utcnow(), "input_tokens": inp, "output_tokens": out,
                  "cached_tokens": cached, "reasoning_tokens": usage.get("reasoning_tokens") if provider else None,
                  "usage_source": "provider" if provider else "estimate",
                  "context_window": context_window, "peak_fill": peak_fill,
                  "estimator_error_ratio": error, "estimator_measured_ratio": estimator_ratio, "provider_cost": provider_cost}
        return self._append(job_id, record)

    def bump(self, job_id, attempt_id, **counters):
        bad = set(counters) - set(self.COUNTERS)
        if bad:
            raise ContextError("unknown_counter", sorted(bad))
        record = {"kind": "counter", "schema": 1, "job_id": job_id, "attempt_id": str(attempt_id)[:64], "recorded_at": utcnow(), **counters}
        return self._append(job_id, record)

    def lines(self, job_id):
        path = self.path(job_id)
        if not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    out.append({"kind": "corrupt_line"})
        return out

    def summary(self, job_id):
        attempts = [r for r in self.lines(job_id) if r.get("kind") == "attempt"]
        counters = [r for r in self.lines(job_id) if r.get("kind") == "counter"]
        total = lambda rows, key: sum(r.get(key) or 0 for r in rows)
        sources = sorted({r["usage_source"] for r in attempts})
        peaks = [r["peak_fill"] for r in attempts if isinstance(r.get("peak_fill"), (int, float))]
        return {"job_id": job_id, "attempts": len(attempts),
                "input_tokens": total(attempts, "input_tokens"), "output_tokens": total(attempts, "output_tokens"),
                "reasoning_tokens": total(attempts, "reasoning_tokens"),
                "usage_sources": sources, "peak_fill": max(peaks) if peaks else None,
                "compaction_count": total(counters, "compaction_count"), "checkpoint_count": total(counters, "checkpoint_count"),
                "fresh_context_count": total(counters, "fresh_context_count"),
                "tool_output_offloaded_bytes": total(counters, "tool_output_offloaded_bytes"),
                "estimated_tokens_saved": total(counters, "estimated_tokens_saved")}

    def finish_job(self, job_id):
        """Exactly one audit event per job, however often this is called."""
        with append_lock(self.path(job_id)):
            if any(r.get("kind") == "summary" for r in self.lines(job_id)):
                return None
            summary = self.summary(job_id)
            with self.path(job_id).open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"kind": "summary", "schema": 1, "recorded_at": utcnow(), **summary}, ensure_ascii=False, sort_keys=True) + "\n")
        if self.audit:
            self.audit.append("CONTEXT_METRICS_SUMMARY", component="context-manager", payload=summary)
        return summary


# --------------------------------------------------------------------------- budget resolution

class BudgetResolver:
    """The effective window is the smallest of what the model, the hardware pass and the runtime allow."""

    def __init__(self, budget_manager, config, estimator):
        self.budget_manager, self.config, self.estimator = budget_manager, config, estimator

    def resolve(self, *, model_window=None, hardware_effective_max=None, runtime_loaded=None, strict=False, **overrides):
        known = {}
        for name, value in (("model", model_window), ("model_pass", hardware_effective_max), ("runtime", runtime_loaded)):
            if value is None:
                continue
            if type(value) is not int or value < 1:
                raise ContextError("budget_invalid", f"{name}={value!r}")
            known[name] = value
        if known:
            source = min(known, key=lambda k: (known[k], k))
            window = known[source]
        else:
            if strict:
                raise ContextError("context_window_unknown")
            source, window = "default", self.config.default_window
        try:
            budget = self.budget_manager.build_budget(window, **overrides)
        except ValueError as exc:
            raise ContextError("budget_invalid", str(exc)) from exc
        budget.update(budget_source=source, window_inputs=dict(known),
                      estimator={"name": "chars_per_token", "safety_factor": self.config.safety_factor})
        return budget

    def from_pass(self, pass_result, *, model_window=None, runtime_loaded=None, strict=False, **overrides):
        limits = (pass_result or {}).get("context_limits") or {}
        effective = limits.get("effective_maximum")
        return self.resolve(model_window=model_window, hardware_effective_max=effective if type(effective) is int else None,
                            runtime_loaded=runtime_loaded, strict=strict, **overrides)


# --------------------------------------------------------------------------- offloading

class OutputOffloader:
    ERROR = re.compile(r"\b(error|exception|traceback|fatal|failed|failure)\b", re.I)
    WARN = re.compile(r"\bwarn(?:ing)?\b", re.I)
    MAX_RANGES = 5

    def __init__(self, root, artifacts, estimator, config, audit=None):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.artifacts, self.estimator, self.config, self.audit = artifacts, estimator, config, audit

    def threshold(self, state="GREEN"):
        if state not in INLINE_FACTOR:
            raise ContextError("unknown_watermark_state", state)
        return max(1, int(self.config.inline_max_tokens * INLINE_FACTOR[state]))

    @staticmethod
    def _bytes(payload):
        if isinstance(payload, bytes):
            return payload
        if isinstance(payload, str):
            return payload.encode("utf-8")
        raise ContextError("payload_must_be_text_or_bytes")

    def process(self, job_id, attempt_id, source, payload, *, state="GREEN", model_ref=None):
        """Small output stays inline (redacted). Large output is stored in full and replaced by a summary."""
        raw = self._bytes(payload)
        text = raw.decode("utf-8", errors="replace")
        tokens = self.estimator.estimate(text, model_ref=model_ref)
        if tokens <= self.threshold(state):
            return {"inline": True, "text": redact_text(text), "tokens": tokens, "record": None}
        record = self.offload(job_id, attempt_id, source, raw, model_ref=model_ref)
        return {"inline": False, "text": self.render_summary(record), "tokens": self.estimator.estimate(self.render_summary(record), model_ref=model_ref), "record": record}

    def offload(self, job_id, attempt_id, source, payload, *, model_ref=None):
        _safe_id(job_id, "job_id")
        raw = self._bytes(payload)
        if len(raw) > self.config.max_offload_bytes:
            raise ContextError("offload_failed", "output_exceeds_max_offload_bytes")
        offload_id = f"OFF-{uuid.uuid4().hex[:12].upper()}"
        folder = self.root / job_id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{offload_id}.txt"
        try:
            path.write_bytes(raw)
            artifact = self.artifacts.register(job_id, path, source_component="context-manager", job_id=job_id)
        except OSError as exc:
            raise ContextError("offload_failed", type(exc).__name__) from exc
        summary, redacted = self._summarize(raw)
        record = {"schema": 1, "offload_id": offload_id, "artifact_id": artifact["artifact_id"], "job_id": job_id,
                  "attempt_id": str(attempt_id)[:64], "source": {"tool": str((source or {}).get("tool"))[:100], "operation": str((source or {}).get("operation"))[:100]},
                  "bytes": len(raw), "lines": summary["counts"]["lines"], "sha256": sha256_bytes(raw), "created_at": utcnow(),
                  "summary": summary, "summary_method": "deterministic", "redacted": redacted}
        record["tokens_saved_estimate"] = max(0, self.estimator.estimate(raw.decode("utf-8", errors="replace"), model_ref=model_ref)
                                             - self.estimator.estimate(self.render_summary(record), model_ref=model_ref))
        return record

    def _summarize(self, raw):
        errors, warnings, lines = [], 0, []
        offset = 0
        for chunk in raw.split(b"\n"):
            text = chunk.decode("utf-8", errors="replace").rstrip("\r")
            lines.append((offset, offset + len(chunk), text))
            offset += len(chunk) + 1
        if lines and lines[-1][2] == "" and lines[-1][0] >= len(raw):
            lines.pop()
        for index, (start, end, text) in enumerate(lines):
            if self.ERROR.search(text):
                errors.append(index)
            elif self.WARN.search(text):
                warnings += 1
        redacted = False
        first = None
        if errors:
            start, end, text = lines[errors[0]]
            masked = redact_text(text)
            redacted = masked != text
            first = {"line": errors[0] + 1, "byte_start": start, "message": masked[:300]}
        ranges = []
        for index in errors[: self.MAX_RANGES]:
            lo, hi = max(index - 2, 0), min(index + 2, len(lines) - 1)
            span = {"start": lines[lo][0], "end": lines[hi][1], "why": "error"}
            if ranges and span["start"] <= ranges[-1]["end"]:
                ranges[-1]["end"] = max(ranges[-1]["end"], span["end"])
            else:
                ranges.append(span)
        summary = {"status": "failed" if errors else "warnings" if warnings else "ok", "status_method": "keyword_heuristic",
                   "counts": {"lines": len(lines), "errors": len(errors), "warnings": warnings},
                   "first_error": first, "relevant_ranges": ranges, "truncated": len(errors) > self.MAX_RANGES}
        return summary, redacted

    @staticmethod
    def render_summary(record):
        s = record["summary"]
        parts = [f"[output offloaded: {record['offload_id']} / {record['artifact_id']}]",
                 f"status={s['status']} ({s['status_method']}) lines={s['counts']['lines']} errors={s['counts']['errors']} warnings={s['counts']['warnings']}",
                 f"bytes={record['bytes']} sha256={record['sha256'][:16]}"]
        if s["first_error"]:
            parts.append(f"first_error line {s['first_error']['line']}: {s['first_error']['message']}")
        if s["relevant_ranges"]:
            parts.append("relevant_byte_ranges=" + ",".join(f"{r['start']}-{r['end']}" for r in s["relevant_ranges"]))
        if s["truncated"]:
            parts.append("summary_covers_only_first_errors=true")
        return "\n".join(parts)

    def read_range(self, artifact_id, start, length, *, allowed_artifacts=None):
        """Exact bytes of an offloaded artifact. Bounded, path-checked, hash-checked."""
        if allowed_artifacts is not None and artifact_id not in allowed_artifacts:
            raise ContextError("policy_denied", "artifact_not_in_manifest")
        record = self.artifacts.get(artifact_id)
        if record is None:
            raise ContextError("piece_not_found", artifact_id)
        if type(start) is not int or type(length) is not int or start < 0 or length < 1:
            raise ContextError("invalid_range")
        if length > self.config.artifact_read_max_bytes:
            raise ContextError("artifact_range_too_large", self.config.artifact_read_max_bytes)
        path = Path(record["path"])
        base = self.root.resolve()
        try:
            resolved = path.resolve()
            if path.is_symlink() or not resolved.is_relative_to(base) or not resolved.is_file():
                raise ContextError("policy_denied", "artifact_path_outside_store")
            data = resolved.read_bytes()
        except OSError as exc:
            raise ContextError("piece_not_found", type(exc).__name__) from exc
        if sha256_bytes(data) != (record.get("integrity") or {}).get("hash"):
            raise ContextError("artifact_integrity_failed", artifact_id)
        return data[start:start + length]

    def read_range_for_prompt(self, artifact_id, start, length, *, allowed_artifacts=None):
        chunk = self.read_range(artifact_id, start, length, allowed_artifacts=allowed_artifacts)
        return redact_text(chunk.decode("utf-8", errors="replace"))


# --------------------------------------------------------------------------- pieces, relevance, health

def make_piece(kind, text, *, layer="L3", ref=None, critical=False, done=False, task=0, file=0, decision=0, safety=0,
               pinned=False, created_at=None):
    """A working-context item. The text lives in memory; only its digest goes into records."""
    if layer not in LAYERS:
        raise ContextError("invalid_layer", layer)
    return {"piece_id": f"CPC-{uuid.uuid4().hex[:12].upper()}", "layer": layer, "kind": kind, "ref": ref or {},
            "text": text, "content_digest": sha256_bytes(text.encode("utf-8")), "critical": bool(critical or pinned or kind == "pin"),
            "done": bool(done), "signals": {"task": task, "file": file, "decision": decision, "safety": safety, "pinned": bool(pinned)},
            "created_at": created_at or utcnow()}


def score_piece(piece, weights, now):
    signals = piece["signals"]
    age = max(0.0, (now - datetime.fromisoformat(piece["created_at"])).total_seconds())
    recency = 1.0 / (1.0 + age / 3600.0)
    parts = {"task": weights["task"] * signals["task"], "file": weights["file"] * signals["file"],
             "decision": weights["decision"] * signals["decision"], "safety": weights["safety"] * signals["safety"],
             "pinned": weights["pinned"] * (1 if signals["pinned"] else 0), "recency": weights["recency"] * recency,
             "done_penalty": -weights["done_penalty"] * (1 if piece["done"] else 0)}
    return {"total": sum(parts.values()), "parts": parts}


# --------------------------------------------------------------------------- checkpoints

class CheckpointWriter:
    LIST_LIMITS = {"changed": 256, "artifacts": 256, "tests": 256, "open_errors": 64, "decisions": 64, "next_steps": 32, "pins": 256}

    def __init__(self, root, estimator, config, *, audit=None, artifacts=None, evidence_store=None, clock=None):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.estimator, self.config, self.audit, self.artifacts, self.evidence = estimator, config, audit, artifacts, evidence_store
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _validate_pin(self, pin):
        if not isinstance(pin, dict) or pin.get("kind") not in PIN_KINDS:
            raise ContextError("pin_missing_source", "invalid_pin_kind")
        ref = pin.get("ref")
        keys = [k for k in PIN_REF_KEYS if isinstance(ref, dict) and ref.get(k)]
        if not keys or not isinstance(pin.get("digest"), str) or not pin["digest"]:
            raise ContextError("pin_missing_source", pin.get("kind"))
        if ref.get("evidence_id") and self.evidence is not None:
            if not any(r["evidence_id"] == ref["evidence_id"] for r in self.evidence.list()):
                raise ContextError("pin_missing_source", f"evidence_not_found:{ref['evidence_id']}")
        if ref.get("artifact_id") and self.artifacts is not None and self.artifacts.get(ref["artifact_id"]) is None:
            raise ContextError("pin_missing_source", f"artifact_not_found:{ref['artifact_id']}")
        return {"pin_id": pin.get("pin_id") or f"PIN-{uuid.uuid4().hex[:10].upper()}", "kind": pin["kind"], "ref": deepcopy(ref),
                "digest": pin["digest"], "value": str(pin.get("value", ""))[:200], "created_at": pin.get("created_at") or utcnow()}

    @staticmethod
    def _list(value, name, limit):
        value = [] if value is None else value
        if not isinstance(value, list) or len(value) > limit or any(not isinstance(x, (dict, str)) for x in value):
            raise ContextError("checkpoint_invalid", name)
        return deepcopy(value)

    def write(self, job_id, attempt_id, *, goal, manifest=None, changed=None, artifacts=None, tests=None, open_errors=None,
              decisions=None, next_steps=None, permission_state=None, pins=None, token_stats=None, reason=None):
        _safe_id(job_id, "job_id")
        if not isinstance(goal, str) or not goal.strip():
            raise ContextError("checkpoint_invalid", "goal")
        record = {"schema": 1, "checkpoint_id": f"CKP-{uuid.uuid4().hex[:12].upper()}", "job_id": job_id, "attempt_id": str(attempt_id)[:64],
                  "created_at": self._clock().isoformat(), "reason": reason, "goal": goal.strip()[:500],
                  "manifest_id": (manifest or {}).get("manifest_id"), "manifest_digest": (manifest or {}).get("manifest_digest"),
                  "changed": self._list(changed, "changed", self.LIST_LIMITS["changed"]),
                  "artifacts": self._list(artifacts, "artifacts", self.LIST_LIMITS["artifacts"]),
                  "tests": self._list(tests, "tests", self.LIST_LIMITS["tests"]),
                  "open_errors": self._list(open_errors, "open_errors", self.LIST_LIMITS["open_errors"]),
                  "decisions": self._list(decisions, "decisions", self.LIST_LIMITS["decisions"]),
                  "next_steps": [str(x)[:200] for x in self._list(next_steps, "next_steps", self.LIST_LIMITS["next_steps"])],
                  "permission_state": deepcopy(permission_state or {}),
                  "pins": [self._validate_pin(p) for p in self._list(pins, "pins", self.LIST_LIMITS["pins"])],
                  "token_stats": deepcopy(token_stats or {}), "truncated_fields": []}
        self._fit(record)
        record["checkpoint_digest"] = canonical_digest({k: v for k, v in record.items() if k != "checkpoint_digest"})
        folder = self.root / job_id
        folder.mkdir(parents=True, exist_ok=True)
        atomic_write_json(folder / f"{record['checkpoint_id']}.json", record)
        if self.audit:
            self.audit.append("CONTEXT_CHECKPOINT_WRITTEN", component="context-manager",
                              payload={"job_id": job_id, "checkpoint_id": record["checkpoint_id"], "checkpoint_digest": record["checkpoint_digest"],
                                       "pins": len(record["pins"]), "reason": reason})
        return record

    def _tokens(self, record):
        return self.estimator.estimate(json.dumps(record, ensure_ascii=False, sort_keys=True), kind="code")

    def _fit(self, record):
        """Free text may be shortened, and says so. Pins, tests and permission state are never cut."""
        limit = self.config.checkpoint_max_tokens
        if self._tokens(record) <= limit:
            return
        while record["next_steps"] and self._tokens(record) > limit:
            record["next_steps"].pop(); self._mark(record, "next_steps")
        if self._tokens(record) > limit and len(record["goal"]) > 200:
            record["goal"] = record["goal"][:200]; self._mark(record, "goal")
        for entry in record["decisions"]:
            if self._tokens(record) <= limit:
                break
            if isinstance(entry, dict) and len(str(entry.get("text", ""))) > 80:
                entry["text"] = str(entry["text"])[:80]; self._mark(record, "decisions")
        if self._tokens(record) > limit:
            raise ContextError("checkpoint_too_large", {"tokens": self._tokens(record), "limit": limit})

    @staticmethod
    def _mark(record, field):
        if field not in record["truncated_fields"]:
            record["truncated_fields"].append(field)

    def load(self, job_id, checkpoint_id):
        path = self.root / _safe_id(job_id, "job_id") / f"{_safe_id(checkpoint_id, 'checkpoint_id')}.json"
        record = load_json(path)
        if record is None:
            raise ContextError("piece_not_found", checkpoint_id)
        if canonical_digest({k: v for k, v in record.items() if k != "checkpoint_digest"}) != record.get("checkpoint_digest"):
            raise ContextError("checkpoint_digest_mismatch", checkpoint_id)
        return record

    def latest(self, job_id):
        folder = self.root / _safe_id(job_id, "job_id")
        if not folder.exists():
            return None
        records = []
        for path in folder.glob("CKP-*.json"):
            try:
                records.append(self.load(job_id, path.stem))
            except ContextError:
                continue                       # a damaged checkpoint is skipped here and reported by `load`
        return max(records, key=lambda r: (r["created_at"], r["checkpoint_id"])) if records else None

    def list_ids(self, job_id):
        folder = self.root / _safe_id(job_id, "job_id")
        return sorted(p.stem for p in folder.glob("CKP-*.json")) if folder.exists() else []


def collect_pins(job, *, evidence_records=(), approvals=()):
    """Critical facts, taken only from structured sources (job record, evidence store, Guard)."""
    pins = []
    job_id = job["job_id"]
    contract = job.get("contract") or {}
    if contract.get("contract_digest"):
        pins.append({"kind": "constraint", "ref": {"job_id": job_id}, "digest": contract["contract_digest"],
                     "value": f"contract {contract.get('contract_id', '')} permission_level={contract.get('permission_level')}"})
    if job.get("policy_hash"):
        pins.append({"kind": "policy_hash", "ref": {"job_id": job_id}, "digest": job["policy_hash"], "value": "policy snapshot"})
    candidate = job.get("candidate") or {}
    if candidate.get("candidate_hash"):
        pins.append({"kind": "code_change", "ref": {"job_id": job_id}, "digest": candidate["candidate_hash"], "value": f"candidate {candidate.get('candidate_id', '')}"})
    for record in evidence_records:
        if record.get("trust_level") == "deterministic" and record.get("job_id") == job_id:
            pins.append({"kind": "test_result", "ref": {"evidence_id": record["evidence_id"]}, "digest": record["evidence_hash"],
                         "value": str((record.get("payload") or {}).get("status"))})
    for approval in approvals:
        ref = {k: approval[k] for k in ("token_id", "gate_id") if approval.get(k)}
        if ref:
            pins.append({"kind": "approval", "ref": ref, "digest": canonical_digest(ref), "value": str(approval.get("action", ""))[:100]})
    return pins


# --------------------------------------------------------------------------- facade

class ContextManager:
    def __init__(self, data_root, config, *, artifacts, audit=None, evidence_store=None, budget_manager=None, clock=None):
        self.config = config
        self.audit = audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        root = Path(data_root)
        self.budget_manager = budget_manager or ContextBudgetManager(config.watermarks)
        self.estimator = TokenEstimator(config, root / "context_metrics" / "calibration.json")
        self.metrics = MetricsRecorder(root / "context_metrics", audit)
        self.resolver = BudgetResolver(self.budget_manager, config, self.estimator)
        self.offloader = OutputOffloader(root / "context_artifacts", artifacts, self.estimator, config, audit)
        self.checkpoints = CheckpointWriter(root / "context_checkpoints", self.estimator, config, audit=audit,
                                            artifacts=artifacts, evidence_store=evidence_store, clock=clock)
        self._flags = {}                       # job_id -> flags from the last watermark reaction (in memory)
        from ..context_assembly import ContextAssembly      # imported here: the module builds on this one
        self.assembly = ContextAssembly(self, root)

    @property
    def enabled(self):
        return self.config.enabled

    # ---- measuring
    def estimate(self, text, **kw):
        return self.estimator.estimate(text, **kw)

    def record_usage(self, job_id, attempt_id, *, messages=None, usage=None, model_ref=None, role=None, context_window=None,
                     used_tokens=None, provider_cost=None):
        """Record one attempt. Provider usage is exact; otherwise the estimate is stored and labelled as such."""
        estimate = self.estimator.estimate_messages(messages, model_ref=model_ref) if messages is not None else None
        ratio = None
        provider = isinstance(usage, dict) and type(usage.get("input_tokens")) is int
        if provider and estimate and model_ref:
            ratio = self.estimator.observe(model_ref, estimate["raw_units"], usage["input_tokens"])
        peak = None
        if context_window:
            if provider and type(usage.get("output_tokens")) is int:
                fill_tokens = usage["input_tokens"] + usage["output_tokens"]
            elif used_tokens is not None:
                fill_tokens = used_tokens
            else:
                fill_tokens = (estimate or {}).get("estimate")
            peak = None if fill_tokens is None else fill_tokens / context_window
        return self.metrics.record_attempt(job_id, attempt_id, role=role, model_ref=model_ref, usage=usage if provider else None,
                                           estimate_tokens=(estimate or {}).get("estimate"), context_window=context_window,
                                           peak_fill=peak, provider_cost=provider_cost, estimator_ratio=ratio)

    # ---- budgets
    def resolve_budget(self, **kw):
        return self.resolver.resolve(**kw)

    def piece(self, kind, text, *, model_ref=None, **kw):
        """A working-context item with its token estimate filled in."""
        piece = make_piece(kind, text, **kw)
        piece["tokens_est"] = self.estimator.estimate(text, model_ref=model_ref)
        return piece

    def health(self, used_tokens, budget, pieces=None, *, last_checkpoint_at=None):
        base = self.budget_manager.health(used_tokens, budget)
        info = {"state": base["state"], "fill_ratio": base["fill_ratio"], "used_tokens": base["used_tokens"],
                "max_input_tokens": base["max_input_tokens"], "actions": list(base["actions"]), "method": "heuristic"}
        now = self._clock()
        if last_checkpoint_at:
            info["last_checkpoint_age_s"] = max(0.0, (now - datetime.fromisoformat(last_checkpoint_at)).total_seconds())
        if pieces:
            total = sum(p["tokens_est"] for p in pieces) or 1
            digests = [p["content_digest"] for p in pieces]
            info.update({
                "tool_output_ratio": sum(p["tokens_est"] for p in pieces if p["kind"] in {"tool_output", "tool_summary"}) / total,
                "historical_ratio": sum(p["tokens_est"] for p in pieces if p["kind"] in {"history", "history_summary"}) / total,
                "unresolved_decision_count": sum(1 for p in pieces if p["kind"] == "decision" and not p["done"]),
                "duplicate_ratio": 1 - len(set(digests)) / len(digests),
                "stale_candidates": [p["piece_id"] for p in pieces if not p["critical"]
                                     and (now - datetime.fromisoformat(p["created_at"])).total_seconds() > self.config.stale_after_s
                                     and score_piece(p, self.config.weights, now)["total"] < 1.0],
            })
        return info

    # ---- offloading and artifacts
    def process_tool_output(self, job_id, attempt_id, source, payload, *, state="GREEN", model_ref=None):
        out = self.offloader.process(job_id, attempt_id, source, payload, state=state, model_ref=model_ref)
        if out["record"]:
            self.metrics.bump(job_id, attempt_id, tool_output_offloaded_bytes=out["record"]["bytes"],
                              estimated_tokens_saved=out["record"]["tokens_saved_estimate"])
        return out

    def read_artifact_range(self, artifact_id, start, length, *, allowed_artifacts=None, for_prompt=False):
        fn = self.offloader.read_range_for_prompt if for_prompt else self.offloader.read_range
        return fn(artifact_id, start, length, allowed_artifacts=allowed_artifacts)

    # ---- checkpoints
    def checkpoint(self, job_id, attempt_id, **kw):
        record = self.checkpoints.write(job_id, attempt_id, **kw)
        self.metrics.bump(job_id, attempt_id, checkpoint_count=1)
        return record

    # ---- watermark reactions
    def trim_to_target(self, pieces, target_tokens):
        """Drop the least relevant non-critical pieces until the total fits. Returns (kept, excluded)."""
        now = self._clock()
        scored = {p["piece_id"]: score_piece(p, self.config.weights, now)["total"] for p in pieces}
        kept = list(pieces)
        excluded = []
        for piece in sorted((p for p in pieces if not p["critical"]), key=lambda p: (scored[p["piece_id"]], p["created_at"])):
            if sum(p["tokens_est"] for p in kept) <= target_tokens:
                break
            kept.remove(piece)
            excluded.append({"piece_id": piece["piece_id"], "reason": "low_relevance"})
        return kept, excluded

    def on_watermark(self, job_id, attempt_id, health, *, pieces=None, checkpoint_source=None, budget=None, model_ref=None):
        """Carry out the actions that `ContextBudgetManager.health` names. Returns a protocol; nothing is hidden.

        `checkpoint_source` is a callable returning the keyword arguments for `checkpoint`; the manager does not
        know the job's content. Without it an ORANGE/RED checkpoint is reported as skipped, never faked.
        """
        state = health["state"]
        if state not in STATES:
            raise ContextError("unknown_watermark_state", state)
        flags = {"offload_factor": INLINE_FACTOR[state], "block_large_tool_dump": False, "rebuild_required": False, "fresh_context_requested": False}
        protocol, excluded = [], []
        work = list(pieces) if pieces is not None else None
        max_input = (budget or {}).get("max_input_tokens") or health.get("max_input_tokens")
        target = int(self.budget_manager.watermarks["green"] * max_input) if max_input else None   # trim back to the GREEN mark
        for action in health["actions"]:
            entry = {"action": action, "status": "applied", "detail": None}
            if action not in KNOWN_ACTIONS:
                entry["status"] = "unknown_action"
            elif action == "trim_tool_outputs":
                entry["detail"] = f"inline threshold {self.offloader.threshold(state)} tokens"
            elif action == "avoid_irrelevant_history":
                if work is None or target is None:
                    entry.update(status="skipped", detail="no_pieces_or_budget")
                else:
                    work, dropped = self.trim_to_target(work, target); excluded += dropped
                    entry["detail"] = f"dropped {len(dropped)}"
            elif action == "checkpoint":
                if checkpoint_source is None:
                    entry.update(status="skipped", detail="no_checkpoint_source")
                else:
                    record = self.checkpoint(job_id, attempt_id, reason=f"watermark_{state.lower()}", **checkpoint_source())
                    entry.update(status="written", detail=record["checkpoint_id"])
            elif action == "compact_completed_work":
                if work is None:
                    entry.update(status="skipped", detail="no_pieces")
                else:
                    done = [p for p in work if p["done"] and not p["critical"]]
                    work = [p for p in work if p not in done]
                    excluded += [{"piece_id": p["piece_id"], "reason": "completed_work"} for p in done]
                    self.metrics.bump(job_id, attempt_id, compaction_count=1)
                    entry["detail"] = f"removed {len(done)}"
            elif action == "artifact_offload":
                if work is None:
                    entry.update(status="skipped", detail="no_pieces")
                else:
                    work, count = self._offload_pieces(job_id, attempt_id, work, state, model_ref)
                    entry["detail"] = f"offloaded {count}"
            elif action in {"context_rebuild", "fresh_task_context"}:
                flags["rebuild_required"] = True
                flags["fresh_context_requested"] = action == "fresh_task_context" or flags["fresh_context_requested"]
                entry.update(status="signalled", detail="rebuild is carried out by repair (Phase 4)")
            elif action == "block_large_tool_dump":
                flags["block_large_tool_dump"] = True
            protocol.append(entry)
        self._flags[job_id] = flags
        if self.audit and state in {"ORANGE", "RED"}:
            self.audit.append("CONTEXT_WATERMARK_ACTIONS", component="context-manager",
                              payload={"job_id": job_id, "attempt_id": str(attempt_id)[:64], "state": state,
                                       "actions": [{"action": e["action"], "status": e["status"]} for e in protocol]})
        return {"state": state, "protocol": protocol, "flags": flags, "pieces": work, "excluded": excluded}

    def _offload_pieces(self, job_id, attempt_id, pieces, state, model_ref):
        out, count = [], 0
        for piece in pieces:
            if piece["kind"] == "tool_output" and not piece["critical"] and piece.get("text") and piece["tokens_est"] > self.offloader.threshold(state):
                record = self.offloader.offload(job_id, attempt_id, piece.get("ref"), piece["text"], model_ref=model_ref)
                summary = make_piece("tool_summary", self.offloader.render_summary(record), layer="L5", ref={"artifact_id": record["artifact_id"]},
                                     task=piece["signals"]["task"], file=piece["signals"]["file"])
                summary["tokens_est"] = self.estimator.estimate(summary["text"], model_ref=model_ref)
                self.metrics.bump(job_id, attempt_id, tool_output_offloaded_bytes=record["bytes"], estimated_tokens_saved=record["tokens_saved_estimate"])
                out.append(summary); count += 1
            else:
                out.append(piece)
        return out, count

    # ---- manifests, assembly, repair (Phase 4; see context_assembly.py)
    def build_manifest(self, job, **kw):
        return self.assembly.build_manifest(job, **kw)

    def assemble(self, manifest, **kw):
        return self.assembly.assemble(manifest, **kw)

    def fresh_context(self, job, checkpoint, **kw):
        return self.assembly.fresh_context(job, checkpoint, **kw)

    def plan_repair(self, job, **kw):
        return self.assembly.plan_repair(job, **kw)

    def repair(self, job, **kw):
        return self.assembly.repair(job, **kw)

    def detect_repetition(self, history, threshold=None):
        return self.assembly.detect_repetition(history, threshold)

    # ---- status for the UIX (read only)
    def status(self, limit=20):
        root = self.metrics.root
        jobs = sorted((p.stem for p in root.glob("*.jsonl")))[-limit:]
        return {"schema": 1, "enabled": self.config.enabled, "jobs": [self.metrics.summary(j) for j in jobs],
                "checkpoints": {j: self.checkpoints.list_ids(j) for j in jobs}}
