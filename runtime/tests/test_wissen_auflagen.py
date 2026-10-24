"""Die Auflagen des Reviews zu Spec 7 (Cloud-Bau, vor dem Einschalten von `wissen`): (1) `vorschlaege.jsonl` und Nachmessung atomar,
(2) Abgleich löst je Datei gegen die Wurzel auf (Verknüpfung/Junction), (3) `oeffnen` fängt auch `OSError`, (4) der Server startet nie
unter `self.lock`, (5) die Teilung von `speicher.py`, (6) `_antrag_von` ohne stillen Rückfall auf „gated“, dazu ein Abschnitt über der Grenze."""
import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk import gated
from guppi_runtime.wissen import adapter, desk_wissen, hilfen, zerlegen
from guppi_runtime.wissen import speicher as S
from test_wissen_desk import Basis as DeskBasis
from wissen_fixture import FakeEmbedServer, alle_freigeben, freigeben, konfig_fuer, oeffnen, repo_anlegen, speicher_anlegen

AGENT1 = S.leser("agent", 1, None, "A1")


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wissen-auflagen-")
        self.addCleanup(self.tmp.cleanup)
        self.srv = FakeEmbedServer(lazy=True)
        self.srv.__enter__()
        self.addCleanup(self.srv.__exit__, None, None, None)
        self.sp = oeffnen(self.tmp.name, self.srv.port, server=self.srv)
        self.addCleanup(self.sp.schliessen)
        self.audit = self.sp.test_audit
        self.repo = Path(self.tmp.name) / "repo"

    def vorschlag(self, titel="Lease zuerst"):
        block = {r[0] for r in self.sp.db.execute("SELECT id FROM abschnitte")}
        return self.sp.vorschlagen(titel=titel, text="Vor jedem Laden die Lease holen.", belege=[], agent_id="A1", lauf_id="J-1", aufgabe_id="I-1", block_ids=block, leser=AGENT1)

    def jsonl(self):
        return self.sp.projekt_root / "local_config" / "wissen" / "vorschlaege.jsonl"


class AtomarSchreiben(Basis):
    def setUp(self):
        super().setUp()
        alle_freigeben(self.sp)
        self.sp.abgleich()

    def aufnehmen(self, v):
        return self.sp.vorschlag_aufnehmen({"vorschlag_id": v["id"], "hash": v["hash"]}, gate_id="HG-1", mission_id="M-1")

    def reste(self, ordner):
        return [p.name for p in Path(ordner).iterdir() if p.name.endswith(".tmp")]

    def test_abbruch_beim_aufnehmen_laesst_datei_und_status_unveraendert(self):
        erster = self.vorschlag("Erster")
        self.aufnehmen(erster)
        vorher = self.jsonl().read_text(encoding="utf-8")
        zweiter = self.vorschlag("Zweiter")
        with mock.patch("guppi_runtime.wissen.hilfen.os.replace", side_effect=OSError("Platte voll")):
            with self.assertRaises(OSError):
                self.aufnehmen(zweiter)
        self.assertEqual(self.jsonl().read_text(encoding="utf-8"), vorher, "die Datei ist entweder ganz alt oder ganz neu")
        self.assertEqual(self.reste(self.jsonl().parent), [], "keine halbe Hilfsdatei bleibt liegen")
        self.assertEqual(self.sp.vorschlag(zweiter["id"])["status"], "offen", "Abbruch zwischen Datei und Datenbank: nichts ist halb aufgenommen")
        self.aufnehmen(zweiter)
        self.assertEqual(len(self.jsonl().read_text(encoding="utf-8").splitlines()), 2, "der zweite Versuch gelingt")

    def test_abbruch_beim_zuruecknehmen_laesst_datei_und_status_unveraendert(self):
        v = self.vorschlag()
        self.aufnehmen(v)
        vorher = self.jsonl().read_text(encoding="utf-8")
        with mock.patch("guppi_runtime.wissen.hilfen.os.replace", side_effect=OSError("gesperrt")):
            with self.assertRaises(OSError):
                self.sp.vorschlag_zuruecknehmen(v["id"])
        self.assertEqual(self.jsonl().read_text(encoding="utf-8"), vorher)
        self.assertEqual(self.sp.vorschlag(v["id"])["status"], "freigegeben")
        self.assertEqual(self.sp.vorschlag_zuruecknehmen(v["id"])["status"], "veraltet")
        self.assertEqual(self.jsonl().read_text(encoding="utf-8"), "")

    def test_nachmessung_wird_atomar_geschrieben(self):
        self.sp.suche("Lease des Testlabors", leser=S.CAPTAIN)
        self.sp.suche("Uhrzeit im Logbuch", leser=S.CAPTAIN)
        saetze = self.sp.nachmessung()
        self.assertEqual(len(saetze), 2)
        datei = self.sp._nachmessung_datei()
        vorher = datei.read_text(encoding="utf-8")
        with mock.patch("guppi_runtime.wissen.hilfen.os.replace", side_effect=OSError("gesperrt")):
            with self.assertRaises(OSError):
                self.sp.nachmessung_bewerten(saetze[0]["frage_sha256"], "getroffen")
            self.sp.suche("Kartendaten mit Prüfwert", leser=S.CAPTAIN)                 # das Protokoll selbst ist nur ein Nebenzweck: kein Fehler nach außen
        self.assertEqual(datei.read_text(encoding="utf-8"), vorher)
        self.assertEqual(self.reste(datei.parent), [])
        self.sp.nachmessung_bewerten(saetze[0]["frage_sha256"], "getroffen")
        self.assertEqual(self.sp.nachmessung()[0]["urteil"], "getroffen")
        out = self.sp.nachmessung_abschliessen()
        self.assertEqual((out["fragen"], out["getroffen"]), (1, 1))
        self.assertTrue((datei.parent / out["datei"]).is_file())


class VerknuepfungenUndJunctions(Basis):
    def setUp(self):
        super().setUp()
        self.aussen = Path(self.tmp.name) / "aussen"
        self.aussen.mkdir()
        (self.aussen / "GEHEIM.md").write_text("# Fremd\n\n## Steuer\n\nDie Steuernummer liegt außerhalb der Wurzel.\n", encoding="utf-8")

    def verknuepfe(self, ziel, quelle, ordner=False):
        try:
            os.symlink(quelle, ziel, target_is_directory=ordner)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"keine Verknüpfungen möglich: {exc}")

    def test_unter_prueft_die_aufgeloeste_datei(self):
        wurzel = self.repo.resolve()
        self.assertTrue(adapter._unter(self.repo / "docs" / "GPU.md", wurzel))
        self.assertFalse(adapter._unter(self.aussen / "GEHEIM.md", wurzel))
        self.assertFalse(adapter._unter(self.repo / "docs" / ".." / ".." / "aussen" / "GEHEIM.md", wurzel))
        with mock.patch.object(Path, "resolve", side_effect=OSError("kaputt")):
            self.assertFalse(adapter._unter(self.repo / "docs" / "GPU.md", wurzel), "nicht auflösbar heißt außerhalb")

    def test_verknuepfter_ordner_fuehrt_nicht_aus_der_wurzel(self):
        self.verknuepfe(self.repo / "docs" / "draussen", self.aussen, ordner=True)
        q = freigeben(self.sp, "markdown", "docs")
        self.sp.abgleich(q["id"])
        dateien = {r[0] for r in self.sp.db.execute("SELECT DISTINCT datei FROM abschnitte WHERE quelle = ?", (q["id"],))}
        self.assertTrue(dateien, "die echten Dateien sind drin")
        self.assertFalse([d for d in dateien if "draussen" in d or "GEHEIM.md" == Path(d).name and "aussen" in d], dateien)
        self.assertEqual(self.sp.db.execute("SELECT count(*) FROM abschnitte WHERE text LIKE '%außerhalb der Wurzel%'").fetchone()[0], 0)

    def test_verknuepfte_einzeldatei_wird_nicht_gelesen(self):
        self.verknuepfe(self.repo / "docs" / "fremd.md", self.aussen / "GEHEIM.md")
        ad = self.sp._adapter("markdown")
        q = {"adapter": "markdown", "wurzel": "repo", "pfad": "docs/fremd.md", "muster": ""}
        self.assertEqual(ad.quell_hash(q), "wis_pfad_ausserhalb")
        with self.assertRaisesRegex(ValueError, "wis_pfad_ausserhalb"):
            list(ad.stuecke(q))

    def test_datei_unter_verknuepftem_ordner_wird_je_datei_verworfen(self):
        """Eine Junction ist für `is_symlink` und für `rglob` nicht überall eine Verknüpfung: der Test erzwingt den Fall, dass der Pfad
        unter `docs` steht, die aufgelöste Datei aber außerhalb der Wurzel liegt."""
        self.verknuepfe(self.repo / "docs" / "draussen", self.aussen, ordner=True)
        ad = self.sp._adapter("markdown")
        q = {"adapter": "markdown", "wurzel": "repo", "pfad": "docs", "muster": "*.md"}
        fremd = self.repo / "docs" / "draussen" / "GEHEIM.md"
        echte = [p for p in (self.repo / "docs").rglob("*.md") if p.parent.name != "draussen"]
        with mock.patch.object(Path, "rglob", return_value=iter(echte + [fremd])):
            dateien = ad._dateien(q)
        self.assertIn(self.repo / "docs" / "GPU.md", dateien)
        self.assertNotIn(fremd, dateien)


class OeffnenFaengtOsError(unittest.TestCase):
    def test_nicht_anlegbarer_ordner_ist_wis_speicher_nicht_lesbar(self):
        with tempfile.TemporaryDirectory(prefix="wissen-oserror-") as tmp:
            repo = repo_anlegen(Path(tmp) / "repo")
            projekt = speicher_anlegen(Path(tmp) / "projekt")
            (projekt / "local_config" / "wissen").write_text("keine Ordner", encoding="utf-8")      # an der Stelle des Ordners liegt eine Datei
            with self.assertRaisesRegex(ValueError, "wis_speicher_nicht_lesbar"):
                S.WissenSpeicher.oeffnen(konfig_fuer(tmp, 1), projekt_root=projekt, repo_root=repo, audit=lambda e, p: None)


class ServerStartNieUnterDerSperre(Basis):
    def setUp(self):
        super().setUp()
        alle_freigeben(self.sp)
        self.sp.abgleich()
        self.sp.einbetten_schritt()
        self.sp.dienst.stoppe()
        self.frei = []

    def beobachte(self):
        """Der Fake-Server antwortet nicht, bis der Starter ruft; der Starter merkt, ob die Sperre dabei frei war (von einem anderen Thread geprüft)."""
        echt = self.sp.dienst.starter
        self.srv.server.kaputt = True

        def starter(cmd, **kw):
            ergebnis = []

            def versuche():                                            # kurz warten statt sofort: ein Hintergrundstart darf die Suche nicht stören
                ergebnis.append(self.sp.lock.acquire(timeout=2))
                if ergebnis[-1]:
                    self.sp.lock.release()
            t = threading.Thread(target=versuche)
            t.start()
            t.join(5)
            self.frei.append(ergebnis == [True])
            self.srv.server.kaputt = False
            return echt(cmd, **kw)

        self.sp.dienst.starter = starter

    def test_suche_startet_den_server_ausserhalb_der_sperre(self):
        """Zusammengeführt mit Prüfung F3: die Suche wartet nicht auf den Start, sie antwortet sofort im Volltext und stößt den Start im
        Hintergrund an; dieser läuft ohne die Sperre, die nächste Suche ist hybrid."""
        self.beobachte()
        r = self.sp.suche("Grenze für den Grafikspeicher", leser=S.CAPTAIN)
        self.assertEqual(r["modus"], "volltext")
        self.sp._start_thread.join(30)
        self.assertEqual(self.frei, [True], "genau ein Start, ohne Sperre")
        self.assertEqual(self.sp.suche("Grenze für den Grafikspeicher", leser=S.CAPTAIN)["modus"], "hybrid")

    def test_einbetten_schritt_startet_den_server_ausserhalb_der_sperre(self):
        self.beobachte()
        self.sp.einbetten_schritt()
        self.assertEqual(self.frei, [True])

    def test_nachfuehren_startet_den_server_ausserhalb_der_sperre(self):
        self.beobachte()
        self.sp.nachfuehren()
        self.assertEqual(self.frei, [True])

    def test_gescheiterter_start_wird_unter_der_sperre_nicht_wiederholt(self):
        self.sp.dienst.stoppe()
        self.srv.server.kaputt = True
        self.sp.dienst._proc = None
        n = len(self.sp.dienst._fehlstarts)
        out = self.sp.einbetten_schritt()
        self.assertEqual(out["ende"], "fehler")
        self.assertEqual(len(self.sp.dienst._fehlstarts) - n, 1, "ein Versuch, nicht zwei")
        self.assertEqual(self.sp.db.execute("SELECT status FROM laeufe WHERE art = 'einbetten' ORDER BY rowid DESC LIMIT 1").fetchone()[0], "abgebrochen")

    def test_suche_fraegt_bei_gescheitertem_start_volltext_und_haengt_nicht_an_der_sperre(self):
        self.srv.server.kaputt = True
        r = self.sp.suche("Grenze für den Grafikspeicher", leser=S.CAPTAIN)
        self.assertEqual(r["modus"], "volltext")
        self.assertTrue(self.sp.lock.acquire(blocking=False))
        self.sp.lock.release()


class SpeicherGeteilt(unittest.TestCase):
    """Auflage 5 (Prüfung F9): `speicher.py` und seine Teile bleiben unter 400 Zeilen, und keine Methode steht in zwei Teilen."""
    TEILE = ("speicher", "einbetten", "suche", "vorschlaege", "nachmessung", "hilfen")

    def test_jede_datei_unter_400_zeilen(self):
        ordner = Path(S.__file__).parent
        for name in self.TEILE:
            self.assertLess(len((ordner / f"{name}.py").read_text(encoding="utf-8").splitlines()), 400, name)

    def test_keine_methode_doppelt(self):
        gesehen = {}
        for klasse in S.WissenSpeicher.__mro__[:-1]:
            for name, wert in vars(klasse).items():
                if callable(wert) and not name.startswith("__"):
                    self.assertNotIn(name, gesehen, f"{name} in {klasse.__name__} und {gesehen.get(name)}")
                    gesehen[name] = klasse.__name__


class AbschnittUeberDerGrenze(Basis):
    def test_langer_abschnitt_wird_geteilt_und_nichts_geht_verloren(self):
        saetze = " ".join(f"Satz {i} über die Lease des Testlabors." for i in range(200))
        self.assertGreater(len(saetze), zerlegen.MAX_ZEICHEN * 3)
        (self.repo / "docs" / "LANG.md").write_text("# Lang\n\n## Ein langer Abschnitt\n\n" + saetze + "\n", encoding="utf-8")
        q = freigeben(self.sp, "markdown", "docs/LANG.md")
        self.sp.abgleich(q["id"])
        zeilen = self.sp.db.execute("SELECT teil, text FROM abschnitte WHERE quelle = ? ORDER BY teil", (q["id"],)).fetchall()
        self.assertGreater(len(zeilen), 1, "über der Grenze entstehen mehrere Teile")
        self.assertEqual([z[0] for z in zeilen], list(range(zeilen[0][0], zeilen[0][0] + len(zeilen))), "Teile zählen lückenlos")
        self.assertLessEqual(max(len(z[1]) for z in zeilen), zerlegen.MAX_ZEICHEN)
        self.assertIn("Satz 0 ", zeilen[0][1])
        self.assertIn("Satz 199 ", zeilen[-1][1])


class AntragOhneStillenRueckfall(DeskBasis):
    def test_unbekannter_antrag_wendet_nichts_an(self):
        with self.assertRaisesRegex(ValueError, "wis_antrag_unbekannt"):
            desk_wissen._antrag_von(self.hub, desk_wissen.KIND_QUELLE, {"adapter": "markdown", "pfad": "gibt/es/nicht.md"})
        with self.assertRaisesRegex(ValueError, "wis_antrag_unbekannt"):
            desk_wissen._vorschlag_aufnehmen(self.hub, {"vorschlag_id": "WV-fehlt", "hash": "x"})
        self.assertEqual(self.sp.quellen(), [])

    def test_fehler_beim_lesen_der_missionen_wendet_nichts_an(self):
        with mock.patch.object(self.hub.runtime.missions, "list", side_effect=RuntimeError("kaputt")):
            with self.assertRaisesRegex(ValueError, "wis_antrag_unbekannt"):
                desk_wissen._antrag_von(self.hub, desk_wissen.KIND_QUELLE, {})

    def test_der_satz_zum_fehlercode_steht_im_speicher(self):
        self.assertNotEqual(S.satz("wis_antrag_unbekannt"), "wis_antrag_unbekannt")

    def test_ein_echter_antrag_traegt_weiter_gate_und_mission(self):
        out = self.beantrage()
        self.decide(out)
        q = self.sp.quellen()[0]
        self.assertTrue(q["freigabe_gate"] and q["freigabe_gate"] != "gated", q)
        self.assertTrue(q["freigabe_mission"] and q["freigabe_mission"] != "gated", q)


class NachReview(Basis):
    """Befunde des unabhängigen Reviews zu 19f7d2d."""
    def setUp(self):
        super().setUp()
        alle_freigeben(self.sp)
        self.sp.abgleich()

    def test_start_und_stopp_des_dienstes_laufen_nacheinander(self):
        """Befund 2: Takt und Desk rufen den Dienst ohne die Speicher-Sperre; zwei Threads dürfen keinen zweiten Prozess starten."""
        self.sp.einbetten_schritt()
        self.sp.dienst.stoppe()
        self.srv.server.kaputt = True
        echt = self.sp.dienst.starter
        drin, gleichzeitig, start = [0], [0], threading.Barrier(2)

        def starter(cmd, **kw):
            drin[0] += 1
            gleichzeitig[0] = max(gleichzeitig[0], drin[0])
            time.sleep(0.3)                                                  # ein langsamer Start: ohne Sperre käme der zweite Thread dazu
            self.srv.server.kaputt = False
            try:
                return echt(cmd, **kw)
            finally:
                drin[0] -= 1
        self.sp.dienst.starter = starter

        def lauf():
            start.wait(5)
            self.sp.dienst.starte()
        ts = [threading.Thread(target=lauf) for _ in range(2)]
        [t.start() for t in ts]
        [t.join(30) for t in ts]
        self.assertEqual(len(self.sp.test_starter.gestartet), 2, "nur der Start aus der Vorbereitung und genau einer jetzt")
        self.assertEqual(gleichzeitig[0], 1)

    def test_einbetten_startet_nie_unter_der_sperre_auch_wenn_der_server_zwischendurch_endet(self):
        """Befund 3, zusammengeführt mit Prüfung F3: der Einbett-Schritt hält `self.lock` nur für die Datenbank. Stirbt der Server
        zwischen zwei Schritten, startet der nächste ihn neu, aber außerhalb der Sperre, und bettet weiter ein."""
        self.sp.einbetten_schritt()
        self.sp.dienst.stoppe()
        (self.repo / "docs" / "NEU.md").write_text("# Neu\n\n## Teil\n\nNeuer Text über die Lease.\n", encoding="utf-8")
        self.sp.abgleich()
        echt, frei = self.sp.dienst.starter, []

        def starter(cmd, **kw):
            ergebnis = []

            def versuche():
                ergebnis.append(self.sp.lock.acquire(timeout=2))
                if ergebnis[-1]:
                    self.sp.lock.release()
            t = threading.Thread(target=versuche)
            t.start()
            t.join(5)
            frei.append(ergebnis == [True])
            self.srv.server.kaputt = False
            return echt(cmd, **kw)
        self.sp.dienst.starter = starter
        self.srv.server.kaputt = True                                          # der Server ist weg, bis der Neustart ihn holt
        n = len(self.sp.test_starter.gestartet)
        out = self.sp.einbetten_schritt()
        self.assertEqual((out["ende"], out["eingebettet"]), ("fertig", 1))
        self.assertEqual(frei, [True], "der Neustart lief ohne die Sperre")
        self.assertEqual(len(self.sp.test_starter.gestartet), n + 1, "genau ein Neustart")

    def test_nachmessung_verliert_unter_gleichzeitigen_suchen_keinen_satz(self):
        """Befund 4: Lesen, Anhängen und Ersetzen laufen unter der Sperre."""
        fragen = [f"Lease Testlabor Frage {i}" for i in range(24)]
        ts = [threading.Thread(target=lambda f=f: self.sp.suche(f, leser=S.CAPTAIN)) for f in fragen]
        [t.start() for t in ts]
        [t.join(60) for t in ts]
        self.assertEqual(len(self.sp.nachmessung()), len(fragen))

    def test_atomares_schreiben_behaelt_die_rechte_der_alten_datei(self):
        """Befund 6."""
        if os.name == "nt":
            self.skipTest("POSIX-Rechte")
        ziel = Path(self.tmp.name) / "daten.jsonl"
        ziel.write_text("alt\n", encoding="utf-8")
        os.chmod(ziel, 0o640)
        hilfen.schreibe_atomar(ziel, "neu\n")
        self.assertEqual((ziel.read_text(encoding="utf-8"), stat.S_IMODE(ziel.stat().st_mode)), ("neu\n", 0o640))
        neu = Path(self.tmp.name) / "frisch.jsonl"
        hilfen.schreibe_atomar(neu, "x\n")
        self.assertEqual(stat.S_IMODE(neu.stat().st_mode), 0o644)


class AntragSchliesstSichBeiNichtAnwendbar(DeskBasis):
    """Befunde 1 und 5: ein Applier, der nichts anwenden kann, lässt den Antrag nicht als Zombie zurück."""
    def mission(self, mission_id):
        return self.hub.runtime.missions.load(mission_id)

    def test_unbekannter_antrag_wird_ueber_decide_abgelehnt_und_geschlossen(self):
        out = self.beantrage()
        mission_id = out["decision_id"].split(":", 1)[1]
        missionen = self.hub.runtime.missions
        echt = missionen.list

        def nur_im_applier_kaputt(*a, **kw):
            frame = sys._getframe(1)
            while frame is not None:
                if frame.f_code.co_name == "_antrag_von":
                    raise RuntimeError("kaputt")
                frame = frame.f_back
            return echt(*a, **kw)
        with mock.patch.object(missionen, "list", side_effect=nur_im_applier_kaputt):
            res = self.decide(out)
        self.assertEqual((res["status"], res["reason"]), ("guard_refused", "wis_antrag_unbekannt"))
        m = self.mission(mission_id)
        self.assertEqual(m["lifecycle"]["status"], "closed")
        self.assertNotIn("approval_tokens", m["execution"])
        self.assertEqual(self.sp.quellen(), [], "nichts angewendet")

    def test_schreibfehler_beim_aufnehmen_schliesst_den_antrag_ohne_halbe_folgen(self):
        self.decide(self.beantrage())
        block = {r[0] for r in self.sp.db.execute("SELECT id FROM abschnitte")}
        v = self.sp.vorschlagen(titel="Lease zuerst", text="Vor jedem Laden die Lease holen.", belege=[], agent_id="A-3", lauf_id="J-1", aufgabe_id="I-1",
                                block_ids=block, leser=S.leser("agent", 1, None, "A-3"))
        with mock.patch("guppi_runtime.wissen.vorschlaege.schreibe_atomar", side_effect=PermissionError("von einem anderen Programm geöffnet")):
            res = self.hub.decide({"id": "request:" + v["mission_id"], "way": "freigeben_und_anwenden"})["result"]
        self.assertEqual((res["status"], res["reason"]), ("guard_refused", "wis_speicher_nicht_lesbar"))
        self.assertEqual(self.mission(v["mission_id"])["lifecycle"]["status"], "closed")
        self.assertEqual(self.sp.vorschlag(v["id"])["status"], "offen")
        self.assertFalse((self.project / "local_config" / "wissen" / "vorschlaege.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
