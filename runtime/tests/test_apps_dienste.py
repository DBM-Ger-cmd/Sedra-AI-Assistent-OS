"""AM4-05 bis AM4-10 (SPEC_APPS_v1_AM4_DIENSTE Teil B): Dienst-Apps – Prüfung des Blocks `dienst`, Start ohne Shell mit minimaler Umgebung, eigener Token, Stoppen (erst bitten, dann beenden),
Absturz und Neustart höchstens 3 Mal je Stunde, rollierendes Protokoll. Ein echtes Python-Skript als Fake-Dienst."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk.dienste import Dienste, ENV_ERLAUBT, pruefe_dienst

SKRIPT = '''import json, os, sys, time
modus = sys.argv[1] if len(sys.argv) > 1 else "warten"
print("ENV " + json.dumps(sorted(os.environ)), flush=True)
datei = os.environ.get("SEDRA_DIENST_TOKEN_DATEI")
print("TOKEN_DATEI " + str(os.path.isfile(datei)), flush=True)
print("PORT " + os.environ.get("SEDRA_DESK_PORT", ""), flush=True)
if modus == "absturz":
    sys.exit(3)
if modus == "laut":
    for i in range(400):
        print("zeile %d " % i + "x" * 80, flush=True)
while True:
    time.sleep(0.2)
'''


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am4-dienste-")
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.app = t / "app"
        self.app.mkdir()
        (self.app / "dienst.py").write_text(SKRIPT, encoding="utf-8")
        self.root = t / "projekt"
        self.audit = []
        self.d = Dienste(self.root, port=4711, audit=lambda e, p: self.audit.append((e, p)))
        self.addCleanup(self.d.stop_alle)

    def block(self, **mehr):
        b = {"start": ["dienst.py"], "ort": "host", "neustart": "nie", "protokoll_max": 512}
        b.update(mehr)
        return pruefe_dienst(b, "CAPTAIN", self.app)[0]

    def log(self, app_id="x"):
        return (self.root / "runtime_data" / "dienste" / app_id / "protokoll.txt")

    def warte(self, bedingung, s=15):
        ende = time.time() + s
        while time.time() < ende:
            if bedingung():
                return True
            time.sleep(0.1)
        return False

    def arten(self):
        return [e for e, _p in self.audit]


class Pruefung(Basis):
    def fehler(self, block, trust="CAPTAIN"):
        return pruefe_dienst(block, trust, self.app)[1]

    def test_gueltiger_block_und_vorgaben(self):
        b, f = pruefe_dienst({"start": ["dienst.py", "--ruhig"]}, "CAPTAIN", self.app)
        self.assertEqual((f, b), ([], {"start": ["dienst.py", "--ruhig"], "ort": "host", "neustart": "nie", "protokoll_max": 512}))

    def test_start_pfad_regeln(self):
        for start, grund in ((["../x.py"], "dienst_start_pfad"), (["/etc/x.py"], "dienst_start_pfad"), (["C:\\x.py"], "dienst_start_pfad"), (["unter/../../x.py"], "dienst_start_pfad"),
                             (["gibtsnicht.py"], "dienst_start_fehlt"), (["dienst.exe"], "dienst_start_art"), (["dienst.py; rm -rf"], "dienst_start_shellzeichen"),
                             (["dienst.py", "a|b"], "dienst_start_shellzeichen"), ([], "dienst_start_ungueltig"), ("dienst.py", "dienst_start_ungueltig"), ([1], "dienst_start_ungueltig")):
            with self.subTest(start=start):
                self.assertIn(grund, self.fehler({"start": start}))

    def test_ort_und_vertrauen(self):
        self.assertIn("dienst_fremd_nur_microvm", self.fehler({"start": ["dienst.py"]}, "COMMUNITY"))
        self.assertIn("dienst_fremd_nur_microvm", self.fehler({"start": ["dienst.py"], "ort": "microvm"}, "COMMUNITY"))
        self.assertIn("dienst_microvm_nicht_verfuegbar", self.fehler({"start": ["dienst.py"], "ort": "microvm"}, "CAPTAIN"))
        self.assertIn("dienst_host_vertrauen", self.fehler({"start": ["dienst.py"]}, "CORE"))
        self.assertEqual(self.fehler({"start": ["dienst.py"]}, "SEDRA_BUILT"), [])
        self.assertIn("dienst_ort_ungueltig", self.fehler({"start": ["dienst.py"], "ort": "wolke"}))

    def test_neustart_protokoll_und_unbekannte_felder(self):
        self.assertIn("dienst_neustart_ungueltig", self.fehler({"start": ["dienst.py"], "neustart": "immer"}))
        for kb in (0, 5, 5000, "viel", True):
            self.assertIn("dienst_protokoll_max_ungueltig", self.fehler({"start": ["dienst.py"], "protokoll_max": kb}), kb)
        self.assertIn("dienst_unbekanntes_feld:netz", self.fehler({"start": ["dienst.py"], "netz": "ja"}))
        self.assertEqual(self.fehler(None), ["dienst_block_fehlt"])

    def test_verknuepfung_aus_dem_app_ordner_hinaus_wird_abgewiesen(self):
        draussen = Path(self.tmp.name) / "draussen.py"
        draussen.write_text("x", encoding="utf-8")
        try:
            os.symlink(draussen, self.app / "link.py")
        except (OSError, NotImplementedError):
            self.skipTest("keine Verknüpfungen")
        self.assertIn("dienst_start_pfad", self.fehler({"start": ["link.py"]}))


class Laufen(Basis):
    def test_start_ohne_shell_mit_minimaler_umgebung_und_eigenem_token(self):
        r = self.d.start("x", self.app, self.block(), "CAPTAIN")
        self.assertEqual(r["id"], "x")
        self.assertTrue(self.warte(lambda: self.log().is_file() and "PORT" in self.log().read_text(encoding="utf-8")))
        text = self.log().read_text(encoding="utf-8")
        umgebung = json.loads(next(z for z in text.splitlines() if z.startswith("ENV ")).split(" ", 1)[1])
        fremd = [k for k in umgebung if k.upper() not in {e.upper() for e in ENV_ERLAUBT} and not k.upper().startswith(("PYTHON", "SYSTEM", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "LANG", "LC_", "HOME"))]
        self.assertEqual(fremd, [], "keine fremden Umgebungsvariablen (Schlüssel, Token anderer Dienste)")
        self.assertIn("SEDRA_DIENST_TOKEN_DATEI", umgebung)
        self.assertIn("TOKEN_DATEI True", text)
        self.assertIn("PORT 4711", text)
        self.assertEqual(self.arten(), ["DIENST_GESTARTET"])
        self.assertEqual(self.audit[0][1]["ort"], "host")

    def test_token_gehoert_dem_dienst_und_ist_nach_dem_stopp_ungueltig(self):
        self.d.start("x", self.app, self.block(), "CAPTAIN")
        token = self.d.laufend["x"]["token"]
        self.assertEqual(self.d.klasse(token), "dienst:x")
        self.assertIsNone(self.d.klasse("falsch"))
        self.assertIsNone(self.d.klasse(None))
        datei = self.root / "runtime_data" / "dienste" / "x" / "token.json"
        self.assertTrue(datei.is_file())
        self.assertNotIn(token, datei.read_text(encoding="utf-8") if sys.platform == "win32" else "", "unter Windows ist er mit der DPAPI geschützt")
        self.assertTrue(self.d.stop("x", "captain", warte=5))
        self.assertIsNone(self.d.klasse(token), "AM4-06: sofort ungültig")
        self.assertFalse(datei.exists())
        self.assertEqual(self.arten(), ["DIENST_GESTARTET", "DIENST_TOKEN_ENTZOGEN", "DIENST_GESTOPPT"])
        self.assertEqual(self.audit[-1][1], {"id": "x", "grund": "captain"})
        self.assertEqual(self.d.zustand()["x"], {"laeuft": False, "pid": None, "seit": None, "grund": "captain"})

    def test_zwei_dienste_zwei_tokens(self):
        self.d.start("a", self.app, self.block(), "CAPTAIN")
        self.d.start("b", self.app, self.block(), "SEDRA_BUILT")
        ta, tb = self.d.laufend["a"]["token"], self.d.laufend["b"]["token"]
        self.assertNotEqual(ta, tb)
        self.assertEqual((self.d.klasse(ta), self.d.klasse(tb)), ("dienst:a", "dienst:b"))

    def test_doppelter_start_und_fremdes_vertrauen_werden_abgewiesen(self):
        self.d.start("x", self.app, self.block(), "CAPTAIN")
        with self.assertRaises(ValueError) as e:
            self.d.start("x", self.app, self.block(), "CAPTAIN")
        self.assertIn("dienst_laeuft_schon", str(e.exception))
        with self.assertRaises(ValueError):
            self.d.start("y", self.app, self.block(), "COMMUNITY")
        with self.assertRaises(ValueError):
            self.d.start("y", self.app, dict(self.block(), ort="microvm"), "CAPTAIN")

    def test_stoppen_ohne_laufenden_dienst(self):
        self.assertFalse(self.d.stop("gibtsnicht"))

    def test_protokoll_ist_rollierend_begrenzt_und_nie_im_audit(self):
        self.d.start("x", self.app, dict(self.block(protokoll_max=16), start=["dienst.py", "laut"]), "CAPTAIN")
        self.assertTrue(self.warte(lambda: self.log().is_file() and self.log().stat().st_size > 1000))
        time.sleep(1.0)
        self.assertLessEqual(self.log().stat().st_size, 16 * 1024 + 200)
        self.assertNotIn("zeile", json.dumps(self.audit))


class Absturz(Basis):
    def test_absturz_wird_gemeldet_und_der_token_entzogen(self):
        self.d.start("x", self.app, self.block(start=["dienst.py", "absturz"]), "CAPTAIN")
        token = self.d.laufend["x"]["token"]
        self.assertTrue(self.warte(lambda: self.d.laufend["x"]["proc"].poll() is not None))
        self.assertEqual(self.d.pruefen(), ["x"])
        self.assertIsNone(self.d.klasse(token))
        self.assertIn(("DIENST_ABGESTUERZT", {"id": "x", "exitcode": 3}), self.audit)
        self.assertEqual(self.d.zustand()["x"]["grund"], "abgestuerzt:3")
        self.assertNotIn("x", self.d.laufend, "neustart: nie")

    def test_neustart_bei_fehler_hoechstens_drei_mal_je_stunde(self):
        jetzt = [1000.0]
        self.d = Dienste(self.root, port=1, audit=lambda e, p: self.audit.append((e, p)), uhr=lambda: jetzt[0])
        self.addCleanup(self.d.stop_alle)
        block = self.block(start=["dienst.py", "absturz"], neustart="bei_fehler")
        self.d.start("x", self.app, block, "CAPTAIN")
        starts = 1
        for runde in range(5):
            self.assertTrue(self.warte(lambda: "x" not in self.d.laufend or self.d.laufend["x"]["proc"].poll() is not None))
            jetzt[0] += 60
            self.d.pruefen()
            if "x" in self.d.laufend:
                starts += 1
        self.assertEqual(starts, 4, "der erste Start plus drei Neustarts")
        self.assertEqual(self.d.zustand()["x"]["grund"], "zu_oft_abgestuerzt")
        self.assertIn(("DIENST_GESTOPPT", {"id": "x", "grund": "zu_oft_abgestuerzt"}), self.audit)

    def test_nach_einer_stunde_zaehlt_der_neustart_wieder(self):
        jetzt = [1000.0]
        self.d = Dienste(self.root, port=1, audit=lambda e, p: self.audit.append((e, p)), uhr=lambda: jetzt[0])
        self.addCleanup(self.d.stop_alle)
        self.d.neustarts["x"] = [1000.0 - 4000, 1000.0 - 3900, 1000.0 - 3700]
        self.d.start("x", self.app, self.block(start=["dienst.py", "absturz"], neustart="bei_fehler"), "CAPTAIN")
        self.assertTrue(self.warte(lambda: self.d.laufend["x"]["proc"].poll() is not None))
        self.d.pruefen()
        self.assertIn("x", self.d.laufend, "die alten Neustarts sind über eine Stunde her")


if __name__ == "__main__":
    unittest.main()
