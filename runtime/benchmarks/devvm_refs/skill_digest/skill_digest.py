import re

TEMPLATE_LANGS = ("markdown", "md")
MORE = "[more: read the full text with skill_read start/end]"
HEADING = re.compile(r"^(#{1,4})\s+(\S.*?)\s*$")


def _fence_lang(line):
    stripped = line.strip()
    if stripped.startswith("```"):
        return stripped[3:].strip().lower()
    return None


def outline(text):
    rows, inside = [], False
    for number, line in enumerate(str(text or "").splitlines(), 1):
        if _fence_lang(line) is not None:
            inside = not inside
            continue
        match = None if inside else HEADING.match(line)
        if match:
            rows.append((number, len(match.group(1)), match.group(2)))
    return rows


def templates(text):
    lines = str(text or "").splitlines()
    heads = outline(text)
    found, start, lang = [], None, None
    for number, line in enumerate(lines, 1):
        fence = _fence_lang(line)
        if fence is None:
            continue
        if start is None:
            start, lang = number, fence
            continue
        if lang in TEMPLATE_LANGS:
            title = ""
            for head_line, _, head_title in heads:
                if head_line < start:
                    title = head_title
            found.append({"title": title, "start": start, "end": number, "lang": lang, "body": lines[start:number - 1]})
        start = None
    return found


def _summary(text):
    inside = False
    for line in str(text or "").splitlines():
        if _fence_lang(line) is not None:
            inside = not inside
            continue
        stripped = line.strip()
        if inside or not stripped or stripped.startswith("#"):
            continue
        return stripped[:160]
    return ""


def digest(text, max_lines=60):
    max_lines = max(2, int(max_lines))
    out = []
    summary = _summary(text)
    if summary:
        out.append("Summary: " + summary)
    for block in templates(text):
        out.append(f"Template ({block['title']}, lines {block['start']}-{block['end']}):")
        out.extend(block["body"])
    out.append("Outline:")
    for number, level, title in outline(text):
        if level in (2, 3):
            out.append(f"{number} {'  ' * (level - 2)}{title}")
    if len(out) <= max_lines:
        return "\n".join(out)
    return "\n".join(out[:max_lines - 1] + [MORE])
