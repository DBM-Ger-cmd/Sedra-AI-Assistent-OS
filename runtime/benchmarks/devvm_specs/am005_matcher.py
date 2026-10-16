"""AM-005 (Agent Manager, deterministic matcher), fourth self-development build (2026-10-07). Hard filter, resource fit, score and ranking as in docs 04_CAPABILITY_MATCHING.md of the archive (v1 weights 30/25/20/15/10),
pure functions on plain dicts. Five small stages with hidden tests written outside the models, and a last stage "all". Seeded with the accepted AM-002 module. Build only, no integration."""

NOTES = '''# Notes for agent_matcher
Pure Python 3 standard library, no file or network access, never modify the arguments, no comments, small private helpers instead of copied code. Uses `ContractError` from `agent_contracts.py` (do not change that file).
The matcher only RECOMMENDS: it never starts anything and never grants permissions. Same input must always give the same output (also when the candidate list is in another order).
'''

COMMON = r'''
import copy
from agent_contracts import ContractError
from agent_matcher import IMPORTS

REQ = {"must": [{"id": "code.write", "minimum_version": "1.0.0"}], "can": [{"id": "code.review", "weight": 3}, {"id": "docs.write", "weight": 1}],
       "min_qualification": "VERIFIED", "effects_allowed": ["read_only", "proposal_only", "preview", "reversible_write"]}
SNAP = {"cpu_cores": 8, "ram_mib": 16000, "vram_mib": 8000, "disk_mib": 100000, "vm_slots": 4}


def cand(agent_id="a1", **kw):
    c = {"agent_id": agent_id, "lifecycle": "ACTIVE", "qualification": "VERIFIED", "admission": {"valid": True, "revoked": False},
         "capabilities": [{"id": "code.write", "version": "1.2.0", "side_effect": "reversible_write"}],
         "stats": {"successes": 8, "runs": 8}, "available": "now", "resources": {"cpu_cores": 2, "ram_mib": 4000, "vram_mib": 0, "disk_mib": 1000, "vm_slots": 1}}
    c.update(kw)
    return c


def reasons(c, req=REQ):
    return [(r["reason_code"], r["requirement"], r["candidate"]) for r in hard_filter(c, req)]
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


M1 = r"""
assert version_at_least("1.2.0", "1.0.0") and version_at_least("1.0.0", "1.0.0") and version_at_least("2.0.0", "1.9.9") and version_at_least("1.10.0", "1.9.0")
assert not version_at_least("1.0.0", "1.0.1") and not version_at_least("0.9.9", "1.0.0") and not version_at_least("1.9.0", "1.10.0")
for a, b in (("1.0", "1.0.0"), ("1.0.0", "x"), (None, "1.0.0"), ("1.0.0", 5)):
    try: version_at_least(a, b)
    except ContractError as exc: assert exc.code == "bad_version", exc.code
    else: raise AssertionError((a, b))
assert [qualification_rank(q) for q in ("UNVERIFIED", "VERIFIED", "PROVEN", "TRUSTED")] == [0, 1, 2, 3]
for bad in ("trusted", "", None, 3, "DRAFT"):
    try: qualification_rank(bad)
    except ContractError as exc: assert exc.code == "bad_qualification", exc.code
    else: raise AssertionError(bad)
"""

M2 = r"""
assert reasons(cand()) == []
assert reasons(cand(lifecycle="QUARANTINED")) == [("lifecycle", "ACTIVE", "QUARANTINED")]
assert reasons(cand(lifecycle="RETIRED")) == [("lifecycle", "ACTIVE", "RETIRED")] and reasons(cand(lifecycle=None)) == [("lifecycle", "ACTIVE", None)]
assert reasons(cand(admission={"valid": True, "revoked": True})) == [("admission_revoked", "valid", "revoked")]
assert reasons(cand(admission={"valid": False, "revoked": False})) == [("admission_invalid", "valid", "invalid")]
assert reasons(cand(admission={"valid": False, "revoked": True})) == [("admission_revoked", "valid", "revoked")], "a revoked admission is reported as revoked even when it is no longer valid"
assert reasons(cand(admission=None)) == [("admission_invalid", "valid", "invalid")] and reasons(cand(admission={})) == [("admission_invalid", "valid", "invalid")]
assert reasons(cand(admission={"valid": "yes", "revoked": False})) == [("admission_invalid", "valid", "invalid")]
assert reasons(cand(qualification="UNVERIFIED")) == [("qualification_too_low", "VERIFIED", "UNVERIFIED")]
assert reasons(cand(qualification="bogus")) == [("qualification_too_low", "VERIFIED", "bogus")]
assert reasons(cand(qualification="TRUSTED")) == [] and reasons(cand(qualification="PROVEN")) == []
assert reasons(cand(qualification="VERIFIED"), {**REQ, "min_qualification": "PROVEN"}) == [("qualification_too_low", "PROVEN", "VERIFIED")]
assert reasons(cand(capabilities=[])) == [("missing_capability", "code.write", None)]
assert reasons(cand(capabilities=[{"id": "other", "version": "1.0.0", "side_effect": "read_only"}])) == [("missing_capability", "code.write", None)]
assert reasons(cand(capabilities=[{"id": "code.write", "version": "0.9.0", "side_effect": "reversible_write"}])) == [("version_incompatible", "1.0.0", "0.9.0")]
assert reasons(cand(capabilities=[{"id": "code.write", "version": "0.9.0", "side_effect": "reversible_write"}, {"id": "code.write", "version": "0.9.5", "side_effect": "reversible_write"}])) == [("version_incompatible", "1.0.0", "0.9.5")]
assert reasons(cand(capabilities=[{"id": "code.write", "version": "1.0.0", "side_effect": "destructive_write"}])) == [("effect_not_allowed", "code.write", "destructive_write")]
assert reasons(cand(capabilities=[{"id": "code.write", "version": "1.0.0", "side_effect": "weird"}])) == [("effect_unclassified", "code.write", "weird")]
assert reasons(cand(capabilities=[{"id": "code.write", "version": "1.0.0"}])) == [("effect_unclassified", "code.write", None)]
assert reasons(cand(capabilities=[{"id": "code.write", "version": "0.1.0", "side_effect": "read_only"}, {"id": "code.write", "version": "1.1.0", "side_effect": "reversible_write"}])) == []
req2 = {**REQ, "must": [{"id": "code.write", "minimum_version": "1.0.0"}, {"id": "tests.run", "minimum_version": "1.0.0"}]}
assert reasons(cand(), req2) == [("missing_capability", "tests.run", None)]
assert reasons(cand(lifecycle="RETIRED", qualification="UNVERIFIED", capabilities=[]), req2) == [("lifecycle", "ACTIVE", "RETIRED"), ("qualification_too_low", "VERIFIED", "UNVERIFIED"), ("missing_capability", "code.write", None), ("missing_capability", "tests.run", None)]
assert reasons(cand(), {**REQ, "must": []}) == []
assert reasons(cand(capabilities=[]), {**REQ, "must": []}) == []
r = hard_filter(cand(lifecycle="RETIRED"), REQ)[0]; assert set(r) == {"reason_code", "requirement", "candidate"}
c, q = cand(), copy.deepcopy(REQ); hard_filter(c, q); assert c == cand() and q == REQ
"""

M3 = r"""
ok = resource_fit({"cpu_cores": 2, "ram_mib": 4000}, SNAP)
assert ok == {"state": "ok", "fit": 0.75, "max_ratio": 0.25}, ok
assert resource_fit({"cpu_cores": 4, "ram_mib": 4000}, SNAP) == {"state": "ok", "fit": 0.5, "max_ratio": 0.5}
assert resource_fit({}, SNAP) == {"state": "ok", "fit": 1.0, "max_ratio": 0.0}
assert resource_fit({"cpu_cores": 0, "ram_mib": 0, "vram_mib": 0}, SNAP) == {"state": "ok", "fit": 1.0, "max_ratio": 0.0}
assert resource_fit({"cpu_cores": 8}, SNAP) == {"state": "ok", "fit": 0.0, "max_ratio": 1.0}
assert resource_fit({"vram_mib": 2000, "vm_slots": 1}, SNAP) == {"state": "ok", "fit": 0.75, "max_ratio": 0.25}
assert resource_fit({"cpu_cores": 9}, SNAP) == {"state": "queued_resource", "fit": None, "max_ratio": None}
assert resource_fit({"vram_mib": 1}, {**SNAP, "vram_mib": 0}) == {"state": "queued_resource", "fit": None, "max_ratio": None}
assert resource_fit({"cpu_cores": 1}, {**SNAP, "cpu_cores": None}) == {"state": "resource_unknown", "fit": None, "max_ratio": None}
assert resource_fit({"cpu_cores": 1}, {k: v for k, v in SNAP.items() if k != "cpu_cores"}) == {"state": "resource_unknown", "fit": None, "max_ratio": None}
assert resource_fit({"cpu_cores": 99, "ram_mib": 1}, {**SNAP, "ram_mib": None}) == {"state": "resource_unknown", "fit": None, "max_ratio": None}
assert resource_fit({"ram_mib": 1000}, {**SNAP, "cpu_cores": None})["state"] == "ok"
assert resource_fit({"cpu_cores": 1}, None) == {"state": "resource_unknown", "fit": None, "max_ratio": None}
assert resource_fit({"cpu_cores": 0}, None) == {"state": "ok", "fit": 1.0, "max_ratio": 0.0}
s, rq = dict(SNAP), {"cpu_cores": 2}; resource_fit(rq, s); assert s == SNAP and rq == {"cpu_cores": 2}
"""

M4 = r"""
sc = score_candidate(cand(), REQ, SNAP)
assert set(sc) == {"score", "components"} and set(sc["components"]) == {"fit_for_purpose", "success_rate", "resource_fit", "qualification", "availability"}, sc
c = sc["components"]
assert c["fit_for_purpose"] == 0.0 and c["success_rate"] == 0.9 and c["resource_fit"] == 0.75 and c["qualification"] == 0.5 and c["availability"] == 1.0, c
assert sc["score"] == round(30 * 0.0 + 25 * 0.9 + 20 * 0.75 + 15 * 0.5 + 10 * 1.0, 2) == 55.0, sc["score"]
full = [{"id": "code.write", "version": "1.2.0", "side_effect": "reversible_write"}, {"id": "code.review", "version": "1.0.0", "side_effect": "read_only"}, {"id": "docs.write", "version": "1.0.0", "side_effect": "proposal_only"}]
assert score_candidate(cand(capabilities=full), REQ, SNAP)["components"]["fit_for_purpose"] == 1.0
assert score_candidate(cand(capabilities=full[:2]), REQ, SNAP)["components"]["fit_for_purpose"] == 0.75
assert score_candidate(cand(capabilities=[full[0], full[2]]), REQ, SNAP)["components"]["fit_for_purpose"] == 0.25
assert score_candidate(cand(capabilities=full), {**REQ, "can": []}, SNAP)["components"]["fit_for_purpose"] == 1.0
req_v = {**REQ, "can": [{"id": "code.review", "weight": 1, "minimum_version": "2.0.0"}]}
assert score_candidate(cand(capabilities=full), req_v, SNAP)["components"]["fit_for_purpose"] == 0.0
assert score_candidate(cand(stats={"successes": 0, "runs": 0}), REQ, SNAP)["components"]["success_rate"] == 0.5
assert abs(score_candidate(cand(stats={"successes": 49, "runs": 50}), REQ, SNAP)["components"]["success_rate"] - 50 / 52) < 1e-9
assert [score_candidate(cand(qualification=q), REQ, SNAP)["components"]["qualification"] for q in ("UNVERIFIED", "VERIFIED", "PROVEN", "TRUSTED")] == [0.0, 0.5, 0.8, 1.0]
assert [score_candidate(cand(available=a), REQ, SNAP)["components"]["availability"] for a in ("now", "sequential", "busy", "other")] == [1.0, 0.5, 0.0, 0.0]
best = cand(qualification="TRUSTED", stats={"successes": 98, "runs": 98}, capabilities=full, resources={})
b = score_candidate(best, REQ, SNAP)
assert b["score"] == round(30 * 1 + 25 * 99 / 100 + 20 * 1 + 15 * 1 + 10 * 1, 2) == 99.75, b
q, sn, ca = copy.deepcopy(REQ), dict(SNAP), cand(); score_candidate(ca, q, sn); assert q == REQ and sn == SNAP and ca == cand()
x = score_candidate(cand(), REQ, {**SNAP, "cpu_cores": None})
assert x["components"]["resource_fit"] == 0.0 and x["score"] == 55.0 - 15.0, x
"""

M5 = r"""
full = [{"id": "code.write", "version": "1.2.0", "side_effect": "reversible_write"}, {"id": "code.review", "version": "1.0.0", "side_effect": "read_only"}]
pool = [cand("a-low", qualification="VERIFIED"), cand("b-top", qualification="TRUSTED", capabilities=full), cand("c-quar", lifecycle="QUARANTINED"),
        cand("d-big", resources={"cpu_cores": 64}), cand("e-unk", resources={"cpu_cores": 1}), cand("f-gone", capabilities=[]), cand("g-mid", qualification="PROVEN", capabilities=full[:1])]
snap = {**SNAP, "cpu_cores": 8}
r = match(REQ, pool, snap)
assert set(r) == {"matcher_version", "eligible", "excluded", "queued", "gaps"} and r["matcher_version"] == "1", set(r)
assert [e["agent_id"] for e in r["eligible"]] == ["b-top", "g-mid", "e-unk", "a-low"], r["eligible"]
assert [e["agent_id"] for e in r["eligible"]][:2] == ["b-top", "g-mid"]
assert [e["agent_id"] for e in r["excluded"]] == ["c-quar", "f-gone"] and r["excluded"][0]["reasons"][0]["reason_code"] == "lifecycle" and r["excluded"][1]["reasons"][0]["reason_code"] == "missing_capability"
assert r["queued"] == [{"agent_id": "d-big", "reason_code": "queued_resource"}] and r["gaps"] == []
assert set(r["eligible"][0]) == {"agent_id", "score", "components", "max_ratio"} and r["eligible"][0]["score"] > r["eligible"][1]["score"] >= r["eligible"][2]["score"]
unk = match(REQ, [cand("u1", resources={"cpu_cores": 1})], {**SNAP, "cpu_cores": None})
assert unk["eligible"] == [] and unk["queued"] == [{"agent_id": "u1", "reason_code": "resource_unknown"}] and unk["gaps"] == []
import random
for seed in range(6):
    shuffled = list(pool); random.Random(seed).shuffle(shuffled)
    assert match(REQ, shuffled, snap) == r, seed
tie = match(REQ, [cand("z", resources={"cpu_cores": 2}), cand("y", resources={"cpu_cores": 2}), cand("x", resources={"cpu_cores": 4})], SNAP)
assert [e["agent_id"] for e in tie["eligible"]] == ["y", "z", "x"], [(e["agent_id"], e["score"], e["max_ratio"]) for e in tie["eligible"]]
tie2 = match(REQ, [cand("m2", stats={"successes": 8, "runs": 8}, resources={"cpu_cores": 2}), cand("m1", stats={"successes": 8, "runs": 8}, resources={"ram_mib": 4000, "cpu_cores": 1})], SNAP)
assert [e["agent_id"] for e in tie2["eligible"]] == ["m1", "m2"] or [e["agent_id"] for e in tie2["eligible"]] == ["m2", "m1"]
assert tie2["eligible"][0]["score"] >= tie2["eligible"][1]["score"]
gap = match({**REQ, "must": [{"id": "code.write", "minimum_version": "1.0.0"}, {"id": "tests.run", "minimum_version": "1.0.0"}, {"id": "deploy", "minimum_version": "1.0.0"}]}, pool, snap)
assert gap["eligible"] == [] and gap["queued"] == [] and gap["gaps"] == [{"missing_capabilities": ["deploy", "tests.run"]}], gap["gaps"]
none = match(REQ, [], snap)
assert none == {"matcher_version": "1", "eligible": [], "excluded": [], "queued": [], "gaps": [{"missing_capabilities": ["code.write"]}]}, none
only_q = match(REQ, [cand("q1", lifecycle="RETIRED")], snap)
assert only_q["eligible"] == [] and only_q["queued"] == [] and only_q["gaps"] == [] and only_q["excluded"][0]["agent_id"] == "q1", only_q
pc, rq, sp = copy.deepcopy(pool), copy.deepcopy(REQ), dict(snap); match(rq, pc, sp); assert pc == pool and rq == REQ and sp == snap
"""

FULL = M1 + M2 + M3 + M4 + M5
NAMES = "version_at_least, qualification_rank, hard_filter, resource_fit, score_candidate, match"
STYLE = " No comments. Put repeated checks into small private helpers. Never modify the arguments."

STAGES = [
    {"name": "versions",
     "task": """In this workspace `agent_contracts.py` already exists (do not change it; it has `ContractError(code, message, field=None)` with `.code`). Create `agent_matcher.py` (Python 3 standard library only, no file or network access).
Add `version_at_least(version, minimum) -> bool`: both arguments must be str of the form "<n>.<n>.<n>" with ASCII digits only, otherwise raise `ContractError("bad_version", ...)`; return True when the version is greater than or equal to the minimum, comparing the three numbers as integers (so "1.10.0" is greater than "1.9.0").
Add `qualification_rank(q) -> int`: "UNVERIFIED" 0, "VERIFIED" 1, "PROVEN" 2, "TRUSTED" 3; anything else (also a non-str) raises `ContractError("bad_qualification", ...)`.""" + STYLE + """ Add `tests/test_agent_matcher.py` (unittest) with your own tests.""",
     "hidden": {"hidden_m1.py": hidden("version_at_least, qualification_rank", M1)}},
    {"name": "hard_filter",
     "task": """In the existing `agent_matcher.py` (keep the other functions) add `hard_filter(candidate, requirement) -> list` of exclusion reasons; an empty list means the candidate passes. A reason is a dict {"reason_code", "requirement", "candidate"}. Never raise on odd data.
`candidate` is a dict with "lifecycle", "qualification", "admission" (a dict with "valid" and "revoked"), "capabilities" (a list of dicts with "id", "version", "side_effect"). `requirement` is a dict with "must" (list of {"id", "minimum_version"}), "min_qualification" and "effects_allowed" (a list of str).
Collect ALL reasons in this order:
1. lifecycle is not exactly "ACTIVE": {"reason_code": "lifecycle", "requirement": "ACTIVE", "candidate": <the lifecycle value>}.
2. admission: if `admission` is a dict and its "revoked" is True: ("admission_revoked", "valid", "revoked"); otherwise if `admission` is not a dict or its "valid" is not exactly True: ("admission_invalid", "valid", "invalid") (tuple order: reason_code, requirement, candidate).
3. qualification rank lower than the rank of `min_qualification` (an unknown candidate qualification counts as lower than everything): ("qualification_too_low", <min_qualification>, <candidate qualification>).
4. for each entry of `must`, in the given order: if the candidate has no capability with that id: ("missing_capability", <id>, None). Else look only at the capabilities with that id whose version satisfies `version_at_least(version, minimum_version)`: if there is none: ("version_incompatible", <minimum_version>, <the highest version of the candidate's capabilities with that id>).
Otherwise take the first of those capabilities in list order: if its `side_effect` is not one of "read_only", "proposal_only", "preview", "reversible_write", "destructive_write", "external_side_effect", "privileged" (or missing): ("effect_unclassified", <id>, <side_effect or None>); else if it is not in `effects_allowed`: ("effect_not_allowed", <id>, <side_effect>).
Use dict reasons with the three keys (the tuples above only show the order of the values).""" + STYLE + """ Add tests to `tests/test_agent_matcher.py`.""",
     "hidden": {"hidden_m2.py": hidden("hard_filter", M2)}},
    {"name": "resource_fit",
     "task": """In the existing `agent_matcher.py` (keep the other functions) add `resource_fit(requested, free) -> dict`. `requested` is a dict of resource name -> needed amount (cpu_cores, ram_mib, vram_mib, disk_mib, vm_slots, or other names); `free` is a dict of the free amounts after the system reserve, or None; a value may be None or missing (unknown).
Only resources with a positive requested amount count. Result: {"state": ..., "fit": ..., "max_ratio": ...}.
- If any counted resource has an unknown free amount (missing, None, or `free` is None): {"state": "resource_unknown", "fit": None, "max_ratio": None}. This wins over queued_resource.
- Else if any counted resource needs more than is free (also when free is 0): {"state": "queued_resource", "fit": None, "max_ratio": None}.
- Else {"state": "ok", "fit": <the minimum over the counted resources of 1 - requested/free>, "max_ratio": <the maximum of requested/free>}; with no counted resource fit is 1.0 and max_ratio 0.0. Values are floats.
An unknown free amount of a resource that is not requested does not matter.""" + STYLE + """ Add tests to `tests/test_agent_matcher.py`.""",
     "hidden": {"hidden_m3.py": hidden("resource_fit", M3)}},
    {"name": "score",
     "task": """In the existing `agent_matcher.py` (keep the other functions) add `score_candidate(candidate, requirement, snapshot) -> dict` returning {"score": <float rounded to 2 decimals>, "components": {"fit_for_purpose", "success_rate", "resource_fit", "qualification", "availability"}} with each component a float from 0 to 1.
The score is 30*fit_for_purpose + 25*success_rate + 20*resource_fit + 15*qualification + 10*availability, rounded to 2 decimals.
- fit_for_purpose: `requirement["can"]` is a list of {"id", "weight", optional "minimum_version"}; the sum of the weights of the entries that the candidate's capabilities satisfy (same id and, when given, `version_at_least(version, minimum_version)`) divided by the sum of all weights; 1.0 when `can` is empty or missing.
- success_rate: with `candidate["stats"]` = {"successes": s, "runs": n}: (s + 1) / (n + 2).
- resource_fit: the "fit" of `resource_fit(candidate["resources"], snapshot)`; 0.0 when its state is not "ok".
- qualification: UNVERIFIED 0.0, VERIFIED 0.5, PROVEN 0.8, TRUSTED 1.0 (anything else 0.0).
- availability: `candidate["available"]` "now" 1.0, "sequential" 0.5, anything else 0.0.""" + STYLE + """ Add tests to `tests/test_agent_matcher.py`.""",
     "hidden": {"hidden_m4.py": hidden("score_candidate", M4)}},
    {"name": "match",
     "task": """In the existing `agent_matcher.py` (keep the other functions) add `match(requirement, candidates, snapshot) -> dict`. The result has exactly the keys "matcher_version" ("1"), "eligible", "excluded", "queued", "gaps". Process each candidate (a dict with "agent_id"):
1. `hard_filter` not empty -> excluded: {"agent_id": ..., "reasons": <the reasons>}.
2. else `resource_fit(candidate["resources"], snapshot)`: state "resource_unknown" or "queued_resource" -> queued: {"agent_id": ..., "reason_code": <the state>}.
3. else eligible: {"agent_id": ..., "score": ..., "components": ..., "max_ratio": <the resource_fit max_ratio>} using `score_candidate`.
Order: `eligible` by score descending, then max_ratio ascending, then agent_id ascending; `excluded` and `queued` by agent_id ascending. The result must not depend on the order of `candidates`.
`gaps`: when `eligible` AND `queued` are both empty, it is [{"missing_capabilities": <sorted list of the ids in requirement["must"] for which no candidate at all (also not an excluded one) has a capability with that id and a version that satisfies minimum_version>}] when that list is not empty (for an empty candidate list that is every must id); in every other case it is [].""" + STYLE + """ Add tests to `tests/test_agent_matcher.py`.""",
     "hidden": {"hidden_m5.py": hidden("match", M5)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_agent_matcher.py` and read `agent_matcher.py` once more. Make sure all functions (version_at_least, qualification_rank, hard_filter, resource_fit, score_candidate, match) work together, that no check is copied into several functions, and that there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_full_m.py": hidden(NAMES, FULL)}},
]
