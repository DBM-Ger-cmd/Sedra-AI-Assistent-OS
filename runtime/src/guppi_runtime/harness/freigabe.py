"""Freigabe der Harness-Shell (SPEC_HARNESS_SHELL_v1 HS-21, HS-22, HS-28, HS-29; G2 §3.5, §3.6; G3 Stufe 2 U7).

Für jeden Aufruf eines Harness-Werkzeugs: **Vorbehalt** (harness/vorbehalte.py, fest) → **Katalog** (`einstufen`) → **Guard**.
- `frei`: Gate beim Guard anlegen, die Harness ruft `approve` (Audit `HARNESS_APPROVED_BY katalog:<regel>`), das Werkzeug läuft mit genau diesem Token.
- `verboten`: das Modell bekommt „verboten: <Begründung>“, nichts läuft.
- `captain` (und in Stufe 2 `vorarbeiter`): eine **Karte** mit Guard-Gate und Vorschau (Diff oder Befehlszeile); die Schleife endet mit
  `ende: wartet`. `beantworten` ist die **eine** Tür für Karte und Posteingang: dasselbe Audit, derselbe Guard-Weg.
Der Guard bleibt die einzige Stelle, die Tokens ausgibt; hier wird nur entschieden, **wer** `approve` ruft. Harness-Code (Vorbehalt): SEDRA
ändert diese Datei nicht an sich selbst.

Karten liegen je Karte als JSON unter `<projekt>/runtime_data/harness/karten/` – mit dem Zustand der Schleife (Verlauf, offener Aufruf),
damit die Antwort auf die Karte die Schleife fortsetzen kann, auch nach einem Neustart des Servers. Kein Thread wartet auf eine Karte."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
from datetime import datetime
from pathlib import Path

from . import erlaubnis as sitzungs_erlaubnis
from . import code_stand as code_stand_mod
from . import vorbehalte
from .katalog import einstufen
from .werkzeuge import AKTION_LESEN, FREI_OHNE_KATALOG, LAUF, LESEN, NAMEN as HARNESS_WERKZEUGE, WerkzeugFehler
from .befehl import BefehlFehler

KARTE_ID = re.compile(r'K-[0-9A-F]{8}')
WEGE = ('erlauben', 'ablehnen', 'sitzung')        # `sitzung` (P0 M1): erlauben und für diese Sitzung merken


def jetzt():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def einstufung(regeln, name, args, plan):
    """{stufe, wirkt_als, regel, begruendung, vorbehalt} – Vorbehalt vor Katalog; `vorarbeiter` wirkt in Stufe 2 wie `captain`."""
    gesperrt = vorbehalte.pruefen_lesen(name, plan['ziel'])
    if gesperrt:
        return {'stufe': 'verboten', 'wirkt_als': 'verboten', 'regel': 'vorbehalt', 'begruendung': gesperrt, 'vorbehalt': True}
    grund = vorbehalte.pruefen(name, plan['ziel'], args, plan.get('vorhanden', False), ungesehen=plan.get('code_ungesehen'))
    if grund:
        return {'stufe': 'captain', 'wirkt_als': 'captain', 'regel': 'vorbehalt', 'begruendung': grund, 'vorbehalt': True}
    e = einstufen(regeln, name, plan['ziel'])
    return dict(e, wirkt_als='captain' if e['stufe'] == 'vorarbeiter' else e['stufe'], vorbehalt=False)


class Karten:
    """Ablage der Freigabe-Karten: eine Datei je Karte, atomar geschrieben; eine Sperre gegen doppelte Antworten."""

    def __init__(self, ordner: Path):
        self.ordner = Path(ordner)
        self._sperre = threading.Lock()

    def _pfad(self, kid):
        if not isinstance(kid, str) or not KARTE_ID.fullmatch(kid):
            raise KeyError('karte_unbekannt')
        return self.ordner / (kid + '.json')

    def speichern(self, karte):
        self.ordner.mkdir(parents=True, exist_ok=True)
        pfad = self._pfad(karte['karte_id'])
        tmp = pfad.with_suffix('.tmp')
        tmp.write_text(json.dumps(karte, ensure_ascii=False, default=str), encoding='utf-8')
        os.replace(tmp, pfad)
        return karte

    def anlegen(self, daten):
        with self._sperre:
            while True:
                kid = 'K-' + secrets.token_hex(4).upper()
                if not self._pfad(kid).exists():
                    break
            return self.speichern(dict(daten, karte_id=kid, status='offen', angelegt=jetzt()))

    def laden(self, kid):
        pfad = self._pfad(kid)
        if not pfad.is_file():
            raise KeyError('karte_unbekannt')
        return json.loads(pfad.read_text(encoding='utf-8'))

    def alle(self, status=None):
        if not self.ordner.is_dir():
            return []
        out = []
        for p in sorted(self.ordner.glob('K-*.json')):
            try:
                k = json.loads(p.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if status is None or k.get('status') == status:
                out.append(k)
        return sorted(out, key=lambda k: k.get('angelegt') or '')

    def vorlegen(self, kid, von, notiz):
        """Der Vorarbeiter legt eine Karte dem Captain vor: sie bleibt offen, `an` wird `captain` (HS-26)."""
        with self._sperre:
            k = self.laden(kid)
            if k.get('status') != 'offen':
                raise ValueError('karte_schon_beantwortet')
            k['an'] = 'captain'
            k['vorgelegt'] = {'von': von, 'notiz': notiz, 'zeit': jetzt()}
            return self.speichern(k)

    def frist_pruefen(self, frist_min=15, jetzt_z=None):
        """Karten `an: vorarbeiter`, die länger als `frist_min` Minuten offen sind, fallen an den Captain (G2 Stufe 3 §5.3, D-G2). Gibt die geänderten zurück."""
        jetzt_z = jetzt_z or datetime.now().astimezone()
        geaendert = []
        with self._sperre:
            for k in self.alle('offen'):
                if k.get('an') != 'vorarbeiter':
                    continue
                try:
                    alt = (jetzt_z - datetime.fromisoformat(k['angelegt'])).total_seconds() / 60
                except (KeyError, ValueError, TypeError):
                    continue
                if alt >= frist_min:
                    k['an'] = 'captain'
                    k['frist_abgelaufen'] = jetzt_z.isoformat(timespec='seconds')
                    geaendert.append(self.speichern(k))
        return geaendert

    def uebernehmen(self, kid):
        """Setzt eine offene Karte auf `in_arbeit` – genau eine Antwort gewinnt; die zweite bekommt ValueError('karte_schon_beantwortet')."""
        with self._sperre:
            k = self.laden(kid)
            if k.get('status') != 'offen':
                raise ValueError('karte_schon_beantwortet')
            k['status'] = 'in_arbeit'
            return self.speichern(k)


def oeffentlich(karte):
    """Was die Oberfläche und der Posteingang von einer Karte sehen (ohne den Verlauf der Schleife und ohne das Gate-Objekt)."""
    return {k: karte.get(k) for k in ('karte_id', 'sitzung_id', 'antwort_id', 'werkzeug', 'args', 'ziel', 'stufe', 'regel', 'begruendung', 'vorbehalt',
                                      'vorschau', 'status', 'entscheidung', 'von', 'ueber', 'notiz', 'angelegt', 'beantwortet', 'ergebnis_kurz',
                                      'mission_id', 'projekt', 'neue_antwort_id', 'warnung', 'an', 'art', 'vorschau_hash', 'vorgelegt', 'frist_abgelaufen', 'zurueckgenommen',
                                      'aufgabe_id', 'erlaubnis')} | {'gate_id': (karte.get('gate') or {}).get('gate_id')}


class Kiste:
    """Die Werkzeugkiste einer Antwort: Harness-Werkzeuge (mit Freigabe) und die lesenden Zustandswerkzeuge (chat_tools, frei).
    Die Schleife ruft `aufruf`; bei `wartet` hält sie mit `festhalten` ihren Zustand an der Karte fest."""

    def __init__(self, werkzeuge, *, regeln, guard, audit, karten, sitzung_id, chat=None, projekt_id=None, aufgaben=None, lokal=True, vorarbeiter=None, extra=None,
                 erlaubnisse=None, projekte=None):
        self.projekte = projekte      # () -> die Projekte des Harness (nicht die des SEDRA-Kerns), das der Sitzung markiert; für `list_projects`
        self.w, self.regeln, self.guard, self.audit, self.karten = werkzeuge, regeln, guard, audit, karten
        self.erlaubnisse = list(erlaubnisse or ())        # P0 M1: Sitzungs-Erlaubnisse („Für diese Sitzung erlauben“), gelten nicht bei Vorbehalt/Warnkarte
        self.sitzung_id, self.chat, self.projekt_id = sitzung_id, chat, projekt_id
        self.vorarbeiter, self.extra = vorarbeiter, extra        # Stufe 3: Ernennung (Karten `an: vorarbeiter`) und die Werkzeuge des Vorarbeiters
        self.aufgaben, self.lokal = aufgaben, lokal        # Stufe 3: Aufgaben-Freigabe gilt nur für lokale Modelle (HS-27)
        self.names = tuple(HARNESS_WERKZEUGE) + (tuple(chat.names) if chat is not None else ()) + (tuple(extra.names) if extra is not None else ())
        self.wirkung = ('datei_schreiben', 'datei_aendern', 'befehl', 'lauf_starten', 'lauf_stoppen', 'modell_laden', 'modell_entladen', 'sitzungen_aufraeumen')
        self._gewarnt = set()            # Nachtrag 434b108: welche Ersetzungen dem Modell schon einen Hinweis bekamen

    def chat_namen(self):
        return tuple(self.chat.names) if self.chat is not None else ()

    def zustand_schema(self, erlaubt=None):
        """Die lesenden Zustandswerkzeuge als EIN Werkzeug mit Auswahl `was` – das spart rund 350 Token je Anfrage gegenüber elf einzelnen Beschreibungen (Messung 02.11.2026).
        `erlaubt`: nur diese Namen (eine Vorlage nennt nicht alle). Die einzelnen Namen gelten beim Aufruf weiter."""
        namen = [n for n in self.chat_namen() if erlaubt is None or n in erlaubt]
        if not namen:
            return None
        eigenschaften, hinweis = {'was': {'type': 'string', 'enum': namen}, 'limit': {'type': 'integer'}, 'name': {'type': 'string'}}, '; limit für list_missions/recent_audit, name für read_doc'
        if 'gateway_vorgang' in namen:                                # SPEC_WISSEN_KERN_v1 WK-12: die GateWay-Auskunft braucht ihre Argumente
            eigenschaften['id'], hinweis = {'type': 'string'}, hinweis + ', id für gateway_vorgang (GW-…)'
        if 'gateway_regel' in namen:
            eigenschaften['frage'], hinweis = {'type': 'string'}, hinweis + ', frage für gateway_regel (Regel, Merkmal, Begriff, Fehlercode)'
        return {'type': 'function', 'function': {'name': 'zustand', 'description': 'Liest den Zustand von SEDRA (nur lesen, frei). was: ' + ', '.join(namen) + hinweis + '.',
                'parameters': {'type': 'object', 'properties': eigenschaften, 'required': ['was']}}}

    def schemas(self):
        z = self.zustand_schema()
        return self.w.schemas() + ([z] if z else []) + (self.extra.schemas() if self.extra is not None else [])

    def _audit(self, event, payload):
        if self.audit is not None:
            try: self.audit.append(event, component='harness', mission_id=self.w.mission_id, payload=payload)
            except Exception: pass

    def aufruf(self, name, args, *, antwort_id=None, abbruch=None):
        """{status: ok|fehler|verboten|wartet|abgebrochen, ergebnis, stufe, regel, wirkung, karte?}."""
        if self.extra is not None and name in self.extra.names:
            return self.extra.call(name, args, self.sitzung_id)       # Vorarbeiter-Werkzeuge: die Sitzung kommt vom Server, nie aus den Argumenten
        if name == 'zustand':                                         # das gebündelte Zustandswerkzeug: `was` wählt das eigentliche, der Rest sind dessen Argumente
            args = dict(args) if isinstance(args, dict) else {}
            was = args.pop('was', None)
            if was not in self.chat_namen():
                return {'status': 'fehler', 'ergebnis': 'error: was unbekannt – erlaubt: ' + ', '.join(self.chat_namen()), 'stufe': None, 'regel': None, 'wirkung': False}
            name = was
        if name not in HARNESS_WERKZEUGE:
            if self.chat is not None and name in self.chat.names:
                text = json.dumps(self.projekte(), ensure_ascii=False) if name == 'list_projects' and callable(self.projekte) else self.chat.call(name, args)
                return {'status': 'fehler' if str(text).startswith('error') else 'ok', 'ergebnis': str(text), 'stufe': 'frei',
                        'regel': 'zustand-lesen', 'wirkung': False}
            return {'status': 'fehler', 'ergebnis': f'error: unknown tool {name}', 'stufe': None, 'regel': None, 'wirkung': False}
        self.w.kontext = {'sitzung_id': self.sitzung_id, 'antwort_id': antwort_id}      # schon beim Vorbereiten bekannt (sitzungen_aufraeumen nimmt die eigene Sitzung aus)
        try:
            plan = self.w.vorbereiten(name, args)
        except (WerkzeugFehler, BefehlFehler) as exc:
            return {'status': 'fehler', 'ergebnis': f'error: {exc}', 'stufe': None, 'regel': None, 'wirkung': False}
        if name == 'lauf_status':                              # lesen: keine Karte, kein Katalog (der Inhalt der Ausgabe ist fremder Text, das Werkzeug kennzeichnet ihn)
            return dict(self.w.ausfuehren(name, args, plan=plan), stufe='frei', regel='lauf-lesen')
        if name in FREI_OHNE_KATALOG:                          # keine Karte: das Fenster bedient der Captain, der Antrag liegt in seinem Posteingang, die Verknüpfung nimmt er weg
            e = einstufen(self.regeln, name, plan['ziel'])
            if e['stufe'] == 'verboten':                        # nur ein ausdrückliches `verboten` des Captains zählt; ohne Regel laufen sie frei
                self._audit('HARNESS_EINGESTUFT', {'werkzeug': name, 'ziel': plan['ziel'][:300], 'stufe': 'verboten', 'regel': e['regel'], 'vorbehalt': False})
                return {'status': 'verboten', 'ergebnis': f"verboten: {e['begruendung']}", 'stufe': 'verboten', 'regel': e['regel'], 'wirkung': False}
            self.w.kontext = {'sitzung_id': self.sitzung_id, 'antwort_id': antwort_id}
            out = self.w.ausfuehren(name, args, plan=plan)
            if name not in ('erinnern', 'sitzungen_auflisten', 'youtube_transkript', 'vorlage_beantragen', 'desktop_lesen', 'belohnungen_lesen', 'wissen_suchen', 'wissen_beantragen'):                  # wissen_*: eigenes Audit im Wissen, nie der Fragetext (WK-06); die Verknüpfung steht schon im Audit des Servers (mit `von`)
                self._audit('HARNESS_APP_OEFFNEN' if name == 'app_oeffnen' else 'HARNESS_PROJEKT_BEANTRAGT', {'ziel': plan['ziel'][:300], 'status': out['status']})
            return dict(out, stufe='frei', regel=name.replace('_', '-'))
        e = einstufung(self.regeln, name, args, plan)
        self._audit('HARNESS_EINGESTUFT', {'werkzeug': name, 'ziel': plan['ziel'][:300], 'stufe': e['stufe'], 'regel': e['regel'], 'vorbehalt': e['vorbehalt']})
        if e['wirkt_als'] == 'verboten':
            return {'status': 'verboten', 'ergebnis': f"verboten: {e['begruendung']}", 'stufe': 'verboten', 'regel': e['regel'], 'wirkung': False}
        warnung = plan.get('warnung') if name == 'datei_schreiben' else None
        warnkarte = False
        if warnung:
            # W-1: beim ersten Mal nur ein Hinweis ans Modell, nichts wird vorgelegt und nichts geschrieben.
            # W-2: besteht es auf derselben Ersetzung, geht es als Karte mit Warnkasten an den Captain (auch wenn der Katalog frei sagt).
            schluessel = (plan['ziel'], hashlib.sha256(plan['fsargs']['content'].encode('utf-8')).hexdigest())
            if schluessel not in self._gewarnt:
                self._gewarnt.add(schluessel)
                self._audit('HARNESS_WARNUNG_HINWEIS', {'ziel': plan['ziel'][:300], 'entfernt': warnung['entfernt'], 'alt': warnung['alt']})
                return {'status': 'hinweis', 'ergebnis': (
                            f"Nicht geschrieben – Hinweis: {warnung['text']} Bestehende Dateien ändert man mit datei_aendern (eine Stelle ersetzen). "
                            "Willst du die ganze Datei trotzdem ersetzen, ruf datei_schreiben mit demselben Inhalt noch einmal auf; dann entscheidet der Captain auf der Karte."),
                        'stufe': e['stufe'], 'regel': e['regel'], 'wirkung': False}
            e = dict(e, wirkt_als='captain')
            warnkarte = True                                  # Kasten und Entscheidung bleiben beim Captain – keine Aufgabe deckt sie
        via_aufgabe, via_sitzung = None, None
        if e['wirkt_als'] != 'frei' and self.aufgaben is not None and self.lokal and not e['vorbehalt'] and not warnkarte:
            weich = vorbehalte.pruefen_weich(name, plan['ziel'], args) or plan.get('weich')
            treffer = self.aufgaben.deckt(self.sitzung_id, name, plan['ziel'], weich=weich)
            if treffer and self.aufgaben.zaehlen(treffer['aufgabe_id']):
                via_aufgabe = treffer['aufgabe_id']
        if e['wirkt_als'] != 'frei' and not via_aufgabe and not e['vorbehalt'] and not warnkarte and not vorbehalte.pruefen_weich(name, plan['ziel'], args):
            treffer = sitzungs_erlaubnis.deckt(self.erlaubnisse, name, plan['ziel'])
            if treffer:
                via_sitzung = treffer['karte_id']
        self.w.kontext = {'sitzung_id': self.sitzung_id, 'antwort_id': antwort_id, 'aufgabe_id': via_aufgabe}
        gate = self.guard.create_gate(self.w.mission_id, plan['gate']['aktion'], plan['gate']['ziel'], request_binding=plan['gate']['bindung'],
                                      risks=[e['begruendung']], rollback_available=name in ('datei_schreiben', 'datei_aendern'))
        if e['wirkt_als'] == 'frei' or via_aufgabe or via_sitzung:
            token = self.guard.approve(gate)
            von = f'aufgabe:{via_aufgabe}' if via_aufgabe else f'sitzung:{via_sitzung}' if via_sitzung else f"katalog:{e['regel']}"
            self._audit('HARNESS_APPROVED_BY', {'approved_by': von, 'werkzeug': name, 'gate_id': gate['gate_id'],
                                                'kanal': 'aufgabe' if via_aufgabe else 'sitzung' if via_sitzung else 'katalog'})     # G10
            alt = _code_vorher(self.w, name, plan)
            out = ausfuehren(self.w, self.guard, name, args, plan, token, abbruch)
            _code_nachher(self.w, name, plan, out, sitzung_id=self.sitzung_id, weg='aufgabe' if via_aufgabe else 'sitzung' if via_sitzung else 'katalog', alt=alt)
            stufe = 'aufgabe' if via_aufgabe else 'sitzung' if via_sitzung else e['stufe']
            return dict(out, stufe=stufe, regel=von if (via_aufgabe or via_sitzung) else e['regel'])
        an = 'captain'
        if e['stufe'] == 'vorarbeiter' and not e['vorbehalt'] and not warnkarte and self.vorarbeiter is not None:
            zustaendig = self.vorarbeiter.zustaendig(self.projekt_id)
            if zustaendig and zustaendig != self.sitzung_id:      # S2: in der eigenen Sitzung des Vorarbeiters wirkt `vorarbeiter` wie `captain`
                an = 'vorarbeiter'
            from ..desk import freigabeklasse                       # G9-10 (E7): Klasse H geht nie an den Vorarbeiter
            if freigabeklasse.klasse('harness_freigabe', 'erlauben', {'werkzeug': name, 'ziel': plan['ziel']}) == freigabeklasse.H:
                an = 'captain'
        vorschau_hash = hashlib.sha256(json.dumps([plan['ziel'], args, plan['vorschau']], ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')).hexdigest()
        karte = self.karten.anlegen({'sitzung_id': self.sitzung_id, 'antwort_id': antwort_id, 'werkzeug': name, 'args': args, 'ziel': plan['ziel'],
                                     'an': an, 'art': 'werkzeug', 'vorschau_hash': vorschau_hash,
                                     'stufe': e['stufe'], 'regel': e['regel'], 'begruendung': e['begruendung'], 'vorbehalt': e['vorbehalt'],
                                     'vorschau': plan['vorschau'], 'gate': gate, 'mission_id': self.w.mission_id, 'projekt': self.projekt_id,
                                     'warnung': warnung})
        self._audit('HARNESS_KARTE', {'karte_id': karte['karte_id'], 'werkzeug': name, 'ziel': plan['ziel'][:300], 'stufe': e['stufe'], 'an': an,
                                      'regel': e['regel'], 'gate_id': gate['gate_id']})
        if plan.get('code_ungesehen'):
            self._audit('HARNESS_CODE_UNGESEHEN', {'karte_id': karte['karte_id'], 'werkzeug': name, 'anzahl': len(plan['code_ungesehen']),
                                                   'zu_gross': bool(plan.get('code_zu_gross'))})
        return {'status': 'wartet', 'ergebnis': f"wartet auf Freigabe ({karte['karte_id']})", 'stufe': e['stufe'], 'regel': e['regel'],
                'wirkung': False, 'karte': oeffentlich(karte)}

    def festhalten(self, karte_id, zustand):
        """Der Zustand der Schleife an der Karte: Verlauf bis vor das Ergebnis des wartenden Aufrufs, seine ID, die übrigen Aufrufe des Zugs."""
        k = self.karten.laden(karte_id)
        k['zustand'] = zustand
        self.karten.speichern(k)


def _code_vorher(w, name, plan):
    """G4: vor dem Schreiben einer Code-Datei die vorige Fassung merken (nur für die Anzeige); liefert ihren Hash."""
    cs = getattr(w, 'code_stand', None)
    if cs is None or name not in vorbehalte.SCHREIBEN or not plan.get('code'):
        return None
    return cs.vorher_merken(plan['ziel'])


def _code_nachher(w, name, plan, out, *, sitzung_id, weg, alt=None, captain=False):
    """G4 nach der Ausführung. Schreiben: Spur; über eine Karte des Captains gilt die neue Fassung als gesehen (G4-07). Lauf/Befehl über
    eine Karte des Captains: die gebundene Liste gilt als gesehen (G4-12) – nur Dateien, deren Fassung noch die gebundene ist.
    Liefert die Zahl der Dateien, die dadurch als gesehen gelten."""
    cs = getattr(w, 'code_stand', None)
    if cs is None or not out.get('wirkung'):
        return 0
    if name in vorbehalte.SCHREIBEN and plan.get('code'):
        cs.spur(plan['ziel'], sitzung_id, weg)
        return 1 if captain and cs.schreiben_gesehen(plan['ziel'], alt) else 0
    if captain and plan.get('code_ungesehen'):
        return cs.gesehen_setzen(plan['gate']['bindung'].get('code_ungesehen'))
    return 0


def _code_zu_gross(w, karte):
    """G4-14: Ist der ungesehene Code zu groß für eine Karte, wird sie im Browser nicht freigegeben (Weg: Konsole, `guppi code-stand`)."""
    if karte.get('art') != 'werkzeug' or karte.get('werkzeug') not in code_stand_mod.AUSFUEHRUNG or getattr(w, 'code_stand', None) is None:
        return
    try:
        plan = w.vorbereiten(karte['werkzeug'], karte['args'])
    except (WerkzeugFehler, BefehlFehler):
        return                                               # der Fehler zeigt sich gleich beim Ausführen
    if plan.get('code_zu_gross'):
        konsole = getattr(w.code_stand, 'konsole', 'CODE_STAND.bat <projekt>')
        raise ValueError(f"code_zu_gross: zu viel ungesehener Code für eine Karte ({len(plan['code_ungesehen'])} Dateien) – in der Konsole "
                         f"„{konsole} --zeigen“, dann „{konsole} --uebernehmen“; danach den Aufruf wiederholen lassen")


def ausfuehren(werkzeuge, guard, name, args, plan, token, abbruch=None):
    """Führt einen freigegebenen Aufruf mit seinem Token aus. Lesen: das Token wird hier verbraucht (das Datei-Werkzeug fragt für Lesen nicht);
    Überschreiben verbraucht es `FilesystemTool.write_text`, `befehl` sein Ausführer; eine neue Datei verbraucht es hier."""
    if name in LESEN or plan['gate']['aktion'] == 'create_new_artifact':
        auth = guard.authorize(token, mission_id=werkzeuge.mission_id, action=plan['gate']['aktion'], target=plan['gate']['ziel'],
                               request_binding=plan['gate']['bindung'])
        if not auth.get('authorized'):
            return {'status': 'fehler', 'ergebnis': 'error: Token passt nicht (' + str(auth.get('reason')) + ')', 'wirkung': False}
    return werkzeuge.ausfuehren(name, args, token=token, abbruch=abbruch, plan=plan)


def _aufgabenkarte(karte, weg, notiz, aufgaben, aenderungen):
    """Antwort auf einen Vorschlag des Vorarbeiters (Kartenart `aufgabe`): nur der Captain gibt frei; er darf die Liste kürzen und Frist/Zähler setzen.
    Die Aufgabe entsteht mit `von=captain`, der Vorschlag bleibt streng geprüft."""
    if weg != 'erlauben':
        return {'status': 'abgelehnt', 'ergebnis': 'abgelehnt: ' + (str(notiz).strip() if notiz and str(notiz).strip() else 'vom Captain, ohne Begründung'), 'wirkung': False}
    doc = json.loads(json.dumps(karte['args']))
    a = aenderungen or {}
    if a.get('auswahl') is not None:
        idx = a['auswahl']
        if not isinstance(idx, list) or not idx or not all(isinstance(i, int) and 0 <= i < len(doc['erlaubt']) for i in idx):
            raise ValueError('auswahl_ungueltig')
        doc['erlaubt'] = [doc['erlaubt'][i] for i in sorted(set(idx))]
    for feld in ('bis', 'max_aufrufe'):
        if a.get(feld) is not None:
            doc['ende'][feld] = a[feld]
    neu, warnungen = aufgaben.anlegen(doc, von='captain', vorschlag_von=karte.get('vorschlag_von'), verbotene_sitzungen=(karte.get('sitzung_id'),))
    karte['aufgabe_id'] = neu['id']
    return {'status': 'ok', 'ergebnis': f"Aufgabe {neu['id']} angelegt", 'wirkung': False}


def beantworten(karten, karte_id, weg, *, notiz=None, von='captain', ueber='karte', guard, audit=None, werkzeuge_fuer, aufgaben=None, aenderungen=None):
    """Die eine Tür für Karte und Posteingang (HS-22): `erlauben` → Guard.approve → Werkzeug mit Token; `ablehnen` → Guard.reject;
    `sitzung` (P0 M1) → wie `erlauben`, dazu `erlaubnis` {werkzeug, muster} im Ergebnis – nur vom Captain, nie für Vorbehalt/Warnkarte/Aufgabe.
    `werkzeuge_fuer(karte)` liefert die Werkzeuge des Projekts der Karte. Rückgabe {karte, ergebnis, status, wirkung, erlaubnis?}."""
    if weg not in WEGE:
        raise ValueError('weg_unbekannt')
    erlaubnis = None
    if weg == 'sitzung':
        vorab = karten.laden(karte_id)
        if von != 'captain':
            raise ValueError('sitzung_nur_captain')
        if not sitzungs_erlaubnis.erlaubt_fuer_karte(vorab):
            raise ValueError('sitzung_nicht_moeglich: Vorbehalt, Warnkasten oder Aufgabe – nur einzeln erlauben')
        erlaubnis = {'werkzeug': vorab['werkzeug'], 'muster': sitzungs_erlaubnis.muster_fuer(vorab['werkzeug'], vorab['ziel']), 'regel': vorab.get('regel')}
        weg = 'erlauben'
    karte = karten.uebernehmen(karte_id)
    gate = karte.get('gate') or {}
    try:
        if karte.get('art') == 'aufgabe':
            out = _aufgabenkarte(karte, weg, notiz, aufgaben, aenderungen)
        elif weg == 'erlauben':
            w = werkzeuge_fuer(karte)
            _code_zu_gross(w, karte)                                # G4-14: vor dem Freigeben, damit nichts halb entschieden ist
            token = guard.approve(gate)
            w.kontext = {'sitzung_id': karte.get('sitzung_id'), 'antwort_id': karte.get('antwort_id'), 'karte_id': karte_id, 'aufgabe_id': None}
            try:
                plan = w.vorbereiten(karte['werkzeug'], karte['args'])
            except (WerkzeugFehler, BefehlFehler) as exc:
                out = {'status': 'fehler', 'ergebnis': f'error: {exc}', 'wirkung': False}
            else:
                # Hat sich das Ziel seit der Karte geändert, passt die Bindung nicht mehr und der Guard lehnt das Token ab (request_digest_mismatch)
                alt = _code_vorher(w, karte['werkzeug'], plan)
                out = ausfuehren(w, guard, karte['werkzeug'], karte['args'], plan, token)
                gesehen = _code_nachher(w, karte['werkzeug'], plan, out, sitzung_id=karte.get('sitzung_id'), alt=alt,
                                        weg='vorarbeiter' if str(von).startswith('vorarbeiter') else 'karte', captain=(von == 'captain' and erlaubnis is None))
                if gesehen and audit is not None and karte['werkzeug'] in code_stand_mod.AUSFUEHRUNG:
                    try:
                        audit.append('HARNESS_CODE_GESEHEN', component='harness', mission_id=karte.get('mission_id'),
                                     payload={'karte_id': karte_id, 'werkzeug': karte['werkzeug'], 'anzahl': gesehen, 'von': von, 'ueber': ueber})
                    except Exception:
                        pass
        else:
            guard.reject(gate, note=notiz)
            out = {'status': 'abgelehnt', 'ergebnis': 'abgelehnt: ' + (str(notiz).strip() if notiz and str(notiz).strip() else 'vom Captain, ohne Begründung'),
                   'wirkung': False}
    except Exception:
        karte['status'] = 'offen'                                   # nichts entschieden: die Karte bleibt offen
        karten.speichern(karte)
        raise
    karte.update(status='beantwortet', entscheidung='sitzung' if erlaubnis else weg, von=von, ueber=ueber, notiz=notiz, beantwortet=jetzt(), gate=gate,
                 ergebnis_kurz=str(out['ergebnis'])[:300], ergebnis_status=out['status'], erlaubnis=erlaubnis)
    karten.speichern(karte)
    if audit is not None:
        try:
            payload = {'karte_id': karte_id, 'weg': karte['entscheidung'], 'von': von, 'ueber': ueber, 'werkzeug': karte['werkzeug'],
                       'regel': karte.get('regel'), 'gate_id': gate.get('gate_id'), 'status': out['status']}
            if erlaubnis:
                payload['erlaubnis'] = erlaubnis
            if str(von).startswith('vorarbeiter:'):
                payload['begruendung'] = notiz                  # HS-29: die Begründung des Vorarbeiters steht im Audit
            audit.append('HARNESS_FREIGABE', component='harness', mission_id=karte.get('mission_id'), payload=payload)
        except Exception:
            pass
    return {'karte': karte, 'ergebnis': out['ergebnis'], 'status': out['status'], 'wirkung': out.get('wirkung', False), 'erlaubnis': erlaubnis}
