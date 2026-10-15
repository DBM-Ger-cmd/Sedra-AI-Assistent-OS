"""E-07 (coder extension "tool card after a failed call", 2026-10-10): when a tool call fails, the toolbox appends a short card that explains how to use exactly this tool for exactly
this kind of error, but each card only once per run (little-coder: tool skill cards selected by error recovery first). `tool_cards.py` only SELECTS: the rules and the card texts are
data given by the caller (Claude writes them for the integration). Pure, no file access. GUPPI builds it, Claude only wrote this file and the hidden tests.
Plan: <projekte>\\Guppy\\ERWEITERUNGSPLAN_CODER_2026-10-10.md."""

NOTES = '''# Notes for tool_cards
Pure Python 3 standard library (re), no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
A tool result is the text the toolbox returns; a failed call returns a text that starts with "error:".
'''

COMMON = r'''
import copy
from tool_cards import IMPORTS

RULES = [("edit_file", r"old was not found", "edit_not_found"), ("edit_file", r"occurs \d+ times", "edit_ambiguous"), ("write_file", r"already exists", "write_exists"),
         ("*", r"is required", "missing_arg"), ("read_file", r"(", "broken_rule"), ("read_file", r"only has \d+ lines", "read_range")]
CARDS = {"edit_not_found": "CARD A", "edit_ambiguous": "CARD B", "write_exists": "CARD C", "missing_arg": "CARD D", "read_range": "CARD E"}
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r"""
assert pick(RULES, "edit_file", "error: old was not found. The most similar lines ...") == "edit_not_found"
assert pick(RULES, "edit_file", "error: OLD WAS NOT FOUND") == "edit_not_found"
assert pick(RULES, "edit_file", "error: old occurs 3 times: add surrounding lines") == "edit_ambiguous"
assert pick(RULES, "write_file", "error: write_file refused: a.py already exists (40 lines)") == "write_exists"
assert pick(RULES, "move_file", "error: source is required") == "missing_arg"
assert pick(RULES, "edit_file", "error: path is required") == "missing_arg"
assert pick(RULES, "read_file", "error: the file only has 12 lines") == "read_range"
assert pick(RULES, "edit_file", "edited a.py (120 bytes)") is None
assert pick(RULES, "edit_file", "old was not found") is None
assert pick(RULES, "list_dir", "error: folder_not_found") is None
assert pick([], "edit_file", "error: old was not found") is None
assert pick(RULES, None, "error: x is required") is None and pick(RULES, "edit_file", None) is None
assert pick([("edit_file", "x"), 5, ("edit_file", r"not found", "k")], "edit_file", "error: not found") == "k"
snap = copy.deepcopy(RULES)
pick(RULES, "read_file", "error: the file only has 1 lines")
assert RULES == snap
"""

C2 = r"""
cp = CardPicker(CARDS, RULES)
assert cp.max_per_key == 1
assert cp.after("edit_file", "error: old was not found.") == "CARD A"
assert cp.after("edit_file", "error: old was not found.") is None
assert cp.after("edit_file", "error: old occurs 2 times") == "CARD B"
assert cp.after("edit_file", "edited a.py") is None
assert cp.after("read_file", "error: the file only has 3 lines") == "CARD E"
assert cp.shown == {"edit_not_found": 1, "edit_ambiguous": 1, "read_range": 1}
two = CardPicker(CARDS, RULES, max_per_key=2)
assert [two.after("write_file", "error: a.py already exists") for _ in range(3)] == ["CARD C", "CARD C", None]
nocard = CardPicker({}, RULES)
assert nocard.after("edit_file", "error: old was not found") is None and nocard.shown == {}
junk = CardPicker(CARDS, [5, None, ("edit_file", "not found", "edit_not_found")])
assert junk.after("edit_file", "error: old was not found") == "CARD A"
zero = CardPicker(CARDS, RULES, max_per_key=0)
assert zero.after("edit_file", "error: old was not found") is None
for bad in (-1, True, 1.5):
    try:
        CardPicker(CARDS, RULES, max_per_key=bad)
        raise AssertionError(bad)
    except ValueError:
        pass
c = dict(CARDS)
cp2 = CardPicker(c, RULES)
cp2.after("edit_file", "error: old was not found")
assert c == CARDS
s = cp2.shown
s["edit_not_found"] = 0
assert cp2.after("edit_file", "error: old was not found") is None
"""

STYLE = " No comments and no docstrings. Never modify the arguments. Put repeated checks into small private helpers."

STAGES = [
    {"name": "cards",
     "task": """Create `tool_cards.py` (Python 3 standard library only) with:
- `pick(rules, tool, result) -> str or None`: the card key for a failed tool call. Only a `result` that is a str starting with "error:" counts (otherwise None; also None when tool is not a str). `rules` is a list of (tool_name, pattern, key) tuples, checked in order: the first rule whose tool_name equals `tool` or is "*" and whose pattern (a regular expression, re.search, case-insensitive) is found in result gives its key. A rule that is not a tuple/list of exactly three str, or whose pattern is not a valid regular expression, is skipped silently.
- class `CardPicker(cards, rules, max_per_key=1)`: `cards` is a dict key -> card text. max_per_key must be an int >= 0 (a bool is not an int), otherwise ValueError. Attribute `max_per_key`, and the property `shown`: a NEW dict key -> how often that card was handed out (only keys handed out at least once; changing it must not change the picker).
`after(tool, result) -> str or None`: key = pick(rules, tool, result); when the key has a card and that card was handed out fewer than max_per_key times, count it and return the card text; otherwise None.""" + STYLE + """ Add `tests/test_tool_cards.py` (unittest) with your own tests.""",
     "hidden": {"hidden_e07_1.py": hidden("pick, CardPicker", C1 + C2)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_tool_cards.py` and read `tool_cards.py` once more. Make sure no check is copied into several places, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_e07_full.py": hidden("pick, CardPicker", C1 + C2)}},
]
