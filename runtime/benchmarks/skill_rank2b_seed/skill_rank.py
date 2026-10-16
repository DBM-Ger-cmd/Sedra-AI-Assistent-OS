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

def rank(entries, query, groups=(), limit=5, min_ratio=0.25):
    q = words(query)
    extra = expand(q, groups)
    idf = idf_table(entries)
    def W(s):
        return sum(idf.get(w, 0) for w in s)
    scored = []
    for entry in entries:
        eid = entry["id"]
        n = words(entry.get("name"))
        d = words(entry.get("description"))
        score = 4 * W(q & n) + 1 * W(q & d) + 2 * W(extra & n) + 0.5 * W(extra & d)
        if q and q.issubset(n):
            score += 3
        if score == 0:
            continue
        scored.append({"id": eid, "score": score})
    scored.sort(key=lambda x: (-x["score"], x["id"]))
    limit = max(1, min(10, limit))
    return [{"id": e["id"], "score": round(e["score"], 2)} for e in scored[:limit]]

def idf_table(entries):
    n = len(entries)
    df = {}
    for entry in entries:
        s = words(entry.get("name")) | words(entry.get("description"))
        for w in s:
            df[w] = df.get(w, 0) + 1
    if not df:
        return {}
    return {w: math.log(1 + n / df[w]) for w in df}