"""Bau-Spec am0_routen: Pruefung der Routen eines Moduls (AM0-03, Stufe A0 der Roadmap, G3 Schritt S4).
Drei Stufen S1 bis S3, je ein versteckter Test; kein eigener Test des Modells. Der Bau liefert nur das eigenstaendige Modul routen_pruefung.py;
den Einbau in desk/gateway.py macht Claude spaeter von Hand (Kandidat wird erst nach Durchsicht des Captains uebernommen).
Referenz: benchmarks/devvm_refs/am0_routen/routen_pruefung.py. Lauf: bau_schleife.py --projekt <Ordner> --spec am0_routen start "<Auftrag>"."""

NOTES = '''# Notizen routen_pruefung
Nur Python-Standardbibliothek. Keine Kommentare, keine Docstrings, keine eigenen Tests (ein unabhaengiger Test beurteilt die Arbeit). Dateiname der Loesung: routen_pruefung.py.
Eine Route ist ein Text der Form "<METHODE> <PFAD>", zum Beispiel "GET /api/strip" oder "GET /api/gateway/*". Der Pfad ist alles nach dem ersten Leerzeichen. Ein Stern am Ende ("/*") steht fuer alles darunter.
Alle Funktionen werfen nie eine Ausnahme; was kein Text ist oder kein Leerzeichen enthaelt, ist keine Route und ergibt False beziehungsweise nichts.
'''

TASK_S1 = '''Lege routen_pruefung.py an mit route_zu_breit(route) -> bool.
Wahr ist es genau dann, wenn der Pfad der Route "/api/*" oder "/uix/*" lautet (egal welche Methode). Alles andere ist falsch, auch "/api", "/api/", "/api/strip", "/api/gateway/*", "/uix/frame/*" und "/apix/*".
Ist route kein Text oder enthaelt es kein Leerzeichen, ist das Ergebnis False.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S2 = '''Ergaenze routen_pruefung.py: die Liste SENSIBEL_COMMUNITY (ein Tupel von Texten) und route_sensibel(route) -> bool.
SENSIBEL_COMMUNITY enthaelt genau diese 18 Eintraege in dieser Reihenfolge: "/api/chat/", "/api/harness/", "/api/arbeitsstand", "/api/audit", "/api/missions", "/api/decisions", "/api/uix/", "/api/cloud", "/api/switches", "/api/processes", "/api/gateway/", "/api/fisch/", "/api/sprache/", "/api/projects", "/api/diagnose", "/api/context", "/api/permissions", "/api/supervisor".
route_sensibel: Nimm den Pfad der Route. Endet er auf "/*", entferne nur den Stern (der Schraegstrich davor bleibt, aus "/api/fisch/*" wird "/api/fisch/"). Das Ergebnis ist wahr, wenn fuer mindestens einen Eintrag E gilt: der Pfad beginnt mit E, oder E beginnt mit dem Pfad. Sonst falsch. Keine Route ergibt False.
Beispiele: "GET /api/audit" wahr; "GET /api/chat/verlauf" wahr; "GET /api/fisch/*" wahr (Eintrag beginnt mit dem Pfad); "GET /api/strip" falsch; "GET /api/gateway/*" wahr; "GET /api/models" falsch; "GET /api/*" wahr.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S3 = '''Ergaenze routen_pruefung.py: pruefe_routen(routes, origin, trust) -> list[str] mit Fehlermeldungen.
- Ist origin nicht genau "local" oder routes keine Liste, ist das Ergebnis eine leere Liste.
- Sonst geht die Funktion die Routen in der Reihenfolge der Liste durch; Eintraege, die kein Text sind, werden uebersprungen. Fuer jede Route: ist route_zu_breit wahr, kommt zuerst "api_route_too_broad:" plus die Route (der ganze Text, mit Methode) in die Ergebnisliste. Danach, nur wenn trust genau "COMMUNITY" ist und route_sensibel wahr ist, kommt "api_route_sensitive:" plus die Route.
Eine Route kann also zwei Meldungen ausloesen. Die Eingabe wird nicht veraendert.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


C1 = hidden('''
assert route_zu_breit("GET /api/*") is True
assert route_zu_breit("POST /api/*") is True
assert route_zu_breit("GET /uix/*") is True
assert route_zu_breit("GET /api/gateway/*") is False
assert route_zu_breit("GET /uix/frame/*") is False
assert route_zu_breit("GET /api/strip") is False
assert route_zu_breit("GET /api") is False
assert route_zu_breit("GET /api/") is False
assert route_zu_breit("GET /apix/*") is False
assert route_zu_breit("GET /api/**") is False
assert route_zu_breit("/api/*") is False
assert route_zu_breit("") is False
assert route_zu_breit(None) is False
assert route_zu_breit(5) is False
assert route_zu_breit(["GET /api/*"]) is False
''', "from routen_pruefung import route_zu_breit\n")

C2 = hidden('''
assert len(SENSIBEL_COMMUNITY) == 18
assert SENSIBEL_COMMUNITY[0] == "/api/chat/"
assert SENSIBEL_COMMUNITY[-1] == "/api/supervisor"
assert "/api/fisch/" in SENSIBEL_COMMUNITY
assert route_sensibel("GET /api/audit") is True
assert route_sensibel("GET /api/chat/verlauf") is True
assert route_sensibel("GET /api/harness/*") is True
assert route_sensibel("GET /api/fisch/*") is True
assert route_sensibel("GET /api/fisch/transkripte") is True
assert route_sensibel("GET /api/gateway/*") is True
assert route_sensibel("GET /api/*") is True
assert route_sensibel("GET /api/strip") is False
assert route_sensibel("GET /api/models") is False
assert route_sensibel("GET /api/status") is False
assert route_sensibel("GET /uix/frame/x") is False
assert route_sensibel("GET /api/uix/clients") is True
assert route_sensibel("") is False
assert route_sensibel(None) is False
assert route_sensibel("GET") is False
''', "from routen_pruefung import route_sensibel, SENSIBEL_COMMUNITY\n")

C3 = hidden('''
assert pruefe_routen(["GET /api/strip"], "local", "COMMUNITY") == []
assert pruefe_routen(["GET /api/*"], "local", "CAPTAIN") == ["api_route_too_broad:GET /api/*"]
assert pruefe_routen(["GET /api/*"], "local", "COMMUNITY") == ["api_route_too_broad:GET /api/*", "api_route_sensitive:GET /api/*"]
assert pruefe_routen(["GET /api/audit"], "local", "COMMUNITY") == ["api_route_sensitive:GET /api/audit"]
assert pruefe_routen(["GET /api/audit"], "local", "CAPTAIN") == []
assert pruefe_routen(["GET /api/audit"], "local", "CORE") == []
assert pruefe_routen(["GET /api/*"], "paket", "COMMUNITY") == []
assert pruefe_routen(["GET /api/*"], None, "COMMUNITY") == []
assert pruefe_routen("GET /api/*", "local", "COMMUNITY") == []
assert pruefe_routen(None, "local", "COMMUNITY") == []
assert pruefe_routen([], "local", "COMMUNITY") == []
assert pruefe_routen([5, None, "GET /uix/*"], "local", "CAPTAIN") == ["api_route_too_broad:GET /uix/*"]
assert pruefe_routen(["GET /api/strip", "GET /api/cloud", "POST /api/x"], "local", "COMMUNITY") == ["api_route_sensitive:GET /api/cloud"]
assert pruefe_routen(["GET /api/gateway/*", "GET /uix/*"], "local", "COMMUNITY") == ["api_route_sensitive:GET /api/gateway/*", "api_route_too_broad:GET /uix/*"]
eingabe = ["GET /api/*", "GET /api/audit"]
kopie = list(eingabe)
pruefe_routen(eingabe, "local", "COMMUNITY")
assert eingabe == kopie
''', "from routen_pruefung import pruefe_routen\n")

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "hidden": {"hidden_routen_s1.py": C1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "hidden": {"hidden_routen_s2.py": C2}},
    {"name": "S3", "task": TASK_S3, "no_own_check": True, "hidden": {"hidden_routen_s3.py": C3}},
]
TASK = TASK_S1
HIDDEN = {"hidden_routen_s1.py": C1}
