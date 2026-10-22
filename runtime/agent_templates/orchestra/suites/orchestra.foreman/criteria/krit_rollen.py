from antwort import ANTWORT
for item in ANTWORT["teilaufgaben"]:
    assert item["rolle"] in {"planer", "coder", "reviewer"}, "nur Rollen der Untergebenen: " + str(item["rolle"])
