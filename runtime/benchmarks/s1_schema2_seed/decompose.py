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
                    "akzeptanz": {"type": "string"},
                },
            },
        },
        "rueckfrage": {"type": ["string", "null"]},
    },
}
TOP = ("teilaufgaben", "rueckfrage")
ITEM = ("titel", "beschreibung", "rolle", "blocker", "akzeptanz")
CLOSED = ("erledigt", "abgebrochen")


def _bad(reason):
    return ValueError("decompose_invalid:" + reason)


def _cyclic(blockers):
    state = {}
    for start in range(len(blockers)):
        if start in state:
            continue
        state[start] = 1
        stack = [iter(blockers[start])]
        path = [start]
        while stack:
            nxt = next(stack[-1], None)
            if nxt is None:
                state[path.pop()] = 2
                stack.pop()
            elif state.get(nxt) == 1:
                return True
            elif nxt not in state:
                state[nxt] = 1
                path.append(nxt)
                stack.append(iter(blockers[nxt]))
    return False


def _assignee(role, subordinates, known):
    if role not in known:
        raise _bad("role_unknown")
    matches = [s for s in subordinates if s["role"] == role and s.get("status") == "aktiv" and not s.get("can_delegate")]
    if not matches:
        raise _bad("role_not_subordinate")
    return min(matches, key=lambda s: (s.get("open_tasks", 0), s["id"]))["id"]


def _item(item, count, subordinates, known):
    if not isinstance(item, dict) or set(item) - set(ITEM):
        raise _bad("extra_key")
    title = item.get("titel")
    if not isinstance(title, str) or not title.strip():
        raise _bad("title_empty")
    if len(title.strip()) > 200:
        raise _bad("title_too_long")
    texts = {k: item.get(k) or "" for k in ("beschreibung", "akzeptanz")}
    if any(len(v) > 4000 for v in texts.values()):
        raise _bad("text_too_long")
    blockers = item.get("blocker") or []
    if not isinstance(blockers, list) or any(type(b) is not int or not 0 <= b < count for b in blockers):
        raise _bad("blocker_index")
    agent = _assignee(item.get("rolle"), subordinates, known)
    return {"titel": title.strip(), "beschreibung": texts["beschreibung"], "rolle": item["rolle"], "blocker": list(blockers),
            "akzeptanz": texts["akzeptanz"], "agent_id": agent}


def check(answer, subordinates, max_subtasks, roles=None):
    if not isinstance(answer, dict) or set(answer) - set(TOP):
        raise _bad("extra_key")
    items = answer.get("teilaufgaben")
    if not isinstance(items, list) or not items:
        raise _bad("empty")
    if len(items) > max_subtasks:
        raise _bad("too_many")
    known = set(roles or ()) | {s["role"] for s in subordinates}
    out = [_item(item, len(items), subordinates, known) for item in items]
    if _cyclic([o["blocker"] for o in out]):
        raise _bad("blocker_cycle")
    return out


def report(root, children):
    rows, open_ = [], []
    for child in sorted(children, key=lambda c: (c["created_at"], c["id"])):
        result = child.get("check_result") or "nicht_geprueft"
        rows.append({"issue_id": child["id"], "titel": child["title"], "zustand": child["state"], "pruefung": result})
        if child["state"] not in CLOSED or result != "gruen":
            open_.append(child["id"])
    return {"zeilen": rows, "offen": open_, "vollstaendig": bool(children) and all(c["state"] in CLOSED for c in children)}
