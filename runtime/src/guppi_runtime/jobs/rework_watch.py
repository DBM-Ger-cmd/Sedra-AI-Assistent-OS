"""Rework watch: stops a rework loop that keeps failing for the same cause. It only advises; it never cancels or changes a job.

Why (2026-10-03, uix_window): 24 discarded generations, the same `parsed.port` failure over many of them and repeated `model_answer_truncated`;
every generation costs minutes of GPU. Plan: docs/LOOP_GUARD_REWORK_PLAN_2026-10-04.md. Built on guppi_runtime.jobs.loop_guard.

Two guards over the same history (each stage of the E1 harness is a new process, so the history is a plain list kept in the job state):
  repeat     the rework call (only the Captain's hint can change it) keeps ending in the same failure signature -> generic_repeat
  ping_pong  answering failure A gives B and answering B gives A -> ping_pong
A new Captain hint changes the call, so the next generation is allowed again.
"""
import hashlib
import re

from ..jobs.loop_guard import LoopGuard, normalize_output

REPEAT_THRESHOLD = 3          # stuck before the 3rd generation that would end in the same failure as the 2 before
PING_PONG_THRESHOLD = 4       # stuck before the 5th generation when 4 failures alternate A, B, A, B
MAX_ENTRIES = 24
START = "start"

_FILE = re.compile(r"[\w./\\:~-]+\.py(?::\d+)?")
_LINE = re.compile(r"\bline \d+\b")
_ERROR_LINE = re.compile(r"^(?:\w+\.)*\w*(?:Error|Exception|Warning)\b")
_TEST_LINE = re.compile(r"^(?:FAIL|ERROR):\s*(\w+)")


def _h(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _clean(text):
    text = _FILE.sub("<file>", text)
    text = _LINE.sub("line", text)
    return normalize_output(text)            # hex addresses, timestamps, durations, ids: one shared normaliser (loop_guard)


def failure_signature(kind, text=""):
    """Identity of a failure, stable across candidates: 16 hex characters, prefixed with its kind ("test:", "gen:", "review:").

    kind "test": the feedback text of a failed VM test. Kept: the REPRO lines of the reproduction harness without their " at ..." tail
    (test id, input, expected, got), the ids of failing tests (FAIL:/ERROR: lines) and exception lines. Dropped: file names, line
    numbers, hex addresses and the traceback frames, because they move from candidate to candidate. Lines are sorted and de-duplicated.
    kind "gen": `text` is the error class of a failed generation (for example model_answer_truncated). kind "review": any rejected review."""
    if kind == "gen":
        word = re.match(r"\w+", str(text).strip().lower())      # the error class; a detail after ":" differs from run to run
        return "gen:" + _h(word.group(0) if word else str(text).strip().lower())
    if kind == "review":
        return "review:" + _h("fail")
    keep = set()
    for raw in str(text).splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("REPRO"):
            line = line.split(" at ", 1)[0]
            keep.add(_clean(line))
            continue
        m = _TEST_LINE.match(line)
        if m:
            keep.add("FAIL " + m.group(1))
        elif _ERROR_LINE.match(line):
            keep.add(_clean(line))
    return "test:" + _h("\n".join(sorted(keep)))


def candidate_key(changes):
    """Identity of a candidate: 16 hex characters over every changed file's path and its content with line endings unified and
    whitespace runs collapsed. Comments and code are kept, so a one-character change is a different candidate. `changes` is the list
    of {"path", "content"} the harness keeps; None or empty gives the key of nothing."""
    files = {}
    for change in changes or []:
        files[str(change.get("path"))] = " ".join(str(change.get("content", "")).replace("\r\n", "\n").split())
    return _h("\n".join(f"{path}\0{files[path]}" for path in sorted(files)))


def same_as_earlier(candidate, state):
    """What the candidate is a repeat of: "the previous attempt" or "attempt N" (N counts `discarded_generations` from 1), else None.
    Only exact identity after whitespace normalisation counts: a near-identical candidate can still fix a failing test."""
    if not candidate:
        return None
    key = candidate_key(candidate)
    if state.get("previous_candidate") and candidate_key(state["previous_candidate"]) == key:
        return "the previous attempt"
    for number, discarded in enumerate(state.get("discarded_generations") or [], 1):
        if discarded.get("candidate") and candidate_key(discarded["candidate"]) == key:
            return f"attempt {number}"
    return None


def hint_key(hint):
    return _h(hint.strip())[:8] if isinstance(hint, str) and hint.strip() else None


class ReworkWatch:
    """History of rework attempts. `entries` is the persisted list: [{"hint", "for", "outcome"}] (newest last, at most MAX_ENTRIES)."""

    def __init__(self, entries=None, repeat_threshold=REPEAT_THRESHOLD, ping_pong_threshold=PING_PONG_THRESHOLD):
        self.entries = [dict(e) for e in (entries or [])][-MAX_ENTRIES:]
        self.repeat_threshold = repeat_threshold
        self.ping_pong_threshold = ping_pong_threshold

    def _guards(self):
        repeat = LoopGuard(guarded={"rework"}, repeat_threshold=self.repeat_threshold, ping_pong_threshold=10 ** 6, normalize=False)
        pingpong = LoopGuard(guarded={"rework_after"}, repeat_threshold=10 ** 6, ping_pong_threshold=self.ping_pong_threshold, normalize=False)
        for e in self.entries:
            repeat.record("rework", {"hint": e["hint"]}, e["outcome"], True)
            pingpong.record("rework_after", {"for": e["for"], "hint": e["hint"]}, e["outcome"], True)
        return repeat, pingpong

    @property
    def last_outcome(self):
        return self.entries[-1]["outcome"] if self.entries else START

    def check(self, hint=None):
        """Judge the generation that is about to start. {"stuck", "detector", "count", "message", "repeated_failure"}."""
        hint = hint_key(hint)
        repeat, pingpong = self._guards()
        out = repeat.check("rework", {"hint": hint})
        if not out["stuck"]:
            out = pingpong.check("rework_after", {"for": self.last_outcome, "hint": hint})
        out = dict(out)
        out["repeated_failure"] = self.last_outcome if out["stuck"] else None
        if out["stuck"]:
            what = "the same failure" if out["detector"] == "generic_repeat" else "two failures that replace each other"
            out["message"] = f"rework stalled: {out['count']} attempts ending in {what}; give a hint, change coder or spec, or stop"
        return out

    def record(self, outcome, hint=None):
        """Remember how the attempt just made ended (a failure signature)."""
        self.entries.append({"hint": hint_key(hint), "for": self.last_outcome, "outcome": outcome})
        del self.entries[:-MAX_ENTRIES]

    @classmethod
    def load(cls, state, **kw):
        return cls(state.get("rework_watch"), **kw)

    def save(self, state):
        state["rework_watch"] = list(self.entries)
