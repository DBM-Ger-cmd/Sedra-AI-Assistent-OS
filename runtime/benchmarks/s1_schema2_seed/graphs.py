def parents(rows):
    result = {}
    for row in rows:
        result[row["id"]] = row.get("reports_to")
    return result


def _has_cycle(org, cid, creports):
    visited = set()
    current = creports
    while current is not None:
        if current == cid:
            return True
        if current in visited:
            return True
        visited.add(current)
        current = org.get(current)
    return False


def check_org(rows, change, max_depth=0):
    cid = change["id"]
    creports = change.get("reports_to")
    cstatus = change.get("status", "aktiv")
    org = {}
    for row in rows:
        org[row["id"]] = row.get("reports_to")
    org[cid] = creports
    if creports == cid:
        raise ValueError("org_self")
    if creports is not None:
        superior_exists = False
        for row in rows:
            if row["id"] == creports:
                if row.get("status") != "beendet":
                    superior_exists = True
                break
        if not superior_exists:
            raise ValueError("org_unknown_superior")
    if creports is not None:
        if _has_cycle(org, cid, creports):
            raise ValueError("org_cycle")
    live = set()
    for row in rows:
        if row.get("status") != "beendet":
            live.add(row["id"])
    if cstatus != "beendet":
        live.add(cid)
    live_roots = []
    for lid in live:
        if org.get(lid) is None:
            live_roots.append(lid)
    if cid in live_roots and len(live_roots) > 1:
        raise ValueError("org_second_root")
    if len(live) > 0 and len(live_roots) == 0:
        raise ValueError("org_no_root")
    if max_depth > 0:
        for lid in live:
            depth = 0
            current = lid
            while current is not None:
                depth += 1
                if depth > max_depth:
                    raise ValueError("org_too_deep")
                current = org.get(current)


def can_terminate(rows, agent_id):
    for row in rows:
        if row.get("reports_to") == agent_id:
            if row.get("status") in ("aktiv", "pausiert"):
                raise ValueError("org_has_subordinates")


def _build_org(rows):
    org = {}
    for row in rows:
        org[row["id"]] = row.get("reports_to")
    return org


def is_below(rows, boss, other):
    org = _build_org(rows)
    if other not in org or boss not in org:
        return False
    if boss == other:
        return False
    visited = set()
    current = other
    while current is not None:
        if current == boss:
            return True
        if current in visited:
            return False
        visited.add(current)
        current = org.get(current)
    return False


def check_delegation(rows, frm, to, can_delegate):
    if not can_delegate:
        raise ValueError("delegation_not_allowed")
    if not is_below(rows, frm, to):
        raise ValueError("delegation_not_below")
    for row in rows:
        if row["id"] == to:
            if row.get("status") != "aktiv":
                raise ValueError("delegation_target_inactive")
            return
    raise ValueError("delegation_target_inactive")

_LEVEL_MAP = {
    'read_only': 1,
    'proposal_only': 1,
    'reversible_write': 2,
    'preview': 3,
}


def level_for(effect, recipe_max):
    if effect not in _LEVEL_MAP:
        raise ValueError('level_not_allowed')
    level = _LEVEL_MAP[effect]
    if recipe_max is not None:
        level = min(level, recipe_max)
    return level


def inherit_level(parent_max, assignee_level):
    if parent_max is None:
        return assignee_level
    return min(parent_max, assignee_level)


def has_cycle(edges):
    graph = {}
    all_nodes = set()
    for task, blocked_by in edges:
        all_nodes.add(task)
        all_nodes.add(blocked_by)
        if task not in graph:
            graph[task] = set()
        graph[task].add(blocked_by)

    state = {node: 0 for node in all_nodes}

    for start_node in all_nodes:
        if state[start_node] != 0:
            continue
        stack = [(start_node, False)]
        while stack:
            node, processed = stack.pop()
            if processed:
                state[node] = 2
                continue
            if state[node] == 1:
                state[node] = 2
                continue
            if state[node] == 2:
                continue
            state[node] = 1
            stack.append((node, True))
            for neighbor in graph.get(node, set()):
                if state[neighbor] == 1:
                    return True
                if state[neighbor] == 0:
                    stack.append((neighbor, False))

    return False
