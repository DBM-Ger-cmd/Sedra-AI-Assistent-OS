"""Der SEDRA-Eigenablauf (Profil sedra-lokal-v1): ein n8n-Workflow läuft ganz lokal in SEDRA, ohne n8n.

Geschlossen wie das n8n-Profil in policy.py, nur mit mehr Knotentypen: Formular- oder manueller Start, PDF lesen, Felder setzen, Code (JavaScript),
Bedingung und lokale Tabellen lesen/schreiben. Ausdrücke und Code laufen in lokal_runner.js (Node, `--permission`, ohne Dateizugriff und Netz).
Nicht erreichbare KI-Zweige bleiben im Dokument und laufen nie. Alles andere wird abgelehnt, bevor etwas läuft.

Gestartet wird nur nach der Freigabe des Captains (execution.py); dieses Modul kennt keine Freigaben."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from copy import deepcopy
from pathlib import Path

from .lokal_daten import Eingaben, Tabellen
from .policy import assessment as _assessment_n8n
from .process import has_process
from .schema import validate

PROFILE = 'sedra-lokal-v1'
RUNNER = Path(__file__).with_name('lokal_runner.js')
MAX_KNOTEN = 32
MAX_ITEMS = 5000
MAX_AUSDRUCK = 20000
MAX_ANTWORT = 12_000_000
NB = 'n8n-nodes-base.'
VERSIONEN = {NB + 'manualTrigger': [1], NB + 'formTrigger': [2, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6], NB + 'extractFromFile': [1, 1.1, 1.2],
             NB + 'set': [3.3, 3.4, 3.5], NB + 'code': [2], NB + 'if': [2, 2.1, 2.2, 2.3, 2.4], NB + 'dataTable': [1, 1.1], NB + 'noOp': [1], NB + 'stickyNote': [1]}
LABEL = {'manualTrigger': 'Manueller Start', 'formTrigger': 'Formular', 'extractFromFile': 'PDF lesen', 'set': 'Felder setzen', 'code': 'Code',
         'if': 'Bedingung', 'dataTable': 'Tabelle', 'noOp': 'Nichts tun'}
LANGCHAIN = '@n8n/n8n-nodes-langchain.'
UNSICHER = {'__proto__', 'prototype', 'constructor'}
AUSLOESER = (NB + 'manualTrigger', NB + 'formTrigger')
OPTIONEN = ('credentials',)


class LokalFehler(RuntimeError):
    pass


# ----------------------------------------------------------------------------------------------------------------------------- Prüfung

def _kurz(typ):
    return str(typ).rsplit('.', 1)[-1]


def _ausdruck_ok(wert):
    if isinstance(wert, str):
        if len(wert) > MAX_AUSDRUCK:
            raise ValueError('ausdruck_zu_lang')
    elif type(wert) not in (int, float, bool) and wert is not None and not isinstance(wert, (list, dict)):
        raise ValueError('unsupported_value')


def _schluessel(wert, erlaubt, grund='unsupported_parameters'):
    if not isinstance(wert, dict) or set(wert) - set(erlaubt):
        raise ValueError(grund)


def _name_ok(name):
    return isinstance(name, str) and 1 <= len(name) <= 64 and all(re.fullmatch(r'[^\W\d]\w*', teil) for teil in name.split('.')) and not UNSICHER.intersection(name.split('.'))


def _pruefe_set(p):
    _schluessel(p, {'mode', 'assignments', 'includeOtherFields', 'options'})
    if p.get('mode', 'manual') != 'manual' or p.get('options', {}) != {} or type(p.get('includeOtherFields', False)) is not bool:
        raise ValueError('unsupported_set_mode')
    zeilen = (p.get('assignments') or {}).get('assignments')
    _schluessel(p.get('assignments'), {'assignments'})
    if not isinstance(zeilen, list) or not 1 <= len(zeilen) <= 64:
        raise ValueError('assignments_required')
    for z in zeilen:
        _schluessel(z, {'id', 'name', 'value', 'type'})
        if not _name_ok(z.get('name')):
            raise ValueError('unsafe_assignment_name')
        if z.get('type', 'string') not in ('string', 'number', 'boolean', 'array', 'object'):
            raise ValueError('unsupported_assignment_type')
        _ausdruck_ok(z.get('value'))


STRING_OPS = {'equals', 'notEquals', 'contains', 'notContains', 'startsWith', 'notStartsWith', 'endsWith', 'notEndsWith', 'empty', 'notEmpty'}
NUMBER_OPS = {'equals', 'notEquals', 'gt', 'gte', 'lt', 'lte', 'empty', 'notEmpty'}
BOOL_OPS = {'true', 'false', 'equals', 'notEquals', 'empty', 'notEmpty'}


def _pruefe_if(p):
    _schluessel(p, {'conditions', 'options'})
    if p.get('options', {}) != {}:
        raise ValueError('unsupported_if_options')
    c = p.get('conditions')
    _schluessel(c, {'options', 'conditions', 'combinator'})
    _schluessel(c.get('options', {}), {'caseSensitive', 'leftValue', 'typeValidation', 'version'})
    if c.get('combinator', 'and') not in ('and', 'or') or c.get('options', {}).get('typeValidation', 'strict') not in ('strict', 'loose'):
        raise ValueError('invalid_combinator')
    zeilen = c.get('conditions')
    if not isinstance(zeilen, list) or not 1 <= len(zeilen) <= 32:
        raise ValueError('conditions_required')
    ops = {'string': STRING_OPS, 'number': NUMBER_OPS, 'boolean': BOOL_OPS}
    for z in zeilen:
        _schluessel(z, {'id', 'leftValue', 'rightValue', 'operator'})
        _ausdruck_ok(z.get('leftValue')); _ausdruck_ok(z.get('rightValue'))
        _schluessel(z.get('operator'), {'type', 'operation', 'singleValue'})
        if z['operator'].get('operation') not in ops.get(z['operator'].get('type'), set()):
            raise ValueError('unsupported_operator')


def _pruefe_code(p):
    _schluessel(p, {'jsCode', 'language', 'mode'})
    if p.get('language', 'javaScript') != 'javaScript' or p.get('mode', 'runOnceForAllItems') != 'runOnceForAllItems':
        raise ValueError('unsupported_code_mode')
    if not isinstance(p.get('jsCode'), str) or not p['jsCode'].strip() or len(p['jsCode']) > MAX_AUSDRUCK:
        raise ValueError('code_required')


def _tabellenname(p):
    ref = p.get('dataTableId')
    if not isinstance(ref, dict):
        raise ValueError('table_required')
    name = ref.get('cachedResultName') or ref.get('value')
    if not isinstance(name, str) or not name.strip() or len(name) > 80:
        raise ValueError('table_required')
    return name.strip()


def _bedingungen_pruefen(p):
    f = p.get('filters')
    if f is None:
        return
    _schluessel(f, {'conditions', 'matchType'})
    zeilen = f.get('conditions', [])
    if not isinstance(zeilen, list) or len(zeilen) > 16:
        raise ValueError('unsupported_filters')
    for z in zeilen:
        _schluessel(z, {'keyName', 'condition', 'keyValue'})
        if not isinstance(z.get('keyName'), str) or z.get('condition', 'eq') not in ('eq', 'neq', 'gt', 'gte', 'lt', 'lte'):
            raise ValueError('unsupported_filters')
        _ausdruck_ok(z.get('keyValue'))
    if f.get('matchType', 'allConditions') != 'allConditions':
        raise ValueError('unsupported_filters')


def _pruefe_tabelle(p):
    _schluessel(p, {'operation', 'dataTableId', 'filters', 'columns', 'options', 'matchType', 'returnAll', 'limit'})
    _tabellenname(p)
    if p.get('options', {}) != {}:
        raise ValueError('unsupported_table_options')
    if p.get('operation') not in ('get', 'upsert'):
        raise ValueError('unsupported_table_operation')
    _bedingungen_pruefen(p)
    if p['operation'] == 'get' and not (p.get('filters') or {}).get('conditions'):
        raise ValueError('table_filter_required')
    if p['operation'] == 'upsert':
        spalten = (p.get('columns') or {}).get('value')
        if not isinstance(spalten, dict) or not 1 <= len(spalten) <= 64 or not all(_name_ok(k) for k in spalten):
            raise ValueError('table_columns_required')
        for v in spalten.values():
            _ausdruck_ok(v)


def _pruefe_extrahieren(p):
    _schluessel(p, {'operation', 'binaryPropertyName', 'options'})
    if p.get('operation') != 'pdf' or not isinstance(p.get('binaryPropertyName'), str) or not p['binaryPropertyName'].strip():
        raise ValueError('unsupported_extract_operation')
    _schluessel(p.get('options', {}), {'joinPages'})


def _pruefe_formular(p):
    _schluessel(p, {'formTitle', 'formDescription', 'formFields', 'options', 'responseMode', 'authentication', 'path', 'formPath'})
    felder = ((p.get('formFields') or {}).get('values')) or []
    if not isinstance(felder, list) or not 1 <= len(felder) <= 16:
        raise ValueError('form_fields_required')
    for f in felder:
        if not isinstance(f, dict) or not isinstance(f.get('fieldLabel'), str) or not f['fieldLabel'].strip() or f.get('fieldType', 'text') not in ('text', 'number', 'file', 'textarea'):
            raise ValueError('unsupported_form_field')


PRUEFER = {'set': _pruefe_set, 'if': _pruefe_if, 'code': _pruefe_code, 'dataTable': _pruefe_tabelle, 'extractFromFile': _pruefe_extrahieren, 'formTrigger': _pruefe_formular}


def _plan(value):
    """Ablaufplan oder ValueError mit einem Grund. Der Plan: Reihenfolge, Kanten und die übersprungenen (nicht erreichbaren) Knoten."""
    doc = validate(value)
    if has_process(doc):
        raise ValueError('process_model_requires_implementation')
    if doc.get('pinData') or doc.get('staticData'):
        raise ValueError('pinned_or_static_data_not_executable')
    knoten = {n['name']: n for n in doc['nodes']}
    start = [n['name'] for n in doc['nodes'] if n['type'] in AUSLOESER]
    if len(start) != 1:
        raise ValueError('one_form_or_manual_start_required')
    kanten = {name: [] for name in knoten}
    for quelle, ausgaenge in doc['connections'].items():
        if quelle not in knoten:
            raise ValueError('unsupported_connection')
        for art, zweige in ausgaenge.items():
            if art != 'main':
                continue
            if len(zweige) > (2 if knoten[quelle]['type'].endswith('.if') else 1):
                raise ValueError('unsupported_output_index')
            for ast, zweig in enumerate(zweige):
                for e in zweig:
                    if e['node'] not in knoten or e['type'] != 'main' or e['index'] != 0:
                        raise ValueError('unsupported_connection')
                    kanten[quelle].append((ast, e['node']))
    erreicht, offen = set(), [start[0]]
    while offen:
        name = offen.pop()
        if name not in erreicht:
            erreicht.add(name)
            offen.extend(ziel for _, ziel in kanten[name])
    uebersprungen = []
    for name, n in knoten.items():
        if name in erreicht:
            continue
        if n['type'].startswith(LANGCHAIN) or n['type'].endswith('.stickyNote'):
            uebersprungen.append(name)
        else:
            raise ValueError('unreachable_nodes:' + name)
    for name in erreicht:
        n = knoten[name]
        if n['typeVersion'] not in VERSIONEN.get(n['type'], []):
            raise ValueError('unsupported_node:' + name)
        if any(a != 'main' for a in doc['connections'].get(name, {})):
            raise ValueError('only_main_connections_supported')
        if n.get('credentials') or any(n.get(k) for k in ('disabled', 'retryOnFail', 'alwaysOutputData', 'continueOnFail', 'executeOnce')) or n.get('onError', 'stopWorkflow') != 'stopWorkflow':
            raise ValueError('unsupported_node_execution_options:' + name)
        pruefer = PRUEFER.get(_kurz(n['type']))
        if pruefer:
            pruefer(n['parameters'])
        elif n['parameters'] and not n['type'].endswith('.manualTrigger'):
            raise ValueError('unsupported_parameters:' + name)
    if len(erreicht) > MAX_KNOTEN:
        raise ValueError('too_many_nodes')
    eingang = {name: 0 for name in erreicht}
    for name in erreicht:
        for _, ziel in kanten[name]:
            eingang[ziel] += 1
    reihe, warte = [], [name for name in erreicht if not eingang[name]]
    while warte:
        name = warte.pop(0)
        reihe.append(name)
        for _, ziel in kanten[name]:
            eingang[ziel] -= 1
            if not eingang[ziel]:
                warte.append(ziel)
    if len(reihe) != len(erreicht) or any(start[0] == z for k in kanten.values() for _, z in k):
        raise ValueError('cycles_not_supported')
    schreibt = sorted({_tabellenname(knoten[n]['parameters']) for n in erreicht if _kurz(knoten[n]['type']) == 'dataTable' and knoten[n]['parameters'].get('operation') == 'upsert'})
    liest = sorted({_tabellenname(knoten[n]['parameters']) for n in erreicht if _kurz(knoten[n]['type']) == 'dataTable' and knoten[n]['parameters'].get('operation') == 'get'})
    return {'doc': doc, 'knoten': knoten, 'kanten': kanten, 'reihe': reihe, 'start': start[0], 'uebersprungen': uebersprungen, 'schreibt': schreibt, 'liest': liest}


def bewerten(value):
    """Wie policy.assessment, für das Eigenablauf-Profil. Zusätzlich: übersprungene Knoten, gelesene und geschriebene Tabellen, Dateifelder des Starts."""
    try:
        plan = _plan(value)
    except ValueError as exc:
        return {'executable': False, 'profile': PROFILE, 'reason': str(exc)}
    start = plan['knoten'][plan['start']]
    dateien = [f['fieldLabel'] for f in ((start['parameters'].get('formFields') or {}).get('values') or []) if f.get('fieldType') == 'file']
    return {'executable': True, 'profile': PROFILE, 'reason': None, 'uebersprungen': plan['uebersprungen'], 'schreibt': plan['schreibt'], 'liest': plan['liest'],
            'dateifelder': dateien, 'knoten_gesamt': len(plan['knoten']), 'knoten_lauffaehig': len(plan['reihe'])}


def bekannte_knoten(nodes):
    """Wie viele Knoten das Eigenablauf-Profil dem Typ und der Version nach kennt (für die Importvorschau)."""
    return sum(1 for n in nodes if n.get('typeVersion') in VERSIONEN.get(n.get('type'), []) and not str(n['type']).endswith('.stickyNote'))


def gesamt_bewertung(value, n8n_bereit=False):
    """Die beste Ausführungsart: n8n-Profil (nur wenn n8n eingerichtet ist), sonst der Eigenablauf, sonst der Grund der Ablehnung."""
    alt = _assessment_n8n(value)
    if alt['executable'] and n8n_bereit:
        return alt
    neu = bewerten(value)
    if neu['executable']:
        return neu
    if alt['executable']:
        return dict(alt, reason=None)
    return neu if not alt['reason'] or alt['reason'].startswith(('unsupported_node:', 'unsupported_parameters', 'unreachable', 'one_manual')) else alt


# ------------------------------------------------------------------------------------------------------------- Ausdrücke (Node-Sandkasten)

def _node_programm():
    pfad = os.environ.get('SEDRA_NODE') or shutil.which('node')
    if not pfad:
        raise LokalFehler('node_fehlt')
    return pfad


def _js(items, nodes, aufgaben):
    """Wertet Aufgaben [{kind: expr|code, source, index}] in der Sandbox aus. Rückgabe: Liste der Werte; bei einem Fehler LokalFehler mit dem Text."""
    if not aufgaben:
        return []
    auftrag = json.dumps({'items': items, 'nodes': nodes, 'tasks': aufgaben}, ensure_ascii=True, allow_nan=False)
    if len(auftrag) > MAX_ANTWORT:
        raise LokalFehler('daten_zu_gross')
    try:
        p = subprocess.run([_node_programm(), '--permission', str(RUNNER)], input=auftrag, capture_output=True, text=True, encoding='utf-8', timeout=60,
                           cwd=str(RUNNER.parent))
    except subprocess.TimeoutExpired as exc:
        raise LokalFehler('ausdruck_zeitlimit') from exc
    except OSError as exc:
        raise LokalFehler('node_nicht_startbar') from exc
    try:
        antwort = json.loads(p.stdout)
    except ValueError as exc:
        raise LokalFehler('ausdruck_antwort_ungueltig:' + (p.stderr.strip().splitlines() or [''])[-1][:200]) from exc
    if 'ergebnisse' not in antwort or len(antwort['ergebnisse']) != len(aufgaben):
        raise LokalFehler('ausdruck_antwort_ungueltig')
    werte = []
    for r in antwort['ergebnisse']:
        if not r.get('ok'):
            raise LokalFehler('ausdruck_fehler: ' + str(r.get('fehler')))
        werte.append(r.get('wert'))
    return werte


def _vorbereiten(wert):
    """n8n-Wert → ('lit', Wert) oder ('js', Quelltext). „=…“ ist ein Ausdruck, ein Text mit {{ … }} wird zusammengesetzt, sonst bleibt der Wert wie er ist."""
    if not isinstance(wert, str) or not wert.startswith('='):
        return 'lit', wert
    text = wert[1:]
    if '{{' not in text:
        return 'lit', text
    if text.startswith('{{') and text.endswith('}}') and text.count('{{') == 1:
        return 'js', text[2:-2]
    teile, rest = [], text
    while True:
        m = re.search(r'\{\{(.+?)\}\}', rest, re.S)
        if not m:
            if rest:
                teile.append(json.dumps(rest))
            break
        if rest[:m.start()]:
            teile.append(json.dumps(rest[:m.start()]))
        teile.append('String((' + m.group(1) + '\n))')
        rest = rest[m.end():]
    return 'js', ' + '.join(teile) or '""'


class Lauf:
    """Der Zustand eines Laufs: Eingaben, Tabellen und die Ausgaben aller Knoten (für $('Name'))."""

    def __init__(self, tabellen, eingaben, eingabe):
        self.tabellen, self.eingaben, self.eingabe = tabellen, eingaben, eingabe
        self.ausgaben = {}
        self.geschrieben = []

    def nodes_json(self):
        return {name: [[{'json': i['json']} for i in zweig] for zweig in zweige] for name, zweige in self.ausgaben.items()}

    def auswerten(self, items, wuensche):
        """wuensche: Liste (index, wert). Ergebnis: Liste der ausgewerteten Werte (Literale unverändert), alle JS-Aufgaben in einem Aufruf."""
        plan, aufgaben = [], []
        for index, wert in wuensche:
            art, inhalt = _vorbereiten(wert)
            if art == 'js':
                plan.append(len(aufgaben)); aufgaben.append({'kind': 'expr', 'source': inhalt, 'index': index})
            else:
                plan.append(('lit', inhalt))
        werte = _js([{'json': i['json']} for i in items], self.nodes_json(), aufgaben)
        return [werte[p] if isinstance(p, int) else p[1] for p in plan]

    def code(self, items, quelle):
        return _js([{'json': i['json']} for i in items], self.nodes_json(), [{'kind': 'code', 'source': quelle, 'index': 0}])[0]


# ------------------------------------------------------------------------------------------------------------------------ Knoten

def _item(json_, binary=None):
    return {'json': json_, 'binary': binary or {}}


def _kopie(item):
    return {'json': deepcopy(item['json']), 'binary': dict(item.get('binary') or {})}


def _setzen(ziel, name, wert):
    teile = name.split('.')
    for teil in teile[:-1]:
        if not isinstance(ziel.get(teil), dict):
            ziel[teil] = {}
        ziel = ziel[teil]
    ziel[teile[-1]] = wert


def _typ(wert, art, name):
    if wert is None:
        return None
    if art == 'number':
        if isinstance(wert, bool):
            raise LokalFehler("Feld '%s' erwartet eine Zahl" % name)
        if isinstance(wert, (int, float)):
            return wert
        try:
            z = float(str(wert).strip().replace(',', '.'))
            return int(z) if z.is_integer() else z
        except ValueError as exc:
            raise LokalFehler("Feld '%s' erwartet eine Zahl, bekam '%s'" % (name, str(wert)[:40])) from exc
    if art == 'boolean':
        if isinstance(wert, bool):
            return wert
        if str(wert).lower() in ('true', 'false'):
            return str(wert).lower() == 'true'
        raise LokalFehler("Feld '%s' erwartet wahr oder falsch" % name)
    if art == 'string' and isinstance(wert, (int, float, bool)):
        return json.dumps(wert) if isinstance(wert, bool) else str(wert)
    return wert


def knoten_set(lauf, n, items):
    p = n['parameters']
    zeilen = p['assignments']['assignments']
    wuensche = [(i, z.get('value')) for i in range(len(items)) for z in zeilen]
    werte = lauf.auswerten(items, wuensche)
    aus = []
    for i, item in enumerate(items):
        neu = _kopie(item) if p.get('includeOtherFields') else _item({})
        for k, z in enumerate(zeilen):
            _setzen(neu['json'], z['name'], _typ(werte[i * len(zeilen) + k], z.get('type', 'string'), z['name']))
        aus.append(neu)
    return [aus]


def _vergleiche(art, op, links, rechts, gross):
    if art == 'string':
        if op in ('empty', 'notEmpty'):
            leer = links is None or links == ''
            return leer if op == 'empty' else not leer
        a, b = str(links), str(rechts)
        if not gross:
            a, b = a.lower(), b.lower()
        return {'equals': a == b, 'notEquals': a != b, 'contains': b in a, 'notContains': b not in a, 'startsWith': a.startswith(b), 'notStartsWith': not a.startswith(b),
                'endsWith': a.endswith(b), 'notEndsWith': not a.endswith(b)}[op]
    if art == 'number':
        if op in ('empty', 'notEmpty'):
            return (links is None) if op == 'empty' else links is not None
        a, b = float(links), float(rechts)
        return {'equals': a == b, 'notEquals': a != b, 'gt': a > b, 'gte': a >= b, 'lt': a < b, 'lte': a <= b}[op]
    if op in ('empty', 'notEmpty'):
        return (links is None) if op == 'empty' else links is not None
    return {'true': links is True, 'false': links is False, 'equals': links == rechts, 'notEquals': links != rechts}[op]


def _bedingung_typ(wert, art, streng, rolle):
    if wert is None:
        return wert
    ok = (art == 'string' and isinstance(wert, str)) or (art == 'number' and isinstance(wert, (int, float)) and not isinstance(wert, bool)) or (art == 'boolean' and isinstance(wert, bool))
    if ok:
        return wert
    if streng:
        raise LokalFehler('Bedingung: der %s Wert passt nicht zum Typ %s' % (rolle, art))
    return _typ(wert, art, rolle) if art != 'string' else str(wert)


def knoten_if(lauf, n, items):
    c = n['parameters']['conditions']
    opts = c.get('options', {})
    gross, streng = opts.get('caseSensitive', True), opts.get('typeValidation', 'strict') == 'strict'
    zeilen = c['conditions']
    wuensche = [(i, z.get(s)) for i in range(len(items)) for z in zeilen for s in ('leftValue', 'rightValue')]
    werte = lauf.auswerten(items, wuensche)
    ja, nein = [], []
    for i, item in enumerate(items):
        ergebnisse = []
        for k, z in enumerate(zeilen):
            art, op = z['operator']['type'], z['operator']['operation']
            links, rechts = werte[(i * len(zeilen) + k) * 2], werte[(i * len(zeilen) + k) * 2 + 1]
            links = _bedingung_typ(links, art, streng, 'linke')
            rechts = _bedingung_typ(rechts, art, streng, 'rechte') if op not in ('empty', 'notEmpty', 'true', 'false') else rechts
            ergebnisse.append(_vergleiche(art, op, links, rechts, gross))
        (ja if (all(ergebnisse) if c.get('combinator', 'and') == 'and' else any(ergebnisse)) else nein).append(_kopie(item))
    return [ja, nein]


def knoten_code(lauf, n, items):
    antwort = lauf.code(items, n['parameters']['jsCode'])
    if isinstance(antwort, dict):
        antwort = [antwort]
    if not isinstance(antwort, list) or len(antwort) > MAX_ITEMS:
        raise LokalFehler('Der Code muss eine Liste von Einträgen zurückgeben (return [{ json: {…} }])')
    aus = []
    for e in antwort:
        if not isinstance(e, dict):
            raise LokalFehler('Der Code muss Objekte zurückgeben (return [{ json: {…} }])')
        aus.append(_item(e['json'] if isinstance(e.get('json'), dict) else e))
    return [aus]


def knoten_pdf(lauf, n, items):
    prop = n['parameters']['binaryPropertyName']
    aus = []
    for item in items:
        datei = (item.get('binary') or {}).get(prop)
        if not datei:
            raise LokalFehler("Im Eintrag fehlt die Datei '%s'" % prop)
        aus.append(_item(pdf_lesen(datei['daten'])))
    return [aus]


def pdf_lesen(daten):
    if not daten.startswith(b'%PDF'):
        raise LokalFehler('Die Datei ist kein PDF')
    try:
        from pypdf import PdfReader
        import io
        leser = PdfReader(io.BytesIO(daten))
        if len(leser.pages) > 200:
            raise LokalFehler('Das PDF hat mehr als 200 Seiten')
        seiten = [(s.extract_text() or '') for s in leser.pages]
    except ImportError as exc:
        raise LokalFehler('pypdf_fehlt') from exc
    except LokalFehler:
        raise
    except Exception as exc:
        raise LokalFehler('PDF nicht lesbar: ' + type(exc).__name__) from exc
    text = '\n\n'.join(seiten)
    if len(text) > 2_000_000:
        raise LokalFehler('PDF-Text zu lang')
    return {'numpages': len(seiten), 'numrender': len(seiten), 'info': {}, 'text': text}


def knoten_tabelle(lauf, n, items):
    p = n['parameters']
    name = _tabellenname(p)
    filter_ = (p.get('filters') or {}).get('conditions', [])
    spalten = (p.get('columns') or {}).get('value', {}) if p['operation'] == 'upsert' else {}
    wuensche = [(i, z.get('keyValue')) for i in range(len(items)) for z in filter_] + [(i, v) for i in range(len(items)) for v in spalten.values()]
    werte = lauf.auswerten(items, wuensche)
    nf, ns = len(filter_), len(spalten)
    aus = []
    for i in range(len(items)):
        basis = i * nf
        bedingungen = [{'spalte': z['keyName'], 'art': z.get('condition', 'eq'), 'wert': werte[basis + k]} for k, z in enumerate(filter_)]
        try:
            if p['operation'] == 'get':
                aus.extend(_item(z) for z in lauf.tabellen.suchen(name, bedingungen, limit=1000))
            else:
                start = len(items) * nf + i * ns
                zeile = {k: werte[start + j] for j, k in enumerate(spalten)}
                aus.extend(_item(z) for z in lauf.tabellen.upsert(name, bedingungen, zeile))
                if name not in lauf.geschrieben:
                    lauf.geschrieben.append(name)
        except ValueError as exc:
            raise LokalFehler('Tabelle %s: %s' % (name, exc)) from exc
    return [aus]


def knoten_start(lauf, n, items):
    eingabe = lauf.eingabe if isinstance(lauf.eingabe, dict) else {}
    if n['type'].endswith('.manualTrigger'):
        return [[_item(deepcopy(eingabe))]]
    felder = n['parameters']['formFields']['values']
    daten, binary = {}, {}
    for f in felder:
        label = f['fieldLabel']
        wert = eingabe.get(label)
        if f.get('fieldType') == 'file':
            if not isinstance(wert, dict) or not wert.get('datei'):
                raise LokalFehler("Für das Formularfeld '%s' fehlt die hochgeladene Datei" % label)
            try:
                inhalt = lauf.eingaben.lesen(wert['datei'])
            except ValueError as exc:
                raise LokalFehler('Datei zu %s: %s' % (label, exc)) from exc
            name = str(wert.get('name') or label)[:200]
            binary[label] = {'daten': inhalt, 'dateiname': name, 'mime': 'application/pdf' if inhalt.startswith(b'%PDF') else 'application/octet-stream'}
            daten[label] = {'filename': name, 'mimetype': binary[label]['mime'], 'size': len(inhalt)}
        else:
            if f.get('requiredField') and wert in (None, ''):
                raise LokalFehler("Das Formularfeld '%s' ist ein Pflichtfeld" % label)
            daten[label] = wert
    daten['submittedAt'] = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    daten['formMode'] = 'sedra'
    return [[_item(daten, binary)]]


HANDLER = {'manualTrigger': knoten_start, 'formTrigger': knoten_start, 'set': knoten_set, 'if': knoten_if, 'code': knoten_code, 'extractFromFile': knoten_pdf,
           'dataTable': knoten_tabelle, 'noOp': lambda lauf, n, items: [[_kopie(i) for i in items]], 'stickyNote': lambda lauf, n, items: [[]]}


# ------------------------------------------------------------------------------------------------------------------------- Lauf

def _kuerzen(wert, tiefe=0):
    if isinstance(wert, str):
        return wert if len(wert) <= 240 else wert[:240] + ' … (%d Zeichen)' % len(wert)
    if isinstance(wert, list):
        return [_kuerzen(w, tiefe + 1) for w in wert[:8]] + (['… (%d weitere)' % (len(wert) - 8)] if len(wert) > 8 else [])
    if isinstance(wert, dict):
        return {k: _kuerzen(v, tiefe + 1) for k, v in wert.items()}
    return wert


def ausfuehren(workflow, eingabe, project):
    """Führt einen geprüften Workflow aus. Wirft nie: Fehler stehen im Ergebnis (status failed, error, fehler_knoten)."""
    start = time.time()
    ergebnis = {'status': 'failed', 'profile': PROFILE, 'knoten': [], 'output': None, 'tabellen_geschrieben': [], 'hinweise': []}
    try:
        plan = _plan(workflow)
    except ValueError as exc:
        ergebnis['error'] = str(exc)
        return ergebnis
    lauf = Lauf(Tabellen(project), Eingaben(project), eingabe)
    eingang = {name: [] for name in plan['reihe']}
    ergebnis['uebersprungen'] = plan['uebersprungen']
    aktuell = None
    try:
        for name in plan['reihe']:
            aktuell = name
            n = plan['knoten'][name]
            art = _kurz(n['type'])
            ist_start = name == plan['start']
            if not ist_start and not eingang[name]:
                lauf.ausgaben[name] = [[], []] if art == 'if' else [[]]
                ergebnis['knoten'].append({'name': name, 'art': LABEL.get(art, art), 'status': 'uebersprungen', 'eingang': 0, 'ausgang': []})
                continue
            zweige = HANDLER[art](lauf, n, eingang[name])
            if any(len(z) > MAX_ITEMS for z in zweige):
                raise LokalFehler('Zu viele Einträge')
            lauf.ausgaben[name] = zweige
            for ast, ziel in plan['kanten'][name]:
                eingang[ziel].extend(_kopie(i) for i in (zweige[ast] if ast < len(zweige) else []))
            erstes = next((z[0] for z in zweige if z), None)
            ergebnis['knoten'].append({'name': name, 'art': LABEL.get(art, art), 'status': 'ok', 'eingang': len(eingang[name]) if not ist_start else 0, 'ausgang': [len(z) for z in zweige],
                                       'beispiel': _kuerzen(erstes['json']) if erstes else None})
        ende = [nm for nm in plan['reihe'] if not plan['kanten'][nm] and any(lauf.ausgaben.get(nm, []))]
        ergebnis['output'] = {nm: [i['json'] for z in lauf.ausgaben[nm] for i in z] for nm in ende}
        leer = [k['name'] for k in ergebnis['knoten'] if k['status'] == 'uebersprungen']
        if leer:
            ergebnis['hinweise'].append('Ohne Daten übersprungen: ' + ', '.join(leer) + '. Die Vorgänger lieferten nichts für diese Knoten.')
        if plan['uebersprungen']:
            ergebnis['hinweise'].append('Nicht im Ablauf angeschlossen, läuft nicht: ' + ', '.join(plan['uebersprungen']) + '.')
        ergebnis['status'] = 'completed'
    except LokalFehler as exc:
        ergebnis['error'] = 'knoten_fehler'
        ergebnis['fehler_knoten'] = aktuell
        ergebnis['fehler_text'] = str(exc)
    except Exception as exc:                                    # nichts darf den Lauf unkontrolliert beenden
        ergebnis['error'] = 'lauf_abgebrochen'
        ergebnis['fehler_knoten'] = aktuell
        ergebnis['fehler_text'] = type(exc).__name__
    ergebnis['tabellen_geschrieben'] = list(lauf.geschrieben)
    ergebnis['dauer_ms'] = int((time.time() - start) * 1000)
    return ergebnis
