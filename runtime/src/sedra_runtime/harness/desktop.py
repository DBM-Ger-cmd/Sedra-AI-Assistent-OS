"""Desktop Builder und Profile (Captain 05.11.2026: die Harness wird der zentrale Punkt und lässt sich für spätere Auftraggeber zuschneiden, wie es die KMU-Shell vorgemacht hat).

Zwei Ebenen, beide nur Zuschnitt der Oberfläche – eine Wahl, keine Erlaubnis; sie vergibt keine Rechte und ändert keinen Schutz (Rechte und Positivliste eines Betreibers sind die
Richtlinie, Stufe 4 des Apps-Modells, nicht hier):
  * die **Wahl** (`desktop.json`): was im Start-Menü und in der Taskleiste erscheint, wohin es gehört, die Marke (Name, Akzentfarbe, Logo, Schrift), die Startseite (welche App
    beim Start vorn liegt, Titel und Text der Begrüßung) und das **Layout** (Baukasten und Raster: die Bausteine der leeren Sitzung auf einem 12-Spalten-Raster, Reihenfolge und
    Sichtbarkeit der Bausteine in den beiden Leisten des Eingabebereichs);
  * die **Profile** (`profile/<id>.json`): benannte Wahlen mit Auftraggeber und Beschreibung, speicher-, anwend-, export- und importierbar – ein Profil je Auftraggeber.
Grundfunktionen bleiben erreichbar (ENTWURF_APPS_MODELL §2.2a): das Gespräch, der Posteingang und die Aufgaben lassen sich weder ausblenden noch wegsortieren. Leer heißt: die Vorgabe
der Shell. Ablage: `<Projekt>/runtime_data/harness/`; die Oberfläche legt die Wahl über die Vorgabe (startmenue.js, taskleiste.js, desktop.js)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ORDNER = ('runtime_data', 'harness')
GRUPPEN = ('arbeit', 'modelle', 'token', 'wissen', 'system', 'pruefung')     # wie start_gruppen.json / startliste.js
GRUND_START = ('decisions', 'tasks', 'wissen')  # Orte (ui/places.js): Posteingang, Aufgaben und Wissen (SPEC_WISSEN_KERN_v1 WK-04) – nie ausblendbar
GRUND_ZELLEN = ('decisions',)                   # die Zelle Freigaben der Taskleiste
ID = re.compile(r'^[a-z0-9][a-z0-9_.:-]{0,59}$')
PROFIL_ID = re.compile(r'^[a-z0-9][a-z0-9-]{1,39}$')
FARBE = re.compile(r'^#[0-9a-fA-F]{6}$')
MAX_LISTE = 80
MAX_PROFILE = 40
TEILE = ('start', 'zellen', 'marke', 'startseite', 'layout')
# Baukasten: die Bausteine, die sich anpassen lassen (die Namen stehen in bausteine.js); Grundfunktionen lassen sich verschieben, aber nie ausblenden
START_BLOECKE = ('gruss', 'schritte', 'hilfe')                                 # die leere Sitzung: Begrüßung, die drei Schritte, der Hilfetext
ZEILE_BAUSTEINE = ('projekt', 'vorlage', 'ordner', 'neues-projekt', 'vorgabe')    # die Zeile unter dem Eingabefeld
WERKZEUG_BAUSTEINE = ('plus', 'schild', 'modell', 'mikro', 'senden')              # die Leiste im Eingabefeld
GRUND_WERKZEUGE = ('schild', 'senden')                                            # wer freigibt und das Senden bleiben immer sichtbar
MENUE_BAUSTEINE = ('zuletzt', 'blick', 'gruppen', 'oberflaechen', 'darstellung')    # die Abschnitte des Start-Menüs: zuletzt benutzt, Auf einen Blick, die Gruppen der Apps, Oberflächen, Darstellung
GRUND_MENUE = ('gruppen',)                                                        # die App-Gruppen sind das Start-Menü: verschiebbar, nie ausblendbar
BLICK_BAUSTEINE = ('aufgaben', 'labor', 'token', 'hardware', 'modelle', 'einstellungen')   # die Kacheln „Auf einen Blick“
GRUND_BLICK = ('einstellungen',)                                                  # der Weg in die Einstellungen bleibt
# Seitenaufbau (Stufe 3): wo die großen Zonen stehen. Keine Zone verschwindet (Seitenleiste, Eingabefeld und Taskleiste sind Grundfunktionen), sie wechseln nur den Platz oder die Breite.
ZONEN_PLATZ = {'seite': ('links', 'rechts'), 'taskleiste': ('unten', 'oben'), 'eingabe': ('unten', 'oben')}
SEITE_BREITE, EINGABE_BREITE = (180, 480), (480, 1400)                            # in Pixel; 0 = die Breite der Shell
ZONEN_VORGABE = {'seite': {'platz': 'links', 'breite': 0}, 'taskleiste': {'platz': 'unten'}, 'eingabe': {'platz': 'unten', 'breite': 0}}
RASTER_SPALTEN, RASTER_ZEILEN, RASTER_HOEHE = 12, 40, 20
SCHRIFTEN = ('serif', 'mono', 'humanist', 'breit')      # Schriftfamilien ohne Nachladen aus dem Netz; leer = die Schrift der Shell (die Stapel stehen in desktop.js)
LOGO = re.compile(r'^data:image/(?:png|jpeg|webp|svg\+xml);base64,[A-Za-z0-9+/]+={0,2}$')
LOGO_MAX = 200_000                                      # Zeichen der Daten-Adresse, rund 150 KB Bild: ein Logo gehört in das Profil, nicht in eine Bilddatei daneben
LEER = {'start': {'ausblenden': [], 'zuordnung': {}}, 'zellen': {'ausblenden': [], 'reihenfolge': []}, 'marke': {'name': '', 'akzent': '', 'logo': '', 'schrift': ''},
        'startseite': {'ort': '', 'titel': '', 'text': ''},
        'layout': {'start': {}, 'zeile': {'reihenfolge': [], 'ausblenden': []}, 'werkzeuge': {'reihenfolge': [], 'ausblenden': []},
                   'menue': {'reihenfolge': [], 'ausblenden': []}, 'blick': {'reihenfolge': [], 'ausblenden': []},
                   'zonen': {'seite': {'platz': 'links', 'breite': 0}, 'taskleiste': {'platz': 'unten'}, 'eingabe': {'platz': 'unten', 'breite': 0}}}}


def _datei(projekt_root):
    return Path(projekt_root).joinpath(*ORDNER, 'desktop.json')


def _profile(projekt_root):
    return Path(projekt_root).joinpath(*ORDNER, 'profile')


VORLAGEN = Path(__file__).resolve().parents[1] / 'uix' / 'shells' / 'harness' / 'profile'     # PR-30: die Vorlagen liegen im Paket, nur lesen


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


def _raster(wert):
    """Die Bausteine der leeren Sitzung auf dem Raster: {id: {x, y, b, h, sichtbar}}; nur bekannte Bausteine, nur Zellen innerhalb von 12 Spalten und 40 Zeilen."""
    if wert is None:
        return {}
    if not isinstance(wert, dict):
        raise ValueError('desktop_layout_ungueltig')
    out = {}
    for k, b in wert.items():
        if k not in START_BLOECKE or not isinstance(b, dict) or set(b) - {'x', 'y', 'b', 'h', 'sichtbar'}:
            raise ValueError('desktop_layout_ungueltig: unbekannter Baustein %s' % str(k)[:30])
        zahlen = [b.get(n, v) for n, v in (('x', 1), ('y', 1), ('b', RASTER_SPALTEN), ('h', 1))]
        if any(type(z) is not int for z in zahlen):
            raise ValueError('desktop_layout_ungueltig: x, y, b und h sind ganze Zahlen')
        x, y, br, h = zahlen
        if not (1 <= x <= RASTER_SPALTEN and 1 <= br <= RASTER_SPALTEN and x + br - 1 <= RASTER_SPALTEN and 1 <= y <= RASTER_ZEILEN and 1 <= h <= RASTER_HOEHE):
            raise ValueError('desktop_layout_ungueltig: ausserhalb des Rasters (12 Spalten, 40 Zeilen)')
        sichtbar = b.get('sichtbar', True)
        if type(sichtbar) is not bool:
            raise ValueError('desktop_layout_ungueltig: sichtbar ist wahr oder falsch')
        out[k] = {'x': x, 'y': y, 'b': br, 'h': h, 'sichtbar': sichtbar}
    return out


def _reihe(wert, erlaubt, grund, name):
    """Eine Leiste: Reihenfolge und ausgeblendete Bausteine; nur bekannte, Grundfunktionen nie ausgeblendet."""
    wert = {} if wert is None else wert
    if not isinstance(wert, dict) or set(wert) - {'reihenfolge', 'ausblenden'}:
        raise ValueError('desktop_layout_ungueltig')
    reihe, aus = _ids(wert.get('reihenfolge'), 'reihenfolge'), _ids(wert.get('ausblenden'), 'ausblenden')
    if any(i not in erlaubt for i in reihe + aus):
        raise ValueError('desktop_layout_ungueltig: unbekannter Baustein in %s (erlaubt: %s)' % (name, ', '.join(erlaubt)))
    if set(aus) & set(grund):
        raise ValueError('desktop_grundfunktion: %s bleiben immer sichtbar' % ', '.join(grund))
    return {'reihenfolge': reihe, 'ausblenden': aus}


def _zonen(wert):
    """Der Seitenaufbau: je Zone der Platz und (Seitenleiste, Eingabefeld) die Breite in Pixel; fehlende Angaben gelten als Vorgabe der Shell."""
    wert = {} if wert is None else wert
    if not isinstance(wert, dict) or set(wert) - set(ZONEN_VORGABE):
        raise ValueError('desktop_zonen_ungueltig: seite, taskleiste, eingabe')
    out = json.loads(json.dumps(ZONEN_VORGABE))
    for zone, angabe in wert.items():
        erlaubt = {'platz'} | ({'breite'} if zone in ('seite', 'eingabe') else set())
        if not isinstance(angabe, dict) or set(angabe) - erlaubt:
            raise ValueError('desktop_zonen_ungueltig: %s kennt nur %s' % (zone, ', '.join(sorted(erlaubt))))
        if 'platz' in angabe:
            if angabe['platz'] not in ZONEN_PLATZ[zone]:
                raise ValueError('desktop_zonen_ungueltig: Platz von %s: %s' % (zone, ', '.join(ZONEN_PLATZ[zone])))
            out[zone]['platz'] = angabe['platz']
        if 'breite' in angabe:
            b, (von, bis) = angabe['breite'], (SEITE_BREITE if zone == 'seite' else EINGABE_BREITE)
            if type(b) is not int or not (b == 0 or von <= b <= bis):
                raise ValueError('desktop_zonen_ungueltig: Breite von %s: 0 (Vorgabe) oder %d bis %d' % (zone, von, bis))
            out[zone]['breite'] = b
    return out


def bereinigt(roh):
    """Gespeicherte Daten von früher (Zuschnitt, Profil): eine Grundfunktion, die erst später dazukam (Wissen, 05.11.2026), fällt still aus
    `ausblenden` heraus – sonst ginge beim Laden der ganze Zuschnitt verloren. Neues Speichern lehnt das Ausblenden weiter ab (`pruefen`)."""
    if not isinstance(roh, dict):
        return roh
    out = dict(roh)
    for teil, grund in (('start', GRUND_START), ('zellen', GRUND_ZELLEN)):
        t = out.get(teil)
        if isinstance(t, dict) and isinstance(t.get('ausblenden'), list):
            out[teil] = dict(t, ausblenden=[x for x in t['ausblenden'] if x not in grund])
    return out


def pruefen(roh):
    """Die Wahl prüfen und normieren; fehlende Teile sind leer. Wirft ValueError mit einem Kennwort, wenn etwas nicht stimmt (auch bei dem Versuch, eine Grundfunktion auszublenden)."""
    roh = {} if roh is None else roh
    if not isinstance(roh, dict) or set(roh) - set(TEILE):
        raise ValueError('desktop_unbekannter_schluessel')
    start, zellen, marke, seite = roh.get('start') or {}, roh.get('zellen') or {}, roh.get('marke') or {}, roh.get('startseite') or {}
    layout = roh.get('layout') or {}
    if not isinstance(layout, dict) or set(layout) - {'start', 'zeile', 'werkzeuge', 'menue', 'blick', 'zonen'}:
        raise ValueError('desktop_unbekannter_schluessel')
    if (not isinstance(start, dict) or set(start) - {'ausblenden', 'zuordnung'} or not isinstance(zellen, dict) or set(zellen) - {'ausblenden', 'reihenfolge'}
            or not isinstance(marke, dict) or set(marke) - {'name', 'akzent', 'logo', 'schrift'} or not isinstance(seite, dict) or set(seite) - {'ort', 'titel', 'text'}):
        raise ValueError('desktop_unbekannter_schluessel')
    zuordnung = start.get('zuordnung') or {}
    if not isinstance(zuordnung, dict) or len(zuordnung) > MAX_LISTE:
        raise ValueError('desktop_zuordnung_ungueltig')
    for k, g in zuordnung.items():
        if not isinstance(k, str) or not ID.match(k) or g not in GRUPPEN:
            raise ValueError('desktop_zuordnung_ungueltig')
    aus_start, aus_zellen = _ids(start.get('ausblenden'), 'ausblenden'), _ids(zellen.get('ausblenden'), 'ausblenden')
    if set(aus_start) & set(GRUND_START) or set(aus_zellen) & set(GRUND_ZELLEN):
        raise ValueError('desktop_grundfunktion: Posteingang, Aufgaben, Wissen und die Zelle Freigaben bleiben immer erreichbar')
    name, akzent = marke.get('name') or '', marke.get('akzent') or ''
    if not isinstance(name, str) or len(name) > 40 or not isinstance(akzent, str) or (akzent and not FARBE.match(akzent)):
        raise ValueError('desktop_marke_ungueltig: Name höchstens 40 Zeichen, Akzent als #rrggbb')
    logo, schrift = marke.get('logo') or '', marke.get('schrift') or ''
    if not isinstance(logo, str) or (logo and (len(logo) > LOGO_MAX or not LOGO.match(logo))):
        raise ValueError('desktop_logo_ungueltig: PNG, JPEG, WebP oder SVG als Daten-Adresse, höchstens %d Zeichen' % LOGO_MAX)
    if schrift not in ('',) + SCHRIFTEN:
        raise ValueError('desktop_schrift_ungueltig: ' + ', '.join(SCHRIFTEN))
    ort, titel, text = seite.get('ort') or '', seite.get('titel') or '', seite.get('text') or ''
    if not isinstance(ort, str) or (ort and not ID.match(ort)) or not isinstance(titel, str) or len(titel) > 60 or not isinstance(text, str) or len(text) > 300:
        raise ValueError('desktop_startseite_ungueltig: Ort als Kennung, Titel höchstens 60, Text höchstens 300 Zeichen')
    return {'start': {'ausblenden': aus_start, 'zuordnung': dict(zuordnung)},
            'zellen': {'ausblenden': aus_zellen, 'reihenfolge': _ids(zellen.get('reihenfolge'), 'reihenfolge')},
            'marke': {'name': name.strip(), 'akzent': akzent, 'logo': logo, 'schrift': schrift},
            'startseite': {'ort': ort, 'titel': titel.strip(), 'text': text.strip()},
            'layout': {'start': _raster(layout.get('start')), 'zeile': _reihe(layout.get('zeile'), ZEILE_BAUSTEINE, (), 'zeile'),
                       'werkzeuge': _reihe(layout.get('werkzeuge'), WERKZEUG_BAUSTEINE, GRUND_WERKZEUGE, 'werkzeuge'),
                       'menue': _reihe(layout.get('menue'), MENUE_BAUSTEINE, GRUND_MENUE, 'menue'), 'blick': _reihe(layout.get('blick'), BLICK_BAUSTEINE, GRUND_BLICK, 'blick'),
                       'zonen': _zonen(layout.get('zonen'))}}


def _leer():
    return json.loads(json.dumps(LEER))


def laden(projekt_root):
    """Die gespeicherte Wahl samt aktivem Profil und Profilliste; fehlt die Datei oder ist sie kaputt, gilt die Vorgabe der Shell (leer) – nie ein Fehler beim Start."""
    try:
        roh = json.loads(_datei(projekt_root).read_text(encoding='utf-8'))
        wahl = pruefen(bereinigt({k: roh.get(k) for k in TEILE}))
        profil = roh.get('profil') if isinstance(roh.get('profil'), str) and PROFIL_ID.match(roh['profil']) else None
    except (OSError, ValueError, AttributeError):
        wahl, profil = _leer(), None
    return dict(wahl, profil=profil, profile=profile_liste(projekt_root), vorlagen=vorlagen_liste())


def _sichern(projekt_root, wahl, profil):
    _schreiben(_datei(projekt_root), dict(wahl, profil=profil))
    return dict(wahl, profil=profil, profile=profile_liste(projekt_root), vorlagen=vorlagen_liste())


def speichern(projekt_root, aenderung):
    """Teile ersetzen: `start`, `zellen` und/oder `marke`; `null` setzt den Teil auf die Vorgabe zurück. Eine Änderung löst die Bindung an ein Profil (`profil` wird leer)."""
    if not isinstance(aenderung, dict) or not aenderung or set(aenderung) - set(TEILE):
        raise ValueError('desktop_aenderung_fehlt: start, zellen, marke oder startseite')
    jetzt = laden(projekt_root)
    neu = {k: jetzt[k] for k in TEILE}
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
    """Ein Profil (auch zum Exportieren): {id, name, auftraggeber, beschreibung, start, zellen, marke, startseite}."""
    pid = _profil_id(pid)
    try:
        d = json.loads((_profile(projekt_root) / (pid + '.json')).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise ValueError('profil_unbekannt')
    return dict(pruefen(bereinigt({k: d.get(k) for k in TEILE})), id=pid, name=str(d.get('name') or pid)[:60], auftraggeber=str(d.get('auftraggeber') or '')[:60],
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
        wahl = {k: jetzt[k] for k in TEILE}
    inhalt = dict(pruefen(wahl), name=name, auftraggeber=str(auftraggeber or '').strip()[:60], beschreibung=str(beschreibung or '').strip()[:200])
    _schreiben(_profile(projekt_root) / (pid + '.json'), inhalt)
    return dict(inhalt, id=pid)


def profil_anwenden(projekt_root, pid):
    """Das Profil wird zur Wahl; `profil` merkt, welches gilt."""
    p = profil_lesen(projekt_root, pid)
    return _sichern(projekt_root, {k: p[k] for k in TEILE}, p['id'])


def profil_loeschen(projekt_root, pid):
    pid = _profil_id(pid)
    p = _profile(projekt_root) / (pid + '.json')
    if not p.exists():
        raise ValueError('profil_unbekannt')
    p.unlink()
    jetzt = laden(projekt_root)
    if jetzt['profil'] == pid:                                       # das gelöschte Profil galt: die Wahl bleibt, die Bindung fällt
        return _sichern(projekt_root, {k: jetzt[k] for k in TEILE}, None)
    return jetzt


# ---- Vorlagen (SPEC_PROFILE_v1 PR-30, PR-34): ein Profil, das im Paket liegt. Übernehmen kopiert es einmal in die Profile des Projekts und wendet die Kopie an;
# eine vorhandene Kopie bleibt, wie sie ist (PR-E2: ein Update ändert die Vorlage, nie das Profil des Nutzers).
def vorlagen_liste():
    out = []
    for p in sorted(VORLAGEN.glob('*.json')):
        try:
            d = json.loads(p.read_text(encoding='utf-8'))
            pruefen(bereinigt({k: d.get(k) for k in TEILE}))
            if PROFIL_ID.match(p.stem) and isinstance(d, dict):
                out.append({'id': p.stem, 'name': str(d.get('name') or p.stem)[:60], 'beschreibung': str(d.get('beschreibung') or '')[:200]})
        except (OSError, ValueError):
            continue
    return out


def vorlage_lesen(vid):
    vid = _profil_id(vid)
    try:
        d = json.loads((VORLAGEN / (vid + '.json')).read_text(encoding='utf-8'))
        return dict(pruefen(bereinigt({k: d.get(k) for k in TEILE})), id=vid, name=str(d.get('name') or vid)[:60], auftraggeber=str(d.get('auftraggeber') or '')[:60],
                    beschreibung=str(d.get('beschreibung') or '')[:200])
    except (OSError, ValueError, AttributeError):
        raise ValueError('vorlage_unbekannt')


def vorlage_uebernehmen(projekt_root, vid):
    v = vorlage_lesen(vid)
    if v['id'] not in [p['id'] for p in profile_liste(projekt_root)]:
        profil_speichern(projekt_root, v['id'], v['name'], v['auftraggeber'], v['beschreibung'], {k: v[k] for k in TEILE})
    return profil_anwenden(projekt_root, v['id'])


def aktion(projekt_root, payload):
    """Die Profil-Aktionen des POST: profil_speichern {id, name, auftraggeber?, beschreibung?} · profil_anwenden {id} · profil_loeschen {id} · profil_importieren {profil: {...}}."""
    a = payload.get('aktion')
    if a == 'profil_speichern':
        profil_speichern(projekt_root, payload.get('id'), payload.get('name'), payload.get('auftraggeber'), payload.get('beschreibung'))
        jetzt = laden(projekt_root)
        return _sichern(projekt_root, {k: jetzt[k] for k in TEILE}, payload['id'])
    if a == 'profil_anwenden':
        return profil_anwenden(projekt_root, payload.get('id'))
    if a == 'profil_loeschen':
        return profil_loeschen(projekt_root, payload.get('id'))
    if a == 'vorlage_uebernehmen':
        return vorlage_uebernehmen(projekt_root, payload.get('id'))
    if a == 'profil_importieren':
        p = payload.get('profil')
        if not isinstance(p, dict):
            raise ValueError('profil_fehlt')
        profil_speichern(projekt_root, p.get('id'), p.get('name'), p.get('auftraggeber'), p.get('beschreibung'), {k: p.get(k) for k in TEILE})
        return laden(projekt_root)
    raise ValueError('aktion_unbekannt: profil_speichern, profil_anwenden, profil_loeschen, profil_importieren, vorlage_uebernehmen')
