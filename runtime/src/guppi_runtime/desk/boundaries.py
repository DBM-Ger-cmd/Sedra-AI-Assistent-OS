"""Modus und die vier Grenzen je Projekt (COCKPIT_MODUL_v1 §3 und Regel 7, SHELL_WERKZEUG_VERTRAG_v1 §10).

Der Captain hat festgelegt: der Mensch steht nur an bleibenden Stellen. Das sind diese – ein **Modus** je Projekt und vier
**Grenzen**, die sagen, was ohne Rückfrage passieren darf:

    projekt   Dateien im Projekt ändern
    netz      ins Netz gehen (nachladen, abrufen)
    loeschen  Dateien löschen
    kosten    Token je Aufgabe

Jede Grenze steht auf `frei`, `fragt` oder `zu`; die Kostengrenze zusätzlich auf einer Zahl. Zwei Regeln sind nicht verhandelbar
(Konzeptprüfung P0/P4): **Netz und Löschen gibt es nicht als `frei`**, und **Lesen ist immer frei**.

Weiter gilt die Entscheidung des Captains, dass **kein Standard im Code steht**: beim ersten Öffnen eines Projekts schlägt GUPPI
Modus und Grenzen *aus dem Projekt* vor und begründet es in einem Satz; bestätigt wird einmal, über ein Gate. Bis dahin ist das
Projekt `unbestätigt`, und was eine Grenze berührt, läuft nicht.

Die Kostengrenze wird gemessen, nicht geraten: bis zwei Wochen Guppy-Meter vorliegen, fragt sie ab dem Doppelten der bisher
teuersten Aufgabe (`measured_limit`)."""
from __future__ import annotations

from pathlib import Path

import yaml

KINDS = ('projekt', 'netz', 'loeschen', 'kosten')
WAYS = ('frei', 'fragt', 'zu')
NEVER_FREE = ('netz', 'loeschen')          # P0/P4: dafür gibt es `frei` nicht
MODES = ('sandbox', 'beobachten', 'vertraut')

MODE_DEFAULTS = {
    'sandbox':    {'projekt': 'fragt', 'netz': 'zu', 'loeschen': 'zu'},
    'beobachten': {'projekt': 'zu', 'netz': 'fragt', 'loeschen': 'zu'},
    'vertraut':   {'projekt': 'frei', 'netz': 'fragt', 'loeschen': 'fragt'},
}
MODE_WORD = {
    'sandbox': 'Sandbox – hier wird gebaut, aber nichts verlässt das Projekt.',
    'beobachten': 'Beobachten – fremder Code: gelesen wird frei, geschrieben wird nichts.',
    'vertraut': 'Vertraut – dein eigenes Werkzeugprojekt: Schreiben läuft durch, Netz und Löschen fragen.',
}
WAY_WORD = {'frei': 'läuft durch', 'fragt': 'fragt dich', 'zu': 'ist zu'}
KIND_WORD = {'projekt': 'Projekt', 'netz': 'Netz', 'loeschen': 'Löschen', 'kosten': 'Kosten'}


class BoundaryError(ValueError):
    pass


def propose(look):
    """Der Vorschlag aus dem Projekt – kein Standard im Code (Captain-Entscheidung §3).

    `look` beschreibt, was im Ordner gefunden wurde: {'empty': bool, 'git': bool, 'foreign': bool, 'files': int}.
    Zurück kommt {mode, boundaries, reason} – der Satz ist die Begründung, die der Captain zu lesen bekommt."""
    empty = bool(look.get('empty'))
    git = bool(look.get('git'))
    foreign = bool(look.get('foreign'))
    if empty:
        mode, reason = 'sandbox', 'Der Ordner ist leer – hier entsteht etwas Neues, also Sandbox.'
    elif git and foreign:
        mode, reason = 'beobachten', 'Ein bestehendes Repository mit fremdem Code – erst lesen, nichts schreiben.'
    elif look.get('own_tool'):
        mode, reason = 'vertraut', 'Dein eigenes Werkzeugprojekt – Schreiben läuft durch, Netz und Löschen fragen.'
    else:
        count = look.get('files', 0)
        word = '1 Datei' if count == 1 else f'{count} Dateien'
        mode, reason = 'sandbox', f'{word} ohne Repository – vorsichtig anfangen, also Sandbox.'
    return {'mode': mode, 'boundaries': dict(MODE_DEFAULTS[mode], kosten='fragt'), 'reason': reason}


def look_at(path: Path):
    """Was in einem Projektordner zu sehen ist – ohne ihn zu verändern und ohne eine Datei zu öffnen."""
    path = Path(path)
    if not path.is_dir():
        return {'empty': True, 'git': False, 'foreign': False, 'files': 0}
    names = []
    for item in path.rglob('*'):
        if item.is_file():
            names.append(item)
        if len(names) > 400:
            break
    git = (path / '.git').exists()
    own = (path / 'tool.yaml').exists() or (path / 'shell.yaml').exists() or (path / 'benchmarks').is_dir()
    foreign = git and not own
    return {'empty': not names, 'git': git, 'foreign': foreign, 'own_tool': own, 'files': len(names)}


def check_values(mode, values):
    """Prüft einen Satz Grenzen, bevor er gespeichert wird. Gibt die bereinigten Werte zurück oder wirft."""
    if mode not in MODES:
        raise BoundaryError('unknown_mode')
    if not isinstance(values, dict):
        raise BoundaryError('boundaries_must_be_a_mapping')
    out = {}
    for kind in KINDS:
        value = values.get(kind, MODE_DEFAULTS[mode].get(kind, 'fragt') if kind != 'kosten' else 'fragt')
        if kind == 'kosten':
            if value not in WAYS and not (type(value) is int and 0 < value <= 100_000_000):
                raise BoundaryError('kosten_must_be_a_way_or_a_number')
        elif value not in WAYS:
            raise BoundaryError(f'{kind}_must_be_one_of_frei_fragt_zu')
        if kind in NEVER_FREE and value == 'frei':
            raise BoundaryError(f'{kind}_cannot_be_free')       # P0/P4
        out[kind] = value
    return out


def sentence(mode, values):
    """Ein Satz für die Leiste und für das Gate: Modus und die vier Grenzen in Worten."""
    parts = []
    for kind in KINDS:
        value = values.get(kind)
        word = WAY_WORD.get(value) or (f'fragt ab {value} Token' if type(value) is int else str(value))
        parts.append(f'{KIND_WORD[kind]}: {word}')
    return mode.capitalize() + ' · ' + ' · '.join(parts)


def decide(kind, values, amount=None):
    """Was mit einer Handlung geschieht, die diese Grenze berührt: 'frei', 'fragt' oder 'zu'.

    Lesen kommt hier nie an – Lesen ist immer frei (§3). `amount` ist die Zahl bei der Kostengrenze."""
    if kind not in KINDS:
        raise BoundaryError('unknown_boundary')
    value = values.get(kind)
    if kind == 'kosten' and type(value) is int:
        return 'fragt' if (amount or 0) >= value else 'frei'
    if value not in WAYS:
        raise BoundaryError('boundary_not_set')
    return value


def measured_limit(most_expensive):
    """Solange nicht gemessen ist, fragt die Kostengrenze ab dem Doppelten der bisher teuersten Aufgabe (§3)."""
    if not most_expensive or most_expensive <= 0:
        return None
    return int(most_expensive) * 2


class Store:
    """`local_config/boundaries.yaml`: je Projekt der bestätigte Modus mit seinen Grenzen. Unbestätigt ist ein Zustand, kein Fehler."""

    def __init__(self, project_root: Path):
        self.path = Path(project_root) / 'local_config' / 'boundaries.yaml'

    def all(self):
        if not self.path.is_file():
            return {}
        try:
            raw = yaml.safe_load(self.path.read_text(encoding='utf-8')) or {}
        except yaml.YAMLError as exc:
            raise BoundaryError(f'boundaries_yaml_unreadable:{exc}') from exc
        projects = raw.get('projects') if isinstance(raw, dict) else None
        return projects if isinstance(projects, dict) else {}

    def get(self, project_id):
        entry = self.all().get(str(project_id))
        if not isinstance(entry, dict) or entry.get('mode') not in MODES:
            return None
        try:
            values = check_values(entry['mode'], entry.get('boundaries') or {})
        except BoundaryError:
            return None
        return {'mode': entry['mode'], 'boundaries': values, 'confirmed_at': entry.get('confirmed_at')}

    def put(self, project_id, mode, values, confirmed_at):
        values = check_values(mode, values)
        projects = self.all()
        projects[str(project_id)] = {'mode': mode, 'boundaries': values, 'confirmed_at': confirmed_at}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.yaml.tmp')
        tmp.write_text(yaml.safe_dump({'projects': projects}, allow_unicode=True, sort_keys=True), encoding='utf-8')
        tmp.replace(self.path)
        return {'mode': mode, 'boundaries': values, 'confirmed_at': confirmed_at}


def crossing(project_id, kind, what, values, amount=None):
    """Eine Überschreitung als Entscheidung an der Grenze (Regel 7): drei Wege, und `aendern` ist einer davon."""
    verdict = decide(kind, values, amount)
    if verdict == 'frei':
        return None
    describe = f'{KIND_WORD[kind]}grenze: {what}'
    return {'id': f'boundary:{project_id}:{kind}:{what}'[:160], 'kind': 'boundary', 'boundary': kind,
            'project_id': project_id, 'title': describe, 'describe': what,
            'note': 'Einmal öffnen gilt für genau diese eine Handlung.' if verdict == 'fragt' else
                    f'Diese Grenze steht auf „zu“. Öffnen heißt, sie für dieses Projekt zu ändern.',
            'ways': (['einmal', 'aendern', 'ablehnen'] if verdict == 'fragt' else ['aendern', 'ablehnen']),
            'verdict': verdict, 'amount': amount}
