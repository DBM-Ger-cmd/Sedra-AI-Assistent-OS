"""Der Sedra-Modell-Router (models/router_verwaltung.py): startet den llama-server im Router-Modus selbst, schreibt die Modellliste, startet neu,
wenn sich der Abschnitt eines Modells aendert, und fasst einen fremden Router nie an. Kein echter Prozess: Popen und HTTP sind ersetzt."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.models.llama_server_runtime import build_command
from guppi_runtime.models.router_verwaltung import RouterVerwaltung, abschnitt_aus_argv, preset_text
from guppi_runtime.models.runtime_control import RuntimeControlError
from host_isolation import setUpModule, tearDownModule  # noqa: F401


class FakeProc:
    def __init__(self, welt, argv):
        self.pid, self.argv, self.welt = 4242, argv, welt
    def poll(self):
        return None if self.welt["laeuft"] else 1


class Welt:
    """Was ein Router waere: laeuft oder nicht; Popen startet ihn, kill beendet ihn."""
    def __init__(self, laeuft=False):
        self.d = {"laeuft": laeuft}
        self.starts, self.kills = [], []
    def popen(self, argv, **kw):
        self.starts.append(list(argv)); self.d["laeuft"] = True
        return FakeProc(self.d, argv)
    def get_json(self, url, timeout=3):
        if not self.d["laeuft"]: raise OSError("refused")
        return 200, {}
    def kill(self, proc):
        self.kills.append(proc.pid); self.d["laeuft"] = False


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.welt = Welt()
        self.v = self.neu()

    def neu(self, **kw):
        return RouterVerwaltung(endpoint="http://127.0.0.1:8090", executable_dir=self.tmp.name, vendor_dir=None, ordner=Path(self.tmp.name) / "router",
                                popen=self.welt.popen, get_json=self.welt.get_json, sleep=lambda s: None, kill=self.welt.kill, pid_lebt=lambda p: False, **kw)

    def abschnitt(self, c="65536"):
        return {"model": "I:/m/a.gguf", "c": c, "np": "1", "ngl": "99"}

    def test_laden_ohne_router_startet_ihn_mit_der_modellliste(self):
        self.assertEqual(self.v.bereitstellen("qwen", self.abschnitt()), "gestartet")
        argv = self.welt.starts[0]
        self.assertIn("--models-preset", argv); self.assertIn("--models-max", argv)
        self.assertEqual(argv[argv.index("--sleep-idle-seconds") + 1], "900")
        ini = self.v.preset.read_text(encoding="utf-8")
        self.assertIn("[qwen]", ini); self.assertIn("c = 65536", ini)
        self.assertTrue(self.v.status()["eigen"])

    def test_gleicher_abschnitt_startet_nicht_neu_ein_anderes_fenster_schon(self):
        self.v.bereitstellen("qwen", self.abschnitt())
        self.assertEqual(self.v.bereitstellen("qwen", self.abschnitt()), "bereit")
        self.assertEqual(len(self.welt.starts), 1)
        self.assertEqual(self.v.bereitstellen("qwen", self.abschnitt("131072")), "gestartet")
        self.assertEqual((len(self.welt.starts), self.welt.kills), (2, [4242]))
        self.assertIn("c = 131072", self.v.preset.read_text(encoding="utf-8"))

    def test_ein_fremder_router_wird_nicht_angefasst(self):
        self.welt.d["laeuft"] = True                             # laeuft, aber Sedra hat ihn nicht gestartet
        self.assertEqual(self.v.bereitstellen("qwen", self.abschnitt()), "fremd")
        self.assertEqual((self.welt.starts, self.welt.kills), ([], []))
        with self.assertRaises(RuntimeControlError) as k:
            self.v.beenden()
        self.assertIn("router_fremd", str(k.exception))

    def test_ohne_automatik_bleibt_er_aus(self):
        self.v.optionen_setzen({"auto_start": False})
        self.assertEqual(self.v.bereitstellen("qwen", self.abschnitt()), "aus")
        self.assertEqual(self.welt.starts, [])

    def test_optionen_werden_geprueft_und_gemerkt(self):
        self.v.optionen_setzen({"models_max": 2, "sleep_idle_s": 0})
        self.assertEqual(self.neu().optionen(), {"auto_start": True, "models_max": 2, "sleep_idle_s": 0})
        for schlecht in ({"models_max": 0}, {"models_max": "2"}, {"sleep_idle_s": -1}, {"unbekannt": 1}):
            with self.assertRaises(ValueError, msg=str(schlecht)):
                self.v.optionen_setzen(schlecht)

    def test_die_liste_bleibt_beim_naechsten_laden_und_ergaenzen_kennt_alle_rezepte(self):
        self.v.bereitstellen("a", self.abschnitt())
        self.v.bereitstellen("b", self.abschnitt())
        ini = self.v.preset.read_text(encoding="utf-8")
        self.assertIn("[a]", ini); self.assertIn("[b]", ini)
        self.assertEqual(self.v.ergaenzen({"a": {"c": "1"}, "z": {"c": "2"}}), ["z"])       # a bleibt wie es ist
        self.assertEqual(self.neu()._abschnitte["a"]["c"], "65536")

    def test_beenden_stoppt_den_eigenen_router_und_start_ohne_modelle_ist_abgelehnt(self):
        with self.assertRaises(RuntimeControlError):
            self.v.starten()
        self.v.bereitstellen("a", self.abschnitt())
        self.assertFalse(self.v.beenden()["laeuft"])

    def test_ein_frueher_von_sedra_gestarteter_router_wird_nach_einem_neustart_wiedergefunden(self):
        self.v.bereitstellen("a", self.abschnitt())
        neu = RouterVerwaltung(endpoint="http://127.0.0.1:8090", executable_dir=self.tmp.name, vendor_dir=None, ordner=Path(self.tmp.name) / "router",
                               popen=self.welt.popen, get_json=self.welt.get_json, sleep=lambda s: None, kill=self.welt.kill, pid_lebt=lambda p: p == 4242)
        self.assertTrue(neu.status()["eigen"])                       # die Nummer steht in router.pid, der Prozess lebt
        self.assertEqual(neu.bereitstellen("a", self.abschnitt()), "bereit")
        self.assertEqual(neu.bereitstellen("a", self.abschnitt("131072")), "gestartet")
        self.assertEqual(self.welt.kills, [4242])

    def test_abschnitt_aus_den_argumenten_des_eigenen_servers(self):
        gguf = Path(self.tmp.name) / "m.gguf"; gguf.write_bytes(b"x")
        argv = build_command("llama-server.exe", gguf=gguf, context=131072, host="127.0.0.1", port=8089, alias="x", parallel=2, n_cpu_moe=28,
                             cache_ram=1024, jinja=False)
        kv = abschnitt_aus_argv(argv)
        self.assertEqual((kv["c"], kv["np"], kv["n-cpu-moe"], kv["cache-ram"], kv["jinja"], kv["model"]), ("131072", "2", "28", "1024", "false", str(gguf)))
        for fremd in ("host", "port", "alias", "no-webui", "no-mmproj"):
            self.assertNotIn(fremd, kv)
        self.assertIn("[x]", preset_text({"x": kv}))


if __name__ == "__main__":
    unittest.main()
