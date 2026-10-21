"""Beispieltyp `echo`, nur im Test (Spec 0, D1, KERN-04): ein neuer Anwendungsfall ist ein Modul mit `register(registry, hub)`
plus eine Zeile in `desk/extensions.MODULES`; `uix_server.py` bleibt unberührt."""
from guppi_runtime.desk.actions import Verb

ITEMS = {'eins': 'Erstes Echo', 'zwei': 'Zweites Echo'}
CALLS = []


def _obj(oid):
    return {'type': 'echo', 'id': oid, 'title': ITEMS[oid], 'state': 'da', 'summary': ITEMS[oid] + ' – nur im Test.',
            'actions': [], 'links': []}


def register(registry, hub):
    def read(hub, oid):
        return _obj(oid) if oid in ITEMS else None

    def listing(hub, payload):
        return [_obj(k) for k in ITEMS]

    def rufen(hub, oid, args):
        CALLS.append((oid, dict(args)))
        return {'echo': args.get('text', oid)}

    def anlegen(hub, oid, args):
        CALLS.append((None, dict(args)))
        return {'angelegt': args.get('text')}

    registry.register(registry.Kind('echo', 'Echo', read, listing, source='test',
                                    verbs=[Verb('rufen', 'Rufen', rufen)],
                                    type_verbs=[Verb('anlegen', 'Anlegen', anlegen)]))
