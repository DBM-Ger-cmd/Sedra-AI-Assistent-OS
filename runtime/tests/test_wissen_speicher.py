"""`wissen/speicher.py` (Spec 7, D7.3, D7.5; WIS-01, WIS-03, WIS-05, WIS-06, WIS-09): eine Frage findet Treffer aus allen drei
Speichern; ein zweiter Abgleich ohne Änderung bettet 0 Abschnitte ein, eine geänderte Datei nur ihre Abschnitte neu, eine
gelöschte verschwindet; ohne Server nur Volltext mit Hinweis; Rechtefilter vor dem Ranking. Fake-Server auf 127.0.0.1."""
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.wissen import ausgabe, schema
from guppi_runtime.wissen import speicher as S
from wissen_fixture import FakeEmbedServer, alle_freigeben, freigeben, oeffnen

AGENT1 = S.leser("agent", 1, None, "A1")


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wissen-speicher-")
        self.addCleanup(self.tmp.cleanup)
        self.srv = FakeEmbedServer(lazy=True)
        self.srv.__enter__()
        self.addCleanup(self.srv.__exit__, None, None, None)
        self.sp = oeffnen(self.tmp.name, self.srv.port, server=self.srv)
        self.addCleanup(self.sp.schliessen)
        self.audit = self.sp.test_audit

    def stellen(self, ergebnis):
        return [t["stelle"] for t in ergebnis["treffer"]]


class Aufnahme(Basis):
    def test_alle_drei_speicher_und_die_doku_liefern_treffer(self):
        alle_freigeben(self.sp)
        a = self.sp.abgleich()
        self.assertEqual((a["quellen"], a["neu"], a["entfernt"], a["gesperrt"]), (6, 12, 0, 0))  # 12: das Logbuch steht nur noch über seine eigene Quelle im Index, nicht zusätzlich im Ordner docs (Prüfung F4)
        adapter = {q["adapter"]: q["abschnitte"] for q in self.sp.quellen()}
        self.assertEqual({k: v > 0 for k, v in adapter.items()}, {"markdown": True, "logbuch": True, "knowledge": True, "arbeitsumfeld": True, "gateway": True})
        self.sp.einbetten_schritt()
        hits = self.stellen(self.sp.suche("Lease des Testlabors holen", leser=S.CAPTAIN, k=10))
        self.assertIn("GPU-Regeln > Lease", hits)
        self.assertIn("Vorarbeiter-Aktion Lease holen", hits, "arbeitsumfeld")
        self.assertIn("Notiz Notiz zum Logbuch", self.stellen(self.sp.suche("Uhrzeit im Logbuch", leser=S.CAPTAIN, k=10)), "knowledge")
        self.assertIn("Regel R-07 Kartendaten", self.stellen(self.sp.suche("Kartendaten mit Prüfwert", leser=S.CAPTAIN)), "gateway")
        self.assertNotIn("Notiz Alt", [r["stelle"] for r in self.sp.db.execute("SELECT stelle FROM abschnitte")], "nur status active")

    def test_zweiter_abgleich_bettet_nichts_ein_und_aenderungen_bleiben_klein(self):
        alle_freigeben(self.sp)
        self.sp.abgleich()
        erster = self.sp.einbetten_schritt()
        self.assertEqual(erster["eingebettet"], 12)
        self.assertEqual(self.sp.abgleich()["uebersprungen"], 6, "Quell-Hash gleich: nichts wird zerlegt")
        self.assertEqual(self.sp.einbetten_schritt()["eingebettet"], 0, "WIS-03")
        repo = Path(self.tmp.name) / "repo"
        gpu = repo / "docs" / "GPU.md"
        gpu.write_text(gpu.read_text(encoding="utf-8").replace("11,5 GB", "11,0 GB"), encoding="utf-8")
        (repo / "docs" / "GEHEIM.md").unlink()
        a = self.sp.abgleich()
        self.assertEqual((a["neu"], a["geaendert"], a["entfernt"]), (0, 1, 1))
        e = self.sp.einbetten_schritt()
        self.assertEqual(e["eingebettet"], 1, "nur der geänderte Abschnitt")
        self.assertEqual(self.sp.db.execute("SELECT count(*) FROM abschnitte WHERE datei = 'docs/GEHEIM.md'").fetchone()[0], 0)
        self.assertEqual(self.sp.db.execute("SELECT count(*) FROM vektoren").fetchone()[0], 11, "Vektoren der gelöschten Abschnitte fallen mit")
        ids = {r[0] for r in self.sp.db.execute("SELECT id FROM abschnitte WHERE datei = 'docs/GPU.md'")}
        self.assertEqual(len(ids), 2, "die ID bleibt bei geändertem Text stabil")

    def test_ohne_freigabe_bleibt_der_speicher_leer(self):
        freigeben(self.sp, "markdown", "docs/GPU.md")
        self.sp.abgleich()
        self.assertEqual(self.sp.db.execute("SELECT count(*) FROM abschnitte WHERE datei != 'docs/GPU.md'").fetchone()[0], 0)
        self.assertEqual([q["pfad"] for q in self.sp.quellen()], ["docs/GPU.md"])

    def test_pfade_werden_geprueft(self):
        for pfad, code in (("/etc/passwd", "wis_pfad_absolut"), ("C:/x", "wis_pfad_absolut"), ("docs/../..", "wis_pfad_ausserhalb"), ("../repo", "wis_pfad_ausserhalb")):
            with self.assertRaisesRegex(ValueError, code):
                freigeben(self.sp, "markdown", pfad)
        with self.assertRaisesRegex(ValueError, "wis_dateiart_nicht_erlaubt"):
            freigeben(self.sp, "markdown", "docs", muster="*.py")
        with self.assertRaisesRegex(ValueError, "wis_adapter_unbekannt"):
            freigeben(self.sp, "quelltext", "docs")
        self.assertEqual(self.sp.quellen(), [])

    def test_unlesbare_quelle_wird_uebersprungen_nicht_geleert(self):
        freigeben(self.sp, "text", "notizen/plan.txt", muster="*.txt")
        self.sp.abgleich()
        self.assertEqual(self.sp.quelle(self.sp.quellen()[0]["id"])["abschnitte"], 1)
        (Path(self.tmp.name) / "repo" / "notizen" / "plan.txt").write_bytes(b"\xff\xfe kein utf8")
        a = self.sp.abgleich()
        self.assertEqual((a["uebersprungen"], a["dateien_uebersprungen"]), (0, 1))
        self.assertEqual(self.sp.quellen()[0]["abschnitte"], 1, "die Datei behält ihre Abschnitte, die Quelle bleibt stehen")
        (Path(self.tmp.name) / "repo" / "notizen" / "plan.txt").unlink()
        self.assertEqual(self.sp.abgleich()["uebersprungen"], 1, "eine fehlende Datei-Quelle wird übersprungen, nicht geleert")
        self.assertEqual(self.sp.quellen()[0]["abschnitte"], 1)
        self.assertEqual([p["grund"] for p in self.audit.nur("WIS_DATEI_UEBERSPRUNGEN")], ["wis_text_kein_utf8", "wis_speicher_nicht_lesbar"])

    def test_harte_funde_werden_nicht_aufgenommen(self):
        p = Path(self.tmp.name) / "repo" / "docs" / "KARTE.md"
        p.write_text("# Karte\n\nKreditkarte 4111 1111 1111 1111 CVV 123 Ablauf 12/27\n", encoding="utf-8")
        freigeben(self.sp, "markdown", "docs/KARTE.md")
        a = self.sp.abgleich()
        gesperrt = self.audit.nur("WIS_ABSCHNITT_GESPERRT")
        self.assertEqual((a["gesperrt"], len(gesperrt)), (1, 1))
        self.assertNotIn("4111", str(gesperrt), "nie Text im Audit")
        self.assertEqual(self.sp.quellen()[0]["abschnitte"], 0)

    def test_quelle_enger_ohne_gate_weiter_nur_mit_antrag(self):
        q = freigeben(self.sp, "markdown", "docs/GPU.md", stufe=1)
        self.assertEqual(self.sp.quelle_aendern(q["id"], stufe=3)["stufe"], 3)
        with self.assertRaisesRegex(ValueError, "wis_quelle_neuer_antrag"):
            self.sp.quelle_aendern(q["id"], stufe=1)
        self.assertEqual(self.sp.quelle_aendern(q["id"], aktiv=False)["aktiv"], 0)
        with self.assertRaisesRegex(ValueError, "wis_quelle_neuer_antrag"):
            self.sp.quelle_aendern(q["id"], aktiv=True)
        self.assertEqual(len(self.audit.nur("WIS_QUELLE_GEAENDERT")), 2)
        q2 = freigeben(self.sp, "markdown", "docs/GPU.md", stufe=1)
        self.assertEqual((q2["id"], self.sp.quelle(q["id"])["aktiv"], self.sp.quelle(q["id"])["stufe"]), (q["id"], 1, 1), "ein neuer Antrag macht den Weg wieder weit")


class Suche(Basis):
    def setUp(self):
        super().setUp()
        alle_freigeben(self.sp)
        self.sp.abgleich()
        self.sp.einbetten_schritt()

    def test_hybrid_findet_andere_worte(self):
        r = self.sp.suche("Grenze für den Grafikspeicher", leser=S.CAPTAIN)
        self.assertEqual((r["modus"], r["hinweis"], r["abdeckung"]), ("hybrid", None, 1.0))
        self.assertEqual(r["treffer"][0]["stelle"], "GPU-Regeln > Videospeicher")
        self.assertEqual((r["treffer"][0]["rang_vektor"], r["treffer"][0]["rang_wort"]), (1, None), "die Wortsuche kennt „Grafikspeicher“ nicht")
        t = r["treffer"][0]
        self.assertEqual(set(t), {"id", "quelle", "datei", "stelle", "datum", "text", "hash", "punkte", "rang_wort", "rang_vektor", "guete", "personenbezug", "befunde"})
        self.assertTrue(ausgabe.ZITAT_MUSTER.fullmatch(f"[{t['id']}]"), t["id"])
        su = self.audit.nur("WIS_SUCHE")[-1]
        self.assertEqual((su["leser_art"], su["modus"], su["k"], su["ids"][0]), ("captain", "hybrid", 5, t["id"]))
        self.assertNotIn("Grafikspeicher", str(su), "nie der Fragetext")

    def test_ohne_server_nur_volltext_mit_hinweis(self):
        self.srv.server.kaputt = True
        self.sp.dienst._proc = None
        r = self.sp.suche("Wie viel VRAM darf ein Modell belegen?", leser=S.CAPTAIN)
        self.assertEqual(r["modus"], "volltext")
        self.assertTrue(r["hinweis"].startswith("Nur Volltextsuche ("), r["hinweis"])
        self.assertEqual(r["treffer"][0]["stelle"], "GPU-Regeln > Videospeicher")
        self.assertIsNone(r["treffer"][0]["rang_vektor"])
        self.assertEqual(len(self.audit.nur("WIS_RUECKFALL_VOLLTEXT")), 1)
        self.sp.suche("VRAM", leser=S.CAPTAIN)
        self.assertEqual(len(self.audit.nur("WIS_RUECKFALL_VOLLTEXT")), 1, "einmal je Zustandswechsel")

    def test_fehlende_engine_heisst_volltext(self):
        self.sp.konfig.engine = None
        self.sp.dienst = type(self.sp.dienst)(self.sp.dienst.e.__class__(**{**self.sp.dienst.e.__dict__, "engine": None}), gpu=self.sp.dienst.gpu, audit=self.sp.audit, pid_datei=self.sp.dienst.pid_datei)
        r = self.sp.suche("VRAM", leser=S.CAPTAIN)
        self.assertEqual((r["modus"], r["hinweis"]), ("volltext", ausgabe.HINWEIS_VOLLTEXT.format(grund="wis_engine_fehlt")))
        self.assertEqual(self.sp.stand()["modus"], "volltext")

    def test_abdeckung_unter_der_grenze_faellt_zurueck(self):
        with schema._immediate(self.sp.db):
            self.sp.db.execute("DELETE FROM vektoren WHERE abschnitt > 4")
        r = self.sp.suche("VRAM", leser=S.CAPTAIN)
        self.assertEqual(r["modus"], "volltext")
        self.assertIn("abdeckung", r["hinweis"])

    def test_stufe_1_sieht_keine_quelle_der_stufe_3(self):
        captain = self.stellen(self.sp.suche("Wo liegt die Steuernummer?", leser=S.CAPTAIN))
        self.assertEqual(captain[0], "Eigene Frage")
        self.assertNotIn("Eigene Frage", self.stellen(self.sp.suche("Wo liegt die Steuernummer?", leser=AGENT1)), "WIS-09")
        self.assertIn("Eigene Frage", self.stellen(self.sp.suche("Wo liegt die Steuernummer?", leser=S.leser("agent", 3, None, "A3"))))

    def test_cloud_route_filtert_personenbezug_und_projekt(self):
        self.assertNotIn("Eigene Frage", self.stellen(self.sp.suche("Wo liegt die Steuernummer?", leser=S.CAPTAIN, route="cloud")), "WIS-11")
        q = freigeben(self.sp, "text", "notizen/plan.txt", muster="*.txt", projekt="P-B")
        self.sp.abgleich()
        self.sp.einbetten_schritt()
        self.assertNotIn("plan.txt", self.stellen(self.sp.suche("Karte des Geländes", leser=S.leser("agent", 1, "P-A", "A1"))))
        self.assertIn("plan.txt", self.stellen(self.sp.suche("Karte des Geländes", leser=S.leser("agent", 1, "P-B", "A1"))))
        self.assertIn("plan.txt", self.stellen(self.sp.suche("Karte des Geländes", leser=S.CAPTAIN)))

    def test_befunde_bleiben_agenten_verborgen(self):
        with schema._immediate(self.sp.db):
            self.sp.db.execute("UPDATE abschnitte SET befunde = '[\"INJECTION_V1\"]' WHERE stelle = 'GPU-Regeln > Lease'")
        self.assertNotIn("GPU-Regeln > Lease", self.stellen(self.sp.suche("Lease des Testlabors", leser=AGENT1)))
        self.assertIn("GPU-Regeln > Lease", self.stellen(self.sp.suche("Lease des Testlabors", leser=S.CAPTAIN)))

    def test_fehlercodes_der_suche(self):
        with self.assertRaisesRegex(ValueError, "wis_anfrage_leer"):
            self.sp.suche("der die das", leser=S.CAPTAIN)
        with self.assertRaisesRegex(ValueError, "wis_anfrage_zu_lang"):
            self.sp.suche("x" * 501, leser=S.CAPTAIN)
        with self.assertRaisesRegex(ValueError, "wis_k_ungueltig"):
            self.sp.suche("VRAM", leser=S.CAPTAIN, k=21)
        with self.assertRaisesRegex(ValueError, "wis_route_ungueltig"):
            self.sp.suche("VRAM", leser=S.CAPTAIN, route="lokal")
        with self.assertRaisesRegex(ValueError, "wis_leser_ungueltig"):
            self.sp.suche("VRAM", leser={"art": "gast", "stufe": 1})

    def test_nachmessung_protokolliert_nur_hashes(self):
        self.sp.suche("VRAM", leser=S.CAPTAIN)
        self.sp.suche("VRAM", leser=AGENT1)
        saetze = self.sp.nachmessung()
        self.assertEqual(len(saetze), 1, "nur Fragen des Captains")
        self.assertEqual(set(saetze[0]), {"zeit", "frage_sha256", "ids", "modus"})
        self.sp.nachmessung_bewerten(saetze[0]["frage_sha256"], "getroffen")
        out = self.sp.nachmessung_abschliessen()
        self.assertEqual((out["fragen"], out["getroffen"], out["anteil"]), (1, 1, 1.0))
        self.assertEqual(self.audit.nur("WIS_NACHMESSUNG")[0]["anteil"], 1.0)
        self.assertEqual(self.sp.nachmessung(), [])


if __name__ == "__main__":
    unittest.main()
