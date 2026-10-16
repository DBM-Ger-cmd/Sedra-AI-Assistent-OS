"""Der Arbeitsplatz von SEDRA: was die Oberflächen sind, wo was steht, wie man etwas tut – und was gerade wartet (Build 24, Ticket B6-G-06).

Klaus, 15.10.2026 19:22: „Die Shell bildet den Arbeitsplatz für SEDRA; SEDRA muss – wie beim KI GateWay – seinen Arbeitsplatz kennen,
um helfen und beraten zu können.“ Dieselbe Bauart wie `gateway/wissen.py`: Wissen aus dem Code in eine SQLite-Tabelle, deterministische
Suche, Antworten ohne Modell (Wissensbasis kommt vor Modellwissen, E2), Knöpfe statt Handlungen (nichts läuft von allein). Der
Live-Stand (was wartet) kommt aus den Lesewegen der Runtime, die der Hub ohnehin hat – hier wird nichts geändert und nichts gespeichert
außer der Wissensdatei `local_config/sedra/arbeitsplatz.sqlite`, die bei jedem Start aus dem Code neu entsteht.

Das Wissen selbst liegt bei den Modulen (`arbeitsplatz.yaml` je Shell und Werkzeug, Klaus 19:36); hier stehen der Lader, der Vertragsteil
(Umschalter, Strg+K, Entscheidungen) und die Antwort. Reine Teile: `lies_modul`, `sammle`, `zustaendig`, `naechstes`, `beschreibung`."""
from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path

VERSION = 'arbeitsplatz-0.1'

# ----------------------------------------------------------------------------------------------------------------- das Wissen der Module
# Klaus 15.10. 19:36: „Arbeitsplatzwissen bleibt immer im Modul.“ Jede Shell und jedes Werkzeug trägt sein Wissen in `arbeitsplatz.yaml`
# im eigenen Ordner (Satz, Zonen, eigene Wörter, Anleitungen, Begriffe). Hier steht nur, was zum Vertrag gehört und in jeder Oberfläche gilt.
DATEI = 'arbeitsplatz.yaml'
ERLAUBT = {'satz', 'zonen', 'woerter', 'anleitungen', 'begriffe'}
from .gateway import OBJECT_TYPES as _VERTRAG_TYPEN
OBJEKT_TYPEN = tuple(t for t in _VERTRAG_TYPEN if t != 'routine')     # die Typen des Vertrags – ohne routine: kein Werkzeug dahinter

UEBERALL = [('Umschalter', 'der runde Knopf unten rechts (Alt+S): Übersicht der Oberflächen, Wechsel, Darstellung Klar/Nacht, Schrift Normal/Groß'),
            ('Strg+K', 'einen Ort öffnen („Entscheidungen“, „Werkstatt“) oder einen Satz an das Gespräch geben'),
            ('Entscheidungen', 'jede Freigabe hat einen Ort; eine Antwort im Gespräch erzeugt dasselbe Audit'),
            ('KI GateWay', 'hat seine eigene Oberfläche „KI GateWay Studio“ (Umschalter → Wechseln zu KI GateWay Studio); dort Vorgänge, Regelbuch, Leitfaden, „Frag SEDRA“'),
            ('Nichts läuft von allein', 'was SEDRA vorschlägt, wird ein Knopf; erst dein Klick führt es aus')]
VERTRAG_ANLEITUNGEN = [
    {'id': 'shell_wechseln', 'titel': 'Die Oberfläche wechseln oder zur Übersicht',
     'schritte': ['Umschalter unten rechts (Alt+S).', '„Übersicht der Oberflächen“ oder „Wechseln zu …“ – die Seite lädt neu.', 'Dort auch Darstellung Klar/Nacht und Schrift Normal/Groß.'],
     'ort': None, 'stich': 'oberfläche oberflaeche wechseln shell übersicht uebersicht umschalter alt+s zurück hauptseite darstellung nacht schrift groß gross'}]
VERTRAG_BEGRIFFE = {'umschalter': 'Der runde Knopf unten rechts (Alt+S) in jeder Oberfläche: Übersicht, Wechsel, Darstellung, Schrift.'}


def _objekt_ok(o):
    return o is None or (isinstance(o, dict) and o.get('type') in OBJEKT_TYPEN and isinstance(o.get('id'), str) and o['id'] and isinstance(o.get('title'), str))


def lies_modul(folder, kind, mid):
    """Die arbeitsplatz.yaml eines Moduls, geprüft. Rückgabe (wissen, befunde): fehlt die Datei → ({}, []); ein Fehler ist ein Befund, kein Absturz –
    und das betroffene Stück bleibt weg (fail-closed: lieber kein Wissen als falsches)."""
    import yaml
    path = Path(folder) / DATEI
    if not path.is_file():
        return {}, []
    befunde = []
    try:
        doc = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    except Exception as exc:
        return {}, [f'{kind}/{mid}: {DATEI} nicht lesbar ({type(exc).__name__})']
    a = doc.get('arbeitsplatz') if isinstance(doc, dict) else None
    if not isinstance(a, dict):
        return {}, [f'{kind}/{mid}: {DATEI} ohne Schlüssel arbeitsplatz']
    extra = sorted(set(a) - ERLAUBT)
    if extra:
        befunde.append(f'{kind}/{mid}: unbekannte Schlüssel {extra}')
    out = {'satz': str(a.get('satz') or ''), 'zonen': [], 'woerter': {}, 'anleitungen': [], 'begriffe': {}}
    for z in (a.get('zonen') or []):
        if isinstance(z, dict) and z.get('name') and z.get('wo'):
            out['zonen'].append((str(z['name']), str(z['wo'])))
        else:
            befunde.append(f'{kind}/{mid}: Zone ohne name/wo')
    for k, v in (a.get('woerter') or {}).items():
        if isinstance(v, dict) and v.get('ist') and _objekt_ok(v.get('objekt')):
            out['woerter'][str(k).lower()] = (str(v['ist']), v.get('objekt'))
        else:
            befunde.append(f'{kind}/{mid}: Wort {k} ohne ist/objekt oder mit fremdem Objekttyp')
    for an in (a.get('anleitungen') or []):
        if isinstance(an, dict) and an.get('id') and an.get('titel') and isinstance(an.get('schritte'), list) and an['schritte'] and _objekt_ok(an.get('ort')):
            out['anleitungen'].append({'id': str(an['id']), 'titel': str(an['titel']), 'schritte': [str(x) for x in an['schritte']], 'ort': an.get('ort'), 'stich': str(an.get('stich') or '')})
        else:
            befunde.append(f'{kind}/{mid}: Anleitung {an.get("id") if isinstance(an, dict) else "?"} unvollständig')
    for k, v in (a.get('begriffe') or {}).items():
        if isinstance(v, str) and v:
            out['begriffe'][str(k).lower()] = v
    return out, befunde


def sammle(module):
    """`module`: Liste von (kind, id, name, folder). Rückgabe: SHELLS, ANLEITUNGEN, BEGRIFFE, befunde – zusammengesetzt aus den Modulen und dem Vertrag."""
    shells, anleitungen, begriffe, befunde = {}, list(VERTRAG_ANLEITUNGEN), dict(VERTRAG_BEGRIFFE), []
    for kind, mid, name, folder in module:
        wissen, b = lies_modul(folder, kind, mid)
        befunde.extend(b)
        if kind == 'shell':
            shells[mid] = {'name': name or mid, 'satz': wissen.get('satz', ''), 'zonen': wissen.get('zonen', []), 'woerter': wissen.get('woerter', {}),
                           'begriffe': wissen.get('begriffe', {})}
        for an in wissen.get('anleitungen', []):
            an = dict(an, modul=f'{kind}/{mid}')
            anleitungen.append(an)
        for k, v in wissen.get('begriffe', {}).items():
            begriffe.setdefault(k, v)
    return shells, anleitungen, begriffe, befunde


def module_aus_registry(registry):
    """Die registrierten Module (Paket und eigene) mit Name aus dem Manifest – ohne Doppelte."""
    import yaml
    out = []
    for kind, datei, key in (('shells', 'shell.yaml', 'shell'), ('tools', 'tool.yaml', 'tool')):
        for folder, origin, problem in registry.module_dirs(kind):
            if problem:
                continue
            name = folder.name
            try:
                doc = yaml.safe_load((folder / datei).read_text(encoding='utf-8')) or {}
                name = str((doc.get(key) or {}).get('name') or folder.name)
            except Exception:
                pass
            out.append((key, folder.name, name, folder))
    return out


# ----------------------------------------------------------------------------------------------------------------- Suche
_WORT = re.compile(r'[a-zäöüß0-9\-\+]{2,}')
_STOPP = frozenset('''wie wird das der die den dem des ist was ein eine einen und mit ich mir mich mein meine im in zu zum zur nicht bitte kann
kannst gibt gibts auf für fuer von bei oder sich sind war hat habe haben dann noch auch nur hier dort dieser diese dieses jetzt mal doch
schon sehr soll sollte muss müssen muessen darf dürfen wo wer wann warum wieso weshalb welche welcher welches alles über ueber nach
vor aus als wenn dass etwas nichts einem einer eines ihm ihr ihre sein seine man uns wir sie es da denn also ganz gut sedra guppi du
finde ich'''.split())
_WO = ('wo finde', 'wo ist', 'wo sind', 'wo steht', 'wo liegt', 'wo kann', 'wie komme', 'wie öffne', 'wie oeffne', 'wo öffne', 'wo oeffne')
_WIE = ('wie lege', 'wie füge', 'wie fuege', 'wie starte', 'wie fahre', 'wie lade', 'wie wechsle', 'wie wechsel', 'wie bestätige', 'wie bestaetige',
        'wie beantworte', 'wie mache', 'wie geht das', 'wie funktioniert', 'wie benutze', 'wie nutze', 'wie arbeite', 'anleitung', 'schritte')
_WAS = ('was ist der', 'was ist die', 'was ist das', 'was ist ein', 'was ist eine', 'was bedeutet', 'was heißt', 'was heisst', 'was sind')
_NAECHSTES = ('nächst', 'naechst', 'was muss ich', 'was soll ich', 'was jetzt', 'was nun', 'als nächstes', 'als naechstes', 'was tun', 'was wartet',
              'was liegt an', 'wo stehe ich', 'was steht an')
ORT_WORTE = ('oberfläche', 'oberflaeche', 'shell', 'cockpit', 'paperclip', 'minimal', 'studio', 'dashboard', 'posteingang', 'issues', 'ziele', 'werkbank',
             'baum', 'navigation', 'reiter', 'schublade', 'umschalter', 'instrument', 'kachel', 'leiste', 'menü', 'menue', 'fenster', 'ablage',
             'teststrecke', 'standardtest', 'werkstatt', 'modell hinzufügen', 'modell hinzufuegen', 'neues modell', 'neues projekt', 'projekt anlegen',
             'strg+k', 'alt+s', 'nacht', 'schrift', 'wechseln', 'übersicht', 'uebersicht', 'logbuch', 'entscheidung', 'grenzen', 'modus', 'vorhaben',
             'arbeitsplatz', 'arbeitsumgebung', 'bedienung', 'hilfe')


def _woerter(text):
    return [w for w in _WORT.findall((text or '').lower()) if w not in _STOPP]


def _trifft(wort, menge):
    """Ganzes Wort, oder ein längeres Wort der Menge beginnt damit (modell → modelle); nie ein Teil mitten im Wort (gate ≠ gateway nicht – das ist ein Anfang; aber „ist“ ≠ „liste“)."""
    if wort in menge:
        return True
    return len(wort) >= 5 and any(m.startswith(wort) and len(m) <= len(wort) + 3 for m in menge)


def zustaendig(frage, aktive_shell=None):
    """Ob die Arbeitsplatz-Wissensbasis die Frage beantwortet (vor dem Modell). Das GateWay wird vorher gefragt (gateway/wissen.py)."""
    low = (frage or '').lower()
    if any(w in low for w in _NAECHSTES):
        return True
    if any(w in low for w in ORT_WORTE) and (any(w in low for w in _WO) or any(w in low for w in _WIE) or any(w in low for w in _WAS) or '?' in low):
        return True
    if any(w in low for w in _WO) or any(w in low for w in _WIE):
        return True
    return False


def beschreibung(shell_id, shells=None):
    """Ein Absatz für den Systemtext des Modells: wo SEDRA gerade arbeitet (rein; `shells` aus `sammle`)."""
    sh = (shells or {}).get(shell_id or '')
    if not sh:
        return 'Deine Arbeitsumgebung ist die Oberfläche von SEDRA. ' + ' '.join(f'{k}: {v}.' for k, v in UEBERALL)
    zonen = ' '.join(f'{k}: {v}.' for k, v in sh['zonen'])
    woerter = ('Wo was ist: ' + '; '.join(f'„{k}“ = {v[0]}' for k, v in sh['woerter'].items()) + '. ') if sh['woerter'] else ''
    return (f'Deine Arbeitsumgebung ist die Oberfläche „{sh["name"]}“: {sh["satz"]} {zonen} {woerter}'
            + ' '.join(f'{k}: {v}.' for k, v in UEBERALL))


def naechstes(live):
    """Was als Nächstes ansteht, aus dem Live-Stand (rein): Liste von (Satz, Objekt) in der Reihenfolge, in der ein Mensch es tun sollte."""
    live = live or {}
    out = []
    if live.get('grenzen_bestaetigt') is False:
        out.append(('Modus und Grenzen sind nicht bestätigt – bis dahin bleibt jede Aufgabe stehen.', {'type': 'boundary', 'id': 'projekt', 'title': 'Modus und Grenzen'}))
    n = live.get('entscheidungen') or 0
    if n:
        out.append((f'{n} Entscheidung{"en warten" if n != 1 else " wartet"} auf deine Antwort (Freigabe oder Ablehnung).', {'type': 'decision', 'id': 'alle', 'title': 'Entscheidungen', 'collection': True}))
    g = live.get('gateway_wartend') or 0
    if g:
        out.append((f'{g} GateWay-Vorg{"änge warten" if g != 1 else "ang wartet"} auf dich (Freigabe, Entscheidung oder Prüfung des Entwurfs) – in der Oberfläche KI GateWay Studio (Alt+S).', None))
    a = live.get('aufgaben_wartend') or 0
    if a:
        out.append((f'{a} Aufgabe{"n warten" if a != 1 else " wartet"} auf dich.', {'type': 'task', 'id': 'alle', 'title': 'Aufgaben', 'collection': True}))
    if not live.get('modell_geladen'):
        out.append(('Kein Modell geladen – das Gespräch antwortet nur aus der Wissensbasis; Entwürfe im GateWay brauchen ein Modell.', {'type': 'model', 'id': 'alle', 'title': 'Werkstatt', 'collection': True}))
    if not live.get('projekte'):
        out.append(('Noch kein Projekt – „＋ Neu → Projekt“.', {'type': 'project', 'id': 'neu', 'title': 'Neues Projekt'}))
    if not out:
        out.append(('Nichts wartet. Du kannst ein Vorhaben aufschreiben – oder im KI GateWay Studio (Alt+S) einen Vorgang anlegen.', {'type': 'intent', 'id': 'alle', 'title': 'Vorhaben', 'collection': True}))
    return out


class ArbeitsplatzWissen:
    """Die Wissensbasis über den Arbeitsplatz in SQLite (aus dem Code), plus Antworten mit Knöpfen. `live_fn()` liefert den Live-Stand."""

    def __init__(self, root: Path, live_fn=None, module=None):
        self.root = Path(root) / 'local_config' / 'sedra'
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'arbeitsplatz.sqlite'
        self.live_fn = live_fn or (lambda: {})
        self.shells, self.anleitungen, self.begriffe, self.befunde = sammle(module or [])
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.execute('CREATE TABLE IF NOT EXISTS wissen (id TEXT PRIMARY KEY, art TEXT, titel TEXT, text TEXT, shell TEXT, objekt TEXT, stichworte TEXT, version TEXT)')
        self._fuellen()

    def _fuellen(self):
        import json
        rows = []
        for sid, sh in self.shells.items():
            text = sh['satz'] + ' ' + ' '.join(f'{k}: {v}.' for k, v in sh['zonen'])
            if sh['woerter']:
                text += ' Wo was ist: ' + '; '.join(f'{k} = {v[0]}' for k, v in sh['woerter'].items()) + '.'
            rows.append(('S-' + sid, 'shell', 'Oberfläche ' + sh['name'], text, sid, '', ' '.join([sid, sh['name'], 'oberfläche shell'] + [z[0] for z in sh['zonen']] + list(sh['woerter'])).lower()))
            for k, (v, obj) in sh['woerter'].items():
                rows.append((f'W-{sid}-{k}', 'wort', f'„{k.capitalize()}“', f'In {sh["name"]}: {v}.', sid,
                             json.dumps(obj, ensure_ascii=False), (k + ' ' + v).lower()))
        for k, v in UEBERALL:
            rows.append(('U-' + k.lower().replace(' ', '-'), 'ueberall', k, v, '', '', (k + ' ' + v).lower()))
        for a in self.anleitungen:
            rows.append(('A-' + a['id'], 'anleitung', a['titel'], ' '.join(f'{i + 1}. {s}' for i, s in enumerate(a['schritte'])), '', json.dumps(a['ort'], ensure_ascii=False) if a['ort'] else '',
                         (a['stich'] + ' ' + a['titel']).lower()))
        for b, text in self.begriffe.items():
            rows.append(('B-' + b, 'begriff', b.capitalize(), text, '', '', (b + ' ' + text).lower()))
        with self._lock:
            self._db.execute('DELETE FROM wissen')
            self._db.executemany('INSERT INTO wissen VALUES (?,?,?,?,?,?,?,?)', [(*r, VERSION) for r in rows])
            self._db.commit()

    def suche(self, frage, shell=None, limit=3):
        import json
        woerter = _woerter(frage)
        low = (frage or '').lower()
        if not woerter:
            return []
        with self._lock:
            rows = self._db.execute('SELECT id, art, titel, text, shell, objekt, stichworte FROM wissen').fetchall()
        scored = []
        for rid, art, titel, text, sh, objekt, stich in rows:
            sw, tw, hw = set(_WORT.findall(stich)), set(_WORT.findall(text.lower())), set(_WORT.findall(titel.lower()))
            score = sum(2 for w in woerter if _trifft(w, sw)) + sum(1 for w in woerter if _trifft(w, tw)) + sum(3 for w in woerter if _trifft(w, hw))
            if not score:
                continue                                 # ohne ein Wort der Frage kein Treffer – Boni machen keinen
            if art == 'anleitung' and any(w in low for w in _WIE):
                score += 2
            if art == 'begriff' and any(w in low for w in _WAS):
                score += 2
            if sh and shell and sh == shell:
                score += 1
            if sh and shell and sh != shell and art == 'wort':
                score -= 2
            if objekt and any(w in low for w in _WO):
                score += 2                               # „wo finde ich …“ will einen Ort, den man öffnen kann
            if art == 'shell' and not any(w in low for w in ('oberfläche', 'oberflaeche', 'shell', sh, (self.shells.get(sh) or {}).get('name', sh).lower())):
                score -= 3                               # die Oberfläche selbst nur, wenn nach ihr gefragt wird
            if score >= 3:
                scored.append((score, {'id': rid, 'art': art, 'titel': titel, 'text': text, 'shell': sh, 'objekt': json.loads(objekt) if objekt else None, 'score': score}))
        scored.sort(key=lambda s: -s[0])
        out, gesehen = [], set()
        for sc, h in scored:                             # ein Wort und sein Begriff sagen dasselbe – einmal reicht; weit Schwächeres ist Rauschen
            key = h['id'].split('-')[-1].lower()
            if key in gesehen or sc * 2 < scored[0][0]:
                continue
            gesehen.add(key); out.append(h)
            if len(out) >= limit:
                break
        return out

    def stand(self):
        try:
            return dict(self.live_fn() or {})
        except Exception as exc:          # ein Leseweg fehlt: dann ohne diesen Wert, nie ein Fehler im Gespräch
            return {'fehler': type(exc).__name__}

    def antwort(self, frage, shell=None):
        frage = str(frage or '').strip()
        low = frage.lower()
        sh = self.shells.get(shell or '')
        name = sh['name'] if sh else 'dieser Oberfläche'
        if any(w in low for w in _NAECHSTES):
            live = self.stand()
            punkte = naechstes(live)
            lines = [f'Dein Arbeitsplatz ist {name}. Das steht an:'] + [f'{i + 1}. {satz}' for i, (satz, _) in enumerate(punkte)]
            actions = [{'kind': 'open', 'object': o, 'title': o['title']} for _, o in punkte if o][:3]
            return self._out('\n'.join(lines), actions, 'naechstes')
        hits = self.suche(frage, shell)
        if not hits:
            return self._out(f'Dazu weiß ich am Arbeitsplatz nichts. Du bist in {name}: {sh["satz"] if sh else ""} Umschalter unten rechts (Alt+S), Strg+K für einen Ort.',
                             [], 'unbekannt')
        lines, actions = [], []
        for h in hits:
            if h['art'] == 'anleitung':
                lines.append(h['titel'] + '\n' + h['text'].replace(' 2. ', '\n2. ').replace(' 3. ', '\n3. ').replace(' 4. ', '\n4. ').replace(' 5. ', '\n5. '))
            else:
                lines.append(f'{h["titel"]}: {h["text"]}')
            if h.get('objekt'):
                actions.append({'kind': 'open', 'object': h['objekt'], 'title': h['objekt'].get('title') or h['titel']})
        return self._out('\n\n'.join(lines), actions[:3], hits[0]['art'])

    def close(self):
        with self._lock:
            try: self._db.close()
            except Exception: pass

    def beschreibung(self, shell_id):
        return beschreibung(shell_id, self.shells)

    @staticmethod
    def _out(reply, actions, art):
        return {'reply': reply, 'ui_actions': [a for a in actions if a], 'art': art, 'quelle': 'arbeitsplatz-wissen ' + VERSION}
