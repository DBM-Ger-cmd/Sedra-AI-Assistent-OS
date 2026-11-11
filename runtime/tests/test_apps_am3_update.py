"""AM3-13 bis AM3-15 (Stück 4): Update einer eingebauten fremden App – Version, Datei-Diff, Rechte-Diff im Gate, atomares Ersetzen, `vorher`, Gewährung und `aktiv`."""
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk import app_speicher, app_update
from sedra_runtime.uix_server import UIXHub

from test_desk_install import ARCH, CODE, module

MANIFEST = '''tool:
  id: fremd
  name: "Fremde App"
  version: {version}
  kind: object
  handles: [task]
  entry: {{js: tool.js}}
  events: {{emits: [], listens: [task.changed]}}
  trust: COMMUNITY
  needs: {{ui: ">=1.1 <2"}}
  rechte:
    lesen: [task]
{extra}'''


def manifest(version="1.0.0", extra=""):
    return MANIFEST.format(version=version, extra=extra)


class Update(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am3-update-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.hub = UIXHub(self.root, ARCH)
        self.addCleanup(self.hub.close)
        self.hub.gateway.app_berechtigung = True
        self.einbauen(manifest(), CODE)
        self.ziel = self.root / "local_config" / "tools" / "fremd"
        self.vorher = self.root / "local_config" / "apps" / "vorher" / "fremd"

    def entscheide(self, art, way="freigeben_und_anwenden"):
        item = next(d for d in self.hub.decisions_view()["items"] if d["kind"] == art)
        return self.hub.decide({"id": item["id"], "way": way})

    def einbauen(self, text, code):
        quelle = module(Path(self.tmp.name) / "quelle" / "fremd", code, text)
        self.hub.install_request({"kind": "tool", "source": str(quelle)})
        self.entscheide("request:install")
        return quelle

    def vorlegen(self, text, code=CODE):
        quelle = module(Path(self.tmp.name) / "quelle2" / "fremd", code, text)
        return self.hub.install_request({"kind": "tool", "source": str(quelle)})

    def gewaehre_und_aktiviere(self):
        self.hub.apps_rechte_request({"id": "fremd", "faehigkeiten": ["lesen:task"]})
        self.entscheide("request:apps_rechte")
        self.hub.apps_aktivieren({"id": "fremd"})

    def test_version_nicht_hoeher_wird_abgewiesen(self):
        for v in ("1.0.0", "0.9.9"):
            with self.assertRaises(ValueError) as e:
                self.vorlegen(manifest(v))
            self.assertIn("update_version_nicht_hoeher", str(e.exception))

    def test_versionsvergleich_zahlenweise(self):
        self.assertTrue(app_update.version_hoeher("1.9.0", "1.10.0"))
        self.assertFalse(app_update.version_hoeher("1.10.0", "1.9.0"))
        self.assertFalse(app_update.version_hoeher("1.0", "1.1.0"))

    def test_das_gate_zeigt_datei_und_rechte_diff(self):
        antrag = self.vorlegen(manifest("1.1.0", "    verben: [task.close]\n"), CODE + "\n// neu\n")
        u = antrag["binding"]["update"]
        arten = {d["pfad"]: d["art"] for d in u["datei_diff"]}
        self.assertEqual(arten, {"tool.js": "geaendert", "tool.yaml": "geaendert"})
        js = next(d for d in u["datei_diff"] if d["pfad"] == "tool.js")
        self.assertTrue(any(z.startswith("+// neu") for z in js["text"]))
        self.assertEqual([(r["faehigkeit"], r["richtung"], r["stufe"]) for r in u["rechte_diff"]], [("verb:task.close", "neu", "B")])
        self.assertTrue(any("verb:task.close" in r and "Stufe B" in r for r in antrag["gate"]["request"]["risks"]))
        self.assertTrue(any(i["kind"] == "request:install" for i in self.hub.decisions_view()["items"]))

    def test_ohne_freigabe_bleibt_die_alte_fassung(self):
        self.vorlegen(manifest("1.1.0"), CODE + "\n// neu\n")
        self.assertNotIn("// neu", (self.ziel / "tool.js").read_text(encoding="utf-8"))
        self.assertFalse(self.vorher.exists())

    def test_anwenden_ersetzt_atomar_und_haelt_die_alte_fassung(self):
        self.gewaehre_und_aktiviere()
        self.vorlegen(manifest("1.1.0"), CODE + "\n// neu\n")
        self.entscheide("request:install")
        self.assertIn("// neu", (self.ziel / "tool.js").read_text(encoding="utf-8"))
        self.assertIn("version: 1.1.0", (self.ziel / "tool.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("// neu", (self.vorher / "tool.js").read_text(encoding="utf-8"))
        self.assertFalse((self.ziel.with_name("fremd.im-bau")).exists())

    def test_gewaehrung_und_aktiv_bleiben_ohne_neue_rechte(self):
        self.gewaehre_und_aktiviere()
        self.vorlegen(manifest("1.1.0"), CODE + "\n// neu\n")
        self.entscheide("request:install")
        eintrag = app_speicher.lesen(self.root)["fremd"]
        self.assertTrue(eintrag["aktiv"])
        self.assertEqual(eintrag["manifest_sha256"], app_speicher.manifest_hash(self.ziel / "tool.yaml"))
        self.assertIn("fremd", self.hub.gateway.tools(), "die App lädt nach dem Update ohne neue Rechte ohne weitere Frage")

    def test_neues_recht_gehoert_zur_selben_entscheidung(self):
        self.gewaehre_und_aktiviere()
        self.vorlegen(manifest("1.1.0", "    verben: [task.close]\n"))
        self.entscheide("request:install")
        eintrag = app_speicher.lesen(self.root)["fremd"]
        self.assertEqual(eintrag["gewaehrt"], ["lesen:task", "verb:task.close"])
        self.assertIn("fremd", self.hub.gateway.tools())

    def test_entfallenes_recht_wird_entzogen(self):
        self.hub.apps_rechte_request({"id": "fremd", "faehigkeiten": ["lesen:task"]})
        self.entscheide("request:apps_rechte")
        neu = manifest("1.1.0").replace("    lesen: [task]\n", "    ereignisse: [system.state]\n")
        self.vorlegen(neu)
        self.entscheide("request:install")
        self.assertEqual(app_speicher.lesen(self.root)["fremd"]["gewaehrt"], ["ereignis:system.state"])

    def test_alte_fassung_geaendert_zwischen_antrag_und_freigabe(self):
        self.vorlegen(manifest("1.1.0"))
        (self.ziel / "tool.js").write_text("// von Hand\n", encoding="utf-8")
        (self.ziel / "tool.yaml").write_text((self.ziel / "tool.yaml").read_text(encoding="utf-8") + "  description: x\n", encoding="utf-8")
        with self.assertRaises(ValueError) as e:
            self.entscheide("request:install")
        self.assertIn("app_changed_since_the_request", str(e.exception))

    def test_zweites_update_ersetzt_vorher(self):
        self.vorlegen(manifest("1.1.0"), CODE + "\n// zwei\n")
        self.entscheide("request:install")
        self.vorlegen(manifest("1.2.0"), CODE + "\n// drei\n")
        self.entscheide("request:install")
        self.assertIn("// zwei", (self.vorher / "tool.js").read_text(encoding="utf-8"))

    def test_schalter_aus_verhaelt_sich_wie_vorher(self):
        self.hub.gateway.app_berechtigung = False
        with self.assertRaises(ValueError) as e:
            self.vorlegen(manifest("1.1.0"))
        self.assertIn("schon vergeben", str(e.exception))


if __name__ == "__main__":
    unittest.main()
