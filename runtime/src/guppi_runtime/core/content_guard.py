"""Inhaltsschutz, Teil 2: die eine Stelle, durch die jeder Modellaufruf geht (SPEC_EIN_SICHERER_WEG_v1 §2, S1–S5).

Herkunft: `guard.py` der ersten externen Lieferung (KI GateWay 0.3.0, 15.10.2026), hier in SEDRA-Form:
  - kein eigener Freigabespeicher mehr: eine Entscheidung (`REVIEW`) wartet in `pending`, wird vom Desk wie jede andere
    beantwortet („einmal“ · „ablehnen“), und „einmal“ gilt genau einen Aufruf mit demselben Bindungs-Hash, zehn Minuten (H11)
  - kein eigenes Logbuch: jedes Ereignis geht in SEDRAs Audit-Kette (`SG_*`, Hashes, Regeln, Zählungen – nie Text)
  - keine eigene Schärfe-Einstellung: der Modus des Projekts entscheidet (Sandbox scharf · Beobachten und Vertraut beobachten);
    was den Rechner verlässt und der Grundschutz sind immer scharf

Ablauf je Aufruf, fail-closed an jeder Stelle:
  1. Form prüfen, jeden Teil scannen          -> Fehler = Sperre
  2. bewerten: ALLOW | REVIEW | PSEUDONYMIZE | BLOCK; REVIEW ohne „einmal“ = Entscheidung, kein Aufruf
  3. Audit schreiben                          -> schreibt es nicht, geht nichts raus
  4. fremde Teile als Daten markieren, für die Cloud pseudonymisieren und erneut prüfen
  5. Modell rufen – nur über `complete`, das der Router mitgibt; kein eigener Weg, kein Ausweichmodell
  6. Antwort prüfen, ggf. zurückübersetzen    -> harte Funde = Antwort zurückgehalten
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import secrets
import threading
import time

from .content_policy import (ALWAYS, BLOCK, GROUPS, KEY_FORMATS, POLICY_VERSION, REVIEW, TEMPLATE_INJECTION, ScanFailure,
                             effective, evaluate, group_of, normalize_messages, reason_text, scan_content, scan_messages)
from .b6core.prompt import BEGIN, END, _neutralize
from .b6core import pseudo as b6pseudo
from .b6core.privacy import scan_text

_SEP = '\n\n§§SEDRA-TEIL§§\n\n'
ONCE_SECONDS = 600
MAX_SEGMENT_CHARS = 2_000_000
MAX_PENDING = 50
# Wie SEDRA die Teile eines Aufrufs einstuft, wenn der Rufer nichts sagt: nach der Rolle. Wer es besser weiß (Anhang = project,
# Webseite = untrusted), gibt `trust` je Teil mit. Fehlt beides, gilt der Teil als fremd.
TRUST_BY_ROLE = {'system': 'system', 'user': 'captain', 'assistant': 'project', 'tool': 'untrusted'}
MODE_SHARP = {'sandbox': True, 'beobachten': False, 'vertraut': False}


@dataclass(frozen=True)
class GuardResult:
    status: str                       # OK | NEEDS_DECISION | BLOCKED | WITHHELD | ERROR
    text: str | None = None           # nur bei OK
    reasons: tuple = ()
    rule_ids: tuple = ()
    notes: tuple = ()
    binding: str = ''
    decision: dict | None = None      # bei NEEDS_DECISION: was der Captain sieht
    output_flags: tuple = ()
    observed: tuple = ()              # was scharf geschehen wäre
    route: str = 'local'

    def describe(self):
        return [reason_text(c) for c in self.reasons]


class ContentGuardStop(RuntimeError):
    """Der Aufruf ist nicht gelaufen. `result` sagt, warum – und bei NEEDS_DECISION, welche Entscheidung wartet."""

    def __init__(self, result: GuardResult):
        super().__init__(result.status + ':' + ','.join(result.reasons))
        self.result = result


class ContentGuard:
    def __init__(self, audit=None, mode='beobachten', cloud_enabled=False, clock=time.time):
        self.audit = audit
        self.mode = mode if mode in MODE_SHARP else 'beobachten'
        self.cloud_enabled = bool(cloud_enabled)
        self.clock = clock
        self._lock = threading.RLock()
        self.pending = {}                 # id -> Entscheidung (ohne Text)
        self.once = {}                    # binding -> Zeitpunkt der Einmal-Erlaubnis
        self.counts = {}                  # Ereignis -> Zahl (für das Werkzeug „schutz“)
        self.recent = []                  # die letzten Ereignisse als Sätze, ohne Text
        self.stats = {k: 0 for k in ('calls', 'passed', 'decisions', 'blocked', 'withheld', 'local', 'cloud', 'pseudonymized', 'observed')}
        self.per_group = {g: {'stopped': 0, 'would': 0} for g in list(GROUPS) + list(ALWAYS)}

    # ---------------------------------------------------------------- Schärfe aus dem Modus
    def set_mode(self, mode):
        self.mode = mode if mode in MODE_SHARP else 'beobachten'

    def enforced(self, group, route='local'):
        return route == 'cloud' or group not in GROUPS or MODE_SHARP.get(self.mode, False)

    # ---------------------------------------------------------------- öffentlich
    def check(self, messages, *, model, route='local'):
        msgs = normalize_messages(self._with_trust(messages))
        scans = scan_messages(msgs, MAX_SEGMENT_CHARS)
        return scans, evaluate(scans, route, model, self.cloud_enabled)

    def call(self, messages, *, model, route='local', mission_id='', complete):
        """Prüfen, rufen, prüfen. Gibt GuardResult(OK, text) zurück oder wirft ContentGuardStop."""
        t0 = time.monotonic()
        with self._lock:
            self.stats['calls'] += 1
        base = {'policy': POLICY_VERSION, 'mode': self.mode, 'model': str(model), 'route': str(route), 'mission_id': str(mission_id)[:80]}
        try:
            msgs = normalize_messages(self._with_trust(messages))
            scans = scan_messages(msgs, MAX_SEGMENT_CHARS)
        except ScanFailure as exc:
            raise ContentGuardStop(self._stop('BLOCKED', base, (str(exc),), event='SG_BLOCKED', route=route))
        verdict = evaluate(scans, route, model, self.cloud_enabled)
        outcome, sharp, watched = effective(verdict, lambda g: self.enforced(g, route))
        segs = [{'i': s.index, 'role': s.role, 'trust': s.trust, 'sha256': s.sha256, 'chars': s.chars, 'rules': list(s.rule_ids)} for s in scans]
        info = dict(base, binding=verdict.binding, outcome=outcome, reasons=list(sharp), observed=list(watched),
                    rules=list(verdict.rule_ids), notes=list(verdict.notes), segments=segs)

        if outcome == BLOCK:
            raise ContentGuardStop(self._stop('BLOCKED', info, sharp, event='SG_BLOCKED', verdict=verdict))
        if outcome == REVIEW:
            if not self._consume_once(verdict.binding):
                decision = self._open(verdict, sharp, segs, route, model, mission_id)
                if not self._log('SG_DECISION_PENDING', dict(info, decision_id=decision['id'])):
                    raise ContentGuardStop(self._stop('ERROR', info, ('SG_AUDIT_FAILED',), verdict=verdict))
                raise ContentGuardStop(GuardResult('NEEDS_DECISION', None, sharp + ('SG_DECISION_REQUIRED',), verdict.rule_ids,
                                                   verdict.notes, verdict.binding, decision, observed=watched, route=route))
            info['approval_used'] = True
            self._log('SG_ONCE_USED', dict(base, binding=verdict.binding))

        wrap = self.enforced('anweisungen', route)
        out_msgs, mapping = self._prepare(msgs, outcome, wrap)
        if out_msgs is None:
            raise ContentGuardStop(self._stop('BLOCKED', info, ('SG_PSEUDO_FAILED',), event='SG_BLOCKED', verdict=verdict))
        info['pseudonymized'] = bool(mapping)
        info['wrapped'] = wrap
        if not self._log('SG_MODEL_CALL', info):
            raise ContentGuardStop(self._stop('ERROR', info, ('SG_AUDIT_FAILED',), verdict=verdict))
        try:
            reply = complete(out_msgs)
        except Exception as exc:              # kein Ausweichen auf ein anderes Modell, keine Wiederholung hier
            info['error'] = type(exc).__name__
            self._stop('ERROR', info, ('SG_MODEL_ERROR',), verdict=verdict)
            raise
        return self._finish(reply, mapping, info, verdict, sharp, watched, t0, route)

    # ---------------------------------------------------------------- Entscheidungen (vom Desk beantwortet)
    def decisions(self):
        with self._lock:
            return list(self.pending.values())

    def answer(self, decision_id, way):
        """„einmal“ merkt eine Einmal-Erlaubnis für genau diesen Bindungs-Hash; „ablehnen“ lässt nichts zurück."""
        with self._lock:
            decision = self.pending.pop(decision_id, None)
        if decision is None:
            raise KeyError('SG_DECISION_UNKNOWN')
        if way == 'einmal':
            with self._lock:
                self.once[decision['binding']] = self.clock()
            self._log('SG_ONCE_GRANTED', {'decision_id': decision_id, 'binding': decision['binding']})
            return {'note': 'Einmal geöffnet – derselbe Aufruf läuft jetzt genau einmal. Schick ihn noch einmal ab.'}
        self._log('SG_DECISION_REJECTED', {'decision_id': decision_id, 'binding': decision['binding']})
        return {'note': 'Abgelehnt. Nichts ist an das Modell gegangen.'}

    def status(self):
        """Der Zustand ohne ein Wort aus einem Aufruf. Trägt beides: SEDRAs Sicht (`groups`, `counts`, `recent`) und die Form, die das
        Werkzeug „schutz“ der Lieferung liest (`count`, `rules`, `events`, `pending`, `sharp`/`of`) – damit es sofort ganz SEDRA zeigt."""
        with self._lock:
            sharp = MODE_SHARP.get(self.mode, False)
            rules = [{'id': g, 'name': n, 'says': h, 'sharp': self.enforced(g), 'fixed': False, **self.per_group[g]} for g, (n, h) in GROUPS.items()]
            rules += [{'id': g, 'name': n, 'says': h, 'sharp': True, 'fixed': True, **self.per_group[g]} for g, (n, h) in ALWAYS.items()]
            events = [{'time': time.strftime('%H:%M:%S', time.localtime(r['at'])), 'head': r['head'], 'text': r['text'], 'tone': r['tone'],
                       'task': r.get('task', '')} for r in reversed(self.recent[-30:])]
            pending = [{'id': d['id'], 'head': 'Wartet auf dich', 'time': time.strftime('%H:%M:%S', time.localtime(d['created_at'])),
                        'task': d.get('mission_id', ''), 'text': f"Modell {d['model']} · Weg {d['route']} · {len(d['segments'])} Teil(e)",
                        'describe': list(d['describe'])} for d in self.pending.values()]
            return {'policy': POLICY_VERSION, 'mode': 'schuetzt' if sharp else 'beobachtet', 'project_mode': self.mode,
                    'sharp': len(GROUPS) if sharp else 0, 'of': len(GROUPS), 'cloud_enabled': self.cloud_enabled,
                    'groups': {g: {'name': n, 'hint': h, 'sharp': self.enforced(g)} for g, (n, h) in GROUPS.items()},
                    'always': {g: {'name': n, 'hint': h} for g, (n, h) in ALWAYS.items()},
                    'count': dict(self.stats), 'rules': rules, 'events': events, 'pending': pending,
                    'counts': dict(self.counts), 'recent': [{'at': r['at'], 'event': r['event'], 'text': r['text']} for r in self.recent[-30:]]}

    # ---------------------------------------------------------------- intern
    def _with_trust(self, messages):
        out = []
        for m in messages if isinstance(messages, (list, tuple)) else []:
            if isinstance(m, dict) and 'trust' not in m and m.get('role') in TRUST_BY_ROLE:
                m = dict(m, trust=TRUST_BY_ROLE[m['role']])
            out.append(m)
        return out or messages

    def _consume_once(self, binding):
        with self._lock:
            granted = self.once.pop(binding, None)
        return granted is not None and self.clock() - granted <= ONCE_SECONDS

    def _open(self, verdict, sharp, segs, route, model, mission_id):
        with self._lock:
            for d in self.pending.values():
                if d['binding'] == verdict.binding:
                    return d                                   # dieselbe Handlung ist eine Entscheidung, nicht zehn (H12)
            if len(self.pending) >= MAX_PENDING:
                raise ContentGuardStop(GuardResult('BLOCKED', None, ('SG_TOO_MANY_PENDING',), route=route))
            did = 'sg-' + verdict.binding[:12] + '-' + secrets.token_hex(3)
            d = {'id': did, 'kind': 'content', 'binding': verdict.binding, 'route': route, 'model': str(model),
                 'mission_id': str(mission_id)[:80], 'reasons': list(sharp), 'describe': [reason_text(c) for c in sharp],
                 'rules': list(verdict.rule_ids), 'segments': segs, 'ways': ['einmal', 'ablehnen'], 'created_at': self.clock()}
            self.pending[did] = d
            return d

    def _prepare(self, msgs, outcome, wrap):
        contents = [m['content'] for m in msgs]
        mapping = {}
        if outcome == 'PSEUDONYMIZE':
            joined = _SEP.join(contents)
            try:
                scan = scan_text('SEDRA', joined)
                result = b6pseudo.pseudonymize(joined, scan)
                if b6pseudo.recheck(result.text, result.mapping):
                    return None, None
            except Exception:
                return None, None
            parts = result.text.split(_SEP)
            if len(parts) != len(contents):
                return None, None
            contents, mapping = parts, dict(result.mapping)
        out = []
        for m, c in zip(msgs, contents):
            if wrap and m['trust'] == 'untrusted':
                c = f'{BEGIN}\n{_neutralize(c)}\n{END}'
            out.append({'role': m['role'], 'content': c})
        return out, mapping

    def _finish(self, reply, mapping, info, verdict, sharp, observed, t0, route):
        if not isinstance(reply, str) or not reply.strip():
            raise ContentGuardStop(self._stop('WITHHELD', info, ('SG_OUTPUT_EMPTY',), verdict=verdict))
        hard, flags = [], []
        try:
            hits = scan_content(reply)
        except ScanFailure as exc:
            raise ContentGuardStop(self._stop('WITHHELD', info, (str(exc),), verdict=verdict))
        for h in hits:
            r = h.rule_id.split(':', 1)[0]
            if r == 'PAN_CVV_V1': hard.append('SG_OUTPUT_CARD')
            elif r.startswith('INVISIBLE_BLOCK'): hard.append('SG_OUTPUT_INVISIBLE')
            elif r in KEY_FORMATS: hard.append('SG_OUTPUT_KEY_FORMAT')
            elif r == TEMPLATE_INJECTION: flags.append('SG_OUTPUT_TEMPLATE')
        hard, flags = tuple(dict.fromkeys(hard)), tuple(dict.fromkeys(flags))
        info = dict(info, output_sha256=sha256(reply.encode('utf-8')).hexdigest(), output_rules=sorted({h.rule_id.split(':')[0] for h in hits}),
                    output_hard=list(hard), output_flags=list(flags), ms=int((time.monotonic() - t0) * 1000))
        if hard and self.enforced('antworten', route):
            raise ContentGuardStop(self._stop('WITHHELD', info, hard, verdict=verdict))
        observed = tuple(observed) + hard
        text = reply
        if mapping:
            try:
                b6pseudo.check_output(reply, mapping)
                text = b6pseudo.rehydrate(reply, mapping)
            except b6pseudo.PseudoError as exc:
                info['pseudo_error'] = str(exc)
                raise ContentGuardStop(self._stop('WITHHELD', info, ('SG_OUTPUT_PSEUDO',), verdict=verdict))
        info['observed'] = list(observed)
        if not self._log('SG_OUTPUT_OK', info):
            raise ContentGuardStop(self._stop('ERROR', info, ('SG_AUDIT_FAILED',), verdict=verdict))
        return GuardResult('OK', text, sharp, verdict.rule_ids, verdict.notes, verdict.binding, output_flags=flags, observed=observed, route=verdict.route)

    def _log(self, event, data):
        with self._lock:
            self.counts[event] = self.counts.get(event, 0) + 1
            self._count(event, data)
            row = self._sentence(event, data)
            if row:
                self.recent.append({'at': self.clock(), 'event': event, 'task': data.get('mission_id', ''), **row})
                del self.recent[:-200]
        if self.audit is None:
            return True
        try:
            self.audit.append(event, component='content-guard', mission_id=data.get('mission_id') or None,
                              payload={k: v for k, v in data.items() if k != 'segments'} | {'segments': len(data.get('segments') or [])})
            return True
        except Exception:
            return False

    def _stop(self, status, info, reasons, *, event='SG_STOPPED', verdict=None, route='local'):
        self._log(event, dict(info, status=status, stop_reasons=list(reasons)))      # Sperre bleibt Sperre, auch ohne Logbuch
        if verdict is None:
            return GuardResult(status, None, tuple(reasons), route=str(route))
        return GuardResult(status, None, tuple(reasons), verdict.rule_ids, verdict.notes, verdict.binding, route=verdict.route)

    def _count(self, event, data):
        s, status = self.stats, data.get('status')
        if event == 'SG_BLOCKED': s['blocked'] += 1
        elif event == 'SG_DECISION_PENDING': s['decisions'] += 1
        elif event == 'SG_STOPPED' and status == 'WITHHELD': s['withheld'] += 1
        elif event == 'SG_OUTPUT_OK':
            s['passed'] += 1
            s['cloud' if data.get('route') == 'cloud' else 'local'] += 1
            if data.get('pseudonymized'): s['pseudonymized'] += 1
            if data.get('observed'): s['observed'] += 1
        for code in data.get('stop_reasons') or (data.get('reasons') if event in ('SG_BLOCKED', 'SG_DECISION_PENDING') else []) or []:
            self.per_group[group_of(code)]['stopped'] += 1
        if event == 'SG_OUTPUT_OK':
            for code in data.get('observed') or []:
                self.per_group[group_of(code)]['would'] += 1

    @staticmethod
    def _sentence(event, data):
        """Ein Satz je Ereignis, ohne Text aus dem Aufruf – für das Werkzeug „schutz“."""
        reasons = [reason_text(c) for c in (data.get('stop_reasons') or data.get('reasons') or [])[:2]]
        observed = [GROUPS.get(group_of(c), ('?',))[0] for c in data.get('observed') or []]
        if event == 'SG_BLOCKED': return {'head': 'Gesperrt', 'tone': 'bad', 'text': ' '.join(reasons)}
        if event == 'SG_DECISION_PENDING': return {'head': 'Wartet auf dich', 'tone': 'warn', 'text': ' '.join(reasons)}
        if event == 'SG_OUTPUT_OK' and observed: return {'head': 'Beobachtet', 'tone': 'warn', 'text': 'Durchgelassen, hätte angehalten: ' + ', '.join(sorted(set(observed)))}
        if event == 'SG_OUTPUT_OK': return {'head': 'Frei', 'tone': 'ok', 'text': 'Geprüft und durchgelassen' + (' · Cloud, mit Platzhaltern' if data.get('pseudonymized') else '') + '.'}
        if event == 'SG_STOPPED' and data.get('status') == 'WITHHELD': return {'head': 'Zurückgehalten', 'tone': 'bad', 'text': 'Antwort zurückgehalten: ' + ' '.join(reasons)}
        if event == 'SG_ONCE_GRANTED': return {'head': 'Einmal', 'tone': 'ok', 'text': 'Einmal geöffnet.'}
        if event == 'SG_DECISION_REJECTED': return {'head': 'Abgelehnt', 'tone': 'ok', 'text': 'Abgelehnt – nichts ist hinausgegangen.'}
        return None
