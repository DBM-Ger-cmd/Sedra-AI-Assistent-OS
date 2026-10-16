import re

MORE = "[more: read the full text with skill_read start/end]"


def _inside_fences(text):
    lines = str(text or "").splitlines()
    fence_blocks = fences(text)
    fence_lines = set()
    for fb in fence_blocks:
        fence_lines.add(fb["start"])
        if fb["end"] is not None:
            for i in range(fb["start"], fb["end"] + 1):
                fence_lines.add(i)
        else:
            for i in range(fb["start"], len(lines) + 1):
                fence_lines.add(i)
    return fence_lines


def locations(text, limit=6):
    limit = int(limit)
    if limit == 0:
        return []
    lines = str(text or "").splitlines()
    fence_lines = _inside_fences(text)
    result = []
    for i, line in enumerate(lines, start=1):
        if i in fence_lines:
            continue
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        tokens = re.findall(r'`([^`\s]+)`', stripped)
        valid = False
        for token in tokens:
            if "/" in token:
                valid = True
                break
            if re.search(r'\.(md|py|json|yaml|yml|txt|toml|js|ts)$', token):
                valid = True
                break
        if not valid:
            continue
        result.append((i, stripped[:160]))
        if len(result) >= limit:
            break
    return result

def digest(text, max_lines=60):
    max_lines = int(max_lines)
    if max_lines < 2:
        max_lines = 2
    lines = str(text or "").splitlines()
    fence_lines = _inside_fences(text)
    summary = None
    for i, line in enumerate(lines, start=1):
        if i in fence_lines:
            continue
        stripped = line.strip()
        if summary is None and stripped and not stripped.startswith("#"):
            summary = stripped[:160]
    result = []
    if summary is not None:
        result.append("Summary: " + summary)
    for t in templates(text):
        result.append("Template (" + t["title"] + ", lines " + str(t["start"]) + "-" + str(t["end"]) + "):")
        for body_line in t["body"]:
            result.append(body_line)
    locs = locations(text)
    if locs:
        result.append("Locations:")
        for ln, l in locs:
            result.append(str(ln) + " " + l)
    result.append("Outline:")
    for hline, hlevel, htitle in outline(text):
        if hlevel in (2, 3):
            indent = "  " * (hlevel - 2)
            result.append(str(hline) + " " + indent + htitle)
    if len(result) > max_lines:
        result = result[:max_lines - 1]
        result.append(MORE)
    return "\n".join(result)


def outline(text):
    lines = str(text or "").splitlines()
    fence_lines = _inside_fences(text)
    result = []
    for i, line in enumerate(lines, start=1):
        if i in fence_lines:
            continue
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            result.append((i, level, title))
    return result


def templates(text):
    fence_blocks = fences(text)
    headings = outline(text)
    result = []
    for fb in fence_blocks:
        if not fb["closed"]:
            continue
        if fb["lang"] not in ("markdown", "md"):
            continue
        closest_title = ""
        for hline, hlevel, htitle in reversed(headings):
            if hline < fb["start"]:
                closest_title = htitle
                break
        result.append({
            "title": closest_title,
            "start": fb["start"],
            "end": fb["end"],
            "lang": fb["lang"],
            "body": fb["body"]
        })
    return result


def fences(text):
    lines = str(text or "").splitlines()
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip(' ')
        leading_spaces = len(line) - len(stripped)
        if leading_spaces > 3:
            i += 1
            continue
        m = re.match(r'^(`{3,}|~{3,})(.*)', stripped)
        if not m:
            i += 1
            continue
        fence_char = m.group(1)[0]
        info_string = m.group(2).strip()
        if fence_char == '`' and '`' in info_string:
            i += 1
            continue
        start = i + 1
        body = []
        closed = False
        end = None
        i += 1
        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip(' ')
            leading_spaces = len(line) - len(stripped)
            if leading_spaces > 3:
                body.append(line)
                i += 1
                continue
            m2 = re.match(r'^(`{3,}|~{3,})\s*$', stripped)
            if not m2:
                body.append(line)
                i += 1
                continue
            close_char = m2.group(1)[0]
            if close_char != fence_char:
                body.append(line)
                i += 1
                continue
            if len(m2.group(1)) < len(m.group(1)):
                body.append(line)
                i += 1
                continue
            end = i + 1
            closed = True
            i += 1
            break
        lang = info_string.split()[0].lower() if info_string else ""
        result.append({"start": start, "end": end, "lang": lang, "body": body, "closed": closed})
    return result
