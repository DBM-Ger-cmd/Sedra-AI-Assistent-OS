"""Die Importgrenze des Pakets `wissen/` (Spec 7, D7.1): reine Module importieren nur die Standardbibliothek und einander in
fester Richtung; Harness-Module nur die erlaubten Teile von `guppi_runtime`; niemand außerhalb von `wissen/` importiert die reinen
Module; `core/` bleibt unberührt. Dazu: die Migrationen im Paket sind die Saat der Bau-Spec, Python 3.12 parst jedes Modul."""
import ast
import sys
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

SRC = Path(__file__).resolve().parents[1] / "src" / "guppi_runtime"
WISSEN = SRC / "wissen"
REIN = {"schema": set(), "zerlegen": set(), "vektor": set(), "fusion": set(), "ausgabe": {"zerlegen"}, "glossar": set()}   # glossar: S7.6 A2
STDLIB = {"array", "hashlib", "heapq", "json", "math", "operator", "re", "sqlite3", "unicodedata", "dataclasses", "typing", "contextlib", "sys"}
HARNESS_ERLAUBT = {"guppi_runtime.core.audit", "guppi_runtime.core.content_policy", "guppi_runtime.core.mission_lock", "guppi_runtime.jobs.testlab",
                   "guppi_runtime.desk.gated", "guppi_runtime.desk.actions", "guppi_runtime.orchestra.runner", "guppi_runtime.local_paths"}


def imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(a.name, 0) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            out.append((node.module or "", node.level))
    return out


def absolut(name, level, modul):
    if level == 0:
        return name
    basis = modul.split(".")[:-level]
    return ".".join(basis + ([name] if name else []))


class Grenze(unittest.TestCase):
    def test_reine_module_nur_standardbibliothek_und_feste_richtung(self):
        for name, erlaubt in REIN.items():
            for imp, level in imports(WISSEN / f"{name}.py"):
                ziel = absolut(imp, level, f"guppi_runtime.wissen.{name}")
                if ziel.startswith("guppi_runtime."):
                    self.assertIn(ziel, {f"guppi_runtime.wissen.{e}" for e in erlaubt}, f"{name} importiert {ziel}")
                else:
                    self.assertIn(ziel.split(".")[0], STDLIB, f"{name} importiert {ziel}")

    def test_harness_module_nur_erlaubte_teile(self):
        for path in sorted(WISSEN.glob("*.py")):
            if path.stem in REIN or path.stem == "__init__":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):                       # `from ..desk import gated` zählt als Import von desk.gated
                if isinstance(node, ast.ImportFrom) and node.level:
                    basis = absolut(node.module or "", node.level, f"guppi_runtime.wissen.{path.stem}")
                    for a in node.names:
                        ziel = basis + "." + a.name
                        if ziel.startswith("guppi_runtime.") and not ziel.startswith("guppi_runtime.wissen"):
                            self.assertTrue(ziel in HARNESS_ERLAUBT or ziel.rsplit(".", 1)[0] in HARNESS_ERLAUBT, f"{path.stem} importiert {ziel}")
            for imp, level in imports(path):
                ziel = absolut(imp, level, f"guppi_runtime.wissen.{path.stem}")
                if ziel.startswith("guppi_runtime.") and not ziel.startswith("guppi_runtime.wissen") and ziel not in ("guppi_runtime.desk", "guppi_runtime.core", "guppi_runtime.orchestra", "guppi_runtime.jobs"):
                    self.assertIn(ziel, HARNESS_ERLAUBT, f"{path.stem} importiert {ziel}")
                self.assertFalse(ziel.startswith(("numpy", "sqlite_vec")), ziel)

    def test_niemand_draussen_importiert_die_reinen_module(self):
        bad = []
        for path in sorted(SRC.rglob("*.py")):
            if path.is_relative_to(WISSEN):
                continue
            modul = ".".join(path.relative_to(SRC.parent).with_suffix("").parts)
            for imp, level in imports(path):
                ziel = absolut(imp, level, modul)
                if ziel.startswith("guppi_runtime.wissen.") and ziel.split(".")[-1] in REIN:
                    bad.append(f"{modul}: {ziel}")
        self.assertEqual(bad, [])

    def test_init_ist_leer_und_core_unberuehrt(self):
        self.assertEqual((WISSEN / "__init__.py").read_text(encoding="utf-8").strip(), "")
        for path in (SRC / "core").rglob("*.py"):
            self.assertNotIn("wissen", path.read_text(encoding="utf-8").lower().replace("arbeitsumfeld_wissen", ""), path.name)

    def test_migrationen_sind_die_saat(self):
        sys.path.insert(0, str(SRC.parents[1] / "benchmarks" / "wis_schema_seed"))
        try:
            import wis_ddl
        finally:
            sys.path.pop(0)
        from guppi_runtime.wissen import schema
        self.assertEqual(schema.MIGRATIONEN, wis_ddl.MIGRATIONEN)
        self.assertEqual(schema.SCHEMA_VERSION, len(wis_ddl.MIGRATIONEN))

    def test_jedes_modul_parst_mit_python_3_12_syntax(self):
        for path in sorted(WISSEN.glob("*.py")):
            ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 12))


if __name__ == "__main__":
    unittest.main()
