"""Skill search ranking, round 3 (Captain 2026-10-13: "erstmal offene punkte angehen"). After round 2 the query "write failing test first" scores `test-driven-development` and `browser-testing-with-devtools` the same (9.94): both
descriptions hold only the word "test", and the stemmer turns "testing" and "test" into one stem, so the order was decided by the id. A name that holds the query word as it is written ("test" in test-driven-development) is a better hit
than a name that holds only its stem ("testing"). Round 3 adds a small bonus for such exact name words to `rank` in the existing `skill_rank.py` (seed: benchmarks/skill_rank3_seed). GUPPI builds it, Claude wrote this file,
the hidden tests and the reference (benchmarks/devvm_refs/skill_rank3). Lesson of round 2: the tests of a stage only use rules of this stage and the stages before."""

SEED = "benchmarks/skill_rank3_seed"      # PIPE-10: devvm_build takes this folder as --seed when none is given
NOTES = '''# Notes for skill_rank (round 3)
`skill_rank.py` is already in the workspace and works. Keep `STOP`, `stem`, `words`, `expand` and `idf_table` exactly as they are. Pure Python 3 standard library, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code. `import` lines belong at the top of the file.
'''

HEAD = '''
from skill_rank import raw_words, rank, idf_table
def e(i, name, desc): return {"id": i, "name": name, "description": desc}
def near(a, b): return abs(a - b) < 0.01
'''

S1 = HEAD + '''
assert raw_words("The Testing of test-driven AND ab x1") == {"driven", "test", "testing"}
assert raw_words(None) == set()
assert raw_words("") == set()
assert raw_words("a an of") == set()
assert raw_words("Skills USING Tests") == {"tests"}
assert raw_words("code-review_and.quality 42") == {"code", "review", "quality"}
'''

IDX = '''
IDX = [e("tdd", "test-driven-development", "Drives development with tests using the red-green-refactor loop. Use when fixing any bug."),
       e("browser", "browser-testing-with-devtools", "Tests in real browsers via Chrome DevTools. Use when debugging anything that runs in a browser."),
       e("sysdebug", "systematic-debugging", "find the root cause of a failure before fixing it"),
       e("review", "code-review-and-quality", "review code changes for quality and correctness"),
       e("plan", "planning-and-task-breakdown", "break a task into small steps")]
G = [["debug", "bug", "error"]]
'''

S2 = S1 + IDX + '''
r = rank(IDX, "write failing test first", G)
assert [x["id"] for x in r] == ["tdd", "browser"] and near(r[0]["score"], 6.89) and near(r[1]["score"], 6.26)
r = rank(IDX, "test", G)
assert [x["id"] for x in r] == ["tdd", "browser"] and near(r[0]["score"], 9.89) and near(r[1]["score"], 9.26)
r = rank(IDX, "testing", G)
assert [x["id"] for x in r] == ["browser", "tdd"] and near(r[0]["score"], 9.89) and near(r[1]["score"], 9.26)
r = rank(IDX, "debug", G)
assert [x["id"] for x in r] == ["sysdebug"] and near(r[0]["score"], 8.01)
r = rank(IDX, "review code", G)
assert [x["id"] for x in r] == ["review"] and near(r[0]["score"], 22.71)
assert rank(IDX, "zzz", G) == [] and rank(IDX, "", G) == []
'''

S3 = S2 + '''
only_desc = [e("a", "other", "write failing"), e("b", "another", "nothing")]
assert rank(only_desc, "failing", []) == [{"id": "a", "score": 1.1}]
exact_name = [e("a", "failing-tests", ""), e("b", "other", "nothing")]
assert rank(exact_name, "failing", []) == [{"id": "a", "score": 7.94}]
before = [dict(x) for x in IDX]
rank(IDX, "test", G)
assert IDX == before
assert rank([{"id": "x"}], "test") == []
assert rank([{"id": "x", "name": None, "description": None}], "test") == []
assert rank([], "test") == []
'''

STAGES = [
    {"name": "raw", "no_own_check": True,
     "task": '''In the existing `skill_rank.py` (keep everything in it) add `raw_words(text) -> set`: the lower-case `str(text)` (None counts as empty), its runs of ASCII letters or digits with at least 3 characters, minus the words in `STOP`; the words are NOT stemmed ("Testing" stays "testing"). Nothing is modified. No comments and no docstrings.''',
     "hidden": {"hidden_rank3_1.py": S1}},
    {"name": "bonus", "no_own_check": True,
     "task": '''Change `rank` in `skill_rank.py`: add a module level constant `EXACT_NAME_BONUS = 0.5` and, to the score of an entry, add `EXACT_NAME_BONUS * W(stems)` where stems = { `stem(w)` for every w in `raw_words(query) & raw_words(name)` } and W is the IDF weight sum that `rank` already uses (a stem not in the table weighs 0). Everything else in `rank` stays as it is (the cap, the cut by `min_ratio`, the order, the rounding). Example: the query "test" scores `test-driven-development` higher than `browser-testing-with-devtools`, the query "testing" the other way round. No comments and no docstrings.''',
     "hidden": {"hidden_rank3_2.py": S2}},
    {"name": "all", "no_own_check": True,
     "task": '''Check `rank` once more: the entries are not modified, an entry without name or description (or None) never raises, an empty list gives an empty list. Then read the file once more: no rule may be copied into several places, no comments, no docstrings, all `import` lines at the top, no leftover debug files. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_rank3_full.py": S2 + S3.split(S2)[1]}},
]
