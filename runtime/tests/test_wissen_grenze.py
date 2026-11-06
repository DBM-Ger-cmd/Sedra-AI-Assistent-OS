"""Die Importgrenze des Pakets `wissen/` (Spec 7, D7.1): reine Module importieren nur die Standardbibliothek und einander in
fester Richtung; Harness-Module nur die erlaubten Teile von `sedra_runtime`; niemand außerhalb von `wissen/` importiert die reinen
Module; `core/` bleibt unberührt. Dazu: die Migrationen im Paket sind die Saat der Bau-Spec, Python 3.12 parst jedes Modul."""
import ast
import sys
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

SRC = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime"
WISSEN = SRC / "wissen"
REIN = {"schema": set(), "zerlegen": set(), "vektor": set(), "fusion": set(), "ausgabe": {"zerlegen"}, "glossar": set()}   # glossar: S7.6 A2
STDLIB = {"array", "hashlib", "heapq", "json", "math", "operator", "re", "sqlite3", "unicodedata", "dataclasses", "typing", "contextlib", "sys"}
HARNESS_ERLAUBT = {"sedra_runtime.core.audit", "sedra_runtime.core.content_policy", "sedra_runtime.core.mission_lock", "sedra_runtime.jobs.testlab",
                   "sedra_runtime.desk.gated", "sedra_runtime.desk.actions", "sedra_runtime.orchestra.runner", "sedra_runtime.local_paths"}


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
                ziel = absolut(imp, level, f"sedra_runtime.wissen.{name}")
                if ziel.startswith("sedra_runtime."):
                    self.assertIn(ziel, {f"sedra_runtime.wissen.{e}" for e in erlaubt}, f"{name} importiert {ziel}")
                else:
                    self.assertIn(ziel.split(".")[0], STDLIB, f"{name} importiert {ziel}")

    def test_harness_module_nur_erlaubte_teile(self):
        for path in sorted(WISSEN.glob("*.py")):
            if path.stem in REIN or path.stem == "__init__":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):                       # `from ..desk import gated` zählt als Import von desk.gated
                if isinstance(node, ast.ImportFrom) and node.level:
                    basis = absolut(node.module or "", node.level, f"sedra_runtime.wissen.{path.stem}")
                    for a in node.names:
                        ziel = basis + "." + a.name
                        if ziel.startswith("sedra_runtime.") and not ziel.startswith("sedra_runtime.wissen"):
                            self.assertTrue(ziel in HARNESS_ERLAUBT or ziel.rsplit(".", 1)[0] in HARNESS_ERLAUBT, f"{path.stem} importiert {ziel}")
            for imp, level in imports(path):
                ziel = absolut(imp, level, f"sedra_runtime.wissen.{path.stem}")
                if ziel.startswith("sedra_runtime.") and not ziel.startswith("sedra_runtime.wissen") and ziel not in ("sedra_runtime.desk", "sedra_runtime.core", "sedra_runtime.orchestra", "sedra_runtime.jobs"):
                    self.assertIn(ziel, HARNESS_ERLAUBT, f"{path.stem} importiert {ziel}")
                if path.stem == "vektor_np" and ziel == "numpy":
                    continue                                      # K5-6 (G2 K5 D-K5-2 Weg A): nur hier, nur bei Bedarf geladen (Test unten)
                self.assertFalse(ziel.startswith(("numpy", "sqlite_vec")), f"{path.stem} importiert {ziel}")

    def test_numpy_nur_in_vektor_np_und_nicht_beim_laden(self):
        tree = ast.parse((WISSEN / "vektor_np.py").read_text(encoding="utf-8"))
        oben = [a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names]
        oben += [n.module for n in tree.body if isinstance(n, ast.ImportFrom)]
        self.assertNotIn("numpy", oben, "numpy wird erst geladen, wenn die Matrix gebraucht wird; ohne numpy läuft alles weiter")

    def test_niemand_draussen_importiert_die_reinen_module(self):
        bad = []
        for path in sorted(SRC.rglob("*.py")):
            if path.is_relative_to(WISSEN):
                continue
            modul = ".".join(path.relative_to(SRC.parent).with_suffix("").parts)
            for imp, level in imports(path):
                ziel = absolut(imp, level, modul)
                if ziel.startswith("sedra_runtime.wissen.") and ziel.split(".")[-1] in REIN:
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
        from sedra_runtime.wissen import schema
        self.assertEqual(schema.MIGRATIONEN, wis_ddl.MIGRATIONEN)
        self.assertEqual(schema.SCHEMA_VERSION, len(wis_ddl.MIGRATIONEN))

    def test_jedes_modul_parst_mit_python_3_12_syntax(self):
        for path in sorted(WISSEN.glob("*.py")):
            ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 12))


if __name__ == "__main__":
    unittest.main()
