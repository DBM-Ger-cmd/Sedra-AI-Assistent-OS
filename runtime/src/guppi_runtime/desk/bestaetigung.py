"""Bestätigungen außerhalb des Browsers für Freigaben der Klasse H (SPEC_APPS_v1_O3PLUS_G9_G2 G9-02, G9-04).

Kommt eine Freigabe der Klasse H über die Seite, führt der Server sie nicht aus. Er legt hier eine Bestätigung `B-…` an, die die
ursprüngliche Ausführung als Funktion hält, und wartet auf ein Ja über den Systemdialog oder die Konsole. Nur im Speicher des Servers:
Nach einem Neustart gibt es keine offenen Bestätigungen mehr, die Entscheidungen bleiben offen (E10). Frist 10 Minuten.
Prüfstelle (O3-02): Änderungen nur durch Claude mit Freigabe des Captains."""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time

FRIST_S = 600


class BestaetigungFehler(ValueError):
    pass


def bindung_hash(binding):
    return hashlib.sha256(json.dumps(binding, ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')).hexdigest()


class Bestaetigungen:
    def __init__(self, uhr=time.monotonic):
        self._offen = {}
        self._sperre = threading.Lock()
        self._uhr = uhr

    def anlegen(self, *, art, id, weg, binding, text, ausfuehren, aktuell=None):
        """`ausfuehren()` ist der heutige Code der Stelle; `aktuell()` liefert die Bindung der Entscheidung, wie sie jetzt ist (None: weg)."""
        with self._sperre:
            for bid, b in list(self._offen.items()):            # eine neue Antwort auf dieselbe Entscheidung ersetzt die alte Bestätigung
                if (b['art'], b['id'], b['weg']) == (art, id, weg):
                    self._offen.pop(bid)
            bid = 'B-' + secrets.token_hex(4).upper()
            self._offen[bid] = {'bid': bid, 'art': art, 'id': id, 'weg': weg, 'hash': bindung_hash(binding), 'text': text,
                                'ausfuehren': ausfuehren, 'aktuell': aktuell, 'angelegt': self._uhr(), 'zeit': time.time()}
            return bid

    def _abgelaufen(self, b):
        return self._uhr() - b['angelegt'] > FRIST_S

    def offen(self):
        """[{bid, art, id, weg, text, rest_s}] – ohne die Funktionen."""
        with self._sperre:
            for bid in [k for k, b in self._offen.items() if self._abgelaufen(b)]:
                self._offen.pop(bid)
            return [{'bid': b['bid'], 'art': b['art'], 'id': b['id'], 'weg': b['weg'], 'text': b['text'],
                     'rest_s': max(0, int(FRIST_S - (self._uhr() - b['angelegt'])))} for b in self._offen.values()]

    def nehmen(self, bid):
        """Entnimmt die Bestätigung und prüft Frist und Bindung. Gibt den Eintrag mit `ausfuehren` zurück."""
        with self._sperre:
            b = self._offen.pop(str(bid or ''), None)
        if b is None:
            raise BestaetigungFehler('bestaetigung_unbekannt')
        if self._abgelaufen(b):
            raise BestaetigungFehler('bestaetigung_abgelaufen')
        if b['aktuell'] is not None:
            jetzt = b['aktuell']()
            if jetzt is None or bindung_hash(jetzt) != b['hash']:
                raise BestaetigungFehler('bestaetigung_hinfaellig')          # schon beantwortet oder geändert
        return b

    def verwerfen(self, bid):
        with self._sperre:
            return self._offen.pop(str(bid or ''), None) is not None
