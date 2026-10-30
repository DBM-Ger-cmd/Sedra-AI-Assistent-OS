"""Aufgaben-Freigabe der Harness-Shell: Speicher, Prüfung, Zähler (SPEC_HARNESS_SHELL_v1 HS-27, HS-29; G2 Stufe 3 §4; G3 Stufe 3 N3).

Der Captain gibt für eine Aufgabe eine Liste von Aufrufen frei (Werkzeug + Muster wie im Katalog), befristet und gezählt. Innerhalb davon läuft der
Agent ohne Karte; die Deckung rechnet `aufgabe_deckung.deckt`. Eine Aufgabe hebt nie `verboten`, nie einen harten Vorbehalt, nie eine Warnkarte –
das entscheidet `freigabe.Kiste.aufruf`. Ablage `<projekt>/runtime_data/harness/aufgaben/T-<8 Hex>.json`, atomar; Ablauf und Erschöpfung stellt
`laden`/`alle` beim nächsten Zugriff fest (mit Audit), nichts wird stillschweigend verlängert.

Harness-Code (Vorbehalt): SEDRA ändert diese Datei nicht an sich selbst. Angelegt wird eine Aufgabe nur vom Captain; ein Vorschlag des Vorarbeiters
(`vorschlag=True`) wird strenger geprüft (keine weiten Muster, keine Vorarbeiter-Sitzung als Nutzer, keine Schreiben-dann-Ausführen-Kombination)."""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
from datetime import datetime, timedelta
from pathlib import Path

from . import aufgabe_deckung, vorbehalte
from .katalog import WERKZEUGE, genauigkeit, passt

ID = re.compile(r'T-[0-9A-F]{8}')
SITZUNG = re.compile(r'S-[0-9A-F]{8}')
BIS_MAX_H = 24
AUFRUFE_MAX = 500
WEIT_DATEI = 5                      # weniger Zeichen ohne Platzhalter = „weit“ (Dateimuster)
WEIT_BEFEHL = 10                    # dasselbe für Befehle
LESEN = ('datei_lesen', 'dateien_auflisten', 'suchen')
SCHREIBEN = ('datei_schreiben', 'datei_aendern')
INTERPRETER = re.compile(r'(python[0-9.]*|py|pythonw|powershell|pwsh|cmd|node|bash|sh|wscript|cscript|perl|ruby|php|deno|bun|wsl|env)')
STATUS = ('aktiv', 'erledigt', 'abgelaufen', 'erschoepft', 'zurueckgenommen')
TITEL_MAX = 120


class AufgabeFehler(ValueError):
    """Die Aufgabe ist ungültig oder die Handlung nicht erlaubt; der Text ist der Grund."""


def jetzt():
    return datetime.now().astimezone()


def _iso(z):
    return z.isoformat(timespec='seconds')


def _probe(muster):
    """Ein Beispielziel zum Muster (Platzhalter durch Zeichen ersetzt) – um zu sehen, ob der Vorbehalt das Muster trifft."""
    return muster.replace('**/', 'x/').replace('**', 'x').replace('*', 'x').replace('?', 'x')


def ist_weit(werkzeug, muster):
    """Ein Muster ohne Anker: führender Platzhalter oder zu wenig festes Stück. Lesen ist davon nicht betroffen (der Katalog regelt es)."""
    if werkzeug in LESEN:
        return False
    m = muster.strip()
    if not m or m[0] in '*?':
        return True
    return genauigkeit(m) < (WEIT_BEFEHL if werkzeug == 'befehl' else WEIT_DATEI)


def _interpreter_offen(muster):
    """Ein Befehlsmuster, das einen Interpreter beliebige Dateien ausführen lässt (`python *`, `powershell -File *` …)."""
    teile = muster.strip().casefold().split()
    if not teile or not INTERPRETER.fullmatch(teile[0].removesuffix('.exe')):
        return False
    rest = [t for t in teile[1:] if not (t.startswith('-') or (t.startswith('/') and len(t) <= 3)) and t != '*']      # Schalter wie -File und /c
    return not rest or muster.strip().casefold().startswith(teile[0] + ' *')


def pruefen_neu(doc, *, jetzt_z=None, vorschlag=False, verbotene_sitzungen=()):
    """(aufgabe, warnungen) aus einer Eingabe – oder AufgabeFehler. `vorschlag`: strengere Regeln für einen Vorschlag des Vorarbeiters (S4, S9)."""
    jetzt_z = jetzt_z or jetzt()
    if not isinstance(doc, dict):
        raise AufgabeFehler('aufgabe_ungueltig')
    titel = doc.get('titel')
    if not isinstance(titel, str) or not titel.strip():
        raise AufgabeFehler('titel_fehlt')
    projekt = doc.get('projekt')
    if not isinstance(projekt, str) or not projekt.strip():
        raise AufgabeFehler('projekt_fehlt')
    sitzungen = doc.get('sitzungen')
    if not isinstance(sitzungen, list) or not sitzungen or not all(isinstance(s, str) and SITZUNG.fullmatch(s) for s in sitzungen):
        raise AufgabeFehler('sitzungen_fehlen: mindestens eine Sitzungs-ID (S-…)')
    if vorschlag and set(sitzungen) & set(verbotene_sitzungen):
        raise AufgabeFehler('selbstfreigabe: ein Vorschlag darf die Vorarbeiter-Sitzung nicht als Nutzer enthalten')
    erlaubt = doc.get('erlaubt')
    if not isinstance(erlaubt, list) or not erlaubt:
        raise AufgabeFehler('erlaubt_fehlt: mindestens ein Eintrag {werkzeug, muster}')
    eintraege, warnungen = [], []
    for n, e in enumerate(erlaubt, 1):
        if not isinstance(e, dict) or e.get('werkzeug') not in WERKZEUGE or not isinstance(e.get('muster'), str) or not e['muster'].strip():
            raise AufgabeFehler(f'erlaubt_{n}_ungueltig: werkzeug aus {", ".join(WERKZEUGE)} und ein muster')
        w, m = e['werkzeug'], e['muster'].strip()
        if w != 'befehl' and w not in ('lauf_starten', 'lauf_stoppen', 'modell_laden', 'modell_entladen') and \
                ('..' in m.replace('\\', '/').split('/') or re.match(r'^([A-Za-z]:|/)', m)):
            raise AufgabeFehler(f'erlaubt_{n}_muster_ausserhalb: relativ zur Projektwurzel, ohne „..“')
        if ist_weit(w, m):
            if vorschlag:
                raise AufgabeFehler(f'erlaubt_{n}_muster_weit: „{m}“ ist zu weit für einen Vorschlag (nur der Captain trägt so etwas ein)')
            warnungen.append(f'weites Muster: {w} „{m}“')
        if w in SCHREIBEN + ('befehl',) and vorbehalte.pruefen(w, _probe(m), {'inhalt': 'x'}):
            if vorschlag:
                raise AufgabeFehler(f'erlaubt_{n}_vorbehalt: „{m}“ trifft einen festen Captain-Vorbehalt und würde nie gelten')
            warnungen.append(f'trifft einen Vorbehalt und gilt nie: {w} „{m}“')
        eintraege.append({'werkzeug': w, 'muster': m})
    if any(e['werkzeug'] in SCHREIBEN for e in eintraege) and any(e['werkzeug'] == 'befehl' and _interpreter_offen(e['muster']) for e in eintraege):
        text = 'S9: Schreiben und beliebige Ausführung in einer Aufgabe (ein Agent könnte Geschriebenes ausführen)'
        if vorschlag:
            raise AufgabeFehler(text)
        warnungen.append(text)
    modelle = doc.get('modelle') or []
    if not isinstance(modelle, list) or not all(isinstance(x, str) and x.strip() for x in modelle):
        raise AufgabeFehler('modelle_ungueltig: eine Liste von Rezept-IDs')
    ende = doc.get('ende')
    if not isinstance(ende, dict) or (ende.get('bis') is None and ende.get('max_aufrufe') is None):
        raise AufgabeFehler('ende_fehlt: mindestens eins von „bis“ und „max_aufrufe“ (D-G4)')
    out_ende = {'bei_erledigt': bool(ende.get('bei_erledigt', True))}
    if ende.get('bis') is not None:
        try:
            bis = datetime.fromisoformat(str(ende['bis']))
        except ValueError:
            raise AufgabeFehler('bis_ungueltig: ISO-Zeitpunkt mit Zeitzone') from None
        if bis.tzinfo is None:
            raise AufgabeFehler('bis_ungueltig: ISO-Zeitpunkt mit Zeitzone')
        if bis <= jetzt_z:
            raise AufgabeFehler('bis_vergangen')
        if bis > jetzt_z + timedelta(hours=BIS_MAX_H):
            raise AufgabeFehler(f'bis_zu_weit: höchstens {BIS_MAX_H} Stunden ab jetzt')
        out_ende['bis'] = _iso(bis)
    if ende.get('max_aufrufe') is not None:
        mx = ende['max_aufrufe']
        if not isinstance(mx, int) or isinstance(mx, bool) or not 1 <= mx <= AUFRUFE_MAX:
            raise AufgabeFehler(f'max_aufrufe_ungueltig: 1 bis {AUFRUFE_MAX}')
        out_ende['max_aufrufe'] = mx
    wunsch = doc.get('wunsch_id')
    return {'titel': titel.strip()[:TITEL_MAX], 'projekt': projekt.strip(), 'sitzungen': list(dict.fromkeys(sitzungen)), 'erlaubt': eintraege,
            'modelle': list(dict.fromkeys(m.strip() for m in modelle)), 'ende': out_ende,
            'wunsch_id': wunsch if isinstance(wunsch, str) else None}, warnungen


def _bis_zeit(wert):
    """Das Ende als Zeitpunkt mit Zeitzone – oder None (kein Ende, nicht lesbar). Nur für die Anzeige; über die Geltung entscheidet `aufgabe_deckung.zustand`."""
    try:
        z = datetime.fromisoformat(wert) if isinstance(wert, str) else wert
    except ValueError:
        return None
    return z if isinstance(z, datetime) and z.tzinfo is not None else None


def oeffentlich(a, jetzt_z=None):
    """Die Aufgabe für Oberfläche und Schild: mit Rest an Aufrufen und Minuten."""
    jetzt_z = jetzt_z or jetzt()
    out = dict(a)
    mx = (a.get('ende') or {}).get('max_aufrufe')
    out['rest_aufrufe'] = None if mx is None else max(0, mx - int(a.get('aufrufe') or 0))
    bis = _bis_zeit((a.get('ende') or {}).get('bis'))
    out['rest_min'] = None if bis is None else max(0, int((bis - jetzt_z).total_seconds() // 60))
    return out


class Aufgaben:
    """Ablage der Aufgaben: eine Datei je Aufgabe, atomar geschrieben, eine Sperre für Zähler und Statuswechsel."""

    def __init__(self, ordner: Path, audit=None, melden=None):
        """`audit(event, payload)` und `melden(name, daten)` sind Rückrufe (beide optional)."""
        self.ordner = Path(ordner)
        self.audit, self.melden = audit, melden
        self._sperre = threading.RLock()

    # ---- Hilfen
    def _pfad(self, tid):
        if not isinstance(tid, str) or not ID.fullmatch(tid):
            raise KeyError('aufgabe_unbekannt')
        return self.ordner / (tid + '.json')

    def _speichern(self, a):
        self.ordner.mkdir(parents=True, exist_ok=True)
        pfad = self._pfad(a['id'])
        tmp = pfad.with_suffix('.tmp')
        tmp.write_text(json.dumps(a, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, pfad)
        return a

    def _roh(self, tid):
        pfad = self._pfad(tid)
        if not pfad.is_file():
            raise KeyError('aufgabe_unbekannt')
        return json.loads(pfad.read_text(encoding='utf-8'))

    def _sagen(self, event, a, extra=None):
        payload = {'aufgabe_id': a['id'], 'titel': a.get('titel'), 'status': a.get('status')} | (extra or {})
        if self.audit is not None:
            try: self.audit(event, payload)
            except Exception: pass
        if self.melden is not None:
            try: self.melden('harness.aufgabe', {'id': a['id'], 'zustand': a.get('status')})
            except Exception: pass

    def _aktuell(self, a, jetzt_z):
        """Wendet Ablauf und Erschöpfung an (mit Audit) und gibt die Aufgabe zurück."""
        neu = aufgabe_deckung.zustand(a, jetzt_z)
        if neu != a.get('status') and neu in STATUS:
            a = dict(a, status=neu, beendet=_iso(jetzt_z), grund={'abgelaufen': 'Frist abgelaufen', 'erschoepft': 'alle Aufrufe verbraucht'}.get(neu))
            self._speichern(a)
            self._sagen('HARNESS_AUFGABE_ABGELAUFEN' if neu == 'abgelaufen' else 'HARNESS_AUFGABE_ERSCHOEPFT', a)
        return a

    # ---- Anlegen, Lesen
    def anlegen(self, doc, *, von='captain', vorschlag_von=None, jetzt_z=None, verbotene_sitzungen=()):
        """Legt eine Aufgabe an. `von` kommt vom Server; ein Vorschlag (vorschlag_von gesetzt) wird streng geprüft. Gibt (aufgabe, warnungen) zurück."""
        jetzt_z = jetzt_z or jetzt()
        a, warnungen = pruefen_neu(doc, jetzt_z=jetzt_z, vorschlag=bool(vorschlag_von), verbotene_sitzungen=verbotene_sitzungen)
        with self._sperre:
            while True:
                tid = 'T-' + secrets.token_hex(4).upper()
                if not self._pfad(tid).exists():
                    break
            a = dict(a, version=1, id=tid, von=von, vorschlag_von=vorschlag_von, status='aktiv', aufrufe=0, angelegt=_iso(jetzt_z), zuletzt=None,
                     beendet=None, grund=None, warnungen=warnungen)
            self._speichern(a)
        self._sagen('HARNESS_AUFGABE_ANGELEGT', a, {'von': von, 'vorschlag_von': vorschlag_von, 'erlaubt': a['erlaubt'], 'ende': a['ende'], 'warnungen': warnungen})
        return a, warnungen

    def laden(self, tid, jetzt_z=None):
        with self._sperre:
            return self._aktuell(self._roh(tid), jetzt_z or jetzt())

    def alle(self, status=None, jetzt_z=None):
        jetzt_z = jetzt_z or jetzt()
        if not self.ordner.is_dir():
            return []
        out = []
        with self._sperre:
            for p in sorted(self.ordner.glob('T-*.json')):
                try:
                    a = self._aktuell(json.loads(p.read_text(encoding='utf-8')), jetzt_z)
                except (OSError, ValueError, KeyError):
                    continue
                if status is None or a.get('status') == status:
                    out.append(a)
        return sorted(out, key=lambda a: a.get('angelegt') or '')

    # ---- Deckung und Zähler
    def deckt(self, sitzung_id, werkzeug, ziel, *, weich=None, jetzt_z=None):
        """{aufgabe_id, eintrag} der deckenden Aufgabe – oder None. `weich` (aus vorbehalte.pruefen_weich): nur eine Aufgabe, die das Modell nennt, deckt."""
        jetzt_z = jetzt_z or jetzt()
        aktive = self.alle('aktiv', jetzt_z)
        if weich:
            aktive = [a for a in aktive if weich.get('modell') in (a.get('modelle') or [])]
        return aufgabe_deckung.deckt(aktive, sitzung_id, werkzeug, ziel, jetzt_z, passt)

    def zaehlen(self, tid, jetzt_z=None):
        """Verbraucht einen Aufruf der Aufgabe (unter Sperre). False, wenn sie nicht mehr aktiv ist oder ihr Zähler erreicht ist – dann gilt die normale Einstufung."""
        jetzt_z = jetzt_z or jetzt()
        with self._sperre:
            a = self._aktuell(self._roh(tid), jetzt_z)
            if a.get('status') != 'aktiv':
                return False
            a = dict(a, aufrufe=int(a.get('aufrufe') or 0) + 1, zuletzt=_iso(jetzt_z))
            self._speichern(a)
            self._aktuell(a, jetzt_z)                    # die letzte Verwendung macht sie sofort „erschoepft“
            return True

    # ---- Beenden und Zurücknehmen
    def beenden(self, tid, grund, *, wer='captain', jetzt_z=None):
        """Schließt eine aktive Aufgabe als `erledigt`. Der Captain immer; jeder andere nur, wenn `ende.bei_erledigt` gesetzt ist (Beenden verengt nur)."""
        jetzt_z = jetzt_z or jetzt()
        with self._sperre:
            a = self._aktuell(self._roh(tid), jetzt_z)
            if a.get('status') != 'aktiv':
                raise AufgabeFehler('nicht_aktiv')
            if wer != 'captain' and not (a.get('ende') or {}).get('bei_erledigt'):
                raise AufgabeFehler('beenden_nicht_erlaubt: die Aufgabe lässt sich nur vom Captain beenden')
            a = dict(a, status='erledigt', beendet=_iso(jetzt_z), grund=str(grund or '')[:300] or 'erledigt')
            self._speichern(a)
        self._sagen('HARNESS_AUFGABE_BEENDET', a, {'wer': wer})
        return a

    def zuruecknehmen(self, tid, grund=None, *, jetzt_z=None):
        """Rücknahme durch den Captain (HS-29): ab dem nächsten Aufruf gilt wieder die normale Einstufung."""
        jetzt_z = jetzt_z or jetzt()
        with self._sperre:
            a = self._aktuell(self._roh(tid), jetzt_z)
            if a.get('status') != 'aktiv':
                raise AufgabeFehler('nicht_aktiv')
            a = dict(a, status='zurueckgenommen', beendet=_iso(jetzt_z), grund=str(grund or '')[:300] or 'vom Captain zurückgenommen')
            self._speichern(a)
        self._sagen('HARNESS_AUFGABE_ZURUECKGENOMMEN', a)
        return a
