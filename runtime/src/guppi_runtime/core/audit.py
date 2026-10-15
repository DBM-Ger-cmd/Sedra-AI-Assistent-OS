from __future__ import annotations
from pathlib import Path
import json
from .util import utcnow, sha256_bytes, read_last_jsonl, append_lock, atomic_write_bytes

SENSITIVE_KEYS = {'password','secret','token','api_key','apikey','credential','credentials','authorization'}
# `approval_token`, `db_password`, `client_secret` ... A bare "token" substring would also hit `max_tokens` and usage counters, so only the ending counts.
SENSITIVE_SUFFIXES = ('_password','_secret','_token','_api_key','_apikey','_credential','_credentials')

def _is_sensitive(key):
    key=str(key).lower()
    return key in SENSITIVE_KEYS or key.endswith(SENSITIVE_SUFFIXES)

def _redact(value):
    if isinstance(value, dict):
        out={}
        for k,v in value.items():
            out[k] = '***REDACTED***' if _is_sensitive(k) else _redact(v)
        return out
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value

class AuditLog:
    def __init__(self, path: Path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _last(self):
        return read_last_jsonl(self.path)

    def append(self, event_type, *, component='guppi-core', mission_id=None, actor='system', payload=None):
        # Read-last, hash and write happen under one lock so concurrent writers cannot fork the chain.
        with append_lock(self.path):
            return self._append_locked(event_type,component,mission_id,actor,payload)

    def _append_locked(self, event_type, component, mission_id, actor, payload):
        last=self._last()
        event={
            'schema':1,
            'event_id': f"EVT-{(int(last['event_id'].split('-')[-1])+1 if last else 1):06d}",
            'timestamp':utcnow(),
            'event_type':event_type,
            'source':{'component':component,'mission_id':mission_id},
            'actor':{'type':'system','id':actor},
            'payload':_redact(payload or {}),
            'integrity':{'previous_event_hash': last['integrity']['event_hash'] if last else None,'event_hash':None},
        }
        canonical=json.dumps(event,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        event['integrity']['event_hash']=sha256_bytes(canonical)
        with self.path.open('a',encoding='utf-8') as f:
            f.write(json.dumps(event,ensure_ascii=False,sort_keys=True)+'\n')
        self._write_head(event)
        return event

    @property
    def head_path(self):
        return self.path.with_name(self.path.name+'.head')

    def _write_head(self, event):
        # The newest event id and hash, kept apart from the log: cutting events off the end of the log leaves a head that the chain no longer contains.
        try:
            self.head_path.write_text(json.dumps({'event_id':event['event_id'],'event_hash':event['integrity']['event_hash']}),encoding='utf-8')
        except OSError:
            pass      # the log itself is the record; a missing head only weakens the truncation check

    def repair(self):
        '''A crash in the middle of a write can leave a last line that is not valid JSON; every later append then fails. This moves
        that one line, unchanged, to `<log>.torn-<time>` and leaves the chain before it intact. Anything else wrong with the log is not repaired.'''
        with append_lock(self.path):
            if not self.path.exists(): return {'status':'no_log'}
            lines=self.path.read_bytes().split(b'\n')
            while lines and not lines[-1].strip(): lines.pop()
            if not lines: return {'status':'clean'}
            try:
                json.loads(lines[-1].decode('utf-8')); return {'status':'clean'}
            except ValueError:
                pass
            torn=self.path.with_name(self.path.name+'.torn-'+utcnow().replace(':','')[:17])
            torn.write_bytes(lines[-1]+b'\n')
            body=b'\n'.join(lines[:-1])
            atomic_write_bytes(self.path,body+b'\n' if body else b'')
            last=self._last()
            if last: self._write_head(last)
            else: self.head_path.unlink(missing_ok=True)
            return {'status':'repaired','moved_to':str(torn),'chars':len(lines[-1]),'chain_ok':self.verify_chain()}

    def _read_head(self):
        try: return json.loads(self.head_path.read_text(encoding='utf-8')).get('event_hash')
        except (OSError, ValueError, AttributeError): return None

    def verify_chain(self):
        prev=None; seen=set()
        if not self.path.exists(): return True
        for line in self.path.read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            event=json.loads(line)
            if event['integrity']['previous_event_hash'] != prev:
                return False
            expected=event['integrity']['event_hash']
            copy=json.loads(json.dumps(event))
            copy['integrity']['event_hash']=None
            canonical=json.dumps(copy,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
            if sha256_bytes(canonical) != expected:
                return False
            prev=expected
            seen.add(expected)
        head=self._read_head()
        # The head may be one event behind (a crash between log and head write) but never missing from the log.
        return head is None or head in seen
