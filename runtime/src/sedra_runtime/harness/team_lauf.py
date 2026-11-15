"""Delegation im Gespräch – der Ablauf im Server (SPEC_DELEGATION_IM_GESPRAECH_v1 §3.2, T3 und T5).

Die Hauptsitzung ruft `team_verteilen`; hier werden die Helfer-Sitzungen angelegt, bekommen ihren Auftrag über denselben Weg wie jede
Nachricht (`api.nachricht`), arbeiten gleichzeitig und liefern ihren Schlusstext zurück. Der Aufruf blockiert den Zug der Hauptsitzung.

Nichts hier erteilt ein Recht (DG-14): ein Helfer hat die Kiste seiner Sitzung; was schreibt oder ausführt, legt die gewohnte Karte vor
(DG-04). Solange ein Helfer auf die Freigabe wartet, zählt seine Zeit nicht (DG-13). Der Captain kann einen Helfer oder alle anhalten (DG-09).

Was dieser Baustein vom Server braucht (harness/api.py reicht es durch): `sitzungen`, `stroeme`, `karten`, `nachricht`, `helfer_sitzung`,
`slots_gesamt`, `belegte_slots`, `_melden`, `_audit`."""
from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict

from . import team

TAKT_S = 0.25
HALTEN = 20                    # so viele beendete Delegationen bleiben für die Oberfläche abrufbar
OHNE_FORTSETZUNG_S = 5.0       # eine beantwortete Karte ohne neue Antwort: so lange warten, dann gilt der Helfer als gescheitert
GUT = ('antwort', 'erledigt', 'nur_plan')
AUFTRAG_KOPF = ('Du bist der Helfer „{rolle}“ in einer Delegation der Sitzung {eltern}. Erledige genau diesen Teilauftrag und antworte am Ende mit dem '
                'Ergebnis als Text; die Hauptsitzung bekommt nur diesen Schlusstext. Du kannst selbst nicht delegieren.\n\nAuftrag:\n')


class TeamLauf:
    def __init__(self, api, clock=time.monotonic, schlaf=time.sleep, takt_s=TAKT_S, zeitlimit_s=team.ZEITLIMIT_S):
        self.api, self.clock, self.schlaf, self.takt_s, self.zeitlimit_s = api, clock, schlaf, takt_s, zeitlimit_s
        self.delegationen = OrderedDict()            # T-… → Delegation
        self._sperre = threading.RLock()
        self._antwort = {}                           # (T-…, nr) → A-… der Antwort, die gerade beobachtet wird
        self._gezaehlt = {}                          # (T-…, nr) → {A-…: (züge, token)} der beendeten Antworten
        self._ohne = {}                              # (T-…, nr) → Sekunden ohne Karte und ohne Antwort
        self._gemeldet = {}

    # ---- lesen
    def stand(self, tid):
        with self._sperre:
            d = self.delegationen.get(tid)
            if d is None:
                raise KeyError('delegation_unbekannt')
            return d.oeffentlich()

    def laufende(self):
        with self._sperre:
            return [d.oeffentlich() for d in self.delegationen.values() if not d.fertig()]

    def _helfer_von(self, sitzung_id):
        for d in self.delegationen.values():
            for h in d.helfer:
                if h['sitzung_id'] == sitzung_id:
                    return d, h
        return None, None

    def datei_hinweis(self, sitzung_id, pfad):
        """T5 (DG-15): der Satz für die Karte, wenn ein anderer Helfer derselben Delegation diese Datei schon zur Änderung vorgelegt hat."""
        with self._sperre:
            d, h = self._helfer_von(sitzung_id)
            if d is None or d.fertig():
                return None
            rolle = d.datei_vorgelegt(h['nr'], pfad)
        return f'Achtung: Diese Datei hat in derselben Delegation auch der Helfer „{rolle}“ zur Änderung vorgelegt.' if rolle else None

    # ---- anhalten (DG-09)
    def stopp(self, tid, sitzung_id=None):
        with self._sperre:
            d = self.delegationen.get(tid)
            if d is None:
                raise KeyError('delegation_unbekannt')
            nr = None
            if sitzung_id is not None:
                nr = next((h['nr'] for h in d.helfer if h['sitzung_id'] == sitzung_id), None)
                if nr is None:
                    raise KeyError('helfer_unbekannt')
            angehalten = self._anhalten(d, nr)
            self._melden(d)
        self.api._audit('HARNESS_TEAM_STOPP', {'delegation': tid, 'helfer': angehalten})
        return {'delegation': tid, 'angehalten': angehalten}

    def _anhalten(self, d, nr=None):
        for h in d.helfer:
            if (nr is None or h['nr'] == nr) and h['zustand'] in (team.LAEUFT, team.FREIGABE) and h['sitzung_id']:
                lauf = self.api.stroeme.laufend_in(h['sitzung_id'])
                if lauf is not None:
                    lauf.stoppen()
                h['ergebnis'] = self._text(h['sitzung_id'])
        return d.anhalten(nr)

    # ---- der Aufruf der Hauptsitzung
    def verteilen(self, eltern_sid, antwort_id, auftraege):
        """Legt die Helfer an, wartet auf alle und gibt den Ergebnistext zurück (DG-01, DG-07). TeamFehler bei falschem Aufruf."""
        sauber = team.pruefe_auftraege(auftraege)
        haupt = self.api.sitzungen.laden(eltern_sid)
        if haupt['kopf'].get('eltern'):
            raise team.TeamFehler('helfer_delegiert_nicht: ein Helfer kann selbst nicht delegieren')        # DG-05, zweite Sicherung neben der Kiste
        with self._sperre:
            if any(d.eltern == eltern_sid and not d.fertig() for d in self.delegationen.values()):
                raise team.TeamFehler('delegation_laeuft: diese Sitzung hat schon eine laufende Delegation')    # DG-13
            d = team.Delegation(eltern_sid, sauber, zeitlimit_s=self.zeitlimit_s)
            self.delegationen[d.id] = d
            while len(self.delegationen) > HALTEN and next(iter(self.delegationen.values())).fertig():
                self.delegationen.popitem(last=False)
        self.api._audit('HARNESS_TEAM_START', {'delegation': d.id, 'eltern': eltern_sid, 'helfer': len(sauber), 'rollen': [a['rolle'] for a in sauber]})
        eigen = haupt.get('slot')
        frei = team.freie_slots(self.api.slots_gesamt(), [eigen if eigen is not None else 0] + list(self.api.belegte_slots(eltern_sid)))
        plaetze = [slot for _i, slot in team.verteilen(len(sauber), frei)['sofort']]          # die Plätze, die den Helfern zusammen gehören
        haupt_antwort = self.api.stroeme.hole(antwort_id) if antwort_id else None
        letzte = self.clock()
        try:
            while True:
                with self._sperre:
                    jetzt = self.clock(); dt, letzte = jetzt - letzte, jetzt
                    for h in d.helfer:
                        if h['zustand'] in (team.LAEUFT, team.FREIGABE):
                            self._beobachten(d, h, dt)
                    belegt = [h['slot'] for h in d.helfer if h['zustand'] in (team.LAEUFT, team.FREIGABE)]
                    frei_jetzt = list(plaetze)
                    for s in belegt:
                        if s in frei_jetzt:
                            frei_jetzt.remove(s)
                    for nr in d.wartende():
                        if not frei_jetzt:
                            break
                        self._starten(d, nr, frei_jetzt.pop(0), haupt)
                    if haupt_antwort is not None and haupt_antwort.abbruch.is_set():           # der Captain hat die Hauptantwort gestoppt: alle Helfer halten mit an
                        self._anhalten(d)
                    self._melden(d)
                    if d.fertig():
                        break
                self.schlaf(self.takt_s)
        finally:
            with self._sperre:
                if not d.fertig():                     # nie eine Delegation, die für immer läuft
                    self._anhalten(d)
                    for h in d.helfer:
                        d.enden(h['nr'], team.GESCHEITERT, grund='Delegation abgebrochen')
                self._melden(d)
            self.api._audit('HARNESS_TEAM_ENDE', {'delegation': d.id, 'eltern': eltern_sid, 'zustaende': [h['zustand'] for h in d.helfer]})
        return team.ergebnis_text(d)

    def _starten(self, d, nr, slot, haupt):
        h = d.helfer[nr - 1]
        try:
            kopf = self.api.helfer_sitzung(haupt, d.id, h['rolle'], team.kurz(h['text'], 50), slot)
            d.starten(nr, kopf['id'], slot)
            out = self.api.nachricht(kopf['id'], {'text': AUFTRAG_KOPF.format(rolle=h['rolle'], eltern=d.eltern) + h['text']})
            if out.get('status') != 'laeuft':
                d.enden(nr, team.GESCHEITERT, grund=out.get('grund') or out.get('status') or 'nicht gestartet')
            else:
                self._antwort[(d.id, nr)] = out['antwort_id']
        except Exception as exc:                                     # ein Helfer, der nicht startet, stoppt die anderen nicht (DG-08)
            d.enden(nr, team.GESCHEITERT, grund=f'{type(exc).__name__}: {exc}')

    def _text(self, sitzung_id):
        """Der Schlusstext eines Helfers: der Text seiner letzten Antwort."""
        try:
            eintraege = self.api.sitzungen.laden(sitzung_id)['eintraege']
        except Exception:
            return ''
        return next((str(e.get('text') or '') for e in reversed(eintraege) if e.get('typ') == 'modell' and e.get('text')), '')

    def _zaehlen(self, d, nr, antwort, daten):
        z = self._gezaehlt.setdefault((d.id, nr), {})
        z[antwort.id] = (int(daten.get('zuege') or 0), daten.get('token') or {})
        d.messen(nr, zuege=sum(v[0] for v in z.values()),
                 token={'ein': sum(int(v[1].get('ein') or 0) for v in z.values()), 'aus': sum(int(v[1].get('aus') or 0) for v in z.values())})

    def _beobachten(self, d, h, dt):
        nr, sid, schluessel = h['nr'], h['sitzung_id'], (d.id, h['nr'])
        lauf = self.api.stroeme.laufend_in(sid)
        if lauf is not None:                                         # er arbeitet (auch wieder nach einer Freigabe)
            self._antwort[schluessel] = lauf.id
            self._ohne.pop(schluessel, None)
            d.weiter(nr)
            if d.takt(nr, dt):
                lauf.stoppen()
                d.enden(nr, team.GESCHEITERT, self._text(sid), grund=f'Zeitlimit von {int(d.zeitlimit_s)} s erreicht')
            return
        a = self.api.stroeme.letzte_in(sid) or self.api.stroeme.hole(self._antwort.get(schluessel))     # die neueste: eine Fortsetzung nach der Freigabe kann zwischen zwei Takten begonnen und geendet haben
        letzte = a.ereignisse[-1] if a is not None and a.ereignisse else None
        if letzte is None or letzte['event'] != 'ende':
            if a is None or a.fertig:
                d.enden(nr, team.GESCHEITERT, self._text(sid), grund='Antwort endete ohne Ergebnis')
            return
        daten = letzte['data']
        self._zaehlen(d, nr, a, daten)
        ende = daten.get('ende')
        if ende == 'wartet':
            kid = daten.get('karte_id')
            if any(k.get('karte_id') == kid for k in self.api.karten.alle('offen')):
                self._ohne.pop(schluessel, None)
                d.wartet_auf_freigabe(nr, kid)
                return
            self._ohne[schluessel] = self._ohne.get(schluessel, 0.0) + dt      # beantwortet: die Fortsetzung startet gleich als neue Antwort
            if self._ohne[schluessel] >= OHNE_FORTSETZUNG_S:
                d.enden(nr, team.GESCHEITERT, self._text(sid), grund='Freigabe-Karte beendet, aber die Antwort wurde nicht fortgesetzt')
        elif ende in GUT:
            d.enden(nr, team.FERTIG, self._text(sid))
        elif ende == 'abgebrochen':
            d.enden(nr, team.ANGEHALTEN, self._text(sid), grund='Antwort abgebrochen')
        else:
            d.enden(nr, team.GESCHEITERT, self._text(sid), grund=daten.get('grund') or ende or 'unbekannt')

    def _melden(self, d):
        stand = d.oeffentlich()
        grob = dict(stand, helfer=[dict(h, sekunden=int(h['sekunden'] // 5)) for h in stand['helfer']])      # die Dauer zählt die Oberfläche selbst; gemeldet wird alle 5 s und bei jedem Wechsel
        bild = json.dumps(grob, sort_keys=True, ensure_ascii=False)
        if self._gemeldet.get(d.id) != bild:
            self._gemeldet[d.id] = bild
            self.api._melden('harness.team', stand)
