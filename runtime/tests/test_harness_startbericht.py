"""O3 G6 (SPEC_APPS_v1_O3PLUS_G9_G2 §2.5): der Start-Bericht. Beim Start fragt SEDRA den Code-Stand des Projekts, das das laufende Programm enthält; hat die Harness Programmdateien unter runtime/src/**
geändert, die der Captain nicht gesehen hat, liegt ein Eintrag im Posteingang – nur zur Kenntnis, Klasse N, macht nichts gesehen."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk import decisions as desk_decisions
from sedra_runtime.desk.freigabeklasse import ARTEN, N, klasse
from sedra_runtime.harness import projekte as harness_projekte
from sedra_runtime.harness.code_stand import CodeStand
from sedra_runtime.uix_server import UIXHub

from test_uix_harness_api import ARCH


class Startbericht(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="o3-startbericht-")
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.root = t / "sedra"
        (self.root / "runtime_data" / "harness").mkdir(parents=True)
        self.wurzel = t / "repo"
        (self.wurzel / "runtime" / "src" / "pkg").mkdir(parents=True)
        (self.wurzel / "runtime" / "src" / "pkg" / "a.py").write_bytes(b"a = 1\n")
        (self.wurzel / "runtime" / "src" / "pkg" / "uix" / "tools").mkdir(parents=True)
        self.projekt = {"id": "sedra-entwicklung", "name": "Sedra", "wurzel": str(self.wurzel.resolve()), "schreibbereich": ["**"]}
        self.cs = CodeStand(self.root / "runtime_data" / "harness" / "code_stand", self.projekt["wurzel"], self.projekt["id"])
        self.assertEqual(self.cs.ungesehen(), [])
        self.audit = []

    def hub(self):
        with mock.patch.object(harness_projekte, "laden", return_value=[self.projekt]):
            hub = UIXHub(self.root, ARCH)
        self.addCleanup(hub.close)
        hub.oberflaeche.uix = (self.wurzel / "runtime" / "src" / "pkg" / "uix").resolve()
        hub.runtime.audit.append = lambda e, component=None, payload=None, **k: self.audit.append((e, payload))
        return hub

    def aendere(self, rel, text, spur=True):
        p = self.wurzel / rel
        p.write_bytes(text)
        import os
        st = p.stat()
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
        if spur:
            self.cs.spur(rel, "S-0000000A", "aufgabe")

    def bericht(self, hub):
        with mock.patch.object(harness_projekte, "laden", return_value=[self.projekt]):
            return hub.harness.startbericht_pruefen()

    def test_kein_bericht_ohne_ungesehene_harness_dateien(self):
        self.assertIsNone(self.bericht(self.hub()))
        self.assertIn("STARTBERICHT", [e for e, _p in self.audit])
        self.assertEqual(self.audit[-1][1], {"anzahl_harness": 0, "anzahl_sonst": 0})

    def test_bericht_nennt_zahl_pfade_und_konsolenweg(self):
        self.aendere("runtime/src/pkg/a.py", b"a = 2\n")
        self.aendere("runtime/src/pkg/b.py", b"b = 1\n", spur=False)
        hub = self.hub()
        b = self.bericht(hub)
        self.assertEqual((b["anzahl_harness"], b["anzahl_sonst"]), (1, 1))
        self.assertIn("hat die Harness 1 Programmdatei geändert", b["text"])
        self.assertIn("du in dieser Fassung nicht gesehen hast. Sie laufen ab jetzt.", b["text"])
        self.assertIn("1 weitere ungesehene Datei ohne Spur", b["text"])
        self.assertEqual(b["pfade"], ["runtime/src/pkg/a.py · Sitzung S-0000000A · Weg aufgabe"])
        self.assertIn("CODE_STAND.bat sedra-entwicklung --zeigen", b["konsole"])
        self.assertEqual(self.audit[-1], ("STARTBERICHT", {"anzahl_harness": 1, "anzahl_sonst": 1}))

    def test_nur_unter_runtime_src_nicht_ein_test_oder_script(self):
        (self.wurzel / "tools").mkdir()
        self.aendere("tools/skript.py", b"x = 1\n")
        self.assertIsNone(self.bericht(self.hub()))

    def test_eintrag_im_posteingang_nur_zur_kenntnis_und_klasse_n(self):
        self.aendere("runtime/src/pkg/a.py", b"a = 2\n")
        hub = self.hub()
        self.bericht(hub)
        [d] = [x for x in hub.decisions_view()["items"] if x["kind"] == "startbericht"]
        self.assertEqual((d["id"], d["ways"], d["gate_id"]), ("startbericht", ["zur_kenntnis"], None))
        self.assertIn("Sie laufen ab jetzt", d["describe"])
        self.assertEqual(ARTEN["startbericht"], N)
        self.assertEqual(klasse("startbericht", "zur_kenntnis", {}), N)

    def test_zur_kenntnis_macht_nichts_gesehen_und_schreibt_audit(self):
        self.aendere("runtime/src/pkg/a.py", b"a = 2\n")
        hub = self.hub()
        self.bericht(hub)
        out = hub.decide({"id": "startbericht", "way": "zur_kenntnis"})
        self.assertEqual(out["status"], "answered")
        self.assertEqual([x for x in hub.decisions_view()["items"] if x["kind"] == "startbericht"], [])
        self.assertIn("STARTBERICHT_GELESEN", [e for e, _p in self.audit])
        self.assertEqual(len(self.cs.ungesehen()), 1, "die Datei ist weiter ungesehen: Läufe brauchen die Code-Karte")

    def test_ohne_code_stand_im_projekt_kein_scan_beim_start(self):
        import shutil
        shutil.rmtree(self.root / "runtime_data" / "harness" / "code_stand")
        self.aendere("runtime/src/pkg/a.py", b"a = 2\n", spur=False)
        self.assertIsNone(self.bericht(self.hub()))

    def test_decisions_helfer(self):
        d = desk_decisions.startbericht_decision({"text": "t", "pfade": ["a"], "zeit": "z", "konsole": "k", "anzahl_harness": 1, "anzahl_sonst": 0})
        self.assertEqual((d["kind"], d["ways"], d["risks"]), ("startbericht", ["zur_kenntnis"], ["a"]))
        self.assertEqual(json.dumps(d["binding"], sort_keys=True), '{"anzahl_harness": 1, "anzahl_sonst": 0}')


if __name__ == "__main__":
    unittest.main()
