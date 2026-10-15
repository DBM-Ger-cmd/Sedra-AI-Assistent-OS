"""Tools the Captain's chat model may call: read its own environment, and – since Build 19 – move in the module environment.

The chat does not put this information into the system prompt: the model asks when it needs it. The reading tools only read what
the windows already show (UIX `models_view` / `switches_view` / objects); nothing is changed, nothing is started, no file is read.

Build 19 (Captain 15.10.: „GUPPI soll sich in seiner Modulumgebung frei bewegen – Fenster öffnen nach Freigabe und Befehle
ausführen“): `open_place`, `open_object`, `list_actions`, `propose_action`, `propose_intent`. **Keines davon tut etwas.** Jedes legt
eine Oberflächen-Handlung (`ui_actions`) in die Antwort; das Gespräch zeigt sie als Knopf, und erst der Klick des Captains öffnet
das Fenster oder läuft über `POST /api/actions` – denselben Weg wie jeder Knopf in einem Werkzeug, mit denselben Gates darunter.
Hat der Captain im selben Satz selbst ums Öffnen gebeten, ist das die Freigabe (das entscheidet das Gespräch, nicht das Modell).
"""
from __future__ import annotations

import json


def _fn(name, description):
    return {"type": "function", "function": {"name": name, "description": description,
                                             "parameters": {"type": "object", "properties": {}, "required": []}}}


def _propose(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
                                             "parameters": {"type": "object", "properties": properties, "required": required}}}


SCHEMAS = {
    "get_model_status": _fn("get_model_status", "Which model runs now, its context length, KV-cache type, whether MTP is on, and who holds the GPU."),
    "list_models": _fn("list_models", "All model recipes of this PC: id, model, enabled, loaded, roles, recommended and maximum context."),
    "get_routing_profile": _fn("get_routing_profile", "The active model combination (routing profile) and what each profile prefers."),
    "get_switches": _fn("get_switches", "The machine-local feature switches (on/off) such as the automatic model loader and the own llama-server."),
    "list_projects": _fn("list_projects", "The projects (folders) registered in GUPPI: name and id."),
    "list_missions": _propose("list_missions", "The latest cards (missions): id, intent, objective, phase, status, pending gates.",
                              {"limit": {"type": "integer", "description": "how many, 1 to 20"}}, []),
    "recent_audit": _propose("recent_audit", "The last audit events: time, event type, component. Read-only history of what GUPPI did.",
                             {"limit": {"type": "integer", "description": "how many, 1 to 30"}}, []),
    "list_docs": _fn("list_docs", "The documentation files of this GUPPI package (docs folder), by name."),
    "read_doc": _propose("read_doc", "Read one documentation file by its name from list_docs (the first part of it).",
                         {"name": {"type": "string", "description": "file name such as BETRIEB.md"}}, ["name"]),
        "list_places": _fn("list_places", "The places (windows) of the SEDRA surface you can open for the Captain: id, label, what is there."),
    "open_place": _propose("open_place",
        "Open a window of the surface for the Captain, e.g. the Maschinenraum or the Werkstatt. The surface shows it as a button "
        "(or opens it at once when the Captain asked for it). Use the place id from list_places.",
        {"place": {"type": "string", "description": "place id from list_places, e.g. machine, models, decisions, logbook"}}, ["place"]),
    "open_object": _propose("open_object",
        "Open the window of one object, e.g. a task by its mission id or a model recipe by its id. Same as open_place for one object.",
        {"type": {"type": "string", "enum": ["task", "candidate", "model", "intent", "project"]},
         "id": {"type": "string", "description": "the object id, e.g. a mission id or recipe id"}}, ["type", "id"]),
    "list_actions": _propose("list_actions",
        "What can be done with one object right now: its state and the actions (verbs) it offers, with whether the Captain must approve.",
        {"type": {"type": "string", "enum": ["task", "candidate", "model", "intent", "boundary"]},
         "id": {"type": "string", "description": "object id; for boundary use projekt"}}, ["type", "id"]),
    "propose_action": _propose("propose_action",
        "Propose to run one action (verb from list_actions) on an object, e.g. load a model or run a task. Nothing runs by this call: "
        "the Captain gets a button and decides; actions that need approval then also go through the usual decision.",
        {"type": {"type": "string", "enum": ["task", "candidate", "model", "intent", "boundary"]},
         "id": {"type": "string"}, "verb": {"type": "string", "description": "verb from list_actions, e.g. laden, entladen, ausfuehren"}},
        ["type", "id", "verb"]),
    "propose_intent": _propose("propose_intent",
        "Propose to write down an intent (Vorhaben): the sentence the Captain wants done. The Captain gets a button; from an intent a task "
        "is made later. Use this when the Captain gives an order that is bigger than one action.",
        {"title": {"type": "string", "description": "short title, at most 80 characters"},
         "text": {"type": "string", "description": "the full sentence of what should be done"}}, ["title"]),
    "list_decisions": _fn("list_decisions", "The decisions that wait for the Captain (approvals): id, title, the ways to answer."),
    # Proposals only: they create a change request that the Captain approves in the Modelle window. Nothing is changed here.
    "propose_routing_change": _propose("propose_routing_change",
        "Propose a change to a model recipe, e.g. the standard context (field context_recommended, value a number such as 65536). "
        "The change waits for the Captain's approval in the Modelle window; it is not applied by this call.",
        {"recipe_id": {"type": "string", "description": "recipe id from list_models"},
         "field": {"type": "string", "enum": ["enabled", "context_recommended", "n_cpu_moe", "kv_cache_type"]},
         "value": {"description": "new value: boolean for enabled, a context tier for context_recommended, an integer for n_cpu_moe, f16 or q8_0 for kv_cache_type"}},
        ["recipe_id", "field", "value"]),
    "propose_switch": _propose("propose_switch",
        "Propose turning a machine-local switch on or off (see get_switches). Waits for the Captain's approval in the Modelle window.",
        {"section": {"type": "string"}, "key": {"type": "string"}, "value": {"type": "boolean"}},
        ["section", "key", "value"]),
}


# Die Orte der Oberfläche – dieselben ids wie `uix/ui/places.js` (ein Test vergleicht beide). Das Objekt dazu kennt nur der Browser.
PLACES = {
    'tasks': ('Aufgaben', 'was läuft und was wartet'), 'intents': ('Vorhaben', 'worum es geht – daraus werden Aufgaben'),
    'boundary': ('Modus und Grenzen', 'Projekt · Netz · Löschen · Kosten'), 'decisions': ('Entscheidungen', 'Freigaben und Grenzen'),
    'models': ('Werkstatt: Modelle', 'laden, wechseln, testen'), 'library': ('Bibliothek', 'Skills ansehen und schreiben'),
    'crew': ('Besatzung', 'Rollen und Agenten'), 'meter': ('Guppy-Meter', 'Token, Zeilen, Kosten'),
    'logbook': ('Logbuch', 'Audit-Kette und Verlauf'), 'hardware': ('Hardware', 'GPU, Speicher, Profil'),
    'machine': ('Maschinenraum', 'Zustand der Runtime'), 'modules': ('Module', 'Shell, Werkzeuge, Vorlagen'),
    'project': ('Projekt und Dateien', 'Dateien des Projekts'),
    'gateway': ('KI GateWay', 'Anfrage prüfen, Entwurf, Prüfung'),
}
OBJECT_TYPES = ('task', 'candidate', 'model', 'intent', 'project')
VERB_TYPES = ('task', 'candidate', 'model', 'intent', 'boundary')
MAX_UI_ACTIONS = 4        # mehr Knöpfe in einer Antwort liest niemand – und ein Modell in einer Schleife soll nicht die Seite füllen


def _limit(args, default, top):
    value = args.get("limit", default)
    if type(value) is not int: value = default
    return max(1, min(top, value))


class ChatTools:
    """Duck-typed like devenv.model_tools.ToolBox, so run_tool_loop can drive it. `hub` is the UIXHub (models_view, switches_view)."""

    def __init__(self, hub):
        self.hub = hub
        self.names = tuple(SCHEMAS)
        self.proposals = []           # change requests made in this chat turn, for the audit and the reply
        self.ui_actions = []          # Build 19: what the surface offers as buttons after the answer (open, verb, intent) – nothing ran
        self.terminal = None          # no ending call: the loop ends when the model answers without a tool
        self.final = None
        self.calls = []

    def schemas(self):
        return [SCHEMAS[n] for n in self.names]

    def call(self, name, args):
        self.calls.append(name)
        if name not in self.names: return f"error: unknown tool {name}"
        try:
            if name == "get_model_status":
                v = self.hub.models_view()
                server = v.get("server") or {}
                lease = v.get("lease")
                return json.dumps({"running": bool(server.get("running")), "model": server.get("model"), "context": server.get("context"),
                                   "kv_cache_type": server.get("kv_cache_type"), "mtp": server.get("spec_type") == "draft-mtp",
                                   "gpu_lease": (f"{lease['owner']} ({lease['purpose']})" if lease else "frei"),
                                   "model_loader_enabled": v.get("loader_enabled")}, ensure_ascii=False)
            if name == "list_models":
                return json.dumps([{"id": r["id"], "model": r["model"], "enabled": r["enabled"], "loaded": r["loaded"], "roles": r["roles"],
                                    "context_recommended": r["context_recommended"], "context_maximum": r["context_maximum"]}
                                   for r in self.hub.models_view()["recipes"]], ensure_ascii=False)
            if name == "get_routing_profile":
                profiles = self.hub.models_view().get("profiles")
                if not profiles: return json.dumps({"active": None})
                return json.dumps({"active": profiles["active"], "profiles": profiles["items"]}, ensure_ascii=False)
            if name == "get_switches":
                items = self.hub.switches_view().get("items") or []
                return json.dumps([{"switch": f"{it['section']}.{it['key']}", "value": it["value"]} for it in items], ensure_ascii=False)
            if name == "list_projects":
                return json.dumps(self.hub.chat_projects(), ensure_ascii=False)
            if name == "list_missions":
                return json.dumps(self.hub.chat_missions(_limit(args, 10, 20)), ensure_ascii=False, default=str)
            if name == "recent_audit":
                return json.dumps(self.hub.chat_audit(_limit(args, 10, 30)), ensure_ascii=False)
            if name == "list_docs":
                return json.dumps(self.hub.chat_docs(), ensure_ascii=False)
            if name == "read_doc":
                return self.hub.chat_doc(args.get("name"))
            if name == "list_places":
                return json.dumps([{"id": k, "label": v[0], "hint": v[1]} for k, v in PLACES.items()], ensure_ascii=False)
            if name == "open_place":
                place = str(args.get("place") or "").strip()
                if place not in PLACES: raise ValueError("unknown_place: use an id from list_places")
                return self._offer({"kind": "open", "place": place, "title": PLACES[place][0]}, f"Fenster {PLACES[place][0]}")
            if name == "open_object":
                kind, oid = str(args.get("type") or ""), str(args.get("id") or "").strip()
                if kind not in OBJECT_TYPES or not oid: raise ValueError("unknown_object_type")
                obj = self.hub.object_view(kind, oid)
                if obj.get("state") == "nicht gefunden": raise ValueError("object_not_found")
                return self._offer({"kind": "open", "object": {"type": kind, "id": oid, "title": str(obj.get("title") or oid)[:60]},
                                    "title": str(obj.get("title") or oid)[:60]}, f"Fenster {obj.get('title') or oid}")
            if name == "list_actions":
                obj = self._object(args)
                return json.dumps({"type": obj["type"], "id": obj["id"], "title": obj.get("title"), "state": obj.get("state"),
                                   "actions": [{"verb": a["verb"], "label": a["label"], "needs_approval": a["needs_gate"]}
                                               for a in self._verbs(obj)]}, ensure_ascii=False)
            if name == "propose_action":
                obj = self._object(args)
                verb = str(args.get("verb") or "").strip()
                found = next((a for a in self._verbs(obj) if a["verb"] == verb), None)
                if found is None: raise ValueError("verb_not_offered_now: call list_actions")
                return self._offer({"kind": "verb", "type": obj["type"], "id": obj["id"], "verb": verb, "label": found["label"],
                                    "needs_gate": bool(found["needs_gate"]), "confirm": found.get("confirm"),
                                    "title": str(obj.get("title") or obj["id"])[:60]}, f"{found['label']}: {obj.get('title') or obj['id']}")
            if name == "propose_intent":
                title = str(args.get("title") or "").strip()[:80]
                if not title: raise ValueError("title_required")
                text = str(args.get("text") or "").strip()[:2000]
                return self._offer({"kind": "intent", "title": title, "text": text}, f"Vorhaben „{title}“")
            if name == "list_decisions":
                items = self.hub.decisions_view().get("items") or []
                return json.dumps([{"id": d["id"], "title": d["title"], "ways": d["ways"]} for d in items[:10]], ensure_ascii=False)
            if name == "propose_routing_change":
                gate = self.hub.routing_request({"recipe_id": args.get("recipe_id"), "field": args.get("field"), "value": args.get("value")})
                return self._proposed(gate)
            if name == "propose_switch":
                gate = self.hub.switch_request({"section": args.get("section"), "key": args.get("key"), "value": args.get("value")})
                return self._proposed(gate)
        except ValueError as exc:     # a refused argument (e.g. unknown_recipe): the code goes back to the model, which can correct itself
            return f"error: {str(exc)[:120]}"
        except Exception as exc:      # a broken read must not end the chat: the model is told, and can answer without it
            return f"error: {type(exc).__name__}"
        return "error: not handled"

    def _object(self, args):
        from .desk import actions as desk_actions      # lazy: the desk imports the hub module, not the other way round
        kind, oid = str(args.get("type") or ""), str(args.get("id") or "").strip()
        if kind not in VERB_TYPES or kind not in desk_actions.VERBS or not oid: raise ValueError("unknown_object_type")
        obj = self.hub.object_view(kind, oid)
        if obj.get("state") == "nicht gefunden": raise ValueError("object_not_found")
        return obj

    def _verbs(self, obj):
        from .desk import actions as desk_actions
        return desk_actions.offered(obj)               # fresh from the state – the same list the window shows

    def _offer(self, action, describe):
        """A button for the Captain, never a deed. The model is told so in its own result."""
        if len(self.ui_actions) >= MAX_UI_ACTIONS: return "error: too_many_actions_in_one_answer"
        if action in self.ui_actions: return json.dumps({"status": "offered", "action": describe}, ensure_ascii=False)
        self.ui_actions.append(action)
        return json.dumps({"status": "offered", "action": describe,
                           "next": "Die Oberfläche zeigt dem Captain dafür einen Knopf. Erst sein Klick führt es aus; Freigaben laufen "
                                   "danach wie gewohnt über die Entscheidungen. Sag ihm, was du vorschlägst – nicht, dass es schon passiert ist."},
                          ensure_ascii=False)

    def _proposed(self, gate):
        describe = (gate or {}).get("describe") or ((gate or {}).get("binding") or {}).get("describe") or "Änderung"
        self.proposals.append(describe)
        return json.dumps({"status": "proposed", "change": describe,
                           "next": "Der Captain bestätigt es im Fenster Modelle. Bis dahin ist nichts geändert."}, ensure_ascii=False)
