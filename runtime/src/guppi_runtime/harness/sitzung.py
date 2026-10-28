"""Sitzungen der Harness-Shell (G2 §3.7, HS-18): eine JSONL-Datei je Sitzung, erste Zeile Kopf, danach eine Zeile je Ereignis.

Nur anhängen, nie umschreiben. Jede Zeile wird mit `fsync` geschrieben, damit ein Absturz höchstens die letzte Zeile kostet; eine kaputte
Zeile wird beim Laden übersprungen und gezählt. Löschen verschiebt die Datei nach `geloescht/` (kein echtes Löschen, Regel des Captains).
Ablage `<projekt>/runtime_data/harness/sitzungen/` (D-E4)."""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
from datetime import datetime
from pathlib import Path

ID = re.compile(r'S-[0-9A-F]{8}')
TITEL_MAX = 60
TYPEN = ('captain', 'modell', 'werkzeug', 'karte', 'titel', 'wahl')     # `wahl`: das Modell der Sitzung wurde geändert (PATCH)


class SitzungFehler(ValueError):
    """Ein Fehler, den der Aufrufer sehen soll (unbekannte ID, falscher Eintrag) – der Text ist der Code."""


def jetzt():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def titel_aus(text):
    """Die ersten 60 Zeichen der ersten Nachricht, auf einer Zeile."""
    flach = ' '.join(str(text or '').split())
    return flach[:TITEL_MAX] if len(flach) <= TITEL_MAX else flach[:TITEL_MAX - 1].rstrip() + '…'


class Sitzungen:
    def __init__(self, ordner: Path):
        self.ordner = Path(ordner)
        self._sperren = {}
        self._sperre = threading.Lock()

    # ---- Hilfen
    def _pfad(self, sid):
        if not isinstance(sid, str) or not ID.fullmatch(sid):
            raise SitzungFehler('sitzung_unbekannt')
        return self.ordner / (sid + '.jsonl')

    def sperre(self, sid):
        """Eine Sperre je Sitzung (K3: nie hub.lock). Auch die Schleife nimmt sie, damit eine Sitzung nicht zwei Antworten zugleich hat."""
        with self._sperre:
            return self._sperren.setdefault(sid, threading.RLock())

    def _schreiben(self, pfad, eintrag, modus='a'):
        zeile = json.dumps(eintrag, ensure_ascii=False, separators=(',', ':')) + '\n'
        with open(pfad, modus, encoding='utf-8', newline='\n') as datei:
            datei.write(zeile)
            datei.flush()
            os.fsync(datei.fileno())

    # ---- öffentlich
    def anlegen(self, projekt, titel='', modell=None, mission_id=None, vorlage=None):
        self.ordner.mkdir(parents=True, exist_ok=True)
        for _ in range(20):
            sid = 'S-' + secrets.token_hex(4).upper()
            pfad = self._pfad(sid)
            kopf = {'typ': 'kopf', 'version': 1, 'id': sid, 'titel': titel_aus(titel), 'projekt': str(projekt), 'vorlage': vorlage,
                    'modell': modell, 'mission_id': mission_id, 'angelegt': jetzt()}
            try:
                self._schreiben(pfad, kopf, modus='x')        # 'x': eine schon vergebene ID wird nie überschrieben
                return kopf
            except FileExistsError:
                continue
        raise SitzungFehler('sitzung_id_nicht_frei')

    def anhaengen(self, sid, eintrag):
        if not isinstance(eintrag, dict) or eintrag.get('typ') not in TYPEN:
            raise SitzungFehler('eintrag_ungueltig')
        pfad = self._pfad(sid)
        with self.sperre(sid):
            if not pfad.is_file():
                raise SitzungFehler('sitzung_unbekannt')
            eintrag = dict(eintrag)
            eintrag.setdefault('zeit', jetzt())
            self._schreiben(pfad, eintrag)
        return eintrag

    def laden(self, sid):
        """{'kopf', 'eintraege', 'kaputt', 'titel', 'modell'} – Titel und Modell so, wie sie nach allen Änderungen gelten."""
        pfad = self._pfad(sid)
        if not pfad.is_file():
            raise SitzungFehler('sitzung_unbekannt')
        kopf, eintraege, kaputt = None, [], 0
        with self.sperre(sid):
            zeilen = pfad.read_text(encoding='utf-8', errors='replace').splitlines()
        for zeile in zeilen:
            if not zeile.strip():
                continue
            try:
                wert = json.loads(zeile)
            except ValueError:
                kaputt += 1
                continue
            if not isinstance(wert, dict):
                kaputt += 1
            elif wert.get('typ') == 'kopf' and kopf is None:
                kopf = wert
            else:
                eintraege.append(wert)
        if kopf is None:
            raise SitzungFehler('sitzung_ohne_kopf')
        titel, modell = kopf.get('titel') or '', kopf.get('modell')
        for e in eintraege:
            if e.get('typ') == 'titel': titel = str(e.get('titel') or '')
            if e.get('typ') == 'wahl' and 'modell' in e: modell = e.get('modell')
        return {'kopf': kopf, 'eintraege': eintraege, 'kaputt': kaputt, 'titel': titel, 'modell': modell}

    def liste(self, projekt=None):
        """Kopf und letzte Zeit je Sitzung, neueste zuerst; mit `projekt` nur die dieses Projekts."""
        if not self.ordner.is_dir():
            return []
        out = []
        for pfad in self.ordner.glob('S-*.jsonl'):
            if not ID.fullmatch(pfad.stem):
                continue
            try:
                s = self.laden(pfad.stem)
            except (SitzungFehler, OSError):
                continue
            if projekt is not None and s['kopf'].get('projekt') != projekt:
                continue
            zuletzt = datetime.fromtimestamp(pfad.stat().st_mtime).astimezone().isoformat(timespec='seconds')
            out.append({'id': pfad.stem, 'titel': s['titel'], 'projekt': s['kopf'].get('projekt'), 'modell': s['modell'],
                        'vorlage': s['kopf'].get('vorlage'), 'angelegt': s['kopf'].get('angelegt'), 'zuletzt': zuletzt,
                        'nachrichten': sum(1 for e in s['eintraege'] if e.get('typ') in ('captain', 'modell'))})
        out.sort(key=lambda x: x['zuletzt'] or '', reverse=True)
        return out

    def titel_aendern(self, sid, titel):
        titel = titel_aus(titel)
        if not titel:
            raise SitzungFehler('titel_leer')
        return self.anhaengen(sid, {'typ': 'titel', 'titel': titel})

    def modell_waehlen(self, sid, modell):
        return self.anhaengen(sid, {'typ': 'wahl', 'modell': (str(modell)[:200] if modell else None)})

    def loeschen(self, sid):
        """Verschiebt die Datei nach geloescht/ – nichts wird wirklich gelöscht. Gibt den neuen Ort zurück."""
        pfad = self._pfad(sid)
        with self.sperre(sid):
            if not pfad.is_file():
                raise SitzungFehler('sitzung_unbekannt')
            ziel_ordner = self.ordner / 'geloescht'
            ziel_ordner.mkdir(parents=True, exist_ok=True)
            ziel = ziel_ordner / pfad.name
            n = 1
            while ziel.exists():
                ziel = ziel_ordner / f'{pfad.stem}.{n}.jsonl'; n += 1
            os.replace(pfad, ziel)
        return ziel
