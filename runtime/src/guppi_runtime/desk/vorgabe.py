"""Der Creator: aus Worten eine Vorgabe (SPEC_SHELL_AUS_VORGABE_v1 Schritt 3, RECHERCHE_SHELL_CREATOR Empfehlung 3).

Drei Wege zu einer Vorgabe, alle ohne Code und ohne Gate (eigene Form, Captain 14.10.):
  1. eine der drei Vorlagen (Reiter · Fenster · Seiten) – ohne Modell
  2. ein Satz an GUPPI: das lokale Modell liefert die Vorgabe **gegen das Schema** (ModelRouter.chat(schema=…), Build 17 Schritt 1),
     danach dieselbe Prüfung wie beim Laden (gateway.check_vorgabe) – was das Modell liefert, wird nie ungeprüft angelegt
  3. von Hand in shell.vorgabe.yaml

Was eine neue *Funktion* wäre (ein Werkzeug, das es nicht gibt), kann keine Vorgabe: dann sagt der Creator es und verweist auf das
Gerüst mit Gate. Kein Modell schreibt hier Code."""
from __future__ import annotations

import json
from pathlib import Path

ZONE_WORD = {'leiste': 'die Instrumente', 'orte': 'die Orte', 'werkstueck': 'das Werkstück', 'gespraech': 'das Gespräch',
             'entscheidungen': 'die Entscheidungen', 'leer': 'eine leere Fläche'}
NACHWEIS_WORD = {'seitenleiste': 'mit den Nachweisen daneben', 'umschalter': 'mit den Nachweisen zum Umschalten',
                 'spalten': 'mit jedem Nachweis in eigener Spalte', 'keine': 'ohne Nachweise'}
PLACE_WORD = {'tasks': 'Aufgaben', 'intents': 'Vorhaben', 'boundary': 'Modus und Grenzen', 'decisions': 'Entscheidungen', 'models': 'Werkstatt',
              'library': 'Bibliothek', 'crew': 'Besatzung', 'meter': 'Guppy-Meter', 'logbook': 'Logbuch', 'hardware': 'Hardware',
              'machine': 'Maschinenraum', 'modules': 'Module', 'project': 'Projekt und Dateien', 'gateway': 'KI GateWay'}
START_WORD = {'task': 'Aufgaben', 'intent': 'Vorhaben', 'boundary': 'Modus und Grenzen', 'decision': 'Entscheidungen', 'model': 'Werkstatt',
              'skill': 'Bibliothek', 'agent': 'Besatzung', 'meter': 'Guppy-Meter', 'logbook': 'Logbuch', 'hardware': 'Hardware',
              'machine': 'Maschinenraum', 'module': 'Module', 'project': 'Projekt', 'gateway': 'KI GateWay'}
START_ID = {'task': 'alle', 'intent': 'alle', 'boundary': 'projekt', 'decision': 'alle', 'model': 'alle', 'skill': 'own', 'agent': 'alle',
            'meter': 'meter', 'logbook': 'audit', 'hardware': 'hardware', 'machine': 'machine', 'module': 'alle', 'project': 'projekt', 'gateway': 'alle'}

TEMPLATES = [
    {'id': 'reiter', 'name': 'Reiter', 'hint': 'wie das Cockpit: Instrumente oben, Orte links, Werkstück mit Nachweisen daneben, Gespräch unten',
     'vorgabe': {'raster': ['leiste', 'orte|werkstueck', 'gespraech'], 'orte': {'breite': 220}, 'werkstueck': {'nachweise': 'seitenleiste'},
                 'gespraech': {'art': 'zone', 'hoehe': 112}, 'entscheidungen': 'karte', 'suche': 'strg-k', 'start': {'type': 'task', 'id': 'alle', 'title': 'Aufgaben'}}},
    {'id': 'fenster', 'name': 'Fenster', 'hint': 'wie Minimal: nur Leiste und Werkstück, Nachweise zum Umschalten, Gespräch als Schublade, Suchfeld',
     'vorgabe': {'raster': ['leiste', 'werkstueck'], 'werkstueck': {'nachweise': 'umschalter'}, 'gespraech': {'art': 'schublade'},
                 'entscheidungen': 'karte', 'suche': 'feld', 'start': {'type': 'task', 'id': 'alle', 'title': 'Aufgaben'}}},
    {'id': 'seiten', 'name': 'Seiten', 'hint': 'wie Paperclip: Orte links, Werkstück mit Nachweisen in Spalten, Entscheidungen rechts, Gespräch unten',
     'vorgabe': {'raster': ['orte|werkstueck|entscheidungen', 'gespraech'], 'orte': {'breite': 200, 'liste': ['tasks', 'intents', 'decisions', 'models', 'logbook', 'modules']},
                 'werkstueck': {'nachweise': 'spalten'}, 'gespraech': {'hoehe': 96}, 'entscheidungen': 'karte', 'suche': 'strg-k',
                 'start': {'type': 'intent', 'id': 'alle', 'title': 'Vorhaben'}}},
]


def schema():
    return json.loads((Path(__file__).resolve().parent.parent / 'uix' / 'ui' / 'schema' / 'vorgabe.schema.json').read_text(encoding='utf-8'))


def sentence(v):
    """Die Vorgabe als ein Satz, den der Captain liest, bevor er anlegt."""
    rows = []
    for row in v.get('raster') or []:
        zones = row.split('|')
        words = []
        for z in zones:
            w = ZONE_WORD.get(z, z)
            if z == 'orte':
                o = v.get('orte') or {}
                w += f" ({o.get('breite', 220)} px" + (', nur ' + ', '.join(PLACE_WORD.get(p, p) for p in o['liste']) if o.get('liste') else '') + ')'
            if z == 'werkstueck':
                w += ' ' + NACHWEIS_WORD.get((v.get('werkstueck') or {}).get('nachweise', 'seitenleiste'))
            if z == 'gespraech':
                w += f" ({(v.get('gespraech') or {}).get('hoehe', 112)} px hoch)"
            words.append(w)
        rows.append(' | '.join(words) if len(words) > 1 else words[0])
    parts = ['Von oben nach unten: ' + '; darunter '.join(rows) + '.']
    if (v.get('gespraech') or {}).get('art') == 'schublade':
        parts.append('Das Gespräch ist eine Schublade mit Knopf.')
    parts.append('Entscheidungen ' + ('erscheinen als Karte, sobald eine wartet.' if v.get('entscheidungen', 'karte') == 'karte' else 'nur als Werkstück.'))
    parts.append({'strg-k': 'Palette mit Strg+K.', 'feld': 'Ein Suchfeld in der Leiste.', 'keine': 'Keine Suche – das Gespräch ist der Weg.'}[v.get('suche', 'strg-k')])
    st = v.get('start') or {'type': 'task'}
    parts.append('Beim Start: ' + (st.get('title') or START_WORD.get(st.get('type'), st.get('type'))) + '.')
    return ' '.join(parts)


def system_prompt():
    places = ', '.join(f'{k} ({v})' for k, v in PLACE_WORD.items())
    starts = ', '.join(f'{k} ({v})' for k, v in START_WORD.items())
    return (
        'Du baust aus dem Wunsch des Captains eine Vorgabe für eine SEDRA-Oberfläche. Du schreibst keinen Code – nur das JSON-Objekt.\n'
        'Zonen: leiste (Instrumente oben), orte (Navigation), werkstueck (das offene Objekt, Pflicht), gespraech (Eingabe), entscheidungen (Freigaben), leer.\n'
        '`raster` sind Zeilen von oben nach unten; Spalten in einer Zeile trennst du mit |, zum Beispiel "orte|werkstueck". Jede Zone höchstens einmal.\n'
        'Das Gespräch braucht eine Zeile im Raster – außer gespraech.art ist "schublade", dann hat es einen Knopf und keine Zeile.\n'
        f'Orte (orte.liste), in dieser Schreibweise: {places}.\n'
        f'Startobjekt (start.type): {starts}; start.id ist bei Sammlungen "alle", bei boundary und project "projekt", bei skill "own", sonst der Typname (meter, audit für logbook, hardware, machine).\n'
        'Nachweise (werkstueck.nachweise): seitenleiste (daneben), umschalter (Reiter), spalten (nebeneinander), keine.\n'
        'Suche: strg-k (Palette), feld (Suchfeld in der Leiste – braucht leiste), keine.\n'
        'Nimm nur, was der Captain will; was er nicht nennt, lässt du weg (es gibt Standardwerte). Kein Feld außerhalb des Schemas.\n'
        'Wünscht der Captain etwas, das keine Zone ist (ein neues Werkzeug, eine Funktion, Daten von außen), setzt du es nicht um – '
        'die Vorgabe beschreibt nur die Anordnung; der Captain sieht dann in der Antwort, was fehlt.'
    )


def check(doc):
    """Dieselbe Prüfung wie beim Laden aus dem Ordner (gateway.read_vorgabe), hier für ein Objekt aus dem Modell."""
    from ..models import structured
    problems = structured.validate(doc, schema()) if isinstance(doc, dict) else ['$: keine Vorgabe']
    if problems:
        return problems
    zones = [z for row in doc['raster'] for z in row.split('|')]
    if 'werkstueck' not in zones:
        return ['$.raster: werkstueck fehlt']
    if len(zones) != len(set(zones)):
        return ['$.raster: eine Zone kommt zweimal vor']
    if (doc.get('gespraech') or {}).get('art', 'zone') == 'zone' and 'gespraech' not in zones:
        return ['$.raster: gespraech fehlt (oder gespraech.art: schublade)']
    if doc.get('suche') == 'feld' and 'leiste' not in zones:
        return ['$.suche: ein Suchfeld braucht die Zone leiste']
    st = doc.get('start')
    if st and START_ID.get(st.get('type')) and st.get('id') != START_ID[st['type']] and st['type'] in ('task', 'intent', 'decision', 'model', 'module', 'agent'):
        return [f"$.start.id: für {st['type']} ist es „{START_ID[st['type']]}“"]
    return []


def propose(router, text, *, mission_id='uix-vorgabe', shell_id='meine', name=None):
    """Ein Satz → eine geprüfte Vorgabe. Wirft ValueError mit Satz, wenn kein Modell da ist oder nichts Gültiges kam."""
    text = str(text or '').strip()
    if not text:
        raise ValueError('Sag, wie die Oberfläche aussehen soll – zum Beispiel „links die Aufgaben, rechts das Gespräch, keine Instrumente“.')
    if len(text) > 2000:
        raise ValueError('Bitte kürzer – zweitausend Zeichen reichen für eine Anordnung.')
    try:
        router.choose()
    except Exception:
        raise ValueError('Kein Modell geladen – nimm eine der drei Vorlagen, oder lade in der Werkstatt ein Modell.')
    s = schema()
    s['required'] = ['raster']                 # id und name setzt SEDRA – das Modell beschreibt nur die Anordnung
    messages = [{'role': 'system', 'content': system_prompt()},
                {'role': 'user', 'content': f'id: {shell_id}\nname: {name or shell_id}\nWunsch: {text}', 'trust': 'captain'}]
    out = router.chat(mission_id, messages, schema=s)
    v = out['parsed']
    v['id'] = shell_id
    v['name'] = name or v.get('name') or shell_id
    problems = check(v)
    if problems:
        raise ValueError('Das Modell hat keine gültige Vorgabe geliefert: ' + '; '.join(problems[:3]) + ' – nimm eine Vorlage oder sag es anders.')
    return {'vorgabe': v, 'sentence': sentence(v), 'rounds': out.get('rounds', 1), 'model': out.get('model')}


def templates(shell_id='meine', name=None):
    out = []
    for t in TEMPLATES:
        v = dict(t['vorgabe'], id=shell_id, name=name or t['name'])
        out.append({'id': t['id'], 'name': t['name'], 'hint': t['hint'], 'vorgabe': v, 'sentence': sentence(v)})
    return out
