"""E-11 part 1 (coder extension "learning loop", 2026-10-11): lessons from runs become small cards; the Captain approves them; unused cards go stale and are archived (life
cycle proposed / active / stale / archived, after the OpenClaw scheme); the coder gets the best matching active card for a task. Idea from Hermes background_review. This is the
card store only (pure logic, JSON in and out); proposing cards from a finished run and the Captain's approval in the UIX come after acceptance. GUPPI builds it (model comparison
2026-10-11), Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/e11_lesson_cards). Plan: <projekte>\\Guppy\\ERWEITERUNGSPLAN_CODER_2026-10-10.md."""

NOTES = '''# Notes for lesson_cards
Pure Python 3 standard library (json, re), no file, process or network access, the time is always passed in (seconds), never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
A card is a dict with exactly the keys "id", "text", "source", "state", "created", "last_used", "uses", "reason". get() and pick() return copies.
'''

COMMON = r'''
import json
from lesson_cards import Cards
D = 86400

def raises(text, fn, *args):
    try:
        fn(*args)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")
BODY
print("ok")
'''


def hidden(body):
    return COMMON.replace("BODY", body)


C1 = r"""
c = Cards()
T0 = 1000000
a = c.propose("  Read the file before you edit it, always.  ", "run-1", T0)
assert a == "LC-0001"
assert c.get(a) == {"id": "LC-0001", "text": "Read the file before you edit it, always.", "source": "run-1", "state": "proposed", "created": T0, "last_used": None, "uses": 0, "reason": None}
raises("text", c.propose, "short", "s", T0)
raises("text", c.propose, "x" * 401, "s", T0)
raises("text", c.propose, None, "s", T0)
raises("text", c.propose, " " * 30 + "a", "s", T0)
raises("source", c.propose, "a long enough lesson text", "", T0)
raises("source", c.propose, "a long enough lesson text", "   ", T0)
raises("source", c.propose, "a long enough lesson text", None, T0)
raises("duplicate", c.propose, "read the FILE before   you edit it, always.", "x", T0)
b = c.propose("abcdefghijklmnopqrst", "s", T0)
assert b == "LC-0002"
assert c.propose("y" * 400, "s", T0) == "LC-0003"
c.approve(a, T0 + 10)
assert c.get(a)["state"] == "active" and c.get(a)["last_used"] == T0 + 10
raises("state", c.approve, a, T0)
raises("state", c.reject, a, "no")
raises("unknown_card", c.use, "LC-9999", T0)
raises("unknown_card", c.get, "LC-9999")
raises("unknown_card", c.approve, "LC-9999", T0)
c.reject(b, "too vague")
assert c.get(b)["state"] == "archived" and c.get(b)["reason"] == "too vague"
raises("state", c.use, b, T0)
raises("state", c.use, "LC-0003", T0)
assert c.propose("abcdefghijklmnopqrst", "y", T0) == "LC-0004"
c.use(a, T0 + 20)
assert c.get(a)["uses"] == 1 and c.get(a)["last_used"] == T0 + 20 and c.get(a)["state"] == "active"
g = c.get(a); g["state"] = "x"
assert c.get(a)["state"] == "active"
"""

C2 = r"""
c = Cards(stale_days=14, archive_days=60)
x = c.propose("Run the hidden test before submit_result", "r", 0); c.approve(x, 0)
y = c.propose("Use edit_file instead of write_file for changes", "r", 0); c.approve(y, 5 * D)
z = c.propose("Keep functions short and without comments please", "r", 0)
assert c.sweep(13 * D) == []
assert c.sweep(14 * D) == [(x, "stale")]
assert c.sweep(14 * D) == []
c.use(x, 20 * D)
assert c.get(x)["state"] == "active" and c.get(x)["uses"] == 1
assert c.sweep(34 * D) == [(x, "stale"), (y, "stale")]
assert c.sweep(79 * D) == [(y, "archived")]
assert c.sweep(80 * D) == [(x, "archived")]
assert c.get(x)["reason"] == "unused" and c.get(z)["state"] == "proposed"
assert c.sweep(1000 * D) == []
w = Cards(stale_days=1, archive_days=2)
v = w.propose("One step per sweep only, never two at once", "r", 0); w.approve(v, 0)
assert w.sweep(200 * D) == [(v, "stale")] and w.sweep(200 * D) == [(v, "archived")]
p = Cards()
a = p.propose("Read the whole file before editing python code", "s", 0); p.approve(a, 0)
b = p.propose("Edit python files with edit_file and small changes", "s", 0); p.approve(b, 0)
cc = p.propose("Never write comments in python code files ok", "s", 0)
d = p.propose("Ask for the hidden test report after a failure", "s", 0); p.approve(d, 0)
assert [k["id"] for k in p.pick("edit the python code")] == [a]
assert [k["id"] for k in p.pick("edit the python code", 5)] == [a, b, d]
assert [k["id"] for k in p.pick("THE", 5)] == [a, d]
p.use(b, 1)
assert [k["id"] for k in p.pick("python", 2)] == [b, a]
assert p.pick("zz") == [] and p.pick("") == [] and p.pick(None) == [] and p.pick("ok an", 5) == []
assert p.pick("edit the python code")[0] == p.get(a)
q = Cards.loads(p.dumps())
assert q.get(a) == p.get(a) and q.get(cc) == p.get(cc)
assert q.propose("A brand new lesson card text here", "s", 0) == "LC-0005"
assert Cards.loads(p.dumps(), stale_days=1).stale_days == 1 and Cards.loads(p.dumps()).archive_days == 60
assert json.loads(p.dumps())["count"] == 4
"""

STAGES = [
    {"name": "cards",
     "task": """Create `lesson_cards.py` (Python 3 standard library only) with a class `Cards(stale_days=14, archive_days=60)` (keep both as attributes of the same name): a store of lesson cards. Times are seconds, always passed in.
- `propose(text, source, now) -> id`: text must be a str whose strip() has 20 to 400 characters, else ValueError("text"); source must be a str that is not empty after strip(), else ValueError("source"); when a card that is not "archived" has the same text after lower() and collapsing all white space to single spaces (" ".join(text.lower().split())): ValueError("duplicate"). The new card: {"id": "LC-0001" (then LC-0002, ... one more for every successful propose), "text": text.strip(), "source": source, "state": "proposed", "created": now, "last_used": None, "uses": 0, "reason": None}. Return the id.
- `approve(id, now)`: only a "proposed" card (else ValueError("state")) becomes "active", last_used = now.
- `reject(id, reason)`: only a "proposed" card (else ValueError("state")) becomes "archived" with reason.
- `use(id, now)`: only an "active" or "stale" card (else ValueError("state")) becomes "active", last_used = now, uses + 1.
- `get(id) -> dict`: a copy of the card.
- Any unknown id: ValueError("unknown_card").
No comments and no docstrings, never modify the arguments, small private helpers instead of copied code. Add `tests/test_lesson_cards.py` (unittest) with your own tests.""",
     "hidden": {"hidden_e11_1.py": hidden(C1)}},
    {"name": "cycle",
     "task": """Add to `Cards` in `lesson_cards.py` (one day = 86400 seconds):
- `sweep(now) -> list`: go through the cards in the order they were proposed; an "active" card with now - last_used >= stale_days days becomes "stale"; else a "stale" card with now - last_used >= archive_days days becomes "archived" with reason "unused". At most ONE step per card per sweep (an active card never goes to archived in one sweep). Return the changes as a list of (id, new_state) tuples. "proposed" and "archived" cards never change.
- `pick(task, limit=1) -> list`: the words of a text are the lower-cased runs of [a-z0-9_] with at least 3 characters. Score every "active" card by the number of distinct words it shares with task; drop cards with score 0; sort by score (high first), then uses (high first), then id; return copies of the first `limit` cards. task None or "" gives [].
- `dumps() -> str`: JSON with "count" (the number of ids given so far) and "cards" (all cards in proposal order); and `Cards.loads(text, stale_days=14, archive_days=60)` (a classmethod) that rebuilds an equal store, so new ids continue after count.
Add tests to `tests/test_lesson_cards.py`.""",
     "hidden": {"hidden_e11_2.py": hidden(C1 + C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_lesson_cards.py` and read `lesson_cards.py` once more. Make sure no state check is copied into several places, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_e11_full.py": hidden(C1 + C2)}},
]
