"""AM-003 (Agent Manager, registry persistence), second self-development build (2026-10-06, revised 2026-10-07 after docs/AM_BAU_FEHLERANALYSE_2026-10-07.md).
SQLite store with revision CAS, idempotent commands and an outbox, in eight small stages (3 to 6 behaviours each) in the same workspace, each with a hidden test written outside the models,
and a last stage "all" with the complete hidden test. Pure stdlib (sqlite3), runs in the microVM. The workspace is seeded with the accepted AM-002 candidate (`agent_contracts.py`) via --seed.
Build only, no integration."""

NOTES = '''# Notes for agent_registry
Pure Python 3 standard library (sqlite3), no network. Uses `agent_contracts.py` of this workspace (`ContractError`, `canonical_digest`, `validate_record`) and never changes it.
All database access uses ONE connection per `Registry`; the database path is given by the caller (":memory:" or a file). Every error is a `ContractError` with a `code`.
Style: small private helper methods for every repeated check, no copies of a check in several methods, no comments, short methods.
'''

COMMON = r'''
import copy, os, tempfile
from agent_contracts import ContractError
from agent_registry import IMPORTS


def raises(code, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ContractError as exc:
        assert exc.code == code, (code, exc.code, str(exc))
        return
    raise AssertionError(f"no ContractError {code}")
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


T1 = r"""
r = Registry(":memory:")
a = r.create("template", "planner@1", {"title": "Planner", "tags": ["x"]})
assert a == {"kind": "template", "key": "planner@1", "revision": 1, "data": {"title": "Planner", "tags": ["x"]}}, a
assert r.get("template", "planner@1") == a and r.get("template", "planner@1") is not a
assert r.get("template", "nope") is None and r.get("agent", "planner@1") is None
raises("exists", r.create, "template", "planner@1", {"other": 1})
assert r.get("template", "planner@1") == a, "a failed create must not change the entry"
b = r.create("agent", "planner@1", {"state": "UNVERIFIED"})
assert b["revision"] == 1 and r.get("agent", "planner@1")["data"] == {"state": "UNVERIFIED"}
raises("bad_kind", r.create, "robot", "k", {})
raises("bad_kind", r.get, "robot", "k")
raises("bad_key", r.create, "agent", "", {})
raises("bad_key", r.create, "agent", 5, {})
raises("bad_key", r.get, "agent", "")
raises("not_canonical", r.create, "agent", "z", {"x": {1, 2}})
assert r.get("agent", "z") is None
src = {"a": [1]}; r.create("agent", "m", src); src["a"].append(2)
assert r.get("agent", "m")["data"] == {"a": [1]}
got = r.get("agent", "m"); got["data"]["a"].append(9)
assert r.get("agent", "m")["data"] == {"a": [1]}
"""

T2 = r"""
r = Registry(":memory:")
assert r.list("agent") == []
r.create("agent", "b", {"n": 2}); r.create("agent", "a", {"n": 1}); r.create("template", "t", {})
assert [x["key"] for x in r.list("agent")] == ["a", "b"] and [x["key"] for x in r.list("template")] == ["t"] and r.list("crew") == []
assert r.list("agent")[0] == {"kind": "agent", "key": "a", "revision": 1, "data": {"n": 1}}
raises("bad_kind", r.list, "robot")
path = os.path.join(tempfile.mkdtemp(), "reg.sqlite")
r1 = Registry(path); r1.create("crew", "dev", {"slots": 3}); r1.close()
r2 = Registry(path)
assert r2.get("crew", "dev") == {"kind": "crew", "key": "dev", "revision": 1, "data": {"slots": 3}}
raises("exists", r2.create, "crew", "dev", {})
assert [x["key"] for x in r2.list("crew")] == ["dev"]
r2.close()
"""

T3 = r"""
r = Registry(":memory:")
r.create("agent", "a1", {"n": 1})
u = r.update("agent", "a1", {"n": 2}, expected_revision=1)
assert u == {"kind": "agent", "key": "a1", "revision": 2, "data": {"n": 2}} and r.get("agent", "a1") == u
raises("conflict", r.update, "agent", "a1", {"n": 3}, expected_revision=1)
assert r.get("agent", "a1")["data"] == {"n": 2}
raises("conflict", r.update, "agent", "a1", {"n": 3}, expected_revision=5)
raises("not_found", r.update, "agent", "zz", {"n": 3}, expected_revision=1)
raises("bad_revision", r.update, "agent", "a1", {}, expected_revision=0)
raises("bad_revision", r.update, "agent", "a1", {}, expected_revision="2")
raises("bad_revision", r.update, "agent", "a1", {}, expected_revision=True)
raises("bad_kind", r.update, "robot", "a1", {}, expected_revision=2)
raises("bad_key", r.update, "agent", "", {}, expected_revision=2)
raises("not_canonical", r.update, "agent", "a1", {"x": float("nan")}, expected_revision=2)
assert r.get("agent", "a1")["revision"] == 2
path = os.path.join(tempfile.mkdtemp(), "reg.sqlite")
w1 = Registry(path); w1.create("agent", "x", {"v": 0})
w2 = Registry(path)
assert w1.update("agent", "x", {"v": 1}, expected_revision=1)["revision"] == 2
raises("conflict", w2.update, "agent", "x", {"v": 2}, expected_revision=1)
assert w2.get("agent", "x")["data"] == {"v": 1}
w1.close(); w2.close()
"""

T4 = r"""
r = Registry(":memory:")
r.create("agent", "a1", {"n": 1}); r.update("agent", "a1", {"n": 2}, expected_revision=1)
assert r.delete("agent", "a1", expected_revision=2) is None and r.get("agent", "a1") is None
raises("not_found", r.delete, "agent", "a1", expected_revision=2)
r.create("agent", "b1", {}); raises("conflict", r.delete, "agent", "b1", expected_revision=9)
assert r.get("agent", "b1") is not None
raises("bad_revision", r.delete, "agent", "b1", expected_revision=0)
raises("bad_revision", r.delete, "agent", "b1", expected_revision=False)
raises("bad_kind", r.delete, "robot", "b1", expected_revision=1)
r.create("agent", "a1", {"again": True}); assert r.get("agent", "a1")["revision"] == 1
assert r.list("agent")[0]["key"] == "a1"
"""

T5 = r"""
r = Registry(":memory:")
c = r.command("cmd-3", "create", "agent", "n", {"q": 1})
assert c == {"command_id": "cmd-3", "revision": 1, "replayed": False}, c
assert r.get("agent", "n") == {"kind": "agent", "key": "n", "revision": 1, "data": {"q": 1}}
assert r.command("cmd-3b", "create", "agent", "n2", {"q": 1}, expected_revision=77)["revision"] == 1
assert r.command("cmd-1", "update", "agent", "n", {"v": 2}, expected_revision=1) == {"command_id": "cmd-1", "revision": 2, "replayed": False}
assert r.get("agent", "n")["data"] == {"v": 2}
assert r.command("cmd-4", "delete", "agent", "n", {"ignored": True}, expected_revision=2) == {"command_id": "cmd-4", "revision": None, "replayed": False}
assert r.get("agent", "n") is None
raises("bad_command", r.command, "", "update", "agent", "k", {}, expected_revision=2)
raises("bad_command", r.command, None, "update", "agent", "k", {}, expected_revision=2)
raises("bad_command", r.command, "cmd-5", "explode", "agent", "k", {}, expected_revision=2)
raises("conflict", r.command, "cmd-6", "update", "agent", "n2", {"v": 5}, expected_revision=9)
assert r.get("agent", "n2")["revision"] == 1
assert r.command("cmd-6", "update", "agent", "n2", {"v": 5}, expected_revision=1)["replayed"] is False
raises("exists", r.command, "cmd-7", "create", "agent", "n2", {})
assert r.command("cmd-7", "create", "agent", "n7", {})["replayed"] is False
raises("not_found", r.command, "cmd-8", "delete", "agent", "nope", None, expected_revision=1)
"""

T6 = r"""
r = Registry(":memory:")
r.create("agent", "k", {"v": 1})
c1 = r.command("cmd-1", "update", "agent", "k", {"v": 2}, expected_revision=1)
c2 = r.command("cmd-1", "update", "agent", "k", {"v": 2}, expected_revision=1)
assert c2 == {"command_id": "cmd-1", "revision": 2, "replayed": True}, c2
assert r.get("agent", "k")["revision"] == 2
assert r.command("cmd-1", "update", "agent", "k", {"v": 2}, expected_revision=1)["replayed"] is True
raises("command_conflict", r.command, "cmd-1", "update", "agent", "k", {"v": 3}, expected_revision=1)
raises("command_conflict", r.command, "cmd-1", "update", "agent", "k", {"v": 2}, expected_revision=2)
raises("command_conflict", r.command, "cmd-1", "update", "agent", "other", {"v": 2}, expected_revision=1)
raises("command_conflict", r.command, "cmd-1", "create", "agent", "k", {"v": 2})
assert r.get("agent", "k") == {"kind": "agent", "key": "k", "revision": 2, "data": {"v": 2}}
assert r.command("cmd-3", "create", "agent", "n", {"a": 1, "b": 2}) == {"command_id": "cmd-3", "revision": 1, "replayed": False}
assert r.command("cmd-3", "create", "agent", "n", {"b": 2, "a": 1})["replayed"] is True
assert r.command("cmd-4", "delete", "agent", "n", None, expected_revision=1)["replayed"] is False
assert r.command("cmd-4", "delete", "agent", "n", None, expected_revision=1) == {"command_id": "cmd-4", "revision": None, "replayed": True}
assert r.get("agent", "n") is None
path = os.path.join(tempfile.mkdtemp(), "reg.sqlite")
a = Registry(path); a.command("c-a", "create", "agent", "p", {"s": 1}); a.close()
b = Registry(path)
assert b.command("c-a", "create", "agent", "p", {"s": 1}) == {"command_id": "c-a", "revision": 1, "replayed": True}
raises("command_conflict", b.command, "c-a", "create", "agent", "p", {"s": 2})
b.close()
"""

T7 = r"""
r = Registry(":memory:")
assert r.outbox_pending() == []
r.create("agent", "k", {"v": 1}); r.update("agent", "k", {"v": 2}, expected_revision=1)
assert r.outbox_pending() == [], "plain create/update write no outbox row"
r.command("c1", "create", "agent", "n", {"q": 1})
r.command("c2", "update", "agent", "n", {"q": 2}, expected_revision=1)
r.command("c2", "update", "agent", "n", {"q": 2}, expected_revision=1)
r.command("c3", "delete", "agent", "n", None, expected_revision=2)
p = r.outbox_pending()
assert [(e["event"], e["kind"], e["key"], e["revision"]) for e in p] == [("created", "agent", "n", 1), ("updated", "agent", "n", 2), ("deleted", "agent", "n", None)], p
assert [e["seq"] for e in p] == sorted(e["seq"] for e in p) and len(set(e["seq"] for e in p)) == 3 and all(isinstance(e["seq"], int) for e in p)
assert p[0]["data"] == {"q": 1} and p[1]["data"] == {"q": 2} and p[2]["data"] is None and p[0]["command_id"] == "c1" and p[2]["command_id"] == "c3"
assert set(p[0]) == {"seq", "event", "kind", "key", "revision", "data", "command_id"}
assert len(r.outbox_pending(limit=2)) == 2 and r.outbox_pending(limit=2)[0]["seq"] == p[0]["seq"]
raises("bad_limit", r.outbox_pending, limit=0)
raises("bad_limit", r.outbox_pending, limit="5")
before = r.outbox_pending()
raises("conflict", r.command, "c9", "update", "agent", "k", {"v": 2}, expected_revision=7)
assert r.outbox_pending() == before and r.get("agent", "k")["revision"] == 2
raises("command_conflict", r.command, "c1", "create", "agent", "n", {"q": 9})
assert r.outbox_pending() == before
path = os.path.join(tempfile.mkdtemp(), "reg.sqlite")
a = Registry(path); a.command("x1", "create", "agent", "z", {}); a.close()
b = Registry(path)
assert [e["key"] for e in b.outbox_pending()] == ["z"]
b.command("x1", "create", "agent", "z", {}); assert len(b.outbox_pending()) == 1
b.close()
"""

T8 = r"""
r = Registry(":memory:")
r.command("c1", "create", "agent", "a", {}); r.command("c2", "create", "agent", "b", {}); r.command("c3", "create", "agent", "c", {})
p = r.outbox_pending()
assert r.outbox_ack(p[0]["seq"]) is None
assert r.outbox_ack(p[0]["seq"]) is None
assert [e["key"] for e in r.outbox_pending()] == ["b", "c"]
assert [e["key"] for e in r.outbox_pending(limit=1)] == ["b"]
raises("not_found", r.outbox_ack, 99999)
r.outbox_ack(p[2]["seq"])
assert [e["key"] for e in r.outbox_pending()] == ["b"]
r.command("c4", "delete", "agent", "a", None, expected_revision=1)
assert [e["event"] for e in r.outbox_pending()] == ["created", "deleted"]
path = os.path.join(tempfile.mkdtemp(), "reg.sqlite")
a = Registry(path); a.command("x1", "create", "agent", "z", {}); a.command("x2", "create", "agent", "y", {})
first = a.outbox_pending()[0]["seq"]; a.outbox_ack(first); a.close()
b = Registry(path)
assert [e["key"] for e in b.outbox_pending()] == ["y"]
b.close()
"""

FULL = T1 + T2 + T3 + T4 + T5 + T6 + T7 + T8

HELPER = (" Put the checks of `kind`, `key`, `expected_revision` and `data` into small private helper methods that every method calls; never copy a check into several methods and write no comments. "
          "Keep every method short.")

STAGES = [
    {"name": "create_get",
     "task": """In this workspace `agent_contracts.py` already exists (do not change it). Create `agent_registry.py` (Python 3 standard library only, `sqlite3`) with `class Registry`.
`Registry(path)` opens ONE sqlite3 connection to `path` (a file path or ":memory:"), creates its tables if missing, and has `close()`. Errors are `ContractError(code, message)` from `agent_contracts`.
Entries are identified by `kind` (one of "template", "agent", "crew") and `key` (a non-empty str), and hold a `data` dict and an integer `revision` that starts at 1. An entry is the dict {"kind", "key", "revision", "data"}.
Methods: `create(kind, key, data) -> entry` and `get(kind, key) -> entry or None`. Returned dicts are copies (changing them never changes the stored data, and changing the dict you passed in later never changes the stored data). `data` is stored as JSON and
must be canonical in the sense of `canonical_digest` (call it for the check; its `not_canonical` error passes through, and nothing is stored then). Errors: unknown kind -> "bad_kind" (in create and get); `key` not a non-empty str -> "bad_key" (in create and get);
creating an existing (kind, key) -> "exists" and the existing entry stays UNCHANGED (use a plain INSERT and turn sqlite3.IntegrityError into "exists"; never INSERT OR REPLACE)." """ + HELPER + """ Add `tests/test_agent_registry.py` (unittest) with your own tests.""",
     "hidden": {"hidden_t1.py": hidden("Registry", T1)}},
    {"name": "list_persist",
     "task": """In the existing `agent_registry.py` (keep the other methods) add `list(kind) -> list of entries` sorted by key (unknown kind -> "bad_kind"). Data written by one Registry on a database file must be read by a new Registry on the same file
(`get`, `list`, and a second `create` of an existing key still gives "exists"). Add tests to `tests/test_agent_registry.py`.""",
     "hidden": {"hidden_t2.py": hidden("Registry", T2)}},
    {"name": "update",
     "task": """In the existing `agent_registry.py` (keep the other methods) add `update(kind, key, data, expected_revision) -> entry`. `expected_revision` must be an int >= 1 and not a bool, otherwise "bad_revision". A missing entry gives "not_found".
A stored revision different from `expected_revision` gives "conflict" and changes nothing. On success the new data is stored, the revision raised by 1, and the new entry returned. The check and the write must be ONE atomic step in the database
(`UPDATE ... WHERE kind=? AND key=? AND revision=?` and look at the number of changed rows; only if it is 0, look whether the entry exists to choose "not_found" or "conflict"), so that two Registry objects on the same file can never both win.
`kind`, `key` and `data` are checked as in `create` (reuse your helpers)." """ + HELPER + """ Add tests to `tests/test_agent_registry.py`.""",
     "hidden": {"hidden_t3.py": hidden("Registry", T3)}},
    {"name": "delete",
     "task": """In the existing `agent_registry.py` (keep the other methods) add `delete(kind, key, expected_revision) -> None` with the same rules as `update` for `kind`, `key`, `expected_revision`, "not_found" and "conflict" (reuse your helpers and the same atomic style: `DELETE ... WHERE ... AND revision=?`).
After a delete, a new `create` of the same key starts at revision 1 again. Add tests to `tests/test_agent_registry.py`.""",
     "hidden": {"hidden_t4.py": hidden("Registry", T4)}},
    {"name": "command_basic",
     "task": """In the existing `agent_registry.py` (keep the other methods) add `command(command_id, op, kind, key, data=None, expected_revision=None) -> dict`: a mutation with an id. `command_id` must be a non-empty str and `op` one of "create", "update", "delete", otherwise "bad_command".
It runs the same operation as `create` / `update` / `delete` (for "create", `expected_revision` is ignored; for "delete", `data` is ignored) and returns {"command_id": ..., "revision": <revision of the entry after the operation, None after a delete>, "replayed": False}.
Errors of the operation (for example "conflict", "exists", "not_found") pass through and change nothing. For now there is no replay handling. Reuse the same code as `create`/`update`/`delete`: call small private methods that do the work without committing, not copies of them.""" + HELPER + """ Add tests to `tests/test_agent_registry.py`.""",
     "hidden": {"hidden_t5.py": hidden("Registry", T5)}},
    {"name": "command_replay",
     "task": """In the existing `agent_registry.py` (keep the other methods) make `command` idempotent. Every successful command stores a receipt (in a table `receipts`: command_id, a text of the request, the revision) in the SAME database transaction as the change,
so that change and receipt are saved together or not at all (use `BEGIN IMMEDIATE ... COMMIT`, and `ROLLBACK` on any exception; create the connection with `isolation_level=None` for this). The request text is the JSON (sort_keys=True) of
[op, kind, key, data, expected_revision], where data is None for "delete" and expected_revision is None for "create". Calling `command` again with the same `command_id` and an identical request (dict key order does not matter) changes nothing and returns
{"command_id": ..., "revision": <stored revision>, "replayed": True}; the receipt is looked up BEFORE the operation runs. The same `command_id` with a different request raises "command_conflict" and changes nothing. A failed operation leaves no receipt.
Receipts survive closing and reopening the database file. Keep `create`, `update`, `delete` working.""" + HELPER + """ Add tests to `tests/test_agent_registry.py`.""",
     "hidden": {"hidden_t6.py": hidden("Registry", T6)}},
    {"name": "outbox_write",
     "task": """In the existing `agent_registry.py` (keep the other methods) add an outbox. Every successful, NOT replayed `command(...)` writes one row into a table `outbox` in the same transaction as the change and the receipt (plain `create`/`update`/`delete` write none; a failed or replayed command writes none).
A row has an integer `seq` (`INTEGER PRIMARY KEY AUTOINCREMENT`), `event` ("created", "updated" or "deleted"), `kind`, `key`, `revision` (None for "deleted"), `data` (the new data dict, None for "deleted"), `command_id`, and an `acked` flag (0 at first).
Add `outbox_pending(limit=100) -> list of dicts` with the keys seq, event, kind, key, revision, data, command_id (oldest `seq` first, only rows that are not acked; `limit` must be an int >= 1 and not a bool, otherwise "bad_limit").
The outbox survives closing and reopening the database file.""" + HELPER + """ Add tests to `tests/test_agent_registry.py`.""",
     "hidden": {"hidden_t7.py": hidden("Registry", T7)}},
    {"name": "outbox_ack",
     "task": """In the existing `agent_registry.py` (keep the other methods) add `outbox_ack(seq) -> None`: marks the row with that `seq` as acked (`acked=1`), so that `outbox_pending` no longer returns it. Acknowledging twice is fine; an unknown `seq` raises "not_found".
Acknowledgements survive closing and reopening the database file. Add tests to `tests/test_agent_registry.py`.""",
     "hidden": {"hidden_t8.py": hidden("Registry", T8)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_agent_registry.py` and read `agent_registry.py` once more. Make sure that all methods (create, get, list, update, delete, command with replay, outbox_pending, outbox_ack) work together, that no check is copied into several
methods, and that there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_full.py": hidden("Registry", FULL)}},
]
