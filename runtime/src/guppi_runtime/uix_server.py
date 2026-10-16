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

from . import gpu_preflight, uix_diag
from .job_supervisor import FINAL_STATES, JobError
from .mission import ALLOWED
from .util import atomic_write_json, load_json, utcnow
from .local_switches import ALLOWED as SWITCH_ALLOWED, LocalSwitches
from . import cloud_settings
from .cloud_settings import CloudKeyStore
from .role_routing import RoutingConfig
from .rework_watch import ReworkWatch
from .model_loader import LoadError
from .testlab import TestLab, default_path
from .runtime import GuppiRuntime
from . import local_paths
from .models import model_add
from .chat_tools import ChatTools
from .devenv.model_tools import run_tool_loop
from .uix_library import LibraryDesk
from .desk import actions as desk_actions
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
    return {
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
        self.events = EventStream()
        self.poller = Poller(self, self.events)

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
        items = desk_decisions.collect(self.missions(), self._open_requests(), self._open_crossings(), self._content_decisions())
        return {'items': items, 'summary': desk_decisions.summary(items)}

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
        if decision['kind'] == 'content':
            result = self.content_guard.answer(did, way)
            self.events.publish('decision.answered', {'id': did, 'kind': 'content', 'way': way})
            return {'status': 'answered', 'id': did, 'way': way, 'result': result}
        mission_id, gate_id = decision['mission_id'], decision['gate_id']
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
        """Ein Vorhaben anlegen. Ohne Gate – es wird nichts ausgeführt, es ist der Satz, um den es geht."""
        project = self._active_project(payload.get('project_id'))
        entry = self.intents.add(payload.get('title'), payload.get('text'), (project or {}).get('project_id'), utcnow())
        self.runtime.audit.append('INTENT_CREATED', component='desk', payload={'id': entry['id'], 'title': entry['title'][:80]})
        self.events.publish('tools.refresh', {})
        return entry

    def intent_to_task(self, intent_id, extra=None):
        """GUPPI macht aus dem Vorhaben eine Aufgabe: geplant, nicht ausgeführt – wie jede Aufgabe aus dem Gespräch."""
        entry = self.intents.get(intent_id)
        if entry is None:
            raise ValueError('unknown_intent')
        text = (str(extra or '').strip() or entry['text'] or entry['title'])
        out = self.create_chat_mission({'intent': text[:400], 'project_id': entry.get('project_id')})
        mission_id = out['mission']['mission_id']
        self.intents.attach(entry['id'], mission_id)
        self.runtime.audit.append('INTENT_TASK_CREATED', component='desk', payload={'intent': entry['id'], 'mission_id': mission_id})
        return {'intent': entry['id'], 'mission_id': mission_id, 'mission': out['mission']}

    def _intent_object(self, entry):
        missions = {m['mission_id']: m for m in self.missions()}
        state, summary = desk_intents.state_of(entry, missions)
        return desk_objects.intent_object(entry, state, summary)

    # ---- Build 9: ein fremdes Modul einbauen (Vertrag §6 „Installation“, §7)
    INSTALL_ACTION = 'install_module'

    def install_request(self, payload):
        """Ein Modul zur Freigabe vorlegen: Manifest, jede Datei mit Hash, und was die Durchsicht gefunden hat.

        Geschrieben wird hier nichts. Der Ordner wird gelesen, geprüft und beschrieben; eingebaut wird er erst nach der Freigabe."""
        kind = str(payload.get('kind') or 'tool')
        if kind not in ('tool', 'shell'):
            raise ValueError('kind_must_be_tool_or_shell')
        source = str(payload.get('source') or '').strip()
        if not source:
            raise ValueError('source_required')
        folder = Path(source)
        if not folder.is_absolute() or '..' in folder.parts:
            raise ValueError('source_must_be_an_absolute_path_without_dotdot')
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
            raise ValueError('manifest_refused:' + ','.join(errors)[:200])
        if manifest['id'] in (self.gateway.tools() if kind == 'tool' else self.gateway.shells()):
            raise ValueError('module_id_already_installed')
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
                'aufgaben_offen': sum(1 for m in missions if m.get('status') == 'active'),
                'aufgaben_wartend': sum(1 for m in missions if m.get('status') == 'active' and (m.get('pending_gates') or 0) > 0),
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
        try:
            model = self.runtime.model_router.choose().id
        except Exception:
            model = None
        return {'vorgaenge': self.gw.liste(), 'vorgaben': self.gw.vorgaben(), 'dateien': files, 'modell': model, 'zwecke': self.gw.zwecke(),
                'merkmale': [{'id': k, 'name': v[0], 'klasse': v[1], 'manuell': k in klassen.MANUELL} for k, v in klassen.MERKMALE.items()],
                'klassen': [{'id': k, 'name': klassen.KLASSE_WORT[k]} for k in klassen.KLASSEN],
                'regeln': [klassen.regel(r) for r in klassen.REGELN], 'policy_version': klassen.POLICY_VERSION, 'regelwerk': klassen.REGELWERK,
                'leitfaden': wissen.leitfaden(), 'schritt_von_zustand': dict(wissen.SCHRITT_VON_ZUSTAND),
                'nicht_im_mvp': ['Kein Versand – der Entwurf bleibt hier.', 'Cloud nur simuliert; ein echter Cloudweg ist ein eigener Beschluss.',
                                 'Anhänge nur .md und .txt; PDF/DOCX sind MVP 2.', 'Keine Rollen: der Nutzer ist die Prüfung.',
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

    def gateway_pruefen(self, payload):
        """POST /api/gateway/pruefen {id, anfrage, dokument?, wunsch?, manuell?, zweck?, verantwortlich?} – liest die Datei aus dem Projekt;
        nichts verlässt den Rechner. Zweck und verantwortliche Person (G-05) werden Teil der Bindung."""
        p = payload or {}
        vid = str(p.get('id') or '').strip()
        dokument = None
        name = str(p.get('dokument') or '').strip()
        if name:
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
            try:
                dokument = (name, path.read_text(encoding='utf-8'))
            except UnicodeDecodeError:
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
        describe = (f'Vorgang „{v.titel}“ freigeben: {klassen.WEG_WORT[weg]} · {e["klasse"]} {e["klasse_wort"]} · '
                    + (', '.join(m['id'] for m in e['merkmale']) or 'keine Merkmale') + ' · ' + e['policy_wort']
                    + f' · Zweck: {ZWECKE.get(v.zweck, v.zweck)} · verantwortlich: {v.verantwortlich}'
                    + (' – deine Prüfung (R1) ist die Freigabe' if review else ''))
        risks = list(e['gruende'])[:4] + (['Cloud ist simuliert: nichts verlässt den Rechner.'] if weg != 'LOCAL_ONLY' else [])
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
        """Nach der Freigabe: der Aufruf – lokal durch den Inhaltsschutz, Cloud simuliert. Mit Einmal-Token und Bindungsprüfung."""
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
                out = rt.model_router.chat(mission_id, messages)
                model = out.get('model') or out.get('provider')
                return out.get('content') or ''
            try:
                e = self.gw.ausfuehren(vid, weg, full['binding'], complete_local)
            except Exception as exc:
                m['execution'].pop('approval_token', None)
                m['result'] = {'kind': 'gateway', 'status': 'fehler', 'grund': str(exc)[:200]}
                m['lifecycle']['status'] = 'closed'
                rt.missions.save(m)
                self._gw_error(exc) if not isinstance(exc, ValueError) else None
                raise ValueError('gateway_fehler:' + str(exc)[:160])
            if model and e.modell == 'lokales Modell':
                e.modell = str(model); e.kennzeichnen(); self.gw._entwurf_speichern(e)
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
        """Ein Objekt in der einen Form (§10.1). Liest dieselben Sichten wie die alten Routen; die bleiben unverändert."""
        if kind == 'task':
            m = next((x for x in self.missions() if x['mission_id'] == oid), None)
            if m is None:
                return desk_objects.not_found(kind, oid)
            obj = desk_objects.task_object(m)
            if self._candidate_report(oid) is not None:          # es gibt ein Werkstück: der Weg dorthin gehört an die Aufgabe
                obj['links'].insert(0, {'type': 'candidate', 'id': oid, 'title': 'Kandidat ansehen', 'rel': 'werkstueck'})
        elif kind == 'candidate':
            try:
                mission = self.runtime.missions.load(oid)
            except Exception:
                return desk_objects.not_found(kind, oid)
            obj = desk_objects.candidate_object(mission, report=self.candidate_report({'mission_id': oid}))
        elif kind == 'model':
            view = self.models_view()
            recipe = next((r for r in view['recipes'] if r['id'] == oid), None)
            if recipe is None:
                return desk_objects.not_found(kind, oid)
            obj = desk_objects.model_object(recipe, view.get('server'))
        elif kind == 'intent':
            entry = self.intents.get(oid)
            if entry is None:
                return desk_objects.not_found(kind, oid)
            obj = self._intent_object(entry)
        elif kind == 'boundary':
            obj = desk_objects.boundary_object(self.boundaries_view({'project_id': oid} if oid not in ('projekt', 'alle') else None))
        elif kind == 'decision':
            d = next((x for x in self.decisions_view()['items'] if x['id'] == oid), None)
            return desk_objects.decision_object(d) if d else desk_objects.not_found(kind, oid)
        elif kind == 'skill':
            s = next((x for x in (self.library.view().get('own') or []) if x.get('id') == oid), None)
            return desk_objects.skill_object(s) if s else desk_objects.not_found(kind, oid)
        elif kind == 'project':
            p = next((x for x in self.projects.list() if (x.get('project_id') == oid or x.get('name') == oid)), None)
            return desk_objects.project_object(p) if p else desk_objects.not_found(kind, oid)
        else:
            raise ValueError('unknown_object_type')
        obj['actions'] = desk_actions.offered(obj)
        return obj

    def objects_view(self, payload):
        """`POST /api/objects {type, id}` für ein Objekt, ohne `id` die Liste des Typs."""
        kind = str(payload.get('type') or '').strip()
        if kind not in desk_objects.TYPES:
            raise ValueError('unknown_object_type')
        oid = payload.get('id')
        if oid:
            return self.object_view(kind, str(oid))
        if kind == 'task':
            items = [desk_objects.task_object(m) for m in self.missions()]
        elif kind == 'intent':
            items = [self._intent_object(e) for e in self.intents.list()]
        elif kind == 'boundary':
            items = [desk_objects.boundary_object(self.boundaries_view())]
        elif kind == 'model':
            view = self.models_view()
            items = [desk_objects.model_object(r, view.get('server')) for r in view['recipes']]
        elif kind == 'decision':
            items = [desk_objects.decision_object(d) for d in self.decisions_view()['items']]
        elif kind == 'skill':
            items = [desk_objects.skill_object(s) for s in (self.library.view().get('own') or [])]
        elif kind == 'project':
            items = [desk_objects.project_object(p) for p in self.projects.list()]
        else:
            items = []
        for item in items:
            item['actions'] = desk_actions.offered(item)
        return {'type': kind, 'items': items}

    def act(self, payload):
        """`POST /api/actions {type, id, verb, args}` (§10.2): ein Weg für dieselbe Handlung aus Gespräch, Werkzeug und Palette.
        Die Gates darunter bleiben, wie sie sind – `run` ruft genau die Hub-Methoden, die auch die alten Routen rufen."""
        kind = str(payload.get('type') or '').strip()
        oid = str(payload.get('id') or '').strip()
        verb = str(payload.get('verb') or '').strip()
        if not oid:
            raise ValueError('id_required')
        out = desk_actions.run(self, kind, oid, verb, payload.get('args') or {})
        self.runtime.audit.append('UIX_ACTION', component='desk', payload={'type': kind, 'id': oid[:60], 'verb': verb})
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
        """What the event stream compares (desk/events.py). Cheap: the views it reads are the ones the routes already read."""
        models = self.models_view()
        server = models.get('server') or {}
        return {'missions': self.missions(), 'decisions': self.decisions_view()['items'],
                'model': {'running': bool(server.get('running')), 'model': server.get('model'), 'context': server.get('context')},
                'live': self._live_signatures(),
                'state': 'READY' if self.runtime.observability.overall() == 'HEALTHY' else 'SAFE_MODE'}

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
        running = [m for m in snap['missions'] if m.get('status') == 'active' and (m.get('phase') or '') not in ('COMPLETE', 'FAILED')]
        waiting = [m for m in snap['missions'] if (m.get('pending_gates') or 0)]
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
                'tasks': {'value': len(running), 'hint': f"{len(running)} läuft · {len(waiting)} wartet", 'tone': 'off'},
                'mode': self._mode_gauge()}

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

    CHAT_SYSTEM = ('Du bist GUPPI, der Assistent des Captains in SEDRA. Antworte kurz und auf Deutsch, in einfachem Text. '
                   'Du bewegst dich in der Oberfläche über deine Werkzeuge: Fenster öffnen (open_place, open_object), nachsehen, was mit '
                   'einem Objekt geht (list_actions), und Handlungen vorschlagen (propose_action, propose_intent). Was du vorschlägst, '
                   'bekommt der Captain als Knopf; erst sein Klick führt es aus, und was eine Freigabe braucht, läuft danach über die '
                   'Entscheidungen. Du änderst keine Dateien und startest keine Programme außerhalb dieser Handlungen. '
                   'Dateien und Ordner siehst du nur, wenn der Captain sie anhängt; dann steht ihr Inhalt in der Nachricht. '
                   'Behaupte nie, etwas getan zu haben – sag, was du vorgeschlagen oder geöffnet hast.')

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
        if not loaded: return {'status': 'no_model', 'message': 'Kein Modell geladen.'}
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
            box = ChatTools(self)
            # Build 24: das Modell weiß, in welcher Oberfläche es arbeitet (Zonen, eigene Wörter, Wege) – aus dem Code, nicht geraten
            messages = [{'role': 'system', 'content': self.CHAT_SYSTEM + ' ' + self.arbeitsplatz.beschreibung(shell) + self.CHAT_TOOL_NOTE}, *turns,
                        {'role': 'user', 'content': attached + text}]

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
                                                                             'offered': [a['kind'] for a in box.ui_actions]})
        if res.get('error'):
            return {'status': 'failed', 'message': str(res['error'])[:300]}
        content = res.get('content')
        if not isinstance(content, str) or not content.strip():
            return {'status': 'failed', 'message': 'model_answer_truncated' if res.get('finish') == 'length' else 'model_answer_empty'}
        return {'status': 'completed', 'reply': content.strip(), 'model': model, 'truncated': res.get('finish') == 'length', 'mission_id': mission_id,
                'tools_used': box.calls, 'proposals': box.proposals, 'ui_actions': box.ui_actions}

    def run_mission(self, payload):
        mission_id = str(payload.get('mission_id') or '').strip()
        if not mission_id:
            raise ValueError('mission_id_required')
        max_steps = payload.get('max_steps',20)
        if type(max_steps) is not int or not 1 <= max_steps <= 32: raise ValueError('max_steps_out_of_range')
        with self.lock:
            m = self.runtime.brain.run(mission_id, max_steps=max_steps)
        return {'mission': _compact_mission(m), 'full_phase': m.get('lifecycle', {}), 'pending_gates': m.get('human_gates', {}).get('pending', [])}

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
                                                  risks=['wirkt erst nach Neustart der GUPPI-Oberfläche'], rollback_available=True, request_binding=binding)
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
                                  ['wirkt erst nach Neustart der GUPPI-Oberfläche', 'ändert, welches Modell wie geladen wird'], 'routing_request'))

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
            m['result'] = {'kind': 'routing_change', **{k: binding[k] for k in ('recipe_id', 'field', 'old', 'new')}, 'backup': backup.name, 'effective': 'next_start'}
            m['lifecycle']['status'] = 'closed'
            rt.missions.save(m)
            rt.audit.append('ROUTING_OVERLAY_CHANGED', component='uix', mission_id=mission_id, payload={k: m['result'][k] for k in ('recipe_id', 'field', 'old', 'new')})
        return {'status': 'applied', 'recipe_id': binding['recipe_id'], 'field': binding['field'], 'new': binding['new'], 'effective': 'next_start'}

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
        view['error'] = getattr(rt, 'cloud_providers_error', None)
        view['key_store_available'] = CloudKeyStore.available()
        return view

    def cloud_save(self, payload):
        res = cloud_settings.save(self.runtime.project_root, payload)
        self.runtime.audit.append('CLOUD_SETTINGS_SAVED', component='desk',
                                  payload={'enabled': res['enabled'], 'providers': sorted((payload.get('providers') or {}).keys())})
        return {'saved': True, 'restart_needed': True}

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
        from .candidate_tests import run_candidate_tests, verify_candidate_tests
        from .candidate_acceptance import command
        op=payload['operation'];mid=payload['mission_id']
        if op=='test':return run_candidate_tests(self.runtime,mid)
        if op=='test-verify':return verify_candidate_tests(self.runtime,mid)
        if op not in {'accept-preview','accept','rollback-preview','rollback'}:raise ValueError('unsupported_candidate_operation')
        return command(self.runtime,mid,op,payload.get('plan'))

    def generate_candidate(self, payload):
        from .code_generation import generate
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
        return {'recipes': recipes,
                'server': managed,
                'lease': ({'owner': holder['owner'], 'purpose': holder['purpose'], 'stale': holder['stale'], 'mine': self.gpu_token is not None and holder['owner'] == self.LEASE_OWNER}
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

    def _release_gpu(self):
        if self._beat_stop is not None:
            self._beat_stop.set(); self._beat_stop = None
        if self.gpu_token is not None:
            self.lab.release(self.gpu_token); self.gpu_token = None

    def load_model(self, payload):
        recipe_id = payload.get('recipe_id')
        if not isinstance(recipe_id, str) or not recipe_id: raise ValueError('recipe_id_required')
        rt = self.runtime
        if rt.role_router is None or getattr(rt, 'model_loader', None) is None or not rt.model_loader.enabled: raise ValueError('model_loader_unavailable')
        from .role_routing import ResolutionError
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
                self._release_gpu() if not (getattr(rt, 'llama_server', None) and rt.llama_server.loaded_models()) else None
                raise ValueError(str(exc))
            except Exception:
                self._release_gpu()
                raise
        return dict(out, recipe_id=recipe_id)

    def unload_model(self, payload):
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
        if self.gpu_token is not None:
            try: self.unload_model({})
            except Exception: self._release_gpu()
        for key in ('_gw_wissen', '_arbeitsplatz'):          # die Wissensdateien sauber schließen (Build 24)
            w = self.__dict__.get(key)
            if w is not None:
                try: w.close()
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


def make_server(hub: UIXHub, port=0):
    token = secrets.token_urlsafe(32)
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
            return bool(supplied) and hmac.compare_digest(supplied, token)

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
            if not self._authorized():
                self.send_error(403)
                return
            if not self._module_allowed('GET', path):
                return
            if path == '/api/events':
                self._events()
                return
            try:
                routes = {
                    '/uix/manifest': hub.gateway.manifest,                  # read-only: active shell and usable tools
                    '/api/decisions': hub.decisions_view,                   # read-only: one list for gates and change requests
                    '/api/strip': hub.strip_view,                           # read-only: the instruments of the Cockpit strip
                    '/api/boundaries': lambda: hub.boundaries_view(),        # read-only: Modus und Grenzen dieses Projekts
                    '/api/guard/status': hub.guard_status,                  # read-only: der Inhaltsschutz (Build 16) – nie Text
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
            if not self._same_origin_ok() or not self._authorized():
                self.send_error(403)
                return
            path = urlsplit(self.path).path
            if not self._module_allowed('POST', path):
                return
            try:
                payload = self._json_body()
                routes = {
                    '/api/decisions/answer': hub.decide,
                    '/api/objects': hub.objects_view,               # read-only: ein Objekt oder die Liste eines Typs (§10.1)
                    '/api/actions': hub.act,                        # Verben statt Routen (§10.2); die Gates darunter bleiben
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
                    '/api/chat/reply': hub.chat_reply,
                    '/api/chat/attach': hub.chat_attach,            # read-only
                    '/api/diagnose/explain': uix_diag.explain,      # read-only
                    '/api/diagnose/command': lambda payload: uix_diag.command(hub, payload),      # reads; only `/rebind ja` changes the hardware binding
                    '/api/mission/run': hub.run_mission,
                    '/api/mission/approve': hub.approve_gate,
                    '/api/mission/reject': hub.reject_gate,
                    '/api/switch/request': hub.switch_request,
                    '/api/switch/apply': hub.switch_apply,
                    '/api/cloud/save': hub.cloud_save,                      # Einstellungen schreiben (Captain-Klick, wirkt nach Neustart)
                    '/api/cloud/key': hub.cloud_key,                        # Schlüssel verschlüsselt ablegen oder löschen; nie zurückgeben
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
                self._send(400, {'error': 'bad_request', 'message': str(exc)})
            except Exception as exc:
                self._send(503, {'error': type(exc).__name__, 'message': str(exc)})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.desk_stop = threading.Event()          # set when the server stops: open event streams end instead of hanging
    _close = server.server_close

    def server_close():
        server.desk_stop.set()
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


def serve(project_root: Path, architecture_root: Path, port=0, open_browser=False, window=False, shell=None):
    hub = UIXHub(project_root, architecture_root)
    try:
        chosen = choose_start_shell(hub, shell)
    except ValueError as exc:
        print(str(exc), flush=True); hub.close(); return 4
    server, url = make_server(hub, port)
    print('SEDRA Desktop (GUPPI UIX):', url, flush=True)
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
