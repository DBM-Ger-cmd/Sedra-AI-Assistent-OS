def _valid(text, old):
    if not isinstance(text, str) or not isinstance(old, str):
        return False
    if not old.strip():
        return False
    return True


def _exact(text, old):
    spans = []
    start = 0
    while True:
        idx = text.find(old, start)
        if idx == -1:
            break
        spans.append((idx, idx + len(old)))
        start = idx + len(old)
    return spans


def _normalize_unicode(line):
    line = line.replace("\u201c", '"')
    line = line.replace("\u201d", '"')
    line = line.replace("\u2018", "'")
    line = line.replace("\u2019", "'")
    line = line.replace("\u2013", "-")
    line = line.replace("\u2014", "-")
    line = line.replace("\u2026", "...")
    line = line.replace("\u00a0", " ")
    return line.strip()


_NORMALIZERS = {
    "trailing_space": str.rstrip,
    "indentation": str.strip,
    "unicode": _normalize_unicode,
}


def _line_strategy(text, old, normalize):
    old_lines = old.split("\n")
    old_ends_nl = old.endswith("\n")
    if old_ends_nl and old_lines and old_lines[-1] == "":
        old_lines = old_lines[:-1]

    if not old_lines:
        return []

    text_lines = text.split("\n")
    num_old = len(old_lines)
    num_text = len(text_lines)
    spans = []

    for i in range(num_text - num_old + 1):
        match = True
        for j in range(num_old):
            t_norm = normalize(text_lines[i + j])
            o_norm = normalize(old_lines[j])
            if t_norm != o_norm:
                match = False
                break
        if match:
            first_line = i
            last_line = i + num_old - 1
            start = sum(len(text_lines[k]) + 1 for k in range(first_line))
            end = start + sum(len(text_lines[k]) + 1 for k in range(first_line, last_line)) + len(text_lines[last_line])
            if old_ends_nl and last_line < num_text - 1:
                end += 1
            spans.append((start, end))
    return spans


def locate(text, old):
    if not _valid(text, old):
        return {"strategy": None, "spans": []}

    spans = _exact(text, old)
    if spans:
        return {"strategy": "exact", "spans": spans}

    for name in ["trailing_space", "indentation", "unicode"]:
        spans = _line_strategy(text, old, _NORMALIZERS[name])
        if spans:
            return {"strategy": name, "spans": spans}

    return {"strategy": None, "spans": []}

def _reindent(new, old, text, start):
    old_lines = old.split("\n")
    text_lines = text.split("\n")
    i = 0
    pos = 0
    for li in range(len(text_lines)):
        line_end = pos + len(text_lines[li]) + 1
        if start < line_end:
            i = li
            break
        pos = line_end
    first_old_nonblank = 0
    for j in range(len(old_lines)):
        if old_lines[j].lstrip():
            first_old_nonblank = j
            old_indent = old_lines[j][:len(old_lines[j]) - len(old_lines[j].lstrip())]
            break
    if i + first_old_nonblank < len(text_lines):
        tl = text_lines[i + first_old_nonblank]
        stripped = tl.lstrip()
        if stripped:
            file_indent = tl[:len(tl) - len(stripped)]
    result_lines = []
    for nl in new.split("\n"):
        if nl.strip() == "":
            result_lines.append(nl)
            continue
        if file_indent.startswith(old_indent):
            prefix = file_indent[len(old_indent):]
            result_lines.append(prefix + nl)
        elif old_indent.startswith(file_indent):
            surplus = old_indent[len(file_indent):]
            if nl.startswith(surplus):
                result_lines.append(nl[len(surplus):])
            else:
                result_lines.append(nl)
        else:
            result_lines.append(nl)
    return "\n".join(result_lines)


def apply(text, old, new):
    if not _valid(text, old) or not isinstance(new, str):
        return {"error": "invalid", "count": 0}
    if old == new:
        return {"error": "identical", "count": 0}
    result = locate(text, old)
    spans = result["spans"]
    if not spans:
        return {"error": "not_found", "count": 0}
    if len(spans) > 1:
        return {"error": "ambiguous", "count": len(spans)}
    start, end = spans[0]
    strategy = result["strategy"]
    if strategy in ("indentation", "unicode"):
        new = _reindent(new, old, text, start)
    new_text = text[:start] + new + text[end:]
    return {"text": new_text, "strategy": strategy}
