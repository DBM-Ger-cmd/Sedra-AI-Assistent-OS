"""Die neun Objekttypen von heute als Einträge im Register (Spec 0, D1, K0.10).

Die Leser sind die Zweige aus `UIXHub.object_view`/`objects_view`, wörtlich verschoben: sie rufen weiter die Hub-Methoden
(`missions()`, `models_view()`, `_intent_object`, `_candidate_report` …). Ein Leser gibt `None` zurück, wo der alte Zweig
`not_found` zurückgab; das Register setzt dann dasselbe Objekt „nicht gefunden“ ein. Die Verben bleiben in `actions.py`.

`decision` trägt seine Wege selbst (`own_actions=True`); in der Liste verliert es sie wie heute (OP-13). `agent` ist ein Platzhalter,
der das heutige Verhalten nachbildet: Einzelansicht `unknown_object_type`, Liste leer. Nur `desk/orchestra_kinds.py` darf ihn ersetzen.

Spec 4 (G2-S1-10, „Platzhalter mit quelle“): ebenso Platzhalter für `issue`, `routine`, `budget` und `gespraech`. Ihre Liste ist leer
und trägt `quelle = {zustand: 'aus', grund: 'orchestra_off', takt: None}` (Nachtrag N7), damit ein Werkzeug „ausgeschaltet“ zeigt,
statt an `unknown_object_type` zu scheitern. Die Liste von `agent` bleibt ohne `quelle`, wie die Golden-Aufzeichnung (K0.7) sie hält.
Spec 1 (S1.H4): `quelle` kommt über den Haken `extra` des Registers; ist die Orchestrierung mit Fehler aus, heißt sie
`{zustand: 'fehler', grund: rt.orchestra_error, takt: None}` (D1.3.4)."""
from __future__ import annotations

from . import actions as desk_actions
from . import objects as desk_objects
from .kinds import Registry

ORDER = ('task', 'intent', 'candidate', 'model', 'skill', 'decision', 'project', 'agent', 'boundary')   # die Reihenfolge von objects.TYPES
PLACEHOLDERS = (('issue', 'Aufgabe'), ('routine', 'Routine'), ('budget', 'Budget'), ('gespraech', 'Gespräch'))   # ersetzt orchestra_kinds
QUELLE_AUS = {'zustand': 'aus', 'grund': 'orchestra_off', 'takt': None}


# ---- task
def _task_read(hub, oid):
    m = next((x for x in hub.missions() if x['mission_id'] == oid), None)
    if m is None:
        return None
    obj = desk_objects.task_object(m)
    if hub._candidate_report(oid) is not None:          # es gibt ein Werkstück: der Weg dorthin gehört an die Aufgabe
        obj['links'].insert(0, {'type': 'candidate', 'id': oid, 'title': 'Kandidat ansehen', 'rel': 'werkstueck'})
    return obj


def _task_list(hub, payload):
    return [desk_objects.task_object(m) for m in hub.missions() if not m.get('antrag')]    # Stufe 6 (S6-E3): Anträge sind keine Aufgaben


# ---- candidate
def _candidate_read(hub, oid):
    try:
        mission = hub.runtime.missions.load(oid)
    except Exception:
        return None
    return desk_objects.candidate_object(mission, report=hub.candidate_report({'mission_id': oid}))


def _candidate_list(hub, payload):
    return []                                           # heute ohne Liste (der else-Zweig von objects_view)


# ---- model
def _model_read(hub, oid):
    view = hub.models_view()
    recipe = next((r for r in view['recipes'] if r['id'] == oid), None)
    if recipe is None:
        return None
    return desk_objects.model_object(recipe, view.get('server'))


def _model_list(hub, payload):
    view = hub.models_view()
    return [desk_objects.model_object(r, view.get('server')) for r in view['recipes']]


def _model_extra(hub, payload):
    """Spec 2 D2.9: die Liste der Modelle trägt zusätzlich `slots` (Spec 4 D4.2.4), solange der Scheduler an ist."""
    slots = hub.slots_view() if hasattr(hub, 'slots_view') else None
    return {'slots': {k: slots.get(k) for k in ('gesamt', 'belegt', 'schlange', 'modell', 'warte_max_s')}} if slots is not None else {}


# ---- intent
def _intent_read(hub, oid):
    entry = hub.intents.get(oid)
    if entry is None:
        return None
    return hub._intent_object(entry)


def _intent_list(hub, payload):
    return [hub._intent_object(e) for e in hub.intents.list()]


# ---- boundary
def _boundary_read(hub, oid):
    return desk_objects.boundary_object(hub.boundaries_view({'project_id': oid} if oid not in ('projekt', 'alle') else None))


def _boundary_list(hub, payload):
    return [desk_objects.boundary_object(hub.boundaries_view())]


# ---- decision
def _decision_read(hub, oid):
    d = next((x for x in hub.decisions_view()['items'] if x['id'] == oid), None)
    return desk_objects.decision_object(d) if d else None


def _decision_list(hub, payload):
    return [desk_objects.decision_object(d) for d in hub.decisions_view()['items']]


# ---- skill
def _skill_read(hub, oid):
    s = next((x for x in (hub.library.view().get('own') or []) if x.get('id') == oid), None)
    return desk_objects.skill_object(s) if s else None


def _skill_list(hub, payload):
    return [desk_objects.skill_object(s) for s in (hub.library.view().get('own') or [])]


# ---- project
def _project_read(hub, oid):
    p = next((x for x in hub.projects.list() if (x.get('project_id') == oid or x.get('name') == oid)), None)
    return desk_objects.project_object(p) if p else None


def _project_list(hub, payload):
    return [desk_objects.project_object(p) for p in hub.projects.list()]


# ---- agent (Platzhalter)
def _agent_read(hub, oid):
    raise ValueError('unknown_object_type')


def _agent_list(hub, payload):
    return []


# ---- issue, routine, budget, gespraech (Platzhalter, Spec 4)
def _placeholder_read(hub, oid):
    raise ValueError('unknown_object_type')


def _placeholder_list(hub, payload):
    return []


def _placeholder_quelle(hub, payload):
    error = getattr(getattr(hub, 'runtime', None), 'orchestra_error', None)
    return {'quelle': {'zustand': 'fehler', 'grund': error, 'takt': None} if error else dict(QUELLE_AUS)}


def kinds(Kind):
    """Die neun Typen in der Reihenfolge von `objects.TYPES`."""
    table = {
        'task': Kind('task', 'Aufgabe', _task_read, _task_list, verbs=desk_actions._task_verbs()),
        'intent': Kind('intent', 'Vorhaben', _intent_read, _intent_list, verbs=desk_actions._intent_verbs()),
        'candidate': Kind('candidate', 'Kandidat', _candidate_read, _candidate_list, verbs=desk_actions._candidate_verbs()),
        'model': Kind('model', 'Modell', _model_read, _model_list, verbs=desk_actions._model_verbs(), extra=_model_extra),
        'skill': Kind('skill', 'Skill', _skill_read, _skill_list),
        'decision': Kind('decision', 'Entscheidung', _decision_read, _decision_list, own_actions=True),
        'project': Kind('project', 'Projekt', _project_read, _project_list),
        'agent': Kind('agent', 'Agent', _agent_read, _agent_list, placeholder=True),
        'boundary': Kind('boundary', 'Modus und Grenzen', _boundary_read, _boundary_list, verbs=desk_actions._boundary_verbs()),
    }
    return [table[name] for name in ORDER] + [Kind(name, title, _placeholder_read, _placeholder_list, placeholder=True,
                                                   extra=_placeholder_quelle) for name, title in PLACEHOLDERS]


def register(registry):
    for kind in kinds(registry.Kind):
        registry.register(kind)
    return registry


def new_registry():
    """Ein Register mit den eingebauten Typen; „nicht gefunden“ ist das Objekt aus `objects.not_found` wie bisher."""
    return register(Registry(not_found=desk_objects.not_found))


_BUILTIN = None


def builtin():
    """Das Register nur mit den eingebauten Typen, eingefroren – für `objects.TYPES`, `actions.VERBS` und Aufrufe ohne Hub."""
    global _BUILTIN
    if _BUILTIN is None:
        reg = new_registry()
        reg.freeze()
        _BUILTIN = reg
    return _BUILTIN
