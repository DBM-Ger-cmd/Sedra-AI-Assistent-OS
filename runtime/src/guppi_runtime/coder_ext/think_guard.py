import copy


def _is_real_int(val):
    return isinstance(val, int) and not isinstance(val, bool)


def reasoning_tokens(data):
    if not isinstance(data, dict):
        return 0
    usage = data.get("usage")
    if isinstance(usage, dict):
        details = usage.get("completion_tokens_details")
        if isinstance(details, dict):
            val = details.get("reasoning_tokens")
            if _is_real_int(val) and val >= 0:
                return val
    choices = data.get("choices")
    if not isinstance(choices, list) or len(choices) == 0:
        return 0
    first = choices[0]
    if not isinstance(first, dict):
        return 0
    message = first.get("message")
    if not isinstance(message, dict):
        return 0
    reasoning_content = message.get("reasoning_content")
    if isinstance(reasoning_content, str):
        return len(reasoning_content) // 4
    return 0


class ThinkGuard:
    _VALID_FAMILIES = ("qwen", "gptoss", "other")

    def __init__(self, limit=2000, family="qwen", max_notes=1):
        if not _is_real_int(limit) or limit <= 0:
            raise ValueError("limit must be an int > 0")
        if not isinstance(family, str) or family not in self._VALID_FAMILIES:
            raise ValueError("family must be one of 'qwen', 'gptoss', 'other'")
        if not _is_real_int(max_notes) or max_notes < 0:
            raise ValueError("max_notes must be an int >= 0")
        self.limit = limit
        self.family = family
        self.max_notes = max_notes
        self._notes_given = 0
        self._switched = False

    _FAMILY_PATCH = {
        "qwen": {"chat_template_kwargs": {"enable_thinking": False}},
        "gptoss": {"chat_template_kwargs": {"reasoning_effort": "low"}},
    }

    def _patch_value(self):
        return self._FAMILY_PATCH.get(self.family, {})

    def feed(self, data):
        if self._switched:
            return {"action": "ok", "text": None}
        n = reasoning_tokens(data)
        if n <= self.limit:
            return {"action": "ok", "text": None}
        if self._notes_given < self.max_notes:
            self._notes_given += 1
            return {"action": "note", "text": f"You thought for {n} tokens. Stop deliberating: decide now and make the next tool call."}
        self._switched = True
        return {"action": "think_less", "text": None}

    def patch(self):
        if not self._switched:
            return {}
        return copy.deepcopy(self._patch_value())
