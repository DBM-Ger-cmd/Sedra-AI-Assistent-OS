"""Spec 7, Bau-Spec wis_store (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D7.1, D7.2, D7.3; WIS-01 bis WIS-04, WIS-10; gates G2-S7-o, G2-S7-q):
`wissen/schema.py`, the memory of the knowledge store: versioned migrations and meta values, the comparison of a source's old and new sections (what is new, changed, gone),
applying that comparison in one transaction, the stable section id, the sections that still need a vector and the vectors themselves, and the model change that
drops every vector of another model. The tables come from wis_ddl.py (the seed benchmarks/wis_schema_seed); times are texts given by the caller, there is no clock in
the module. SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/wis_store)."""

SEED = "benchmarks/wis_schema_seed"      # PIPE-10: devvm_build takes this folder as --seed when none is given

NOTES = '''# Notes for wis_store
Python 3 standard library only (sqlite3, hashlib, json, contextlib) plus `from wis_ddl import MIGRATIONEN` (wis_ddl.py is given in the workspace: do not change it). No clock (every time is an argument), no other files, no network, no guppi_runtime import.
The connection is opened by the caller with wis_ddl.open_db (rows are sqlite3.Row, isolation_level None, foreign keys on); return plain dicts, lists and tuples. Every write runs inside one `BEGIN IMMEDIATE` ... `COMMIT` (ROLLBACK on any exception); a refusal (ValueError) is raised BEFORE anything is written.
Every refusal is a ValueError with exactly the code the task names. No comments and no docstrings, small private helpers instead of copied code.
'''

HEAD = r'''
import json
import wis_ddl
from schema import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


T0 = "2026-10-22T10:00:00Z"
T1 = "2026-10-22T11:00:00Z"


def db():
    c = wis_ddl.open_db(":memory:")
    migriere(c, jetzt=T0)
    return c


def quelle(c, qid="Q-1", stufe=1, projekt=None, personenbezug=0):
    c.execute("INSERT INTO quellen (id, art, adapter, wurzel, pfad, freigabe_gate, freigabe_mission, stufe, projekt, personenbezug, erstellt) "
              "VALUES (?, 'datei', 'markdown', 'repo', 'docs/A.md', 'HG-1', 'M-1', ?, ?, ?, ?)", (qid, stufe, projekt, personenbezug, T0))


def a(datei, stelle, teil, text, hash_=None, datum="2026-10-20", befunde=None):
    out = {"datei": datei, "stelle": stelle, "teil": teil, "text": text, "hash": hash_ or ("h-" + text), "datum": datum}
    if befunde is not None:
        out["befunde"] = befunde
    return out


def rows(c, sql, *params):
    return [tuple(r) for r in c.execute(sql, params)]
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
c = wis_ddl.open_db(":memory:")
assert migriere(c, jetzt=T0) == [1]
assert not c.in_transaction
assert rows(c, "SELECT version, angewendet, beschreibung FROM migrationen") == [(1, T0, wis_ddl.MIGRATIONEN[0][1])]
assert lies_meta(c) == {"schema_version": "1"}
assert migriere(c, jetzt=T1) == []
assert rows(c, "SELECT count(*) FROM migrationen") == [(1,)]
names = {r[0] for r in rows(c, "SELECT name FROM sqlite_master WHERE type = 'table'")}
assert {"meta", "quellen", "abschnitte", "vektoren", "vorschlaege", "laeufe", "abschnitte_fts"} <= names
assert rows(c, "SELECT count(*) FROM abschnitte_fts") == [(0,)]
setze_meta(c, {"modell_id": "bge", "modell_dim": 1024})
assert lies_meta(c) == {"modell_dim": "1024", "modell_id": "bge", "schema_version": "1"}
setze_meta(c, {"modell_id": "bge2"})
assert lies_meta(c)["modell_id"] == "bge2"
assert not c.in_transaction
c.execute("INSERT INTO migrationen (version, angewendet, beschreibung) VALUES (99, ?, 'zukunft')", (T1,))
raises("wis_schema_neuer", migriere, c, jetzt=T1)
assert SCHEMA_VERSION == len(wis_ddl.MIGRATIONEN)
'''

C2 = r'''
seen = set()
i1 = abschnitt_id("Q-1", "docs/A.md", "Kopf", 1, lambda i: i in seen)
assert len(i1) == 11
assert i1[0] == "W"
assert abschnitt_id("Q-1", "docs/A.md", "Kopf", 1, lambda i: False) == i1
assert len({i1, abschnitt_id("Q-1", "docs/A.md", "Kopf", 2, lambda i: False), abschnitt_id("Q-2", "docs/A.md", "Kopf", 1, lambda i: False)}) == 3
seen.add(i1)
i2 = abschnitt_id("Q-1", "docs/A.md", "Kopf", 1, lambda i: i in seen)
assert len(i2) == 13
assert i2.startswith(i1)
raises("wis_id_kollision", abschnitt_id, "Q-1", "docs/A.md", "Kopf", 1, lambda i: True)
c = db()
quelle(c)
c.execute("INSERT INTO abschnitte (id, quelle, datei, stelle, teil, text, hash, datum, aufgenommen, zeichen) VALUES "
          "('W1', 'Q-1', 'docs/A.md', 'Kopf', 1, 'alt', 'h-alt', '2026-10-01', ?, 3), ('W2', 'Q-1', 'docs/A.md', 'Regeln', 1, 'r', 'h-r', '2026-10-01', ?, 1), "
          "('W3', 'Q-1', 'docs/A.md', 'Regeln', 2, 'r2', 'h-r2', '2026-10-01', ?, 2)", (T0, T0, T0))
quelle(c, "Q-2")
c.execute("INSERT INTO abschnitte (id, quelle, datei, stelle, teil, text, hash, datum, aufgenommen, zeichen) VALUES ('W9', 'Q-2', 'docs/A.md', 'Kopf', 1, 'fremd', 'h-fremd', '2026-10-01', ?, 5)", (T0,))
neu = a("docs/A.md", "Kopf", 1, "neu")
gleich = a("docs/A.md", "Regeln", 1, "r")
dazu = a("docs/A.md", "Anhang", 1, "x")
v = vergleiche(c, "Q-1", [neu, gleich, dazu])
assert v["neu"] == [dazu]
assert v["geaendert"] == [(1, neu)]
assert v["entfernt"] == [3]
assert v["gleich"] == 1
assert vergleiche(c, "Q-1", []) == {"neu": [], "geaendert": [], "entfernt": [1, 2, 3], "gleich": 0}
assert vergleiche(c, "Q-3", [dazu]) == {"neu": [dazu], "geaendert": [], "entfernt": [], "gleich": 0}
raises("wis_abschnitt_doppelt", vergleiche, c, "Q-1", [dazu, dict(dazu, text="y")])
raises("wis_abschnitt_ungueltig", vergleiche, c, "Q-1", [dict(dazu, teil=0)])
raises("wis_abschnitt_ungueltig", vergleiche, c, "Q-1", [dict(dazu, text="")])
raises("wis_abschnitt_ungueltig", vergleiche, c, "Q-1", [{"datei": "d", "stelle": "s", "teil": 1, "text": "t"}])
raises("wis_abschnitt_ungueltig", vergleiche, c, "Q-1", ["kein dict"])
'''

C3 = r'''
c = db()
quelle(c)
first = [a("docs/A.md", "Kopf", 1, "eins"), a("docs/A.md", "Regeln", 1, "zwei", befunde=["SG_TEMPLATE_INJECTION"]), a("docs/A.md", "Regeln", 2, "drei")]
assert wende_an(c, "Q-1", vergleiche(c, "Q-1", first), jetzt=T0) == {"neu": 3, "geaendert": 0, "entfernt": 0}
assert not c.in_transaction
got = rows(c, "SELECT nr, quelle, datei, stelle, teil, text, hash, datum, aufgenommen, befunde, zeichen FROM abschnitte ORDER BY nr")
assert got[0] == (1, "Q-1", "docs/A.md", "Kopf", 1, "eins", "h-eins", "2026-10-20", T0, "[]", 4)
assert got[1][9] == '["SG_TEMPLATE_INJECTION"]'
ids = [r[0] for r in rows(c, "SELECT id FROM abschnitte ORDER BY nr")]
assert ids[0] == abschnitt_id("Q-1", "docs/A.md", "Kopf", 1, lambda i: False)
assert len(set(ids)) == 3
assert rows(c, "SELECT stand FROM quellen WHERE id = 'Q-1'") == [(T0,)]
assert rows(c, "SELECT rowid FROM abschnitte_fts WHERE abschnitte_fts MATCH 'zwei'") == [(2,)]
second = [a("docs/A.md", "Kopf", 1, "eins neu", datum="2026-10-21"), a("docs/A.md", "Regeln", 1, "zwei")]
assert wende_an(c, "Q-1", vergleiche(c, "Q-1", second), jetzt=T1) == {"neu": 0, "geaendert": 1, "entfernt": 1}
assert rows(c, "SELECT nr, id, text, hash, datum, aufgenommen, befunde, zeichen FROM abschnitte WHERE stelle = 'Kopf'") == [(1, ids[0], "eins neu", "h-eins neu", "2026-10-21", T1, "[]", 8)]
assert rows(c, "SELECT nr, aufgenommen FROM abschnitte WHERE stelle = 'Regeln'") == [(2, T0)]
assert rows(c, "SELECT rowid FROM abschnitte_fts WHERE abschnitte_fts MATCH 'drei'") == []
assert rows(c, "SELECT stand FROM quellen WHERE id = 'Q-1'") == [(T1,)]
assert wende_an(c, "Q-1", vergleiche(c, "Q-1", second), jetzt="2026-10-22T12:00:00Z") == {"neu": 0, "geaendert": 0, "entfernt": 0}
raises("wis_quelle_unbekannt", wende_an, c, "Q-x", {"neu": [a("d", "s", 1, "t")], "geaendert": [], "entfernt": []}, jetzt=T1)
raises("wis_abschnitt_ungueltig", wende_an, c, "Q-1", {"neu": [a("d", "s", 0, "t")], "geaendert": [], "entfernt": [2]}, jetzt=T1)
assert rows(c, "SELECT count(*) FROM abschnitte") == [(2,)]
'''

C4 = r'''
c = db()
quelle(c)
wende_an(c, "Q-1", vergleiche(c, "Q-1", [a("docs/A.md", "Kopf", 1, "eins"), a("docs/A.md", "Regeln", 1, "zwei")]), jetzt=T0)
assert offene_vektoren(c, "bge", 10) == [(1, "Kopf\neins", "h-eins"), (2, "Regeln\nzwei", "h-zwei")]
assert offene_vektoren(c, "bge", 1) == [(1, "Kopf\neins", "h-eins")]
blob = bytes(8)
assert schreibe_vektoren(c, "bge", 2, [(1, "h-eins", blob)]) == 1
assert not c.in_transaction
assert offene_vektoren(c, "bge", 10) == [(2, "Regeln\nzwei", "h-zwei")]
assert offene_vektoren(c, "anderes", 10) == [(1, "Kopf\neins", "h-eins"), (2, "Regeln\nzwei", "h-zwei")]
assert rows(c, "SELECT abschnitt, modell_id, dim, hash, blob FROM vektoren") == [(1, "bge", 2, "h-eins", blob)]
assert schreibe_vektoren(c, "bge", 2, [(1, "h-eins", b"\x00\x00\x80\x3f" * 2), (2, "h-zwei", blob)]) == 2
assert rows(c, "SELECT count(*) FROM vektoren") == [(2,)]
assert offene_vektoren(c, "bge", 10) == []
wende_an(c, "Q-1", vergleiche(c, "Q-1", [a("docs/A.md", "Kopf", 1, "eins neu"), a("docs/A.md", "Regeln", 1, "zwei")]), jetzt=T1)
assert offene_vektoren(c, "bge", 10) == [(1, "Kopf\neins neu", "h-eins neu")]
raises("wis_vektor_dim", schreibe_vektoren, c, "bge", 2, [(1, "h", bytes(7))])
raises("wis_vektor_dim", schreibe_vektoren, c, "bge", 0, [])
raises("wis_abschnitt_unbekannt", schreibe_vektoren, c, "bge", 2, [(1, "h-eins neu", blob), (77, "h", blob)])
assert rows(c, "SELECT count(*) FROM vektoren WHERE abschnitt = 1 AND hash = 'h-eins neu'") == [(0,)]
raises("wis_limit_ungueltig", offene_vektoren, c, "bge", 0)
'''

C5 = r'''
c = db()
quelle(c)
wende_an(c, "Q-1", vergleiche(c, "Q-1", [a("docs/A.md", "Kopf", 1, "eins neu"), a("docs/A.md", "Regeln", 1, "zwei")]), jetzt=T0)
blob = bytes(8)
schreibe_vektoren(c, "bge", 2, [(1, "h-eins neu", blob), (2, "h-zwei", blob)])
assert lies_meta(c).get("modell_id") is None
assert modellwechsel(c, "bge", 2) == 0
assert lies_meta(c)["modell_id"] == "bge"
assert modellwechsel(c, "bge", 2) == 0
assert rows(c, "SELECT count(*) FROM vektoren") == [(2,)]
assert not c.in_transaction
schreibe_vektoren(c, "neu", 2, [(1, "h-eins neu", blob)])
assert rows(c, "SELECT abschnitt, modell_id FROM vektoren ORDER BY abschnitt") == [(1, "neu"), (2, "bge")]
assert modellwechsel(c, "neu", 2) == 1
assert rows(c, "SELECT abschnitt, modell_id FROM vektoren") == [(1, "neu")]
assert lies_meta(c)["modell_id"] == "neu"
assert modellwechsel(c, "neu", 3) == 1
assert lies_meta(c)["modell_dim"] == "3"
assert rows(c, "SELECT count(*) FROM vektoren") == [(0,)]
schreibe_vektoren(c, "neu", 2, [(1, "h-eins neu", blob)])
wende_an(c, "Q-1", vergleiche(c, "Q-1", []), jetzt=T1)
assert rows(c, "SELECT count(*) FROM vektoren") == [(0,)]
'''

H1 = {"hidden_store_1.py": hidden("SCHEMA_VERSION, migriere, lies_meta, setze_meta", C1)}
H2 = {**H1, "hidden_store_2.py": hidden("migriere, abschnitt_id, vergleiche", C2)}
H3 = {**H2, "hidden_store_3.py": hidden("migriere, abschnitt_id, vergleiche, wende_an", C3)}
H4 = {**H3, "hidden_store_4.py": hidden("migriere, vergleiche, wende_an, offene_vektoren, schreibe_vektoren", C4)}
H5 = {**H4, "hidden_store_5.py": hidden("migriere, lies_meta, vergleiche, wende_an, schreibe_vektoren, modellwechsel", C5)}

TABLES = """Tables (wis_ddl.py, the seed; do not change it): meta (schluessel PRIMARY KEY, wert), migrationen (version PRIMARY KEY, angewendet, beschreibung), quellen (id PRIMARY KEY, art, adapter, wurzel, pfad, muster, freigabe_gate, freigabe_mission, stufe, projekt, personenbezug, aktiv, stand, quell_hash, erstellt), abschnitte (nr AUTOINCREMENT, id UNIQUE, quelle REFERENCES quellen ON DELETE CASCADE, datei, stelle, teil, text, hash, datum, aufgenommen, befunde JSON text, zeichen; UNIQUE (quelle, datei, stelle, teil)) with an FTS5 table abschnitte_fts kept in step by triggers, vektoren (abschnitt PRIMARY KEY REFERENCES abschnitte ON DELETE CASCADE, modell_id, dim, hash, blob with length 4 * dim), vorschlaege, laeufe."""

STAGES = [
    {"name": "migriere",
     "task": f"""Create `schema.py` (Python 3; `from wis_ddl import MIGRATIONEN`, a tuple of (version int, beschreibung, sql) in ascending order; wis_ddl.py is in the workspace) with `SCHEMA_VERSION` = the number of migrations and three functions.
{TABLES}
`migriere(db, *, jetzt)` -> list of the versions applied now, in order. First `PRAGMA quick_check` must answer 'ok', else ValueError('wis_schema_kaputt'). The current version is the largest `migrationen.version`, or 0 when that table does not exist yet (look in sqlite_master). A current version above SCHEMA_VERSION -> ValueError('wis_schema_neuer'), nothing written. Every migration with a higher version than the current one runs in its own transaction: `db.executescript("BEGIN IMMEDIATE;" + sql)`, then a row in migrationen (version, angewendet = jetzt, beschreibung), then meta 'schema_version' = str(version) (INSERT OR REPLACE), then COMMIT. Nothing to do -> [] and nothing written.
`lies_meta(db)` -> dict of all meta rows (schluessel -> wert, both texts). `setze_meta(db, werte)` writes every item of the mapping with INSERT OR REPLACE as texts (str(key), str(value)) inside one BEGIN IMMEDIATE ... COMMIT and returns None. No function leaves a transaction open.""",
     "hidden": H1},
    {"name": "vergleiche",
     "task": """Add to `schema.py` (keep everything else):
`abschnitt_id(quelle_id, datei, stelle, teil, belegt)` -> the stable section id: 'W' plus the first 10 hex characters of sha256 of the UTF-8 text f"{quelle_id}|{datei}|{stelle}|{teil}". While `belegt(id)` (a callable) says True, take 2 more characters (12, 14, ... up to 64); when even 64 are taken -> ValueError('wis_id_kollision').
`vergleiche(db, quelle_id, abschnitte)` -> {"neu": [...], "geaendert": [...], "entfernt": [...], "gleich": int}: only reads. Every element of `abschnitte` must be a dict with the keys datei, stelle, teil, text, hash, datum, where teil is an int >= 1 (a bool is not an int) and the other five are non-empty strings, else ValueError('wis_abschnitt_ungueltig'); the key (datei, stelle, teil) must not occur twice in the input, else ValueError('wis_abschnitt_doppelt'). Compared with the rows of `abschnitte` of this quelle (other sources are ignored): a key not in the table -> the dict goes to "neu" (input order); a key in the table with a different hash -> the pair (nr of the row, the dict) goes to "geaendert" (input order); same hash -> "gleich" counts it; table rows whose key is not in the input -> their nr in "entfernt", ascending. The input dicts are returned as the same objects, never modified.""",
     "hidden": H2},
    {"name": "wende_an",
     "task": """Add `wende_an(db, quelle_id, abgleich, *, jetzt)` -> {"neu": n, "geaendert": n, "entfernt": n} (the counts) to `schema.py` (keep everything else): applies a result of `vergleiche` in ONE transaction (BEGIN IMMEDIATE ... COMMIT, ROLLBACK on any exception).
Checks before anything is written: the quelle must exist in `quellen`, else ValueError('wis_quelle_unbekannt'); every dict in "neu" and in the pairs of "geaendert" is checked like in `vergleiche` ('wis_abschnitt_ungueltig').
Then: every nr in "entfernt" is deleted from abschnitte (only rows of this quelle); every pair in "geaendert" updates its row: text, hash, datum from the dict, aufgenommen = jetzt, befunde = json.dumps(list of the dict's "befunde", [] when missing), zeichen = len(text) -- the id and nr stay; every dict in "neu" is inserted with id = abschnitt_id(quelle_id, datei, stelle, teil, belegt) where belegt looks the id up in abschnitte, quelle = quelle_id, the six fields, aufgenommen = jetzt, befunde as above, zeichen = len(text). Finally `quellen.stand = jetzt`. The FTS5 table follows through the triggers of the seed: nothing to do there.""",
     "hidden": H3},
    {"name": "vektoren",
     "task": """Add to `schema.py` (keep everything else):
`offene_vektoren(db, modell_id, limit)` -> list of tuples (nr, stelle + "\\n" + text, hash) of the sections that have no row in `vektoren` with this abschnitt, this modell_id AND the section's current hash (a vector of another model or of an older hash does not count), ordered by nr, at most `limit` rows; limit must be an int >= 1, else ValueError('wis_limit_ungueltig'). Only reads.
`schreibe_vektoren(db, modell_id, dim, zeilen)` -> the number of rows written: zeilen is an iterable of tuples (nr, hash, blob). dim must be an int >= 1 and every blob bytes (or bytearray) of exactly 4 * dim bytes, else ValueError('wis_vektor_dim') before anything is written. Inside one BEGIN IMMEDIATE ... COMMIT: INSERT OR REPLACE into vektoren (abschnitt = nr, modell_id, dim, hash, blob). A nr that is not in abschnitte makes sqlite raise sqlite3.IntegrityError (foreign keys are on): ROLLBACK everything and raise ValueError('wis_abschnitt_unbekannt').
""",
     "hidden": H4},
    {"name": "modellwechsel",
     "task": """Add `modellwechsel(db, modell_id, dim)` -> the number of deleted vectors to `schema.py` (keep everything else): when meta already has modell_id == modell_id and modell_dim == str(dim), nothing changes and 0 is returned. Otherwise, inside one BEGIN IMMEDIATE ... COMMIT: delete every vektoren row whose modell_id differs from the new one OR whose dim differs from the new dim, set meta modell_id and modell_dim (as texts, INSERT OR REPLACE), return the number of deleted rows. Vectors of the new model with the new dim stay.""",
     "hidden": H5},
]
