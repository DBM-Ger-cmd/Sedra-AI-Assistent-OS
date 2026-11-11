"""O3 G7-03/G7-04: die Konsole `CODE_STAND.bat <projekt> --oberflaeche | --uebernehmen-oberflaeche | --zuruecksetzen | --zuruecknehmen U-…` – ohne Oberfläche, dieselbe Ablage und dieselbe Audit-Kette,
Audit mit `kanal: konsole`. Wegwerf-Projekt, der uix-Ordner kommt als Parameter."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.harness import code_stand
from sedra_runtime.harness import projekte as harness_projekte
from sedra_runtime.harness.code_stand import CodeStand, konsole_oberflaeche
from sedra_runtime.harness.oberflaeche import Oberflaeche, sha


class Konsole(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.root = t / "sedra"
        (self.root / "runtime_data" / "harness").mkdir(parents=True)
        (self.root / "runtime_data" / "audit").mkdir(parents=True)
        self.wurzel = t / "repo"
        self.uix = self.wurzel / "runtime" / "src" / "pkg" / "uix"
        (self.uix / "tools").mkdir(parents=True)
        self.datei = self.uix / "tools" / "a.js"
        self.datei.write_bytes(b"alt\n")
        self.projekt = {"id": "p", "name": "P", "wurzel": str(self.wurzel.resolve()), "schreibbereich": ["**"]}
        patcher = mock.patch.object(harness_projekte, "laden", return_value=[self.projekt])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ob = Oberflaeche(self.root / "runtime_data" / "harness" / "oberflaeche", self.uix)
        self.ob.zurueckhalten(self.datei, "S-1", "T-1")
        self.datei.write_bytes(b"neu\nfetch(x)\n")

    def ruf(self, art, u=None):
        return konsole_oberflaeche(self.root, "p", art, u, uix=self.uix)

    def audit(self):
        pfad = self.root / "runtime_data" / "audit" / "events.jsonl"
        return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()] if pfad.is_file() else []

    def test_zeigen_nennt_dateien_diff_hinweise_und_uebernahmen(self):
        code, text = self.ruf("zeigen")
        self.assertEqual(code, 0)
        self.assertIn("Zurückgehalten: 1 Datei", text)
        self.assertIn("geändert tools/a.js · Sitzung S-1", text)
        self.assertIn("-alt", text)
        self.assertIn("⚠", text)
        self.assertIn("Keine Übernahme zum Zurücknehmen", text)

    def test_uebernehmen_schreibt_audit_mit_kanal_konsole_und_setzt_code_gesehen(self):
        cs = CodeStand(self.root / "runtime_data" / "harness" / "code_stand", self.projekt["wurzel"], "p")
        cs.erfassen()
        code, text = self.ruf("uebernehmen")
        antwort = json.loads(text)
        self.assertEqual((code, antwort["status"], antwort["anzahl"], antwort["veraltet"]), (0, "uebernommen", 1, []))
        self.assertEqual(Oberflaeche(self.ob.ablage, self.uix).stand()["dateien"], {})
        e = [x for x in self.audit() if x["event_type"] == "HARNESS_OBERFLAECHE_UEBERNOMMEN"]
        self.assertEqual(e[-1]["payload"]["kanal"], "konsole")
        stand = CodeStand(self.root / "runtime_data" / "harness" / "code_stand", self.projekt["wurzel"], "p").stand()["gesehen"]
        self.assertEqual(stand["runtime/src/pkg/uix/tools/a.js"], sha(b"neu\nfetch(x)\n"), "G2-07: Code-Dateien gelten als gesehen")

    def test_zuruecksetzen(self):
        code, text = self.ruf("zuruecksetzen")
        antwort = json.loads(text)
        self.assertEqual((code, antwort["status"], antwort["hergestellt"]), (0, "zurueckgesetzt", ["tools/a.js"]))
        self.assertEqual(self.datei.read_bytes(), b"alt\n")
        self.assertEqual([x for x in self.audit() if x["event_type"] == "HARNESS_OBERFLAECHE_ZURUECKGESETZT"][-1]["payload"]["kanal"], "konsole")

    def test_zuruecknehmen_und_unbekannte_uebernahme(self):
        u = json.loads(self.ruf("uebernehmen")[1])["u"]
        code, text = self.ruf("zuruecknehmen", u)
        antwort = json.loads(text)
        self.assertEqual((code, antwort["status"], antwort["hergestellt"]), (0, "zurueckgenommen", ["tools/a.js"]))
        self.assertEqual(self.datei.read_bytes(), b"alt\n")
        e = [x for x in self.audit() if x["event_type"] == "HARNESS_OBERFLAECHE_ZURUECK"][-1]["payload"]
        self.assertEqual((e["u"], e["kanal"]), (u, "konsole"))
        code, text = self.ruf("zuruecknehmen", "U-gibt-es-nicht")
        self.assertEqual(code, 2)
        self.assertIn("uebernahme_unbekannt", text)

    def test_zuruecknehmen_nennt_seit_der_uebernahme_geaenderte_dateien(self):
        u = json.loads(self.ruf("uebernehmen")[1])["u"]
        self.datei.write_bytes(b"danach geaendert\n")
        antwort = json.loads(self.ruf("zuruecknehmen", u)[1])
        self.assertEqual(antwort["seit_der_uebernahme_geaendert"], ["tools/a.js"])
        self.assertEqual(self.datei.read_bytes(), b"danach geaendert\n")

    def test_falscher_root_und_unbekanntes_projekt(self):
        self.assertEqual(konsole_oberflaeche(Path(self.tmp.name) / "leer", "p", "zeigen")[0], 2)
        self.assertEqual(konsole_oberflaeche(self.root, "gibt-es-nicht", "zeigen")[0], 2)

    def test_main_kennt_die_neuen_schalter(self):
        for argv in (["--root", str(self.root / "gibt-es-nicht"), "p", "--oberflaeche"], ["--root", str(self.root / "x"), "p", "--zuruecknehmen", "U-1"]):
            with redirect_stdout(io.StringIO()) as aus:
                self.assertEqual(code_stand.main(argv), 2)
            self.assertIn("refused", aus.getvalue())


if __name__ == "__main__":
    unittest.main()
