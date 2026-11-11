"""AM3-01, AM3-05, AM3-06, AM3-08 (Stück 1): das Feld `rechte`, die Berechtigungsdatei und die Ladeentscheidung im Gateway.
Hinter dem Schalter `app_berechtigung` (Standard aus): aus ändert nichts, an lädt nur eine gewährte, aktive App mit passender Fassung."""
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk import app_speicher, berechtigung
from sedra_runtime.desk.gateway import Gateway
from sedra_runtime.desk.rechte_diff import stufe

MANIFEST = '''tool:
  id: fremd
  name: Fremd
  version: 1.0.0
  kind: object
  handles: [task]
  entry: {js: tool.js}
  trust: COMMUNITY
  needs: {ui: ">=1.1 <2"}
  rechte:
    lesen: [task]
    ereignisse: [system.state]
'''


class Laden(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am3-laden-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ordner = self.root / "local_config" / "tools" / "fremd"
        self.ordner.mkdir(parents=True)
        (self.ordner / "tool.js").write_text("export default {};\n", encoding="utf-8")
        self.schreibe(MANIFEST)
        self.gw = Gateway(self.root)
        self.gw.herkunft_pruefen = False

    def schreibe(self, text):
        (self.ordner / "tool.yaml").write_text(text, encoding="utf-8")

    def gewaehre(self, **felder):
        h = app_speicher.manifest_hash(self.ordner / "tool.yaml")
        eintrag = berechtigung.eintrag_neu(h, "COMMUNITY", ["lesen:task", "ereignis:system.state"])
        eintrag.update(felder)
        app_speicher.aendern(self.root, "fremd", lambda _alt: eintrag)

    def geladen(self):
        return "fremd" in self.gw.tools()

    def abgewiesen(self):
        return {r["id"]: r["reasons"] for r in self.gw.manifest()["rejected"]}

    def test_schalter_aus_aendert_nichts(self):
        self.assertFalse(self.gw.app_berechtigung)
        self.assertTrue(self.geladen())

    def test_ohne_gewaehrung_nicht_geladen(self):
        self.gw.app_berechtigung = True
        self.assertFalse(self.geladen())
        self.assertEqual(self.abgewiesen()["fremd"], ["keine_gewaehrung"])

    def test_gewaehrt_aber_inaktiv(self):
        self.gw.app_berechtigung = True
        self.gewaehre()
        self.assertEqual(self.abgewiesen()["fremd"], ["app_inaktiv"])

    def test_gewaehrt_und_aktiv_laedt_mit_wirksamen_rechten(self):
        self.gw.app_berechtigung = True
        self.gewaehre(aktiv=True)
        self.assertTrue(self.geladen())
        self.assertEqual(self.gw.tools()["fremd"][1]["wirksam"], ["ereignis:system.state", "lesen:task"])

    def test_geaendertes_manifest_macht_die_gewaehrung_veraltet(self):
        self.gw.app_berechtigung = True
        self.gewaehre(aktiv=True)
        self.schreibe(MANIFEST + "    ablage: 100\n")
        self.assertEqual(self.abgewiesen()["fremd"], ["gewaehrung_veraltet"])

    def test_beantragt_mehr_als_gewaehrt(self):
        self.gw.app_berechtigung = True
        self.gewaehre(aktiv=True, gewaehrt=["lesen:task"])
        [grund] = self.abgewiesen()["fremd"]
        self.assertEqual(grund, "rechte_nicht_gewaehrt:ereignis:system.state")

    def test_kaputte_datei_gilt_als_keine_gewaehrung(self):
        self.gw.app_berechtigung = True
        datei = app_speicher.datei(self.root)
        datei.parent.mkdir(parents=True)
        datei.write_text("apps: [kaputt\n", encoding="utf-8")
        self.assertEqual(self.abgewiesen()["fremd"], ["keine_gewaehrung"])

    def test_stufe_c_wird_beim_pruefen_abgewiesen(self):
        self.schreibe(MANIFEST + "    verben: [candidate.uebernehmen]\n")
        [grund] = self.abgewiesen()["fremd"]
        self.assertEqual(grund, "rechte_stufe_c:verb:candidate.uebernehmen")

    def test_die_vier_verben_mit_gate_sind_stufe_c_die_uebrigen_b(self):
        for v in ("candidate.uebernehmen", "candidate.zuruecknehmen", "boundary.bestaetigen", "boundary.aendern"):
            self.assertEqual(stufe("verb:" + v), "C")
        self.assertEqual(stufe("verb:task.close"), "B")

    def test_unbekannter_rechteschluessel(self):
        self.schreibe(MANIFEST + "    admin: ja\n")
        self.assertEqual(self.abgewiesen()["fremd"], ["rechte_unbekannt:admin"])

    def test_captain_modul_wird_nicht_gefiltert(self):
        self.schreibe(MANIFEST.replace("COMMUNITY", "CAPTAIN"))
        self.gw.app_berechtigung = True
        self.assertTrue(self.geladen(), "nur COMMUNITY wird gefiltert; CAPTAIN lädt wie bisher")

    def test_die_datei_nimmt_nur_gueltige_ids_auf(self):
        app_speicher.schreiben(self.root, {"fremd": {"aktiv": True}, "../x": {"aktiv": True}, "ok": "kein dict"})
        self.assertEqual(list(app_speicher.lesen(self.root)), ["fremd"])


if __name__ == "__main__":
    unittest.main()
