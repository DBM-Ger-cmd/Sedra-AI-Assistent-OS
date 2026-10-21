"""Feste Daten des Agenten-Teams für die Browserabnahme von Shell D (Spec 4, D4.4, G2-S4-17). Nur Prüfmittel, nicht im Paket.

    uix_check.py --shell paperclip --fixture orchestra          # Team bereit, mit Daten
    uix_check.py --shell paperclip --fixture orchestra-aus      # Orchestrierung ausgeschaltet (quelle.zustand = aus)
    uix_check.py --shell paperclip --fixture orchestra-fehler   # Orchestrierung ausgefallen (quelle.zustand = fehler)

Die Typen `agent`, `issue`, `routine` und `gespraech` liefert später Spec 0/1 über `desk/extensions`. Solange es diese Andockstelle
nicht gibt, legt sich die Fixture als Hülle um `hub.objects_view` des Prüfprojekts: dieselbe Route (`POST /api/objects`), dieselbe
Form (§10.1, Nachtrag N7), kein Eingriff in das Paket. Ein Typ, den die Fixture nicht kennt, geht unverändert an den Hub.

Inhalt (D4.4): vier Agenten mit Vorgesetzten (einer pausiert, einer bei 80 Prozent Budget, einer mit offener Entscheidung), sechs
Issues in verschiedenen Zuständen mit Blocker und Zielkette, zwei Routinen, zwei Gespräche mit je drei Nachrichten (eine aus der
Cloud) und das Feld `slots` am Typ `model`. Die offene Entscheidung steht nur als Zahl am Agenten (`offene_entscheidungen`);
eine echte Entscheidung legt die Fixture nicht an, damit der Posteingang des Prüfprojekts unverfälscht bleibt."""
from __future__ import annotations

import copy

VARIANTS = ('orchestra', 'orchestra-aus', 'orchestra-fehler')
TYPES = ('agent', 'issue', 'routine', 'gespraech')
TS = '2026-10-21T08:00:00Z'


def _budget(prozent, stufe):
    return {'grenze_token': 200000, 'verbraucht_token': prozent * 2000, 'grenze_eur_cent': None, 'verbraucht_eur_cent': None,
            'prozent': prozent, 'stufe': stufe, 'zeitraum': 'monat'}


def _agent(aid, name, rolle, reports_to, status='aktiv', arbeitet=False, prozent=10, stufe='ok', offen=0):
    return {'type': 'agent', 'id': aid, 'title': name, 'state': status, 'summary': f'{name} – {rolle}, {status}.',
            'actions': [], 'links': [], 'rolle': rolle, 'reports_to': reports_to, 'status': status, 'arbeitet': arbeitet,
            'budget': _budget(prozent, stufe), 'offene_entscheidungen': offen}


AGENTS = [
    _agent('A-UA', 'Unterarbeiter', 'unterarbeiter', None, arbeitet=True, prozent=35),
    _agent('A-PL', 'Planer', 'planer', 'A-UA', prozent=80, stufe='warnung'),
    _agent('A-CO', 'Coder', 'coder', 'A-UA', arbeitet=True, prozent=55, offen=1),
    _agent('A-RE', 'Reviewer', 'reviewer', 'A-UA', status='pausiert', prozent=5),
]


def _issue(iid, title, zustand, bearbeiter, prioritaet, blocker=(), kommentare=0, eltern=None, mission=None):
    return {'type': 'issue', 'id': iid, 'title': title, 'state': zustand, 'summary': f'{title} – {zustand}.', 'actions': [], 'links': [],
            'zustand': zustand, 'bearbeiter': bearbeiter, 'prioritaet': prioritaet, 'blocker': list(blocker), 'kommentare': kommentare,
            'eltern_id': eltern, 'mission_id': mission, 'vorhaben_id': 'V-1', 'projekt_id': 'P-1', 'geaendert': TS}


ISSUES = [
    _issue('UA-1', 'CSV-Export planen', 'erledigt', 'A-PL', 2, kommentare=2),
    _issue('UA-2', 'CSV-Export bauen', 'in_arbeit', 'A-CO', 3, eltern='UA-1', kommentare=1),
    _issue('UA-3', 'Export prüfen', 'wartet', 'A-RE', 2, blocker=['UA-2'], eltern='UA-1'),
    _issue('UA-4', 'Dokumentation ergänzen', 'zugewiesen', 'A-PL', 1),
    _issue('UA-5', 'Altlasten sichten', 'offen', None, 1),
    _issue('UA-6', 'Prototyp verwerfen', 'abgebrochen', 'A-CO', 0),
]

ROUTINES = [
    {'type': 'routine', 'id': 'R-1', 'title': 'Morgendlicher Bericht', 'state': 'an', 'summary': 'Jeden Tag um 06:30 Uhr.', 'actions': [],
     'links': [], 'agent_id': 'A-UA', 'cron': '30 6 * * *', 'zeitzone': 'Europe/Berlin', 'nachholen': 'auslassen', 'enabled': True,
     'letzter_lauf': {'termin': TS, 'ausgang': 'erzeugt', 'issue_id': 'UA-1'}, 'next_run': '2026-10-22T04:30:00Z'},
    {'type': 'routine', 'id': 'R-2', 'title': 'Wochenreview', 'state': 'aus', 'summary': 'Montags um 09:00 Uhr.', 'actions': [],
     'links': [], 'agent_id': 'A-RE', 'cron': '0 9 * * 1', 'zeitzone': 'Europe/Berlin', 'nachholen': 'nachholen', 'enabled': False,
     'letzter_lauf': None, 'next_run': None},
]


def _msg(mid, agent, rolle, text, status, route='lokal', provider=None, model=None, issue=None):
    return {'type': 'gespraech', 'id': mid, 'title': text.split('\n')[0][:60], 'state': status, 'summary': text, 'actions': [], 'links': [],
            'agent_id': agent, 'rolle': rolle, 'ts': TS, 'issue_id': issue, 'mission_id': None, 'route': route,
            'provider_id': provider, 'model': model}


MESSAGES = [
    _msg(1, 'A-UA', 'captain', 'Bau den CSV-Export.', 'angenommen', issue='UA-1'),
    _msg(2, 'A-UA', 'agent', 'Drei Issues angelegt: UA-1, UA-2, UA-3.', 'beantwortet'),
    _msg(3, 'A-UA', 'captain', 'Wie weit ist der Export?', 'wartet_freigabe'),
    _msg(4, 'A-CO', 'captain', 'Nimm UA-2 zuerst.', 'angenommen', issue='UA-2'),
    _msg(5, 'A-CO', 'agent', 'UA-2 läuft, erster Entwurf steht.', 'beantwortet', route='cloud', provider='anbieter-a', model='modell-x'),
    _msg(6, 'A-CO', 'system', 'Lauf #12 läuft.', 'laeuft'),
]

SLOTS = {'gesamt': 3, 'modell': 'coder.qwen', 'warte_max_s': 120,
         'belegt': [{'slot': 1, 'run_id': 'L-12', 'agent_id': 'A-CO', 'titel': 'CSV-Export bauen', 'prioritaet': 'agent', 'seit': TS},
                    {'slot': 2, 'run_id': 'L-13', 'agent_id': 'A-UA', 'titel': 'Bericht', 'prioritaet': 'captain', 'seit': TS}],
         'schlange': [{'run_id': 'L-14', 'agent_id': 'A-PL', 'prioritaet': 'routine', 'seit': TS}]}


def quelle(variant):
    if variant == 'orchestra-aus':
        return {'zustand': 'aus', 'grund': 'orchestra_off', 'takt': None}
    if variant == 'orchestra-fehler':
        return {'zustand': 'fehler', 'grund': 'orchestra_config_invalid:budget', 'takt': None}
    return {'zustand': 'bereit', 'grund': '', 'takt': {'zustand': 'läuft', 'letzter': TS}}


def listing(kind, payload, variant):
    """Die Liste eines Fixture-Typs in der Form des Desk, mit `quelle` (N7). Aus oder ausgefallen: leere Liste."""
    data = {'agent': AGENTS, 'issue': ISSUES, 'routine': ROUTINES, 'gespraech': MESSAGES}[kind]
    items = copy.deepcopy(data) if variant == 'orchestra' else []
    out = {'type': kind, 'items': items, 'quelle': quelle(variant)}
    if kind == 'gespraech':
        agent = str((payload or {}).get('agent') or '')
        out['items'] = [m for m in items if m['agent_id'] == agent][-int((payload or {}).get('limit') or 50):]
        out['mehr'] = False
    return out


def read(kind, oid, variant):
    """Ein Objekt eines Fixture-Typs; ein unbekanntes ist `not_found` wie beim Desk."""
    if kind == 'gespraech':
        return listing(kind, {'agent': oid}, variant)
    for item in listing(kind, {}, variant)['items']:
        if item['id'] == oid:
            return item
    return {'type': kind, 'id': oid, 'title': oid, 'state': 'nicht gefunden', 'summary': 'Dieses Objekt gibt es nicht (mehr).',
            'actions': [], 'links': [], 'missing': True}


def install(hub, variant='orchestra'):
    """Die Hülle um `hub.objects_view`. Muss vor `make_server` laufen (die Route bindet die Methode beim Start)."""
    if variant not in VARIANTS:
        raise ValueError(f'unknown fixture {variant}: {", ".join(VARIANTS)}')
    inner = hub.objects_view

    def objects_view(payload):
        kind = str((payload or {}).get('type') or '').strip()
        if kind in TYPES:
            oid = (payload or {}).get('id')
            return read(kind, str(oid), variant) if oid else listing(kind, payload, variant)
        out = inner(payload)
        if kind == 'model' and not (payload or {}).get('id') and variant == 'orchestra':
            out['slots'] = copy.deepcopy(SLOTS)
        return out

    hub.objects_view = objects_view
    return hub
