from __future__ import annotations
from pathlib import Path
import uuid, yaml, threading, time
from contextlib import ExitStack, contextmanager
from .mission_lock import exclusive
from .request_binding import digest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from .util import utcnow, load_json, atomic_write_json

TOKEN_TTL_S = 24 * 3600          # an approval that is not spent within a day is void; the Captain approves again
TOKEN_KEEP_S = 30 * 24 * 3600    # spent or expired tokens stay in the store this long as a trace, then they are dropped


def _parse_time(value):
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


class Guard:
    def __init__(self, rules_path: Path, audit=None, token_store_path: Path|None=None, token_ttl_s: int=TOKEN_TTL_S):
        self.token_ttl_s=int(token_ttl_s)
        raw=yaml.safe_load(Path(rules_path).read_text(encoding="utf-8"))["guard_rules"]
        self.defaults=raw["defaults"]; self.rules={r["action"]:r for r in raw["rules"]}; self.audit=audit
        self.token_store_path=Path(token_store_path) if token_store_path else None
        stored=load_json(self.token_store_path,{}) if self.token_store_path else {}
        self._issued_tokens=stored or {}
        self._lock=threading.RLock()

    def _persist_tokens(self):
        if self.token_store_path:
            atomic_write_json(self.token_store_path,self._issued_tokens)

    @contextmanager
    def token_transaction(self, wait_s=2.0):
        # An OS lock, not a create-exclusive file: it is released when the holder dies, so a crash during an approval cannot
        # block every later approval. A lock that is really held still fails closed after `wait_s`.
        with self._lock:
            if not self.token_store_path:
                yield; return
            lock_path=self.token_store_path.with_suffix('.lock')
            stack=ExitStack(); deadline=time.monotonic()+wait_s
            while True:
                try:
                    stack.enter_context(exclusive(lock_path)); break
                except RuntimeError as exc:
                    if str(exc)!='mission_execution_busy' or time.monotonic()>=deadline:
                        raise RuntimeError('guard_token_store_busy_or_interrupted') from exc
                    time.sleep(0.01)
            with stack:
                self._issued_tokens=load_json(self.token_store_path,{}) or {}
                yield

    def evaluate(self, action, *, mission_id=None, target="", required_permissions=None, present_permissions=None):
        required=set(required_permissions or []); present=set(present_permissions or [])
        if not required.issubset(present):
            decision="BLOCK"; rid="missing_permission"; reason="Required permission missing"
        else:
            rule=self.rules.get(action)
            decision=(rule or {}).get("decision",self.defaults["unknown_action"])
            rid=(rule or {}).get("id","default"); reason=f"Rule {rid}"
        if self.audit:
            ev={"ALLOW":"GUARD_ALLOWED","BLOCK":"GUARD_BLOCKED","CAPTAIN_REQUIRED":"CAPTAIN_GATE_REQUESTED"}[decision]
            self.audit.append(ev,component="guard",mission_id=mission_id,payload={"action":action,"target":target,"rule_id":rid})
        return {"decision":decision,"rule_id":rid,"reason":reason,"action":action,"target":target}

    def create_gate(self, mission_id, action, target="", risks=None, rollback_available=False, request_binding=None):
        return {"schema":1,"gate_id":f"HG-{uuid.uuid4().hex[:8].upper()}","mission_id":mission_id,"request":{"exact_action":action,"targets":[target] if target else [],"risks":risks or [],"rollback_available":rollback_available,"request_digest":digest(request_binding) if request_binding is not None else None},"status":"pending","resolution":{"decision":None,"decided_at":None,"scope":[],"note":None},"validity":{"single_use":True,"expires_at":None}}

    def approve(self, gate, scope=None):
        with self.token_transaction(): return self._approve(gate,scope)

    def reject(self, gate, note=None):
        """The Captain says no: the gate is resolved with DENY and no token is issued, so the action cannot run on this gate."""
        gate["status"]="resolved"
        gate["resolution"]={"decision":"DENY","decided_at":utcnow(),"scope":[],"note":note}
        if self.audit: self.audit.append("CAPTAIN_GATE_DENIED",component="guard",mission_id=gate["mission_id"],payload={"gate_id":gate["gate_id"]})
        return gate

    def _approve(self, gate, scope=None):
        targets=gate['request']['targets']
        chosen=targets if scope is None else scope
        if not isinstance(chosen,list) or not chosen or not set(chosen).issubset(set(targets)):
            raise ValueError('approval_requires_explicit_gate_scope')
        gate["status"]="resolved"
        gate["resolution"]={"decision":"APPROVE_ONCE","decided_at":utcnow(),"scope":scope or gate["request"]["targets"],"note":None}
        token={"token_id":f"APR-{uuid.uuid4().hex[:8].upper()}","mission_id":gate["mission_id"],"gate_id":gate["gate_id"],"grants":{"action_type":gate["request"]["exact_action"],"targets":gate["resolution"]["scope"],"request_digest":gate["request"].get("request_digest")},"limits":{"single_use":True,"max_uses":1},"status":"active","used_at":None}
        now=datetime.now(timezone.utc)
        token["validity"]={"expires_at":(now+timedelta(seconds=self.token_ttl_s)).isoformat()}
        self._issued_tokens[token["token_id"]]=deepcopy(token)
        self._prune_tokens(now)
        self._persist_tokens()
        if self.audit: self.audit.append("CAPTAIN_GATE_APPROVED",component="guard",mission_id=gate["mission_id"],payload={"gate_id":gate["gate_id"]})
        return token

    def _prune_tokens(self, now):
        """Drop tokens that were spent or expired long ago, so the store does not grow for ever. Active tokens are never dropped here."""
        limit=now-timedelta(seconds=TOKEN_KEEP_S)
        for token_id, issued in list(self._issued_tokens.items()):
            if issued.get("status")=="active":
                expires=_parse_time((issued.get("validity") or {}).get("expires_at"))
                done=expires if expires and expires<=now else None
            else:
                done=_parse_time(issued.get("used_at"))
            if done is not None and done<limit:
                del self._issued_tokens[token_id]

    def authorize(self, token, *, mission_id, action, target="", request_binding=None):
        with self.token_transaction():
            return self._authorize(token,mission_id=mission_id,action=action,target=target,request_binding=request_binding)

    def check_token(self, token, *, mission_id, action, target="", request_binding=None):
        """Would `authorize` accept this token right now? Same checks, but the token is NOT consumed.

        Lets a scheduler learn that an approval is real before it queues the work; the executor still spends the token.
        """
        with self.token_transaction():
            return self._check(token,mission_id=mission_id,action=action,target=target,request_binding=request_binding)

    def _authorize(self, token, *, mission_id, action, target="", request_binding=None):
        result=self._check(token,mission_id=mission_id,action=action,target=target,request_binding=request_binding)
        if not result["authorized"]: return result
        issued=self._issued_tokens[token["token_id"]]
        used_at=utcnow()
        token["status"]="used"
        token["used_at"]=used_at
        issued["status"]="used"
        issued["used_at"]=used_at
        self._persist_tokens()
        return result

    def _check(self, token, *, mission_id, action, target="", request_binding=None):
        if not isinstance(token,dict) or not token or token.get("status") != "active":
            return {"authorized":False,"reason":"missing_or_inactive_token"}
        token_id=token.get("token_id")
        if not isinstance(token_id,str):return {"authorized":False,"reason":"invalid_token_id"}
        issued=self._issued_tokens.get(token_id)
        if not issued or issued.get("status") != "active":
            return {"authorized":False,"reason":"token_not_issued_by_guard"}
        expires=(issued.get("validity") or {}).get("expires_at")       # read from the Guard's own record, never from the copy the caller holds
        if expires is not None:
            moment=_parse_time(expires)
            if moment is None or moment<=datetime.now(timezone.utc):
                return {"authorized":False,"reason":"token_expired"}
        if token.get("mission_id") != issued.get("mission_id") or token.get("grants") != issued.get("grants"):
            return {"authorized":False,"reason":"token_tampered"}
        if token.get("mission_id") != mission_id:
            return {"authorized":False,"reason":"mission_mismatch"}
        grants=token.get("grants",{})
        if grants.get("action_type") != action:
            return {"authorized":False,"reason":"action_mismatch"}
        targets=grants.get("targets") or []
        if not targets or target not in targets:
            return {"authorized":False,"reason":"target_out_of_scope"}
        expected_digest=digest(request_binding) if request_binding is not None else None
        if grants.get('request_digest') != expected_digest:
            return {'authorized':False,'reason':'request_digest_mismatch'}
        limits=issued.get("limits",{})
        if limits.get("single_use",True) and token.get("used_at"):
            return {"authorized":False,"reason":"token_already_used"}
        return {"authorized":True,"reason":"approved"}
