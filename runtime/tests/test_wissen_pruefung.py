"""Befunde der Prüfung Spec 7 vom 23.10.2026 (F1–F11, `docs/PRUEFUNG_SPEC7_CODE_2026-10-23.md`) und die offenen G4-Auflagen:
OSError beim Öffnen schaltet nur `wissen` aus (F1), ein Abschnitt, den der Server ablehnt, blockiert das Einbetten nicht (F2),
die Suche wartet nicht auf einen Einbett-Schritt und startet keinen Server (F3), das Logbuch steht nicht doppelt im Index (F4),
ein Vorschlag erbt den Personenbezug vom ganzen Block (F5), Dateien atomar und kaputte Zeilen ohne Absturz (F6), Links aus der
Wurzel hinaus werden nicht gelesen (F7), kein Applier ohne Antrag (F8), lange Logbuch-Zeilen werden geteilt (F10), Netzfehler
der Anfrage geben Volltext (F11). Fake-Server auf 127.0.0.1, keine GPU, kein Modell."""
import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.wissen import adapter as adapter_mod
from guppi_runtime.wissen import desk_wissen, zerlegen
from guppi_runtime.wissen import speicher as S
from wissen_fixture import FakeEmbedServer, alle_freigeben, freigeben, konfig_fuer, oeffnen, repo_anlegen


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wissen-pruefung-")
        self.addCleanup(self.tmp.cleanup)
        self.srv = FakeEmbedServer(lazy=True)
        self.srv.__enter__()
        self.addCleanup(self.srv.__exit__, None, None, None)
        self.sp = oeffnen(self.tmp.name, self.srv.port, server=self.srv)
        self.addCleanup(self.sp.schliessen)
        self.audit = self.sp.test_audit
        self.repo = Path(self.tmp.name) / "repo"


class F1Oeffnen(unittest.TestCase):
    def test_ordner_nicht_anlegbar_ist_valueerror(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            repo, projekt = repo_anlegen(tmp / "repo"), tmp / "projekt"
            projekt.mkdir()
            (projekt / "local_config").write_text("eine Datei, kein Ordner", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "^wis_speicher_nicht_lesbar:"):
                S.WissenSpeicher.oeffnen(konfig_fuer(tmp, 1), projekt_root=projekt, repo_root=repo, audit=None)


class F2GiftAbschnitt(Basis):
    def test_ein_abgelehnter_abschnitt_blockiert_die_folgenden_nicht(self):
        (self.repo / "docs" / "A.md").write_text("# A\n\nGIFT steht hier.\n\n" + "\n\n".join(f"## T{i}\n\nInhalt {i} Lease" for i in range(30)), encoding="utf-8")
        freigeben(self.sp, "markdown", "docs/A.md")
        self.sp.abgleich()
        echt = self.sp.dienst.einbette

        def einbette(texte, timeout=None):
            if any("GIFT" in t for t in texte):
                raise ValueError("wis_server_antwort")
            return echt(texte, timeout)
        self.sp.dienst.einbette = einbette
        out = self.sp.einbetten_schritt()
        self.assertEqual((out["ende"], out["uebersprungen"]), ("fertig", 1))
        self.assertEqual(out["eingebettet"], 30)
        self.assertEqual(len(self.audit.nur("WIS_ABSCHNITT_NICHT_EINBETTBAR")), 1)
        self.assertEqual(self.sp.einbetten_schritt()["eingebettet"], 0, "der abgelehnte Abschnitt wird im selben Prozess nicht neu versucht")
        self.assertEqual(self.sp.suche("Lease", leser=S.CAPTAIN)["modus"], "hybrid")

    def test_ohne_server_bleibt_es_ein_fehler(self):
        self.sp.einbetten_schritt()
        self.srv.server.kaputt = True
        (self.repo / "docs" / "B.md").write_text("# B\n\nNeuer Text.\n", encoding="utf-8")
        freigeben(self.sp, "markdown", "docs/B.md")
        self.sp.abgleich()
        self.assertEqual(self.sp.einbetten_schritt()["ende"], "fehler")
        self.assertEqual(self.audit.nur("WIS_ABSCHNITT_NICHT_EINBETTBAR"), [], "ein toter Server markiert keine Abschnitte")


class F3Sperre(Basis):
    def test_suche_wartet_nicht_auf_den_einbett_schritt(self):
        alle_freigeben(self.sp)
        self.sp.abgleich()
        self.sp.einbetten_schritt()
        (self.repo / "docs" / "NEU.md").write_text("# Neu\n\n" + "\n\n".join(f"## Teil {i}\n\nThema {i} und Lease." for i in range(6)), encoding="utf-8")
        self.sp.abgleich()
        echt = self.sp.dienst.einbette

        def langsam(texte, timeout=None):
            if len(texte) > 1:
                time.sleep(2.0)
            return echt(texte, timeout)
        self.sp.dienst.einbette = langsam
        th = threading.Thread(target=self.sp.einbetten_schritt)
        th.start()
        time.sleep(0.3)
        t0 = time.monotonic()
        r = self.sp.suche("Lease", leser=S.CAPTAIN)
        dauer = time.monotonic() - t0
        self.assertEqual(self.sp.einbetten_schritt()["ende"], "beschaeftigt", "nie zwei Schritte zugleich")
        th.join()
        self.assertLess(dauer, 1.5)
        self.assertEqual(r["modus"], "hybrid")

    def test_suche_startet_keinen_server_sondern_stoesst_ihn_an(self):
        alle_freigeben(self.sp)
        self.sp.abgleich()
        self.sp.einbetten_schritt()
        self.sp.dienst.stoppe()
        self.srv.server.kaputt = True                               # kein Server antwortet
        t0 = time.monotonic()
        r = self.sp.suche("VRAM", leser=S.CAPTAIN)
        self.assertLess(time.monotonic() - t0, 1.5, "die Suche wartet nicht auf den Start")
        self.assertEqual(r["modus"], "volltext")
        self.assertIn("server_startet", r["hinweis"])
        self.srv.server.kaputt = False
        self.sp._start_thread.join(10)
        self.assertFalse(self.sp._start_thread.is_alive(), "der Start lief im Hintergrund")
        self.assertEqual(self.sp.suche("VRAM", leser=S.CAPTAIN)["modus"], "hybrid")


class F4Logbuch(Basis):
    def zahl(self, datei, adapter):
        return self.sp.db.execute("SELECT count(*) FROM abschnitte a JOIN quellen q ON q.id = a.quelle WHERE a.datei = ? AND q.adapter = ?", (datei, adapter)).fetchone()[0]

    def test_logbuch_nur_ueber_die_eigene_quelle(self):
        alle_freigeben(self.sp)
        self.sp.abgleich()
        self.assertEqual(self.zahl(adapter_mod.LOGBUCH, "markdown"), 0)
        self.assertEqual(self.zahl(adapter_mod.LOGBUCH, "logbuch"), 3)

    def test_abgeschaltetes_logbuch_kommt_ueber_den_ordner_zurueck(self):
        alle_freigeben(self.sp)
        self.sp.abgleich()
        lb = next(q for q in self.sp.quellen() if q["adapter"] == "logbuch")
        self.sp.quelle_aendern(lb["id"], aktiv=False)
        self.sp.abgleich()
        self.assertGreater(self.zahl(adapter_mod.LOGBUCH, "markdown"), 0)

    def test_freigabe_des_logbuchs_nach_dem_ordner_entfernt_die_kopie(self):
        freigeben(self.sp, "markdown", "docs")
        self.sp.abgleich()
        self.assertGreater(self.zahl(adapter_mod.LOGBUCH, "markdown"), 0)
        freigeben(self.sp, "logbuch", adapter_mod.LOGBUCH)
        self.sp.abgleich()
        self.assertEqual(self.zahl(adapter_mod.LOGBUCH, "markdown"), 0)


class F5Personenbezug(Basis):
    def test_vorschlag_ohne_belege_erbt_den_personenbezug_des_blocks(self):
        alle_freigeben(self.sp)
        self.sp.abgleich()
        self.sp.einbetten_schritt()
        leser = S.leser("agent", 3, None, "A-1")
        r = self.sp.suche("Wo liegt die Steuernummer?", leser=leser)
        self.assertTrue(any(t["personenbezug"] for t in r["treffer"]))
        v = self.sp.vorschlagen(titel="Steuer", text="Die Steuernummer liegt im vertraulichen Ordner.", belege=[], agent_id="A-1", lauf_id="L1",
                                aufgabe_id=None, block_ids={t["id"] for t in r["treffer"]}, leser=leser)
        self.assertEqual(v["personenbezug"], 1)


class F6Dateien(Basis):
    def test_kaputte_zeile_in_vorschlaege_bricht_die_ruecknahme_nicht(self):
        datei = Path(self.tmp.name) / "projekt" / adapter_mod.VORSCHLAEGE
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text('{"id": "WV-alt", "titel": "x"}\nkaputt{\n', encoding="utf-8")
        with S.schema._immediate(self.sp.db):
            self.sp.db.execute("INSERT INTO vorschlaege (id, titel, text, hash, vorschlag_stufe, personenbezug, status, erstellt) VALUES ('WV-1','t','x','h',1,0,'freigegeben','2026-10-23T00:00:00Z')")
        self.assertEqual(self.sp.vorschlag_zuruecknehmen("WV-1")["status"], "veraltet")
        self.assertEqual([json.loads(z)["id"] for z in datei.read_text(encoding="utf-8").splitlines()], ["WV-alt"])
        self.assertFalse(datei.with_name(datei.name + ".tmp").exists())

    def test_nachmessung_bewerten_verliert_keinen_satz(self):
        for i in range(5):
            self.sp._protokolliere(f"Frage {i}", [], "volltext")
        self.sp.nachmessung_bewerten(S._sha("Frage 2"), "getroffen")
        saetze = self.sp.nachmessung()
        self.assertEqual(len(saetze), 5)
        self.assertEqual([s.get("urteil") for s in saetze].count("getroffen"), 1)


@unittest.skipUnless(hasattr(os, "symlink"), "Symlinks")
class F7Links(Basis):
    def test_link_aus_der_wurzel_wird_nicht_gelesen(self):
        draussen = Path(self.tmp.name) / "draussen"
        draussen.mkdir()
        (draussen / "GEHEIM_AUSSEN.md").write_text("# Außen\n\nDieser Text liegt außerhalb des Repos.\n", encoding="utf-8")
        try:
            os.symlink(draussen, self.repo / "docs" / "link", target_is_directory=True)
        except OSError:
            self.skipTest("keine Symlinks erlaubt")
        freigeben(self.sp, "markdown", "docs")
        self.sp.abgleich()
        n = self.sp.db.execute("SELECT count(*) FROM abschnitte WHERE text LIKE '%außerhalb des Repos%'").fetchone()[0]
        self.assertEqual(n, 0)

    def test_quelle_die_spaeter_ein_link_nach_draussen_wird(self):
        freigeben(self.sp, "markdown", "notizen", muster="*.txt")
        self.sp.abgleich()
        draussen = Path(self.tmp.name) / "draussen2"
        draussen.mkdir()
        (draussen / "x.txt").write_text("fremd fremd fremd", encoding="utf-8")
        ziel = self.repo / "notizen"
        for p in ziel.iterdir():
            p.unlink()
        ziel.rmdir()
        try:
            os.symlink(draussen, ziel, target_is_directory=True)
        except OSError:
            self.skipTest("keine Symlinks erlaubt")
        self.sp.abgleich()
        self.assertEqual(self.sp.db.execute("SELECT count(*) FROM abschnitte WHERE text LIKE '%fremd%'").fetchone()[0], 0)


class F8Antrag(unittest.TestCase):
    def test_ohne_antrag_kein_stilles_gated(self):
        hub = SimpleNamespace(runtime=SimpleNamespace(missions=SimpleNamespace(list=lambda: [])))
        with self.assertRaisesRegex(ValueError, "wis_antrag_unbekannt"):
            desk_wissen._antrag_von(hub, desk_wissen.KIND_QUELLE, {"pfad": "docs"})


class F10Logbuch(unittest.TestCase):
    def test_lange_zeile_wird_geteilt(self):
        zeile = "| 2026-10-22 10:00 | BAU | " + "wort " * 600 + "|"
        teile = zerlegen.zerlege_logbuch("# Logbuch\n\n" + zeile + "\n", "x")
        zeilen = [t for t in teile if "Zeile" in t["stelle"]]
        self.assertGreater(len(zeilen), 1)
        self.assertTrue(all(len(t["text"]) <= zerlegen.MAX_ZEICHEN for t in zeilen))
        self.assertEqual([t["teil"] for t in zeilen], list(range(1, len(zeilen) + 1)))


class F11Netzfehler(Basis):
    def test_unvollstaendige_antwort_gibt_volltext(self):
        alle_freigeben(self.sp)
        self.sp.abgleich()
        self.sp.einbetten_schritt()

        def bricht(texte, timeout=None):
            raise http.client.IncompleteRead(b"")
        self.sp.dienst.einbette = bricht
        self.assertIsNone(self.sp.dienst.anfrage_vektor("VRAM", starten=False))
        self.assertEqual(self.sp.suche("VRAM", leser=S.CAPTAIN)["modus"], "volltext")


if __name__ == "__main__":
    unittest.main()
