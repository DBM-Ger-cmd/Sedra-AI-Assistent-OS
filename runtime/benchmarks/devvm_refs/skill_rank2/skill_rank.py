import math

STOP = frozenset(["the", "and", "for", "with", "from", "that", "this", "use", "when", "into", "your", "you", "are", "not", "any", "all", "can", "used", "using", "skill", "skills"])

def stem(word):
    word = str(word).lower()
    suffix = None
    if word.endswith("ing") and len(word) - 3 >= 3:
        suffix = "ing"
    elif word.endswith("ed") and len(word) - 2 >= 3:
        suffix = "ed"
    elif word.endswith("s") and len(word) - 1 >= 3:
        suffix = "s"
    if suffix is None:
        return word
    rest = word[:-len(suffix)]
    if suffix in ("ing", "ed"):
        vowels = set("aeiou")
        if len(rest) >= 2 and rest[-1] == rest[-2] and rest[-1] not in vowels:
            rest = rest[:-1]
    return rest

def words(text):
    if text is None:
        text = ""
    text = str(text).lower()
    import re
    runs = re.findall(r'[a-zA-Z0-9]+', text)
    result = set()
    for run in runs:
        if len(run) < 3:
            continue
        if run in STOP:
            continue
        result.add(stem(run))
    return result

def expand(stems, groups):
    result = set()
    for group in groups:
        members = set()
        for word in group:
            members.add(stem(word))
        if members & stems:
            result |= members
    return result - stems

DESC_SYNONYM_CAP = 1.0


def idf_table(entries):
    counts = {}
    for entry in entries:
        for w in words(entry.get("name")) | words(entry.get("description")):
            counts[w] = counts.get(w, 0) + 1
    n = len(entries)
    return {w: math.log(1 + n / df) for w, df in counts.items()}


def _weight(table, stems):
    return sum(table.get(w, 0.0) for w in stems)


def rank(entries, query, groups=(), limit=5, min_ratio=0.25):
    q = words(query)
    extra = expand(q, groups)
    table = idf_table(entries)
    scored = []
    for entry in entries:
        n = words(entry.get("name"))
        d = words(entry.get("description"))
        score = 4 * _weight(table, q & n) + _weight(table, q & d) + 2 * _weight(table, extra & n)
        score += min(0.5 * _weight(table, extra & d), DESC_SYNONYM_CAP)
        if q and q <= n:
            score += 3
        if score > 0:
            scored.append({"id": entry["id"], "score": score})
    scored.sort(key=lambda x: (-x["score"], x["id"]))
    if scored:
        floor = min_ratio * scored[0]["score"]
        scored = [s for s in scored if s["score"] >= floor]
    limit = max(1, min(10, int(limit)))
    return [{"id": s["id"], "score": round(s["score"], 2)} for s in scored[:limit]]
