"""Loop guard (written by the assistant, not by GUPPI, after the E1 attempt of 2026-10-04 did not get a reviewed candidate; see docs/LOOP_GUARD_E1_ATTEMPT_2026-10-04.md): detects an agent that keeps repeating itself. Read-only: it reports, it never stops anything itself.

Why (2026-10-03): a rework coder looped through 20000 tokens and the uix_window job ran 12 generations, several with the same cause.
Nothing noticed that the same call was made again with the same result. The caller records every call and its outcome and asks
`check` BEFORE the next call; on "stuck" the caller changes something (new context, other model, ask the Captain) instead of repeating.

Two patterns:
  generic_repeat - the same call (tool + arguments) keeps returning the same outcome.
  ping_pong      - two different calls alternate (A B A B ...) and every repeat of each returns the same outcome as before.

Only the standard library may be used. Only calls of guarded tools are judged; others are never stuck.
"""
import hashlib
import json
import re

HISTORY_SIZE = 24
REPEAT_THRESHOLD = 4
PING_PONG_THRESHOLD = 6
OUTPUT_LIMIT = 2000
GUARDED_TOOLS = frozenset({
    "fs_read", "read_file", "list_directory", "web_search", "web_fetch", "shell_exec", "knowledge_search",
})


def _h(v):
    raw = json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def signature(tool_name, args):
    """Identity of a call: f"{tool_name}:{h}" where h is the first 16 hex characters of the SHA-256 of the canonical JSON of
    `args` (json.dumps with sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str, encoded as UTF-8).
    The order of the keys in `args` must not change the signature; different values must."""
    return f"{tool_name}:{_h(args)}"


# Host-generated volatility only (lesson of StarNet's tool-progress-guard, 2026-10-04): ordinary numbers and words stay, so different
# results stay different. Order matters: timestamps and UUIDs before the shorter hex and number patterns.
_VOLATILE = (
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<time>"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<uuid>"),
    (re.compile(r"\b(SDJ|SBX|HG|CAND|PRJ|KN|M)-[0-9A-Fa-f]{8,}\b"), r"\1-<id>"),
    (re.compile(r"\bEVT-\d+\b"), "EVT-<id>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "0x<hex>"),
    (re.compile(r"\b[0-9a-fA-F]{12,}\b"), lambda m: "<hex>" if len(set(m.group(0).lower())) >= 6 else m.group(0)),
    (re.compile(r"\b\d+(?:\.\d+)?\s?(?:ms|s|sec|secs|seconds|min|minutes)\b"), "<duration>"),
    (re.compile(r"\bpid[ =:]*\d+\b", re.IGNORECASE), "pid <n>"),
)


def normalize_output(text):
    """The text with its host-generated volatility replaced by fixed markers, and whitespace runs collapsed to one space:
    ISO-8601 timestamps -> <time>, UUIDs -> <uuid>, GUPPI ids (SDJ-, SBX-, HG-, CAND-, PRJ-, KN-, M- plus 8 or more hex digits, EVT- plus
    digits) keep their prefix -> SDJ-<id>, 0x addresses -> 0x<hex>, hex or digit strings of 12 or more -> <hex>, durations such as
    1.2s, 350ms, 3 min -> <duration>, `pid 123` -> pid <n>. Everything else, ordinary numbers included, is left as it is."""
    text = str(text)
    for pattern, marker in _VOLATILE:
        text = pattern.sub(marker, text)
    return " ".join(text.split())


def _outcome_hash(output, is_error, normalize):
    text = normalize_output(output) if normalize else str(output)
    return _h({"is_error": bool(is_error), "output": text[:OUTPUT_LIMIT]})


def outcome_hash(output, is_error):
    """Identity of a result: the first 16 hex characters of the SHA-256 of the canonical JSON (same rules as in `signature`)
    of {"is_error": bool(is_error), "output": normalize_output(output)[:OUTPUT_LIMIT]}. The output is normalised BEFORE it is cut.
    Outputs that differ only after OUTPUT_LIMIT characters, or only in timestamps, durations or ids, are the same outcome;
    an error and a success never are."""
    return _outcome_hash(output, is_error, True)


class LoopGuard:
    """Sliding window over the recorded calls.

    record(tool_name, args, output, is_error=False): remember one finished call (its signature and outcome_hash) and drop the
    oldest entries so that at most `history_size` (the constructor argument) remain. Unguarded tools are remembered too.

    check(tool_name, args) -> dict: judge the call that is ABOUT to be made; it changes nothing. Always returns
    {"stuck": bool, "detector": None | "generic_repeat" | "ping_pong", "count": int, "message": str}.
    Not stuck: {"stuck": False, "detector": None, "count": 0, "message": ""}. A tool that is not in `guarded` is never stuck.

    generic_repeat is tested first. Let s be the signature of the call. Walk the recorded entries from the newest back, looking
    only at entries with signature s (other entries in between are skipped). The newest of them sets the reference outcome; count
    how many consecutive ones (newest first) have that same outcome and stop at the first that differs. Call that number streak
    (0 when there is no entry with s). The call is stuck when streak + 1 >= repeat_threshold; count is streak + 1 and the message
    contains the tool name and the count.

    ping_pong is tested second. Let `last` be the newest entry and `other` the signature of the newest earlier entry whose
    signature differs from last's and whose tool is guarded. It applies only if the new call's signature equals `other`.
    Count alt = how many entries from the newest back alternate strictly last, other, last, other, ... (the newest entry is
    "last"; stop at the first entry that breaks the pattern). It needs alt >= 2. It is a ping-pong only if no progress was made:
    among those alt entries all entries with last's signature have one single outcome, and all entries with other's signature
    have one single outcome. The call is stuck when alt + 1 >= ping_pong_threshold; count is alt + 1 and the message contains
    the count.

    Tool names are arbitrary strings and may contain ":" (for example "mcp:read"). Keep the tool name with every recorded entry;
    never recover it by splitting a signature. "Guarded" is always decided from the stored tool name.

    reset(): forget everything. recorded_count (read-only property): how many entries are remembered right now (0 after reset, never more
    than the `history_size` constructor argument, which is only the maximum and is not exposed as an attribute)."""

    def __init__(self, guarded=GUARDED_TOOLS, history_size=HISTORY_SIZE, repeat_threshold=REPEAT_THRESHOLD,
                 ping_pong_threshold=PING_PONG_THRESHOLD, normalize=True):
        self._norm = bool(normalize)         # False: the caller's outputs are already canonical (for example failure signatures)
        self._guarded = frozenset(guarded)
        self._size = history_size
        self._rep = repeat_threshold
        self._pp = ping_pong_threshold
        self._h = []

    def record(self, tool_name, args, output, is_error=False):
        self._h.append((tool_name, signature(tool_name, args), _outcome_hash(output, is_error, self._norm)))
        del self._h[:-self._size]

    def _ok(self):
        return {"stuck": False, "detector": None, "count": 0, "message": ""}

    def check(self, tool_name, args):
        if tool_name not in self._guarded:
            return self._ok()
        sig = signature(tool_name, args)
        streak, ref = 0, None
        for _t, s, o in reversed(self._h):
            if s != sig:
                continue
            if ref is None:
                ref, streak = o, 1
            elif o == ref:
                streak += 1
            else:
                break
        if streak + 1 >= self._rep:
            return {"stuck": True, "detector": "generic_repeat", "count": streak + 1,
                    "message": f"{tool_name} was called {streak + 1} times with identical arguments and result"}
        if self._h:
            last = self._h[-1][1]
            other = next((s for t, s, _o in reversed(self._h[:-1]) if s != last and t in self._guarded), None)
            if other is not None and sig == other:
                alt = 0
                for t, s, o in reversed(self._h):
                    if s != (last if alt % 2 == 0 else other):
                        break
                    alt += 1
                if alt >= 2:
                    tail = self._h[-alt:]
                    la = {o for t, s, o in tail if s == last}
                    ot = {o for t, s, o in tail if s == other}
                    if len(la) == 1 and len(ot) == 1 and alt + 1 >= self._pp:
                        return {"stuck": True, "detector": "ping_pong", "count": alt + 1,
                                "message": f"{alt + 1} alternating calls without new information"}
        return self._ok()

    def level(self, tool_name, args, warn_margin=1):
        """Like `check`, plus a warning step before the block: {"level": "ok" | "warn" | "stuck", ...the check fields}.
        "warn" means the same call would be stuck if the thresholds were `warn_margin` lower (default: one repeat earlier), so the
        caller can tell the model it is repeating itself while it still may continue. The repeat threshold is never probed below 2
        and the ping-pong threshold never below 3, so a warning needs at least one earlier occurrence."""
        out = self.check(tool_name, args)
        if out["stuck"]:
            return {**out, "level": "stuck"}
        probe = LoopGuard(self._guarded, self._size, max(2, self._rep - warn_margin), max(3, self._pp - warn_margin), self._norm)
        probe._h = list(self._h)
        warn = probe.check(tool_name, args)
        if warn["stuck"]:
            return {**warn, "level": "warn", "message": "warning: " + warn["message"]}
        return {**out, "level": "ok"}

    def reset(self):
        self._h.clear()

    @property
    def recorded_count(self):
        return len(self._h)
