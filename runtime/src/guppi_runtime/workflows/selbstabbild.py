"""Selbstabbild: SEDRA beschreibt seine eigenen Abläufe als Prozessmodelle (Plan docs/PLAN_PROZESS_APPS_UIX.md, Phase 5).

Die Abläufe stehen in `runtime/config/selbstabbild.yaml`, jeder Schritt mit seiner Quelle (Datei und wörtlicher Suchtext). Daraus entstehen Prozessmodelle
im Format von `process.py`: nie ausführbar (alle Knoten deaktiviert), Menschen als Rolle, nie als technischer Schritt. Der Abweichungstest `pruefen` meldet
jeden Schritt, dessen Quelle fehlt oder deren Text sich geändert hat; `anlegen` schreibt nur, wenn alle Quellen stimmen. Es gibt keine Rückrichtung:
ein Modell ändert weder Code noch Konfiguration."""
import json
from pathlib import Path

import yaml

from ..core.request_binding import digest
from .process import PREFIX
from .schema import validate

REPO = Path(__file__).resolve().parents[4]
KONFIG = Path(__file__).resolve().parents[3] / 'config' / 'selbstabbild.yaml'
PREFIX_NAME = 'SEDRA-Selbstabbild · '
ARTEN = ('start', 'task', 'decision', 'end')
WEISEN = ('manual', 'assisted', 'automatable')
FELDER = {'lieferant': 'supplier', 'eingabe': 'input', 'ergebnis': 'output', 'empfaenger': 'customer',
          'nachweis': 'evidence', 'abschluss': 'completion', 'ausnahme': 'exception', 'rolle': 'role'}


def ablauf_pruefen(a, quelle_pflicht=True):
    """Ein Ablauf {id, name, schritte}: Form, Schrittarten, Folgeschritte, genau ein Start. Fehler: ValueError mit Satz."""
    if not isinstance(a, dict) or not isinstance(a.get('id'), str) or not isinstance(a.get('name'), str) or not a['name'].strip():
        raise ValueError('selbstabbild_ablauf_ungueltig')
    schritte = a.get('schritte')
    if not isinstance(schritte, list) or not 2 <= len(schritte) <= 32 or not all(isinstance(s, dict) for s in schritte):
        raise ValueError('selbstabbild_schritte_ungueltig: ' + a['id'])
    namen = {s.get('id'): s for s in schritte}
    if len(namen) != len(schritte) or len({s.get('name') for s in schritte}) != len(schritte) or not all(isinstance(s.get('name'), str) and s['name'].strip() for s in schritte):
        raise ValueError('selbstabbild_schritt_doppelt: ' + a['id'])
    if sum(s.get('art') == 'start' for s in schritte) != 1:
        raise ValueError('selbstabbild_genau_ein_start: ' + a['id'])
    for s in schritte:
        if s.get('art') not in ARTEN or s.get('arbeitsweise') not in WEISEN:
            raise ValueError('selbstabbild_art_oder_weise: ' + a['id'] + '.' + str(s.get('id')))
        q = s.get('quelle')
        if quelle_pflicht and (not isinstance(q, dict) or not isinstance(q.get('datei'), str) or not isinstance(q.get('suche'), str) or not q['suche']):
            raise ValueError('selbstabbild_quelle_fehlt: ' + a['id'] + '.' + str(s.get('id')))
        weiter = s.get('weiter', [])
        if not isinstance(weiter, list) or any(w not in namen for w in weiter):
            raise ValueError('selbstabbild_weiter_unbekannt: ' + a['id'] + '.' + str(s.get('id')))
        if s['art'] == 'decision' and len(weiter) != 2:
            raise ValueError('selbstabbild_entscheidung_zwei_wege: ' + a['id'] + '.' + s['id'])
        if s['art'] == 'end' and weiter:
            raise ValueError('selbstabbild_ende_ohne_folge: ' + a['id'] + '.' + s['id'])


def laden(pfad=KONFIG):
    """Die Abläufe, geprüft. Fehler: ValueError mit Satz."""
    try:
        doc = yaml.safe_load(Path(pfad).read_text(encoding='utf-8'))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError('selbstabbild_nicht_lesbar: ' + str(exc)[:200])
    liste = doc.get('ablaeufe') if isinstance(doc, dict) and doc.get('schema') == 1 else None
    if not isinstance(liste, list) or not liste:
        raise ValueError('selbstabbild_ohne_ablaeufe')
    ids = set()
    for a in liste:
        if not isinstance(a, dict) or a.get('id') in ids:
            raise ValueError('selbstabbild_ablauf_ungueltig')
        ids.add(a.get('id'))
        ablauf_pruefen(a)
    return liste


def _tiefen(schritte):
    """Spalte je Schritt: kürzester Weg vom Start (Rückwege ändern nichts)."""
    start = next(s['id'] for s in schritte if s['art'] == 'start')
    namen = {s['id']: s for s in schritte}
    tiefe, reihe = {start: 0}, [start]
    for sid in reihe:
        for w in namen[sid]['weiter']:
            if w not in tiefe:
                tiefe[w] = tiefe[sid] + 1
                reihe.append(w)
    for s in schritte:
        tiefe.setdefault(s['id'], max(tiefe.values()) + 1)
    return tiefe, reihe


def modell(ablauf):
    """Ein Ablauf als n8n-Dokument mit Prozessangaben. Alle Knoten sind deaktiviert; das Dokument besteht `validate`."""
    schritte = [dict(s, weiter=s.get('weiter', [])) for s in ablauf['schritte']]
    tiefe, reihe = _tiefen(schritte)
    nummer = {sid: i + 1 for i, sid in enumerate(reihe + [s['id'] for s in schritte if s['id'] not in reihe])}
    spalte, nodes, name_von = {}, [], {s['id']: s['name'] for s in schritte}
    for s in schritte:
        zeile = spalte.get(tiefe[s['id']], 0)
        spalte[tiefe[s['id']]] = zeile + 1
        meta = {'schema': 1, 'kind': s['art'], 'mode': s['arbeitsweise'], 'source': 'proposal', 'role_status': 'proposal', 'core_step': nummer[s['id']],
                'original_notes': ('Quelle: ' + s['quelle']['datei'] + ' · ' + s['quelle']['suche']) if s.get('quelle') else 'Entwurf von SEDRA, noch nicht bestätigt' + (' · Zweck: ' + ablauf['zweck'] if s['art'] == 'start' and ablauf.get('zweck') else '')}
        for de, en in FELDER.items():
            if s.get(de):
                meta[en] = str(s[de])
        typ = {'start': ('manualTrigger', 1), 'decision': ('if', 2.2)}.get(s['art'], ('noOp', 1))
        nodes.append({'id': 'sa-' + ablauf['id'] + '-' + s['id'], 'name': s['name'], 'type': 'n8n-nodes-base.' + typ[0], 'typeVersion': typ[1],
                      'position': [tiefe[s['id']] * 260, zeile * 170], 'parameters': {}, 'disabled': True,
                      'notes': PREFIX + json.dumps(meta, ensure_ascii=False, sort_keys=True), 'notesInFlow': False})
    verbindungen = {}
    for s in schritte:
        if not s['weiter']:
            continue
        zweige = [[{'node': name_von[w], 'type': 'main', 'index': 0}] for w in s['weiter']] if s['art'] == 'decision' \
            else [[{'node': name_von[w], 'type': 'main', 'index': 0} for w in s['weiter']]]
        verbindungen[s['name']] = {'main': zweige}
    return validate({'name': ablauf.get('anzeigename') or PREFIX_NAME + ablauf['name'], 'nodes': nodes, 'connections': verbindungen, 'settings': {'executionOrder': 'v1'}, 'active': False})


def pruefen(pfad=KONFIG, wurzel=REPO):
    """Abweichungstest: Schritte, deren Quelle fehlt oder deren Suchtext nicht mehr in der Datei steht. Leere Liste = Abbild stimmt mit dem Stand überein."""
    probleme, cache = [], {}
    for a in laden(pfad):
        for s in a['schritte']:
            datei = s['quelle']['datei']
            if '..' in Path(datei).parts or Path(datei).is_absolute():
                probleme.append({'ablauf': a['id'], 'schritt': s['id'], 'datei': datei, 'grund': 'pfad_unzulaessig'})
                continue
            if datei not in cache:
                try:
                    cache[datei] = (Path(wurzel) / datei).read_text(encoding='utf-8')
                except OSError:
                    cache[datei] = None
            if cache[datei] is None:
                probleme.append({'ablauf': a['id'], 'schritt': s['id'], 'datei': datei, 'grund': 'datei_fehlt'})
            elif s['quelle']['suche'] not in cache[datei]:
                probleme.append({'ablauf': a['id'], 'schritt': s['id'], 'datei': datei, 'grund': 'text_nicht_mehr_vorhanden'})
    return probleme


def _vorhanden(store, name):
    for record in store.listing():
        if record['workflow']['name'] == name:
            return record
    return None


def abweichung(store, pfad=KONFIG):
    """Je Ablauf: fehlt (noch nie angelegt), gleich (neueste Revision entspricht den Quellen) oder abweichend."""
    out = []
    for a in laden(pfad):
        doc = modell(a)
        record = _vorhanden(store, doc['name'])
        status = 'fehlt' if record is None else 'gleich' if record['digest'] == digest(doc) else 'abweichend'
        out.append({'ablauf': a['id'], 'name': doc['name'], 'status': status, 'id': record['id'] if record else None, 'revision': record['revision'] if record else None})
    return out


def anlegen(store, pfad=KONFIG, wurzel=REPO):
    """Legt fehlende Abläufe an und schreibt für abweichende eine neue Revision. Nur wenn alle Quellen stimmen (sonst ValueError)."""
    probleme = pruefen(pfad, wurzel)
    if probleme:
        raise ValueError('selbstabbild_quellen_abweichend: %d Schritt(e), erster: %s.%s (%s)' % (len(probleme), probleme[0]['ablauf'], probleme[0]['schritt'], probleme[0]['grund']))
    out = []
    for a in laden(pfad):
        doc = modell(a)
        record = _vorhanden(store, doc['name'])
        if record is None:
            saved = store.save(doc, None, None, 'Aus den Quellen von SEDRA erzeugt')
            status = 'angelegt'
        elif record['digest'] == digest(doc):
            saved, status = record, 'unveraendert'
        else:
            saved = store.save(doc, record['id'], record['revision'], 'Aus den Quellen von SEDRA neu erzeugt, Quelle hat sich geändert')
            status = 'aktualisiert'
        out.append({'ablauf': a['id'], 'name': doc['name'], 'status': status, 'id': saved['id'], 'revision': saved['revision']})
    return out


ENTWURF_PREFIX = 'Entwurf · '
ENTWURF_MAX_SCHRITTE = 16


def entwurf(payload):
    """Ein von SEDRA vorgeschlagener Prozess (Werkzeug prozess_beantragen) als Prozessmodell. Nie ausführbar, jede Angabe ist ein Vorschlag.
    payload: {name, zweck?, schritte: [{name, art, arbeitsweise, rolle?, eingabe?, ergebnis?, ... , weiter?}]}; ohne `weiter` folgt der nächste Schritt der Liste."""
    if not isinstance(payload, dict) or not isinstance(payload.get('name'), str) or not payload['name'].strip() or len(payload['name']) > 120:
        raise ValueError('prozess_name_fehlt')
    roh = payload.get('schritte')
    if not isinstance(roh, list) or not 2 <= len(roh) <= ENTWURF_MAX_SCHRITTE or not all(isinstance(s, dict) for s in roh):
        raise ValueError('prozess_schritte_ungueltig: 2 bis %d Schritte' % ENTWURF_MAX_SCHRITTE)
    schritte = []
    for i, s in enumerate(roh):
        t = {k: (str(v)[:400] if k in FELDER or k == 'name' else v) for k, v in s.items() if k in set(FELDER) | {'name', 'art', 'arbeitsweise', 'weiter'}}
        t['id'] = 's%d' % (i + 1)
        t.setdefault('art', 'start' if i == 0 else 'end' if i == len(roh) - 1 else 'task')
        t.setdefault('arbeitsweise', 'manual')
        schritte.append(t)
    namen = {s['name']: s['id'] for s in schritte if isinstance(s.get('name'), str)}
    for i, s in enumerate(schritte):
        if 'weiter' in s:
            if not isinstance(s['weiter'], list) or any(w not in namen for w in s['weiter']):
                raise ValueError('prozess_weiter_unbekannt: ' + str(s.get('name')))
            s['weiter'] = [namen[w] for w in s['weiter']]
        elif s['art'] != 'end' and i + 1 < len(schritte):
            s['weiter'] = [schritte[i + 1]['id']]
        else:
            s['weiter'] = []
    ablauf = {'id': 'entwurf', 'name': payload['name'].strip(), 'anzeigename': ENTWURF_PREFIX + payload['name'].strip(), 'schritte': schritte}
    ablauf_pruefen(ablauf, quelle_pflicht=False)
    if isinstance(payload.get('zweck'), str) and payload['zweck'].strip():
        ablauf['zweck'] = payload['zweck'].strip()[:400]
    return modell(ablauf)
