TYPES = ("agent", "issue", "routine", "budget")


def register(registry, hub):
    orchestra = getattr(getattr(hub, "runtime", None), "orchestra", None)
    if orchestra is None:
        return []
    kinds = []
    for name in TYPES:
        title_map = {"agent": "Agent", "issue": "Aufgabe", "routine": "Routine", "budget": "Budget"}
        kind = registry.Kind(name, title_map[name], None, None, source="orchestra")
        kinds.append(kind)
    for kind in kinds:                                      # alle vier ersetzen ihren Platzhalter aus builtin_kinds (Spec 4)
        registry.register(kind, replace_placeholder=True)
    kind_map = {k.name: k for k in kinds}
    kind_map["agent"].read = agent_read
    kind_map["agent"].listing = agent_listing
    kind_map["issue"].read = issue_read
    kind_map["issue"].listing = issue_listing
    kind_map["routine"].read = routine_read
    kind_map["routine"].listing = routine_listing
    kind_map["budget"].read = budget_read
    kind_map["budget"].listing = budget_listing
    return list(TYPES)


def _make_read(obj_fn, facade_fn):
    def read(hub, oid):
        orch = getattr(getattr(hub, "runtime", None), "orchestra", None)
        if orch is None:
            return None
        row = getattr(orch, facade_fn)(oid)
        if row is None:
            return None
        return obj_fn(row)
    return read


def _make_listing(obj_fn, facade_fn, filter_fn=None):
    def listing(hub, payload):
        orch = getattr(getattr(hub, "runtime", None), "orchestra", None)
        if orch is None:
            return []
        if filter_fn:
            rows = getattr(orch, facade_fn)(**filter_fn(payload))
        else:
            rows = getattr(orch, facade_fn)()
        if rows is None:
            return []
        return [obj_fn(row) for row in rows]
    return listing


def _build_links(row, link_specs):
    links = []
    for t, key in link_specs:
        val = row.get(key)
        if val is not None and val != "":
            links.append({"type": t, "id": val})
    return links


def _build_object(obj_type, row_id, title, state, summary, links):
    return {"type": obj_type, "id": row_id, "title": title, "state": state, "summary": summary, "actions": [], "links": links}


def agent_object(row):
    reports_to = row.get("reports_to")
    if reports_to is not None and reports_to != "":
        summary = row.get("role", "") + " · unter " + reports_to
    else:
        summary = row.get("role", "") + " · direkt unter dem Captain"
    links = _build_links(row, [("agent", "reports_to")])
    return _build_object(
        "agent",
        row["id"],
        row["name"],
        row["status"],
        summary,
        links,
    )


def issue_object(row):
    assignee = row.get("assignee")
    checkout_by = row.get("checkout_by")
    if assignee is not None and assignee != "":
        summary = "zugewiesen an " + assignee
    else:
        summary = "nicht zugewiesen"
    if checkout_by is not None and checkout_by != "":
        summary += " · ausgecheckt von " + checkout_by
    links = _build_links(row, [("agent", "assignee"), ("issue", "parent_id"), ("task", "mission_id"), ("intent", "goal_ref"), ("project", "project_id")])
    return _build_object(
        "issue",
        row["id"],
        row["title"],
        row["state"],
        summary,
        links,
    )


def routine_object(row):
    cron = row.get("cron", "")
    timezone = row.get("timezone", "Europe/Berlin")
    summary = cron + " (" + timezone + ")"
    enabled = row.get("enabled")
    state = "an" if enabled else "aus"
    links = _build_links(row, [("agent", "agent_id")])
    return _build_object(
        "routine",
        row["id"],
        row["title"],
        state,
        summary,
        links,
    )


agent_read = _make_read(agent_object, "agent")
agent_listing = _make_listing(agent_object, "agents")

issue_read = _make_read(issue_object, "issue")
issue_listing = _make_listing(issue_object, "issues", lambda p: {"state": (p or {}).get("state"), "assignee": (p or {}).get("assignee")})

routine_read = _make_read(routine_object, "routine")
routine_listing = _make_listing(routine_object, "routines")


def budget_read(hub, oid):
    orch = getattr(getattr(hub, "runtime", None), "orchestra", None)
    if orch is None:
        return None
    agent = orch.agent(oid)
    if agent is None:
        return None
    spent = orch.spent(agent["id"])
    warn_percent = orch.config.warn_percent
    stop_percent = orch.config.stop_percent
    return budget_object(agent, spent, warn_percent, stop_percent)


def budget_listing(hub, payload):
    orch = getattr(getattr(hub, "runtime", None), "orchestra", None)
    if orch is None:
        return []
    agents = orch.agents()
    if agents is None:
        return []
    warn_percent = orch.config.warn_percent
    stop_percent = orch.config.stop_percent
    return [budget_object(a, orch.spent(a["id"]), warn_percent, stop_percent) for a in agents]


def budget_object(agent, spent, warn_percent=80, stop_percent=100):
    limits = []
    budget_tokens = agent.get("budget_tokens")
    if budget_tokens is not None and budget_tokens != "" and budget_tokens != 0:
        limits.append(("Token", spent.get("tokens", 0), budget_tokens))
    budget_eur_cent = agent.get("budget_eur_cent")
    if budget_eur_cent is not None and budget_eur_cent != "" and budget_eur_cent != 0:
        limits.append(("Cent", spent.get("eur_cent", 0), budget_eur_cent))
    if not limits:
        state = "ohne Grenze"
        summary = "keine Grenze gesetzt"
    else:
        parts = []
        max_ratio = 0
        for label, used, limit in limits:
            parts.append(label + " " + str(used) + "/" + str(limit))
            ratio = used * 100 / limit
            if ratio > max_ratio:
                max_ratio = ratio
        summary = " · ".join(parts)
        if max_ratio >= stop_percent:
            state = "gestoppt"
        elif max_ratio >= warn_percent:
            state = "Warnung"
        else:
            state = "im Rahmen"
    links = [{"type": "agent", "id": agent["id"]}]
    return _build_object(
        "budget",
        agent["id"],
        "Budget " + agent["name"],
        state,
        summary,
        links,
    )
