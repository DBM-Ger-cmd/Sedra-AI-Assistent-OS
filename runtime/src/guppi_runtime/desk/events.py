"""One event stream for the whole desktop (SHELL_WERKZEUG_VERTRAG_v1 §5, §10.4).

Until now every window polled its own route every 3–8 seconds. Here the server does the looking once and sends what *changed* to the
shell, which hands it to the tools over the bus. `/api/events` is the Server-Sent-Events endpoint; a shell that reconnects sends
`Last-Event-ID` and gets what it missed from the ring buffer.

Nothing in here runs a mission or changes state: it reads the same views the routes read. The poll interval stays on the server side,
so a quiet PC stays quiet. Testable without a browser: `EventStream` is a plain object and `diff()` is a pure function."""
from __future__ import annotations

import json
import threading
import time

RING = 256                      # events kept for a shell that reconnects
HEARTBEAT_S = 15                # a comment line, so a proxy or a sleeping tab notices the connection is alive


class EventStream:
    """Numbered events with a ring buffer and blocking readers. One per server."""

    def __init__(self, ring=RING):
        self.lock = threading.Condition()
        self.ring, self.size = [], ring
        self.last_id = 0

    def publish(self, name, payload=None):
        with self.lock:
            self.last_id += 1
            event = {'id': self.last_id, 'event': name, 'data': payload or {}}
            self.ring.append(event)
            del self.ring[:-self.size]
            self.lock.notify_all()
            return event

    def since(self, last_id):
        """The events after last_id that are still in the ring (plus whether anything was lost)."""
        with self.lock:
            if not self.ring:
                return [], False
            lost = last_id and last_id < self.ring[0]['id'] - 1
            return [e for e in self.ring if e['id'] > last_id], bool(lost)

    def wait(self, last_id, timeout=HEARTBEAT_S):
        """Blocks until there is an event after last_id, or the timeout passes (then an empty list)."""
        with self.lock:
            if self.ring and self.ring[-1]['id'] > last_id:
                return [e for e in self.ring if e['id'] > last_id]
            self.lock.wait(timeout)
            return [e for e in self.ring if e['id'] > last_id]


def sse(event):
    """One event in the text/event-stream format."""
    return ('id: %d\nevent: %s\ndata: %s\n\n' % (event['id'], event['event'], json.dumps(event['data'], ensure_ascii=False))).encode('utf-8')


def _mission_shape(m):
    return {'id': m.get('mission_id'), 'phase': m.get('phase'), 'status': m.get('status'),
            'steps': len(m.get('steps') or []), 'step': m.get('steps_done') or 0, 'pending': m.get('pending_gates') or 0,
            'title': m.get('intent') or m.get('objective') or m.get('mission_id')}


def diff(before, after):
    """The events between two snapshots. A snapshot is {'missions': [...], 'decisions': [...], 'model': {...}, 'state': str}.

    Pure: same input, same list of (name, payload) pairs – that is what the tests check."""
    out = []
    before = before or {}
    old_m = {m['id']: m for m in (_mission_shape(x) for x in (before.get('missions') or []))}
    new_m = {m['id']: m for m in (_mission_shape(x) for x in (after.get('missions') or []))}
    for mid, m in new_m.items():
        if old_m.get(mid) != m:
            out.append(('task.changed', m))
    for mid in old_m.keys() - new_m.keys():
        out.append(('task.changed', dict(old_m[mid], phase='GONE')))
    old_d = {d['id']: d for d in (before.get('decisions') or [])}
    new_d = {d['id']: d for d in (after.get('decisions') or [])}
    for did, d in new_d.items():
        if did not in old_d:
            out.append(('decision.pending', {'id': did, 'kind': d['kind'], 'title': d['title'], 'describe': d.get('describe'),
                                             'mission_id': d.get('mission_id'), 'gate_id': d.get('gate_id'),
                                             'agent_id': d.get('agent_id')}))      # N4: leer, solange kein Agent betroffen ist
    for did in old_d.keys() - new_d.keys():
        out.append(('decision.answered', {'id': did, 'kind': old_d[did]['kind']}))
    # Live-Zeilen: der Schnappschuss trägt nur die Anzahl je laufender Aufgabe; das Werkzeug holt das Neue mit `since` (desk/live.py)
    old_live, new_live = before.get('live') or {}, after.get('live') or {}
    for tid, count in new_live.items():
        if count > old_live.get(tid, 0):
            out.append(('live.line', {'task_id': tid, 'line': '', 'since': old_live.get(tid, 0), 'total': count}))
    out.extend(_team_events(before, after))
    if (before.get('model') or None) != (after.get('model') or None):
        out.append(('model.changed', after.get('model') or {}))
    if before.get('state') != after.get('state') and after.get('state') is not None:
        out.append(('system.state', {'state': after.get('state')}))
    return out


# Spec 4 (D4.3.2, N3): das Team. Die Felder `orchestra` und `slots` legen die Erweiterungen bei (desk/extensions.snapshot);
# fehlt ein Feld (Orchestrierung aus, kein Scheduler) oder fehlte es beim letzten Blick, entsteht daraus kein Ereignis.
STUFE = {0: 0, 'ok': 0, 80: 1, 'warnung': 1, 100: 2, 'gestoppt': 2}
STUFE_WORT = ('ok', 'warnung', 'gestoppt')


def _changed(old, new):
    """Die IDs, deren Eintrag neu, anders oder weg ist – nach ID sortiert, damit dieselbe Eingabe dieselbe Liste gibt."""
    return sorted((k for k in set(old) | set(new) if old.get(k) != new.get(k)), key=str)


def _budget(entry):
    """Ein Eintrag aus `orchestra.budgets`: die Stufe (0, 80, 100 oder ihr Wort) allein oder {stufe, prozent}."""
    if isinstance(entry, dict):
        return STUFE.get(entry.get('stufe'), 0), entry.get('prozent')
    return STUFE.get(entry, 0), None


def _slots(snap):
    slots = snap.get('slots') or {}
    held = {s.get('slot'): s for s in (slots.get('belegt') or []) if isinstance(s, dict)}
    queue = slots.get('schlange')
    return slots.get('gesamt'), held, (list(queue) if isinstance(queue, (list, tuple)) else queue)


def _team_events(before, after):
    out = []
    if isinstance(before.get('orchestra'), dict) and isinstance(after.get('orchestra'), dict):
        old, new = before['orchestra'], after['orchestra']
        lowered = []
        old_b, new_b = old.get('budgets') or {}, new.get('budgets') or {}
        warnings = []
        for key in _changed(old_b, new_b):
            if key not in new_b:
                continue
            (was, _), (now, pct) = _budget(old_b.get(key, 0)), _budget(new_b[key])
            cloud = str(key).startswith('cloud:')
            if now > was:
                warnings.append(('budget.warning', {'agent_id': '' if cloud else key, 'prozent': pct, 'stufe': STUFE_WORT[now],
                                                    **({'anbieter': str(key)[6:]} if cloud else {})}))
            elif now < was and not cloud:
                lowered.append(key)                              # Budget erhöht: kein Alarm, nur der Agent sieht anders aus
        old_a, new_a = old.get('agents') or {}, new.get('agents') or {}
        agents = sorted(set(_changed(old_a, new_a)) | set(lowered), key=str)
        out.extend(('agent.changed', {'id': aid}) for aid in agents)
        out.extend(('issue.changed', {'id': iid}) for iid in _changed(old.get('issues') or {}, new.get('issues') or {}))
        out.extend(warnings)
    if isinstance(before.get('slots'), dict) and isinstance(after.get('slots'), dict):
        (old_total, old_held, old_queue), (new_total, new_held, new_queue) = _slots(before), _slots(after)
        queue_len = len(new_queue) if isinstance(new_queue, list) else (new_queue or 0)
        slot_events = []
        for n in _changed(old_held, new_held):
            s = new_held.get(n) or old_held.get(n) or {}
            slot_events.append(('slot.changed', {'slot': n, 'state': 'belegt' if n in new_held else 'frei', 'run_id': s.get('run_id'),
                                                 'priority': (new_held.get(n) or {}).get('prioritaet'), 'queue_len': queue_len}))
        if not slot_events and (old_queue != new_queue or old_total != new_total):
            slot_events.append(('slot.changed', {'slot': None, 'state': None, 'run_id': None, 'priority': None, 'queue_len': queue_len}))
        out.extend(slot_events)
    return out


class Poller:
    """Looks at the hub every `interval` seconds and publishes what changed. One thread for the whole desktop."""

    def __init__(self, hub, stream: EventStream, interval=3.0, snapshot=None):
        self.hub, self.stream, self.interval = hub, stream, interval
        self._snapshot = snapshot or (lambda: hub.desk_snapshot())
        self._stop = threading.Event()
        self._thread = None
        self.last = None
        self.error = None

    def tick(self):
        """One look; returns the events published (tests call this directly, without a thread)."""
        try:
            now = self._snapshot()
            self.error = None
        except Exception as exc:                 # a broken view must not kill the stream; the shell is told once
            text = f'{type(exc).__name__}: {exc}'[:200]
            if self.error == text:
                return []                        # the same problem is not repeated every few seconds
            self.error = text
            return [self.stream.publish('desk.error', {'message': text})]
        events = diff(self.last, now)
        self.last = now
        return [self.stream.publish(name, payload) for name, payload in events]

    def start(self):
        if self._thread is not None:
            return
        def loop():
            while not self._stop.wait(self.interval):
                self.tick()
        self._thread = threading.Thread(target=loop, name='desk-poller', daemon=True)
        self.tick()                               # the first snapshot is the ground truth, it publishes nothing useful
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None


def stream_to(wfile, stream: EventStream, last_id=0, stop=None, heartbeat=HEARTBEAT_S, clock=time.monotonic):
    """Writes events to an open response until the client goes away or `stop` is set. Returns the last id written."""
    beat = clock()
    missed, lost = stream.since(last_id)
    if lost:
        wfile.write(b'event: desk.resync\ndata: {}\n\n')
    for event in missed:
        wfile.write(sse(event)); last_id = event['id']
    wfile.flush()
    while stop is None or not stop.is_set():
        for event in stream.wait(last_id, timeout=min(heartbeat, 5)):
            wfile.write(sse(event)); last_id = event['id']
            beat = clock()
        if clock() - beat >= heartbeat:
            wfile.write(b': ping\n\n'); beat = clock()
        wfile.flush()
    return last_id
