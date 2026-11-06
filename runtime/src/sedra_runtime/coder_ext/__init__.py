from . import read_tracker
from . import tool_cards
from . import coder_cards
from . import fuzzy_edit
from . import syntax_note
from . import think_guard
from . import no_call_monitor
from . import replay_log
from . import result_pruner
from . import churn_guard

ALL = ("e01", "e02", "e03", "e04", "e05", "e07", "e08", "e09", "e12")


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def parse_enabled(text):
    if text is None or text.strip().lower() in ("", "none"):
        return frozenset()
    if text.strip().lower() == "all":
        return frozenset(ALL)
    items = [x.strip().lower() for x in text.split(",")]
    result = []
    for item in items:
        if item == "":
            continue
        if item not in ALL:
            raise ValueError(f"Unknown item: {item}")
        result.append(item)
    return frozenset(result)


def shown_range(text, start, end, per_read=150):
    n = len(text.splitlines())
    s = start if _is_int(start) else None
    e = end if _is_int(end) else None
    if n <= per_read and s is None and e is None:
        return (1, n)
    first = max(1, s) if s is not None else 1
    if e is not None:
        last = min(n, e, first + per_read - 1)
    else:
        last = min(n, first + per_read - 1)
    return (first, last)


class CoderExtensions:
    def __init__(self, enabled="", think_limit=2000, family="qwen", max_corrections=2, terminal="submit_result", tool_names=(), prune_at=0.5, window=32768, cards=None, rules=None):
        if not _is_int(think_limit) or think_limit <= 0:
            raise ValueError("think_limit must be an int > 0")
        if family not in ("qwen", "gptoss", "other"):
            raise ValueError("family must be one of 'qwen', 'gptoss', 'other'")
        if not _is_int(max_corrections) or max_corrections < 0:
            raise ValueError("max_corrections must be an int >= 0")
        if not (0 < prune_at < 1):
            raise ValueError("prune_at must satisfy 0 < prune_at < 1")
        if not _is_int(window) or window <= 0:
            raise ValueError("window must be an int > 0")
        self.enabled = parse_enabled(enabled)
        self.think_limit = think_limit
        self.family = family
        self.max_corrections = max_corrections
        self.terminal = terminal
        self.tool_names = tool_names
        self.prune_at = prune_at
        self.window = window
        self.tracker = read_tracker.ReadTracker() if "e01" in self.enabled else None
        self.cards = tool_cards.CardPicker(cards or coder_cards.CARDS, rules or coder_cards.RULES) if "e07" in self.enabled else None
        self._think = think_guard.ThinkGuard(think_limit, family) if "e02" in self.enabled else None
        self._monitor = no_call_monitor.NoCallMonitor(tool_names, max_corrections, terminal) if "e03" in self.enabled else None
        self._recorder = None
        self._churn = churn_guard.ChurnGuard() if "e12" in self.enabled else None

    def is_on(self, key):
        return key in self.enabled

    def _check_edit(self, name, path, current):
        v = self.tracker.check_edit(path, current)
        if v == "unread":
            refuse = name + " refused: you have not read " + path + " in this run. Read it first with read_file {\"path\": \"" + path + "\"}, then copy old exactly from what you read."
            return {"refuse": refuse, "note": None}
        if v == "changed":
            return {"refuse": None, "note": "(note: " + path + " changed since you last read it; the edit was applied because old still matched)"}
        return {"refuse": None, "note": None}

    def _check_overwrite(self, path, current):
        v = self.tracker.check_overwrite(path, current)
        if v == "unread":
            return {"refuse": "write_file refused: " + path + " exists and you have not read it. Read it with read_file first, or change it with edit_file.", "note": None}
        if v == "changed":
            return {"refuse": "write_file refused: " + path + " changed since you read it. Read it again first.", "note": None}
        if v == "partial":
            seen = self.tracker.seen(path)
            ranges = ", ".join(str(a) + "-" + str(b) for a, b in seen) if seen else "none"
            n = len(current.splitlines())
            return {"refuse": "write_file refused: you have only seen lines " + ranges + " of " + path + " (" + str(n) + " lines). Read the rest first, or change it with edit_file.", "note": None}
        return {"refuse": None, "note": None}

    def before_tool(self, name, args, current):
        if not self.is_on("e01"):
            return {"refuse": None, "note": None}
        if not isinstance(args, dict):
            return {"refuse": None, "note": None}
        path = args.get("path")
        if not isinstance(path, str):
            return {"refuse": None, "note": None}
        if current is None:
            return {"refuse": None, "note": None}
        if name in ("edit_file", "append_file"):
            return self._check_edit(name, path, current)
        if name == "write_file":
            return self._check_overwrite(path, current)
        return {"refuse": None, "note": None}

    def edit_fallback(self, text, old, new):
        if not self.is_on("e08"):
            return None
        result = fuzzy_edit.apply(text, old, new)
        if isinstance(result, dict) and "text" in result:
            return result
        return None

    def after_tool(self, name, args, ok, result, current):
        parts = []
        if self.is_on("e01") and ok:
            self._bookkeeping(name, args, current)
        if self.is_on("e09") and ok and name in ("write_file", "append_file", "edit_file"):
            sn = syntax_note.note(args.get("path") if isinstance(args, dict) else None, current)
            if sn is not None:
                parts.append(sn)
        if self.is_on("e07") and not ok:
            ca = self.cards.after(name, result) if self.cards is not None else None
            if ca is not None:
                parts.append(ca)
        if self._churn is not None and ok:
            warning = self._churn.feed(name, args, result + chr(10) + chr(10).join(parts))
            if warning is not None:
                parts.append(warning)
        return "\n".join(parts)

    def _bookkeeping(self, name, args, current):
        if not isinstance(args, dict):
            return
        if name == "read_file" and isinstance(current, str):
            self.tracker.note_read(args.get("path"), current, *shown_range(current, args.get("start"), args.get("end")))
            return
        if name == "write_file":
            self.tracker.note_write(args.get("path"), current)
        if name == "append_file":
            self.tracker.note_write(args.get("path"), current)
        if name == "edit_file":
            self.tracker.note_edit(args.get("path"), current)
        if name == "delete_file":
            self.tracker.forget(args.get("path"))
        if name == "move_file":
            self.tracker.move(args.get("source"), args.get("destination"))

    def after_answer(self, data, has_calls):
        notes = []
        if self._think is not None:
            res = self._think.feed(data)
            if res.get("text") is not None:
                notes.append(res["text"])
        if has_calls:
            return {"notes": notes, "action": "continue", "calls": []}
        if self._monitor is not None:
            choices = data.get("choices", []) if isinstance(data, dict) else []
            first = choices[0] if choices else {}
            message = first.get("message", {}) if isinstance(first, dict) else {}
            res = self._monitor.feed(message)
            text = res.get("text")
            if text is not None:
                notes.append(text)
            return {"notes": notes, "action": res.get("action", "stop"), "calls": res.get("calls", [])}
        return {"notes": notes, "action": "stop", "calls": []}

    def request_patch(self):
        if self._think is not None:
            return self._think.patch()
        return {}

    def prune(self, messages, prompt_tokens):
        if self.is_on("e05") and prompt_tokens > self.prune_at * self.window:
            return result_pruner.prune(messages)
        return messages

    def wrap_post(self, post, mode=None, records=None):
        if mode is None or not self.is_on("e04"):
            return post
        if mode == "record":
            self._recorder = replay_log.Recorder(post)
            return self._recorder
        if mode == "replay":
            return replay_log.Player(records or [])
        raise ValueError("invalid mode")

    def records(self):
        if self._recorder is None:
            return []
        return self._recorder.records
