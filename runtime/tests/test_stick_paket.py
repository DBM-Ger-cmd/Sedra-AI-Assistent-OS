import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))

import stick_paket  # noqa: E402


def _schreibe(wurzel, rel, text=""):
    pfad = Path(wurzel, rel)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(text, encoding="utf-8")
    return pfad


class StickPaketTests(unittest.TestCase):
    """Stick-Paket: Importhuelle folgt statischen Importen, Liste wird gelesen, Kopie ohne Verknuepfungen mit Manifest."""

    def _baum(self, tmp):
        src = Path(tmp, "runtime", "src")
        _schreibe(src, "sedra_runtime/__init__.py")
        _schreibe(src, "sedra_runtime/a/__init__.py")
        _schreibe(src, "sedra_runtime/a/haupt.py", "from . import hilfe\nfrom ..b import ziel\n")
        _schreibe(src, "sedra_runtime/a/hilfe.py", "import sedra_runtime.c.tief\n")
        _schreibe(src, "sedra_runtime/b/__init__.py", "def ziel(): pass\n")
        _schreibe(src, "sedra_runtime/c/tief.py", "x = 1\n")
        _schreibe(src, "sedra_runtime/unbenutzt.py", "import os\n")
        return src

    def test_closure_follows_absolute_and_relative_imports_and_parent_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = self._baum(tmp)
            rel = {str(p.relative_to(src)).replace("\\", "/") for p in stick_paket.closure(src, ["sedra_runtime.a.haupt"])}
            self.assertEqual(rel, {
                "sedra_runtime/__init__.py",
                "sedra_runtime/a/__init__.py",
                "sedra_runtime/a/haupt.py",
                "sedra_runtime/a/hilfe.py",
                "sedra_runtime/b/__init__.py",
                "sedra_runtime/c/tief.py",
            })

    def test_a_missing_module_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = self._baum(tmp)
            with self.assertRaises(FileNotFoundError):
                stick_paket.closure(src, ["sedra_runtime.gibt_es_nicht"])

    def test_list_reads_the_three_kinds_and_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            liste = Path(tmp, "l.txt")
            liste.write_text("# kommentar\n\nrepo A/\nbestand B -> C/\nmodul sedra_runtime.x\n", encoding="utf-8")
            self.assertEqual(stick_paket.liste(liste), [("repo", "A/", "A/"), ("bestand", "B", "C/"), ("modul", "sedra_runtime.x", "sedra_runtime.x")])
            liste.write_text("unbekannt X\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                stick_paket.liste(liste)

    def test_copy_and_manifest_without_reparse_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, bestand, ziel = Path(tmp, "repo"), Path(tmp, "best"), Path(tmp, "stick")
            self._baum(repo)
            _schreibe(repo, "START_SEDRA.bat", "@echo off\n")
            _schreibe(bestand, "engines/llama.cpp/b11160/llama.dll", "dll")
            liste = Path(tmp, "l.txt")
            liste.write_text("repo START_SEDRA.bat\nbestand engines/llama.cpp/b11160/ -> engines/llama.cpp/b11160/\nmodul sedra_runtime.a.haupt\n", encoding="utf-8")
            paare = stick_paket.plan(stick_paket.liste(liste), repo, bestand)
            self.assertIn("START_SEDRA.bat", paare)
            self.assertIn("engines/llama.cpp/b11160/llama.dll", paare)
            self.assertIn("runtime/src/sedra_runtime/a/hilfe.py", paare)
            rel = stick_paket.kopieren(paare, ziel)
            daten = stick_paket.manifest(ziel, rel, "test")
            geschrieben = json.loads(Path(ziel, "STICK_MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(geschrieben, daten)
            self.assertEqual(len(geschrieben["dateien"]), len(paare))
            self.assertTrue(all(len(d["sha256"]) == 64 for d in geschrieben["dateien"]))
            self.assertFalse(any("__pycache__" in d["pfad"] for d in geschrieben["dateien"]))


if __name__ == "__main__":
    unittest.main()
