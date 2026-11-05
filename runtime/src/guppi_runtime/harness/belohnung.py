"""Belohnungs- und Lernsystem der Harness (Captain 05.11.2026: „danke“, „das hast du gut gemacht“ und ähnliche Wörter zeigen, welche Antworten gut waren, und gehören in die Wissensdatenbank).

Gegenstück: eine **Korrektur** („falsch“, „das stimmt nicht“, „so nicht“ …) direkt nach einer Antwort wird als korrigierte Antwort gemerkt (⚑); die Worte des Captains sind die Lehre.
Lob und Korrektur sind die Fakten für den **Rückblick** (Vorlage `rueckblick`, nach dem Hermes-Muster: vier Fragen, Maßnahmen nur nach Zustimmung, gelernte Regeln in `docs/AAR/LESSONS.md`); die
Regeln stehen danach im Systemprompt (`lessons`). Ablauf: schickt der Captain eine kurze Nachricht mit einem Lobwort direkt nach einer Antwort von Sedra, merkt sich die Harness diese Antwort als **gute Antwort**:
  * ein Eintrag `belohnung` in der Sitzung (die Oberfläche zeigt ein ★ an der Antwort; die Eintragsart zählt nie in den Verlauf, der ans Modell geht),
  * ein Abschnitt in der Tagesdatei `<Projekt>/runtime_data/harness/belohnungen/JJJJ-MM-TT.md` (Markdown, wie das Betriebslog: der Ordner kann als Quelle in die Wissensdatenbank),
  * eine Zeile in `_index.jsonl` im selben Ordner (für die Übersicht), und ein Audit-Ereignis `HARNESS_BELOHNUNG`.
Bei einer Antwort mit Werkzeugen (Dateien geändert, Befehle, Tests) hält der Eintrag fest, **was** getan wurde – so wird eine gelobte Lösung beim Programmieren nachschlagbar. „Besonders gut“
(Stufe 2) sind die Wörter der Liste `besonders` („perfekt“, „genau so“ …). Die Wörter stehen in `config/belohnung.yaml`; eigene in `local_config/belohnung.yaml`. Gelobt wird je Antwort höchstens einmal; „nicht gut gemacht“ und Aufträge mit einem „danke“
mittendrin (mehr als `max_zeichen`) zählen nicht. Gespeichert werden nur kurze Auszüge der Frage und der Antwort, lokal im Projekt."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import yaml

ORDNER = ('runtime_data', 'harness', 'belohnungen')
INDEX = '_index.jsonl'
QUELLE_PFAD = '/'.join(ORDNER)                          # so steht der Ordner in der Quelle der Wissensdatenbank (Wurzel „projekt“)
STANDARD = Path(__file__).resolve().parents[3] / 'config' / 'belohnung.yaml'
FRAGE_MAX, ANTWORT_MAX = 240, 480
KEIN_LOB_ENDE = ('fehler', 'abgebrochen', 'wartet')     # eine Antwort, die nicht zu Ende kam, wird nicht gelobt


def _lesen(pfad):
    try:
        d = yaml.safe_load(Path(pfad).read_text(encoding='utf-8')) or {}
        return d.get('belohnung') or {}
    except (OSError, yaml.YAMLError):
        return {}


def einstellungen(projekt_root=None, standard=STANDARD):
    """Die Wörter und Grenzen: die Vorgabe des Pakets, darüber die Datei des Captains (`lob` ersetzt, `lob_zusaetzlich` ergänzt)."""
    e = _lesen(standard)
    lob = [str(w).strip().lower() for w in (e.get('lob') or []) if str(w).strip()]
    verneinung = [str(w).strip().lower() for w in (e.get('verneinung') or []) if str(w).strip()]
    maximum = e.get('max_zeichen') if type(e.get('max_zeichen')) is int and e.get('max_zeichen') > 0 else 300
    if projekt_root is not None:
        eigen = _lesen(Path(projekt_root) / 'local_config' / 'belohnung.yaml')
        if isinstance(eigen.get('lob'), list):
            lob = [str(w).strip().lower() for w in eigen['lob'] if str(w).strip()]
        lob += [str(w).strip().lower() for w in (eigen.get('lob_zusaetzlich') or []) if str(w).strip()]
    korrektur = [str(w).strip().lower() for w in (e.get('korrektur') or []) if str(w).strip()]
    if projekt_root is not None:
        korrektur += [str(w).strip().lower() for w in (_lesen(Path(projekt_root) / 'local_config' / 'belohnung.yaml').get('korrektur_zusaetzlich') or []) if str(w).strip()]
    vs = e.get('vorschlaege') if isinstance(e.get('vorschlaege'), dict) else {}
    if projekt_root is not None:
        eig = _lesen(Path(projekt_root) / 'local_config' / 'belohnung.yaml').get('vorschlaege')
        vs = dict(vs, **eig) if isinstance(eig, dict) else vs
    vorschlaege = {'an': vs.get('an') is not False, 'min_zeichen': vs.get('min_zeichen') if type(vs.get('min_zeichen')) is int and vs.get('min_zeichen') > 0 else 3,
                   'max': min(vs.get('max'), 10) if type(vs.get('max')) is int and vs.get('max') > 0 else 5}
    besonders = [str(w).strip().lower() for w in (e.get('besonders') or []) if str(w).strip()]
    if projekt_root is not None:
        besonders += [str(w).strip().lower() for w in (_lesen(Path(projekt_root) / 'local_config' / 'belohnung.yaml').get('besonders_zusaetzlich') or []) if str(w).strip()]
    lob = sorted(set(lob) | set(besonders), key=lambda w: (-len(w), w))                      # ein besonders-Wort ist immer auch ein Lobwort
    return {'lob': lob, 'besonders': sorted(set(besonders)), 'korrektur': sorted(set(korrektur), key=lambda w: (-len(w), w)), 'verneinung': verneinung, 'max_zeichen': maximum, 'vorschlaege': vorschlaege}


def _woerter(text):
    return re.findall(r"[0-9a-zäöüß]+", str(text).lower())


def _treffer(text, woerter, einst):
    """(Lobwort, Stufe) – Stufe 2 bei einem „besonders“-Wort, sonst 1; None, wenn die Nachricht kein Lob ist. Ganze Wörter, höchstens `max_zeichen` lang, nicht verneint
    („nicht gut gemacht“, „kein danke“); tragen mehrere Wörter, gewinnt das besonders gute, sonst das längste."""
    if not isinstance(text, str) or not text.strip() or len(text) > einst['max_zeichen']:
        return None
    w = _woerter(text)
    treffer = []
    for wort in woerter:                                        # längere Gruppen zuerst: „vielen dank“ vor „dank“
        g = _woerter(wort)
        if not g:
            continue
        for i in range(len(w) - len(g) + 1):
            if w[i:i + len(g)] == g and not any(v in einst['verneinung'] for v in w[max(0, i - 3):i]):
                treffer.append((wort, 2 if wort in einst.get('besonders', []) else 1))
                break
    if not treffer:
        return None
    return sorted(treffer, key=lambda t: (-t[1], -len(t[0])))[0]


def erkennen(text, einst):
    """(Lobwort, Stufe) – Stufe 2 bei einem „besonders“-Wort, sonst 1; None, wenn die Nachricht kein Lob ist (siehe `_treffer`)."""
    return _treffer(text, einst['lob'], einst)


def korrektur(text, einst):
    """Das Korrekturwort („falsch“, „das stimmt nicht“ …) oder None; gleiche Regeln wie beim Lob (ganze Wörter, kurze Nachricht, nicht verneint: „nicht falsch“ ist keine Korrektur)."""
    t = _treffer(text, einst.get('korrektur', []), einst)
    return t[0] if t else None


def urteil(text, einst):
    """('korrektur', Wort, 0) oder ('lob', Wort, Stufe) oder None. Eine Korrektur geht vor: „danke, aber das ist falsch“ ist keine Belohnung."""
    k = korrektur(text, einst)
    if k:
        return 'korrektur', k, 0
    l = erkennen(text, einst)
    return ('lob', l[0], l[1]) if l else None


def gelobte_antwort(eintraege, streng=True):
    """Die Antwort, die gleich vor der neuen Nachricht stand: der letzte sichtbare Eintrag muss eine Antwort von Sedra sein, die noch kein Urteil trägt. Für ein Lob (`streng`) muss sie zu Ende
    gekommen sein; eine Korrektur darf auch eine abgebrochene oder fehlerhafte Antwort treffen – gerade aus ihr lernt man."""
    sichtbar = [e for e in eintraege if e.get('typ') in ('captain', 'modell') and (e.get('typ') == 'captain' or (e.get('text') or '').strip())]
    if not sichtbar or sichtbar[-1].get('typ') != 'modell':
        return None, None
    antwort = sichtbar[-1]
    if (streng and antwort.get('ende') in KEIN_LOB_ENDE) or not antwort.get('antwort_id'):
        return None, None
    if any(e.get('typ') == 'belohnung' and e.get('antwort_id') == antwort['antwort_id'] for e in eintraege):
        return None, None
    frage = next((e for e in reversed(sichtbar[:-1]) if e.get('typ') == 'captain'), None)
    return antwort, frage


CODE_WERKZEUGE = ('datei_aendern', 'datei_schreiben')


def loesung(eintraege, antwort_id):
    """Was die gelobte Antwort getan hat: geänderte Dateien, ausgeführte Befehle und Läufe, Werkzeuge mit Anzahl (nur, was gelang). `code` ist wahr, wenn Dateien geändert wurden."""
    dateien, befehle, zaehler = [], [], {}
    for e in eintraege:
        if e.get('typ') != 'werkzeug' or e.get('antwort_id') != antwort_id or e.get('status') != 'ok':
            continue
        name, args = str(e.get('name') or ''), e.get('args') if isinstance(e.get('args'), dict) else {}
        zaehler[name] = zaehler.get(name, 0) + 1
        if name in CODE_WERKZEUGE and args.get('pfad') and str(args['pfad']) not in dateien:
            dateien.append(str(args['pfad']))
        elif name == 'befehl' and args.get('befehl'):
            befehle.append(_kurz(args['befehl'], 120))
        elif name == 'lauf_starten' and args.get('lauf'):
            befehle.append('Lauf ' + _kurz(args['lauf'], 60))
    return {'dateien': dateien[:12], 'befehle': befehle[:8], 'werkzeuge': zaehler, 'code': bool(dateien)}


def _kurz(text, n):
    t = ' '.join(str(text or '').split())
    return t if len(t) <= n else t[:n - 1] + '…'


def ordner(projekt_root):
    return Path(projekt_root).joinpath(*ORDNER)


def vermerken(projekt_root, ausloeser, antwort, frage, *, sitzung_id, titel='', vorlage=None, modell=None, quelle='wort', zeit=None, stufe=1, tat=None, art_urteil='lob', korrektur_text=None):
    """Die gute Antwort festhalten (Tagesdatei und Index); gibt den Datensatz zurück. Dieselbe Antwort wird nie zweimal eingetragen (der Aufrufer prüft es über den Sitzungseintrag)."""
    zeit = zeit or time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
    satz = {'zeit': zeit, 'ausloeser': ausloeser, 'quelle': quelle, 'sitzung_id': sitzung_id, 'titel': _kurz(titel, 80), 'vorlage': vorlage, 'modell': modell,
            'antwort_id': antwort.get('antwort_id'), 'frage': _kurz((frage or {}).get('text'), FRAGE_MAX), 'antwort': _kurz(antwort.get('text'), ANTWORT_MAX),
            'stufe': 2 if stufe == 2 else 1, 'art': 'code' if (tat or {}).get('code') else 'antwort', 'tat': tat or {}, 'urteil': 'korrektur' if art_urteil == 'korrektur' else 'lob'}
    if satz['urteil'] == 'korrektur':
        satz['stufe'] = 0
        satz['korrektur'] = _kurz(korrektur_text, FRAGE_MAX)
    ziel = ordner(projekt_root)
    ziel.mkdir(parents=True, exist_ok=True)
    tag = zeit[:10]
    datei = ziel / (tag + '.md')
    kopf = '' if datei.exists() else '# Gute und korrigierte Antworten %s\n\nAntworten von Sedra, die der Captain gelobt oder korrigiert hat (Zeiten in UTC). Stichwort: Lob, gute Antwort, danke, Korrektur, falsch, Lehre.\n\n' % tag
    tat = satz['tat'] or {}
    titel_art = 'Korrigierte Antwort' if satz['urteil'] == 'korrektur' else ('Besonders gute Antwort' if satz['stufe'] == 2 else 'Gute Antwort')
    block = '## %s %s „%s“ – %s\n\n- Sitzung: %s%s\n- Vorlage: %s · Modell: %s\n- Frage: %s\n- Antwort (Auszug): %s\n' % (
        zeit[11:16], titel_art, ausloeser, satz['titel'] or satz['sitzung_id'], satz['sitzung_id'],
        ' (%s)' % satz['titel'] if satz['titel'] else '', vorlage or 'ohne Vorlage', modell or '?', satz['frage'] or '–', satz['antwort'] or '–')
    if satz.get('korrektur'):
        block += '- Korrektur des Captains: %s\n' % satz['korrektur']
    if tat.get('dateien'):
        block += '- %s in Dateien: %s\n' % ('Betroffen' if satz['urteil'] == 'korrektur' else 'Gelöst', ', '.join(tat['dateien']))
    if tat.get('befehle'):
        block += '- Befehle und Läufe: %s\n' % '; '.join(tat['befehle'])
    if tat.get('werkzeuge'):
        block += '- Werkzeuge: %s\n' % ', '.join('%s×%d' % (k, v) for k, v in sorted(tat['werkzeuge'].items()))
    block += '\n'
    with datei.open('a', encoding='utf-8', newline='\n') as f:
        f.write(kopf + block)
    with (ziel / INDEX).open('a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(satz, ensure_ascii=False) + '\n')
    return satz


def _saetze(projekt_root):
    saetze = []
    try:
        for z in (ordner(projekt_root) / INDEX).read_text(encoding='utf-8').splitlines():
            try:
                x = json.loads(z)
            except ValueError:
                continue
            if isinstance(x, dict):
                saetze.append(x)
    except OSError:
        pass
    return saetze


def uebersicht(projekt_root, limit=10):
    """Für die Info-Seite: wie viele gute Antworten und Korrekturen, je Vorlage und je Modell (nur Lob), die letzten."""
    alle = _saetze(projekt_root)
    saetze = [x for x in alle if x.get('urteil', 'lob') == 'lob']
    korrekturen = [x for x in alle if x.get('urteil') == 'korrektur']
    zaehle = lambda feld, liste: sorted(({'name': k or '–', 'anzahl': sum(1 for x in liste if (x.get(feld) or None) == (k or None))} for k in {x.get(feld) or '' for x in liste}),
                                        key=lambda x: (-x['anzahl'], x['name']))
    n = max(1, int(limit))
    return {'anzahl': len(saetze), 'besonders': sum(1 for x in saetze if x.get('stufe') == 2), 'code': sum(1 for x in saetze if x.get('art') == 'code'), 'korrekturen': len(korrekturen),
            'je_vorlage': zaehle('vorlage', saetze)[:8], 'je_modell': zaehle('modell', saetze)[:8], 'letzte': list(reversed(saetze[-n:])), 'letzte_korrekturen': list(reversed(korrekturen[-n:])),
            'ordner': QUELLE_PFAD}


def lesen(projekt_root, tage=7, art='alle', suche='', limit=20):
    """Für das Chat-Werkzeug `belohnungen_lesen` und den Rückblick: die Einträge der letzten `tage` Tage (art: alle, lob, korrektur), mit Suchwörtern in Frage, Antwort, Korrektur, Dateien und
    Titel (jedes Wort muss vorkommen), die neuesten zuerst. Nur lesen."""
    tage = max(1, min(int(tage or 7), 365))
    seit = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(time.time() - tage * 86400))
    worte = [w for w in _woerter(suche)]
    out = []
    for x in reversed(_saetze(projekt_root)):
        if str(x.get('zeit') or '') < seit:
            break
        if art in ('lob', 'korrektur') and x.get('urteil', 'lob') != art:
            continue
        heu = ' '.join(_woerter(' '.join([str(x.get(k) or '') for k in ('frage', 'antwort', 'korrektur', 'titel', 'vorlage')] + list((x.get('tat') or {}).get('dateien') or []))))
        if worte and not all(w in heu for w in worte):
            continue
        out.append(x)
        if len(out) >= max(1, min(int(limit or 20), 100)):
            break
    return out


def zeile(x):
    """Ein Eintrag als Text für das Modell (Daten, keine Anweisung)."""
    zeichen = '⚑ korrigiert' if x.get('urteil') == 'korrektur' else ('★★ besonders gut' if x.get('stufe') == 2 else '★ gut')
    tat = x.get('tat') or {}
    teile = ['[%s] %s · %s · %s · %s' % (str(x.get('zeit') or '')[:16].replace('T', ' '), zeichen, x.get('vorlage') or 'ohne Vorlage', x.get('modell') or '?', x.get('titel') or x.get('sitzung_id')),
             '  Frage: ' + (x.get('frage') or '–'), '  Antwort: ' + (x.get('antwort') or '–')]
    if x.get('korrektur'):
        teile.append('  Korrektur des Captains: ' + x['korrektur'])
    if tat.get('dateien'):
        teile.append('  Dateien: ' + ', '.join(tat['dateien']))
    if tat.get('befehle'):
        teile.append('  Befehle: ' + '; '.join(tat['befehle']))
    return '\n'.join(teile)


LESSONS_PFAD = ('docs', 'AAR', 'LESSONS.md')
LESSONS_ZEILEN, LESSONS_ZEICHEN = 25, 2000


def lessons(wurzel):
    """Die gelernten Regeln des Projekts (`docs/AAR/LESSONS.md`, vom Captain bestätigt, nach dem Hermes-Muster): die letzten höchstens 25 Zeilen ohne Überschriften und Leerzeilen, höchstens
    2 000 Zeichen; leer, wenn es die Datei nicht gibt. Sie stehen im Systemprompt, damit Sedra nicht dieselben Fehler wiederholt."""
    try:
        zeilen = Path(wurzel).joinpath(*LESSONS_PFAD).read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeDecodeError, TypeError):
        return ''
    nutz = [z.strip() for z in zeilen if z.strip() and not z.lstrip().startswith('#')][-LESSONS_ZEILEN:]
    text = '\n'.join(nutz)
    return text if len(text) <= LESSONS_ZEICHEN else text[-LESSONS_ZEICHEN:]


# ---- Vorhersagen beim Tippen (Captain 05.11.2026: aus Lob und Korrektur lassen sich Vorschläge für die Eingabe ableiten)
FUELLWOERTER = {'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einen', 'und', 'oder', 'mit', 'für', 'fuer', 'bitte', 'mal', 'mach', 'ist', 'sind', 'wie', 'was', 'wo', 'wir', 'ich', 'du',
                'zu', 'in', 'im', 'auf', 'von', 'bei', 'nach', 'noch', 'auch', 'jetzt', 'dann', 'nicht', 'kann', 'kannst', 'soll', 'sollst', 'mir', 'uns'}


def _inhalt(text):
    """Die bedeutungstragenden Wörter einer Eingabe (klein, ohne Füllwörter, mindestens drei Buchstaben)."""
    return [w for w in _woerter(text) if len(w) >= 3 and w not in FUELLWOERTER]


def _aehnlich(tipp, frage):
    """Wie gut passt die gespeicherte Frage zu dem, was gerade getippt wird? 0 = gar nicht. Anfang der Frage zählt am meisten, dann gemeinsame Wörter im Verhältnis zu den getippten;
    das letzte, noch unfertige Wort darf ein Wortanfang sein."""
    t, f = ' '.join(_woerter(tipp)), ' '.join(_woerter(frage))
    if not t or not f or t == f:
        return 0.0
    punkte = 3.0 if f.startswith(t) else 0.0
    tw, fw = _inhalt(tipp), _woerter(frage)
    if tw:
        treffer = 0
        for i, w in enumerate(tw):
            letztes = i == len(tw) - 1 and not str(tipp).endswith((' ', '.', '?', '!'))       # das letzte Wort ist noch unfertig, wenn nichts dahinter steht
            if w in fw or (letztes and any(x.startswith(w) for x in fw)):
                treffer += 1
        anteil = treffer / len(tw)
        if anteil >= 0.67:
            punkte += 2.0 * anteil
    return punkte


def vorschlaege(projekt_root, text, vorlage=None, einst=None):
    """Vorschläge für die Eingabe: {'an', 'vorschlaege': [{frage, stufe, dateien, vorlage}], 'warnungen': [{frage, korrektur}]}. Nur gelobte Fragen (die Antwort war gut) mit mindestens so vielen
    Zeichen wie getippt, keine doppelten; ähnlich korrigierte Fragen werden zur Warnung mit den Worten des Captains. Aus, wenn `vorschlaege.an` falsch ist oder zu wenig getippt wurde."""
    einst = einst or einstellungen(projekt_root)
    v = einst['vorschlaege']
    text = str(text or '')
    if not v['an']:
        return {'an': False, 'vorschlaege': [], 'warnungen': []}
    if len(text.strip()) < v['min_zeichen'] or text.startswith('/') or '\n' in text:
        return {'an': True, 'vorschlaege': [], 'warnungen': []}
    gut, gesehen, warn = [], set(), []
    alle = _saetze(projekt_root)
    for rang, x in enumerate(reversed(alle)):                                       # die neuesten zuerst
        f = str(x.get('frage') or '').strip()
        if not f:
            continue
        p = _aehnlich(text, f)
        if p <= 0:
            continue
        if x.get('urteil') == 'korrektur':
            if p >= 2.0 and len(_inhalt(text)) >= 2 and len(warn) < 2 and x.get('korrektur'):
                warn.append({'frage': f, 'korrektur': str(x['korrektur'])})
            continue
        norm = ' '.join(_woerter(f))
        if norm in gesehen or len(f) <= len(text.strip()):
            continue
        gesehen.add(norm)
        p += 0.5 if x.get('stufe') == 2 else 0.0
        p += 0.5 if vorlage and x.get('vorlage') == vorlage else 0.0
        p -= rang * 0.001                                                           # bei gleicher Güte die neuere
        gut.append((p, {'frage': f, 'stufe': x.get('stufe') or 1, 'dateien': list((x.get('tat') or {}).get('dateien') or [])[:3], 'vorlage': x.get('vorlage')}))
    gut.sort(key=lambda t: -t[0])
    return {'an': True, 'vorschlaege': [g for _p, g in gut[:v['max']]], 'warnungen': warn}
