"""`wissen/adapter.py` (Spec 7, D7.3; WIS-01): die drei bestehenden Speicher werden nur gelesen (Hash der Dateien vor und nach
Abgleich gleich, SQLite nur `mode=ro`), die Stücke tragen Stelle, Datei und Datum wie in D7.3; Markdown-Ordner nur `*.md`/`*.txt`,
Logbuch je Zeile, Vorschläge aus `vorschlaege.jsonl` je Partition."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.wissen import adapter
from wissen_fixture import repo_anlegen, speicher_anlegen

SPEICHER = ("runtime_data/knowledge/records.jsonl", "local_config/arbeitsumfeld/wissen.sqlite", "local_config/gateway/wissen.sqlite")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Adapter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wissen-adapter-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = repo_anlegen(Path(self.tmp.name) / "repo")
        self.projekt = speicher_anlegen(Path(self.tmp.name) / "projekt")

    def ad(self, name):
        return adapter.adapter_fuer(name, repo_root=self.repo, projekt_root=self.projekt)

    def quelle(self, name, pfad, wurzel="projekt", **more):
        return {"id": "Q-1", "adapter": name, "wurzel": wurzel, "pfad": pfad, "muster": more.pop("muster", "*.md"), "stufe": 1, "projekt": None, "personenbezug": 0, **more}

    def stuecke(self, name, pfad, **kw):
        return list(self.ad(name).stuecke(self.quelle(name, pfad, **kw)))

    def test_die_drei_speicher_bleiben_unveraendert(self):
        vorher = {p: sha(self.projekt / p) for p in SPEICHER}
        for name, pfad in (("knowledge", SPEICHER[0]), ("arbeitsumfeld", SPEICHER[1]), ("gateway", SPEICHER[2] + "#wissen"), ("gateway", SPEICHER[2] + "#eigene")):
            ad = self.ad(name)
            q = self.quelle(name, pfad)
            self.assertTrue(list(ad.stuecke(q)), name)
            self.assertTrue(ad.quell_hash(q))
        self.assertEqual({p: sha(self.projekt / p) for p in SPEICHER}, vorher)

    def test_knowledge_liefert_notizen_und_lektionen_nur_aktive(self):
        out = self.stuecke("knowledge", SPEICHER[0])
        self.assertEqual([(d, s["stelle"]) for d, _, s in out], [("knowledge:KN-1", "Notiz Notiz zum Logbuch"), ("knowledge:KN-2", "Lektion Regex sauber")])
        self.assertEqual(out[0][1], "2026-10-20T08:00:00Z")
        self.assertIn("Auslöser: re.match(, regex", out[1][2]["text"])

    def test_arbeitsumfeld_und_gateway_tragen_art_und_was_tun(self):
        au = self.stuecke("arbeitsumfeld", SPEICHER[1])
        self.assertEqual([d for d, _, _ in au], ["arbeitsumfeld:AU-1", "arbeitsumfeld:AU-2"])
        self.assertEqual(au[0][2]["stelle"], "Ordner local_config")
        self.assertTrue(au[0][2]["text"].endswith("Quelle: Platte"))
        gw = self.stuecke("gateway", SPEICHER[2] + "#wissen")
        self.assertEqual((gw[0][0], gw[0][2]["stelle"]), ("gateway:R-07", "Regel R-07 Kartendaten"))
        self.assertIn("Was tun: Entwurf pseudonymisieren", gw[0][2]["text"])
        eigene = self.stuecke("gateway", SPEICHER[2] + "#eigene")
        self.assertEqual((eigene[0][0], eigene[0][1], eigene[0][2]["stelle"]), ("gateway:eigene:1", "2026-10-21T12:00:00Z", "Eigene Frage"))
        self.assertEqual(eigene[0][2]["text"], "Frage: Wo liegt die Steuernummer?\nAntwort: Im vertraulichen Ordner.")

    def test_ein_fehlender_speicher_ist_nicht_lesbar(self):
        (self.projekt / SPEICHER[1]).unlink()
        with self.assertRaisesRegex(ValueError, "wis_speicher_nicht_lesbar"):
            self.stuecke("arbeitsumfeld", SPEICHER[1])
        self.assertEqual(self.ad("arbeitsumfeld").quell_hash(self.quelle("arbeitsumfeld", SPEICHER[1])), "wis_speicher_nicht_lesbar")

    def test_markdown_ordner_nur_erlaubte_dateiarten_relative_pfade(self):
        (self.repo / "docs" / "skript.py").write_text("print(1)\n", encoding="utf-8")
        (self.repo / "docs" / ".git").mkdir()
        (self.repo / "docs" / ".git" / "x.md").write_text("# versteckt\n\nx\n", encoding="utf-8")
        out = self.stuecke("markdown", "docs", wurzel="repo")
        dateien = sorted({d for d, _, _ in out})
        self.assertEqual(dateien, ["docs/GEHEIM.md", "docs/GPU.md", "docs/LOGBUCH_AGENT_MANAGER.md"])
        self.assertEqual([s["stelle"] for d, _, s in out if d == "docs/GPU.md"], ["GPU-Regeln > Videospeicher", "GPU-Regeln > Lease"])
        self.assertTrue(all(len(datum) == 20 and datum.endswith("Z") for _, datum, _ in out))
        with self.assertRaisesRegex(ValueError, "wis_dateiart_nicht_erlaubt"):
            self.stuecke("markdown", "docs/skript.py", wurzel="repo")
        ad = self.ad("markdown")
        self.assertEqual(ad.pruefe_pfad(self.repo, "docs\\GPU.md", "*.md"), "docs/GPU.md")
        self.assertEqual(ad.quell_hash(self.quelle("markdown", "docs", wurzel="repo")), ad.quell_hash(self.quelle("markdown", "docs", wurzel="repo")))
        (self.repo / "docs" / "GPU.md").write_text("# Neu\n\nx\n", encoding="utf-8")
        self.assertNotEqual(ad.quell_hash(self.quelle("markdown", "docs", wurzel="repo")), ad.quell_hash(self.quelle("markdown", "docs/GEHEIM.md", wurzel="repo")))

    def test_logbuch_je_zeile_mit_datum_der_zeile(self):
        out = self.stuecke("logbuch", "docs/LOGBUCH_AGENT_MANAGER.md", wurzel="repo")
        self.assertEqual(out[0][2]["stelle"], "Logbuch Agent Manager")
        self.assertEqual((out[1][1], out[1][2]["stelle"]), ("2026-10-20T09:00", "Logbuch Agent Manager > Zeile 2026-10-20 09:00 BAU Erster Bau der Werkbank"))

    def test_zu_grosse_dateien_werden_gemeldet(self):
        ad = adapter.adapter_fuer("text", repo_root=self.repo, projekt_root=self.projekt, datei_max_bytes=10)
        gemeldet = []
        out = list(ad.stuecke(self.quelle("text", "notizen", wurzel="repo", muster="*.txt"), lambda d, g: gemeldet.append((d, g))))
        self.assertEqual((out, gemeldet), ([], [("notizen/plan.txt", "wis_datei_zu_gross")]))

    def test_vorschlaege_je_partition(self):
        p = self.projekt / adapter.VORSCHLAEGE
        p.parent.mkdir(parents=True, exist_ok=True)
        zeilen = [{"id": "WV-1", "titel": "Eins", "text": "Text eins", "stufe": 1, "projekt": None, "personenbezug": 0, "freigegeben": "2026-10-22T10:00:00Z"},
                  {"id": "WV-2", "titel": "Zwei", "text": "Text zwei", "stufe": 3, "projekt": "P", "personenbezug": 1, "freigegeben": "2026-10-22T11:00:00Z"}]
        p.write_text("".join(json.dumps(z) + "\n" for z in zeilen), encoding="utf-8")
        eins = self.stuecke("vorschlag", adapter.VORSCHLAEGE + "#Q-VS-1-alle-0", stufe=1, projekt=None, personenbezug=0)
        self.assertEqual([(d, s["stelle"], datum) for d, datum, s in eins], [("vorschlag:WV-1", "Vorschlag Eins", "2026-10-22T10:00:00Z")])
        zwei = self.stuecke("vorschlag", adapter.VORSCHLAEGE + "#Q-VS-3-P-1", stufe=3, projekt="P", personenbezug=1)
        self.assertEqual([d for d, _, _ in zwei], ["vorschlag:WV-2"])

    def test_unbekannter_adapter(self):
        with self.assertRaisesRegex(ValueError, "wis_adapter_unbekannt"):
            self.ad("quelltext")
        self.assertEqual({e["adapter"] for e in adapter.ERSTBESTUECKUNG}, {"markdown", "logbuch", "knowledge", "arbeitsumfeld", "gateway"})


if __name__ == "__main__":
    unittest.main()
