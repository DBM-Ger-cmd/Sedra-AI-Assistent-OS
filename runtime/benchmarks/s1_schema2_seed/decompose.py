SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["teilaufgaben", "rueckfrage"],
    "properties": {
        "teilaufgaben": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["titel", "beschreibung", "rolle", "blocker", "akzeptanz"],
                "properties": {
                    "titel": {"type": "string"},
                    "beschreibung": {"type": "string"},
                    "rolle": {"type": "string"},
                    "blocker": {"type": "array", "items": {"type": "integer"}},
                    "akzeptanz": {"type": "string"}
                }
            }
        },
        "rueckfrage": {
            "type": ["string", "null"]
        }
    }
}


def _check_entry(entry, n):
    if not isinstance(entry, dict):
        raise ValueError("decompose_invalid:extra_key")
    allowed = {"titel", "beschreibung", "rolle", "blocker", "akzeptanz"}
    for k in entry:
        if k not in allowed:
            raise ValueError("decompose_invalid:extra_key")
    titel = entry.get("titel")
    if not isinstance(titel, str) or titel.strip() == "":
        raise ValueError("decompose_invalid:title_empty")
    if len(titel.strip()) > 200:
        raise ValueError("decompose_invalid:title_too_long")
    beschreibung = entry.get("beschreibung", "")
    akzeptanz = entry.get("akzeptanz", "")
    if not isinstance(beschreibung, str):
        beschreibung = ""
    if not isinstance(akzeptanz, str):
        akzeptanz = ""
    if len(beschreibung) > 4000 or len(akzeptanz) > 4000:
        raise ValueError("decompose_invalid:text_too_long")
    blocker = entry.get("blocker")
    if blocker is None:
        blocker = []
    if not isinstance(blocker, list):
        raise ValueError("decompose_invalid:blocker_index")
    for x in blocker:
        if type(x) is not int:
            raise ValueError("decompose_invalid:blocker_index")
        if x < 0 or x >= n:
            raise ValueError("decompose_invalid:blocker_index")
    return {
        "titel": titel.strip(),
        "beschreibung": beschreibung,
        "rolle": entry.get("rolle", ""),
        "blocker": list(blocker),
        "akzeptanz": akzeptanz
    }


def _has_cycle(entries):
    n = len(entries)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = [WHITE] * n
    for start in range(n):
        if color[start] != WHITE:
            continue
        stack = [(start, 0)]
        color[start] = GRAY
        while stack:
            u, idx = stack[-1]
            blockers = entries[u]["blocker"]
            if idx < len(blockers):
                v = blockers[idx]
                stack[-1] = (u, idx + 1)
                if color[v] == GRAY:
                    return True
                if color[v] == WHITE:
                    color[v] = GRAY
                    stack.append((v, 0))
            else:
                stack.pop()
                color[u] = BLACK
    return False


def check(answer, subordinates, max_subtasks, roles=None):
    if not isinstance(answer, dict):
        raise ValueError("decompose_invalid:extra_key")
    allowed_keys = {"teilaufgaben", "rueckfrage"}
    for key in answer:
        if key not in allowed_keys:
            raise ValueError("decompose_invalid:extra_key")
    if "teilaufgaben" not in answer:
        raise ValueError("decompose_invalid:empty")
    teilaufgaben = answer["teilaufgaben"]
    if not isinstance(teilaufgaben, list):
        raise ValueError("decompose_invalid:empty")
    if len(teilaufgaben) == 0:
        raise ValueError("decompose_invalid:empty")
    if len(teilaufgaben) > max_subtasks:
        raise ValueError("decompose_invalid:too_many")
    n = len(teilaufgaben)
    known_roles = set()
    if roles is not None:
        known_roles.update(roles)
    for sub in subordinates:
        known_roles.add(sub["role"])
    result = []
    for i in range(n):
        entry = _check_entry(teilaufgaben[i], n)
        if entry["rolle"] not in known_roles:
            raise ValueError("decompose_invalid:role_unknown")
        candidates = [
            sub for sub in subordinates
            if sub["role"] == entry["rolle"]
            and sub["status"] == "aktiv"
            and not sub.get("can_delegate", 0)
        ]
        if not candidates:
            raise ValueError("decompose_invalid:role_not_subordinate")
        candidates.sort(key=lambda s: (s.get("open_tasks", 0), s["id"]))
        entry["agent_id"] = candidates[0]["id"]
        result.append(entry)
    if _has_cycle(result):
        raise ValueError("decompose_invalid:blocker_cycle")
    return result


def report(root, children):
    rows = sorted(children, key=lambda c: (c["created_at"], c["id"]))
    zeilen = []
    offen = []
    for c in rows:
        cr = c.get("check_result")
        if cr is None or cr == "":
            pruefung = "nicht_geprueft"
        else:
            pruefung = cr
        zeilen.append({
            "issue_id": c["id"],
            "titel": c["title"],
            "zustand": c["state"],
            "pruefung": pruefung
        })
        closed = c["state"] in ("erledigt", "abgebrochen")
        if not closed or pruefung != "gruen":
            offen.append(c["id"])
    vollstaendig = len(zeilen) > 0 and all(c["state"] in ("erledigt", "abgebrochen") for c in rows)
    return {"zeilen": zeilen, "offen": offen, "vollstaendig": vollstaendig}
