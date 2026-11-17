"""App Coder (Sedra IDE, SPEC_SEDRA_IDE_2026-11-16): Ort, Start-Menü, Manifest, Rahmen-Seite und die harten Regeln der Spec
(Zeilenzahl, kein Netz, kein eval, keine Hex-Farben ausserhalb der Tokens, Texte in de und en gleich, Syntax). Kein Browser-Test."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk.gateway import OBJECT_TYPES, check_tool

UIX = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix"
TOOL = UIX / "tools" / "coder"
NODE = shutil.which("node")
GEHALTEN = {".js", ".css"}
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
ADRESSE = re.compile(r"(?:https?:)?//[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,}")
VERBOTEN = re.compile(r"\beval\s*\(|\bnew\s+Function\b|\binnerHTML\b|\bouterHTML\b|insertAdjacentHTML|document\.write|\bsetInterval\b|"
                      r"\bfetch\s*\(|XMLHttpRequest|WebSocket|EventSource|sendBeacon|@latest")


def dateien():
    return sorted(p for p in TOOL.iterdir() if p.suffix in GEHALTEN)


class Anmeldung(unittest.TestCase):
    def test_ort_menue_und_typ(self):
        orte = {o["id"]: o for o in json.loads((UIX / "ui" / "orte_kern.json").read_text(encoding="utf-8"))["orte"]}
        self.assertEqual(orte["coder"]["label"], "Coder")
        self.assertEqual(orte["coder"]["object"], {"type": "coder", "id": "app", "title": "Coder"})
        self.assertIn("coder", OBJECT_TYPES)
        gruppen = json.loads((UIX / "shells" / "harness" / "start_gruppen.json").read_text(encoding="utf-8"))
        self.assertEqual(gruppen["zuordnung"]["coder"], "arbeit")
        places = (UIX / "ui" / "places.js").read_text(encoding="utf-8")
        self.assertIn("id: 'coder'", places)

    def test_manifest_ohne_routen_im_rahmen(self):
        yml = yaml.safe_load((TOOL / "tool.yaml").read_text(encoding="utf-8"))
        man, fehler = check_tool(yml, TOOL, "package")
        self.assertEqual(fehler, [])
        self.assertEqual(man["handles"], ["coder"])
        self.assertEqual(man["api"], ["GET /api/uix/coder/projekte", "GET /api/uix/coder/dateien/*", "GET /api/uix/coder/datei/*",
                                "GET /api/uix/coder/aenderungen/*", "GET /api/uix/coder/original/*", "GET /api/uix/coder/modelle", "POST /api/uix/coder/agent",
                                "POST /api/uix/coder/speichern", "GET /api/uix/coder/speichern/*", "POST /api/uix/coder/speichern/anwenden"],
                         "Lese-Routen; Agent: Modelle lesen und eine Frage stellen (kein Schreibweg); Speichern nur als Antrag an die Freigaben (E4)")
        self.assertEqual(man["trust"], "CAPTAIN", "Rahmen-Werkzeug, nie in der Seite der Shell")
        for name in man["js"] + man["css"]:
            self.assertTrue((TOOL / Path(name).name).is_file(), name)
        self.assertEqual(man["js"][-1].rsplit("/", 1)[-1], "tool.js", "tool.js zuletzt: es startet die IDE")
        eingebunden = {Path(n).name for n in man["js"] + man["css"]}
        self.assertEqual({p.name for p in dateien()}, eingebunden, "jede Datei ist eingebunden, keine fehlt")


class Lader(unittest.TestCase):
    def test_rahmen_in_losem_container_wird_nach_dem_einhaengen_angemeldet(self):
        """Die Harness-Shell mountet Apps in losen Containern: der Rahmen hat dann noch kein contentWindow. Ohne späte Anmeldung
        kennt die Brücke ihn nicht ('Nachricht aus unbekannter Quelle abgelehnt') und jede Route im Rahmen läuft in die Zeitgrenze."""
        text = (UIX / "ui" / "loader.js").read_text(encoding="utf-8")
        self.assertIn("MutationObserver", text)
        self.assertIn("fenster.isConnected", text)
        self.assertIn("bruecke.abmelden(fenstergriff)", text)
        self.assertNotIn("bruecke.register(fenster.contentWindow", text, "nie mit einem möglicherweise leeren Fenster anmelden")


class Regeln(unittest.TestCase):
    def test_jede_datei_hoechstens_400_zeilen(self):
        for p in dateien() + [TOOL / "tool.yaml", TOOL / "README.md"]:
            n = len(p.read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(n, 400, f"{p.name}: {n} Zeilen")

    def test_kein_netz_kein_eval_keine_hex_farben(self):
        for p in dateien():
            for nr, zeile in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                z = zeile.replace("http://www.w3.org/2000/svg", "")        # Namensraum-Kennung, kein Abruf
                self.assertIsNone(ADRESSE.search(z), f"{p.name}:{nr} Netzadresse")
                self.assertIsNone(VERBOTEN.search(z), f"{p.name}:{nr} verboten: {zeile.strip()[:60]}")
                if p.name != "tokens.css":
                    self.assertIsNone(HEX.search(z), f"{p.name}:{nr} Hex-Farbe ausserhalb der Tokens")

    def test_kein_browserspeicher_und_nur_eigener_container(self):
        for p in dateien():
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("localStorage", text, f"{p.name}: im Rahmen gibt es keinen Speicher")
            self.assertNotIn("sessionStorage", text, p.name)
            if p.suffix == ".css":
                bloecke = re.sub(r"/\*.*?\*/", "", text, flags=re.S).split("}")
                for b in bloecke:
                    sel = b.split("{")[0].strip()
                    if sel and not sel.startswith("@"):
                        self.assertTrue(sel.startswith(".t-coder"), f"{p.name}: {sel[:40]}")

    def test_texte_de_en_gleich_und_vollstaendig(self):
        de = set(re.findall(r"(?:^|[\s,{])([a-zA-Z_]\w*):\s*['\"]", (TOOL / "texte_de.js").read_text(encoding="utf-8"), flags=re.M))
        en = set(re.findall(r"(?:^|[\s,{])([a-zA-Z_]\w*):\s*['\"]", (TOOL / "texte_en.js").read_text(encoding="utf-8"), flags=re.M))
        self.assertEqual(sorted(de - en), [])
        self.assertEqual(sorted(en - de), [])
        benutzt, vorsaetze = set(), set()
        for p in dateien():
            if p.suffix == ".js":
                quelle = p.read_text(encoding="utf-8")
                benutzt |= set(re.findall(r"\bT\('([a-zA-Z_]\w*)'\s*[,)]", quelle))
                vorsaetze |= set(re.findall(r"\bT\('([a-zA-Z_]\w*_)'\s*\+", quelle))
        self.assertEqual(sorted(k for k in benutzt if k not in de), [])
        for v in vorsaetze:
            self.assertTrue(any(k.startswith(v) for k in de), f"kein Text mit Vorsatz {v}")

    @unittest.skipUnless(NODE, "node fehlt")
    def test_syntax_aller_skripte(self):
        for p in dateien():
            if p.suffix == ".js":
                out = subprocess.run([NODE, "--check", str(p)], capture_output=True, text=True, encoding="utf-8", timeout=60)
                self.assertEqual(out.returncode, 0, f"{p.name}: {out.stderr[:200]}")


if __name__ == "__main__":
    unittest.main()
