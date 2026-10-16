import re

_WORD = re.compile(r"[a-z0-9]{3,}")


def normalize_name(name):
    if name is None:
        return ""
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def _words(text):
    return set(_WORD.findall(str(text or "").lower()))


def similarity(a, b):
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _linked(a, b, threshold):
    name = normalize_name(a.get("name"))
    if name and name == normalize_name(b.get("name")):
        return True
    return similarity(a.get("description"), b.get("description")) >= threshold


def group_duplicates(entries, threshold=0.8):
    parent = {e["id"]: e["id"] for e in entries}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(entries):
        for b in entries[i + 1:]:
            if _linked(a, b, threshold):
                parent[find(a["id"])] = find(b["id"])
    groups = {}
    for e in entries:
        groups.setdefault(find(e["id"]), []).append(e["id"])
    return sorted(sorted(g) for g in groups.values() if len(g) > 1)


def pick_primary(entries, priority):
    def rank(e):
        source = e.get("source")
        order = priority.index(source) if source in priority else len(priority)
        return (bool(e.get("flags")), order, -e.get("lines", 0), e["id"])
    return min(entries, key=rank)


def merge_index(entries, priority, threshold=0.8):
    by_id = {e["id"]: e for e in entries}
    aliases, extra = {}, {}
    for ids in group_duplicates(entries, threshold):
        primary = pick_primary([by_id[i] for i in ids], priority)
        others = [by_id[i] for i in ids if i != primary["id"]]
        for o in others:
            aliases[o["id"]] = primary["id"]
        extra[primary["id"]] = {"merged_from": sorted(o["id"] for o in others),
                                "also_in": sorted({o.get("source") for o in others if o.get("source")})}
    kept = [{**e, **extra.get(e["id"], {})} for e in entries if e["id"] not in aliases]
    return {"entries": kept, "aliases": aliases}


def resolve(aliases, skill_id):
    return aliases.get(skill_id, skill_id)
