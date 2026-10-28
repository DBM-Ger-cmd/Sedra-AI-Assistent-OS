"""Der Strom einer laufenden Antwort (G2 §3.2, §5): nummerierte Ereignisse, vollständig gehalten bis `ende` + 10 Minuten.

Anders als der gemeinsame Ereignisstrom (desk/events, Ring 256) verliert dieser nichts: ein Client, der neu verbindet, bekommt alles ab
seiner letzten Nummer (`Last-Event-ID`). Höchstens 8 Antworten laufen zugleich; die neunte wird mit `zu_viele_antworten` abgelehnt.
Rein: keine Dateien, kein Modell; die Uhr ist austauschbar."""
from __future__ import annotations

import json
import secrets
import threading
import time

MAX_LAUFEND = 8
HALTEN_S = 600              # nach `ende` noch 10 Minuten lesbar, dann aufgeräumt
WARTEN_S = 15


class ZuVieleAntworten(RuntimeError):
    def __init__(self):
        super().__init__('zu_viele_antworten')


class Antwort:
    def __init__(self, aid, sitzung_id, clock=time.monotonic):
        self.id, self.sitzung_id, self.clock = aid, sitzung_id, clock
        self.ereignisse = []
        self.cond = threading.Condition()
        self.abbruch = threading.Event()
        self.fertig_um = None
        self.begonnen = clock()

    @property
    def fertig(self):
        return self.fertig_um is not None

    def senden(self, name, daten=None):
        """Hängt ein Ereignis an und weckt die Leser. Nach dem Ende kommt nichts mehr dazu."""
        with self.cond:
            if self.fertig:
                return None
            ereignis = {'id': len(self.ereignisse) + 1, 'event': name, 'data': daten or {}, 't': round(self.clock() - self.begonnen, 3)}
            self.ereignisse.append(ereignis)
            if name == 'ende':
                self.fertig_um = self.clock()
            self.cond.notify_all()
            return ereignis

    def beenden(self):
        with self.cond:
            if not self.fertig:
                self.fertig_um = self.clock()
            self.cond.notify_all()

    def lesen(self, ab=0, timeout=WARTEN_S):
        """Die Ereignisse nach Nummer `ab`. Blockiert, bis ein neues kommt, die Antwort endet oder `timeout` vergeht (dann [])."""
        with self.cond:
            if len(self.ereignisse) <= ab and not self.fertig:
                self.cond.wait(timeout)
            return list(self.ereignisse[ab:])

    def stoppen(self):
        self.abbruch.set()


class Stroeme:
    def __init__(self, clock=time.monotonic, max_laufend=MAX_LAUFEND, halten_s=HALTEN_S):
        self.clock, self.max_laufend, self.halten_s = clock, max_laufend, halten_s
        self._antworten = {}
        self._sperre = threading.Lock()

    def anlegen(self, sitzung_id):
        self.aufraeumen()
        with self._sperre:
            if sum(1 for a in self._antworten.values() if not a.fertig) >= self.max_laufend:
                raise ZuVieleAntworten()
            while True:
                aid = 'A-' + secrets.token_hex(4).upper()
                if aid not in self._antworten:
                    break
            antwort = Antwort(aid, sitzung_id, self.clock)
            self._antworten[aid] = antwort
            return antwort

    def hole(self, aid):
        self.aufraeumen()
        with self._sperre:
            return self._antworten.get(aid)

    def laufende(self):
        with self._sperre:
            return [a for a in self._antworten.values() if not a.fertig]

    def laufend_in(self, sitzung_id):
        return next((a for a in self.laufende() if a.sitzung_id == sitzung_id), None)

    def aufraeumen(self):
        jetzt = self.clock()
        with self._sperre:
            for aid in [aid for aid, a in self._antworten.items() if a.fertig and jetzt - a.fertig_um >= self.halten_s]:
                del self._antworten[aid]


def sse(ereignis):
    return ('id: %d\nevent: %s\ndata: %s\n\n' % (ereignis['id'], ereignis['event'],
                                                 json.dumps(dict(ereignis['data'], t=ereignis.get('t')), ensure_ascii=False))).encode('utf-8')


def schreiben(wfile, antwort, ab=0, stop=None, heartbeat=WARTEN_S):
    """Schreibt die Ereignisse ab Nummer `ab` in eine offene SSE-Antwort, bis `ende` gesendet ist, der Client geht oder `stop` gesetzt ist."""
    letzte = ab
    while stop is None or not stop.is_set():
        neu = antwort.lesen(letzte, timeout=min(heartbeat, 5))
        for e in neu:
            wfile.write(sse(e)); letzte = e['id']
        if not neu:
            wfile.write(b': ping\n\n')
        wfile.flush()
        if antwort.fertig and letzte >= len(antwort.ereignisse):
            break
    return letzte
