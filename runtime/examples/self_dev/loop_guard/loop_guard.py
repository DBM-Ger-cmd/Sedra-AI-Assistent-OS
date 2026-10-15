"""Loop guard: detects an agent that keeps repeating itself. Read-only: it reports, it never stops anything itself.

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

HISTORY_SIZE = 24             # only the newest 24 recorded calls are kept
REPEAT_THRESHOLD = 4          # generic_repeat: stuck when this call would be the 4th identical one
PING_PONG_THRESHOLD = 6       # ping_pong: stuck when this call would be the 6th alternating one
OUTPUT_LIMIT = 2000           # only the first 2000 characters of an output count for the outcome
GUARDED_TOOLS = frozenset({
    "fs_read", "read_file", "list_directory", "web_search", "web_fetch", "shell_exec", "knowledge_search",
})


def signature(tool_name, args):
    """Identity of a call: f"{tool_name}:{h}" where h is the first 16 hex characters of the SHA-256 of the canonical JSON of
    `args` (json.dumps with sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str, encoded as UTF-8).
    The order of the keys in `args` must not change the signature; different values must."""
    raise NotImplementedError


def outcome_hash(output, is_error):
    """Identity of a result: the first 16 hex characters of the SHA-256 of the canonical JSON (same rules as in `signature`)
    of {"is_error": bool(is_error), "output": str(output)[:OUTPUT_LIMIT]}.
    Outputs that differ only after OUTPUT_LIMIT characters are the same outcome; an error and a success never are."""
    raise NotImplementedError


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
                 ping_pong_threshold=PING_PONG_THRESHOLD):
        raise NotImplementedError

    def record(self, tool_name, args, output, is_error=False):
        raise NotImplementedError

    def check(self, tool_name, args):
        raise NotImplementedError

    def reset(self):
        raise NotImplementedError

    @property
    def recorded_count(self):
        raise NotImplementedError
