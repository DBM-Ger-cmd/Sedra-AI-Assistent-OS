"""Der Kerndienst Wissen (SPEC_WISSEN_KERN_v1 WK-01, WK-02, WK-06; G2 K1 §2): `fragen` bei aus, Fehler und Treffern, der Cloud-Filter als
zweite Sperre, die Grenze für k, der Block nur bei Treffern und als fremde Daten, der Systemsatz fest je Konfiguration, die Zitatprüfung
mit Kennungen aus dem Werkzeug, die Route aus dem Anbieter. Mit einem Speicher-Ersatz: keine Datenbank, kein Modell, kein Netz."""
import unittest
from types import SimpleNamespace

from sedra_runtime.wissen import ausgabe, dienst
from sedra_runtime.wissen.speicher import CAPTAIN, leser

A, B = "W0123456789ab", "Wbbbbbbbbbbbb"


def treffer(id, personenbezug=0, text="Vor dem Laden die Lease holen."):
    return {"id": id, "datei": "docs/werkbank.md", "stelle": "Werkbank > Lease", "datum": "2026-11-05", "hash": "h", "text": text, "personenbezug": personenbezug}


class Speicher:
    def __init__(self, ergebnis=None, fehler=None, datamarking=False):
        self.konfig = SimpleNamespace(kontext_treffer=5, je_treffer=1600, gesamt=8000, datamarking=datamarking)
        self.ergebnis, self.fehler, self.aufrufe, self.ereignisse = ergebnis, fehler, [], []

    def suche(self, frage, **kw):
        self.aufrufe.append((frage, kw))
        if self.fehler:
            raise ValueError(self.fehler)
        return self.ergebnis

    def audit(self, event, payload):
        self.ereignisse.append((event, payload))


class Fragen(unittest.TestCase):
    def test_ohne_speicher_ist_es_aus(self):
        a = dienst.fragen(None, "Lease", leser=CAPTAIN, route="local")
        self.assertEqual((a.art, a.treffer, a.code, a.ergebnis), ("aus", [], "wissen_aus", None))
        self.assertIn("abgeschaltet", a.hinweis)
        self.assertEqual(dienst.block(None, a), [])

    def test_fehler_der_suche_wird_satz(self):
        sp = Speicher(fehler="wis_anfrage_leer")
        a = dienst.fragen(sp, "", leser=CAPTAIN, route="local")
        self.assertEqual((a.art, a.code, a.ergebnis), ("fehler", "wis_anfrage_leer", None))
        self.assertNotEqual(a.hinweis, "wis_anfrage_leer", "der deutsche Satz, nicht der Code")

    def test_treffer_und_argumente_der_suche(self):
        sp = Speicher({"modus": "hybrid", "treffer": [treffer(A)], "hinweis": None})
        a = dienst.fragen(sp, "Lease", leser=CAPTAIN, route="local", filter={"quellen": ["Q1"]}, mission_id="M-1")
        self.assertEqual((a.art, a.ids), ("hybrid", [A]))
        frage, kw = sp.aufrufe[0]
        self.assertEqual((frage, kw["leser"], kw["route"], kw["k"], kw["filter"], kw["protokoll"]), ("Lease", CAPTAIN, "local", 5, {"quellen": ["Q1"]}, False))

    def test_k_wird_begrenzt(self):
        sp = Speicher({"modus": "volltext", "treffer": []})
        dienst.fragen(sp, "x", leser=CAPTAIN, route="local", k=99)
        dienst.fragen(sp, "x", leser=CAPTAIN, route="local", k=0)
        self.assertEqual([kw["k"] for _, kw in sp.aufrufe], [20, 1])

    def test_unbekannte_route_gilt_als_cloud(self):
        sp = Speicher({"modus": "hybrid", "treffer": [treffer(A, 1), treffer(B)]})
        a = dienst.fragen(sp, "x", leser=leser("agent", 4, None, "A-1"), route="irgendwas")
        self.assertEqual(sp.aufrufe[0][1]["route"], "cloud")
        self.assertEqual(a.ids, [B], "Personenbezug geht nie in die Cloud (WIS-11)")
        self.assertEqual(sp.ereignisse, [("WIS_CLOUD_GEFILTERT", {"mission_id": None, "ids": [A]})])

    def test_lokal_behaelt_personenbezug(self):
        sp = Speicher({"modus": "hybrid", "treffer": [treffer(A, 1)]})
        self.assertEqual(dienst.fragen(sp, "x", leser=CAPTAIN, route="local").ids, [A])
        self.assertEqual(sp.ereignisse, [])


class Block(unittest.TestCase):
    def test_ohne_treffer_kein_block(self):
        sp = Speicher({"modus": "hybrid", "treffer": []})
        self.assertEqual(dienst.block(sp, dienst.fragen(sp, "x", leser=CAPTAIN, route="local")), [])
        self.assertEqual(sp.ereignisse, [], "ohne Block kein WIS_KONTEXT")

    def test_block_ist_fremde_daten_mit_kennung(self):
        sp = Speicher({"modus": "hybrid", "treffer": [treffer(A)]})
        msgs = dienst.block(sp, dienst.fragen(sp, "x", leser=CAPTAIN, route="local"), mission_id="M-1")
        self.assertEqual([(m["role"], m["trust"]) for m in msgs], [("system", "system"), ("user", "untrusted")])
        self.assertEqual(msgs[0]["content"], ausgabe.SYSTEM_WISSEN)
        self.assertIn(f"[{A}]", msgs[1]["content"])
        ev, p = sp.ereignisse[-1]
        self.assertEqual((ev, p["ids"], p["modus"], p["mission_id"]), ("WIS_KONTEXT", [A], "hybrid", "M-1"))
        self.assertNotIn("Lease", str(sp.ereignisse), "kein Text der Quelle im Audit (WK-06)")

    def test_systemsatz_fest_je_konfiguration(self):
        self.assertEqual(dienst.systemsatz(Speicher()), dienst.systemsatz(Speicher()))
        self.assertEqual(dienst.systemsatz(Speicher(datamarking=True)), ausgabe.SYSTEM_WISSEN_MARKIERT)
        self.assertEqual(dienst.systemsatz(None), ausgabe.SYSTEM_WISSEN)


class Nachbereiten(unittest.TestCase):
    def setUp(self):
        self.ereignisse = []
        self.audit = lambda e, p: self.ereignisse.append((e, p))

    def test_fremde_kennung_wird_markiert(self):
        a = dienst.aus_ergebnis({"modus": "hybrid", "treffer": [treffer(A)], "hinweis": None})
        text = dienst.nachbereiten(f"Lease zuerst [{A}] und [W0000000000].", a, audit=self.audit, mission_id="M-1")
        self.assertIn("stammt nicht aus den gefundenen Stellen", text)
        self.assertEqual(self.ereignisse, [("WIS_ZITAT_FREMD", {"mission_id": "M-1", "ids": ["W0000000000"]})])

    def test_kennung_aus_dem_werkzeug_gilt(self):
        text = dienst.nachbereiten(f"Siehe [{B}].", None, audit=self.audit, weitere_ids=[B])
        self.assertNotIn("Hinweis", text)
        self.assertEqual(self.ereignisse, [])

    def test_fehlende_zitate_bekommen_die_fundstellen_und_den_hinweis(self):
        a = dienst.aus_ergebnis({"modus": "volltext", "treffer": [treffer(A)], "hinweis": "Nur Volltextsuche (x): …"})
        text = dienst.nachbereiten("Ohne Beleg.", a, audit=self.audit)
        self.assertIn(f"Gefundene Stellen: [{A}]", text)
        self.assertTrue(text.endswith("Nur Volltextsuche (x): …"))
        self.assertEqual(self.ereignisse[0][0], "WIS_ZITAT_FEHLT")

    def test_ohne_ergebnis_kein_hinweis(self):
        self.assertEqual(dienst.nachbereiten("Text.", dienst.aus_ergebnis(None), audit=self.audit), "Text.")


class Route(unittest.TestCase):
    def test_route_aus_anbieter(self):
        router = SimpleNamespace(adapters={"lokal": SimpleNamespace(route="local"), "wolke": SimpleNamespace(route="cloud")})
        self.assertEqual([dienst.route_aus_anbieter(a, router) for a in ("lokal", "wolke", "unbekannt", None)], ["local", "cloud", "cloud", "cloud"])
        self.assertEqual(dienst.route_aus_anbieter("llama-cpp-server"), "local", "der Modellserver der Harness")
        self.assertEqual(dienst.route_aus_anbieter("langdock"), "cloud")


class Labor(unittest.TestCase):
    """K1 (05.11.2026): Wissen ist Standard an; sein Start legt kein testlab.db an, ohne Datei ist die GPU frei."""

    def test_ohne_datei_frei_und_nichts_angelegt(self):
        import tempfile
        from pathlib import Path
        from sedra_runtime.wissen.embed import TestLabZugang, VerzoegertesLabor
        with tempfile.TemporaryDirectory() as tmp:
            pfad = Path(tmp) / "testlab" / "testlab.db"
            geoeffnet = []
            lab = VerzoegertesLabor(pfad, lambda p: geoeffnet.append(p))
            self.assertEqual(TestLabZugang(lab).lage().zustand, "frei")
            self.assertFalse(pfad.exists())
            self.assertEqual(geoeffnet, [], "ohne Datei wird das Labor nicht geöffnet")


if __name__ == "__main__":
    unittest.main()
