"""Verben statt Routen (SHELL_WERKZEUG_VERTRAG_v1 §10.2).

`POST /api/actions {type, id, verb, args}` – ein Weg für dieselbe Handlung, egal ob sie aus dem Gespräch, aus einem Werkzeug oder
aus der Palette kommt. Jedes Verb weiß, was es ist:

    name        das Wort im Knopf („Übernehmen“)
    needs_gate  ob der Captain entscheidet, bevor etwas passiert
    when        ob das Verb im jetzigen Zustand überhaupt angeboten wird
    run         was es tut – und das ist immer ein Aufruf, den es vorher schon gab

Damit ändert sich nichts an den Gates: `run` ruft dieselben Hub-Methoden wie die alten Routen, der Guard prüft wie bisher, und wo
eine Freigabe nötig ist, entsteht eine Entscheidung, die an genau einer Stelle beantwortet wird (`decisions.py`)."""
from __future__ import annotations


class Verb:
    def __init__(self, verb, label, run, needs_gate=False, when=None, confirm=None):
        self.verb, self.label, self.run, self.needs_gate = verb, label, run, needs_gate
        self.when = when or (lambda obj: True)
        self.confirm = confirm           # ein Satz, den die Oberfläche vor dem Ausführen zeigt; None heißt: einfach tun

    def offered(self, obj):
        try:
            return bool(self.when(obj))
        except Exception:
            return False

    def describe(self):
        return {'verb': self.verb, 'label': self.label, 'needs_gate': self.needs_gate, 'confirm': self.confirm}


def _task_verbs():
    return [
        Verb('ausfuehren', 'Ausführen', lambda hub, oid, args: hub.run_mission({'mission_id': oid, **({'max_steps': args['max_steps']} if 'max_steps' in args else {})}),
             when=lambda o: o['state'] in ('bereit', 'geplant', 'angehalten')),
    ]
    # Bewusst kein „Neu lesen“: Nachlesen ist keine Handlung am Objekt, und der Ereignisstrom meldet jede Änderung von selbst
    # (Cockpit-Regel 3: die Zeile trägt die Verben des Objekts, nichts sonst).


def _boundary_first(hub, kind, what, amount=None):
    """Die Deckungsprüfung vor `guard.create_gate` (§10, Regel 7): berührt die Handlung eine Grenze, entscheidet erst die
    Grenze – entweder sie ist frei, oder es entsteht eine Entscheidung an der Grenze und die Handlung läuft nicht."""
    out = hub.cross_boundary(kind, what, amount=amount)
    if out['verdict'] == 'frei':
        return None
    if out['verdict'] == 'unbestätigt':
        raise ValueError('boundaries_not_confirmed')
    return {'status': 'boundary', 'boundary': kind, 'decision': out['decision'],
            'note': 'Die ' + kind + 'grenze steht im Weg. Die Entscheidung liegt an der Werkbank.'}


def _take_over(resolution):
    """Übernehmen und Zurücknehmen sind zwei Schritte: erst die Vorschau (sie bindet genau diese Dateien mit ihren Hashes),
    dann die Ausführung gegen genau diese Vorschau. Der Guard vergleicht beides – deshalb holt das Verb die Vorschau selbst,
    statt sie der Oberfläche zu überlassen, wo sie veralten könnte."""
    def run(hub, oid, args):
        if resolution == 'accept':
            stopped = _boundary_first(hub, 'projekt', 'Dateien dieses Kandidaten überschreiben')
            if stopped:
                return stopped
        plan = args.get('plan')
        if plan is None:
            preview = hub.candidate_operation({'operation': resolution + '-preview', 'mission_id': oid})
            plan = preview.get('plan') if isinstance(preview, dict) else None
            if plan is None:
                return preview
        return hub.candidate_operation({'operation': resolution, 'mission_id': oid, 'plan': plan})
    return run


def _candidate_verbs():
    return [
        Verb('testen', 'Testen', lambda hub, oid, args: hub.candidate_operation({'operation': 'test', 'mission_id': oid}),
             when=lambda o: o['state'] in ('vorgeschlagen', 'braucht Durchsicht')),
        Verb('nachpruefen', 'Tests nachprüfen', lambda hub, oid, args: hub.candidate_operation({'operation': 'test-verify', 'mission_id': oid}),
             when=lambda o: o['state'] == 'vorgeschlagen'),
        Verb('uebernehmen', 'Übernehmen', _take_over('accept'),
             needs_gate=True, when=lambda o: o['state'] == 'vorgeschlagen' and o.get('qualified'),
             confirm='Diese Dateien werden überschrieben. Die alten Fassungen werden vorher gesichert, die Rücknahme bleibt möglich.'),
        Verb('zuruecknehmen', 'Rückgängig', _take_over('rollback'),
             needs_gate=True, when=lambda o: o['state'] == 'übernommen',
             confirm='Die übernommenen Dateien werden auf den gesicherten Stand zurückgesetzt.'),
    ]


def _intent_verbs():
    return [
        # args.stufe (Index): die Stufe wird zur Aufgabe und hängt an ihr; ohne Stufe wie bisher das ganze Vorhaben
        Verb('aufgabe_machen', 'Aufgabe daraus machen',
             lambda hub, oid, args: hub.intent_to_task(oid, args.get('text'), stufe=args.get('stufe')),
             when=lambda o: o['state'] != 'fertig'),
    ]


def _boundary_verbs():
    return [
        # Auch das Bestätigen ist eine Freigabe: der Captain sagt einmal ja, und es steht im Audit (§3).
        Verb('bestaetigen', 'Modus und Grenzen bestätigen',
             lambda hub, oid, args: hub.boundaries_request({'project_id': None if oid in ('projekt', 'alle') else oid}),
             needs_gate=True, when=lambda o: not o.get('confirmed'),
             confirm='Damit gelten Modus und Grenzen für alles, was in diesem Projekt passiert.'),
        Verb('aendern', 'Grenzen ändern',
             lambda hub, oid, args: hub.boundaries_request({'project_id': None if oid in ('projekt', 'alle') else oid,
                                                            'mode': args.get('mode'), 'boundaries': args.get('boundaries')}),
             needs_gate=True, when=lambda o: bool(o.get('confirmed')),
             confirm='Eine geänderte Grenze gilt ab sofort für dieses Projekt.'),
    ]


def _model_verbs():
    return [
        Verb('laden', 'Laden', lambda hub, oid, args: hub.load_model({'recipe_id': oid}), when=lambda o: o['state'] == 'bereit'),
        Verb('entladen', 'Entladen', lambda hub, oid, args: hub.unload_model({'erzwingen': args.get('erzwingen') is True}), when=lambda o: o['state'] == 'geladen'),   # `erzwingen` (Spec 2 D2.6): nur der Captain, über args
        Verb('testen', 'Testen', lambda hub, oid, args: hub.model_test({'recipe_id': oid}), when=lambda o: o['state'] == 'geladen'),
    ]


def _registry(hub=None):
    """Das Register des Hubs (mit den Erweiterungen) oder, ohne Hub, das der eingebauten Typen (Spec 0, D1)."""
    from inspect import getattr_static
    from .kinds import Registry
    reg = getattr_static(hub, 'kinds', None)         # statisch: ein Hub-Ersatz mit __getattr__ (Tests) wird nicht gefragt
    if isinstance(reg, Registry):
        return reg
    from .builtin_kinds import builtin
    return builtin()


def table(registry=None):
    """{Objekttyp: {Verb: Verb}} – aus dem Register gelesen (Spec 0, D1); nur Typen mit Verben."""
    return (registry or _registry()).table()


def __getattr__(name):
    if name == 'VERBS':                                  # Kompatibilität: die Verben der eingebauten Typen
        return table()
    raise AttributeError(name)


def offered(obj, registry=None):
    """Die Verben, die dieses Objekt in seinem jetzigen Zustand anbietet (Cockpit-Regel 3)."""
    return (registry or _registry()).offered(obj)


def run(hub, kind, oid, verb, args=None, lookup=None):
    """Führt ein Verb aus. Der Zustand wird vorher frisch gelesen: ein Verb, das jetzt nicht angeboten wird, läuft nicht."""
    args = args or {}
    if not isinstance(args, dict):
        raise ValueError('args_must_be_an_object')
    known = table(_registry(hub)).get(kind)
    if known is None:
        raise ValueError('unknown_object_type')
    action = known.get(verb)
    if action is None:
        raise ValueError('unknown_verb')
    obj = (lookup or hub.object_view)(kind, oid)
    if obj.get('state') == 'nicht gefunden':
        raise ValueError('object_not_found')
    if not action.offered(obj):
        raise ValueError('verb_not_offered_in_this_state')
    result = action.run(hub, oid, args)
    return {'status': 'done', 'type': kind, 'id': oid, 'verb': verb, 'needs_gate': action.needs_gate, 'result': result}


def run_type(hub, kind, verb, args=None):
    """Ein Verb ohne Objekt („anlegen“, Spec 0 D1): nur wenn der Typ ein `type_verb` dieses Namens hat, sonst `id_required`
    wie bisher. `run` bekommt `None` als ID."""
    known = _registry(hub).get(kind)
    action = known.type_verb(verb) if known is not None else None
    if action is None:
        raise ValueError('id_required')
    args = args or {}
    if not isinstance(args, dict):
        raise ValueError('args_must_be_an_object')
    result = action.run(hub, None, args)
    return {'status': 'done', 'type': kind, 'id': None, 'verb': verb, 'needs_gate': action.needs_gate, 'result': result}
