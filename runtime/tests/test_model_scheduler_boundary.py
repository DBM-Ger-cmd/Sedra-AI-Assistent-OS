"""Spec 2, D2.2: the pure modules stay pure; the scheduler never reaches into core/."""
import ast
import unittest
from pathlib import Path

JOBS = Path(__file__).resolve().parents[1] / "src" / "guppi_runtime" / "jobs"


def imports(name):
    tree = ast.parse((JOBS / name).read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            found.add("." * node.level + (node.module or ""))
    return found


class BoundaryTests(unittest.TestCase):
    def test_slotplan_and_vramplan_import_neither_the_package_nor_sqlite(self):
        for name in ("slotplan.py", "vramplan.py"):
            with self.subTest(module=name):
                found = imports(name)
                self.assertFalse({m for m in found if m.startswith(".") or "guppi_runtime" in m or m.startswith("sqlite3")}, found)

    def test_the_scheduler_modules_do_not_import_core(self):
        for name in ("model_scheduler.py", "slot_store.py", "slot_db.py", "testlab.py"):
            with self.subTest(module=name):
                self.assertFalse({m for m in imports(name) if "core" in m.split(".")}, name)


if __name__ == "__main__":
    unittest.main()
