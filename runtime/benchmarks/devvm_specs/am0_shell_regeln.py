"""Bau-Spec am0_shell_regeln: Regeln fuer fremde Shells (AM0-06, Stufe A0, G3 Schritt S5, Kern ohne Anbindung).
Drei Stufen S1 bis S3, je ein versteckter Test; kein eigener Test des Modells. Der Bau liefert nur das Modul shell_regeln.py; die Anbindung an desk/gateway.py (check_shell) und ui/loader.js macht Claude spaeter von Hand.
S1 pruefe_shell | S2 Sonderfaelle und Eingabetypen | S3 pruefe_einbau und darf_code_laden.
Referenz: benchmarks/devvm_refs/am0_shell_regeln/shell_regeln.py. Lauf: bau_schleife.py --projekt <Ordner> --spec am0_shell_regeln start "<Auftrag>"."""

NOTES = '''# Notizen shell_regeln
Nur Python-Standardbibliothek. Keine Kommentare, keine Docstrings, keine eigenen Tests (ein unabhaengiger Test beurteilt die Arbeit). Dateiname der Loesung: shell_regeln.py.
Eine Shell ist eine Oberflaeche mit einem Manifest (dict aus einer YAML-Datei). "trust" ist das Vertrauen: "CORE", "CAPTAIN", "SEDRA_BUILT" oder "COMMUNITY". Eine fremde Shell (COMMUNITY) darf nur eine Vorgabe sein (Schluessel "vorgabe"), keinen eigenen Code haben (Schluessel "entry") und kein eigenes CSS mitbringen (Datei "shell.css").
Ein Wert gilt als "gesetzt", wenn er nicht None, "", False, {} oder [] ist. Alle Funktionen werfen nie eine Ausnahme; Fehlermeldungen sind Texte genau in der angegebenen Schreibweise.
'''

TASK_S1 = '''Lege shell_regeln.py an mit pruefe_shell(doc, trust, dateien) -> list[str]. doc ist das Manifest (dict), trust das Vertrauen (Text), dateien eine Liste der relativen Dateipfade im Ordner der Shell.
- Ist trust nicht genau "COMMUNITY", ist das Ergebnis [] (eigene Shells des Captains und Kern-Shells behalten ihren Code).
- Bei "COMMUNITY" kommen diese Meldungen in dieser Reihenfolge, jede nur wenn sie zutrifft:
  1. "community_shell_needs_vorgabe": doc["vorgabe"] fehlt oder ist nicht gesetzt.
  2. "community_shell_no_entry": doc["entry"] ist gesetzt.
  3. "community_shell_no_css": der Pfad "shell.css" steht in dateien (genau diese Schreibweise; ein Pfad wie "sub/shell.css" zaehlt nicht).
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S2 = '''Ergaenze shell_regeln.py (alles andere bleibt) so, dass pruefe_shell auch mit ungewoehnlichen Eingaben richtig arbeitet:
- Ist doc bei "COMMUNITY" kein dict, ist das Ergebnis genau ["community_shell_needs_vorgabe"].
- dateien darf eine Liste, ein Tupel oder eine Menge sein; ist es etwas anderes (zum Beispiel None oder ein Text), gilt es als leer, es gibt dann keine Meldung 3.
- Gesetzt ist: jeder Wert ausser None, "", False, {} und []. Also ist "vorgabe": {"titel": "x"} gesetzt, "vorgabe": 1 und "vorgabe": True ebenfalls, "vorgabe": None nicht gesetzt.
- Die Eingaben werden nicht veraendert. Bei trust "CORE", "CAPTAIN", "SEDRA_BUILT", None, 5 oder jedem anderen Wert ausser "COMMUNITY" ist das Ergebnis [] egal wie doc aussieht.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S3 = '''Ergaenze shell_regeln.py:
- pruefe_einbau(kind, doc) -> list[str]: die Pruefung vor dem Einbau-Gate. Ist kind nicht genau "shell", ist das Ergebnis []. Ist kind "shell" und doc ein dict mit gesetztem "vorgabe" (gesetzt wie oben), ist es []. Sonst ["shell_einbau_nur_vorgabe"].
- darf_code_laden(trust, frame) -> bool: die zweite Sicherung im Lader. Ist trust genau "COMMUNITY", ist das Ergebnis False, egal was frame ist (frame sagt, ob die Shell eine Vorgabe ist). Fuer jedes andere trust ist es True.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


C1 = hidden('''
assert pruefe_shell({"vorgabe": {"titel": "x"}}, "COMMUNITY", ["shell.yaml"]) == []
assert pruefe_shell({}, "COMMUNITY", []) == ["community_shell_needs_vorgabe"]
assert pruefe_shell({"vorgabe": None}, "COMMUNITY", []) == ["community_shell_needs_vorgabe"]
assert pruefe_shell({"vorgabe": ""}, "COMMUNITY", []) == ["community_shell_needs_vorgabe"]
assert pruefe_shell({"vorgabe": {"a": 1}, "entry": {"js": ["shell.js"]}}, "COMMUNITY", []) == ["community_shell_no_entry"]
assert pruefe_shell({"vorgabe": {"a": 1}}, "COMMUNITY", ["shell.css"]) == ["community_shell_no_css"]
assert pruefe_shell({"vorgabe": {"a": 1}}, "COMMUNITY", ["shell.yaml", "shell.css", "README.md"]) == ["community_shell_no_css"]
assert pruefe_shell({"vorgabe": {"a": 1}}, "COMMUNITY", ["sub/shell.css"]) == []
assert pruefe_shell({"vorgabe": {"a": 1}}, "COMMUNITY", ["Shell.css"]) == []
assert pruefe_shell({"entry": {"js": ["x.js"]}}, "COMMUNITY", ["shell.css"]) == ["community_shell_needs_vorgabe", "community_shell_no_entry", "community_shell_no_css"]
assert pruefe_shell({"entry": {"js": ["x.js"]}}, "CAPTAIN", ["shell.css"]) == []
assert pruefe_shell({}, "CORE", []) == []
assert pruefe_shell({}, "SEDRA_BUILT", []) == []
assert pruefe_shell({"vorgabe": {"a": 1}, "entry": ""}, "COMMUNITY", []) == []
assert pruefe_shell({"vorgabe": {"a": 1}, "entry": {}}, "COMMUNITY", []) == []
''', "from shell_regeln import pruefe_shell\n")

C2 = hidden('''
assert pruefe_shell(None, "COMMUNITY", []) == ["community_shell_needs_vorgabe"]
assert pruefe_shell("text", "COMMUNITY", ["shell.css"]) == ["community_shell_needs_vorgabe"]
assert pruefe_shell([1], "COMMUNITY", []) == ["community_shell_needs_vorgabe"]
assert pruefe_shell({"vorgabe": 1}, "COMMUNITY", ("shell.css",)) == ["community_shell_no_css"]
assert pruefe_shell({"vorgabe": 1}, "COMMUNITY", {"shell.css"}) == ["community_shell_no_css"]
assert pruefe_shell({"vorgabe": 1}, "COMMUNITY", None) == []
assert pruefe_shell({"vorgabe": 1}, "COMMUNITY", "shell.css") == []
assert pruefe_shell({"vorgabe": 1}, "COMMUNITY", 5) == []
assert pruefe_shell({"vorgabe": True}, "COMMUNITY", []) == []
assert pruefe_shell({"vorgabe": False}, "COMMUNITY", []) == ["community_shell_needs_vorgabe"]
assert pruefe_shell({"vorgabe": [1]}, "COMMUNITY", []) == []
assert pruefe_shell({"vorgabe": []}, "COMMUNITY", []) == ["community_shell_needs_vorgabe"]
assert pruefe_shell({}, None, []) == []
assert pruefe_shell({}, 5, []) == []
assert pruefe_shell({}, "community", []) == []
assert pruefe_shell(None, "CAPTAIN", None) == []
doc = {"vorgabe": {"a": 1}, "entry": {"js": ["x.js"]}}
dateien = ["shell.css"]
pruefe_shell(doc, "COMMUNITY", dateien)
assert doc == {"vorgabe": {"a": 1}, "entry": {"js": ["x.js"]}}
assert dateien == ["shell.css"]
''', "from shell_regeln import pruefe_shell\n")

C3 = hidden('''
assert pruefe_einbau("shell", {"vorgabe": {"a": 1}}) == []
assert pruefe_einbau("shell", {}) == ["shell_einbau_nur_vorgabe"]
assert pruefe_einbau("shell", {"vorgabe": None}) == ["shell_einbau_nur_vorgabe"]
assert pruefe_einbau("shell", {"entry": {"js": ["a.js"]}}) == ["shell_einbau_nur_vorgabe"]
assert pruefe_einbau("shell", None) == ["shell_einbau_nur_vorgabe"]
assert pruefe_einbau("shell", "x") == ["shell_einbau_nur_vorgabe"]
assert pruefe_einbau("tool", {}) == []
assert pruefe_einbau("tool", None) == []
assert pruefe_einbau(None, {}) == []
assert pruefe_einbau("Shell", {}) == []
assert darf_code_laden("COMMUNITY", False) is False
assert darf_code_laden("COMMUNITY", True) is False
assert darf_code_laden("COMMUNITY", None) is False
assert darf_code_laden("CAPTAIN", False) is True
assert darf_code_laden("CORE", False) is True
assert darf_code_laden("SEDRA_BUILT", True) is True
assert darf_code_laden(None, False) is True
assert darf_code_laden("community", False) is True
''', "from shell_regeln import pruefe_einbau, darf_code_laden\n")

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "hidden": {"hidden_shellr_s1.py": C1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "hidden": {"hidden_shellr_s2.py": C2}},
    {"name": "S3", "task": TASK_S3, "no_own_check": True, "hidden": {"hidden_shellr_s3.py": C3}},
]
TASK = TASK_S1
HIDDEN = {"hidden_shellr_s1.py": C1}
