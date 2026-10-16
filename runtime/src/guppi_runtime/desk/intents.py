"""Vorhaben (COCKPIT_MODUL_v1 Regel 8: „Ein Vorhaben ist Gesprächsgegenstand; GUPPI macht Aufgaben daraus“).

Ein Vorhaben ist kein Auftrag und keine Mission: es ist der Satz, um den es geht, und die Klammer um die Aufgaben, die daraus
entstehen. Deshalb kostet das Anlegen nichts und braucht keine Freigabe – es wird nichts ausgeführt. Erst wenn daraus eine
Aufgabe wird, beginnt der gewohnte Weg (Plan, Gates, Ausführung).

Gespeichert wird in `local_config/intents.yaml`, je Projekt. Der Text gehört dem Captain; GUPPI hängt nur die Aufgaben an."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ID = re.compile(r'^V-[0-9A-F]{8}$')
MAX_TITLE = 120
MAX_TEXT = 4000
MAX_INTENTS = 500      # eine Datei, die ein Mensch liest – darüber hinaus ist etwas anderes kaputt


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


def state_of(entry, missions_by_id):
    """Der Zustand eines Vorhabens kommt aus seinen Aufgaben – es hat keinen eigenen."""
    tasks = [missions_by_id.get(t) for t in (entry.get('tasks') or [])]
    tasks = [t for t in tasks if t]
    if not tasks:
        return 'noch keine Aufgabe', 'Noch keine Aufgabe. Sag im Gespräch, was zuerst passieren soll.'
    waiting = [t for t in tasks if (t.get('pending_gates') or 0)]
    open_tasks = [t for t in tasks if t.get('status') == 'active']
    done = [t for t in tasks if t.get('phase') == 'COMPLETE']
    if waiting:
        return 'wartet auf dich', f'{len(waiting)} von {len(tasks)} Aufgaben warten auf deine Freigabe.'
    if open_tasks:
        return 'in Arbeit', f'{len(open_tasks)} von {len(tasks)} Aufgaben sind offen.'
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

    def add(self, title, text, project_id, now):
        title, text = check(title, text)
        items = self.all()
        if len(items) >= MAX_INTENTS:               # Härtung: nichts, was in einer Schleife unbegrenzt wächst
            raise ValueError('too_many_intents')
        iid = new_id(f'{project_id}:{title}:{now}')
        items[iid] = {'title': title, 'text': text, 'project_id': project_id, 'created_at': now, 'tasks': []}
        self._write(items)
        return dict(items[iid], id=iid)

    def attach(self, intent_id, mission_id):
        items = self.all()
        entry = items.get(str(intent_id))
        if not isinstance(entry, dict):
            raise ValueError('unknown_intent')
        tasks = list(entry.get('tasks') or [])
        if mission_id not in tasks:
            tasks.append(mission_id)
        entry['tasks'] = tasks
        self._write(items)
        return dict(entry, id=str(intent_id))
