"""Desktop Builder und Profile (Captain 05.11.2026: die Harness wird der zentrale Punkt und lässt sich für spätere Auftraggeber zuschneiden, wie es die KMU-Shell vorgemacht hat).

Zwei Ebenen, beide nur Zuschnitt der Oberfläche – eine Wahl, keine Erlaubnis; sie vergibt keine Rechte und ändert keinen Schutz (Rechte und Positivliste eines Betreibers sind die
Richtlinie, Stufe 4 des Apps-Modells, nicht hier):
  * die **Wahl** (`desktop.json`): was im Start-Menü und in der Taskleiste erscheint, wohin es gehört, und die Marke (Name, Akzentfarbe);
  * die **Profile** (`profile/<id>.json`): benannte Wahlen mit Auftraggeber und Beschreibung, speicher-, anwend-, export- und importierbar – ein Profil je Auftraggeber.
Grundfunktionen bleiben erreichbar (ENTWURF_APPS_MODELL §2.2a): das Gespräch, der Posteingang und die Aufgaben lassen sich weder ausblenden noch wegsortieren. Leer heißt: die Vorgabe
der Shell. Ablage: `<Projekt>/runtime_data/harness/`; die Oberfläche legt die Wahl über die Vorgabe (startmenue.js, taskleiste.js, desktop.js)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ORDNER = ('runtime_data', 'harness')
GRUPPEN = ('arbeit', 'modelle', 'token', 'wissen', 'system', 'pruefung')     # wie start_gruppen.json / startliste.js
GRUND_START = ('decisions', 'tasks')            # Orte (ui/places.js): Posteingang und Aufgaben – nie ausblendbar
GRUND_ZELLEN = ('decisions',)                   # die Zelle Freigaben der Taskleiste
ID = re.compile(r'^[a-z0-9][a-z0-9_.:-]{0,59}$')
PROFIL_ID = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')
FARBE = re.compile(r'^#[0-9a-fA-F]{6}$')
MAX_LISTE = 80
MAX_PROFILE = 40
LEER = {'start': {'ausblenden': [], 'zuordnung': {}}, 'zellen': {'ausblenden': [], 'reihenfolge': []}, 'marke': {'name': '', 'akzent': ''}}


def _datei(projekt_root):
    return Path(projekt_root).joinpath(*ORDNER, 'desktop.json')


def _profile(projekt_root):
    return Path(projekt_root).joinpath(*ORDNER, 'profile')


def _schreiben(pfad, daten):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix('.tmp')
    tmp.write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(pfad)


def _ids(wert, name):
    if wert is None:
        return []
    if not isinstance(wert, list) or len(wert) > MAX_LISTE:
        raise ValueError(f'desktop_{name}_ungueltig')
    out = []
    for x in wert:
        if not isinstance(x, str) or not ID.match(x):
            raise ValueError(f'desktop_{name}_ungueltig')
        if x not in out:
            out.append(x)
    return out


def pruefen(roh):
    """Die Wahl prüfen und normieren; fehlende Teile sind leer. Wirft ValueError mit einem Kennwort, wenn etwas nicht stimmt (auch bei dem Versuch, eine Grundfunktion auszublenden)."""
    roh = {} if roh is None else roh
    if not isinstance(roh, dict) or set(roh) - {'start', 'zellen', 'marke'}:
        raise ValueError('desktop_unbekannter_schluessel')
    start, zellen, marke = roh.get('start') or {}, roh.get('zellen') or {}, roh.get('marke') or {}
    if (not isinstance(start, dict) or set(start) - {'ausblenden', 'zuordnung'} or not isinstance(zellen, dict) or set(zellen) - {'ausblenden', 'reihenfolge'}
            or not isinstance(marke, dict) or set(marke) - {'name', 'akzent'}):
        raise ValueError('desktop_unbekannter_schluessel')
    zuordnung = start.get('zuordnung') or {}
    if not isinstance(zuordnung, dict) or len(zuordnung) > MAX_LISTE:
        raise ValueError('desktop_zuordnung_ungueltig')
    for k, g in zuordnung.items():
        if not isinstance(k, str) or not ID.match(k) or g not in GRUPPEN:
            raise ValueError('desktop_zuordnung_ungueltig')
    aus_start, aus_zellen = _ids(start.get('ausblenden'), 'ausblenden'), _ids(zellen.get('ausblenden'), 'ausblenden')
    if set(aus_start) & set(GRUND_START) or set(aus_zellen) & set(GRUND_ZELLEN):
        raise ValueError('desktop_grundfunktion: Posteingang, Aufgaben und die Zelle Freigaben bleiben immer erreichbar')
    name, akzent = marke.get('name') or '', marke.get('akzent') or ''
    if not isinstance(name, str) or len(name) > 40 or not isinstance(akzent, str) or (akzent and not FARBE.match(akzent)):
        raise ValueError('desktop_marke_ungueltig: Name höchstens 40 Zeichen, Akzent als #rrggbb')
    return {'start': {'ausblenden': aus_start, 'zuordnung': dict(zuordnung)},
            'zellen': {'ausblenden': aus_zellen, 'reihenfolge': _ids(zellen.get('reihenfolge'), 'reihenfolge')},
            'marke': {'name': name.strip(), 'akzent': akzent}}


def _leer():
    return json.loads(json.dumps(LEER))


def laden(projekt_root):
    """Die gespeicherte Wahl samt aktivem Profil und Profilliste; fehlt die Datei oder ist sie kaputt, gilt die Vorgabe der Shell (leer) – nie ein Fehler beim Start."""
    try:
        roh = json.loads(_datei(projekt_root).read_text(encoding='utf-8'))
        wahl = pruefen({k: roh.get(k) for k in ('start', 'zellen', 'marke')})
        profil = roh.get('profil') if isinstance(roh.get('profil'), str) and PROFIL_ID.match(roh['profil']) else None
    except (OSError, ValueError, AttributeError):
        wahl, profil = _leer(), None
    return dict(wahl, profil=profil, profile=profile_liste(projekt_root))


def _sichern(projekt_root, wahl, profil):
    _schreiben(_datei(projekt_root), dict(wahl, profil=profil))
    return dict(wahl, profil=profil, profile=profile_liste(projekt_root))


def speichern(projekt_root, aenderung):
    """Teile ersetzen: `start`, `zellen` und/oder `marke`; `null` setzt den Teil auf die Vorgabe zurück. Eine Änderung löst die Bindung an ein Profil (`profil` wird leer)."""
    if not isinstance(aenderung, dict) or not aenderung or set(aenderung) - {'start', 'zellen', 'marke'}:
        raise ValueError('desktop_aenderung_fehlt: start, zellen oder marke')
    jetzt = laden(projekt_root)
    neu = {k: jetzt[k] for k in ('start', 'zellen', 'marke')}
    for teil in aenderung:
        neu[teil] = pruefen({teil: aenderung[teil]})[teil]
    return _sichern(projekt_root, neu, None)


# ---- Profile
def profile_liste(projekt_root):
    out = []
    for p in sorted(_profile(projekt_root).glob('*.json')):
        try:
            d = json.loads(p.read_text(encoding='utf-8'))
            if PROFIL_ID.match(p.stem) and isinstance(d, dict):
                out.append({'id': p.stem, 'name': str(d.get('name') or p.stem)[:60], 'auftraggeber': str(d.get('auftraggeber') or '')[:60], 'beschreibung': str(d.get('beschreibung') or '')[:200]})
        except (OSError, ValueError):
            continue
    return out


def _profil_id(wert):
    if not isinstance(wert, str) or not PROFIL_ID.match(wert):
        raise ValueError('profil_id_ungueltig: 2 bis 40 Zeichen, a-z, 0-9 und Bindestrich')
    return wert


def profil_lesen(projekt_root, pid):
    """Ein Profil (auch zum Exportieren): {id, name, auftraggeber, beschreibung, start, zellen, marke}."""
    pid = _profil_id(pid)
    try:
        d = json.loads((_profile(projekt_root) / (pid + '.json')).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise ValueError('profil_unbekannt')
    return dict(pruefen({k: d.get(k) for k in ('start', 'zellen', 'marke')}), id=pid, name=str(d.get('name') or pid)[:60], auftraggeber=str(d.get('auftraggeber') or '')[:60],
                beschreibung=str(d.get('beschreibung') or '')[:200])


def profil_speichern(projekt_root, pid, name, auftraggeber='', beschreibung='', wahl=None):
    """Die Wahl (oder eine übergebene, z. B. beim Importieren) als Profil ablegen; ein vorhandenes Profil gleicher ID wird ersetzt."""
    pid = _profil_id(pid)
    name = str(name or '').strip()
    if not name or len(name) > 60:
        raise ValueError('profil_name_ungueltig: 1 bis 60 Zeichen')
    if pid not in [p['id'] for p in profile_liste(projekt_root)] and len(profile_liste(projekt_root)) >= MAX_PROFILE:
        raise ValueError('profile_zu_viele')
    if wahl is None:
        jetzt = laden(projekt_root)
        wahl = {k: jetzt[k] for k in ('start', 'zellen', 'marke')}
    inhalt = dict(pruefen(wahl), name=name, auftraggeber=str(auftraggeber or '').strip()[:60], beschreibung=str(beschreibung or '').strip()[:200])
    _schreiben(_profile(projekt_root) / (pid + '.json'), inhalt)
    return dict(inhalt, id=pid)


def profil_anwenden(projekt_root, pid):
    """Das Profil wird zur Wahl; `profil` merkt, welches gilt."""
    p = profil_lesen(projekt_root, pid)
    return _sichern(projekt_root, {k: p[k] for k in ('start', 'zellen', 'marke')}, p['id'])


def profil_loeschen(projekt_root, pid):
    pid = _profil_id(pid)
    p = _profile(projekt_root) / (pid + '.json')
    if not p.exists():
        raise ValueError('profil_unbekannt')
    p.unlink()
    jetzt = laden(projekt_root)
    if jetzt['profil'] == pid:                                       # das gelöschte Profil galt: die Wahl bleibt, die Bindung fällt
        return _sichern(projekt_root, {k: jetzt[k] for k in ('start', 'zellen', 'marke')}, None)
    return jetzt


def aktion(projekt_root, payload):
    """Die Profil-Aktionen des POST: profil_speichern {id, name, auftraggeber?, beschreibung?} · profil_anwenden {id} · profil_loeschen {id} · profil_importieren {profil: {...}}."""
    a = payload.get('aktion')
    if a == 'profil_speichern':
        profil_speichern(projekt_root, payload.get('id'), payload.get('name'), payload.get('auftraggeber'), payload.get('beschreibung'))
        jetzt = laden(projekt_root)
        return _sichern(projekt_root, {k: jetzt[k] for k in ('start', 'zellen', 'marke')}, payload['id'])
    if a == 'profil_anwenden':
        return profil_anwenden(projekt_root, payload.get('id'))
    if a == 'profil_loeschen':
        return profil_loeschen(projekt_root, payload.get('id'))
    if a == 'profil_importieren':
        p = payload.get('profil')
        if not isinstance(p, dict):
            raise ValueError('profil_fehlt')
        profil_speichern(projekt_root, p.get('id'), p.get('name'), p.get('auftraggeber'), p.get('beschreibung'), {k: p.get(k) for k in ('start', 'zellen', 'marke')})
        return laden(projekt_root)
    raise ValueError('aktion_unbekannt: profil_speichern, profil_anwenden, profil_loeschen, profil_importieren')
