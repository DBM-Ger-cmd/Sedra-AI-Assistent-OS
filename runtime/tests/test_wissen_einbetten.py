"""`wissen/embed.py` (Spec 7, D7.4; WIS-04, WIS-12): Einbetten nur über 127.0.0.1 (Socket-Prüfung), eigene PID-Datei, nur die
eigene PID wird beendet, Prüfsumme der GGUF, Modell-ID und Modellwechsel (alle Vektoren der alten ID weg, Neuaufbau), Pause,
solange ein Bau die GPU hält (Fake-TestLab), Zeitgrenze der Anfrage. Fake-Server, Fake-Prozess, keine GPU."""
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.wissen import embed, schema
from guppi_runtime.wissen import speicher as S
from wissen_fixture import FakeEmbedServer, alle_freigeben, oeffnen


class FakeLab:
    """Nur die drei Leser, die `TestLabZugang` benutzt."""

    def __init__(self):
        self.halter, self.res, self.runden = None, [], []

    def holder(self, name="gpu"):
        return self.halter

    def reservations(self):
        return list(self.res)

    def queue(self, statuses=("planned", "running")):
        return [r for r in self.runden if r["status"] in statuses]


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wissen-embed-")
        self.addCleanup(self.tmp.cleanup)
        self.srv = FakeEmbedServer(lazy=True)
        self.srv.__enter__()
        self.addCleanup(self.srv.__exit__, None, None, None)
        self.lab = FakeLab()
        self.sp = oeffnen(self.tmp.name, self.srv.port, server=self.srv, gpu=embed.TestLabZugang(self.lab))
        self.addCleanup(self.sp.schliessen)
        self.audit = self.sp.test_audit
        alle_freigeben(self.sp)
        self.sp.abgleich()


class Server(Basis):
    def test_nur_127_0_0_1_wird_gerufen_und_die_pid_datei_ist_die_eigene(self):
        echte = socket.create_connection
        adressen = []

        def merke(address, *a, **kw):
            adressen.append(address[0])
            return echte(address, *a, **kw)

        with mock.patch("socket.create_connection", merke):
            out = self.sp.einbetten_schritt()
        self.assertEqual(out["ende"], "fertig")
        self.assertEqual(out["eingebettet"], 13)
        self.assertEqual(set(adressen), {"127.0.0.1"}, "WIS-04: kein Netz")
        self.assertTrue(adressen)
        pid = json.loads(self.sp.dienst.pid_datei.read_text(encoding="utf-8"))
        proc = self.sp.test_starter.gestartet[0]
        self.assertEqual((pid["pid"], pid["port"], pid["alias"]), (proc.pid, self.srv.port, "wissen-embed"))
        cmd = proc.cmd
        self.assertEqual(cmd[cmd.index("-ngl") + 1], "0")
        self.assertEqual(cmd[cmd.index("--device") + 1], "none")
        self.assertEqual(cmd[cmd.index("--alias") + 1], "wissen-embed")
        self.assertNotIn("--no-webui", cmd, "keine GUPPI-Signatur")
        starts = self.audit.nur("WIS_EMBED_SERVER")
        self.assertEqual((starts[0]["aktion"], starts[0]["pid"], starts[0]["geraet"]), ("start", proc.pid, "cpu"))
        self.assertEqual(self.sp.dienst.stoppe(), proc.pid)
        self.assertTrue(proc.beendet)
        self.assertFalse(self.sp.dienst.pid_datei.exists())
        self.assertEqual(self.audit.nur("WIS_EMBED_SERVER")[-1]["aktion"], "stop")
        self.assertEqual(len(self.srv.anfragen), 2, "Prüfsatz und ein Stapel von 13")

    def test_ein_fremder_server_auf_dem_port_wird_nicht_angefasst(self):
        fremd = FakeEmbedServer(alias="anderer")
        fremd.__enter__()
        self.addCleanup(fremd.__exit__, None, None, None)
        self.sp.dienst.e = self.sp.dienst.e.__class__(**{**self.sp.dienst.e.__dict__, "port": fremd.port})
        with self.assertRaisesRegex(ValueError, "wis_port_belegt"):
            self.sp.dienst.starte()
        self.assertIsNone(self.sp.dienst.stoppe())
        self.assertEqual(self.sp.test_starter.gestartet, [])
        self.assertEqual(self.sp.einbetten_schritt()["ende"], "fehler")

    def test_falsche_pruefsumme_bettet_nichts_ein(self):
        with self.sp.lock:
            self.sp.dienst.e = self.sp.dienst.e.__class__(**{**self.sp.dienst.e.__dict__, "gguf_sha256": "0" * 64})
        out = self.sp.einbetten_schritt()
        self.assertEqual((out["ende"], out["grund"], out["eingebettet"]), ("fehler", "wis_modell_pruefsumme", 0))
        self.assertEqual(self.sp.test_starter.gestartet, [])

    def test_zwei_fehlstarts_machen_den_dienst_nicht_bereit(self):
        self.srv.server.kaputt = True
        for _ in range(2):
            self.assertEqual(self.sp.einbetten_schritt()["grund"], "wis_server_start")
        self.assertEqual(self.sp.dienst.bereit(), (False, "wis_server_start"))
        self.assertEqual(self.sp.suche("VRAM", leser=S.CAPTAIN)["modus"], "volltext")

    def test_falsche_dimension_ist_wis_server_antwort(self):
        self.sp.einbetten_schritt()
        self.srv.server.falsche_dim = True
        with self.assertRaisesRegex(ValueError, "wis_server_antwort"):
            self.sp.dienst.einbette(["x"])
        self.assertIsNone(self.sp.dienst.anfrage_vektor("x"), "ohne Vektor fällt die Suche auf Volltext zurück")


class Modell(Basis):
    def test_modell_id_und_wechsel_bauen_den_index_neu(self):
        mid = self.sp.dienst.modell_id()
        self.assertEqual(mid, "fake-embed@" + self.sp.konfig.modell_sha256[:12] + "#modell#8#e1")
        self.sp.einbetten_schritt()
        self.assertEqual(schema.lies_meta(self.sp.db)["modell_id"], mid)
        self.assertEqual(self.sp.db.execute("SELECT count(*) FROM vektoren WHERE modell_id = ?", (mid,)).fetchone()[0], 13)
        self.sp.dienst.e = self.sp.dienst.e.__class__(**{**self.sp.dienst.e.__dict__, "pooling": "cls"})
        neu = self.sp.dienst.modell_id()
        self.assertNotEqual(neu, mid)
        self.assertEqual(self.sp.suche("VRAM", leser=S.CAPTAIN)["modus"], "volltext", "bis zum Neuaufbau nur Volltext")
        out = self.sp.einbetten_schritt()
        self.assertEqual(self.audit.nur("WIS_MODELL_WECHSEL"), [{"alt": mid, "neu": neu, "geloescht": 13}])
        self.assertEqual(out["eingebettet"], 13)
        self.assertEqual(self.sp.db.execute("SELECT count(*) FROM vektoren WHERE modell_id = ?", (mid,)).fetchone()[0], 0, "alle Vektoren der alten ID weg")
        self.assertEqual(self.sp.db.execute("SELECT status FROM laeufe WHERE art = 'neuaufbau'").fetchone()[0], "fertig")
        self.assertEqual(self.sp.stand()["neuaufbau"], False)

    def test_eine_neue_zerleger_version_bettet_alles_neu_ein(self):
        self.sp.einbetten_schritt()
        with mock.patch("guppi_runtime.wissen.zerlegen.ZERLEGER_VERSION", "z3"):
            with schema._immediate(self.sp.db):
                self.sp.db.execute("UPDATE quellen SET quell_hash = NULL")
            a = self.sp.abgleich()
        self.assertEqual(a["geaendert"], 13)
        self.assertEqual(self.sp.einbetten_schritt()["eingebettet"], 13)


class Pause(Basis):
    def test_ein_bau_haelt_die_aufnahme_an_und_danach_laeuft_sie_auf_der_cpu(self):
        self.lab.halter = {"owner": "devvm-build", "stale": False}
        out = self.sp.einbetten_schritt()
        self.assertEqual((out["ende"], out["eingebettet"], out["grund"]), ("pause", 0, "lease:devvm-build"))
        self.assertEqual(self.sp.test_starter.gestartet, [], "kein Server während eines Baus")
        self.assertEqual(self.sp.einbetten_schritt()["ende"], "pause")
        self.assertEqual(self.audit.nur("WIS_EINBETTEN_PAUSE"), [{"grund": "lease:devvm-build"}], "einmal je Pause")
        self.assertEqual(self.sp.stand()["pause_grund"], "lease:devvm-build")
        self.lab.halter = {"owner": "guppi-uix", "stale": False}
        out = self.sp.einbetten_schritt()
        self.assertEqual((out["ende"], out["geraet"], out["eingebettet"]), ("fertig", "cpu", 13), "der Modellserver für Chat und Agenten hält nicht an")
        e = self.audit.nur("WIS_EINBETTEN")[-1]
        self.assertEqual((e["geraet"], e["eingebettet"], e["ende"]), ("cpu", 13, "fertig"))
        self.assertGreaterEqual(e["dauer_s"], 0.0)
        self.assertEqual(self.sp.db.execute("SELECT status, lease FROM laeufe WHERE art = 'einbetten' ORDER BY id").fetchall()[0][:], ("pausiert", 0))

    def test_reservierung_und_runde_zaehlen_als_bau_ein_alter_halter_nicht(self):
        z = embed.TestLabZugang(self.lab)
        self.assertEqual(z.lage().zustand, "frei")
        self.lab.res = [{"owner": "night-g"}]
        self.assertEqual(z.lage(), embed.GpuLage("bau", "reservierung:night-g"))
        self.lab.res = []
        self.lab.runden = [{"id": 7, "status": "running"}]
        self.assertEqual(z.lage(), embed.GpuLage("bau", "runde:7"))
        self.lab.runden = []
        self.lab.halter = {"owner": "devvm-build", "stale": True}
        self.assertEqual(z.lage().zustand, "frei")

    def test_die_anfrage_laeuft_auch_waehrend_eines_baus(self):
        self.sp.einbetten_schritt()
        self.lab.halter = {"owner": "devvm-build", "stale": False}
        self.assertEqual(self.sp.suche("VRAM", leser=S.CAPTAIN)["modus"], "hybrid", "G2-S7-i")
        self.assertEqual(self.sp.einbetten_schritt()["ende"], "pause")

    def test_der_dienst_nimmt_nie_eine_lease(self):
        quelle = Path(embed.__file__).read_text(encoding="utf-8")
        for verboten in ("try_acquire", "acquire(", "lease(", "clear_leftovers"):
            self.assertNotIn(verboten, quelle.split('"""', 2)[2], verboten)


if __name__ == "__main__":
    unittest.main()
