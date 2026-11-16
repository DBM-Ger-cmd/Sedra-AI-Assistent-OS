"""G2-09 (SPEC_APPS_v1_O3PLUS_G9_G2): die Vorschau der Oberfläche als Prüfserver in einem eigenen Prozess – Start mit leerem Prüfprojekt, eigener Port, keine Schlüssel des Betriebs; Adresse,
Ende (Wunsch, Zeit, nächster Start, Sammelkarte); ein echter Prozess startet, antwortet und endet. Die Route ist ein geschützter Weg."""
import http.client
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.harness import pruefserver
from sedra_runtime.harness.pruefserver import Pruefserver, PruefserverFehler

RUNTIME = Path(__file__).resolve().parents[1]
QUELLEN = RUNTIME / "src"
ARCH = sorted((RUNTIME.parent / "architecture").glob("SEDRA_Architecture_v*"))[-1]


class FalscherProzess:
    """Ein Prozess, der eine Banner-Zeile ausgibt (oder nicht) und sich beenden lässt."""
    def __init__(self, zeilen, argv=None, env=None, cwd=None):
        self.stdout = iter(zeilen)
        self.argv, self.env, self.cwd = argv, env, cwd
        self.pid, self.beendet, self.getoetet = 4242, False, False

    def poll(self):
        return 0 if self.beendet else None

    def terminate(self):
        self.beendet = True

    def kill(self):
        self.beendet = self.getoetet = True

    def wait(self, timeout=None):
        return 0


class Mit(unittest.TestCase):
    BANNER = ["SEDRA Desktop (UIX): http://127.0.0.1:50123/?token=abc\n", "Loopback-only.\n"]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pruef-")
        self.addCleanup(self.tmp.cleanup)
        self.ablage = Path(self.tmp.name) / "pruef"
        self.prozesse, self.audit = [], []

    def popen(self, zeilen=None):
        def f(argv, **kw):
            p = FalscherProzess(self.BANNER if zeilen is None else zeilen, argv, kw.get("env"), kw.get("cwd"))
            self.prozesse.append(p)
            return p
        return f

    def server(self, **kw):
        kw.setdefault("popen", self.popen())
        s = Pruefserver(self.ablage, ARCH, QUELLEN, audit=lambda e, p: self.audit.append((e, p)), start_s=2, **kw)
        self.addCleanup(s.beenden)
        return s

    def test_start_nennt_die_adresse_und_startet_einen_eigenen_prozess_im_leeren_projekt(self):
        s = self.server()
        with mock.patch.dict(os.environ, {"SEDRA_SECRET_NVIDIA_API_KEY": "geheim", "NVIDIA_API_KEY": "geheim2", "ANTHROPIC_API_KEY": "geheim3", "GITHUB_TOKEN": "geheim4",
                                          "SEDRA_ANDERES": "wird nicht vererbt", "PYTHONPATH": "C:\\fremd", "PATH": "C:\\pfad"}):
            info = s.starten("harness")
        self.assertEqual((info["laeuft"], info["adresse"], info["shell"], info["pid"]), (True, "http://127.0.0.1:50123/?token=abc", "harness", 4242))
        p = self.prozesse[0]
        self.assertIn("-m", p.argv)
        self.assertIn("sedra_runtime.uix_server", p.argv)
        self.assertEqual(p.argv[p.argv.index("--port") + 1], "0", "eigener Port")
        self.assertEqual(p.argv[p.argv.index("--shell") + 1], "harness")
        self.assertEqual(p.argv[p.argv.index("--architecture") + 1], str(ARCH))
        projekt = Path(p.argv[p.argv.index("--root") + 1])
        self.assertTrue(projekt.is_dir() and projekt.parent == self.ablage, "frisches Prüfprojekt unter der Ablage")
        self.assertEqual(list(projekt.iterdir()), [], "leer: kein Arbeitsstand, keine Entscheidungen, keine Sitzungen")
        for name in ("SEDRA_SECRET_NVIDIA_API_KEY", "NVIDIA_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN", "SEDRA_ANDERES"):
            self.assertNotIn(name, p.env, f"{name}: Positivliste, nichts Fremdes wird vererbt – auch kein Schlüssel unter anderem Namen")
        self.assertEqual(p.env.get("PATH"), "C:\\pfad", "was ein Python-Prozess braucht, kommt mit")
        self.assertEqual(p.env["PYTHONPATH"], str(QUELLEN), "nur die Quellen des Betriebs, kein fremdes PYTHONPATH")
        self.assertEqual(p.env["PYTHONIOENCODING"], "utf-8")
        self.assertLessEqual({k.upper() for k in p.env}, pruefserver.UMGEBUNG_ERLAUBT | {"PYTHONPATH", "PYTHONIOENCODING"}, "nichts außerhalb der Positivliste")
        self.assertEqual(s.status()["adresse"], info["adresse"])
        self.assertEqual(self.audit[0][0], "HARNESS_VORSCHAU_START")

    def test_ohne_shell_kein_shell_argument_und_eine_ungueltige_wird_abgewiesen(self):
        s = self.server()
        s.starten()
        self.assertNotIn("--shell", self.prozesse[0].argv)
        for schlecht in ("../x", "Harness", "a b", "x" * 41, 5):
            with self.subTest(schlecht), self.assertRaises(PruefserverFehler):
                s.starten(schlecht)

    def test_beenden_stoppt_den_prozess_und_loescht_das_pruefprojekt(self):
        s = self.server()
        s.starten()
        projekt = Path(self.prozesse[0].argv[self.prozesse[0].argv.index("--root") + 1])
        self.assertTrue(s.beenden("wunsch"))
        self.assertTrue(self.prozesse[0].beendet)
        self.assertFalse(projekt.exists())
        self.assertEqual(s.status(), {"laeuft": False})
        self.assertFalse(s.beenden("noch einmal"), "nichts mehr da")
        self.assertIn(("HARNESS_VORSCHAU_ENDE", {"grund": "wunsch"}), self.audit)

    def test_hoechstens_einer_zugleich(self):
        s = self.server()
        s.starten()
        s.starten()
        self.assertEqual([p.beendet for p in self.prozesse], [True, False])
        self.assertEqual(len([d for d in self.ablage.iterdir()]), 1)

    def test_ende_nach_der_dauer(self):
        s = self.server(dauer_s=0.2)
        s.starten()
        for _ in range(50):
            if not s.status()["laeuft"]:
                break
            time.sleep(0.05)
        self.assertEqual(s.status(), {"laeuft": False})
        self.assertTrue(self.prozesse[0].beendet)
        self.assertIn(("HARNESS_VORSCHAU_ENDE", {"grund": "zeit"}), self.audit)

    def test_ohne_adresse_scheitert_der_start_sauber(self):
        s = self.server(popen=self.popen(["Traceback …\n"]))
        with self.assertRaises(PruefserverFehler) as ctx:
            s.starten()
        self.assertIn("start_ohne_adresse", str(ctx.exception))
        self.assertTrue(self.prozesse[0].beendet)
        self.assertEqual(list(self.ablage.iterdir()), [], "das Prüfprojekt ist wieder weg")
        self.assertEqual(s.status(), {"laeuft": False})

    def test_ein_von_selbst_beendeter_prozess_gilt_nicht_mehr_als_laufend(self):
        s = self.server()
        s.starten()
        self.prozesse[0].beendet = True
        self.assertEqual(s.status(), {"laeuft": False})
        self.assertEqual(list(self.ablage.iterdir()), [])


class EchterProzess(unittest.TestCase):
    def test_prozess_startet_antwortet_und_endet(self):
        tmp = tempfile.TemporaryDirectory(prefix="pruef-echt-")
        self.addCleanup(tmp.cleanup)
        ablage = Path(tmp.name) / "pruef"
        s = Pruefserver(ablage, ARCH, QUELLEN, start_s=120)
        self.addCleanup(s.beenden)
        info = s.starten()
        self.assertTrue(info["adresse"].startswith("http://127.0.0.1:"))
        host, port = info["adresse"].split("//")[1].split("/")[0].split(":")
        self.assertNotEqual(int(port), 0)
        c = http.client.HTTPConnection(host, int(port), timeout=20)
        c.request("GET", "/" + info["adresse"].split("/", 3)[3])
        self.assertEqual(c.getresponse().status, 200, "der Prüfserver antwortet")
        c.close()
        pid_proc = s._proc
        self.assertTrue(s.beenden("test"))
        self.assertIsNotNone(pid_proc.poll(), "der Prozess ist beendet")
        self.assertEqual(list(ablage.iterdir()), [], "das Prüfprojekt ist gelöscht")


class Weg(unittest.TestCase):
    def test_die_route_ist_ein_geschuetzter_weg_mit_einstufung(self):
        from sedra_runtime.desk import freigabeklasse as fk
        from sedra_runtime.harness import api
        self.assertTrue(api.GESCHUETZT.fullmatch("/api/harness/oberflaeche/vorschau"))
        self.assertTrue(api.GESCHUETZT.fullmatch("/api/harness/oberflaeche/vorschau_ende"))
        self.assertTrue(api.WEG.fullmatch("/api/harness/oberflaeche/vorschau"))
        self.assertEqual(fk.ROUTEN_HARNESS["POST oberflaeche/vorschau"][:2], ("handlung", "N"))
        self.assertIn("POST oberflaeche/vorschau_ende", fk.ROUTEN_HARNESS)


class WegMitHub(unittest.TestCase):
    def test_route_startet_beendet_und_hub_close_beendet_den_pruefserver(self):
        from sedra_runtime.uix_server import UIXHub
        tmp = tempfile.TemporaryDirectory(prefix="pruef-hub-")
        self.addCleanup(tmp.cleanup)
        hub = UIXHub(Path(tmp.name), ARCH)
        fertig = []

        def popen(argv, **kw):
            p = FalscherProzess(Mit.BANNER, argv, kw.get("env"), kw.get("cwd"))
            fertig.append(p)
            return p
        ps = Pruefserver(Path(tmp.name) / "pruef", ARCH, QUELLEN, popen=popen, start_s=2)
        hub.harness.__dict__["_pruefserver"] = ps
        st, antwort = hub.harness.handle("POST", "/api/harness/oberflaeche/vorschau", "", {"shell": "harness"})
        self.assertEqual((st, antwort["laeuft"], antwort["shell"]), (200, True, "harness"))
        self.assertEqual(hub.harness.handle("GET", "/api/harness/oberflaeche/vorschau", "")[1]["adresse"], antwort["adresse"])
        self.assertEqual(hub.harness.handle("POST", "/api/harness/oberflaeche/vorschau_ende", "", {})[1], {"beendet": True})
        self.assertTrue(fertig[0].beendet)
        with self.assertRaises(ValueError):
            hub.harness.handle("POST", "/api/harness/oberflaeche/vorschau", "", {"shell": "../x"})
        hub.harness.handle("POST", "/api/harness/oberflaeche/vorschau", "", {})
        self.assertFalse(fertig[1].beendet)
        hub.close()
        self.assertTrue(fertig[1].beendet, "mit dem Betriebsserver endet der Prüfserver")


if __name__ == "__main__":
    unittest.main()
