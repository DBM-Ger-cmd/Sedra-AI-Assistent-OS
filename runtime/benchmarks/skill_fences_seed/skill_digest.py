import re

MORE = "[more: read the full text with skill_read start/end]"


def _non_fence_lines(lines):
    in_fence = False
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield (i, line)


def digest(text, max_lines=60):
    max_lines = int(max_lines)
    if max_lines < 2:
        max_lines = 2
    lines = str(text or "").splitlines()
    summary = None
    for i, line in _non_fence_lines(lines):
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
    result = []
    for i, line in _non_fence_lines(lines):
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            result.append((i, level, title))
    return result


def templates(text):
    lines = str(text or "").splitlines()
    headings = outline(text)
    result = []
    in_fence = False
    fence_start = None
    fence_lang = None
    fence_body = []
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not in_fence:
            m = re.match(r'^```(\S*)', stripped)
            if m:
                in_fence = True
                fence_start = i
                fence_lang = m.group(1).lower()
                fence_body = []
        else:
            if re.match(r'^```\s*$', stripped):
                in_fence = False
                if fence_lang in ("markdown", "md"):
                    closest_title = ""
                    for hline, hlevel, htitle in reversed(headings):
                        if hline < fence_start:
                            closest_title = htitle
                            break
                    result.append({
                        "title": closest_title,
                        "start": fence_start,
                        "end": i,
                        "lang": fence_lang,
                        "body": fence_body
                    })
                fence_start = None
                fence_lang = None
                fence_body = []
            else:
                fence_body.append(line)
    return result
