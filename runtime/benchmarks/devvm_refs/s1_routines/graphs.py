LEVELS = {"read_only": 1, "proposal_only": 1, "reversible_write": 2, "preview": 3}
LIVE = ("aktiv", "pausiert")


def parents(rows):
    return {row["id"]: row.get("reports_to") for row in rows}


def _merged(rows, change):
    out = [dict(row) for row in rows if row["id"] != change["id"]]
    out.append({"id": change["id"], "reports_to": change.get("reports_to"), "status": change.get("status", "aktiv")})
    return out


def _chain(up, start):
    seen, node = [], start
    while node is not None and node not in seen:
        seen.append(node)
        node = up.get(node)
    return seen, node


def check_org(rows, change, max_depth):
    agent, boss = change["id"], change.get("reports_to")
    if boss == agent:
        raise ValueError("org_self")
    status = {row["id"]: row.get("status") for row in rows if row["id"] != agent}
    if boss is not None and status.get(boss) in (None, "beendet"):
        raise ValueError("org_unknown_superior")
    merged = _merged(rows, change)
    up = parents(merged)
    seen, stop = _chain(up, boss)
    if agent in seen or stop is not None:
        raise ValueError("org_cycle")
    live = [row for row in merged if row["status"] in LIVE]
    roots = [row["id"] for row in live if row.get("reports_to") is None]
    if boss is None and agent in roots and len(roots) > 1:
        raise ValueError("org_second_root")
    if live and not roots:
        raise ValueError("org_no_root")
    for row in live:
        if len(_chain(up, row["id"])[0]) > max_depth:
            raise ValueError("org_too_deep")


def can_terminate(rows, agent_id):
    if any(row.get("reports_to") == agent_id and row.get("status") in LIVE for row in rows):
        raise ValueError("org_has_subordinates")


def is_below(rows, boss, other):
    seen, _ = _chain(parents(rows), other)
    return boss in seen[1:]


def check_delegation(rows, frm, to, can_delegate):
    if not can_delegate:
        raise ValueError("delegation_not_allowed")
    if not is_below(rows, frm, to):
        raise ValueError("delegation_not_below")
    if next((row.get("status") for row in rows if row["id"] == to), None) != "aktiv":
        raise ValueError("delegation_target_inactive")


def level_for(effect, recipe_max):
    if effect not in LEVELS:
        raise ValueError("level_not_allowed")
    level = LEVELS[effect]
    return level if recipe_max is None else min(level, recipe_max)


def inherit_level(parent_max, assignee_level):
    return assignee_level if parent_max is None else min(parent_max, assignee_level)


def has_cycle(edges):
    graph = {}
    for task, blocked_by in edges:
        graph.setdefault(task, []).append(blocked_by)
    state = {}
    for start in graph:
        if state.get(start):
            continue
        stack = [(start, iter(graph.get(start, ())))]
        state[start] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[node] = 2
                stack.pop()
            elif state.get(nxt) == 1:
                return True
            elif not state.get(nxt):
                state[nxt] = 1
                stack.append((nxt, iter(graph.get(nxt, ()))))
    return False
