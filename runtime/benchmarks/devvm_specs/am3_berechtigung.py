"""Bau-Spec am3_berechtigung: Gewaehrung, Aktivierung und Ladeentscheidung einer fremden App (AM3-05, AM3-06, AM3-08, AM3-09, AM3-28, Stufe A4, Kern ohne Anbindung).
Drei Stufen S1 bis S3, je ein versteckter Test; kein eigener Test des Modells. Der Bau liefert nur das Modul berechtigung.py (reine Funktionen auf dicts, keine Datei);
Lesen und Schreiben von local_config/apps/berechtigung.yaml und die Anbindung an das Gateway macht Claude spaeter von Hand.
S1 wirksame Rechte und Ladeentscheidung | S2 Werkseinstellung | S3 Eintrag anlegen, gewaehren, entziehen, aktivieren.
Referenz: benchmarks/devvm_refs/am3_berechtigung/berechtigung.py. Lauf: bau_schleife.py --projekt <Ordner> --spec am3_berechtigung start "<Auftrag>"."""

NOTES = '''# Notizen berechtigung
Nur Python-Standardbibliothek. Keine Kommentare, keine Docstrings, keine eigenen Tests (ein unabhaengiger Test beurteilt die Arbeit). Dateiname der Loesung: berechtigung.py.
Eine "Faehigkeit" ist ein Text der Form "<art>:<wert>", zum Beispiel "lesen:rechnung", "verb:rechnung.ablegen", "ereignis:system.state" oder "ablage:2048". Ein "Eintrag" ist das dict einer App in der Berechtigungsdatei:
{"vertrauen": "COMMUNITY", "manifest_sha256": "<hex>", "aktiv": True oder False, "gewaehrt": [Faehigkeiten]}. Alle Funktionen sind rein: sie lesen ihre Argumente und geben neue Werte zurueck, nie dieselben Objekte, nie eine Aenderung der Eingabe.
Fehler sind ValueError mit genau dem angegebenen Text. Ergebnislisten von Faehigkeiten sind aufsteigend sortiert (Textvergleich) und ohne Doppelte.
'''

TASK_S1 = '''Lege berechtigung.py an mit zwei Funktionen.
1. wirksam(beantragt, gewaehrt, obergrenze=None) -> list[str]: die Faehigkeiten, die in beantragt UND in gewaehrt stehen, und, wenn obergrenze nicht None ist, auch in obergrenze. Alle drei Argumente sind Listen, Tupel oder Mengen von Texten; ist eines davon etwas anderes oder enthaelt es einen Eintrag, der kein Text ist, ValueError("faehigkeiten_ungueltig").
2. ladeentscheidung(eintrag, beantragt, manifest_sha256) -> dict mit genau den Schluesseln "laden" (bool), "grund" (Text oder None), "wirksam" (Liste). beantragt wie oben (sonst ValueError("faehigkeiten_ungueltig")). Es gilt die erste zutreffende Zeile:
   - eintrag ist kein dict: laden False, grund "keine_gewaehrung", wirksam [].
   - eintrag["manifest_sha256"] ist nicht gleich dem Argument manifest_sha256, fehlt oder ist kein Text (also auch, wenn beide None sind): laden False, grund "gewaehrung_veraltet", wirksam [].
   - eintrag["aktiv"] ist nicht genau True: laden False, grund "app_inaktiv", wirksam [].
   - es gibt beantragte Faehigkeiten, die nicht in eintrag["gewaehrt"] stehen (fehlt "gewaehrt" oder ist es keine Liste, gilt es als leer; Eintraege dort, die keine Texte sind, zaehlen nicht): laden False, grund "rechte_nicht_gewaehrt:" gefolgt von diesen fehlenden Faehigkeiten, sortiert und mit "," ohne Leerzeichen verbunden, wirksam [].
   - sonst: laden True, grund None, wirksam = beantragt sortiert und ohne Doppelte.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S2 = '''Ergaenze berechtigung.py: werkseinstellung(beantragt, eigene_typen) -> list[str], die Faehigkeiten, die eine fremde App nach dem Einbau sofort gewaehrt bekommt (nur harmlose, Stufe A).
beantragt ist eine Liste von Faehigkeiten (wie in S1, sonst ValueError("faehigkeiten_ungueltig")); eigene_typen ist eine Liste, ein Tupel oder eine Menge von Texten (etwas anderes zaehlt als leer). Aus beantragt bleiben genau diese:
- "lesen:<typ>", wenn <typ> in eigene_typen steht.
- "ereignis:<name>", wenn <name> eines von system.state, model.changed, desk.resync, tools.refresh, slot.changed ist.
- "ablage:<n>", wenn <n> nur aus den Ziffern 0 bis 9 besteht und die Zahl groesser als 0 und hoechstens 1048576 ist.
Alles andere (zum Beispiel "verb:...", "zelle:text", "dienst:...", lesen anderer Typen, andere Ereignisse, groessere Ablage) bleibt nicht gewaehrt. Das Ergebnis ist sortiert und ohne Doppelte.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S3 = '''Ergaenze berechtigung.py vier Funktionen auf Eintraegen:
- eintrag_neu(manifest_sha256, vertrauen, gewaehrt) -> dict: {"vertrauen": vertrauen, "manifest_sha256": manifest_sha256, "aktiv": False, "gewaehrt": <gewaehrt sortiert, ohne Doppelte>}. gewaehrt wie in S1 (sonst ValueError("faehigkeiten_ungueltig")).
- gewaehren(eintrag, faehigkeiten) -> dict: eine Kopie des Eintrags (alle anderen Schluessel unveraendert), in der "gewaehrt" die Vereinigung aus dem alten "gewaehrt" und faehigkeiten ist, sortiert und ohne Doppelte.
- entziehen(eintrag, faehigkeiten) -> dict: wie gewaehren, aber die genannten Faehigkeiten werden aus "gewaehrt" entfernt; nicht vorhandene sind kein Fehler.
- aktivieren(eintrag, aktiv) -> dict: eine Kopie des Eintrags mit "aktiv" gleich dem Argument. aktiv muss genau True oder False sein, sonst ValueError("aktiv_ungueltig").
Bei gewaehren, entziehen und aktivieren ist ein eintrag, der kein dict ist oder dessen "gewaehrt" keine Liste ist, ein Fehler ValueError("eintrag_ungueltig") (vor der Pruefung der anderen Argumente). Der alte Eintrag und seine Liste werden nie veraendert.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


C1 = hidden('''
def wirft(f, text, *a):
    try:
        f(*a)
    except ValueError as e:
        return str(e) == text
    return False
assert wirksam(["a", "b"], ["b", "c"]) == ["b"]
assert wirksam(["b", "a", "a"], ["a", "b", "x"]) == ["a", "b"]
assert wirksam([], ["a"]) == []
assert wirksam(["a"], []) == []
assert wirksam(("a", "b"), {"a"}) == ["a"]
assert wirksam(["a", "b"], ["a", "b"], ["b"]) == ["b"]
assert wirksam(["a", "b"], ["a", "b"], []) == []
assert wirksam(["a", "b"], ["a", "b"], None) == ["a", "b"]
assert wirft(wirksam, "faehigkeiten_ungueltig", "a", ["a"])
assert wirft(wirksam, "faehigkeiten_ungueltig", ["a"], None)
assert wirft(wirksam, "faehigkeiten_ungueltig", ["a", 5], ["a"])
assert wirft(wirksam, "faehigkeiten_ungueltig", ["a"], ["a"], "a")
E = {"vertrauen": "COMMUNITY", "manifest_sha256": "h1", "aktiv": True, "gewaehrt": ["lesen:a", "verb:x.y"]}
assert ladeentscheidung(E, ["lesen:a"], "h1") == {"laden": True, "grund": None, "wirksam": ["lesen:a"]}
assert ladeentscheidung(E, ["verb:x.y", "lesen:a", "lesen:a"], "h1") == {"laden": True, "grund": None, "wirksam": ["lesen:a", "verb:x.y"]}
assert ladeentscheidung(E, [], "h1") == {"laden": True, "grund": None, "wirksam": []}
assert ladeentscheidung(None, ["lesen:a"], "h1") == {"laden": False, "grund": "keine_gewaehrung", "wirksam": []}
assert ladeentscheidung("x", [], "h1")["grund"] == "keine_gewaehrung"
assert ladeentscheidung(E, ["lesen:a"], "h2") == {"laden": False, "grund": "gewaehrung_veraltet", "wirksam": []}
assert ladeentscheidung({"aktiv": True, "gewaehrt": []}, [], "h1")["grund"] == "gewaehrung_veraltet"
assert ladeentscheidung({"aktiv": True, "gewaehrt": []}, [], None)["grund"] == "gewaehrung_veraltet"
assert ladeentscheidung({"manifest_sha256": None, "aktiv": True, "gewaehrt": []}, [], None)["grund"] == "gewaehrung_veraltet"
assert ladeentscheidung({"manifest_sha256": 5, "aktiv": True, "gewaehrt": []}, [], 5)["grund"] == "gewaehrung_veraltet"
assert ladeentscheidung(dict(E, aktiv=False), ["lesen:a"], "h1") == {"laden": False, "grund": "app_inaktiv", "wirksam": []}
assert ladeentscheidung(dict(E, aktiv="ja"), ["lesen:a"], "h1")["grund"] == "app_inaktiv"
assert ladeentscheidung({"manifest_sha256": "h1", "gewaehrt": []}, [], "h1")["grund"] == "app_inaktiv"
assert ladeentscheidung(E, ["lesen:a", "zelle:text", "verb:z.q"], "h1") == {"laden": False, "grund": "rechte_nicht_gewaehrt:verb:z.q,zelle:text", "wirksam": []}
assert ladeentscheidung(dict(E, gewaehrt=None), ["lesen:a"], "h1")["grund"] == "rechte_nicht_gewaehrt:lesen:a"
assert ladeentscheidung(dict(E, gewaehrt=["lesen:a", 5, None]), ["lesen:a"], "h1")["laden"] is True
assert wirft(ladeentscheidung, "faehigkeiten_ungueltig", E, "lesen:a", "h1")
assert wirft(ladeentscheidung, "faehigkeiten_ungueltig", None, [5], "h1")
''', "from berechtigung import wirksam, ladeentscheidung\n")

C2 = hidden('''
def wirft(f, *a):
    try:
        f(*a)
    except ValueError as e:
        return str(e) == "faehigkeiten_ungueltig"
    return False
assert werkseinstellung(["lesen:a", "lesen:b"], ["a"]) == ["lesen:a"]
assert werkseinstellung(["lesen:a"], []) == []
assert werkseinstellung(["lesen:a"], None) == []
assert werkseinstellung(["lesen:a"], "a") == []
assert werkseinstellung(["lesen:a"], ("a",)) == ["lesen:a"]
assert werkseinstellung(["lesen:a"], {"a"}) == ["lesen:a"]
assert werkseinstellung(["ereignis:system.state", "ereignis:model.changed", "ereignis:desk.resync", "ereignis:tools.refresh", "ereignis:slot.changed"], []) == ["ereignis:desk.resync", "ereignis:model.changed", "ereignis:slot.changed", "ereignis:system.state", "ereignis:tools.refresh"]
assert werkseinstellung(["ereignis:decision.pending", "ereignis:task.changed"], []) == []
assert werkseinstellung(["ablage:1"], []) == ["ablage:1"]
assert werkseinstellung(["ablage:1048576"], []) == ["ablage:1048576"]
assert werkseinstellung(["ablage:1048577"], []) == []
assert werkseinstellung(["ablage:0"], []) == []
assert werkseinstellung(["ablage:abc", "ablage:-5", "ablage:10x", "ablage:"], []) == []
assert werkseinstellung(["ablage:\\u00b2"], []) == []
assert werkseinstellung(["verb:a.b", "zelle:text", "dienst:microvm", "dienst:host", "route:GET /x"], ["a.b", "x"]) == []
assert werkseinstellung(["lesen:a", "lesen:a", "ablage:5"], ["a"]) == ["ablage:5", "lesen:a"]
assert werkseinstellung([], ["a"]) == []
assert wirft(werkseinstellung, "lesen:a", ["a"])
assert wirft(werkseinstellung, ["lesen:a", 3], ["a"])
liste = ["ablage:5", "lesen:a"]
werkseinstellung(liste, ["a"])
assert liste == ["ablage:5", "lesen:a"]
''', "from berechtigung import werkseinstellung\n")

C3 = hidden('''
def fehler(f, text, *a):
    try:
        f(*a)
    except ValueError as e:
        return str(e) == text
    return False
n = eintrag_neu("h1", "COMMUNITY", ["b", "a", "b"])
assert n == {"vertrauen": "COMMUNITY", "manifest_sha256": "h1", "aktiv": False, "gewaehrt": ["a", "b"]}
assert eintrag_neu("h", "v", []) == {"vertrauen": "v", "manifest_sha256": "h", "aktiv": False, "gewaehrt": []}
assert fehler(eintrag_neu, "faehigkeiten_ungueltig", "h", "v", "a")
assert fehler(eintrag_neu, "faehigkeiten_ungueltig", "h", "v", [1])
E = {"vertrauen": "COMMUNITY", "manifest_sha256": "h1", "aktiv": True, "gewaehrt": ["lesen:a"], "extra": {"x": 1}}
g = gewaehren(E, ["verb:x.y", "lesen:a"])
assert g["gewaehrt"] == ["lesen:a", "verb:x.y"]
assert (g["vertrauen"], g["manifest_sha256"], g["aktiv"], g["extra"]) == ("COMMUNITY", "h1", True, {"x": 1})
assert E["gewaehrt"] == ["lesen:a"]
assert g is not E
assert g["gewaehrt"] is not E["gewaehrt"]
assert gewaehren(E, [])["gewaehrt"] == ["lesen:a"]
d = entziehen(E, ["lesen:a", "nie:da"])
assert d["gewaehrt"] == []
assert d["aktiv"] is True
assert E["gewaehrt"] == ["lesen:a"]
assert entziehen(dict(E, gewaehrt=["b", "a", "c"]), ["b"])["gewaehrt"] == ["a", "c"]
a = aktivieren(E, False)
assert a["aktiv"] is False
assert a["gewaehrt"] == ["lesen:a"]
assert E["aktiv"] is True
assert aktivieren(dict(E, aktiv=False), True)["aktiv"] is True
assert fehler(aktivieren, "aktiv_ungueltig", E, 1)
assert fehler(aktivieren, "aktiv_ungueltig", E, "ja")
assert fehler(aktivieren, "aktiv_ungueltig", E, None)
for f, args in ((gewaehren, (["a"],)), (entziehen, (["a"],)), (aktivieren, (True,))):
    assert fehler(f, "eintrag_ungueltig", None, *args)
    assert fehler(f, "eintrag_ungueltig", "x", *args)
    assert fehler(f, "eintrag_ungueltig", {"gewaehrt": "a"}, *args)
    assert fehler(f, "eintrag_ungueltig", {}, *args)
assert fehler(aktivieren, "eintrag_ungueltig", None, "kein bool")
assert fehler(gewaehren, "faehigkeiten_ungueltig", E, "lesen:b")
assert fehler(entziehen, "faehigkeiten_ungueltig", E, [5])
''', "from berechtigung import eintrag_neu, gewaehren, entziehen, aktivieren\n")

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "hidden": {"hidden_berecht_s1.py": C1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "hidden": {"hidden_berecht_s2.py": C2}},
    {"name": "S3", "task": TASK_S3, "no_own_check": True, "hidden": {"hidden_berecht_s3.py": C3}},
]
TASK = TASK_S1
HIDDEN = {"hidden_berecht_s1.py": C1}
