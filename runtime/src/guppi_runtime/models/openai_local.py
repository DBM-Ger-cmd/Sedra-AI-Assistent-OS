from __future__ import annotations
import json
import re
from urllib.request import Request, urlopen
from urllib.error import URLError
from .base import BaseModelAdapter, ModelAdapterError, require_loopback_url
from ..jobs.runaway_guard import RunawayGuard


class OpenAICompatibleLocalAdapter(BaseModelAdapter):
    def __init__(self, adapter_id: str, base_url: str, timeout=20):
        self.id=adapter_id
        self.base_url=require_loopback_url(base_url)
        self.timeout=int(timeout)

    def _request(self, method, path, payload=None):
        body=None if payload is None else json.dumps(payload).encode("utf-8")
        req=Request(self.base_url+path,data=body,method=method,headers={"Content-Type":"application/json"})
        try:
            with urlopen(req,timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (URLError,TimeoutError,OSError,json.JSONDecodeError) as exc:
            raise ModelAdapterError(f"local_model_api_error:{exc}") from exc

    def health(self):
        try:
            self.list_models(); return True
        except Exception:
            return False

    def list_models(self):
        data=self._request("GET","/v1/models")
        return [x.get("id") for x in data.get("data",[]) if x.get("id")]

    def chat(self,messages,model=None,**kwargs):
        if not isinstance(messages,list) or not messages:
            raise ModelAdapterError("messages_required")
        if model is None:
            models=self.list_models()
            if not models: raise ModelAdapterError("no_models_available")
            model=models[0]
        payload={"model":model,"messages":messages,"stream":False}
        for key in ("temperature","max_tokens","top_p"):
            if key in kwargs and kwargs[key] is not None: payload[key]=kwargs[key]
        fmt=kwargs.get("response_format")
        if fmt is not None:
            # Strukturierte Antwort (models/structured.py): LM Studio, llama-server und Ollama (/v1) erzwingen das Schema serverseitig.
            if not isinstance(fmt,dict) or fmt.get("type") not in ("json_schema","json_object"): raise ModelAdapterError("invalid_response_format")
            payload["response_format"]=fmt
        tools=kwargs.get("tools")
        if tools:
            # Function tools (chat_tools.py): the server returns the model's calls in message.tool_calls, see "message" below.
            if not isinstance(tools,list): raise ModelAdapterError("invalid_tools")
            payload["tools"]=tools; payload["tool_choice"]=kwargs.get("tool_choice") or "auto"
        effort=kwargs.get("reasoning_effort")
        if effort is not None:
            # "none" switches thinking off on the local models measured so far; any other value is passed on as the provider's own hint.
            if effort not in ("none","low","medium","high"): raise ModelAdapterError("invalid_reasoning_effort")
            payload["reasoning_effort"]=effort
        budget=kwargs.get("thinking_budget_tokens")
        if budget is not None:
            # Measured on LM Studio: this field caps the thinking exactly (200 -> 200, 800 -> 800) on both local models. Unknown
            # fields are NOT passed on: on qwen an unknown reasoning field ended in an engine error ("terminated"), so only
            # fields known to work are ever sent.
            if type(budget) is not int or not 1<=budget<=65536: raise ModelAdapterError("invalid_thinking_budget_tokens")
            payload["thinking_budget_tokens"]=budget
        on_delta=kwargs.get("on_delta")
        if on_delta is not None and not callable(on_delta): raise ModelAdapterError("invalid_on_delta")
        if kwargs.get("stream_guard") or on_delta is not None:
            # Harness-Shell (SPEC_HARNESS_SHELL_v1_G2 §3.2): mit `on_delta` wird immer gestreamt, auch ohne Runaway-Wächter.
            return self._chat_streamed(payload,model,kwargs.get("stream_guard"),on_delta=on_delta,with_message=bool(tools))
        data=self._request("POST","/v1/chat/completions",payload)
        choices=data.get("choices") or []
        if not choices: raise ModelAdapterError("no_completion_choice")
        message=choices[0].get("message",{})
        content=message.get("content") or ""
        finish=choices[0].get("finish_reason")
        reasoning=message.get("reasoning_content") or message.get("reasoning") or ""
        harmony=split_harmony(content)
        if harmony is not None:
            content,thinking=harmony
            reasoning=(reasoning+"\n"+thinking) if isinstance(reasoning,str) and reasoning else thinking
        # A reasoning model can spend the whole token limit on thinking and return an empty `content` without any error.
        # Say so, so a caller never mistakes "ran out of tokens while thinking" for "answered with nothing".
        return {"provider":self.id,"model":model,"content":content,"raw":data,"usage":normalize_usage(data.get("usage")),
                "finish_reason":finish,"truncated":finish=="length","reasoning_chars":len(reasoning) if isinstance(reasoning,str) else 0,
                "empty_answer":not content.strip(),"message":message if tools else None}


    def _chat_streamed(self,payload,model,option,on_delta=None,with_message=False):
        """Opt-in (`stream_guard`: True or a dict of RunawayGuard settings): the answer is streamed and watched; a runaway (the model only repeats
        itself, runaway_guard.py) closes the connection, which stops the server's generation, and comes back as finish_reason "runaway" with
        the text so far. Plan docs/LOOP_GUARD_STARNET_EXTENSIONS_PLAN_2026-10-04.md, item E.

        `on_delta(kanal, stueck)` (Harness-Shell, SPEC_HARNESS_SHELL_v1_G2 §3.2, K4) bekommt jedes Teilstück: `antwort` und `denken` als Text,
        `werkzeug` als {index, id, name, arguments} (Teilstück eines Aufrufs). Die Teilstücke von `delta.tool_calls` werden nach `index`
        zusammengesetzt und kommen am Ende als `message.tool_calls` zurück – dieselbe Form wie ohne Streamen. Wirft `on_delta`, wird die
        Verbindung geschlossen (der Server hört auf zu rechnen) und das Ergebnis hat finish_reason "abgebrochen"."""
        guards=None
        if option:
            try: settings=option if isinstance(option,dict) else {}; guards={"answer":RunawayGuard(**settings),"thinking":RunawayGuard(**settings)}
            except TypeError as exc: raise ModelAdapterError("invalid_stream_guard") from exc
        payload=dict(payload,stream=True,stream_options={"include_usage":True})
        req=Request(self.base_url+"/v1/chat/completions",data=json.dumps(payload).encode("utf-8"),method="POST",
                    headers={"Content-Type":"application/json","Accept":"text/event-stream"})
        parts={"answer":[],"thinking":[]}
        calls={}                                     # index -> {"id","type","function":{"name","arguments"}}
        finish=usage=runaway=stopped=None
        chunks=0
        try:
            with urlopen(req,timeout=self.timeout) as resp:
                for raw in resp:
                    line=raw.decode("utf-8","replace").strip()
                    if not line.startswith("data:"): continue
                    body=line[5:].strip()
                    if body=="[DONE]": break
                    try: event=json.loads(body)
                    except ValueError: continue
                    chunks+=1
                    if event.get("usage"): usage=event["usage"]
                    for choice in event.get("choices") or []:
                        delta=choice.get("delta") or {}
                        for channel,piece in (("answer",delta.get("content") or ""),("thinking",delta.get("reasoning_content") or delta.get("reasoning") or "")):
                            if not piece: continue
                            parts[channel].append(piece)
                            if guards is not None:
                                verdict=guards[channel].feed(piece)
                                if verdict and runaway is None: runaway=dict(verdict,channel=channel)
                            if on_delta is not None and stopped is None:
                                stopped=_deliver(on_delta,"antwort" if channel=="answer" else "denken",piece)
                        for part in delta.get("tool_calls") or []:
                            if not isinstance(part,dict): continue
                            index=part.get("index") if type(part.get("index")) is int else len(calls)
                            call=calls.setdefault(index,{"id":None,"type":"function","function":{"name":"","arguments":""}})
                            if part.get("id"): call["id"]=part["id"]
                            if part.get("type"): call["type"]=part["type"]
                            fn=part.get("function") or {}
                            if fn.get("name"): call["function"]["name"]+=fn["name"]
                            if fn.get("arguments"): call["function"]["arguments"]+=fn["arguments"]
                            if on_delta is not None and stopped is None:
                                stopped=_deliver(on_delta,"werkzeug",{"index":index,"id":part.get("id"),"name":fn.get("name") or "","arguments":fn.get("arguments") or ""})
                        if choice.get("finish_reason"): finish=choice["finish_reason"]
                    if runaway is not None or stopped is not None: break    # leaving the with-block closes the connection and the server stops generating
        except (URLError,TimeoutError,OSError) as exc:
            raise ModelAdapterError(f"local_model_api_error:{exc}") from exc
        content="".join(parts["answer"]); reasoning="".join(parts["thinking"])
        harmony=split_harmony(content)
        if harmony is not None:
            content,thinking=harmony
            reasoning=(reasoning+"\n"+thinking) if reasoning else thinking
        if runaway is not None: finish="runaway"
        if stopped is not None: finish="abgebrochen"
        message=None
        if with_message:
            message={"role":"assistant","content":content}
            tool_calls=[calls[i] for i in sorted(calls)]
            for n,call in enumerate(tool_calls):
                if not call["id"]: call["id"]=f"call_{n}"
            if tool_calls: message["tool_calls"]=tool_calls
        return {"provider":self.id,"model":model,"content":content,"raw":{"streamed":True,"chunks":chunks},"usage":normalize_usage(usage),
                "finish_reason":finish,"truncated":finish in ("length","runaway"),"reasoning_chars":len(reasoning),"empty_answer":not content.strip(),
                "runaway":runaway,"message":message,"stopped":stopped}


def _deliver(on_delta,channel,piece):
    """None, solange der Empfänger annimmt; sonst der Grund, warum er abgebrochen hat (seine Ausnahme)."""
    try:
        on_delta(channel,piece)
        return None
    except Exception as exc:
        return f"{type(exc).__name__}:{exc}"[:200]


_HARMONY_MESSAGE=re.compile(r"<\|channel\|>\s*(\w+)[^<]*?(?:<\|constrain\|>[^<]*)?<\|message\|>(.*?)(?=<\|end\|>|<\|return\|>|<\|call\|>|<\|start\|>|\Z)",re.S)


def split_harmony(text):
    """(answer, thinking) for raw Harmony output (gpt-oss with the server's parser off), else None.

    The answer is the `final` channel only; the `analysis` channel is thinking and never becomes the answer. Raw Harmony without
    a final message gives an empty answer, which the callers already treat as "ran out while thinking"."""
    if not isinstance(text,str) or "<|channel|>" not in text or "<|message|>" not in text: return None
    final,thinking=[],[]
    for channel,body in _HARMONY_MESSAGE.findall(text):
        (final if channel=="final" else thinking).append(body.strip())
    return ("\n".join(final),"\n".join(thinking))


def normalize_usage(value):
    """Token counts as the provider reported them, or None. Never a guess."""
    if not isinstance(value,dict): return None
    prompt,completion=value.get("prompt_tokens"),value.get("completion_tokens")
    if type(prompt) is not int or type(completion) is not int or prompt<0 or completion<0: return None
    out={"input_tokens":prompt,"output_tokens":completion}
    details=value.get("prompt_tokens_details")
    cached=details.get("cached_tokens") if isinstance(details,dict) else None
    if type(cached) is int and cached>=0: out["cached_tokens"]=cached
    completion_details=value.get("completion_tokens_details")
    reasoning=completion_details.get("reasoning_tokens") if isinstance(completion_details,dict) else None
    if type(reasoning) is int and 0<=reasoning<=completion: out["reasoning_tokens"]=reasoning   # part of output_tokens, not extra
    return out
