"""AM0-02 (SPEC_APPS_v1_AM0_G2 §2): die Herkunftsdatei eingebauter Module – Einbau schreibt sie, Laden prüft sie, Entfernen löscht sie.
Geändert, hinzugefügt, fehlend, Herkunftsdatei gelöscht → abgewiesen mit Grund und Audit (einmal je Grund); CAPTAIN-Module ohne Datei laden wie bisher."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from test_desk_install import ARCH, CODE, module
from sedra_runtime.desk import herkunft

CAPTAIN_MANIFEST = '''tool:
  id: eigen
  name: Eigen
  version: 1.0.0
  kind: object
  handles: [task]
  entry: {js: tool.js}
  api: [GET /api/strip]
  events: {emits: [object.open], listens: [task.changed]}
  trust: CAPTAIN
  needs: {ui: ">=1.0 <2"}
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Herkunft(unittest.TestCase):
    def setUp(self):
        from sedra_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix="am0-herkunft-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.hub = UIXHub(self.root, ARCH)
        self.addCleanup(self.hub.close)
        self.source = module(Path(self.tmp.name) / "quelle" / "fremd", CODE)
        (self.source / "README.md").write_text("# fremd\n", encoding="utf-8")
        self.installed = self.root / "local_config" / "tools" / "fremd"
        self.datei = self.root / "local_config" / "uix_herkunft" / "tools" / "fremd.json"
        self.hub.install_request({"kind": "tool", "source": str(self.source)})
        item = next(d for d in self.hub.decisions_view()["items"] if d["kind"] == "request:install")
        self.hub.decide({"id": item["id"], "way": "freigeben_und_anwenden"})

    def abgewiesen(self):
        return {r["id"]: r["reasons"] for r in self.hub.gateway.manifest()["rejected"]}

    def ereignisse(self, typ):
        audit = self.hub.runtime.audit
        zeilen = [json.loads(z) for z in audit.path.read_text(encoding="utf-8").splitlines() if z.strip()]
        return [e for e in zeilen if e.get("event_type") == typ]

    def tampered(self):
        return self.ereignisse("UIX_MODULE_TAMPERED")

    def test_einbau_schreibt_die_herkunft_ausserhalb_des_moduls(self):
        self.assertTrue(self.datei.is_file())
        self.assertFalse((self.installed / "herkunft.json").exists())
        eintrag = json.loads(self.datei.read_text(encoding="utf-8"))
        self.assertEqual(eintrag["vertrauen_beim_einbau"], "COMMUNITY")
        self.assertEqual(eintrag["quelle"], str(self.source))
        self.assertEqual(eintrag["dateien"], {"README.md": sha(self.installed / "README.md"), "tool.js": sha(self.installed / "tool.js"), "tool.yaml": sha(self.installed / "tool.yaml")})
        self.assertIn("trust: COMMUNITY", (self.installed / "tool.yaml").read_text(encoding="utf-8"), "die Hashes gelten für das umgeschriebene Manifest")

    def test_audit_des_einbaus_nennt_den_hash_der_herkunft(self):
        [eintrag] = self.ereignisse("UIX_MODULE_INSTALLED")
        self.assertEqual(eintrag["payload"]["herkunft_sha256"], sha(self.datei))

    def test_unveraendert_wird_geladen(self):
        self.assertIn("fremd", [t["id"] for t in self.hub.gateway.manifest()["tools"]])
        self.assertNotIn("fremd", self.abgewiesen())

    def test_geaenderte_datei_wird_abgewiesen_und_einmal_gemeldet(self):
        (self.installed / "tool.js").write_text(CODE + "\n// nachträglich\n", encoding="utf-8")
        self.assertEqual(self.abgewiesen()["fremd"], ["herkunft_abweichung:tool.js"])
        self.assertFalse(self.hub.gateway.allowed("tool", "fremd", "GET", "/api/strip"), "auch die Allowlist kennt es nicht mehr")
        self.abgewiesen()
        self.assertEqual(len(self.tampered()), 1)
        self.assertEqual(self.tampered()[0]["payload"], {"kind": "tool", "id": "fremd", "gruende": ["herkunft_abweichung:tool.js"]})

    def test_zusaetzliche_datei_wird_abgewiesen(self):
        (self.installed / "extra.js").write_text("// neu\n", encoding="utf-8")
        self.assertEqual(self.abgewiesen()["fremd"], ["herkunft_datei_neu:extra.js"])

    def test_fehlende_datei_wird_abgewiesen(self):
        (self.installed / "README.md").unlink()
        self.assertEqual(self.abgewiesen()["fremd"], ["herkunft_datei_fehlt:README.md"])

    def test_geloeschte_herkunftsdatei_weist_ab(self):
        self.datei.unlink()
        self.assertEqual(self.abgewiesen()["fremd"], ["herkunft_fehlt"])

    def test_kaputte_herkunftsdatei_weist_ab(self):
        self.datei.write_text("kein json", encoding="utf-8")
        self.assertEqual(self.abgewiesen()["fremd"], ["herkunft_unlesbar"])

    def test_schalter_aus_laedt_trotz_aenderung(self):
        (self.installed / "tool.js").write_text("// anders\n", encoding="utf-8")
        self.hub.gateway.herkunft_pruefen = False
        self.assertNotIn("fremd", self.abgewiesen())

    def test_captain_modul_ohne_herkunftsdatei_laedt_wie_bisher(self):
        module(self.root / "local_config" / "tools" / "eigen", CODE, CAPTAIN_MANIFEST)
        self.assertIn("eigen", [t["id"] for t in self.hub.gateway.manifest()["tools"]])
        self.assertNotIn("eigen", self.abgewiesen())

    def test_zweiter_aufruf_hasht_nicht_neu(self):
        self.hub.gateway.manifest()
        vorher = self.hub.gateway._pruefer.hash_laeufe
        self.hub.gateway.manifest()
        self.hub.gateway.allowed("tool", "fremd", "GET", "/api/strip")
        self.assertEqual(self.hub.gateway._pruefer.hash_laeufe, vorher)

    def test_entfernen_loescht_die_herkunft(self):
        self.hub.install_remove({"kind": "tool", "id": "fremd"})
        self.assertFalse(self.datei.exists())

    def test_trust_apply_zieht_die_herkunft_nach(self):
        self.hub.trust_request({"kind": "tool", "id": "fremd"})
        item = next(d for d in self.hub.decisions_view()["items"] if d["kind"] == "request:trust")
        self.hub.decide({"id": item["id"], "way": "freigeben_und_anwenden"})
        eintrag = json.loads(self.datei.read_text(encoding="utf-8"))
        self.assertEqual(eintrag["dateien"]["tool.yaml"], sha(self.installed / "tool.yaml"))
        self.assertIn("trust: CAPTAIN", (self.installed / "tool.yaml").read_text(encoding="utf-8"))
        self.assertIn("fremd", [t["id"] for t in self.hub.gateway.manifest()["tools"]])


class Modul(unittest.TestCase):
    def test_aktualisieren_ohne_eintrag_tut_nichts(self):
        with tempfile.TemporaryDirectory() as tmp:
            ordner = Path(tmp) / "m"
            ordner.mkdir()
            (ordner / "a.js").write_text("x", encoding="utf-8")
            self.assertIsNone(herkunft.aktualisieren(tmp, "tools", "abc", ordner))
            self.assertFalse(herkunft.pfad(tmp, "tools", "abc").exists())

    def test_kaputtes_json_meldet_herkunft_unlesbar(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = herkunft.pfad(tmp, "tools", "abc")
            p.parent.mkdir(parents=True)
            p.write_text("{", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                herkunft.lesen(tmp, "tools", "abc")
            self.assertEqual(str(ctx.exception), "herkunft_unlesbar")


if __name__ == "__main__":
    unittest.main()
