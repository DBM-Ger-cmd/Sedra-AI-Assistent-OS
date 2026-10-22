from antwort import ANTWORT
assert isinstance(ANTWORT, dict) and set(ANTWORT) <= {"teilaufgaben", "rueckfrage"}, "nur teilaufgaben und rueckfrage"
items = ANTWORT["teilaufgaben"]
assert isinstance(items, list) and 1 <= len(items) <= 8, "1 bis 8 Teilaufgaben"
for item in items:
    assert set(item) == {"titel", "beschreibung", "rolle", "blocker", "akzeptanz"}, "genau die fünf Felder"
    assert isinstance(item["titel"], str) and 0 < len(item["titel"].strip()) <= 200, "Titel 1 bis 200 Zeichen"
