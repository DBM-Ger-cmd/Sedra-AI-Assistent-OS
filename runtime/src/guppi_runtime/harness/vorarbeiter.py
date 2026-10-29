"""Vorarbeiter-Freigabe der Harness-Shell (SPEC_HARNESS_SHELL_v1 HS-26 Rest, HS-29; G2 Stufe 3 §5; G3 Stufe 3 N4).

Der Captain ernennt eine Sitzung mit Vorlage `vorarbeiter` (Recht `vorarbeiter_freigabe`) zum Vorarbeiter eines Projekts. Karten der Stufe `vorarbeiter`
anderer Sitzungen gehen dann an ihn (`an: vorarbeiter`); er entscheidet sie mit den Werkzeugen unten – in derselben Tür wie der Captain
(`freigabe.beantworten`), mit demselben Audit und mit Begründung. Stufe `captain`, Vorbehalte, Warnkarten, Aufgabenkarten und seine eigenen Karten kann er
nie entscheiden (S2, S3); Identität und Rechte prüft der Server bei jedem Aufruf, nie das Modell (S1).

Harness-Code (Vorbehalt): SEDRA ändert diese Datei nicht an sich selbst."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

from . import aufgabe as harness_aufgabe

BEGRUENDUNG_MIN = 15
BREMSE_PRO_STUNDE = 30
FRIST_MIN = 15
WEGE = ('erlauben', 'ablehnen', 'vorlegen')


def jetzt():
    return datetime.now().astimezone()


class Vorarbeiter:
    """Ernennung je Projekt und die Bremse (Entscheidungen je Stunde). Ablage `runtime_data/harness/vorarbeiter.json`, atomar."""

    def __init__(self, pfad: Path):
        self.pfad = Path(pfad)
        self._sperre = threading.Lock()

    def _lesen(self):
        try:
            doc = json.loads(self.pfad.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            doc = {}
        doc.setdefault('projekte', {})
        doc.setdefault('entscheidungen', {})
        return doc

    def _schreiben(self, doc):
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.pfad.with_suffix('.tmp')
        tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, self.pfad)

    def alle(self):
        with self._sperre:
            return dict(self._lesen()['projekte'])

    def zustaendig(self, projekt_id):
        """Die Sitzung, die Vorarbeiter des Projekts ist – oder None."""
        with self._sperre:
            return (self._lesen()['projekte'].get(projekt_id) or {}).get('sitzung_id')

    def projekt_von(self, sitzung_id):
        with self._sperre:
            return next((p for p, v in self._lesen()['projekte'].items() if v.get('sitzung_id') == sitzung_id), None)

    def ernennen(self, projekt_id, sitzung_id, von='captain', jetzt_z=None):
        with self._sperre:
            doc = self._lesen()
            doc['projekte'][projekt_id] = {'sitzung_id': sitzung_id, 'ernannt': (jetzt_z or jetzt()).isoformat(timespec='seconds'), 'von': von}
            self._schreiben(doc)
            return doc['projekte'][projekt_id]

    def entziehen(self, projekt_id):
        with self._sperre:
            doc = self._lesen()
            alt = doc['projekte'].pop(projekt_id, None)
            self._schreiben(doc)
            return alt

    def bremse_frei(self, projekt_id, limit=BREMSE_PRO_STUNDE, jetzt_z=None):
        jetzt_z = jetzt_z or jetzt()
        with self._sperre:
            zeiten = self._lesen()['entscheidungen'].get(projekt_id) or []
        return sum(1 for z in zeiten if datetime.fromisoformat(z) > jetzt_z - timedelta(hours=1)) < limit

    def merken(self, projekt_id, jetzt_z=None):
        jetzt_z = jetzt_z or jetzt()
        with self._sperre:
            doc = self._lesen()
            zeiten = [z for z in doc['entscheidungen'].get(projekt_id) or [] if datetime.fromisoformat(z) > jetzt_z - timedelta(hours=1)]
            zeiten.append(jetzt_z.isoformat(timespec='seconds'))
            doc['entscheidungen'][projekt_id] = zeiten
            self._schreiben(doc)


def _fn(name, beschreibung, props, pflicht):
    return {'type': 'function', 'function': {'name': name, 'description': beschreibung,
                                              'parameters': {'type': 'object', 'properties': props, 'required': pflicht}}}


_S = {'type': 'string'}
SCHEMAS = {
    'freigaben_offen': _fn('freigaben_offen', 'Listet die offenen Freigabe-Karten, die an dich gerichtet sind (Stufe „vorarbeiter“), mit voller Vorschau und vorschau_hash.', {}, []),
    'freigabe_entscheiden': _fn(
        'freigabe_entscheiden',
        'Entscheidet eine Karte, die an dich gerichtet ist: weg = erlauben, ablehnen oder vorlegen (an den Captain weiterreichen). Gib den vorschau_hash der Karte mit '
        '(beweist, dass du die aktuelle Vorschau gelesen hast) und eine Begründung (mindestens 15 Zeichen).',
        {'karte_id': _S, 'weg': {'type': 'string', 'enum': list(WEGE)}, 'begruendung': _S, 'vorschau_hash': _S}, ['karte_id', 'weg', 'begruendung', 'vorschau_hash']),
    'aufgabe_vorschlagen': _fn(
        'aufgabe_vorschlagen',
        'Schlägt dem Captain eine Aufgaben-Freigabe vor (er entscheidet auf einer Karte). Felder: titel, projekt, sitzungen (IDs S-…), erlaubt (Liste von {werkzeug, muster}), '
        'modelle (optional), ende ({bis (ISO mit Zeitzone, höchstens 24 h) und/oder max_aufrufe (höchstens 500)}). Keine weiten Muster.',
        {'titel': _S, 'projekt': _S, 'sitzungen': {'type': 'array', 'items': _S}, 'erlaubt': {'type': 'array', 'items': {'type': 'object'}},
         'modelle': {'type': 'array', 'items': _S}, 'ende': {'type': 'object'}}, ['titel', 'projekt', 'sitzungen', 'erlaubt', 'ende']),
    'aufgabe_beenden': _fn('aufgabe_beenden', 'Schließt eine aktive Aufgaben-Freigabe als erledigt (nur wenn sie „bei erledigt“ erlaubt). Verlängern oder erweitern kannst du nicht.',
                           {'id': _S, 'grund': _S}, ['id']),
}
ENTSCHEIDEN = ('freigaben_offen', 'freigabe_entscheiden')
VORSCHLAGEN = ('aufgabe_vorschlagen', 'aufgabe_beenden')


class Werkzeuge:
    """Die Werkzeuge einer Vorarbeiter-Sitzung. `api` liefert Karten, Aufgaben, Ernennung und die eine Tür (`beantworten`); `rechte` kommt aus der Vorlage.
    Die Sitzung des Aufrufers übergibt die Kiste – sie steht nie in den Argumenten (S1)."""

    def __init__(self, api, rechte, *, frist_min=FRIST_MIN, bremse=BREMSE_PRO_STUNDE):
        self.api, self.rechte, self.frist_min, self.bremse = api, rechte, frist_min, bremse
        self._namen = (ENTSCHEIDEN if rechte.get('vorarbeiter_freigabe') else ()) + (VORSCHLAGEN if rechte.get('aufgaben_vorschlagen') else ())
        self.names = tuple(self._namen)

    def schemas(self):
        return [SCHEMAS[n] for n in self.names]

    @staticmethod
    def _antwort(status, text, wirkung=False):
        return {'status': status, 'ergebnis': text, 'stufe': 'frei', 'regel': 'vorarbeiter-werkzeug', 'wirkung': wirkung}

    def call(self, name, args, sitzung_id):
        args = args if isinstance(args, dict) else {}
        try:
            if name not in self.names:
                return self._antwort('fehler', f'error: Werkzeug {name} ist dir nicht erlaubt')
            projekt = self.api.vorarbeiter.projekt_von(sitzung_id)
            if projekt is None:
                return self._antwort('fehler', 'error: nicht_ernannt – diese Sitzung ist nicht der Vorarbeiter eines Projekts (nur der Captain ernennt)')
            if name == 'freigaben_offen':
                return self.offen(sitzung_id, projekt)
            if name == 'freigabe_entscheiden':
                return self.entscheiden(sitzung_id, projekt, args)
            if name == 'aufgabe_vorschlagen':
                return self.vorschlagen(sitzung_id, projekt, args)
            return self.beenden(sitzung_id, args)
        except (ValueError, KeyError) as exc:
            return self._antwort('fehler', f'error: {exc.args[0] if exc.args else exc}')

    def offen(self, sitzung_id, projekt):
        self.api.karten.frist_pruefen(self.frist_min)
        karten = [k for k in self.api.karten.alle('offen') if k.get('an') == 'vorarbeiter' and k.get('projekt') == projekt and k.get('sitzung_id') != sitzung_id]
        if not karten:
            return self._antwort('ok', 'Keine offenen Karten an dich.')
        zeilen = [f"Karte {k['karte_id']} · Sitzung {k['sitzung_id']} · {k['werkzeug']} · Ziel {k['ziel']}\nStufe {k['stufe']} · Regel {k['regel']} · vorschau_hash {k['vorschau_hash']}\n"
                  f"Vorschau:\n{str(k.get('vorschau') or '')[:6000]}" for k in karten]
        return self._antwort('ok', '\n\n---\n\n'.join(zeilen))

    def entscheiden(self, sitzung_id, projekt, args):
        karten = self.api.karten
        karten.frist_pruefen(self.frist_min)
        weg = str(args.get('weg') or '')
        if weg not in WEGE:
            return self._antwort('fehler', 'error: weg_unbekannt – erlauben, ablehnen oder vorlegen')
        try:
            karte = karten.laden(str(args.get('karte_id') or ''))
        except KeyError:
            return self._antwort('fehler', 'error: karte_unbekannt')
        if karte.get('projekt') != projekt:
            return self._antwort('fehler', 'error: nur_captain – die Karte gehört zu einem anderen Projekt')
        if karte.get('status') != 'offen':
            return self._antwort('fehler', 'error: karte_schon_beantwortet')
        if karte.get('an') != 'vorarbeiter' or karte.get('art', 'werkzeug') != 'werkzeug' or karte.get('vorbehalt') or karte.get('warnung') \
                or karte.get('stufe') == 'captain':
            return self._antwort('fehler', 'error: nur_captain – diese Karte darfst du nicht entscheiden; der Captain entscheidet sie')
        if karte.get('sitzung_id') == sitzung_id:
            return self._antwort('fehler', 'error: selbstfreigabe – Karten deiner eigenen Sitzung entscheidest du nicht')
        if args.get('vorschau_hash') != karte.get('vorschau_hash'):
            return self._antwort('fehler', 'error: hash_veraltet – lies die Karte mit freigaben_offen neu und gib den aktuellen vorschau_hash an')
        begruendung = str(args.get('begruendung') or '').strip()
        if len(begruendung) < BEGRUENDUNG_MIN:
            return self._antwort('fehler', f'error: begruendung_fehlt – mindestens {BEGRUENDUNG_MIN} Zeichen')
        if not self.api.vorarbeiter.bremse_frei(projekt, self.bremse):
            return self._antwort('fehler', f'error: zu_viele – höchstens {self.bremse} Entscheidungen je Stunde; der Rest geht an den Captain')
        von = f'vorarbeiter:{sitzung_id}'
        self.api.vorarbeiter.merken(projekt)
        if weg == 'vorlegen':
            karten.vorlegen(karte['karte_id'], von, begruendung)
            self.api.audit_ereignis('HARNESS_FREIGABE_VORGELEGT', {'karte_id': karte['karte_id'], 'von': von, 'begruendung': begruendung})
            return self._antwort('ok', f"Karte {karte['karte_id']} liegt jetzt beim Captain.")
        r = self.api.beantworten(karte['karte_id'], weg, begruendung, ueber='werkzeug', von=von)
        return self._antwort('ok', f"Karte {karte['karte_id']}: {weg} entschieden. Ergebnis: {r.get('ergebnis_status')} – {str(r.get('ergebnis') or '')[:300]}")

    def vorschlagen(self, sitzung_id, projekt, args):
        doc = {k: args.get(k) for k in ('titel', 'projekt', 'sitzungen', 'erlaubt', 'modelle', 'ende') if k in args}
        if doc.get('projekt') != projekt:
            return self._antwort('fehler', 'error: projekt_passt_nicht – eine Aufgabe schlägst du nur für dein eigenes Projekt vor')
        karte = self.api.aufgabe_vorschlagen(sitzung_id, doc)
        return self._antwort('ok', f"Vorschlag liegt beim Captain als Karte {karte['karte_id']}. Du kannst ihn nicht selbst freigeben.")

    def beenden(self, sitzung_id, args):
        a = harness_aufgabe_beenden(self.api, str(args.get('id') or ''), args.get('grund'), f'vorarbeiter:{sitzung_id}')
        return self._antwort('ok', f"Aufgabe {a['id']} ist erledigt.")


def harness_aufgabe_beenden(api, tid, grund, wer):
    try:
        return api.aufgaben.beenden(tid, grund, wer=wer)
    except KeyError as exc:
        raise ValueError('aufgabe_unbekannt') from exc
    except harness_aufgabe.AufgabeFehler as exc:
        raise ValueError(str(exc)) from exc
