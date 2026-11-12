"""Die Daten des SEDRA-Eigenablaufs: lokale Tabellen (Ersatz für n8n „Data table“) und hochgeladene Eingabedateien.

Alles liegt unter runtime_data/ des Projekts; Namen kommen nie als Pfad von außen (nur als Schlüssel), Schreiben ist atomar."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
from pathlib import Path

from ..core.util import utcnow

MAX_ZEILEN = 20000
MAX_BYTES = 8_000_000
MAX_EINGABE = 5_000_000
UMLAUTE = str.maketrans({'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss', 'Ä': 'ae', 'Ö': 'oe', 'Ü': 'ue'})


def _slug(name):
    return re.sub(r'[^a-z0-9]+', '-', str(name).translate(UMLAUTE).lower()).strip('-')[:80]


def _kurz(name):
    """Nur ASCII-Buchstaben und Ziffern: n8n-Exporte verlieren Umlaute in Tabellennamen („Kosten bersicht“), so finden beide Schreibweisen dieselbe Tabelle."""
    return re.sub(r'[^a-z0-9]+', '', str(name).lower())


def _fest(path):
    for teil in (path.parent.parent, path.parent, path):
        if teil.is_symlink():
            raise ValueError('tabelle_symlink_abgelehnt')


def _schreiben(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    _fest(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix='.tmp-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _gleich(a, b):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _vergleich(wert, art, ziel):
    if art in ('eq', 'equals', None):
        return _gleich(wert, ziel)
    if art in ('neq', 'notEquals'):
        return not _gleich(wert, ziel)
    try:
        a, b = float(wert), float(ziel)
    except (TypeError, ValueError):
        return False
    return {'gt': a > b, 'gte': a >= b, 'lt': a < b, 'lte': a <= b}.get(art, False)


class Tabellen:
    def __init__(self, project):
        self.root = Path(project).resolve() / 'runtime_data' / 'workflow_tabellen'

    def _datei(self, name):
        slug = _slug(name)
        if not slug:
            raise ValueError('tabelle_name_ungueltig')
        return self.root / (slug + '.json')

    def _alle(self):
        if not self.root.is_dir():
            return []
        out = []
        for pfad in sorted(self.root.glob('*.json')):
            try:
                out.append((pfad, json.loads(pfad.read_text(encoding='utf-8'))))
            except (OSError, ValueError):
                continue
        return out

    def _finden(self, name):
        """Die vorhandene Tabelle zu einem Namen (gleicher Schlüssel oder gleiche Kurzform), sonst None."""
        ziel, kurz = _slug(name), _kurz(name)
        for pfad, doc in self._alle():
            if pfad.stem == ziel or _kurz(doc.get('name', '')) == kurz:
                return pfad, doc
        return None

    def liste(self):
        return [{'name': d.get('name'), 'zeilen': len(d.get('zeilen', [])), 'spalten': d.get('spalten', []), 'geaendert': d.get('geaendert')} for _, d in self._alle()]

    def lesen(self, name, limit=200):
        gefunden = self._finden(name)
        if not gefunden:
            raise ValueError('tabelle_nicht_gefunden')
        doc = gefunden[1]
        return {'name': doc['name'], 'spalten': doc.get('spalten', []), 'zeilen': doc.get('zeilen', [])[:limit], 'anzahl': len(doc.get('zeilen', []))}

    def _speichern(self, pfad, doc):
        doc['geaendert'] = utcnow()
        text = json.dumps(doc, ensure_ascii=False, allow_nan=False, indent=1)
        if len(text.encode('utf-8')) > MAX_BYTES or len(doc['zeilen']) > MAX_ZEILEN:
            raise ValueError('tabelle_zu_gross')
        _schreiben(pfad, text)

    def _doc(self, name):
        gefunden = self._finden(name)
        if gefunden:
            return gefunden
        return self._datei(name), {'name': str(name)[:80], 'spalten': [], 'zeilen': [], 'naechste_id': 1}

    def importieren(self, name, text, art='auto', ersetzen=True):
        """CSV (Semikolon oder Komma) oder JSON (Liste von Objekten) in eine Tabelle laden. Zahlen bleiben Zahlen."""
        if not isinstance(text, str) or not text.strip() or len(text.encode('utf-8')) > MAX_BYTES:
            raise ValueError('tabelle_daten_ungueltig')
        text = text.lstrip('﻿')
        if art == 'auto':
            art = 'json' if text.lstrip()[:1] in '[{' else 'csv'
        if art == 'json':
            try:
                rohe = json.loads(text)
            except ValueError as exc:
                raise ValueError('tabelle_json_ungueltig') from exc
            if isinstance(rohe, dict):
                rohe = rohe.get('zeilen') if isinstance(rohe.get('zeilen'), list) else [rohe]
            if not isinstance(rohe, list) or not all(isinstance(z, dict) for z in rohe):
                raise ValueError('tabelle_json_ungueltig')
        else:
            kopf = text.splitlines()[0]
            trenner = ';' if kopf.count(';') >= kopf.count(',') else ','
            rohe = [{k.strip(): _zahl(v) for k, v in zeile.items() if k is not None} for zeile in csv.DictReader(io.StringIO(text), delimiter=trenner)]
        pfad, doc = self._doc(name)
        if ersetzen:
            doc['zeilen'], doc['naechste_id'] = [], 1
        for zeile in rohe:
            doc['zeilen'].append(self._neu(doc, {str(k): v for k, v in zeile.items() if k not in ('id',)}))
        doc['spalten'] = _spalten(doc)
        self._speichern(pfad, doc)
        return {'name': doc['name'], 'zeilen': len(doc['zeilen']), 'spalten': doc['spalten']}

    @staticmethod
    def _neu(doc, werte):
        zeile = dict(id=doc.get('naechste_id', 1), **werte)
        zeile['createdAt'] = zeile['updatedAt'] = utcnow()
        doc['naechste_id'] = zeile['id'] + 1
        return zeile

    @staticmethod
    def _passt(zeile, bedingungen):
        return all(_vergleich(zeile.get(b['spalte']), b.get('art'), b['wert']) for b in bedingungen)

    def suchen(self, name, bedingungen, limit=1000):
        gefunden = self._finden(name)
        if not gefunden:
            raise ValueError('tabelle_nicht_gefunden:' + str(name))
        return [dict(z) for z in gefunden[1].get('zeilen', []) if self._passt(z, bedingungen)][:limit]

    def upsert(self, name, bedingungen, werte):
        pfad, doc = self._doc(name)
        treffer = [z for z in doc['zeilen'] if self._passt(z, bedingungen)]
        if treffer:
            for z in treffer:
                z.update(werte)
                z['updatedAt'] = utcnow()
            ergebnis = treffer
        else:
            neu = {b['spalte']: b['wert'] for b in bedingungen if b.get('art') in ('eq', 'equals', None)}
            neu.update(werte)
            ergebnis = [self._neu(doc, neu)]
            doc['zeilen'].append(ergebnis[0])
        doc['spalten'] = _spalten(doc)
        self._speichern(pfad, doc)
        return [dict(z) for z in ergebnis]


def _spalten(doc):
    spalten = []
    for z in doc['zeilen']:
        for k in z:
            if k not in spalten and k not in ('id', 'createdAt', 'updatedAt'):
                spalten.append(k)
    return spalten


def _zahl(wert):
    """CSV-Felder: deutsche und englische Zahlen werden Zahlen, alles andere bleibt Text."""
    if not isinstance(wert, str):
        return wert
    s = wert.strip()
    if re.fullmatch(r'-?\d+', s) and not (len(s) > 1 and s.startswith('0')):
        return int(s)
    if re.fullmatch(r'-?\d{1,3}(\.\d{3})*,\d+|-?\d+,\d+', s):
        return float(s.replace('.', '').replace(',', '.'))
    if re.fullmatch(r'-?\d+\.\d+', s):
        return float(s)
    return s


class Eingaben:
    """Hochgeladene Dateien für Läufe, adressiert über ihre SHA-256-Summe: wer genehmigt, genehmigt genau diese Bytes."""

    def __init__(self, project):
        self.root = Path(project).resolve() / 'runtime_data' / 'workflow_eingaben'

    def speichern(self, daten):
        if not isinstance(daten, (bytes, bytearray)) or not daten or len(daten) > MAX_EINGABE:
            raise ValueError('eingabe_leer_oder_zu_gross')
        summe = hashlib.sha256(bytes(daten)).hexdigest()
        pfad = self.root / (summe + '.bin')
        if not pfad.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            _fest(pfad)
            fd, tmp = tempfile.mkstemp(dir=str(self.root), prefix='.tmp-')
            with os.fdopen(fd, 'wb') as stream:
                stream.write(bytes(daten))
            os.replace(tmp, pfad)
        return summe

    def lesen(self, summe):
        if not isinstance(summe, str) or not re.fullmatch('[a-f0-9]{64}', summe):
            raise ValueError('eingabe_kennung_ungueltig')
        pfad = self.root / (summe + '.bin')
        _fest(pfad)
        if not pfad.is_file():
            raise ValueError('eingabe_nicht_gefunden')
        daten = pfad.read_bytes()
        if hashlib.sha256(daten).hexdigest() != summe:
            raise ValueError('eingabe_beschaedigt')
        return daten
