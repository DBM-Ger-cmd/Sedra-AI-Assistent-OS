"""Die Wege der Harness-Shell unter /api/harness/ (G2 §4, Stufe 1), eingebunden in uix_server.

    GET    projekte                           Harness-Projekte
    GET    sitzungen[?projekt=]               Liste (neueste zuerst) und welche gerade antworten
    POST   sitzungen                          {projekt, titel?, modell?} → Kopf; `vorlage` bleibt in Stufe 1 null
    GET    sitzungen/<id>                     Verlauf
    PATCH  sitzungen/<id>                     {titel?, modell?}
    DELETE sitzungen/<id>                     nach geloescht/ verschieben (kein echtes Löschen)
    POST   sitzungen/<id>/nachricht           {text} → {antwort_id}; ohne geladenes Modell {status: kein_modell, grund} (HS-53)
    GET    antworten/<id>/strom               SSE der Antwort; Wiederaufnahme mit Last-Event-ID oder ?last=
    POST   antworten/<id>/stopp               Abbruch

Die Schleife läuft in einem eigenen Thread und nimmt nie `hub.lock` (K3). Auf dem gemeinsamen Ereignisstrom erscheinen nur
`harness.sitzung` (angelegt, geändert, verschoben) und `harness.antwort` (läuft, fertig) – der Text läuft über den eigenen Strom."""
from __future__ import annotations

import re
import threading
from urllib.parse import parse_qs

from . import projekte as harness_projekte
from . import schleife
from .sitzung import SitzungFehler, Sitzungen, titel_aus
from .strom import Stroeme, ZuVieleAntworten

TEXT_MAX = 8000
VERLAUF_MAX = 20                       # so viele frühere Nachrichten gehen mit (Captain und Modell)
PROVIDER = 'llama-cpp-server'
# Stufe 1: nur die lesenden Zustandswerkzeuge aus chat_tools (kein Vorschlag, kein Öffnen, kein Netz)
LESEN = ('get_model_status', 'list_models', 'get_routing_profile', 'get_switches', 'list_projects', 'list_missions', 'recent_audit',
         'list_docs', 'read_doc', 'list_decisions', 'arbeitsplatz_stand')
WEG = re.compile(r'/api/harness/(?:(projekte)|(sitzungen)(?:/(S-[0-9A-F]{8})(?:/(nachricht))?)?|antworten/(A-[0-9A-F]{8})/(strom|stopp))')


class NichtGefunden(LookupError):
    pass


class HarnessApi:
    def __init__(self, hub):
        self.hub = hub
        self.sitzungen = Sitzungen(hub.project_root / 'runtime_data' / 'harness' / 'sitzungen')
        self.stroeme = Stroeme()
        self._start = threading.Lock()
        self.execute = lambda mission, request: hub.runtime.control.execute(mission, request)     # in Tests ersetzbar
        self.threads = {}

    # ---- Hilfen
    def _melden(self, name, daten):
        events = getattr(self.hub, 'events', None)
        if events is not None:
            events.publish(name, daten)

    def _audit(self, event, payload):
        try:
            self.hub.runtime.audit.append(event, component='harness', payload=payload)
        except Exception:
            pass

    def geladen(self):
        """Die geladenen Modelle des llama-server (HS-50: nur dieser) – und der Grund, wenn keines läuft."""
        rt = self.hub.runtime
        server = getattr(rt, 'llama_server', None)
        loaded = server.loaded_models() if server is not None else []
        grund = getattr(rt, 'llama_server_error', None)
        return loaded, grund

    def projekte(self):
        try:
            return {'projekte': harness_projekte.laden(self.hub.project_root), 'fehler': None}
        except harness_projekte.ProjektFehler as exc:
            return {'projekte': [], 'fehler': str(exc)}

    def _projekt(self, pid):
        p = next((x for x in self.projekte()['projekte'] if x['id'] == pid), None)
        if p is None:
            raise ValueError('projekt_unbekannt')
        return p

    def _sitzung(self, sid):
        try:
            return self.sitzungen.laden(sid)
        except SitzungFehler as exc:
            if str(exc) == 'sitzung_unbekannt':
                raise NichtGefunden('sitzung_unbekannt') from exc
            raise

    # ---- Wege
    def handle(self, method, path, query='', payload=None):
        """(status, body) – oder ('sse', antwort, ab) für den Strom. ValueError → 400, NichtGefunden → 404 (im Server)."""
        m = WEG.fullmatch(path)
        if not m:
            raise NichtGefunden('weg_unbekannt')
        projekte, sitzungen, sid, nachricht, aid, aktion = m.groups()
        payload = payload or {}
        q = parse_qs(query or '')
        if projekte and method == 'GET':
            return 200, self.projekte()
        if sitzungen and not sid:
            if method == 'GET':
                laufend = {a.sitzung_id: a.id for a in self.stroeme.laufende()}
                liste = self.sitzungen.liste(q['projekt'][0] if q.get('projekt') else None)
                for s in liste:
                    s['laeuft'] = laufend.get(s['id'])
                return 200, {'sitzungen': liste, 'laufend': laufend}
            if method == 'POST':
                return 200, self.anlegen(payload)
        if sid and not nachricht:
            if method == 'GET':
                s = self._sitzung(sid)
                laufend = self.stroeme.laufend_in(sid)
                return 200, dict(s, id=sid, laeuft=laufend.id if laufend else None)
            if method == 'PATCH':
                return 200, self.aendern(sid, payload)
            if method == 'DELETE':
                return 200, self.loeschen(sid)
        if nachricht and method == 'POST':
            return 200, self.nachricht(sid, payload)
        if aid:
            antwort = self.stroeme.hole(aid)
            if antwort is None:
                raise NichtGefunden('antwort_unbekannt')
            if aktion == 'strom' and method == 'GET':
                try:
                    ab = int((q.get('last') or ['0'])[0] or 0)
                except ValueError:
                    ab = 0
                return 'sse', antwort, max(0, ab)
            if aktion == 'stopp' and method == 'POST':
                antwort.stoppen()
                self._audit('HARNESS_STOPP', {'sitzung_id': antwort.sitzung_id, 'antwort_id': aid})
                return 200, {'antwort_id': aid, 'gestoppt': True}
        raise NichtGefunden('methode_unbekannt')

    def anlegen(self, payload):
        if payload.get('vorlage') is not None:
            raise ValueError('vorlage_ab_stufe_3')
        projekt = self._projekt(str(payload.get('projekt') or harness_projekte.STANDARD['id']))
        titel = titel_aus(payload.get('titel') or '')
        # Eine Mission je Sitzung (wie chat_reply): alle Züge hängen daran (Audit, Nutzung). Ohne hub.lock (K3).
        mission = self.hub.runtime.brain.create_mission('Harness-Sitzung ' + (titel or projekt['name']), None, 'S1')
        kopf = self.sitzungen.anlegen(projekt['id'], titel, modell=(str(payload['modell'])[:200] if payload.get('modell') else None),
                                      mission_id=mission['identity']['mission_id'])
        self._audit('HARNESS_SITZUNG_ANGELEGT', {'sitzung_id': kopf['id'], 'projekt': projekt['id'], 'mission_id': kopf['mission_id']})
        self._melden('harness.sitzung', {'id': kopf['id'], 'was': 'angelegt', 'projekt': projekt['id'], 'titel': kopf['titel']})
        return kopf

    def aendern(self, sid, payload):
        self._sitzung(sid)
        if 'titel' in payload:
            self.sitzungen.titel_aendern(sid, payload.get('titel'))
        if 'modell' in payload:
            self.sitzungen.modell_waehlen(sid, payload.get('modell'))
        s = self.sitzungen.laden(sid)
        self._melden('harness.sitzung', {'id': sid, 'was': 'geaendert', 'titel': s['titel']})
        return dict(s, id=sid)

    def loeschen(self, sid):
        self._sitzung(sid)
        if self.stroeme.laufend_in(sid):
            raise ValueError('antwort_laeuft')
        ziel = self.sitzungen.loeschen(sid)
        self._audit('HARNESS_SITZUNG_VERSCHOBEN', {'sitzung_id': sid, 'nach': 'geloescht/' + ziel.name})
        self._melden('harness.sitzung', {'id': sid, 'was': 'verschoben'})
        return {'id': sid, 'verschoben': 'geloescht/' + ziel.name}

    def nachricht(self, sid, payload):
        text = payload.get('text')
        if not isinstance(text, str) or not text.strip() or len(text) > TEXT_MAX:
            raise ValueError('text_required')
        if payload.get('anhaenge'):
            raise ValueError('anhaenge_ab_stufe_2')
        s = self._sitzung(sid)
        loaded, grund = self.geladen()
        if not loaded:
            return {'status': 'kein_modell', 'grund': 'Kein Modell geladen – Modell wählen.' + (' Grund: ' + str(grund) if grund else '')}
        info = loaded[0]
        modell = info.get('identifier') or info.get('modelKey')
        if s['modell'] and any(s['modell'] in (x.get('identifier'), x.get('modelKey')) for x in loaded):
            modell = s['modell']
        with self._start:
            if self.stroeme.laufend_in(sid):
                raise ValueError('antwort_laeuft')
            try:
                antwort = self.stroeme.anlegen(sid)
            except ZuVieleAntworten as exc:
                raise ValueError('zu_viele_antworten') from exc
        verlauf = [{'role': 'user' if e['typ'] == 'captain' else 'assistant', 'content': e.get('text') or ''}
                   for e in s['eintraege'] if e.get('typ') in ('captain', 'modell') and (e.get('text') or '').strip()][-VERLAUF_MAX:]
        self.sitzungen.anhaengen(sid, {'typ': 'captain', 'text': text, 'anhaenge': []})
        if not s['titel']:
            self.sitzungen.titel_aendern(sid, text)
            self._melden('harness.sitzung', {'id': sid, 'was': 'geaendert', 'titel': titel_aus(text)})
        projekt = next((p for p in self.projekte()['projekte'] if p['id'] == s['kopf'].get('projekt')), None)
        from ..chat_tools import ChatTools
        box = ChatTools(self.hub, LESEN)
        messages = [{'role': 'system', 'content': schleife.system_prompt(projekt['name'] if projekt else None, box.names)},
                    *verlauf, {'role': 'user', 'content': text}]
        guard = getattr(self.hub.runtime.model_router, 'content_guard', None)
        from ..core.content_guard import MODE_SHARP
        live = guard is None or not MODE_SHARP.get(guard.mode, True)          # D-E2: im scharfen Modus kein Live-Text
        fenster = info.get('contextLength') if isinstance(info.get('contextLength'), int) else None
        mission_id = s['kopf'].get('mission_id')

        def lauf():
            try:
                mission = self.hub.runtime.missions.load(mission_id)
                schleife.laufen(self.execute, mission, box, messages, antwort, modell=modell, provider=PROVIDER, sitzungen=self.sitzungen,
                                sitzung_id=sid, fenster=fenster, live_text=live)
            except Exception as exc:                  # nie still: der Strom endet mit Grund, die Sitzung bekommt eine Zeile
                grund = f'{type(exc).__name__}: {exc}'[:300]
                antwort.senden('fehler', {'grund': grund})
                try:
                    self.sitzungen.anhaengen(sid, {'typ': 'modell', 'antwort_id': antwort.id, 'text': '', 'ende': 'fehler', 'grund': grund, 'zuege': 0})
                except Exception:
                    pass
                antwort.senden('ende', {'ende': 'fehler', 'zuege': 0, 'token': {'ein': 0, 'aus': 0}, 'grund': grund})
            finally:
                antwort.beenden()
                letzte = (antwort.ereignisse[-1]['data'] if antwort.ereignisse else {})
                self._audit('HARNESS_ANTWORT', {'sitzung_id': sid, 'antwort_id': antwort.id, 'ende': letzte.get('ende'), 'zuege': letzte.get('zuege'),
                                                'werkzeuge': sum(1 for e in antwort.ereignisse if e['event'] == 'werkzeug.ende')})
                self._melden('harness.antwort', {'sitzung_id': sid, 'antwort_id': antwort.id, 'zustand': 'fertig', 'ende': letzte.get('ende')})
                self.threads.pop(antwort.id, None)

        t = threading.Thread(target=lauf, name='harness-' + antwort.id, daemon=True)
        self.threads[antwort.id] = t
        self._melden('harness.antwort', {'sitzung_id': sid, 'antwort_id': antwort.id, 'zustand': 'laeuft'})
        t.start()
        return {'status': 'laeuft', 'antwort_id': antwort.id, 'modell': modell, 'live': live}
