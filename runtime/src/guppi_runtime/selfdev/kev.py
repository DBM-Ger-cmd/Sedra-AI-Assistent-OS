"""Loopback-only client for a local Kev server (POST /v1/systemone).

No Kev weights or server are bundled; this adapter is optional and fail-closed. GUPPI can detect the provider, but cannot
claim a Kev answer unless a local server returned a structurally valid, internally consistent response.

Wire format (read from the Kev project's kev/api.py and kev/serve.py, not guessed):
  request   {"state": <str|object>, "model": "kev-latest", "questions": {<id>: {"type": "noul"|"choice"|"score", "instructions": ..., "criteria": ...}}}
  response  {"model": ..., "answers": {<id>: {...}}, "usage": {"input_tokens": n, "output_tokens": n}, "latency_ms": n}
  answers   noul   {"type": "noul", "noul": p(true)}
            choice {"type": "choice", "choice": key, "confidence": c, "probabilities": {key: p}}
            score  {"type": "score", "score": expected_level, "legend": {...}, "confidence": c, "probabilities": {"0": p, ...}}
  auth      Authorization: Bearer <KEV_API_KEY> when the server was started with that variable; an open server needs none.

A Kev answer is a calibrated opinion of a small model. It is a *model assessment*, never deterministic test evidence.
"""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

QUESTION_TYPES = ("noul", "choice", "score")
QUESTION_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")
MAX_QUESTIONS = 32
MAX_OPTIONS = 255
PROBABILITY_TOLERANCE = 0.02       # the Kev server rounds to 4 decimals and its own clients accept |sum - 1| < 0.02
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class KevProviderError(RuntimeError):
    pass


class KevVerificationProvider:
    def __init__(self, endpoint="http://127.0.0.1:8008/v1/systemone", *, enabled=False, opener=None, timeout=5, model="kev-latest", api_key=None):
        self.endpoint = endpoint
        self.enabled = bool(enabled)
        self.timeout = int(timeout)
        self.model = model if isinstance(model, str) and model else "kev-latest"
        self._api_key = api_key if isinstance(api_key, str) and api_key else None      # never logged, never returned
        self._opener = opener
        parsed = urlparse(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("kev_endpoint_must_be_loopback_http")

    def status(self):
        return {"provider": "kev", "enabled": self.enabled, "endpoint": self.endpoint, "mode": "local_only", "model": self.model,
                "api_key_configured": self._api_key is not None}

    # ---- request
    @staticmethod
    def normalize_questions(questions):
        """Accept the server's own shape (dict id -> question) or a list of question dicts (with an optional `id`).

        Returns the dict the server expects. Questions without a usable type, with empty options, or with too many are
        refused here, before anything is sent.
        """
        if isinstance(questions, dict):
            items = list(questions.items())
        elif isinstance(questions, list):
            items = [((q.get("id") if isinstance(q, dict) else None) or f"q{i + 1}", q) for i, q in enumerate(questions)]
        else:
            raise ValueError("invalid_kev_questions")
        if not 1 <= len(items) <= MAX_QUESTIONS:
            raise ValueError("invalid_kev_questions")
        out = {}
        for qid, raw in items:
            if not isinstance(qid, str) or not QUESTION_ID.fullmatch(qid) or qid in out or not isinstance(raw, dict):
                raise ValueError("invalid_kev_questions")
            qtype = raw.get("type") or ("noul" if "question" in raw or "instructions" in raw else None)
            if qtype not in QUESTION_TYPES:
                raise ValueError("invalid_kev_question_type")
            question = {"type": qtype}
            instructions = raw.get("instructions", raw.get("question"))
            if instructions is not None:
                question["instructions"] = instructions
            criteria = raw.get("criteria")
            if qtype == "choice":
                if not isinstance(criteria, dict) or not 1 <= len(criteria) <= MAX_OPTIONS or any(not isinstance(k, str) or not k for k in criteria):
                    raise ValueError("invalid_kev_choice_criteria")
            elif qtype == "score":
                if not isinstance(criteria, list) or not 1 <= len(criteria) <= MAX_OPTIONS:
                    raise ValueError("invalid_kev_score_criteria")
            elif criteria is not None and not isinstance(criteria, dict):
                raise ValueError("invalid_kev_noul_criteria")
            if criteria is not None:
                question["criteria"] = criteria
            out[qid] = question
        return out

    def verify(self, state, questions):
        if not self.enabled:
            return {"status": "UNAVAILABLE", "provider": "kev", "reason": "kev_provider_disabled"}
        if not isinstance(state, str) or not state.strip() or len(state) > 65536:
            raise ValueError("invalid_kev_state")
        asked = self.normalize_questions(questions)
        body = json.dumps({"state": state, "model": self.model, "questions": asked}, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = Request(self.endpoint, data=body, method="POST", headers=headers)
        try:
            if self._opener:
                result = self._opener(request, self.timeout)
                raw = result.read() if hasattr(result, "read") else result
            else:
                with urlopen(request, timeout=self.timeout) as response:
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise KevProviderError("kev_response_too_large")
            data = json.loads(raw.decode("utf-8"))
        except KevProviderError:
            raise
        except HTTPError as exc:
            exc.close()                                   # release the socket; the status code is all we keep
            raise KevProviderError("kev_unauthorized" if exc.code == 401 else f"kev_http_{exc.code}") from exc
        except Exception as exc:
            raise KevProviderError(f"kev_request_failed:{type(exc).__name__}") from exc
        if not isinstance(data, dict):
            raise KevProviderError("kev_invalid_response")
        answers = self._validate_answers(data.get("answers"), asked)
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return {"status": "ANSWERED", "provider": "kev", "trust_level": "model_assessment", "model": data.get("model"),
                "answers": [answers[qid] for qid in asked], "by_id": answers,
                "usage": {k: usage[k] for k in ("input_tokens", "output_tokens") if type(usage.get(k)) is int} if usage else None,
                "raw": data}

    # ---- response checks: a server that answers nonsense is treated as no answer at all
    @staticmethod
    def _valid_distribution(probabilities, keys):
        if not isinstance(probabilities, dict) or set(probabilities) != set(keys):
            return False
        values = list(probabilities.values())
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1 for v in values):
            return False
        return abs(sum(values) - 1.0) < PROBABILITY_TOLERANCE

    def _validate_answers(self, answers, asked):
        if not isinstance(answers, dict) or set(answers) != set(asked):
            raise KevProviderError("kev_answer_set_mismatch")
        for qid, question in asked.items():
            answer, qtype = answers[qid], question["type"]
            if not isinstance(answer, dict) or answer.get("type") != qtype:
                raise KevProviderError("kev_answer_type_mismatch")
            if qtype == "noul":
                p = answer.get("noul")
                if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 <= p <= 1:
                    raise KevProviderError("kev_invalid_answer")
                continue
            keys = list(question["criteria"]) if qtype == "choice" else [str(i) for i in range(len(question["criteria"]))]
            if not self._valid_distribution(answer.get("probabilities"), keys):
                raise KevProviderError("kev_invalid_answer")
            confidence = answer.get("confidence")
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                raise KevProviderError("kev_invalid_answer")
            if qtype == "choice" and answer.get("choice") not in keys:
                raise KevProviderError("kev_invalid_answer")
            if qtype == "score":
                score = answer.get("score")
                if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= len(keys) - 1:
                    raise KevProviderError("kev_invalid_answer")
        return {qid: answers[qid] for qid in asked}
