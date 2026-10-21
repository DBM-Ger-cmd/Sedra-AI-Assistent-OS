"""Spec 1, Bau-Spec s1_graphs (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D1.1 `graphs.py`, ORC-02, ORC-05, ORC-08; gates G2-S1-01, G2-S1-22):
`orchestra/graphs.py`, the pure graph rules of the orchestration: the organisation tree (one root, no cycle, a depth limit, no terminating with subordinates),
delegation only downwards, the mapping of a template's effect to a permission level and the cycle test for task blockers. No database, no clock, no input or output;
every refusal is ValueError('<code>') with the codes of D1.1 (the German sentences live in desk/orchestra_kinds.py). org.py and board.py import it (seed of s1_board).
GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/s1_graphs)."""

NOTES = '''# Notes for s1_graphs
Python 3 standard library only, and nothing is imported at all: no sqlite3, no files, no clock, no network. Every function is pure: it never modifies its arguments (rows are lists of dicts).
Every refusal is a ValueError with exactly the code the task names. No comments and no docstrings, small private helpers instead of copied code (ONE helper walks up the reports_to chain with a visited set).
'''

HEAD = r'''
import copy
from graphs import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def a(id, boss=None, status="aktiv"):
    return {"id": id, "reports_to": boss, "status": status}


ORG = [a("A"), a("B", "A"), a("C", "B"), a("D", "A"), a("X", "A", "beendet"), a("P", "D", "pausiert")]
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
keep = copy.deepcopy(ORG)
assert parents(ORG) == {"A": None, "B": "A", "C": "B", "D": "A", "X": "A", "P": "D"}
assert parents([]) == {}
assert parents([{"id": "Z", "status": "aktiv"}]) == {"Z": None}
for change in (a("E", "C"), a("E", "P"), a("C", "D"), a("B", "D"), a("D", "C"), a("P", "B", "pausiert")):
    assert check_org(ORG, change, 6) is None, change
raises("org_self", check_org, ORG, a("B", "B"), 6)
raises("org_self", check_org, ORG, a("N", "N"), 6)
for boss in ("Q", "X"):
    raises("org_unknown_superior", check_org, ORG, a("E", boss), 6)
raises("org_unknown_superior", check_org, ORG, a("B", "X"), 6)
for agent, boss in (("A", "B"), ("A", "C"), ("B", "C"), ("D", "P")):
    raises("org_cycle", check_org, ORG, a(agent, boss), 6)
loop = [a("A"), a("K", "L"), a("L", "K")]
raises("org_cycle", check_org, loop, a("E", "K"), 6)
assert ORG == keep
'''

C2 = r'''
raises("org_second_root", check_org, ORG, a("E"), 6)
raises("org_second_root", check_org, ORG, a("E", None, "pausiert"), 6)
raises("org_second_root", check_org, ORG, a("B"), 6)
assert check_org(ORG, a("A"), 6) is None
assert check_org(ORG, a("A", None, "pausiert"), 6) is None
assert check_org([], a("A"), 6) is None
assert check_org([a("A", None, "beendet")], a("N"), 6) is None
assert check_org([a("A", None, "beendet"), a("N", None, "beendet")], a("M"), 6) is None
assert check_org(ORG, a("E", None, "beendet"), 6) is None
raises("org_no_root", check_org, [a("A", None, "beendet"), a("B", "A")], a("C", "B"), 6)
raises("org_no_root", check_org, [a("A", None, "beendet"), a("B", "A", "pausiert")], a("C", "B", "pausiert"), 6)
assert check_org([a("A", None, "beendet"), a("B", "A", "beendet")], a("C", None, "beendet"), 6) is None
'''

C3 = r'''
deep = [a("L1")] + [a(f"L{i}", f"L{i - 1}") for i in range(2, 7)]
assert check_org(deep, a("E", "L5"), 6) is None
raises("org_too_deep", check_org, deep, a("E", "L6"), 6)
assert check_org(deep, a("E", "L6"), 7) is None
raises("org_too_deep", check_org, deep + [a("M", "L1")], a("L2", "M"), 6)
assert check_org(deep + [a("M", "L1")], a("L5", "M"), 6) is None
assert check_org(deep + [a("Z", "L6", "beendet")], a("L6", "L5"), 6) is None
raises("org_too_deep", check_org, [a("A")], a("B", "A"), 1)
assert check_org([], a("A"), 1) is None
raises("org_has_subordinates", can_terminate, ORG, "A")
raises("org_has_subordinates", can_terminate, ORG, "D")
assert can_terminate(ORG, "C") is None
assert can_terminate([a("A"), a("B", "A", "beendet")], "A") is None
assert can_terminate(ORG, "nobody") is None
'''

C4 = r'''
keep = copy.deepcopy(ORG)
assert is_below(ORG, "A", "C") is True
assert is_below(ORG, "B", "C") is True
assert is_below(ORG, "A", "P") is True
for boss, other in (("C", "B"), ("B", "D"), ("C", "C"), ("A", "A"), ("D", "C"), ("A", "nobody")):
    assert is_below(ORG, boss, other) is False, (boss, other)
assert is_below([a("K", "L"), a("L", "K")], "Q", "K") is False
assert check_delegation(ORG, "A", "C", 1) is None
assert check_delegation(ORG, "B", "C", True) is None
raises("delegation_not_allowed", check_delegation, ORG, "A", "C", 0)
raises("delegation_not_allowed", check_delegation, ORG, "A", "C", False)
raises("delegation_not_allowed", check_delegation, ORG, "C", "A", 0)
for frm, to in (("C", "B"), ("B", "D"), ("D", "C"), ("B", "B")):
    raises("delegation_not_below", check_delegation, ORG, frm, to, 1)
raises("delegation_target_inactive", check_delegation, ORG, "A", "P", 1)
raises("delegation_target_inactive", check_delegation, ORG, "D", "P", 1)
raises("delegation_target_inactive", check_delegation, ORG, "A", "X", 1)
assert ORG == keep
'''

C5 = r'''
for effect, level in (("read_only", 1), ("proposal_only", 1), ("reversible_write", 2), ("preview", 3)):
    assert level_for(effect, None) == level, effect
assert level_for("preview", 2) == 2
assert level_for("reversible_write", 6) == 2
assert level_for("read_only", 0) == 0
for effect in ("irreversible_write", "", None, "READ_ONLY"):
    raises("level_not_allowed", level_for, effect, 6)
assert inherit_level(None, 4) == 4
assert inherit_level(2, 4) == 2
assert inherit_level(5, 3) == 3
assert inherit_level(0, 3) == 0
assert has_cycle([]) is False
assert has_cycle([("t1", "t2"), ("t2", "t3"), ("t1", "t3")]) is False
assert has_cycle([("t1", "t2"), ("t2", "t3"), ("t3", "t1")]) is True
assert has_cycle([("t1", "t1")]) is True
assert has_cycle([("a", "b"), ("c", "d"), ("d", "c")]) is True
edges = [(f"n{i}", f"n{i + 1}") for i in range(3000)]
assert has_cycle(edges) is False
assert has_cycle(edges + [("n3000", "n0")]) is True
assert has_cycle(iter([("x", "y"), ("y", "x")])) is True
'''

H1 = {"hidden_graphs_1.py": hidden("parents, check_org", C1)}
H2 = {**H1, "hidden_graphs_2.py": hidden("check_org", C2)}
H3 = {**H2, "hidden_graphs_3.py": hidden("check_org, can_terminate", C3)}
H4 = {**H3, "hidden_graphs_4.py": hidden("is_below, check_delegation", C4)}
H5 = {**H4, "hidden_graphs_5.py": hidden("level_for, inherit_level, has_cycle", C5)}

ROWS = """Rows are dicts {"id", "reports_to", "status"} (reports_to None = no superior; status 'aktiv', 'pausiert' or 'beendet'; a missing reports_to counts as None)."""

STAGES = [
    {"name": "cycle",
     "task": f"""Create `graphs.py` (Python 3, no imports at all) with two functions. {ROWS}
- `parents(rows)` -> dict {{id: reports_to}} for every row.
- `check_org(rows, change, max_depth)` -> None, or ValueError('<code>'). change is a row {{id, reports_to, status}} (status missing = 'aktiv'): a new agent or the new state of an existing one (it replaces the row with the same id). Checks in this order, each the first that fails:
  1. 'org_self': change reports_to == change id.
  2. 'org_unknown_superior': reports_to is not None and no OTHER row has that id, or that row has status 'beendet'.
  3. 'org_cycle': walk up from the new superior over reports_to in the organisation WITH the change applied; reaching the agent itself is a cycle, and so is reaching any agent a second time (a loop that already exists). Use a visited set, never recursion.
  (Later stages add more checks after these; max_depth is used in a later stage.) Never modify rows or change.""",
     "hidden": H1},
    {"name": "root",
     "task": """Extend `check_org(rows, change, max_depth)` in `graphs.py` (keep everything else). After the three checks, with the change applied ("live" = status 'aktiv' or 'pausiert'):
  4. 'org_second_root': change has no superior, its status is live, and another live agent has no superior either.
  5. 'org_no_root': there are live agents but none of them is without superior.
A terminated agent (status 'beendet') never counts as a root.""",
     "hidden": H2},
    {"name": "depth",
     "task": """Extend `graphs.py` (keep everything else):
- `check_org`, last check 6. 'org_too_deep': with the change applied, a live agent ('aktiv' or 'pausiert') whose depth is greater than max_depth; the depth of an agent is the number of agents on its way up to the top including itself (root = 1). Moving an agent also moves its subordinates, so check every live agent.
- `can_terminate(rows, agent_id)` -> None, or ValueError('org_has_subordinates') when a row with reports_to == agent_id has status 'aktiv' or 'pausiert'. Unknown ids are fine (None).""",
     "hidden": H3},
    {"name": "delegate",
     "task": """Add to `graphs.py` (keep everything else):
- `is_below(rows, boss, other)` -> bool: True when boss is found walking up from other over reports_to (directly or further up); an agent is never below itself; unknown ids give False; an existing loop must not hang (visited set).
- `check_delegation(rows, frm, to, can_delegate)` -> None or ValueError, checks in this order: 'delegation_not_allowed' when can_delegate is falsy (0 or False); 'delegation_not_below' when `to` is not below `frm`; 'delegation_target_inactive' when the row of `to` does not have status 'aktiv'.""",
     "hidden": H4},
    {"name": "level",
     "task": """Add to `graphs.py` (keep everything else):
- `level_for(effect, recipe_max)` -> int: the permission level of a template effect: 'read_only' 1, 'proposal_only' 1, 'reversible_write' 2, 'preview' 3; any other effect (also None or other spelling) -> ValueError('level_not_allowed'). When recipe_max is not None the result is the smaller of both.
- `inherit_level(parent_max, assignee_level)` -> int: assignee_level when parent_max is None, else the smaller of both.
- `has_cycle(edges)` -> bool: edges is any iterable of pairs (task, blocked_by) of a directed graph task -> blocked_by; True when the graph has a cycle (a self edge counts). Without recursion: chains of several thousand edges must work.""",
     "hidden": H5},
]
