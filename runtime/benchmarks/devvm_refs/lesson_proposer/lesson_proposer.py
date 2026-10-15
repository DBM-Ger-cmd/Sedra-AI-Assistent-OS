import re

TABLE = [
    ("reserved_name", r"potential_credential_file"),
    ("placeholder_write", r"\[written: \d+ characters|\[\.\.\.cut\.\.\.\]"),
    ("missing_module", r"ModuleNotFoundError: No module named '([A-Za-z0-9_.]+)"),
    ("syntax_error", r"SyntaxError"),
]
TEXTS = {
    "reserved_name": "Do not name files token, secret or password: the sandbox refuses them as credential files. Choose a neutral name such as usage_meter.py.",
    "placeholder_write": "Never repeat a write call from your shortened history, its text is only a placeholder. Read the file with read_file and write the real content.",
    "syntax_error": "A file with a syntax error cannot be imported. After every write call check_syntax on the file before you go on.",
}


def signatures(text):
    if not isinstance(text, str):
        return []
    return [key for key, pattern in TABLE if re.search(pattern, text)]


def _norm(text):
    return " ".join(str(text).lower().split())


def _lessons(text):
    out = []
    for key in signatures(text):
        if key == "missing_module":
            for name in re.findall(TABLE[2][1], text):
                out.append("The module '" + name.split(".")[0] + "' is not available in the sandbox. Use only the Python standard library and the modules of the project.")
        else:
            out.append(TEXTS[key])
    return out


def propose(failures, run_id, known=None, limit=3):
    if not isinstance(failures, list):
        return []
    seen = {_norm(k) for k in (known or [])}
    result = []
    for entry in failures:
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
            continue
        stage = entry.get("stage") if isinstance(entry.get("stage"), str) else "?"
        for lesson in _lessons(entry["text"]):
            if _norm(lesson) in seen:
                continue
            seen.add(_norm(lesson))
            result.append({"text": lesson, "source": "run:" + run_id + ":" + stage})
    return result[:limit]
