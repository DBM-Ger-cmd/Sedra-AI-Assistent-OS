"""Skill search ranking, round 2 (Captain 2026-10-13: "GUPPI soll die zweite Runde bauen"). Round 1 (skill_rank, built by GUPPI) counts every shared word the same. Audit result on the real libraries: "test" is in dozens of descriptions
and still counts fully, so `browser-testing-with-devtools` ranks before `test-driven-development`; in the large library the sum of many weak synonym hits in descriptions puts unrelated skills (analytics-tracking) into the result.
Round 2 changes `rank` in the existing `skill_rank.py` (seed: benchmarks/skill_rank2_seed): every word is weighted by how rare it is in the library (IDF), the synonym hits in descriptions are capped, and results far below the
best one are cut. GUPPI builds it, Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/skill_rank2)."""

NOTES = '''# Notes for skill_rank (round 2)
`skill_rank.py` is already in the workspace and works. Keep `STOP`, `stem`, `words` and `expand` exactly as they are. Pure Python 3 standard library (`math` is allowed), never modify the arguments, no comments and no docstrings, small private helpers instead of copied code. `import` lines belong at the top of the file.
'''

HEAD = '''
import math
from skill_rank import idf_table, rank, words
def e(i, name, desc): return {"id": i, "name": name, "description": desc}
def near(a, b): return abs(a - b) < 0.01
'''

S1 = HEAD + '''
T = idf_table([e("a", "alpha-beta", "gamma alpha"), e("b", "alpha", None), e("c", "delta", "beta"), {"id": "d"}])
assert set(T) == {"alpha", "beta", "gamma", "delta"}
assert near(T["alpha"], math.log(3)) and near(T["beta"], math.log(3))
assert near(T["gamma"], math.log(5)) and near(T["delta"], math.log(5))
assert idf_table([]) == {}
assert idf_table([{"id": "x"}]) == {}
one = idf_table([e("a", "alpha", "alpha alpha")])
assert set(one) == {"alpha"} and near(one["alpha"], math.log(2))
rows = [e("a", "alpha", "beta"), e("b", "gamma", "alpha")]
before = [dict(r) for r in rows]
idf_table(rows)
assert rows == before
'''

IDX = '''
IDX = [e("tdd", "test-driven-development", "write a failing test first, then the code that makes it pass"),
       e("browser", "browser-testing-with-devtools", "test pages in a browser: check the console, network and failing requests, then test again and test the fix"),
       e("sysdebug", "systematic-debugging", "find the root cause of a failure before fixing it"),
       e("debugrec", "debugging-and-error-recovery", "recovery from errors and broken builds, diagnose the failure"),
       e("review", "code-review-and-quality", "review code changes for quality and correctness"),
       e("plan", "planning-and-task-breakdown", "break a task into small steps"),
       e("docs", "documentation-and-adrs", "write documentation and decision records"),
       e("perf", "performance-optimization", "measure and speed up slow code")]
G = [["debug", "bug", "error", "fault", "failure", "crash"]]
'''

S2 = S1 + IDX + '''
r = rank(IDX, "write failing test first", G)
assert [x["id"] for x in r][:2] == ["tdd", "browser"]
assert near(r[0]["score"], 13.46) and near(r[1]["score"], 9.66)
r = rank(IDX, "test", G)
assert [x["id"] for x in r][:2] == ["browser", "tdd"] and near(r[0]["score"], 11.05) and near(r[1]["score"], 11.05)
r = rank(IDX, "debug root cause", G)
assert [x["id"] for x in r][:2] == ["debugrec", "sysdebug"] and near(r[1]["score"], 11.64)
r = rank(IDX, "review code changes", G)
assert r[0]["id"] == "review" and near(r[0]["score"], 19.68)
assert rank(IDX, "zzz qqq", G) == [] and rank(IDX, "", G) == [] and rank([], "test", G) == []
'''

S3 = S2 + '''
r = rank(IDX, "debug root cause", G)
assert near(r[0]["score"], 11.83)
r = rank(IDX, "failure", G)
assert [x["id"] for x in r] == ["debugrec", "sysdebug"] and near(r[0]["score"], 10.22) and near(r[1]["score"], 4.83)
r = rank(IDX, "review code changes", G, min_ratio=0.0)
assert [x["id"] for x in r] == ["review", "perf", "tdd"] and near(r[1]["score"], 1.3) and near(r[2]["score"], 1.3)
assert [x["id"] for x in rank(IDX, "review code changes", G, min_ratio=0.05)] == ["review", "perf", "tdd"]
assert [x["id"] for x in rank(IDX, "review code changes", G, min_ratio=0.07)] == ["review"]
CAP = [e("a", "unrelated", "bug error fault crash"), e("b", "other", "nothing")]
assert rank(CAP, "debug", [["debug", "bug", "error", "fault", "crash"]]) == [{"id": "a", "score": 1.0}]
assert near(rank([e("a", "unrelated", "bug"), e("b", "other", "nothing")], "debug", [["debug", "bug"]])[0]["score"], 0.55)
'''

S4 = S3 + '''
many = [e(f"s{i:02d}", f"alpha-{i}", "alpha") for i in range(15)]
assert [x["id"] for x in rank(many, "alpha")] == ["s00", "s01", "s02", "s03", "s04"]
assert len(rank(many, "alpha", limit=50)) == 10 and len(rank(many, "alpha", limit=0)) == 1 and len(rank(many, "alpha", limit="3")) == 3
assert rank([{"id": "x"}], "alpha") == []
assert rank([{"id": "x", "name": None, "description": None}], "alpha") == []
tie = rank([e("b", "alpha", ""), e("a", "alpha", "")], "alpha")
assert [x["id"] for x in tie] == ["a", "b"] and tie[0]["score"] == tie[1]["score"]
assert len(rank([e("a", "alpha", "")], "alpha")) == 1
before = [dict(x) for x in IDX]
rank(IDX, "debug", G)
assert IDX == before
'''

STAGES = [
    {"name": "idf", "no_own_check": True,
     "task": '''In the existing `skill_rank.py` (keep everything in it) add `idf_table(entries) -> dict`. `entries` are dicts with "id" and (optional, may be None) "name" and "description". For every entry take the set `words(name) | words(description)`; df of a stem is the number of entries whose set holds it.
The result maps every stem that occurs to `math.log(1 + n / df)` where n = `len(entries)` (natural logarithm). For an empty list, or entries without any word, the result is `{}`. Nothing is modified. `import math` goes to the top of the file. No comments and no docstrings.''',
     "hidden": {"hidden_rank2_1.py": S1}},
    {"name": "weighted", "no_own_check": True,
     "task": '''Change `rank(entries, query, groups=(), limit=5, min_ratio=0.25)` in `skill_rank.py`: the formula stays the same but every word counts with its IDF weight from `idf_table(entries)` (a stem that is not in the table weighs 0). With q = words(query), extra = expand(q, groups), n = words(name), d = words(description) of an entry and W(set) = the sum of the IDF weights of the stems in the set:
score = 4 * W(q & n) + 1 * W(q & d) + 2 * W(extra & n) + 0.5 * W(extra & d), plus 3 when q is not empty and q is a subset of n. Entries with score 0 are left out; sort by score descending, then id ascending; return the first `limit` as {"id", "score"} with the score rounded to 2 decimals; `limit` is cut to 1 to 10. (`min_ratio` is used in the next step; for now accept it.) No comments and no docstrings.''',
     "hidden": {"hidden_rank2_2.py": S2}},
    {"name": "cap_cut", "no_own_check": True,
     "task": '''Two more rules in `rank`. (1) The part `0.5 * W(extra & d)` of the score is at most 1.0 (a module level constant `DESC_SYNONYM_CAP = 1.0`). (2) After sorting, drop every result whose score is lower than `min_ratio` times the score of the best result (the best one always stays; `min_ratio=0.0` drops nothing); then apply `limit`. `limit` may be a number or a string with a number (`int(limit)` first). Nothing is modified. No comments and no docstrings.''',
     "hidden": {"hidden_rank2_3.py": S3}},
    {"name": "all", "no_own_check": True,
     "task": '''Check `rank` once more: an entry without name or description (or with None) never raises; two entries with the same score come out in id order; limit 0 gives one result and limit 50 at most ten; an empty list gives an empty list; the entries are not modified.
Then read the file once more: no rule may be copied into several places, no comments, no docstrings, all `import` lines at the top (there is one inside `words` that must move), no leftover debug files. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_rank2_full.py": S4}},
]
