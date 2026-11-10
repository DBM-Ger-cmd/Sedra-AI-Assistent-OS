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
    'invalid_workflow_json': 'Das ist kein gültiges JSON. Bitte die n8n-Datei unverändert wählen (Export aus n8n: „Download" im Workflow-Menü).',
    'duplicate_json_key': 'Die Datei enthält einen doppelten Schlüssel; so kann sie nicht eindeutig gelesen werden.',
    'non_finite_json': 'Die Datei enthält Zahlen, die kein JSON erlaubt (NaN oder unendlich).',
    'workflow_nodes_or_connections_invalid': 'Das sieht nicht nach einem n8n-Workflow aus: es fehlen „nodes" (1 bis %d Knoten) oder „connections".' % MAX_NODES,
    'invalid_node': 'Ein Eintrag unter „nodes" ist kein Knoten.',
    'invalid_or_duplicate_node_id': 'Zwei Knoten haben dieselbe Kennung oder eine Kennung ist ungültig.',
    'invalid_or_duplicate_node_name': 'Zwei Knoten heißen gleich oder ein Name ist leer. n8n verlangt eindeutige Namen.',
    'reserved_node_identity': 'Ein Knoten trägt einen reservierten Namen.',
    'invalid_node_type_or_parameters': 'Ein Knoten hat keinen Typ oder keine „parameters".',
    'invalid_node_version': 'Ein Knoten hat keine gültige Versionsnummer („typeVersion").',
    'invalid_node_position': 'Ein Knoten hat eine unbrauchbare Position.',
    'invalid_connection_source': 'Eine Verbindung geht von einem Knoten aus, den es nicht gibt.',
    'invalid_connection_output': 'Eine Verbindung hat einen ungültigen Ausgang.',
    'invalid_connection_branch': 'Eine Verbindung hat einen ungültigen Zweig.',
    'invalid_connection_target': 'Eine Verbindung führt zu einem Knoten, den es nicht gibt.',
    'invalid_process_metadata': 'Die Prozess-Notizen von SEDRA in dieser Datei sind beschädigt.',
}

# Typ-Endung → Kategorie (Schlüssel ist der letzte Teil nach dem letzten Punkt)
_KATEGORIEN = {
    # Auslöser
    'manualTrigger': 'ausloeser', 'scheduleTrigger': 'ausloeser', 'webhook': 'ausloeser',
    'formTrigger': 'ausloeser', 'cron': 'ausloeser', 'appTrigger': 'ausloeser',
    'start': 'ausloeser',
    # KI/Modell
    'lmChatOpenAi': 'ki', 'lmChatAnthropic': 'ki', 'lmChatGoogleGemini': 'ki',
    'lmChatMistralCloud': 'ki', 'lmChatGroq': 'ki', 'lmChatAzureOpenAi': 'ki',
    'lmChatOllama': 'ki', 'agent': 'ki', 'chainLlm': 'ki',
    'informationExtractor': 'ki', 'textClassifier': 'ki',
    'memoryBufferMemory': 'ki', 'memoryVectorMemory': 'ki',
    'tool': 'ki', 'vectorStore': 'ki', 'embeddings': 'ki',
    # Daten
    'postgres': 'daten', 'mySql': 'daten', 'gmail': 'daten',
    'notion': 'daten', 'airtable': 'daten', 'googleSheets': 'daten',
    'readWriteFile': 'daten', 'excel': 'daten', 'csv': 'daten',
    'html': 'daten', 'xml': 'daten',
    # Code
    'code': 'code', 'function': 'code', 'functionItem': 'code',
    # Netzwerk
    'httpRequest': 'netzwerk', 'emailSend': 'netzwerk',
    'slack': 'netzwerk', 'telegram': 'netzwerk',
    'apiTrigger': 'netzwerk',
    # Ablauf
    'executeWorkflow': 'ablauf', 'if': 'ablauf', 'switch': 'ablauf',
    'merge': 'ablauf', 'wait': 'ablauf', 'splitInBatches': 'ablauf',
    'filter': 'ablauf', 'aggregate': 'ablauf', 'sort': 'ablauf',
    'noOp': 'ablauf', 'set': 'ablauf',
    'crypto': 'ablauf', 'dateTime': 'ablauf', 'splitOut': 'ablauf',
    'limit': 'ablauf', 'removeDuplicates': 'ablauf',
    'summarize': 'ablauf', 'compareDatasets': 'ablauf',
    'errorTrigger': 'ablauf', 'chatTrigger': 'ablauf',
}

# Klartext-Labels für die Kategorien
_KATEGORIE_LABEL = {
    'ausloeser': 'Auslöser', 'ki': 'KI/Modell', 'daten': 'Daten',
    'code': 'Code', 'netzwerk': 'Netzwerk', 'ablauf': 'Ablauf', 'sonstige': 'Sonstige',
}

# KI-Typ-Endungen (letzte Teil nach Punkt), die als "ki" gelten
_KI_ENDUNGEN = tuple('lmChat' + s for s in ('OpenAi', 'Anthropic', 'GoogleGemini', 'MistralCloud', 'Groq', 'AzureOpenAi', 'Ollama')) + (
    'agent', 'chainLlm', 'informationExtractor', 'textClassifier',
)
_KI_TYP_PREFIXES = ('@n8n/n8n-nodes-langchain.', 'lmChat', 'lmChatOllama')

# Geheimnis-Schlüssel (ohne Unterscheidung Groß/Klein)
_GEHEIM_SCHLUESSEL = re.compile(
    r'(authorization|api[-_]?key|apikey|access[-_]?token|secret|password|passwd|client_secret|bearer)', re.I
)

# Muster für bekannte Secrets (Wert muss NICHT mit = beginnen, d. h. kein n8n-Ausdruck)
_GEEIGNETER_WERT_MUSTER = re.compile(
    r'^(?!.*=\{)'
    r'(sk-[a-zA-Z0-9]{10,}|'
    r'ghp_[a-zA-Z0-9]{20,}|'
    r'xox[bapr]-[a-zA-Z0-9-]+|'
    r'AIza[a-zA-Z0-9_-]{10,}|'
    r'[a-zA-Z0-9/+]{32,}={0,2})'
)

# Platzhalter, die KEINE Secrets sind (wenn Wert darauf matcht)
_PLATZHALTER_MUSTER = re.compile(
    r'^={|<.+>|YOUR_|xxx|placeholder|ENTER_|CHANGE_|TODO|SETME|DEIN_|DEINE_', re.I
)

# n8n-Ausdrücke, die auf Zugriffsdaten verweisen → KEIN Fund
_N8N_AUSDRUCK = re.compile(r'^=.*\$[cenj].*\bcredentials\b', re.I)

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


def _kategorie(typ):
    """Kategorie eines Knotentyps bestimmen."""
    ende = str(typ).rsplit('.', 1)[-1]
    if ende in _KATEGORIEN:
        return _KATEGORIEN[ende]
    # Langchain-Präfix prüfen
    typ_str = str(typ).lower()
    if 'n8n-nodes-langchain' in typ_str:
        for end in ('lmChat', 'agent', 'chainLlm', 'informationExtractor', 'textClassifier',
                     'memory', 'tool', 'vectorStore', 'embeddings'):
            if end in typ_str:
                return 'ki'
    if ende in _KI_ENDUNGEN:
        return 'ki'
    if any(str(typ).startswith(p) for p in _KI_TYP_PREFIXES):
        return 'ki'
    return 'sonstige'


def _kategoriere_knoten(nodes):
    """Knoten nach Kategorie gruppieren. Gibt Dict {kat: [node_names]} zurück."""
    groups = {k: [] for k in _KATEGORIE_LABEL}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if str(n.get('type', '')).endswith('stickyNote'):
            continue
        cat = _kategorie(n.get('type', ''))
        groups.setdefault(cat, []).append(n.get('name', ''))
    return groups


def _ausloeser_info(nodes):
    """Info zu Auslösern: name, art, zeitplan (lesbar oder null)."""
    aus = []
    for n in nodes:
        if not _ist_ausloeser(n.get('type', '')):
            continue
        name = n.get('name', '')
        typ = n.get('type', '')
        par = n.get('parameters', {})
        zeitplan = None
        # scheduleTrigger
        if str(typ).endswith('scheduleTrigger'):
            interval = par.get('interval', {}) if isinstance(par, dict) else {}
            if isinstance(interval, dict):
                minuten = interval.get('value', interval.get('interval', '')) if 'value' in interval else ''
                if minuten:
                    zeitplan = 'alle %s Minuten' % minuten
        # cron
        elif str(typ).endswith('cron'):
            expression = par.get('expression', '') if isinstance(par, dict) else ''
            if expression and not expression.startswith('='):
                zeitplan = 'Cron: %s' % str(expression)[:60]
        aus.append({'name': name, 'art': _label(typ), 'zeitplan': zeitplan})
    return aus


def _zugaenge(nodes):
    """Zugangsdaten nach Art auflisten."""
    arten = {}
    for n in nodes:
        creds = n.get('credentials')
        if not isinstance(creds, dict):
            continue
        for art in creds:
            arten.setdefault(art, set()).add(n.get('name', ''))
    return {'knoten': sum(1 for n in nodes if isinstance(n.get('credentials'), dict)),
            'arten': sorted(arten.keys()), 'arten_detail': {a: sorted(v) for a, v in arten.items()}}


def _geheimnis_wert_bewerten(wert):
    """Prüft einen Wert auf Geheimnis. Gibt True zurück wenn es ein Geheimnis ist."""
    if not isinstance(wert, str):
        return False
    wert = wert.strip()
    if not wert:
        return False
    # n8n-Ausdruck mit $credentials → kein Geheimnis
    if _N8N_AUSDRUCK.search(wert):
        return False
    # Startet mit = → n8n-Ausdruck
    if wert.startswith('='):
        return False
    # Platzhalter
    if _PLATZHALTER_MUSTER.search(wert):
        return False
    # Bekannte Muster
    if _GEEIGNETER_WERT_MUSTER.search(wert):
        return True
    return False


def _suche_geheimnisse_knoten(node, pfad='', tiefe=0, max_tiefe=8):
    """Rekursiv nach Klartext-Secrets in Parametern suchen.
    Gibt Liste von {knoten, ort, art, stufe, text} zurück.
    Tiefe begrenzt, Wert wird nie im Ergebnis ausgegeben."""
    funde = []
    if tiefe > max_tiefe:
        return funde
    name = node.get('name', '')
    if not isinstance(node, dict):
        return funde
    params = node.get('parameters', {})
    if not isinstance(params, dict):
        return funde

    def _check_params(par, ort):
        if not isinstance(par, dict):
            return
        for key, val in par.items():
            aktueller_ort = '%s.%s' % (ort, key) if ort else key
            if _GEHEIM_SCHLUESSEL.search(key):
                if isinstance(val, str) and _geheimnis_wert_bewerten(val):
                    funde.append({
                        'knoten': name, 'ort': aktueller_ort, 'art': 'Schlüssel im Klartext',
                        'stufe': 'warn', 'text': ('Geheimnis im Klartext erkannt: %s (%s). Wert wird nicht ausgegeben.' % (key, _GEHEIM_SCHLUESSEL.search(key).group(1))),
                    })
            elif isinstance(val, dict):
                # HTTP-Request Header/Query als name/value-Paare
                name_val = val.get('name') if isinstance(val.get('name'), str) else None
                val_val = val.get('value') if isinstance(val.get('value'), str) else None
                if name_val and val_val and isinstance(val_val, str):
                    aktueller_ort_p = '%s[%s]' % (ort, name_val)
                    if _GEHEIM_SCHLUESSEL.search(name_val) and _geheimnis_wert_bewerten(val_val):
                        funde.append({
                            'knoten': name, 'ort': aktueller_ort_p, 'art': 'Header-/Query-Parameter',
                            'stufe': 'warn', 'text': ('Geheimnis im Klartext erkannt: %s (%s). Wert wird nicht ausgegeben.' % (name_val, _GEHEIM_SCHLUESSEL.search(name_val).group(1))),
                        })
                else:
                    _check_params(val, aktueller_ort)
            elif isinstance(val, list):
                for i, item in enumerate(val):
                    if isinstance(item, dict):
                        _check_params(item, '%s[%d]' % (ort, i))

    _check_params(params, 'parameters')
    # Auch credentials rekursiv prüfen (obwohl Werte meist Referenzen)
    creds = node.get('credentials', {})
    if isinstance(creds, dict):
        for art, details in creds.items():
            if isinstance(details, dict):
                for dk, dv in details.items():
                    if isinstance(dv, str) and _GEHEIM_SCHLUESSEL.search(dk) and _geheimnis_wert_bewerten(dv):
                        funde.append({
                            'knoten': name, 'ort': 'credentials.%s.%s' % (art, dk), 'art': 'Zugriffsdaten',
                            'stufe': 'warn', 'text': ('Geheimnis in Zugangsdaten: %s (%s). Wert wird nicht ausgegeben.' % (dk, _GEHEIM_SCHLUESSEL.search(dk).group(1))),
                        })
    return funde


def _externe_ziele(nodes):
    """Externe Ziele aus HTTP-URLs, Webhooks, E-Mail, Slack, Telegram."""
    doms = set()
    dienste = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        name = n.get('name', '')
        typ = str(n.get('type', ''))
        par = n.get('parameters', {}) or {}
        # httpRequest
        if str(typ).endswith('httpRequest'):
            url = par.get('url', '') if isinstance(par, dict) else ''
            if isinstance(url, str):
                if url.startswith('=') or '{' in url or '${' in url:
                    doms.add('(dynamisch)')
                else:
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        host = parsed.netloc.split('@')[-1]  # user:pass@ entfernen
                        if host:
                            doms.add(host)
                    except Exception:
                        pass
        # webhook
        if str(typ).endswith('webhook'):
            pfad = par.get('path', '') if isinstance(par, dict) else ''
            methode = par.get('method', '') if isinstance(par, dict) else ''
            if isinstance(pfad, str) and isinstance(methode, str):
                dienste.append('Webhook (Pfad: %s, Methode: %s)' % (pfad[:50], methode[:10]))
        # E-Mail / Gmail
        if str(typ).endswith('emailSend') or str(typ).endswith('gmail'):
            dienste.append('E-Mail / Gmail')
        # Slack
        if str(typ).endswith('slack'):
            dienste.append('Slack')
        # Telegram
        if str(typ).endswith('telegram'):
            dienste.append('Telegram')
    return {'domains': sorted(doms), 'dienste': dienste}


def _cloud_knoten(nodes):
    """KI-Knoten prüfen: Cloud oder lokal?"""
    cloud_trenner = {'lmChatAnthropic': 'Anthropic', 'lmChatOpenAi': 'OpenAI',
                     'lmChatGoogleGemini': 'Google Gemini', 'lmChatMistralCloud': 'Mistral',
                     'lmChatGroq': 'Groq', 'lmChatAzureOpenAi': 'Azure OpenAI',
                     'lmChatOllama': 'Ollama'}
    ergebnis = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        typ = str(n.get('type', ''))
        ende = typ.rsplit('.', 1)[-1]
        if ende not in cloud_trenner:
            continue
        provider_name = cloud_trenner[ende]
        par = n.get('parameters', {}) or {}
        ort = 'unbekannt'
        # Basis-URL prüfen
        base_url = par.get('baseUrl', '') if isinstance(par, dict) else ''
        if not isinstance(base_url, str):
            base_url = ''
        if base_url in ('127.0.0.1', 'localhost', '127.0.0.1:11434', 'localhost:11434'):
            ort = 'lokal'
        elif base_url and 'localhost' not in base_url and '127.0.0.1' not in base_url:
            ort = 'cloud'
        elif 'Ollama' in provider_name:
            ort = 'lokal'
        elif 'OpenAi' in provider_name and ende == 'lmChatOpenAi':
            # credentials-Namen prüfen
            creds = n.get('credentials', {}) or {}
            cred_name = creds.get('name', creds.get('httpHeaderAuth', {}).get('name', '')) if isinstance(creds, dict) else ''
            if isinstance(cred_name, str) and ('lokal' in cred_name.lower() or 'sedra' in cred_name.lower()):
                ort = 'lokal'
            else:
                ort = 'cloud'
        else:
            ort = 'cloud'
        ergebnis.append({'name': n.get('name', ''), 'typ': typ, 'anbieter': provider_name, 'ort': ort})
    return ergebnis


def _modellknoten_info(nodes):
    """KI-Modellknoten analysieren (für SPEZ-04a D)."""
    ergebnis = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        typ = str(n.get('type', ''))
        ende = typ.rsplit('.', 1)[-1]
        # Nur Modellknoten und KI-Knoten
        is_ki = (ende in _KI_ENDUNGEN or
                 any(typ.startswith(p) for p in _KI_TYP_PREFIXES) or
                 'n8n-nodes-langchain' in typ.lower())
        if not is_ki:
            continue
        # Modellname lesen
        par = n.get('parameters', {}) or {}
        modell = par.get('modelName', '') if isinstance(par, dict) else ''
        if isinstance(modell, dict):
            modell = modell.get('name', modell.get('value', ''))
        modell = modell if isinstance(modell, str) else ''
        if modell and modell.startswith('='):
            modell = None
        elif modell and modell in ('', '{}'):
            modell = None

        # Anbieter bestimmen
        anbieter = 'unbekannt'
        ort = 'unbekannt'
        cloud_map = {'lmChatAnthropic': 'anthropic', 'lmChatOpenAi': 'openai',
                     'lmChatGoogleGemini': 'google', 'lmChatMistralCloud': 'mistral',
                     'lmChatGroq': 'groq', 'lmChatAzureOpenAi': 'azure', 'lmChatOllama': 'ollama'}
        if ende in cloud_map:
            anbieter = cloud_map[ende]
            # Ort prüfen
            base_url = par.get('baseUrl', '') if isinstance(par, dict) else ''
            if isinstance(base_url, str) and base_url in ('127.0.0.1', 'localhost', '127.0.0.1:11434', 'localhost:11434'):
                ort = 'lokal'
            elif 'Ollama' in anbieter:
                ort = 'lokal'
            else:
                ort = 'cloud'
        else:
            anbieter = 'lokal'
            ort = 'lokal'

        # Optionen
        optionen = {}
        for key in ('temperature', 'maxTokens', 'timeout', 'maxRetries'):
            val = par.get(key) if isinstance(par, dict) else None
            if val is not None:
                optionen[key] = val

        # Umstellbar: ja wenn ein bekannter Cloud-Anbieter
        umstellbar = anbieter in ('openai', 'anthropic', 'google', 'mistral', 'groq', 'azure')

        ergebnis.append({
            'name': n.get('name', ''), 'typ': typ, 'anbieter': anbieter,
            'modell': modell, 'ort': ort, 'nutzer': [], 'optionen': optionen,
            'umstellbar': umstellbar,
        })
    return ergebnis


def _code_knoten_info(nodes):
    """Code-Knoten analysieren."""
    ergebnis = []
    muster_prozess = re.compile(r'child_process|require\s*\(\s*[\'"]fs[\'"]\s*\)|eval\s*\(|exec\s*\(|fetch\s*\(|http\.request', re.I)
    for n in nodes:
        if not isinstance(n, dict):
            continue
        typ = str(n.get('type', ''))
        if not str(typ).endswith(('code', 'function', 'functionItem')):
            continue
        par = n.get('parameters', {}) or {}
        code = par.get('code', '') if isinstance(par, dict) else ''
        if not isinstance(code, str):
            code = ''
        sprache = 'javascript'
        zeilen = code.count('\n') + 1
        ergebnis.append({
            'name': n.get('name', ''), 'typ': typ, 'sprache': sprache, 'zeilen': zeilen,
        })
        # Warnung bei gefährlichen Mustern
        if muster_prozess.search(code):
            zeilen_nummern = []
            for i, zeile in enumerate(code.split('\n'), 1):
                if muster_prozess.search(zeile):
                    zeilen_nummern.append(i)
            ergebnis[-1]['gefaehrliche_muster'] = zeilen_nummern
    return ergebnis


def _satz_bauen(zaehler, kategorien, kategorie_list):
    """Satz aus den Zahlen bauen."""
    teile = []
    ausloeser = zaehler.get('ausloeser', 0)
    if ausloeser == 1:
        teile.append('Startet über Zeitplan.')
    elif ausloeser == 0:
        teile.append('Hat keinen Auslöser (Start).')
    s = []
    if zaehler.get('knoten', 0):
        s.append('%d Knoten' % zaehler['knoten'])
    ki = kategorie_list.get('ki', 0)
    if ki:
        s.append('%d KI-Knoten' % ki)
    code = kategorie_list.get('code', 0)
    if code:
        s.append('%d Code-Knoten' % code)
    teile.append('. ' + ' und '.join(s) + '.')
    return ''.join(teile)



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
    'urteil': {stufe, satz}, 'aenderungen': [...], 'layout_noetig': bool, 'zaehler': {...},
    'zusammenfassung': str, 'kategorien': {kat: [namen]}, 'pruefung': {geheimnisse: [...], cloud: [...], code: [...]},
    'modellknoten': [{name, typ, anbieter, modell, ort, nutzer, optionen, umstellbar}],
    'workflow': dokument}. Wirft nie; Fehler stehen in 'fehler'."""
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
    # --- Neue Analyse ---
    kategorien = _kategoriere_knoten(nodes)
    ausloeser = _ausloeser_info(nodes)
    zugang_info = _zugaenge(nodes)
    externe = _externe_ziele(nodes)
    cloud = _cloud_knoten(nodes)
    modellknoten = _modellknoten_info(nodes)
    code_knoten = _code_knoten_info(nodes)
    # --- Secrets ---
    alle_geheimnisse = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if str(n.get('type', '')).endswith('stickyNote'):
            continue
        funde_knoten = _suche_geheimnisse_knoten(n)
        if funde_knoten:
            alle_geheimnisse.extend(funde_knoten)
            # Funde zur Warnung hinzufügen
            funde.append({'stufe': 'warn', 'text': 'Geheimnis-Erkennung: %d Einträge mit verdächtigen Werten (%s). Werte werden nicht angezeigt und nicht gespeichert.' % (len(funde_knoten), ', '.join(set(g['knoten'] for g in funde_knoten))[:120])})
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
        # Kategorie und KI-Typ in Hinweisen
        kat = _kategorie(n.get('type', ''))
        if kat and kat != 'sonstige':
            hinweise.append('Kategorie: ' + _KATEGORIE_LABEL.get(kat, kat))
        if kat == 'ki':
            hinweise.append('KI-Knoten')
        zeilen.append({'id': n['id'], 'name': n['name'], 'typ': n['type'], 'art': _label(n['type']), 'status': 'notiz' if notiz else ('unterstuetzt' if unterstuetzt else 'erhalten'),
                       'ausloeser': _ist_ausloeser(n['type']), 'deaktiviert': bool(n.get('disabled')), 'zugang': hat_zugang, 'hinweise': hinweise,
                       'kategorie': kat})
    verb = _verbindungen(doc)
    verbunden = {v['von'] for v in verb} | {v['nach'] for v in verb}
    lose = [n['name'] for n in nodes if n['name'] not in verbunden and not str(n['type']).endswith('stickyNote')]
    echte = [z for z in zeilen if z['status'] != 'notiz']
    erhalten = [z for z in zeilen if z['status'] == 'erhalten']
    # Auslöser-Warnung
    if not any(z['ausloeser'] for z in echte):
        funde.append({'stufe': 'info', 'text': 'Es gibt keinen Auslöser (Start). In n8n wird so ein Workflow nur von einem anderen aufgerufen.'})
    # Unbekannte Knoten
    if erhalten:
        funde.append({'stufe': 'warn', 'text': '%d von %d Knoten kennt SEDRA noch nicht (%s). Sie bleiben vollständig erhalten und erscheinen im Bild, laufen hier aber nicht.' % (len(erhalten), len(echte), ', '.join(sorted({z['art'] for z in erhalten})[:5]))})
    # Zugangsdaten
    if zugang:
        funde.append({'stufe': 'warn', 'text': 'Zugangsdaten: %d Knoten verweisen darauf (%s). Es stehen nur die Verweise in der Datei, keine Passwörter. Vor dem Weitergeben prüfen; der bereinigte Export entfernt sie.' % (len(zugang), ', '.join(zugang[:4]))})
    # pinData
    if doc.get('pinData'):
        funde.append({'stufe': 'info', 'text': 'Die Datei enthält angeheftete Testdaten (pinData). Sie bleiben erhalten; der bereinigte Export lässt sie weg.'})
    # Deaktivierte Knoten
    if any(z['deaktiviert'] for z in echte):
        funde.append({'stufe': 'info', 'text': '%d Knoten sind in n8n ausgeschaltet; das bleibt so.' % sum(1 for z in echte if z['deaktiviert'])})
    # Lose Knoten
    if lose:
        funde.append({'stufe': 'warn', 'text': 'Nicht verbunden: %s. Sie hängen an nichts und würden nie erreicht.' % ', '.join(lose[:5])})
    # Aktiv
    if doc.get('active') is True:
        funde.append({'stufe': 'info', 'text': 'In n8n war der Workflow aktiv. Hier wird er nie von selbst gestartet; Läufe brauchen die Freigabe des Captains.'})
    # Prozessmodell
    if rep['process']['model_only']:
        funde.append({'stufe': 'info', 'text': 'Das ist ein Prozessmodell von SEDRA (Beschreibung ohne Ausführung).'})
    # Urteil
    ass = assessment(doc)
    if erhalten or zugang or not ass['executable']:
        urteil = {'stufe': 'teilweise', 'satz': 'Wird übernommen und bleibt vollständig erhalten. Ausführen lässt sich davon in SEDRA nur, was die Engine kennt; hier sind es %d von %d Knoten.' % (len(echte) - len(erhalten), len(echte))}
    else:
        urteil = {'stufe': 'ok', 'satz': 'Alle Knoten sind bekannt. Ausgeführt wird nur nach der Freigabe des Captains.'}
    # Zusammenfassung bauen
    kategorie_list = {k: len(v) for k, v in kategorien.items()}
    zusammenfassung = _satz_bauen(
        {'knoten': len(echte), 'ausloeser': sum(1 for z in echte if z['ausloeser'])},
        kategorien, kategorie_list
    )
    return {'ok': True, 'fehler': None, 'name': doc['name'], 'knoten': zeilen, 'verbindungen': verb, 'funde': funde, 'urteil': urteil, 'aenderungen': aenderungen,
            'layout_noetig': _alle_null_oder_gleich(nodes), 'ausfuehrbar': ass['executable'],
            'zaehler': {'knoten': len(echte), 'notizen': len(zeilen) - len(echte), 'verbindungen': len(verb), 'unbekannt': len(erhalten), 'zugang': len(zugang),
                        'ausloeser': sum(1 for z in echte if z['ausloeser'])},
            'zusammenfassung': zusammenfassung, 'kategorien': kategorien,
            'ausloeser_info': ausloeser, 'zugaenge': zugang_info,
            'externe_ziele': externe, 'cloud_knoten': cloud,
            'modellknoten': modellknoten, 'code_knoten': code_knoten,
            'pruefung': {'geheimnisse': alle_geheimnisse},
            'workflow': doc}
