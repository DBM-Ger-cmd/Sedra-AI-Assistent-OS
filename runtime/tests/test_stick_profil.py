"""A9 (SPEC_STICK_AUS_PROFIL_v1 ST-01, ST-04, ST-05): der Stick wird aus dem Profil „stick“ gebaut – Werkzeuge mit `profile:`, Grundfunktionen und Instrumente der Taskleiste;
`--pruefen` meldet, was fehlt; das Manifest nennt Profil, Apps und Grundfunktionen. Wegwerf-Baum, nichts wird auf einen Stick geschrieben."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))

import stick_paket  # noqa: E402

TOOLS = "runtime/src/sedra_runtime/uix/tools"


def tool(repo, tid, **felder):
    ordner = Path(repo, TOOLS, tid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "tool.js").write_text("// x\n", encoding="utf-8")
    zeilen = ["tool:", f"  id: {tid}", f"  name: {tid}", "  version: 1.0.0", "  kind: object", "  handles: [task]", "  entry: {js: tool.js}", "  trust: CORE", '  needs: {ui: ">=1.0 <2"}']
    for k, v in felder.items():
        zeilen.append(f"  {k}: {v}")
    (ordner / "tool.yaml").write_text("\n".join(zeilen) + "\n", encoding="utf-8")


class Profil(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo, self.best, self.ziel = (Path(self.tmp.name, n) for n in ("repo", "best", "stick"))
        for t in (self.repo, self.best):
            t.mkdir()
        Path(self.repo, "runtime/src/sedra_runtime").mkdir(parents=True)
        Path(self.repo, "runtime/src/sedra_runtime/__init__.py").write_text("", encoding="utf-8")
        tool(self.repo, "profil-app", profile="[stick, privat]")
        tool(self.repo, "grund-app", grundfunktion="logbuch")
        tool(self.repo, "andere-app", profile="[privat]")
        tool(self.repo, "ohne-app")
        tool(self.repo, "gauge-a")
        leiste = Path(self.repo, "runtime/src/sedra_runtime/uix/shells/harness/leiste.json")
        leiste.parent.mkdir(parents=True)
        leiste.write_text(json.dumps({"zellen": ["gauge-a"]}), encoding="utf-8")
        self.liste = Path(self.tmp.name, "liste.txt")
        self.liste.write_text("profil stick\nmodul sedra_runtime\n", encoding="utf-8")

    def ids(self, paare):
        return sorted({Path(k).parts[5] for k in paare if k.startswith(TOOLS + "/")})

    def test_liste_liest_profil(self):
        self.assertEqual(stick_paket.liste(self.liste)[0], ("profil", "stick", "stick"))
        self.liste.write_text("profil\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            stick_paket.liste(self.liste)

    def test_plan_nimmt_genau_profil_grundfunktion_und_taskleiste(self):
        paare = stick_paket.plan(stick_paket.liste(self.liste), self.repo, self.best)
        self.assertEqual(self.ids(paare), ["gauge-a", "grund-app", "profil-app"], "ST-01: nicht andere-app, nicht ohne-app")
        self.assertIn(f"{TOOLS}/profil-app/tool.yaml", paare)
        self.assertEqual(stick_paket.profil_werkzeuge(self.repo, "stick"),
                         {"gauge-a": "Zelle der Taskleiste", "grund-app": "Grundfunktion logbuch", "profil-app": "profile: [stick]"})
        self.assertEqual(stick_paket.profil_werkzeuge(self.repo, "privat")["andere-app"], "profile: [privat]")

    def test_vollstaendig(self):
        eintraege = stick_paket.liste(self.liste)
        paare = stick_paket.plan(eintraege, self.repo, self.best)
        self.assertEqual(stick_paket.pruefen_vollstaendig(self.repo, "stick", paare), [])

    def test_fehlende_zelle_und_fehlende_abhaengigkeit_werden_gemeldet(self):
        leiste = Path(self.repo, "runtime/src/sedra_runtime/uix/shells/harness/leiste.json")
        leiste.write_text(json.dumps({"zellen": ["gauge-a", "gauge-weg"]}), encoding="utf-8")
        tool(self.repo, "braucht-was", profile="[stick]", needs='{ui: ">=1.0 <2", apps: {basis-app: ">=1.0"}}')
        paare = stick_paket.plan(stick_paket.liste(self.liste), self.repo, self.best)
        fehlt = stick_paket.pruefen_vollstaendig(self.repo, "stick", paare)
        self.assertIn("fehlt: Werkzeug gauge-weg (Zelle der Taskleiste) – kein Ordner uix/tools/gauge-weg/", fehlt)
        self.assertIn("fehlt: basis-app (braucht braucht-was)", fehlt)

    def test_pruefen_gibt_einen_fehlercode_und_bricht_vor_dem_kopieren_ab(self):
        Path(self.repo, "runtime/src/sedra_runtime/uix/shells/harness/leiste.json").write_text(json.dumps({"zellen": ["gauge-weg"]}), encoding="utf-8")
        with redirect_stdout(io.StringIO()) as aus:
            code = stick_paket.main(["--repo", str(self.repo), "--bestand", str(self.best), "--ziel", str(self.ziel), "--liste", str(self.liste), "--pruefen"])
        self.assertEqual(code, 1)
        self.assertIn("fehlt: Werkzeug gauge-weg", aus.getvalue())
        with redirect_stdout(io.StringIO()) as aus:
            code = stick_paket.main(["--repo", str(self.repo), "--bestand", str(self.best), "--ziel", str(self.ziel), "--liste", str(self.liste)])
        self.assertEqual(code, 1)
        self.assertIn("Abbruch", aus.getvalue())
        self.assertFalse(self.ziel.exists(), "es wurde nichts kopiert")

    def test_kopie_und_manifest_mit_profil(self):
        with redirect_stdout(io.StringIO()):
            code = stick_paket.main(["--repo", str(self.repo), "--bestand", str(self.best), "--ziel", str(self.ziel), "--liste", str(self.liste)])
        self.assertEqual(code, 0)
        m = json.loads(Path(self.ziel, "STICK_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(m["profil"], {"art": "stick", "apps": ["gauge-a", "grund-app", "profil-app"], "grundfunktionen": ["logbuch"]})
        self.assertTrue(all(len(d["sha256"]) == 64 for d in m["dateien"]))
        self.assertFalse(Path(self.ziel, TOOLS, "ohne-app").exists())

    def test_ohne_profilzeile_bleibt_alles_wie_vorher(self):
        self.liste.write_text("modul sedra_runtime\n", encoding="utf-8")
        eintraege = stick_paket.liste(self.liste)
        self.assertIsNone(stick_paket.profil_info(eintraege, self.repo))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(stick_paket.main(["--repo", str(self.repo), "--bestand", str(self.best), "--ziel", str(self.ziel), "--liste", str(self.liste)]), 0)
        self.assertNotIn("profil", json.loads(Path(self.ziel, "STICK_MANIFEST.json").read_text(encoding="utf-8")))

    def test_echtes_repo_die_grundfunktionen_sind_im_profil(self):
        repo = Path(__file__).resolve().parents[2]
        werkzeuge = stick_paket.profil_werkzeuge(repo, "stick")
        for tid in ("decisions", "talk", "task", "logbook", "boundaries", "modules", "system"):
            self.assertIn(tid, werkzeuge, "AM2-13: die sieben Grundfunktionen gehören immer dazu")
        for zelle in stick_paket.taskleisten_zellen(repo):
            self.assertTrue(Path(repo, TOOLS, zelle).is_dir(), zelle)


if __name__ == "__main__":
    unittest.main()
