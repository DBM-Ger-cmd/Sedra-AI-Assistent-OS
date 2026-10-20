"""PIPE-09 (20.10.2026): Ein Ort, von dem aus gebaut wird.

Gebaut wird aus dem Arbeitsstand (Git). Die Laufzeit-Installation (<guppi>) muss dieselbe Engine und dieselbe llama_server.yaml haben, sonst
baut der eine Ort mit einer anderen Engine als der andere (Build 24: still b11371 statt b11160, der GPU-Canary scheiterte).
Die Laufzeit-Installation kommt aus dem Platzhalter <guppi> (runtime/config/local_paths.yaml, nicht im Git); fehlt der Eintrag, wird der
Nachbarordner "GUPPI_Runtime_v1.20" neben dem Arbeitsstand versucht. Findet sich keine, wird übersprungen."""
import sys
import unittest
from pathlib import Path

import yaml

import env_skip
from guppi_runtime import local_paths

ARBEITSSTAND = env_skip.RUNTIME.parent
NACHBAR = "GUPPI_Runtime_v1.20"

# Freigegebene Engine-Versionen. Änderung nur mit Captain-Gate.
FREIGEGEBEN = ("b11160",)


def finde_laufzeit():
    kandidaten = []
    wert = local_paths.expand("<guppi>")
    if not local_paths.unresolved(wert):
        kandidaten.append(Path(wert))
    kandidaten.append(ARBEITSSTAND.parent / NACHBAR)
    for ordner in kandidaten:
        if (ordner / "runtime" / "config" / "llama_server.yaml").is_file() and ordner.resolve() != ARBEITSSTAND.resolve():
            return ordner
    return None


LAUFZEIT = finde_laufzeit()


def lade(ordner):
    return yaml.safe_load((ordner / "runtime" / "config" / "llama_server.yaml").read_text(encoding="utf-8"))["llama_server"]


@unittest.skipIf(LAUFZEIT is None, "Laufzeit-Installation (<guppi> oder Nachbarordner GUPPI_Runtime_v1.20) auf diesem PC nicht gefunden")
class BauOrtTest(unittest.TestCase):
    def setUp(self):
        self.a = lade(ARBEITSSTAND)
        self.l = lade(LAUFZEIT)

    def test_llama_server_yaml_gleich(self):
        for schluessel in ("engine_source", "engine_build"):
            self.assertEqual(self.a[schluessel], self.l[schluessel], schluessel)
        for schluessel in ("engine_build", "gguf"):
            self.assertEqual(self.a["canary"][schluessel], self.l["canary"][schluessel], "canary." + schluessel)
        self.assertEqual(self.a, self.l)  # ganzer Inhalt; Zeilenenden und Kommentare zählen nicht

    def test_engine_ordner_vorhanden(self):
        build = self.l["engine_build"]
        ziel = Path("engines") / "llama.cpp" / build
        self.assertTrue((LAUFZEIT / ziel).is_dir(), f"Laufzeit-Installation: {ziel} fehlt")
        if not (ARBEITSSTAND / "engines").is_dir():
            self.skipTest("dieser Arbeitsstand ist ein Git-Worktree ohne engines/ (nicht im Git); geprüft wurde nur die Laufzeit-Installation")
        self.assertTrue((ARBEITSSTAND / ziel).is_dir(), f"Arbeitsstand: {ziel} fehlt")

    def test_engine_build_freigegeben(self):
        for name, cfg in (("Arbeitsstand", self.a), ("Laufzeit", self.l)):
            self.assertIn(cfg["engine_build"], FREIGEGEBEN, f"{name}: engine_build nicht freigegeben (Änderung nur mit Captain-Gate)")
            self.assertIn(cfg["canary"]["engine_build"], FREIGEGEBEN, f"{name}: canary.engine_build nicht freigegeben (Änderung nur mit Captain-Gate)")


if __name__ == "__main__":
    unittest.main()
