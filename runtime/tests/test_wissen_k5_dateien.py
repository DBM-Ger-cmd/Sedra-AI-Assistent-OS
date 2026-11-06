"""K5-1 und K5-2 (SPEC_WISSEN_KERN_v1 WK-21, WK-22, WK-27-Vorarbeit; G2 K5 §2.1, §2.2, §2.4, §2.5): freigegebene Ordner `w:<id>` mit Prüfung und
Untergrenzen; Migration 2 behält den Bestand, legt eine Sicherung an und läuft ohne Fremdschlüssel (DROP löscht keine Abschnitte); der Abgleich
liest nur neue und geänderte Dateien, in Schritten, behält bei unlesbaren Dateien die alten Abschnitte und löscht die Abschnitte entfernter
Dateien; der Stand je Datei. Ohne Modell, ohne Netz (Fake-Embedding), keine GPU."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.wissen import schema, wurzeln
from wissen_fixture import FakeEmbedServer, freigeben, oeffnen

MD = "# Akte {n}\n\n## Vertrag\n\nLaufzeit {n} Jahre, Kündigung drei Monate.\n\n## Kontakt\n\nAnsprechpartner im Einkauf.\n"


class Wurzeln(unittest.TestCase):
    def test_pruefen(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok, probleme = wurzeln.pruefen({"wurzeln": [{"id": "kunden", "pfad": tmp, "name": "Kunden", "personenbezug": 1, "stufe": 2},
                                                        {"id": "X", "pfad": tmp}, {"id": "rel", "pfad": "relativ/ordner"},
                                                        {"id": "weg", "pfad": str(Path(tmp) / "fehlt")}, {"id": "kunden", "pfad": tmp}, "kaputt"]})
            self.assertEqual(list(ok), ["kunden"])
            self.assertEqual((ok["kunden"].personenbezug, ok["kunden"].stufe, ok["kunden"].schluessel), (1, 2, "w:kunden"))
            self.assertEqual(len(probleme), 5)
            self.assertNotIn("pfad", ok["kunden"].oeffentlich(), "das Modell sieht keinen Pfad")
        self.assertEqual(wurzeln.pruefen({"wurzeln": "nein"})[0], {})
        self.assertEqual((wurzeln.kennung("w:kunden"), wurzeln.kennung("projekt"), wurzeln.kennung("w:../x")), ("kunden", None, None))

    def test_kaputte_datei_heisst_keine_wurzeln(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "local_config").mkdir()
            (Path(tmp) / "local_config" / "wissen_wurzeln.yaml").write_text("wurzeln: [: kaputt", encoding="utf-8")
            w, probleme = wurzeln.lesen(tmp)
            self.assertEqual(w, {})
            self.assertIn("nicht lesbar", probleme[0])
            self.assertEqual(wurzeln.lesen(Path(tmp) / "leer"), ({}, []))


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wissen-k5-")
        self.addCleanup(self.tmp.cleanup)
        self.srv = FakeEmbedServer(lazy=True)
        self.srv.__enter__()
        self.addCleanup(self.srv.__exit__, None, None, None)
        self.akten = Path(self.tmp.name) / "akten"
        self.akten.mkdir()
        for n in range(1, 6):
            (self.akten / f"akte{n}.md").write_text(MD.format(n=n), encoding="utf-8")
        projekt = Path(self.tmp.name) / "projekt"
        (projekt / "local_config").mkdir(parents=True)
        (projekt / "local_config" / "wissen_wurzeln.yaml").write_text(
            f"wurzeln:\n  - {{id: akten, pfad: '{self.akten.as_posix()}', name: Akten, personenbezug: 1, stufe: 2}}\n", encoding="utf-8")
        self.sp = oeffnen(self.tmp.name, self.srv.port, server=self.srv)
        self.addCleanup(self.sp.schliessen)

    def quelle(self, **kw):
        return freigeben(self.sp, "markdown", ".", wurzel="w:akten", stufe=kw.pop("stufe", 2), **kw)


class FreigegebeneOrdner(Basis):
    def test_quelle_unter_freigegebenem_ordner_mit_untergrenzen(self):
        q = self.quelle()
        self.assertEqual((q["wurzel"], q["art"], q["personenbezug"]), ("w:akten", "ordner", 1), "Personenbezug kommt von der Wurzel")
        with self.assertRaisesRegex(ValueError, "wis_stufe_unter_wurzel"):
            self.quelle(stufe=1)
        with self.assertRaisesRegex(ValueError, "wis_wurzel_unbekannt"):
            freigeben(self.sp, "markdown", ".", wurzel="w:gibtsnicht", stufe=2)
        with self.assertRaisesRegex(ValueError, "wis_adapter_unbekannt"):
            freigeben(self.sp, "knowledge", "x.jsonl", wurzel="w:akten", stufe=2)
        with self.assertRaisesRegex(ValueError, "wis_pfad_ausserhalb"):
            freigeben(self.sp, "markdown", "../projekt", wurzel="w:akten", stufe=2)
        self.sp.abgleich()
        treffer = self.sp.suche("Kündigung", leser={"art": "captain", "stufe": 6, "projekt": None, "agent_id": None})["treffer"]
        self.assertTrue(treffer and all(t["personenbezug"] for t in treffer))

    def test_entfernte_wurzel_ueberspringt_statt_zu_leeren(self):
        self.quelle()
        self.sp.abgleich()
        vorher = self.sp.db.execute("SELECT count(*) FROM abschnitte").fetchone()[0]
        (self.sp.projekt_root / "local_config" / "wissen_wurzeln.yaml").write_text("wurzeln: []\n", encoding="utf-8")
        with schema._immediate(self.sp.db):
            self.sp.db.execute("UPDATE quellen SET quell_hash = 'anders'")
        self.sp.abgleich()
        self.assertEqual(self.sp.db.execute("SELECT count(*) FROM abschnitte").fetchone()[0], vorher)
        self.assertTrue(any(p["grund"] == "wis_wurzel_unbekannt" for p in self.sp.test_audit.nur("WIS_DATEI_UEBERSPRUNGEN")))


class AbgleichJeDatei(Basis):
    def zaehlen(self):
        gelesen = []
        echt = self.sp._adapter

        def adapter(name):
            ad = echt(name)
            roh = ad.stuecke_datei
            ad.stuecke_datei = lambda q, p: (gelesen.append(p.name), roh(q, p))[1]
            return ad
        self.sp._adapter = adapter
        return gelesen

    def ids(self, datei):
        return [r[0] for r in self.sp.db.execute("SELECT id FROM abschnitte WHERE datei = ? ORDER BY nr", (datei,))]

    def test_nur_geaenderte_dateien_werden_gelesen(self):
        q = self.quelle()
        gelesen = self.zaehlen()
        self.sp.abgleich()
        self.assertEqual(sorted(gelesen), [f"akte{n}.md" for n in range(1, 6)])
        ids_2 = self.ids("akte2.md")
        gelesen.clear()
        (self.akten / "akte3.md").write_text(MD.format(n=3) + "\n## Neu\n\nNachtrag zur Akte.\n", encoding="utf-8")
        a = self.sp.abgleich()
        self.assertEqual(gelesen, ["akte3.md"], "nur die geänderte Datei")
        self.assertEqual((a["neu"], a["entfernt"]), (1, 0))
        self.assertEqual(self.ids("akte2.md"), ids_2, "unveränderte Dateien behalten ihre Kennungen")
        st = self.sp.dateien_stand(q["id"])
        self.assertEqual((st["summen"]["aufgenommen"], st["summen"]["uebersprungen"], st["summen"]["offen"]), (5, 0, 0))
        self.assertEqual({d["datei"] for d in st["dateien"]}, {f"akte{n}.md" for n in range(1, 6)})

    def test_entfernte_datei_verliert_ihre_abschnitte(self):
        q = self.quelle()
        self.sp.abgleich()
        (self.akten / "akte4.md").unlink()
        a = self.sp.abgleich()
        self.assertGreater(a["entfernt"], 0)
        self.assertEqual(self.ids("akte4.md"), [])
        self.assertNotIn("akte4.md", {d["datei"] for d in self.sp.dateien_stand(q["id"])["dateien"]})

    def test_unlesbare_datei_behaelt_alte_abschnitte_und_steht_mit_grund_da(self):
        q = self.quelle()
        self.sp.abgleich()
        alt = self.ids("akte1.md")
        (self.akten / "akte1.md").write_bytes(b"\xff\xfe kein utf-8 \xff")
        self.sp.abgleich()
        self.assertEqual(self.ids("akte1.md"), alt)
        zeile = [d for d in self.sp.dateien_stand(q["id"], zustand="uebersprungen")["dateien"]][0]
        self.assertEqual((zeile["datei"], zeile["grund"]), ("akte1.md", "wis_text_kein_utf8"))
        (self.akten / "akte1.md").write_text(MD.format(n=1), encoding="utf-8")
        self.sp.abgleich()
        self.assertEqual(self.sp.dateien_stand(q["id"])["summen"]["uebersprungen"], 0, "wieder lesbar → wieder aufgenommen")

    def test_in_schritten(self):
        self.sp.konfig.dateien_je_schritt = 2
        q = self.quelle()
        gelesen = self.zaehlen()
        a1 = self.sp.abgleich()
        self.assertEqual((len(gelesen), a1["dateien_offen"]), (2, 3))
        self.assertEqual(self.sp.dateien_stand(q["id"])["summen"]["offen"], 3)
        self.sp.abgleich(); self.sp.abgleich()
        self.assertEqual(len(gelesen), 5)
        self.assertEqual(self.sp.dateien_stand(q["id"])["summen"]["offen"], 0)
        gelesen.clear()
        self.assertEqual(self.sp.abgleich()["uebersprungen"], 1, "fertig: der Quell-Hash stimmt, nichts wird gelesen")
        self.assertEqual(gelesen, [])
        with self.assertRaisesRegex(ValueError, "wis_zustand_ungueltig"):
            self.sp.dateien_stand(q["id"], zustand="quatsch")


class Migration(unittest.TestCase):
    def test_v1_bestand_bleibt_sicherung_und_tabelle_dateien(self):
        with tempfile.TemporaryDirectory(prefix="wissen-mig-") as tmp:
            srv = FakeEmbedServer(lazy=True)
            srv.__enter__()
            try:
                pfad = Path(tmp) / "projekt" / "local_config" / "wissen" / "wissen.sqlite"
                pfad.parent.mkdir(parents=True)
                db = schema.oeffne_db(pfad)
                eins = schema.MIGRATIONEN[0]
                db.executescript("BEGIN IMMEDIATE;" + eins[2])
                db.execute("INSERT INTO migrationen VALUES (1, 'x', 'y')")
                db.execute("INSERT INTO meta VALUES ('schema_version', '1')")
                db.execute("INSERT INTO quellen (id, art, adapter, wurzel, pfad, muster, freigabe_gate, freigabe_mission, stufe, personenbezug, erstellt) "
                           "VALUES ('Q-alt', 'ordner', 'markdown', 'repo', 'docs', '*.md', 'HG', 'M', 1, 0, 'jetzt')")
                db.execute("INSERT INTO abschnitte (id, quelle, datei, stelle, text, hash, datum, aufgenommen, zeichen) VALUES ('W0000000001', 'Q-alt', 'docs/a.md', 'A', 'Text', 'h', 'd', 'd', 4)")
                db.execute("COMMIT")
                db.close()
                sp = oeffnen(tmp, srv.port, server=srv)
                try:
                    self.assertEqual(schema.lies_meta(sp.db)["schema_version"], str(schema.SCHEMA_VERSION))
                    self.assertEqual(sp.db.execute("SELECT count(*) FROM abschnitte WHERE quelle = 'Q-alt'").fetchone()[0], 1, "DROP hat die Abschnitte nicht mitgelöscht")
                    self.assertEqual(sp.db.execute("SELECT count(*) FROM dateien").fetchone()[0], 0)
                    self.assertTrue(pfad.with_name("wissen.sqlite.bak-v1").is_file())
                    alt = sqlite3.connect(str(pfad.with_name("wissen.sqlite.bak-v1")))
                    self.assertEqual(alt.execute("SELECT count(*) FROM abschnitte").fetchone()[0], 1)
                    alt.close()
                    self.assertEqual(sp.db.execute("PRAGMA foreign_keys").fetchone()[0], 1, "Fremdschlüssel wieder an")
                    with self.assertRaises(sqlite3.IntegrityError):
                        sp.db.execute("INSERT INTO quellen (id, art, adapter, wurzel, pfad, freigabe_gate, freigabe_mission, stufe, personenbezug, erstellt) "
                                      "VALUES ('Q-x', 'ordner', 'markdown', 'irgendwo', 'x', 'HG', 'M', 1, 0, 'jetzt')")
                finally:
                    sp.schliessen()
            finally:
                srv.__exit__(None, None, None)


if __name__ == "__main__":
    unittest.main()
