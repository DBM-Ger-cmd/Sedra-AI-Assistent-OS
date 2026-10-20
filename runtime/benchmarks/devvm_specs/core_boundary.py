"""Core boundary (review 2026-10-11, finding 4, docs/REVIEW_2026-10-11.md): GUPPI's core (mission, brain, guard, audit, bus, registry, journal ...) must not import
the DevVM, agent manager or coder-extension parts, neither directly nor through other modules. `core_boundary.py` reads the imports of Python sources with `ast` and lists
the forbidden ones. Pure functions, nothing is imported or executed. It is the first piece of the package split (core/, jobs/, models/, devvm/): a test can then keep the
boundary while GUPPI adds code to itself. GUPPI builds it (night chain 2026-10-11); Claude only wrote this file, the hidden tests and the reference
(benchmarks/devvm_refs/core_boundary)."""

NOTES = '''# Notes for core_boundary
Pure Python 3 standard library (ast, collections), no file, process or network access, nothing is imported or executed, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code.
Module names are dotted names such as "guppi_runtime.core.brain". A name belongs to a group when it equals the group or starts with the group followed by "." ("guppi_runtime.devenv.devvm_tools" is NOT inside "guppi_runtime.devenv.devvm").
'''

COMMON = r'''
from core_boundary import IMPORTS
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
assert imports_of("import os", "p.a") == ["os"]
assert imports_of("import os.path, json", "p.a") == ["json", "os.path"]
assert imports_of("import yaml as y", "p.a") == ["yaml"]
assert imports_of("from pathlib import Path", "p.a") == ["pathlib"]
assert imports_of("from .guard import Guard", "p.brain") == ["p.guard"]
assert imports_of("from ..util import x", "p.tools.shell") == ["p.util"]
assert imports_of("from . import a, b", "p.tools.shell") == ["p.tools.a", "p.tools.b"]
assert imports_of("from .tools import ToolManager", "p.runtime") == ["p.tools"]
assert imports_of("def f():\n    from .devvm import X\n    return X\n", "p.runtime") == ["p.devvm"]
assert imports_of("import b\nimport a\nimport b\n", "p.a") == ["a", "b"]
assert imports_of("", "p.a") == []
assert imports_of("x = 1", "p.a") == []
assert imports_of("from __future__ import annotations", "p.a") == ["__future__"]
for bad in ("def (", "import"):
    try:
        imports_of(bad, "p.a")
        raise AssertionError("no error")
    except ValueError as exc:
        assert str(exc) == "unparsable"
try:
    imports_of("from .. import x", "p.a")
    raise AssertionError("no error")
except ValueError as exc:
    assert str(exc) == "relative_import_beyond_top"
try:
    imports_of("from . import x", "solo")
    raise AssertionError("no error")
except ValueError as exc:
    assert str(exc) == "relative_import_beyond_top"
'''

C2 = r'''
S = {
    "g.brain": "from .guard import Guard\nfrom .devvm import Vm\n",
    "g.guard": "import yaml\n",
    "g.runtime": "from .agent_manager.cli import main\nfrom .brain import GuppiBrain\n",
    "g.devvm": "import os\n",
    "g.devvm_tools": "import os\n",
    "g.agent_manager.cli": "from ..devvm import Vm\n",
    "g.audit": "from .devvm_tools import x\n",
}
CORE = ["g.brain", "g.guard", "g.audit"]
BAD = ["g.devvm", "g.agent_manager"]
assert violations(S, CORE, BAD) == [("g.brain", "g.devvm")]
assert violations(S, CORE + ["g.runtime"], BAD) == [("g.brain", "g.devvm"), ("g.runtime", "g.agent_manager.cli")]
assert violations(S, ["g"], BAD) == [("g.agent_manager.cli", "g.devvm"), ("g.brain", "g.devvm"), ("g.runtime", "g.agent_manager.cli")]
assert violations(S, CORE, ["g.devvm_tools"]) == [("g.audit", "g.devvm_tools")]
assert violations(S, [], BAD) == []
assert violations(S, CORE, []) == []
assert violations({}, CORE, BAD) == []
copy = dict(S)
violations(S, CORE, BAD)
assert S == copy
try:
    violations({"g.guard": "def ("}, CORE, BAD)
    raise AssertionError("no error")
except ValueError as exc:
    assert str(exc) == "unparsable"
assert violations({"g.other": "def ("}, CORE, BAD) == []
'''

C3 = r'''
T = {
    "k.mission": "from .bus import Bus\n",
    "k.bus": "from .helpers import h\n",
    "k.helpers": "from .devvm.tools import run\n",
    "k.guard": "import yaml\n",
    "k.audit": "from .devvm import a\nfrom .bus import Bus\n",
    "k.loop1": "from .loop2 import x\n",
    "k.loop2": "from .loop1 import y\n",
    "k.devvm": "",
    "k.devvm.tools": "",
}
CORE = ["k.mission", "k.guard", "k.audit", "k.loop1"]
BAD = ["k.devvm"]
assert chains(T, CORE, BAD) == [["k.audit", "k.devvm"], ["k.mission", "k.bus", "k.helpers", "k.devvm.tools"]]
assert chains(T, ["k.guard", "k.loop1"], BAD) == []
assert chains(T, ["k.bus"], BAD) == [["k.bus", "k.helpers", "k.devvm.tools"]]
U = {
    "c.a": "from .z import q\nfrom .b import p\n",
    "c.b": "from .x.bad import r\n",
    "c.z": "from .y import s\n",
    "c.y": "from .x.worse import t\n",
}
assert chains(U, ["c.a"], ["c.x"]) == [["c.a", "c.b", "c.x.bad"]]
V = {"c.a": "from .x.zz import q\nfrom .x.aa import p\n"}
assert chains(V, ["c.a"], ["c.x"]) == [["c.a", "c.x.aa"]]
assert chains(T, [], BAD) == []
assert chains({}, CORE, BAD) == []
copy = dict(T)
chains(T, CORE, BAD)
assert T == copy
'''

STAGES = [
    {"name": "imports",
     "task": """Create `core_boundary.py` (Python 3 standard library only) with `imports_of(source, module) -> list[str]`: the dotted names a Python source imports. Nothing is imported or executed.
- source: the text of one Python file. module: its dotted module name (for example "guppi_runtime.core.brain").
- Parse with ast.parse; on SyntaxError raise ValueError("unparsable"). Look at EVERY import statement, also the ones inside functions (walk the whole tree).
- `import a.b, c as d` gives "a.b" and "c" (the real name, not the alias). `from x.y import z` gives "x.y".
- Relative imports: level n removes the last n parts of `module` to get the base; when n is greater than or equal to the number of parts of `module` raise ValueError("relative_import_beyond_top"). `from .x import z` gives base + ".x"; `from . import a, b` (no module after the dots) gives base + ".a" and base + ".b".
- Return the names sorted, each name once.
No comments and no docstrings, never modify the arguments, small private helpers instead of copied code. Add `tests/test_core_boundary.py` (unittest) with your own tests.""",
     "hidden": {"hidden_core_boundary_1.py": hidden("imports_of", C1)}},
    {"name": "violations",
     "task": """Add `violations(sources, core, forbidden) -> list[tuple[str, str]]` to `core_boundary.py`: the direct imports from the core into forbidden parts.
- sources: a dict {dotted module name: source text}. core and forbidden: lists of group names. A name belongs to a group when it equals the group or starts with the group followed by "." ("g.devvm_tools" is NOT inside "g.devvm").
- For every module in sources that belongs to a core group, every name from imports_of(its source, its module name) that belongs to a forbidden group gives the pair (module, imported name).
- Return the pairs sorted, each pair once. Modules outside the core are not parsed at all (a broken file there is no error); a broken core module raises the ValueError of imports_of.
Never modify the arguments. Add tests to `tests/test_core_boundary.py`.""",
     "hidden": {"hidden_core_boundary_2.py": hidden("imports_of, violations", C1 + C2)}},
    {"name": "chains",
     "task": """Add `chains(sources, core, forbidden) -> list[list[str]]` to `core_boundary.py`: also the INDIRECT ways from a core module into a forbidden part.
- For every module in sources that belongs to a core group (in sorted order) search breadth-first: start with the path [start]; take paths from the front of a queue; for the last module of a path go through imports_of(its source, its name) in that (sorted) order:
  - a name that belongs to a forbidden group ends the search for this start: the answer is the path plus that name;
  - otherwise a name that is a key of sources and was not seen before for this start (the start counts as seen) is marked as seen and the path plus that name goes to the back of the queue.
- A start without any forbidden name reached gives no entry. Return the list of answers (one list of names per start that reached a forbidden name, starts in sorted order). Use the same group rule as violations.
Never modify the arguments. Add tests to `tests/test_core_boundary.py`.""",
     "hidden": {"hidden_core_boundary_3.py": hidden("imports_of, violations, chains", C1 + C2 + C3)}},
    {"name": "all",
     "task": """Run the whole test file `tests/test_core_boundary.py` and read `core_boundary.py` once more. Make sure the group rule and the relative-import rule are each written only once, the file has no comments and no docstrings and there are no leftover debug files. Fix only real defects, keep the behaviour. If everything is fine, change nothing.""",
     "hidden": {"hidden_core_boundary_full.py": hidden("imports_of, violations, chains", C1 + C2 + C3)}},
]
