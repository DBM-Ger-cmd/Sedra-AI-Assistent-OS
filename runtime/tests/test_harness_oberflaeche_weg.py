"""O3 G2 (SPEC_APPS_v1_O3PLUS_G9_G2 G2-01 bis G2-04, G2-08, G2-10): der ganze Weg – ein Schreibvorgang unter einer Aufgabe hält die bestätigte Fassung zurück, der Betriebsserver liefert
sie aus; über eine Karte, ohne Aufgabe oder bei abgeschaltetem Schalter wird nichts zurückgehalten. Echter Guard, Wegwerf-Projekt."""
import http.client
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.core.guard import Guard
from sedra_runtime.harness.aufgabe import Aufgaben
from sedra_runtime.harness.freigabe import Karten, Kiste
from sedra_runtime.harness.oberflaeche import INHALT_MAX, Oberflaeche
from sedra_runtime.harness.werkzeuge import Werkzeuge
from sedra_runtime.uix_server import UIXHub, make_server

from test_desk_install import ARCH as ARCH_UIX, CODE, module
from test_harness_oberflaeche_weich import ARCH, S, SITZUNG, TASKLEISTE, aufgabe, regel


class Weg(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "projekt"
        for rel in (TASKLEISTE, S + "tools/gauge-ram/tool.js"):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_bytes(b"alt\n")
        self.guard = Guard(ARCH / "core" / "guard" / "guard_rules.yaml", None, Path(self.tmp.name) / "tokens.json")
        self.regeln = [regel("lesen", ["datei_lesen", "dateien_auflisten", "suchen"], ["**"], "frei"), regel("schreiben", ["datei_schreiben", "datei_aendern"], ["**"], "frei")]
        self.projekt = {"id": "p", "name": "P", "wurzel": str(self.root), "schreibbereich": ["**"]}
        self.ablage = Path(self.tmp.name) / "runtime_data" / "harness" / "oberflaeche"
        self.ob = Oberflaeche(self.ablage, self.root / S)
        self.karten = Karten(Path(self.tmp.name) / "karten")
        self.aufgaben = Aufgaben(Path(self.tmp.name) / "aufgaben")

    def kiste(self, oberflaeche="ja"):
        w = Werkzeuge(self.projekt, guard=self.guard, mission_id="M-O3WEG", regeln=self.regeln, oberflaeche=self.ob if oberflaeche == "ja" else None)
        return Kiste(w, regeln=self.regeln, guard=self.guard, audit=None, karten=self.karten, sitzung_id=SITZUNG, aufgaben=self.aufgaben, projekt_id="p")

    def aendern(self, kiste, pfad=TASKLEISTE, neu="neu"):
        return kiste.aufruf("datei_aendern", {"pfad": pfad, "alt": "alt", "neu": neu})

    def test_unter_einer_aufgabe_wird_die_bestaetigte_fassung_zurueckgehalten(self):
        self.aufgaben.anlegen(aufgabe(oberflaeche=[TASKLEISTE]))
        out = self.aendern(self.kiste())
        self.assertEqual((out["status"], out["stufe"]), ("ok", "aufgabe"))
        self.assertEqual((self.root / TASKLEISTE).read_bytes(), b"neu\n", "auf der Platte steht die neue Fassung (Tests, Vorschau)")
        gehalten, bestaetigt = self.ob.gehalten(self.root / TASKLEISTE)
        self.assertEqual((gehalten, bestaetigt), (True, b"alt\n"), "der Betriebsserver liefert die bestätigte")
        [e] = self.ob.liste()
        self.assertEqual((e["rel"], e["sitzung"], e["aufgabe"] is not None, e["geaendert"]), ("shells/harness/taskleiste.js", SITZUNG, True, True))

    def test_ein_zweiter_schreibvorgang_aendert_die_gemerkte_fassung_nicht(self):
        self.aufgaben.anlegen(aufgabe(oberflaeche=[TASKLEISTE]))
        k = self.kiste()
        self.aendern(k, neu="neu")
        (self.root / TASKLEISTE).write_bytes(b"alt\n")
        self.aendern(k, neu="noch neuer")
        self.assertEqual(self.ob.gehalten(self.root / TASKLEISTE), (True, b"alt\n"))

    def test_ueber_eine_karte_wird_nicht_zurueckgehalten(self):
        out = self.aendern(self.kiste())
        self.assertEqual(out["status"], "wartet", "ohne Aufgabe ist es eine Karte (O3 weich)")
        self.assertEqual(self.ob.stand()["dateien"], {})

    def test_schalter_aus_haelt_nichts_mehr_zurueck(self):
        self.aufgaben.anlegen(aufgabe(oberflaeche=[TASKLEISTE]))
        out = self.aendern(self.kiste(oberflaeche=None))
        self.assertEqual(out["status"], "ok")
        self.assertEqual(self.ob.stand()["dateien"], {})

    def test_zu_grosse_datei_erreicht_die_ablage_nie(self):
        """Das Werkzeug lehnt Dateien über DATEI_MAX schon beim Vorbereiten ab (`datei_zu_gross`); die Grenze der Ablage ist gleich groß – Zurückhalten kann sie also nicht überschreiten."""
        from sedra_runtime.harness.werkzeuge import DATEI_MAX
        self.assertLessEqual(DATEI_MAX, INHALT_MAX)
        (self.root / TASKLEISTE).write_bytes(b"alt\n" + b"x" * (DATEI_MAX + 1))
        self.aufgaben.anlegen(aufgabe(oberflaeche=[TASKLEISTE]))
        out = self.aendern(self.kiste())
        self.assertEqual(out["status"], "fehler")
        self.assertIn("datei_zu_gross", out["ergebnis"])
        self.assertEqual(self.ob.stand()["dateien"], {})

    def test_ein_anderes_projekt_wird_nicht_zurueckgehalten(self):
        anderes = Path(self.tmp.name) / "anderes"
        (anderes / TASKLEISTE).parent.mkdir(parents=True)
        (anderes / TASKLEISTE).write_bytes(b"alt\n")
        self.projekt = {"id": "p", "name": "P", "wurzel": str(anderes), "schreibbereich": ["**"]}
        self.aufgaben.anlegen(aufgabe(oberflaeche=[TASKLEISTE]))
        out = self.aendern(self.kiste())
        self.assertEqual(out["status"], "ok", "der weiche Vorbehalt gilt, zurückgehalten wird dort nichts: der Server liefert diesen Ordner nicht aus")
        self.assertEqual(self.ob.stand()["dateien"], {})


class Ausliefern(unittest.TestCase):
    """G2-03 über HTTP: ein lokales Werkzeug (`local_config/tools/<id>`) dient als `uix`-Ordner des Betriebsservers."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="o3-liefern-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.hub = UIXHub(self.root, ARCH_UIX)
        self.addCleanup(self.hub.close)
        self.hub.gateway.herkunft_pruefen = False
        manifest = ('tool:\n  id: lokal\n  name: Lokal\n  version: 1.0.0\n  kind: object\n  handles: [task]\n  entry: {js: tool.js}\n  trust: CAPTAIN\n  needs: {ui: ">=1.0 <2"}\n')
        self.quelle = module(self.root / "local_config" / "tools" / "lokal", "// v1\n", manifest)
        (self.root / "local_config" / "tools" / "lokal" / "tool.js").write_bytes(b"// v1\n")      # LF, nicht CRLF: der Test vergleicht Bytes
        self.hub.oberflaeche.uix = (self.root / "local_config").resolve()
        server, url = make_server(self.hub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.port = server.server_port

    def hole(self, pfad):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            c.request("GET", pfad)
            res = c.getresponse()
            return res.status, res.read()
        finally:
            c.close()

    def test_zurueckgehaltene_datei_kommt_in_der_bestaetigten_fassung_neue_datei_ist_404(self):
        datei = self.root / "local_config" / "tools" / "lokal" / "tool.js"
        self.assertEqual(self.hole("/uix/tools/lokal/tool.js"), (200, b"// v1\n"))
        self.assertTrue(self.hub.oberflaeche.zurueckhalten(datei, "S-1", "T-1"))
        datei.write_bytes(b"// v2\n")
        self.assertEqual(self.hole("/uix/tools/lokal/tool.js"), (200, b"// v1\n"), "bestätigt, nicht die Platte")
        self.hub.oberflaeche.uebernehmen(self.hub.oberflaeche.bindung())
        self.assertEqual(self.hole("/uix/tools/lokal/tool.js"), (200, b"// v2\n"), "nach der Übernahme gilt die neue Fassung")
        neu = self.root / "local_config" / "tools" / "lokal" / "neu.js"
        self.assertTrue(self.hub.oberflaeche.zurueckhalten(neu))
        neu.write_bytes(b"// neu\n")
        self.assertEqual(self.hole("/uix/tools/lokal/neu.js")[0], 404, "neu = es gab sie nicht")

    def test_nicht_zurueckgehaltenes_wird_unveraendert_geliefert_und_der_hub_hat_den_baustein(self):
        self.assertEqual(self.hole("/uix/tools/lokal/tool.js"), (200, b"// v1\n"))
        self.assertIsNotNone(self.hub.oberflaeche)
        self.assertEqual(self.hole("/uix/ui/loader.js")[0], 200)


if __name__ == "__main__":
    unittest.main()
