TYPES = ("agent", "issue", "routine", "budget")


def _links(*pairs):
    return [{"type": kind, "id": oid} for kind, oid in pairs if oid]


def _object(kind, oid, title, state, summary, links):
    return {"type": kind, "id": oid, "title": title, "state": state, "summary": summary, "actions": [], "links": links}


def agent_object(row):
    boss = row.get("reports_to")
    where = f"unter {boss}" if boss else "direkt unter dem Captain"
    return _object("agent", row["id"], row["name"], row["status"], f"{row['role']} · {where}", _links(("agent", boss)))


def issue_object(row):
    who = f"zugewiesen an {row['assignee']}" if row.get("assignee") else "nicht zugewiesen"
    if row.get("checkout_by"):
        who += f" · ausgecheckt von {row['checkout_by']}"
    links = _links(("agent", row.get("assignee")), ("issue", row.get("parent_id")), ("task", row.get("mission_id")),
                   ("intent", row.get("goal_ref")), ("project", row.get("project_id")))
    return _object("issue", row["id"], row["title"], row["state"], who, links)


def routine_object(row):
    state = "an" if row.get("enabled") else "aus"
    summary = f"{row['cron']} ({row.get('timezone') or 'Europe/Berlin'})"
    return _object("routine", row["id"], row["title"], state, summary, _links(("agent", row["agent_id"])))


def _percent(used, limit):
    return used * 100 / limit if limit else None


def budget_object(agent, spent, warn_percent=80, stop_percent=100):
    parts, percents = [], []
    for label, used, limit in (("Token", spent["tokens"], agent.get("budget_tokens")), ("Cent", spent["eur_cent"], agent.get("budget_eur_cent"))):
        if limit:
            parts.append(f"{label} {used}/{limit}")
            percents.append(_percent(used, limit))
    if not percents:
        state, summary = "ohne Grenze", "keine Grenze gesetzt"
    else:
        top = max(percents)
        state = "gestoppt" if top >= stop_percent else "Warnung" if top >= warn_percent else "im Rahmen"
        summary = " · ".join(parts)
    return _object("budget", agent["id"], "Budget " + agent["name"], state, summary, _links(("agent", agent["id"])))


def _orchestra(hub):
    return getattr(getattr(hub, "runtime", None), "orchestra", None)


def _budget(hub, agent):
    orch = _orchestra(hub)
    return budget_object(agent, orch.spent(agent["id"]), orch.config.warn_percent, orch.config.stop_percent)


def _read(fetch, build):
    def read(hub, oid):
        row = fetch(_orchestra(hub), oid)
        return build(hub, row) if row is not None else None
    return read


def _listing(rows, build):
    def listing(hub, payload):
        return [build(hub, row) for row in rows(_orchestra(hub), payload)]
    return listing


def _issue_filter(orch, payload):
    return orch.issues(state=payload.get("state"), assignee=payload.get("assignee"))


def register(registry, hub):
    if _orchestra(hub) is None:
        return []
    plain = lambda make: (lambda hub, row: make(row))
    kinds = [
        (registry.Kind("agent", "Agent", _read(lambda o, i: o.agent(i), plain(agent_object)), _listing(lambda o, p: o.agents(), plain(agent_object)), source="orchestra"), True),
        (registry.Kind("issue", "Aufgabe", _read(lambda o, i: o.issue(i), plain(issue_object)), _listing(_issue_filter, plain(issue_object)), source="orchestra"), False),
        (registry.Kind("routine", "Routine", _read(lambda o, i: o.routine(i), plain(routine_object)), _listing(lambda o, p: o.routines(), plain(routine_object)), source="orchestra"), False),
        (registry.Kind("budget", "Budget", _read(lambda o, i: o.agent(i), _budget), _listing(lambda o, p: o.agents(), _budget), source="orchestra"), False),
    ]
    for kind, replace in kinds:
        registry.register(kind, replace_placeholder=replace)
    return list(TYPES)
