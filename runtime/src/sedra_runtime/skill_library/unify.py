import copy
import re


def normalize_name(name):
    if name is None:
        return ""
    s = str(name).lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = s.strip('-')
    return s


def similarity(a, b):
    def get_words(text):
        if text is None:
            text = ""
        lower = text.lower()
        words = re.findall(r'[a-z0-9]{3,}', lower)
        return set(words)
    words_a = get_words(a)
    words_b = get_words(b)
    if not words_a or not words_b:
        return 0.0
    common = words_a & words_b
    all_words = words_a | words_b
    return len(common) / len(all_words)

def group_duplicates(entries, threshold=0.8):
    if not entries:
        return []
    n = len(entries)
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb
    for i in range(n):
        for j in range(i + 1, n):
            ei, ej = entries[i], entries[j]
            ni = normalize_name(ei.get("name"))
            nj = normalize_name(ej.get("name"))
            if ni and ni == nj:
                union(i, j)
                continue
            si = ei.get("description", "")
            sj = ej.get("description", "")
            if similarity(si, sj) >= threshold:
                union(i, j)
    groups = {}
    for i in range(n):
        root = find(i)
        if root not in groups:
            groups[root] = []
        groups[root].append(entries[i]["id"])
    result = []
    for root in groups:
        group_ids = sorted(groups[root])
        if len(group_ids) >= 2:
            result.append(group_ids)
    result.sort(key=lambda g: g[0])
    return result


def pick_primary(entries, priority):
    priority_set = set(priority)
    priority_index = {src: i for i, src in enumerate(priority)}

    def sort_key(entry):
        flags = entry.get("flags")
        has_flags = 1 if flags else 0
        source = entry.get("source")
        if source is None or source not in priority_index:
            source_rank = len(priority)
        else:
            source_rank = priority_index[source]
        lines = entry.get("lines", 0)
        id_val = entry.get("id", "")
        return (has_flags, source_rank, -lines, id_val)

    return min(entries, key=sort_key)


def merge_index(entries, priority, threshold=0.8):
    entries_copy = copy.deepcopy(entries)
    groups = group_duplicates(entries, threshold)
    group_to_primary = {}
    for group in groups:
        group_entries = [e for e in entries_copy if e["id"] in group]
        primary = pick_primary(group_entries, priority)
        group_to_primary[tuple(group)] = primary["id"]
    aliases = {}
    for group in groups:
        primary_id = group_to_primary[tuple(group)]
        for gid in group:
            if gid != primary_id:
                aliases[gid] = primary_id
    result_entries = []
    alias_set = set(aliases.keys())
    for entry in entries_copy:
        if entry["id"] in alias_set:
            continue
        for group in groups:
            primary_id = group_to_primary[tuple(group)]
            if entry["id"] == primary_id:
                other_ids = sorted([gid for gid in group if gid != primary_id])
                other_entries = [e for e in entries_copy if e["id"] in other_ids]
                also_in = sorted(set(e.get("source", "") for e in other_entries if e.get("source")))
                entry["merged_from"] = other_ids
                entry["also_in"] = also_in
                break
        result_entries.append(entry)
    return {"entries": result_entries, "aliases": aliases}


def resolve(aliases, skill_id):
    if skill_id in aliases:
        return aliases[skill_id]
    return skill_id
