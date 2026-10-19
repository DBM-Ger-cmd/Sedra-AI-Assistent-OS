"""News-Skill (Translator Fisch v0.1, PROMPT_SPEC B) – ehrlich für eine Runtime ohne Netz: der Brief entsteht aus den Quellen, die der
Captain gibt (Text, Datei), nie aus dem Gedächtnis des Modells. Keine erfundenen Namen, Zahlen, Termine; keine künstliche Mindestmenge.
Profil (DATA_MODEL.json → news) und Lesen der Antwort sind rein; der Modellaufruf liegt im Hub."""
from __future__ import annotations

import re

TIEFEN = ('kurz', 'standard', 'deep_dive')
BRIEFS = ('morning', 'wochenrueckblick', 'thema')
MAX_QUELLEN = 12
MAX_QUELLE_TEXT = 12000
MAX_ITEMS = 20

PROFIL_LEER = {'interessen': [], 'ausschluss': [], 'region': 'DE/EU', 'sprache': 'de', 'tiefe': 'standard', 'max_items': 5, 'brief': 'morning'}

SYSTEM = ('Du bist der Nachrichten-Fisch. Du erstellst aus den unten gegebenen Quellen einen persönlichen Brief – nur aus diesen Quellen, '
          'auf Deutsch. Regeln: 1. Nur was in den Quellen steht; keine erfundenen Namen, Zahlen, Preise, Termine, Fähigkeiten. '
          '2. Dubletten zusammenführen. 3. Relevanz anhand des Profils erklären; große Meldungen nicht nur deshalb weglassen, weil sie '
          'nicht perfekt passen. 4. Ausschlussthemen weglassen. 5. Unsicherheit sichtbar machen (Vertrauen: hoch/mittel/niedrig). '
          '6. Keine Mindestmenge erzwingen; sachlich, kein Clickbait. Antworte nur mit Blöcken dieser Form, je Meldung:\n'
          'MELDUNG\nTITEL: <Titel>\nKURZ: <ein bis zwei Sätze>\nWARUM: <warum relevant für dieses Profil>\n'
          'TIEFE: <Deep Dive, drei bis sechs Sätze>\nQUELLE: <Name der Quelle genau wie angegeben>\nTAGS: <a, b, c>\nVERTRAUEN: <hoch|mittel|niedrig>')


def profil_pruefen(p):
    """Das Profil (rein): Listen von Wörtern, Region, Sprache, Tiefe, Anzahl, Briefart – oder ValueError."""
    p = dict(PROFIL_LEER, **{k: v for k, v in (p or {}).items() if k in PROFIL_LEER})
    def woerter(v):
        if isinstance(v, str): v = [x.strip() for x in v.split(',')]
        if not isinstance(v, list): raise ValueError('profil_invalid')
        return [str(x).strip()[:60] for x in v if str(x).strip()][:20]
    p['interessen'], p['ausschluss'] = woerter(p['interessen']), woerter(p['ausschluss'])
    p['region'] = str(p['region'] or 'DE/EU')[:40]; p['sprache'] = str(p['sprache'] or 'de')[:8]
    if p['tiefe'] not in TIEFEN or p['brief'] not in BRIEFS: raise ValueError('profil_invalid')
    try: p['max_items'] = max(1, min(MAX_ITEMS, int(p['max_items'])))
    except (TypeError, ValueError): raise ValueError('profil_invalid')
    return p


def quellen_pruefen(quellen):
    if not isinstance(quellen, list) or not quellen or len(quellen) > MAX_QUELLEN: raise ValueError('quellen_required')
    out = []
    for q in quellen:
        if not isinstance(q, dict): raise ValueError('quellen_required')
        name, text = str(q.get('name') or '').strip()[:120], str(q.get('text') or '').strip()
        if not name or not text or len(text) > MAX_QUELLE_TEXT: raise ValueError('quellen_required')
        out.append({'name': name, 'text': text, 'datum': str(q.get('datum') or '')[:20]})
    return out


def nachricht(profil, quellen, heute):
    kopf = (f"Heute: {heute}. Region: {profil['region']}. Sprache: {profil['sprache']}. Tiefe: {profil['tiefe']}. "
            f"Höchstens {profil['max_items']} Meldungen. Briefart: {profil['brief']}.\n"
            f"Interessen: {', '.join(profil['interessen']) or '–'}. Ausschluss: {', '.join(profil['ausschluss']) or '–'}.\n\nQUELLEN:\n")
    return kopf + '\n\n'.join(f"=== Quelle: {q['name']}" + (f" ({q['datum']})" if q['datum'] else '') + f"\n{q['text']}" for q in quellen)


def lesen(antwort, quellen):
    """Die Blöcke des Modells in Meldungen (rein). Eine Meldung ohne bekannte Quelle wird als unsicher markiert, nicht erfunden."""
    bekannte = {q['name'] for q in quellen}
    items = []
    for block in re.split(r'^\s*MELDUNG\s*$', str(antwort or ''), flags=re.M)[1:]:
        f = {}
        for key in ('TITEL', 'KURZ', 'WARUM', 'TIEFE', 'QUELLE', 'TAGS', 'VERTRAUEN'):
            m = re.search(rf'^{key}:\s*(.*?)(?=^\s*(?:TITEL|KURZ|WARUM|TIEFE|QUELLE|TAGS|VERTRAUEN):|\Z)', block, re.S | re.M)
            f[key] = m.group(1).strip() if m else ''
        if not f['TITEL']: continue
        quelle_ok = f['QUELLE'] in bekannte
        vertrauen = f['VERTRAUEN'].lower() if f['VERTRAUEN'].lower() in ('hoch', 'mittel', 'niedrig') else 'niedrig'
        items.append({'titel': f['TITEL'][:160], 'kurz': f['KURZ'], 'warum': f['WARUM'], 'tiefe': f['TIEFE'], 'quelle': f['QUELLE'],
                      'quelle_bekannt': quelle_ok, 'tags': [t.strip() for t in f['TAGS'].split(',') if t.strip()][:8],
                      'vertrauen': vertrauen if quelle_ok else 'niedrig'})
    return items[:MAX_ITEMS]
