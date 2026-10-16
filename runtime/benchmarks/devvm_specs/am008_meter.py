"""AM-008 (Guppy meter data, 2026-10-08): the numbers behind the small "how much code was written" window of the Guppy XP desktop (cards plus a weekly activity grid, like the Captain's example picture).
Pure functions on plain dicts, three small stages with hidden tests written outside the models and a last stage "all". GUPPI builds it, Claude only wrote this file and the reference. Build only, no integration."""

NOTES = '''# Notes for code_meter
Pure Python 3 standard library, no file or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
A record is {"date": "YYYY-MM-DD", "author": "guppi" or "claude", "added": int >= 0}. Records that are not dicts, have another author, a bad date or an added that is not a non-negative int (a bool is not an int) are skipped without error.
'''

COMMON = r'''
import copy
import datetime
from code_meter import IMPORTS

R = [{"date": "2026-10-05", "author": "guppi", "added": 100}, {"date": "2026-10-05", "author": "claude", "added": 50}, {"date": "2026-10-07", "author": "guppi", "added": 10},
     {"date": "2026-10-08", "author": "claude", "added": 300}, {"date": "2026-10-08", "author": "guppi", "added": 20}]
TODAY = "2026-10-08"
D = {"2026-10-05": {"guppi": 100, "claude": 50}, "2026-10-07": {"guppi": 10, "claude": 0}, "2026-10-08": {"guppi": 20, "claude": 300}}
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r"""
snap = copy.deepcopy(R)
assert daily_totals(R) == D and list(daily_totals(R)) == sorted(D) and R == snap
assert daily_totals([]) == {} and daily_totals(iter(R[:1])) == {"2026-10-05": {"guppi": 100, "claude": 0}}
junk = ["x", None, 5, {}, {"date": "2026-13-01", "author": "guppi", "added": 1}, {"date": "x", "author": "guppi", "added": 1}, {"date": None, "author": "guppi", "added": 1},
        {"date": "2026-10-05", "author": "bob", "added": 1}, {"date": "2026-10-05", "author": "guppi", "added": -1}, {"date": "2026-10-05", "author": "guppi", "added": True},
        {"date": "2026-10-05", "author": "guppi", "added": 1.5}, {"date": "2026-10-05", "author": "guppi", "added": "3"}, {"date": "2026-10-05", "author": "guppi"}]
assert daily_totals(junk) == {} and daily_totals(junk + R) == D
assert daily_totals([{"date": "2026-10-05", "author": "guppi", "added": 0}]) == {"2026-10-05": {"guppi": 0, "claude": 0}}
assert daily_totals([{"date": "2026-10-05", "author": "guppi", "added": 4}] * 3)["2026-10-05"]["guppi"] == 12
"""

C2 = r"""
snap = copy.deepcopy(D)
grid = heatmap(D, TODAY, 3)
assert D == snap and len(grid) == 7 and all(len(row) == 3 for row in grid)
assert grid[3][2] == {"date": "2026-10-08", "guppi": 20, "claude": 300, "lines": 320, "level": 4}
assert grid[0][2] == {"date": "2026-10-05", "guppi": 100, "claude": 50, "lines": 150, "level": 2}
assert grid[2][2]["date"] == "2026-10-07" and grid[2][2]["lines"] == 10 and grid[2][2]["level"] == 1
assert grid[1][2] == {"date": "2026-10-06", "guppi": 0, "claude": 0, "lines": 0, "level": 0}
assert [grid[r][2] for r in (4, 5, 6)] == [None, None, None]
assert grid[0][0]["date"] == "2026-09-21" and grid[6][1]["date"] == "2026-10-04" and grid[0][1]["date"] == "2026-09-28"
assert all(grid[r][c] is not None for r in range(7) for c in (0, 1))
assert heatmap(D, "2026-10-11", 1)[6][0]["date"] == "2026-10-11" and heatmap(D, "2026-10-11", 1)[0][0]["date"] == "2026-10-05"
empty = heatmap({}, TODAY, 2)
assert all(c is None or (c["level"] == 0 and c["lines"] == 0) for row in empty for c in row)
levels = heatmap({"2026-10-05": {"guppi": 1, "claude": 0}, "2026-10-06": {"guppi": 25, "claude": 0}, "2026-10-07": {"guppi": 26, "claude": 0}, "2026-10-08": {"guppi": 100, "claude": 0}}, TODAY, 1)
assert [levels[r][0]["level"] for r in range(4)] == [1, 1, 2, 4]
assert len(heatmap(D, TODAY)[0]) == 20 and heatmap(D, TODAY)[3][19]["date"] == TODAY
old = heatmap({"2020-01-01": {"guppi": 999, "claude": 0}}, TODAY, 2)
assert all(c is None or c["level"] == 0 for row in old for c in row)
"""

C3 = r"""
snap = copy.deepcopy(D)
c = cards(D, TODAY)
assert D == snap
assert c == {"total_lines": 480, "guppi_lines": 130, "claude_lines": 350, "guppi_share": 27, "active_days": 3, "peak_date": "2026-10-08", "last_30_lines": 480}
assert cards({}, TODAY) == {"total_lines": 0, "guppi_lines": 0, "claude_lines": 0, "guppi_share": 0, "active_days": 0, "peak_date": None, "last_30_lines": 0}
old = {**D, "2026-09-08": {"guppi": 1000, "claude": 0}, "2026-09-09": {"guppi": 7, "claude": 0}}
c = cards(old, TODAY)
assert c["last_30_lines"] == 487 and c["total_lines"] == 1487 and c["peak_date"] == "2026-09-08"
tie = {"2026-10-02": {"guppi": 5, "claude": 5}, "2026-10-01": {"guppi": 10, "claude": 0}, "2026-10-03": {"guppi": 0, "claude": 0}}
c = cards(tie, TODAY)
assert c["peak_date"] == "2026-10-01" and c["active_days"] == 2
assert cards({"2026-10-08": {"guppi": 1, "claude": 2}}, TODAY)["guppi_share"] == 33 and cards({"2026-10-08": {"guppi": 1, "claude": 1}}, TODAY)["guppi_share"] == 50
assert cards({"2026-10-08": {"guppi": 1, "claude": 7}}, TODAY)["guppi_share"] == 13 and cards({"2026-10-08": {"guppi": 5, "claude": 0}}, TODAY)["guppi_share"] == 100
assert cards({"2026-10-08": {"guppi": 3, "claude": 5}}, TODAY)["guppi_share"] == 38
zero = cards({"2026-10-07": {"guppi": 0, "claude": 0}, "2026-10-08": {"guppi": 0, "claude": 0}}, TODAY)
assert zero["peak_date"] is None and zero["active_days"] == 0 and zero["total_lines"] == 0
"""

STYLE = " No comments and no docstrings. Never modify the arguments. Put repeated checks into small private helpers."

STAGES = [
    {"name": "daily",
     "task": """Create `code_meter.py` (Python 3 standard library only) with `daily_totals(records) -> dict`. `records` is any iterable of records {"date": "YYYY-MM-DD", "author": "guppi" or "claude", "added": int}. Skip silently every item that is not a dict, whose author is not "guppi" or "claude",
whose date is not a str that `datetime.date.fromisoformat` accepts, or whose "added" is missing, negative or not an int (a bool or a float is not valid). Return {date: {"guppi": n, "claude": n}} with the added lines summed per date and author (a missing author counts 0), the keys sorted ascending,
and the date normalised with `.isoformat()`.""" + STYLE + """ Add `tests/test_code_meter.py` (unittest) with your own tests.""",
     "hidden": {"hidden_m1.py": hidden("daily_totals", C1)}},
    {"name": "heatmap",
     "task": """In the existing `code_meter.py` (keep the other functions) add `heatmap(daily, today, weeks=20) -> list`: a grid of 7 rows (Monday=0 to Sunday=6) and `weeks` columns, the oldest week on the left, the last column is the week that contains `today` (an ISO date str). `daily` is the result of `daily_totals`.
A cell is {"date": iso str, "guppi": n, "claude": n, "lines": guppi+claude, "level": 0..4} (a day without data has zeros). A day after `today` is None. The level of a day is 0 when it has no lines, else `1 + (lines * 4 - 1) // peak` where peak is the largest `lines` of any day shown in the grid
(0 for every cell when the peak is 0; days outside the grid do not count).""" + STYLE + """ Add tests to `tests/test_code_meter.py`.""",
     "hidden": {"hidden_m2.py": hidden("daily_totals, heatmap", C2)}},
    {"name": "cards",
     "task": """In the existing `code_meter.py` (keep the other functions) add `cards(daily, today) -> dict` with exactly the keys: "total_lines" (all guppi+claude), "guppi_lines", "claude_lines", "guppi_share" (int percent of guppi in total, rounded half up, 0 when total is 0, computed with integers only),
"active_days" (days with more than 0 lines), "peak_date" (the date with the most lines, the EARLIEST date on a tie, None when there is no day with lines) and "last_30_lines" (lines of the 30 days that end with `today`, today included).""" + STYLE + """ Add tests to `tests/test_code_meter.py`.""",
     "hidden": {"hidden_m3.py": hidden("daily_totals, heatmap, cards", C3)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_code_meter.py` and read `code_meter.py` once more. Make sure no check is copied into several functions, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_full_m.py": hidden("daily_totals, heatmap, cards", C1 + C2 + C3)}},
]
