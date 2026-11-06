"""Aufnahmen (Kern): ein Record je Aufnahme nach VoiceBrief – Status, Datei im Projekt (`<Projekt>/sprache/aufnahmen/<id>.<endung>`
und `<id>.json`), kein Netz. Der Browser nimmt auf (MediaRecorder) und schickt die Stücke nacheinander, jedes unter dem 1-MiB-Limit
eines Requests (uix_server._json_body), base64; der Kern hängt sie an die Datei. Löschen und Transkribieren sind Handlungen am Record."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
from pathlib import Path

from .stt import SPRACHEN

MIME = {'audio/webm': 'webm', 'audio/ogg': 'ogg', 'audio/mp4': 'm4a', 'audio/wav': 'wav', 'audio/mpeg': 'mp3'}
MAX_TITEL = 120
MAX_STUECK = 720_000              # Zeichen base64 je Stück – unter dem 1-MiB-Limit eines Requests
MAX_GROESSE = 200 * 1024 * 1024   # Bytes je Aufnahme
MAX_ABSPIELEN = 24 * 1024 * 1024  # darüber kommt die Datei nicht mehr als base64, nur ihr Pfad
ZEIT_LIMIT = 6 * 3600
STATUS = ('laeuft', 'fertig')
STT_STATUS = ('offen', 'laeuft', 'fertig', 'fehler')
_ID = re.compile(r'^A-[0-9A-F]{8}$')


def neu(titel, mime, sprache, now):
    titel = str(titel or '').strip()[:MAX_TITEL] or ('Aufnahme ' + now[:16].replace('T', ' '))
    mime = str(mime or 'audio/webm').split(';', 1)[0].strip().lower()
    if mime not in MIME: raise ValueError('mime_unbekannt')
    if sprache not in SPRACHEN: raise ValueError('sprache_unbekannt')
    aid = 'A-' + hashlib.sha256(f'{titel}:{now}'.encode('utf-8')).hexdigest()[:8].upper()
    return {'id': aid, 'titel': titel, 'mime': mime, 'endung': MIME[mime], 'sprache': sprache, 'created_at': now, 'status': 'laeuft',
            'dauer': 0.0, 'groesse': 0, 'stuecke': 0, 'transkript_id': None, 'stt': {'status': 'offen', 'provider': '', 'fehler': '', 'at': ''}}


def stueck_lesen(data):
    """Ein Stück aus dem Browser: base64, begrenzt. Leer ist erlaubt (MediaRecorder liefert manchmal 0 Bytes)."""
    s = str(data or '')
    if len(s) > MAX_STUECK: raise ValueError('stueck_zu_gross')
    try:
        return base64.b64decode(s, validate=True)
    except (ValueError, TypeError):
        raise ValueError('stueck_unlesbar')


def kurz(a):
    return {k: a[k] for k in ('id', 'titel', 'sprache', 'mime', 'created_at', 'status', 'dauer', 'groesse', 'transkript_id', 'stt')}


class Store:
    def __init__(self, project_root):
        self.dir = Path(project_root) / 'sprache' / 'aufnahmen'
        self.lock = threading.Lock()

    def _meta(self, aid):
        if not _ID.match(str(aid)): raise ValueError('unknown_recording')
        return self.dir / f'{aid}.json'

    def datei(self, a): return self.dir / f"{a['id']}.{a['endung']}"

    def pfad_im_projekt(self, a): return str(Path('sprache') / 'aufnahmen' / self.datei(a).name)

    def liste(self):
        out = []
        for p in sorted(self.dir.glob('A-*.json')) if self.dir.is_dir() else []:
            if not re.match(r'^A-[0-9A-F]{8}\.json$', p.name): continue
            try: out.append(kurz(json.loads(p.read_text(encoding='utf-8'))))
            except (OSError, ValueError, KeyError): continue
        return sorted(out, key=lambda x: x['created_at'], reverse=True)

    def get(self, aid):
        p = self._meta(aid)
        if not p.is_file(): raise ValueError('unknown_recording')
        return json.loads(p.read_text(encoding='utf-8'))

    def schreiben(self, a):
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self._meta(a['id']).with_suffix('.json.tmp')
        tmp.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding='utf-8')
        tmp.replace(self._meta(a['id']))
        return a

    def beginnen(self, titel, mime, sprache, now):
        a = neu(titel, mime, sprache, now)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.datei(a).write_bytes(b'')
        return self.schreiben(a)

    def anhaengen(self, aid, data):
        roh = stueck_lesen(data)
        with self.lock:
            a = self.get(aid)
            if a['status'] != 'laeuft': raise ValueError('aufnahme_beendet')
            if a['groesse'] + len(roh) > MAX_GROESSE: raise ValueError('aufnahme_zu_gross')
            with open(self.datei(a), 'ab') as f: f.write(roh)
            a['groesse'] += len(roh); a['stuecke'] += 1
            return self.schreiben(a)

    def beenden(self, aid, dauer, now):
        with self.lock:
            a = self.get(aid)
            try: d = float(dauer or 0)
            except (TypeError, ValueError): d = 0.0
            a['dauer'] = round(min(max(d, 0.0), ZEIT_LIMIT), 2); a['status'] = 'fertig'; a['beendet_at'] = now
            if a['groesse'] == 0: raise ValueError('aufnahme_leer')
            return self.schreiben(a)

    def abspielen(self, aid):
        """Die Datei als base64 für <audio> – bis MAX_ABSPIELEN; darüber nur der Pfad im Projekt."""
        a = self.get(aid)
        p = self.datei(a)
        groesse = p.stat().st_size if p.is_file() else 0
        zu_gross = groesse > MAX_ABSPIELEN
        daten = '' if zu_gross or not groesse else base64.b64encode(p.read_bytes()).decode('ascii')
        return dict(a, daten=daten, pfad=self.pfad_im_projekt(a), zu_gross=zu_gross)

    def loeschen(self, aid):
        with self.lock:
            a = self.get(aid)
            if a['stt']['status'] == 'laeuft': raise ValueError('transkription_laeuft')
            for p in (self.datei(a), self._meta(aid)):
                if p.is_file(): p.unlink()
        return {'id': aid, 'geloescht': True}

    def stt_setzen(self, aid, status, now, provider=None, fehler='', transkript_id=None):
        if status not in STT_STATUS: raise ValueError('stt_status_unbekannt')
        with self.lock:
            a = self.get(aid)
            a['stt'] = {'status': status, 'provider': a['stt'].get('provider', '') if provider is None else provider, 'fehler': str(fehler or '')[:400], 'at': now}
            if transkript_id: a['transkript_id'] = transkript_id
            return self.schreiben(a)
