"""Läufe der Harness-Shell, Teil 1: die Lauf-Typen (SPEC_HARNESS_SHELL_v1 HS-20, G2 Stufe 3 §6.1, G3 Stufe 3 N6).

Ein Lauf ist kein freier Befehl. `runtime/config/harness_laeufe.yaml` (Repo, harter Vorbehalt – die Datei ändert nur Claude) nennt die Lauf-Typen; `lauf_starten`
nimmt eine Lauf-ID und Parameter, die ihr Muster **ganz** erfüllen. Hier: laden, prüfen und `argv_bauen` – das fertige Argument-Feld für den Prozess,
ohne Shell-Interpreter. Starter, Hülle und Register kommen in Teil 2 (N7).

Harness-Code (Vorbehalt): SEDRA ändert diese Datei nicht an sich selbst."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

DATEI = 'harness_laeufe.yaml'
LAEUFE_DATEI = Path(__file__).resolve().parents[3] / 'config' / DATEI
ID = re.compile(r'[a-z][a-z0-9_]{0,40}')
PLATZHALTER = re.compile(r'\{([a-z][a-z0-9_]*)\}')
PROGRAMM = re.compile(r'[A-Za-z0-9_.-]+')
GPU = ('keine', 'slot', 'exklusiv')
FORTSCHRITT = {'zeilen': 2, 'prozent': 1, 'text': 0}           # Art → Zahl der Gruppen, die die Regel braucht
VERBOTEN = set(';|&<>`$()"\'\n\r\0')                            # in keinem Parameterwert (auch ohne Shell: kein Raum für Tricks)
MEHRERE_MAX = 10
ZEITLIMIT_MAX_MIN = 600


class LaufFehler(ValueError):
    """Die Datei oder der Aufruf ist ungültig; der Text nennt den Grund."""


def _bool(wert, name):
    if not isinstance(wert, bool):
        raise LaufFehler(f'{name}_kein_wahr_falsch')
    return wert


def pruefen(doc):
    """{id: Typ} aus einer gelesenen Datei – oder LaufFehler mit Grund."""
    k = doc.get('harness_laeufe') if isinstance(doc, dict) else None
    if not isinstance(k, dict) or not isinstance(k.get('laeufe'), list) or not k['laeufe']:
        raise LaufFehler('laeufe_fehlen: die Datei braucht „harness_laeufe: laeufe:“ mit mindestens einem Typ')
    out = {}
    for n, t in enumerate(k['laeufe'], 1):
        if not isinstance(t, dict):
            raise LaufFehler(f'lauf_{n}_kein_eintrag')
        lid = t.get('id')
        if not isinstance(lid, str) or not ID.fullmatch(lid):
            raise LaufFehler(f'lauf_{n}_id_ungueltig: kleine Buchstaben, Ziffern und Unterstrich')
        if lid in out:
            raise LaufFehler(f'lauf_{lid}_doppelt')
        argv = t.get('argv')
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
            raise LaufFehler(f'lauf_{lid}_argv_ungueltig: eine Liste von Texten')
        if not PROGRAMM.fullmatch(argv[0]):
            raise LaufFehler(f'lauf_{lid}_programm_ungueltig: ein Programmname ohne Pfad und Platzhalter')
        parameter = t.get('parameter') or {}
        if not isinstance(parameter, dict):
            raise LaufFehler(f'lauf_{lid}_parameter_ungueltig')
        benutzt = set()
        for a in argv[1:]:
            if '{' in a or '}' in a:
                m = PLATZHALTER.fullmatch(a)
                if not m:
                    raise LaufFehler(f'lauf_{lid}_platzhalter_ungueltig: „{a}“ – ein Platzhalter steht als ganzes Element, {{name}}')
                if m.group(1) not in parameter:
                    raise LaufFehler(f'lauf_{lid}_parameter_fehlt: „{m.group(1)}“ steht im argv, aber nicht unter parameter')
                benutzt.add(m.group(1))
        if '{' in argv[0] or '}' in argv[0]:
            raise LaufFehler(f'lauf_{lid}_programm_ungueltig')
        normal = {}
        for name, p in parameter.items():
            if not isinstance(name, str) or not ID.fullmatch(name) or not isinstance(p, dict):
                raise LaufFehler(f'lauf_{lid}_parameter_{name}_ungueltig')
            if name not in benutzt:
                raise LaufFehler(f'lauf_{lid}_parameter_{name}_unbenutzt: er steht nicht im argv')
            muster = p.get('muster')
            try:
                re.compile(muster)
            except (TypeError, re.error):
                raise LaufFehler(f'lauf_{lid}_parameter_{name}_muster_ungueltig') from None
            vorgabe = p.get('vorgabe')
            if vorgabe is not None:
                vorgabe = str(vorgabe)
            normal[name] = {'muster': muster, 'vorgabe': vorgabe, 'mehrere': _bool(p.get('mehrere', False), f'lauf_{lid}_mehrere')}
            if vorgabe is not None:
                for stueck in (vorgabe.split() if normal[name]['mehrere'] else [vorgabe]):
                    if not re.fullmatch(muster, stueck):
                        raise LaufFehler(f'lauf_{lid}_parameter_{name}_vorgabe_passt_nicht_zum_muster')
        ordner = t.get('ordner', '.')
        teile = str(ordner).replace('\\', '/').split('/')
        if not isinstance(ordner, str) or '..' in teile or re.match(r'^([A-Za-z]:|/)', ordner):
            raise LaufFehler(f'lauf_{lid}_ordner_ungueltig: relativ zur Projektwurzel, ohne „..“')
        gpu = t.get('gpu', 'keine')
        if gpu not in GPU:
            raise LaufFehler(f'lauf_{lid}_gpu_unbekannt: {", ".join(GPU)}')
        braucht_modell = _bool(t.get('braucht_modell', False), f'lauf_{lid}_braucht_modell')
        modell = t.get('modell')
        if braucht_modell and (not isinstance(modell, str) or not modell.strip()):
            raise LaufFehler(f'lauf_{lid}_modell_fehlt: wer ein Modell braucht, nennt es (Rezept oder Rolle)')
        fortschritt = t.get('fortschritt')
        if fortschritt is not None:
            art = fortschritt.get('art') if isinstance(fortschritt, dict) else None
            if art not in FORTSCHRITT:
                raise LaufFehler(f'lauf_{lid}_fortschritt_art_unbekannt: {", ".join(FORTSCHRITT)}')
            regex = fortschritt.get('regex')
            if FORTSCHRITT[art]:
                try:
                    if re.compile(regex).groups < FORTSCHRITT[art]:
                        raise LaufFehler(f'lauf_{lid}_fortschritt_gruppen: „{art}“ braucht {FORTSCHRITT[art]} Gruppe(n)')
                except (TypeError, re.error):
                    raise LaufFehler(f'lauf_{lid}_fortschritt_regex_ungueltig') from None
            fortschritt = {'art': art, 'regex': regex if FORTSCHRITT[art] else None}
        zeit = t.get('zeitlimit_min', 60)
        if not isinstance(zeit, int) or isinstance(zeit, bool) or not 1 <= zeit <= ZEITLIMIT_MAX_MIN:
            raise LaufFehler(f'lauf_{lid}_zeitlimit_ungueltig: 1 bis {ZEITLIMIT_MAX_MIN} Minuten')
        out[lid] = {'id': lid, 'name': str(t.get('name') or lid), 'argv': list(argv), 'ordner': ordner, 'parameter': normal, 'gpu': gpu,
                    'modell_weg': _bool(t.get('modell_weg', gpu == 'exklusiv'), f'lauf_{lid}_modell_weg'), 'braucht_modell': braucht_modell,
                    'modell': modell.strip() if isinstance(modell, str) else None, 'fortschritt': fortschritt, 'zeitlimit_min': zeit}
    return out


def laden(datei: Path = LAEUFE_DATEI):
    """{laeufe: {id: Typ}, datei} – ungültig oder nicht lesbar → LaufFehler (kein stiller Rückfall, kein Lauf ohne gültige Typen)."""
    try:
        doc = yaml.safe_load(Path(datei).read_text(encoding='utf-8'))
    except (OSError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise LaufFehler(f'datei_unlesbar: {Path(datei).name}: {type(exc).__name__}') from exc
    return {'laeufe': pruefen(doc), 'datei': str(datei)}


def _werte(name, p, wert):
    """Die geprüften Stücke eines Parameters (bei `mehrere` mehrere)."""
    if isinstance(wert, bool) or not isinstance(wert, (str, int)):
        raise LaufFehler(f'parameter_{name}_ungueltig: ein Text')
    text = str(wert).strip()
    stuecke = text.split() if p['mehrere'] else [text]
    if not stuecke or (p['mehrere'] and len(stuecke) > MEHRERE_MAX):
        raise LaufFehler(f'parameter_{name}_ungueltig: ' + (f'höchstens {MEHRERE_MAX} Werte' if stuecke else 'leer'))
    for s in stuecke:
        if not s or any(c in VERBOTEN or c.isspace() for c in s) or s.startswith('-') or '..' in s.replace('\\', '/').split('/'):
            raise LaufFehler(f'parameter_{name}_ungueltig: „{s[:40]}“ enthält ein unerlaubtes Zeichen')
        if not re.fullmatch(p['muster'], s):
            raise LaufFehler(f'parameter_{name}_muster: „{s[:40]}“ erfüllt das Muster des Laufs nicht')
    return stuecke


def argv_bauen(typ, parameter, wurzel):
    """{argv, ordner, ziel, bindung, typ} für einen Aufruf – oder LaufFehler. `ziel` ist die Lauf-ID (Einstufung), `bindung` hängt das Guard-Token an genau diesen Lauf
    mit genau diesen Argumenten. Programm `python` ersetzt der Starter durch den Python dieser Runtime (wie bei `befehl`)."""
    parameter = {} if parameter is None else parameter
    if not isinstance(parameter, dict):
        raise LaufFehler('parameter_kein_objekt')
    unbekannt = sorted(set(parameter) - set(typ['parameter']))
    if unbekannt:
        raise LaufFehler(f'parameter_unbekannt: {", ".join(map(str, unbekannt))}')
    werte = {}
    for name, p in typ['parameter'].items():
        wert = parameter.get(name, p['vorgabe'])
        if wert is None:
            raise LaufFehler(f'parameter_fehlt: {name}')
        werte[name] = _werte(name, p, wert)
    argv = [typ['argv'][0]]
    for a in typ['argv'][1:]:
        m = PLATZHALTER.fullmatch(a)
        argv += werte[m.group(1)] if m else [a]
    wurzel_p = Path(wurzel).resolve()
    ordner = (wurzel_p / typ['ordner']).resolve()
    try:
        ordner.relative_to(wurzel_p)
    except ValueError:
        raise LaufFehler('ordner_ausserhalb: der Ordner des Laufs liegt nicht im Projekt') from None
    if not ordner.is_dir():
        raise LaufFehler('ordner_fehlt')
    return {'argv': argv, 'ordner': ordner, 'ziel': typ['id'], 'bindung': {'lauf': typ['id'], 'argv': argv, 'ordner': typ['ordner']}, 'typ': typ}
