"""Recording and replay of model calls (plan docs/LOOP_GUARD_STARNET_EXTENSIONS_PLAN_2026-10-04.md, item D).

Why: a real run could not be repeated. The raw reply of a failed generation was not kept (for the Gemma runaway only `output_tokens: 20000`
is known), the review kept 500 characters, and a stall, a review or a runaway guard could only be tested against hand-made stubs. StarNet
gets byte-identical runs from a replay provider with fixtures; this is the same idea for GUPPI.

Recorder   appends one JSON line per model call to `<dir>/<mission or job id>.jsonl`: the request digest, the (capped) request, the reply
           with its finish reason and usage, or the error, and the seconds it took. Off unless the router has a recorder; the runtime
           gives it one only when the environment variable GUPPI_RECORD_REPLIES is 1/true/yes. Local files, no gate: it is data, not
           evidence. Recording can never break an inference: every failure inside it is swallowed.
ReplayAdapter  a model adapter that answers from recordings by request digest, so a stage can be run without a GPU. A digest that was never
           recorded is an error (`replay_miss`), never a guess; several recordings of one digest are returned in order, and the last one
           is reused when they run out.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path

from .base import BaseModelAdapter, ModelAdapterError

SAMPLING_KEYS = ("temperature", "max_tokens", "top_p", "reasoning_effort", "thinking_budget_tokens", "stream_guard")   # stream_guard changes the reply
CONTENT_CAP = 200_000          # characters of a reply kept in a recording
MESSAGE_CAP = 20_000           # characters kept per request message (the digest covers the whole request)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]")


def request_digest(messages, model, kwargs):
    """24 hex characters over the whole request: messages, model and the sampling settings that were set (None counts as not set)."""
    sampling = {k: kwargs.get(k) for k in SAMPLING_KEYS if kwargs.get(k) is not None}
    raw = json.dumps({"messages": messages, "model": model, "sampling": sampling}, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _capped_messages(messages):
    out = []
    for message in messages if isinstance(messages, list) else []:
        content = message.get("content") if isinstance(message, dict) else message
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)
        out.append({"role": message.get("role") if isinstance(message, dict) else None, "chars": len(text), "content": text[:MESSAGE_CAP]})
    return out


class Recorder:
    def __init__(self, directory, clock=time.time):
        self.directory = Path(directory)
        self.clock = clock
        self._lock = threading.Lock()

    def path_for(self, mission_id):
        return self.directory / (_SAFE_NAME.sub("_", str(mission_id or "unknown"))[:80] + ".jsonl")

    def record(self, mission_id, adapter_id, model, messages, kwargs, *, result=None, error=None, seconds=0.0):
        try:
            entry = {"schema": 1, "at": self.clock(), "mission_id": mission_id, "provider": adapter_id, "model": model,
                     "digest": request_digest(messages, model, kwargs),
                     "sampling": {k: kwargs.get(k) for k in SAMPLING_KEYS if kwargs.get(k) is not None},
                     "request": _capped_messages(messages), "seconds": round(float(seconds), 3)}
            if error is not None:
                entry["error"] = f"{type(error).__name__}:{error}"
            else:
                content = result.get("content") or ""
                entry["reply"] = {"content": content[:CONTENT_CAP], "content_chars": len(content), "content_cut": len(content) > CONTENT_CAP,
                                  "finish_reason": result.get("finish_reason"), "truncated": result.get("truncated"),
                                  "usage": result.get("usage"), "reasoning_chars": result.get("reasoning_chars"),
                                  "empty_answer": result.get("empty_answer"), "runaway": result.get("runaway")}
            line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
            with self._lock:
                self.directory.mkdir(parents=True, exist_ok=True)
                with self.path_for(mission_id).open("a", encoding="utf-8") as stream:
                    stream.write(line)
        except Exception:
            pass                      # recording is a convenience; it must never break or slow an inference with an error


def load_recordings(location):
    """Every recording line of a file, or of every `*.jsonl` in a folder (sorted by name), in order. Unreadable lines are skipped."""
    location = Path(location)
    files = sorted(location.glob("*.jsonl")) if location.is_dir() else [location]
    records = []
    for file in files:
        for line in file.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict) and value.get("digest"):
                records.append(value)
    return records


class ReplayAdapter(BaseModelAdapter):
    def __init__(self, recordings, adapter_id="replay"):
        self.id = adapter_id
        self._by_digest = {}
        for record in recordings:
            self._by_digest.setdefault(record["digest"], []).append(record)
        self._used = {}

    def health(self):
        return True

    def list_models(self):
        return sorted({r.get("model") for records in self._by_digest.values() for r in records if r.get("model")})

    def chat(self, messages, model=None, **kwargs):
        digest = request_digest(messages, model, kwargs)
        records = self._by_digest.get(digest)
        if not records:
            raise ModelAdapterError(f"replay_miss:{digest}")
        index = self._used.get(digest, 0)
        self._used[digest] = index + 1
        record = records[min(index, len(records) - 1)]
        if record.get("error"):
            raise ModelAdapterError(record["error"])
        reply = record["reply"]
        return {"provider": self.id, "model": model, "content": reply.get("content") or "", "raw": {}, "usage": reply.get("usage"),
                "finish_reason": reply.get("finish_reason"), "truncated": reply.get("truncated"),
                "reasoning_chars": reply.get("reasoning_chars"), "empty_answer": reply.get("empty_answer"),
                "runaway": reply.get("runaway"), "replayed": True, "content_cut": reply.get("content_cut", False)}
