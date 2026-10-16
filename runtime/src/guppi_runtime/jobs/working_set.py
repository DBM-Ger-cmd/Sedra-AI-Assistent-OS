"""The working set: what a model is sent for ONE step of a job (Phase 9).

Until now a handler sent everything it had, from the first message to the last, at every step. That costs tokens, time (a 90k-token
prompt takes about 45 s to process on this PC) and, with qwen3.5, stability (llama.cpp #21383: crashes with long prompts whose
prefix keeps changing). The working set keeps the history OUTSIDE the window and sends only what the step needs:

    [ head ]            policy, task contract, snapshot, pins. Byte-identical from step to step (cache friendly).
    [ archive index ]   one short line per archived block, plus pinned facts verbatim. Changes ONLY when a block is archived.
    [ active turns ]    the recent turns, append-only between compactions.
    [ this step ]       the current task, plus excerpts RECALLED from the archive because they match this step.

Everything that changes per step sits at the END, so a server that reuses the unchanged beginning of a prompt can do so.

Compaction is by BLOCK: when the active turns pass the compaction mark, the oldest run of turns (never the most recent ones) is stored
whole as an artifact (exact bytes, hash-checked, readable by range) and replaced in the window by one index line. Pinned or critical
entries are never lost: they move verbatim into the "pinned facts" of the index. Nothing is summarised by a model; the index line is
built from the text itself (first lines, errors, file names, key words), so the same input always gives the same prompt.

Deliberate limits: relevance is lexical (shared words, errors, files), not semantic. A block whose words do not overlap the step is
not recalled (it stays reachable by id). Tool results that arrive large are offloaded by the existing OutputOffloader first.
"""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

from ..context_manager import ContextError, _safe_id, redact_text
from ..util import atomic_write_json, load_json, utcnow

ROLES = ("user", "assistant", "tool")
KINDS = frozenset({"turn", "tool_result", "decision", "note", "error"})
STOP = frozenset("""the and for with that this from are was were has have had not but you your our their its can will would should could
into than then them they there here what when where which while about also been being over under after before between each such only
more most other some any all one two via per ein eine der die das und mit von zu den dem des ist sind war wird nicht auch auf aus bei""".split())
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_.\-/]{2,}|\d{3,}")
PATHISH = re.compile(r"[\w./\\-]+\.(?:py|md|yaml|yml|json|txt|toml|ini|cfg|js|ts|html|css|sh|bat|ps1)\b")
ERRISH = re.compile(r"\b(error|exception|traceback|fatal|failed|failure)\b", re.I)


def keywords(text, limit=40):
    """The distinctive words of a text, most frequent first, in a fixed order. Deterministic."""
    counts = {}
    for word in WORD.findall(text or ""):
        w = word.lower().strip("._-/")
        if len(w) >= 3 and w not in STOP:
            counts[w] = counts.get(w, 0) + 1
    return [w for w, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]


OFFLOAD_MAX_PARTS = 2               # offloaded outputs recalled for one step
OFFLOAD_MAX_LINES = 40              # lines of one output handed back at most
ASK_MAX_CHARS = 1200                # a step longer than this carries pasted material; what it asks for is its last paragraph


def _all_words(text):
    """Every distinct word of a text (same word rules as keywords())."""
    return {w for w in (x.lower().strip("._-/") for x in WORD.findall(text or "")) if len(w) >= 3 and w not in STOP}


def _ask_of(step_task):
    """What a step asks for. A short step is all question. A long one is pasted material (a file just read) followed by the question, and the
    pasted words must not pull recalls in, so only its last paragraph counts."""
    if len(step_task) <= ASK_MAX_CHARS:
        return step_task
    paragraphs = [p for p in step_task.split("\n\n") if p.strip()]
    return (paragraphs[-1] if paragraphs else step_task)[-ASK_MAX_CHARS:]


def _first_line(text):
    return next((l.strip() for l in (text or "").splitlines() if l.strip()), "")[:80]


def common_prefix(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


class WorkingSet:
    def __init__(self, manager, root, job, *, manifest, keep_recent=4, compact_at=None, target=None, index_share=0.08, recall_k=2,
                 recall_tokens=1200, model_ref=None, merge_roles=True):
        if not isinstance(job, dict) or not job.get("job_id"):
            raise ContextError("working_set_invalid", "job_required")
        self.manager, self.job, self.model_ref = manager, job, model_ref
        self.job_id = _safe_id(job["job_id"], "job_id")
        self.folder = Path(root) / self.job_id
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / "working_set.json"
        budget = manifest["budget"]
        self.window = int(budget["max_input_tokens"])
        marks = manager.budget_manager.watermarks
        self.compact_at = int(compact_at if compact_at is not None else marks["green"] * self.window)
        self.target = int(target if target is not None else 0.6 * self.compact_at)
        if not 0 < self.target < self.compact_at <= self.window:
            raise ContextError("working_set_invalid", "need 0 < target < compact_at <= window")
        if keep_recent < 1 or recall_k < 0:
            raise ContextError("working_set_invalid", "keep_recent_and_recall_k")
        self.keep_recent, self.recall_k, self.recall_tokens, self.index_share = keep_recent, recall_k, recall_tokens, index_share
        self.merge_roles = merge_roles
        self.manifest = manifest
        self._head = self._build_head()
        state = load_json(self.path) or {}
        self.state = {"schema": 1, "job_id": self.job_id, "manifest_digest": manifest["manifest_digest"], "entries": [], "blocks": [], "pinned": [],
                      "seq": 0, "block_seq": 0, "attempt_id": "ATT-NONE", "offloads": [], **state}
        self.last_prompt = ""
        self.stats = {"composes": 0, "compactions": 0, "recalls": 0, "offload_recalls": 0}
        self._offload_cache = {}

    # ------------------------------------------------------------------ persistence
    def _save(self):
        atomic_write_json(self.path, self.state)

    def bind_attempt(self, attempt_id):
        self.state["attempt_id"] = str(attempt_id)[:64]

    # ------------------------------------------------------------------ head
    def _build_head(self):
        pieces = self.manager.assembly._fixed_pieces(self.manifest, self.model_ref)
        order = ("L0", "L1", "L2", "L3", "L4", "L5")
        pieces.sort(key=lambda p: order.index(p["layer"]))
        text = "\n\n".join(p["text"] for p in pieces)
        # Pin ids are random per manifest. They carry no meaning for the model, and in the head they would change the start of the
        # prompt every time a manifest is rebuilt (a new attempt, a restart): the digest in the same line identifies the pin.
        return re.sub(r"^- PIN-[0-9A-Fa-f]+ ", "- ", text, flags=re.M)

    def rehead(self, manifest):
        """A new manifest (for example a changed task contract) replaces the head. History and archive stay."""
        self.manifest = manifest
        self._head = self._build_head()
        self.state["manifest_digest"] = manifest["manifest_digest"]
        self._save()

    # ------------------------------------------------------------------ adding
    def _est(self, text):
        return self.manager.estimate(text, model_ref=self.model_ref)

    def add(self, kind, text, *, role="user", source=None, pinned=False, critical=False, decision=0, safety=0):
        """Add one turn. A large tool result is offloaded first: the window gets its summary and a reference, never the whole dump."""
        if kind not in KINDS or role not in ROLES:
            raise ContextError("working_set_invalid", f"kind_or_role:{kind}:{role}")
        if not isinstance(text, str) or not text.strip():
            raise ContextError("working_set_invalid", "text_required")
        artifact = None
        original = text
        if kind == "tool_result":
            out = self.manager.offloader.process(self.job_id, self.state["attempt_id"], source or {"tool": "tool", "operation": "call"}, text,
                                                 state=self._health_state(), model_ref=self.model_ref)
            text = out["text"]
            if out["record"]:
                artifact = out["record"]["artifact_id"]
                # The window only keeps the summary. Remember where the full output is, so a later step that asks for something
                # inside it can get exactly that part back (see _recall_offloaded).
                self.state["offloads"].append({"artifact_id": artifact, "bytes": out["record"]["bytes"], "label": _first_line(original)})
                self.manager.metrics.bump(self.job_id, self.state["attempt_id"], tool_output_offloaded_bytes=out["record"]["bytes"],
                                          estimated_tokens_saved=out["record"]["tokens_saved_estimate"])
        else:
            text = redact_text(text)
        self.state["seq"] += 1
        entry = {"entry_id": f"E{self.state['seq']:05d}", "kind": kind, "role": role, "text": text, "tokens": self._est(text),
                 "critical": bool(critical or pinned), "pinned": bool(pinned), "signals": {"decision": decision, "safety": safety},
                 "artifact": artifact, "created_at": utcnow()}
        self.state["entries"].append(entry)
        self._save()
        return entry

    def _health_state(self):
        used = self.active_tokens() + self._est(self._head)
        return self.manager.budget_manager.health(used, {"max_input_tokens": self.window})["state"]

    def active_tokens(self):
        return sum(e["tokens"] for e in self.state["entries"])

    # ------------------------------------------------------------------ compaction
    def _index_lines(self):
        return [b["index_line"] for b in self.state["blocks"]]

    def fixed_tokens(self):
        return self._est(self._head) + self._est(self._index_text())

    def compact(self, force=False):
        """Archive the oldest run of turns if the active ones pass the mark (or `force`). Returns the new block or None."""
        entries = self.state["entries"]
        if not force and self.fixed_tokens() + self.active_tokens() <= self.compact_at:
            return None
        if len(entries) <= self.keep_recent:
            return None
        movable = entries[: len(entries) - self.keep_recent]
        take, tokens = [], self.fixed_tokens() + self.active_tokens()
        for entry in movable:
            if not force and tokens <= self.target:
                break
            take.append(entry)
            tokens -= entry["tokens"]
        if not take:
            return None
        return self._archive(take)

    def _archive(self, take):
        sections, ranges, offset = [], [], 0
        for e in take:
            part = f"[{e['entry_id']} {e['role']}/{e['kind']}]\n{e['text']}\n"
            raw = part.encode("utf-8")
            ranges.append({"entry_id": e["entry_id"], "start": offset, "length": len(raw), "keywords": keywords(e["text"], 14)})
            offset += len(raw)
            sections.append(part)
        body = "".join(sections)
        record = self.manager.offloader.offload(self.job_id, self.state["attempt_id"], {"tool": "working_set", "operation": "archive"}, body, model_ref=self.model_ref)
        self.state["block_seq"] += 1
        block_id = f"B{self.state['block_seq']:03d}"
        original = sum(e["tokens"] for e in take)
        lines = []
        for e in take[:8]:
            first = next((l.strip() for l in e["text"].splitlines() if l.strip()), "")
            lines.append(f"{e['role']}: {first[:90]}")
        files = sorted({m for e in take for m in PATHISH.findall(e["text"])})[:6]
        errors = sum(1 for e in take if ERRISH.search(e["text"]))
        block = {"block_id": block_id, "entry_ids": [e["entry_id"] for e in take], "artifact_id": record["artifact_id"], "sha256": record["sha256"],
                 "bytes": len(body.encode("utf-8")), "tokens": original, "ranges": ranges, "keywords": keywords(body, 30), "errors": errors,
                 "files": files, "created_at": utcnow()}
        block["index_line"] = (f"{block_id} ({len(take)} turns, ~{original} tokens, {errors} with errors)"
                               + (f" files: {', '.join(files)}" if files else "") + " | " + " / ".join(lines[:3]))[:420]
        for e in take:
            if e["critical"] and e["text"] not in [p["text"] for p in self.state["pinned"]]:
                self.state["pinned"].append({"entry_id": e["entry_id"], "text": e["text"], "tokens": e["tokens"]})
        taken = {e["entry_id"] for e in take}
        self.state["entries"] = [e for e in self.state["entries"] if e["entry_id"] not in taken]
        self.state["blocks"].append(block)
        self._save()
        saved = max(0, original - self._est(block["index_line"]))
        self.manager.metrics.bump(self.job_id, self.state["attempt_id"], compaction_count=1, estimated_tokens_saved=saved)
        self.stats["compactions"] += 1
        if self.manager.audit:
            self.manager.audit.append("WORKING_SET_BLOCK_ARCHIVED", component="working-set",
                                      payload={"job_id": self.job_id, "block_id": block_id, "turns": len(take), "tokens": original, "artifact_id": record["artifact_id"]})
        return block

    # ------------------------------------------------------------------ the archive index
    def _index_text(self):
        if not self.state["blocks"] and not self.state["pinned"]:
            return ""
        budget = int(self.index_share * self.window)
        lines = ["ARCHIVE (earlier steps, stored outside this window; relevant parts are recalled at the end of the prompt when a step needs them)"]
        if self.state["pinned"]:
            lines.append("PINNED FACTS (verbatim):")
            lines += [f"- {p['text']}" for p in self.state["pinned"]]
        blocks = self._index_lines()
        shown = list(blocks)
        # the index itself must stay small: when it outgrows its share, the OLDEST lines collapse into one count
        while len(shown) > 1 and self._est("\n".join(lines + shown)) > budget:
            shown.pop(0)
        hidden = len(blocks) - len(shown)
        if hidden:
            lines.append(f"({hidden} older blocks omitted from this list; still stored: {', '.join(b['block_id'] for b in self.state['blocks'][:hidden])})")
        return "\n".join(lines + [f"- {l}" for l in shown])

    # ------------------------------------------------------------------ recall
    def _relevance(self, block, step_words, recent_words, step_text):
        """What the step asks for counts fully; what the last turns talked about counts 30 percent. A block that shares nothing with
        the step itself is recalled only on a strong signal from the recent turns."""
        keys = set(block["keywords"])
        norm = math.sqrt(max(1, len(keys)))
        from_step, from_recent = len(keys & step_words), len(keys & (recent_words - step_words))
        score = from_step / norm + 0.3 * from_recent / norm
        score += 0.5 * sum(1 for f in block["files"] if f.lower() in step_text.lower())
        if block["errors"] and ERRISH.search(step_text):
            score += 0.5
        return score if (from_step or score >= 0.5) else 0.0

    def recall(self, block_id, query=None, *, max_tokens=None):
        """Exact text from an archived block: the best-matching turns for `query`, or the first ones. Hash- and range-checked."""
        block = next((b for b in self.state["blocks"] if b["block_id"] == block_id), None)
        if block is None:
            raise ContextError("piece_not_found", block_id)
        budget = max_tokens or self.recall_tokens
        words = set(keywords(query or "", 30))
        ranked = sorted(block["ranges"], key=lambda r: (-len(words & set(r["keywords"])), r["start"]))
        out, used = [], 0
        for r in ranked:
            if words and not (words & set(r["keywords"])) and out:
                continue
            chunk = self.manager.offloader.read_range(block["artifact_id"], r["start"], min(r["length"], self.manager.config.artifact_read_max_bytes)).decode("utf-8", "replace")
            cost = self._est(chunk)
            if used + cost > budget:
                keep = int(len(chunk) * max(0, budget - used) / max(1, cost))
                if keep < 200:
                    break
                chunk = chunk[:keep] + "\n[... cut to fit; read the rest of this block by id]"
                cost = budget - used
            out.append(redact_text(chunk)); used += cost
            if used >= budget:
                break
        return {"block_id": block_id, "text": "\n".join(out), "tokens": used, "entries": len(out)}

    def _offload_lines(self, item):
        """The lines and the distinct words of one offloaded output, read from its hash-checked artifact once and kept in memory. None if lost."""
        key = item["artifact_id"]
        if key not in self._offload_cache:
            try:
                raw = self.manager.offloader.read_range(key, 0, min(item["bytes"], self.manager.config.artifact_read_max_bytes))
            except ContextError:
                self._offload_cache[key] = None             # a lost or altered artifact is not recalled; the step goes on without it
            else:
                text = raw.decode("utf-8", "replace")
                self._offload_cache[key] = (text.splitlines(), _all_words(text))
        return self._offload_cache[key]

    def _recall_offloaded(self, step_words, budget):
        """Lines of fully offloaded tool outputs that the step asks for. The window holds only their summary; without this a question about
        something inside such an output could only be answered by guessing. Exact lines from the hash-checked artifact, nothing generated.
        A word counts the less the more outputs contain it (a name that only one output has is what the step is asking for)."""
        loaded = [(item, self._offload_lines(item)) for item in self.state["offloads"]]
        loaded = [(item, data) for item, data in loaded if data]
        if not loaded:
            return []
        df = {}
        for _, (_, words) in loaded:
            for w in words & step_words:
                df[w] = df.get(w, 0) + 1
        scored = []
        for item, (lines, words) in loaded:
            hit = sorted(w for w in words & step_words)
            score = sum(1.0 / df[w] for w in hit)
            if score >= 0.5:                                  # at least one word that no more than two outputs share
                scored.append((score, item, lines, hit))
        scored.sort(key=lambda x: (-x[0], x[1]["artifact_id"]))
        parts, used = [], 0
        for _, item, lines, hit in scored[:OFFLOAD_MAX_PARTS]:
            if budget - used < 120:
                break
            lowered = [l.lower() for l in lines]
            rank = {w: 1.0 / max(1, sum(1 for l in lowered if w in l)) / df[w] for w in hit}    # few lines, few outputs: names the thing asked for
            best = sorted(((sum(rank[w] for w in hit if w in l), i) for i, l in enumerate(lowered)), key=lambda x: (-x[0], x[1]))
            chosen = sorted(i for sc, i in best[:OFFLOAD_MAX_LINES] if sc > 0)
            text = "\n".join(lines[i] for i in chosen)
            cost = self._est(text)
            if not text or used + cost > budget:
                continue
            parts.append((item, redact_text(text), cost))
            used += cost
        return parts

    # ------------------------------------------------------------------ composing a step
    def compose(self, step_task):
        """The messages for one step: stable head + index, active turns, then this step with its recalled excerpts."""
        if not isinstance(step_task, str) or not step_task.strip():
            raise ContextError("working_set_invalid", "step_task_required")
        self.compact()
        fixed = self.fixed_tokens()
        step_tokens = self._est(step_task)
        if fixed + step_tokens > self.compact_at:
            raise ContextError("minimum_context_exceeds_window", {"minimum_tokens": fixed + step_tokens, "limit": self.compact_at})
        recalled, recall_text = [], ""
        room = self.window - (fixed + self.active_tokens() + step_tokens)
        if self.state["blocks"] and self.recall_k and room > 200:
            step_words = set(keywords(step_task, 40))
            recent_words = set(keywords("\n".join(e["text"] for e in self.state["entries"][-2:]), 40))
            scored = sorted(((self._relevance(b, step_words, recent_words, step_task), b) for b in self.state["blocks"]), key=lambda x: (-x[0], x[1]["block_id"]))
            budget = min(self.recall_tokens, max(0, int(0.5 * room)))
            parts = []
            for score, block in scored[: self.recall_k]:
                if score <= 0 or budget < 120:
                    continue
                got = self.recall(block["block_id"], step_task, max_tokens=budget // max(1, min(self.recall_k, len(scored))))
                if got["text"]:
                    parts.append(f"RECALLED FROM ARCHIVE {block['block_id']}:\n{got['text']}")
                    recalled.append({"block_id": block["block_id"], "tokens": got["tokens"], "score": round(score, 3)})
            recall_text = "\n\n".join(parts)
            self.stats["recalls"] += len(recalled)
        if self.state["offloads"] and self.recall_k and room > 200:
            for item, text, cost in self._recall_offloaded(_all_words(_ask_of(step_task)), min(self.recall_tokens, max(0, int(0.5 * room)))):
                recall_text += ("\n\n" if recall_text else "") + f"RECALLED FROM OFFLOADED OUTPUT {item['artifact_id']} ({item['label']}):\n{text}"
                recalled.append({"artifact_id": item["artifact_id"], "tokens": cost, "kind": "offloaded_output"})
                self.stats["offload_recalls"] += 1
        system = self._head + (("\n\n" + self._index_text()) if self._index_text() else "")
        turns = [(("assistant" if e["role"] == "assistant" else "user"), (f"[tool result] {e['text']}" if e["kind"] == "tool_result" else e["text"])) for e in self.state["entries"]]
        tail = step_task if not recall_text else f"{recall_text}\n\nCURRENT STEP:\n{step_task}"
        messages = [{"role": "system", "content": system}]
        for role, text in turns + [("user", tail)]:
            if self.merge_roles and messages[-1]["role"] == role and len(messages) > 1:
                messages[-1]["content"] += "\n\n" + text
            else:
                messages.append({"role": role, "content": text})
        prompt = "\n".join(m["role"] + ":" + m["content"] for m in messages)
        reuse = common_prefix(self.last_prompt, prompt) / len(self.last_prompt) if self.last_prompt else 0.0
        self.last_prompt = prompt
        self.stats["composes"] += 1
        tokens = self._est(prompt)
        return {"messages": messages, "tokens": tokens, "prefix_digest": hashlib.sha256(system.encode("utf-8")).hexdigest(), "reuse_of_previous": round(reuse, 4),
                "recalled": recalled, "archived_blocks": len(self.state["blocks"]), "active_turns": len(self.state["entries"]),
                "parts": {"head": self._est(self._head), "index": self._est(self._index_text()), "turns": self.active_tokens(), "step": step_tokens},
                "state": self.manager.budget_manager.health(tokens, {"max_input_tokens": self.window})["state"]}

    def status(self):
        return {"job_id": self.job_id, "window": self.window, "compact_at": self.compact_at, "active_turns": len(self.state["entries"]),
                "active_tokens": self.active_tokens(), "blocks": len(self.state["blocks"]), "pinned_facts": len(self.state["pinned"]), **self.stats}
