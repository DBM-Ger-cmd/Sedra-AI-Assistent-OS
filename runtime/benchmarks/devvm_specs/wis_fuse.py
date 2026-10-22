"""Spec 7, Bau-Spec wis_fuse (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D7.1, D7.5, D7.7; WIS-05, WIS-06, WIS-09, WIS-11; gates G2-S7-c, G2-S7-g, G2-S7-o):
`wissen/fusion.py`, the pure rules of the hybrid search: the words of a question and the FTS5 query, the rarity weight (idf) and the quality of a full-text hit,
the weighted reciprocal rank fusion of the word list and the vector list (with an optional top-hit protection), the full-text-only fallback, and the rights
filter (level, project, personal data on the cloud route, findings for agents) as a rule and as a SQL condition. No file, no clock, no database, no model.
SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/wis_fuse)."""

NOTES = '''# Notes for wis_fuse
Python 3 standard library only (re, math); no sqlite3, no files, no clock, no network, no guppi_runtime import.
Every function is pure and never modifies its arguments. Every refusal is a ValueError with exactly the code the task names.
No comments and no docstrings, small private helpers instead of copied code.
'''

HEAD = r'''
import copy
import math
import sqlite3
from fusion import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def near(a, b):
    return abs(a - b) < 1e-9


def rrf(k, w_v, rv, w_w, rw, g=1.0):
    return (w_v / (k + rv) if rv else 0.0) + (w_w * g / (k + rw) if rw else 0.0)


def nrs(treffer):
    return [t["nr"] for t in treffer]


def leser(art="agent", stufe=1, projekt="P1"):
    return {"art": art, "stufe": stufe, "projekt": projekt, "agent_id": "A1" if art == "agent" else None}


def quelle(aktiv=1, stufe=1, projekt=None, personenbezug=0):
    return {"aktiv": aktiv, "stufe": stufe, "projekt": projekt, "personenbezug": personenbezug}
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
assert woerter("Wie viel Videospeicher darf ein Modell belegen?") == ["videospeicher", "modell", "belegen"]
assert woerter("Der GPU-Lease und der gpu-lease, llama_server!") == ["gpu-lease", "llama_server"]
assert woerter("Was ist R-07 und R-07?") == ["r-07"]
assert woerter("a b c") == []
assert woerter(" ".join(f"wort{i}" for i in range(20))) == [f"wort{i}" for i in range(12)]
assert woerter(" ".join(f"wort{i}" for i in range(20)), hoechstens=3) == ["wort0", "wort1", "wort2"]
assert woerter("Über Ärger und Öl") == ["ärger", "öl"]
assert "der" in STOPPWOERTER
assert "videospeicher" not in STOPPWOERTER
raises("wis_anfrage_leer", woerter, None)
assert fts_anfrage(["videospeicher", "modell"]) == '"videospeicher" OR "modell"'
assert fts_anfrage([]) == ""
assert fts_anfrage(['b"c', '"']) == '"bc"'
assert near(idf(100, 0), math.log(1 + 100.5 / 0.5))
assert near(idf(100, 50), math.log(1 + 50.5 / 50.5))
assert idf(10, 10) < idf(10, 1)
raises("wis_idf_ungueltig", idf, 5, 6)
raises("wis_idf_ungueltig", idf, -1, 0)
'''

C2 = r'''
w = {"videospeicher": 4.0, "modell": 1.0, "belegen": 3.0}
assert near(guete(w, {"videospeicher", "belegen"}), 7.0 / 8.0)
assert near(guete(w, {"modell"}), 1.0 / 8.0)
assert near(guete(w, {"videospeicher", "modell", "belegen", "extra"}), 1.0)
assert guete(w, set()) == 0.0
assert guete({}, {"x"}) == 0.0
assert guete({"a": 0.0, "b": 0.0}, {"a"}) == 0.0
assert near(guete({"a": 2.0, "b": -5.0}, {"a"}), 1.0)
assert near(guete({"a": 2, "b": 2}, ["a"]), 0.5)
assert guete(w, frozenset()) == 0.0
'''

C3 = r'''
G = {"k": 60, "w_vektor": 1.0, "w_wort": 0.75, "guete": True, "spitzenschutz": False}
g = {1: 1.0, 2: 0.5, 3: 0.1, 4: 0.0}
out = fusioniere([1, 2, 3], [2, 4, 1], g, G)
assert nrs(out) == [1, 2, 4, 3]
assert out[0] == {"nr": 1, "punkte": rrf(60, 1.0, 3, 0.75, 1, 1.0), "rang_wort": 1, "rang_vektor": 3, "guete": 1.0}
assert out[1] == {"nr": 2, "punkte": rrf(60, 1.0, 1, 0.75, 2, 0.5), "rang_wort": 2, "rang_vektor": 1, "guete": 0.5}
assert out[2] == {"nr": 4, "punkte": rrf(60, 1.0, 2, 0.75, None), "rang_wort": None, "rang_vektor": 2, "guete": 0.0}
assert near(out[3]["punkte"], 0.75 * 0.1 / 63)
assert fusioniere([], [], {}, G) == []
assert nrs(fusioniere([], [7, 8], {}, G)) == [7, 8]
assert nrs(fusioniere([1, 2, 3], [2, 4, 1], g, dict(G, guete=False))) == [2, 1, 4, 3]
assert near(fusioniere([3], [], g, dict(G, guete=False))[0]["punkte"], 0.75 / 61)
assert nrs(fusioniere([1, 2, 3, 4, 5, 6], [], {n: 1.0 for n in range(1, 7)}, G, k_aus=2)) == [1, 2]
assert nrs(fusioniere([11], [12], {11: 1.0}, dict(G, w_vektor=0.0))) == [11, 12]
assert nrs(fusioniere([11], [12], {11: 1.0}, dict(G, w_wort=0.0))) == [12, 11]
assert near(fusioniere([11], [12], {11: 1.0}, {"k": 10})[0]["punkte"], 1.0 / 11)
wort, vektor = [1, 2], [2, 1]
keep = copy.deepcopy((wort, vektor, g, G))
fusioniere(wort, vektor, g, G)
assert (wort, vektor, g, G) == keep
for bad in ({"k": 0}, {"w_wort": -1}, {"w_vektor": 0, "w_wort": 0}, {"w_vektor": True}):
    raises("wis_fusion_gewichte", fusioniere, [1], [1], g, bad)
raises("wis_k_ungueltig", fusioniere, [1], [1], g, G, k_aus=0)
raises("wis_liste_ungueltig", fusioniere, [1, 1], [2], g, G)
raises("wis_liste_ungueltig", fusioniere, [1], ["2"], g, G)
'''

C4 = r'''
G = {"k": 60, "w_vektor": 1.0, "w_wort": 0.75, "guete": True, "spitzenschutz": True}
g = {1: 1.0, 2: 0.9, 3: 0.9, 4: 0.9, 5: 0.9, 6: 0.9, 7: 0.1}
wort = [1, 2, 3, 4, 5, 6]
vektor = [7, 2, 3, 4, 5, 6]
ohne = fusioniere(wort, vektor, g, dict(G, spitzenschutz=False))
assert nrs(ohne) == [2, 3, 4, 5, 6]
mit = fusioniere(wort, vektor, g, G)
assert nrs(mit) == [2, 3, 4, 7, 1]
assert mit[3] == {"nr": 7, "punkte": rrf(60, 1.0, 1, 0.75, None), "rang_wort": None, "rang_vektor": 1, "guete": 0.1}
assert mit[4]["rang_wort"] == 1
assert nrs(fusioniere(wort, vektor, g, G, k_aus=3)) == [2, 7, 1]
assert nrs(fusioniere(wort, vektor, g, G, k_aus=2)) == [7, 1]
assert nrs(fusioniere(wort, vektor, g, G, k_aus=1)) == [7]
assert nrs(fusioniere(wort, vektor, {**g, 1: 0.4}, G)) == [2, 3, 4, 5, 7]
assert nrs(fusioniere(wort, vektor, {**g, 1: 0.5}, G)) == [2, 3, 4, 7, 1]
assert nrs(fusioniere([2, 7], vektor, g, G)) == [2, 7, 3, 4, 5]
assert nrs(fusioniere([], vektor, g, G)) == [7, 2, 3, 4, 5]
assert nrs(fusioniere(wort, [], g, G)) == [1, 2, 3, 4, 5]
v = nur_volltext([4, 5, 6])
assert nrs(v) == [4, 5, 6]
assert v[0] == {"nr": 4, "punkte": 1.0 / 61, "rang_wort": 1, "rang_vektor": None, "guete": None}
assert nrs(nur_volltext([4, 5, 6], k_aus=2)) == [4, 5]
assert nur_volltext([]) == []
raises("wis_k_ungueltig", nur_volltext, [1], k_aus=0)
raises("wis_liste_ungueltig", nur_volltext, [1, 1])
'''

C5 = r'''
assert darf_lesen(quelle(), leser(), "local") is True
assert darf_lesen(quelle(stufe=3), leser(stufe=1), "local") is False
assert darf_lesen(quelle(aktiv=0), leser(stufe=6), "local") is False
assert darf_lesen(quelle(projekt="P1"), leser(projekt="P1"), "local") is True
assert darf_lesen(quelle(projekt="P2"), leser(projekt="P1"), "local") is False
assert darf_lesen(quelle(projekt="P2"), leser(projekt=None), "local") is False
assert darf_lesen(quelle(projekt="P2"), leser("captain", 6, None), "local") is True
assert darf_lesen(quelle(personenbezug=1), leser(stufe=6), "local") is True
assert darf_lesen(quelle(personenbezug=1), leser("captain", 6, None), "cloud") is False
assert darf_lesen(quelle(), leser(), "cloud") is True
assert darf_lesen(quelle(), leser(), "local", befunde=["SG_TEMPLATE_INJECTION"]) is False
assert darf_lesen(quelle(), leser(), "local", befunde=["SG_TEMPLATE_INJECTION"], befunde_sperren=False) is True
assert darf_lesen(quelle(), leser("captain", 6, None), "local", befunde=["SG_TEMPLATE_INJECTION"]) is True
assert darf_lesen({"aktiv": 1}, leser(), "local") is False
raises("wis_route_ungueltig", darf_lesen, quelle(), leser(), "lokal")
raises("wis_stufe_ungueltig", darf_lesen, quelle(), leser(stufe=7), "local")
raises("wis_stufe_ungueltig", darf_lesen, quelle(), {"art": "agent", "stufe": "1"}, "local")
raises("wis_leser_ungueltig", darf_lesen, quelle(), leser("gast"), "local")
'''

C6 = r'''
c = sqlite3.connect(":memory:")
c.execute("CREATE TABLE quellen (id TEXT PRIMARY KEY, aktiv INTEGER, stufe INTEGER, projekt TEXT, personenbezug INTEGER)")
c.executemany("INSERT INTO quellen VALUES (?,?,?,?,?)", [("q1", 1, 1, None, 0), ("q2", 1, 3, None, 0), ("q3", 1, 1, "P1", 0), ("q4", 1, 1, "P2", 0), ("q5", 0, 1, None, 0), ("q6", 1, 1, None, 1)])


def ids(leser_, route):
    where, params = sql_filter(leser_, route)
    assert isinstance(where, str)
    assert isinstance(params, tuple)
    return [r[0] for r in c.execute("SELECT q.id FROM quellen q WHERE " + where + " ORDER BY q.id", params)]


assert ids(leser(stufe=1, projekt="P1"), "local") == ["q1", "q3", "q6"]
assert ids(leser(stufe=3, projekt="P1"), "local") == ["q1", "q2", "q3", "q6"]
assert ids(leser(stufe=1, projekt="P2"), "local") == ["q1", "q4", "q6"]
assert ids(leser(stufe=1, projekt=None), "local") == ["q1", "q6"]
assert ids(leser(stufe=1, projekt="P1"), "cloud") == ["q1", "q3"]
assert ids(leser("captain", 6, None), "local") == ["q1", "q2", "q3", "q4", "q6"]
assert ids(leser("captain", 6, None), "cloud") == ["q1", "q2", "q3", "q4"]
assert ids(leser("captain", 0, None), "local") == []
rows = [dict(zip(("aktiv", "stufe", "projekt", "personenbezug"), r)) for r in c.execute("SELECT aktiv, stufe, projekt, personenbezug FROM quellen ORDER BY id")]
for l, route in ((leser(stufe=1, projekt="P1"), "local"), (leser(stufe=3, projekt=None), "cloud"), (leser("captain", 6, None), "cloud")):
    assert [q["aktiv"] for q in rows if darf_lesen(q, l, route)] == [1] * len(ids(l, route))
raises("wis_route_ungueltig", sql_filter, leser(), "")
raises("wis_stufe_ungueltig", sql_filter, leser(stufe=-1), "local")
raises("wis_leser_ungueltig", sql_filter, {"stufe": 1}, "local")
'''

H1 = {"hidden_fuse_1.py": hidden("STOPPWOERTER, woerter, fts_anfrage, idf", C1)}
H2 = {**H1, "hidden_fuse_2.py": hidden("guete", C2)}
H3 = {**H2, "hidden_fuse_3.py": hidden("fusioniere", C3)}
H4 = {**H3, "hidden_fuse_4.py": hidden("fusioniere, nur_volltext", C4)}
H5 = {**H4, "hidden_fuse_5.py": hidden("darf_lesen", C5)}
H6 = {**H5, "hidden_fuse_6.py": hidden("darf_lesen, sql_filter", C6)}

STAGES = [
    {"name": "woerter",
     "task": """Create `fusion.py` (Python 3 standard library only) with FUSION_VERSION = "f1", a frozenset STOPPWOERTER of German filler words (at least: der die das den dem des ein eine einen einem einer eines und oder mit ohne von vom zu zum zur im in am an auf aus bei für fuer ist sind war wird werden wurde hat haben kann können koennen darf muss soll sollen es sie er wir ich man sich nicht kein keine wie was wer wo wann warum welche welcher welches wieviel viele viel dass als auch noch nur schon so da dort hier dann wenn bis nach vor über ueber um ob wieder) and:
`woerter(frage, *, hoechstens=12)` -> list of the search words: frage must be a str, else ValueError('wis_anfrage_leer'); the matches of the regex [\\wäöüß]+(?:[-_][\\wäöüß]+)* in frage.lower(), in order, without words of length 1, without stop words and without repetitions (the first occurrence stays), at most `hoechstens`.
`fts_anfrage(woerter)` -> the FTS5 query text: every word with its double quotes removed, wrapped in double quotes, joined with ' OR '; words that are empty after the removal are skipped; an empty list gives ''.
`idf(n_abschnitte, n_wort)` -> math.log(1 + (n_abschnitte - n_wort + 0.5) / (n_wort + 0.5)); both must be ints >= 0 with n_wort <= n_abschnitte, else ValueError('wis_idf_ungueltig').""",
     "hidden": H1},
    {"name": "guete",
     "task": """Add `guete(idf_je_wort, enthalten)` -> float in 0..1 to `fusion.py` (keep everything else): the share of a question's rarity weight that a section covers. idf_je_wort maps word -> idf value; enthalten is any container of the words the section contains. Negative values count as 0. Result = (sum of the values of the contained words) / (sum of all values), at most 1.0; when the sum of all values is 0 (empty mapping or only zeros) the result is 0.0.""",
     "hidden": H2},
    {"name": "fusioniere",
     "task": """Add `fusioniere(wort, vektor, g, gewichte, k_aus=5)` -> list of hits to `fusion.py` (keep everything else): the weighted reciprocal rank fusion. wort and vektor are the section numbers (ints) in rank order (rank 1 first), each without repetitions, else ValueError('wis_liste_ungueltig') (a list that is not a list/tuple of ints counts as invalid too). g maps section number -> quality from `guete` (a missing number counts as 0.0). gewichte is a dict with the keys k (int >= 1, default 60), w_vektor (number >= 0, default 1.0), w_wort (number >= 0, default 0.75), guete (bool, default True) and spitzenschutz (bool, default False); missing keys take the default, an empty dict is allowed; k not an int or < 1, a weight that is a bool, not a number or negative, or both weights 0 -> ValueError('wis_fusion_gewichte'). k_aus must be an int 1..20, else ValueError('wis_k_ungueltig'). Checks in this order: lists, k_aus, gewichte.
Every section that occurs in either list gets punkte = w_vektor / (k + rang_vektor) [only when it is in vektor] + w_wort * faktor / (k + rang_wort) [only when it is in wort], where faktor = its g value when gewichte.guete is True, else 1.0. Sort by punkte descending, ties by the smaller section number; return the first k_aus as dicts {"nr", "punkte" (the float), "rang_wort" (1-based or None), "rang_vektor" (1-based or None), "guete" (the g value as float, 0.0 when missing)}. Build the spitzenschutz in the next stage (ignore the key here). Never modify the arguments.""",
     "hidden": H3},
    {"name": "spitzenschutz",
     "task": """Extend `fusioniere` in `fusion.py` (keep everything else) by the spitzenschutz and add `nur_volltext(wort, k_aus=5)`.
spitzenschutz True: the protected sections are the first of vektor (when vektor is not empty) and the first of wort when its g value is >= 0.5 (and it is not already the first of vektor). Let `fehlt` be the protected sections that are not among the k_aus hits chosen above. Then the result is: the chosen hits that are not protected, cut to the first max(0, k_aus - len(fehlt)) of them, plus the chosen hits that are protected, plus one hit for every section in `fehlt` (its normal punkte and ranks) -- the whole list sorted again by punkte descending, then nr, and cut to the first k_aus. So a protected section always appears (unless k_aus is smaller than the number of protected sections), and the hits with the lowest punkte give way.
`nur_volltext(wort, k_aus=5)` -> the first k_aus sections of wort as hits {"nr", "punkte": 1.0 / (60 + rang), "rang_wort": rang, "rang_vektor": None, "guete": None}; same checks as fusioniere for the list ('wis_liste_ungueltig') and k_aus ('wis_k_ungueltig').""",
     "hidden": H4},
    {"name": "darf_lesen",
     "task": """Add `darf_lesen(quelle, leser, route, *, befunde=(), befunde_sperren=True)` -> bool to `fusion.py` (keep everything else): may this reader see sections of this source? quelle is a dict with aktiv (truthy/falsy), stufe (int 0..6), projekt (text or None), personenbezug (truthy/falsy); leser a dict with art ('captain' or 'agent'), stufe (int 0..6), projekt (text or None), agent_id; route 'local' or 'cloud'.
Checks first: leser not a dict or art not 'captain'/'agent' -> ValueError('wis_leser_ungueltig'); leser stufe not an int (a bool is not) or outside 0..6 -> ValueError('wis_stufe_ungueltig'); route not 'local'/'cloud' -> ValueError('wis_route_ungueltig').
False when: quelle.aktiv is falsy; quelle.stufe is missing (None) or greater than leser.stufe; leser.art is 'agent' and quelle.projekt is not None and differs from leser.projekt (a captain sees every project); route is 'cloud' and quelle.personenbezug is truthy (whatever the level); leser.art is 'agent', befunde_sperren is True and befunde is not empty (a captain still sees sections with findings). Otherwise True.""",
     "hidden": H5},
    {"name": "sql_filter",
     "task": """Add `sql_filter(leser, route)` -> (where_text, params_tuple) to `fusion.py` (keep everything else): the same rules as `darf_lesen` (without befunde) as a SQL condition on the table alias `q` (columns q.aktiv, q.stufe, q.projekt, q.personenbezug), with the same checks ('wis_leser_ungueltig', 'wis_stufe_ungueltig', 'wis_route_ungueltig'). The text is "q.aktiv = 1 AND q.stufe <= ?" with the reader's stufe as parameter; for an agent " AND (q.projekt IS NULL OR q.projekt = ?)" with the reader's projekt (None is allowed as a parameter: then only sources without a project pass); for route 'cloud' " AND q.personenbezug = 0". The params are a tuple in the order of the placeholders.""",
     "hidden": H6},
]
