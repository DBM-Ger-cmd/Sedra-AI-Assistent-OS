"""Die Werkzeugkiste der Harness-Shell (SPEC_HARNESS_SHELL_v1 HS-20, G2 §3.4, D-E5, G3 Stufe 2 U4–U6).

`datei_lesen` (≤ 400 Zeilen, mit Nummern), `dateien_auflisten` (≤ 300), `suchen` (ripgrep, sonst Python; ≤ 200 Treffer), `datei_schreiben`,
`datei_aendern` (genau einmal ersetzen) und `befehl` (harness/befehl.py). Je Projekt eine eigene `FilesystemTool`-Instanz mit Wurzel =
Projektwurzel (K5, D-E3); Schreiben nur im Schreibbereich des Projekts. Diese Datei entscheidet **nicht**, ob ein Aufruf laufen darf – das
macht `freigabe.py` (Vorbehalt → Katalog → Guard). Hier stehen: Argumente prüfen, das Ziel für die Einstufung, die Vorschau für die Karte,
die Bindung für das Guard-Gate, und die Ausführung mit dem Token."""
from __future__ import annotations

import difflib
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from ..core.request_binding import file_request
from ..tools.base import ToolPermissionError, ToolValidationError
from ..tools.filesystem import FilesystemTool
from . import befehl as befehl_mod
from . import projekte as harness_projekte
from .katalog import einstufen

LESEN_MAX = 400
LESEN_ZEICHEN_MAX = 8000          # je Lese-Aufruf, Zeilennummern eingerechnet (≈ 2–3k Token; das Fenster ist 16 384)
LISTE_MAX = 300
TREFFER_MAX = 200
VORSCHAU_MAX = 300
DATEI_MAX = 1_000_000
UEBERSPRINGEN = {'.git', 'node_modules', '__pycache__', '.venv', 'engines', '.mypy_cache', '.pytest_cache'}
LESEN = ('datei_lesen', 'dateien_auflisten', 'suchen')
WIRKUNG = ('datei_schreiben', 'datei_aendern', 'befehl')
NAMEN = LESEN + WIRKUNG
AKTION_LESEN = 'harness_lesen'


class WerkzeugFehler(ValueError):
    """Falscher Aufruf (Argumente, Pfad, Schreibbereich) – der Text ist der Grund, er geht als Ergebnis an das Modell."""


def _fn(name, beschreibung, eigenschaften, pflicht):
    return {'type': 'function', 'function': {'name': name, 'description': beschreibung,
                                             'parameters': {'type': 'object', 'properties': eigenschaften, 'required': pflicht}}}


S, I = {'type': 'string'}, {'type': 'integer'}
SCHEMAS = {
    'datei_lesen': _fn('datei_lesen', 'Liest eine Textdatei des Projekts abschnittsweise, mit Zeilennummern (höchstens 400 Zeilen je Aufruf).',
                       {'pfad': dict(S, description='Pfad relativ zur Projektwurzel'), 'ab_zeile': dict(I, description='erste Zeile, ab 1'),
                        'zeilen': dict(I, description='Zahl der Zeilen, höchstens 400')}, ['pfad']),
    'dateien_auflisten': _fn('dateien_auflisten', 'Listet einen Ordner des Projekts (höchstens 300 Einträge).',
                             {'pfad': dict(S, description='Ordner relativ zur Projektwurzel, Standard „.“'),
                              'muster': dict(S, description='optional: Glob für Namen, z. B. *.md')}, []),
    'suchen': _fn('suchen', 'Sucht Text oder einen regulären Ausdruck in den Dateien des Projekts (höchstens 200 Treffer).',
                  {'text': dict(S, description='gesuchter Text (Groß/Klein egal)'), 'regex': dict(S, description='oder: regulärer Ausdruck'),
                   'pfad': dict(S, description='Ordner, Standard „.“'), 'muster': dict(S, description='optional: Glob für Dateinamen, z. B. *.py')}, []),
    'datei_schreiben': _fn('datei_schreiben', 'Schreibt eine Textdatei im Schreibbereich des Projekts (neu oder ganz ersetzt). Braucht je nach Katalog eine Freigabe.',
                           {'pfad': S, 'inhalt': S}, ['pfad', 'inhalt']),
    'datei_aendern': _fn('datei_aendern', 'Ersetzt in einer Datei genau eine Stelle: `alt` muss genau einmal vorkommen. Braucht je nach Katalog eine Freigabe.',
                         {'pfad': S, 'alt': S, 'neu': S}, ['pfad', 'alt', 'neu']),
    'befehl': _fn('befehl', 'Führt einen Befehl im Projekt aus (eine Zeile, ohne Pipes und Umleitungen). Lesende Git-Befehle und die Tests sind frei, sonst Freigabe.',
                  {'befehl': S, 'ordner': dict(S, description='Ordner relativ zur Projektwurzel, Standard „.“'),
                   'zeitlimit_s': dict(I, description='höchstens 600')}, ['befehl']),
}


class Werkzeuge:
    def __init__(self, projekt, *, guard, audit=None, mission_id, regeln, clock=None):
        self.projekt, self.guard, self.mission_id, self.regeln = projekt, guard, mission_id, regeln
        self.wurzel = Path(projekt['wurzel']).resolve()
        self.fs = FilesystemTool(self.wurzel, guard=guard, audit=audit)

    def schemas(self):
        return [SCHEMAS[n] for n in NAMEN]

    # ---- Pfade
    def _rel(self, pfad, muss_da=False):
        try:
            p = self.fs._resolve(str(pfad or '.'), must_exist=muss_da)
        except ToolPermissionError as exc:
            raise WerkzeugFehler('pfad_ausserhalb: der Pfad liegt nicht im Projekt') from exc
        except ToolValidationError as exc:
            raise WerkzeugFehler('pfad_fehlt: ' + str(pfad)) from exc
        return p, (p.relative_to(self.wurzel).as_posix() or '.')

    def _text(self, args, key, pflicht=True):
        v = args.get(key)
        if v is None and not pflicht:
            return None
        if not isinstance(v, str):
            raise WerkzeugFehler(f'argument_fehlt: {key}')
        return v

    # ---- Vorbereiten: Ziel, Vorschau, Gate – ohne Wirkung
    def vorbereiten(self, name, args):
        """{ziel, vorhanden, gate: {aktion, ziel, bindung}, vorschau, kurz} für einen Aufruf – oder WerkzeugFehler."""
        if name not in NAMEN:
            raise WerkzeugFehler(f'werkzeug_unbekannt: {name}')
        args = args if isinstance(args, dict) else {}
        if name == 'befehl':
            zeile = self._text(args, 'befehl')
            befehl_mod.zerlegen(zeile)                                   # Interpreterzeichen sofort ablehnen
            cwd = befehl_mod.ordner_in(self.wurzel, args.get('ordner') or '.')
            rel = cwd.relative_to(self.wurzel).as_posix() or '.'
            return {'ziel': zeile, 'vorhanden': False, 'vorschau': befehl_mod.ziel_text(zeile, rel), 'kurz': zeile,
                    'gate': {'aktion': befehl_mod.AKTION, 'ziel': befehl_mod.ziel_text(zeile, rel), 'bindung': befehl_mod.bindung(zeile, rel)}}
        if name in LESEN:
            p, rel = self._rel(args.get('pfad') or '.', muss_da=True)
            return {'ziel': rel, 'vorhanden': True, 'vorschau': f'{name} {rel}', 'kurz': rel,
                    'gate': {'aktion': AKTION_LESEN, 'ziel': rel, 'bindung': {'werkzeug': name, 'args': args}}}
        p, rel = self._rel(self._text(args, 'pfad'))
        if not harness_projekte.im_schreibbereich(self.projekt, p):
            raise WerkzeugFehler(f'ausserhalb_schreibbereich: {rel} – schreiben nur in {", ".join(self.projekt["schreibbereich"])}')
        if p.exists() and not p.is_file():
            raise WerkzeugFehler('ziel_ist_ordner')
        alt_text = p.read_text(encoding='utf-8') if p.is_file() else ''
        fsargs = self._fsargs(name, args, p, alt_text)
        neu_text = fsargs['content']
        aktion = 'overwrite_existing' if p.exists() else 'create_new_artifact'
        # Warnung (Nachtrag 434b108, Captain 29.10.2026): datei_schreiben auf eine BESTEHENDE Datei, die viele Zeilen verliert.
        warnung = ersetzung_warnung(alt_text, neu_text) if (name == 'datei_schreiben' and p.is_file()) else None
        return {'ziel': rel, 'vorhanden': p.exists(), 'vorschau': diff(alt_text, neu_text, rel), 'kurz': rel, 'fsargs': fsargs, 'warnung': warnung,
                'gate': {'aktion': aktion, 'ziel': str(p), 'bindung': file_request('write_text', fsargs, p)}}

    def _fsargs(self, name, args, p, alt_text):
        if name == 'datei_schreiben':
            inhalt = self._text(args, 'inhalt')
            fsargs = {'path': str(p.relative_to(self.wurzel)), 'content': inhalt}
        else:
            if not p.is_file():
                raise WerkzeugFehler('datei_fehlt: datei_aendern ändert nur vorhandene Dateien')
            alt, neu = self._text(args, 'alt'), self._text(args, 'neu')
            n = alt_text.count(alt) if alt else 0
            if n == 0:
                raise WerkzeugFehler('nicht_gefunden: `alt` steht nicht in der Datei')
            if n > 1:
                raise WerkzeugFehler(f'nicht_eindeutig: `alt` steht {n}× in der Datei – mehr Zusammenhang angeben')
            fsargs = {'path': str(p.relative_to(self.wurzel)), 'content': alt_text.replace(alt, neu, 1)}
        if p.is_file():
            fsargs['expected_sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
        return fsargs

    # ---- Ausführen (die Freigabe ist entschieden; `token` ist das Guard-Token für genau diesen Aufruf)
    def ausfuehren(self, name, args, *, token=None, abbruch=None, plan=None):
        """{status: ok|fehler|abgebrochen, ergebnis: Text, wirkung: bool}. `plan` ist das Ergebnis von `vorbereiten` (sonst neu)."""
        plan = plan or self.vorbereiten(name, args)
        try:
            if name == 'datei_lesen':
                return self._lesen(args, plan)
            if name == 'dateien_auflisten':
                return self._auflisten(args, plan)
            if name == 'suchen':
                return self._suchen(args, plan)
            if name in ('datei_schreiben', 'datei_aendern'):
                out = self.fs.write_text(self.mission_id, plan['fsargs'], approval_token=token)
                if out.get('status') != 'completed':
                    return {'status': 'fehler', 'ergebnis': 'nicht geschrieben: ' + json.dumps({k: out.get(k) for k in ('status', 'guard')}, ensure_ascii=False, default=str)[:300], 'wirkung': False}
                return {'status': 'ok', 'ergebnis': f"{plan['ziel']} geschrieben ({out.get('action')}, {out.get('bytes')} Bytes, sha256 {out.get('sha256', '')[:12]})", 'wirkung': True}
            if name == 'befehl':
                r = befehl_mod.ausfuehren(self.wurzel, args.get('befehl'), args.get('ordner') or '.', args.get('zeitlimit_s') or 120,
                                          guard=self.guard, mission_id=self.mission_id, token=token, abbruch=abbruch)
                kopf = f"Exitcode {r['exitcode']} · {r['dauer_s']} s" + (' · gekürzt' if r['gekuerzt'] else '') + {'zeitlimit': ' · ZEITLIMIT', 'abgebrochen': ' · ABGEBROCHEN', 'nicht_erlaubt': ''}.get(r['status'], '')
                status = {'ok': 'ok', 'abgebrochen': 'abgebrochen'}.get(r['status'], 'fehler')
                return {'status': status, 'ergebnis': kopf + '\n' + r['ausgabe'], 'wirkung': r['status'] in ('ok', 'fehler', 'zeitlimit')}
        except (ToolValidationError, ToolPermissionError, befehl_mod.BefehlFehler, WerkzeugFehler, OSError, UnicodeDecodeError) as exc:
            return {'status': 'fehler', 'ergebnis': f'error: {exc}', 'wirkung': False}
        return {'status': 'fehler', 'ergebnis': f'error: werkzeug_unbekannt {name}', 'wirkung': False}

    def _lesen(self, args, plan):
        out = self.fs.read_text(self.mission_id, {'path': plan['ziel']})
        if out.get('status') != 'completed':
            return {'status': 'fehler', 'ergebnis': 'nicht gelesen: ' + str(out.get('status')), 'wirkung': False}
        zeilen = out['content'].splitlines()
        ab = max(1, int(args.get('ab_zeile') or 1))
        n = max(1, min(LESEN_MAX, int(args.get('zeilen') or 200)))
        # Zeichen- und Tokengrenze (28.10.2026, Abnahme Nemotron C2): 200 Zeilen einer Logbuchdatei waren 126 KB und sprengten das
        # Fenster (47 734 Token gegen 16 384). Je Aufruf höchstens LESEN_ZEICHEN_MAX Zeichen; die nächste Stelle nennt `ab_zeile`.
        stueck, zeichen, i = [], 0, ab - 1
        breite = len(str(min(len(zeilen), ab - 1 + n)))
        while i < min(len(zeilen), ab - 1 + n):
            zeile = zeilen[i]
            kopfzeile = len(f'{i + 1:>{breite}}| ')
            if zeichen + kopfzeile + len(zeile) > LESEN_ZEICHEN_MAX:
                if stueck:
                    break
                zeile = zeile[:LESEN_ZEICHEN_MAX - kopfzeile] + ' […Zeile gekürzt]'
            stueck.append(zeile)
            zeichen += kopfzeile + len(zeile) + 1
            i += 1
        ende = ab - 1 + len(stueck)
        weiter = f' · weiter mit ab_zeile={ende + 1}' if ende < len(zeilen) else ''
        kopf = f"{plan['ziel']} · Zeilen {ab}–{ende} von {len(zeilen)}{weiter}"
        return {'status': 'ok', 'ergebnis': kopf + '\n' + '\n'.join(f'{k:>{breite}}| {z}' for k, z in enumerate(stueck, ab)), 'wirkung': False}

    def _auflisten(self, args, plan):
        out = self.fs.list_dir(self.mission_id, {'path': plan['ziel'], 'limit': 5000, 'bounded': True})
        muster = args.get('muster')
        eintraege = [e for e in out.get('entries') or [] if not muster or fnmatch.fnmatch(e['name'].lower(), str(muster).lower())]
        zeilen = [('d ' + e['name'] + '/') if e['type'] == 'dir' else f"f {e['name']} ({e['size']} B)" for e in eintraege[:LISTE_MAX]]
        kopf = f"{plan['ziel']} · {len(eintraege)} Einträge" + (f' · gezeigt {LISTE_MAX}' if len(eintraege) > LISTE_MAX or out.get('truncated') else '')
        return {'status': 'ok', 'ergebnis': kopf + '\n' + '\n'.join(zeilen), 'wirkung': False}

    def _darf_lesen(self, rel):
        return einstufen(self.regeln, 'suchen', rel)['stufe'] != 'verboten' and einstufen(self.regeln, 'datei_lesen', rel)['stufe'] != 'verboten'

    def _suchen(self, args, plan):
        text, regex = args.get('text'), args.get('regex')
        if not (isinstance(text, str) and text) and not (isinstance(regex, str) and regex):
            raise WerkzeugFehler('argument_fehlt: text oder regex')
        try:
            muster = re.compile(regex) if regex else re.compile(re.escape(text), re.I)
        except re.error as exc:
            raise WerkzeugFehler(f'regex_ungueltig: {exc}') from exc
        start = self.wurzel / plan['ziel']
        treffer, dateien = [], 0
        for datei in self._dateien(start, args.get('muster')):
            rel = datei.relative_to(self.wurzel).as_posix()
            if not self._darf_lesen(rel):
                continue                                                  # was der Katalog nicht lesen lässt, wird auch nicht durchsucht
            try:
                if datei.stat().st_size > DATEI_MAX:
                    continue
                inhalt = datei.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                continue
            dateien += 1
            for i, z in enumerate(inhalt.splitlines(), 1):
                if muster.search(z):
                    treffer.append(f'{rel}:{i}: {z.strip()[:200]}')
                    if len(treffer) >= TREFFER_MAX:
                        break
            if len(treffer) >= TREFFER_MAX:
                break
        kopf = f'{len(treffer)} Treffer in {dateien} durchsuchten Dateien' + (f' · bei {TREFFER_MAX} abgeschnitten' if len(treffer) >= TREFFER_MAX else '')
        return {'status': 'ok', 'ergebnis': kopf + '\n' + '\n'.join(treffer), 'wirkung': False}

    def _dateien(self, start, muster):
        """Die Dateien unter `start` in fester Reihenfolge – mit ripgrep (`rg --files`), falls vorhanden, sonst mit os.walk."""
        if start.is_file():
            yield start; return
        rg = shutil.which('rg')
        namen = None
        if rg:
            try:
                out = subprocess.run([rg, '--files', '--hidden', '--no-messages', *sum((['-g', '!' + d] for d in UEBERSPRINGEN), []), str(start)],
                                     capture_output=True, text=True, encoding='utf-8', timeout=60)
                namen = sorted(Path(z) for z in out.stdout.splitlines() if z.strip())
            except (OSError, subprocess.TimeoutExpired):
                namen = None
        if namen is None:
            namen = []
            for wurzel, ordner, dateien in os.walk(start):
                ordner[:] = sorted(d for d in ordner if d not in UEBERSPRINGEN)
                namen.extend(Path(wurzel) / f for f in sorted(dateien))
        for p in namen:
            p = p if p.is_absolute() else start / p
            if muster and not fnmatch.fnmatch(p.name.lower(), str(muster).lower()):
                continue
            if p.is_symlink() or not p.is_file():
                continue
            yield p


WARN_ZEILEN = 50          # Nachtrag 434b108: mehr als 50 Zeilen der alten Datei entfernt …
WARN_ANTEIL = 0.30        # … oder mehr als 30 % ihrer Zeilen


def ersetzung_warnung(alt, neu):
    """None oder {entfernt, neu, alt, text}: eine bestehende Datei, die der neue Inhalt weitgehend ersetzt. Zählt über difflib (Zeilen,
    nicht Zeichen), damit ein umgebrochener Absatz nicht als Löschung zählt."""
    a, b = alt.splitlines(), neu.splitlines()
    if not a:
        return None
    gleich = sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    entfernt, hinzu = len(a) - gleich, len(b) - gleich
    if entfernt > WARN_ZEILEN or entfernt / len(a) > WARN_ANTEIL:
        return {'entfernt': entfernt, 'neu': hinzu, 'alt': len(a),
                'text': f'Ersetzt die ganze Datei: {entfernt} von {len(a)} Zeilen gelöscht, {hinzu} neu.'}
    return None


def diff(alt, neu, rel):
    """Unified-Diff für die Karte (HS-22); ab VORSCHAU_MAX Zeilen gekürzt mit Hinweis."""
    zeilen = list(difflib.unified_diff(alt.splitlines(), neu.splitlines(), 'a/' + rel, 'b/' + rel, lineterm='', n=3))
    if not zeilen:
        return f'{rel}: keine Änderung'
    if len(zeilen) > VORSCHAU_MAX:
        return '\n'.join(zeilen[:VORSCHAU_MAX]) + f'\n… {len(zeilen) - VORSCHAU_MAX} weitere Zeilen („ganz anzeigen“ im Reiter)'
    return '\n'.join(zeilen)
