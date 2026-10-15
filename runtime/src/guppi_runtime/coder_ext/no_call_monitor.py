import re
import json

_UNUSED_RE = re.compile(r'<unused\d+>')

_TEXTS = {
    'empty': "Your answer was empty. Continue the task: make the next tool call.",
    'garbage': "Your answer was unreadable. Continue the task with a normal tool call.",
    'thinking_only': "You only thought and did not act. Make the next tool call now.",
}


def _extract_fences(content):
    result = []
    parts = content.split('\n')
    i = 0
    while i < len(parts):
        stripped = parts[i].strip()
        if stripped.startswith('```'):
            lang = stripped[3:].strip()
            if lang in ('', 'json'):
                fence_lines = []
                i += 1
                while i < len(parts):
                    if parts[i].strip().startswith('```'):
                        i += 1
                        break
                    fence_lines.append(parts[i])
                    i += 1
                result.append('\n'.join(fence_lines))
            else:
                i += 1
        else:
            i += 1
    return result


def _parse_candidate(candidate, tool_names):
    results = []
    try:
        parsed = json.loads(candidate)
    except ValueError:
        return results
    if isinstance(parsed, list):
        items = parsed
    else:
        items = [parsed]
    tool_names_set = set(tool_names)
    for obj in items:
        if not isinstance(obj, dict):
            continue
        name = obj.get('name')
        if name not in tool_names_set:
            continue
        args = obj.get('arguments', obj.get('parameters', {}))
        if not isinstance(args, dict):
            continue
        results.append((name, args))
    return results


def extract_calls(content, tool_names):
    if not isinstance(content, str):
        return []
    fences = _extract_fences(content)
    if fences:
        candidates = fences
    else:
        candidates = [content.strip()]
    result = []
    for candidate in candidates:
        result.extend(_parse_candidate(candidate, tool_names))
    return result


def _has_reasoning(message):
    rc = message.get('reasoning_content')
    return isinstance(rc, str) and rc.strip() != ''


def classify(message, tool_names):
    return _classify_and_extract(message, tool_names)[0]


def _classify_and_extract(message, tool_names):
    if not isinstance(message, dict):
        message = {}
    tool_calls = message.get('tool_calls')
    if isinstance(tool_calls, list) and len(tool_calls) > 0:
        return 'call', []
    content = message.get('content')
    if not isinstance(content, str):
        content = ''
    if _UNUSED_RE.search(content):
        return 'garbage', []
    calls = extract_calls(content, tool_names)
    if calls:
        return 'text_call', calls
    if not content.strip():
        if _has_reasoning(message):
            return 'thinking_only', []
        return 'empty', []
    return 'prose', []


def _check_max_corrections(val):
    if isinstance(val, bool) or not isinstance(val, int) or val < 0:
        raise ValueError("max_corrections must be an int >= 0")


def _text_for_kind(kind, terminal):
    return _TEXTS.get(kind, "Do not answer in text. Use a tool call: continue the work, or call {} when everything is done.".format(terminal))


class NoCallMonitor:
    def __init__(self, tool_names, max_corrections=2, terminal="submit_result"):
        _check_max_corrections(max_corrections)
        self.tool_names = tool_names
        self.max_corrections = max_corrections
        self.terminal = terminal
        self._consecutive_corrections = 0

    def feed(self, message):
        kind, calls = _classify_and_extract(message, self.tool_names)
        if kind == 'call':
            self._consecutive_corrections = 0
            return {"kind": "call", "action": "continue", "calls": [], "text": None}
        if kind == 'text_call':
            self._consecutive_corrections = 0
            return {"kind": "text_call", "action": "run", "calls": calls, "text": None}
        if self._consecutive_corrections < self.max_corrections:
            self._consecutive_corrections += 1
            text = _text_for_kind(kind, self.terminal)
            return {"kind": kind, "action": "correct", "calls": [], "text": text}
        return {"kind": kind, "action": "stop", "calls": [], "text": None}
