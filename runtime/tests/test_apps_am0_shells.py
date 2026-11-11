"""AM0-06 und AM0-07 (SPEC_APPS_v1_AM0_G2 §6, §7): eine fremde Shell ist nur eine Vorgabe – ohne eigenen Code und ohne eigenes CSS; die Gate-Texte
sagen, was für Werkzeug und Vorgabe-Shell wirklich gilt."""
import tempfile
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from test_desk_install import ARCH, CODE, module
from sedra_runtime.desk.gateway import check_shell

VORGABE = {"shell": {"id": "fremd-shell", "name": "Fremd", "version": "1.0.0", "trust": "COMMUNITY", "needs": {"ui": ">=1.0 <2"}, "vorgabe": "shell.vorgabe.yaml"}}
CODE_SHELL = {"shell": {"id": "fremd-shell", "name": "Fremd", "version": "1.0.0", "trust": "COMMUNITY", "needs": {"ui": ">=1.0 <2"}, "entry": {"js": "shell.js"},
                        "provides": ["strip", "talk"]}}


def shell_ordner(root, doc, dateien=()):
    folder = Path(root) / "fremd-shell"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "shell.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    for name in dateien:
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text("// x\n", encoding="utf-8")
    return folder


class Regeln(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am0-shells-")
        self.addCleanup(self.tmp.cleanup)

    def fehler(self, doc, dateien=(), origin="local"):
        return check_shell(doc, shell_ordner(self.tmp.name, doc, dateien), origin)[1]

    def test_code_shell_von_fremden_wird_abgewiesen(self):
        self.assertIn("community_shell_needs_vorgabe", self.fehler(CODE_SHELL, ["shell.js"]))
        self.assertIn("community_shell_no_entry", self.fehler(dict(shell=dict(CODE_SHELL["shell"], vorgabe="shell.vorgabe.yaml")), ["shell.js", "shell.vorgabe.yaml"]))

    def test_eigene_captain_shell_darf_code_haben(self):
        doc = {"shell": dict(CODE_SHELL["shell"], trust="CAPTAIN")}
        self.assertEqual(self.fehler(doc, ["shell.js"]), [])

    def test_fremde_vorgabe_mit_css_wird_abgewiesen(self):
        self.assertIn("community_shell_no_css", self.fehler(VORGABE, ["shell.vorgabe.yaml", "shell.css"]))

    def test_css_in_anderer_schreibweise_wird_abgewiesen(self):
        """Windows: `SHELL.CSS` ist dieselbe Datei wie `shell.css`; `_check_frame_shell` lädt sie als shell.css. Vor dem 11.11. kam sie am Verbot vorbei."""
        for name in ("SHELL.CSS", "Shell.css", "shell.CSS"):
            self.assertIn("community_shell_no_css", self.fehler(VORGABE, ["shell.vorgabe.yaml", name]), name)

    def test_css_in_einem_unterordner_zaehlt_nicht(self):
        self.assertNotIn("community_shell_no_css", self.fehler(VORGABE, ["shell.vorgabe.yaml", "sub/shell.css"]))


class Gate(unittest.TestCase):
    def setUp(self):
        from sedra_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix="am0-gate-")
        self.addCleanup(self.tmp.cleanup)
        self.hub = UIXHub(Path(self.tmp.name) / "project", ARCH)
        self.addCleanup(self.hub.close)

    def test_einbau_einer_code_shell_wird_vor_dem_gate_abgewiesen(self):
        quelle = Path(self.tmp.name) / "quelle" / "fremd-shell"
        quelle.mkdir(parents=True)
        (quelle / "shell.yaml").write_text(yaml.safe_dump(CODE_SHELL), encoding="utf-8")
        (quelle / "shell.js").write_text(CODE, encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            self.hub.install_request({"kind": "shell", "source": str(quelle)})
        self.assertIn("shell_einbau_nur_vorgabe", str(ctx.exception))
        self.assertEqual(self.hub.decisions_view()["summary"]["count"], 0)

    def test_gate_text_des_werkzeugs_nennt_rahmen_und_leserouten(self):
        quelle = module(Path(self.tmp.name) / "quelle" / "fremd", CODE)
        antwort = self.hub.install_request({"kind": "tool", "source": str(quelle)})
        risks = antwort["gate"]["request"]["risks"]
        self.assertEqual(risks[0], "läuft abgeschottet in einem eigenen Rahmen: ohne Token, ohne Netz, ohne Zugriff auf die Seite")
        self.assertEqual(risks[1], "nicht begrenzt: Rechenzeit und Speicher im Browser")
        self.assertEqual(risks[2], "Leserouten: /api/strip")
        self.assertIn("Leserouten: 1", antwort["binding"]["describe"])
        self.assertNotIn("nur Leserouten", antwort["binding"]["describe"])


if __name__ == "__main__":
    unittest.main()
