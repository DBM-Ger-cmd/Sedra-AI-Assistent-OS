"""Die Vorschau eines n8n-Imports: was in der Datei steht, was SEDRA daraus macht und was der Captain wissen sollte, bevor er sie übernimmt.

Echte n8n-Exporte sind oft lockerer als das strenge Austauschformat von SEDRA: Teilauswahlen aus der Zwischenablage haben keinen Namen, ältere
Exporte keine Knoten-Kennungen, manche Knoten keine Position. Die Vorschau füllt solche Lücken auf (Normalisieren) und sagt genau, was sie getan hat;
alles andere bleibt unverändert erhalten (unbekannte Felder und Knoten, Zugangs-Verweise ohne Werte, Gedächtnisdaten). Nichts wird gespeichert,
gestartet oder freigegeben. Die Antwort enthält das (normalisierte) Dokument, das der Editor übernimmt, sobald der Captain „Als Entwurf öffnen“ wählt."""
from __future__ import annotations

import re
import uuid
from copy import deepcopy

from .policy import assessment
from .schema import MAX_BYTES, MAX_NODES, VERSIONS, report, strict_json

SAETZE = {
    'workflow_size_limit': 'Die Datei ist größer als 1 MB oder kein Text.',
    'invalid_workflow_json': 'Das ist kein gültiges JSON. Bitte die n8n-Datei unverändert wählen (Export aus n8n: „Download“ im Workflow-Menü).',
    'duplicate_json_key': 'Die Datei enthält einen doppelten Schlüssel; so kann sie nicht eindeutig gelesen werden.',
    'non_finite_json': 'Die Datei enthält Zahlen, die kein JSON erlaubt (NaN oder unendlich).',
    'workflow_nodes_or_connections_invalid': 'Das sieht nicht nach einem n8n-Workflow aus: es fehlen „nodes“ (1 bis %d Knoten) oder „connections“.' % MAX_NODES,
    'invalid_node': 'Ein Eintrag unter „nodes“ ist kein Knoten.',
    'invalid_or_duplicate_node_id': 'Zwei Knoten haben dieselbe Kennung oder eine Kennung ist ungültig.',
    'invalid_or_duplicate_node_name': 'Zwei Knoten heißen gleich oder ein Name ist leer. n8n verlangt eindeutige Namen.',
    'reserved_node_identity': 'Ein Knoten trägt einen reservierten Namen.',
    'invalid_node_type_or_parameters': 'Ein Knoten hat keinen Typ oder keine „parameters“.',
    'invalid_node_version': 'Ein Knoten hat keine gültige Versionsnummer („typeVersion“).',
    'invalid_node_position': 'Ein Knoten hat eine unbrauchbare Position.',
    'invalid_connection_source': 'Eine Verbindung geht von einem Knoten aus, den es nicht gibt.',
    'invalid_connection_output': 'Eine Verbindung hat einen ungültigen Ausgang.',
    'invalid_connection_branch': 'Eine Verbindung hat einen ungültigen Zweig.',
    'invalid_connection_target': 'Eine Verbindung führt zu einem Knoten, den es nicht gibt.',
    'invalid_process_metadata': 'Die Prozess-Notizen von SEDRA in dieser Datei sind beschädigt.',
}

BEKANNT = {'manualTrigger': 'Manueller Start', 'scheduleTrigger': 'Zeitplan', 'webhook': 'Webhook', 'formTrigger': 'Formular', 'cron': 'Zeitplan (Cron)',
           'set': 'Felder setzen', 'if': 'Bedingung', 'switch': 'Mehrere Wege', 'merge': 'Zusammenführen', 'noOp': 'Nichts tun', 'wait': 'Warten',
           'stickyNote': 'Notiz', 'code': 'Eigener Code', 'function': 'Funktion', 'functionItem': 'Funktion je Eintrag', 'httpRequest': 'HTTP-Anfrage',
           'respondToWebhook': 'Antwort auf Webhook', 'splitInBatches': 'In Stapeln', 'filter': 'Filter', 'aggregate': 'Zusammenfassen', 'sort': 'Sortieren',
           'executeWorkflow': 'Workflow ausführen', 'emailSend': 'E-Mail senden', 'googleSheets': 'Google Sheets', 'slack': 'Slack', 'telegram': 'Telegram'}


def _label(typ):
    ende = str(typ).rsplit('.', 1)[-1]
    if ende in BEKANNT:
        return BEKANNT[ende]
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', ende)[:40].strip().capitalize() or str(typ)


def _ist_ausloeser(typ):
    ende = str(typ).rsplit('.', 1)[-1].lower()
    return ende.endswith('trigger') or ende in ('webhook', 'cron', 'start')


def normalisieren(doc, dateiname=None):
    """Lücken eines lockeren n8n-Exports schließen (Kopie): fehlender Name, fehlende Knoten-Kennungen, fehlende Positionen, fehlende „typeVersion“
    und fehlende „parameters“. Alles andere bleibt, wie es ist. Gibt (neues Dokument, Liste der Änderungen in Klartext) zurück."""
    aenderungen = []
    if not isinstance(doc, dict):
        return doc, aenderungen
    d = deepcopy(doc)
    if not isinstance(d.get('name'), str) or not d['name'].strip():
        basis = re.sub(r'\.json$', '', str(dateiname or ''), flags=re.I).strip()
        d['name'] = (basis or 'Importierter n8n-Workflow')[:200]
        aenderungen.append('Der Workflow hatte keinen Namen; er heißt jetzt „%s“.' % d['name'])
    if isinstance(d.get('nodes'), list) and d.get('connections') is None:
        d['connections'] = {}
        aenderungen.append('Es gab keine Verbindungen; der Workflow hat nur einzelne Knoten.')
    nodes = d.get('nodes')
    if isinstance(nodes, list):
        ohne_id = ohne_pos = ohne_ver = ohne_par = 0
        benutzt = {n.get('id') for n in nodes if isinstance(n, dict) and isinstance(n.get('id'), str)}
        for i, n in enumerate(nodes):
            if not isinstance(n, dict):
                continue
            if not isinstance(n.get('id'), str) or not n['id']:
                neu = str(uuid.uuid5(uuid.NAMESPACE_URL, 'sedra-import/%d/%s' % (i, n.get('name'))))
                while neu in benutzt:
                    neu = str(uuid.uuid4())
                n['id'] = neu; benutzt.add(neu); ohne_id += 1
            if not isinstance(n.get('position'), list):
                n['position'] = [0, 0]; ohne_pos += 1
            if type(n.get('typeVersion')) not in (int, float):
                n['typeVersion'] = 1; ohne_ver += 1
            if not isinstance(n.get('parameters'), dict):
                n['parameters'] = {}; ohne_par += 1
        for z, text in ((ohne_id, '%d Knoten bekamen eine Kennung (der Export hatte keine).'), (ohne_pos, '%d Knoten hatten keine Position; sie werden beim Öffnen angeordnet.'),
                        (ohne_ver, '%d Knoten bekamen die Version 1 (der Export nannte keine).'), (ohne_par, '%d Knoten bekamen leere Parameter.')):
            if z:
                aenderungen.append(text % z)
    return d, aenderungen


def _alle_null_oder_gleich(nodes):
    pos = [tuple(n.get('position') or (0, 0)) for n in nodes if not str(n.get('type', '')).endswith('stickyNote')]
    return len(pos) > 1 and len(set(pos)) < max(2, len(pos) // 2)


def _verbindungen(doc):
    out = []
    ifs = {n['name'] for n in doc['nodes'] if str(n['type']).endswith('.if')}
    for von, arten in (doc.get('connections') or {}).items():
        for art, zweige in (arten or {}).items():
            for ast, zweig in enumerate(zweige or []):
                for e in zweig or []:
                    out.append({'von': von, 'nach': e.get('node'), 'art': art, 'zweig': ('Ja' if ast == 0 else 'Nein') if von in ifs else (str(ast + 1) if len(zweige) > 1 else '')})
    return out


def vorschau(text, dateiname=None):
    """Die Vorschau eines Imports. Rückgabe: {'ok': bool, 'fehler': {code, satz} | None, 'name', 'knoten': [...], 'verbindungen': [...], 'funde': [{stufe, text}],
    'urteil': {stufe, satz}, 'aenderungen': [...], 'layout_noetig': bool, 'zaehler': {...}, 'workflow': dokument}. Wirft nie; Fehler stehen in 'fehler'."""
    leer = {'ok': False, 'fehler': None, 'name': dateiname or '', 'knoten': [], 'verbindungen': [], 'funde': [], 'urteil': None, 'aenderungen': [], 'layout_noetig': False,
            'zaehler': {}, 'workflow': None}
    try:
        roh = strict_json(text)
    except ValueError as exc:
        return dict(leer, fehler={'code': str(exc), 'satz': SAETZE.get(str(exc), 'Die Datei ließ sich nicht lesen.')})
    doc, aenderungen = normalisieren(roh, dateiname)
    try:
        rep = report(doc)
    except ValueError as exc:
        return dict(leer, name=(doc.get('name') if isinstance(doc, dict) else '') or '', aenderungen=aenderungen, fehler={'code': str(exc), 'satz': SAETZE.get(str(exc), 'Die Datei ließ sich nicht prüfen (' + str(exc) + ').')})
    nodes = doc['nodes']
    funde, zeilen = [], []
    zugang = []
    for n in nodes:
        notiz = str(n['type']).endswith('stickyNote')
        unterstuetzt = n['typeVersion'] in VERSIONS.get(n['type'], [])
        hat_zugang = bool(n.get('credentials'))
        if hat_zugang:
            zugang.append(n['name'])
        hinweise = []
        if n.get('disabled'):
            hinweise.append('in n8n ausgeschaltet')
        if hat_zugang:
            hinweise.append('verweist auf Zugangsdaten (ohne Werte)')
        if _ist_ausloeser(n['type']) and not str(n['type']).endswith('manualTrigger'):
            hinweise.append('startet in n8n von außen; hier nur ein Bild, nichts läuft')
        zeilen.append({'id': n['id'], 'name': n['name'], 'typ': n['type'], 'art': _label(n['type']), 'status': 'notiz' if notiz else ('unterstuetzt' if unterstuetzt else 'erhalten'),
                       'ausloeser': _ist_ausloeser(n['type']), 'deaktiviert': bool(n.get('disabled')), 'zugang': hat_zugang, 'hinweise': hinweise})
    verb = _verbindungen(doc)
    verbunden = {v['von'] for v in verb} | {v['nach'] for v in verb}
    lose = [n['name'] for n in nodes if n['name'] not in verbunden and not str(n['type']).endswith('stickyNote')]
    echte = [z for z in zeilen if z['status'] != 'notiz']
    erhalten = [z for z in zeilen if z['status'] == 'erhalten']
    if not any(z['ausloeser'] for z in echte):
        funde.append({'stufe': 'info', 'text': 'Es gibt keinen Auslöser (Start). In n8n wird so ein Workflow nur von einem anderen aufgerufen.'})
    if erhalten:
        funde.append({'stufe': 'warn', 'text': '%d von %d Knoten kennt SEDRA noch nicht (%s). Sie bleiben vollständig erhalten und erscheinen im Bild, laufen hier aber nicht.' % (len(erhalten), len(echte), ', '.join(sorted({z['art'] for z in erhalten})[:5]))})
    if zugang:
        funde.append({'stufe': 'warn', 'text': 'Zugangsdaten: %d Knoten verweisen darauf (%s). Es stehen nur die Verweise in der Datei, keine Passwörter. Vor dem Weitergeben prüfen; der bereinigte Export entfernt sie.' % (len(zugang), ', '.join(zugang[:4]))})
    if doc.get('pinData'):
        funde.append({'stufe': 'info', 'text': 'Die Datei enthält angeheftete Testdaten (pinData). Sie bleiben erhalten; der bereinigte Export lässt sie weg.'})
    if any(z['deaktiviert'] for z in echte):
        funde.append({'stufe': 'info', 'text': '%d Knoten sind in n8n ausgeschaltet; das bleibt so.' % sum(1 for z in echte if z['deaktiviert'])})
    if lose:
        funde.append({'stufe': 'warn', 'text': 'Nicht verbunden: %s. Sie hängen an nichts und würden nie erreicht.' % ', '.join(lose[:5])})
    if doc.get('active') is True:
        funde.append({'stufe': 'info', 'text': 'In n8n war der Workflow aktiv. Hier wird er nie von selbst gestartet; Läufe brauchen die Freigabe des Captains.'})
    if rep['process']['model_only']:
        funde.append({'stufe': 'info', 'text': 'Das ist ein Prozessmodell von SEDRA (Beschreibung ohne Ausführung).'})
    ass = assessment(doc)
    if erhalten or zugang or not ass['executable']:
        urteil = {'stufe': 'teilweise', 'satz': 'Wird übernommen und bleibt vollständig erhalten. Ausführen lässt sich davon in SEDRA nur, was die Engine kennt; hier sind es %d von %d Knoten.' % (len(echte) - len(erhalten), len(echte))}
    else:
        urteil = {'stufe': 'ok', 'satz': 'Alle Knoten sind bekannt. Ausgeführt wird nur nach der Freigabe des Captains.'}
    return {'ok': True, 'fehler': None, 'name': doc['name'], 'knoten': zeilen, 'verbindungen': verb, 'funde': funde, 'urteil': urteil, 'aenderungen': aenderungen,
            'layout_noetig': _alle_null_oder_gleich(nodes), 'ausfuehrbar': ass['executable'],
            'zaehler': {'knoten': len(echte), 'notizen': len(zeilen) - len(echte), 'verbindungen': len(verb), 'unbekannt': len(erhalten), 'zugang': len(zugang),
                        'ausloeser': sum(1 for z in echte if z['ausloeser'])},
            'workflow': doc}
