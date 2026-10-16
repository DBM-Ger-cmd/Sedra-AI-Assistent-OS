"""Skill search ranking (Captain 2026-10-13: "GUPPI soll die Suche verbessern"). The first search of the skill library counts shared words of at least 3 letters, so "debug root cause" does not
find `systematic-debugging` (debug != debugging), "write failing test first" ranks `ci-cd-and-automation` before the test skills, and nothing knows that bug, error and debug mean nearly the same.
`skill_rank.py` is the new pure ranking: word stems, stop words, name hits worth more than description hits, synonym groups worth less than direct hits, a bonus when the name covers the whole
query, a fixed order for equal scores. The hook into SkillLibrary.search (and a group table for the real library) is wired by Claude after acceptance. GUPPI builds it, Claude wrote this file,
the hidden tests and the reference (benchmarks/devvm_refs/skill_rank)."""

NOTES = '''# Notes for skill_rank
Pure Python 3 standard library, no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code. `STOP` is a module level frozenset.
'''

S1 = '''
from skill_rank import stem, words, STOP
assert stem("testing") == "test"
assert stem("tests") == "test"
assert stem("debugging") == "debug"
assert stem("planning") == "plan"
assert stem("reviewed") == "review"
assert stem("stopped") == "stop"
assert stem("reviews") == "review"
assert stem("writing") == "writ"
assert stem("sing") == "sing"
assert stem("bed") == "bed"
assert stem("css") == "css"
assert stem("Testing") == "test"
assert stem("see") == "see"
assert isinstance(STOP, frozenset) and "the" in STOP and "skills" in STOP
assert words("Debugging the API Tests!") == {"debug", "api", "test"}
assert words("use when you can") == set()
assert words(None) == set()
assert words("a an of") == set()
assert words("code-review and quality") == {"code", "review", "quality"}
'''

S2 = S1 + '''
from skill_rank import expand
G = [["debug", "bug", "error", "fault"], ["test", "tdd", "spec"], ["plan", "break"]]
assert expand({"debug"}, G) == {"bug", "error", "fault"}
assert expand({"debug", "bug"}, G) == {"error", "fault"}
assert expand({"bugs"}, G) == set()
assert expand({"bug", "plan"}, G) == {"debug", "error", "fault", "break"}
assert expand({"unrelated"}, G) == set()
assert expand(set(), G) == set()
assert expand({"debug"}, []) == set()
assert expand({"test"}, [["testing", "check"]]) == {"check"}
mine = {"debug"}
expand(mine, G)
assert mine == {"debug"}
'''

S3 = S2 + '''
from skill_rank import rank
def e(i, name, desc): return {"id": i, "name": name, "description": desc}
IDX = [e("systematic-debugging", "systematic-debugging", "find the root cause of a failure before fixing it"),
       e("debugging-and-error-recovery", "debugging-and-error-recovery", "systematic root cause debugging and recovery from errors"),
       e("test-driven-development", "test-driven-development", "write a failing test first, then the code that makes it pass"),
       e("ci-cd-and-automation", "ci-cd-and-automation", "automate builds and run every test in a pipeline, first on a branch"),
       e("code-review-and-quality", "code-review-and-quality", "review code changes for quality and correctness"),
       e("planning-and-task-breakdown", "planning-and-task-breakdown", "break a task into small steps")]
assert rank(IDX, "") == []
assert rank(IDX, "the and for") == []
assert rank(IDX, "zzz qqq") == []
top = [r["id"] for r in rank(IDX, "debug root cause")]
assert top[:2] == ["debugging-and-error-recovery", "systematic-debugging"]
assert [r["id"] for r in rank(IDX, "write failing test first")][:2] == ["test-driven-development", "ci-cd-and-automation"]
assert [r["id"] for r in rank(IDX, "review code changes")][0] == "code-review-and-quality"
assert [r["id"] for r in rank(IDX, "plan small steps")][0] == "planning-and-task-breakdown"
assert rank(IDX, "debugging") == [{"id": "debugging-and-error-recovery", "score": 8.0}, {"id": "systematic-debugging", "score": 7.0}]
assert rank(IDX, "systematic debugging")[0] == {"id": "systematic-debugging", "score": 11.0}
G = [["debug", "bug", "error", "fault"]]
plain = {r["id"]: r["score"] for r in rank(IDX, "bug", G)}
assert plain == {"debugging-and-error-recovery": 5.0, "systematic-debugging": 2.0}
assert rank(IDX, "error", G)[0] == {"id": "debugging-and-error-recovery", "score": 10.5}
before = [dict(x) for x in IDX]
rank(IDX, "debug", G)
assert IDX == before
'''

S4 = S3 + '''
many = [e(f"s{i:02d}", f"alpha-{i}", "alpha") for i in range(15)]
assert [r["id"] for r in rank(many, "alpha")] == ["s00", "s01", "s02", "s03", "s04"]
assert len(rank(many, "alpha", limit=50)) == 10
assert len(rank(many, "alpha", limit=0)) == 1
assert len(rank(many, "alpha", limit=3)) == 3
assert rank([], "alpha") == []
assert rank([{"id": "x"}], "alpha") == []
assert rank([{"id": "x", "name": None, "description": None}], "alpha") == []
assert rank([e("b", "alpha", ""), e("a", "alpha", "")], "alpha") == [{"id": "a", "score": 7.0}, {"id": "b", "score": 7.0}]
assert rank([e("a", "beta", "alpha")], "alpha beta") == [{"id": "a", "score": 5.0}]
assert rank([e("a", "alpha-beta", "")], "alpha beta") == [{"id": "a", "score": 11.0}]
assert rank([e("a", "alpha", "")], "alpha beta") == [{"id": "a", "score": 4.0}]
'''

STAGES = [
    {"name": "stems", "no_own_check": True,
     "task": '''Create `skill_rank.py` with a module level frozenset `STOP` (the words: the and for with from that this use when into your you are not any all can used using skill skills) and two functions.
`stem(word) -> str`: the lower-case `str(word)`; look at the suffixes "ing", "ed", "s" in this order and take the FIRST one the word ends with, but only if at least 3 letters stay; remove it. After removing "ing" or "ed" (not "s"), when the last two letters of the rest are the same consonant (not a, e, i, o, u) remove one of them. Only one suffix is ever removed ("testing" gives "test", "debugging" gives "debug", "reviews" gives "review", "writing" gives "writ", "sing" stays "sing", "bed" stays "bed").
`words(text) -> set`: the lower-case `str(text)` (None counts as empty), its runs of ASCII letters or digits with at least 3 characters, minus the words in `STOP`, each one stemmed (the stop word check comes BEFORE stemming); the result is the set of stems.
No comments and no docstrings.''',
     "hidden": {"hidden_rank_1.py": S1}},
    {"name": "expand", "no_own_check": True,
     "task": '''In `skill_rank.py` (keep the functions) add `expand(stems, groups) -> set`. `stems` is a set of stems, `groups` is a list of word lists (synonym groups). The stems of the words of a group (use `stem`) are its members. A group applies when at least one of its members is in `stems`; the result is the union of the members of all applying groups MINUS `stems` itself. Neither argument is modified. No comments and no docstrings.''',
     "hidden": {"hidden_rank_2.py": S2}},
    {"name": "rank", "no_own_check": True,
     "task": '''In `skill_rank.py` add `rank(entries, query, groups=(), limit=5) -> list`. `entries` are dicts with "id" and (optional, may be None) "name" and "description". Let q = `words(query)`, extra = `expand(q, groups)`. For every entry let n = `words(name)` and d = `words(description)`.
score = 4 * |q & n| + 1 * |q & d| + 2 * |extra & n| + 0.5 * |extra & d|, plus 3 when q is not empty and q is a subset of n. Entries with score 0 are left out. Sort by score descending, then id ascending (plain string order). Return the first `limit` as a list of {"id": id, "score": score} with the score rounded to 2 decimals; `limit` is cut to the range 1 to 10. Nothing is modified. No comments and no docstrings.''',
     "hidden": {"hidden_rank_3.py": S3}},
    {"name": "all", "no_own_check": True,
     "task": '''Check `rank` once more against these rules: an entry without name or description (or with None) never raises; two entries with the same score come out in id order; limit 0 gives one result and limit 50 at most ten; an empty list of entries gives an empty list.
Then read the file once more: no rule may be copied into several places, no comments, no docstrings, no leftover debug files. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_rank_full.py": S4}},
]
