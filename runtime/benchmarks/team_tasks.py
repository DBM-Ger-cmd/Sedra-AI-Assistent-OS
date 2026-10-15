r"""Task set of the small-team bench (benchmarks/small_team.py): rework_bench's five tasks with stricter checks, plus three harder ones.

Why stricter: in the first full run (2026-10-05) the reviewer rejected two candidates that rework_bench's grader accepted, and it was right.
`isoformat_date` accepted `except ValueError: if "month" in str(e): raise ValueError("bad_day")` (every other bad date leaks the library's own error), and
`urlparse_port` accepted a version that dropped the `port is None` check (`http://127.0.0.1/` then dies with TypeError). The extra checks below close both.
rework_bench.py itself is not changed: its 2026-10-03 numbers stay comparable.

Why harder: Jan alone solved 10 of 10, so a reviewer could not show any use. The three new tasks need more than one change, so a first fix is often incomplete:
`parse_pair` (split, int, range), `get_nested` (two lookup levels, wrong type in between), `read_flag` (normalising and refusing unknown words).
Grading stays static (the answer is parsed, never executed on this host).
"""
from __future__ import annotations

import ast

from rework_bench import TASKS as BASE_TASKS, _try_guarded


def _calls(fn, suffix):
    return any(isinstance(n, ast.Call) and ast.unparse(n.func).endswith(suffix) for n in ast.walk(fn))


def _handler_has_no_condition(fn):
    """True when no `except` handler decides by looking at the message (an If or `str(e)` inside the handler)."""
    for t in ast.walk(fn):
        if isinstance(t, ast.Try):
            for h in t.handlers:
                if any(isinstance(n, ast.If) for n in ast.walk(h)) or "str(" in ast.unparse(h):
                    return False
    return True


def _none_handled(fn):
    """The missing-port case (`parsed.port` is None) is still handled: a comparison with None or `not port`."""
    for n in ast.walk(fn):
        if isinstance(n, ast.Compare) and any(isinstance(c, ast.Constant) and c.value is None for c in n.comparators):
            return True
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not) and ast.unparse(n.operand).split(".")[-1] == "port":      # `not port`, not `not 1 <= port <= 65535`
            return True
    return False


EXTRA = {
    "isoformat_date": {"handler_does_not_sniff_message": _handler_has_no_condition},
    "urlparse_port": {"missing_port_still_rejected": _none_handled},
}

HARD = [
    {"id": "pair_parse", "fn": "parse_pair",
     "code": 'def parse_pair(text):\n    """Return (a, b) as ints from "a,b" when both are whole numbers 0..255, else raise ValueError("bad_pair")."""\n'
             '    a, b = text.split(",")\n    return int(a), int(b)\n',
     "failure": "AssertionError: ValueError(\"bad_pair\") not raised for '1' / '300,1' / 'x,1'; got ValueError('not enough values to unpack'), no error, ValueError(\"invalid literal for int()\")",
     "repro": "REPRO   input '1': expected ValueError('bad_pair'), got ValueError: not enough values to unpack (expected 2, got 1) at mod.py:3\n"
              "REPRO   input '300,1': expected ValueError('bad_pair'), got (300, 1)\nREPRO   input 'x,1': expected ValueError('bad_pair'), got ValueError: invalid literal for int() with base 10: 'x' at mod.py:4",
     "checks": {"split_unpack_guarded": lambda f: _try_guarded(f, lambda n: isinstance(n, ast.Call) and ast.unparse(n.func).endswith("split"), "ValueError", "bad_pair")
                or any(isinstance(n, ast.Compare) and "len(" in ast.unparse(n) for n in ast.walk(f)),
                "int_guarded": lambda f: _try_guarded(f, lambda n: isinstance(n, ast.Call) and ast.unparse(n.func) == "int", "ValueError", "bad_pair"),
                "range_checked": lambda f: any(isinstance(n, ast.Compare) and any(isinstance(c, ast.Constant) and c.value == 255 for c in ast.walk(n)) for n in ast.walk(f))}},
    {"id": "nested_lookup", "fn": "get_nested",
     "code": 'def get_nested(config, section, key):\n    """Return config[section][key]; a missing section or key, or a section that is not a dict, raises LookupError("config_missing")."""\n'
             '    return config[section][key]\n',
     "failure": "AssertionError: LookupError('config_missing') not raised: KeyError('db') for {} / TypeError for {'db': None}",
     "repro": "REPRO   input ({}, 'db', 'port'): expected LookupError('config_missing'), got KeyError: 'db' at mod.py:3\n"
              "REPRO   input ({'db': None}, 'db', 'port'): expected LookupError('config_missing'), got TypeError: 'NoneType' object is not subscriptable at mod.py:3",
     "checks": {"lookup_guarded": lambda f: _try_guarded(f, lambda n: isinstance(n, ast.Subscript), "KeyError", "config_missing") or _try_guarded(f, lambda n: isinstance(n, ast.Subscript), "LookupError", "config_missing"),
                "wrong_type_handled": lambda f: "TypeError" in ast.unparse(f) or "isinstance(" in ast.unparse(f)}},
    {"id": "flag_words", "fn": "read_flag",
     "code": 'def read_flag(text):\n    """Return True for true/1/yes and False for false/0/no (any case, spaces around ignored); any other text raises ValueError("bad_flag")."""\n'
             '    return text in ("true", "1", "yes")\n',
     "failure": "AssertionError: ValueError('bad_flag') not raised for 'maybe'; got False. ' YES ' returned False, expected True",
     "repro": "REPRO   input 'maybe': expected ValueError('bad_flag'), got False at mod.py:3\nREPRO   input ' YES ': expected True, got False at mod.py:3",
     "checks": {"normalises": lambda f: _calls(f, ".strip") and _calls(f, ".lower"),
                "refuses_unknown": lambda f: "bad_flag" in ast.unparse(f) and any(isinstance(n, ast.Raise) for n in ast.walk(f)),
                "false_words_listed": lambda f: all(w in ast.unparse(f) for w in ("false", "no", "0"))}},
]


def _merged(task):
    extra = EXTRA.get(task["id"])
    return {**task, "checks": {**task["checks"], **extra}} if extra else task


BASE = [_merged(t) for t in BASE_TASKS]
TEAM_TASKS = BASE + HARD
SETS = {"base": BASE, "hard": HARD, "all": TEAM_TASKS}
