import re

INVISIBLE = {0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF}
SOURCE = re.compile(r"[a-z0-9_.:-]{1,40}")
FLAGS = (
    ("ignore_instructions", re.compile(r"\b(ignore|disregard|forget)\s+(all\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions|rules|messages)", re.I)),
    ("role_claim", re.compile(r"^\s*(system|assistant|developer)\s*:", re.I | re.M)),
    ("tool_call", re.compile(r"<tool_call>|\"function_call\"|<\|im_start\|>", re.I)),
    ("approve_gate", re.compile(r"\bapprove\s+(the\s+)?gate\b|\bHG-[0-9A-F]{8}\b", re.I)),
    ("secret_request", re.compile(r"\b(api[_ -]?key|password|access[_ ]token|secret[_ ]key)\b", re.I)),
)
TYPES = {"str": str, "int": int, "bool": bool}


def clean(text):
    return "".join(ch for ch in text if (ord(ch) >= 32 or ch in "\n\t") and ord(ch) != 127 and ord(ch) not in INVISIBLE)


def untrusted(text, source, limit=4000):
    if not isinstance(text, str):
        raise ValueError("text")
    if not isinstance(source, str) or not SOURCE.fullmatch(source):
        raise ValueError("source")
    body = clean(text)
    cut = len(body) - limit
    if cut > 0:
        body = body[:limit] + f"\n[truncated {cut} chars]"
    body = re.sub(r"</untrusted", "</untrusted_", body, flags=re.I)
    return f'<untrusted source="{source}">\n{body}\n</untrusted>'


def flags(text):
    text = clean(text) if isinstance(text, str) else ""
    return [name for name, pattern in FLAGS if pattern.search(text)]


def _field_errors(name, value, rule):
    kind = TYPES[rule["type"]]
    if type(value) is not kind:
        return [f"type:{name}"]
    if kind is str and "max" in rule and len(value) > rule["max"]:
        return [f"too_long:{name}"]
    if kind is int and "max" in rule and value > rule["max"]:
        return [f"too_large:{name}"]
    if kind is str and "pattern" in rule and not re.fullmatch(rule["pattern"], value):
        return [f"pattern:{name}"]
    return []


def check_request(tool, args, schema):
    if tool not in schema:
        return ["unknown_tool"]
    if not isinstance(args, dict):
        return ["args"]
    fields = schema[tool]
    errors = [f"unknown_field:{k}" for k in sorted(args) if k not in fields]
    for name in sorted(fields):
        rule = fields[name]
        if name not in args:
            if rule.get("required"):
                errors.append(f"missing:{name}")
            continue
        errors += _field_errors(name, args[name], rule)
    return errors


def rate_ok(history, now, limit=30, window=60):
    return sum(1 for t in history if now - window < t <= now) < limit
