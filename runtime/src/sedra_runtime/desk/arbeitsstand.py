"""Gedächtnis der Oberfläche auf dem Server (SPEC_DOCK_OHNE_NEUAUFBAU_v1 §9.2, §10; Captain 26.10.2026 E4, E5).

Drei Dinge, die einen Shell-Wechsel und ein Neuladen überstehen sollen, ohne im Browser zu liegen:

- **Arbeitsstand**: welche Objekte offen sind und welches vorn liegt. Jede Shell meldet ihn, jede neue Shell übernimmt ihn.
- **Ablage**: Inhalte der Werkzeuge je Werkzeug und Objekt (Frage, Treffer, halb ausgefüllte Anträge). Darf Personenbezug
  enthalten: er bleibt im Prozess der Runtime auf diesem PC.
- **Gesprächsverlauf**: was der Captain im Gespräch gefragt und gesehen hat.

Alles liegt nur im Speicher dieses Prozesses: nie auf der Platte, nie im Audit, nie in einer Cloud-Route. Ein Neustart der Runtime
leert es (gewollt). Vergessen wird beim Schließen eines Objekts in irgendeiner Shell, nach `RUHE_S` ohne Zugriff und auf Wunsch.

Rein bis auf die Sperre: kein Netz, keine Datei, die Uhr wird übergeben (Tests mit Schein-Uhr). Fehler sind `ValueError` mit Code.
"""
from __future__ import annotations

import json
import re
import threading
import time

MAX_OFFEN = 24                     # Objekte im Arbeitsstand
MAX_VERLAUF = 50                   # Einträge im Gesprächsverlauf
MAX_EINTRAG = 256 * 1024           # Bytes je Werkzeug und Objekt in der Ablage
MAX_ABLAGE = 8 * 1024 * 1024       # Bytes der ganzen Ablage
MAX_TEXT = 16000                   # Zeichen je Eintrag im Verlauf
RUHE_S = 12 * 3600                 # ohne Zugriff so lange: vergessen

OBJEKT = re.compile(r'^[a-z][a-z0-9_]{0,30}:[A-Za-z0-9_.:\-]{1,120}$')
WERKZEUG = re.compile(r'^[a-z0-9-]{2,40}$')
FELDER = ('type', 'id', 'title', 'ansicht', 'view', 'collection')


def schluessel(obj):
    """`typ:id` eines Objekts {type, id}; ValueError, wenn es keins ist."""
    if not isinstance(obj, dict):
        raise ValueError('objekt_ungueltig')
    key = f"{obj.get('type')}:{obj.get('id')}"
    if not OBJEKT.match(key):
        raise ValueError('objekt_ungueltig')
    return key


def _objekt(o):
    """Nur die bekannten Felder eines offenen Objekts, Texte gekürzt (rein)."""
    out = {}
    for k in FELDER:
        v = o.get(k)
        if v is None:
            continue
        if k == 'collection':
            out[k] = bool(v)
        elif isinstance(v, (str, int)):
            out[k] = str(v)[:200]
    schluessel(out)
    return out


def _groesse(werte):
    return len(json.dumps(werte, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


class Gedaechtnis:
    """Arbeitsstand, Ablage und Gesprächsverlauf eines Runtime-Prozesses."""

    def __init__(self, uhr=time.time):
        self.uhr = uhr
        self.lock = threading.Lock()
        self._offen = []           # [{objekt, zeit}] in der Reihenfolge der letzten Benutzung, das jüngste vorn
        self._vorn = None
        self._shell = None
        self._ablage = {}          # (werkzeug, schluessel) -> {werte, zeit, groesse}
        self._verlauf = []

    # ---- Arbeitsstand ------------------------------------------------------------------------------------------------
    def arbeitsstand(self):
        with self.lock:
            self._aufraeumen()
            return {'offen': [dict(e['objekt']) for e in self._offen], 'vorn': self._vorn, 'shell': self._shell}

    def melden(self, offen, vorn=None, geschlossen=(), shell=None):
        """Eine Shell meldet, was sie offen hat. Was sie nicht nennt, aber nicht geschlossen hat, bleibt stehen – vielleicht kann
        diese Shell es nur nicht zeichnen (A20). Geschlossenes fällt heraus, samt seiner Ablage."""
        if not isinstance(offen, list) or not isinstance(geschlossen, (list, tuple)):
            raise ValueError('arbeitsstand_ungueltig')
        neu = []
        for o in offen[:MAX_OFFEN]:
            obj = _objekt(o if isinstance(o, dict) else {})
            if all(schluessel(n['objekt']) != schluessel(obj) for n in neu):
                neu.append({'objekt': obj, 'zeit': self.uhr()})
        zu = {str(k) for k in geschlossen}
        with self.lock:
            genannt = {schluessel(n['objekt']) for n in neu}
            rest = [e for e in self._offen if schluessel(e['objekt']) not in genannt and schluessel(e['objekt']) not in zu]
            self._offen = (neu + rest)[:MAX_OFFEN]
            if vorn is not None:
                self._vorn = str(vorn)[:160] if str(vorn) in {schluessel(e['objekt']) for e in self._offen} else self._vorn
            if self._vorn in zu or self._vorn not in {schluessel(e['objekt']) for e in self._offen}:
                self._vorn = schluessel(self._offen[0]['objekt']) if self._offen else None
            if shell:
                self._shell = str(shell)[:40]
            for key in zu:
                self._vergiss_objekt(key)
            return {'offen': len(self._offen), 'vorn': self._vorn}

    def schliessen(self, key):
        with self.lock:
            self._offen = [e for e in self._offen if schluessel(e['objekt']) != key]
            if self._vorn == key:
                self._vorn = schluessel(self._offen[0]['objekt']) if self._offen else None
            self._vergiss_objekt(key)

    # ---- Ablage ------------------------------------------------------------------------------------------------------
    def ablage_lesen(self, werkzeug, key):
        self._pruefe(werkzeug, key)
        with self.lock:
            self._aufraeumen()
            e = self._ablage.get((werkzeug, key))
            if not e:
                return {'werte': {}, 'zeit': None}
            e['zeit'] = self.uhr()
            return {'werte': json.loads(json.dumps(e['werte'])), 'zeit': e['zeit']}

    def ablage_schreiben(self, werkzeug, key, werte):
        """Ersetzt die Werte dieses Werkzeugs an diesem Objekt. Zu groß → `ablage_zu_gross`; ist die ganze Ablage voll, fallen die
        ältesten Einträge anderer Objekte heraus (die Rückgabe nennt, wie viele)."""
        self._pruefe(werkzeug, key)
        if not isinstance(werte, dict):
            raise ValueError('ablage_ungueltig')
        try:
            groesse = _groesse(werte)
        except (TypeError, ValueError):
            raise ValueError('ablage_ungueltig')
        if groesse > MAX_EINTRAG:
            raise ValueError('ablage_zu_gross')
        with self.lock:
            if not werte:
                self._ablage.pop((werkzeug, key), None)
                return {'gespeichert': 0, 'verdraengt': 0}
            self._ablage[(werkzeug, key)] = {'werte': json.loads(json.dumps(werte)), 'zeit': self.uhr(), 'groesse': groesse}
            verdraengt = 0
            while sum(e['groesse'] for e in self._ablage.values()) > MAX_ABLAGE:
                alt = min((k for k in self._ablage if k != (werkzeug, key)), key=lambda k: self._ablage[k]['zeit'], default=None)
                if alt is None:
                    break
                del self._ablage[alt]
                verdraengt += 1
            return {'gespeichert': groesse, 'verdraengt': verdraengt}

    # ---- Gesprächsverlauf --------------------------------------------------------------------------------------------
    def verlauf(self):
        with self.lock:
            return {'eintraege': [dict(e) for e in self._verlauf]}

    def verlauf_merken(self, rolle, text, modell=None, **extra):
        if rolle not in ('user', 'assistant'):
            raise ValueError('rolle_ungueltig')
        eintrag = {'rolle': rolle, 'text': str(text or '')[:MAX_TEXT], 'zeit': self.uhr()}
        if modell:
            eintrag['modell'] = str(modell)[:120]
        for k, v in extra.items():
            if isinstance(v, str) and v:
                eintrag[k] = v[:MAX_TEXT]
        with self.lock:
            self._verlauf.append(eintrag)
            del self._verlauf[:-MAX_VERLAUF]

    def verlauf_leeren(self):
        with self.lock:
            n = len(self._verlauf)
            self._verlauf.clear()
            return n

    # ---- Übersicht und Leeren ----------------------------------------------------------------------------------------
    def uebersicht(self):
        """Für den Maschinenraum: Zahlen, nie Inhalte."""
        with self.lock:
            self._aufraeumen()
            zeiten = [e['zeit'] for e in self._ablage.values()] + [e['zeit'] for e in self._offen]
            return {'offen': len(self._offen), 'ablage_eintraege': len(self._ablage),
                    'ablage_bytes': sum(e['groesse'] for e in self._ablage.values()), 'verlauf': len(self._verlauf),
                    'aeltester': min(zeiten) if zeiten else None}

    def leeren(self):
        with self.lock:
            zahlen = {'offen': len(self._offen), 'ablage': len(self._ablage), 'verlauf': len(self._verlauf)}
            self._offen, self._vorn, self._ablage, self._verlauf = [], None, {}, []
            return zahlen

    # ---- intern ------------------------------------------------------------------------------------------------------
    @staticmethod
    def _pruefe(werkzeug, key):
        if not isinstance(werkzeug, str) or not WERKZEUG.match(werkzeug):
            raise ValueError('werkzeug_ungueltig')
        if not isinstance(key, str) or not OBJEKT.match(key):
            raise ValueError('objekt_ungueltig')

    def _vergiss_objekt(self, key):
        for k in [k for k in self._ablage if k[1] == key]:
            del self._ablage[k]

    def _aufraeumen(self):
        grenze = self.uhr() - RUHE_S
        self._offen = [e for e in self._offen if e['zeit'] >= grenze]
        for k in [k for k, e in self._ablage.items() if e['zeit'] < grenze]:
            del self._ablage[k]
        if self._vorn and self._vorn not in {schluessel(e['objekt']) for e in self._offen}:
            self._vorn = schluessel(self._offen[0]['objekt']) if self._offen else None
