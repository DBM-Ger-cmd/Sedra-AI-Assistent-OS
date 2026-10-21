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

# Standing approval (Spec 1, D1.4, G2-S1-KERN-01): the limits live here, in the Guard; orchestra may only choose tighter ones.
STANDING_ACTION = 'wake_agent'
STANDING_MAX_LEVEL = 3
STANDING_MAX_DAYS = 30
STANDING_MAX_USES = 50


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
        token={"token_id":f"APR-{uuid.uuid4().hex[:8].upper()}","mission_id":gate["mission_id"],"gate_id":gate["gate_id"],"grants":{"action_type":gate["request"]["exact_action"],"targets":gate["resolution"]["scope"],"request_digest":gate["request"].get("request_digest")},"limits":{"single_use":True,"max_uses":1},"status":"active","used_at":None,"kind":"once"}
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
            if issued.get("kind")=="standing":          # an active standing token is never dropped; an ended one after TOKEN_KEEP_S
                done=None if issued.get("status")=="active" else _parse_time(issued.get("ended_at"))
            elif issued.get("status")=="active":
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
        if issued.get("kind","once") != "once":       # a standing token is never spent through authorize/check_token
            return {"authorized":False,"reason":"token_kind_mismatch"}
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

    # --- Standing approval (Spec 1, D1.4): several uses, not bound to a mission, only for wake_agent of one agent ---

    def _standing_refused(self, reason, mission_id=None, agent_id=None):
        if self.audit: self.audit.append("CAPTAIN_STANDING_REFUSED",component="guard",mission_id=mission_id,payload={"agent_id":agent_id,"reason":reason})
        return {"authorized":False,"reason":reason}

    def _standing_tokens(self, agent_id, active_only=True):
        target="agent:"+str(agent_id)
        found=[t for t in self._issued_tokens.values() if t.get("kind")=="standing" and (t.get("grants") or {}).get("targets")==[target]
               and (t.get("status")=="active" or not active_only)]
        return sorted(found,key=lambda t:t.get("granted_at") or "")

    def _end(self, t, reason, now):
        t["status"]={"verbraucht":"spent","abgelaufen":"expired"}.get(reason,"ended"); t["ended_at"]=now.isoformat(); t["end_reason"]=reason
        agent_id=t["grants"]["targets"][0].removeprefix("agent:")
        if self.audit: self.audit.append("CAPTAIN_STANDING_ENDED",component="guard",mission_id=t.get("mission_id"),payload={"token_id":t["token_id"],"agent_id":agent_id,"reason":reason})

    def grant_standing(self, approval_token, *, mission_id, agent_id, fingerprint, max_uses, expires_at):
        """Turn one spent Captain approval for exactly this binding into a standing approval for wake_agent of one agent."""
        with self.token_transaction():
            binding={"art":"standing","agent_id":agent_id,"fingerprint":fingerprint,"max_uses":max_uses,"expires_at":expires_at}
            r=self._authorize(approval_token,mission_id=mission_id,action=STANDING_ACTION,target="agent:"+str(agent_id),request_binding=binding)
            if not r["authorized"]: return self._standing_refused(r["reason"],mission_id,agent_id)
            now=datetime.now(timezone.utc); fp=fingerprint if isinstance(fingerprint,dict) else {}
            if fp.get("agent_id")!=agent_id or fp.get("status")!="aktiv": return self._standing_refused("standing_agent_not_active",mission_id,agent_id)
            level=fp.get("permission_level")
            if type(level) is not int or not 0<=level<=STANDING_MAX_LEVEL: return self._standing_refused("standing_level_too_high",mission_id,agent_id)
            if type(max_uses) is not int or not 1<=max_uses<=STANDING_MAX_USES: return self._standing_refused("standing_uses_out_of_range",mission_id,agent_id)
            until=_parse_time(expires_at) if isinstance(expires_at,str) else None
            if until is None or not now<until<=now+timedelta(days=STANDING_MAX_DAYS): return self._standing_refused("standing_expiry_out_of_range",mission_id,agent_id)
            for old in self._standing_tokens(agent_id): self._end(old,"ersetzt",now)
            token={"token_id":f"STD-{uuid.uuid4().hex[:8].upper()}","kind":"standing","mission_id":mission_id,"gate_id":approval_token.get("gate_id"),
                   "grants":{"action_type":STANDING_ACTION,"targets":["agent:"+str(agent_id)],"request_digest":digest(fingerprint)},
                   "limits":{"single_use":False,"max_uses":max_uses,"max_level":STANDING_MAX_LEVEL},
                   "uses":0,"status":"active","validity":{"expires_at":until.isoformat()},"granted_at":now.isoformat(),"last_used_at":None,"ended_at":None,"end_reason":None}
            self._issued_tokens[token["token_id"]]=token
            self._persist_tokens()
            if self.audit: self.audit.append("CAPTAIN_STANDING_GRANTED",component="guard",mission_id=mission_id,payload={"token_id":token["token_id"],"agent_id":agent_id,"max_uses":max_uses,"expires_at":token["validity"]["expires_at"],"level":level})
            return {"authorized":True,"token":deepcopy(token)}

    def authorize_standing(self, agent_id, *, fingerprint, budget_stage, run_ref):
        """One use of the agent's standing approval, or the reason why not. Expiry, a changed fingerprint, a stopped budget and the
        last use end the token; the caller then needs a single Captain approval again."""
        with self.token_transaction():
            active=self._standing_tokens(agent_id)
            if not active: return {"authorized":False,"reason":"no_standing_approval"}
            t=active[-1]; now=datetime.now(timezone.utc); refusal=None
            expires=_parse_time((t.get("validity") or {}).get("expires_at"))
            if expires is None or expires<=now: self._end(t,"abgelaufen",now); refusal="standing_expired"
            elif digest(fingerprint)!=t["grants"]["request_digest"]: self._end(t,"erloschen:fingerabdruck",now); refusal="standing_fingerprint_changed"
            elif budget_stage=="gestoppt": self._end(t,"erloschen:budget",now); refusal="standing_budget_exhausted"
            elif t["uses"]>=t["limits"]["max_uses"]: self._end(t,"verbraucht",now); refusal="standing_used_up"
            if refusal:
                self._persist_tokens(); return {"authorized":False,"reason":refusal}
            t["uses"]+=1; t["last_used_at"]=now.isoformat()
            if t["uses"]==t["limits"]["max_uses"]: self._end(t,"verbraucht",now)       # the last use still counts, then the token ends
            self._persist_tokens()
            if self.audit: self.audit.append("CAPTAIN_STANDING_USED",component="guard",mission_id=t.get("mission_id"),payload={"token_id":t["token_id"],"agent_id":agent_id,"uses":t["uses"],"max_uses":t["limits"]["max_uses"],"run_ref":run_ref})
            return {"authorized":True,"token_id":t["token_id"],"uses":t["uses"],"left":t["limits"]["max_uses"]-t["uses"]}

    def revoke_standing(self, agent_id, *, reason):
        """End every active standing approval of the agent. Needs no gate: it only makes the system stricter."""
        with self.token_transaction():
            now=datetime.now(timezone.utc); found=self._standing_tokens(agent_id)
            for t in found: self._end(t,"widerrufen:"+str(reason),now)
            if found: self._persist_tokens()
            if self.audit: self.audit.append("CAPTAIN_STANDING_REVOKED",component="guard",payload={"agent_id":agent_id,"reason":reason,"count":len(found)})
            return len(found)

    def standing_status(self, agent_id):
        """A copy of the agent's newest standing token, or None. Read only (for the mirror in orchestra.db)."""
        with self.token_transaction():
            found=self._standing_tokens(agent_id,active_only=False)
            return deepcopy(found[-1]) if found else None
