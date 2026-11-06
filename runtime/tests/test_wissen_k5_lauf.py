"""K5-7 (SPEC_WISSEN_KERN_v1 WK-24; G2 K5 §2.7, D-K5-4, D-K5-6): die Erstaufnahme als Lauf der Harness. Der Lauf gleicht in Schritten ab, bettet
danach ein und meldet Fortschrittszeilen, die die Regel des Lauftyps liest; er hält `aufnahme.lock`, der Takt setzt so lange aus; ist die Sperre
belegt, endet der Lauf mit 3; ein abgebrochener Lauf gibt die Sperre frei und ein neuer macht ohne doppelte Abschnitte weiter; einen Einbett-Server,
den er selbst gestartet hat, beendet er. Der Lauftyp `wissen_aufnahme` steht gültig in harness_laeufe.yaml und nimmt nur Quell-IDs.
Ohne Modell, ohne Netz (Fake-Embedding), keine GPU."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.core.mission_lock import exclusive
from guppi_runtime.harness import lauf
from guppi_runtime.wissen import aufnahme, aufnahme_lauf
from wissen_fixture import FakeEmbedServer, freigeben, oeffnen

MD = "# Akte {n}\n\n## Vertrag\n\nLaufzeit {n} Jahre, Kündigung drei Monate.\n\n## Kontakt\n\nAnsprechpartner {n} im Einkauf.\n"
RUNTIME = Path(__file__).resolve().parents[1]


class Abbruch(Exception):
    pass


class Lauf(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wissen-k5-lauf-")
        self.addCleanup(self.tmp.cleanup)
        self.srv = FakeEmbedServer(lazy=True)
        self.srv.__enter__()
        self.addCleanup(self.srv.__exit__, None, None, None)
        self.akten = Path(self.tmp.name) / "akten"
        self.akten.mkdir()
        for n in range(1, 8):
            (self.akten / f"akte{n}.md").write_text(MD.format(n=n), encoding="utf-8")
        projekt = Path(self.tmp.name) / "projekt"
        (projekt / "local_config").mkdir(parents=True)
        (projekt / "local_config" / "wissen_wurzeln.yaml").write_text(
            f"wurzeln:\n  - {{id: akten, pfad: '{self.akten.as_posix()}', name: Akten, personenbezug: 1, stufe: 2}}\n", encoding="utf-8")
        self.sp = oeffnen(self.tmp.name, self.srv.port, server=self.srv)
        self.addCleanup(self.sp.schliessen)
        self.sp.konfig.dateien_je_schritt = 3
        self.q = freigeben(self.sp, "markdown", ".", wurzel="w:akten", stufe=2)["id"]
        self.zeilen = []

    def laufen(self, **kw):
        kw.setdefault("ausgabe", self.zeilen.append)
        kw.setdefault("schlaf", lambda s: None)
        return aufnahme_lauf.laufen(self.sp, self.q, **kw)

    def sperre(self):
        return exclusive(self.sp.pfad.parent / aufnahme.SPERRE)

    def test_lauf_gleicht_in_schritten_ab_und_bettet_ein(self):
        self.assertEqual(self.laufen(), 0)
        self.assertEqual(self.zeilen[-1], "fertig")
        stand = self.sp.dateien_stand(self.q)["summen"]
        self.assertEqual((stand["aufgenommen"], stand["offen"]), (7, 0))
        s = self.sp.stand()
        self.assertEqual(s["vektoren"], s["abschnitte"])
        abgleich = [z for z in self.zeilen if z.endswith("eingebettet –")]
        self.assertEqual(len(abgleich), 3, "7 Dateien zu 3 je Schritt")
        self.assertIn("Stand 21/100 · Dateien 3/7", abgleich[0])
        self.assertTrue(self.zeilen[-2].startswith("Stand 100/100 · Dateien 7/7"))
        regel = lauf.laden(RUNTIME / "config" / "harness_laeufe.yaml")["laeufe"]["wissen_aufnahme"]["fortschritt"]
        self.assertEqual(lauf.fortschritt_aus(self.zeilen, regel)["prozent"], 100, "die Regel liest die Zeilen, auch hinter „fertig“")
        self.assertEqual(lauf.fortschritt_aus(abgleich[:1], regel)["prozent"], 21)
        aktionen = [p["aktion"] for e, p in self.sp.test_audit.events if e == "WIS_AUFNAHME_LAUF"]
        self.assertEqual(aktionen, ["start", "ende"])
        prozesse = self.sp.test_starter.gestartet
        self.assertTrue(prozesse and all(p.beendet for p in prozesse), "den selbst gestarteten Einbett-Server beendet der Lauf")

    def test_laufender_server_bleibt_an(self):
        self.sp.einbetten_schritt()                                # der Server läuft schon (z. B. vom Takt der Oberfläche)
        prozesse = list(self.sp.test_starter.gestartet)
        self.assertEqual(self.laufen(), 0)
        self.assertEqual(self.sp.test_starter.gestartet, prozesse, "kein zweiter Server")
        self.assertFalse(any(p.beendet for p in prozesse), "einen fremden oder schon laufenden Server lässt der Lauf an")

    def test_sperre_zwischen_takt_und_lauf(self):
        with self.sperre():
            self.assertEqual(aufnahme.nachfuehren(self.sp), {"uebersprungen": "aufnahme_lauf"}, "der Takt setzt aus, solange der Lauf dran ist")
            self.assertEqual(self.laufen(warten_s=0), 3, "zwei Läufe gleichzeitig gibt es nicht")
        self.assertIn("belegt", self.zeilen[-1])
        self.assertNotIn("uebersprungen", aufnahme.nachfuehren(self.sp), "ohne Lauf taktet er wieder")

    def test_lauf_haelt_die_sperre_fuer_seine_dauer(self):
        gesehen = []

        def ausgabe(z):
            gesehen.append(aufnahme.nachfuehren(self.sp))
            self.zeilen.append(z)

        self.assertEqual(self.laufen(ausgabe=ausgabe), 0)
        self.assertTrue(gesehen and all(g == {"uebersprungen": "aufnahme_lauf"} for g in gesehen))
        with self.sperre():
            pass                                                   # am Ende wieder frei

    def test_abbruch_und_wiederaufnahme_ohne_doppelte_abschnitte(self):
        def abbrechen(z):
            self.zeilen.append(z)
            raise Abbruch

        with self.assertRaises(Abbruch):
            self.laufen(ausgabe=abbrechen)
        self.assertEqual(self.sp.dateien_stand(self.q)["summen"]["aufgenommen"], 3, "der erste Schritt ist drin")
        with self.sperre():
            pass                                                   # der Abbruch hat die Sperre freigegeben
        self.zeilen.clear()
        self.assertEqual(self.laufen(), 0)
        self.assertIn("Dateien 6/7", self.zeilen[0], "der neue Lauf macht beim nächsten Schritt weiter")
        n = self.sp.db.execute("SELECT count(*), count(DISTINCT datei || stelle) FROM abschnitte WHERE quelle = ?", (self.q,)).fetchone()
        self.assertEqual(n[0], n[1])
        self.assertEqual(n[0], 14)

    def test_unbekannte_oder_abgeschaltete_quelle(self):
        self.assertEqual(aufnahme_lauf.laufen(self.sp, "Q-00000000", ausgabe=self.zeilen.append), 2)
        self.assertIn("unbekannt", self.zeilen[-1])
        with self.sperre():
            pass

    def test_main_ohne_quelle_endet_mit_2(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(aufnahme_lauf.main(["--project", t, "--quelle", "Q-00000000"]), 2)


class Lauftyp(unittest.TestCase):
    def test_lauftyp_gueltig_und_nur_quell_ids(self):
        typ = lauf.laden(RUNTIME / "config" / "harness_laeufe.yaml")["laeufe"]["wissen_aufnahme"]
        self.assertEqual((typ["gpu"], typ["modell_weg"], typ["braucht_modell"], typ["ordner"]), ("keine", False, False, "runtime"))
        wurzel = RUNTIME.parent
        a = lauf.argv_bauen(typ, {"quelle": "Q-1a2b3c4d"}, wurzel)
        self.assertEqual(a["argv"][1:3], ["benchmarks/wissen_aufnahme.py", "--project"])
        self.assertEqual(a["argv"][-1], "Q-1a2b3c4d")
        self.assertTrue((RUNTIME / "benchmarks" / "wissen_aufnahme.py").is_file())
        for falsch in ("Q-1A2B3C4D", "Q-1a2b3c4", "--quelle", "w:akten", "Q-1a2b3c4d x"):
            with self.assertRaises(lauf.LaufFehler, msg=falsch):
                lauf.argv_bauen(typ, {"quelle": falsch}, wurzel)
        with self.assertRaisesRegex(lauf.LaufFehler, "parameter_fehlt"):
            lauf.argv_bauen(typ, {}, wurzel)


if __name__ == "__main__":
    unittest.main()
