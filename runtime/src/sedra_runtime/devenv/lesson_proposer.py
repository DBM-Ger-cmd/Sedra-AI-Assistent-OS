import re


def _check_reserved_name(text):
    return bool(re.search(r'potential_credential_file', text))


def _check_placeholder_write(text):
    return bool(re.search(r'\[written: \d+ characters', text)) or bool(re.search(r'\[\.\.\.cut\.\.\.\]', text))


def _check_missing_module(text):
    return bool(re.search(r"ModuleNotFoundError: No module named '", text))


def _check_syntax_error(text):
    return bool(re.search(r'SyntaxError', text))


def _get_missing_module_name(text):
    return re.findall(r"ModuleNotFoundError: No module named '([A-Za-z0-9_.]+)", text)


def signatures(text):
    if not isinstance(text, str):
        return []
    result = []
    if _check_reserved_name(text):
        result.append("reserved_name")
    if _check_placeholder_write(text):
        result.append("placeholder_write")
    if _check_missing_module(text):
        result.append("missing_module")
    if _check_syntax_error(text):
        result.append("syntax_error")
    return result


def propose(failures, run_id, known=None, limit=3):
    if not isinstance(failures, list):
        return []
    lesson_texts = {
        "reserved_name": "Do not name files token, secret or password: the sandbox refuses them as credential files. Choose a neutral name such as usage_meter.py.",
        "placeholder_write": "Never repeat a write call from your shortened history, its text is only a placeholder. Read the file with read_file and write the real content.",
        "syntax_error": "A file with a syntax error cannot be imported. After every write call check_syntax on the file before you go on.",
    }
    result = []
    seen_mistakes = set()
    seen_texts = set()
    if known:
        for k in known:
            if isinstance(k, str):
                seen_texts.add(re.sub(r'\s+', ' ', k.strip()).lower())
    for f in failures:
        if len(result) >= limit:
            break
        if not isinstance(f, dict):
            continue
        if "text" not in f or not isinstance(f.get("text"), str):
            continue
        stage = f.get("stage")
        if not isinstance(stage, str):
            stage = "?"
        mistakes = signatures(f["text"])
        for m in mistakes:
            if len(result) >= limit:
                break
            if m == "missing_module":
                for raw_name in _get_missing_module_name(f["text"]):
                    if len(result) >= limit:
                        break
                    name = raw_name.split(".")[0]
                    key = ("missing_module", name)
                    if key in seen_mistakes:
                        continue
                    seen_mistakes.add(key)
                    lesson = "The module '" + name + "' is not available in the sandbox. Use only the Python standard library and the modules of the project."
                    normalized = re.sub(r'\s+', ' ', lesson.strip()).lower()
                    if known and normalized in seen_texts:
                        continue
                    entry = {"text": lesson, "source": "run:" + run_id + ":" + stage}
                    result.append(entry)
                continue
            if m in seen_mistakes:
                continue
            seen_mistakes.add(m)
            lesson = lesson_texts[m]
            normalized = re.sub(r'\s+', ' ', lesson.strip()).lower()
            if known and normalized in seen_texts:
                continue
            entry = {"text": lesson, "source": "run:" + run_id + ":" + stage}
            result.append(entry)
    return result
