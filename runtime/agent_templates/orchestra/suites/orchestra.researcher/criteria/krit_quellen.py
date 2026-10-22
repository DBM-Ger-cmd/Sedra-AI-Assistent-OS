import re
from antwort import BERICHT
assert isinstance(BERICHT, dict) and set(BERICHT) == {"zusammenfassung", "quellen"}, "nur zusammenfassung und quellen"
assert isinstance(BERICHT["zusammenfassung"], str) and BERICHT["zusammenfassung"].strip(), "eine Zusammenfassung"
for q in BERICHT["quellen"]:
    assert set(q) == {"url", "sha256"} and re.fullmatch(r"[0-9a-f]{64}", q["sha256"]), "Quelle mit Prüfsumme"
