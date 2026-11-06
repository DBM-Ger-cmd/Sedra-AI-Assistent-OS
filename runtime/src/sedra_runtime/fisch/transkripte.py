"""Transkripte (Fisch, 19.10.2026) – nach LocalScribe (Transcript = Wörter/Cues mit Zeiten; Exporter TXT/SRT/VTT/JSON; Suche nach
ganzen Wörtern) und VoiceBrief (Record = Status + Versionen; Export ändert den Record nie, ADR-009; Identity-Mapping getrennt vom
Transkript, ADR-011; Golden Record erst nach Prüfung, ADR-014; Platzhalter heißen so, ADR-008).

Ein Transkript liegt als JSON unter `<Projekt>/fisch/transkripte/<id>.json`: Titel, Sprache, Quelle (Dateiname), Cues
[{start, end, text}], Versionen (jede Fassung des Textes mit Herkunft: import · pseudonymisiert), Status (entwurf · geprüft ·
freigegeben). Das Mapping einer Pseudonymisierung liegt daneben in `<id>.mapping.json` – nie in einem Export.
Sprache → Text macht der Kern (sprache/stt.py: whisperx oder whisper auf dem Rechner); `transkribieren()` hier ist nur noch die
Auskunft ohne Provider, die der Kern ersetzt, sobald einer da ist – nichts wird erfunden."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

STATUS = ('entwurf', 'geprueft', 'freigegeben')
FORMATE = ('txt', 'srt', 'vtt', 'json', 'md')
MAX_TEXT = 400_000
MAX_TITEL = 120
SPRACHEN = ('de', 'en', 'fr', 'es', 'it')

_TS = re.compile(r'(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})')
_TS_SHORT = re.compile(r'(\d{1,2}):(\d{2})[.,](\d{1,3})')


# ---------------------------------------------------------------- Zeiten und Cues (rein)
def zeit_lesen(s):
    m = _TS.search(s)
    if m:
        h, mi, se, ms = m.groups()
        return int(h) * 3600 + int(mi) * 60 + int(se) + int(ms.ljust(3, '0')) / 1000
    m = _TS_SHORT.search(s)
    if m:
        mi, se, ms = m.groups()
        return int(mi) * 60 + int(se) + int(ms.ljust(3, '0')) / 1000
    raise ValueError('zeit_unlesbar')


def zeit_schreiben(sek, stil):
    sek = max(0.0, float(sek))
    h, rest = divmod(int(sek), 3600)
    mi, se = divmod(rest, 60)
    ms = int(round((sek - int(sek)) * 1000))
    if ms == 1000: ms, se = 0, se + 1
    return f'{h:02d}:{mi:02d}:{se:02d}{"," if stil == "srt" else "."}{ms:03d}'


def cues_aus_text(text, sekunden_je_cue=5.0, woerter_je_cue=12):
    """Reiner Text ohne Zeiten: Sätze zu Cues, mit gleichmäßig geschätzten Zeiten – als Schätzung gekennzeichnet (geschaetzt=True)."""
    woerter = text.split()
    cues, i, t = [], 0, 0.0
    while i < len(woerter):
        teil = woerter[i:i + woerter_je_cue]
        cues.append({'start': round(t, 3), 'end': round(t + sekunden_je_cue, 3), 'text': ' '.join(teil)})
        i += woerter_je_cue; t += sekunden_je_cue
    return cues


def cues_aus_srt_vtt(text):
    """SRT oder WebVTT: Blöcke mit „Start --> Ende“ und Zeilen darunter. Nummern und WEBVTT-Kopf werden übergangen."""
    cues = []
    for block in re.split(r'\n\s*\n', text.replace('\r\n', '\n').strip()):
        zeilen = [z for z in block.split('\n') if z.strip()]
        zeiten = next((z for z in zeilen if '-->' in z), None)
        if not zeiten: continue
        a, b = zeiten.split('-->', 1)
        try: start, end = zeit_lesen(a), zeit_lesen(b)
        except ValueError: continue
        inhalt = [z for z in zeilen[zeilen.index(zeiten) + 1:]]
        if inhalt: cues.append({'start': start, 'end': max(end, start), 'text': ' '.join(x.strip() for x in inhalt)})
    return cues


def erkennen(text):
    t = text.lstrip()
    if t.upper().startswith('WEBVTT'): return 'vtt'
    if re.search(r'^\s*\d+\s*\n\s*\d{1,2}:\d{2}:\d{2}[,.]\d{3}\s*-->', t, re.M): return 'srt'
    return 'txt'


def importieren(text, titel, sprache='de', quelle=''):
    """Aus TXT/SRT/VTT ein Transkript (rein, ohne Speicher). Sprache ist eine Angabe des Captains (LocalScribe: der Guard vor dem Modell)."""
    text = str(text or '')
    if not text.strip() or len(text) > MAX_TEXT: raise ValueError('text_required')
    titel = str(titel or '').strip()[:MAX_TITEL]
    if not titel: raise ValueError('titel_required')
    if sprache not in SPRACHEN: raise ValueError('sprache_unbekannt')
    art = erkennen(text)
    cues = cues_aus_srt_vtt(text) if art in ('srt', 'vtt') else cues_aus_text(text)
    if not cues: raise ValueError('keine_cues')
    return {'titel': titel, 'sprache': sprache, 'quelle': str(quelle or '')[:200], 'format': art, 'geschaetzt': art == 'txt', 'cues': cues}


def volltext(cues):
    return ' '.join(c['text'] for c in cues)


# ---------------------------------------------------------------- Export (LocalScribe-Form)
def export_txt(cues): return volltext(cues)


def export_srt(cues):
    bloecke = [f"{i + 1}\n{zeit_schreiben(c['start'], 'srt')} --> {zeit_schreiben(c['end'], 'srt')}\n{c['text']}" for i, c in enumerate(cues)]
    return ('\n\n'.join(bloecke) + '\n') if bloecke else ''


def export_vtt(cues):
    bloecke = [f"{zeit_schreiben(c['start'], 'vtt')} --> {zeit_schreiben(c['end'], 'vtt')}\n{c['text']}" for c in cues]
    return ('WEBVTT\n\n' + '\n\n'.join(bloecke) + '\n') if bloecke else 'WEBVTT\n'


def export_json(t, cues):
    doc = {'titel': t['titel'], 'sprache': t['sprache'], 'quelle': t.get('quelle', ''), 'status': t['status'], 'version': t['aktuell'],
           'cues': cues}
    return json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + '\n'


def _mmss(sek):
    return f"{int(sek // 60):02d}:{int(sek % 60):02d}"


def export_md(t, cues, erk=None):
    """Das Protokoll ohne KI (Markdown): Kopf, Erkenntnisse nur wenn gelesen, dann die Abschrift mit Zeiten. Ohne Modell entsteht nichts dazu."""
    kopf = [f"# {t['titel']}", '', f"- Sprache: {t['sprache']}", f"- Quelle: {t.get('quelle') or '–'}", f"- Fassung: {fassung(t)['version']} ({t['status']})", '']
    if erk:
        kopf += [f"## Erkenntnisse (gelesen aus Fassung {erk.get('version')}, Modell {erk.get('model') or '–'})", '']
        kopf += ['**Zusammenfassung:** ' + (erk.get('zusammenfassung') or '–'), '']
        for titel, liste in (('Entscheidungen', erk.get('entscheidungen') or []), ('Offene Fragen', erk.get('offen') or []), ('Aufgaben', erk.get('aufgaben') or [])):
            kopf += [f"**{titel}:**"] + [f"- {x}" for x in liste] + ['- keine' if not liste else '', '']
    else:
        kopf += ['## Erkenntnisse', '', 'Noch keine – dieses Protokoll ist ohne KI erstellt.', '']
    kopf += ['## Abschrift', '']
    kopf += [f"[{_mmss(c['start'])}–{_mmss(c['end'])}] {c['text']}" for c in cues]
    return '\n'.join(kopf) + '\n'


def exportieren(t, fmt):
    """Der Export einer Fassung – nie ein Mapping, nie eine Änderung am Record (ADR-009). Freigegeben: die freigegebene Fassung."""
    if fmt not in FORMATE: raise ValueError('format_unbekannt')
    cues = fassung(t)['cues']
    if fmt == 'md': return export_md(t, cues, t.get('erkenntnisse') if t.get('erkenntnisse') and t['erkenntnisse'].get('version') == fassung(t)['version'] else None)
    return {'txt': export_txt, 'srt': export_srt, 'vtt': export_vtt}[fmt](cues) if fmt != 'json' else export_json(t, cues)


# ---------------------------------------------------------------- Suche (LocalScribe: ganze Wörter, Reihenfolge, Groß/Klein egal)
def _wort(w): return re.sub(r'^[\W_]+|[\W_]+$', '', w).lower()


def suchen(cues, frage):
    tokens = [_wort(x) for x in str(frage or '').split() if _wort(x)]
    if not tokens: return []
    treffer = []
    for ci, c in enumerate(cues):
        woerter = [_wort(w) for w in c['text'].split()]
        for i in range(0, max(0, len(woerter) - len(tokens) + 1)):
            if woerter[i:i + len(tokens)] == tokens:
                treffer.append({'cue': ci, 'start': c['start'], 'end': c['end'], 'wort': i, 'anzahl': len(tokens), 'text': c['text']})
    return treffer


# ---------------------------------------------------------------- der Record
def fassung(t, version=None):
    v = t['aktuell'] if version is None else version
    for f in t['versionen']:
        if f['version'] == v: return f
    raise ValueError('version_unbekannt')


def _hash(cues): return hashlib.sha256(json.dumps(cues, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:16]


def neu(imp, now, herkunft='import'):
    """Der Record aus einem Import – `herkunft` nennt die erste Fassung: import · manuell · stt:whisperx (Kern, sprache/)."""
    tid = 'T-' + hashlib.sha256(f"{imp['titel']}:{now}".encode('utf-8')).hexdigest()[:8].upper()
    return {'id': tid, 'titel': imp['titel'], 'sprache': imp['sprache'], 'quelle': imp['quelle'], 'format': imp['format'],
            'geschaetzt': imp['geschaetzt'], 'created_at': now, 'status': 'entwurf', 'aktuell': 1, 'freigegeben_version': None,
            'versionen': [{'version': 1, 'herkunft': str(herkunft or 'import')[:40], 'at': now, 'hash': _hash(imp['cues']), 'cues': imp['cues'], 'mapping': False}]}


def transkribieren(_pfad=None):
    """Die Auskunft ohne Provider (VoiceBrief ADR-008: Platzhalter heißen so). Der Kern (sprache/stt.py) ersetzt sie, sobald whisperx
    oder whisper auf dem Rechner ist – `hub.sprache.provider()`; hier bleibt der Platzhalter für Tests ohne Hub."""
    return {'status': 'platzhalter', 'provider': 'keiner', 'install': 'pip install whisperx',
            'note': 'Kein Sprach-zu-Text-Provider auf diesem Rechner. Ein fertiges Transkript (TXT, SRT, VTT) importieren – '
                    'oder whisperx bzw. whisper installieren; dann transkribiert der Rekorder lokal.'}


class Store:
    def __init__(self, project_root: Path):
        self.dir = Path(project_root) / 'fisch' / 'transkripte'

    def _pfad(self, tid):
        if not re.match(r'^T-[0-9A-F]{8}$', str(tid)): raise ValueError('unknown_transcript')
        return self.dir / f'{tid}.json'

    def liste(self):
        out = []
        for p in sorted(self.dir.glob('T-*.json')) if self.dir.is_dir() else []:
            if not re.match(r'^T-[0-9A-F]{8}\.json$', p.name): continue      # das Mapping (T-….mapping.json) ist kein Transkript
            try: t = json.loads(p.read_text(encoding='utf-8'))
            except (OSError, ValueError): continue
            out.append({'id': t['id'], 'titel': t['titel'], 'sprache': t['sprache'], 'status': t['status'], 'cues': len(fassung(t)['cues']),
                        'versionen': len(t['versionen']), 'aktuell': t['aktuell'], 'geschaetzt': t.get('geschaetzt', False), 'created_at': t['created_at']})
        return sorted(out, key=lambda x: x['created_at'], reverse=True)

    def get(self, tid):
        p = self._pfad(tid)
        if not p.is_file(): raise ValueError('unknown_transcript')
        return json.loads(p.read_text(encoding='utf-8'))

    def schreiben(self, t):
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self._pfad(t['id']).with_suffix('.json.tmp')
        tmp.write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding='utf-8')
        tmp.replace(self._pfad(t['id']))
        return t

    def mapping_schreiben(self, tid, version, mapping):
        """Das Identity-Mapping getrennt vom Transkript (ADR-011) – nur hier, nie im Export."""
        p = self.dir / f'{tid}.mapping.json'
        alt = json.loads(p.read_text(encoding='utf-8')) if p.is_file() else {}
        alt[str(version)] = mapping
        p.write_text(json.dumps(alt, ensure_ascii=False, indent=1), encoding='utf-8')

    def neue_fassung(self, t, cues, herkunft, now, mapping=None):
        """Eine neue Fassung anhängen – additiv, der Record bleibt (VoiceBrief: Versionen, nie Überschreiben)."""
        if t['status'] == 'freigegeben': raise ValueError('record_freigegeben')
        v = max(f['version'] for f in t['versionen']) + 1
        t['versionen'].append({'version': v, 'herkunft': herkunft, 'at': now, 'hash': _hash(cues), 'cues': cues, 'mapping': mapping is not None})
        t['aktuell'] = v; t['status'] = 'entwurf'
        if mapping is not None: self.mapping_schreiben(t['id'], v, mapping)
        return self.schreiben(t)

    def status_setzen(self, t, status, now):
        """entwurf → geprüft → freigegeben; freigegeben friert die aktuelle Fassung ein (Golden Record, ADR-014)."""
        if status not in STATUS: raise ValueError('status_unbekannt')
        if status == 'freigegeben' and t['status'] != 'geprueft': raise ValueError('erst_pruefen')
        t['status'] = status
        if status == 'freigegeben': t['freigegeben_version'] = t['aktuell']
        if status == 'entwurf': t['freigegeben_version'] = None
        t['status_at'] = now
        return self.schreiben(t)
