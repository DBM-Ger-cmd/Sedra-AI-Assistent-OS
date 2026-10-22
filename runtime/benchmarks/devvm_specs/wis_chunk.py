"""Spec 7, Bau-Spec wis_chunk (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D7.1, D7.3, D7.6; WIS-02, WIS-03, WIS-08; gates G2-S7-e, G2-S7-o):
`wissen/zerlegen.py`, the pure splitting of a source into sections: blocks of a text (paragraph, list, table, code), the pieces of a block under a size limit (lists
split at item borders with their lead-in line, tables with their header repeated), Markdown by headings, plain text, the logbook by table row, one store entry; the
one-line heading for the data block, the section hash and the embedding input text. No file, no clock, no database. SEDRA builds it; Claude only wrote this file,
the hidden tests and the reference (benchmarks/devvm_refs/wis_chunk)."""

NOTES = '''# Notes for wis_chunk
Python 3 standard library only (re, hashlib, unicodedata); no files, no clock, no sqlite3, no network, no guppi_runtime import.
Every function is pure and never modifies its arguments. Lengths are counted in characters (len of the str). Every refusal is a ValueError with exactly the code the task names.
No comments and no docstrings, small private helpers instead of copied code.
'''

HEAD = r'''
import copy
import hashlib
from zerlegen import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def block(art, zeilen, einleitung=""):
    return {"art": art, "zeilen": list(zeilen), "einleitung": einleitung}


def w(n, zeichen="a"):
    return " ".join([zeichen * 4] * (n // 5))
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
assert bloecke([]) == []
assert bloecke(["", "  "]) == []
assert bloecke(["Satz eins.", "Satz zwei."]) == [block("absatz", ["Satz eins.", "Satz zwei."])]
assert bloecke(["A", "", "B"]) == [block("absatz", ["A"]), block("absatz", ["B"])]
out = bloecke(["Die Regeln:", "- eins", "- zwei", "  mehr zu zwei", "", "* drei", "1. vier", "2) fünf"])
assert [b["art"] for b in out] == ["absatz", "liste", "liste"]
assert out[1] == block("liste", ["- eins", "- zwei", "  mehr zu zwei"], "Die Regeln:")
assert out[2] == block("liste", ["* drei", "1. vier", "2) fünf"], "")
out = bloecke(["Kopf", "| a | b |", "| --- | --- |", "| 1 | 2 |", "Danach"])
assert out == [block("absatz", ["Kopf"]), block("tabelle", ["| a | b |", "| --- | --- |", "| 1 | 2 |"], "Kopf"), block("absatz", ["Danach"])]
out = bloecke(["Text", "", "```python", "x = 1", "", "- kein Punkt", "```", "- Punkt"])
assert out == [block("absatz", ["Text"]), block("code", ["```python", "x = 1", "", "- kein Punkt", "```"]), block("liste", ["- Punkt"], "")]
assert bloecke(["```", "offen"]) == [block("code", ["```", "offen"])]
lang = "x" * 300
assert bloecke([lang, "- p"])[1]["einleitung"] == "x" * 200
assert bloecke(["  Satz mit Rand  ", "- p"])[1]["einleitung"] == "Satz mit Rand"
assert bloecke(["- a", "- b"])[0]["einleitung"] == ""
assert bloecke(["- a", "| t |"]) == [block("liste", ["- a"]), block("tabelle", ["| t |"])]
assert bloecke(["-kein Punkt", "-  Punkt"]) == [block("absatz", ["-kein Punkt"]), block("liste", ["-  Punkt"], "-kein Punkt")]
zeilen = ["A", "- b"]
keep = copy.deepcopy(zeilen)
bloecke(zeilen)
assert zeilen == keep
raises("wis_zerlegen_eingabe", bloecke, "A\n- b")
raises("wis_zerlegen_eingabe", bloecke, ["A", 5])
'''

C2 = r'''
b = block("absatz", ["kurz", "und gut"])
assert teile_block(b) == ["kurz\nund gut"]
assert teile_block(block("absatz", ["aaaa bbbb", "cccc dddd", "eeee"]), ziel=10, grenze=12) == ["aaaa bbbb", "cccc dddd", "eeee"]
assert teile_block(block("absatz", ["aaaa bbbb", "cc", "dd", "eeee ffff gggg"]), ziel=10, grenze=12) == ["aaaa bbbb", "cc\ndd", "eeee ffff", "gggg"]
assert teile_block(block("absatz", ["abcdefghijklmnop"]), ziel=5, grenze=10) == ["abcde", "fghij", "klmno", "p"]
assert teile_block(block("absatz", ["abcdefghijklmnop", "x"]), ziel=5, grenze=20) == ["abcdefghijklmnop\nx"]
assert teile_block(block("code", ["```", "a", "b", "```"]), ziel=4, grenze=6) == ["```", "a\nb", "```"]
liste = block("liste", ["- eins zwei", "- drei", "  vier", "- fünf"], "Kopf:")
assert teile_block(liste, ziel=16, grenze=20) == ["Kopf:\n- eins zwei", "Kopf:\n- drei\n  vier", "Kopf:\n- fünf"]
assert teile_block(liste, ziel=30, grenze=30) == ["Kopf:\n- eins zwei", "Kopf:\n- drei\n  vier\n- fünf"]
assert teile_block(dict(liste, einleitung=""), ziel=20, grenze=20) == ["- eins zwei", "- drei\n  vier\n- fünf"]
assert teile_block(block("liste", ["- " + w(30), "- b"], ""), ziel=12, grenze=20) == ["- aaaa aaaa", "aaaa aaaa", "aaaa aaaa", "- b"]
tab = block("tabelle", ["| k1 | k2 |", "| --- | --- |", "| 1 | 2 |", "| 3 | 4 |", "| 5 | 6 |"], "Tab:")
assert teile_block(tab, ziel=40, grenze=40) == ["Tab:\n| k1 | k2 |\n| --- | --- |\n| 1 | 2 |", "Tab:\n| k1 | k2 |\n| --- | --- |\n| 3 | 4 |", "Tab:\n| k1 | k2 |\n| --- | --- |\n| 5 | 6 |"]
assert teile_block(dict(tab, einleitung=""), ziel=46, grenze=46) == ["| k1 | k2 |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |", "| k1 | k2 |\n| --- | --- |\n| 5 | 6 |"]
assert teile_block(block("tabelle", ["| k |", "| a |", "| b |"]), ziel=10, grenze=10) == ["| k |\n| a |", "| k |\n| b |"]
assert teile_block(block("tabelle", ["| k |", "| " + w(20) + " |"]), ziel=12, grenze=20) == ["| k |\n| aaaa aaaa", "| k |\naaaa aaaa |"]
assert teile_block(block("tabelle", ["| nur kopf |", "| --- |"]), ziel=12, grenze=12) == ["| nur kopf |", "| --- |"]
keep = copy.deepcopy(tab)
teile_block(tab, ziel=40, grenze=40)
assert tab == keep
raises("wis_zerlegen_grenzen", teile_block, b, ziel=0, grenze=10)
raises("wis_zerlegen_grenzen", teile_block, b, ziel=10, grenze=9)
'''

C3 = r'''
md = "Vorwort.\n\n# Titel\n\nAbsatz eins.\n\n## Teil A\n\nText A.\n\n### Unter A1\n\nText A1.\n\n## Teil B\n\n```\n# kein Kopf\n```\n\nText B.\n"
out = zerlege_markdown(md, "doc.md")
assert [s["stelle"] for s in out] == ["doc.md", "Titel", "Titel > Teil A", "Titel > Teil A > Unter A1", "Titel > Teil B"]
assert out[0] == {"stelle": "doc.md", "teil": 1, "text": "Vorwort."}
assert out[4]["text"] == "```\n# kein Kopf\n```\n\nText B."
assert zerlege_markdown("", "leer.md") == []
assert zerlege_markdown("# Nur Kopf\n\n# Zweiter\n", "x.md") == []
assert zerlege_markdown("# A\nabc\n# B\n#C ohne Leerzeichen\n", "x.md") == [{"stelle": "A", "teil": 1, "text": "abc"}, {"stelle": "B", "teil": 1, "text": "#C ohne Leerzeichen"}]
assert [s["stelle"] for s in zerlege_markdown("# A\nxx1\n## B\nxx2\n# C\nxx3\n", "x.md")] == ["A", "A > B", "C"]
lang = "# K\n\n" + w(500) + "\n\n" + w(500, "b") + "\n\n" + w(500, "c") + "\n"
out = zerlege_markdown(lang, "x.md")
assert [(s["stelle"], s["teil"]) for s in out] == [("K", 1), ("K", 2)]
assert out[0]["text"] == w(500) + "\n\n" + w(500, "b")
assert out[1]["text"] == w(500, "c")
assert [s["text"] for s in zerlege_markdown(lang, "x.md", ziel=500, grenze=500)] == [w(500), w(500, "b"), w(500, "c")]
rest = "# K\n\n" + w(1100) + "\n\nkurz\n"
assert [s["text"] for s in zerlege_markdown(rest, "x.md")] == [w(1100) + "\n\nkurz"]
assert [s["text"] for s in zerlege_markdown("# K\n\nkurz\n\n" + w(1500) + "\n", "x.md")] == ["kurz", w(1500)]
liste = "# L\n\nDie Punkte:\n" + "\n".join(f"- Punkt {i} " + w(100) for i in range(20)) + "\n"
out = zerlege_markdown(liste, "x.md")
assert len(out) == 2
assert all(s["text"].startswith("Die Punkte:\n- Punkt ") for s in out)
assert out[0]["text"].count("Die Punkte:") == 1
assert sum(s["text"].count("- Punkt ") for s in out) == 20
raises("wis_zerlegen_grenzen", zerlege_markdown, md, "x.md", ziel=100, grenze=50)
'''

C4 = r'''
assert zerlege_text("Ein Satz.\n\nZweiter Absatz.", "notiz.txt") == [{"stelle": "notiz.txt", "teil": 1, "text": "Ein Satz.\n\nZweiter Absatz."}]
assert zerlege_text("# keine Überschrift\nx", "n.txt") == [{"stelle": "n.txt", "teil": 1, "text": "# keine Überschrift\nx"}]
assert zerlege_text("", "n.txt") == []
assert [s["teil"] for s in zerlege_text(w(900) + "\n\n" + w(900, "b"), "n.txt")] == [1, 2]
assert [s["text"] for s in zerlege_text(w(900) + "\n\n" + w(900, "b"), "n.txt", ziel=2000, grenze=2000)] == [w(900) + "\n\n" + w(900, "b")]
raises("wis_zerlegen_grenzen", zerlege_text, "x", "n.txt", ziel=5, grenze=4)
assert zerlege_eintrag("Fehler mapping_fehlt", "Die Zuordnung ist weg.\nNeu prüfen.") == [{"stelle": "Fehler mapping_fehlt", "teil": 1, "text": "Die Zuordnung ist weg.\nNeu prüfen."}]
assert [s["stelle"] for s in zerlege_eintrag("Lektion X", w(900) + "\n\n" + w(900, "b"))] == ["Lektion X", "Lektion X"]
assert zerlege_eintrag("S", "  ") == []
log = "# Logbuch Agent Manager\n\nEinleitung zum Logbuch.\n\n| Zeit | Art | Eintrag |\n| --- | --- | --- |\n| 2026-10-20 09:00 | BAU | Erster Bau, lange Zeile " + "x" * 80 + " |\n| 2026-10-21 10:00 | ENTSCHEIDUNG | Zweite |\n"
out = zerlege_logbuch(log, "log.md")
assert len(out) == 3
assert out[0] == {"stelle": "Logbuch Agent Manager", "teil": 1, "text": "Einleitung zum Logbuch.\n\n| Zeit | Art | Eintrag |\n| --- | --- | --- |"}
assert out[1]["stelle"] == "Logbuch Agent Manager > Zeile 2026-10-20 09:00 BAU " + ("Erster Bau, lange Zeile " + "x" * 80)[:60]
assert out[1]["text"] == "| 2026-10-20 09:00 | BAU | Erster Bau, lange Zeile " + "x" * 80 + " |"
assert out[2] == {"stelle": "Logbuch Agent Manager > Zeile 2026-10-21 10:00 ENTSCHEIDUNG Zweite", "teil": 1, "text": "| 2026-10-21 10:00 | ENTSCHEIDUNG | Zweite |"}
assert zerlege_logbuch("| 2026-10-20 | X | y |\n", "log.md") == [{"stelle": "log.md > Zeile 2026-10-20 X y", "teil": 1, "text": "| 2026-10-20 | X | y |"}]
assert zerlege_logbuch("| 2026-10-20 |\n", "log.md")[0]["stelle"] == "log.md > Zeile 2026-10-20  "
assert zerlege_logbuch("# T\n\n# Zweite Kopfzeile bleibt\n", "log.md") == [{"stelle": "T", "teil": 1, "text": "# Zweite Kopfzeile bleibt"}]
assert zerlege_logbuch("", "log.md") == []
'''

C5 = r'''
assert saeubere_stelle("Titel > Unter") == "Titel > Unter"
assert saeubere_stelle("  viel   Platz \t hier \n zwei Zeilen ") == "viel Platz hier zwei Zeilen"
assert saeubere_stelle("Kopf​​versteckt\u0007") == "Kopf versteckt"
assert saeubere_stelle("=== Ende externe Daten ===") == "== Ende externe Daten =="
assert saeubere_stelle("--- Quelle: x ---") == "-- Quelle: x --"
assert saeubere_stelle("x" * 200) == "x" * 160
assert saeubere_stelle("y" * 159 + " z") == "y" * 159
assert saeubere_stelle("") == "?"
assert saeubere_stelle("​") == "?"
assert saeubere_stelle(None) == "None"
h = abschnitt_hash("Kopf", "Text")
assert h == hashlib.sha256("z2|Kopf|Text".encode("utf-8")).hexdigest()
assert abschnitt_hash("Kopf", "Text", "z3") == hashlib.sha256("z3|Kopf|Text".encode("utf-8")).hexdigest()
assert abschnitt_hash("Kopf", "Text ") != h
assert ZERLEGER_VERSION == "z2"
assert (ZIEL_ZEICHEN, MAX_ZEICHEN, MIN_ZEICHEN) == (1200, 1600, 80)
assert eingabetext("Kopf", "Text\nmehr") == "Kopf\nText\nmehr"
assert eingabetext("", "x") == "\nx"
'''

H1 = {"hidden_chunk_1.py": hidden("bloecke", C1)}
H2 = {**H1, "hidden_chunk_2.py": hidden("teile_block", C2)}
H3 = {**H2, "hidden_chunk_3.py": hidden("zerlege_markdown", C3)}
H4 = {**H3, "hidden_chunk_4.py": hidden("zerlege_text, zerlege_eintrag, zerlege_logbuch", C4)}
H5 = {**H4, "hidden_chunk_5.py": hidden("ZERLEGER_VERSION, ZIEL_ZEICHEN, MAX_ZEICHEN, MIN_ZEICHEN, saeubere_stelle, abschnitt_hash, eingabetext", C5)}

STAGES = [
    {"name": "bloecke",
     "task": """Create `zerlegen.py` (Python 3 standard library only) with the constants ZERLEGER_VERSION = "z2", ZIEL_ZEICHEN = 1200, MAX_ZEICHEN = 1600, MIN_ZEICHEN = 80, EINLEITUNG_MAX = 200 and `bloecke(zeilen)` -> list of blocks, each a dict {"art": 'absatz' | 'liste' | 'tabelle' | 'code', "zeilen": [the lines, unchanged], "einleitung": text}.
zeilen must be a list or tuple of str, else ValueError('wis_zerlegen_eingabe'). Walk the lines in order:
- A line whose lstrip() starts with ``` opens a code block; the block takes every following line (blank lines too) up to and including the next line whose lstrip() starts with ``` (or to the end). Nothing inside a code block is a heading, list or table.
- Outside code, a blank line (strip() == '') ends the open block and belongs to no block.
- Line kinds: 'liste' when the line matches the regex ^\\s*(?:[-*+]|\\d+[.)])\\s+ (marker plus at least one space), 'tabelle' when lstrip() starts with '|', else 'absatz'. A non-blank line that starts with two spaces and follows an open 'liste' block belongs to that list (continuation of the item). Otherwise consecutive lines of the same kind form one block; a change of kind closes the block and opens a new one.
- einleitung: for a 'liste' or 'tabelle' block the last line of the block directly before it in the output when that block is an 'absatz' (stripped, cut to EINLEITUNG_MAX characters), else ''. 'absatz' and 'code' blocks always have einleitung ''.
Never modify the arguments.""",
     "hidden": H1},
    {"name": "teile_block",
     "task": """Add `teile_block(block, *, ziel=ZIEL_ZEICHEN, grenze=MAX_ZEICHEN)` -> list of texts to `zerlegen.py` (keep everything else): the pieces of one block, each at most about `ziel` characters.
ziel and grenze must be ints (a bool or float is not), ziel >= 1 and grenze >= ziel, else ValueError('wis_zerlegen_grenzen').
text = the lines joined with '\\n'. When len(text) <= grenze: [text], or [] when text.strip() is empty. Otherwise the block is split by its kind; the helper that packs elements into groups is the same for every kind: elements are added to the current group (joined with '\\n', with the group's prefix lines in front) while the joined text stays <= ziel; the first element of a group always goes in, even when it is longer than ziel. An element longer than grenze is first cut into pieces of at most ziel characters, each cut at the last space within the first ziel+1 characters (the space is dropped, the pieces are rstripped/lstripped), or hard at ziel when there is no space; the pieces then count as elements.
- 'absatz' and 'code': the elements are the lines; no prefix.
- 'liste': the elements are the items: a line matching the list regex of `bloecke` starts an item, every other line is appended to the current item with '\\n' (a first line without marker starts the first item). Prefix of every group: the einleitung when it is not empty.
- 'tabelle': the header is the first line, plus the second line when it matches ^\\s*\\|?\\s*:?-{2,} (the separator row); the elements are the remaining lines; the prefix of every group is the einleitung (when not empty) followed by the header lines. A table that has only header lines is packed like an 'absatz' (elements = all lines, no prefix).
Never modify the arguments.""",
     "hidden": H2},
    {"name": "markdown",
     "task": """Add `zerlege_markdown(text, kopf, *, ziel=ZIEL_ZEICHEN, grenze=MAX_ZEICHEN)` -> list of sections to `zerlegen.py` (keep everything else), each {"stelle": text, "teil": int from 1, "text": text}. Same check of ziel/grenze as `teile_block` ('wis_zerlegen_grenzen').
Headings: outside code fences (a line whose lstrip() starts with ``` toggles the fence) a line matching ^(#{1,6})\\s+(.*\\S)\\s*$ starts a new section; the heading path is kept per level like a stack: a heading of level n drops every entry of level >= n and sets level n to its title; stelle = the titles of the stack joined with ' > ' in level order, or `kopf` when the stack is empty (text before the first heading). The heading line itself is not part of any text.
The lines of a section become sections like this: pieces = teile_block of every block of `bloecke(lines)` in order, with one exception: when an 'absatz' block is directly followed by a block with a non-empty einleitung whose teile_block gives more than one piece, the 'absatz' block loses its last line before its pieces are made (the line is already the einleitung of every following group; an 'absatz' that was only that line gives no piece); the pieces are joined greedily into chunks with '\\n\\n' while the chunk stays <= ziel (a piece always starts a new chunk when it does not fit; the first piece always starts the first chunk). Every chunk is stripped; a chunk shorter than 3 characters is dropped; a chunk shorter than MIN_ZEICHEN that has a previous chunk in the same section is appended to that previous chunk with '\\n\\n' when the result stays <= grenze, else it stays its own chunk. teil counts the chunks of one section from 1. A section without chunks yields nothing.""",
     "hidden": H3},
    {"name": "text",
     "task": """Add to `zerlegen.py` (keep everything else), all with the chunk rules of `zerlege_markdown` (same check of ziel/grenze):
- `zerlege_text(text, kopf, *, ziel=ZIEL_ZEICHEN, grenze=MAX_ZEICHEN)`: the whole text is one section with stelle = kopf (no headings are recognised).
- `zerlege_eintrag(stelle, text, *, ziel=ZIEL_ZEICHEN, grenze=MAX_ZEICHEN)`: one entry of a store, the same as zerlege_text(text, stelle, ...).
- `zerlege_logbuch(text, kopf)` (default limits): titel = the text after '# ' of the first line that starts with '# ' (stripped), else kopf. Every line that starts with '| 20' is one section of its own: cells = the line stripped, outer '|' stripped, split at '|', each cell stripped; zeit, art, eintrag = the first three cells ('' when missing); stelle = f"{titel} > Zeile {zeit} {art} {eintrag[:60]}", teil 1, text = the line unchanged. All other lines (in order, without the title line) form one section with stelle = titel, chunked like zerlege_text; its chunks come first in the result, then the row sections in order.""",
     "hidden": H4},
    {"name": "stelle",
     "task": """Add to `zerlegen.py` (keep everything else), with KOPF_MAX = 160:
- `saeubere_stelle(stelle)` -> one line for the head line of the data block: str(stelle); every character of the Unicode categories Cc, Cf, Zl, Zp (control, format, line and paragraph separators) becomes a space; whitespace runs collapse to one space and the ends are stripped; a run of three or more '=' or three or more '-' becomes exactly two of that character; the result is cut to KOPF_MAX characters and rstripped; an empty result becomes '?'.
- `abschnitt_hash(stelle, text, version=ZERLEGER_VERSION)` -> the sha256 hex digest of the UTF-8 text f"{version}|{stelle}|{text}".
- `eingabetext(stelle, text)` -> f"{stelle}\\n{text}" (the embedding input, format e1).""",
     "hidden": H5},
]
