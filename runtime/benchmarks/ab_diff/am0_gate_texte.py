"""Differenztest-Faelle fuer den A/B-Bau (ab_bau.py): am0_gate_texte. Diese Spec ist NICHT auf die Randfall-Muster der Checkliste geschaerft
(docs/CODER_PROFIL_UND_WORKFLOW_2026-11-11.md Abschnitt 5). Nur Faelle, die die Spec eindeutig festlegt: Eintraege, die kein Text sind oder nicht genau mit "GET " beginnen
(klein geschrieben, mit fuehrendem Leerzeichen, "GET" ohne Pfad), doppelte Pfade (die erste zaehlt), routen keine Liste (Tupel, Text, None), funde mit leeren und
nicht-Text-Eintraegen, funde keine Liste, Eingaben nicht veraendern (die Ergebnisse werden verglichen), unbekannte art -> ValueError."""

MODUL = "gate_texte"

ROUTEN = [[], ["GET /api/a"], ["GET /api/a", "GET /api/b"], ["GET /api/b", "GET /api/a", "GET /api/b"], ["GET /api/a", "GET /api/a"], ["POST /api/x"], ["GET "], ["GET"], ["get /api/a"],
          [" GET /api/a"], ["GET  /api/a"], ["GET /api/a ", "GET /api/a"], ["GET /x", "POST /x", "GET /y"], ["GET /api/gateway/*"], ["GET GET /a"], ["GET /A", "GET /a"],
          [5, None, "GET /api/a"], [["GET /a"]], [b"GET /a"], ["GET\t/a"], ["GET /ä", "GET /ä"], ["GET x"], ["", "GET /a"], ["GET /a", None, 5, "GET /b"],
          None, "GET /api/a", ("GET /api/a",), {"GET /api/a"}, {"GET /a": 1}, 5, True, ""]
FUNDE = [None, [], [""], ["x"], ["x", "", "y"], [None, "x", 5, "y"], ["x", ["y"]], ["  "], ["a", "a"], ("x",), "x", {"x"}, {"x": 1}, 5, [b"x"], [True, "x"], ["ä", "–"], ["", ""]]
ARTEN = ["tool", "shell", "Tool", "SHELL", "tool ", "", None, 5, ["tool"], "workflow", "tools"]


def faelle(ref):
    return {
        "leserouten_text": [(r,) for r in ROUTEN],
        "risiken_werkzeug": [(r, f) for r in ROUTEN for f in FUNDE] + [(r,) for r in ROUTEN],
        "risiken_shell": [(f,) for f in FUNDE] + [()],
        "risiken": [(a, r, f) for a in ARTEN for r in ROUTEN[:8] + [None] for f in FUNDE[:8]] + [(a,) for a in ARTEN],
    }
