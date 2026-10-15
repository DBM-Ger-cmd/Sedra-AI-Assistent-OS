"""The core boundary of GUPPI itself (review 2026-10-11, finding 4): the core modules must not import the DevVM, agent manager or coder-extension parts, neither
directly nor through other modules (also not lazily inside a function: core_boundary reads every import with ast). Uses core_boundary.py, which GUPPI built in the
night chain of 2026-10-11 (integrated 2026-10-12). When this test fails, the message names the import chain to cut."""
import unittest
from pathlib import Path

from guppi_runtime.core_boundary import chains, violations

SRC = Path(__file__).resolve().parents[1] / "src"
P = "guppi_runtime."
# Since the package split of 2026-10-12 the core is the package guppi_runtime.core; runtime.py (the composition root) is checked with it.
CORE = [P + "core", P + "runtime"]
MOVED = ("mission", "brain", "guard", "audit", "message_bus", "registry", "step_journal", "permission_levels", "util", "mission_lock",
         "request_binding", "errors", "manual_plan")
# Build 16: the content guard lives in the core too (SPEC_EIN_SICHERER_WEG S1) – with the B6 modules it brings along, hash-checked.
ADDED = ("content_policy", "content_guard", "b6core") + tuple("b6core." + m for m in ("contracts", "names", "normalize", "privacy", "prompt", "pseudo"))
FORBIDDEN = [P + m for m in ("devenv", "devvm", "devvm_agents", "devvm_evidence", "devvm_mcp", "devvm_style", "devvm_tools", "agent_manager", "coder_ext")]


def sources():
    out = {}
    for path in sorted((SRC / "guppi_runtime").rglob("*.py")):
        parts = list(path.relative_to(SRC).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        out[".".join(parts)] = path.read_text(encoding="utf-8")
    return out


class CoreBoundary(unittest.TestCase):
    def test_the_core_imports_no_devvm_agent_manager_or_coder_ext_part(self):
        found = sources()
        self.assertGreater(len(found), 50)
        self.assertEqual(violations(found, CORE, FORBIDDEN), [])
        self.assertEqual(chains(found, CORE, FORBIDDEN), [], "cut the first forbidden import of each chain")

    def test_the_check_would_notice_a_forbidden_import(self):
        found = sources()
        found[P + "core.brain"] += "\nfrom ..devvm_tools import DevToolBox\n"
        self.assertEqual(violations(found, CORE, FORBIDDEN), [(P + "core.brain", P + "devvm_tools")])

    def test_the_core_imports_nothing_outside_its_package(self):
        found = sources()
        core = {name: text for name, text in found.items() if name == P + "core" or name.startswith(P + "core.")}
        self.assertEqual(set(core), {P + "core"} | {P + "core." + m for m in MOVED + ADDED})
        outside = [pair for pair in violations(core, [P + "core"], [P[:-1]]) if not pair[1].startswith(P + "core")]
        self.assertEqual(outside, [])

    def test_the_old_names_are_the_same_module_objects(self):
        import importlib
        for name in MOVED:
            self.assertIs(importlib.import_module(P + name), importlib.import_module(P + "core." + name), name)


if __name__ == "__main__":
    unittest.main()
