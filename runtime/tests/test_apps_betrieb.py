"""AM7 Betriebsart A (SPEC_APPS_v1_AM7_UNTERNEHMEN): die Richtlinie des Betreibers – Schema, Durchsetzung über der Gewährung, Änderung per Hash, Person und Rolle im Audit, Nachweis-Export,
die Seite „Was SEDRA mit deinen Eingaben tut“. Schalter `betrieb_unternehmen` Standard aus."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk import richtlinie as rl
from sedra_runtime.desk.gateway import Gateway
from sedra_runtime.uix_server import UIXHub, make_server

from test_desk_install import ARCH

GUT = {"richtlinie": {"schema": 1, "rolle": "sachbearbeitung", "person": "Erika Muster", "apps": [{"id": "erlaubt-app", "version": ">=1.0 <2"}],
                      "shells": {"erlaubt": ["gateway-kmu", "harness"], "start": "gateway-kmu"}, "obergrenzen": {"community": "verboten", "dienste": "verboten"},
                      "aufbewahrung": {"entwuerfe_stunden": 12, "gespraeche_tage": 30}}}
APP = '''tool:
  id: {id}
  name: "App {id}"
  version: {version}
  kind: object
  handles: [{typ}]
  entry: {{js: tool.js}}
  trust: {trust}
  needs: {{ui: ">=1.0 <2"}}
'''


def kopie(**ueberschreiben):
    d = json.loads(json.dumps(GUT))
    d["richtlinie"].update(ueberschreiben)
    return d


class Schema(unittest.TestCase):
    def test_gueltig_und_normalisiert(self):
        daten, fehler = rl.pruefen(GUT)
        self.assertEqual(fehler, [])
        self.assertEqual((daten["rolle"], daten["person"], daten["gespraech"]), ("sachbearbeitung", "Erika Muster", "nur_gateway"))
        self.assertEqual(daten["obergrenzen"], {"community": "verboten", "dienste": "verboten", "zellen_fremd": "erlaubt", "ereignisse_inhalt": "erlaubt"})
        self.assertEqual(daten["apps"], [{"id": "erlaubt-app", "version": ">=1.0 <2", "sha256": None}])
        self.assertEqual(rl.pruefen(kopie(person="  Erika   Muster "))[0]["person"], "Erika Muster")

    def test_feste_rollen(self):
        for rolle in rl.ROLLEN:
            self.assertEqual(rl.pruefen(kopie(rolle=rolle))[1], [])
        self.assertIn("richtlinie_rolle_ungueltig", rl.pruefen(kopie(rolle="chef"))[1])

    def test_unbekanntes_feld_macht_sie_ungueltig_auch_die_ki_kennzeichnung_ist_nicht_abschaltbar(self):
        self.assertIn("richtlinie_unbekanntes_feld:kennzeichnung", rl.pruefen(kopie(kennzeichnung="aus"))[1])
        self.assertIn("richtlinie_unbekanntes_feld:ki_kennzeichnung", rl.pruefen(kopie(ki_kennzeichnung=False))[1])

    def test_fehlerfaelle(self):
        self.assertEqual(rl.pruefen(None)[1], ["richtlinie_mapping_fehlt"])
        self.assertEqual(rl.pruefen({"richtlinie": "x"})[1], ["richtlinie_mapping_fehlt"])
        for ueber, grund in (({"person": ""}, "richtlinie_person_ungueltig"), ({"person": 5}, "richtlinie_person_ungueltig"), ({"schema": 2}, "richtlinie_schema_ungueltig"),
                             ({"apps": [{"id": "A B"}]}, "richtlinie_app_ungueltig"), ({"apps": [{"id": "x-app", "sha256": "abc"}]}, "richtlinie_app_ungueltig"),
                             ({"apps": "alle"}, "richtlinie_apps_ungueltig"), ({"shells": {"erlaubt": "alle"}}, "richtlinie_shells_ungueltig"),
                             ({"shells": {"erlaubt": ["harness"], "start": "gateway-kmu"}}, "richtlinie_shell_start_ungueltig"),
                             ({"obergrenzen": {"community": "vielleicht"}}, "richtlinie_obergrenzen_ungueltig"), ({"obergrenzen": {"netz": "verboten"}}, "richtlinie_obergrenzen_ungueltig"),
                             ({"grundfunktionen_sichtbar": {"chef": ["logbuch"]}}, "richtlinie_grundfunktionen_ungueltig"), ({"grundfunktionen_sichtbar": {"betreiber": ["keller"]}}, "richtlinie_grundfunktionen_ungueltig"),
                             ({"aufbewahrung": {"entwuerfe_stunden": 0}}, "richtlinie_aufbewahrung_ungueltig"), ({"aufbewahrung": {"unbekannt": 5}}, "richtlinie_aufbewahrung_ungueltig"),
                             ({"gespraech": "immer"}, "richtlinie_gespraech_ungueltig")):
            with self.subTest(ueber=ueber):
                self.assertIn(grund, rl.pruefen(kopie(**ueber))[1])

    def test_fragen(self):
        daten, _ = rl.pruefen(GUT)
        r = rl.Richtlinie(daten, "h", [], True)
        self.assertIsNone(r.app_erlaubt("erlaubt-app", "1.2.0"))
        self.assertEqual(r.app_erlaubt("erlaubt-app", "2.0.0"), "richtlinie_app_version")
        self.assertEqual(r.app_erlaubt("fremd-app", "1.0.0"), "richtlinie_app_nicht_erlaubt")
        self.assertTrue(r.shell_erlaubt("harness"))
        self.assertFalse(r.shell_erlaubt("cockpit"))
        self.assertTrue(r.verboten("community") and not r.verboten("zellen_fremd"))
        self.assertEqual(r.start_shell(), "gateway-kmu")
        self.assertEqual(r.grundfunktionen(), list(rl.GRUNDFUNKTIONEN), "ohne Angabe sieht die Rolle alle")
        inaktiv = rl.Richtlinie()
        self.assertTrue(inaktiv.shell_erlaubt("irgendwas") and inaktiv.app_erlaubt("x") is None and not inaktiv.verboten("community"))

    def test_hash_in_der_richtlinie_bindet_die_fassung(self):
        daten, _ = rl.pruefen(kopie(apps=[{"id": "erlaubt-app", "sha256": "a" * 64}]))
        r = rl.Richtlinie(daten, "h", [], True)
        self.assertIsNone(r.app_erlaubt("erlaubt-app", "1.0.0", "a" * 64))
        self.assertEqual(r.app_erlaubt("erlaubt-app", "1.0.0", "b" * 64), "richtlinie_app_hash")

    def test_versionsbereiche(self):
        for bereich, version, ok in ((">=1.0 <2", "1.5.3", True), (">=1.0 <2", "2.0.0", False), (">=1.2", "1.1.9", False), ("==1.0", "1.0.7", True), ("1.0", "1.0.0", True), ("quatsch", "1.0.0", False)):
            self.assertEqual(rl._version_passt(bereich, version), ok, (bereich, version))

    def test_sichtbare_grundfunktionen_je_rolle(self):
        daten, _ = rl.pruefen(kopie(grundfunktionen_sichtbar={"sachbearbeitung": ["gespraech", "entscheidungen"], "betreiber": list(rl.GRUNDFUNKTIONEN)}))
        self.assertEqual(rl.Richtlinie(daten, "h", [], True).grundfunktionen(), ["gespraech", "entscheidungen"])


class Laden(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "local_config").mkdir()

    def schreibe(self, text):
        (self.root / "local_config" / "richtlinie.yaml").write_text(text, encoding="utf-8")

    def test_keine_datei_ist_einzelplatzbetrieb(self):
        r = rl.laden(self.root)
        self.assertEqual((r.aktiv, r.vorhanden, r.hash), (False, False, None))

    def test_gueltige_datei(self):
        self.schreibe(yaml.safe_dump(GUT))
        r = rl.laden(self.root)
        self.assertTrue(r.aktiv and r.vorhanden)
        self.assertEqual(len(r.hash), 64)
        self.assertEqual(r.beschreibung()["person"], "Erika Muster")

    def test_kaputte_oder_ungueltige_datei_ist_nicht_aktiv_mit_fehlern(self):
        self.schreibe("richtlinie: [kaputt\n")
        r = rl.laden(self.root)
        self.assertEqual((r.aktiv, r.vorhanden), (False, True))
        self.assertTrue(r.fehler[0].startswith("richtlinie_nicht_lesbar"))
        self.schreibe(yaml.safe_dump(kopie(rolle="chef")))
        self.assertIn("richtlinie_rolle_ungueltig", rl.laden(self.root).fehler)

    def test_aenderung_wird_am_hash_erkannt_und_protokolliert(self):
        protokoll = []
        audit = lambda e, p: protokoll.append((e, p))  # noqa: E731
        self.schreibe(yaml.safe_dump(GUT))
        r1 = rl.laden(self.root)
        self.assertEqual(rl.aenderung_pruefen(self.root, r1, audit)[0], None, "erster Stand: alt gibt es nicht")
        self.assertIsNone(rl.aenderung_pruefen(self.root, r1, audit), "unverändert: nichts")
        self.schreibe(yaml.safe_dump(kopie(person="Max Neu")))
        r2 = rl.laden(self.root)
        self.assertEqual(rl.aenderung_pruefen(self.root, r2, audit), (r1.hash, r2.hash))
        self.assertEqual([e for e, _p in protokoll], ["RICHTLINIE_GEAENDERT", "RICHTLINIE_GEAENDERT"])
        self.assertEqual(protokoll[-1][1], {"alt_hash": r1.hash, "neu_hash": r2.hash})
        self.assertNotIn("Max", json.dumps(protokoll), "ohne Inhalt")


class Gateway_(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am7-gw-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.gw = Gateway(self.root)
        self.gw.herkunft_pruefen = False

    def app(self, id, version="1.0.0", trust="CAPTAIN", typ="rechnung"):
        ordner = self.root / "local_config" / "tools" / id
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "tool.js").write_text("// x\n", encoding="utf-8")
        (ordner / "tool.yaml").write_text(APP.format(id=id, version=version, trust=trust, typ=typ), encoding="utf-8")

    def aktiv(self, **ueber):
        self.gw.richtlinie = rl.Richtlinie(rl.pruefen(kopie(**ueber))[0], "h", [], True)

    def abgewiesen(self):
        return {r["id"]: r["reasons"] for r in self.gw.manifest()["rejected"]}

    def test_ohne_richtlinie_aendert_sich_nichts(self):
        self.app("irgendeine")
        self.assertIn("irgendeine", self.gw.tools())

    def test_app_nicht_auf_der_liste_wird_nicht_geladen_die_auf_der_liste_schon(self):
        self.app("erlaubt-app", "1.2.0")
        self.app("fremde-app", typ="angebot")
        self.aktiv()
        self.assertIn("erlaubt-app", self.gw.tools())
        self.assertEqual(self.abgewiesen()["fremde-app"], ["richtlinie_app_nicht_erlaubt"])

    def test_version_ausserhalb_des_bereichs(self):
        self.app("erlaubt-app", "2.0.0")
        self.aktiv()
        self.assertEqual(self.abgewiesen()["erlaubt-app"], ["richtlinie_app_version"])

    def test_paket_werkzeuge_und_grundfunktionen_bleiben(self):
        self.aktiv(apps=[])
        ids = set(self.gw.tools())
        self.assertTrue({"decisions", "talk", "task", "logbook", "boundaries", "modules", "system"} <= ids)

    def test_obergrenze_community_und_dienste(self):
        self.app("erlaubt-app", trust="COMMUNITY")
        self.aktiv(obergrenzen={"community": "verboten"})
        self.assertEqual(self.abgewiesen()["erlaubt-app"], ["richtlinie_community_verboten"])
        self.aktiv(obergrenzen={"community": "erlaubt"})
        self.assertIn("erlaubt-app", self.gw.tools())

    def test_shell_nicht_erlaubt_wird_nicht_geladen(self):
        self.aktiv()
        shells = set(self.gw.shells())
        self.assertEqual(shells, {"gateway-kmu", "harness"})
        self.assertEqual(self.abgewiesen()["cockpit"], ["richtlinie_shell_nicht_erlaubt"])

    def test_obergrenzen_nehmen_faehigkeiten_die_wirkung(self):
        self.aktiv(obergrenzen={"zellen_fremd": "verboten", "ereignisse_inhalt": "verboten"})
        w = self.gw._richtlinie_wirksam(["lesen:task", "zelle:text", "ereignis:system.state", "ereignis:decision.pending", "verb:task.close"])
        self.assertEqual(w, ["lesen:task", "ereignis:system.state", "verb:task.close"])
        self.aktiv()
        self.assertEqual(self.gw._richtlinie_wirksam(["zelle:text"]), ["zelle:text"])


class HubTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am7-hub-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        (self.root / "local_config").mkdir(parents=True)
        (self.root / "local_config" / "switches.yaml").write_text("switches:\n  betrieb_unternehmen: {enabled: true}\n", encoding="utf-8")
        (self.root / "local_config" / "richtlinie.yaml").write_text(yaml.safe_dump(GUT), encoding="utf-8")
        self.hub = UIXHub(self.root, ARCH)
        self.addCleanup(self.hub.close)
        server, url = make_server(self.hub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.port, self.token = server.server_port, url.split("#")[1]

    def hole(self, methode, pfad, body=None):
        kopf = {"X-SEDRA-Token": self.token}
        text = None
        if body is not None:
            kopf["Content-Type"] = "application/json"
            text = json.dumps(body)
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            c.request(methode, pfad, text, kopf)
            res = c.getresponse()
            roh = res.read()
            try:
                return res.status, json.loads(roh or b"{}")
            except ValueError:
                return res.status, {}
        finally:
            c.close()

    def audit(self):
        return [json.loads(z) for z in self.hub.runtime.audit.path.read_text(encoding="utf-8").splitlines() if z.strip()]

    def test_richtlinie_gilt_start_shell_audit_mit_person_und_rolle(self):
        self.assertTrue(self.hub.richtlinie.aktiv)
        self.assertEqual(self.hub.gateway.registry.config()["shell"], "gateway-kmu")
        self.assertEqual({e["event_type"] for e in self.audit()} >= {"RICHTLINIE_GEAENDERT"}, True)
        self.hub.runtime.audit.append("TEST_EREIGNIS", component="test", payload={"person": "Fälscher", "x": 1})
        e = [x for x in self.audit() if x["event_type"] == "TEST_EREIGNIS"][-1]
        self.assertEqual((e["payload"]["person"], e["payload"]["rolle"], e["payload"]["x"]), ("Erika Muster", "sachbearbeitung", 1), "AM7-12: aus der Richtlinie, nicht vom Aufrufer")
        self.assertTrue(self.hub.runtime.audit.verify_chain())

    def test_anzeige_export_eingaben(self):
        status, v = self.hole("GET", "/api/uix/betrieb")
        self.assertEqual((status, v["schalter"], v["rolle"], v["person"]), (200, True, "sachbearbeitung", "Erika Muster"))
        self.assertTrue(v["richtlinie"]["aktiv"])
        status, ex = self.hole("GET", "/api/uix/betrieb/export")
        self.assertEqual(status, 200)
        self.assertTrue(ex["json"]["audit"]["kette_ok"])
        self.assertIn("Nachweis für die Prüfung", ex["text"])
        self.assertIn("Kette in Ordnung", ex["text"])
        self.assertNotIn("anfrage", json.dumps(ex["json"]).lower().replace("anfrage_", ""), "keine Inhalte")
        status, t = self.hole("GET", "/api/uix/betrieb/eingaben")
        self.assertEqual(t["titel"], "Was SEDRA mit deinen Eingaben tut")
        text = " ".join(t["absaetze"])
        self.assertIn("nach 12 Stunden gelöscht", text)
        self.assertIn("nach 30 Tagen", text)
        self.assertIn("Erika Muster, Rolle sachbearbeitung", text)
        self.assertIn("keine Rechtsauskunft", text)

    def test_es_gibt_keinen_weg_die_richtlinie_zu_aendern(self):
        for methode in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertNotEqual(self.hole(methode, "/api/uix/betrieb", {})[0], 200, methode)
        self.assertEqual(self.hole("POST", "/api/uix/betrieb/export", {})[0] in (403, 404, 405), True)

    def test_shell_wechsel_in_eine_nicht_erlaubte_shell_ist_nicht_moeglich(self):
        with self.assertRaises(ValueError):
            self.hub.shell_set({"shell": "cockpit"})
        self.assertEqual(self.hub.shell_set({"shell": "harness"})["status"] in ("set", "visit", "switched", "ok"), True)

    def test_ungueltige_richtlinie_wird_protokolliert_und_nicht_still_ignoriert(self):
        self.hub.close()
        (self.root / "local_config" / "richtlinie.yaml").write_text(yaml.safe_dump(kopie(kennzeichnung="aus")), encoding="utf-8")
        hub2 = UIXHub(self.root, ARCH)
        self.addCleanup(hub2.close)
        self.assertFalse(hub2.richtlinie.aktiv)
        self.assertIn("richtlinie_unbekanntes_feld:kennzeichnung", hub2.richtlinie.fehler)
        arten = [json.loads(z)["event_type"] for z in hub2.runtime.audit.path.read_text(encoding="utf-8").splitlines() if z.strip()]
        self.assertIn("RICHTLINIE_UNGUELTIG", arten)

    def test_aenderung_der_datei_wird_beim_naechsten_start_protokolliert(self):
        self.hub.close()
        (self.root / "local_config" / "richtlinie.yaml").write_text(yaml.safe_dump(kopie(person="Max Neu")), encoding="utf-8")
        hub2 = UIXHub(self.root, ARCH)
        self.addCleanup(hub2.close)
        gesehen = [json.loads(z) for z in hub2.runtime.audit.path.read_text(encoding="utf-8").splitlines() if z.strip()]
        geaendert = [e for e in gesehen if e["event_type"] == "RICHTLINIE_GEAENDERT"]
        self.assertEqual(len(geaendert), 2)
        self.assertNotEqual(geaendert[-1]["payload"]["alt_hash"], geaendert[-1]["payload"]["neu_hash"])

    def test_schalter_aus_ist_einzelplatzbetrieb(self):
        self.hub.close()
        (self.root / "local_config" / "switches.yaml").write_text("switches:\n  betrieb_unternehmen: {enabled: false}\n", encoding="utf-8")
        hub2 = UIXHub(self.root, ARCH)
        self.addCleanup(hub2.close)
        self.assertFalse(hub2.richtlinie.aktiv)
        self.assertIn("cockpit", hub2.gateway.shells())

    def test_verantwortliche_person_kommt_aus_der_richtlinie_nicht_vom_aufrufer(self):
        """AM7-03: bei aktiver Richtlinie die Person aus der Datei; ein mitgegebener Name wird überschrieben."""
        v = self.hub.gateway_new({"titel": "Prüfung der Person", "wunsch": "local"})
        vid = v["id"]
        out = self.hub.gateway_pruefen({"id": vid, "anfrage": "Bitte eine kurze Antwort auf die Anfrage zur Lieferung vorbereiten.", "zweck": "antwortentwurf", "verantwortlich": "Jemand Anderes"})
        self.assertEqual(out["verantwortlich"], "Erika Muster")

    def test_ohne_richtlinie_bleibt_die_eingabe_wie_bisher(self):
        self.hub.close()
        (self.root / "local_config" / "switches.yaml").write_text("switches:\n  betrieb_unternehmen: {enabled: false}\n", encoding="utf-8")
        hub2 = UIXHub(self.root, ARCH)
        self.addCleanup(hub2.close)
        vid = hub2.gateway_new({"titel": "Ohne Richtlinie", "wunsch": "local"})["id"]
        out = hub2.gateway_pruefen({"id": vid, "anfrage": "Bitte eine kurze Antwort auf die Anfrage zur Lieferung vorbereiten.", "zweck": "antwortentwurf", "verantwortlich": "Torsten"})
        self.assertEqual(out["verantwortlich"], "Torsten")


if __name__ == "__main__":
    unittest.main()
