"""Which shell is active and which tools are there (SHELL_WERKZEUG_VERTRAG_v1 §2, §10).

Two kinds of module folders: the ones in the package (`uix/shells`, `uix/tools`, trust CORE) and the ones the Captain installed
(`local_config/shells`, `local_config/tools`). `local_config/uix.yaml` names the active shell, the order of the tools and the tools
that are switched off. Nothing here reads a module's code; the gateway checks the manifests."""
from __future__ import annotations

from pathlib import Path
import os
import re
import tempfile
import threading
import time

import yaml

UIX_DIR = Path(__file__).resolve().parents[1] / 'uix'
DEFAULT_SHELL = 'start'      # der Einstieg, solange der Captain keine Oberfläche gewählt hat
MODULE_ID = re.compile(r'^[a-z0-9-]{2,40}$')


def _lesen(path) -> str:
    """Windows: eine Datei, die gerade ersetzt wird, lässt sich für einen Moment nicht öffnen (PermissionError); kurz warten und neu versuchen."""
    for versuch in range(20):
        try:
            return path.read_text(encoding='utf-8')
        except PermissionError:
            if versuch == 19: raise
            time.sleep(0.02)


class UixConfigError(ValueError):
    pass


class Registry:
    def __init__(self, project_root: Path, package_dir: Path = UIX_DIR):
        self.project_root = Path(project_root)
        self.package_dir = Path(package_dir)
        # START_SEDRA <id> (Build 18): für diesen Start eine andere Shell als in uix.yaml – die Wahl in der Datei bleibt, wie sie ist
        self.shell_override = None

    @property
    def config_path(self) -> Path:
        return self.project_root / 'local_config' / 'uix.yaml'

    def config(self) -> dict:
        """uix.yaml as a plain dict with defaults; a broken file is reported, never guessed around."""
        path = self.config_path
        raw = {}
        if path.is_file():
            try:
                raw = yaml.safe_load(_lesen(path)) or {}
            except yaml.YAMLError as exc:
                raise UixConfigError(f'uix_yaml_unreadable:{exc}') from exc
        if not isinstance(raw, dict):
            raise UixConfigError('uix_yaml_must_be_a_mapping')
        uix = raw.get('uix', raw)
        shell = self.shell_override or uix.get('shell', DEFAULT_SHELL)
        tools = uix.get('tools') or {}
        order = tools.get('order') or []
        disabled = tools.get('disabled') or []
        if not isinstance(shell, str) or not MODULE_ID.match(shell):
            raise UixConfigError('uix_yaml_shell_invalid')
        for name, value in (('order', order), ('disabled', disabled)):
            if not isinstance(value, list) or not all(isinstance(v, str) and MODULE_ID.match(v) for v in value):
                raise UixConfigError(f'uix_yaml_tools_{name}_invalid')
        return {'shell': shell, 'order': list(order), 'disabled': list(disabled), 'from_file': path.is_file()}

    def save_config(self, shell=None, order=None, disabled=None) -> dict:
        """uix.yaml schreiben: aktive Shell, Reihenfolge, abgeschaltete Werkzeuge.

        Nur was mitgegeben wird, ändert sich; der Rest bleibt stehen. Geschrieben wird über eine Temp-Datei, und danach wird
        die Datei noch einmal gelesen – wenn sie nicht mehr gültig wäre, hätte der Captain sonst eine Oberfläche, die beim
        nächsten Öffnen nicht startet."""
        current = self.config()
        # die Wahl aus der Datei, nicht der Override dieses Starts: wer unter `START_SEDRA cockpit` ein Werkzeug abschaltet, soll
        # damit nicht nebenbei das Cockpit als Wahl festschreiben (gefunden in Build 19)
        shell = str(self._raw().get('shell') or DEFAULT_SHELL) if shell is None else str(shell)
        order = current['order'] if order is None else [str(t) for t in order]
        disabled = current['disabled'] if disabled is None else [str(t) for t in disabled]
        if not MODULE_ID.match(shell):
            raise UixConfigError('uix_yaml_shell_invalid')
        for name, value in (('order', order), ('disabled', disabled)):
            if not all(MODULE_ID.match(v) for v in value):
                raise UixConfigError(f'uix_yaml_tools_{name}_invalid')
        doc = {'uix': {'shell': shell, 'tools': {'order': order, 'disabled': sorted(set(disabled))}}}
        shelf = self._raw().get('shelf')
        if shelf:                                   # Build 19: die eigene Ablage steht daneben und überlebt jeden Shell-Wechsel
            doc['uix']['shelf'] = shelf
        return self._write(doc)

    def _raw(self) -> dict:
        """Der `uix:`-Teil der Datei, wie er ist (config() hat ihn schon geprüft)."""
        path = self.config_path
        if not path.is_file():
            return {}
        raw = yaml.safe_load(_lesen(path)) or {}
        return raw.get('uix', raw) if isinstance(raw, dict) else {}

    _SCHREIBSPERRE = threading.Lock()        # Härtung 30.10.: zwei Tabs schreiben uix.yaml nacheinander, nicht übereinander

    def _write(self, doc) -> dict:
        path = self.config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._SCHREIBSPERRE:
            fd, tmp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                    fh.write(yaml.safe_dump(doc, allow_unicode=True, sort_keys=True))
                for versuch in range(20):          # Windows: ersetzt werden darf nicht, was ein Leser gerade offen hat (PermissionError); kurz warten und neu versuchen
                    try:
                        os.replace(tmp, path); break
                    except PermissionError:
                        if versuch == 19: raise
                        time.sleep(0.02)
            except BaseException:
                try: os.unlink(tmp)
                except OSError: pass
                raise
        return self.config()

    # ---- Build 19: die eigene Ablage einer Shell (Captain 15.10.: „unten selber Aufgaben und Icons anlegen“)
    # Steht in uix.yaml und nicht im Browser: SEDRA startet jedes Mal auf einem neuen Port, und der Speicher des Browsers gehört
    # dem Port – eine Ablage dort wäre nach dem nächsten START_SEDRA leer.
    SHELF_MAX = 24
    SHELF_KINDS = ('place', 'object', 'auftrag')
    SHELF_TYPES = ('task', 'intent', 'project', 'model', 'agent', 'skill', 'logbook', 'decision', 'candidate', 'machine',
                   'hardware', 'meter', 'module', 'boundary', 'gateway')
    ICON_ID = re.compile(r'^[a-z][a-z0-9-]{1,23}$')
    OBJECT_ID = re.compile(r'^[A-Za-z0-9._:-]{1,80}$')

    def shelf(self) -> dict:
        """{shell id: [Eintrag, …]} – nur gültige Einträge; eine von Hand kaputt geschriebene Ablage fällt auf die Vorgabe der Shell zurück."""
        self.config()
        raw = self._raw().get('shelf') or {}
        out = {}
        if isinstance(raw, dict):
            for shell, items in raw.items():
                try:
                    out[str(shell)] = self.check_shelf(items)
                except UixConfigError:
                    continue
        return out

    def check_shelf(self, items) -> list:
        if not isinstance(items, list) or len(items) > self.SHELF_MAX:
            raise UixConfigError('shelf_must_be_a_list_of_at_most_%d' % self.SHELF_MAX)
        out = []
        for it in items:
            if not isinstance(it, dict) or it.get('kind') not in self.SHELF_KINDS:
                raise UixConfigError('shelf_entry_kind_invalid')
            label = str(it.get('label') or '').strip()
            if not label or len(label) > 24:
                raise UixConfigError('shelf_entry_label_1_to_24_chars')
            icon = str(it.get('icon') or 'star')
            if not self.ICON_ID.match(icon):
                raise UixConfigError('shelf_entry_icon_invalid')
            entry = {'kind': it['kind'], 'label': label, 'icon': icon}
            if it['kind'] == 'place':
                place = str(it.get('place') or '')
                if not MODULE_ID.match(place):
                    raise UixConfigError('shelf_entry_place_invalid')
                entry['place'] = place
            elif it['kind'] == 'object':
                obj = it.get('object') or {}
                if not isinstance(obj, dict) or obj.get('type') not in self.SHELF_TYPES or not self.OBJECT_ID.match(str(obj.get('id') or '')):
                    raise UixConfigError('shelf_entry_object_invalid')
                entry['object'] = {'type': obj['type'], 'id': str(obj['id']), 'title': str(obj.get('title') or label)[:60]}
                if obj.get('collection'):
                    entry['object']['collection'] = True
            else:
                text = str(it.get('text') or '').strip()
                if not text or len(text) > 400:
                    raise UixConfigError('shelf_entry_text_1_to_400_chars')
                entry['text'] = text
            out.append(entry)
        return out

    def save_shelf(self, shell: str, items) -> list:
        """Die Ablage einer Shell schreiben; `items=None` nimmt sie heraus (dann gilt wieder die Vorgabe der Shell)."""
        if not MODULE_ID.match(str(shell or '')):
            raise UixConfigError('uix_yaml_shell_invalid')
        checked = None if items is None else self.check_shelf(items)
        current = self.config()
        raw = self._raw()
        shelf = dict(raw.get('shelf') or {}) if isinstance(raw.get('shelf'), dict) else {}
        if checked is None:
            shelf.pop(shell, None)
        else:
            shelf[shell] = checked
        doc = {'uix': {'shell': str(raw.get('shell') or DEFAULT_SHELL),
                       'tools': {'order': current['order'], 'disabled': sorted(set(current['disabled']))}}}
        if shelf:
            doc['uix']['shelf'] = shelf
        self._write(doc)
        return checked or []

    def roots(self, kind: str):
        """(folder, origin) pairs for 'shells' or 'tools': package first, then the Captain's own."""
        if kind not in ('shells', 'tools'):
            raise ValueError('unknown_module_kind')
        return [(self.package_dir / kind, 'package'), (self.project_root / 'local_config' / kind, 'local')]

    def module_dirs(self, kind: str):
        """Every candidate folder with its origin; a local module never replaces a package module of the same id."""
        seen, out = set(), []
        for root, origin in self.roots(kind):
            if not root.is_dir():
                continue
            for d in sorted(root.iterdir()):
                if not d.is_dir() or d.name.startswith(('_', '.')):
                    continue                                    # _template is a template, not a module
                if d.name in seen:
                    out.append((d, origin, 'duplicate_id'))
                    continue
                seen.add(d.name)
                out.append((d, origin, None))
        return out

    def ordered(self, ids):
        """The tool ids in the Captain's order (uix.yaml), the rest alphabetically after them."""
        order = self.config()['order']
        rank = {t: i for i, t in enumerate(order)}
        return sorted(ids, key=lambda t: (rank.get(t, len(order)), t))
