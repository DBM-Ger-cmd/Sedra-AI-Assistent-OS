from __future__ import annotations
from .base import ModelAdapterError
from ..core.content_guard import ContentGuardStop
from . import structured
from contextlib import nullcontext
import json
import time


class ModelRouter:
    def __init__(self, audit=None):
        self.audit=audit
        self.adapters={}

    def register(self, adapter):
        if adapter.id in self.adapters: raise ModelAdapterError(f"duplicate_adapter:{adapter.id}")
        self.adapters[adapter.id]=adapter

    def status(self, check_health=False):
        if check_health:
            return {aid:{"registered":True,"healthy":bool(adapter.health())} for aid,adapter in self.adapters.items()}
        return {aid:{"registered":True} for aid in self.adapters}

    def _allowed(self, adapter_id):
        """Provider health (role routing, off by default) can keep a provider in cooldown out of the choice."""
        health=getattr(self,"provider_health",None)
        return True if health is None else health.allows(adapter_id)

    def choose(self, provider=None):
        if provider:
            adapter=self.adapters.get(provider)
            if not adapter: raise ModelAdapterError(f"unknown_provider:{provider}")
            if not self._allowed(provider): raise ModelAdapterError(f"provider_cooldown:{provider}")
            if not adapter.health(): raise ModelAdapterError(f"provider_unavailable:{provider}")
            return adapter
        for adapter in self.adapters.values():
            if self._allowed(adapter.id) and adapter.health(): return adapter
        raise ModelAdapterError("no_healthy_local_model_provider")

    def chat(self, mission_id, messages, provider=None, model=None, schema=None, **kwargs):
        """Ein Modellaufruf. Mit `schema=` (JSON-Schema, flache Teilmenge – models/structured.py) kommt die Antwort geprüft zurück:
        der Server erzwingt die Form, der Prompt nennt sie, die Antwort wird hier geprüft und bei Fehlern mit dem Fehlersatz noch
        einmal erbeten (höchstens MAX_ROUNDS). Das Ergebnis trägt dann `parsed` und `rounds`. Jede Runde ist ein voller Aufruf –
        durch den Inhaltsschutz, mit Audit, gezählt."""
        if schema is None:
            return self._once(mission_id,messages,provider,model,**kwargs)
        structured.check_schema(schema)
        msgs=list(messages)
        at=next((i for i,m in enumerate(msgs) if not (isinstance(m,dict) and m.get("role")=="system")),len(msgs))
        msgs.insert(at,{"role":"system","content":structured.hint(schema)})
        kwargs=dict(kwargs,response_format=structured.response_format(schema))
        kwargs.setdefault("temperature",0)
        errors=[]
        for round_ in range(1,structured.MAX_ROUNDS+1):
            result=self._once(mission_id,msgs,provider,model,**kwargs)
            value,problem=structured.parse(result.get("content"))
            errors=[problem] if problem else structured.validate(value,schema)
            if not errors:
                result["parsed"]=value; result["rounds"]=round_
                return result
            if self.audit:
                self.audit.append("MODEL_SCHEMA_RETRY",component="model-router",mission_id=mission_id,
                                  payload={"round":round_,"errors":errors[:8]})
            msgs=msgs+[{"role":"assistant","content":result.get("content") or ""},
                       {"role":"user","content":structured.retry_message(errors)}]
        raise ModelAdapterError("structured_output_failed:"+"; ".join(errors[:4]))

    def _once(self, mission_id, messages, provider=None, model=None, **kwargs):
        adapter=self.choose(provider)
        hw=getattr(self,"hardware_manager",None)
        health=getattr(self,"provider_health",None)
        recorder=getattr(self,"recorder",None)       # model_call recording (models/recording.py), only set when GUPPI_RECORD_REPLIES is on
        guard=getattr(self,"content_guard",None)     # Inhaltsschutz (core/content_guard.py): die Runtime setzt ihn immer; nur nackte Tests lassen ihn weg
        started=time.monotonic()
        try:
            with hw.job() if hw else nullcontext():
                if guard is None:
                    result=adapter.chat(messages,model=model,**kwargs)
                else:
                    result=self._guarded(guard,adapter,mission_id,messages,model,kwargs)
        except ContentGuardStop:
            raise                                    # der Aufruf ist nicht gelaufen – kein Anbieterfehler, keine Aufzeichnung
        except Exception as exc:
            if recorder is not None: recorder.record(mission_id,adapter.id,model,messages,kwargs,error=exc,seconds=time.monotonic()-started)
            if health is not None:
                from ..failure_classes import classify
                health.report_failure(adapter.id,classify(exception=exc))   # only provider faults count; the rest is ignored there
            raise
        if recorder is not None: recorder.record(mission_id,adapter.id,model,messages,kwargs,result=result,seconds=time.monotonic()-started)
        if health is not None: health.report_success(adapter.id)
        if self.audit:
            self.audit.append("TOOL_CALLED",component="model-router",mission_id=mission_id,payload={"provider":adapter.id,"model":result.get("model")})
        return result

    @staticmethod
    def _guarded(guard, adapter, mission_id, messages, model, kwargs):
        """Jeder Aufruf geht durch den Inhaltsschutz: vorher Scan und Bewertung, nachher die Antwortprüfung (SPEC_EIN_SICHERER_WEG S2).
        Der Guard sieht nur Text; Werkzeugaufrufe einer Antwort werden ihm als JSON gezeigt, damit auch deren Argumente geprüft sind."""
        box={}
        def complete(prepared):
            res=adapter.chat(prepared,model=model,**kwargs)
            box["result"]=res
            content=res.get("content") if isinstance(res,dict) else None
            if isinstance(content,str) and content.strip(): return content
            calls=res.get("tool_calls") if isinstance(res,dict) else None
            if calls: box["calls"]=True; return json.dumps(calls,ensure_ascii=False,sort_keys=True)
            return content if isinstance(content,str) else ""
        name=model or getattr(adapter,"default_model",None) or adapter.id
        verdict=guard.call(messages,model=str(name),route=getattr(adapter,"route","local"),mission_id=mission_id or "",complete=complete)
        result=box["result"]
        if box.get("calls"):
            result["tool_calls"]=json.loads(verdict.text)   # zurückübersetzt, falls pseudonymisiert
        else:
            result["content"]=verdict.text
        result["guard"]={"binding":verdict.binding,"observed":list(verdict.observed),"flags":list(verdict.output_flags)}
        return result
