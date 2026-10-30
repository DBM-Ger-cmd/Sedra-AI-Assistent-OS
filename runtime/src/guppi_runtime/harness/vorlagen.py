"""Vorlagen der Harness-Shell (SPEC_HARNESS_SHELL_v1 HS-19, G2 Stufe 3 §3, G3 Stufe 3 N1).

Eine Vorlage ist eine YAML-Datei (Daten) mit einer Markdown-Datei daneben (Systemprompt): `runtime/config/harness_vorlagen/<id>.yaml`.
Eine gleichnamige Datei in `local_config/harness_vorlagen/` des Projekts (Captain) hat Vorrang. Eine ungültige Vorlage ist ein Fehler
mit Grund, nie ein stiller Rückfall. `werkzeuge` ist eine Whitelist; die Rechte prüft der Server bei jedem Aufruf, nicht die Vorlage allein.
Diese Datei liest; geschrieben wird nur über `grenzen_schreiben` (Stufe 5, D-U4) – und das ruft allein der Applier eines freigegebenen
Antrags (`harness/antraege.py`), nie ein Weg der API direkt."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from .werkzeuge import NAMEN as HARNESS_WERKZEUGE

VORLAGEN_DIR = Path(__file__).resolve().parents[3] / 'config' / 'harness_vorlagen'
ID = re.compile(r'[a-z0-9][a-z0-9-]{0,31}')
SYSTEM_MAX = 12_000
# Werkzeuge, die spätere Aufgaben von Stufe 3 liefern; eine Vorlage darf sie schon nennen, die Kiste bietet nur, was es gibt.
VORGESEHEN = ('lauf_starten', 'lauf_stoppen', 'lauf_status', 'freigaben_offen', 'freigabe_entscheiden', 'aufgabe_vorschlagen', 'aufgabe_beenden')
RECHTE = ('vorarbeiter_freigabe', 'aufgaben_vorschlagen')


class VorlageFehler(ValueError):
    """Die Vorlage ist ungültig oder unbekannt; der Text nennt den Grund."""


def _chat_namen():
    from ..chat_tools import SCHEMAS
    return tuple(SCHEMAS)


def bekannte_werkzeuge():
    return tuple(HARNESS_WERKZEUGE) + VORGESEHEN + _chat_namen()


def pruefen(doc, system_text, bekannt=None):
    """Die Vorlage als Dict – oder VorlageFehler mit Grund."""
    v = doc.get('harness_vorlage') if isinstance(doc, dict) else None
    if not isinstance(v, dict):
        raise VorlageFehler('vorlage_fehlt: die Datei braucht „harness_vorlage:“')
    vid = v.get('id')
    if not isinstance(vid, str) or not ID.fullmatch(vid):
        raise VorlageFehler('id_ungueltig: kleine Buchstaben, Ziffern und Bindestrich')
    if not isinstance(v.get('name'), str) or not v['name'].strip():
        raise VorlageFehler(f'{vid}_name_fehlt')
    if not isinstance(system_text, str) or not system_text.strip():
        raise VorlageFehler(f'{vid}_system_leer')
    if len(system_text) > SYSTEM_MAX:
        raise VorlageFehler(f'{vid}_system_zu_lang: höchstens {SYSTEM_MAX} Zeichen')
    werkzeuge = v.get('werkzeuge')
    if not isinstance(werkzeuge, list) or not werkzeuge or not all(isinstance(w, str) for w in werkzeuge):
        raise VorlageFehler(f'{vid}_werkzeuge_fehlen: eine Liste von Werkzeugnamen')
    bekannt = tuple(bekannt) if bekannt is not None else bekannte_werkzeuge()
    unbekannt = [w for w in werkzeuge if w not in bekannt]
    if unbekannt:
        raise VorlageFehler(f'{vid}_werkzeug_unbekannt: {", ".join(unbekannt)}')
    rechte = v.get('rechte') or {}
    if not isinstance(rechte, dict) or any(k not in RECHTE or not isinstance(x, bool) for k, x in rechte.items()):
        raise VorlageFehler(f'{vid}_rechte_ungueltig: erlaubt {", ".join(RECHTE)} (wahr/falsch)')
    zuege = v.get('max_zuege', 24)
    if not isinstance(zuege, int) or isinstance(zuege, bool) or not 4 <= zuege <= 40:
        raise VorlageFehler(f'{vid}_max_zuege_ungueltig: 4 bis 40')
    frist = v.get('frist_min', 15)
    if not isinstance(frist, int) or isinstance(frist, bool) or not 5 <= frist <= 60:
        raise VorlageFehler(f'{vid}_frist_min_ungueltig: 5 bis 60')
    bremse = v.get('bremse_pro_stunde', 30)
    if not isinstance(bremse, int) or isinstance(bremse, bool) or not 1 <= bremse <= 100:
        raise VorlageFehler(f'{vid}_bremse_pro_stunde_ungueltig: 1 bis 100')
    modell = v.get('modell')
    if modell is not None and not isinstance(modell, str):
        raise VorlageFehler(f'{vid}_modell_ungueltig')
    return {'id': vid, 'name': v['name'].strip(), 'beschreibung': str(v.get('beschreibung') or '').strip(), 'system': system_text.strip(),
            'werkzeuge': list(dict.fromkeys(werkzeuge)), 'rechte': {k: bool(rechte.get(k, False)) for k in RECHTE},
            'modell': modell, 'max_zuege': zuege, 'frist_min': frist, 'bremse_pro_stunde': bremse}


def _lesen(yaml_pfad: Path):
    try:
        text = yaml_pfad.read_text(encoding='utf-8')
        doc = yaml.safe_load(text)
    except (OSError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise VorlageFehler(f'datei_unlesbar: {yaml_pfad.name}: {type(exc).__name__}') from exc
    v = doc.get('harness_vorlage') if isinstance(doc, dict) else None
    name = v.get('system') if isinstance(v, dict) else None
    if not isinstance(name, str) or not name or Path(name).name != name or not name.endswith('.md'):
        raise VorlageFehler(f'{yaml_pfad.stem}_system_ungueltig: eine .md-Datei im selben Ordner')
    md = yaml_pfad.with_name(name)
    try:
        system_text = md.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as exc:
        raise VorlageFehler(f'{yaml_pfad.stem}_system_unlesbar: {name}') from exc
    vorlage = pruefen(doc, system_text)
    if vorlage['id'] != yaml_pfad.stem:
        raise VorlageFehler(f'{yaml_pfad.stem}_id_passt_nicht: Dateiname und id müssen gleich sein')
    vorlage['hash'] = hashlib.sha256((text + '\n--\n' + system_text).encode('utf-8')).hexdigest()
    return vorlage


def _ordner(projekt_root, repo_dir):
    return [Path(projekt_root) / 'local_config' / 'harness_vorlagen', Path(repo_dir)]


def laden(projekt_root, vorlage_id, repo_dir=VORLAGEN_DIR):
    """Eine Vorlage nach ID (Captain-Ordner vor Repo). Unbekannt oder ungültig → VorlageFehler."""
    if not isinstance(vorlage_id, str) or not ID.fullmatch(vorlage_id):
        raise VorlageFehler('vorlage_unbekannt')
    for ordner in _ordner(projekt_root, repo_dir):
        pfad = ordner / (vorlage_id + '.yaml')
        if pfad.is_file():
            v = _lesen(pfad)
            v['quelle'] = 'local_config' if ordner.name == 'harness_vorlagen' and ordner.parent.name == 'local_config' else 'repo'
            return v
    raise VorlageFehler('vorlage_unbekannt')


def liste(projekt_root, repo_dir=VORLAGEN_DIR):
    """Alle Vorlagen ohne den Systemtext; ungültige erscheinen mit `fehler`, damit sie nicht still fehlen."""
    ids = {}
    for ordner in _ordner(projekt_root, repo_dir):
        if ordner.is_dir():
            for p in sorted(ordner.glob('*.yaml')):
                ids.setdefault(p.stem, None)
    out = []
    for vid in sorted(ids):
        try:
            v = laden(projekt_root, vid, repo_dir)
            out.append({k: v[k] for k in ('id', 'name', 'beschreibung', 'werkzeuge', 'rechte', 'modell', 'max_zuege', 'hash', 'quelle')} | {'fehler': None})
        except VorlageFehler as exc:
            out.append({'id': vid, 'name': vid, 'fehler': str(exc)})
    return out


class Begrenzt:
    """Die Werkzeugkiste einer Sitzung mit Vorlage: bietet nur die Whitelist der Vorlage und lehnt andere Aufrufe ab (der Server prüft, nicht nur das Angebot).
    Alles andere (`aufruf`, `call`, `festhalten`, `wirkung` …) reicht sie an die Kiste durch – fehlt es dort, fehlt es hier (die Schleife fragt mit `hasattr`)."""

    def __init__(self, box, erlaubt):
        self._box = box
        self.names = tuple(n for n in box.names if n in set(erlaubt))
        self._erlaubt = frozenset(self.names)

    def schemas(self):
        return [s for s in self._box.schemas() if s['function']['name'] in self._erlaubt]

    def __getattr__(self, attr):
        inner = getattr(self._box, attr)
        if attr == 'aufruf':
            def aufruf(name, args, **kw):
                if name not in self._erlaubt:
                    return {'status': 'fehler', 'ergebnis': f'error: Werkzeug {name} ist in dieser Vorlage nicht erlaubt', 'stufe': None, 'regel': None, 'wirkung': False}
                return inner(name, args, **kw)
            return aufruf
        if attr == 'call':
            return lambda name, args: inner(name, args) if name in self._erlaubt else f'error: Werkzeug {name} ist in dieser Vorlage nicht erlaubt'
        return inner


# ---------------------------------------------------------------- Stufe 5: Grenzen (D-U4) – Kopie der Vorlage mit anderem max_zuege
def grenzen_schreiben(projekt_root, vorlage_id, max_zuege, repo_dir=VORLAGEN_DIR):
    """Kopie der Vorlage (`.yaml` + `.md`) nach `local_config/harness_vorlagen/`, nur `max_zuege` geändert; eine vorhandene Kopie wird
    vorher gesichert (`.bak-<zeit>`). Rückgabe {datei, sicherung, max_zuege, quelle_vorher}. Nur der Applier ruft das."""
    import time
    from ..core.util import atomic_write_text
    if not isinstance(max_zuege, int) or isinstance(max_zuege, bool) or not 4 <= max_zuege <= 40:
        raise VorlageFehler('max_zuege_ungueltig: 4 bis 40')
    v = laden(projekt_root, vorlage_id, repo_dir)                       # unbekannt/ungültig → VorlageFehler
    quelle = next(o / (vorlage_id + '.yaml') for o in _ordner(projekt_root, repo_dir) if (o / (vorlage_id + '.yaml')).is_file())
    doc = yaml.safe_load(quelle.read_text(encoding='utf-8'))
    doc['harness_vorlage']['max_zuege'] = max_zuege
    pruefen(doc, v['system'])
    ziel_dir = Path(projekt_root) / 'local_config' / 'harness_vorlagen'
    ziel_dir.mkdir(parents=True, exist_ok=True)
    ziel = ziel_dir / (vorlage_id + '.yaml')
    sicherung = None
    if ziel.is_file():
        sicherung = ziel.with_name(ziel.name + '.bak-' + time.strftime('%Y%m%d-%H%M%S'))
        n = 0
        while sicherung.exists():
            n += 1
            sicherung = ziel.with_name(ziel.name + f'.bak-{time.strftime("%Y%m%d-%H%M%S")}-{n}')
        sicherung.write_bytes(ziel.read_bytes())
    md_quelle = quelle.with_name(doc['harness_vorlage']['system'])
    md_ziel = ziel_dir / md_quelle.name
    if md_quelle.resolve() != md_ziel.resolve():
        atomic_write_text(md_ziel, md_quelle.read_text(encoding='utf-8'))
    kopf = (f'# Kopie der Vorlage „{vorlage_id}“ mit geänderter Grenze (max_zuege) – geschrieben über die Einstellungen der Harness-Shell\n'
            '# (Stufe 5, D-U4) nach Freigabe im Posteingang. Löschen dieser Datei stellt die Vorlage des Repos wieder her.\n')
    atomic_write_text(ziel, kopf + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120))
    return {'datei': str(ziel), 'sicherung': str(sicherung) if sicherung else None, 'max_zuege': max_zuege, 'quelle_vorher': v['quelle']}
