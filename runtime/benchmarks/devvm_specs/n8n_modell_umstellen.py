"""Bau-Spec n8n_modell_umstellen: ein n8n-Workflow (als dict) wird auf das lokale Modell von SEDRA umgestellt.
Vier Stufen S1 bis S4 (so heissen sie fuer bau_schleife.py), je Stufe ein versteckter Test; kein eigener Test des Modells, keine eigene Pruefung (der versteckte Test ist der einzige Richter).
S1 Modellknoten finden | S2 umstellen (Kopie, Original bleibt) | S3 Optionen je Verwendung | S4 Bericht mit Hinweisen.
Referenz: benchmarks/devvm_refs/n8n_modell_umstellen/n8n_lokal.py. Lauf: bau_schleife.py --projekt <Ordner> --spec n8n_modell_umstellen start "<Auftrag>"."""

NOTES = '''# Notizen n8n_lokal
Nur Python-Standardbibliothek. Keine Kommentare, keine Docstrings, keine eigenen Tests (ein unabhaengiger Test beurteilt die Arbeit). Dateiname der Loesung: n8n_lokal.py.
Ein n8n-Workflow ist ein dict mit "nodes" (Liste von dicts mit "name", "type", "parameters", ...) und "connections". Eingaben werden nie veraendert.
'''

TASK_S1 = '''Lege n8n_lokal.py an mit modellknoten(workflow) -> list[str].
Ein Modellknoten ist ein Knoten, dessen "type" mit "@n8n/n8n-nodes-langchain." beginnt und dessen letzter Teil nach dem Punkt einer von diesen ist: lmChatAnthropic, lmChatOpenAi, lmChatGoogleGemini, lmChatOllama, lmChatMistralCloud, lmChatGroq, lmChatAzureOpenAi.
Zurueck kommen die "name"-Werte aller Modellknoten in der Reihenfolge von workflow["nodes"]; abgeschaltete Knoten ("disabled": true) zaehlen mit.
Ist workflow kein dict, hat keine Liste "nodes", oder ist ein Eintrag kein dict oder ohne "type"/"name" als Text, wird der Eintrag uebersprungen; es gibt nie eine Ausnahme, im Zweifel eine leere Liste.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S2 = '''Ergaenze n8n_lokal.py: umstellen(workflow, modell="qwen3.6-35b-a3b", zugang="SEDRA lokal") -> dict.
Zurueck kommt eine tiefe Kopie des Workflows (das Original bleibt unveraendert), in der jeder Modellknoten (wie in modellknoten) so umgestellt ist:
- "type" ist "@n8n/n8n-nodes-langchain.lmChatOpenAi" und "typeVersion" ist 1.3.
- "parameters" ist {"model": {"__rl": True, "mode": "id", "value": modell}, "options": {}}.
- "credentials" ist {"openAiApi": {"id": "", "name": zugang}} (eine alte "credentials"-Angabe entfaellt).
- Alle anderen Schluessel des Knotens (id, name, position, disabled, notes, ...) und alle anderen Knoten sowie "connections" bleiben unveraendert.
Ein Workflow ohne Modellknoten kommt als gleiche Kopie zurueck; ist workflow kein dict, wird {} zurueckgegeben.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S3 = '''Ergaenze n8n_lokal.py: umstellen setzt in "parameters"["options"] jedes umgestellten Modellknotens ausserdem diese Werte: "temperature", "maxTokens", "timeout": 180000, "maxRetries": 1.
"temperature" und "maxTokens" haengen davon ab, womit der Modellknoten verbunden ist. Die Verbindung steht in workflow["connections"][<Name des Modellknotens>]["ai_languageModel"]: eine Liste von Listen von dicts mit "node" (Name des Zielknotens). Der Typ des Zielknotens ist der letzte Teil seines "type" nach dem Punkt.
- Ziel informationExtractor, textClassifier oder sentimentAnalysis: temperature 0, maxTokens 512.
- Ziel agent: temperature 0.1, maxTokens 1024.
- jedes andere Ziel oder keine Verbindung: temperature 0.2, maxTokens 1024.
Hat der Knoten mehrere Ziele, gilt die kleinste temperature und die kleinste maxTokens aller Ziele. Ein Ziel, das es nicht als Knoten gibt, zaehlt wie ein anderes Ziel.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''

TASK_S4 = '''Ergaenze n8n_lokal.py: bericht(vorher, nachher, basis_url="http://127.0.0.1:8090/v1") -> dict mit den Schluesseln "umgestellt", "zugang", "hinweise".
- "umgestellt": die Namen der Modellknoten aus nachher, die in vorher einen anderen "type" hatten als in nachher (Reihenfolge wie in nachher).
- "zugang": {"name": <Name aus dem credentials-Eintrag openAiApi des ersten umgestellten Knotens oder "">, "basis_url": basis_url}.
- "hinweise": Liste von Texten. Fuer jeden umgestellten Knoten ein Text der Form "<Name>: <alter Typ-Endteil> -> lmChatOpenAi" (der alte Typ-Endteil ist der Teil nach dem letzten Punkt des alten "type"). Gibt es in nachher mindestens einen Knoten, dessen "type" mit "agent" endet, kommt zusaetzlich genau ein Text, der "--jinja" enthaelt. Gab es bei einem umgestellten Knoten in vorher eine "credentials"-Angabe, kommt zusaetzlich genau ein Text, der "Zugangsdaten" enthaelt. Wurde nichts umgestellt, ist "hinweise" genau ["Kein Modellknoten umgestellt."].
Ist ein Eingang kein dict, wird er wie ein Workflow ohne Knoten behandelt.
Keine Kommentare, keine Docstrings, keine eigenen Tests.'''


def hidden(body, imports=""):
    return imports + body + "\nprint('ok')\n"


FIX = '''
import copy
def knoten(name, art, **mehr):
    d = {"id": name.lower(), "name": name, "type": art, "typeVersion": 1, "position": [0, 0], "parameters": {}}
    d.update(mehr)
    return d
ANTH = "@n8n/n8n-nodes-langchain.lmChatAnthropic"
WF = {"name": "t", "nodes": [
    knoten("Start", "n8n-nodes-base.formTrigger"),
    knoten("Extractor", "@n8n/n8n-nodes-langchain.informationExtractor"),
    knoten("Modell A", ANTH, parameters={"model": {"value": "claude"}, "options": {}}, credentials={"anthropicApi": {"id": "7", "name": "Anthropic"}}, notes="wichtig", disabled=True),
    knoten("Agent", "@n8n/n8n-nodes-langchain.agent"),
    knoten("Modell B", "@n8n/n8n-nodes-langchain.lmChatOpenAi"),
    knoten("Notiz", "n8n-nodes-base.stickyNote"),
    knoten("Lokal", "@n8n/n8n-nodes-langchain.lmChatOllama"),
    knoten("Fremd", "n8n-nodes-base.lmChatAnthropic"),
], "connections": {
    "Start": {"main": [[{"node": "Extractor", "type": "main", "index": 0}]]},
    "Modell A": {"ai_languageModel": [[{"node": "Extractor", "type": "ai_languageModel", "index": 0}]]},
    "Modell B": {"ai_languageModel": [[{"node": "Agent", "type": "ai_languageModel", "index": 0}, {"node": "Extractor", "type": "ai_languageModel", "index": 0}]]},
    "Lokal": {"ai_languageModel": [[{"node": "Gibt es nicht", "type": "ai_languageModel", "index": 0}]]},
}}
'''

C1 = hidden('''
assert modellknoten(WF) == ["Modell A", "Modell B", "Lokal"]
assert modellknoten({"nodes": []}) == [] and modellknoten({}) == [] and modellknoten(None) == [] and modellknoten("x") == []
assert modellknoten({"nodes": [None, 5, {"name": "a"}, {"type": "@n8n/n8n-nodes-langchain.lmChatGroq"}, {"name": 3, "type": "@n8n/n8n-nodes-langchain.lmChatGroq"}]}) == []
assert modellknoten({"nodes": [{"name": "G", "type": "@n8n/n8n-nodes-langchain.lmChatGroq"}, {"name": "Z", "type": "@n8n/n8n-nodes-langchain.lmChatAzureOpenAi"}, {"name": "M", "type": "@n8n/n8n-nodes-langchain.lmChatMistralCloud"}, {"name": "X", "type": "@n8n/n8n-nodes-langchain.lmChatUnbekannt"}]}) == ["G", "Z", "M"]
assert modellknoten({"nodes": "kaputt"}) == []
''', "from n8n_lokal import modellknoten\n" + FIX)

C2 = hidden('''
vorher = copy.deepcopy(WF)
neu = umstellen(WF)
assert WF == vorher
assert neu is not WF and neu["nodes"] is not WF["nodes"]
a = next(n for n in neu["nodes"] if n["name"] == "Modell A")
assert a["type"] == "@n8n/n8n-nodes-langchain.lmChatOpenAi" and a["typeVersion"] == 1.3
assert a["parameters"]["model"] == {"__rl": True, "mode": "id", "value": "qwen3.6-35b-a3b"}
assert a["credentials"] == {"openAiApi": {"id": "", "name": "SEDRA lokal"}}
assert a["notes"] == "wichtig" and a["disabled"] is True and a["id"] == "modell a" and a["position"] == [0, 0]
b = next(n for n in neu["nodes"] if n["name"] == "Modell B")
assert b["credentials"]["openAiApi"]["name"] == "SEDRA lokal"
fremd = next(n for n in neu["nodes"] if n["name"] == "Fremd")
assert fremd["type"] == "n8n-nodes-base.lmChatAnthropic" and "credentials" not in fremd
assert [n["name"] for n in neu["nodes"]] == [n["name"] for n in WF["nodes"]]
assert neu["connections"] == WF["connections"] and neu["name"] == "t"
x = umstellen(WF, modell="m1", zugang="Z1")
assert next(n for n in x["nodes"] if n["name"] == "Lokal")["parameters"]["model"]["value"] == "m1"
assert next(n for n in x["nodes"] if n["name"] == "Lokal")["credentials"]["openAiApi"]["name"] == "Z1"
leer = {"nodes": [knoten("A", "n8n-nodes-base.set")], "connections": {}}
assert umstellen(leer) == leer and umstellen(leer) is not leer
assert umstellen(None) == {} and umstellen([1]) == {}
''', "from n8n_lokal import umstellen\n" + FIX)

C3 = hidden('''
neu = umstellen(WF)
def opt(name):
    return next(n for n in neu["nodes"] if n["name"] == name)["parameters"]["options"]
assert opt("Modell A") == {"temperature": 0, "maxTokens": 512, "timeout": 180000, "maxRetries": 1}
assert opt("Modell B") == {"temperature": 0, "maxTokens": 512, "timeout": 180000, "maxRetries": 1}
assert opt("Lokal") == {"temperature": 0.2, "maxTokens": 1024, "timeout": 180000, "maxRetries": 1}
nur_agent = {"nodes": [knoten("M", ANTH), knoten("Ag", "@n8n/n8n-nodes-langchain.agent")], "connections": {"M": {"ai_languageModel": [[{"node": "Ag", "type": "ai_languageModel", "index": 0}]]}}}
o = umstellen(nur_agent)["nodes"][0]["parameters"]["options"]
assert o["temperature"] == 0.1 and o["maxTokens"] == 1024
klass = {"nodes": [knoten("M", ANTH), knoten("K", "@n8n/n8n-nodes-langchain.textClassifier"), knoten("S", "@n8n/n8n-nodes-langchain.sentimentAnalysis")], "connections": {"M": {"ai_languageModel": [[{"node": "S", "type": "ai_languageModel", "index": 0}], [{"node": "K", "type": "ai_languageModel", "index": 0}]]}}}
assert umstellen(klass)["nodes"][0]["parameters"]["options"]["temperature"] == 0
kette = {"nodes": [knoten("M", ANTH), knoten("C", "@n8n/n8n-nodes-langchain.chainLlm")], "connections": {"M": {"ai_languageModel": [[{"node": "C", "type": "ai_languageModel", "index": 0}]]}}}
assert umstellen(kette)["nodes"][0]["parameters"]["options"]["temperature"] == 0.2
ohne = {"nodes": [knoten("M", ANTH)]}
o2 = umstellen(ohne)["nodes"][0]["parameters"]["options"]
assert o2["temperature"] == 0.2 and o2["maxTokens"] == 1024
assert umstellen(WF) == umstellen(WF)
''', "from n8n_lokal import umstellen\n" + FIX)

C4 = hidden('''
neu = umstellen(WF)
b = bericht(WF, neu)
assert b["umgestellt"] == ["Modell A", "Lokal"]
assert b["zugang"] == {"name": "SEDRA lokal", "basis_url": "http://127.0.0.1:8090/v1"}
h = b["hinweise"]
assert "Modell A: lmChatAnthropic -> lmChatOpenAi" in h and "Lokal: lmChatOllama -> lmChatOpenAi" in h
assert not any(t.startswith("Modell B") for t in h)
assert sum("--jinja" in t for t in h) == 1 and sum("Zugangsdaten" in t for t in h) == 1
assert len(h) == 4
c = bericht(WF, umstellen(WF, zugang="Z"), basis_url="http://x/v1")
assert c["zugang"] == {"name": "Z", "basis_url": "http://x/v1"}
leer = {"nodes": [knoten("A", "n8n-nodes-base.set")], "connections": {}}
e = bericht(leer, umstellen(leer))
assert e == {"umgestellt": [], "zugang": {"name": "", "basis_url": "http://127.0.0.1:8090/v1"}, "hinweise": ["Kein Modellknoten umgestellt."]}
f = bericht(None, None)
assert f["umgestellt"] == [] and f["hinweise"] == ["Kein Modellknoten umgestellt."]
ohne_agent = {"nodes": [knoten("M", ANTH), knoten("E", "@n8n/n8n-nodes-langchain.informationExtractor")], "connections": {"M": {"ai_languageModel": [[{"node": "E", "type": "ai_languageModel", "index": 0}]]}}}
g = bericht(ohne_agent, umstellen(ohne_agent))
assert g["hinweise"] == ["M: lmChatAnthropic -> lmChatOpenAi"]
''', "from n8n_lokal import umstellen, bericht\n" + FIX)

STAGES = [
    {"name": "S1", "task": TASK_S1, "no_own_check": True, "hidden": {"hidden_n8n_s1.py": C1}},
    {"name": "S2", "task": TASK_S2, "no_own_check": True, "hidden": {"hidden_n8n_s2.py": C2}},
    {"name": "S3", "task": TASK_S3, "no_own_check": True, "hidden": {"hidden_n8n_s3.py": C3}},
    {"name": "S4", "task": TASK_S4, "no_own_check": True, "hidden": {"hidden_n8n_s4.py": C4}},
]
TASK = TASK_S1
HIDDEN = {"hidden_n8n_s1.py": C1}
