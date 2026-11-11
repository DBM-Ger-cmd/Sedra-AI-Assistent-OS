"""O3 G2-05 bis G2-07 (SPEC_APPS_v1_O3PLUS_G9_G2): die Sammelkarte „Oberflächen-Änderungen übernehmen“ als Antrag im Posteingang. Der Antrag (gated.request) wird abgefangen, das Anwenden ruft den
Applier wie die Freigabe-Tür. Dazu die Einstufung (Klasse H für das Übernehmen) und die Routen der Harness."""
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk import decisions as desk_decisions
from sedra_runtime.desk.freigabeklasse import ARTEN, H, N, ROUTEN_HARNESS
from sedra_runtime.harness import antraege
from sedra_runtime.harness.api import GESCHUETZT, WEG
from sedra_runtime.harness.oberflaeche import Oberflaeche, sha
from sedra_runtime.uix_server import UIXHub, make_server

from test_uix_harness_api import ARCH, anfrage


class Hub:
    def __init__(self, ob):
        self.oberflaeche = ob
        self.audit, self.ereignisse, self._offen = [], [], []
        self.runtime = SimpleNamespace(audit=SimpleNamespace(append=lambda e, component=None, payload=None, **k: self.audit.append((e, payload))))
        self.events = SimpleNamespace(publish=lambda name, daten: self.ereignisse.append((name, daten)))
        self.harness = SimpleNamespace(oberflaeche_uebernehmen=lambda b, kanal='posteingang': ob.uebernehmen(b, kanal=kanal))

    def _open_requests(self):
        return self._offen


class Karte(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.uix = t / "uix"
        (self.uix / "tools" / "x").mkdir(parents=True)
        self.datei = self.uix / "tools" / "x" / "tool.js"
        self.datei.write_bytes(b"alt\n")
        self.ob = Oberflaeche(t / "ablage", self.uix)
        self.hub = Hub(self.ob)

    def aendern(self, text=b"neu\nfetch('/api/harness/karten')\n"):
        self.ob.zurueckhalten(self.datei, "S-1", "T-1")
        self.datei.write_bytes(text)

    def antrag(self, offen=None):
        self.hub._offen = offen or []
        with mock.patch.object(antraege.gated, "request", return_value={"mission_id": "M-NEU"}) as anfrage:
            out = antraege.oberflaeche_antrag(self.hub)
        return out, anfrage

    def test_ohne_zurueckgehaltene_dateien_kein_antrag(self):
        with self.assertRaises(ValueError) as e:
            self.antrag()
        self.assertIn("nichts_zurueckgehalten", str(e.exception))

    def test_antrag_bindet_genau_die_dateien_und_nennt_hinweise_und_diff(self):
        self.aendern()
        out, anfrage = self.antrag()
        self.assertEqual((out["mission_id"], out["anzahl"], out["schon_offen"]), ("M-NEU", 1, False))
        args, kw = anfrage.call_args
        self.assertEqual(args[1], antraege.KIND_OBERFLAECHE)
        self.assertEqual(args[4], {"dateien": [["tools/x/tool.js", sha(b"neu\nfetch('/api/harness/karten')\n")]]})
        self.assertTrue(kw["exact"])
        text = "\n".join(kw["risks"])
        self.assertIn("mit allen Rechten der Seite", text)
        self.assertIn("-alt", text)
        self.assertIn("⚠", text, "G3: Hinweise auf der Sammelkarte")
        self.assertIn("Hinweise sind eine Lesehilfe", text)
        self.assertEqual(self.ob.gehalten(self.datei)[0], True, "der Antrag übernimmt nichts")

    def test_derselbe_stand_ist_schon_beantragt(self):
        self.aendern()
        _, anfrage = self.antrag()
        binding = anfrage.call_args[0][4]
        out, anfrage2 = self.antrag(offen=[{"kind": antraege.KIND_OBERFLAECHE, "mission_id": "M-ALT", "binding": binding}])
        self.assertEqual((out["mission_id"], out["schon_offen"]), ("M-ALT", True))
        anfrage2.assert_not_called()

    def test_zu_viele_dateien_nur_ueber_die_konsole(self):
        for i in range(31):
            d = self.uix / "tools" / "x" / f"f{i}.js"
            d.write_bytes(b"a\n")
            self.ob.zurueckhalten(d)
            d.write_bytes(b"b\n")
        with self.assertRaises(ValueError) as e:
            self.antrag()
        self.assertIn("zu_gross_fuer_eine_karte", str(e.exception))
        self.assertIn("Konsole", str(e.exception))

    def test_anwenden_uebernimmt_die_gebundene_fassung(self):
        self.aendern()
        _, anfrage = self.antrag()
        binding = anfrage.call_args[0][4]
        out = antraege._oberflaeche_anwenden(self.hub, binding)
        self.assertEqual((out["uebernommen"], out["veraltet"]), (1, 0))
        self.assertEqual(self.ob.stand()["dateien"], {})
        self.assertEqual(self.hub.ereignisse[0][0], "harness.oberflaeche")

    def test_veraltete_bindung_uebernimmt_nichts(self):
        self.aendern()
        _, anfrage = self.antrag()
        binding = anfrage.call_args[0][4]
        self.datei.write_bytes(b"noch ganz anders\n")
        with self.assertRaises(ValueError) as e:
            antraege._oberflaeche_anwenden(self.hub, binding)
        self.assertIn(antraege.gated.STALE, str(e.exception))
        self.assertTrue(self.ob.gehalten(self.datei)[0], "bleibt zurückgehalten")

    def test_applier_ist_registriert_und_titel_gesetzt(self):
        registry = mock.MagicMock()
        with mock.patch.object(antraege.gated, "register_applier") as reg:
            antraege.registrieren(registry)
        self.assertIn(antraege.KIND_OBERFLAECHE, [c.args[0] for c in reg.call_args_list])
        self.assertIn("harness_oberflaeche", desk_decisions.REQUEST_TITLE)
        self.assertIn("harness_oberflaeche", desk_decisions.REQUEST_NOTE)


class Einstufung(unittest.TestCase):
    def test_uebernehmen_ist_klasse_h_die_rueckwege_sind_n_oder_zurueck(self):
        self.assertEqual(ARTEN["request:harness_oberflaeche"], H)
        self.assertEqual(ARTEN["harness_oberflaeche"], {"uebernehmen": H, "zuruecksetzen": N})
        self.assertEqual(ROUTEN_HARNESS["POST oberflaeche/vorlegen"][0], "antrag")
        for weg in ("POST oberflaeche/zuruecksetzen", "POST oberflaeche/zuruecknehmen"):
            self.assertEqual(ROUTEN_HARNESS[weg][0], "zurueck", weg)

    def test_routen_passen_zum_muster_und_die_schreibenden_sind_geschuetzt(self):
        for pfad in ("/api/harness/oberflaeche", "/api/harness/oberflaeche/vorlegen", "/api/harness/oberflaeche/zuruecksetzen", "/api/harness/oberflaeche/zuruecknehmen"):
            self.assertTrue(WEG.fullmatch(pfad), pfad)
        for pfad in ("/api/harness/oberflaeche/vorlegen", "/api/harness/oberflaeche/zuruecksetzen", "/api/harness/oberflaeche/zuruecknehmen"):
            self.assertTrue(GESCHUETZT.fullmatch(pfad), "S7: keine Antwort aus einem Harness-Prozess: " + pfad)
        self.assertFalse(GESCHUETZT.fullmatch("/api/harness/oberflaeche"), "Lesen bleibt frei")


class Routen(unittest.TestCase):
    """Die Routen der Harness über HTTP: lesen, zurücksetzen, zurücknehmen; Vorlegen ohne Änderung ist ein Fehler."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="o3-routen-")
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.hub = UIXHub(t / "project", ARCH)
        self.addCleanup(self.hub.close)
        self.uix = t / "uix"
        (self.uix / "tools").mkdir(parents=True)
        self.datei = self.uix / "tools" / "a.js"
        self.datei.write_bytes(b"alt\n")
        self.hub.oberflaeche.uix = self.uix.resolve()
        server, self.url = make_server(self.hub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

    def test_lesen_zuruecksetzen_und_zuruecknehmen(self):
        ob = self.hub.oberflaeche
        code, leer = anfrage(self.url, "GET", "/api/harness/oberflaeche")
        self.assertEqual((code, leer["dateien"], leer["uebernahmen"], leer["aktiv"]), (200, [], [], True))
        ob.zurueckhalten(self.datei, "S-1", "T-1")
        self.datei.write_bytes(b"neu\n")
        code, sicht = anfrage(self.url, "GET", "/api/harness/oberflaeche")
        self.assertEqual([e["rel"] for e in sicht["dateien"]], ["tools/a.js"])
        code, antwort = anfrage(self.url, "POST", "/api/harness/oberflaeche/zuruecksetzen", {})
        self.assertEqual((code, antwort["hergestellt"]), (200, ["tools/a.js"]))
        self.assertEqual(self.datei.read_bytes(), b"alt\n")
        ob.zurueckhalten(self.datei)
        self.datei.write_bytes(b"neu2\n")
        u = ob.uebernehmen(ob.bindung())["u"]
        code, antwort = anfrage(self.url, "POST", "/api/harness/oberflaeche/zuruecknehmen", {"u": u})
        self.assertEqual((code, antwort["hergestellt"]), (200, ["tools/a.js"]))
        self.assertEqual(self.datei.read_bytes(), b"alt\n")
        code, fehler = anfrage(self.url, "POST", "/api/harness/oberflaeche/zuruecknehmen", {})
        self.assertEqual(code, 400)

    def test_vorlegen_ohne_aenderung_ist_ein_fehler(self):
        code, antwort = anfrage(self.url, "POST", "/api/harness/oberflaeche/vorlegen", {})
        self.assertEqual(code, 400)
        self.assertIn("nichts_zurueckgehalten", str(antwort))


if __name__ == "__main__":
    unittest.main()
