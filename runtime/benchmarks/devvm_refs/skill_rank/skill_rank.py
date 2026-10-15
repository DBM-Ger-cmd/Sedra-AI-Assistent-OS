import re

_WORD = re.compile(r"[a-z0-9]{3,}")
STOP = frozenset("the and for with from that this use when into your you are not any all can used using skill skills".split())


def stem(word):
    w = str(word).lower()
    for suffix in ("ing", "ed", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            w = w[:-len(suffix)]
            if suffix != "s" and w[-1] == w[-2] and w[-1] not in "aeiou":
                w = w[:-1]
            break
    return w


def words(text):
    return {stem(w) for w in _WORD.findall(str(text or "").lower()) if w not in STOP}


def expand(stems, groups):
    extra = set()
    for group in groups:
        members = {stem(w) for w in group}
        if members & stems:
            extra |= members
    return extra - stems


def rank(entries, query, groups=(), limit=5):
    q = words(query)
    extra = expand(q, groups)
    found = []
    for e in entries:
        n, d = words(e.get("name")), words(e.get("description"))
        score = 4 * len(q & n) + len(q & d) + 2 * len(extra & n) + 0.5 * len(extra & d)
        if q and q <= n:
            score += 3
        if score > 0:
            found.append((-score, e["id"]))
    found.sort()
    return [{"id": i, "score": round(-s, 2)} for s, i in found[:max(1, min(int(limit), 10))]]
