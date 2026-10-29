from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import hashlib
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit
import webbrowser

import yaml

from . import uix_diag
from .models import gpu_preflight
from .jobs.job_supervisor import FINAL_STATES, JobError
from .core.mission import ALLOWED
from .core.errors import InvalidTransition
from .core.util import atomic_write_json, load_json, utcnow
from .local_switches import ALLOWED as SWITCH_ALLOWED, LocalSwitches
from . import cloud_settings, labor_runs
from .cloud_settings import CloudKeyStore
from .models.role_routing import RoutingConfig
from .jobs.rework_watch import ReworkWatch
from .models.model_loader import LoadError
from .jobs.testlab import TestLab, default_path
from .runtime import GuppiRuntime

INSTALLATION = Path(__file__).resolve().parents[3]     # das Programmverzeichnis (runtime/src/guppi_runtime/..), Ziel der Updates


def quelle_pruefen(payload):
    """Der Ordner eines Imports, bevor irgendetwas gelesen wird. Liefert (Art, Ordner) oder wirft einen Satz mit dem nächsten Schritt.
    Eigener Schritt, damit der Import einheitlich prüft (Auftrag AUFTRAG_EINHEITLICHER_IMPORT_2026-10-16, Abschnitt 3.1)."""
    p = payload if isinstance(payload, dict) else {}
    kind = str(p.get('kind') or '').strip()
    if kind not in ('tool', 'shell'):
        raise ValueError('Bitte zuerst wählen, ob es eine Shell oder ein Werkzeug ist.')
    source = str(p.get('source') or '').strip()
    if not source:
        raise ValueError('Bitte den vollständigen Ordnerpfad eingeben, zum Beispiel D:\\Shells\\meine-shell.')
    folder = Path(source)
    if not folder.is_absolute() or '..' in folder.parts:
        raise ValueError('Der Ordnerpfad muss vollständig sein und darf kein „..“ enthalten, zum Beispiel D:\\Shells\\meine-shell.')
    if not folder.is_dir():
        raise ValueError(f'Dieser Ordner gibt es nicht: {folder}. Pfad prüfen oder den Ordner über den Dialog wählen.')
    if not (folder / f'{kind}.yaml').is_file():
        raise ValueError(f'In diesem Ordner fehlt die Datei {kind}.yaml. Ohne sie gibt es nichts zu importieren.')
    return kind, folder
from . import local_paths
from .models import model_add
from .chat_tools import ChatTools
from .devenv.model_tools import run_tool_loop
from .uix_library import LibraryDesk
from .desk import actions as desk_actions
from .desk import builtin_kinds as desk_builtin_kinds
from .desk import extensions as desk_extensions
from .desk import gated as desk_gated
from .desk import kinds as desk_kinds
from . import uix_clients
from .desk import boundaries as desk_boundaries
from .desk import vorgabe as desk_vorgabe
from .desk import gateway as desk_gateway
from .desk import install as desk_install
from .desk import intents as desk_intents
from .desk import decisions as desk_decisions
from .desk import registry as desk_registry
from .desk import live as desk_live
from .desk import objects as desk_objects
from .desk.events import EventStream, Poller
from .desk.gateway import Gateway


def _compact_mission(m):
    route = ((m.get('routing') or {}).get('route') or {})
    # SPEC_UIX_STUFE6 §2.5 (S6-E3): eine Definition von „offen“ für Baum, Aufgaben, Leiste und Arbeitsplatz. Ein Freigabe-Antrag
    # (desk/gated.py) ist keine Aufgabe – er steht im Posteingang und ist nach der Entscheidung weg.
    antrag = bool((m.get('context') or {}).get('gated_request'))
    status, phase = m.get('lifecycle', {}).get('status'), m.get('lifecycle', {}).get('phase')
    return {
        'antrag': antrag,
        'offen': status == 'active' and (phase or '') not in ('COMPLETE', 'FAILED') and not antrag,
        'mission_id': m.get('identity', {}).get('mission_id'),
        'created_at': m.get('identity', {}).get('created_at'),
        'mission_class': m.get('identity', {}).get('mission_class'),
        'intent': m.get('captain_intent', {}).get('original'),
        'objective': m.get('objective', {}).get('current'),
        'phase': m.get('lifecycle', {}).get('phase'),
        'status': m.get('lifecycle', {}).get('status'),
        'risk': m.get('risk', {}).get('level'),
        'pending_gates': len(m.get('human_gates', {}).get('pending', [])),
        # the Deck shows the gates and the sea chart without loading the whole record (Build 6)
        'gates': [{'gate_id': g.get('gate_id'), 'action': (g.get('request') or {}).get('exact_action'), 'targets': (g.get('request') or {}).get('targets', []),
                   'risks': (g.get('request') or {}).get('risks', []), 'rollback': bool((g.get('request') or {}).get('rollback_available'))}
                  for g in m.get('human_gates', {}).get('pending', []) if isinstance(g, dict)],
        'steps': [str(st.get('description') or st.get('action') or st.get('id') or '') for st in ((m.get('plan') or {}).get('steps') or []) if isinstance(st, dict)][:12],
        'steps_done': len(((m.get('execution') or {}).get('results') or [])),
        # ARTIFACT_ONLY heißt: nur ein Plan-Artefakt, nichts ausgeführt – die Oberfläche darf das nicht „fertig“ nennen
        'qualification': (m.get('result') or {}).get('qualification'),
        'skills': [x.get('id') for x in route.get('skills', [])],
        'tools': [x.get('id') for x in route.get('tools', [])],
        'topic_gaps': route.get('topic_gaps', []),
    }


class UIXHub:
    def __init__(self, project_root: Path, architecture_root: Path):
        self.project_root = Path(project_root).resolve()
        self.architecture_root = Path(architecture_root).resolve()
        self.runtime = GuppiRuntime(self.project_root, self.architecture_root)
        self.boot_state = self.runtime.boot()
        self.lock = threading.RLock()
        from .projects import ProjectRegistry
        self.projects = ProjectRegistry(self.runtime)
        # Models put on the GPU from the UIX follow the TESTLAB rule: the shared GPU lease is held for as long as the model is loaded.
        self.lab = TestLab(default_path(self.project_root))
        self.model_lock = threading.Lock()
        self._routing_boot = self._routing_values()           # the routing overlay as this process started with it
        self._switch_boot = {s: dict(v) for s, v in self.runtime.switches.values.items()}     # what this process started with
        self.sync_guard_mode()                                # Build 16: Schärfe des Inhaltsschutzes aus dem Modus des Projekts
        self._run = subprocess.run       # replaced in tests: no real PowerShell / taskkill / nvidia-smi
        self.gpu_token = None
        self._beat_stop = None
        self.library = LibraryDesk(self)                     # Bibliothek window: own capabilities, imported libraries, the Captain's own skills
        # The desk (Build 7): manifests and allowlist for the desktop modules, one decision list, one event stream instead of a poll per window.
        self.gateway = Gateway(self.project_root)
        self.gateway.entwicklung = self.runtime.switches.apply('entwicklung', 'enabled', False) is True    # Stufe 6 (S6-E4)
        self.events = EventStream()
        self.poller = Poller(self, self.events)
        # Gedächtnis der Oberfläche (SPEC_DOCK_OHNE_NEUAUFBAU_v1 §9.2, §10): Arbeitsstand, Ablage der Werkzeuge, Gesprächsverlauf.
        # Nur im Speicher dieses Prozesses – übersteht Neuladen und Shell-Wechsel, nicht den Neustart der Runtime.
        from .desk.arbeitsstand import Gedaechtnis
        self.gedaechtnis = Gedaechtnis()
        # Spec 0 (D1): Objekttypen und Verben stehen im Register. Die Erweiterungen docken einmal hier an, danach ist es zu –
        # über eine Anfrage kommt kein Typ dazu. Ein neuer Anwendungsfall ist ein Modul in desk/extensions.MODULES, keine Zeile hier.
        self.kinds = desk_builtin_kinds.new_registry()
        self.extensions = desk_extensions.load(self.kinds, self, desk_extensions.MODULES, audit=self._desk_audit)
        self.kinds.freeze()
        self._extensions_started = None
        # Harness-Shell (SPEC_HARNESS_SHELL_v1 Stufe 1): Sitzungen, Antwort-Strom, Schleife – eigene Sperren, nie self.lock (K3)
        from .harness.api import HarnessApi
        self.harness = HarnessApi(self)

    def _desk_audit(self, event, payload):
        self.runtime.audit.append(event, component='desk', payload=payload)

    def start_extensions(self):
        """Der Takt der Erweiterungen (z. B. der Herzschlag der Orchestrierung) läuft, solange die Oberfläche läuft – einmal je Hub."""
        if self._extensions_started is None:
            self._extensions_started = desk_extensions.start(self, self.extensions, audit=self._desk_audit)
        return self._extensions_started

    def status(self):
        rt = self.runtime
        return {
            'system_state': 'READY' if rt.observability.overall() == 'HEALTHY' else 'SAFE_MODE',
            'health': rt.observability.report(),
            'project': {
                'name': self.project_root.name,
                'path': str(self.project_root),
            },
            'tools': rt.tools.list(),
            'capability_router': {
                'healthy': rt.capability_router.health(),
                'skills': len(rt.registry.skills),
                'topics': len(rt.capability_router.topic_catalog()),
            },
            'hardware': rt.hardware.to_dict(),
            'hardware_manager': {
                'capabilities': rt.hardware_manager.capabilities(),
                'profile_state': rt.hardware_manager.state_record(),
            },
            'development_environment': rt.sandbox.doctor(),
            'recommended_model_profile': rt.recommended_model_profile,
            'model_runtimes': rt.model_router.status(check_health=False),
            'portable_model_runtime': rt.model_runtime.status(),
            'self_development': rt.self_development.view(),
        }

    def missions(self):
        return [_compact_mission(m) for m in self.runtime.missions.list()]

    # ---- the desk (Build 7): one list of decisions, one snapshot the event stream watches, the strip's instruments
    def decisions_view(self):
        """Every open decision in one shape: mission gates and the change requests of chat, Werkstatt and Bibliothek."""
        items = desk_decisions.collect(self.missions(), self._open_requests(), self._open_crossings(), self._content_decisions(), self._scheduler_decisions(),
                                       self.harness.entscheidungen())            # Harness-Shell Stufe 2: Freigabe-Karten (HS-22)
        return {'items': items, 'summary': desk_decisions.summary(items)}

    def _scheduler_decisions(self):
        """Spec 2 (D2.8, D2.10): the model scheduler's questions (cloud offer, locked server); none while it is off."""
        sched = self._scheduler()
        try: return sched.decisions() if sched is not None else []
        except Exception: return []

    def _answer_scheduler(self, decision, way):
        """The Captain's answer to a scheduler question. Accepting a cloud offer only marks the job `cloud_offload_approved`: what that
        does is Spec 3."""
        sched = self._scheduler()
        if sched is None: raise ValueError('unknown_decision')
        out = sched.answer(decision['id'], way)
        if out.get('approved'):
            sup = getattr(self.runtime, 'job_supervisor', None)
            if sup is not None:
                try:
                    with sup.store.mutate(out['run_id']) as job: job['cloud_offload_approved'] = True
                except Exception: self.runtime.audit.append('SLOT_CLOUD_MARK_FAILED', component='uix', payload={'run_id': out['run_id']})
            self.runtime.audit.append('CLOUD_OFFLOAD_APPROVED', component='uix', payload={'run_id': out['run_id']})
        return out

    # ---- Build 16: der Inhaltsschutz (core/content_guard.py) – seine Entscheidungen, sein Modus, sein Zustand
    @property
    def content_guard(self):
        return getattr(self.runtime.model_router, 'content_guard', None)

    def _content_decisions(self):
        guard = self.content_guard
        return guard.decisions() if guard is not None else []

    def sync_guard_mode(self):
        """S5: der Modus des aktiven Projekts entscheidet die Schärfe. Nichts bestätigt = scharf (G-04, Ticket B6-G-01); Beobachten nur als
        bestätigter Modus des Projekts."""
        guard = self.content_guard
        if guard is None:
            return None
        try:
            view = self.boundaries_view()
        except Exception:
            view = {}
        mode = view.get('mode') if view.get('confirmed') else 'sandbox'      # G-04 (B6-G-01): nichts bestätigt = scharf
        if mode != guard.mode:
            guard.set_mode(mode)
            self.runtime.audit.append('SG_MODE_SET', component='content-guard', payload={'mode': guard.mode, 'project_id': view.get('project_id')})
        return guard.mode

    def guard_status(self, payload=None):
        """GET /api/guard/status – was das Werkzeug „schutz“ zeigt: Gruppen, Schärfe, Zählungen, die letzten Ereignisse. Kein Text."""
        guard = self.content_guard
        if guard is None:
            return {'enabled': False, 'note': 'Kein Inhaltsschutz in dieser Runtime.'}
        self.sync_guard_mode()
        view = self.boundaries_view()
        return {'enabled': True, **guard.status(), 'project_id': view.get('project_id'), 'confirmed': bool(view.get('confirmed')),
                'sentence': ('Sandbox: alle Regeln scharf.' if guard.mode == 'sandbox' else
                             'Beobachten: Funde werden gezählt und gezeigt; was den Rechner verlässt und der Grundschutz sind scharf.'),
                'limits': 'Pseudonymisierung ist keine Anonymisierung. Was mit welcher Rechtsgrundlage an einen Anbieter darf, entscheidet ihr – SEDRA zeigt und bindet die Entscheidung, es trifft sie nicht.'}

    def decide(self, payload):
        """Answer one decision the way it offers (§10.3). Approve, reject and apply stay the calls they were: the guard's
        once-only token and content binding are untouched; this only puts them behind one door."""
        did = str(payload.get('id') or '').strip()
        way = str(payload.get('way') or '').strip()
        items = self.decisions_view()['items']
        decision = next((d for d in items if d['id'] == did), None)
        desk_decisions.check_answer(decision, way)
        if decision['kind'] == 'boundary':
            crossing = self.open_crossings.get(did)
            if crossing is None:
                raise ValueError('unknown_decision')
            out = self._answer_crossing(crossing, way)
            self.events.publish('decision.answered', {'id': did, 'kind': 'boundary', 'way': way})
            return out
        if decision['kind'] in ('cloud_offload', 'slot_server'):
            result = self._answer_scheduler(decision, way)
            self.events.publish('decision.answered', {'id': did, 'kind': decision['kind'], 'way': way})
            return {'status': 'answered', 'id': did, 'way': way, 'result': result}
        if decision['kind'] == 'harness_freigabe':          # Harness-Shell Stufe 2 (HS-22): dieselbe Tür wie die Karte im Verlauf
            result = self.harness.beantworten(did.removeprefix('harness:'), way, payload.get('note'), ueber='posteingang')
            return {'status': 'answered', 'id': did, 'way': way, 'result': result}
        if decision['kind'] == 'content':
            result = self.content_guard.answer(did, way)
            self.events.publish('decision.answered', {'id': did, 'kind': 'content', 'way': way})
            return {'status': 'answered', 'id': did, 'way': way, 'result': result}
        mission_id, gate_id = decision['mission_id'], decision['gate_id']
        if decision['apply'] is None and desk_gated.applier(decision['kind'].removeprefix('request:')):    # Spec 1, D1.3.3 (G2-S1-09)
            out = desk_gated.decide(self, mission_id) if way == 'freigeben_und_anwenden' else desk_gated.reject(self, mission_id)
            self.events.publish('decision.answered', {'id': did, 'kind': decision['kind'], 'way': way})
            return {'status': 'answered', 'id': did, 'way': way, 'result': out}
        if way == 'ablehnen':
            out = self.reject_gate({'mission_id': mission_id, 'gate_id': gate_id})
            if decision['kind'] == 'request:gateway':
                vid = ((decision.get('binding') or {}).get('vorgang_id'))
                if vid:
                    try: self.gw.abgelehnt(vid)
                    except Exception: pass
        else:
            out = self.approve_gate({'mission_id': mission_id, 'gate_id': gate_id})
            if way == 'freigeben_und_anwenden':
                apply = {'/api/switch/apply': self.switch_apply, '/api/routing-config/apply': self.routing_apply,
                         '/api/model/add/apply': self.model_add_apply, '/api/library/custom/apply': self.library.custom_apply,
                         '/api/boundaries/apply': self.boundaries_apply, '/api/uix/install/apply': self.install_apply,
                         '/api/uix/trust/apply': self.trust_apply, '/api/gateway/apply': self.gateway_apply}.get(decision['apply'])
                if apply is None:
                    raise ValueError('decision_cannot_be_applied')
                out = apply({'mission_id': mission_id})
        self.events.publish('decision.answered', {'id': did, 'kind': decision['kind'], 'way': way})
        return {'status': 'answered', 'id': did, 'way': way, 'result': out}

    # ---- Build 9: Vorhaben (Regel 8) – Gesprächsgegenstand, aus dem Aufgaben werden
    @property
    def intents(self):
        store = self.__dict__.get('_intents')
        if store is None:
            store = self.__dict__['_intents'] = desk_intents.Store(self.project_root)
        return store

    def intent_create(self, payload):
        """Ein Vorhaben anlegen. Ohne Gate – es wird nichts ausgeführt, es ist der Satz, um den es geht.
        Mit `stufen` (Liste) oder `vorlage` (Kennung aus GET /api/intent/vorlagen) bekommt es seine Stufen (19.10.2026)."""
        from .desk import vorhaben_vorlagen as vv
        project = self._active_project(payload.get('project_id'))
        stufen, vorlage = payload.get('stufen'), payload.get('vorlage')
        title, text = payload.get('title'), payload.get('text')
        if vorlage and vorlage != 'leer':
            v = vv.finde(vorlage)
            if v is None:
                raise ValueError('unknown_vorlage')
            stufen = stufen or v['stufen']
            title, text = title or v['titel'], text or v['satz']
        entry = self.intents.add(title, text, (project or {}).get('project_id'), utcnow(), stufen=stufen, vorlage=vorlage)
        self.runtime.audit.append('INTENT_CREATED', component='desk', payload={'id': entry['id'], 'title': entry['title'][:80],
                                                                                'stufen': len(entry.get('stufen') or [])})
        self.events.publish('tools.refresh', {})
        return entry

    def intent_vorlagen(self, payload=None):
        """GET /api/intent/vorlagen – die Vorlagen für Vorhaben mit Stufen. Nur Text, legt nichts an."""
        from .desk import vorhaben_vorlagen as vv
        return {'vorlagen': vv.liste()}

    def intent_to_task(self, intent_id, extra=None, stufe=None):
        """GUPPI macht aus dem Vorhaben eine Aufgabe: geplant, nicht ausgeführt – wie jede Aufgabe aus dem Gespräch.
        Mit `stufe` (Index) wird die Stufe zur Aufgabe: ihr Text ist der Auftrag, das Vorhaben der Rahmen; die Aufgabe hängt an der Stufe."""
        entry = self.intents.get(intent_id)
        if entry is None:
            raise ValueError('unknown_intent')
        stufen = entry.get('stufen') or []
        if stufe is not None:
            try:
                stufe = int(stufe)
            except (TypeError, ValueError):
                raise ValueError('unknown_stufe')
            if not 0 <= stufe < len(stufen):
                raise ValueError('unknown_stufe')
            s = stufen[stufe]
            text = f"{entry['title']} – Stufe {stufe + 1} von {len(stufen)}: {s.get('name')}. " + (str(extra or '').strip() or s.get('text') or '')
        else:
            text = (str(extra or '').strip() or entry['text'] or entry['title'])
        out = self.create_chat_mission({'intent': text[:400], 'project_id': entry.get('project_id')})
        mission_id = out['mission']['mission_id']
        self.intents.attach(entry['id'], mission_id, stufe=stufe)
        self.runtime.audit.append('INTENT_TASK_CREATED', component='desk', payload={'intent': entry['id'], 'mission_id': mission_id,
                                                                                     'stufe': stufe})
        return {'intent': entry['id'], 'mission_id': mission_id, 'mission': out['mission'], 'stufe': stufe}

    def _intent_object(self, entry):
        missions = {m['mission_id']: m for m in self.missions()}
        state, summary = desk_intents.state_of(entry, missions)
        obj = desk_objects.intent_object(entry, state, summary)
        obj['stufen'] = desk_intents.stufen_of(entry, missions)
        obj['vorlage'] = entry.get('vorlage') or ''
        if obj['stufen']:
            done = sum(1 for s in obj['stufen'] if s['state'] == 'fertig')
            cur = next((s for s in obj['stufen'] if s['current']), None)
            obj['summary'] = entry['title'] + f" – {done} von {len(obj['stufen'])} Stufen fertig" + (f" · jetzt: {cur['name']}" if cur else '')
            if state == 'noch keine Aufgabe':
                obj['state'] = 'offen'
        return obj

    # ---- Build 9: ein fremdes Modul einbauen (Vertrag §6 „Installation“, §7)
    INSTALL_ACTION = 'install_module'

    def install_request(self, payload):
        """Ein Modul zur Freigabe vorlegen: Manifest, jede Datei mit Hash, und was die Durchsicht gefunden hat.

        Geschrieben wird hier nichts. Der Ordner wird gelesen, geprüft und beschrieben; eingebaut wird er erst nach der Freigabe."""
        kind, folder = quelle_pruefen(payload)
        area = 'tools' if kind == 'tool' else 'shells'
        read = desk_install.read_module(folder, area)
        doc = yaml.safe_load((folder / (f'{kind}.yaml')).read_text(encoding='utf-8'))
        check = desk_gateway.check_tool if kind == 'tool' else desk_gateway.check_shell
        # Was durch das Gate kommt, hat nicht der Captain geschrieben: es ist COMMUNITY, egal was das Manifest behauptet.
        # Bis zum 15.10.2026 galt das Vertrauen aus der Datei – ein fremdes Modul mit `trust: CAPTAIN` hätte seine Schreibrouten
        # behalten. Gefunden mit der ersten externen Lieferung. Wer es hochstufen will, tut das bewusst in der Datei.
        if isinstance(doc, dict) and isinstance(doc.get(kind), dict):
            doc[kind]['trust'] = 'COMMUNITY'
        manifest, errors = check(doc, folder, 'local')
        if errors:
            raise ValueError('Das Manifest wurde abgelehnt: ' + ', '.join(errors)[:300] + '. Die Angaben in ' + kind + '.yaml korrigieren und erneut vorlegen.')
        if manifest['id'] in (self.gateway.tools() if kind == 'tool' else self.gateway.shells()):
            raise ValueError(f'Die Kennung „{manifest["id"]}“ ist schon vergeben (eingebaute {"Shell" if kind == "shell" else "Werkzeug"} oder früherer Import). '
                             f'Im Manifest eine andere id setzen oder die alte Fassung zuerst entfernen.')
        describe = (f'Modul „{manifest["name"]}“ ({manifest["id"]}) einbauen · {len(read["files"])} Datei(en) · '
                    f'als COMMUNITY, nur Leserouten ({len(manifest["api"])}) · {desk_install.summary(read["findings"])}'
                    + (' · bringt eigene Objekttypen: ' + ', '.join(manifest.get('own_types') or []) if manifest.get('own_types') else ''))
        binding = {'kind': kind, 'id': manifest['id'], 'source': str(folder), 'trust': manifest['trust'],
                   'files': read['files'], 'routes': manifest['api'], 'findings': read['findings'], 'describe': describe}
        with self.lock:
            m = self.runtime.brain.create_mission(describe[:160], None, 'S1')
            gate = self.runtime.guard.create_gate(m['identity']['mission_id'], self.INSTALL_ACTION, f'{area}:{manifest["id"]}',
                                                  risks=['fremder Code läuft danach in derselben Seite wie die Shell']
                                                        + ([f['flag'] + ' in ' + f['file'] for f in read['findings'][:6]] if read['findings'] else []),
                                                  rollback_available=True, request_binding=binding)
            m['human_gates']['pending'].append(gate)
            m['context']['install_request'] = binding
            self.runtime.missions.save(m)
        return self._remember('install', {'mission_id': m['identity']['mission_id'], 'gate': gate, 'binding': binding})

    def install_apply(self, payload):
        """Nach der Freigabe: die Dateien kopieren – aber nur, wenn jede noch genau den Hash hat, der im Gate stand."""
        mission_id = str(payload.get('mission_id') or '').strip()
        if not mission_id:
            raise ValueError('mission_id_required')
        rt = self.runtime
        with rt.missions.execution_lock(mission_id):
            m = rt.missions.load(mission_id)
            binding = (m.get('context') or {}).get('install_request')
            token = (m.get('execution') or {}).get('approval_token')
            if not binding:
                raise ValueError('not_an_install_request')
            if not token:
                raise ValueError('captain_approval_required')
            area = 'tools' if binding['kind'] == 'tool' else 'shells'
            if not rt.guard.authorize(token, mission_id=mission_id, action=self.INSTALL_ACTION,
                                      target=f"{area}:{binding['id']}", request_binding=binding)['authorized']:
                raise ValueError('captain_approval_invalid')
            source = Path(binding['source'])
            for record in binding['files']:          # genau die Dateien, genau diese Fassung
                path = source / record['path']
                if not path.is_file() or desk_install.sha256(path) != record['sha256']:
                    raise ValueError('module_changed_since_the_request:' + record['path'])
            target = self.project_root / 'local_config' / area / binding['id']
            if target.exists():
                raise ValueError('module_id_already_installed')
            # Erst daneben bauen, dann an seinen Platz rücken: bricht etwas ab, bleibt kein halbes Modul liegen, das beim
            # nächsten Öffnen geladen würde. Und nach dem Kopieren wird noch einmal gehasht – geprüft ist, was jetzt dort steht.
            staging = target.with_name(target.name + '.im-bau')
            if staging.exists():
                shutil.rmtree(staging)
            staging.mkdir(parents=True)
            try:
                for record in binding['files']:
                    destination = staging / record['path']
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source / record['path'], destination)
                    if desk_install.sha256(destination) != record['sha256']:
                        raise ValueError('module_changed_while_copying:' + record['path'])
                # nach der Hashprüfung: das eingebaute Manifest sagt, was gilt – COMMUNITY. Die Quelle bleibt unverändert.
                man_name = 'tool.yaml' if binding['kind'] == 'tool' else 'shell.yaml'
                man_doc = yaml.safe_load((staging / man_name).read_text(encoding='utf-8'))
                man_doc[binding['kind']]['trust'] = 'COMMUNITY'
                (staging / man_name).write_text(yaml.safe_dump(man_doc, allow_unicode=True, sort_keys=False), encoding='utf-8')
                staging.replace(target)
            except BaseException:
                shutil.rmtree(staging, ignore_errors=True)
                raise
            m['execution'].pop('approval_token', None)
            m['result'] = {'kind': 'install', 'id': binding['id'], 'area': area, 'files': len(binding['files'])}
            m['lifecycle']['status'] = 'closed'
            rt.missions.save(m)
            rt.audit.append('UIX_MODULE_INSTALLED', component='desk', mission_id=mission_id,
                            payload={'kind': binding['kind'], 'id': binding['id'], 'trust': binding['trust'],
                                     'files': len(binding['files']), 'findings': len(binding['findings'])})
        self.events.publish('tools.refresh', {})
        return {'status': 'installed', 'id': binding['id'], 'area': area, 'files': len(binding['files']),
                'note': 'Das Modul liegt jetzt unter local_config – die Oberfläche lädt es beim nächsten Öffnen.'}

    # ---- Build 12: die Module sichtbar machen (Spec SHELL_E_UND_MODULE §2.3)
    # Diese vier schreiben nur `local_config` – nie den Projektordner. Sie berühren deshalb keine Grenze aus Build 9, und das
    # steht auch im Werkzeug. Fremder Code bleibt ein Gate; eigene Form (Shell wechseln, an/aus, Vorlage) ist Audit
    # (Captain-Entscheidung 14.10.2026): ein Gate an dieser Stelle würde die Freigabe zur Gewohnheit machen.

    def modules_view(self, payload=None):
        """Was geladen ist, was abgelehnt wurde und warum, welche Shell läuft – die eine Liste, die das Werkzeug zeichnet."""
        manifest = self.gateway.manifest()
        config = self.gateway.registry.config()
        shells, _ = self.gateway._load('shells')
        tools, _ = self.gateway._load('tools')

        def public(folder, man, enabled=True):
            return {'id': man['id'], 'name': man.get('name') or man['id'], 'description': man.get('description') or '',
                    'version': man.get('version'), 'trust': man.get('trust'), 'origin': man.get('origin'),
                    'kind': man.get('kind'), 'slot': man.get('slot'), 'handles': man.get('handles') or [],
                    'routes': man.get('api') or [], 'folder': str(folder), 'enabled': enabled,
                    'required': man['id'] in self.REQUIRED_TOOLS,
                    'own_types': man.get('own_types') or [],
                    'preview': (Path(folder) / 'preview.png').is_file()}      # die Start-Shell fragt nicht ins Leere
        disabled = set(config['disabled'])
        return {'shell': manifest['config']['shell'],
                'shell_available': manifest['shell'] is not None,
                'shells': [dict(public(folder, man, man['id'] == config['shell']),
                                default=(man['id'] == self.gateway.registry.config()['shell']))     # Standard = uix.yaml, nicht die laufende Wahl
                           for folder, man in (shells[i] for i in sorted(shells))],
                'tools': [public(folder, man, man['id'] not in disabled) for folder, man in
                          (tools[i] for i in sorted(tools))],
                'rejected': manifest['rejected'],
                'templates': [str(self.gateway.registry.package_dir / 'tools' / '_template'),
                              str(self.gateway.registry.package_dir / 'shells' / '_template')],
                'note': 'Einbauen und Entfernen ändert nur local_config – der Projektordner wird dabei nie angefasst.'}

    def shell_standard(self, payload):
        """„Zum Standard machen“ in der Übersicht: schreibt die Shell in uix.yaml, ohne die laufende Ansicht zu wechseln.
        Kein Gate (eigene Form, wie die Wahl der Shell), aber im Audit."""
        from .uix_start import write_standard_shell
        wanted = str((payload or {}).get('shell') or '').strip()
        try:
            name = write_standard_shell(self.runtime.project_root, wanted)
        except ValueError:
            raise ValueError('unknown_shell')
        self.runtime.audit.append('UIX_STANDARD_SET', component='desk', payload={'shell': wanted})
        return {'status': 'set', 'shell': wanted, 'name': name,
                'note': f'{name} startet ab jetzt ohne Wahl. Die laufende Ansicht bleibt.'}

    def shell_set(self, payload):
        """Die aktive Shell wechseln. Kein Gate: eigene Form, mit einem Klick zurück – aber im Audit."""
        wanted = str((payload or {}).get('shell') or '').strip()
        shells = self.gateway.shells()
        if wanted not in shells:
            raise ValueError('unknown_shell')
        before = self.gateway.registry.config()['shell']
        if (payload or {}).get('nur_jetzt'):
            # Build 19: „Zur Übersicht“ aus einer Oberfläche – wie `START_SEDRA` ohne Argument: nur für diesen Lauf, die Wahl in
            # uix.yaml bleibt. Wer in der Übersicht eine Oberfläche nimmt, wählt ausdrücklich, und das hebt den Override auf.
            self.gateway.registry.shell_override = wanted
            self.runtime.audit.append('UIX_SHELL_VISIT', component='desk', payload={'from': before, 'to': wanted})
            self.events.publish('tools.refresh', {})
            return {'status': 'visit', 'shell': wanted, 'before': before,
                    'note': 'Nur für diesen Lauf – die gewählte Oberfläche bleibt in uix.yaml stehen.'}
        self.gateway.registry.save_config(shell=wanted)
        self.gateway.registry.shell_override = None     # eine ausdrückliche Wahl schlägt START_SEDRA <id> / --uebersicht dieses Starts
        self.runtime.audit.append('UIX_SHELL_CHANGED', component='desk', payload={'from': before, 'to': wanted})
        self.events.publish('tools.refresh', {})
        return {'status': 'set', 'shell': wanted, 'before': before,
                'note': 'Beim nächsten Öffnen der Seite ist die neue Shell da – der Loader lädt genau eine beim Start.'}

    def shelf_view(self):
        """GET /api/uix/shelf – die eigenen Ablagen je Shell (Build 19). Leer heißt: die Shell zeigt ihre Vorgabe."""
        return {'shelf': self.gateway.registry.shelf(), 'max': self.gateway.registry.SHELF_MAX,
                'chosen': str(self.gateway.registry._raw().get('shell') or desk_registry.DEFAULT_SHELL)}

    def shelf_save(self, payload):
        """POST /api/uix/shelf {shell, items|null} – eigene Form: Audit, kein Gate (Captain-Entscheidung 14.10.). Kein Eintrag
        führt etwas aus: ein Ort öffnet ein Fenster, ein Auftrag geht als Satz ins Gespräch und dort den gewohnten Weg."""
        shell = str((payload or {}).get('shell') or '').strip()
        if shell not in self.gateway.shells():
            raise ValueError('unknown_shell')
        items = (payload or {}).get('items')
        try:
            saved = self.gateway.registry.save_shelf(shell, items)
        except desk_registry.UixConfigError as exc:
            raise ValueError(str(exc)) from exc
        self.runtime.audit.append('UIX_SHELF_SAVED', component='desk',
                                  payload={'shell': shell, 'count': len(saved), 'reset': items is None,
                                           'kinds': sorted({e['kind'] for e in saved})})
        return {'status': 'saved' if items is not None else 'reset', 'shell': shell, 'items': saved}

    def tool_enabled(self, payload):
        """Ein Werkzeug an- oder abschalten (uix.yaml). Kein Gate, Audit – rückgängig mit demselben Knopf."""
        tool = str((payload or {}).get('id') or '').strip()
        on = bool((payload or {}).get('enabled'))
        if tool not in self.gateway.tools():
            raise ValueError('unknown_tool')
        if not on and tool in self.REQUIRED_TOOLS:
            # Ohne Gespräch gibt es kein Eingabefeld (Regel 1); ohne „Module“ käme der Captain nur über die Datei zurück.
            raise ValueError('tool_is_required:' + tool)
        config = self.gateway.registry.config()
        disabled = set(config['disabled'])
        disabled.discard(tool) if on else disabled.add(tool)
        self.gateway.registry.save_config(disabled=sorted(disabled))
        self.runtime.audit.append('UIX_TOOL_ENABLED' if on else 'UIX_TOOL_DISABLED', component='desk', payload={'id': tool})
        self.events.publish('tools.refresh', {})
        return {'status': 'on' if on else 'off', 'id': tool, 'disabled': sorted(disabled)}

    SCAFFOLD_ID = re.compile(r'^[a-z0-9-]{2,40}$')
    REQUIRED_TOOLS = ('talk', 'modules')      # das Gespräch (Vertrag) und der Weg zurück zu dieser Liste

    def module_scaffold(self, payload):
        """Aus der Vorlage ein eigenes Modul anlegen: kopieren, `id` auf den Ordnernamen setzen, prüfen, Audit.

        Kein Gate: der Inhalt ist unsere eigene Vorlage, kein fremder Code. Geprüft wird trotzdem – ein Modul, das gar nicht
        geladen würde, soll nicht erst entstehen."""
        kind = 'tools' if str((payload or {}).get('kind') or 'tool') == 'tool' else 'shells'
        mid = str((payload or {}).get('id') or '').strip()
        if not self.SCAFFOLD_ID.match(mid):
            raise ValueError('id_invalid')
        if mid in (self.gateway.tools() if kind == 'tools' else self.gateway.shells()):
            raise ValueError('module_id_already_installed')
        # Build 17: eine Shell aus Vorgabe (SPEC_SHELL_AUS_VORGABE_v1) – `vorgabe: true` nimmt die Vorlage, ein Objekt ist die Vorgabe selbst
        vorgabe = (payload or {}).get('vorgabe')
        if vorgabe is not None and kind != 'shells':
            raise ValueError('vorgabe_is_for_shells')
        if vorgabe is not None and not (vorgabe is True or isinstance(vorgabe, dict)):
            raise ValueError('vorgabe_invalid')
        template = self.gateway.registry.package_dir / kind / ('_vorgabe' if vorgabe is not None else '_template')
        if not template.is_dir():
            raise ValueError('template_missing')
        target = self.project_root / 'local_config' / kind / mid
        if target.exists():
            raise ValueError('folder_exists')
        # Gebaut wird in einem Ordner, der schon den richtigen Namen trägt: die Prüfung verlangt `id` = Ordnername, und ein
        # Zwischenname wie „routinen.im-bau“ fällt genau darüber. Der Punkt davor hält den Halter aus der Registrierung.
        holder = target.parent / ('.im-bau-' + mid)
        shutil.rmtree(holder, ignore_errors=True)
        staging = holder / mid
        staging.mkdir(parents=True)
        try:
            name = 'tool.yaml' if kind == 'tools' else 'shell.yaml'
            for item in sorted(template.iterdir()):
                if item.is_file():
                    shutil.copy2(item, staging / item.name)
            doc = yaml.safe_load((staging / name).read_text(encoding='utf-8'))
            key = 'tool' if kind == 'tools' else 'shell'
            doc[key]['id'] = mid
            doc[key]['name'] = (payload or {}).get('name') or mid
            doc[key]['trust'] = 'CAPTAIN'
            (staging / name).write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding='utf-8')
            if vorgabe is not None:
                vfile = staging / desk_gateway.VORGABE_FILE
                v = yaml.safe_load(vfile.read_text(encoding='utf-8')) if vorgabe is True else dict(vorgabe)
                if not isinstance(v, dict):
                    raise ValueError('vorgabe_invalid')
                v['id'] = mid; v['name'] = doc[key]['name']
                vfile.write_text(yaml.safe_dump(v, allow_unicode=True, sort_keys=False), encoding='utf-8')
            else:
                js = (staging / ('tool.js' if kind == 'tools' else 'shell.js'))
                js.write_text(js.read_text(encoding='utf-8').replace("id: 'beispiel'", f"id: '{mid}'")
                              .replace("'t-beispiel'", f"'t-{mid}'").replace("'sh-beispiel", f"'sh-{mid}"), encoding='utf-8')
                css = (staging / ('tool.css' if kind == 'tools' else 'shell.css'))
                if css.is_file():
                    css.write_text(css.read_text(encoding='utf-8').replace('.t-beispiel', f'.t-{mid}').replace('.sh-beispiel', f'.sh-{mid}'), encoding='utf-8')
            check = desk_gateway.check_tool if kind == 'tools' else desk_gateway.check_shell
            man, errors = check(yaml.safe_load((staging / name).read_text(encoding='utf-8')), staging, 'local')
            if errors:
                raise ValueError('scaffold_would_not_load:' + ','.join(errors)[:160])
            staging.replace(target)
        finally:
            shutil.rmtree(holder, ignore_errors=True)
        self.runtime.audit.append('UIX_MODULE_SCAFFOLDED', component='desk', payload={'kind': kind, 'id': mid, 'vorgabe': vorgabe is not None})
        self.events.publish('tools.refresh', {})
        note = ('Die Oberfläche steht – aus der Vorgabe, ohne Code. Nimm sie im Einstieg oder im Werkzeug „Module“; uix_check --shell ' + mid + ' prüft sie ganz.'
                if vorgabe is not None else 'Der Ordner liegt in local_config. Öffne ihn, schreib dein Werkzeug hinein, dann uix_check --tool ' + mid + '.')
        return {'status': 'created', 'id': mid, 'kind': kind, 'folder': str(target), 'note': note}

    # ---- Build 17: der Creator – aus Worten eine Vorgabe (desk/vorgabe.py); angelegt wird sie mit module_scaffold(vorgabe=…)
    def vorgaben_view(self, payload=None):
        """GET /api/uix/vorgaben – die drei Vorlagen (Reiter · Fenster · Seiten) mit Satz; und ob ein Modell für den Satz-Weg da ist."""
        try:
            self.runtime.model_router.choose(); model = True
        except Exception:
            model = False
        return {'templates': desk_vorgabe.templates(), 'model': model,
                'note': None if model else 'Kein Modell geladen – die drei Vorlagen gehen auch ohne.'}

    def vorgabe_propose(self, payload):
        """POST /api/uix/vorgabe {text, id, name} – GUPPI macht aus dem Satz eine Vorgabe, gegen das Schema erzwungen und geprüft.
        Legt nichts an: der Captain sieht Satz und Skizze und sagt „So anlegen“."""
        p = payload or {}
        mid = str(p.get('id') or 'meine').strip()
        if not self.SCAFFOLD_ID.match(mid):
            raise ValueError('id_invalid')
        out = desk_vorgabe.propose(self.runtime.model_router, p.get('text'), shell_id=mid, name=(p.get('name') or '').strip() or None)
        self.runtime.audit.append('UIX_VORGABE_PROPOSED', component='desk', payload={'id': mid, 'rounds': out['rounds'], 'chars': len(str(p.get('text') or ''))})
        return out

    def guard_probe(self, payload):
        """POST /api/guard/probe {text, trust, route} – was der Inhaltsschutz täte. Kein Modell, kein Speicher, keine Zählung."""
        from .gateway.probe import probe
        guard = self.content_guard
        if guard is None:
            raise ValueError('no_guard')
        p = payload or {}
        try:
            return probe(guard, p.get('text'), str(p.get('trust') or 'untrusted'), str(p.get('route') or 'local'))
        except ValueError as exc:
            raise ValueError(str(exc))

    # ---- Build 19: das KI GateWay (gateway/vorgang.py, SPEC_GATEWAY_VORGANG_v1) – ein Vorgang nach dem Studio Flow
    GATEWAY_ACTION = 'gateway_release'

    @property
    def gw(self):
        store = self.__dict__.get('_gateway')
        if store is None:
            from .gateway.vorgang import GateWay
            store = self.__dict__['_gateway'] = GateWay(self.project_root, self.runtime.audit)
        return store

    @property
    def gw_wissen(self):
        """Die Wissensbasis des GateWay (gateway/wissen.py): Regelbuch, Leitfaden, Live-Zustand – SEDRAs Blick auf seine Arbeitsumgebung."""
        w = self.__dict__.get('_gw_wissen')
        if w is None:
            from .gateway.wissen import GatewayWissen
            w = self.__dict__['_gw_wissen'] = GatewayWissen(self.project_root, self.gw)
        return w

    @property
    def fisch(self):
        """Der Fisch (19.10.2026, fisch/hub.py): Übersetzer, Nachrichten aus gegebenen Quellen, Transkripte – die Werkzeuge der Shell „Fisch“."""
        f = self.__dict__.get('_fisch')
        if f is None:
            from .fisch.hub import FischHub
            f = self.__dict__['_fisch'] = FischHub(self)
        return f

    @property
    def sprache(self):
        """Der Kern „Sprache“ (19.10.2026, sprache/hub.py): Aufnehmen und Sprache → Text für jede Shell – Provider auf dem Rechner (whisperx, whisper)."""
        s = self.__dict__.get('_sprache')
        if s is None:
            from .sprache.hub import SpracheHub
            s = self.__dict__['_sprache'] = SpracheHub(self)
        return s

    @property
    def arbeitsplatz(self):
        """Build 24 (B6-G-06, Klaus 15.10. 19:22): die Wissensbasis über den Arbeitsplatz – die Oberflächen, ihre Orte und Anleitungen,
        und was gerade wartet. Wie gw_wissen: deterministisch, vor dem Modell, nichts läuft von allein."""
        w = self.__dict__.get('_arbeitsplatz')
        if w is None:
            from .desk.arbeitsplatz import ArbeitsplatzWissen, module_aus_registry
            w = self.__dict__['_arbeitsplatz'] = ArbeitsplatzWissen(self.project_root, self.arbeitsplatz_stand, module_aus_registry(self.gateway.registry))
            if w.befunde:
                self.runtime.audit.append('UIX_ARBEITSPLATZ_BEFUND', component='uix', payload={'befunde': w.befunde[:20]})
        return w

    def aktive_shell(self):
        try:
            return self.gateway.registry.config().get('shell')
        except Exception:
            return None

    def arbeitsplatz_stand(self):
        """Der Live-Stand des Arbeitsplatzes aus den Lesewegen, die es schon gibt – nur Zahlen und Namen, kein Text eines Vorgangs."""
        def safe(fn, default):
            try: return fn()
            except Exception: return default
        decisions = safe(lambda: self.decisions_view().get('items') or [], [])
        missions = safe(self.missions, [])
        boundaries = safe(lambda: self.boundaries_view(), {})
        models = safe(self.models_view, {})
        vorgaenge = safe(lambda: self.gw.liste(), [])
        loaded = next((r['id'] for r in (models.get('recipes') or []) if r.get('loaded')), None)
        return {'shell': self.aktive_shell(), 'entscheidungen': len(decisions),
                'gateway_gesamt': len(vorgaenge), 'gateway_wartend': sum(1 for v in vorgaenge if v.get('zustand') in ('GEPRUEFT', 'WARTET', 'ENTWURF')),
                'aufgaben_offen': sum(1 for m in missions if m.get('offen')),
                'aufgaben_wartend': sum(1 for m in missions if m.get('offen') and (m.get('pending_gates') or 0) > 0),
                'grenzen_bestaetigt': bool(boundaries.get('confirmed')) if boundaries.get('project_id') else None,
                'modell_geladen': loaded, 'projekte': len(safe(self.projects.list, []))}

    def gateway_frage(self, payload):
        """POST /api/gateway/frage {frage, vorgang?} – die Antwort der Wissensbasis, ohne Modell. Audit ohne Text."""
        p = payload or {}
        frage = str(p.get('frage') or '').strip()
        if not frage or len(frage) > 20000:
            raise ValueError('frage_required')
        out = self.gw_wissen.antwort(frage, (str(p['vorgang']) if p.get('vorgang') else None))
        self.runtime.audit.append('UIX_CHAT_GATEWAY_WISSEN', component='gateway', payload={'art': out['art'], 'actions': len(out['ui_actions']), 'via': 'frage'})
        return out

    def gateway_wissen_eintrag(self, payload):
        """POST /api/gateway/wissen {frage, antwort} – eigener Eintrag des Nutzers (Klaus 15.10.: ohne Gate, nur Audit). Kein Vorgangstext."""
        p = payload or {}
        frage, antwort = str(p.get('frage') or '').strip(), str(p.get('antwort') or '').strip()
        if not frage or not antwort or len(frage) > 300 or len(antwort) > 2000:
            raise ValueError('eintrag_invalid')
        self.gw_wissen.eintragen(frage, antwort)
        self.runtime.audit.append('GW_WISSEN_EINTRAG', component='gateway', payload={'laenge_frage': len(frage), 'laenge_antwort': len(antwort)})
        return {'status': 'gemerkt'}

    def _gw_error(self, exc):
        from .gateway.vorgang import GatewayError
        if isinstance(exc, GatewayError):
            raise ValueError(str(exc))
        raise exc

    def update_suche(self, payload=None):
        """POST /api/update/suche – nur nachsehen, auf Klick: die Versions-Tags des öffentlichen Repositorys. Schreibt nichts."""
        from .update_suche import suche
        r = suche()
        self.runtime.audit.append('UPDATE_SUCHE', component='update', payload={'status': r['status'], 'neueste': r['neueste']})
        return r

    def update_vorschau(self, payload=None):
        """POST /api/update/vorschau – lädt den gewählten Release-Tag in den Staging-Ordner (nicht ins Programm), prüft das Manifest
        und nennt Dateien und Rechteänderungen. Übernommen wird erst mit /api/update/uebernehmen und der Rechte-Bestätigung."""
        from .update_holen import herunterladen
        from .update_anwenden import MANIFEST, plan
        tag = str((payload or {}).get('tag') or '')
        stand = herunterladen(INSTALLATION, tag)
        manifest = stand / MANIFEST
        if not manifest.is_file():
            raise ValueError('update_manifest_fehlt')
        p = plan(stand, INSTALLATION, manifest.read_text(encoding='utf-8'))
        self.runtime.audit.append('UPDATE_VORSCHAU', component='update', payload={'tag': tag, 'geaendert': len(p['dateien_geaendert']), 'rechte': len(p['rechte'])})
        return {'tag': tag, 'anzahl': p['anzahl'], 'geaendert': p['dateien_geaendert'], 'entfallen': p['dateien_entfallen'],
                'rechte': p['rechte'], 'rechte_schluessel': p['rechte_schluessel'], 'wirkt': 'nach dem Neustart von SEDRA'}

    def update_uebernehmen(self, payload=None):
        """POST /api/update/uebernehmen – übernimmt den vorbereiteten Stand. `rechte_schluessel` muss die Rechteliste aus der Vorschau bestätigen."""
        from .update_anwenden import MANIFEST, anwenden
        from .update_holen import TAG
        tag = str((payload or {}).get('tag') or '')
        if not TAG.match(tag):
            raise ValueError('tag_ungueltig')
        stand = INSTALLATION / 'local_config' / 'update' / 'staging' / tag
        if not (stand / MANIFEST).is_file():
            raise ValueError('update_nicht_vorbereitet')
        r = anwenden(stand, INSTALLATION, (stand / MANIFEST).read_text(encoding='utf-8'), str((payload or {}).get('rechte_schluessel') or ''), tag)
        self.runtime.audit.append('UPDATE_UEBERNOMMEN', component='update', payload={'tag': tag, 'geaendert': r['geaendert'], 'entfallen': r['entfallen']})
        return r

    def update_zurueck(self, payload=None):
        """POST /api/update/zurueck – stellt die letzte Sicherung wieder her. Wirkung nach dem Neustart."""
        from .update_anwenden import zurueck
        r = zurueck(INSTALLATION)
        self.runtime.audit.append('UPDATE_ZURUECKGESETZT', component='update', payload={'version': r['version']})
        return r

    def gateway_cloud(self):
        """Der Cloudweg des GateWay. `anbieter`: die eingeschalteten Cloud-Anbieter (config/cloud_providers.yaml, Schlüssel per Umgebungsvariable),
        `bereit`: die davon, deren Schlüssel gesetzt ist (health() liest nur den Schlüssel, kein Netzwerk). Ohne Anbieter ist es die Simulation."""
        adapters = [a for a in self.runtime.model_router.adapters.values() if getattr(a, 'route', 'local') == 'cloud']
        ready = [a.id for a in adapters if a.health()]
        return {'modus': 'anbieter' if adapters else 'simuliert', 'anbieter': [a.id for a in adapters], 'bereit': ready,
                'fehler': getattr(self.runtime, 'cloud_providers_error', None)}

    def gateway_list(self, payload=None):
        """GET /api/gateway/vorgaenge – die Vorgänge, die Vorgaben und die Textdateien des Projekts, die ein Vorgang mitnehmen darf."""
        from .gateway import klassen, wissen
        from .gateway.vorgang import LESBAR
        files = []
        project = self._active_project()
        if project:
            try:
                ws = self.runtime.filesystem_tool._resolve(project['workspace_path'], must_exist=True)
                for p in sorted(ws.rglob('*')):
                    if p.is_file() and p.suffix.lower() in LESBAR and '/.' not in p.as_posix()[len(ws.as_posix()):] and len(files) < 200:
                        files.append({'pfad': p.relative_to(ws).as_posix(), 'bytes': p.stat().st_size})
            except Exception:
                files = []
        # Das geladene Modell aus dem Serverstatus, nicht über choose(): choose() prüft jeden Anbieter mit Zeitlimit (2 s ohne Modell)
        try:
            server = getattr(self.runtime, 'llama_server', None)
            loaded = server.loaded_models() if server is not None else []
            model = (loaded[0].get('identifier') or loaded[0].get('modelKey')) if loaded else None
        except Exception:
            model = None
        # Hochgeladene Dateien (Eingang) stehen vor den Projektdateien; ihr Name ist der Schlüssel, unter dem sie geprüft werden
        eingang = [{'pfad': p.name, 'bytes': p.stat().st_size, 'eingang': True} for p in sorted(self.gateway_eingang().iterdir()) if p.is_file()]
        files = eingang + files
        return {'vorgaenge': self.gw.liste(), 'vorgaben': self.gw.vorgaben(), 'dateien': files, 'modell': model, 'zwecke': self.gw.zwecke(),
                'cloud': self.gateway_cloud(),
                'merkmale': [{'id': k, 'name': v[0], 'klasse': v[1], 'manuell': k in klassen.MANUELL} for k, v in klassen.MERKMALE.items()],
                'klassen': [{'id': k, 'name': klassen.KLASSE_WORT[k]} for k in klassen.KLASSEN],
                'regeln': [klassen.regel(r) for r in klassen.REGELN], 'policy_version': klassen.POLICY_VERSION, 'regelwerk': klassen.REGELWERK,
                'leitfaden': wissen.leitfaden(), 'schritt_von_zustand': dict(wissen.SCHRITT_VON_ZUSTAND),
                'nicht_im_mvp': ['Kein Versand – der Entwurf bleibt hier.',
                                 'Cloud nur über einen eingeschalteten Anbieter; ohne Anbieter bleibt es bei der Simulation. Personenbezug geht nie in die Cloud (R-01).',
                                 'Anhänge nur .md, .txt und .docx; PDF und .doc sind nicht dabei.', 'Keine Rollen: der Nutzer ist die Prüfung.',
                                 'MCP/Agenten nur dokumentiert, nicht angebunden.']}

    def gateway_get(self, vid):
        try:
            v = self.gw.get(vid)
        except Exception as exc:
            self._gw_error(exc)
        e = self.gw.entwurf(v.id)
        out = v.oeffentlich()
        out['entwurf'] = None if e is None else {'text': e.text, 'sha256': e.sha256, 'weg': e.weg, 'modell': e.modell, 'erstellt': e.erstellt,
                                                 'loeschen_am': e.loeschen_am, 'pruefung': e.pruefung, 'rechecks': e.rechecks,
                                                 'kennzeichnung': e.kennzeichnung or e.kennzeichnen()}
        out['freigabe_offen'] = v.mission_id if v.zustand == 'WARTET' else None
        return out

    def gateway_new(self, payload):
        try:
            v = self.gw.neu((payload or {}).get('titel'), (payload or {}).get('wunsch') or 'local')
        except Exception as exc:
            self._gw_error(exc)
        self.events.publish('tools.refresh', {})
        return self.gateway_get(v.id)

    def gateway_eingang(self):
        """Der Eingang des GateWay für Dateien, die der Nutzer hochlädt (ohne Projekt). Liegt unter local_config, nie in git."""
        folder = self.project_root / 'local_config' / 'gateway' / 'eingang'
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def gateway_upload(self, payload):
        """POST /api/gateway/upload {name, data} – eine Datei (.md, .txt, .docx, bis 2 MB, Base64) in den Eingang des GateWay legen.
        Nichts wird ausgeführt. Ist der Text nicht lesbar, wird die Datei sofort wieder entfernt."""
        import base64, binascii
        from .gateway.dokumente import lies_datei, DokumentFehler
        p = payload or {}
        name = Path(str(p.get('name') or '').strip()).name
        if not name or name.startswith('.') or Path(name).suffix.lower() not in ('.md', '.txt', '.docx'):
            raise ValueError('dateityp_nicht_erlaubt')
        try:
            raw = base64.b64decode(str(p.get('data') or ''), validate=True)
        except (binascii.Error, ValueError):
            raise ValueError('daten_ungueltig')
        if not raw or len(raw) > 2_000_000:
            raise ValueError('datei_zu_gross_oder_leer')
        target = self.gateway_eingang() / name
        target.write_bytes(raw)
        try:
            lies_datei(target)
        except DokumentFehler as exc:
            target.unlink(missing_ok=True)
            raise ValueError('dokument_nicht_lesbar:' + str(exc)[:80])
        self.runtime.audit.append('GW_DATEI_HOCHGELADEN', component='gateway', payload={'endung': target.suffix.lower(), 'bytes': len(raw)})
        return {'name': name, 'bytes': len(raw)}

    # ---- Vorschau und Ausgabe (Spezifikation Gateway, Abschnitt 3): nur das Original wird gelesen; die Ausgabe geht in den Ausgang
    GW_REGEL = {'ORT': 'O-1', 'ADDRESS': 'O-1', 'PERSON': 'R-01', 'COMPANY': 'R-01', 'EMAIL': 'R-01', 'PHONE': 'R-01',
                'CUSTOMER_ID': 'R-01', 'TERM': 'R-01'}

    def _gw_fundstellen(self, name):
        """(Dateiname, Text, Fundstellen) eines Originals im Eingang. Dieselbe Erkennung wie beim Prüfen (b6core)."""
        from .gateway import ablage
        from .gateway.dokumente import lies_datei, DokumentFehler
        from .core.b6core import pseudo
        from .core.b6core.normalize import normalize
        from .core.b6core.privacy import scan_text
        try:
            path = self.gateway_eingang() / ablage.sicherer_name(name)
        except ablage.AblageFehler as exc:
            raise ValueError(str(exc))
        if not path.is_file(): raise ValueError('original_nicht_gefunden')
        try: raw = lies_datei(path)
        except DokumentFehler as exc: raise ValueError('dokument_nicht_lesbar:' + str(exc)[:80])
        text = normalize(raw).clean
        spans = pseudo.collect_spans(text, scan_text('GW', text))
        # Gemerkte Vorgaben gelten vor den Regeln (Spezifikation 6b): jedes Vorkommen eines gemerkten Textes wird Fundstelle,
        # auch wenn die Regeln es übersehen. Überlappt eine Regel-Fundstelle, bleibt die Regel.
        import re as _re
        from .gateway import vorgaben_text as _vt
        try:
            gemerkt = _vt.laden(self.project_root)
        except _vt.VorgabeFehler:
            gemerkt = []
        for e in gemerkt:
            if not e.get('text'): continue
            for m in _re.finditer(_re.escape(e['text']), text, _re.IGNORECASE):
                a, b = m.start(), m.end()
                if any(a < sb and sa < b for sa, sb, _ in spans): continue
                spans.append((a, b, e.get('typ', 'TERM')))
        spans.sort()
        fund = [{'id': i, 'start': a, 'end': b, 'text': text[a:b], 'typ': t, 'regel': 'Vorgabe' if any(e.get('typ') == t and str(e.get('text', '')).casefold() == text[a:b].casefold() for e in gemerkt) else self.GW_REGEL.get(t, '')} for i, (a, b, t) in enumerate(spans)]
        return path.name, text, fund

    # ---- gemerkte Vorgaben (Spezifikation 5.3): global, Vorschlag statt stiller Ersetzung; das Audit nennt nie den Text
    def gateway_vorgaben_liste(self, payload=None):
        from .gateway import vorgaben_text as vt
        try:
            return {'vorgaben': vt.laden(self.project_root)}
        except vt.VorgabeFehler as exc:
            raise ValueError(str(exc))

    def gateway_vorgabe_merken(self, payload):
        from .gateway import vorgaben_text as vt
        p = payload or {}
        try:
            e = vt.merken(self.project_root, str(p.get('text') or ''), str(p.get('typ') or ''), str(p.get('art') or ''),
                          str(p.get('platzhalter') or ''))
        except vt.VorgabeFehler as exc:
            raise ValueError(str(exc))
        self.runtime.audit.append('GW_VORGABE_GEMERKT', component='gateway', payload={'typ': e['typ'], 'art': e['art']})
        return e

    def gateway_vorgabe_loeschen(self, payload):
        from .gateway import vorgaben_text as vt
        vid = str((payload or {}).get('id') or '')
        try:
            ok = vt.loeschen(self.project_root, vid)
        except vt.VorgabeFehler as exc:
            raise ValueError(str(exc))
        if not ok: raise ValueError('vorgabe_nicht_gefunden')
        self.runtime.audit.append('GW_VORGABE_GELOESCHT', component='gateway', payload={'id': vid})
        return {'status': 'geloescht', 'id': vid}

    def gateway_vorschau(self, payload):
        """POST /api/gateway/vorschau {name} – der Text des Originals mit allen Fundstellen. Nur lesen, kein Modell."""
        from .gateway import vorgaben_text as vt
        name, text, fund = self._gw_fundstellen(str((payload or {}).get('name') or ''))
        try:
            vorschlaege = vt.vorschlaege(vt.laden(self.project_root), fund)
        except vt.VorgabeFehler as exc:
            raise ValueError(str(exc))
        return {'name': name, 'text': text, 'fundstellen': fund, 'vorschlaege': vorschlaege}

    def gateway_ausgabe(self, payload):
        """POST /api/gateway/ausgabe {name, auswahl:[{id, art}], ziel} – gewählte Stellen ersetzen (art: ersetzen | behalten | entfernen),
        gleicher Text wird überall gleich ersetzt, und die Fassung geht in den Ausgang. Das Original bleibt unverändert."""
        from .gateway import ablage
        p = payload or {}
        name, text, fund = self._gw_fundstellen(str(p.get('name') or ''))
        by_id = {f['id']: f for f in fund}
        ersatz, nummern, vorgaben = {}, {}, []
        for sel in (p.get('auswahl') or []):
            try:
                f = by_id[int(sel.get('id'))]
            except (TypeError, ValueError, KeyError):
                raise ValueError('fundstelle_unbekannt')
            art = str(sel.get('art') or '')
            if art not in ('ersetzen', 'behalten', 'entfernen'): raise ValueError('vorgabe_unbekannt')
            key = (f['typ'], f['text'].casefold())
            if art == 'behalten':
                vorgaben.append({'art': 'behalten', 'typ': f['typ']}); continue
            if art == 'entfernen':
                repl = ''
            else:
                if key not in nummern:
                    nummern[key] = sum(1 for k in nummern if k[0] == f['typ']) + 1
                repl = '<%s_%03d>' % (f['typ'], nummern[key])
            vorgaben.append({'art': art, 'typ': f['typ'], 'platzhalter': repl})
            for g in fund:                                   # für alle gleichen Stellen im Dokument
                if (g['typ'], g['text'].casefold()) == key: ersatz[g['start']] = (g['end'], repl)
        out = text
        for a in sorted(ersatz, reverse=True):
            b, repl = ersatz[a]
            out = out[:a] + repl + out[b:]
        try:
            v = ablage.speichern_unter(self.project_root, name, out, str(p.get('ziel') or ''), vorgaben)
        except ablage.AblageFehler as exc:
            raise ValueError(str(exc))
        self.runtime.audit.append('GW_AUSGABE_GESPEICHERT', component='gateway',
                                  payload={'ziel': v['name'], 'original_sha256': v['original_sha256'], 'vorgaben': len(vorgaben)})
        return {'name': v['name'], 'ordner': 'Ausgang', 'vermerk': v}

    def gateway_arbeitskopie(self, payload):
        """POST /api/gateway/arbeitskopie {name} – eine Arbeitskopie des Originals (Original bleibt, bekommt einen Vermerk)."""
        from .gateway import ablage
        try:
            kopie = ablage.arbeitskopie(self.project_root, str((payload or {}).get('name') or ''))
        except ablage.AblageFehler as exc:
            raise ValueError(str(exc))
        self.runtime.audit.append('GW_ARBEITSKOPIE', component='gateway', payload={'endung': kopie.suffix.lower()})
        return {'name': kopie.name, 'ordner': 'Arbeitskopien'}

    def gateway_speichern_unter(self, payload):
        """POST /api/gateway/speichern-unter {quelle, ziel, text, vorgaben} – die bearbeitete Fassung in den Ausgang, mit Vermerk.
        Das Audit enthält Namen, Prüfsumme und die Art der Vorgaben, nie den Text."""
        from .gateway import ablage
        p = payload or {}
        try:
            v = ablage.speichern_unter(self.project_root, str(p.get('quelle') or ''), str(p.get('text') or ''),
                                       str(p.get('ziel') or ''), p.get('vorgaben') or [])
        except ablage.AblageFehler as exc:
            raise ValueError(str(exc))
        self.runtime.audit.append('GW_AUSGABE_GESPEICHERT', component='gateway',
                                  payload={'ziel': v['name'], 'original_sha256': v['original_sha256'], 'vorgaben': len(v['vorgaben'])})
        return {'name': v['name'], 'ordner': 'Ausgang', 'vermerk': v}

    def gateway_pruefen(self, payload):
        """POST /api/gateway/pruefen {id, anfrage, dokument?, wunsch?, manuell?, zweck?, verantwortlich?} – liest die Datei aus dem Projekt;
        nichts verlässt den Rechner. Zweck und verantwortliche Person (G-05) werden Teil der Bindung."""
        p = payload or {}
        vid = str(p.get('id') or '').strip()
        dokument = None
        name = str(p.get('dokument') or '').strip()
        if name:
            eingang = self.gateway_eingang()
            if Path(name).name == name and (eingang / name).is_file():
                path = eingang / name                 # eine hochgeladene Datei hat Vorrang vor dem Projekt
            else:
                project = self._active_project()
                if not project:
                    raise ValueError('no_project')
                ws = self.runtime.filesystem_tool._resolve(project['workspace_path'], must_exist=True)
                path = (ws / name)
                try:
                    if not path.resolve().is_relative_to(ws.resolve()) or not path.is_file():
                        raise ValueError('dokument_nicht_gefunden')
                except ValueError:
                    raise
                except Exception:
                    raise ValueError('dokument_nicht_gefunden')
            from .gateway.dokumente import lies_datei, DokumentFehler
            try:
                dokument = (name, lies_datei(path))
            except DokumentFehler:
                raise ValueError('dokument_nicht_lesbar')
        try:
            v = self.gw.get(vid)
            if p.get('wunsch') in ('local', 'cloud'):
                v.wunsch = p['wunsch']
            self.gw.pruefen(vid, p.get('anfrage'), dokument, manuell=[str(m) for m in (p.get('manuell') or [])],
                            zweck=(str(p['zweck']) if p.get('zweck') is not None else None),
                            verantwortlich=(str(p['verantwortlich']) if p.get('verantwortlich') is not None else None))
        except Exception as exc:
            self._gw_error(exc)
        return self.gateway_get(vid)

    def gateway_freigabe(self, payload):
        """POST /api/gateway/freigabe {id, weg} – legt das Gate vor: Bindung über Anfrage, Dokument, Policy, Klasse, Merkmale, Weg, Übergabeprompt,
        Zweck und verantwortliche Person (G-05)."""
        from .gateway import klassen
        from .gateway.vorgang import ZWECKE
        p = payload or {}
        vid, weg = str(p.get('id') or '').strip(), str(p.get('weg') or '').strip()
        try:
            v = self.gw.get(vid)
            binding_payload, binding = self.gw.bindung(vid, weg)
        except Exception as exc:
            self._gw_error(exc)
        e = v.einstufung
        review = e['review'] == 'PENDING'
        cloud = self.gateway_cloud()
        if weg != 'LOCAL_ONLY' and cloud['modus'] == 'anbieter' and not cloud['bereit']:
            # fail-closed: ein Cloudweg, dessen Anbieter keinen Schlüssel hat, wird gar nicht erst zur Freigabe vorgelegt
            raise ValueError('cloud_anbieter_nicht_bereit')
        describe = (f'Vorgang „{v.titel}“ freigeben: {klassen.WEG_WORT[weg]} · {e["klasse"]} {e["klasse_wort"]} · '
                    + (', '.join(m['id'] for m in e['merkmale']) or 'keine Merkmale') + ' · ' + e['policy_wort']
                    + f' · Zweck: {ZWECKE.get(v.zweck, v.zweck)} · verantwortlich: {v.verantwortlich}'
                    + (' – deine Prüfung (R1) ist die Freigabe' if review else ''))
        if weg == 'LOCAL_ONLY':
            cloud_risk = []
        elif cloud['modus'] == 'anbieter':
            cloud_risk = [f'Cloud-Anbieter {cloud["bereit"][0]}: der Übergabeprompt verlässt den Rechner (nach Inhaltsschutz und Regelwerk).']
        else:
            cloud_risk = ['Cloud ist simuliert (kein Anbieter eingeschaltet): nichts verlässt den Rechner.']
        risks = list(e['gruende'])[:4] + cloud_risk
        full = dict(binding_payload, describe=describe, binding=binding, vorgang_id=vid)
        with self.lock:
            m = self.runtime.brain.create_mission(describe[:160], None, 'S1')
            gate = self.runtime.guard.create_gate(m['identity']['mission_id'], self.GATEWAY_ACTION, f'gateway:{vid}', risks=risks,
                                                  rollback_available=True, request_binding=full)
            m['human_gates']['pending'].append(gate)
            m['context']['gateway_request'] = full
            self.runtime.missions.save(m)
        self.gw.vorgemerkt(vid, weg, m['identity']['mission_id'], binding)
        self.events.publish('decision.pending', {'id': 'request:' + m['identity']['mission_id'], 'kind': 'request:gateway', 'title': describe[:120],
                                                 'describe': describe, 'mission_id': m['identity']['mission_id'], 'gate_id': gate.get('gate_id')})
        return self._remember('gateway', {'mission_id': m['identity']['mission_id'], 'gate': gate, 'binding': full})

    def gateway_apply(self, payload):
        """Nach der Freigabe: der Aufruf – lokal oder über den Cloud-Anbieter, jeweils durch den Inhaltsschutz (Router). Ohne Anbieter
        bleibt es bei der Simulation. Mit Einmal-Token und Bindungsprüfung."""
        mission_id = str((payload or {}).get('mission_id') or '').strip()
        if not mission_id:
            raise ValueError('mission_id_required')
        rt = self.runtime
        with rt.missions.execution_lock(mission_id):
            m = rt.missions.load(mission_id)
            full = (m.get('context') or {}).get('gateway_request')
            token = (m.get('execution') or {}).get('approval_token')
            if not full:
                raise ValueError('not_a_gateway_request')
            if not token:
                raise ValueError('captain_approval_required')
            if not rt.guard.authorize(token, mission_id=mission_id, action=self.GATEWAY_ACTION, target=f"gateway:{full['vorgang_id']}",
                                      request_binding=full)['authorized']:
                raise ValueError('captain_approval_invalid')
            vid, weg = full['vorgang_id'], full['weg']
            model = None
            def complete_local(messages):
                nonlocal model
                out = rt.model_router.chat(mission_id, messages, slot_owner='captain-chat')
                model = out.get('model') or out.get('provider')
                return out.get('content') or ''
            cloud = self.gateway_cloud()
            complete_cloud = None
            if weg != 'LOCAL_ONLY' and cloud['modus'] == 'anbieter':
                # Der Anbieter, der bereit ist – sonst den ersten, damit der Router den Fehler sichtbar macht (kein stiller Rückfall)
                provider = (cloud['bereit'] or cloud['anbieter'])[0]
                def complete_cloud(messages):
                    nonlocal model
                    out = rt.model_router.chat(mission_id, messages, provider=provider)
                    model = f'{provider} · {out.get("model") or provider}'
                    return out.get('content') or ''
            try:
                e = self.gw.ausfuehren(vid, weg, full['binding'], complete_local, complete_cloud=complete_cloud)
            except Exception as exc:
                m['execution'].pop('approval_token', None)
                m['result'] = {'kind': 'gateway', 'status': 'fehler', 'grund': str(exc)[:200]}
                m['lifecycle']['status'] = 'closed'
                rt.missions.save(m)
                # Jeder Fehler des Aufrufs – auch ein Anbieterfehler oder ein Inhaltsschutz-Stopp – wird ein Vorgangsfehler mit Grund,
                # nicht eine rohe Ausnahme beim Aufrufer (vorher ging _gw_error hier durch und ließ alles Fremde unbehandelt).
                raise ValueError('gateway_fehler:' + str(exc)[:160]) from None
            if model and e.modell in ('lokales Modell', 'Cloud'):
                e.modell = (('Cloud · ' + str(model)) if e.modell == 'Cloud' else str(model))
                e.kennzeichnen(); self.gw._entwurf_speichern(e)
            m['execution'].pop('approval_token', None)
            m['result'] = {'kind': 'gateway', 'vorgang': vid, 'weg': weg, 'entwurf_sha256': e.sha256}
            m['lifecycle']['status'] = 'closed'
            rt.missions.save(m)
        self.events.publish('decision.answered', {'id': 'request:' + mission_id, 'kind': 'request:gateway', 'way': 'freigeben_und_anwenden'})
        self.events.publish('tools.refresh', {})
        return {'status': 'applied', **self.gateway_get(vid)}

    def gateway_pruefung(self, payload):
        p = payload or {}
        try:
            self.gw.pruefung(str(p.get('id') or ''), str(p.get('urteil') or ''))
        except Exception as exc:
            self._gw_error(exc)
        return self.gateway_get(str(p.get('id')))

    def gateway_verwerfen(self, payload):
        p = payload or {}
        vid = str(p.get('id') or '')
        try:
            v = self.gw.get(vid)
            if v.zustand == 'WARTET' and v.mission_id:
                try: self.reject_gate({'mission_id': v.mission_id, 'gate_id': None})
                except Exception: pass
            self.gw.verwerfen(vid)
        except Exception as exc:
            self._gw_error(exc)
        return self.gateway_get(vid)

    # ---- Schreibrouten freigeben (Captain-Entscheidung 15.10.2026, 02:12): ein fremdes Modul kommt als COMMUNITY mit Leserouten.
    # Schreiben darf es erst, wenn der Captain genau die Routen gesehen und freigegeben hat – ein Gate, kein Häkchen.
    TRUST_ACTION = 'grant_module_write_routes'

    def trust_request(self, payload):
        """Vorlegen: welche POST-Routen das Modul in seinem Manifest nennt. Erst nach der Freigabe wird das Vertrauen CAPTAIN."""
        kind = 'tools' if str((payload or {}).get('kind') or 'tool') == 'tool' else 'shells'
        mid = str((payload or {}).get('id') or '').strip()
        loaded = self.gateway.tools() if kind == 'tools' else self.gateway.shells()
        if mid not in loaded:
            raise ValueError('unknown_module')
        folder, man = loaded[mid]
        if man.get('origin') != 'local':
            raise ValueError('only_a_local_module_can_be_raised')
        if man.get('trust') != 'COMMUNITY':
            raise ValueError('module_is_not_community')
        name = 'tool.yaml' if kind == 'tools' else 'shell.yaml'
        doc = yaml.safe_load((folder / name).read_text(encoding='utf-8'))
        key = 'tool' if kind == 'tools' else 'shell'
        wanted = [r for r in (doc.get(key) or {}).get('api') or [] if isinstance(r, str) and not r.startswith('GET ')]
        if not wanted:
            raise ValueError('module_asks_for_no_write_route')
        own = man.get('own_types') or []
        describe = (f'„{man["name"]}“ ({mid}) darf schreiben: ' + ', '.join(wanted)
                    + (f' · eigene Objekttypen: {", ".join(own)}' if own else ''))
        binding = {'kind': kind, 'id': mid, 'routes': wanted, 'manifest_sha256': desk_install.sha256(folder / name), 'describe': describe}
        with self.lock:
            m = self.runtime.brain.create_mission(describe[:160], None, 'S1')
            gate = self.runtime.guard.create_gate(m['identity']['mission_id'], self.TRUST_ACTION, f'{kind}:{mid}',
                                                  risks=['fremder Code schreibt danach über diese Routen in die Runtime'] + wanted,
                                                  rollback_available=True, request_binding=binding)
            m['human_gates']['pending'].append(gate)
            m['context']['trust_request'] = binding
            self.runtime.missions.save(m)
        return self._remember('trust', {'mission_id': m['identity']['mission_id'], 'gate': gate, 'binding': binding})

    def trust_apply(self, payload):
        """Nach der Freigabe: das Manifest auf CAPTAIN setzen – nur, wenn es noch dasselbe ist wie im Gate."""
        mission_id = str((payload or {}).get('mission_id') or '').strip()
        if not mission_id:
            raise ValueError('mission_id_required')
        rt = self.runtime
        with rt.missions.execution_lock(mission_id):
            m = rt.missions.load(mission_id)
            binding = (m.get('context') or {}).get('trust_request')
            token = (m.get('execution') or {}).get('approval_token')
            if not binding:
                raise ValueError('not_a_trust_request')
            if not token:
                raise ValueError('captain_approval_required')
            if not rt.guard.authorize(token, mission_id=mission_id, action=self.TRUST_ACTION,
                                      target=f"{binding['kind']}:{binding['id']}", request_binding=binding)['authorized']:
                raise ValueError('captain_approval_invalid')
            folder = self.project_root / 'local_config' / binding['kind'] / binding['id']
            name = 'tool.yaml' if binding['kind'] == 'tools' else 'shell.yaml'
            if not (folder / name).is_file() or desk_install.sha256(folder / name) != binding['manifest_sha256']:
                raise ValueError('manifest_changed_since_the_request')     # was freigegeben wurde, ist nicht mehr da
            doc = yaml.safe_load((folder / name).read_text(encoding='utf-8'))
            key = 'tool' if binding['kind'] == 'tools' else 'shell'
            doc[key]['trust'] = 'CAPTAIN'
            tmp = folder / (name + '.tmp')
            tmp.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding='utf-8')
            tmp.replace(folder / name)
            m['execution'].pop('approval_token', None)
            m['result'] = {'kind': 'trust', 'id': binding['id'], 'routes': binding['routes']}
            m['lifecycle']['status'] = 'closed'
            rt.missions.save(m)
            rt.audit.append('UIX_MODULE_WRITE_ROUTES_GRANTED', component='desk', mission_id=mission_id,
                            payload={'kind': binding['kind'], 'id': binding['id'], 'routes': binding['routes']})
        self.events.publish('tools.refresh', {})
        return {'status': 'granted', 'id': binding['id'], 'routes': binding['routes'],
                'note': 'Das Modul darf jetzt über diese Routen schreiben – beim nächsten Laden der Seite.'}

    def install_remove(self, payload):
        """Entfernen ist kein Gate (§6), nur Audit – was weg ist, kann nichts mehr tun."""
        kind = 'tools' if str(payload.get('kind') or 'tool') == 'tool' else 'shells'
        mid = str(payload.get('id') or '').strip()
        if not re.fullmatch(r'[a-z0-9-]{2,40}', mid):
            raise ValueError('id_invalid')
        folder = self.project_root / 'local_config' / kind / mid
        if not folder.is_dir():
            raise ValueError('module_not_installed')
        if folder.is_symlink():                      # eine Verknüpfung wird gelöst, nicht ihr Ziel ausgeräumt
            raise ValueError('module_folder_is_a_symlink')
        if kind == 'shells' and mid == self.gateway.registry.config()['shell']:
            raise ValueError('shell_is_active')      # erst eine andere nehmen – sonst steht die Seite beim nächsten Laden leer
        shutil.rmtree(folder)
        self.runtime.audit.append('UIX_MODULE_REMOVED', component='desk', payload={'kind': kind, 'id': mid})
        self.events.publish('tools.refresh', {})
        return {'status': 'removed', 'id': mid}

    # ---- Build 9: Modus und die vier Grenzen je Projekt (COCKPIT_MODUL_v1 §3, Regel 7)
    BOUNDARY_ACTION = 'set_project_boundaries'
    ONCE_SECONDS = 600            # eine Einmal-Erlaubnis gilt zehn Minuten – danach wird wieder gefragt
    MAX_OPEN_CROSSINGS = 50       # offene Grenzfragen; mehr heißt, dass etwas im Kreis läuft

    @property
    def boundaries(self):
        store = self.__dict__.get('_boundaries')
        if store is None:
            store = self.__dict__['_boundaries'] = desk_boundaries.Store(self.project_root)
        return store

    def _active_project(self, project_id=None):
        """Das Projekt, um das es geht: das genannte, sonst das einzige, sonst das zuletzt angelegte."""
        projects = self.projects.list()
        if project_id:
            return next((p for p in projects if p.get('project_id') == project_id), None)
        return projects[-1] if projects else None

    def _most_expensive_task(self):
        """Die bisher teuerste Aufgabe in Token – daraus kommt die vorläufige Kostengrenze, bis gemessen ist."""
        manager = getattr(self.runtime, 'context_manager', None)
        if manager is None:
            return None
        most = 0
        for m in self.missions():
            try:
                summary = manager.metrics.summary(m['mission_id'])
            except Exception:
                continue
            most = max(most, (summary.get('input_tokens') or 0) + (summary.get('output_tokens') or 0))
        return most or None

    def boundaries_view(self, payload=None):
        """Modus und Grenzen dieses Projekts – oder der Vorschlag, wenn noch nichts bestätigt ist (§3: kein Standard im Code)."""
        project = self._active_project((payload or {}).get('project_id'))
        if project is None:
            return {'project_id': None, 'confirmed': False, 'note': 'Noch kein Projekt angelegt – Grenzen gehören zu einem Projekt.'}
        pid = project['project_id']
        current = self.boundaries.get(pid)
        measured = desk_boundaries.measured_limit(self._most_expensive_task())
        if current:
            return {'project_id': pid, 'name': project.get('name'), 'confirmed': True, 'mode': current['mode'],
                    'boundaries': current['boundaries'], 'confirmed_at': current.get('confirmed_at'),
                    'sentence': desk_boundaries.sentence(current['mode'], current['boundaries']),
                    'measured_limit': measured,
                    'note': None if measured else 'Die Kostengrenze wird gemessen, nicht geraten – zwei Wochen Guppy-Meter.'}
        try:
            path = self.runtime.filesystem_tool._resolve(project['workspace_path'], must_exist=True)
        except Exception:
            path = Path(project.get('workspace_path') or '.')
        proposal = desk_boundaries.propose(desk_boundaries.look_at(path))
        return {'project_id': pid, 'name': project.get('name'), 'confirmed': False, 'mode': proposal['mode'],
                'boundaries': proposal['boundaries'], 'reason': proposal['reason'], 'measured_limit': measured,
                'sentence': desk_boundaries.sentence(proposal['mode'], proposal['boundaries']),
                'note': 'Noch nicht bestätigt: bis du einmal zustimmst, läuft nichts, was eine Grenze berührt.'}

    def boundaries_request(self, payload):
        """Modus und Grenzen festlegen – immer über ein Gate, auch beim ersten Mal (§3: der Captain bestätigt einmal)."""
        view = self.boundaries_view(payload)
        if not view.get('project_id'):
            raise ValueError('no_project')
        mode = str(payload.get('mode') or view['mode'])
        values = desk_boundaries.check_values(mode, payload.get('boundaries') or view['boundaries'])
        pid = view['project_id']
        describe = ('Modus und Grenzen für „' + str(view.get('name') or pid) + '“ festlegen: '
                    + desk_boundaries.sentence(mode, values))
        binding = {'project_id': pid, 'mode': mode, 'boundaries': values, 'describe': describe,
                   'old': (self.boundaries.get(pid) or {}).get('mode')}
        with self.lock:
            m = self.runtime.brain.create_mission(describe[:160], None, 'S1')
            gate = self.runtime.guard.create_gate(m['identity']['mission_id'], self.BOUNDARY_ACTION, f'project:{pid}',
                                                  risks=['gilt für alles, was in diesem Projekt passiert'],
                                                  rollback_available=True, request_binding=binding)
            m['human_gates']['pending'].append(gate)
            m['context']['boundaries_request'] = binding
            self.runtime.missions.save(m)
        return self._remember('boundaries', {'mission_id': m['identity']['mission_id'], 'gate': gate, 'binding': binding})

    def boundaries_apply(self, payload):
        """Nach der Freigabe: schreiben, mit derselben Prüfung des Einmal-Tokens wie bei den Schaltern."""
        mission_id = str(payload.get('mission_id') or '').strip()
        if not mission_id:
            raise ValueError('mission_id_required')
        rt = self.runtime
        with rt.missions.execution_lock(mission_id):
            m = rt.missions.load(mission_id)
            binding = (m.get('context') or {}).get('boundaries_request')
            token = (m.get('execution') or {}).get('approval_token')
            if not binding:
                raise ValueError('not_a_boundaries_request')
            if not token:
                raise ValueError('captain_approval_required')
            if not rt.guard.authorize(token, mission_id=mission_id, action=self.BOUNDARY_ACTION,
                                      target=f"project:{binding['project_id']}", request_binding=binding)['authorized']:
                raise ValueError('captain_approval_invalid')
            saved = self.boundaries.put(binding['project_id'], binding['mode'], binding['boundaries'], utcnow())
            m['execution'].pop('approval_token', None)
            m['result'] = {'kind': 'boundaries', **saved}
            m['lifecycle']['status'] = 'closed'
            rt.missions.save(m)
            rt.audit.append('PROJECT_BOUNDARIES_SET', component='desk', mission_id=mission_id,
                            payload={'project_id': binding['project_id'], 'mode': binding['mode'], 'boundaries': binding['boundaries']})
        self.events.publish('decision.answered', {'id': 'request:' + mission_id, 'kind': 'request:boundaries', 'way': 'freigeben_und_anwenden'})
        self.sync_guard_mode()                                   # Build 16: der neue Modus ist sofort die Schärfe des Inhaltsschutzes
        return {'status': 'applied', **saved}

    def _open_crossings(self):
        return list(self.__dict__.setdefault('open_crossings', {}).values())

    def cross_boundary(self, kind, what, project_id=None, amount=None):
        """Eine Handlung berührt eine Grenze. Ergebnis: 'frei', oder eine Entscheidung, die an der Werkbank wartet (Regel 7).

        Eine Einmal-Erlaubnis gilt für genau diese eine Handlung und wird beim Verbrauch gelöscht – wie der Einmal-Token des Guard."""
        view = self.boundaries_view({'project_id': project_id} if project_id else None)
        if not view.get('project_id'):
            return {'verdict': 'frei', 'note': 'ohne Projekt gibt es keine Grenze'}
        pid = view['project_id']
        once = self.__dict__.setdefault('boundary_once', {})
        key = f'{pid}:{kind}:{what}'
        granted = once.pop(key, None)
        if granted is not None:
            # Härtung: eine Einmal-Erlaubnis, die liegen bleibt, ist nach ONCE_SECONDS keine mehr. Sonst gilt ein „ja“ von
            # heute früh noch am Abend für eine Handlung, an die beim Zustimmen niemand mehr denkt.
            if time.time() - granted <= self.ONCE_SECONDS:
                self.runtime.audit.append('BOUNDARY_PASSED_ONCE', component='desk', payload={'project_id': pid, 'boundary': kind, 'what': str(what)[:120]})
                return {'verdict': 'frei', 'once': True}
            self.runtime.audit.append('BOUNDARY_ONCE_EXPIRED', component='desk',
                                      payload={'project_id': pid, 'boundary': kind, 'what': str(what)[:120],
                                               'after_seconds': int(time.time() - granted)})
        if not view['confirmed']:
            return {'verdict': 'unbestätigt', 'decision': None,
                    'note': 'Für dieses Projekt sind Modus und Grenzen noch nicht bestätigt – das ist der erste Schritt.'}
        crossing = desk_boundaries.crossing(pid, kind, what, view['boundaries'], amount)
        if crossing is None:
            return {'verdict': 'frei'}
        open_now = self.__dict__.setdefault('open_crossings', {})
        # Härtung: dieselbe Handlung ist eine Entscheidung, nicht zehn. Fragt ein Werkzeug in einer Schleife, wächst weder
        # die Liste des Captains noch der Speicher – er sieht einmal, worum es geht.
        same = next((c for c in open_now.values()
                     if c['project_id'] == pid and c['boundary'] == kind and c['describe'] == crossing['describe']), None)
        if same is not None:
            return {'verdict': same['verdict'], 'decision': same, 'again': True}
        if len(open_now) >= self.MAX_OPEN_CROSSINGS:
            raise ValueError('too_many_open_boundary_decisions')
        open_now[crossing['id']] = crossing
        self.runtime.audit.append('BOUNDARY_CROSSED', component='desk',
                                  payload={'project_id': pid, 'boundary': kind, 'what': str(what)[:120], 'verdict': crossing['verdict']})
        self.events.publish('decision.pending', {'id': crossing['id'], 'kind': 'boundary', 'title': crossing['title'],
                                                 'describe': crossing['describe'], 'mission_id': None, 'gate_id': None})
        return {'verdict': crossing['verdict'], 'decision': crossing}

    def _answer_crossing(self, crossing, way):
        """Die drei Wege an der Grenze. `aendern` beantwortet die Entscheidung nicht – es öffnet die, die darüber entscheidet."""
        self.open_crossings.pop(crossing['id'], None)
        if way == 'einmal':
            self.__dict__.setdefault('boundary_once', {})[f"{crossing['project_id']}:{crossing['boundary']}:{crossing['describe']}"] = time.time()
            self.runtime.audit.append('BOUNDARY_OPENED_ONCE', component='desk',
                                      payload={'project_id': crossing['project_id'], 'boundary': crossing['boundary'], 'what': crossing['describe'][:120]})
            return {'status': 'answered', 'id': crossing['id'], 'way': way,
                    'result': {'note': 'Einmal geöffnet – die Handlung kann jetzt genau einmal laufen.'}}
        if way == 'aendern':
            self.runtime.audit.append('BOUNDARY_CHANGE_REQUESTED', component='desk',
                                      payload={'project_id': crossing['project_id'], 'boundary': crossing['boundary']})
            return {'status': 'answered', 'id': crossing['id'], 'way': way,
                    'result': {'open': {'type': 'boundary', 'id': crossing['project_id'], 'title': 'Modus und Grenzen'},
                               'note': 'Die Grenze ändert der Captain – die Änderung selbst ist wieder eine Freigabe.'}}
        self.runtime.audit.append('BOUNDARY_REFUSED', component='desk',
                                  payload={'project_id': crossing['project_id'], 'boundary': crossing['boundary'], 'what': crossing['describe'][:120]})
        return {'status': 'answered', 'id': crossing['id'], 'way': 'ablehnen', 'result': {'note': 'Abgelehnt. Nichts ist passiert.'}}

    # ---- Build 8: ein Objektmodell, Verben statt Routen, Live-Zeilen
    def object_view(self, kind, oid):
        """Ein Objekt in der einen Form (§10.1); welcher Typ was liest, steht im Register (desk/builtin_kinds.py, Erweiterungen)."""
        return self.kinds.view(self, kind, oid)

    def objects_view(self, payload):
        """`POST /api/objects {type, id}` für ein Objekt, ohne `id` die Liste des Typs."""
        return self.kinds.request(self, payload)

    def act(self, payload, client='shell'):
        """`POST /api/actions {type, id, verb, args}` (§10.2): ein Weg für dieselbe Handlung aus Gespräch, Werkzeug und Palette.
        Die Gates darunter bleiben, wie sie sind – `run` ruft genau die Hub-Methoden, die auch die alten Routen rufen.
        `client` setzt der Server aus dem Token (Spec 0, D2), nie der Aufrufer; es steht nur im Audit."""
        kind = str(payload.get('type') or '').strip()
        oid = str(payload.get('id') or '').strip()
        verb = str(payload.get('verb') or '').strip()
        if oid:
            out = desk_actions.run(self, kind, oid, verb, payload.get('args') or {})
        else:                                           # ein Verb ohne Objekt („anlegen“) nur, wenn der Typ es hat; sonst id_required
            out = desk_actions.run_type(self, kind, verb, payload.get('args') or {})
        self.runtime.audit.append('UIX_ACTION', component='desk', payload={'type': kind, 'id': oid[:60], 'verb': verb, 'client': client})
        return out

    def live_view(self, payload):
        """Die Live-Zeilen einer Aufgabe; `since` liefert nur das Neue (der Strom schickt dasselbe von sich aus)."""
        mid = str(payload.get('task_id') or payload.get('id') or '').strip()
        if not mid:
            raise ValueError('task_id_required')
        try:
            mission = self.runtime.missions.load(mid)
        except Exception:
            return {'task_id': mid, 'lines': [], 'total': 0, 'note': 'Diese Aufgabe gibt es nicht mehr.'}
        all_lines = desk_live.lines(mission, self.audit_view()['events'])
        since = payload.get('since') or 0
        if type(since) is not int or since < 0:
            raise ValueError('since_must_be_a_number')
        return {'task_id': mid, 'lines': desk_live.tail(all_lines, since, limit=200), 'total': len(all_lines)}

    DIFF_BYTES = 64_000

    def _candidate_report(self, mid):
        """Der Bericht, den die Kandidatenvorbereitung selbst geschrieben hat (`candidate-report.json`): Diff, statische Prüfungen,
        Teststand, Unveränderlichkeit. Er ist die Quelle – die Oberfläche denkt sich nichts dazu."""
        path = self.runtime.control.workspace / mid / 'candidate-report.json'
        if not path.is_file():
            return None
        try:
            return load_json(path)
        except Exception:
            return None

    QUALIFICATION_WORDS = {
        'PREPARED_NOT_TESTED': 'vorbereitet, noch nicht getestet – die Tests liefen nicht, der Diff ist geprüft',
        'TESTED_IN_VM': 'in der Entwicklungsumgebung getestet',
        'TESTED_ON_HOST': 'auf diesem Rechner getestet (nicht isoliert)',
        'FAILED': 'die Prüfung ist fehlgeschlagen',
    }

    def candidate_report(self, payload):
        """Was über diesen Kandidaten nachgewiesen ist – für die Spalte „Nachweise“ (Cockpit-Regel 5)."""
        mid = str(payload.get('mission_id') or payload.get('id') or '').strip()
        if not mid:
            raise ValueError('mission_id_required')
        report = self._candidate_report(mid)
        if report is None:
            return {'mission_id': mid, 'exists': False,
                    'note': 'Für diese Aufgabe gibt es keinen Kandidatenbericht; sie ändert keine Dateien.'}
        precheck = report.get('sandbox_precheck') or {}
        return {'mission_id': mid, 'exists': True,
                'qualification': report.get('qualification'),
                'qualification_text': self.QUALIFICATION_WORDS.get(report.get('qualification'), str(report.get('qualification') or '')),
                'ready_for_merge': bool(report.get('ready_for_merge')),
                'tests_executed': bool(report.get('tests_executed')),
                'host_code_executed': bool(report.get('host_code_executed')),
                'source_modified': bool(report.get('source_modified')),
                'static_checks': [c for c in (report.get('static_checks') or []) if isinstance(c, dict)][:50],
                'files': report.get('candidate_files') or [],
                'execution_ready': bool(precheck.get('execution_ready')) if precheck else None,
                'blockers': (precheck.get('blockers') or []) if precheck else [],
                'commands': ((report.get('sandbox_plan') or {}).get('request') or {}).get('commands') or [],
                'created_at': report.get('created_at')}

    def candidate_diff(self, payload):
        """Alter und neuer Text der Dateien, die ein Kandidat ändern will – nur lesen, nichts vorbereiten.

        Die Übernahme-Vorschau (`candidate_acceptance.preview`) ist der genaue Weg, aber sie ist ein Schritt im Übernahmeweg und
        lehnt ab, sobald eine Übernahme läuft. Zum Ansehen genügt, was in der Mission gebunden steht (der neue Inhalt mit dem
        erwarteten Hash der alten Datei) plus die Datei, wie sie jetzt auf der Platte liegt."""
        mid = str(payload.get('mission_id') or payload.get('id') or '').strip()
        if not mid:
            raise ValueError('mission_id_required')
        mission = self.runtime.missions.load(mid)
        binding = (((mission.get('plan') or {}).get('steps') or [{}])[0] or {}).get('binding') or {}
        inputs = binding.get('inputs') or {}
        root = inputs.get('project_path') or ''
        files = []
        for change in (inputs.get('changes') or [])[:12]:
            path = (root + '/' + change['path']) if root else change['path']
            before, note = '', None
            try:
                source = self.runtime.filesystem_tool._resolve(path, must_exist=True)
                if self.runtime.guard.evaluate('read_project_file', mission_id=mid, target=str(source))['decision'] != 'ALLOW':
                    note = 'Die alte Fassung darf hier nicht gelesen werden; der Diff zeigt nur den neuen Text.'
                else:
                    raw = source.read_bytes()[:self.DIFF_BYTES]
                    before = raw.decode('utf-8', 'replace')
                    if change.get('expected_sha256') and hashlib.sha256(source.read_bytes()).hexdigest() != change['expected_sha256']:
                        note = 'Achtung: die Datei auf der Platte stimmt nicht mehr mit dem Stand überein, auf den sich der Kandidat bezieht.'
            except Exception as exc:
                note = f'Alte Fassung nicht lesbar ({type(exc).__name__}) – wahrscheinlich eine neue Datei.'
            files.append({'path': change['path'], 'before': before, 'after': str(change.get('content') or '')[:self.DIFF_BYTES], 'note': note})
        acceptance = (mission.get('execution') or {}).get('candidate_acceptance') or {}
        report = self._candidate_report(mid) or {}
        return {'mission_id': mid, 'files': files, 'unified': [d for d in (report.get('diff') or []) if isinstance(d, str)][:12],
                'state': acceptance.get('status') or ('vorgeschlagen' if files else 'keiner')}

    def cost_view(self, payload):
        """Was eine Aufgabe gekostet hat (Cockpit-Regel 5, „Münzloch“).

        Die Zahlen stehen schon da: der Control Master meldet jeden Modellaufruf an den Kontext-Manager, und der verbucht ihn unter
        der Missions-ID. Was der Anbieter gemeldet hat, ist exakt; was geschätzt wurde, sagt das Feld `quellen` – geschätzt und
        gemessen werden hier nie vermischt."""
        mid = str(payload.get('task_id') or payload.get('id') or '').strip()
        if not mid:
            raise ValueError('task_id_required')
        manager = getattr(self.runtime, 'context_manager', None)
        summary = None
        if manager is not None:
            try:
                summary = manager.metrics.summary(mid)
            except Exception:
                summary = None
        if summary and not summary.get('attempts'):
            summary = None
        out = {'task_id': mid, 'attempts': (summary or {}).get('attempts', 0),
               'input_tokens': (summary or {}).get('input_tokens') or 0,
               'output_tokens': (summary or {}).get('output_tokens') or 0,
               'quellen': (summary or {}).get('usage_sources') or [],
               'peak_fill': (summary or {}).get('peak_fill')}
        out['tokens'] = (out['input_tokens'] or 0) + (out['output_tokens'] or 0)
        if summary is None:
            out['note'] = 'Für diese Aufgabe ist noch kein Modellaufruf verbucht – entweder lief keiner, oder der Kontext-Manager ist aus.'
        try:
            meter = self.meter_view()
            today = ((meter.get('tokens') or {}).get('ranges') or {}).get('today') or {}
            out['today'] = {'tokens': today.get('tokens') or 0, 'runs': today.get('runs') or 0}
        except Exception:
            out['today'] = None
        return out

    def _live_signatures(self):
        """Wie viele Zeilen jede laufende Aufgabe hat – mehr braucht der Strom nicht, um das Neue zu erkennen."""
        out = {}
        for m in self.missions():
            if m.get('status') != 'active':
                continue
            try:
                mission = self.runtime.missions.load(m['mission_id'])
            except Exception:
                continue
            out[m['mission_id']] = desk_live.signature(desk_live.lines(mission))
        return out

    def desk_snapshot(self):
        """What the event stream compares (desk/events.py). Cheap: the views it reads are the ones the routes already read.
        Die Erweiterungen legen ihre Felder bei (Spec 4, D4.3.2); einen eingebauten Schlüssel überschreiben sie nicht."""
        models = self.models_view()
        server = models.get('server') or {}
        slots = self.slots_view()
        return {**desk_extensions.snapshot(self, self.extensions), **({'slots': slots} if slots is not None else {}), 'missions': self.missions(), 'decisions': self.decisions_view()['items'],
                'model': {'running': bool(server.get('running')), 'model': server.get('model'), 'context': server.get('context')},
                'live': self._live_signatures(),
                'state': 'READY' if self.runtime.observability.overall() == 'HEALTHY' else 'SAFE_MODE'}

    def slots_view(self):
        """Slots, occupancy and queue for the desk (Spec 2, D2.9; shape: Spec 4 D4.2.4): `ModelScheduler.view()` plus the task titles, or None
        when the scheduler is off (the field is then missing and Shell D shows its interim state). Never raises."""
        sched = self._scheduler()
        if sched is None: return None
        view = sched.view()
        if view.get('error'): return None
        orch = getattr(self.runtime, 'orchestra', None)
        def titel(task_id):
            try: return (orch.issue(task_id) or {}).get('title') if orch is not None and task_id else None
            except Exception: return None
        view['belegt'] = [dict(b, titel=titel(b.get('task_id'))) for b in view.get('belegt') or []]
        return view

    def scheduler_poll(self):
        """One scheduler step per tick of the desk poller (D2.7: no service of its own): a crashed server, a waiting benchmark. Never raises."""
        sched = self._scheduler()
        if sched is None: return
        try: sched.poll()
        except Exception as exc: self.runtime.audit.append('SLOT_POLL_FAILED', component='uix', payload={'error': type(exc).__name__})

    def _slots_gauge(self):
        view = self.slots_view()
        if view is None: return None
        total, held, queue = view.get('gesamt') or 0, len(view.get('belegt') or []), len(view.get('schlange') or [])
        server = (view.get('server') or {}).get('state')
        hint = f"{queue} wartet" if queue else ('Modellserver ' + str(server) if server not in (None, 'bereit') else 'frei')
        tone = 'warn' if view.get('warnung') or server in ('gesperrt', 'drain', 'exklusiv') else ('ok' if total else 'off')
        return {'value': f'{held}/{total}', 'hint': hint, 'tone': tone}

    def _mode_gauge(self):
        """Das Instrument „Modus“ (Regel 7): der Modus dieses Projekts und die vier Grenzen in Worten – oder der Hinweis,
        dass noch nichts bestätigt ist. Es behauptet nichts, was nicht gilt."""
        try:
            view = self.boundaries_view()
        except Exception as exc:
            return {'value': '–', 'hint': f'Grenzen nicht lesbar ({type(exc).__name__})', 'tone': 'warn'}
        if not view.get('project_id'):
            return {'value': '–', 'hint': 'kein Projekt', 'tone': 'off'}
        values = view['boundaries']
        short = ' · '.join(f"{desk_boundaries.KIND_WORD[k]}: {values[k] if not isinstance(values[k], int) else str(values[k]) + ' Token'}" for k in desk_boundaries.KINDS)
        if not view['confirmed']:
            return {'value': 'nicht bestätigt', 'hint': 'Vorschlag: ' + view['mode'] + ' · ' + short, 'tone': 'warn'}
        return {'value': view['mode'].capitalize(), 'hint': short, 'tone': 'off'}

    def strip_view(self):
        """The instruments of the Cockpit strip in one call: state, model, GPU, decisions, tasks, mode and boundaries."""
        snap = self.desk_snapshot()
        models = self.models_view()
        hw = self.runtime.hardware.to_dict()
        lease = models.get('lease')
        running = [m for m in snap['missions'] if m.get('offen', m.get('status') == 'active' and (m.get('phase') or '') not in ('COMPLETE', 'FAILED'))]
        waiting = [m for m in running if (m.get('pending_gates') or 0)]          # Stufe 6: Anträge warten im Posteingang, nicht hier
        loaded = next((r for r in models['recipes'] if r.get('loaded')), None)
        return {'state': {'value': snap['state'],
                          'hint': f"{len(self.runtime.registry.skills)} Fähigkeiten · Audit " + ('intakt' if self.audit_view()['chain_ok'] else 'prüfen'),
                          'tone': 'ok' if snap['state'] == 'READY' else 'warn'},
                'model': {'value': (loaded or {}).get('id') or snap['model'].get('model') or 'keins geladen',
                          'hint': ('Kontext ' + str(snap['model'].get('context')) if snap['model'].get('context') else 'Werkstatt öffnet die Modelle'),
                          'tone': 'ok' if snap['model'].get('running') else 'off'},
                'gpu': {'value': (f"{hw.get('vram_gb')} GB" if hw.get('vram_gb') else '–'), 'hint': (hw.get('gpu_name') or 'keine GPU erkannt')
                        + (' · Sperre ' + ('belegt: ' + str(lease.get('purpose'))[:40] if lease else 'frei')), 'tone': 'warn' if lease and not lease.get('mine') else 'off'},
                'decisions': {'value': len(snap['decisions']), 'hint': (snap['decisions'][0]['title'][:48] if snap['decisions'] else 'nichts wartet'),
                              'tone': 'warn' if snap['decisions'] else 'ok'},
                'tasks': {'value': len(running),
                          'hint': f"{len(running)} {'läuft' if len(running) == 1 else 'laufen'} · {len(waiting)} {'wartet' if len(waiting) == 1 else 'warten'} auf dich",
                          'tone': 'warn' if waiting else 'off'},
                'cloud': self._cloud_gauge(),
                'mode': self._mode_gauge(),
                **({'slots': gauge} if (gauge := self._slots_gauge()) is not None else {}),
                **({'wissen': zelle} if (zelle := self._wissen_gauge()) is not None else {})}

    def _wissen_gauge(self):
        """SPEC_SHELL_WISSEN_v1 §4.3: Modus, Abdeckung und offene Vorschläge; ohne Schalter `wissen` keine Zelle (das Instrument sagt „aus“)."""
        from .wissen import desk_basis
        try:
            return desk_basis.strip_zelle(getattr(self.runtime, 'wissen', None))
        except Exception:
            return None

    def _cloud_gauge(self):
        """Die Online-KI in der Leiste: bereit (Schlüssel gesetzt), Schlüssel fehlt, oder kein Anbieter eingeschaltet."""
        c = self.gateway_cloud()
        if c['bereit']:
            return {'value': 'Cloud · ' + c['bereit'][0], 'hint': 'Anbieter bereit · Klick schaltet die Gesprächsauswahl', 'tone': 'ok'}
        if c['anbieter']:
            return {'value': 'Cloud · ohne Schlüssel', 'hint': 'Anbieter ' + c['anbieter'][0] + ' braucht einen Schlüssel', 'tone': 'warn'}
        return {'value': 'Cloud · aus', 'hint': 'kein Anbieter eingeschaltet', 'tone': 'off'}

    def route(self, payload):
        return self.runtime.capability_router.route(
            payload.get('intent', ''),
            payload.get('objective'),
            payload.get('mission_class', 'S1'),
            payload.get('topic'),
        )

    def create_chat_mission(self, payload):
        intent = str(payload.get('intent') or '').strip()
        if not intent:
            raise ValueError('intent_required')
        mission_class = payload.get('mission_class', 'S1')
        objective = payload.get('objective')
        with self.lock:
            project=self.projects.get(payload['project_id']) if payload.get('project_id') else None
            m = self.runtime.brain.create_mission(intent, objective, mission_class)
            if project:
                m['context']['refs'].append({'project_id':project['project_id'],'workspace_path':project['workspace_path']})
                self.runtime.missions.save(m)
            # Advance only through UNDERSTAND and PLAN. No execution happens here.
            m = self.runtime.brain.run(m['identity']['mission_id'], max_steps=3)
        return {
            'mission': _compact_mission(m),
            'full_phase': m.get('lifecycle', {}),
            'route': ((m.get('routing') or {}).get('route') or {}),
            'plan': m.get('plan', {}),
            'message': 'Mission vorbereitet. Noch keine Ausführung gestartet.',
        }

    CHAT_SYSTEM = ('Du bist SEDRA, der Assistent des Captains. Antworte kurz und auf Deutsch, in einfachem Text. '
                   'Du bewegst dich in der Oberfläche über deine Werkzeuge: Fenster öffnen (open_place, open_object), nachsehen, was mit '
                   'einem Objekt geht (list_actions), und Handlungen vorschlagen (propose_action, propose_intent). Was du vorschlägst, '
                   'bekommt der Captain als Knopf; erst sein Klick führt es aus, und was eine Freigabe braucht, läuft danach über die '
                   'Entscheidungen. Du änderst keine Dateien und startest keine Programme außerhalb dieser Handlungen. '
                   'Dateien und Ordner siehst du nur, wenn der Captain sie anhängt; dann steht ihr Inhalt in der Nachricht. '
                   'Behaupte nie, etwas getan zu haben – sag, was du vorgeschlagen oder geöffnet hast.')

    # Der Planungstisch (19.10.2026): ein Assistent in einer Rolle plant mit dem Captain – jede Festlegung ist ein Vorschlag (Knopf)
    PLANUNG_SYSTEM = ('Du bist {rolle} am Planungstisch der Firma und planst mit dem Captain. Antworte kurz und auf Deutsch, in einfachem Text. '
                      'Deine Aufgabe: aus dem Gespräch Ziele und Aufträge machen. Ein Ziel mit mehreren Schritten legst du mit propose_intent an '
                      '(Titel, Satz, und die Stufen in der Reihenfolge, 2 bis 12); einen einzelnen Auftrag mit klarem Ergebnis mit propose_task. '
                      'Frag nach, wenn das Ziel oder das Ergebnis unklar ist – aber höchstens eine Rückfrage, dann schlag vor. '
                      'Was du vorschlägst, bekommt der Captain als Knopf; erst sein Klick legt es an, und es wird nichts ausgeführt. '
                      'Behaupte nie, etwas angelegt zu haben. Wo du stehst, siehst du mit arbeitsplatz_stand und list_missions.')
    PLANUNG_ROLLEN = {'planner': 'der Planer', 'researcher': 'der Rechercheur', 'coder': 'der Entwickler', 'reviewer': 'der Prüfer',
                      'documentation': 'der Dokumentar', 'context curator': 'der Kontextpfleger'}

    def planung_reply(self, payload):
        """POST /api/planung/reply {text, history, rolle, mission_id} – das Gespräch am Planungstisch: derselbe Weg wie chat_reply
        (Control Master, Audit, Inhaltsschutz), nur mit dem Systemsatz der Rolle und den Werkzeugen des Planens (chat_tools.PLANUNG_TOOLS)."""
        rolle = str(payload.get('rolle') or 'planner').strip().lower()[:40]
        return self.chat_reply(dict(payload, modus='planung', rolle=rolle))

    CHAT_STATE_WORDS = ('modell', 'kontext', 'profil', 'schalter', 'geladen', 'läuft', 'laeuft', 'gpu', 'grafikspeicher', 'einstellung', 'kv-cache',
                        'projekt', 'karte', 'mission', 'audit', 'verlauf', 'doku', 'dokument',
                        'gateway', 'vorgang', 'regel', 'leitfaden', 'schutzklasse', 'merkmal', 'entwurf',   # B6-G-03: nachschlagen, nicht raten
                        'oberfläche', 'oberflaeche', 'arbeitsplatz', 'teststrecke', 'posteingang', 'umschalter')   # Build 24: der Arbeitsplatz
    # Build 19: ein Satz, der etwas öffnen oder tun will, muss über ein Werkzeug laufen – sonst sagt ein kleines Modell „das kann ich nicht“
    CHAT_MOVE_WORDS = ('öffne', 'oeffne', 'fenster', 'zeig', 'lade', 'entlade', 'starte', 'führe', 'fuehre', 'ausführ', 'ausfuehr',
                       'teste', 'übernimm', 'uebernimm', 'vorhaben', 'aufgabe', 'freigabe', 'entscheidung')
    CHAT_TOOL_NOTE = (' Will der Captain ein Fenster sehen, rufe open_place (Orte aus list_places) oder open_object. Will er etwas tun lassen '
                      '(Modell laden, Aufgabe ausführen, Kandidat testen), rufe erst list_actions und dann propose_action. Ein größerer '
                      'Auftrag wird mit propose_intent ein Vorhaben. Sag nie „das kann ich nicht“, wenn eines dieser Werkzeuge passt.'
                      ' Du weißt nichts über deine Umgebung, bis du es nachschaust. Fragt der Captain nach dem geladenen Modell, dem Kontext, '
                      'den Modellen, dem Profil, den Schaltern, Projekten, Karten, dem Verlauf (Audit) oder der Doku, rufe das passende Werkzeug auf '
                      'und antworte danach aus dessen Ergebnis. Nenne nur Werte, die ein Werkzeug geliefert hat; was als Maximum gilt, sagt das Rezept (context_maximum), '
                      'nicht eine Messung. Fragt der Captain nach dem KI GateWay, einem Vorgang (GW-…), einer Regel (R-01…R-16), einem Merkmal, '
                      'dem Ablauf oder einem Fehlercode, rufe erst gateway_status, gateway_vorgang, gateway_regel oder gateway_leitfaden; einen Text, '
                      'den er dir gibt, prüfst du mit gateway_pruefe_text. Du siehst nie den Anfragetext eines Vorgangs – sag das, statt ihn zu erfinden. '
                      'Fragt der Captain, wo etwas in der Oberfläche ist, wie er etwas tut (Projekt anlegen, Modell hinzufügen, Teststrecke, Freigabe) '
                      'oder was als Nächstes ansteht, rufe arbeitsplatz_wissen bzw. arbeitsplatz_stand und antworte daraus. '
                      'Rate nie. Will der Captain etwas ändern (zum Beispiel den Kontext), schlage es mit propose_routing_change oder '
                      'propose_switch vor. Das wird erst wirksam, wenn der Captain im Fenster Modelle freigibt. Sag nie, dass etwas geändert ist, '
                      'bevor es freigegeben wurde; sag stattdessen, dass der Vorschlag im Fenster Modelle zur Freigabe liegt.')

    ATTACH_LIST_LIMIT = 150
    ATTACH_DEPTH = 4
    ATTACH_FILE_BYTES = 12_000
    ATTACH_MAX = 5
    # Files that hold secrets are never read into a model prompt, whatever the Captain types (hardening 2026-10-14; the list follows .gitignore).
    SECRET_NAMES = re.compile(r'^(\.env(\..*)?|tokens\.json|.*\.token|id_(rsa|ed25519|ecdsa)(\.pub)?|.*\.(pem|key|pfx|p12|kdbx))$', re.I)
    SECRET_DIRS = frozenset({'.ssh', '.gnupg', '.aws', '.azure', '.kube', '.docker'})

    def _refuse_secret(self, path):
        parts = {p.lower() for p in path.parts}
        if parts & self.SECRET_DIRS or self.SECRET_NAMES.match(path.name): raise ValueError('secret_file_refused')

    def chat_attach(self, payload):
        """Read-only look at a file or folder the captain names in the chat: kind, size, folder listing or a text excerpt.
        Nothing is changed; the result is shown to the captain and sent along as context with the next message."""
        raw = str(payload.get('path') or '').strip().strip('"')
        if not raw or len(raw) > 500 or chr(0) in raw: raise ValueError('path_required')
        path = Path(raw)
        if not path.is_absolute(): raise ValueError('absolute_path_required')
        try:
            path = path.resolve(strict=True)
        except OSError:
            raise ValueError('path_not_found')
        self._refuse_secret(path)
        if path.is_dir():
            # Subfolders are listed too (model folders keep their files two levels down), depth-limited and bounded.
            entries, truncated = [], False
            for root, dirs, files in os.walk(path):
                rel = Path(root).relative_to(path)
                dirs[:] = sorted(d for d in dirs if d not in self.HIDDEN_NAMES)
                if len(rel.parts) >= self.ATTACH_DEPTH: dirs[:] = []
                dirs[:] = [d for d in dirs if d.lower() not in self.SECRET_DIRS]
                for f in sorted(files, key=str.lower):
                    if self.SECRET_NAMES.match(f): continue
                    if len(entries) >= self.ATTACH_LIST_LIMIT: truncated = True; break
                    try: size = os.path.getsize(os.path.join(root, f))
                    except OSError: size = None
                    entries.append({'name': (rel / f).as_posix(), 'type': 'file', 'size': size})
                if truncated: break
            self.runtime.audit.append('UIX_CHAT_ATTACH', component='uix', payload={'kind': 'dir', 'path': str(path), 'entries': len(entries)})
            return {'path': str(path), 'kind': 'dir', 'entries': entries, 'truncated': truncated}
        if not path.is_file(): raise ValueError('path_not_found')
        out = {'path': str(path), 'kind': 'file', 'size': path.stat().st_size}
        try:
            with open(path, 'rb') as fh: data = fh.read(self.ATTACH_FILE_BYTES + 1)
            out['excerpt'] = data[:self.ATTACH_FILE_BYTES].decode('utf-8')
            out['truncated'] = len(data) > self.ATTACH_FILE_BYTES
        except UnicodeDecodeError:
            out['binary'] = True
        except OSError:
            raise ValueError('access_blocked')
        self.runtime.audit.append('UIX_CHAT_ATTACH', component='uix', payload={'kind': 'file', 'path': str(path), 'bytes': out['size'], 'binary': bool(out.get('binary'))})
        return out

    def _attachment_context(self, attachments):
        """Context block for the model: what the captain attached, re-read here (the client's text is not trusted)."""
        if not attachments: return ''
        if not isinstance(attachments, list) or len(attachments) > self.ATTACH_MAX or not all(isinstance(a, str) for a in attachments): raise ValueError('invalid_attachments')
        parts = []
        for raw in attachments:
            info = self.chat_attach({'path': raw})
            if info['kind'] == 'dir':
                listing = '\n'.join('- ' + e['name'] + (' (' + str(round(e['size'] / 2**20)) + ' MB)' if e.get('size') else '') for e in info['entries'])
                parts.append('Ordner ' + info['path'] + ' enthält diese Dateien (inkl. Unterordner):\n' + listing + ('\n... (gekürzt)' if info['truncated'] else ''))
            elif info.get('binary'):
                parts.append('Datei ' + info['path'] + ' (' + str(info['size']) + ' Bytes, kein Text)')
            else:
                parts.append('Datei ' + info['path'] + ':\n' + info['excerpt'] + ('\n... (gekürzt)' if info['truncated'] else ''))
        return 'Vom Captain angehängt (nur Lesezugriff, nichts davon wurde verändert):\n' + '\n\n'.join(parts) + '\n\n'

    def chat_reply(self, payload):
        """Text answer of the loaded local model to a chat message. Goes through the Control Master like every model call
        (feasibility, audit, usage metrics) and is bound to the mission that was created for this message. No tools, no execution."""
        mission_id = str(payload.get('mission_id') or '').strip()      # empty: the first reply of a chat opens its session mission
        text = str(payload.get('text') or '').strip()
        if not text or len(text) > 8000: raise ValueError('text_required')
        history = payload.get('history') or []
        if not isinstance(history, list) or len(history) > 20: raise ValueError('invalid_history')
        attached = self._attachment_context(payload.get('attachments'))
        # Ticket B6-G-03 (Klaus 15.10. 14:27: „Wissensbasis kommt vor Modellwissen“): Fragen an das GateWay beantwortet die Wissensbasis
        # deterministisch – auch ohne Modell, und im Studio auch dann, wenn eines geladen ist. Kein Modellaufruf, kein Text im Audit.
        from .gateway.wissen import GatewayWissen
        from .desk import arbeitsplatz as desk_arbeitsplatz
        shell = self.aktive_shell()
        if GatewayWissen.zustaendig(text, shell):
            out = self.gw_wissen.antwort(text, (str(payload['vorgang']) if payload.get('vorgang') else None))
            self.runtime.audit.append('UIX_CHAT_GATEWAY_WISSEN', component='gateway', payload={'art': out['art'], 'shell': shell, 'actions': len(out['ui_actions']), 'via': 'chat'})
            return {'status': 'completed', 'reply': out['reply'], 'model': 'gateway-wissen', 'truncated': False, 'mission_id': mission_id,
                    'tools_used': [], 'proposals': [], 'ui_actions': out['ui_actions'], 'quelle': out['quelle']}
        # Build 24 (B6-G-06): Fragen nach dem Arbeitsplatz – wo etwas ist, wie man es tut, was als Nächstes ansteht – beantwortet die
        # Arbeitsplatz-Wissensbasis aus Code und Live-Stand; im Studio bleibt „was als Nächstes“ beim GateWay (oben).
        if desk_arbeitsplatz.zustaendig(text, shell):
            out = self.arbeitsplatz.antwort(text, shell)
            self.runtime.audit.append('UIX_CHAT_ARBEITSPLATZ_WISSEN', component='uix', payload={'art': out['art'], 'shell': shell, 'actions': len(out['ui_actions']), 'via': 'chat'})
            return {'status': 'completed', 'reply': out['reply'], 'model': 'arbeitsplatz-wissen', 'truncated': False, 'mission_id': mission_id,
                    'tools_used': [], 'proposals': [], 'ui_actions': out['ui_actions'], 'quelle': out['quelle']}
        turns = []
        for h in history[-8:]:
            if not isinstance(h, dict) or h.get('role') not in ('user', 'assistant') or not isinstance(h.get('content'), str): raise ValueError('invalid_history')
            turns.append({'role': h['role'], 'content': h['content'][:4000]})
        rt = self.runtime
        server = getattr(rt, 'llama_server', None)
        loaded = server.loaded_models() if server is not None else []
        # SPEC_SHELL_WISSEN_v1 §4.6 (W-E4): „Frag das Wissen“ – nur, wenn die Shell es einschaltet (gespraech.wissen); nur lokal, Stufe 6
        wissen = None
        if payload.get('wissen') is True and getattr(rt, 'wissen', None) is not None:
            from .wissen import desk_basis
            wissen_extra, wissen = desk_basis.kontext(rt.wissen, text, mission_id or None)
            if not loaded:
                return {'status': 'completed', 'reply': desk_basis.ohne_modell(wissen), 'model': 'wissen', 'truncated': False, 'mission_id': mission_id,
                        'tools_used': [], 'proposals': [], 'ui_actions': [], 'wissen': desk_basis.nachweis(wissen)}
        if not loaded:
            # Befund M1 (Architekturreview): ein ungültiger Wert in der Konfiguration schaltet den Server still ab – der Grund gehört in den Chat
            grund = getattr(rt, 'llama_server_error', None)
            return {'status': 'no_model', 'message': 'Kein Modell geladen.' + (' Grund: ' + str(grund) if grund else '')}
        model = loaded[0].get('identifier') or loaded[0].get('modelKey')
        with self.lock:
            if not mission_id:
                # One mission carries all model calls of a chat window (audit, usage). It is not planned: a plan is made only on request.
                mission = rt.brain.create_mission('Chat-Sitzung mit dem lokalen Modell', None, 'S1')
                mission_id = mission['identity']['mission_id']
            else:
                mission = rt.missions.load(mission_id)
            # The model may call the read-only environment tools (chat_tools.py) before it answers. Every model turn goes through the
            # Control Master like a plain chat call (feasibility, usage, audit); the tool calls are audited below.
            planung = payload.get('modus') == 'planung'
            if planung:
                from .chat_tools import PLANUNG_TOOLS
                box = ChatTools(self, PLANUNG_TOOLS)
                rolle = str(payload.get('rolle') or 'planner')
                system = self.PLANUNG_SYSTEM.format(rolle=self.PLANUNG_ROLLEN.get(rolle, 'der Assistent „' + rolle[:40] + '“')) + ' ' + self.arbeitsplatz.beschreibung(shell)
            else:
                box = ChatTools(self)
                # Build 24: das Modell weiß, in welcher Oberfläche es arbeitet (Zonen, eigene Wörter, Wege) – aus dem Code, nicht geraten
                system = self.CHAT_SYSTEM + ' ' + self.arbeitsplatz.beschreibung(shell) + self.CHAT_TOOL_NOTE
            messages = [{'role': 'system', 'content': system}, *turns, {'role': 'user', 'content': attached + text}]
            if wissen is not None and wissen_extra:
                from .wissen import lauf as wissen_lauf
                messages = wissen_lauf.nachrichten_mit(messages, wissen_extra)

            # A question about the system (model, context, profile, switches) must be looked up: the first turn then forces a tool call.
            # Without this a small model answers from memory (2026-10-14: a right-looking context value that no tool had read).
            low = text.lower()
            asks_state = any(k in low for k in self.CHAT_STATE_WORDS) or any(k in low for k in self.CHAT_MOVE_WORDS)
            turn_no = [0]

            def post(body):
                turn_no[0] += 1
                choice = 'required' if asks_state and turn_no[0] == 1 else 'auto'
                out = rt.control.execute(mission, {'action': 'model_inference', 'provider': 'llama-cpp-server', 'model': body['model'],
                                                   'temperature': body['temperature'], 'max_tokens': body['max_tokens'],
                                                   'messages': body['messages'], 'tools': body['tools'], 'tool_choice': choice})
                if out.get('status') != 'completed': raise RuntimeError(str(out.get('reason_code') or out.get('error') or out.get('status')))
                r = out['model_result']
                usage = r.get('usage') or {}
                return {'choices': [{'message': r.get('message') or {'content': r.get('content') or ''}, 'finish_reason': r.get('finish_reason')}],
                        'usage': {'prompt_tokens': usage.get('input_tokens') or 0}}

            res = run_tool_loop(post, model, messages, box, {'temperature': 0.7}, max_tokens=2048 if attached else 1024)   # the model reasons first; answers about attachments are longer
        self.runtime.audit.append('UIX_CHAT_TOOLS', component='uix', payload={'model': model, 'calls': box.calls, 'turns': res.get('turns'), 'finish': res.get('finish'),
                                                                             'offered': [a['kind'] for a in box.ui_actions], 'modus': 'planung' if planung else 'gespraech'})
        if res.get('error'):
            return {'status': 'failed', 'message': str(res['error'])[:300]}
        content = res.get('content')
        if not isinstance(content, str) or not content.strip():
            return {'status': 'failed', 'message': 'model_answer_truncated' if res.get('finish') == 'length' else 'model_answer_empty'}
        out = {'status': 'completed', 'reply': content.strip(), 'model': model, 'truncated': res.get('finish') == 'length', 'mission_id': mission_id,
               'tools_used': box.calls, 'proposals': box.proposals, 'ui_actions': box.ui_actions}
        if wissen is not None:                                   # Zitatprüfung wie bei den Agenten (D7.6, WIS-07)
            from .wissen import desk_basis, lauf as wissen_lauf
            if wissen.get('treffer'):
                out['reply'] = wissen_lauf.nachbereite(out['reply'], wissen, mission_id=mission_id, audit=rt.wissen.audit)
            out['wissen'] = desk_basis.nachweis(wissen)
        return out

    def run_mission(self, payload):
        mission_id = str(payload.get('mission_id') or '').strip()
        if not mission_id:
            raise ValueError('mission_id_required')
        max_steps = payload.get('max_steps',20)
        if type(max_steps) is not int or not 1 <= max_steps <= 32: raise ValueError('max_steps_out_of_range')
        with self.lock:
            m = self.runtime.brain.run(mission_id, max_steps=max_steps)
        return {'mission': _compact_mission(m), 'full_phase': m.get('lifecycle', {}), 'pending_gates': m.get('human_gates', {}).get('pending', [])}

    def mission_lifecycle(self, mission_id, aktion):
        """Schließen, Beenden und Archivieren einer Aufgabe (Verben in desk/actions.py). Ohne Gate: es wird nichts ausgeführt,
        nur der Stand gesetzt. Beenden folgt der Phasentabelle (FAILED nur, wo sie es erlaubt); jede Änderung steht im Audit."""
        with self.lock:
            m = self.runtime.missions.load(mission_id)
            status, phase = m['lifecycle']['status'], m['lifecycle']['phase']
            if aktion == 'schliessen':
                if status != 'active' or phase in ('EXECUTE', 'VERIFY', 'REWORK'): raise ValueError('nicht_schliessbar_jetzt')
                m['lifecycle']['status'] = 'closed'
            elif aktion == 'beenden':
                if status != 'active': raise ValueError('nicht_beendbar_jetzt')
                try: self.runtime.missions.transition(m, 'FAILED')
                except InvalidTransition as exc: raise ValueError('phase_erlaubt_kein_beenden') from exc
                m['result'] = {'kind': m.get('result', {}).get('kind'), 'qualification': 'BEENDET', 'accepted': False, 'tests_executed': False}
                self.runtime.missions.save(m)
            elif aktion == 'archivieren':
                if status != 'closed': raise ValueError('nicht_archivierbar_jetzt')
                m['lifecycle']['status'] = 'archived'
                m['lifecycle']['archived_at'] = utcnow()
            else:
                raise ValueError('unknown_lifecycle_action')
            if aktion != 'beenden': self.runtime.missions.save(m)
            self.runtime.audit.append('MISSION_LIFECYCLE', component='desk', mission_id=mission_id,
                                      payload={'aktion': aktion, 'von': status, 'nach': m['lifecycle']['status'], 'phase': m['lifecycle']['phase']})
        return {'status': 'done', 'mission_id': mission_id, 'lifecycle': m['lifecycle']}

    def approve_gate(self, payload):
        mission_id = str(payload.get('mission_id') or '').strip()
        gate_id = payload.get('gate_id')
        if not isinstance(gate_id,str) or not gate_id: raise ValueError('exact_gate_id_required')
        if not mission_id:
            raise ValueError('mission_id_required')
        with self.runtime.missions.execution_lock(mission_id):
            m = self.runtime.missions.load(mission_id)
            pending = m.get('human_gates', {}).get('pending', [])
            if not pending:
                raise ValueError('no_pending_human_gate')
            index = 0
            if gate_id:
                index = next((i for i, g in enumerate(pending) if g.get('gate_id') == gate_id), None)
                if index is None:
                    raise ValueError('gate_id_not_pending')
            gate = pending[index]
            token = self.runtime.guard.approve(gate)
            m['human_gates']['pending'].pop(index)
            m['human_gates']['resolved'].append(gate)
            m['execution']['approval_token'] = token
            self.runtime.missions.save(m)
        return {'status': 'approved', 'mission_id': mission_id, 'gate_id': gate.get('gate_id')}

    def reject_gate(self, payload):
        mission_id = str(payload.get('mission_id') or '').strip()
        gate_id = payload.get('gate_id')
        if not isinstance(gate_id,str) or not gate_id: raise ValueError('exact_gate_id_required')
        if not mission_id: raise ValueError('mission_id_required')
        with self.runtime.missions.execution_lock(mission_id):
            m = self.runtime.missions.load(mission_id)
            pending = m.get('human_gates', {}).get('pending', [])
            index = next((i for i, g in enumerate(pending) if g.get('gate_id') == gate_id), None)
            if index is None: raise ValueError('gate_id_not_pending')
            gate = self.runtime.guard.reject(pending.pop(index))
            m['human_gates']['resolved'].append(gate)
            # a denied mission waits instead of running on; where PAUSED is not allowed the phase stays as it is
            if 'PAUSED' in ALLOWED.get(m['lifecycle']['phase'], set()): self.runtime.missions.transition(m, 'PAUSED')
            else: self.runtime.missions.save(m)
        return {'status': 'rejected', 'mission_id': mission_id, 'gate_id': gate_id}

    def mission_details(self, payload):
        return self.runtime.missions.load(payload['mission_id'])

    # ---- machine-local switches (local_config/switches.yaml): changed only behind a Captain gate, effective at the next start
    SWITCH_ACTION = 'change_switch'

    def _switch_path(self):
        return self.runtime.project_root / 'local_config' / 'switches.yaml'

    def _switch_values(self):
        path = self._switch_path()
        return LocalSwitches.load(path).values if path.exists() else {}

    def _switch_digest(self):
        path = self._switch_path()
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

    def switches_view(self):
        values = self._switch_values()
        items = [{'section': s, 'key': k, 'value': values.get(s, {}).get(k)} for s in SWITCH_ALLOWED for k in sorted(SWITCH_ALLOWED[s])]
        return {'items': items, 'restart_needed': values != self._switch_boot,
                'error': getattr(self.runtime, 'switches_error', None)}

    def _check_switch(self, payload):
        section, key, value = payload.get('section'), payload.get('key'), payload.get('value')
        if section not in SWITCH_ALLOWED or key not in SWITCH_ALLOWED[section]: raise ValueError('unknown_switch')
        if type(value) is not bool: raise ValueError('switch_value_must_be_boolean')
        return section, key, value

    def switch_request(self, payload):
        section, key, value = self._check_switch(payload)
        old = self._switch_values().get(section, {}).get(key)
        binding = {'section': section, 'key': key, 'old': old, 'new': value, 'file_sha256': self._switch_digest()}
        target = f'switch:{section}.{key}'
        with self.lock:
            m = self.runtime.brain.create_mission(f'Schalter {section}.{key} auf {"an" if value else "aus"} stellen', None, 'S1')
            gate = self.runtime.guard.create_gate(m['identity']['mission_id'], self.SWITCH_ACTION, target,
                                                  risks=['wirkt erst nach Neustart der SEDRA-Oberfläche'], rollback_available=True, request_binding=binding)
            m['human_gates']['pending'].append(gate)
            m['context']['switch_request'] = binding
            self.runtime.missions.save(m)
        return self._remember('switch', {'mission_id': m['identity']['mission_id'], 'gate': gate, 'binding': binding})

    def _remember(self, kind, res):
        """Keeps a change request open until its gate is decided, so the Modelle window can show it even when the chat made it."""
        self.__dict__.setdefault('open_requests', {})[res['mission_id']] = dict(res, kind=kind)
        return res

    def _open_requests(self):
        out = []
        for mid, req in list(self.__dict__.get('open_requests', {}).items()):
            try: m = self.runtime.missions.load(mid)
            except Exception: self.open_requests.pop(mid, None); continue
            pending = {g.get('gate_id') for g in (m.get('human_gates') or {}).get('pending', [])}
            if req['gate'].get('gate_id') in pending: out.append({'kind': req['kind'], 'mission_id': mid, 'gate': req['gate'], 'binding': req['binding']})
            else: self.open_requests.pop(mid, None)
        # Nach einem Neustart ist die Merkliste leer, das Gate aber steht noch in der Mission. Offene GateWay-Freigaben daher
        # zusätzlich aus den Missionen lesen – sonst zeigt der Knopf „Jetzt freigeben“ auf eine Entscheidung, die es nicht gibt.
        known = {r['mission_id'] for r in out}
        for m in self.runtime.missions.list():
            mid = (m.get('identity') or {}).get('mission_id')
            binding = (m.get('context') or {}).get('gateway_request')
            if not mid or mid in known or not binding: continue
            for gate in (m.get('human_gates') or {}).get('pending', []):
                if isinstance(gate, dict) and gate.get('gate_id'):
                    out.append({'kind': 'gateway', 'mission_id': mid, 'gate': gate, 'binding': binding})
                    break
        out += desk_gated.pending(self, {r['mission_id'] for r in out})     # Spec 1: gated-Anträge nach einem Neustart (G2-S1-09)
        return out

    @staticmethod
    def _edit_switch_text(text, section, key, value):
        """Changes one boolean in the inline-mapping layout of switches.yaml; comments and every other line stay as they are."""
        word = 'true' if value else 'false'
        line = re.compile(r'^(\s+' + re.escape(section) + r':\s*\{)([^}]*)(\}.*)$', re.M)
        m = line.search(text)
        if m:
            pairs = [p.strip() for p in m.group(2).split(',') if p.strip()]
            found = False
            for i, p in enumerate(pairs):
                if p.split(':')[0].strip() == key: pairs[i] = f'{key}: {word}'; found = True
            if not found: pairs.append(f'{key}: {word}')
            return text[:m.start()] + m.group(1) + ', '.join(pairs) + m.group(3) + text[m.end():]
        entry = f'  {section}: {{{key}: {word}}}'
        head = re.search(r'^switches:[ \t]*\r?$', text, re.M)
        if head: return text[:head.end()] + '\n' + entry + text[head.end():]
        return text.rstrip('\n') + '\nswitches:\n' + entry + '\n'

    def switch_apply(self, payload):
        mission_id = str(payload.get('mission_id') or '').strip()
        if not mission_id: raise ValueError('mission_id_required')
        rt = self.runtime
        with rt.missions.execution_lock(mission_id):
            m = rt.missions.load(mission_id)
            binding = (m.get('context') or {}).get('switch_request')
            token = (m.get('execution') or {}).get('approval_token')
            if not binding: raise ValueError('not_a_switch_request')
            if not token: raise ValueError('captain_approval_required')
            if binding['file_sha256'] != self._switch_digest(): raise ValueError('switch_file_changed_repeat_request')
            target = f"switch:{binding['section']}.{binding['key']}"
            if not rt.guard.authorize(token, mission_id=mission_id, action=self.SWITCH_ACTION, target=target, request_binding=binding)['authorized']:
                raise ValueError('captain_approval_invalid')
            path = self._switch_path()
            old_text = path.read_text(encoding='utf-8') if path.exists() else ''
            backup = None
            if path.exists():
                backup = path.with_name(path.name + '.bak-' + utcnow()[:10] + '-uix')
                shutil.copy2(path, backup)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._edit_switch_text(old_text, binding['section'], binding['key'], binding['new']), encoding='utf-8')
            try: LocalSwitches.load(path)
            except ValueError as exc:                      # never leave a file the runtime would refuse
                path.write_text(old_text, encoding='utf-8'); raise ValueError(str(exc))
            m['execution'].pop('approval_token', None)
            m['result'] = {'kind': 'switch_change', 'section': binding['section'], 'key': binding['key'], 'old': binding['old'], 'new': binding['new'],
                           'backup': backup.name if backup else None, 'effective': 'next_start'}
            m['lifecycle']['status'] = 'closed'
            rt.missions.save(m)
            rt.audit.append('LOCAL_SWITCH_CHANGED', component='uix', mission_id=mission_id, payload={k: m['result'][k] for k in ('section', 'key', 'old', 'new')})
        return {'status': 'applied', 'section': binding['section'], 'key': binding['key'], 'new': binding['new'], 'effective': 'next_start'}

    # ---- role routing overlay (local_config/role_routing.yaml): a few fields of the Captain's own recipes, behind a Captain gate
    ROUTING_ACTION = 'change_routing'
    ROUTING_FIELDS = {'enabled': 'Aktiv', 'context_recommended': 'Kontext', 'n_cpu_moe': 'Experten im Arbeitsspeicher', 'kv_cache_type': 'KV-Cache-Genauigkeit'}
    KV_TYPES = ('f16', 'q8_0')

    def _routing_path(self):
        return self.runtime.project_root / 'local_config' / 'role_routing.yaml'

    @staticmethod
    def _read_raw(path):
        with open(path, encoding='utf-8', newline='') as f: return f.read()

    @staticmethod
    def _write_raw(path, text):
        with open(path, 'w', encoding='utf-8', newline='') as f: f.write(text)

    def _routing_recipes(self):
        path = self._routing_path()
        if not path.exists(): return []
        data = (yaml.safe_load(self._read_raw(path)) or {}).get('role_routing') or {}
        out = []
        for cap in data.get('capabilities') or []:
            profile = cap.get('profile') or {}
            context = profile.get('context') or {}
            server = profile.get('server') or {}
            out.append({'id': cap['id'], 'model': cap.get('model'), 'enabled': cap.get('enabled', True),
                        'context_recommended': context.get('recommended'), 'context_tiers': context.get('tiers') or [],
                        'n_cpu_moe': server.get('n_cpu_moe'), 'kv_cache_type': server.get('kv_cache_type'), 'has_server': 'server' in profile})
        return out

    def _routing_values(self):
        try: return {r['id']: {k: r[k] for k in ('enabled', 'context_recommended', 'n_cpu_moe', 'kv_cache_type')} for r in self._routing_recipes()}
        except Exception: return {}

    def routing_config_view(self):
        return {'recipes': self._routing_recipes(), 'restart_needed': self._routing_values() != self._routing_boot,
                'fields': self.ROUTING_FIELDS}

    def _check_routing_change(self, payload):
        rid, field, value = payload.get('recipe_id'), payload.get('field'), payload.get('value')
        recipe = next((r for r in self._routing_recipes() if r['id'] == rid), None)
        if recipe is None: raise ValueError('unknown_recipe')
        if field not in self.ROUTING_FIELDS: raise ValueError('unknown_field')
        if field == 'enabled':
            if type(value) is not bool: raise ValueError('value_must_be_boolean')
        elif field == 'context_recommended':
            if type(value) is not int or value not in recipe['context_tiers']: raise ValueError('context_must_be_one_of_the_tiers')
        elif field == 'n_cpu_moe':
            if type(value) is not int or not 0 <= value <= 48 or not recipe['has_server']: raise ValueError('n_cpu_moe_must_be_0_to_48')
        elif field == 'kv_cache_type':
            if value not in self.KV_TYPES or not recipe['has_server']: raise ValueError('kv_cache_type_must_be_f16_or_q8_0')
        return recipe, field, value

    @staticmethod
    def _recipe_span(lines, rid):
        start = next((i for i, l in enumerate(lines) if re.fullmatch(r'    - id:\s*' + re.escape(rid) + r'\s*', l.rstrip('\r\n'))), None)
        if start is None: raise ValueError('recipe_not_in_file')
        end = len(lines)
        for i in range(start + 1, len(lines)):
            t = lines[i].rstrip('\r\n')
            if re.match(r'    - id:', t) or (t.strip() and not t.lstrip().startswith('#') and len(t) - len(t.lstrip()) <= 2): end = i; break
        return start, end

    @classmethod
    def _edit_routing_text(cls, text, rid, field, value, stamp):
        lines = text.splitlines(keepends=True)
        start, end = cls._recipe_span(lines, rid)
        eol = '\r\n' if lines[start].endswith('\r\n') else '\n'
        word = 'true' if value is True else 'false' if value is False else str(value)
        span = range(start + 1, end)
        if field == 'enabled':
            for i in span:
                if re.match(r'      enabled:\s*(true|false)', lines[i]):
                    lines[i] = f'      enabled: {word}   # set in the UIX {stamp}{eol}'; break
            else:
                lines.insert(start + 1, f'      enabled: {word}   # set in the UIX {stamp}{eol}')
        elif field == 'context_recommended':
            for i in span:
                new, n = re.subn(r'(context:\s*\{recommended:\s*)\d+', lambda m: m.group(1) + word, lines[i], count=1)
                if n: lines[i] = new; break
            else: raise ValueError('context_line_not_found')
        else:
            for i in span:
                if re.match(r'\s+server:\s*\{', lines[i]):
                    new, n = re.subn(r'(\b' + field + r':\s*)[A-Za-z0-9_.]+', lambda m: m.group(1) + word, lines[i], count=1)
                    if not n: new = re.sub(r'\}(\s*(?:#.*)?)$', lambda m: f', {field}: {word}' + '}' + m.group(1), lines[i].rstrip('\r\n'), count=1) + eol
                    lines[i] = new; break
            else: raise ValueError('server_line_not_found')
        return ''.join(lines)

    def routing_request(self, payload):
        recipe, field, value = self._check_routing_change(payload)
        old = recipe['enabled'] if field == 'enabled' else recipe[field]
        describe = f"{recipe['id']}: {self.ROUTING_FIELDS[field]} {old if old is not None else 'nicht gesetzt'} → {value}"
        binding = {'recipe_id': recipe['id'], 'field': field, 'old': old, 'new': value, 'file_sha256': self._file_digest(self._routing_path()), 'describe': describe}
        return self._remember('routing', self._gate_request(f'Routing ändern: {describe}', self.ROUTING_ACTION, f"routing:{recipe['id']}.{field}", binding,
                                  ['wirkt beim nächsten Laden des Modells (ohne Neustart)', 'ändert, welches Modell wie geladen wird'], 'routing_request'))

    def routing_apply(self, payload):
        mission_id = str(payload.get('mission_id') or '').strip()
        if not mission_id: raise ValueError('mission_id_required')
        rt = self.runtime
        with rt.missions.execution_lock(mission_id):
            m = rt.missions.load(mission_id)
            binding = self._spend_approval(m, mission_id, 'routing_request', self.ROUTING_ACTION,
                                           lambda b: f"routing:{b['recipe_id']}.{b['field']}", self._file_digest(self._routing_path()))
            path = self._routing_path()
            old_text = self._read_raw(path)
            backup = path.with_name(path.name + '.bak-' + utcnow()[:10] + '-uix')
            shutil.copy2(path, backup)
            self._write_raw(path, self._edit_routing_text(old_text, binding['recipe_id'], binding['field'], binding['new'], utcnow()[:10]))
            try: RoutingConfig.load(rt.config_root / 'role_routing.yaml', path)
            except Exception as exc:            # never leave an overlay the runtime would refuse
                self._write_raw(path, old_text); raise ValueError(f'routing_overlay_invalid:{exc}')
            m['execution'].pop('approval_token', None)
            m['result'] = {'kind': 'routing_change', **{k: binding[k] for k in ('recipe_id', 'field', 'old', 'new')}, 'backup': backup.name, 'effective': 'naechstes_laden'}
            m['lifecycle']['status'] = 'closed'
            rt.missions.save(m)
            rt.audit.append('ROUTING_OVERLAY_CHANGED', component='uix', mission_id=mission_id, payload={k: m['result'][k] for k in ('recipe_id', 'field', 'old', 'new')})
            rt.reload_role_routing()          # ohne Neustart: die Änderung gilt beim nächsten Laden
            self._routing_boot = self._routing_values()     # damit die Ansicht nicht „Neustart nötig“ zeigt
        return {'status': 'applied', 'recipe_id': binding['recipe_id'], 'field': binding['field'], 'new': binding['new'], 'effective': 'naechstes_laden'}

    # ---- a new model the short way (Captain 2026-10-14): pick the GGUF, see the proposed recipe, approve once, load, test
    PICK_TIMEOUT_S = 600
    BROWSE_LIMIT = 400

    def _models_root(self):
        root = local_paths.load().get('modelle')
        return Path(root) if root and Path(root).is_dir() else None

    def model_pick(self, payload):
        """The file dialog of this PC (Explorer on Windows, Finder on macOS, zenity on Linux when installed); the server runs in the Captain's
        session, so the dialog appears on the desktop. Returns the chosen path, or why there is none; the caller then offers the folder list."""
        root = self._models_root()
        start = str(root) if root else ''
        ps_start = start.replace("'", "''")                      # the folder is quoted into a PowerShell / AppleScript literal: escape its quotes
        as_start = start.replace('\\', '\\\\').replace('"', '\\"')
        try:
            if sys.platform == 'win32':
                script = ("Add-Type -AssemblyName System.Windows.Forms; $d = New-Object System.Windows.Forms.OpenFileDialog; "
                          "$d.Filter = 'GGUF-Modelle (*.gguf)|*.gguf'; $d.Title = 'Modell waehlen (GGUF)'; " + (f"$d.InitialDirectory = '{ps_start}'; " if start else '') +
                          "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.FileName }")
                out = self._run(['powershell', '-NoProfile', '-STA', '-Command', script], capture_output=True, text=True, timeout=self.PICK_TIMEOUT_S)
            elif sys.platform == 'darwin':
                where = f' default location POSIX file "{as_start}"' if start else ''
                out = self._run(['osascript', '-e', f'POSIX path of (choose file with prompt "Modell wählen (GGUF)" of type {{"gguf"}}{where})'],
                                capture_output=True, text=True, timeout=self.PICK_TIMEOUT_S)
            elif shutil.which('zenity'):
                out = self._run(['zenity', '--file-selection', '--title=Modell wählen (GGUF)', '--file-filter=*.gguf'] + ([f'--filename={start}/'] if start else []),
                                capture_output=True, text=True, timeout=self.PICK_TIMEOUT_S)
            else:
                return {'picked': False, 'reason': 'no_dialog', 'root': start or None}
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {'picked': False, 'reason': 'dialog_failed:' + type(exc).__name__, 'root': start or None}
        chosen = (out.stdout or '').strip().splitlines()
        if not chosen or not chosen[-1].strip():
            return {'picked': False, 'reason': 'cancelled', 'root': start or None}
        return {'picked': True, 'path': chosen[-1].strip(), 'root': start or None}

    def model_browse(self, payload):
        """Folders and .gguf files under the model folder of this PC (local_paths.yaml: modelle), read-only and confined to it."""
        root = self._models_root()
        if root is None:
            return {'root': None, 'path': '', 'entries': [], 'note': 'Kein Modellordner eingetragen (runtime/config/local_paths.yaml: modelle). Pfad direkt eingeben oder den Dialog nutzen.'}
        sub = payload.get('path') or ''
        if not isinstance(sub, str) or len(sub) > 300 or sub.startswith(('/', '\\')) or ':' in sub: raise ValueError('invalid_path')
        parts = [p for p in sub.replace('\\', '/').split('/') if p not in ('', '.')]
        if '..' in parts: raise ValueError('invalid_path')
        folder = root.joinpath(*parts)
        try:
            if folder.resolve() != root.resolve() and root.resolve() not in folder.resolve().parents: raise ValueError('invalid_path')
            items = sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            raise ValueError('folder_not_readable')
        entries, truncated = [], False
        for p in items:
            if p.name.startswith('.') or p.name.startswith('_guppi_entfernt'): continue
            if p.is_dir(): entries.append({'name': p.name, 'type': 'dir'})
            elif p.suffix.lower() == '.gguf':
                try: size = round(p.stat().st_size / 2 ** 30, 2)
                except OSError: size = None
                entries.append({'name': p.name, 'type': 'file', 'size_gb': size, 'path': str(p)})
            if len(entries) >= self.BROWSE_LIMIT: truncated = True; break
        return {'root': str(root), 'path': '/'.join(parts), 'entries': entries, 'truncated': truncated}

    def _existing_recipe_ids(self):
        router = self.runtime.role_router
        ids = {r['id'] for r in (router.config.recipes if router is not None else [])}
        ids |= {r['id'] for r in self._routing_recipes()}
        return ids

    def _proposal(self, payload):
        raw = str(payload.get('path') or '').strip().strip('"')
        if not raw or len(raw) > 500: raise ValueError('path_required')
        path = Path(raw)
        if not path.is_absolute(): raise ValueError('absolute_path_required')
        try: info = model_add.gguf_info(path)
        except model_add.GgufError as exc: raise ValueError(str(exc))
        except OSError: raise ValueError('path_not_found')
        roles = payload.get('roles')
        recipe = model_add.propose_recipe(info, path, self._existing_recipe_ids(), roles if isinstance(roles, list) else None)
        rid = payload.get('recipe_id')
        if rid is not None:
            if not isinstance(rid, str) or not re.fullmatch(r'[a-z][a-z0-9_]{1,40}\.[a-z][a-z0-9_]{1,60}', rid): raise ValueError('recipe_id_invalid')
            if rid in self._existing_recipe_ids(): raise ValueError('recipe_id_taken')
            recipe['id'] = rid
        ctx = payload.get('context_recommended')
        if ctx is not None:
            if type(ctx) is not int or ctx not in recipe['profile']['context']['tiers']: raise ValueError('context_must_be_one_of_the_tiers')
            recipe['profile']['context']['recommended'] = ctx
        root = self._models_root()
        in_root = bool(root) and (root.resolve() in path.resolve().parents)
        return info, recipe, in_root

    def model_inspect(self, payload):
        """What the file says about itself and the recipe that would be written; nothing is changed."""
        info, recipe, in_root = self._proposal(payload)
        return {'info': info, 'recipe': recipe, 'yaml': model_add.recipe_yaml(recipe), 'in_models_root': in_root,
                'models_root': str(self._models_root()) if self._models_root() else None, 'overlay': str(self._routing_path()),
                'overlay_exists': self._routing_path().exists()}

    def model_add_request(self, payload):
        """A mission with one gate for exactly this recipe block; the block is written only after the Captain approves it."""
        info, recipe, in_root = self._proposal(payload)
        block = model_add.recipe_yaml(recipe)
        describe = f"Neues Modell {recipe['id']}: {info['name']} ({info.get('quantization') or '?'}, {info['size_gb']} GB, Kontext bis {recipe['profile']['context']['maximum']})"
        binding = {'recipe_id': recipe['id'], 'path': str(Path(payload['path'])), 'block': block, 'block_sha256': hashlib.sha256(block.encode('utf-8')).hexdigest(),
                   'file_sha256': self._file_digest(self._routing_path()), 'describe': describe}
        return self._remember('model_add', self._gate_request(describe, self.ROUTING_ACTION, f"routing:add:{recipe['id']}", binding,
                                  ['schreibt ein Rezept in local_config/role_routing.yaml', 'das Modell kann danach geladen werden'], 'model_add_request'))

    def model_add_apply(self, payload):
        mission_id = str(payload.get('mission_id') or '').strip()
        if not mission_id: raise ValueError('mission_id_required')
        rt = self.runtime
        with rt.missions.execution_lock(mission_id):
            m = rt.missions.load(mission_id)
            binding = self._spend_approval(m, mission_id, 'model_add_request', self.ROUTING_ACTION,
                                           lambda b: f"routing:add:{b['recipe_id']}", self._file_digest(self._routing_path()))
            if binding['recipe_id'] in self._existing_recipe_ids(): raise ValueError('recipe_id_taken')
            path = self._routing_path()
            old_text = self._read_raw(path) if path.exists() else ''
            backup = None
            if path.exists():
                backup = path.with_name(path.name + '.bak-' + utcnow()[:10] + '-uix'); shutil.copy2(path, backup)
            path.parent.mkdir(parents=True, exist_ok=True)
            recipe = yaml.safe_load('x:\n' + binding['block'])['x'][0]        # the approved block, parsed back: what is written is what was shown
            new_text = model_add.insert_recipe(old_text, recipe)
            self._write_raw(path, new_text)
            try:
                config = RoutingConfig.load(rt.config_root / 'role_routing.yaml', path)
            except Exception as exc:            # never leave an overlay the runtime would refuse
                self._write_raw(path, old_text) if old_text else path.unlink(missing_ok=True)
                raise ValueError(f'routing_overlay_invalid:{exc}')
            if rt.role_router is not None:
                rt.role_router.config = config        # the recipe is usable now, not only after a restart
            self._routing_boot = self._routing_values()
            m['execution'].pop('approval_token', None)
            m['result'] = {'kind': 'routing_recipe_added', 'recipe_id': binding['recipe_id'], 'path': binding['path'], 'backup': backup.name if backup else None, 'effective': 'now'}
            m['lifecycle']['status'] = 'closed'
            rt.missions.save(m)
            rt.audit.append('ROUTING_RECIPE_ADDED', component='uix', mission_id=mission_id, payload={'recipe_id': binding['recipe_id'], 'block_sha256': binding['block_sha256']})
        return {'status': 'applied', 'recipe_id': binding['recipe_id'], 'effective': 'now'}

    TEST_PROMPT = 'Antworte in einem kurzen deutschen Satz: Welches Sprachmodell bist du und wofür eignest du dich? Danach schreibe die Zahlen 1 bis 5 durch Komma getrennt.'

    def model_test(self, payload):
        """One short request to the loaded model of a recipe through the Control Master (audited like every call): answer, seconds, tokens per second."""
        rid = payload.get('recipe_id')
        if not isinstance(rid, str) or not rid: raise ValueError('recipe_id_required')
        rt = self.runtime
        recipe = next((r for r in self.models_view()['recipes'] if r['id'] == rid), None)
        if recipe is None: raise ValueError('unknown_recipe')
        if not recipe['loaded']: raise ValueError('model_not_loaded')
        with self.lock:
            mission = rt.brain.create_mission(f'Modelltest {rid}', None, 'S1')
            started = time.monotonic()
            out = rt.control.execute(mission, {'action': 'model_inference', 'provider': recipe['provider'], 'model': recipe['model'], 'temperature': 0.2, 'max_tokens': 120,
                                               'messages': [{'role': 'user', 'content': self.TEST_PROMPT}]})
            seconds = round(time.monotonic() - started, 2)
        if out.get('status') != 'completed':
            return {'status': out.get('status', 'failed'), 'message': str(out.get('reason_code') or out.get('error') or 'model_call_failed')[:300], 'seconds': seconds}
        result = out['model_result']; usage = result.get('usage') or {}
        completion = usage.get('completion_tokens') or usage.get('completion')
        reply = str(result.get('content') or '').strip()
        return {'status': 'completed', 'recipe_id': rid, 'reply': reply[:600], 'seconds': seconds, 'completion_tokens': completion,
                'tokens_per_s': round(completion / seconds, 1) if completion and seconds else None, 'numbers_ok': all(n in reply for n in ('1', '2', '3', '4', '5')),
                'mission_id': mission['identity']['mission_id']}

    # ---- Einstellungen: Cloud-Modelle mit API-Schlüssel (cloud_settings.py). Speichern ist der Klick des Captains; wirkt nach dem Neustart.
    # Ein Schlüssel verlässt den Server nie: die Antwort sagt nur, ob er per Umgebung, gespeichert oder gar nicht da ist.
    def cloud_view(self):
        rt = self.runtime
        view = cloud_settings.view(rt.project_root, rt.cloud_key_store, os.environ)
        view['restart_needed'] = cloud_settings.signature(rt.project_root, rt.cloud_key_store, os.environ) != rt.cloud_boot_signature
        # Was der laufende Server wirklich hat: nur diese Anbieter können antworten (ohne Neustart nichts Neues).
        live = sorted(aid for aid, a in rt.model_router.adapters.items() if getattr(a, 'route', 'local') == 'cloud')
        view['live'] = live
        for p in view['providers']:
            p['live'] = p['id'] in live
        view['error'] = getattr(rt, 'cloud_providers_error', None)
        view['key_store_available'] = CloudKeyStore.available()
        return view

    def cloud_save(self, payload):
        res = cloud_settings.save(self.runtime.project_root, payload)
        self.runtime.audit.append('CLOUD_SETTINGS_SAVED', component='desk',
                                  payload={'enabled': res['enabled'], 'providers': sorted((payload.get('providers') or {}).keys())})
        return {'saved': True, 'restart_needed': True}

    def cloud_models(self, payload):
        """Die Modelle eines Anbieters beim Anbieter abfragen (nur lesen; kein Prompt geht hinaus). Auf Klick, nie automatisch."""
        from .models.cloud_api import provider_models
        pid = payload.get('provider') if isinstance(payload, dict) else None
        cfg = cloud_settings.load_config(self.runtime.project_root)
        if not isinstance(pid, str) or pid not in (cfg.get('providers') or {}) or not cloud_settings.PROVIDER_ID.match(pid):
            raise ValueError('unknown_provider')
        models = provider_models(cfg, pid, os.environ, self.runtime.cloud_key_store)
        self.runtime.audit.append('CLOUD_MODELS_QUERIED', component='desk', payload={'provider': pid, 'count': len(models)})
        from . import modell_zustand
        return {'provider': pid, 'models': models, 'zustand': modell_zustand.fuer_anbieter(self.runtime.project_root, pid)}

    def _labor_provider(self, payload):
        pid = payload.get('provider') if isinstance(payload, dict) else None
        cfg = cloud_settings.load_config(self.runtime.project_root)
        if not isinstance(pid, str) or pid not in (cfg.get('providers') or {}) or not cloud_settings.PROVIDER_ID.match(pid):
            raise ValueError('unknown_provider')
        return cfg, pid

    def labor_connection(self, payload):
        """KI Labor: die Kette vom Schlüssel bis zu einer beantworteten Testnachricht, in Schritten. Auf Klick."""
        from . import labor
        cfg, pid = self._labor_provider(payload)
        res = labor.connection_test(cfg, pid, os.environ, self.runtime.cloud_key_store, audit=self.runtime.audit)
        self.runtime.audit.append('LABOR_CONNECTION_TEST', component='desk', payload={'provider': pid, 'ok': res['ok']})
        return res

    def chat_cloud(self, payload):
        """Das Gespräch mit einem Cloud-Modell, auf Wahl im Gespräch. Geht durch den Inhaltsschutz; nur wenn eingeschaltet.
        Der Text selbst kommt nie ins Audit, nur Anbieter, Modell und Ergebnis."""
        from . import labor
        cfg, pid = self._labor_provider(payload)
        text = str((payload or {}).get('text') or '').strip()
        if not text or len(text) > 4000: raise ValueError('text_invalid')
        history = [h for h in ((payload or {}).get('history') or [])[-10:]
                   if isinstance(h, dict) and h.get('role') in ('user', 'assistant') and isinstance(h.get('content'), str)]
        messages = history + [{'role': 'user', 'content': text}]
        from . import modell_zustand
        modell = str((payload or {}).get('model') or '')
        t0 = time.monotonic()
        try:
            res = labor.cloud_chat(cfg, pid, modell, messages, os.environ, self.runtime.cloud_key_store, audit=self.runtime.audit)
        except Exception:
            # ein Anbieterfehler ist ein Befund über das Modell: rot. Eine Sperre des Inhaltsschutzes ist keiner (siehe unten).
            modell_zustand.merken(self.runtime.project_root, pid, modell, False, (time.monotonic() - t0) * 1000)
            raise
        if res.get('status') == 'completed':
            modell_zustand.merken(self.runtime.project_root, pid, modell, True, (time.monotonic() - t0) * 1000)
        self.runtime.audit.append('CLOUD_CHAT', component='desk', payload={'provider': pid, 'model': res.get('model'), 'status': res.get('status')})
        return res

    def chat_kombi(self, payload):
        """Lokal + KI in einem Fenster: das lokale Modell erstellt den ersten Entwurf (wie im normalen Gespräch), die Cloud prüft
        und verbessert ihn. Beide Schritte gehen durch den Inhaltsschutz. Sperrt der Inhaltsschutz den Cloud-Schritt, bleibt der
        lokale Entwurf, und die Antwort sagt warum. Das Audit enthält nur Anbieter, Modell und Ausgang, nie den Text."""
        from .core.content_guard import ContentGuardStop
        p = payload or {}
        text = str(p.get('text') or '').strip()
        if not text or len(text) > 4000: raise ValueError('text_invalid')
        provider, model = str(p.get('provider') or ''), str(p.get('model') or '')
        if not provider or not model: raise ValueError('cloud_model_required')
        history = (p.get('history') or [])[-8:]
        local = self.chat_reply({'text': text, 'history': history, 'mission_id': p.get('mission_id') or ''})
        if local.get('status') != 'completed':
            return {'status': 'no_local', 'local': None, 'cloud': None, 'reason': local.get('message') or local.get('status')}
        draft = str(local.get('reply') or '')[:3000]
        prompt = ('Aufgabe des Nutzers:\n' + text + '\n\nErster Entwurf des lokalen Modells:\n' + draft +
                  '\n\nPrüfe den Entwurf, verbessere ihn und nenne offene Punkte ausdrücklich als offen.')
        try:
            cloud = self.chat_cloud({'text': prompt, 'history': history, 'provider': provider, 'model': model})
        except ContentGuardStop as exc:
            self.runtime.audit.append('KOMBI_CLOUD_GESPERRT', component='uix', payload={'provider': provider, 'grund': str(exc)[:80]})
            return {'status': 'cloud_gesperrt', 'local': draft, 'cloud': None, 'reason': 'Der Inhaltsschutz hat den Cloud-Schritt gesperrt; der lokale Entwurf bleibt.'}
        except ValueError as exc:
            return {'status': 'cloud_fehler', 'local': draft, 'cloud': None, 'reason': str(exc)[:160]}
        if cloud.get('status') != 'completed':
            # Der Inhaltsschutz sperrt meist als Ergebnis, nicht als Ausnahme (labor.cloud_chat): dann bleibt der lokale Entwurf
            status = 'cloud_gesperrt' if cloud.get('status') == 'blocked' else 'cloud_fehler'
            self.runtime.audit.append('KOMBI_CLOUD_' + status.upper(), component='uix', payload={'provider': provider, 'grund': ','.join(cloud.get('reasons') or [])[:80]})
            reason = ('Der Inhaltsschutz hat den Cloud-Schritt gesperrt; der lokale Entwurf bleibt.' if status == 'cloud_gesperrt'
                      else 'Der Cloud-Schritt ist nicht gelaufen; der lokale Entwurf bleibt.')
            return {'status': status, 'local': draft, 'cloud': None, 'reason': reason, 'reasons': list(cloud.get('reasons') or [])}
        self.runtime.audit.append('KOMBI_CHAT', component='uix', payload={'provider': provider, 'model': model, 'status': cloud.get('status')})
        return {'status': 'completed', 'local': draft, 'cloud': cloud.get('reply'), 'model': model, 'provider': provider,
                'local_model': local.get('model')}

    # ---- Gedächtnis der Oberfläche (SPEC_DOCK_OHNE_NEUAUFBAU_v1 §9.2, §10) ------------------------------------------------
    # Nichts davon kommt ins Audit außer Zahlen; Inhalte bleiben im Speicher dieses Prozesses.

    def arbeitsstand_view(self):
        """GET /api/arbeitsstand – die offenen Objekte und welches vorn liegt; eine neue Shell übernimmt sie (§10.4)."""
        return self.gedaechtnis.arbeitsstand()

    def arbeitsstand_melden(self, payload, shell=None):
        """POST /api/arbeitsstand {offen, vorn, geschlossen} – eine Shell meldet, was sie offen hat (§10.2)."""
        p = payload if isinstance(payload, dict) else {}
        return self.gedaechtnis.melden(p.get('offen') or [], p.get('vorn'), p.get('geschlossen') or [], shell)

    def gedaechtnis_leeren(self, payload=None):
        """POST /api/arbeitsstand/leeren – „Gedächtnis leeren“ im Umschalter: Arbeitsstand, Ablage und Gesprächsverlauf (§10.5)."""
        zahlen = self.gedaechtnis.leeren()
        self.runtime.audit.append('GEDAECHTNIS_GELEERT', component='uix', payload=zahlen)
        return dict(zahlen, status='geleert')

    def ablage_lesen(self, werkzeug, payload):
        """POST /api/ablage/lesen {objekt} – nur die Einträge des rufenden Werkzeugs (Kopf X-SEDRA-Tool, §10.3)."""
        if not werkzeug: raise ValueError('ablage_nur_fuer_werkzeuge')
        return self.gedaechtnis.ablage_lesen(werkzeug, str((payload or {}).get('objekt') or ''))

    def ablage_schreiben(self, werkzeug, payload):
        """POST /api/ablage/schreiben {objekt, werte} – ersetzt die Werte des rufenden Werkzeugs an diesem Objekt (§10.3)."""
        if not werkzeug: raise ValueError('ablage_nur_fuer_werkzeuge')
        p = payload or {}
        return self.gedaechtnis.ablage_schreiben(werkzeug, str(p.get('objekt') or ''), p.get('werte'))

    def chat_verlauf(self):
        """GET /api/chat/verlauf – was der Captain im Gespräch gefragt und gesehen hat (§9.2)."""
        return self.gedaechtnis.verlauf()

    def chat_verlauf_leeren(self, payload=None):
        n = self.gedaechtnis.verlauf_leeren()
        self.runtime.audit.append('CHAT_VERLAUF_GELEERT', component='uix', payload={'eintraege': n})
        return {'status': 'geleert', 'eintraege': n}

    def _verlauf(self, art, payload, out):
        """Hält fest, was über eine Route des Gesprächs ging – nur über die Route, damit interne Aufrufe (Planungstisch, Kombi)
        nichts doppelt schreiben. Bei der Cloud steht die Antwort nach dem Inhaltsschutz da: das, was der Captain gesehen hat."""
        try:
            p = payload if isinstance(payload, dict) else {}
            text = str(p.get('text') or '').strip()
            o = out if isinstance(out, dict) else {}
            if not text:
                return out
            if art == 'reply' and o.get('status') == 'completed':
                # eine Antwort mit Personenbezug aus dem Wissen bleibt lokal: nach dem Neuladen geht sie in keinen Cloud-Weg (§4.6)
                lokal = 'ja' if (o.get('wissen') or {}).get('personenbezug') else ''
                self.gedaechtnis.verlauf_merken('user', text, nur_lokal=lokal)
                self.gedaechtnis.verlauf_merken('assistant', o.get('reply') or '', o.get('model'), nur_lokal=lokal)
            elif art == 'cloud' and o.get('status') == 'completed':
                self.gedaechtnis.verlauf_merken('user', text)
                self.gedaechtnis.verlauf_merken('assistant', o.get('reply') or '', o.get('model'))
            elif art == 'kombi' and o.get('local'):
                self.gedaechtnis.verlauf_merken('user', text)
                self.gedaechtnis.verlauf_merken('assistant', o.get('cloud') or o.get('local') or '', o.get('model') or o.get('local_model'),
                                                 entwurf=o.get('local') if o.get('cloud') else '', hinweis=o.get('reason') or '')
        except ValueError:
            pass                      # der Verlauf darf eine Antwort nie verhindern
        return out

    def vorarbeiter(self, payload):
        """Vorarbeiter-Aktion aus dem Entwurfsfenster: feste Liste, für Cloud- und lokale Modelle gleich."""
        from . import vorarbeiter
        p = payload if isinstance(payload, dict) else {}
        return vorarbeiter.aktion(self.runtime.project_root, str(p.get('aktion') or ''), p.get('args'), audit=self.runtime.audit)

    def entwurf_save(self, payload):
        from . import entwurf
        p = payload if isinstance(payload, dict) else {}
        name = str(p.get('name') or '') or entwurf.new_name(str(p.get('ext') or 'html'))
        return entwurf.save(self.runtime.project_root, name, p.get('content'))

    def entwurf_read(self, payload):
        from . import entwurf
        return entwurf.read(self.runtime.project_root, str((payload or {}).get('name') or ''))

    def entwurf_list(self, payload=None):
        from . import entwurf
        return {'entwuerfe': entwurf.listing(self.runtime.project_root)}

    def labor_model_test(self, payload):
        """KI Labor: jedes Modell des Anbieters einmal ansprechen. Kostet Anbieter-Tokens; deshalb nur auf Klick."""
        from . import labor
        cfg, pid = self._labor_provider(payload)
        res = labor.model_test(cfg, pid, os.environ, self.runtime.cloud_key_store, audit=self.runtime.audit)
        from . import modell_zustand
        for r in res.get('results') or []:
            # der Test ist ein Befund über jedes Modell: die Auswahl zeigt danach den Stand. Sperren des Inhaltsschutzes zählen nicht.
            if str(r.get('detail') or '').startswith('Inhaltsschutz'): continue
            modell_zustand.merken(self.runtime.project_root, pid, r.get('model') or '', bool(r.get('ok')), r.get('ms') or 0)
        self.runtime.audit.append('LABOR_MODEL_TEST', component='desk', payload={'provider': pid, 'passed': res.get('passed'), 'total': res.get('total')})
        return res

    def cloud_module_model(self, payload):
        """Welches Modell ein Modul nutzt (KI Labor). Provider None löscht die Zuordnung. Wirkt sofort für neue Aufrufe."""
        p = payload if isinstance(payload, dict) else {}
        models = cloud_settings.set_module_model(self.runtime.project_root, str(p.get('module') or ''),
                                                 p.get('provider') or None, p.get('model'))
        self.runtime.audit.append('CLOUD_MODULE_MODEL_SET', component='desk', payload={'module': p.get('module'), 'provider': p.get('provider') or None})
        return {'module_models': models}

    def cloud_key(self, payload):
        pid = payload.get('provider') if isinstance(payload, dict) else None
        known = (cloud_settings.load_config(self.runtime.project_root).get('providers') or {})
        if not isinstance(pid, str) or pid not in known or not cloud_settings.PROVIDER_ID.match(pid): raise ValueError('unknown_provider')
        store = self.runtime.cloud_key_store
        if payload.get('clear'):
            store.delete(pid); action = 'deleted'
        else:
            store.set(pid, cloud_settings.check_key_value(payload.get('value')))
            action = 'stored'
        self.runtime.audit.append('CLOUD_KEY_CHANGED', component='desk', payload={'provider': pid, 'action': action})     # ohne Wert
        return {'provider': pid, 'key': 'gespeichert' if store.has(pid) else 'fehlt', 'restart_needed': True}

    # ---- shared by the gated file changes (switches, routing)
    @staticmethod
    def _file_digest(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest() if Path(path).exists() else None

    def _gate_request(self, title, action, target, binding, risks, context_key):
        """A mission that carries one gate for exactly this change; nothing is written until the Captain approves it."""
        with self.lock:
            m = self.runtime.brain.create_mission(title, None, 'S1')
            gate = self.runtime.guard.create_gate(m['identity']['mission_id'], action, target, risks=risks, rollback_available=True, request_binding=binding)
            m['human_gates']['pending'].append(gate)
            m['context'][context_key] = binding
            self.runtime.missions.save(m)
        return {'mission_id': m['identity']['mission_id'], 'gate': gate, 'binding': binding}

    def _spend_approval(self, m, mission_id, context_key, action, target_of, current_digest):
        """The bound request of a mission, once its single-use approval checks out and the file is still the one the Captain saw."""
        binding = (m.get('context') or {}).get(context_key)
        token = (m.get('execution') or {}).get('approval_token')
        if not binding: raise ValueError('not_a_matching_request')
        if not token: raise ValueError('captain_approval_required')
        if binding['file_sha256'] != current_digest: raise ValueError('file_changed_repeat_request')
        if not self.runtime.guard.authorize(token, mission_id=mission_id, action=action, target=target_of(binding), request_binding=binding)['authorized']:
            raise ValueError('captain_approval_invalid')
        return binding

    # ---- project files (read-only view through the filesystem tool: confined to the project root, guarded, audited)
    HIDDEN_NAMES = frozenset({'__pycache__', '.git', 'node_modules', '.venv', '.mypy_cache', '.pytest_cache'})
    FILE_PREVIEW_BYTES = 100_000

    def _project_path(self, payload):
        project = self.projects.get(payload.get('project_id'))
        sub = payload.get('path') or ''
        if not isinstance(sub, str) or len(sub) > 300 or sub.startswith(('/', '\\')) or ':' in sub: raise ValueError('invalid_path')
        parts = [p for p in sub.replace('\\', '/').split('/') if p not in ('', '.')]
        if '..' in parts: raise ValueError('invalid_path')
        return '/'.join([project['workspace_path'], *parts]), parts

    def project_files(self, payload):
        from .tools.base import ToolError
        rel, parts = self._project_path(payload)
        try:
            out = self.runtime.filesystem_tool.execute('M-UIX-VIEW', 'list_dir', {'path': rel, 'bounded': True, 'limit': 300})
        except ToolError as exc:
            raise ValueError(str(exc))
        if out.get('status') != 'completed': raise ValueError('access_blocked')
        entries = [{'name': e['name'], 'type': e['type'], 'size': e['size']} for e in out['entries']
                   if e['name'] not in self.HIDDEN_NAMES and e['type'] in ('dir', 'file')]
        entries.sort(key=lambda e: (e['type'] != 'dir', e['name'].lower()))
        return {'path': '/'.join(parts), 'entries': entries, 'truncated': bool(out.get('truncated'))}

    def project_file(self, payload):
        from .tools.base import ToolError
        rel, parts = self._project_path(payload)
        if not parts: raise ValueError('invalid_path')
        try:
            out = self.runtime.filesystem_tool.execute('M-UIX-VIEW', 'read_text', {'path': rel, 'max_bytes': self.FILE_PREVIEW_BYTES})
        except ToolError as exc:
            if str(exc) == 'file_not_decodable': return {'path': '/'.join(parts), 'binary': True}
            if str(exc) == 'file_too_large': return {'path': '/'.join(parts), 'too_large': True}
            raise ValueError(str(exc))
        if out.get('status') != 'completed': raise ValueError('access_blocked')
        return {'path': '/'.join(parts), 'content': out['content'], 'bytes': out['bytes']}

    def new_project(self, payload):
        with self.lock: return self.projects.create(payload.get('name'))

    def candidate_operation(self, payload):
        from .selfdev.candidate_tests import run_candidate_tests, verify_candidate_tests
        from .selfdev.candidate_acceptance import command
        op=payload['operation'];mid=payload['mission_id']
        if op=='test':return run_candidate_tests(self.runtime,mid)
        if op=='test-verify':return verify_candidate_tests(self.runtime,mid)
        if op not in {'accept-preview','accept','rollback-preview','rollback'}:raise ValueError('unsupported_candidate_operation')
        return command(self.runtime,mid,op,payload.get('plan'))

    def generate_candidate(self, payload):
        from .selfdev.code_generation import generate
        project=self.projects.get(payload['project_id'])
        with self.lock:
            m=self.runtime.brain.create_mission('Ändere Code als Kandidat: '+str(payload['intent']),inputs=None)
            m['context']['refs']=[{'project_id':project['project_id'],'workspace_path':project['workspace_path']}];self.runtime.missions.save(m)
            # Bound selection is processed by Control Master; model has no tool dispatch.
            out=generate(self.runtime,m,project,payload.get('files'))
        return dict(out,mission_id=m['identity']['mission_id'])

    def audit_view(self):
        """Read-only: chain state plus the newest events without their payloads."""
        audit = self.runtime.audit
        lines = audit.path.read_text(encoding='utf-8').splitlines()[-40:] if audit.path.exists() else []
        events = [json.loads(l) for l in lines if l.strip()]
        return {'chain_ok': audit.verify_chain(),
                'events': [{'event_id': e.get('event_id'), 'timestamp': e.get('timestamp'), 'event_type': e.get('event_type'),
                            'component': (e.get('source') or {}).get('component'), 'mission_id': (e.get('source') or {}).get('mission_id')}
                           for e in events]}

    # ---- models and routing profile (read, load, unload, switch profile)
    LEASE_OWNER = 'guppi-uix'

    def models_view(self):
        rt = self.runtime
        router = rt.role_router
        managed = rt.llama_server.status() if getattr(rt, 'llama_server', None) else None
        loaded_key = (managed or {}).get('model') if (managed or {}).get('running') else None
        recipes = []
        for r in (router.config.recipes if router is not None else []):
            ctx = (r.get('profile') or {}).get('context') or {}
            recipes.append({'id': r['id'], 'model': r['model'], 'roles': r['roles'], 'provider': r['provider'], 'enabled': r['enabled'],
                            'location': r['location'], 'size_gb': r.get('model_size_gb'), 'min_vram_gb': r.get('min_vram_gb'),
                            'context_recommended': ctx.get('recommended'), 'context_maximum': ctx.get('maximum'),
                            'loaded': bool(loaded_key and r['provider'] == 'llama-cpp-server' and r['model'] == loaded_key)})
        holder = self.lab.holder()
        profiles = rt.routing_profiles.view() if rt.routing_profiles else None
        return {'recipes': recipes, 'zuletzt': self._last_recipe(),
                'server': managed,
                'lease': ({'owner': holder['owner'], 'purpose': holder['purpose'], 'stale': holder['stale'], 'mine': self._lease_is_mine(holder)}
                          if holder else None),
                'profiles': ({'active': profiles['active'], 'items': {n: {'description': p.get('description', ''), **{k: (v.get('prefer') or []) for k, v in p.items() if isinstance(v, dict)}}
                                                                       for n, p in profiles['profiles'].items()}} if profiles else None),
                'loader_enabled': bool(getattr(rt, 'model_loader', None) and rt.model_loader.enabled),
                'open_requests': self._open_requests()}

    # ---- Standardtest (models/standard_test.py): stability, token speed, read/write speed and coder power of the loaded model.
    # Only one test at a time; it reloads the model with other contexts; the result is a recommendation (see standard_test_apply in the UI).
    def standard_test_status(self):
        return dict(self.__dict__.get('std_test') or {'state': 'bereit'})

    def standard_test_start(self, payload):
        from .models import standard_test as stest
        duration, criteria = payload.get('duration'), payload.get('criteria')
        if not isinstance(criteria, list): raise ValueError('criteria_required')
        with self.lock:
            if (self.__dict__.get('std_test') or {}).get('state') == 'läuft': raise ValueError('standard_test_running')
            server = getattr(self.runtime, 'llama_server', None)
            loaded = server.loaded_models() if server is not None else []
            if not loaded: raise ValueError('no_model_loaded')
            key = loaded[0].get('modelKey')
            recipe = next((r for r in self._routing_recipes() if r.get('model') == key and r.get('provider') == 'llama-cpp-server'), None)
            if recipe is None: raise ValueError('recipe_for_model_missing')
            ctx = (recipe.get('profile') or {}).get('context') or {}
            test_plan = stest.plan(duration, criteria, ctx.get('tiers') or [], ctx.get('recommended'))
            self.std_test = {'state': 'läuft', 'duration': duration, 'recipe_id': recipe['id'], 'model': key, 'progress': [], 'plan': test_plan}
        threading.Thread(target=self._standard_test_worker, args=(key, recipe['id'], test_plan), daemon=True).start()
        return self.standard_test_status()

    def _standard_test_worker(self, key, recipe_id, test_plan):
        from .models import standard_test as stest
        server = self.runtime.llama_server
        adapter = self.runtime.model_router.adapters['llama-cpp-server']
        def post(path, body): return adapter._request('POST', path, body)
        def reload(ctx):
            try:
                server.unload_model(all_models=True)
                server.load_model(key, context_length=ctx)
                return bool(server.loaded_models())
            except Exception: return False
        def progress(p): self.std_test['progress'].append(p)
        try:
            out = stest.run(test_plan, post, reload, on_progress=progress)
            out.update(recipe_id=recipe_id, model=key, finished_at=utcnow())
            folder = self.runtime.project_root / 'runtime_data' / 'standard_tests'
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{recipe_id}-{int(time.time())}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
            self.runtime.audit.append('UIX_STANDARD_TEST', component='uix', payload={'recipe_id': recipe_id, 'duration': test_plan['duration'], 'recommendation': out['recommendation']})
            self.std_test.update(state='fertig', result=out)
        except Exception as exc:
            self.std_test.update(state='fehler', error=type(exc).__name__)

    # ---- read-only views for the chat tools (chat_tools.py): projects, cards (missions), the audit log and the docs of this package
    DOCS_DIR = Path(__file__).resolve().parents[3] / 'docs'

    def chat_projects(self):
        return [{'name': p.get('display_name'), 'id': p.get('project_id')} for p in self.projects.list()][:50]

    def chat_missions(self, limit):
        return [_compact_mission(m) for m in self.runtime.missions.list()[:limit]]

    def chat_audit(self, limit):
        lines = Path(self.runtime.audit.path).read_text(encoding='utf-8', errors='replace').splitlines()[-limit:]
        out = []
        for line in lines:
            try: e = json.loads(line)
            except ValueError: continue
            out.append({'time': e.get('timestamp'), 'event': e.get('event_type'), 'component': (e.get('source') or {}).get('component')})
        return out

    def chat_docs(self):
        return sorted(p.name for p in self.DOCS_DIR.glob('*.md'))

    def chat_doc(self, name):
        if not isinstance(name, str) or '/' in name or '\\' in name or not name.endswith('.md'): raise ValueError('doc_name_invalid')
        path = self.DOCS_DIR / name
        if not path.is_file(): raise ValueError('doc_not_found')
        return path.read_text(encoding='utf-8', errors='replace')[:6000]

    def _start_lease_beat(self):
        stop = threading.Event()
        self._beat_stop = stop
        token = self.gpu_token

        def beat():
            while not stop.wait(30):
                if not self.lab.heartbeat(token):        # taken over: stop pretending we own the GPU
                    self.gpu_token = None
                    return
                server = getattr(self.runtime, 'llama_server', None)
                if server is not None and not server.loaded_models():    # the server ended on its own: give the GPU back
                    with self.model_lock:
                        self._release_gpu()
                    return
        threading.Thread(target=beat, daemon=True).start()

    def _scheduler(self):
        """The model scheduler when it is on (Spec 2, D2.6): then the workshop goes through it and holds no lease of its own. None: as before (D2.1)."""
        sched = getattr(self.runtime, 'model_scheduler', None)
        return sched if sched is not None and sched.enabled else None

    def _lease_is_mine(self, holder):
        sched = self._scheduler()
        if sched is not None: return holder['owner'] == sched.owner
        return self.gpu_token is not None and holder['owner'] == self.LEASE_OWNER

    def _release_gpu(self):
        if self._beat_stop is not None:
            self._beat_stop.set(); self._beat_stop = None
        if self.gpu_token is not None:
            self.lab.release(self.gpu_token); self.gpu_token = None

    def _last_file(self):
        return Path(self.runtime.project_root) / 'local_config' / 'zuletzt_geladen.json'

    def _last_recipe(self):
        # das zuletzt erfolgreich geladene Rezept; fehlt die Datei oder ist sie kaputt, gibt es keine Vorgabe
        try: return str(json.loads(self._last_file().read_text(encoding='utf-8')).get('recipe_id') or '')
        except Exception: return ''

    def _remember_recipe(self, recipe_id):
        try:
            path = self._last_file(); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'recipe_id': recipe_id}, ensure_ascii=False), encoding='utf-8')
        except Exception: pass                                  # die Merkhilfe darf das Laden nicht verhindern

    def _log_load_failure(self, recipe_id, resolution, exc):
        # Ein Fehlschlag mit allem, was man zur Ursache braucht: Rezept, geprüfter Pfad, ob die Datei da ist, Ausnahme
        try:
            # 2026-10-16: the server profile is in load_profile; 'profile' is the routing profile's NAME, so this lookup always logged gguf ''
            server = ((resolution or {}).get('load_profile') or {}).get('server') or {}
            gguf = str(server.get('gguf') or '')
            self.runtime.audit.append('MODEL_LOAD_FAILED', component='uix', payload={
                'recipe_id': recipe_id, 'gguf': gguf, 'gguf_exists': bool(gguf) and Path(gguf).is_file(),
                'provider': (resolution or {}).get('provider_ref'), 'exception': type(exc).__name__, 'detail': str(exc)[:300]})
        except Exception:
            pass                                                    # das Protokoll darf das Laden nicht zusätzlich brechen

    def load_model(self, payload):
        recipe_id = payload.get('recipe_id') or self._last_recipe()          # ohne Auswahl: das zuletzt geladene Modell
        if not isinstance(recipe_id, str) or not recipe_id: raise ValueError('recipe_id_required')
        rt = self.runtime
        if rt.role_router is None or getattr(rt, 'model_loader', None) is None or not rt.model_loader.enabled: raise ValueError('model_loader_unavailable')
        from .models.role_routing import ResolutionError
        sched = self._scheduler()
        if sched is not None: return self._load_via_scheduler(sched, recipe_id)
        with self.model_lock:
            try: resolution = rt.role_router.resolve_recipe(recipe_id)
            except ResolutionError as exc:
                # A switch: the model this UIX loaded still holds the VRAM the new one needs. Free it and check again; if the new model
                # is still not usable, the old one stays unloaded (the caller is told).
                server = getattr(rt, 'llama_server', None)
                if 'hardware_pressure' in str(exc) and self.gpu_token is not None and server is not None and server.loaded_models():
                    server.unload_model(all_models=True); time.sleep(2)
                    try: resolution = rt.role_router.resolve_recipe(recipe_id)
                    except ResolutionError as again: raise ValueError(f'recipe_not_usable:{again}')
                else: raise ValueError(f'recipe_not_usable:{exc}')
            took_lease = self.gpu_token is None
            if took_lease:
                token = self.lab.try_acquire(self.LEASE_OWNER, f'Modell {recipe_id} (UIX)', ttl_s=600)
                if token is None:
                    h = self.lab.holder() or {}
                    raise ValueError(f"gpu_lease_busy:{h.get('owner')}:{h.get('purpose')}")
                self.gpu_token = token; self._start_lease_beat()
            try:
                server = getattr(rt, 'llama_server', None)
                if server is not None and server.loaded_models() and resolution['provider_ref'] == 'llama-cpp-server':
                    server.unload_model(all_models=True)          # one model on the GPU at a time
                out = rt.model_loader.ensure(resolution)
            except LoadError as exc:
                self._log_load_failure(recipe_id, resolution, exc)
                self._release_gpu() if not (getattr(rt, 'llama_server', None) and rt.llama_server.loaded_models()) else None
                raise ValueError(str(exc))
            except Exception as exc:
                self._log_load_failure(recipe_id, resolution, exc)
                self._release_gpu()
                raise
            self._remember_recipe(recipe_id)
        return dict(out, recipe_id=recipe_id)

    def _load_via_scheduler(self, sched, recipe_id):
        """Werkstatt `model laden` with the scheduler on (D2.6): `ensure_server`, no lease and no beat of this process (SCH-11)."""
        from .jobs.model_scheduler import SchedulerError
        from .models.role_routing import ResolutionError
        rt = self.runtime
        with self.model_lock:
            view = sched.view()
            running = view.get('modell')
            if running and running != recipe_id and (view.get('server') or {}).get('state') == 'bereit':      # in drain/exklusiv/gesperrt `ensure_server` says no
                # A switch: the Captain asked for another model, so the running one goes first (not while runs are active).
                stopped = sched.stop_server(owner='werkstatt')
                if stopped['status'] == 'leases_active': raise ValueError('leases_active:' + ','.join(stopped['active']))
                time.sleep(2)
            try: resolution = rt.role_router.resolve_recipe(recipe_id)
            except ResolutionError as exc: raise ValueError(f'recipe_not_usable:{exc}')
            try: out = sched.ensure_server(resolution, owner='werkstatt')
            except SchedulerError as exc:
                self._log_load_failure(recipe_id, resolution, exc)
                raise ValueError(exc.reason)
            self._remember_recipe(recipe_id)
        return dict(out['load'], recipe_id=recipe_id)

    def unload_model(self, payload):
        sched = self._scheduler()
        if sched is not None:
            # `erzwingen` (the Captain's button) marks the active leases `unterbrochen` and stops the server; without it, active runs only give a hint.
            with self.model_lock:
                out = sched.stop_server(owner='werkstatt', force=payload.get('erzwingen') is True)
            if out['status'] == 'leases_active': raise ValueError('leases_active:' + ','.join(out['active']))
            if out['status'] == 'gesperrt': raise ValueError('server_gesperrt')
            return {'status': 'unloaded', 'detail': out['status'], 'interrupted': out['interrupted']}
        server = getattr(self.runtime, 'llama_server', None)
        with self.model_lock:
            out = server.unload_model(all_models=True) if server is not None else {'output': 'no managed server'}
            self._release_gpu()
        return {'status': 'unloaded', 'detail': out.get('output')}

    def use_profile(self, payload):
        name = payload.get('name')
        profiles = self.runtime.routing_profiles
        if not isinstance(name, str) or not name or profiles is None: raise ValueError('routing_profile_required')
        try: profiles.use(name)
        except Exception as exc: raise ValueError(str(exc))
        self.runtime.audit.append('ROUTING_PROFILE_CHANGED', component='uix', payload={'profile': name})
        return {'active': profiles.active}

    # ---- what runs on this PC: llama-servers, GUPPI runs, supervisor jobs; and stopping them on the Captain's request
    def _process_rows(self):
        script = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -in 'llama-server.exe','python.exe','pythonw.exe' } | "
                  "Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine,@{n='Started';e={$_.CreationDate.ToString('s')}} | ConvertTo-Json -Compress")
        text = gpu_preflight._powershell(script, self._run)
        data = json.loads(text) if text else []
        return data if isinstance(data, list) else [data]

    @staticmethod
    def _short(cmd, limit=170):
        """The command line without the interpreter path: what the process is doing."""
        cmd = (cmd or '').strip()
        if cmd.startswith('"') and cmd.count('"') >= 2: rest = cmd.split('"', 2)[2]
        else: rest = cmd.split(' ', 1)[1] if ' ' in cmd else cmd
        return rest.strip().replace(chr(92), '/')[:limit]

    def processes_view(self):
        rt = self.runtime
        try:
            rows = self._process_rows()
        except FileNotFoundError:        # no PowerShell (macOS, Linux): the window says so instead of showing an error
            managed = rt.llama_server.status() if getattr(rt, 'llama_server', None) else {}
            servers = [{'pid': managed.get('pid'), 'alias': managed.get('model') or '?', 'port': managed.get('port'), 'context': managed.get('context'), 'started': None, 'ours': True, 'parent_pid': None, 'parent': None}] if managed.get('running') else []
            return {'servers': servers, 'runs': [], 'jobs': [], 'expected': [], 'mismatch': False, 'vram_used_gb': None,
                    'note': 'Die Liste fremder Prozesse gibt es nur unter Windows; hier erscheint nur der eigene Modell-Server.'}
        by_pid = {int(r['ProcessId']): r for r in rows}
        managed = rt.llama_server.status() if getattr(rt, 'llama_server', None) else {}
        own_pid = managed.get('pid') if managed.get('running') else None
        runtime_root = str(Path(__file__).resolve().parents[2]).lower().replace('/', '\\')
        servers, runs = [], []
        for r in rows:
            pid = int(r['ProcessId']); cmd = r.get('CommandLine') or ''
            info = {'name': r.get('Name') or '', 'path': r.get('ExecutablePath') or '', 'cmd': cmd}
            parent = by_pid.get(int(r.get('ParentProcessId') or 0))
            if info['name'].lower() == 'llama-server.exe':
                if not gpu_preflight.is_guppi_server(info): continue       # LM Studio's own engine and others are never listed
                toks = cmd.split()
                def opt(flag):
                    return toks[toks.index(flag) + 1] if flag in toks and toks.index(flag) + 1 < len(toks) else None
                servers.append({'pid': pid, 'alias': opt('--alias') or '?', 'port': opt('--port'), 'context': opt('-c'), 'started': r.get('Started'),
                                'ours': pid == own_pid, 'parent_pid': parent and int(parent['ProcessId']),
                                'parent': self._short(parent.get('CommandLine')) if parent else None})
            elif pid != os.getpid() and runtime_root in cmd.lower().replace('/', '\\') and any(k in cmd for k in ('benchmarks', 'job_worker', 'e1_golden')) and 'uix_server' not in cmd:
                runs.append({'pid': pid, 'cmd': self._short(cmd), 'started': r.get('Started')})
        jobs = []
        sup = getattr(rt, 'job_supervisor', None)
        if sup is not None:
            try:
                jobs = [j for j in sup.view()['jobs'] if j['state'] not in FINAL_STATES]
            except Exception:
                jobs = []
        # what the active routing profile wants on the GPU, against what is there
        expected = []
        profiles, router = rt.routing_profiles, rt.role_router
        if profiles is not None and profiles.active and router is not None:
            models = {r['id']: r['model'] for r in router.config.recipes}
            for purpose in ('coder', 'verifier'):
                for rid in profiles.prefer(purpose)[:1]:
                    expected.append({'purpose': purpose, 'recipe_id': rid, 'model': models.get(rid)})
        loaded = [s['alias'] for s in servers]
        mismatch = bool(loaded) and bool(expected) and not any(e['model'] in loaded for e in expected)
        try: vram = gpu_preflight.vram_used_gb(self._run)
        except Exception: vram = None
        view = {'servers': servers, 'runs': runs, 'jobs': jobs, 'expected': expected, 'mismatch': mismatch, 'vram_used_gb': vram}
        if sys.platform != 'win32' and self._run is subprocess.run:      # no PowerShell inventory: say so instead of showing an empty list as the truth
            view['note'] = 'Die Liste fremder Prozesse gibt es nur unter Windows; hier erscheint nur der eigene Modell-Server.'
        return view

    def _still_running(self, pid, started):
        try: rows = self._process_rows()
        except Exception: return False
        return any(int(r['ProcessId']) == pid and r.get('Started') == started for r in rows)

    def stop_process(self, payload):
        pid = payload.get('pid')
        if type(pid) is not int or payload.get('confirm') is not True: raise ValueError('pid_and_confirm_required')
        view = self.processes_view()
        server = next((s for s in view['servers'] if s['pid'] == pid), None)
        run = next((r for r in view['runs'] if r['pid'] == pid), None)
        if server is None and run is None: raise ValueError('pid_not_stoppable')       # only GUPPI's own llama-servers and runs, never an arbitrary pid
        stopped = []
        with self.model_lock:
            # The pid was read a moment ago; Windows reuses pids. Kill only a process that still started at the same time as the one listed.
            if not self._still_running(pid, (server or run).get('started')): raise ValueError('process_changed_or_gone')
            if server is not None and server['ours']:
                self.runtime.llama_server.unload_model(all_models=True); self._release_gpu(); stopped.append(pid)
            else:
                if run is not None:      # a run takes the servers it started down with it, otherwise they stay on the GPU
                    for s in view['servers']:
                        if s['parent_pid'] == pid and not s['ours']:
                            gpu_preflight._stop(s['pid'], self._run); stopped.append(s['pid'])
                gpu_preflight._stop(pid, self._run); stopped.append(pid)
        self.runtime.audit.append('UIX_PROCESS_STOPPED', component='uix', payload={'pid': pid, 'kind': 'server' if server else 'run', 'stopped': stopped,
                                                                                    'what': (server or run).get('alias') or (server or run).get('cmd')})
        return {'status': 'stopped', 'stopped': stopped}

    def cancel_job(self, payload):
        job_id = payload.get('job_id')
        sup = getattr(self.runtime, 'job_supervisor', None)
        if not isinstance(job_id, str) or not job_id or sup is None: raise ValueError('job_id_required')
        try: out = sup.cancel(job_id, requested_by='captain-uix', reason='cancelled in the UIX')
        except JobError as exc: raise ValueError(str(exc))
        return {'status': out['status']}

    # ---- rework watch (plan 2026-10-04): a rework that keeps failing for the same cause waits for the Captain's hint
    def _e1_states(self):
        base = self.project_root / 'runtime_data' / 'e1_golden_path'
        for path in sorted(base.glob('**/state.json')) if base.is_dir() else []:
            try: state = load_json(path, {})
            except Exception: continue
            if isinstance(state, dict) and state.get('job_id') and state.get('rework_watch'):
                yield path, state

    def _stalled_supervisor_jobs(self):
        sup = getattr(self.runtime, 'job_supervisor', None)
        if sup is None: return []
        try: jobs, _ = sup.store.scan()
        except Exception: return []
        return [j for j in jobs if j.get('state') == 'BLOCKED' and (j.get('supervisor_flags') or {}).get('escalated_to') == 'captain'
                and (j.get('last_error') or {}).get('reason_code') == 'rework_stalled']

    def meter_view(self):
        """Read-only. Guppy meter: lines of code written by GUPPI and by Claude (git log of the project folder and the build candidates)."""
        from .agent_manager.meter_service import meter_view
        return meter_view(Path(__file__).resolve().parents[3], self.project_root)

    def agents_view(self):
        """Read-only. Agent manager: imported templates (always UNVERIFIED) and assignments of the fake runtime, marked as demo."""
        from .agent_manager.view import agents_view
        return agents_view(self.project_root / 'runtime_data' / 'agent_manager' / 'registry.sqlite')

    def rework_view(self):
        """Read-only. Every job whose rework the watch has stopped, with what it saw and the hint already given."""
        stalled = []
        for job in self._stalled_supervisor_jobs():
            retry = job.get('retry') or {}
            verdict = ReworkWatch(retry.get('watch')).check(retry.get('captain_hint'))
            stalled.append({'kind': 'supervisor', 'job_id': job['job_id'], 'detector': verdict['detector'], 'count': verdict['count'],
                            'failure': verdict['repeated_failure'], 'hint': retry.get('captain_hint')})
        for path, state in self._e1_states():
            verdict = ReworkWatch.load(state).check(state.get('captain_hint'))
            if not verdict['stuck']: continue
            try:
                if self.runtime.self_development.jobs.load(state['job_id'])['state'] in FINAL_STATES | {'ACTIVATED'}: continue
            except Exception: pass
            stalled.append({'kind': 'e1', 'job_id': state['job_id'], 'scenario': state.get('scenario'), 'detector': verdict['detector'],
                            'count': verdict['count'], 'failure': verdict['repeated_failure'], 'hint': state.get('captain_hint')})
        return {'stalled': stalled}

    def rework_hint(self, payload):
        """The Captain's hint for a stalled rework. A supervisor job returns to REWORK; an E1 run gets `captain_hint` in its state, which
        lets the next `generate` run. Anything that is not stalled is refused."""
        job_id, text = payload.get('job_id'), payload.get('text')
        if not isinstance(job_id, str) or not job_id: raise ValueError('job_id_required')
        if not isinstance(text, str) or not text.strip() or len(text) > 2000: raise ValueError('invalid_hint')
        text = text.strip()
        with self.lock:
            if any(j['job_id'] == job_id for j in self._stalled_supervisor_jobs()):
                try: self.runtime.job_supervisor.give_hint(job_id, text, resolved_by='captain-uix')
                except JobError as exc: raise ValueError(str(exc))
                kind = 'supervisor'
            else:
                found = next(((path, state) for path, state in self._e1_states() if state['job_id'] == job_id
                              and ReworkWatch.load(state).check(state.get('captain_hint'))['stuck']), None)
                if found is None: raise ValueError('no_stalled_rework')
                path, state = found
                if text == (state.get('captain_hint') or ''): raise ValueError('hint_not_new')
                state['captain_hint'] = text
                atomic_write_json(path, state)
                kind = 'e1'
            self.runtime.audit.append('UIX_REWORK_HINT_GIVEN', component='uix', payload={'job_id': job_id, 'kind': kind, 'chars': len(text)})
        return {'status': 'hint_given', 'kind': kind, 'job_id': job_id}

    def close(self):
        """Window closed: a model this UIX loaded is not left on the GPU, and the lease goes back."""
        self.poller.stop()
        sched = self._scheduler()
        if sched is not None:                                # the scheduler's server does not outlive the window while no run needs it
            try: sched.stop_server(owner='werkstatt-close')
            except Exception: pass
        if self.gpu_token is not None:                       # only the path without the scheduler holds its own lease
            try: self.unload_model({})
            except Exception: self._release_gpu()
        for key in ('_gw_wissen', '_arbeitsplatz'):          # die Wissensdateien sauber schließen (Build 24)
            w = self.__dict__.get(key)
            if w is not None:
                try: w.close()
                except Exception: pass
        if getattr(self.runtime, 'wissen', None) is not None:    # Spec 7: Takt und eigener Embedding-Server enden mit der Oberfläche
            try: self.runtime.wissen.schliessen()
            except Exception: pass

    def dev_environment(self):
        rt = self.runtime
        return {
            'doctor': rt.sandbox.doctor(),
            'history': rt.sandbox.history()[-20:],
            'ui_name': 'SEDRA Entwicklungsumgebung',
            'technical_backend': 'sandbox',
        }


STATIC_FILE = re.compile(r'/uix/(css|js)/([a-z_]+)\.\1')
STATIC_TYPES = {'css': 'text/css; charset=utf-8', 'js': 'text/javascript; charset=utf-8'}
# Files of the desktop modules (Build 7): /uix/ui/<file>, /uix/ui/schema/<file>, /uix/shells/<id>/<file>, /uix/tools/<id>/<file>
MODULE_FILE = re.compile(r'/uix/(ui|shells|tools)/(?:([a-z0-9_-]{2,40})/)?([a-z0-9_.-]{1,60})')
FRAME_PAGE = re.compile(r'/uix/frame/([a-z0-9-]{2,40})')


def make_server(hub: UIXHub, port=0):
    token = secrets.token_urlsafe(32)
    # Spec 0 (D2): je externem Client ein eigener Token; die Zuordnung Token → Client steht nur hier im Speicher.
    client_tokens = {c: secrets.token_urlsafe(32) for c in uix_clients.CLIENTS}
    html_path = Path(__file__).parent / 'uix' / 'desk.html'
    html = html_path.read_bytes()
    retro_html = (Path(__file__).parent / 'uix' / 'retro_desktop.html').read_bytes()     # Build 6's desktop, kept in the archive under /retro
    hardware_html = (Path(__file__).parent / 'hardware_manager' / 'dashboard.html').read_bytes()    # the Hardware Manager view, shown in a UIX window

    class Handler(BaseHTTPRequestHandler):
        server_version = 'GUPPI-UIX/1.0'
        timeout = 30          # a client that stops sending does not keep a thread forever (hardening 2026-10-14)

        def log_message(self, *_args):
            pass

        def _same_origin_ok(self):
            host = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != host:
                return False
            origin = self.headers.get('Origin')
            return not origin or origin == 'http://' + host

        def _authorized(self):
            supplied = self.headers.get('X-GUPPI-Token', '')
            if not supplied and urlsplit(self.path).path == '/api/events':
                # EventSource cannot send headers; for this one read-only stream the token may ride in the query. It never leaves the
                # machine (loopback, Referrer-Policy: no-referrer) and opens nothing a GET route would not.
                supplied = parse_qs(urlsplit(self.path).query).get('token', [''])[0]
            if not supplied:
                return None
            if hmac.compare_digest(supplied, token):
                return 'browser'
            return next((c for c, t in client_tokens.items() if hmac.compare_digest(supplied, t)), None)

        def _client(self, token_class):
            """Die Herkunft für das Audit: `shell`, `chat`, `cli` oder `mcp`. Gerufen erst nach `_module_allowed`: ein Kopf
            `X-SEDRA-Tool`, der bis hierher kommt, hat die Allowlist für genau diese Route bestanden."""
            tool = self.headers.get('X-SEDRA-Tool')
            return desk_kinds.client_for(token_class, tool, tool_ok=bool(tool))

        def _module_allowed(self, method, path):
            """A call that names its module (X-SEDRA-Tool / X-SEDRA-Shell) may only use the routes of that manifest (§6).
            Without such a header the call comes from the shell's own page and is checked by token and origin as before."""
            for header, kind in (('X-SEDRA-Tool', 'tool'), ('X-SEDRA-Shell', 'shell')):
                module = self.headers.get(header)
                if not module:
                    continue
                if not hub.gateway.allowed(kind, module, method, path):
                    hub.runtime.audit.append('UIX_TOOL_DENIED', component='desk',
                                             payload={'kind': kind, 'module': module[:40], 'method': method, 'path': path[:120]})
                    self._send(403, {'error': 'tool_route_not_allowed', 'message': f'Das Werkzeug „{module[:40]}“ darf {method} {path} nicht aufrufen.'})
                    return False
            return True

        def _module_file(self, path):
            """Serves a file of ui/, a shell or a tool; returns True when it answered."""
            m = MODULE_FILE.fullmatch(path)
            if not m:
                return False
            file = hub.gateway.file(m.group(1), m.group(2), m.group(3))
            if file is None:
                self.send_error(404)
                return True
            from .desk.gateway import SERVE_TYPES
            self._send(200, file.read_bytes(), SERVE_TYPES[file.suffix.lstrip('.')])
            return True

        def _events(self):
            """/api/events: one Server-Sent-Events stream for every tool (§10.4). Reconnect with Last-Event-ID."""
            try:
                last = int(parse_qs(urlsplit(self.path).query).get('last', [''])[0] or self.headers.get('Last-Event-ID') or 0)
            except ValueError:
                last = 0
            self.send_response(200)
            for name, value in (('Content-Type', 'text/event-stream; charset=utf-8'), ('Cache-Control', 'no-store'), ('X-Accel-Buffering', 'no'),
                                ('Connection', 'close'), ('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'no-referrer')):
                self.send_header(name, value)
            self.end_headers()
            hub.poller.start()
            self.connection.settimeout(None)
            from .desk.events import stream_to
            try:
                stream_to(self.wfile, hub.events, last, stop=getattr(self.server, 'desk_stop', None))
            except (BrokenPipeError, ConnectionResetError, OSError, ValueError):
                pass                                    # the Captain closed the window or the tab slept: nothing to report

        def _harness(self, method, path, payload=None):
            """/api/harness/… (harness/api.py): die Wege der Harness-Shell; der Strom einer Antwort als SSE wie _events."""
            try:
                out = hub.harness.handle(method, path, urlsplit(self.path).query, payload)
            except ValueError as exc:
                self._send(400, {'error': 'bad_request', 'message': FRIENDLY_400.get(str(exc), str(exc)), 'code': str(exc)})
                return
            except LookupError as exc:
                self._send(404, {'error': 'not_found', 'message': str(exc)})
                return
            except Exception as exc:
                self._send(503, {'error': type(exc).__name__, 'message': str(exc)})
                return
            if out[0] != 'sse':
                self._send(out[0], out[1])
                return
            try:
                last = int(self.headers.get('Last-Event-ID') or out[2] or 0)
            except ValueError:
                last = out[2]
            self.send_response(200)
            for name, value in (('Content-Type', 'text/event-stream; charset=utf-8'), ('Cache-Control', 'no-store'), ('X-Accel-Buffering', 'no'),
                                ('Connection', 'close'), ('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'no-referrer')):
                self.send_header(name, value)
            self.end_headers()
            self.connection.settimeout(None)
            from .harness.strom import schreiben
            try:
                schreiben(self.wfile, out[1], last, stop=getattr(self.server, 'desk_stop', None))
            except (BrokenPipeError, ConnectionResetError, OSError, ValueError):
                pass

        def _harness_write(self, method):
            """PATCH und DELETE gibt es nur für /api/harness/sitzungen/<id> – dieselben Prüfungen wie POST (Herkunft, Token, Allowlist)."""
            path = urlsplit(self.path).path
            if not self._same_origin_ok() or self._authorized() != 'browser':
                self.send_error(403)
                return
            if not path.startswith('/api/harness/'):
                self.send_error(404)
                return
            if not self._module_allowed(method, path):
                return
            try:
                payload = self._json_body() if method == 'PATCH' else {}
            except ValueError as exc:
                self._send(400, {'error': 'bad_request', 'message': str(exc)})
                return
            self._harness(method, path, payload)

        def do_PATCH(self):
            self._harness_write('PATCH')

        def do_DELETE(self):
            self._harness_write('DELETE')

        def _send(self, code, body, kind='application/json; charset=utf-8', frame_self=False):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
            elif isinstance(body, str):
                body = body.encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self' blob: data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors '" + ("self" if frame_self else "none") + "'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _json_body(self):
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= 1024 * 1024 or self.headers.get('Transfer-Encoding'):
                raise ValueError('request_too_large')
            self.connection.settimeout(10)
            raw = self.rfile.read(length)
            if len(raw)!=length: raise ValueError('incomplete_request')
            value = json.loads(raw or b'{}')
            if not isinstance(value, dict):
                raise ValueError('json_object_required')
            return value

        def do_GET(self):
            if not self._same_origin_ok():
                self.send_error(403)
                return
            path = urlsplit(self.path).path
            if path == '/':
                self._send(200, html, 'text/html; charset=utf-8')
                return
            if path == '/retro':          # Build 6's desktop, kept so the Captain can compare; not the way in any more
                self._send(200, retro_html, 'text/html; charset=utf-8')
                return
            static = STATIC_FILE.fullmatch(path)
            if static:           # the page's own styles and scripts (uix/css, uix/js): code only, no data, read at request time
                file = Path(__file__).parent / 'uix' / static.group(1) / (static.group(2) + '.' + static.group(1))
                if not file.is_file():
                    self.send_error(404)
                    return
                self._send(200, file.read_bytes(), STATIC_TYPES[static.group(1)])
                return
            if path == '/hardware':          # the page itself carries no data; its reads need the token like every other API call
                self._send(200, hardware_html, 'text/html; charset=utf-8', frame_self=True)
                return
            # Files of ui/, of the active shell and of the tools: code and styles, never data – and a <script src> cannot carry the
            # token header. Like the page's own uix/css and uix/js they are served before the token check; only registered folders,
            # no '..', and only the file types the gateway allows.
            if self._module_file(path):
                return
            frame = FRAME_PAGE.fullmatch(path)
            if frame:           # Stufe C: die Seite eines abgeschotteten Werkzeug-Rahmens; ohne Token, ohne Daten (siehe desk/gateway.frame_page)
                page = hub.gateway.frame_page(frame.group(1))
                if page is None:
                    self.send_error(404)
                    return
                self._send(200, page, 'text/html; charset=utf-8', frame_self=True)
                return
            if self._authorized() != 'browser':          # CLI- und MCP-Token öffnen keine GET-Route (uix_clients.ROUTES)
                self.send_error(403)
                return
            if not self._module_allowed('GET', path):
                return
            if path == '/api/events':
                self._events()
                return
            if path.startswith('/api/harness/'):          # projekte, sitzungen[/<id>], antworten/<id>/strom (harness/api.py)
                self._harness('GET', path)
                return
            try:
                routes = {
                    '/uix/manifest': hub.gateway.manifest,                  # read-only: active shell and usable tools
                    '/api/decisions': hub.decisions_view,                   # read-only: one list for gates and change requests
                    '/api/strip': hub.strip_view,                           # read-only: the instruments of the Cockpit strip
                    '/api/arbeitsstand': hub.arbeitsstand_view,             # read-only: offene Objekte für die nächste Shell (§10)
                    '/api/chat/verlauf': hub.chat_verlauf,                  # read-only: der Gesprächsverlauf (§9.2), nur im Speicher
                    '/api/boundaries': lambda: hub.boundaries_view(),        # read-only: Modus und Grenzen dieses Projekts
                    '/api/guard/status': hub.guard_status,                  # read-only: der Inhaltsschutz (Build 16) – nie Text
                    '/api/intent/vorlagen': hub.intent_vorlagen,            # read-only: Vorlagen für Vorhaben mit Stufen (19.10.2026)
                    '/api/fisch/rollen': hub.fisch.rollen,                  # read-only: Rollen des Übersetzers (Fisch)
                    '/api/fisch/profil': hub.fisch.profil,                  # read-only: das News-Profil des Projekts (Fisch)
                    '/api/fisch/transkripte': hub.fisch.transkripte,        # read-only: die Transkripte und die Auskunft zum STT-Provider (Fisch)
                    '/api/sprache/status': hub.sprache.status,             # read-only: der STT-Provider dieses Rechners (Kern Sprache)
                    '/api/sprache/aufnahmen': hub.sprache.aufnahmen,       # read-only: die Aufnahmen (ohne Daten)
                    '/api/sprache/kern/stand': hub.sprache.kern_stand,     # read-only: läuft eine Aufnahme im Kern (überlebt den Shell-Wechsel)
                    '/api/gateway/vorgaben': hub.gateway_vorgaben_liste,    # read-only: die gemerkten Vorgaben – das Werkzeug liest sie per GET (tool.yaml), bisher stand die Route nur unter POST
                    '/api/uix/vorgaben': hub.vorgaben_view,                 # read-only: die drei Vorlagen einer Shell aus Vorgabe (Build 17)
                    '/api/gateway/vorgaenge': hub.gateway_list,             # read-only: Vorgänge, Vorgaben, Textdateien des Projekts (Build 19)
                    '/api/projects': hub.projects.list,
                    '/api/status': hub.status,
                    '/api/missions': hub.missions,
                    '/api/dev-environment': hub.dev_environment,
                    # Hardware Manager, read-only (same routes and shapes as its own dashboard server; no route can change hardware)
                    '/api/state': lambda: {'state': hub.runtime.hardware_manager.get_state(), 'history': hub.runtime.hardware_manager.history(120)},
                    '/api/inventory': hub.runtime.hardware_manager.inventory,
                    '/api/profiles': hub.runtime.hardware_manager.profiles,
                    '/api/capabilities': hub.runtime.hardware_manager.capabilities,
                    '/api/audit': hub.audit_view,                           # read-only
                    '/api/switches': hub.switches_view,                     # read-only
                    '/api/cloud': hub.cloud_view,                           # read-only: Einstellungen Cloud-Modelle, ohne Schlüssel
                    '/api/labor/runs': lambda: {'runs': labor_runs.list_runs(hub.runtime.project_root)},   # read-only: was die Läufe tun
                    '/api/routing-config': hub.routing_config_view,         # read-only
                    '/api/models': hub.models_view,                         # read-only
                    '/api/standard-test': hub.standard_test_status,         # read-only: progress and result of the Standardtest
                    '/api/processes': hub.processes_view,                   # read-only
                    '/api/rework': hub.rework_view,                         # read-only
                    '/api/agents': hub.agents_view,                         # read-only
                    '/api/meter': hub.meter_view,                           # read-only
                    '/api/library': hub.library.view,                       # read-only: own capabilities, libraries, the Captain's skills (Bibliothek window)
                    '/api/diagnose': lambda: uix_diag.view(hub),            # read-only
                    '/api/skills': lambda: {k: v.get('data', {}) for k, v in hub.runtime.registry.skills.items()},
                    '/api/tools': hub.runtime.tools.list,
                    '/api/topics': hub.runtime.capability_router.topic_catalog,
                    '/api/self-development': hub.runtime.self_development.view,
                    '/api/supervisor': hub.runtime.job_supervisor_status,   # read-only
                    '/api/context': hub.runtime.context_status,             # read-only
                    '/api/routing': hub.runtime.routing_status,             # read-only
                    '/api/permissions': hub.runtime.permission_status,      # read-only
                    '/api/resources': hub.runtime.resource_status,          # read-only
                    '/api/uix/modules': hub.modules_view,                   # read-only: Shell, Werkzeuge, Abgelehnte, Vorlagen
                    '/api/uix/shelf': hub.shelf_view,                       # read-only: die eigenen Ablagen je Shell (Build 19)
                }
                fn = routes.get(path)
                if fn is None:
                    self.send_error(404)
                    return
                self._send(200, fn())
            except Exception as exc:
                self._send(503, {'error': type(exc).__name__, 'message': str(exc)})

        def do_POST(self):
            token_class = self._authorized() if self._same_origin_ok() else None
            path = urlsplit(self.path).path
            if token_class is None or (token_class != 'browser' and path not in uix_clients.ROUTES):
                self.send_error(403)
                return
            if not self._module_allowed('POST', path):
                return
            try:
                payload = self._json_body()
                if path.startswith('/api/harness/'):      # sitzungen, sitzungen/<id>/nachricht, antworten/<id>/stopp (harness/api.py)
                    self._harness('POST', path, payload)
                    return
                client = self._client(token_class)
                if path in uix_clients.ROUTES and isinstance(payload, dict) and 'client' in payload:
                    hub.runtime.audit.append('UIX_CLIENT_REFUSED', component='desk', payload={'path': path, 'client': client})
                    desk_kinds.refuse_client_field(payload)     # 400 client_is_set_by_server
                routes = {
                    '/api/decisions/answer': hub.decide,
                    '/api/objects': hub.objects_view,               # read-only: ein Objekt oder die Liste eines Typs (§10.1)
                    '/api/actions': lambda p: hub.act(p, client=client),   # Verben statt Routen (§10.2); die Gates darunter bleiben
                    '/api/live': hub.live_view,                     # read-only: die Zeilen einer Aufgabe
                    '/api/candidate/diff': hub.candidate_diff,      # read-only: alter und neuer Text der Kandidatendateien
                    '/api/candidate/report': hub.candidate_report,  # read-only: Nachweise aus candidate-report.json
                    '/api/cost': hub.cost_view,                     # read-only: Token und Aufrufe dieser Aufgabe
                    '/api/intent/create': hub.intent_create,        # ein Vorhaben anlegen – ohne Gate, es führt nichts aus
                    '/api/boundaries': hub.boundaries_view,         # read-only: Modus und Grenzen (oder der Vorschlag)
                    '/api/boundaries/request': hub.boundaries_request,
                    '/api/boundaries/apply': hub.boundaries_apply,
                    '/api/uix/shell': hub.shell_set,                # eigene Form: Audit, kein Gate
                    '/api/uix/standard': hub.shell_standard,        # zum Standard machen: uix.yaml, ohne Wechsel der Ansicht; Audit
                    '/api/uix/enabled': hub.tool_enabled,
                    '/api/uix/shelf': hub.shelf_save,               # eigene Ablage: Audit, kein Gate (Build 19)
                    '/api/uix/scaffold': hub.module_scaffold,
                    '/api/uix/vorgabe': hub.vorgabe_propose,        # GUPPI schlägt eine Vorgabe vor – legt nichts an
                    '/api/guard/probe': hub.guard_probe,            # read-only in der Sache: prüft nur, ruft kein Modell, speichert nichts
                    '/api/gateway/vorgang': lambda p: hub.gateway_get(str((p or {}).get('id') or '')),   # read-only: ein Vorgang mit Entwurf
                    '/api/gateway/neu': hub.gateway_new,
                    '/api/gateway/vorgaben': hub.gateway_vorgaben_liste,
                    '/api/gateway/vorgabe/merken': hub.gateway_vorgabe_merken,
                    '/api/gateway/vorgabe/loeschen': hub.gateway_vorgabe_loeschen,
                    '/api/update/suche': hub.update_suche,
                    '/api/update/vorschau': hub.update_vorschau,         # lädt in den Staging-Ordner, schreibt nichts ins Programm
                    '/api/update/uebernehmen': hub.update_uebernehmen,   # braucht die Rechte-Bestätigung aus der Vorschau
                    '/api/update/zurueck': hub.update_zurueck,
                    '/api/gateway/vorschau': hub.gateway_vorschau,
                    '/api/gateway/ausgabe': hub.gateway_ausgabe,
                    '/api/gateway/arbeitskopie': hub.gateway_arbeitskopie,
                    '/api/gateway/speichern-unter': hub.gateway_speichern_unter,
                    '/api/gateway/upload': hub.gateway_upload,      # Datei in den Eingang des GateWay legen (ohne Projekt)
                    '/api/gateway/pruefen': hub.gateway_pruefen,    # Datenschutz prüfen: lokal, nichts verlässt den Rechner
                    '/api/gateway/freigabe': hub.gateway_freigabe,  # legt das Gate vor
                    '/api/gateway/apply': hub.gateway_apply,
                    '/api/gateway/pruefung': hub.gateway_pruefung,  # R2: geprüft / verworfen
                    '/api/gateway/verwerfen': hub.gateway_verwerfen,
                    '/api/gateway/frage': hub.gateway_frage,        # Wissensbasis: Antwort ohne Modell, nichts läuft (Ticket B6-G-03)
                    '/api/gateway/wissen': hub.gateway_wissen_eintrag,   # eigener Eintrag des Nutzers, nur Audit
                    '/api/uix/install': hub.install_request,        # legt vor, baut nicht ein
                    '/api/uix/install/apply': hub.install_apply,
                    '/api/uix/trust': hub.trust_request,            # Schreibrouten freigeben: Gate, kein Häkchen
                    '/api/uix/trust/apply': hub.trust_apply,
                    '/api/uix/remove': hub.install_remove,
                    '/api/project/create': hub.new_project,
                    '/api/standard-test/start': hub.standard_test_start,
                    '/api/mission/details': hub.mission_details,
                    '/api/candidate': hub.candidate_operation,
                    '/api/code/generate': hub.generate_candidate,
                    '/api/route': hub.route,
                    '/api/chat': hub.create_chat_mission,
                    '/api/project/files': hub.project_files,        # read-only
                    '/api/project/file': hub.project_file,          # read-only
                    '/api/chat/reply': lambda p: hub._verlauf('reply', p, hub.chat_reply(p)),     # §9.2: hält den Verlauf fest
                    '/api/chat/verlauf/leeren': hub.chat_verlauf_leeren,
                    '/api/arbeitsstand': lambda p: hub.arbeitsstand_melden(p, self.headers.get('X-SEDRA-Shell')),
                    '/api/arbeitsstand/leeren': hub.gedaechtnis_leeren,     # „Gedächtnis leeren“ im Umschalter (§10.5)
                    '/api/ablage/lesen': lambda p: hub.ablage_lesen(self.headers.get('X-SEDRA-Tool'), p),          # §10.3
                    '/api/ablage/schreiben': lambda p: hub.ablage_schreiben(self.headers.get('X-SEDRA-Tool'), p),
                    '/api/planung/reply': hub.planung_reply,
                    # Fisch (19.10.2026): Übersetzung und Brief rufen das Modell (Mission, Audit, Inhaltsschutz); Transkripte schreiben nur ins Projekt
                    '/api/fisch/uebersetzen': hub.fisch.uebersetzen,
                    '/api/fisch/profil/speichern': hub.fisch.profil_speichern,
                    '/api/fisch/brief': hub.fisch.brief,
                    '/api/fisch/transkript': hub.fisch.transkript,
                    '/api/fisch/transkript/import': hub.fisch.transkript_import,
                    '/api/fisch/transkript/suche': hub.fisch.transkript_suche,
                    '/api/fisch/transkript/pseudonymisieren': hub.fisch.transkript_pseudonymisieren,
                    '/api/fisch/transkript/status': hub.fisch.transkript_status,
                    '/api/fisch/transkript/export': hub.fisch.transkript_export,
                    '/api/fisch/transkript/erkenntnisse': hub.fisch.transkript_erkenntnisse,   # SEDRA liest die Fassung: Zusammenfassung, Entscheidungen, Fragen, Aufgaben
                    '/api/sprache/aufnahme': hub.sprache.abspielen,                    # read-only: ein Record mit den Daten (Kern Sprache, 19.10.2026)
                    '/api/sprache/kern/start': hub.sprache.kern_start,
                    '/api/sprache/kern/pause': hub.sprache.kern_pause,
                    '/api/sprache/kern/weiter': hub.sprache.kern_weiter,
                    '/api/sprache/kern/stopp': hub.sprache.kern_stopp,
                    '/api/sprache/kern/verwerfen': hub.sprache.kern_verwerfen,
                    '/api/sprache/aufnahme/beginnen': hub.sprache.beginnen,
                    '/api/sprache/aufnahme/stueck': hub.sprache.stueck,
                    '/api/sprache/aufnahme/beenden': hub.sprache.beenden,
                    '/api/sprache/aufnahme/loeschen': hub.sprache.loeschen,
                    '/api/sprache/aufnahme/transkribieren': hub.sprache.transkribieren,   # Provider im Hintergrund oder Abschrift von Hand        # der Planungstisch (19.10.2026): Rolle, Werkzeuge des Planens, sonst wie chat_reply
                    '/api/chat/attach': hub.chat_attach,            # read-only
                    '/api/diagnose/explain': uix_diag.explain,      # read-only
                    '/api/diagnose/command': lambda payload: uix_diag.command(hub, payload),      # reads; only `/rebind ja` changes the hardware binding
                    '/api/mission/run': hub.run_mission,
                    '/api/mission/approve': hub.approve_gate,
                    '/api/mission/reject': hub.reject_gate,
                    '/api/switch/request': hub.switch_request,
                    '/api/switch/apply': hub.switch_apply,
                    '/api/cloud/save': hub.cloud_save,                      # Einstellungen schreiben (Captain-Klick, wirkt nach Neustart)
                    '/api/cloud/models': hub.cloud_models,          # Modellliste beim Anbieter abfragen (auf Klick, nur lesen)
                    '/api/labor/connection': hub.labor_connection,  # KI Labor: Verbindungstest in Schritten (auf Klick)
                    '/api/labor/models-test': hub.labor_model_test, # KI Labor: alle Modelle einmal testen (auf Klick)
                    '/api/vorarbeiter/aktion': hub.vorarbeiter,     # feste Vorarbeiter-Aktionen (Entwurfsfenster)
                    '/api/entwurf/save': hub.entwurf_save,         # Entwurf speichern (nur im Entwurfsordner)
                    '/api/entwurf/read': hub.entwurf_read,
                    '/api/entwurf/list': hub.entwurf_list,
                    '/api/chat/kombi': lambda p: hub._verlauf('kombi', p, hub.chat_kombi(p)),              # Lokal + KI: erst das lokale Modell, dann die Cloud prüft (ein Fenster)
                    '/api/chat/cloud': lambda p: hub._verlauf('cloud', p, hub.chat_cloud(p)),              # Gespräch mit einem Cloud-Modell (Wahl neben Senden); Inhaltsschutz
                    '/api/cloud/key': hub.cloud_key,
                    '/api/cloud/module-model': hub.cloud_module_model,   # welches Modell ein Modul nutzt (KI Labor)                        # Schlüssel verschlüsselt ablegen oder löschen; nie zurückgeben
                    '/api/routing-config/request': hub.routing_request,
                    '/api/routing-config/apply': hub.routing_apply,
                    '/api/model/pick': hub.model_pick,              # opens the file dialog of this PC, reads nothing else
                    '/api/model/browse': hub.model_browse,          # read-only, confined to the model folder
                    '/api/model/inspect': hub.model_inspect,        # read-only
                    '/api/model/add/request': hub.model_add_request,
                    '/api/model/add/apply': hub.model_add_apply,
                    '/api/model/test': hub.model_test,
                    '/api/library/search': hub.library.search,               # read-only
                    '/api/library/read': hub.library.read,                   # read-only, one page
                    '/api/library/text': hub.library.full_text,              # read-only, the whole SKILL.md
                    '/api/library/custom/request': hub.library.custom_request,
                    '/api/library/custom/apply': hub.library.custom_apply,
                    '/api/model/load': hub.load_model,
                    '/api/model/unload': hub.unload_model,
                    '/api/process/stop': hub.stop_process,
                    '/api/job/cancel': hub.cancel_job,
                    '/api/rework/hint': hub.rework_hint,
                    '/api/routing-profile': hub.use_profile,
                }
                fn = routes.get(path)
                if fn is None:
                    self.send_error(404)
                    return
                self._send(200, fn(payload))
            except ValueError as exc:
                self._send(400, {'error': 'bad_request', 'message': FRIENDLY_400.get(str(exc), str(exc)), **({'code': str(exc)} if str(exc) in FRIENDLY_400 else {})})
            except Exception as exc:
                self._send(503, {'error': type(exc).__name__, 'message': str(exc)})

    class Server(ThreadingHTTPServer):
        request_queue_size = 64    # Standard 5: eine Seite lädt viele Skripte zugleich; bei mehreren Browsern lehnte Windows Verbindungen ab (29.10.2026)

    server = Server(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    hub.start_extensions()
    server.desk_stop = threading.Event()          # set when the server stops: open event streams end instead of hanging
    for c, t in client_tokens.items():
        uix_clients.write(hub.project_root, c, t, server.server_port)
    _close = server.server_close

    def server_close():
        server.desk_stop.set()
        for c in client_tokens:
            uix_clients.remove(hub.project_root, c)
        _close()
    server.server_close = server_close
    return server, 'http://127.0.0.1:' + str(server.server_port) + '/#' + token


# macOS app bundles and the usual Linux names; the same app-mode arguments work for all Chromium-based browsers.
POSIX_BROWSERS = ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
                  '/Applications/Chromium.app/Contents/MacOS/Chromium', '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser')
POSIX_BROWSER_NAMES = ('google-chrome', 'google-chrome-stable', 'microsoft-edge', 'chromium', 'chromium-browser', 'brave-browser')


def open_app_window(url):
    """Start GUPPI's UIX as its own window (the integrated uix_window capability: Edge/Chrome in app mode). The capability only builds the
    argument list and refuses any URL but GUPPI's own loopback UIX; starting the process is done here. Returns the process, or None."""
    import os, shutil, subprocess, sys, tempfile
    from .capabilities.uix_window import browser_candidates, pick_browser, window_argv
    if sys.platform == 'win32':
        # Windows upper-cases the names in os.environ, the capability looks them up as Windows documents them.
        env = {n: os.environ.get(n, '') for n in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA')}
        browser = pick_browser(browser_candidates(env), os.path.isfile)
    else:
        browser = pick_browser(POSIX_BROWSERS, os.path.isfile) or next((p for p in map(shutil.which, POSIX_BROWSER_NAMES) if p), None)
    if not browser:
        return None
    profile = str(Path(tempfile.gettempdir()) / 'guppi-uix-window-profile')    # its own profile: the normal browser profile stays untouched
    return subprocess.Popen(window_argv(browser, url, profile))


def choose_start_shell(hub, shell):
    """START_SEDRA <id> oder START_SEDRA --uebersicht: die Shell nur für diesen Start. `None` = wie in uix.yaml.
    Eine unbekannte Shell ist ein Fehler mit Satz, kein stiller Rückfall – der Captain wollte genau diese."""
    if not shell:
        return None
    available = sorted(hub.gateway.shells())
    if shell not in available:
        raise ValueError(f'Die Oberfläche „{shell}“ gibt es nicht. Vorhanden: {", ".join(available)}.')
    hub.gateway.registry.shell_override = shell
    return shell


FRIENDLY_400 = {      # code -> sentence for the Captain; `code` keeps the code
    'unknown_decision': 'Diese Frage ist nicht mehr offen: sie wurde schon beantwortet oder hat sich erledigt. Die Liste zeigt den aktuellen Stand.',
    'way_not_offered': 'Diese Antwort bietet die Frage nicht an. Die Liste zeigt, was möglich ist.',
}


def serve(project_root: Path, architecture_root: Path, port=0, open_browser=False, window=False, shell=None):
    hub = UIXHub(project_root, architecture_root)
    try:
        chosen = choose_start_shell(hub, shell)
    except ValueError as exc:
        print(str(exc), flush=True); hub.close(); return 4
    server, url = make_server(hub, port)
    hub.poller.start()      # the scheduler's step must not wait for a browser: it runs in the poller's beat
    print('SEDRA Desktop (UIX):', url, flush=True)
    if chosen:
        print(f'Oberfläche für diesen Start: {chosen} (die Wahl in uix.yaml bleibt unverändert).', flush=True)
    print('Loopback-only. Captain gates remain enforced by the runtime.', flush=True)
    if window:
        proc = open_app_window(url)
        if proc is None:
            print('Kein Edge, Chrome oder Chromium gefunden: die Oberfläche öffnet im Standardbrowser. Beenden mit Strg+C (macOS: ctrl+C) im Terminal.', flush=True)
            webbrowser.open(url)
        else:
            def stop_with_window():
                proc.wait()      # the window was closed
                server.shutdown()
            threading.Thread(target=stop_with_window, daemon=True).start()
    elif open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        hub.close()
        server.server_close()
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog='guppi-uix')
    p.add_argument('--root', default='.')
    p.add_argument('--architecture', required=True)
    p.add_argument('--port', type=int, default=0)
    p.add_argument('--open', action='store_true')
    p.add_argument('--window', action='store_true', help='open the UIX as its own window (Edge/Chrome app mode); closing the window stops the server')
    p.add_argument('--shell', help='start in this shell (this start only; uix.yaml stays)')
    args = p.parse_args(argv)
    return serve(Path(args.root), Path(args.architecture), args.port, args.open, args.window, shell=args.shell) or 0


if __name__ == '__main__':
    raise SystemExit(main())
