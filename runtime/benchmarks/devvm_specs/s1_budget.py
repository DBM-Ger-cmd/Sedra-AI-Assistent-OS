"""Spec 1, Bau-Spec s1_budget (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D1.1 `budget.py`, D1.2 spend.estimated and budget_incidents, D1.5, ORC-09; gates G2-S1-19,
G2-S1-22): `orchestra/budget.py`, the booking of what a run used and the budget incidents. A run without `usage` from the model books its output cap with estimated = 1
(an upper bound, never a guess downwards); every booking tells whether it crossed the warning or the stop threshold (only when rising over it); an incident is opened at
most once per agent and kind while it is unresolved, and the Captain's decision closes it. The arithmetic is budgetcalc.py (written by Claude after rule V4, part of the
seed benchmarks/s1_schema2_seed, as is store.py with schema 2). The thresholds come from OrchestraConfig (warn_percent, stop_percent) and are arguments here.
GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/s1_budget)."""

SEED = "benchmarks/s1_schema2_seed"      # PIPE-10: devvm_build takes this folder as --seed when none is given

NOTES = '''# Notes for s1_budget
Python 3 standard library only plus `import budgetcalc` and `from store import immediate` (store.py, budgetcalc.py and the other files of the workspace are given: do not change them).
No clock (now is an argument), no other files, no network. The connection is opened by the caller with store.open_db (rows are sqlite3.Row, isolation_level None, foreign keys on);
return plain dicts. Every write runs inside `with immediate(conn):`. Every refusal is a ValueError with exactly the code the task names.
No comments and no docstrings, small private helpers instead of copied code (one helper reads an agent row, one sums an agent's spend with budgetcalc.totals).
'''

HEAD = r'''
import store, budgetcalc
from budget import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def agent(conn, id, boss=None, tokens=None, eur=None, period="gesamt"):
    conn.execute("INSERT INTO agents (id, instance_id, template_id, name, role, reports_to, status, permission_level, budget_tokens, budget_eur_cent, budget_period, created_at, updated_at) "
                 "VALUES (?, ?, 't', ?, 'coder', ?, 'aktiv', 2, ?, ?, ?, '2026-10-21T08:00:00Z', '2026-10-21T08:00:00Z')", (id, "inst-" + id, "Name " + id, boss, tokens, eur, period))


def row(conn, id):
    return dict(conn.execute("SELECT * FROM agents WHERE id = ?", (id,)).fetchone())


def spend(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM spend ORDER BY id")]


def db():
    conn = store.open_db(":memory:")
    agent(conn, "A")
    agent(conn, "B", "A", tokens=1000)
    agent(conn, "M", "A", tokens=1000, period="monat")
    agent(conn, "E", "A", eur=500)
    return conn


T0, T1, T2 = "2026-10-21T08:00:00Z", "2026-10-21T08:00:01Z", "2026-10-21T08:00:02Z"
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
c = db()
r = book(c, "B", "T1", "M-1", {"tokens_in": 100, "tokens_out": 200, "provider_id": "llama", "model": "q"}, "lokal", T0, 512)
assert r == {"before_pct": 0, "after_pct": 30, "crossing": None}
s = spend(c)[0]
assert (s["agent_id"], s["task_id"], s["mission_id"], s["provider"], s["provider_id"], s["model"], s["ts"]) == ("B", "T1", "M-1", "lokal", "llama", "q", T0)
assert (s["tokens_in"], s["tokens_out"], s["requests"], s["eur_cent"], s["estimated"]) == (100, 200, 1, 0, 0)
r = book(c, "B", "T1", "M-1", None, "lokal", T1, 512)
assert r == {"before_pct": 30, "after_pct": 81, "crossing": "warnung"}
s = spend(c)[1]
assert (s["tokens_in"], s["tokens_out"], s["requests"], s["estimated"]) == (0, 512, 1, 1)
assert book(c, "B", "T2", None, {"tokens_in": 100, "tokens_out": 100, "requests": 2, "eur_cent": 3}, "cloud", T1, 512) == {"before_pct": 81, "after_pct": 101, "crossing": "stopp"}
assert (spend(c)[2]["requests"], spend(c)[2]["eur_cent"], spend(c)[2]["provider"]) == (2, 3, "cloud")
assert book(c, "B", "T2", None, {"tokens_out": 10}, "lokal", T2, 512) == {"before_pct": 101, "after_pct": 102, "crossing": None}
assert book(c, "A", None, None, {"tokens_in": 5}, "lokal", T2, 512) == {"before_pct": None, "after_pct": None, "crossing": None}
assert book(c, "M", None, None, {"tokens_out": 150}, "lokal", T2, 512, warn=10, stop=20) == {"before_pct": 0, "after_pct": 15, "crossing": "warnung"}
assert book(c, "M", None, None, {}, "lokal", T2, 512, warn=10, stop=20) == {"before_pct": 15, "after_pct": 15, "crossing": None}
assert spend(c)[-1]["estimated"] == 0
n = len(spend(c))
raises("budget_provider_invalid", book, c, "B", None, None, None, "extern", T2, 512)
raises("agent_not_found", book, c, "Z", None, None, None, "lokal", T2, 512)
assert len(spend(c)) == n
assert not c.in_transaction
'''

C2 = r'''
c = db()
v = state(c, row(c, "B"), T0, 80, 100)
assert v == {"grenze_token": 1000, "verbraucht_token": 0, "grenze_eur_cent": None, "verbraucht_eur_cent": 0, "prozent": 0, "stufe": "ok", "zeitraum": "gesamt"}
book(c, "B", None, None, {"tokens_in": 400, "tokens_out": 450}, "lokal", T0, 512)
v = state(c, row(c, "B"), T0, 80, 100)
assert (v["verbraucht_token"], v["prozent"], v["stufe"]) == (850, 85, "warnung")
assert state(c, row(c, "B"), T0, 90, 100)["stufe"] == "ok"
assert state(c, row(c, "B"), T0, 50, 85)["stufe"] == "gestoppt"
book(c, "M", None, None, {"tokens_out": 900}, "lokal", "2026-09-30T23:59:59Z", 512)
book(c, "M", None, None, {"tokens_out": 300}, "lokal", "2026-10-01T00:00:00Z", 512)
m = state(c, row(c, "M"), T0, 80, 100)
assert (m["verbraucht_token"], m["prozent"], m["stufe"], m["zeitraum"]) == (300, 30, "ok", "monat")
assert state(c, row(c, "M"), "2026-09-30T23:59:59Z", 80, 100)["verbraucht_token"] == 900
book(c, "E", None, None, {"tokens_out": 99999, "eur_cent": 450}, "cloud", T0, 512)
e = state(c, row(c, "E"), T0, 80, 100)
assert (e["grenze_token"], e["grenze_eur_cent"], e["verbraucht_eur_cent"], e["prozent"], e["stufe"]) == (None, 500, 450, 90, "warnung")
c.execute("UPDATE agents SET budget_tokens = 100000 WHERE id = 'E'")
assert state(c, row(c, "E"), T0, 80, 100)["prozent"] == 99
a = state(c, row(c, "A"), T0, 80, 100)
assert (a["grenze_token"], a["prozent"], a["stufe"]) == (None, None, "ok")
assert state(c, row(c, "B"), T0, 80, 100) == budgetcalc.view(row(c, "B"), budgetcalc.totals(spend(c)[:1], "gesamt", T0), 80, 100)
'''

C3 = r'''
c = db()
book(c, "B", None, None, None, "lokal", T0, 812)
i = open_incident(c, "B", "warnung", 81, T1)
assert isinstance(i, int)
inc = dict(c.execute("SELECT * FROM budget_incidents WHERE id = ?", (i,)).fetchone())
assert (inc["agent_id"], inc["kind"], inc["percent"], inc["used_tokens"], inc["limit_tokens"], inc["used_eur_cent"], inc["limit_eur_cent"]) == ("B", "warnung", 81, 812, 1000, 0, None)
assert (inc["created_at"], inc["resolved_at"], inc["resolution"], inc["request_mission_id"]) == (T1, None, None, None)
assert open_incident(c, "B", "warnung", 95, T2) == i
assert c.execute("SELECT count(*) FROM budget_incidents").fetchone()[0] == 1
s = open_incident(c, "B", "stopp", 100, T2)
assert s != i
assert open_incident(c, "E", "warnung", 90, T2) not in (i, s)
raises("incident_kind_invalid", open_incident, c, "B", "Warnung", 81, T1)
raises("agent_not_found", open_incident, c, "Z", "warnung", 81, T1)
done = resolve_incident(c, i, "erhoeht", T2)
assert (done["id"], done["resolved_at"], done["resolution"], done["kind"]) == (i, T2, "erhoeht", "warnung")
raises("incident_resolved", resolve_incident, c, i, "fortgesetzt", T2)
raises("incident_not_found", resolve_incident, c, 999, "erhoeht", T2)
raises("incident_resolution_invalid", resolve_incident, c, s, "ja", T2)
assert [resolve_incident(c, s, r, T2)["resolution"] for r in ("abgelehnt",)] == ["abgelehnt"]
again = open_incident(c, "B", "warnung", 82, T2)
assert again not in (i, s)
assert c.execute("SELECT count(*) FROM budget_incidents WHERE agent_id = 'B'").fetchone()[0] == 3
assert not c.in_transaction
'''

H1 = {"hidden_budget_1.py": hidden("book", C1)}
H2 = {**H1, "hidden_budget_2.py": hidden("book, state", C2)}
H3 = {**H2, "hidden_budget_3.py": hidden("book, open_incident, resolve_incident", C3)}

CALC = """budgetcalc.py (given): totals(spend_rows, period, now) -> {tokens, eur_cent, requests, estimated} ('gesamt' or 'monat' = the UTC month of now); percent(used, limit); stage(pct, warn, stop); crossing(before_pct, after_pct, warn, stop) -> None | 'warnung' | 'stopp'; view(agent_row, totals, warn, stop) -> {grenze_token, verbraucht_token, grenze_eur_cent, verbraucht_eur_cent, prozent, stufe, zeitraum}."""

STAGES = [
    {"name": "book",
     "task": f"""Create `budget.py` (Python 3; `import budgetcalc`, `from store import immediate`; both files are in the workspace) with `book(conn, agent_id, task_id, mission_id, usage, provider, now, cap_tokens, warn=80, stop=100)` -> {{"before_pct", "after_pct", "crossing"}}.
{CALC}
- provider must be 'lokal' or 'cloud', else ValueError('budget_provider_invalid') (checked first). Then inside `with immediate(conn):` read the agent row (none -> ValueError('agent_not_found')).
- before_pct = the agent's percent before the booking, after_pct after it: budgetcalc.view(agent row, budgetcalc.totals(all spend rows of the agent, the agent's budget_period, now), warn, stop)["prozent"] (None without a limit).
- Insert one spend row: agent_id, task_id, mission_id, provider, provider_id and model from usage, tokens_in, tokens_out, requests (default 1), eur_cent (default 0) from usage (missing numbers 0), ts = now. usage None means the model gave no usage: book tokens_in 0, tokens_out = cap_tokens and estimated = 1 (otherwise estimated 0; an empty dict is a usage with zeros).
- crossing = budgetcalc.crossing(before_pct, after_pct, warn, stop). `book` records spending that already happened: it NEVER refuses because of the budget (no limit check, a booking past 100 % is written and reported as crossing 'stopp'); only an invalid provider or an unknown agent refuse, and a refused call writes nothing.""",
     "hidden": H1},
    {"name": "state",
     "task": """Add `state(conn, agent, now, warn, stop)` to `budget.py` (keep everything else): agent is an agents row as a dict; return budgetcalc.view(agent, budgetcalc.totals(the agent's spend rows as dicts, agent['budget_period'], now), warn, stop). `book` must use the same helper for its percents.""",
     "hidden": H2},
    {"name": "incidents",
     "task": """Add to `budget.py` (keep everything else), table budget_incidents (id AUTOINCREMENT, agent_id, kind 'warnung'/'stopp', percent, used_tokens, limit_tokens, used_eur_cent, limit_eur_cent, created_at, request_mission_id, resolved_at, resolution):
- `open_incident(conn, agent_id, kind, pct, now)` -> incident id. kind not 'warnung'/'stopp' -> ValueError('incident_kind_invalid'); inside `with immediate(conn):` unknown agent -> 'agent_not_found'. When the agent already has an UNRESOLVED incident of that kind, return its id and write nothing; else insert percent = pct, used_tokens and used_eur_cent from budgetcalc.totals of the agent's period, limit_tokens/limit_eur_cent from the agent row (budget_tokens, budget_eur_cent), created_at = now.
- `resolve_incident(conn, incident_id, resolution, now)` -> the incident as a dict: resolution must be 'erhoeht', 'fortgesetzt', 'abgelehnt' or 'zeitraum' (else 'incident_resolution_invalid'); unknown id -> 'incident_not_found'; already resolved -> 'incident_resolved'; sets resolved_at = now and resolution. After that a new incident of the same kind can be opened.""",
     "hidden": H3},
]
