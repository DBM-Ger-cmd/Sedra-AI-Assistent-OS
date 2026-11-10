import copy

PRAEFIX = "@n8n/n8n-nodes-langchain."
MODELLE = {"lmChatAnthropic", "lmChatOpenAi", "lmChatGoogleGemini", "lmChatOllama", "lmChatMistralCloud", "lmChatGroq", "lmChatAzureOpenAi"}
STRENG = {"informationExtractor", "textClassifier", "sentimentAnalysis"}


def _knoten(workflow):
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
        return []
    return [n for n in workflow["nodes"] if isinstance(n, dict) and isinstance(n.get("name"), str) and isinstance(n.get("type"), str)]


def _ist_modell(knoten):
    art = knoten["type"]
    return art.startswith(PRAEFIX) and art.rsplit(".", 1)[-1] in MODELLE


def modellknoten(workflow):
    return [n["name"] for n in _knoten(workflow) if _ist_modell(n)]


def _optionen(workflow, name):
    typen = {n["name"]: n["type"].rsplit(".", 1)[-1] for n in _knoten(workflow)}
    verbindungen = workflow.get("connections")
    ziele = []
    if isinstance(verbindungen, dict) and isinstance(verbindungen.get(name), dict):
        for gruppe in verbindungen[name].get("ai_languageModel") or []:
            for eintrag in gruppe or []:
                if isinstance(eintrag, dict):
                    ziele.append(typen.get(eintrag.get("node")))
    temperatur, token = [], []
    for ziel in ziele:
        if ziel in STRENG:
            temperatur.append(0)
            token.append(512)
        elif ziel == "agent":
            temperatur.append(0.1)
            token.append(1024)
        else:
            temperatur.append(0.2)
            token.append(1024)
    return {"temperature": min(temperatur) if temperatur else 0.2, "maxTokens": min(token) if token else 1024, "timeout": 180000, "maxRetries": 1}


def umstellen(workflow, modell="qwen3.6-35b-a3b", zugang="SEDRA lokal"):
    if not isinstance(workflow, dict):
        return {}
    neu = copy.deepcopy(workflow)
    for knoten in _knoten(neu):
        if not _ist_modell(knoten):
            continue
        knoten["type"] = PRAEFIX + "lmChatOpenAi"
        knoten["typeVersion"] = 1.3
        knoten["parameters"] = {"model": {"__rl": True, "mode": "id", "value": modell}, "options": _optionen(neu, knoten["name"])}
        knoten["credentials"] = {"openAiApi": {"id": "", "name": zugang}}
    return neu


def bericht(vorher, nachher, basis_url="http://127.0.0.1:8090/v1"):
    alt = {n["name"]: n for n in _knoten(vorher)}
    umgestellt = [n["name"] for n in _knoten(nachher) if _ist_modell(n) and n["name"] in alt and alt[n["name"]]["type"] != n["type"]]
    hinweise = ["%s: %s -> lmChatOpenAi" % (name, alt[name]["type"].rsplit(".", 1)[-1]) for name in umgestellt]
    if any(n["type"].endswith("agent") for n in _knoten(nachher)):
        hinweise.append("Agent-Knoten brauchen Werkzeug-Aufrufe: der Server muss mit --jinja laufen.")
    if any(alt[name].get("credentials") for name in umgestellt):
        hinweise.append("Die alten Zugangsdaten werden nicht mehr benutzt; in n8n den Zugang fuer das lokale Modell anlegen.")
    if not umgestellt:
        hinweise = ["Kein Modellknoten umgestellt."]
    zugang = ""
    if umgestellt:
        neu = {n["name"]: n for n in _knoten(nachher)}[umgestellt[0]]
        zugang = ((neu.get("credentials") or {}).get("openAiApi") or {}).get("name", "")
    return {"umgestellt": umgestellt, "zugang": {"name": zugang, "basis_url": basis_url}, "hinweise": hinweise}
