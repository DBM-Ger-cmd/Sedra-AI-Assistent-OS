"""AM2-07 bis AM2-11, AM2-19, AM2-20 (SPEC_APPS_v1_AM2_ORTE_UND_GRUNDFUNKTIONEN): Apps, die eine Shell mitbringt; globale id; Vertrauen; Auslieferung; needs.apps; rollen."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk.gateway import Gateway

NODE = shutil.which("node")
UIX = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix"

VORLAGE = '''tool:
  id: {id}
  name: "App {id}"
  version: {version}
  kind: object
  handles: [{typ}]
  entry: {{js: tool.js}}
  trust: {trust}
  needs: {{ui: ">=1.0 <2"{apps}}}
{extra}'''


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am2-shellapps-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.gw = Gateway(self.root)
        self.gw.herkunft_pruefen = False

    def schreibe(self, ordner, id, version="1.0.0", typ="rechnung", trust="COMMUNITY", apps="", extra=""):
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "tool.js").write_text("// x\n", encoding="utf-8")
        (ordner / "tool.yaml").write_text(VORLAGE.format(id=id, version=version, typ=typ, trust=trust, apps=apps, extra=extra), encoding="utf-8")

    def shell_app(self, shell, id, **kw):
        self.schreibe(self.root / "local_config" / "shells" / shell / "apps" / id, id, **kw)

    def tool(self, id, **kw):
        self.schreibe(self.root / "local_config" / "tools" / id, id, **kw)

    def abgewiesen(self):
        return {r["id"]: r["reasons"] for r in self.gw.manifest()["rejected"]}


class ShellApps(Basis):
    def test_app_einer_shell_wird_geladen_und_gilt_nur_dort(self):
        self.shell_app("cockpit", "kassenbuch")
        man = self.gw.tools()["kassenbuch"][1]
        self.assertEqual((man["shells"], man["shell_app"]), (["cockpit"], "cockpit"))
        ids_harness = [t["id"] for t in self.gw.manifest()["tools"]]
        self.assertNotIn("kassenbuch", ids_harness, "die aktive Shell ist die Standard-Shell, nicht cockpit")
        self.assertIn("kassenbuch", [e["id"] for e in self.gw.manifest()["nicht_in_dieser_shell"]])

    def test_anderes_shells_im_manifest_wird_abgewiesen(self):
        self.shell_app("cockpit", "kassenbuch", extra="  shells: [harness]\n")
        self.assertEqual(self.abgewiesen()["kassenbuch"], ["shell_app_shells_fest"])
        self.shell_app("cockpit", "kassenbuch", extra="  shells: [cockpit]\n")
        self.assertIn("kassenbuch", self.gw.tools())

    def test_eingebaute_shell_app_ist_community_auch_wenn_die_shell_captain_ist(self):
        self.shell_app("cockpit", "kassenbuch", trust="CAPTAIN")
        self.assertEqual(self.abgewiesen()["kassenbuch"], ["shell_app_vertrauen_community"])

    def test_id_global_eindeutig_eine_shell_app_verdraengt_kein_werkzeug(self):
        self.tool("kassenbuch")
        self.shell_app("cockpit", "kassenbuch")
        self.assertIn("kassenbuch", self.gw.tools(), "das Werkzeug bleibt")
        self.assertIsNone(self.gw.tools()["kassenbuch"][1]["shell_app"])
        self.assertEqual(self.abgewiesen()["kassenbuch"], ["id_doppelt"])

    def test_zwei_shell_apps_mit_derselben_id_beide_abgewiesen(self):
        self.shell_app("cockpit", "kassenbuch")
        self.shell_app("minimal", "kassenbuch")
        self.assertNotIn("kassenbuch", self.gw.tools())
        self.assertEqual(sum(1 for r in self.gw.manifest()["rejected"] if r["id"] == "kassenbuch"), 2)

    def test_paket_werkzeug_wird_von_einer_shell_app_gleicher_id_nicht_beruehrt(self):
        self.shell_app("cockpit", "decisions")
        self.assertEqual(self.gw.tools()["decisions"][1]["origin"], "package")
        self.assertEqual(self.abgewiesen()["decisions"], ["id_doppelt"])

    def test_auslieferung_unter_dem_bestehenden_pfad(self):
        self.shell_app("cockpit", "kassenbuch")
        pfad = self.gw.file("tools", "kassenbuch", "tool.js")
        self.assertIsNotNone(pfad)
        self.assertTrue(pfad.is_file())
        self.assertIn("apps", pfad.parts)

    def test_ordner_mit_unterstrich_und_verknuepfung_zaehlen_nicht(self):
        self.shell_app("cockpit", "_vorlage")
        self.assertNotIn("_vorlage", self.gw.tools())
        self.assertEqual([f.name for f, _o, _s in self.gw.registry.shell_app_dirs()], [])

    def test_paket_shell_apps_werden_gefunden(self):
        ordner = UIX / "shells"
        self.assertTrue(all(o in ("package", "local") for _f, o, _s in self.gw.registry.shell_app_dirs()))
        self.assertTrue(ordner.is_dir())

    def test_arbeitsstand_behaelt_apps_anderer_shells_ueber_den_leersatz(self):
        """AM2-11: eine App, die in der Ziel-Shell fehlt, steht in `nicht_in_dieser_shell` mit ihren Objekttypen – so sagt der Leerzustand wo sie verfügbar ist."""
        self.shell_app("cockpit", "kassenbuch")
        eintrag = next(e for e in self.gw.manifest()["nicht_in_dieser_shell"] if e["id"] == "kassenbuch")
        self.assertEqual((eintrag["shells"], eintrag["handles"]), (["cockpit"], ["rechnung"]))


class NeedsApps(Basis):
    def test_fehlende_app(self):
        self.tool("haupt", apps=', apps: {"basis": ">=1.0"}')
        self.assertEqual(self.abgewiesen()["haupt"], ["needs_app_fehlt:basis"])

    def test_passende_version(self):
        self.tool("basis", version="1.2.0", typ="angebot")
        self.tool("haupt", apps=', apps: {"basis": ">=1.1 <2"}')
        self.assertIn("haupt", self.gw.tools())

    def test_falsche_version(self):
        self.tool("basis", version="1.0.0", typ="angebot")
        self.tool("haupt", apps=', apps: {"basis": ">=1.1 <2"}')
        self.assertEqual(self.abgewiesen()["haupt"], ["needs_app_version:basis"])

    def test_kette_faellt_mit_ihrem_glied(self):
        self.tool("haupt", typ="kunde", apps=', apps: {"mitte": ">=1.0"}')
        self.tool("mitte", typ="lieferant", apps=', apps: {"basis": ">=1.0"}')
        gruende = self.abgewiesen()
        self.assertEqual(gruende["mitte"], ["needs_app_fehlt:basis"])
        self.assertEqual(gruende["haupt"], ["needs_app_fehlt:mitte"])

    def test_zyklus_bleibt_geladen(self):
        self.tool("eins", typ="kunde", apps=', apps: {"zwei": ">=1.0"}')
        self.tool("zwei", typ="lieferant", apps=', apps: {"eins": ">=1.0"}')
        self.assertEqual(sorted(set(self.gw.tools()) & {"eins", "zwei"}), ["eins", "zwei"])

    def test_ungueltige_form(self):
        self.tool("haupt", apps=', apps: {"Basis": ">=1.0"}')
        self.assertEqual(self.abgewiesen()["haupt"], ["needs_apps_invalid"])
        self.tool("haupt", apps=', apps: {"basis": "irgendwas"}')
        self.assertEqual(self.abgewiesen()["haupt"], ["needs_apps_invalid"])

    def test_eine_shell_app_darf_eine_andere_voraussetzen(self):
        self.shell_app("cockpit", "basis", typ="angebot")
        self.shell_app("cockpit", "haupt", apps=', apps: {"basis": ">=1.0"}')
        self.assertEqual(sorted(set(self.gw.tools()) & {"basis", "haupt"}), ["basis", "haupt"])


class Rollen(Basis):
    def test_rollen_sind_erlaubt_und_ohne_wirkung(self):
        self.tool("rolle", extra="  rollen: [buchhaltung, leitung]\n")
        man = self.gw.tools()["rolle"][1]
        self.assertEqual(man["rollen"], ["buchhaltung", "leitung"])
        self.assertIn("rolle", [t["id"] for t in self.gw.manifest()["tools"]], "Rollen blenden bis AM7 nichts aus")

    def test_ungueltige_rollen(self):
        for extra in ("  rollen: buchhaltung\n", "  rollen: [Gross]\n", "  rollen: [x]\n", "  rollen: [%s]\n" % ", ".join("rolle%d" % i for i in range(21))):
            self.tool("rolle", extra=extra)
            self.assertEqual(self.abgewiesen().get("rolle"), ["rollen_invalid"], extra)


class Anzeige(unittest.TestCase):
    @unittest.skipUnless(NODE, "node fehlt")
    def test_modul_laedt_ohne_fehler(self):
        out = subprocess.run([NODE, "-e", "require(%s); process.stdout.write('ok')" % json.dumps(str(UIX / "tools" / "modules" / "tool.js"))],
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual((out.returncode, out.stdout), (0, "ok"), out.stderr)


if __name__ == "__main__":
    unittest.main()
