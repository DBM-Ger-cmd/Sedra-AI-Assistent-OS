"""Skill library unification (Captain 2026-10-13: "doppelte Punkte zusammenlegen, damit es nicht zu Verwechslung oder Mehrfachaufruf kommt, das ist eine Aufgabe fuer Guppy").
The core library (64 skills from three repos) holds the same skill several times (test-driven-development twice, context-engineering twice, debugging variants); the coder would
find both and read both. `skill_unify.py` finds such duplicates in the index entries and merges each group into ONE entry with aliases for the others. Pure logic; the hook into
build_library and SkillLibrary.read (aliases in index.json) is wired by Claude after acceptance. GUPPI builds it, Claude wrote this file, the hidden tests and the reference
(benchmarks/devvm_refs/skill_unify)."""

NOTES = '''# Notes for skill_unify
Pure Python 3 standard library, no file, process or network access, never modify the arguments (entries are dicts, return copies where you change something), no comments and no docstrings, small private helpers instead of copied code.
'''

S1 = '''
from skill_unify import normalize_name, similarity
assert normalize_name("Test Driven_Development") == "test-driven-development"
assert normalize_name("  --API & Interface Design!  ") == "api-interface-design"
assert normalize_name("Caf\\u00e9") == "caf"
assert normalize_name(None) == ""
assert normalize_name(42) == "42"
assert normalize_name("---") == ""
assert similarity("Review a diff for bugs", "review a DIFF for bugs") == 1.0
assert similarity("alpha beta gamma", "gamma delta epsilon") == 0.2
assert similarity("alpha beta", "") == 0.0
assert similarity(None, "alpha beta") == 0.0
assert similarity("a an to", "a an to") == 0.0
assert similarity("alpha beta gamma delta", "alpha beta gamma delta epsilon") == 0.8
'''

S2 = S1 + '''
from skill_unify import group_duplicates
def e(i, name, desc): return {"id": i, "name": name, "description": desc}
rows = [e("tdd", "test-driven-development", "write the failing test first then code"),
        e("tdd-2", "Test Driven Development", "totally different words about red green refactor loops"),
        e("review", "code-review", "review a diff for correctness bugs and style"),
        e("review-b", "pr-check", "review a diff for correctness bugs and style"),
        e("sql", "sql-tuner", "tune slow sql queries and indexes"),
        e("tdd-3", "tdd", "totally different words about red green refactor loops")]
assert group_duplicates(rows) == [["review", "review-b"], ["tdd", "tdd-2", "tdd-3"]]
assert group_duplicates(rows[4:5]) == []
assert group_duplicates([]) == []
assert group_duplicates([e("a", "", "alpha beta"), e("b", "", "gamma delta")]) == []
assert group_duplicates([e("a", "", ""), e("b", "", "")]) == []
assert group_duplicates([e("a", "x", "alpha beta gamma delta"), e("b", "y", "alpha beta gamma epsilon")]) == []
assert group_duplicates([e("a", "x", "alpha beta gamma delta"), e("b", "y", "alpha beta gamma epsilon")], threshold=0.5) == [["a", "b"]]
before = [dict(r) for r in rows]
group_duplicates(rows)
assert rows == before
'''

S3 = S2 + '''
from skill_unify import pick_primary
def p(i, source, lines, flags=()): return {"id": i, "source": source, "lines": lines, "flags": list(flags)}
PRI = ["addy", "superpowers", "context"]
a, b, c = p("x-b", "superpowers", 300), p("x-a", "addy", 100), p("x-c", "other", 900)
assert pick_primary([a, b, c], PRI) is b
assert pick_primary([a, c], PRI) is a
assert pick_primary([p("m", "addy", 10), p("n", "addy", 50)], PRI)["id"] == "n"
assert pick_primary([p("m", "addy", 50), p("k", "addy", 50)], PRI)["id"] == "k"
assert pick_primary([p("f", "addy", 500, ["override"]), p("g", "context", 10)], PRI)["id"] == "g"
assert pick_primary([p("z", "other", 1), p("y", "another", 1)], PRI)["id"] == "y"
assert pick_primary([p("only", "addy", 1)], [])["id"] == "only"
assert pick_primary([{"id": "q", "source": "addy"}, {"id": "r", "source": "addy", "lines": 5}], PRI)["id"] == "r"
'''

S4 = S3 + '''
from skill_unify import merge_index, resolve
def f(i, name, desc, source, lines): return {"id": i, "name": name, "description": desc, "source": source, "lines": lines, "flags": []}
idx = [f("tdd", "test-driven-development", "write the failing test first", "superpowers", 326),
       f("sql", "sql-tuner", "tune slow sql queries", "context", 30),
       f("tdd-2", "Test Driven Development", "red green refactor", "addy", 394),
       f("tdd-3", "tdd", "write the failing test first", "context", 80)]
snapshot = [dict(x) for x in idx]
out = merge_index(idx, ["addy", "superpowers", "context"])
assert idx == snapshot
assert [x["id"] for x in out["entries"]] == ["sql", "tdd-2"]
assert out["aliases"] == {"tdd": "tdd-2", "tdd-3": "tdd-2"}
kept = out["entries"][1]
assert kept["merged_from"] == ["tdd", "tdd-3"]
assert kept["also_in"] == ["context", "superpowers"]
assert kept["name"] == "Test Driven Development" and kept["lines"] == 394
assert "merged_from" not in out["entries"][0]
assert out["entries"][0] is not idx[1]
assert merge_index([], ["addy"]) == {"entries": [], "aliases": {}}
none = merge_index(idx[1:2], ["addy"])
assert none == {"entries": [idx[1]], "aliases": {}}
assert resolve(out["aliases"], "tdd") == "tdd-2"
assert resolve(out["aliases"], "tdd-2") == "tdd-2"
assert resolve(out["aliases"], "unknown") == "unknown"
assert resolve({}, "a") == "a"
assert merge_index(idx, ["addy"], threshold=1.01)["aliases"] == {"tdd": "tdd-2"}
'''

STAGES = [
    {"name": "names", "no_own_check": True,
     "task": '''Create `skill_unify.py` with two functions.
`normalize_name(name) -> str`: None gives ""; otherwise `str(name)` in lower case, every run of characters that are not ASCII letters or digits becomes ONE "-", leading and trailing "-" are removed ("Test Driven_Development" gives "test-driven-development", "Caf\\u00e9" gives "caf", "---" gives "").
`similarity(a, b) -> float`: the words of a text are the runs of ASCII letters or digits of at least 3 characters in the lower-case text (None counts as the empty text). The result is |common words| / |all words of both| (Jaccard); 0.0 when one of the texts has no words.
No comments and no docstrings.''',
     "hidden": {"hidden_unify_1.py": S1}},
    {"name": "groups", "no_own_check": True,
     "task": '''In `skill_unify.py` (keep the functions) add `group_duplicates(entries, threshold=0.8) -> list`. `entries` is a list of dicts with "id", "name" and "description". Two entries belong together when their `normalize_name(name)` is the same and not empty, OR `similarity` of their descriptions is >= threshold.
Belonging together is transitive (a with b and b with c puts all three in one group). The result is a list of groups with at least 2 entries; a group is the sorted list of its ids; the groups are sorted by their first id. No entry is modified. No comments and no docstrings.''',
     "hidden": {"hidden_unify_2.py": S2}},
    {"name": "primary", "no_own_check": True,
     "task": '''In `skill_unify.py` add `pick_primary(entries, priority)`: `entries` are the dicts of ONE group ("id", "source", "lines" (missing = 0), "flags" (a list, missing = none)), `priority` is a list of source names, best first. Return (the same object, not a copy) the entry that is best by this order:
1. an entry without flags before an entry with flags; 2. the source that stands earlier in `priority` (a source that is not in the list, or none, comes after all listed ones); 3. more lines first; 4. the smaller id (plain string comparison). No comments and no docstrings.''',
     "hidden": {"hidden_unify_3.py": S3}},
    {"name": "all", "no_own_check": True,
     "task": '''In `skill_unify.py` add `merge_index(entries, priority, threshold=0.8) -> dict` and `resolve(aliases, skill_id) -> str`.
`merge_index` finds the groups with `group_duplicates`, takes `pick_primary` of each group, and returns {"entries": [...], "aliases": {...}}. "entries" are COPIES of the entries that stay (all entries except the non-primary members of the groups), in their original order; the primary of a group gets two more keys: "merged_from" (the sorted ids of the other members) and "also_in" (the sorted, distinct, non-empty "source" values of the other members). Entries outside any group get no new key. "aliases" maps the id of every non-primary member to the id of its primary. The argument is not modified.
`resolve(aliases, skill_id)` returns the primary id for an alias and the given id otherwise (one step, no chains).
Then read the file once more: no rule may be copied into several places, no comments, no docstrings, no leftover debug files. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_unify_full.py": S4}},
]
