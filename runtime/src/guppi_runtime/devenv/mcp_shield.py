import re

_INVISIBLE = set(
    "\u200B\u200C\u200D\u200E\u200F\u202A\u202B\u202C\u202D\u202E"
    "\u2066\u2067\u2068\u2069\uFEFF"
)

_CONTROL_RE = re.compile(
    r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]'
)


def _clean(text):
    body = _CONTROL_RE.sub('', text)
    body = ''.join(ch for ch in body if ch not in _INVISIBLE)
    return body


def clean(text):
    if not isinstance(text, str):
        return text
    return _clean(text)


def flags(text):
    if not isinstance(text, str):
        return []
    body = clean(text)
    patterns = [
        ("ignore_instructions", re.compile(
            r'\b(ignore|disregard|forget)\s+(all\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions|rules|messages)',
            re.IGNORECASE)),
        ("role_claim", re.compile(
            r'^\s*(system|assistant|developer)\s*:',
            re.IGNORECASE | re.MULTILINE)),
        ("tool_call", re.compile(
            r'<tool_call>|"function_call"|<\|im_start\|>',
            re.IGNORECASE)),
        ("approve_gate", re.compile(
            r'\bapprove\s+(the\s+)?gate\b|\bHG-[0-9A-F]{8}\b',
            re.IGNORECASE)),
        ("secret_request", re.compile(
            r'\b(api[_ -]?key|password|access[_ ]token|secret[_ ]key)\b',
            re.IGNORECASE)),
    ]
    result = []
    for name, pat in patterns:
        if pat.search(body):
            result.append(name)
    return result


def untrusted(text, source, limit=4000):
    if not isinstance(text, str):
        raise ValueError("text")
    if not isinstance(source, str) or not re.fullmatch(r'[a-z0-9_.:-]{1,40}', source):
        raise ValueError("source")
    body = _clean(text)
    if len(body) > limit:
        cut = len(body) - limit
        body = body[:limit] + '\n[truncated ' + str(cut) + ' chars]'
    body = re.sub(r'</untrusted', '</untrusted_', body, flags=re.IGNORECASE)
    return '<untrusted source="' + source + '">\n' + body + '\n</untrusted>'


def check_request(tool, args, schema):
    errors = []
    if tool not in schema:
        return ["unknown_tool"]
    if not isinstance(args, dict):
        return ["args"]
    tool_schema = schema[tool]
    known_fields = set(tool_schema.keys())
    for key in sorted(args.keys()):
        if key not in known_fields:
            errors.append("unknown_field:" + key)
    for field_name in sorted(tool_schema.keys()):
        field_schema = tool_schema[field_name]
        field_type = field_schema["type"]
        is_required = field_schema.get("required", False)
        if field_name not in args:
            if is_required:
                errors.append("missing:" + field_name)
            continue
        value = args[field_name]
        if field_type == "str":
            if not isinstance(value, str):
                errors.append("type:" + field_name)
                continue
            max_len = field_schema.get("max")
            if max_len is not None and len(value) > max_len:
                errors.append("too_long:" + field_name)
                continue
            pattern = field_schema.get("pattern")
            if pattern is not None and re.fullmatch(pattern, value) is None:
                errors.append("pattern:" + field_name)
                continue
        elif field_type == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append("type:" + field_name)
                continue
            max_val = field_schema.get("max")
            if max_val is not None and value > max_val:
                errors.append("too_large:" + field_name)
                continue
        elif field_type == "bool":
            if not isinstance(value, bool):
                errors.append("type:" + field_name)
                continue
    return errors


def rate_ok(history, now, limit=30, window=60):
    count = sum(1 for t in history if now - window < t <= now)
    return count < limit
