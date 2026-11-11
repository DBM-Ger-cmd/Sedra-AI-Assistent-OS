"""Abnahme vor Wirkung für die Oberfläche (SPEC_APPS_v1_O3PLUS_G9_G2 §2.3 G2 und §2.6 G7): Code der Oberfläche, den die Harness geschrieben hat, wirkt erst, wenn der Captain ihn übernimmt.

Der laufende Server liefert alles unter `uix/` bei jeder Anfrage von der Platte aus – was die Harness dort schreibt, läuft sofort in der Seite des Captains. Dieser Baustein hält
deshalb die **bestätigte Fassung** jeder geänderten Datei zurück (Inhalt in der Ablage, Hash im Stand) und liefert sie aus, bis die Änderung übernommen ist.
Die Ablage liegt unter `runtime_data/harness/oberflaeche/` (harter Vorbehalt: das Modell kann sie nicht schreiben):
  stand.json   {schema, dateien: {rel: {bestaetigt_sha, sitzung, aufgabe, zeit}}, uebernahmen: [U-…]}
  inhalt/<sha> der Inhalt jeder bestätigten (alten) Fassung, höchstens 1 MB
  verworfen/<zeit>/<rel>  neue Dateien, die ein Zurücksetzen oder Zurücknehmen von der Platte nimmt – gelöscht wird nichts

Reiner Baustein: Wege, Hashes, Dateien. Wer ihn ruft (Karte, Konsole, Server), entscheidet über Klasse H und Kanal; hier steht nur, was dann geschieht. Alle Dateien und der Stand werden atomar geschrieben."""
from __future__ import annotations

import difflib
import hashlib
import os
import threading
from datetime import datetime
from pathlib import Path

from ..core.util import atomic_write_json
from ..desk.install import HINWEIS_SATZ, hinweise_im_diff

SCHEMA = 1
INHALT_MAX = 1_000_000            # wie VORHER_MAX des Code-Stands (G2-08): größere Dateien werden nicht zurückgehalten, die Schreibaktion wird zur Karte
UEBERNAHMEN_MAX = 20              # so viele Übernahmen bleiben zum Zurücknehmen
KARTE_DATEIEN_MAX = 30            # G2-06: wie die G4-Karte
KARTE_ZEILEN_MAX = 2000


def jetzt():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def sha(daten: bytes) -> str:
    return hashlib.sha256(daten).hexdigest()


class Oberflaeche:
    def __init__(self, ablage, uix_wurzel, *, audit=None, uhr=jetzt):
        self.ablage = Path(ablage)
        self.uix = Path(uix_wurzel).resolve()
        self.audit = audit
        self.uhr = uhr
        self.lock = threading.RLock()

    # ---- Pfade und Stand
    def rel(self, pfad):
        """Der Pfad relativ zum `uix/`-Ordner des laufenden Programms (mit `/`), sonst None – nur dort liefert der Server aus (G2-02)."""
        try:
            return Path(pfad).resolve().relative_to(self.uix).as_posix()
        except (ValueError, OSError):
            return None

    def _stand_datei(self):
        return self.ablage / 'stand.json'

    def stand(self):
        import json
        try:
            d = json.loads(self._stand_datei().read_text(encoding='utf-8'))
        except (OSError, ValueError):
            d = {}
        d = d if isinstance(d, dict) else {}
        dateien = d.get('dateien') if isinstance(d.get('dateien'), dict) else {}
        uebernahmen = d.get('uebernahmen') if isinstance(d.get('uebernahmen'), list) else []
        return {'schema': SCHEMA, 'dateien': dateien, 'uebernahmen': uebernahmen}

    def _speichern(self, d):
        self.ablage.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._stand_datei(), d)

    def _inhalt_pfad(self, s):
        return self.ablage / 'inhalt' / s

    def _inhalt_merken(self, daten: bytes):
        s = sha(daten)
        ziel = self._inhalt_pfad(s)
        if not ziel.exists():
            ziel.parent.mkdir(parents=True, exist_ok=True)
            tmp = ziel.with_name(ziel.name + '.tmp')
            tmp.write_bytes(daten)
            os.replace(tmp, ziel)
        return s

    def _inhalt_lesen(self, s):
        try:
            return self._inhalt_pfad(s).read_bytes()
        except OSError:
            return None

    def _melden(self, event, payload):
        if self.audit:
            try:
                self.audit(event, payload)
            except Exception:                    # das Audit darf eine Übernahme nie verhindern
                pass

    # ---- G2-01: zurückhalten
    def zurueckhalten(self, pfad, sitzung=None, aufgabe=None):
        """Vor dem Schreiben unter einer Aufgabe: merkt die bestätigte Fassung der Datei. Rückgabe: True (zurückgehalten, auch schon vorher), False (nicht unter `uix/`) oder
        None (zu groß für die Ablage – die Schreibaktion wird zur Karte). Weitere Schreibvorgänge an derselben Datei ändern die gemerkte Fassung nicht."""
        rel = self.rel(pfad)
        if rel is None:
            return False
        with self.lock:
            d = self.stand()
            if rel in d['dateien']:
                return True
            p = Path(pfad)
            if p.is_file():
                if p.stat().st_size > INHALT_MAX:
                    return None
                alt = self._inhalt_merken(p.read_bytes())
            else:
                alt = None                       # neue Datei: bestätigt ist „es gab sie nicht“
            d['dateien'][rel] = {'bestaetigt_sha': alt, 'sitzung': sitzung, 'aufgabe': aufgabe, 'zeit': self.uhr()}
            self._speichern(d)
        self._melden('HARNESS_OBERFLAECHE_ZURUECKGEHALTEN', {'datei': rel, 'neu': alt is None, 'aufgabe': aufgabe})
        return True

    # ---- G2-03: ausliefern
    def gehalten(self, pfad):
        """(True, bytes|None) – die bestätigte Fassung, die der Server statt der Platte liefert (None = neu, also 404) – oder (False, None), wenn die Datei nicht zurückgehalten ist."""
        rel = self.rel(pfad)
        if rel is None:
            return False, None
        e = self.stand()['dateien'].get(rel)
        if e is None:
            return False, None
        s = e.get('bestaetigt_sha')
        return True, (self._inhalt_lesen(s) if s else None)

    def gehalten_rel(self, rel):
        e = self.stand()['dateien'].get(rel)
        if e is None:
            return False, None
        s = e.get('bestaetigt_sha')
        return True, (self._inhalt_lesen(s) if s else None)

    # ---- Ansicht
    def _jetzt_sha(self, rel):
        p = self.uix / rel
        try:
            return sha(p.read_bytes()) if p.is_file() else None
        except OSError:
            return None

    def liste(self):
        """Die zurückgehaltenen Dateien: {rel, neu, geloescht, bestaetigt_sha, sha_jetzt, sitzung, aufgabe, zeit, geaendert}. `geaendert` = die Platte weicht von der bestätigten Fassung ab."""
        out = []
        for rel, e in sorted(self.stand()['dateien'].items()):
            jetzt_sha = self._jetzt_sha(rel)
            out.append({'rel': rel, 'neu': e.get('bestaetigt_sha') is None, 'geloescht': jetzt_sha is None and e.get('bestaetigt_sha') is not None,
                        'bestaetigt_sha': e.get('bestaetigt_sha'), 'sha_jetzt': jetzt_sha, 'sitzung': e.get('sitzung'), 'aufgabe': e.get('aufgabe'), 'zeit': e.get('zeit'),
                        'geaendert': jetzt_sha != e.get('bestaetigt_sha')})
        return out

    def bindung(self, liste=None):
        """Woran eine Übernahme gebunden ist: genau diese Dateien in genau dieser Fassung ([rel, sha_jetzt])."""
        return [[e['rel'], e['sha_jetzt']] for e in (liste if liste is not None else self.liste()) if e['geaendert']]

    def vorschau(self, liste=None, hinweise=None):
        """G2-06: je Datei der vollständige Diff bestätigt → jetzt (unified), begrenzt auf KARTE_DATEIEN_MAX Dateien und KARTE_ZEILEN_MAX Zeilen. `hinweise(zeilen) -> zeilen` (G3) markiert hinzukommende Zeilen.
        Rückgabe: (text, zu_gross) – zu_gross heißt: nur über die Konsole übernehmen (G7-04)."""
        liste = [e for e in (liste if liste is not None else self.liste()) if e['geaendert']]
        hinweise = hinweise if hinweise is not None else hinweise_im_diff                  # G3-02: Hinweise sind Teil der Sammelkarte
        zu_gross = len(liste) > KARTE_DATEIEN_MAX
        teile, zeilen_summe = [HINWEIS_SATZ], 0
        for e in liste[:KARTE_DATEIEN_MAX]:
            alt = self._text(self._inhalt_lesen(e['bestaetigt_sha'])) if e['bestaetigt_sha'] else ''
            neu = self._text((self.uix / e['rel']).read_bytes()) if e['sha_jetzt'] else ''
            if alt is None or neu is None:
                teile.append(f"--- {e['rel']} (keine Textdatei: {'neu' if e['neu'] else 'geändert'}, Vorschau nicht möglich)")
                continue
            diff = list(difflib.unified_diff(alt.splitlines(), neu.splitlines(), 'bestätigt/' + e['rel'], 'jetzt/' + e['rel'], lineterm='', n=2))
            if hinweise is not None:
                diff = hinweise(diff)
            if zeilen_summe + len(diff) > KARTE_ZEILEN_MAX:
                zu_gross = True
                teile.append(f"--- {e['rel']} (Diff nicht mehr gezeigt: über {KARTE_ZEILEN_MAX} Zeilen – über die Konsole ansehen)")
                continue
            zeilen_summe += len(diff)
            teile.append('\n'.join(diff) if diff else f"--- {e['rel']} (Inhalt gleich, nur der Name oder das Zeitstempel änderte sich)")
        return '\n'.join(teile), zu_gross

    @staticmethod
    def _text(daten):
        if daten is None:
            return None
        try:
            return daten.decode('utf-8')
        except UnicodeDecodeError:
            return None

    # ---- G2-07: übernehmen, zurücksetzen
    def uebernehmen(self, bindung, kanal='seite', gesehen=None):
        """Für jede gebundene Datei, deren Fassung noch stimmt, endet das Zurückhalten. Es entsteht ein Übernahme-Satz `U-…` mit alter und neuer Fassung (G7-01). `gesehen(rel_liste)`
        bekommt die übernommenen Pfade (der Aufrufer setzt Code-Dateien im Code-Stand auf gesehen). Rückgabe: {u, uebernommen: [rel], veraltet: [rel]} – `veraltet`: die Datei hat sich nach der Karte geändert."""
        uebernommen, veraltet, saetze = [], [], []
        with self.lock:
            d = self.stand()
            for rel, erwartet in bindung:
                e = d['dateien'].get(rel)
                if e is None:
                    continue
                if self._jetzt_sha(rel) != erwartet:
                    veraltet.append(rel)
                    continue
                saetze.append({'rel': rel, 'alt_sha': e.get('bestaetigt_sha'), 'neu_sha': erwartet})
                del d['dateien'][rel]
                uebernommen.append(rel)
            u = None
            if saetze:
                u = 'U-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + sha(repr(saetze).encode())[:4]
                d['uebernahmen'].append({'id': u, 'zeit': self.uhr(), 'dateien': saetze, 'kanal': kanal})
                d['uebernahmen'] = d['uebernahmen'][-UEBERNAHMEN_MAX:]
            self._speichern(d)
        if u and gesehen:
            gesehen(uebernommen)
        if u:
            self._melden('HARNESS_OBERFLAECHE_UEBERNOMMEN', {'u': u, 'dateien': len(uebernommen), 'kanal': kanal})
        return {'u': u, 'uebernommen': uebernommen, 'veraltet': veraltet}

    def _wiederherstellen(self, rel, alt_sha, zeit):
        """Die Platte auf die alte Fassung bringen; war die Datei neu, wandert sie nach verworfen/ (gelöscht wird nichts). Rückgabe: 'hergestellt' | 'verworfen' | 'inhalt_fehlt'."""
        ziel = self.uix / rel
        if alt_sha is None:
            if ziel.is_file():
                weg = self.ablage / 'verworfen' / zeit / rel
                weg.parent.mkdir(parents=True, exist_ok=True)
                os.replace(ziel, weg)
            return 'verworfen'
        daten = self._inhalt_lesen(alt_sha)
        if daten is None:
            return 'inhalt_fehlt'
        ziel.parent.mkdir(parents=True, exist_ok=True)
        tmp = ziel.with_name(ziel.name + '.sedra-tmp')
        tmp.write_bytes(daten)
        os.replace(tmp, ziel)
        return 'hergestellt'

    def zuruecksetzen(self, kanal='seite'):
        """Alle zurückgehaltenen Dateien auf die bestätigte Fassung; neue Dateien nach verworfen/<zeit>/. Rückgabe: {hergestellt, verworfen, fehlt}."""
        zeit = datetime.now().strftime('%Y%m%d-%H%M%S')
        erg = {'hergestellt': [], 'verworfen': [], 'fehlt': []}
        with self.lock:
            d = self.stand()
            for rel, e in list(d['dateien'].items()):
                r = self._wiederherstellen(rel, e.get('bestaetigt_sha'), zeit)
                if r == 'inhalt_fehlt':
                    erg['fehlt'].append(rel)
                    continue
                erg['hergestellt' if r == 'hergestellt' else 'verworfen'].append(rel)
                del d['dateien'][rel]
            self._speichern(d)
        self._melden('HARNESS_OBERFLAECHE_ZURUECKGESETZT', {'hergestellt': len(erg['hergestellt']), 'verworfen': len(erg['verworfen']), 'kanal': kanal})
        return erg

    # ---- G7-02: eine Übernahme zurücknehmen
    def uebernahmen(self):
        return list(reversed(self.stand()['uebernahmen']))

    def zuruecknehmen(self, u, kanal='seite', gesehen=None):
        """Stellt je Datei die alte Fassung wieder her, wenn die Datei noch die übernommene Fassung hat; sonst bleibt sie und wird genannt (`seit_der_uebernahme_geaendert`).
        Rückgabe: {u, hergestellt, verworfen, geaendert, fehlt}; unbekannte Übernahme → ValueError."""
        zeit = datetime.now().strftime('%Y%m%d-%H%M%S')
        erg = {'u': u, 'hergestellt': [], 'verworfen': [], 'geaendert': [], 'fehlt': []}
        with self.lock:
            d = self.stand()
            satz = next((x for x in d['uebernahmen'] if x.get('id') == u), None)
            if satz is None:
                raise ValueError('uebernahme_unbekannt')
            for f in satz['dateien']:
                if self._jetzt_sha(f['rel']) != f['neu_sha']:
                    erg['geaendert'].append(f['rel'])                      # seit_der_uebernahme_geaendert
                    continue
                r = self._wiederherstellen(f['rel'], f['alt_sha'], zeit)
                if r == 'inhalt_fehlt':
                    erg['fehlt'].append(f['rel'])
                else:
                    erg['hergestellt' if r == 'hergestellt' else 'verworfen'].append(f['rel'])
            d['uebernahmen'] = [x for x in d['uebernahmen'] if x.get('id') != u]
            self._speichern(d)
        if gesehen and (erg['hergestellt']):
            gesehen(erg['hergestellt'])                                    # die alten Fassungen gelten als gesehen
        self._melden('HARNESS_OBERFLAECHE_ZURUECK', {'u': u, 'dateien': len(erg['hergestellt']) + len(erg['verworfen']), 'geaendert': len(erg['geaendert']), 'kanal': kanal})
        return erg
