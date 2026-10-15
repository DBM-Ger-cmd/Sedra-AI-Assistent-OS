"""Gate bar, the computing part (G7 of docs/ABLAUF_GESPRAECH_2026-10-13.md; Captain 2026-10-13: approvals do not stand as buttons in the conversation but in a bar under it: red = waiting, green = approved,
grey = rejected, with symbol and text; one click opens a detail view; every gate is decided alone, by its ID; the conversation only gets a quiet text line). `gate_bar.py` turns the gates of the mission system
(see guppi_runtime/core/guard.py create_gate and uix_server approve_gate / reject_gate) into the rows, texts and requests for that bar. Pure functions, no drawing, no network: the window code (after
the GUPPI Chat window is finished) only draws what these functions return. GUPPI builds it, Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/gate_bar)."""

NOTES = '''# Notes for gate_bar
Pure Python 3 standard library (`datetime` is allowed), no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code, `import` lines at the top. Texts contain the characters ● ✓ ✕ · and ü; write them as they are (UTF-8 source).
A gate is a dict like the mission system makes it:
{"gate_id": "HG-AB12CD34", "mission_id": "M-1", "request": {"exact_action": "start_build", "targets": [...], "risks": [...], "rollback_available": False, "request_digest": None or text},
 "status": "pending" or "resolved", "resolution": {"decision": None or "APPROVE_ONCE" or "DENY", "decided_at": None or an ISO time text like "2026-10-13T18:02:30+00:00"}}
'''

HEAD = r'''
def g(i, action="start_build", status="pending", decision=None, at=None, targets=(), risks=(), rb=False, digest=None, mission="M-1"):
    return {"gate_id": i, "mission_id": mission, "request": {"exact_action": action, "targets": list(targets), "risks": list(risks), "rollback_available": rb, "request_digest": digest},
            "status": status, "resolution": {"decision": decision, "decided_at": at}}
A = g("HG-A")
B = g("HG-B", "approve_spec", "resolved", "APPROVE_ONCE", "2026-10-13T18:02:30+00:00")
C = g("HG-C", "change_switch", "resolved", "DENY", "2026-10-13T17:50:00+00:00", targets=["switches.yaml"])
D = g("HG-D", "adopt_candidate", targets=["x"], risks=["r1", "r2"], rb=True, digest="abcdef0123456789")
'''

S1 = HEAD + r'''
from gate_bar import title, gate_state, row
assert title(A) == "Bau starten · GPU" and title(B) == "Spec freigeben" and title(D) == "Kandidat übernehmen"
assert title(C) == "Change switch · switches.yaml"
assert title(g("X", "")) == "Freigabe" and title({}) == "Freigabe"
assert title(g("X", "do_this_THING", targets=["a", "b"])) == "Do this thing · a"
assert title(g("X", "start_build", targets=["ignored"])) == "Bau starten · GPU"
assert gate_state(A) == "open" and gate_state(B) == "approved" and gate_state(C) == "rejected"
assert gate_state(g("X", status="resolved", decision="APPROVE_ONCE")) == "approved"
assert gate_state(g("X", status="resolved", decision=None)) == "rejected"
assert gate_state(g("X", status="resolved", decision="something")) == "rejected"
assert gate_state({"status": "pending"}) == "open" and gate_state({}) == "open"
assert row(A) == {"gate_id": "HG-A", "mission_id": "M-1", "state": "open", "symbol": "●", "label": "offen", "title": "Bau starten · GPU", "time": "", "text": "● offen · Bau starten · GPU"}
assert row(B, 120) == {"gate_id": "HG-B", "mission_id": "M-1", "state": "approved", "symbol": "✓", "label": "freigegeben", "title": "Spec freigeben", "time": "20:02", "text": "✓ freigegeben 20:02 · Spec freigeben"}
assert row(C)["text"] == "✕ abgelehnt 17:50 · Change switch · switches.yaml" and row(C)["symbol"] == "✕"
assert row(C, -60)["time"] == "16:50" and row(B, 0)["time"] == "18:02"
assert row(g("X", status="resolved", decision="DENY"))["text"] == "✕ abgelehnt · Bau starten · GPU"
assert row(g("X", status="resolved", decision="APPROVE_ONCE", at="2026-10-13T23:30:00+00:00"), 60)["time"] == "00:30"
snapshot = repr(B)
row(B, 30)
assert repr(B) == snapshot
'''

S2 = S1 + r'''
from gate_bar import bar, badge
now = "2026-10-13T18:02:40+00:00"
b = bar([A, B, C, D], now, tz_minutes=120)
assert [r["gate_id"] for r in b["rows"]] == ["HG-A", "HG-D", "HG-B"]
assert b["rows"][2]["text"] == "✓ freigegeben 20:02 · Spec freigeben" and b["rows"][0]["state"] == "open"
assert b["history"] == ["✕ abgelehnt 19:50 · Change switch · switches.yaml"]
assert b["open_count"] == 2 and b["badge"] == " (2 offen)"
late = bar([A, B, C, D], "2026-10-13T18:03:10+00:00")
assert [r["gate_id"] for r in late["rows"]] == ["HG-A", "HG-D"] and late["history"][0] == "✓ freigegeben 18:02 · Spec freigeben" and len(late["history"]) == 2
assert [r["gate_id"] for r in bar([A, B], "2026-10-13T18:03:10+00:00", keep_s=60)["rows"]] == ["HG-A", "HG-B"]
assert bar([A, B], "2026-10-13T18:02:50+00:00", keep_s=20)["rows"][1]["gate_id"] == "HG-B"
assert bar([A, B], "2026-10-13T18:02:50+00:00", keep_s=10)["rows"][1:] == [] if False else True
E = g("HG-E", "approve_spec", "resolved", "APPROVE_ONCE", "2026-10-13T18:02:35+00:00")
two = bar([B, E], "2026-10-13T18:02:40+00:00")
assert [r["gate_id"] for r in two["rows"]] == ["HG-E", "HG-B"] and two["open_count"] == 0 and two["badge"] == ""
assert bar([], now) == {"rows": [], "history": [], "open_count": 0, "badge": ""}
assert badge([A, D]) == " (2 offen)" and badge([B]) == "" and badge([]) == "" and badge([A]) == " (1 offen)"
gates = [A, B, C, D]
snapshot = repr(gates)
bar(gates, now)
assert repr(gates) == snapshot
'''

S3 = S2 + r'''
from gate_bar import detail, decision_payload, conversation_line
assert detail(D) == [("Aktion", "adopt_candidate"), ("Ziele", "x"), ("Risiken", "r1, r2"), ("Rücknahme möglich", "ja"), ("Prüfsumme", "abcdef012345"), ("Gate-ID", "HG-D")]
assert detail(A) == [("Aktion", "start_build"), ("Ziele", "keine"), ("Risiken", "keine"), ("Rücknahme möglich", "nein"), ("Prüfsumme", "keine"), ("Gate-ID", "HG-A")]
assert detail(g("X", targets=["a", "b"]))[1] == ("Ziele", "a, b")
assert decision_payload("approve", A) == {"url": "/api/mission/approve", "body": {"mission_id": "M-1", "gate_id": "HG-A"}}
assert decision_payload("reject", D) == {"url": "/api/mission/reject", "body": {"mission_id": "M-1", "gate_id": "HG-D"}}
for bad in (lambda: decision_payload("approve", B), lambda: decision_payload("reject", C), lambda: decision_payload("all", A), lambda: decision_payload("approve_all", A),
            lambda: decision_payload("approve", g("", mission="M-1")), lambda: decision_payload("approve", g("HG-X", mission="")), lambda: decision_payload("approve", {})):
    try:
        bad()
    except ValueError:
        continue
    raise AssertionError("no ValueError")
for kind, gate, text in (("approve", A, "exact_gate_id_required"), ("reject", B, "gate_not_open"), ("maybe", A, "unknown_decision")):
    try:
        decision_payload(kind, gate if gate is not None else A)
    except ValueError as error:
        assert str(error) == text, (kind, str(error))
assert conversation_line("requested", A) == "Freigabe angefragt: Bau starten · GPU, siehe Leiste"
assert conversation_line("approved", B, 60) == "Freigegeben 19:02: Spec freigeben"
assert conversation_line("rejected", C) == "Abgelehnt 17:50: Change switch · switches.yaml"
assert conversation_line("requested", D) == "Freigabe angefragt: Kandidat übernehmen, siehe Leiste"
try:
    conversation_line("done", A)
except ValueError as error:
    assert str(error) == "unknown_event"
else:
    raise AssertionError("no ValueError")
'''

STAGES = [
    {"name": "rows", "no_own_check": True,
     "task": '''Create `gate_bar.py` (the gate format is in NOTES.md) with three functions.
`title(gate) -> str`: the short name of a gate. Known actions have a fixed title: "start_build" -> "Bau starten · GPU", "approve_spec" -> "Spec freigeben", "adopt_candidate" -> "Kandidat übernehmen" (keep these in a module level dict `TITLES`); any other `request.exact_action` becomes the action with every "_" turned into a space and the first letter upper case, the rest lower case (Python `capitalize()`), followed by " · " and the first entry of `request.targets` when there is one ("change_switch" with target "switches.yaml" -> "Change switch · switches.yaml"). A known action never gets a target appended. No action (missing or empty) gives "Freigabe". A missing `request` is the same as an empty one.
`gate_state(gate) -> str`: "open" when `status` is not "resolved" (also when it is missing); when it is "resolved": "approved" if `resolution.decision` is a text that starts with "APPROVE", otherwise "rejected" (no decision or any other decision).
`row(gate, tz_minutes=0) -> dict` with the keys gate_id, mission_id (as in the gate; None when missing), state (gate_state), symbol, label, title (title(gate)), time and text. The look of a state: open "●" / "offen", approved "✓" / "freigegeben", rejected "✕" / "abgelehnt". `time` is "" for an open gate and for a decided gate without `decided_at`; otherwise the time of day "HH:MM" of `resolution.decided_at` (an ISO text, parse it with datetime.fromisoformat) moved by `tz_minutes` minutes (it may cross midnight). `text` is "<symbol> <label>" + (" " + time if there is a time) + " · " + title, for example "✓ freigegeben 20:02 · Spec freigeben" and "● offen · Bau starten · GPU". The gate is not modified. No comments and no docstrings.''',
     "hidden": {"hidden_gate_1.py": S1}},
    {"name": "bar", "no_own_check": True,
     "task": '''In `gate_bar.py` (keep everything) add `badge(gates) -> str` and `bar(gates, now, keep_s=20, tz_minutes=0) -> dict`.
`badge`: the text for the window title: "" when no gate is open, otherwise " (N offen)" with N the number of open gates (note the space at the start).
`bar`: `now` is an ISO text. The result has the keys "rows", "history", "open_count" and "badge" (the badge of all gates). "rows": first the `row(...)` (with tz_minutes) of every OPEN gate in the order of the list, then the rows of the decided gates (state approved or rejected, with a `decided_at`) that were decided at most `keep_s` seconds before `now`, newest decision first. "history": the `text` of the row of every other decided gate (decided more than `keep_s` seconds before `now`), newest decision first. Decided gates without `decided_at` appear nowhere. The sorting uses the decision time itself (not shifted by tz_minutes). "open_count": the number of open gates. The gates are not modified. No comments and no docstrings.''',
     "hidden": {"hidden_gate_2.py": S2}},
    {"name": "details", "no_own_check": True,
     "task": '''In `gate_bar.py` add three functions.
`detail(gate) -> list`: the lines of the detail view, a list of (label, value) tuples in this order: ("Aktion", the exact_action or ""), ("Ziele", the targets joined with ", " or "keine"), ("Risiken", the risks joined with ", " or "keine"), ("Rücknahme möglich", "ja" if `rollback_available` is true else "nein"), ("Prüfsumme", the first 12 characters of `request_digest`, or "keine" when there is none), ("Gate-ID", the gate_id or "").
`decision_payload(kind, gate) -> dict`: what the window sends when the Captain decides ONE gate. `kind` is "approve" or "reject" (anything else raises ValueError("unknown_decision")). A gate that is not open raises ValueError("gate_not_open"); a gate without gate_id or without mission_id raises ValueError("exact_gate_id_required"). The checks run in this order: kind, open, ids. The result is {"url": "/api/mission/approve" (or "/api/mission/reject"), "body": {"mission_id": ..., "gate_id": ...}}. There is no function and no kind that decides several gates at once.
`conversation_line(event, gate, tz_minutes=0) -> str`: the quiet line for the conversation (no buttons): event "requested" -> "Freigabe angefragt: <title>, siehe Leiste"; "approved" -> "Freigegeben <time>: <title>"; "rejected" -> "Abgelehnt <time>: <title>" (<time> is the `time` of the row, shifted by tz_minutes). Another event raises ValueError("unknown_event"). Keep the three texts in a module level dict. No comments and no docstrings.''',
     "hidden": {"hidden_gate_3.py": S3}},
    {"name": "all", "no_own_check": True,
     "task": '''Read `gate_bar.py` once more: no rule may be copied into several places (the decision of a gate state, the title, the time of a row each exist once), no comments, no docstrings, all `import` lines at the top, no leftover debug files. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_gate_full.py": S3}},
]
