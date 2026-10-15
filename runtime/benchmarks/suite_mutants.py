r"""Finds gaps in a hidden acceptance suite by mutation testing (hardening round, Captain 2026-10-09).

    .venv\Scripts\python.exe benchmarks/suite_mutants.py <suite_dir> [<suite_dir> ...] [--max 120]

The reference of the suite is changed in one small place at a time (a comparison turned around, `and` and `or` swapped, a number moved by one, a constant flipped, a return value replaced by None, a branch of an `if` emptied).
Each changed reference ("mutant") runs through the suite on the host (trusted code only: it is derived from the reference). A mutant that PASSES every criterion SURVIVED: the suite does not notice that behaviour,
which is either a gap in the hidden tests (like the `peak_date` case of the Guppy meter that the am008 suite missed until 2026-10-09) or an equivalent change that does not alter behaviour. The list is for a human to read.
The suite files are not changed.
"""
import argparse
import ast
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.acceptance_suite import host_runner, load_suite, run_suite  # noqa: E402

COMPARE_SWAPS = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}


def sites(tree):
    """[(kind, index)] of every place that can be changed, in the order of ast.walk."""
    found = []
    for index, node in enumerate(ast.walk(tree)):
        if isinstance(node, ast.Compare) and type(node.ops[0]) in COMPARE_SWAPS:
            found.append(("compare", index))
        elif isinstance(node, ast.BoolOp):
            found.append(("boolop", index))
        elif isinstance(node, ast.Constant) and type(node.value) is int:
            found.append(("number", index))
        elif isinstance(node, ast.Constant) and type(node.value) is bool:
            found.append(("bool", index))
        elif isinstance(node, ast.Return) and node.value is not None and not (isinstance(node.value, ast.Constant) and node.value.value is None):
            found.append(("return", index))
        elif isinstance(node, ast.If) and node.body:
            found.append(("if", index))
    return found


def mutate(source, kind, target):
    """The source with the one change of `kind` at the node number `target`, or None when it does not parse back."""
    tree = ast.parse(source)
    for index, node in enumerate(ast.walk(tree)):
        if index != target:
            continue
        if kind == "compare":
            node.ops[0] = COMPARE_SWAPS[type(node.ops[0])]()
        elif kind == "boolop":
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        elif kind == "number":
            node.value = node.value + 1
        elif kind == "bool":
            node.value = not node.value
        elif kind == "return":
            node.value = ast.Constant(None)
        elif kind == "if":
            node.body = [ast.Pass()]
        break
    ast.fix_missing_locations(tree)
    try:
        return ast.unparse(tree)
    except Exception:
        return None


def describe(source, kind, target):
    for index, node in enumerate(ast.walk(ast.parse(source))):
        if index == target:
            return f"{kind} at line {getattr(node, 'lineno', '?')}: {(ast.get_source_segment(source, node) or '')[:90]!r}"
    return kind


def survivors(suite, maximum=120):
    """For every reference file: the mutants that pass the whole suite. Returns (tried, [description])."""
    runner, tried, alive = host_runner(timeout=60), 0, []
    for name, source in sorted(suite.reference.items()):
        try:
            todo = sites(ast.parse(source))
        except SyntaxError:
            continue
        for kind, target in todo[:maximum]:
            changed = mutate(source, kind, target)
            if changed is None or changed == source:
                continue
            tried += 1
            files = {**suite.reference, name: changed}
            if run_suite(suite, files, runner)["passed"]:
                alive.append(f"{name}: {describe(source, kind, target)}")
    return tried, alive


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("suites", nargs="+")
    ap.add_argument("--max", type=int, default=120, help="most mutants per reference file")
    args = ap.parse_args()
    for folder in args.suites:
        suite = load_suite(folder)
        tried, alive = survivors(suite, args.max)
        print(f"{suite.label()}: {tried} mutants, {len(alive)} survived ({100 * (tried - len(alive)) // max(tried, 1)} % caught)")
        for line in alive:
            print("   survived:", line)


if __name__ == "__main__":
    main()
