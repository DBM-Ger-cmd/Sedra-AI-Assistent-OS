"""Spec 1, Bau-Spec s1_messages (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D1.1 `messages.py`, D1.2 table agent_messages, D1.3.6, ORC-14; Spec 4 D4.3.1,
gates G2-S1-12, G2-S4-12, G2-S1-22): `orchestra/messages.py`, the conversation of the Captain with one agent (Shell D's agent window, desk type `gespraech`). A message is
added once per idempotency key (a double click of `anweisen` gives the same message, no second issue), its status follows a fixed order (accepted -> waiting for approval ->
running -> answered or error; with a standing approval accepted -> running directly; an error is possible at every step before the end), and the history is read page by
page, newest last. The connection comes from store.open_db (schema 2 of the seed benchmarks/s1_schema2_seed); every write runs in store.immediate.
GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/s1_messages)."""

SEED = "benchmarks/s1_schema2_seed"      # PIPE-10: devvm_build takes this folder as --seed when none is given

NOTES = '''# Notes for s1_messages
Python 3 standard library only plus `from store import immediate` (store.py and the other files of the workspace are given: do not change them). No clock (now is an argument), no other files, no network.
The connection is opened by the caller with store.open_db (rows are sqlite3.Row, isolation_level None, foreign keys on); return plain dicts. Every write runs inside `with immediate(conn):`.
Every refusal is a ValueError with exactly the code the task names (checked before SQLite could raise an IntegrityError). No comments and no docstrings, small private helpers instead of copied code.
'''

HEAD = r'''
import store
from messages import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def agent(conn, id, boss=None, status="aktiv"):
    conn.execute("INSERT INTO agents (id, instance_id, template_id, name, role, reports_to, status, permission_level, created_at, updated_at) "
                 "VALUES (?, ?, 't', ?, 'coder', ?, ?, 2, '2026-10-21T08:00:00Z', '2026-10-21T08:00:00Z')", (id, "inst-" + id, "Name " + id, boss, status))


def db():
    conn = store.open_db(":memory:")
    agent(conn, "A")
    agent(conn, "B", "A")
    return conn


T0, T1, T2 = "2026-10-21T08:00:00Z", "2026-10-21T08:00:01Z", "2026-10-21T08:00:02Z"
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
c = db()
r = add(c, "B", "captain", "Bitte den Bericht.", T0)
assert r["neu"] is True
assert isinstance(r["id"], int)
row = dict(c.execute("SELECT * FROM agent_messages WHERE id = ?", (r["id"],)).fetchone())
assert (row["agent_id"], row["rolle"], row["text"], row["ts"], row["status"], row["route"]) == ("B", "captain", "Bitte den Bericht.", T0, "angenommen", "lokal")
assert (row["issue_id"], row["mission_id"], row["idempotency_key"]) == (None, None, None)
r2 = add(c, "B", "agent", "Antwort", T1, status="beantwortet", issue_id="T9")
assert r2["id"] > r["id"]
assert tuple(c.execute("SELECT status, issue_id FROM agent_messages WHERE id = ?", (r2["id"],)).fetchone()) == ("beantwortet", "T9")
assert add(c, "B", "system", "x" * 8000, T1)["neu"] is True
for role in ("Captain", "", None, "tool"):
    raises("message_role_invalid", add, c, "B", role, "Hallo", T0)
raises("message_status_invalid", add, c, "B", "captain", "Hallo", T0, status="neu")
for text in ("", "   ", None, 5):
    raises("message_empty", add, c, "B", "captain", text, T0)
raises("message_too_long", add, c, "B", "captain", "x" * 8001, T0)
raises("agent_not_found", add, c, "Z", "captain", "Hallo", T0)
assert c.execute("SELECT count(*) FROM agent_messages").fetchone()[0] == 3
assert not c.in_transaction
'''

C2 = r'''
c = db()
first = add(c, "B", "captain", "Bitte den Bericht.", T0, key="captain:m-1")
assert first["neu"] is True
again = add(c, "B", "captain", "anderer Text", T1, key="captain:m-1")
assert again == {"id": first["id"], "neu": False}
assert c.execute("SELECT count(*) FROM agent_messages").fetchone()[0] == 1
assert c.execute("SELECT text FROM agent_messages").fetchone()[0] == "Bitte den Bericht."
other = add(c, "A", "captain", "Hallo", T1, key="captain:m-1")
assert other["neu"] is True
assert add(c, "B", "captain", "Neu", T1, key="captain:m-2")["neu"] is True
assert add(c, "B", "captain", "ohne", T2)["neu"] is True
assert add(c, "B", "captain", "ohne", T2)["neu"] is True
assert c.execute("SELECT count(*) FROM agent_messages").fetchone()[0] == 5
raises("message_empty", add, c, "B", "captain", "", T1, key="captain:m-1")
assert not c.in_transaction
'''

C3 = r'''
c = db()
m = add(c, "B", "captain", "Los", T0)["id"]
out = set_status(c, m, "wartet_freigabe", T1, mission_id="M-1")
assert (out["id"], out["status"], out["mission_id"], out["text"], out["ts"]) == (m, "wartet_freigabe", "M-1", "Los", T0)
assert set_status(c, m, "laeuft", T1)["mission_id"] == "M-1"
assert dict(c.execute("SELECT * FROM agent_messages WHERE id = ?", (m,)).fetchone()) == dict(out, status="laeuft")
assert set_status(c, m, "beantwortet", T2, mission_id="M-2")["mission_id"] == "M-2"
raises("message_status_invalid", set_status, c, m, "fehler", T2)
raises("message_status_invalid", set_status, c, m, "laeuft", T2)
d = add(c, "B", "captain", "Direkt", T0)["id"]
assert set_status(c, d, "laeuft", T1)["status"] == "laeuft"
assert set_status(c, d, "fehler", T1)["status"] == "fehler"
raises("message_status_invalid", set_status, c, d, "beantwortet", T2)
w = add(c, "B", "captain", "Abgelehnt", T0)["id"]
set_status(c, w, "wartet_freigabe", T1)
assert set_status(c, w, "fehler", T1)["status"] == "fehler"
x = add(c, "B", "captain", "x", T0)["id"]
for bad in ("beantwortet", "angenommen", "neu", None):
    raises("message_status_invalid", set_status, c, x, bad, T1)
assert set_status(c, x, "fehler", T1)["status"] == "fehler"
raises("message_not_found", set_status, c, 999, "laeuft", T1)
assert tuple(c.execute("SELECT status, ts, mission_id FROM agent_messages WHERE id = ?", (m,)).fetchone()) == ("beantwortet", T0, "M-2")
assert not c.in_transaction
'''

C4 = r'''
c = db()
ids = [add(c, "B", "captain" if i % 2 else "agent", "Nachricht %d" % i, T0)["id"] for i in range(7)]
add(c, "A", "captain", "fremd", T0)
p = page(c, "B", limit=3)
assert [m["id"] for m in p["items"]] == ids[4:]
assert p["mehr"] is True
assert sorted(p["items"][0]) == sorted(["id", "agent_id", "rolle", "text", "ts", "status", "issue_id", "mission_id", "route", "provider_id", "model", "idempotency_key"])
assert p["items"][-1]["text"] == "Nachricht 6"
p2 = page(c, "B", before_id=ids[4], limit=3)
assert ([m["id"] for m in p2["items"]], p2["mehr"]) == (ids[1:4], True)
p3 = page(c, "B", before_id=ids[1], limit=3)
assert ([m["id"] for m in p3["items"]], p3["mehr"]) == (ids[:1], False)
assert page(c, "B") == {"items": page(c, "B", limit=200)["items"], "mehr": False}
assert len(page(c, "B")["items"]) == 7
assert page(c, "Z") == {"items": [], "mehr": False}
assert page(c, "B", limit=7)["mehr"] is False
for limit in (0, 201, "5", True, None):
    raises("page_limit_invalid", page, c, "B", None, limit)
assert last(c, "B") == ids[-1]
assert last(c, "Z") is None
assert last(c, "A") == ids[-1] + 1
c.execute("BEGIN")
assert page(c, "B", limit=2) == {"items": p["items"][1:], "mehr": True}
assert last(c, "B") == ids[-1]
c.execute("COMMIT")
'''

H1 = {"hidden_messages_1.py": hidden("add", C1)}
H2 = {**H1, "hidden_messages_2.py": hidden("add", C2)}
H3 = {**H2, "hidden_messages_3.py": hidden("add, set_status", C3)}
H4 = {**H3, "hidden_messages_4.py": hidden("add, page, last", C4)}

TABLE = """Table (store.py, schema 2): agent_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT NOT NULL REFERENCES agents(id), rolle ('captain','agent','system'), text (at most 8000), ts, status ('angenommen','wartet_freigabe','laeuft','beantwortet','fehler'), issue_id, mission_id, route (default 'lokal'), provider_id, model, idempotency_key; UNIQUE (agent_id, idempotency_key) when the key is not NULL)."""

STAGES = [
    {"name": "add",
     "task": f"""Create `messages.py` (Python 3; `from store import immediate`; store.py is in the workspace) with `add(conn, agent_id, rolle, text, now, key=None, status='angenommen', issue_id=None)` -> {{"id": int, "neu": True}}.
{TABLE}
Checks in this order, each a ValueError: rolle not one of captain/agent/system -> 'message_role_invalid'; status not one of the five -> 'message_status_invalid'; text not a string or empty after strip -> 'message_empty'; longer than 8000 characters -> 'message_too_long'; then, inside `with immediate(conn):`, no row in agents with that id -> 'agent_not_found'.
Insert the row (ts = now, the given status and issue_id, idempotency_key = key; route keeps its default) and return its id with "neu": True. A refused call writes nothing.""",
     "hidden": H1},
    {"name": "idem",
     "task": """Extend `add` in `messages.py` (keep everything else): when key is not None and the agent already has a message with that idempotency key, return {"id": <that message's id>, "neu": False} and write nothing (the text of the old message stays). The key is per agent (another agent may use the same key). The checks of rolle, status and text still come first.""",
     "hidden": H2},
    {"name": "status",
     "task": """Add `set_status(conn, msg_id, status, now, mission_id=None)` -> the message as a dict (all columns) to `messages.py` (keep everything else), inside `with immediate(conn):`.
Unknown msg_id -> ValueError('message_not_found'). Allowed steps only (else ValueError('message_status_invalid'), also for an unknown status): angenommen -> wartet_freigabe, laeuft or fehler; wartet_freigabe -> laeuft or fehler; laeuft -> beantwortet or fehler; beantwortet and fehler are final.
mission_id: when given it replaces the stored one, when None the stored one stays. Only status and mission_id change: ts stays the time of the message.""",
     "hidden": H3},
    {"name": "page",
     "task": """Add to `messages.py` (keep everything else):
- `page(conn, agent_id, before_id=None, limit=50)` -> {"items": [...], "mehr": bool}: the agent's messages with id < before_id (all when None), the NEWEST `limit` of them, returned oldest first (newest last) as dicts with all columns; mehr is True when older messages than those returned exist. limit must be an int (`type(limit) is int`) from 1 to 200, else ValueError('page_limit_invalid'). An unknown agent gives no items.
- `last(conn, agent_id)` -> the id of the agent's newest message, or None.
Both only read (no `immediate`, no transaction of their own): they also work inside a transaction the caller has open.""",
     "hidden": H4},
]
