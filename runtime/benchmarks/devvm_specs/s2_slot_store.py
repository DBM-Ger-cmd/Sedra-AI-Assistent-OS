"""Spec 2, Bau-Spec s2_slot_store (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D2.2 `slot_store.py`, D2.3, D2.7, D2.8, SCH-02, SCH-08, SCH-09, SCH-10; gates G2-S2-02,
G2-S2-03, G2-S2-14): `jobs/slot_store.py`, the memory of the model scheduler in the test lab database (tables slot_server, slot_leases, handover_requests, slot_events): a run asks
for a slot (request), gets it when the pure rules of slotplan.py say so (take), keeps it alive (beat), gives it back (release) or loses it (reap, a server that goes away); another
process asks for the GPU (handover); the Desk reads the queue (view). The connection comes from slot_db.open_db (the seed benchmarks/s2_schema_seed); every write runs in
slot_db.immediate; times are UTC texts "YYYY-MM-DDTHH:MM:SSZ", there is no clock in the module. GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference
(benchmarks/devvm_refs/s2_slot_store)."""

SEED = "benchmarks/s2_schema_seed"      # PIPE-10: devvm_build takes this folder as --seed when none is given

NOTES = '''# Notes for s2_slot_store
Python 3 standard library only plus `from slot_db import immediate` and `from slotplan import FORMAT, STATES, admit, decide_reason, needs_cloud_offer, order` (slot_db.py, slotplan.py and the other files of the workspace are given: do not change them). No clock (now is an argument), no other files, no network.
The connection is opened by the caller with slot_db.open_db (rows are sqlite3.Row, isolation_level None); return plain dicts. Every write runs inside `with immediate(conn):`; a refusal (ValueError) is raised BEFORE anything is written.
Every refusal is a ValueError with exactly the code the task names. No comments and no docstrings, small private helpers instead of copied code.
'''

HEAD = r'''
import slot_db
from slot_store import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def at(s):
    return "2026-10-21T08:%02d:%02dZ" % divmod(s, 60)


CFG = {"age_after_s": 60, "age_cap": 5, "swap": "none", "queue_max": 3, "wait_max_s": 300}


def db():
    return slot_db.open_db(":memory:")


def raw_server(c, state="bereit", slots=2, recipe="R1", gen=3, owner=None):
    c.execute("INSERT OR REPLACE INTO slot_server (name, gen, recipe, slots, state, since, owner) VALUES ('main', ?, ?, ?, ?, ?, ?)", (gen, recipe, slots, state, at(0), owner))


def lease(c, run_id, state="wartend", priority=5, enq=0, slot=None):
    c.execute("INSERT INTO slot_leases (run_id, kind, owner, agent_id, priority, enqueued, state, slot, ttl_s) VALUES (?, 'job', 'sedra', 'A', ?, ?, ?, ?, 120)",
              (run_id, priority, at(enq), state, slot))


def state_of(c, run_id):
    return c.execute("SELECT state FROM slot_leases WHERE run_id = ?", (run_id,)).fetchone()[0]
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
c = db()
assert request(c, "j1", "job", "sedra", 5, at(0)) == {"run_id": "j1", "neu": True}
row = dict(c.execute("SELECT * FROM slot_leases WHERE run_id = 'j1'").fetchone())
assert (row["kind"], row["owner"], row["priority"], row["enqueued"], row["state"], row["ttl_s"]) == ("job", "sedra", 5, at(0), "wartend", 120)
assert (row["agent_id"], row["task_id"], row["slot"], row["server_gen"], row["started"], row["heartbeat"], row["reason"]) == (None,) * 7
assert request(c, "j1", "job", "anderer", 7, at(30)) == {"run_id": "j1", "neu": False}
assert tuple(c.execute("SELECT owner, priority, enqueued FROM slot_leases").fetchone()) == ("sedra", 5, at(0))
assert request(c, "d1", "direkt", "chat", 7, at(10), agent_id="A", task_id="T1", ttl_s=30)["neu"] is True
assert tuple(c.execute("SELECT kind, agent_id, task_id, ttl_s FROM slot_leases WHERE run_id = 'd1'").fetchone()) == ("direkt", "A", "T1", 30)
c.execute("UPDATE slot_leases SET state = 'aktiv' WHERE run_id = 'j1'")
assert request(c, "j1", "job", "sedra", 5, at(40))["neu"] is False
c.execute("UPDATE slot_leases SET state = 'unterbrochen', slot = 1 WHERE run_id = 'j1'")
assert request(c, "j1", "job", "sedra", 3, at(50)) == {"run_id": "j1", "neu": True}
assert tuple(c.execute("SELECT state, priority, enqueued, slot FROM slot_leases WHERE run_id = 'j1'").fetchone()) == ("wartend", 3, at(50), None)
for bad in ("", None, 5):
    raises("run_id_invalid", request, c, bad, "job", "sedra", 5, at(0))
raises("lease_kind_invalid", request, c, "x", "chat", "sedra", 5, at(0))
raises("owner_invalid", request, c, "x", "job", "", 5, at(0))
for bad in (10, -1, "5", True):
    raises("priority_invalid", request, c, "x", "job", "sedra", bad, at(0))
raises("ttl_invalid", request, c, "x", "job", "sedra", 5, at(0), ttl_s=0)
assert c.execute("SELECT count(*) FROM slot_leases").fetchone()[0] == 2
assert not c.in_transaction
'''

C2 = r'''
c = db()
s = set_server(c, at(0), "startet", recipe="R1", slots=2)
assert (s["state"], s["gen"], s["recipe"], s["slots"], s["since"], s["interrupted"]) == ("startet", 1, "R1", 2, at(0), [])
s = set_server(c, at(5), "bereit", pid=77)
assert (s["state"], s["gen"], s["since"], s["pid"], s["recipe"], s["slots"]) == ("bereit", 1, at(5), 77, "R1", 2)
assert set_server(c, at(9), "bereit", reason="ok")["since"] == at(5)
assert set_server(c, at(20), "startet")["gen"] == 2
set_server(c, at(21), "bereit", slots=2)
lease(c, "b", "aktiv", slot=2)
lease(c, "a", "aktiv", slot=1)
lease(c, "w", "wartend")
s = set_server(c, at(30), "aus")
assert s["interrupted"] == ["a", "b"]
assert (state_of(c, "a"), state_of(c, "b"), state_of(c, "w")) == ("unterbrochen", "unterbrochen", "wartend")
assert c.execute("SELECT reason FROM slot_leases WHERE run_id = 'a'").fetchone()[0] == "server_aus"
assert (s["state"], s["gen"], s["recipe"], s["slots"], s["pid"], s["owner"]) == ("aus", 2, None, None, None, None)
assert set_server(c, at(31), "gesperrt")["interrupted"] == []
set_server(c, at(32), "bereit", slots=1)
lease(c, "g", "aktiv", slot=1)
assert set_server(c, at(33), "gesperrt", reason="3 Neustarts")["interrupted"] == ["g"]
assert tuple(c.execute("SELECT state, reason FROM slot_server").fetchone()) == ("gesperrt", "3 Neustarts")
raises("server_state_invalid", set_server, c, at(40), "an")
raises("field_invalid", set_server, c, at(40), "bereit", color="rot")
for bad in (0, 9, "2"):
    raises("slots_invalid", set_server, c, at(40), "bereit", slots=bad)
assert c.execute("SELECT state FROM slot_server").fetchone()[0] == "gesperrt"
assert not c.in_transaction
'''

C3 = r'''
c = db()
assert note(c, "restarts", at(0), 600) == 1
assert note(c, "restarts", at(100), 600) == 2
assert note(c, "restarts", at(700), 600) == 2
assert note(c, "garbage", at(700), 300) == 1
assert note(c, "garbage", at(710), 5) == 1
assert note(c, "restarts", at(701), 3600) == 3
assert tuple(c.execute("SELECT state, since FROM slot_server").fetchone()) == ("aus", at(0))
raises("field_invalid", note, c, "pid", at(0), 600)
raises("window_invalid", note, c, "restarts", at(0), 0)
raises("window_invalid", note, c, "restarts", at(0), "600")
set_server(c, at(800), "startet", recipe="R1")
assert note(c, "restarts", at(801), 600) == 3
assert c.execute("SELECT restarts FROM slot_server").fetchone()[0].count("2026") == 3
'''

C4 = r'''
c = db()
raw_server(c, "bereit", 2)
for run_id, prio, enq in (("a", 5, 0), ("b", 5, 1), ("c", 7, 2)):
    request(c, run_id, "job", "sedra", prio, at(enq))
assert take(c, "a", at(10), CFG) == {"granted": True, "slot": 1, "reason": None}
row = dict(c.execute("SELECT * FROM slot_leases WHERE run_id = 'a'").fetchone())
assert (row["state"], row["slot"], row["server_gen"], row["started"], row["heartbeat"], row["reason"]) == ("aktiv", 1, 3, at(10), at(10), None)
assert take(c, "b", at(11), CFG)["reason"] == "wartet_in_reihe"
assert take(c, "c", at(12), CFG) == {"granted": True, "slot": 2, "reason": None}
assert take(c, "b", at(13), CFG) == {"granted": False, "slot": None, "reason": "kein_slot"}
assert tuple(c.execute("SELECT state, reason, slot FROM slot_leases WHERE run_id = 'b'").fetchone()) == ("wartend", "kein_slot", None)
c.execute("UPDATE slot_leases SET state = 'fertig' WHERE run_id = 'a'")
assert take(c, "b", at(14), CFG)["slot"] == 1
for bad in ("zz", "a"):
    raises("lease_not_requested", take, c, bad, at(15), CFG)
c2 = db()
raw_server(c2, "aus", None, None, 0)
request(c2, "x", "job", "sedra", 5, at(0))
request(c2, "y", "job", "sedra", 5, at(1))
assert take(c2, "x", at(2), CFG)["slot"] == 1
assert take(c2, "y", at(3), CFG)["reason"] == "server_startet"
c3 = db()
raw_server(c3, "bereit", 2, "R1")
request(c3, "z", "job", "sedra", 5, at(0))
assert take(c3, "z", at(1), CFG, recipe="R2")["reason"] == "model_swap_not_allowed"
assert take(c3, "z", at(2), dict(CFG, swap="idle"), recipe="R2")["granted"] is True
for state, owner, reason in (("drain", None, "drain"), ("exklusiv", "nacht", "exklusiv:nacht"), ("gesperrt", None, "gesperrt"), ("startet", None, "server_startet")):
    cx = db()
    raw_server(cx, state, 2, "R1", 4, owner)
    request(cx, "q", "job", "sedra", 5, at(0))
    assert take(cx, "q", at(1), CFG)["reason"] == reason, state
assert not c.in_transaction
'''

C5 = r'''
c = db()
raw_server(c, "bereit", 2)
request(c, "a", "job", "sedra", 5, at(0))
request(c, "b", "job", "sedra", 5, at(1))
request(c, "w", "job", "sedra", 5, at(2))
take(c, "a", at(3), CFG)
take(c, "b", at(4), CFG)
assert beat(c, "a", at(30)) is True
assert c.execute("SELECT heartbeat, started FROM slot_leases WHERE run_id = 'a'").fetchone()[:] == (at(30), at(3))
assert beat(c, "w", at(31)) is False
assert release(c, "a", "fertig", at(40)) is True
assert state_of(c, "a") == "fertig"
assert release(c, "a", "fertig", at(41)) is False
assert release(c, "zz", "fertig", at(41)) is False
assert beat(c, "a", at(42)) is False
assert release(c, "b", "unterbrochen", at(43)) is True and state_of(c, "b") == "unterbrochen"
assert release(c, "w", "fertig", at(44)) is True and state_of(c, "w") == "verfallen"
raises("outcome_invalid", release, c, "x", "verfallen", at(45))
c2 = db()
raw_server(c2, "bereit", 3)
for run_id in ("l1", "l2", "l3", "l4"):
    request(c2, run_id, "job", "sedra", 5, at(0))
take(c2, "l1", at(1), CFG)
take(c2, "l2", at(2), CFG)
c2.execute("UPDATE slot_leases SET state = 'fertig' WHERE run_id = 'l3'")
assert reap(c2, ["l1", "q"], at(50)) == ["l2", "l4"]
assert (state_of(c2, "l1"), state_of(c2, "l2"), state_of(c2, "l3"), state_of(c2, "l4")) == ("aktiv", "verfallen", "fertig", "verfallen")
assert reap(c2, [], at(51)) == ["l1"]
assert reap(c2, [], at(52)) == []
assert [e["kind"] for e in events(c2, 4)] == ["reap", "reap", "reap", "take"]
assert [e["kind"] for e in events(c)][:2] == ["release", "release"]
'''

C6 = r'''
c = db()
assert handover_request(c, "nacht", "Messung", 5, 4711, at(0)) is True
assert handover_request(c, "nacht", "Messung", 5, 4711, at(30)) is False
row = dict(c.execute("SELECT * FROM handover_requests WHERE owner = 'nacht'").fetchone())
assert (row["since"], row["heartbeat"], row["ttl_s"], row["pid"], row["purpose"], row["priority"]) == (at(0), at(30), 60, 4711, "Messung", 5)
assert handover_request(c, "bau", "devvm_build", 7, 99, at(10), ttl_s=300) is True
assert handover_request(c, "alt", "Test", 5, 1, at(5), ttl_s=10) is True
assert [r["owner"] for r in handover_pending(c, at(12))] == ["bau", "nacht", "alt"]
assert [r["owner"] for r in handover_pending(c, at(15))] == ["bau", "nacht", "alt"]
assert [r["owner"] for r in handover_pending(c, at(16))] == ["bau", "nacht"]
assert [r["owner"] for r in handover_pending(c, at(91))] == ["bau"]
assert handover_clear(c, "bau") is True
assert handover_clear(c, "bau") is False
assert [r["owner"] for r in handover_pending(c, at(14))] == ["nacht", "alt"]
assert [e["kind"] for e in events(c, 10)] == ["handover", "handover", "handover"]
raises("owner_invalid", handover_request, c, "", "x", 5, 1, at(0))
raises("priority_invalid", handover_request, c, "x", "x", 11, 1, at(0))
raises("ttl_invalid", handover_request, c, "x", "x", 5, 1, at(0), ttl_s=0)
assert not c.in_transaction
'''

C7 = r'''
c = db()
v = view(c, at(0), CFG)
assert v == {"server": {"state": "aus", "gen": 0, "recipe": None, "slots": None}, "gesamt": 0, "belegt": [], "schlange": [], "warnung": None}
raw_server(c, "bereit", 2, "R1", 4)
request(c, "j1", "job", "sedra", 5, at(0), agent_id="A1", task_id="T1")
request(c, "j2", "job", "sedra", 3, at(5), agent_id="A2", task_id="T2")
request(c, "d1", "direkt", "chat", 7, at(8))
request(c, "j3", "job", "sedra", 5, at(9), agent_id="A3")
take(c, "j1", at(10), CFG)
take(c, "d1", at(11), CFG)
take(c, "j2", at(12), CFG)
v = view(c, at(20), CFG)
assert v["server"] == {"state": "bereit", "gen": 4, "recipe": "R1", "slots": 2}
assert v["gesamt"] == 2
assert v["belegt"] == [{"slot": 1, "run_id": "j1", "agent_id": "A1", "task_id": "T1", "prioritaet": 5, "seit": at(10)},
                       {"slot": 2, "run_id": "d1", "agent_id": None, "task_id": None, "prioritaet": 7, "seit": at(11)}]
assert [q["run_id"] for q in v["schlange"]] == ["j3", "j2"]
assert v["schlange"][0] == {"run_id": "j3", "agent_id": "A3", "prioritaet": 5, "seit": at(9), "grund": None}
assert v["schlange"][1]["grund"] == "kein_slot"
assert v["warnung"] is None
aged = view(c, at(190), CFG)
assert [q["run_id"] for q in aged["schlange"]] == ["j2", "j3"]
assert aged["schlange"][0]["prioritaet"] == 3
late = view(c, at(400), CFG)
assert late["warnung"] == {"run_id": "j2", "grund": "wartezeit"}
assert view(c, at(20), dict(CFG, queue_max=1))["warnung"] == {"run_id": "j2", "grund": "schlange"}
c.execute("UPDATE slot_leases SET state = 'fertig' WHERE run_id IN ('j1', 'd1', 'j2', 'j3')")
assert view(c, at(20), CFG)["belegt"] == []
'''

H1 = {"hidden_store_1.py": hidden("request", C1)}
H2 = {**H1, "hidden_store_2.py": hidden("set_server", C2)}
H3 = {**H2, "hidden_store_3.py": hidden("note, set_server", C3)}
H4 = {**H3, "hidden_store_4.py": hidden("request, take", C4)}
H5 = {**H4, "hidden_store_5.py": hidden("request, take, beat, release, reap, events", C5)}
H6 = {**H5, "hidden_store_6.py": hidden("handover_request, handover_clear, handover_pending, events", C6)}
H7 = {**H6, "hidden_store_7.py": hidden("request, take, view", C7)}

TABLES = """Tables (slot_db.py, the seed; do not change it): slot_server (one row name='main': gen, recipe, slots, context_per_slot, state, pid, since, restarts and garbage as JSON text lists, reason, owner), slot_leases (run_id PRIMARY KEY, kind 'job'|'direkt', owner, agent_id, task_id, priority 0..9, enqueued, state 'wartend'|'aktiv'|'fertig'|'unterbrochen'|'verfallen', slot, server_gen, started, heartbeat, ttl_s, reason), handover_requests (owner PRIMARY KEY, purpose, priority, pid, since, heartbeat, ttl_s), slot_events (id, ts, kind, run_id, detail). A missing slot_server row counts as the default {name 'main', gen 0, recipe None, slots None, context_per_slot None, state 'aus', pid None, since None, restarts '[]', garbage '[]', reason None, owner None}."""

STAGES = [
    {"name": "request",
     "task": f"""Create `slot_store.py` (Python 3; `from slot_db import immediate`; slot_db.py and slotplan.py are in the workspace) with `request(conn, run_id, kind, owner, priority, now, agent_id=None, task_id=None, ttl_s=120)` -> {{"run_id": run_id, "neu": True or False}}: a run asks for a slot.
{TABLES}
Checks first, each a ValueError and before anything is written: run_id not a non-empty string -> 'run_id_invalid'; kind not 'job' or 'direkt' -> 'lease_kind_invalid'; owner not a non-empty string -> 'owner_invalid'; priority not an int (a bool counts as not an int) or outside 0..9 -> 'priority_invalid'; ttl_s not an int or < 1 -> 'ttl_invalid'.
Inside `with immediate(conn):` -- when a row with this run_id exists in the state 'wartend' or 'aktiv', change nothing and return neu False (a double request is harmless). Otherwise (no row, or a final state 'fertig', 'unterbrochen' or 'verfallen' of an earlier attempt) write the row new with INSERT OR REPLACE: state 'wartend', enqueued = now, ttl_s, the given kind, owner, priority, agent_id, task_id, and every other column NULL; return neu True.""",
     "hidden": H1},
    {"name": "server",
     "task": """Add `set_server(conn, now, state, **fields)` -> the server row as a dict plus the key "interrupted" (list of run_ids) to `slot_store.py` (keep everything else): the one server row 'main' (see the tables above) is created or changed.
Checks first (ValueError, nothing written): state not one of aus, startet, bereit, drain, exklusiv, gesperrt (import STATES from slotplan) -> 'server_state_invalid'; a field name other than recipe, slots, context_per_slot, pid, reason, owner -> 'field_invalid'; slots given and not None and not an int 1..8 -> 'slots_invalid'.
Inside `with immediate(conn):` start from the current row (or the default). state 'startet' raises gen by 1. since becomes now when the state differs from the old one or since is None. The new state is stored. State 'aus' first resets recipe, slots, context_per_slot, pid and owner to None; then the given fields are applied (gen stays). When the new state is 'aus' or 'gesperrt' and the old one was neither: every lease in the state 'aktiv' (sorted by run_id) becomes 'unterbrochen' with reason 'server_aus' resp. 'server_gesperrt', and their run_ids are the "interrupted" list (else an empty list). Save the row (INSERT OR REPLACE) and add an event row (slot_events: ts = now, kind 'server_' + state, run_id NULL, detail = recipe or empty text). Return the saved row as a dict with "interrupted".""",
     "hidden": H2},
    {"name": "note",
     "task": """Add `note(conn, field, now, window_s)` -> int to `slot_store.py` (keep everything else): counts events of the server in a time window (restarts, garbage answers).
field must be 'restarts' or 'garbage' (else ValueError('field_invalid')); window_s an int >= 1 (else ValueError('window_invalid')); checks before anything is written.
Inside `with immediate(conn):` read the server row (or the default), take the JSON list of UTC texts in that column, keep only entries >= now minus window_s seconds (text comparison is fine, same format; use the format '%Y-%m-%dT%H:%M:%SZ' to compute the limit), append now, store the list again as JSON text (json.dumps) and save the row (since becomes now when it was None; the other columns stay). Return the length of the stored list.""",
     "hidden": H3},
    {"name": "take",
     "task": """Add `take(conn, run_id, now, cfg, recipe=None)` -> {"granted": bool, "slot": int or None, "reason": text or None} to `slot_store.py` (keep everything else); `from slotplan import admit, decide_reason` (the pure rules, given).
Inside `with immediate(conn):` -- the run must be in the table in the state 'wartend', else ValueError('lease_not_requested'). Read the server (or the default), mode = the server state when it is 'drain' or 'exklusiv', else 'normal'; active = all leases in the state 'aktiv', waiting = all in the state 'wartend' (as dicts).
reason = decide_reason(server, recipe, mode, active, cfg). When reason is None and run_id is in admit(server, active, waiting, mode, now, cfg): the run gets the smallest free slot number (1..server slots when the state is 'bereit', else only 1; numbers of active leases are used), its row becomes state 'aktiv' with slot, server_gen = server gen, started = now, heartbeat = now, reason NULL; add an event (kind 'take', run_id, detail = the slot number); return {"granted": True, "slot": n, "reason": None}.
Otherwise nothing but the run's reason column changes: the reason found, or 'wartet_in_reihe' when decide_reason said None (a better-ranked run goes first); return {"granted": False, "slot": None, "reason": that text}.""",
     "hidden": H4},
    {"name": "release",
     "task": """Add to `slot_store.py` (keep everything else):
- `release(conn, run_id, outcome, now)` -> bool: outcome must be 'fertig' or 'unterbrochen' (else ValueError('outcome_invalid'), before anything is written). Inside `with immediate(conn):` -- an unknown run or one in a final state ('fertig', 'unterbrochen', 'verfallen') -> False, nothing changes. A run in the state 'aktiv' gets the outcome as its state; a run in the state 'wartend' (the request is withdrawn) becomes 'verfallen'. Add an event (kind 'release', run_id, detail = outcome). Return True.
- `beat(conn, run_id, now)` -> bool: sets heartbeat = now for a lease in the state 'aktiv' (inside `immediate`); True when a row changed, False otherwise (the lease is gone).
- `reap(conn, live_run_ids, now)` -> sorted list of run_ids: every lease in the state 'wartend' or 'aktiv' whose run_id is not in live_run_ids becomes 'verfallen' (an event of kind 'reap' with the run_id each); final rows stay; the clock never frees a lease that is still in live_run_ids.
- `events(conn, limit=20)` -> the newest `limit` rows of slot_events as dicts, newest first (by id).""",
     "hidden": H5},
    {"name": "handover",
     "task": """Add to `slot_store.py` (keep everything else): another process (a benchmark, a build) asks for the GPU.
- `handover_request(conn, owner, purpose, priority, pid, now, ttl_s=60)` -> bool: owner a non-empty string ('owner_invalid'), priority an int 0..9 ('priority_invalid'), ttl_s an int >= 1 ('ttl_invalid'); checked before anything is written. Inside `with immediate(conn):` upsert the row for the owner: purpose cut to 200 characters, priority, pid, heartbeat = now, ttl_s; since stays the old value when the owner already has a row, else now. A new row adds an event (kind 'handover', run_id NULL, detail = owner) and returns True; a refreshed row returns False.
- `handover_clear(conn, owner)` -> bool: deletes the row; True when one was deleted.
- `handover_pending(conn, now)` -> list of dicts: the rows that are alive (heartbeat plus ttl_s seconds >= now; parse the times with '%Y-%m-%dT%H:%M:%SZ'), ordered by priority (higher first), then since, then owner.""",
     "hidden": H6},
    {"name": "view",
     "task": """Add `view(conn, now, cfg)` -> dict to `slot_store.py` (keep everything else; `from slotplan import needs_cloud_offer, order`): what the Desk shows. Only reads (no transaction of its own).
{"server": {"state", "gen", "recipe", "slots"} of the server row (or the default), "gesamt": the server's slots or 0 when None, "belegt": the leases in the state 'aktiv' ordered by slot, each {"slot", "run_id", "agent_id", "task_id", "prioritaet": priority, "seit": started}, "schlange": the leases in the state 'wartend' in the order of slotplan.order(waiting, now, cfg), each {"run_id", "agent_id", "prioritaet": the stored priority (not the aged one), "seit": enqueued, "grund": the reason column}, "warnung": needs_cloud_offer(waiting, now, cfg)} (waiting = the 'wartend' leases as dicts).""",
     "hidden": H7},
]
