"""Differenztest-Faelle fuer den A/B-Bau (ab_bau.py): am0_shell_regeln. Diese Spec ist NICHT auf die Randfall-Muster der Checkliste geschaerft
(docs/CODER_PROFIL_UND_WORKFLOW_2026-11-11.md Abschnitt 5). Nur Faelle, die die Spec eindeutig festlegt: trust ausser genau "COMMUNITY" (auch None, Zahlen, Listen),
doc kein dict, dateien als Liste, Tupel, Menge oder etwas anderes, shell.css in jeder Gross- und Kleinschreibung und mit Unterordner, gesetzt = nicht None, "", False, {}, [].
Bewusst NICHT enthalten: 0 und 0.0 (gleich False in Python, die Spec sagt dazu nichts Eindeutiges)."""

MODUL = "shell_regeln"

V = {"titel": "x"}
VORGABEN = [V, {"a": 1}, 1, True, "text", [1], (), (1,), {1}, 2.5, None, "", False, {}, []]
ENTRIES = [None, "", False, {}, [], {"js": ["x.js"]}, "x.js", 1, True, ["x.js"], (), (1,)]
DOCS = [None, "text", 5, [1], [], (), {}, {"vorgabe": V}, {"entry": {"js": ["x"]}}, {"vorgabe": None, "entry": None}, {"vorgabe": "", "entry": ""}, {"vorgabe": False}, {"vorgabe": {}},
        {"vorgabe": []}, {"VORGABE": V}, {"Vorgabe": V}] + [{"vorgabe": v, "entry": e} for v in VORGABEN for e in ENTRIES]
TRUSTS = ["COMMUNITY", "CORE", "CAPTAIN", "SEDRA_BUILT", "community", "Community", "COMMUNITY ", " COMMUNITY", "", None, 5, ["COMMUNITY"], ("COMMUNITY",), True, {"COMMUNITY"}, "x"]
DATEIEN = [[], ["shell.css"], ["Shell.css"], ["SHELL.CSS"], ["sub/shell.css"], ["sub/SHELL.CSS"], ["./shell.css"], ["shell.css "], [" shell.css"], ["shell.css.bak"], ["xshell.css"], ["shell.yaml", "README.md"],
           ["shell.yaml", "shell.css", "README.md"], ["sub/shell.css", "Shell.Css"], ("shell.css",), ("a", "b"), {"shell.css"}, {"SHELL.CSS"}, {"a"},
           None, "shell.css", 5, {"shell.css": 1}, [1, None, "shell.css"], [None], [["shell.css"]], [b"shell.css"], "", ["", "shell.css"], (), set()]
KINDS = ["shell", "tool", "Shell", "SHELL", "shell ", "", None, 5, ["shell"], ("shell",), "workflow"]
FRAMES = [None, True, False, {}, [], "x", 1, {"vorgabe": V}, {"vorgabe": None}, 0]


def faelle(ref):
    return {
        "pruefe_shell": [(d, t, f) for d in DOCS for t in TRUSTS[:5] + [None, 5, ["COMMUNITY"]] for f in DATEIEN[:3]]
                        + [(d, "COMMUNITY", f) for d in DOCS[:30] for f in DATEIEN]
                        + [(d, t, ["shell.css"]) for d in DOCS[:30] for t in TRUSTS],
        "pruefe_einbau": [(k, d) for k in KINDS for d in DOCS],
        "darf_code_laden": [(t, f) for t in TRUSTS for f in FRAMES],
    }
