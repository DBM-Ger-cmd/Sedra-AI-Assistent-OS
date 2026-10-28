"""Vorhaben (COCKPIT_MODUL_v1 Regel 8: „Ein Vorhaben ist Gesprächsgegenstand; GUPPI macht Aufgaben daraus“).

Ein Vorhaben ist kein Auftrag und keine Mission: es ist der Satz, um den es geht, und die Klammer um die Aufgaben, die daraus
entstehen. Deshalb kostet das Anlegen nichts und braucht keine Freigabe – es wird nichts ausgeführt. Erst wenn daraus eine
Aufgabe wird, beginnt der gewohnte Weg (Plan, Gates, Ausführung).

Gespeichert wird in `local_config/intents.yaml`, je Projekt. Der Text gehört dem Captain; GUPPI hängt nur die Aufgaben an."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .objects import ONLY_PLAN_WORD, only_plan

ID = re.compile(r'^V-[0-9A-F]{8}$')
MAX_TITLE = 120
MAX_TEXT = 4000
MAX_INTENTS = 500      # eine Datei, die ein Mensch liest – darüber hinaus ist etwas anderes kaputt
MAX_STUFEN = 12        # Stufen eines Vorhabens (19.10.2026): ein Weg mit mehr Schritten ist zwei Vorhaben
MAX_STUFE_NAME = 80
MAX_STUFE_TEXT = 600


def new_id(seed):
    import hashlib
    return 'V-' + hashlib.sha256(str(seed).encode('utf-8')).hexdigest()[:8].upper()


def check(title, text):
    title = str(title or '').strip()
    if not 1 <= len(title) <= MAX_TITLE:
        raise ValueError('title_required')
    text = str(text or '').strip()
    if len(text) > MAX_TEXT:
        raise ValueError('text_too_long')
    return title, text


def check_stufen(stufen):
    """Die Stufen eines Vorhabens: Name und Satz je Stufe, in der Reihenfolge, wie sie gegangen werden. Leer ist erlaubt."""
    if stufen in (None, '', []):
        return []
    if not isinstance(stufen, list) or len(stufen) > MAX_STUFEN:
        raise ValueError('stufen_invalid')
    out = []
    for s in stufen:
        if isinstance(s, str):
            s = {'name': s}
        if not isinstance(s, dict):
            raise ValueError('stufen_invalid')
        name = str(s.get('name') or '').strip()
        text = str(s.get('text') or '').strip()
        if not 1 <= len(name) <= MAX_STUFE_NAME or len(text) > MAX_STUFE_TEXT:
            raise ValueError('stufen_invalid')
        out.append({'name': name, 'text': text, 'tasks': []})
    return out


def _tasks_state(tasks):
    """Der Zustand aus einer Liste von Aufgaben (Missionen): wartet auf dich · in Arbeit · fertig · offen."""
    if not tasks:
        return 'offen'
    if any((t.get('pending_gates') or 0) for t in tasks):
        return 'wartet auf dich'
    if any(t.get('status') == 'active' and (t.get('phase') or '') not in ('COMPLETE', 'FAILED') for t in tasks):
        return 'in Arbeit'
    if any(only_plan(t.get('phase'), t.get('qualification')) for t in tasks):
        return ONLY_PLAN_WORD
    if all(t.get('phase') == 'COMPLETE' for t in tasks):
        return 'fertig'
    return 'offen'


def stufen_of(entry, missions_by_id):
    """Die Stufen mit ihrem Zustand aus den Aufgaben, die an ihnen hängen – die erste, die nicht fertig ist, ist die aktuelle."""
    out, current = [], None
    for i, s in enumerate(entry.get('stufen') or []):
        tasks = [missions_by_id.get(t) for t in (s.get('tasks') or [])]
        tasks = [t for t in tasks if t]
        state = _tasks_state(tasks)
        if current is None and state != 'fertig':
            current = i
        out.append({'index': i, 'name': s.get('name') or f'Stufe {i + 1}', 'text': s.get('text') or '', 'state': state,
                    'tasks': [{'id': t.get('mission_id'), 'title': str(t.get('intent') or t.get('mission_id'))[:60],
                               'phase': t.get('phase') or '', 'waits': bool(t.get('pending_gates'))} for t in tasks]})
    for s in out:
        s['current'] = (s['index'] == current)
    return out


def state_of(entry, missions_by_id):
    """Der Zustand eines Vorhabens kommt aus seinen Aufgaben – es hat keinen eigenen."""
    tasks = [missions_by_id.get(t) for t in (entry.get('tasks') or [])]
    tasks = [t for t in tasks if t]
    if not tasks:
        return 'noch keine Aufgabe', 'Noch keine Aufgabe. Sag im Gespräch, was zuerst passieren soll.'
    waiting = [t for t in tasks if (t.get('pending_gates') or 0)]
    open_tasks = [t for t in tasks if t.get('status') == 'active']
    done = [t for t in tasks if t.get('phase') == 'COMPLETE']
    plan_only = [t for t in done if only_plan(t.get('phase'), t.get('qualification'))]
    if waiting:
        return 'wartet auf dich', f'{len(waiting)} von {len(tasks)} Aufgaben warten auf deine Freigabe.'
    if open_tasks:
        return 'in Arbeit', f'{len(open_tasks)} von {len(tasks)} Aufgaben sind offen.'
    if plan_only:
        return ONLY_PLAN_WORD, f'{len(plan_only)} von {len(tasks)} Aufgaben wurden nicht ausgeführt – es gibt nur einen Plan, kein Werkzeug dafür.'
    if len(done) == len(tasks):
        return 'fertig', f'Alle {len(tasks)} Aufgaben sind fertig.'
    return 'offen', f'{len(tasks)} Aufgaben, keine davon läuft gerade.'


class Store:
    def __init__(self, project_root: Path):
        self.path = Path(project_root) / 'local_config' / 'intents.yaml'

    def all(self):
        if not self.path.is_file():
            return {}
        try:
            raw = yaml.safe_load(self.path.read_text(encoding='utf-8')) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f'intents_yaml_unreadable:{exc}') from exc
        items = raw.get('intents') if isinstance(raw, dict) else None
        return items if isinstance(items, dict) else {}

    def list(self, project_id=None):
        out = [dict(v, id=k) for k, v in sorted(self.all().items(), key=lambda kv: kv[1].get('created_at') or '')]
        return [i for i in out if not project_id or i.get('project_id') == project_id]

    def get(self, intent_id):
        entry = self.all().get(str(intent_id))
        return dict(entry, id=str(intent_id)) if isinstance(entry, dict) else None

    def _write(self, items):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.yaml.tmp')
        tmp.write_text(yaml.safe_dump({'intents': items}, allow_unicode=True, sort_keys=True), encoding='utf-8')
        tmp.replace(self.path)

    def add(self, title, text, project_id, now, stufen=None, vorlage=None):
        title, text = check(title, text)
        stufen = check_stufen(stufen)
        items = self.all()
        if len(items) >= MAX_INTENTS:               # Härtung: nichts, was in einer Schleife unbegrenzt wächst
            raise ValueError('too_many_intents')
        iid = new_id(f'{project_id}:{title}:{now}')
        items[iid] = {'title': title, 'text': text, 'project_id': project_id, 'created_at': now, 'tasks': [], 'stufen': stufen}
        if vorlage:
            items[iid]['vorlage'] = str(vorlage)[:40]
        self._write(items)
        return dict(items[iid], id=iid)

    def attach(self, intent_id, mission_id, stufe=None):
        """Eine Aufgabe an das Vorhaben hängen – und, wenn gesagt, an eine seiner Stufen (Index)."""
        items = self.all()
        entry = items.get(str(intent_id))
        if not isinstance(entry, dict):
            raise ValueError('unknown_intent')
        tasks = list(entry.get('tasks') or [])
        if mission_id not in tasks:
            tasks.append(mission_id)
        entry['tasks'] = tasks
        if stufe is not None:
            stufen = entry.get('stufen') or []
            if not isinstance(stufe, int) or not 0 <= stufe < len(stufen):
                raise ValueError('unknown_stufe')
            own = list(stufen[stufe].get('tasks') or [])
            if mission_id not in own:
                own.append(mission_id)
            stufen[stufe]['tasks'] = own
            entry['stufen'] = stufen
        self._write(items)
        return dict(entry, id=str(intent_id))
