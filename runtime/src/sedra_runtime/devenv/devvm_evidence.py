"""Evidence for the arbiter (Captain's idea 2026-10-07: the judge decides better with more and better evidence).

Until now the arbiter saw the task, up to 8000 characters of diff and the last 800 characters of the failure output. It never saw the check script, and a script stops at its FIRST failing
assert, so nothing was known about the other assertions (AM-004 `permissions`: assertions 4 to 13 contradicted assertions 14 and 18, and the judge could not see it).

This module gives it the facts: every `assert` of the check is rewritten into a recorder call and the whole script runs to the end (inside the microVM, through the same judge as the check),
so each assertion reports PASS or FAIL and, for `==`, the value it got and the value it expected. `format_evidence` turns that table and the numbered check script into text.
Nothing here decides anything; the arbiter still has to name the sentence of the task that supports a failing assertion.
"""
import ast
import json

MARKER = "EVIDENCE_JSON "
MAX_TEXT = 6000

DRIVER = r'''
import ast, json, sys
path = sys.argv[1]
source = open(path, encoding="utf-8").read()
tree = ast.parse(source)
sites = {}


def thunk(node):
    return ast.Lambda(args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), body=node)


class Rewrite(ast.NodeTransformer):
    count = 0

    def visit_Assert(self, node):
        self.count += 1
        test = node.test
        sites[self.count] = {"n": self.count, "line": node.lineno, "src": (ast.get_source_segment(source, node) or "")[:240], "pass": 0, "fail": 0, "error": 0, "first": None}
        parts = test.values if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And) else [test]       # a chain "a == 1 and b == 2 and ..." is judged part by part: the report names the FIRST part that is false
        entries = []
        for part in parts:
            if isinstance(part, ast.Compare) and len(part.ops) == 1:
                entries.append(ast.Tuple([ast.Constant((ast.get_source_segment(source, part) or "")[:160]), ast.Constant(type(part.ops[0]).__name__), thunk(part), thunk(part.left), thunk(part.comparators[0])], ast.Load()))
            else:
                entries.append(ast.Tuple([ast.Constant((ast.get_source_segment(source, part) or "")[:160]), ast.Constant(None), thunk(part), ast.Constant(None), ast.Constant(None)], ast.Load()))
        args = [ast.Constant(self.count), thunk(test), ast.List(entries, ast.Load())]
        return ast.copy_location(ast.Expr(ast.Call(ast.Name("__chk", ast.Load()), args, [])), node)


def show(fn):
    if fn is None:
        return None
    try:
        return repr(fn())[:200]
    except Exception as exc:
        return "<" + type(exc).__name__ + ">"


def first_false(parts):
    for src, op, whole, left, right in parts:
        try:
            if whole():
                continue
        except Exception as exc:
            return {"error": type(exc).__name__ + ": " + str(exc)[:120], "part": src, "chain": len(parts) > 1}
        return {"got": show(left), "expected": show(right), "op": op, "part": src, "chain": len(parts) > 1}
    return None


def __chk(n, test, parts):
    site = sites[n]
    try:
        ok = bool(test())
    except AssertionError:
        ok = False
    except Exception as exc:
        site["error"] += 1
        if site["first"] is None:
            site["first"] = {"error": type(exc).__name__ + ": " + str(exc)[:120]}
        return
    if ok:
        site["pass"] += 1
        return
    site["fail"] += 1
    if site["first"] is None:
        site["first"] = first_false(parts) or {"error": "fails"}


Rewrite().visit(tree)
ast.fix_missing_locations(tree)
setup_error = None
stop_line = None
stop_values = None


def script_frame_values(tb):
    """Line and simple values of the innermost frame of the test script itself: a test that stops with `raise AssertionError("...")` inside a loop (try / except / else) names no value, but the loop variable shows which case failed."""
    frame = None
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == path:
            frame = tb
        tb = tb.tb_next
    if frame is None:
        return None, None
    values = []
    for key, value in list(frame.tb_frame.f_locals.items()):
        if key.startswith("__") or callable(value) or type(value).__name__ == "module":
            continue
        try:
            text = repr(value)
        except Exception:
            continue
        values.append(key + "=" + text[:160])
    return frame.tb_lineno, values[-6:]


try:
    sys.path.insert(0, ".")
    exec(compile(tree, path, "exec"), {"__name__": "__main__", "__file__": path, "__chk": __chk})
except SystemExit:
    pass
except Exception as exc:
    setup_error = type(exc).__name__ + ": " + str(exc)[:160]
    try:
        stop_line, stop_values = script_frame_values(exc.__traceback__)
    except Exception:
        pass
print("EVIDENCE_JSON " + json.dumps({"sites": [sites[k] for k in sorted(sites)], "setup_error": setup_error, "stop_line": stop_line, "stop_values": stop_values}))
'''


def parse(output):
    """The evidence table from the judge's output, or None when the driver did not report."""
    for line in reversed(str(output).splitlines()):
        if line.startswith(MARKER):
            try:
                data = json.loads(line[len(MARKER):])
            except ValueError:
                return None
            return data if isinstance(data, dict) and isinstance(data.get("sites"), list) else None
    return None


def _ranges(numbers):
    out, run = [], []
    for n in numbers:
        if run and n == run[-1] + 1:
            run.append(n)
        else:
            if run: out.append(run)
            run = [n]
    if run: out.append(run)
    return ", ".join(f"#{r[0]}" if len(r) == 1 else f"#{r[0]}-#{r[-1]}" for r in out)


def stop_text(evidence):
    """' (line N; values: a=..., b=...)' of the place where the test script stopped, or ''."""
    if not evidence.get("stop_line"): return ""
    values = "; values: " + ", ".join(evidence["stop_values"]) if evidence.get("stop_values") else ""
    return f" (line {evidence['stop_line']}{values})"


def describe(first):
    """What one failing assertion found: for `==` the expected and the actual value; for another comparison (in, is, !=, <, ...) the part that is false with both values; for an error its text."""
    part = f"`{first['part']}`: " if first.get("part") and (first.get("chain") or first.get("op") not in (None, "Eq")) else ""
    if first.get("got") is not None and "expected" in first:
        if first.get("op") in (None, "Eq"): return f"{part}expected {first['expected']} but the work gives {first['got']}"
        return f"{part}left side is {first['got']}, right side is {first['expected']}"
    return part + str(first.get("error", ""))


def format_evidence(check, evidence, detail=8):
    """Failing assertions first, with what they got and expected (at most `detail` of them in full, the rest summarised), then the ranges of the passing and the unreached ones; at most MAX_TEXT characters."""
    sites = evidence["sites"]
    reached = lambda s: s["pass"] + s["fail"] + s["error"]
    failing = [s for s in sites if reached(s) and (s["fail"] or s["error"])]
    passing = [s["n"] for s in sites if reached(s) and not (s["fail"] or s["error"])]
    unreached = [s["n"] for s in sites if not reached(s)]
    lines = ["Evidence about the automatic check. Every assertion of the check was run separately and the script ran to the end (the work was not changed):"]
    for site in failing[:detail]:
        first = site["first"] or {}
        what = describe(first)
        lines.append(f"  #{site['n']} (line {site['line']}) FAILS {site['fail'] + site['error']} of {reached(site)} times: {what[:330]}\n      {site['src'][:150]}")
    if len(failing) > detail:
        lines.append(f"  ... and {len(failing) - detail} more assertions fail: " + _ranges([s["n"] for s in failing[detail:]]) + " (look at the pattern of the first ones)")
    if passing:
        lines.append("  pass: " + _ranges(passing))
    if unreached:
        lines.append("  NOT REACHED (the script stopped or the code around them never ran): " + _ranges(unreached))
    if evidence.get("setup_error"):
        lines.append(f"  the script itself stopped with: {evidence['setup_error']}" + stop_text(evidence))
    lines.append(f"{len(failing)} of {len(sites)} assertions fail" + (f", {len(unreached)} were not reached." if unreached else "."))
    result = "\n".join(lines)
    return result if len(result) <= MAX_TEXT else result[:MAX_TEXT] + "\n  ... (cut)"


def bug_report(evidence, limit=2):
    """A short bug report for the developer from the evidence table of an acceptance test the developer does not see: only the FIRST `limit` failing assertions, each with what the test expects and what the work gives
    (Captain 2026-10-09: the raw traceback of a hidden test shows neither value, so a rework round cannot find the defect). Empty when nothing fails."""
    lines = []
    for site in evidence.get("sites", []):
        if not (site["fail"] or site["error"]):
            continue
        first = site["first"] or {}
        what = describe(first) or "fails"
        if first.get("op") in (None, "Eq") and not first.get("chain") and first.get("got") is not None and "expected" in first: what = f"expects {first['expected']} but the work gives {first['got']}"
        lines.append(f"  - line {site['line']}: {site['src'][:150]}\n    the test {what[:300]}")
        if len(lines) == limit:
            break
    stopped = ""
    if evidence.get("setup_error"):       # the test script ended with an error instead of a failed assert (for example `raise AssertionError(...)` in a loop): say where and with which values
        stopped = f"The test script stopped with: {evidence['setup_error'][:200]}{stop_text(evidence)[:420]}"
    if not lines and not stopped: return ""
    return ("The first failing checks of the acceptance test:\n" + "\n".join(lines) if lines else "") + (("\n" if lines else "") + stopped if stopped else "")


ARBITER_RULES = ("\n\nHow to judge: the work is judged against the TASK, never against the check. For EVERY failing assertion above, find the sentence of the task that requires the EXPECTED value and quote it exactly. "
                 "If no sentence requires it, that assertion invents a requirement and the check is wrong there. If two assertions cannot both be right (the same situation expected to give different results), the check is wrong. "
                 "If a failing assertion is backed by a sentence of the task that the work violates, the work is wrong. Answer PASS only when every failing assertion is wrong or unsupported; give one line per failing assertion in `cause`: "
                 "#number: \"quoted sentence\" or #number: NONE.")


def chained_asserts(source, min_parts=3):
    """[(line, parts)] of the `assert a and b and c ...` lines with at least `min_parts` parts. The evidence driver names the first false part, but a hidden test that checks ONE thing per assert (or gives the assert a message)
    is easier for the developer to act on and for a reader to judge; the check is a hint for whoever writes acceptance tests, never a gate."""
    found = []
    try: tree = ast.parse(source)
    except SyntaxError: return found
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.BoolOp) and isinstance(node.test.op, ast.And) and len(node.test.values) >= min_parts:
            found.append((node.lineno, len(node.test.values)))
    return sorted(found)
