"""AM2-12 bis AM2-18 (SPEC_APPS_v1_AM2_ORTE_UND_GRUNDFUNKTIONEN §2.3): die sieben Grundfunktionen, ihre Werkzeuge im Paket, die Erklärung je Shell, Warnungen statt Fehler,
Archiv und Einstieg, Überdeckung durch einen App-Ort."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk import grundfunktionen as gf
from sedra_runtime.desk import orte
from sedra_runtime.desk.gateway import Gateway, check_shell, check_tool

NODE = shutil.which("node")
UIX = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix"


class Bausteine(unittest.TestCase):
    def test_sieben_grundfunktionen_mit_je_einem_werkzeug(self):
        self.assertEqual(len(gf.NAMEN), 7)
        self.assertEqual(sorted(gf.WERKZEUG), sorted(gf.NAMEN))
        self.assertEqual(len(set(gf.WERKZEUG.values())), 7)

    def test_tool_feld_nur_im_paket_und_core(self):
        self.assertEqual(gf.pruefe_tool_feld("logbuch", "CORE", "package"), [])
        self.assertEqual(gf.pruefe_tool_feld("logbuch", "COMMUNITY", "local"), ["grundfunktion_nur_im_paket"])
        self.assertEqual(gf.pruefe_tool_feld("logbuch", "CAPTAIN", "local"), ["grundfunktion_nur_im_paket"])
        self.assertEqual(gf.pruefe_tool_feld("logbuch", "CORE", "local"), ["grundfunktion_nur_im_paket"])
        self.assertEqual(gf.pruefe_tool_feld("etwas", "CORE", "package"), ["grundfunktion_unbekannt"])
        self.assertEqual(gf.pruefe_tool_feld(None, "CORE", "package"), [])

    def test_erklaerung_formen(self):
        slots = ["talk", "dock"]
        self.assertEqual(gf.pruefe_erklaerung({"logbuch": "ort", "gespraech": "slot:talk", "aufgaben": "eigen", "modus_grenzen": "verwaltung"}, slots), [])
        self.assertEqual(gf.pruefe_erklaerung({"logbuch": "irgendwie"}, slots), ["grundfunktion_art_ungueltig:logbuch"])
        self.assertEqual(gf.pruefe_erklaerung({"gespraech": "slot:inbox"}, slots), ["grundfunktion_art_ungueltig:gespraech"], "der Slot muss die Shell tragen")
        self.assertEqual(gf.pruefe_erklaerung({"keller": "ort"}, slots), ["grundfunktion_unbekannt:keller"])
        self.assertEqual(gf.pruefe_erklaerung(["ort"], slots), ["grundfunktionen_ungueltig"])
        self.assertEqual(gf.pruefe_erklaerung(None, slots), [])

    def test_warnungen_je_fehlender_erklaerung(self):
        w = gf.warnungen({"logbuch": "ort"}, ["dock"])
        self.assertEqual(sorted(w), sorted("grundfunktion_nicht_erklaert:" + n for n in gf.NAMEN if n != "logbuch"))

    def test_warnung_wenn_die_shell_nicht_traegt_was_sie_erklaert(self):
        self.assertEqual(gf.warnungen({n: "ort" for n in gf.NAMEN}, ["talk"]), ["grundfunktion_nicht_erreichbar:" + n for n in gf.NAMEN])
        self.assertEqual(gf.warnungen({**{n: "ort" for n in gf.NAMEN}, "gespraech": "slot:talk"}, ["dock"]), ["grundfunktion_nicht_erreichbar:gespraech"])

    def test_archiv_und_einstieg_muessen_nur_module_berechtigungen_erklaeren(self):
        self.assertEqual(gf.warnungen({}, ["chooser"], archiv=True), ["grundfunktion_nicht_erklaert:module_berechtigungen"])
        self.assertEqual(gf.warnungen({"module_berechtigungen": "eigen"}, ["chooser"], einstieg=True), [])

    def test_rahmen_erklaert_aus_seinen_slots(self):
        voll = gf.aus_rahmen(["dock", "talk", "strip", "tree", "palette", "inbox"])
        self.assertEqual(voll["gespraech"], "slot:talk")
        self.assertEqual(voll["entscheidungen"], "slot:inbox")
        self.assertEqual(sorted(voll), sorted(gf.NAMEN))
        self.assertEqual(gf.warnungen(voll, ["dock", "talk", "strip", "tree", "palette", "inbox"]), [])
        ohne = gf.aus_rahmen(["dock", "talk"])
        self.assertEqual(sorted(ohne), ["gespraech"], "ohne Suche und Karte kann der Rahmen nicht mehr erklären")

    def test_app_ort_mit_dem_objekttyp_einer_grundfunktion_wird_abgewiesen(self):
        ort = {"id": "mein-ort", "label": "x", "hint": "", "words": ["zauberwort"], "object": {"type": "task", "id": "alle"}}
        self.assertIn("grundfunktion_ueberdeckt", orte.pruefe_ort(ort, ["task"], "x"))
        ort["object"]["type"] = "rechnung"
        self.assertEqual(orte.pruefe_ort(ort, ["rechnung"], "x"), [])


class Paket(unittest.TestCase):
    def test_die_sieben_paket_werkzeuge_tragen_ihre_grundfunktion(self):
        for name, tid in gf.WERKZEUG.items():
            ordner = UIX / "tools" / tid
            man, fehler = check_tool(yaml.safe_load((ordner / "tool.yaml").read_text(encoding="utf-8")), ordner, "package")
            self.assertEqual(fehler, [], tid)
            self.assertEqual(man["grundfunktion"], name, tid)

    def test_kein_anderes_paket_werkzeug_traegt_eine(self):
        for ordner in sorted((UIX / "tools").iterdir()):
            if not (ordner / "tool.yaml").is_file() or ordner.name in gf.WERKZEUG.values():
                continue
            doc = yaml.safe_load((ordner / "tool.yaml").read_text(encoding="utf-8"))
            self.assertNotIn("grundfunktion", doc["tool"], ordner.name)

    def test_jede_paket_shell_ist_gueltig_und_hat_hoechstens_warnungen(self):
        for ordner in sorted((UIX / "shells").iterdir()):
            if not (ordner / "shell.yaml").is_file() or ordner.name.startswith("_"):
                continue
            man, fehler = check_shell(yaml.safe_load((ordner / "shell.yaml").read_text(encoding="utf-8")), ordner, "package")
            self.assertEqual(fehler, [], ordner.name)
            self.assertIsInstance(man["grundfunktionen_warnungen"], list)

    def test_die_erklaerten_shells_haben_keine_warnung(self):
        for shell in ("harness", "cockpit", "paperclip", "minimal", "fisch"):
            ordner = UIX / "shells" / shell
            man, _ = check_shell(yaml.safe_load((ordner / "shell.yaml").read_text(encoding="utf-8")), ordner, "package")
            self.assertEqual(man["grundfunktionen_warnungen"], [], shell)
            self.assertEqual(sorted(man["grundfunktionen"]), sorted(gf.NAMEN), shell)

    def test_luecken_sind_sichtbar_kmu_start_und_xp(self):
        kmu, _ = check_shell(yaml.safe_load((UIX / "shells" / "gateway-kmu" / "shell.yaml").read_text(encoding="utf-8")), UIX / "shells" / "gateway-kmu", "package")
        self.assertEqual(kmu["grundfunktionen_warnungen"], [], "AM7-08/09: die KMU-Shell erklärt seit der Rollen-Sicht alle sieben (Verwaltung)")
        for shell in ("start", "sedra-xp"):
            man, _ = check_shell(yaml.safe_load((UIX / "shells" / shell / "shell.yaml").read_text(encoding="utf-8")), UIX / "shells" / shell, "package")
            self.assertEqual(man["grundfunktionen_warnungen"], ["grundfunktion_nicht_erklaert:module_berechtigungen"], shell)

    def test_vorgabe_shells_bekommen_die_erklaerung_vom_rahmen(self):
        for shell in ("wissensbasis", "gateway-studio"):
            ordner = UIX / "shells" / shell
            man, fehler = check_shell(yaml.safe_load((ordner / "shell.yaml").read_text(encoding="utf-8")), ordner, "package")
            self.assertEqual(fehler, [], shell)
            self.assertEqual(man["grundfunktionen"]["gespraech"], "slot:talk", shell)
            self.assertEqual(man["grundfunktionen_warnungen"], [], shell)


class Gateway_(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am2-gf-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def lokal(self, art, id, text, js=True):
        ordner = self.root / "local_config" / art / id
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / ("tool.yaml" if art == "tools" else "shell.yaml")).write_text(text, encoding="utf-8")
        if js:
            (ordner / ("tool.js" if art == "tools" else "shell.js")).write_text("// x\n", encoding="utf-8")

    def test_lokales_werkzeug_mit_grundfunktion_wird_abgewiesen(self):
        self.lokal("tools", "falsch", 'tool:\n  id: falsch\n  name: F\n  version: 1.0.0\n  kind: object\n  handles: [task]\n  grundfunktion: logbuch\n'
                                      '  entry: {js: tool.js}\n  trust: CAPTAIN\n  needs: {ui: ">=1.0 <2"}\n')
        gw = Gateway(self.root)
        gruende = {r["id"]: r["reasons"] for r in gw.manifest()["rejected"]}
        self.assertEqual(gruende["falsch"], ["grundfunktion_nur_im_paket"])

    def test_manifest_meldet_die_warnungen_der_shells(self):
        gw = Gateway(self.root)
        grund = {(w["id"], w["grund"]) for w in gw.manifest()["warnungen"]}
        self.assertFalse([g for g in grund if g[0] == "gateway-kmu" and g[1].startswith("grundfunktion")], "AM7-08/09: die KMU-Shell erklärt alle sieben")
        self.assertIn(("start", "grundfunktion_nicht_erklaert:module_berechtigungen"), grund)
        self.assertFalse([g for g in grund if g[0] == "harness" and g[1].startswith("grundfunktion")])

    def test_lokale_shell_mit_falscher_erklaerung_wird_abgewiesen(self):
        self.lokal("shells", "meine", 'shell:\n  id: meine\n  name: M\n  version: 1.0.0\n  entry: {js: shell.js}\n  provides: [dock, talk]\n  trust: CAPTAIN\n'
                                      '  needs: {ui: ">=1.0 <2"}\n  grundfunktionen: {logbuch: irgendwie, keller: ort}\n')
        gw = Gateway(self.root)
        gruende = {r["id"]: r["reasons"] for r in gw.manifest()["rejected"]}
        self.assertEqual(sorted(gruende["meine"]), ["grundfunktion_art_ungueltig:logbuch", "grundfunktion_unbekannt:keller"])

    def test_werkzeug_mit_grundfunktion_ist_in_jeder_shell_sichtbar(self):
        gw = Gateway(self.root)
        m = gw.manifest()
        self.assertEqual(sorted(t["id"] for t in m["tools"] if t.get("grundfunktion")), sorted(gf.WERKZEUG.values()))
        self.assertFalse([e for e in m["nicht_in_dieser_shell"] if e["id"] in gf.WERKZEUG.values()])


class Anzeige(unittest.TestCase):
    @unittest.skipUnless(NODE, "node fehlt")
    def test_satz_im_werkzeug_module(self):
        skript = ("const m = require(%s);process.stdout.write(JSON.stringify([m.grundfunktionenSatz(['grundfunktion_nicht_erklaert:logbuch','grundfunktion_nicht_erreichbar:aufgaben']), m.grundfunktionenSatz([]), m.grundfunktionenSatz(null)]));")
        out = subprocess.run([NODE, "-e", skript % json.dumps(str(UIX / "tools" / "modules" / "tool.js"))], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout), ["Grundfunktionen · nicht erklärt: Logbuch · erklärt, aber nicht erreichbar: Aufgaben", "", ""])


if __name__ == "__main__":
    unittest.main()
