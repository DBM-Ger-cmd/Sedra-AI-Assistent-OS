"""Belohnungssystem der Harness (Captain 05.11.2026: „danke“, „das hast du gut gemacht“ und ähnliche Wörter zeigen, welche Antworten gut waren, und gehören in die Wissensdatenbank).

Ablauf: schickt der Captain eine kurze Nachricht mit einem Lobwort direkt nach einer Antwort von Sedra, merkt sich die Harness diese Antwort als **gute Antwort**:
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
    besonders = [str(w).strip().lower() for w in (e.get('besonders') or []) if str(w).strip()]
    if projekt_root is not None:
        besonders += [str(w).strip().lower() for w in (_lesen(Path(projekt_root) / 'local_config' / 'belohnung.yaml').get('besonders_zusaetzlich') or []) if str(w).strip()]
    lob = sorted(set(lob) | set(besonders), key=lambda w: (-len(w), w))                      # ein besonders-Wort ist immer auch ein Lobwort
    return {'lob': lob, 'besonders': sorted(set(besonders)), 'verneinung': verneinung, 'max_zeichen': maximum}


def _woerter(text):
    return re.findall(r"[0-9a-zäöüß]+", str(text).lower())


def erkennen(text, einst):
    """(Lobwort, Stufe) – Stufe 2 bei einem „besonders“-Wort, sonst 1; None, wenn die Nachricht kein Lob ist. Ganze Wörter, höchstens `max_zeichen` lang, nicht verneint
    („nicht gut gemacht“, „kein danke“); tragen mehrere Wörter, gewinnt das besonders gute, sonst das längste."""
    if not isinstance(text, str) or not text.strip() or len(text) > einst['max_zeichen']:
        return None
    w = _woerter(text)
    treffer = []
    for wort in einst['lob']:                                   # längere Gruppen zuerst: „vielen dank“ vor „dank“
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


def gelobte_antwort(eintraege):
    """Die Antwort, die gleich vor der neuen Nachricht stand: der letzte sichtbare Eintrag muss eine zu Ende gekommene Antwort von Sedra sein, die noch kein Lob trägt."""
    sichtbar = [e for e in eintraege if e.get('typ') in ('captain', 'modell') and (e.get('typ') == 'captain' or (e.get('text') or '').strip())]
    if not sichtbar or sichtbar[-1].get('typ') != 'modell':
        return None, None
    antwort = sichtbar[-1]
    if antwort.get('ende') in KEIN_LOB_ENDE or not antwort.get('antwort_id'):
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


def vermerken(projekt_root, ausloeser, antwort, frage, *, sitzung_id, titel='', vorlage=None, modell=None, quelle='wort', zeit=None, stufe=1, tat=None):
    """Die gute Antwort festhalten (Tagesdatei und Index); gibt den Datensatz zurück. Dieselbe Antwort wird nie zweimal eingetragen (der Aufrufer prüft es über den Sitzungseintrag)."""
    zeit = zeit or time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
    satz = {'zeit': zeit, 'ausloeser': ausloeser, 'quelle': quelle, 'sitzung_id': sitzung_id, 'titel': _kurz(titel, 80), 'vorlage': vorlage, 'modell': modell,
            'antwort_id': antwort.get('antwort_id'), 'frage': _kurz((frage or {}).get('text'), FRAGE_MAX), 'antwort': _kurz(antwort.get('text'), ANTWORT_MAX),
            'stufe': 2 if stufe == 2 else 1, 'art': 'code' if (tat or {}).get('code') else 'antwort', 'tat': tat or {}}
    ziel = ordner(projekt_root)
    ziel.mkdir(parents=True, exist_ok=True)
    tag = zeit[:10]
    datei = ziel / (tag + '.md')
    kopf = '' if datei.exists() else '# Gute Antworten %s\n\nAntworten von Sedra, die der Captain gelobt hat (Zeiten in UTC). Stichwort: Lob, gute Antwort, danke.\n\n' % tag
    tat = satz['tat'] or {}
    block = '## %s %s „%s“ – %s\n\n- Sitzung: %s%s\n- Vorlage: %s · Modell: %s\n- Frage: %s\n- Antwort (Auszug): %s\n' % (
        zeit[11:16], 'Besonders gute Antwort' if satz['stufe'] == 2 else 'Gute Antwort', ausloeser, satz['titel'] or satz['sitzung_id'], satz['sitzung_id'],
        ' (%s)' % satz['titel'] if satz['titel'] else '', vorlage or 'ohne Vorlage', modell or '?', satz['frage'] or '–', satz['antwort'] or '–')
    if tat.get('dateien'):
        block += '- Gelöst in Dateien: %s\n' % ', '.join(tat['dateien'])
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


def uebersicht(projekt_root, limit=10):
    """Für die Info-Seite: wie viele gute Antworten, je Vorlage und je Modell, und die letzten."""
    saetze = []
    try:
        for z in (ordner(projekt_root) / INDEX).read_text(encoding='utf-8').splitlines():
            try:
                s = json.loads(z)
            except ValueError:
                continue
            if isinstance(s, dict):
                saetze.append(s)
    except OSError:
        pass
    zaehle = lambda feld: sorted(({'name': k or '–', 'anzahl': sum(1 for s in saetze if (s.get(feld) or None) == (k or None))} for k in {s.get(feld) or '' for s in saetze}),
                                 key=lambda x: (-x['anzahl'], x['name']))
    return {'anzahl': len(saetze), 'besonders': sum(1 for s in saetze if s.get('stufe') == 2), 'code': sum(1 for s in saetze if s.get('art') == 'code'), 'je_vorlage': zaehle('vorlage')[:8], 'je_modell': zaehle('modell')[:8], 'letzte': list(reversed(saetze[-max(1, int(limit)):])), 'ordner': QUELLE_PFAD}
