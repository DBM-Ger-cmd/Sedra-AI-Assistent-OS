import re

TEMPLATE_LANGS = ("markdown", "md")
MORE = "[more: read the full text with skill_read start/end]"
HEADING = re.compile(r"^(#{1,4})\s+(\S.*?)\s*$")
TOKEN = re.compile(r"`([^`\s]+)`")
FILE_END = re.compile(r"\.(md|py|json|yaml|yml|txt|toml|js|ts)$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def fences(text):
    found, current = [], None
    for number, line in enumerate(str(text or "").splitlines(), 1):
        match = FENCE.match(line)
        if current is None:
            if match and not (match.group(1)[0] == "`" and "`" in match.group(2)):
                info = match.group(2).split()
                current = {"start": number, "char": match.group(1)[0], "length": len(match.group(1)),
                           "lang": info[0].lower() if info else "", "body": []}
        elif match and match.group(1)[0] == current["char"] and len(match.group(1)) >= current["length"] and not match.group(2).strip():
            found.append({"start": current["start"], "end": number, "lang": current["lang"], "body": current["body"], "closed": True})
            current = None
        else:
            current["body"].append(line)
    if current is not None:
        found.append({"start": current["start"], "end": None, "lang": current["lang"], "body": current["body"], "closed": False})
    return found


def _covered(text):
    total = len(str(text or "").splitlines())
    lines = set()
    for block in fences(text):
        lines.update(range(block["start"], (block["end"] or total) + 1))
    return lines


def outline(text):
    inside = _covered(text)
    rows = []
    for number, line in enumerate(str(text or "").splitlines(), 1):
        match = None if number in inside else HEADING.match(line)
        if match:
            rows.append((number, len(match.group(1)), match.group(2)))
    return rows


def templates(text):
    heads = outline(text)
    found = []
    for block in fences(text):
        if block["closed"] and block["lang"] in TEMPLATE_LANGS:
            title = ""
            for head_line, _, head_title in heads:
                if head_line < block["start"]:
                    title = head_title
            found.append({"title": title, "start": block["start"], "end": block["end"], "lang": block["lang"], "body": block["body"]})
    return found


def _summary(text):
    inside = _covered(text)
    for number, line in enumerate(str(text or "").splitlines(), 1):
        stripped = line.strip()
        if number in inside or not stripped or stripped.startswith("#"):
            continue
        return stripped[:160]
    return ""


def locations(text, limit=6):
    inside = _covered(text)
    found = []
    for number, line in enumerate(str(text or "").splitlines(), 1):
        stripped = line.strip()
        if number in inside or stripped.startswith("#"):
            continue
        if any("/" in token or FILE_END.search(token) for token in TOKEN.findall(stripped)):
            found.append((number, stripped[:160]))
    return found[:max(0, int(limit))]


def digest(text, max_lines=60):
    max_lines = max(2, int(max_lines))
    out = []
    summary = _summary(text)
    if summary:
        out.append("Summary: " + summary)
    for block in templates(text):
        out.append(f"Template ({block['title']}, lines {block['start']}-{block['end']}):")
        out.extend(block["body"])
    places = locations(text)
    if places:
        out.append("Locations:")
        out.extend(f"{number} {line}" for number, line in places)
    out.append("Outline:")
    for number, level, title in outline(text):
        if level in (2, 3):
            out.append(f"{number} {'  ' * (level - 2)}{title}")
    if len(out) <= max_lines:
        return "\n".join(out)
    return "\n".join(out[:max_lines - 1] + [MORE])
