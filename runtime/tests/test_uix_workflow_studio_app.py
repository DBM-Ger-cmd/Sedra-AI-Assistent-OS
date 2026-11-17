"""App „Workflow Studio“ (Sammel-App der Harness-Shell): n8n Workflows, Szenario Studio, Startassistent, Live & Debugger, Factory und
Freigaben in einem Aufbau wie die Vorlage. Geprüft werden Modi und Gruppen, der Startassistent (offene Angaben werden erkannt und
mit Eingaben geschlossen), der Ort, das Menü (die zusammengelegten Werkzeuge sind ausgeblendet) und die Verdrahtung in der Shell."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk.gateway import check_tool

UIX = Path(__file__).resolve().parents[1] / "src" / "sedra_runtime" / "uix"
NODE = shutil.which("node")


def node(skript):
    out = subprocess.run([NODE, "-e", skript], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr[:400]
    return json.loads(out.stdout)


def _lade(pfade):
    """Lädt die Browserskripte in Node in derselben Reihenfolge wie die Seite."""
    return "globalThis.sedraDom = {}; " + "".join("require(%s); " % json.dumps(str(UIX / p)) for p in pfade)


class WorkflowStudioApp(unittest.TestCase):
    @unittest.skipUnless(NODE, "node fehlt")
    def test_modi_und_wahl(self):
        res = node(_lade(["shells/harness/workflow_studio_geteilt.js", "shells/harness/workflow_studio_assist.js", "shells/harness/workflow_studio_live.js", "shells/harness/workflow_studio.js"]) +
                   "const W = globalThis.sedraHarness.workflow_studio;"
                   "process.stdout.write(JSON.stringify({modi: W.MODI.map(m=>[m.id, m.zellen.map(z=>z.type)]), wahl: [W.modusWahl('factory'), W.modusWahl('x'), W.modusWahl(null)], gruppen: W.GRUPPEN}));")
        modi = dict(res["modi"])
        self.assertEqual(list(modi), ["leitstand", "katalog", "editor", "factory", "freigaben",
                                      "verbindungen", "modelle", "hardware", "design"])
        self.assertEqual(modi["leitstand"], ["decision", "task"], "der Leitstand zeigt nur echte Werkzeuge")
        self.assertEqual(modi["factory"], ["project", "factory-laeufe"])
        self.assertEqual(res["wahl"], ["factory", "leitstand", "leitstand"])
        self.assertEqual(res["gruppen"], ["Leitstand", "Direkt arbeiten", "Vorbereitung", "Prüfen und verbessern", "Plattform & Design"],
                         "die Gruppen der Vorlage, ohne leere Gruppe")

    def test_notaus_und_design_sind_echt_verdrahtet(self):
        js = "".join((UIX / "shells" / "harness" / n).read_text(encoding="utf-8") for n in ("workflow_studio_geteilt.js", "workflow_studio_assist.js", "workflow_studio_live.js", "workflow_studio.js"))
        # derselbe Notaus wie im Editor: dieselben Verben, kein eigener Weg
        for verb in ("fabrik_stopp", "fabrik_status", "fabrik_freigeben"):
            self.assertIn(verb, js)
        editor = (UIX / 'ui' / 'workflow-editor.js').read_text(encoding='utf-8')
        self.assertIn('unifiedWorkspace', editor)
        self.assertIn("root.sedraWorkflowNotaus.attach(this)", editor)
        # das Design nutzt den Schlüssel und die Namen aus js/theme.js
        theme = (UIX / "js" / "theme.js").read_text(encoding="utf-8")
        self.assertIn("'sedra.theme'", theme)
        for name in ("retro", "klar", "nacht"):
            self.assertIn("'%s'" % name, theme)
            self.assertIn("'%s'" % name, js)

    @unittest.skipUnless(NODE, "node fehlt")
    def test_startassistent_erkennt_und_schliesst_offene_angaben(self):
        """Der Kern des Startassistenten: offene Angaben je Schritt werden gefunden, und nach dem Ausfüllen (so wie er es speichert) bleibt keine offen."""
        res = node(_lade(["ui/workflow-model.js", "ui/workflow-process.js"] + ["shells/harness/workflow_studio_geteilt.js", "shells/harness/workflow_studio_assist.js", "shells/harness/workflow_studio_live.js", "shells/harness/workflow_studio.js"]) +
                   "const W = globalThis.sedraHarness.workflow_studio; const P = globalThis.sedraWorkflowProcess; const M = globalThis.sedraWorkflowModel;"
                   "const doc = M.example(); const vorher = W.luecken(doc);"
                   "const doc2 = JSON.parse(JSON.stringify(doc));"
                   "doc2.nodes.forEach(n=>{ if(n.type.endsWith('.stickyNote')) return; const meta = P.get(n) || P.blank(n);"
                   "  if(meta.kind==='annotation') return;"
                   "  ['role','input','output','evidence','completion'].forEach(k=>{ if(!(meta[k]||'').trim() && !(k==='input'&&meta.kind==='start') && !(k==='output'&&meta.kind==='end')) meta[k]='ausgefüllt'; });"
                   "  P.set(n, meta); });"
                   "process.stdout.write(JSON.stringify({vorher: vorher.length, nachher: W.luecken(doc2).length, erster: vorher[0] ? vorher[0].fehlt.map(f=>f[0]) : []}));")
        self.assertGreater(res["vorher"], 0, "das Beispiel hat offene Angaben, sonst prüft der Test nichts")
        self.assertEqual(res["nachher"], 0, "nach dem Ausfüllen darf nichts mehr offen sein")
        self.assertTrue(set(res["erster"]) <= {"role", "input", "output", "evidence", "completion"})

    def test_navigation_wie_die_vorlage(self):
        css = (UIX / "shells" / "harness" / "workflow_studio.css").read_text(encoding="utf-8")
        self.assertIn(".hs-ws-nav{", css)
        self.assertIn("var(--panel)", css)
        shell = (UIX / "shells" / "harness" / "shell.yaml").read_text(encoding="utf-8")
        self.assertIn("workflow_studio.css", shell)

    def test_ort_menue_und_werkzeug(self):
        orte = {o["id"]: o for o in json.loads((UIX / "ui" / "orte_kern.json").read_text(encoding="utf-8"))["orte"]}
        self.assertEqual(orte["workflow-studio"]["object"], {"type": "workflow-studio", "id": "app", "title": "SEDRA Workflow Studio"})
        gruppen = json.loads((UIX / "shells" / "harness" / "start_gruppen.json").read_text(encoding="utf-8"))
        self.assertEqual(gruppen["zuordnung"]["workflow-studio"], "arbeit")
        for alt in ("workflow", "scenario", "factory-studio"):
            self.assertIn(alt, gruppen["ausblenden"], f"{alt}: steckt jetzt in der App, nicht mehr im Menü")
        yml = yaml.safe_load((UIX / "tools" / "workflow-studio" / "tool.yaml").read_text(encoding="utf-8"))
        man, fehler = check_tool(yml, UIX / "tools" / "workflow-studio", "package")
        self.assertEqual(fehler, [])
        self.assertEqual(man["handles"], ["workflow-studio"])

    def test_verdrahtung_in_der_harness_shell(self):
        shell = (UIX / "shells" / "harness" / "shell.yaml").read_text(encoding="utf-8")
        self.assertIn("workflow_studio.js", shell)
        for teil in ("workflow_studio_geteilt.js", "workflow_studio_assist.js", "workflow_studio_live.js"):
            self.assertIn(teil, shell)
        self.assertLess(shell.index("workflow_studio.js"), shell.index("shell.js]"), "shell.js muss zuletzt stehen")
        app = (UIX / "shells" / "harness" / "app.js").read_text(encoding="utf-8")
        self.assertIn("objekt.type === 'workflow-studio'", app)
        self.assertIn("ws.abbauen", app)
        self.assertIn("ws.zeichnen", app)

    def test_andere_shells_unangetastet(self):
        """Die übrigen Shells werden nicht weiterentwickelt: diese App ändert nur die Harness-Shell (und das Icon, das jede Shell liest)."""
        icons = (UIX / "shells" / "minimal" / "icons.js").read_text(encoding="utf-8")
        self.assertIn("'workflow-studio': 'maschine'", icons)


if __name__ == "__main__":
    unittest.main()
