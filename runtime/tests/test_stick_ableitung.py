"""AM8-10 bis AM8-12 (SPEC_APPS_v1_AM8_VERZEICHNIS): Abhängigkeiten im Manifest (needs.apps, needs.kern, needs.dateien), Zeilenart `shell <id>` und `app <id>` in stick_paket.py,
Gegenprobe gegen die Liste. Wegwerf-Baum, nichts wird auf einen Stick geschrieben."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))

import stick_paket  # noqa: E402
import yaml  # noqa: E402

from host_isolation import setUpModule, tearDownModule  # noqa: F401,E402

from sedra_runtime.desk.gateway import _common  # noqa: E402

SRC = "runtime/src/sedra_runtime"
TOOLS = SRC + "/uix/tools"
SHELLS = SRC + "/uix/shells"


def tool(repo, tid, needs="", **felder):
    ordner = Path(repo, TOOLS, tid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "tool.js").write_text("// x\n", encoding="utf-8")
    zeilen = ["tool:", f"  id: {tid}", f"  name: {tid}", "  version: 1.0.0", "  kind: object", "  handles: [task]", "  entry: {js: tool.js}", "  trust: CORE",
              "  needs: {ui: \">=1.0 <2\"" + (", " + needs if needs else "") + "}"]
    zeilen += [f"  {k}: {v}" for k, v in felder.items()]
    (ordner / "tool.yaml").write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def shell(repo, sid, needs="", gruppen=(), zellen=(), grundfunktionen=""):
    ordner = Path(repo, SHELLS, sid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "shell.js").write_text("// x\n", encoding="utf-8")
    zeilen = ["shell:", f"  id: {sid}", f"  name: {sid}", "  version: 1.0.0", "  entry: {js: [shell.js]}", "  trust: CORE",
              "  needs: {ui: \">=1.0 <2\"" + (", " + needs if needs else "") + "}"]
    if grundfunktionen:
        zeilen.append("  grundfunktionen: {" + grundfunktionen + "}")
    (ordner / "shell.yaml").write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    if gruppen:
        (ordner / "start_gruppen.json").write_text(json.dumps({"zuordnung": {g: "arbeit" for g in gruppen}}), encoding="utf-8")
    if zellen:
        (ordner / "leiste.json").write_text(json.dumps({"zellen": list(zellen)}), encoding="utf-8")


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo, self.best, self.ziel = (Path(self.tmp.name, n) for n in ("repo", "best", "stick"))
        for t in (self.repo, self.best):
            t.mkdir()
        (self.repo / SRC).mkdir(parents=True)
        (self.repo / SRC / "__init__.py").write_text("", encoding="utf-8")
        for kern in ("fisch", "sprache"):
            (self.repo / SRC / kern).mkdir()
            (self.repo / SRC / kern / "__init__.py").write_text("", encoding="utf-8")
        for pfad in ("uix/js/a.js", "uix/ui/b.js", "uix/css/c.css"):
            (self.repo / SRC / pfad).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / SRC / pfad).write_text("//\n", encoding="utf-8")
        tool(self.repo, "basis")
        tool(self.repo, "ober", needs='apps: {basis: ">=1.0"}, kern: [fisch], dateien: [js/a.js, css/]')
        tool(self.repo, "slotapp")
        tool(self.repo, "gruppenapp")
        tool(self.repo, "zelle-a")
        tool(self.repo, "fremd")
        shell(self.repo, "meine", needs="kern: [sprache], dateien: [ui/]", gruppen=["gruppenapp", "ort-ohne-werkzeug"], zellen=["zelle-a"], grundfunktionen="gespraech: slot:slotapp, logbuch: ort")
        self.liste = Path(self.tmp.name, "liste.txt")

    def rel(self, ableitung):
        return sorted(ableitung)

    def main(self, *args, liste=None):
        if liste is not None:
            self.liste.write_text(liste, encoding="utf-8")
        with redirect_stdout(io.StringIO()) as aus:
            code = stick_paket.main(["--repo", str(self.repo), "--bestand", str(self.best), "--ziel", str(self.ziel), "--liste", str(self.liste), *args])
        return code, aus.getvalue()


class Ableitung(Basis):
    def test_liste_liest_shell_und_app(self):
        self.liste.write_text("shell meine\napp ober\n", encoding="utf-8")
        self.assertEqual(stick_paket.liste(self.liste), [("shell", "meine", "meine"), ("app", "ober", "ober")])
        self.liste.write_text("app\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            stick_paket.liste(self.liste)

    def test_app_zieht_apps_kern_und_dateien(self):
        erg = stick_paket.ableitung(self.repo, "app", "ober")
        self.assertEqual(sorted(erg), sorted([f"{TOOLS}/ober/", f"{TOOLS}/basis/", f"{SRC}/fisch/", f"{SRC}/uix/js/a.js", f"{SRC}/uix/css/"]))
        self.assertEqual(erg[f"{TOOLS}/basis/"], "needs.apps von ober")

    def test_shell_zieht_slot_gruppen_taskleiste_und_eigene_needs(self):
        erg = stick_paket.ableitung(self.repo, "shell", "meine")
        for pfad in (f"{SHELLS}/meine/", f"{TOOLS}/slotapp/", f"{TOOLS}/gruppenapp/", f"{TOOLS}/zelle-a/", f"{SRC}/sprache/", f"{SRC}/uix/ui/"):
            self.assertIn(pfad, erg)
        self.assertNotIn(f"{TOOLS}/fremd/", erg, "was kein Manifest nennt, kommt nicht dazu")
        self.assertNotIn(f"{TOOLS}/ort-ohne-werkzeug/", erg, "eine Gruppen-ID ohne Werkzeug wird übergangen")

    def test_grundfunktion_gehoert_immer_zur_shell(self):
        tool(self.repo, "logbuch-app", grundfunktion="logbuch")
        self.assertIn(f"{TOOLS}/logbuch-app/", stick_paket.ableitung(self.repo, "shell", "meine"))

    def test_zyklus_haengt_nicht(self):
        tool(self.repo, "a1", needs='apps: {a2: ">=1.0"}')
        tool(self.repo, "a2", needs='apps: {a1: ">=1.0"}')
        self.assertEqual(sorted(stick_paket.ableitung(self.repo, "app", "a1")), [f"{TOOLS}/a1/", f"{TOOLS}/a2/"])

    def test_plan_kopiert_die_abgeleiteten_dateien(self):
        paare = stick_paket.plan(stick_paket.liste(self._liste("app ober\n")), self.repo, self.best)
        for pfad in (f"{TOOLS}/ober/tool.yaml", f"{TOOLS}/basis/tool.js", f"{SRC}/fisch/__init__.py", f"{SRC}/uix/js/a.js", f"{SRC}/uix/css/c.css"):
            self.assertIn(pfad, paare)
        self.assertNotIn(f"{TOOLS}/fremd/tool.yaml", paare)

    def _liste(self, text):
        self.liste.write_text(text, encoding="utf-8")
        return self.liste


class Pruefen(Basis):
    def test_vollstaendig_ist_leer(self):
        self.assertEqual(stick_paket.pruefen_ableitung(self.repo, stick_paket.liste(self._l("shell meine\napp ober\n"))), [])
        self.assertEqual(self.main("--pruefen")[0], 0)

    def test_fehlendes_kern_paket_und_fehlende_datei_werden_gemeldet(self):
        tool(self.repo, "kaputt", needs='apps: {gibtsnicht: ">=1.0"}, kern: [nirgends], dateien: [js/weg.js]')
        fehlt = stick_paket.pruefen_ableitung(self.repo, stick_paket.liste(self._l("app kaputt\n")))
        self.assertIn(f"fehlt: {TOOLS}/gibtsnicht/ (needs.apps von kaputt)", fehlt)
        self.assertIn(f"fehlt: {SRC}/nirgends/ (needs.kern von kaputt)", fehlt)
        self.assertIn(f"fehlt: {SRC}/uix/js/weg.js (needs.dateien von kaputt)", fehlt)

    def test_pruefen_gibt_fehlercode_und_kopieren_bricht_ab(self):
        tool(self.repo, "kaputt", needs="kern: [nirgends]")
        code, aus = self.main("--pruefen", liste="app kaputt\n")
        self.assertEqual(code, 1)
        self.assertIn("fehlt:", aus)
        code, aus = self.main()
        self.assertEqual(code, 1)
        self.assertIn("Abbruch", aus)
        self.assertFalse(self.ziel.exists(), "vor dem Kopieren abgebrochen")

    def test_kopieren_und_manifest(self):
        self.assertEqual(self.main(liste="app ober\nmodul sedra_runtime\n")[0], 0)
        daten = json.loads((self.ziel / "STICK_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertIn(f"{TOOLS}/basis/tool.yaml", [d["pfad"] for d in daten["dateien"]])
        self.assertNotIn("profil", daten)

    def _l(self, text):
        self.liste.write_text(text, encoding="utf-8")
        return self.liste


class Gegenprobe(Basis):
    def test_gegenprobe_nennt_nur_was_die_manifeste_nicht_decken(self):
        liste = f"repo {TOOLS}/ober/\nrepo {TOOLS}/fremd/\nrepo {SRC}/fisch/\nrepo {SRC}/sprache/\nrepo {SRC}/uix/shells/meine/\nrepo START.bat\nmodul sedra_runtime\nshell meine\napp ober\n"
        self.liste.write_text(liste, encoding="utf-8")
        befund = stick_paket.gegenprobe(self.repo, stick_paket.liste(self.liste))
        self.assertEqual(befund, [f"nur in der Liste: {TOOLS}/fremd/"], "Befund, kein stilles Angleichen; Dateien ausserhalb der Ordner zählen nicht")

    def test_gegenprobe_ohne_zeilen_nimmt_die_harness(self):
        shell(self.repo, "harness", needs="kern: [fisch]")
        self.liste.write_text(f"repo {SRC}/fisch/\nrepo {SRC}/sprache/\n", encoding="utf-8")
        self.assertEqual(stick_paket.gegenprobe(self.repo, stick_paket.liste(self.liste)), [f"nur in der Liste: {SRC}/sprache/"])

    def test_gegenprobe_per_aufruf_aendert_nichts(self):
        code, aus = self.main("--gegenprobe", liste=f"repo {TOOLS}/fremd/\nshell meine\n")
        self.assertEqual(code, 0)
        self.assertIn("1 Zeilen", aus)
        self.assertFalse(self.ziel.exists())

    def test_echtes_repo_die_harness_deckt_kern_und_dateien_der_liste(self):
        repo = Path(__file__).resolve().parents[2]
        befund = stick_paket.gegenprobe(repo, stick_paket.liste(Path(stick_paket.HERE, "stick_liste.txt")))
        for kern in ("core", "harness", "fisch", "sprache"):
            self.assertNotIn(f"nur in der Liste: {SRC}/{kern}/", befund)
        for pfad in ("ui", "js", "css"):
            self.assertNotIn(f"nur in der Liste: {SRC}/uix/{pfad}/", befund)


class Schema(unittest.TestCase):
    """AM8-10: needs.kern und needs.dateien sind Listen aus Namen; alle Manifeste des Pakets erfüllen das und nennen nur, was es gibt."""

    def test_gateway_prueft_die_felder(self):
        for needs, fehler in (({"kern": "core"}, "needs_kern_invalid"), ({"dateien": ["../x"]}, "needs_dateien_invalid"), ({"kern": [1]}, "needs_kern_invalid"),
                              ({"dateien": ["C:/x"]}, "needs_dateien_invalid"), ({"kern": ["core"], "dateien": ["ui/", "js/a.js"]}, None)):
            doc = {"id": "x", "name": "X", "version": "1.0.0", "trust": "CORE", "needs": {"ui": ">=1.0 <2", **needs}, "entry": {"js": ["x.js"]}}
            fehlerliste = []
            _common(doc, "shell", Path("x"), "package", fehlerliste)
            if fehler:
                self.assertIn(fehler, fehlerliste, needs)
            else:
                self.assertNotIn("needs_kern_invalid", fehlerliste)
                self.assertNotIn("needs_dateien_invalid", fehlerliste)

    def test_alle_manifeste_im_paket(self):
        repo = Path(__file__).resolve().parents[2]
        src = repo / SRC
        manifeste = [(d, yaml.safe_load((d / "tool.yaml").read_text(encoding="utf-8"))["tool"]) for d in sorted((src / "uix/tools").glob("*/")) if (d / "tool.yaml").is_file()]
        manifeste += [(d, yaml.safe_load((d / "shell.yaml").read_text(encoding="utf-8"))["shell"]) for d in sorted((src / "uix/shells").glob("*/")) if (d / "shell.yaml").is_file()]
        self.assertGreater(len(manifeste), 40)
        for ordner, man in manifeste:
            n = man.get("needs") or {}
            self.assertIsInstance(n, dict, ordner)
            for k in n.get("kern") or []:
                self.assertTrue((src / k).is_dir(), f"{ordner.name}: needs.kern {k} fehlt")
            for d in n.get("dateien") or []:
                self.assertTrue((src / "uix" / d).exists(), f"{ordner.name}: needs.dateien {d} fehlt")
            for dep in n.get("apps") or {}:
                self.assertTrue((src / "uix/tools" / dep).is_dir(), f"{ordner.name}: needs.apps {dep} fehlt")


if __name__ == "__main__":
    unittest.main()
