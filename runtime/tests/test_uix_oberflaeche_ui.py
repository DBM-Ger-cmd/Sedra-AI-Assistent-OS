"""O3 G2-05 (Sammelkarte am Ende einer Aufgabe), G1-06 (Formular für `oberflaeche`), G7-05 (Einstellungen: Zurücknehmen): die Oberfläche der Harness-Shell und die Verknüpfung am Ende einer Aufgabe."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.harness import antraege
from sedra_runtime.uix_server import UIXHub

from test_uix_harness_api import ARCH

NODE = shutil.which("node")
HARNESS = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix" / "shells" / "harness"


class AmEnde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="o3-ende-")
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.hub = UIXHub(t / "project", ARCH)
        self.addCleanup(self.hub.close)
        uix = t / "uix"
        (uix / "tools").mkdir(parents=True)
        self.datei = uix / "tools" / "a.js"
        self.datei.write_bytes(b"alt\n")
        self.hub.oberflaeche.uix = uix.resolve()

    def halten(self):
        self.hub.oberflaeche.zurueckhalten(self.datei, "S-1", "T-1")
        self.datei.write_bytes(b"neu\n")

    def melden(self, zustand):
        with mock.patch.object(antraege, "oberflaeche_antrag", return_value={"mission_id": "M-1"}) as antrag:
            self.hub.harness._melden("harness.aufgabe", {"id": "T-1", "zustand": zustand})
        return antrag

    def test_ende_einer_aufgabe_mit_zurueckgehaltenen_dateien_legt_die_sammelkarte_vor(self):
        self.halten()
        for zustand in ("erledigt", "abgelaufen", "erschoepft", "zurueckgenommen"):
            with self.subTest(zustand=zustand):
                self.melden(zustand).assert_called_once()

    def test_laufende_aufgabe_und_nichts_zurueckgehalten_legt_nichts_vor(self):
        self.melden("erledigt").assert_not_called()
        self.halten()
        self.melden("aktiv").assert_not_called()

    def test_ein_fehler_beim_vorlegen_bleibt_still(self):
        self.halten()
        with mock.patch.object(antraege, "oberflaeche_antrag", side_effect=ValueError("zu_gross")):
            self.hub.harness._melden("harness.aufgabe", {"id": "T-1", "zustand": "erledigt"})


@unittest.skipUnless(NODE, "node fehlt")
class Oberflaeche(unittest.TestCase):
    def test_reine_hilfen(self):
        skript = ("const o = require(%s); process.stdout.write(JSON.stringify({"
                  "a: o.dateiText({neu: true, rel: 'tools/n.js', sitzung: 'S-1'}), b: o.dateiText({geloescht: true, rel: 'x.js'}), c: o.dateiText({rel: 'y.js'}),"
                  "u: o.uebernahmeText({id: 'U-1', zeit: '2026-11-11T20:30:00+01:00', dateien: [1, 2], kanal: 'konsole'}),"
                  "z1: o.zuruecknehmenSatz({hergestellt: ['a'], verworfen: ['b'], geaendert: ['c'], fehlt: ['d']}), z2: o.zuruecknehmenSatz({}), satz: o.SATZ}));")
        out = subprocess.run([NODE, "-e", skript % json.dumps(str(HARNESS / "oberflaeche.js"))], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        r = json.loads(out.stdout)
        self.assertEqual((r["a"], r["b"], r["c"]), ("neu tools/n.js · Sitzung S-1", "gelöscht x.js", "geändert y.js"))
        self.assertEqual(r["u"], "U-1 · 2026-11-11 20:30 · 2 Datei(en) · konsole")
        for teil in ("1 Datei(en) auf die alte Fassung gebracht", "1 neue Datei(en) nach verworfen/", "seit der Übernahme geändert und deshalb gelassen: c", "alte Fassung nicht mehr gespeichert: d"):
            self.assertIn(teil, r["z1"])
        self.assertEqual(r["z2"], "Nichts zu tun.")
        self.assertIn("mit allen Rechten", r["satz"])
        self.assertIn("CODE_STAND.bat", r["satz"])

    def test_einhaengung_und_formular(self):
        yaml = (HARNESS / "shell.yaml").read_text(encoding="utf-8")
        self.assertIn("oberflaeche.js", yaml)
        self.assertLess(yaml.index("erlaubnisse.js"), yaml.index("oberflaeche.js"))
        einst = (HARNESS / "einstellungen.js").read_text(encoding="utf-8")
        self.assertIn("H().oberflaeche.flaeche(S, box)", einst)
        auf = (HARNESS / "aufgabe.js").read_text(encoding="utf-8")
        self.assertIn("oberflaeche: oberflaeche.value.split(',')", auf)
        self.assertIn("Code an diesen Stellen läuft in der Oberfläche mit allen Rechten der Seite – auch Freigaben.", auf, "G1-06: der Satz steht am Formular")
        self.assertIn("a.oberflaeche_hinweis", auf)
        for datei in ("oberflaeche.js", "aufgabe.js", "einstellungen.js"):
            self.assertLessEqual(len((HARNESS / datei).read_text(encoding="utf-8").splitlines()), 400, datei)
            self.assertNotIn("innerHTML", (HARNESS / datei).read_text(encoding="utf-8"), datei)


if __name__ == "__main__":
    unittest.main()
