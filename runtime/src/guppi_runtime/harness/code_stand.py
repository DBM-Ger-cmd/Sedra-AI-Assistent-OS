"""Gesehener Code-Stand je Harness-Projekt (SPEC_APPS_v1 G4, docs/SPEC_APPS_v1_G4_MODELLCODE_G2.md).

Die Harness startet keinen Lauf und keinen Befehl, solange im Projekt Code liegt, dessen aktuelle Fassung der Captain nicht gesehen hat –
außer er sieht ihn auf der Karte und gibt frei. Grund (Vorlage AM0-E1 §5a.3): Ein Lauf oder Befehl führt Code auf dem Rechner aus; Code,
den das Modell geschrieben hat, käme so an allen Vorbehalten vorbei.

- **Code-Datei**: Endung aus CODE_ENDUNGEN oder Name aus CODE_NAMEN; übersprungen werden AUSLASSEN und versteckte Ordner. Eine Heuristik:
  was nicht darauf steht, wird nicht geprüft (G2 §7).
- **Gesehener Stand**: je Code-Datei der SHA-256 der Fassung, die als gesehen gilt. Beim ersten Gebrauch gilt der vorhandene Stand als
  gesehen (G4-04, ungeprüft angenommen). Ungesehen ist, was davon abweicht – gefunden durch Vergleich mit dem Dateisystem, damit auch
  Änderungen durch Läufe, Programme oder von außen auffallen (G4-05).
- **Spur**: was die Harness selbst geschrieben hat (Sitzung, Weg), und die vorige Fassung, wenn sie gesehen war – nur für die Anzeige.

Die Ablage liegt unter `runtime_data/harness/` (harter Vorbehalt): das Modell kann sie nicht schreiben.
Harness-Code (Vorbehalt): SEDRA ändert diese Datei nicht an sich selbst."""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import threading
from datetime import datetime
from pathlib import Path

from ..core.util import atomic_write_json

CODE_ENDUNGEN = frozenset({'.py', '.pyw', '.pth', '.js', '.mjs', '.cjs', '.ps1', '.psm1', '.bat', '.cmd', '.sh', '.vbs', '.exe', '.dll'})
CODE_NAMEN = frozenset({'pyproject.toml', 'setup.cfg', 'setup.py', 'tox.ini', 'pytest.ini', 'package.json', 'conftest.py',
                        'sitecustomize.py', 'usercustomize.py'})
BINAER = frozenset({'.exe', '.dll'})
AUSLASSEN = frozenset({'.git', 'node_modules', '__pycache__', '.venv', 'engines', '.mypy_cache', '.pytest_cache', 'runtime_data'})
# Ordner (relativ zur Projektwurzel), die nicht gescannt werden: die portable Laufzeit (Python mit Standardbibliothek, Sandbox-SDK; auf dem PC und
# dem Stick tausende Dateien, Bau-PC zusätzlich `python.aus`). Das Modell schreibt dort nicht – harter Vorbehalt in harness/vorbehalte.py.
AUSLASSEN_PFADE = ('runtime/portable',)
NUR_PRUEFEN = ('python -m py_compile', 'node --check')          # G4-E1: prüfen nur die Schreibweise, führen keinen Projekt-Code aus
AUSFUEHRUNG = ('befehl', 'lauf_starten')
KARTE_DATEIEN_MAX = 30
KARTE_ZEILEN_MAX = 2000
ANFANG_ZEILEN = 200
VORHER_MAX = 1_000_000


def jetzt():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def ist_code(rel):
    name = str(rel).replace('\\', '/').rsplit('/', 1)[-1].lower()
    return name in CODE_NAMEN or os.path.splitext(name)[1] in CODE_ENDUNGEN


def nur_pruefen(zeile):
    z = ' '.join(str(zeile or '').split()).lower()
    return any(z == p or z.startswith(p + ' ') for p in NUR_PRUEFEN)


def bindung(liste):
    """Woran eine Freigabe gebunden ist: genau diese Dateien in genau dieser Fassung (G4-11)."""
    return [[e['pfad'], e['neu']] for e in liste]


def _sha_datei(pfad):
    h = hashlib.sha256()
    with open(pfad, 'rb') as f:
        for stueck in iter(lambda: f.read(1 << 20), b''):
            h.update(stueck)
    return h.hexdigest()


class CodeStand:
    """Der gesehene Stand eines Projekts. `ablage` ist der Ordner unter runtime_data/harness/, `audit(event, payload)` optional."""

    def __init__(self, ablage, wurzel, projekt_id, *, audit=None, konsole=None):
        self.ablage = Path(ablage)
        self.wurzel = Path(wurzel).resolve()
        self.projekt_id = str(projekt_id)
        self.datei = self.ablage / f'{self.projekt_id}.json'
        self.spur_datei = self.ablage / f'{self.projekt_id}.spur.json'
        self.vorher = self.ablage / 'vorher'
        self.audit = audit
        # wie man den Stand außerhalb des Browsers ansieht – setzt der Server (G4-16); ohne Angabe die Form aus docs/BETRIEB.md
        self.konsole = konsole or f'CODE_STAND.bat {self.projekt_id}'
        self._cache = {}                     # rel → (size, mtime_ns, sha): nur Geändertes wird neu gehasht
        self._sperre = threading.RLock()

    def _melden(self, event, payload):
        if callable(self.audit):
            try:
                self.audit(event, dict(payload, projekt=self.projekt_id))
            except Exception:
                pass

    # ---- Dateisystem
    def erfassen(self):
        """{rel: sha256} aller Code-Dateien des Projekts."""
        out, cache = {}, {}
        for ordner, unter, dateien in os.walk(self.wurzel):
            basis = Path(ordner).relative_to(self.wurzel).as_posix()
            basis = '' if basis == '.' else basis + '/'
            unter[:] = [u for u in unter if u not in AUSLASSEN and not u.startswith('.') and (basis + u).lower() not in AUSLASSEN_PFADE]
            for name in dateien:
                if not ist_code(name):
                    continue
                pfad = Path(ordner) / name
                try:
                    st = pfad.stat()
                except OSError:
                    continue                                      # verschwunden oder unlesbar: zählt nicht als vorhanden
                rel = pfad.relative_to(self.wurzel).as_posix()
                alt = self._cache.get(rel)
                if alt and alt[0] == st.st_size and alt[1] == st.st_mtime_ns:
                    sha = alt[2]
                else:
                    try:
                        sha = _sha_datei(pfad)
                    except OSError:
                        continue
                cache[rel] = (st.st_size, st.st_mtime_ns, sha)
                out[rel] = sha
        self._cache = cache
        return out

    def _sha_jetzt(self, rel):
        p = self.wurzel / rel
        try:
            return _sha_datei(p) if p.is_file() else None
        except OSError:
            return None

    # ---- Ablage
    def _lesen(self, pfad, leer):
        try:
            return json.loads(Path(pfad).read_text(encoding='utf-8'))
        except FileNotFoundError:
            return leer
        except (OSError, ValueError):
            return leer

    def _speichern(self, d):
        d['zuletzt'] = jetzt()
        atomic_write_json(self.datei, d)

    def stand(self):
        """Der gesehene Stand; beim ersten Gebrauch der vorhandene (G4-04)."""
        with self._sperre:
            d = self._lesen(self.datei, None)
            if isinstance(d, dict) and isinstance(d.get('gesehen'), dict):
                return d
            aktuell = self.erfassen()
            d = {'schema': 1, 'projekt': self.projekt_id, 'wurzel': str(self.wurzel), 'gesehen': aktuell, 'angelegt': jetzt()}
            self._speichern(d)
            summe = hashlib.sha256(json.dumps(sorted(aktuell.items())).encode('utf-8')).hexdigest()
            self._melden('HARNESS_CODE_STAND_ANGELEGT', {'dateien': len(aktuell), 'hash': summe})
            return d

    def _spur(self):
        d = self._lesen(self.spur_datei, {})
        return d if isinstance(d, dict) else {}

    # ---- Abfragen
    def ungesehen(self):
        """[{pfad, alt, neu, herkunft}] – alt/neu sind Hashes (None: neu angelegt bzw. gelöscht)."""
        with self._sperre:
            gesehen = self.stand()['gesehen']
            aktuell = self.erfassen()
            spur = self._spur()
            out = []
            for rel in sorted(set(aktuell) | set(gesehen)):
                alt, neu = gesehen.get(rel), aktuell.get(rel)
                if alt != neu:
                    out.append({'pfad': rel, 'alt': alt, 'neu': neu, 'herkunft': spur.get(rel)})
            return out

    # ---- Schreiben durch die Harness
    def vorher_merken(self, rel):
        """Vor dem Schreiben: die vorige Fassung ablegen, wenn sie gesehen war. Liefert ihren Hash (None: Datei neu)."""
        with self._sperre:
            if not ist_code(rel):
                return None
            p = self.wurzel / rel
            if not p.is_file():
                return None
            try:
                daten = p.read_bytes()
            except OSError:
                return None
            sha = hashlib.sha256(daten).hexdigest()
            if self.stand()['gesehen'].get(rel) == sha and len(daten) <= VORHER_MAX:
                ziel = self.vorher / sha
                if not ziel.exists():
                    self.vorher.mkdir(parents=True, exist_ok=True)
                    tmp = ziel.with_suffix('.tmp')
                    tmp.write_bytes(daten)
                    os.replace(tmp, ziel)
            return sha

    def spur(self, rel, sitzung_id, weg):
        """Was die Harness geschrieben hat: Sitzung, Weg (karte, aufgabe, sitzung, katalog, vorarbeiter), Zeit."""
        with self._sperre:
            s = self._spur()
            s[rel] = {'sitzung_id': sitzung_id, 'weg': weg, 'zeit': jetzt()}
            atomic_write_json(self.spur_datei, s)

    def schreiben_gesehen(self, rel, alt_sha):
        """G4-07: über eine Karte des Captains geschrieben – die neue Fassung gilt als gesehen, wenn die vorige es war (oder neu ist)."""
        with self._sperre:
            d = self.stand()
            if d['gesehen'].get(rel) != alt_sha:
                return False
            neu = self._sha_jetzt(rel)
            if neu is None:
                return False
            d['gesehen'][rel] = neu
            self._speichern(d)
            self._spur_weg([rel])
            return True

    def gesehen_setzen(self, eintraege):
        """G4-12: die Dateien einer freigegebenen Karte gelten als gesehen – nur, wenn ihre Fassung noch die gebundene ist."""
        with self._sperre:
            d = self.stand()
            aktuell = self.erfassen()
            fertig = []
            for pfad, neu in eintraege or []:
                if aktuell.get(pfad) != neu:
                    continue
                if neu is None:
                    d['gesehen'].pop(pfad, None)
                else:
                    d['gesehen'][pfad] = neu
                fertig.append(pfad)
            if fertig:
                self._speichern(d)
                self._spur_weg(fertig)
            return len(fertig)

    def uebernehmen(self):
        """Konsole (G4-16): der aktuelle Stand gilt als gesehen. Liefert die Zahl der Dateien, die vorher ungesehen waren."""
        with self._sperre:
            vorher = len(self.ungesehen())
            d = self.stand()
            d['gesehen'] = self.erfassen()
            self._speichern(d)
            atomic_write_json(self.spur_datei, {})
            return vorher

    def _spur_weg(self, pfade):
        s = self._spur()
        if any(p in s for p in pfade):
            for p in pfade:
                s.pop(p, None)
            atomic_write_json(self.spur_datei, s)

    # ---- Anzeige
    def _text(self, rel):
        try:
            return (self.wurzel / rel).read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            return None

    def _vorher_text(self, sha):
        try:
            return (self.vorher / sha).read_bytes().decode('utf-8') if sha else None
        except (OSError, UnicodeDecodeError):
            return None

    def _eintrag(self, e):
        rel, alt, neu, h = e['pfad'], e['alt'], e['neu'], e.get('herkunft')
        quelle = (f"von der Harness geschrieben (Sitzung {h.get('sitzung_id') or '?'}, Weg {h.get('weg')}, {h.get('zeit')})" if h
                  else 'außerhalb der Harness geändert')
        if neu is None:
            return [f'■ {rel} – gelöscht ({quelle})']
        if os.path.splitext(rel.lower())[1] in BINAER:
            return [f'■ {rel} – Binärdatei, sha256 {neu[:16]}… ({quelle}); Inhalt nicht anzeigbar']
        jetzt_text = self._text(rel)
        if jetzt_text is None:
            return [f'■ {rel} – nicht als Text lesbar, sha256 {neu[:16]}… ({quelle})']
        if alt is None:
            zeilen = jetzt_text.splitlines()
            return [f'■ {rel} – neu ({quelle}), {len(zeilen)} Zeilen:'] + ['+' + z for z in zeilen]
        vorher = self._vorher_text(alt)
        if vorher is not None:
            diff = list(difflib.unified_diff(vorher.splitlines(), jetzt_text.splitlines(), fromfile=f'{rel} (gesehen)', tofile=f'{rel} (jetzt)', lineterm=''))
            return [f'■ {rel} – geändert ({quelle}):'] + diff
        zeilen = jetzt_text.splitlines()
        kopf = (f'■ {rel} – geändert ({quelle}); die gesehene Fassung ist nicht gespeichert, im Repo mit „git diff“ ansehen. '
                f'{len(zeilen)} Zeilen, sha256 {neu[:16]}…, Anfang:')
        return [kopf] + zeilen[:ANFANG_ZEILEN] + ([f'… ({len(zeilen) - ANFANG_ZEILEN} weitere Zeilen)'] if len(zeilen) > ANFANG_ZEILEN else [])

    def vorschau(self, liste, begrenzt=True):
        """(Text für die Karte, zu_gross) – G4-13/14. Zuerst, was die Harness geschrieben hat, dann alles andere. `begrenzt=False`: die Konsole
        zeigt alles, ohne Grenze."""
        sortiert = sorted(liste, key=lambda e: (e.get('herkunft') is None, e['pfad']))
        n = len(sortiert)
        kopf = (f'Code, den du noch nicht gesehen hast ({n} Datei{"" if n == 1 else "en"}). '
                'Mit „Erlauben“ gilt genau diese Fassung als gesehen; danach laufen Läufe und Befehle wieder ohne diese Karte, bis sich Code ändert.')
        zeilen, zu_gross = [kopf], begrenzt and n > KARTE_DATEIEN_MAX
        for e in (sortiert[:KARTE_DATEIEN_MAX] if begrenzt else sortiert):
            stueck = self._eintrag(e)
            if begrenzt and len(zeilen) + len(stueck) > KARTE_ZEILEN_MAX:
                zu_gross = True
                break
            zeilen.extend(stueck)
        if zu_gross:
            zeilen.append(f'… Zu viel ungesehener Code für eine Karte ({n} Dateien). Diese Karte lässt sich nicht im Browser freigeben: '
                          f'in der Konsole mit „{self.konsole} --zeigen“ ansehen und mit „{self.konsole} --uebernehmen“ übernehmen, '
                          'dann den Aufruf wiederholen lassen.')
        return '\n'.join(zeilen), zu_gross


# ---------------------------------------------------------------- Konsole (G4-16): außerhalb des Browsers ansehen und übernehmen
def konsole(root, projekt_id, uebernehmen=False):
    """(Exitcode, Text). `root` ist der Projektordner der Oberfläche (z. B. workspace/GUPPI_OS) – dieselbe Ablage wie der Server.
    Ein `root` ohne runtime_data/harness wird abgelehnt: sonst entstünde still ein zweiter Stand, und „übernehmen“ wirkte nicht.
    Schlanker Einstieg ohne die ganze Runtime (auch für den USB-Stick): nur Kern und Harness."""
    from ..core.audit import AuditLog
    from . import projekte as harness_projekte
    root = Path(root).resolve()
    if not (root / 'runtime_data' / 'harness').is_dir():
        return 2, json.dumps({'status': 'refused', 'error': 'root_ist_nicht_der_projektordner',
                              'grund': f'Unter {root} gibt es kein runtime_data/harness. --root muss der Projektordner der Oberfläche sein '
                                       '(z. B. workspace/GUPPI_OS); unter Windows: CODE_STAND.bat im SEDRA-Ordner.'}, ensure_ascii=False)
    try:
        projekte = harness_projekte.laden(root)
    except harness_projekte.ProjektFehler as exc:
        return 2, json.dumps({'status': 'refused', 'error': str(exc)}, ensure_ascii=False)
    projekt = next((p for p in projekte if p['id'] == projekt_id), None)
    if projekt is None:
        return 2, json.dumps({'status': 'refused', 'error': 'projekt_unbekannt', 'projekte': [p['id'] for p in projekte]}, ensure_ascii=False)
    audit = AuditLog(root / 'runtime_data' / 'audit' / 'events.jsonl')         # dieselbe Kette wie die Oberfläche (Dateisperre beim Anhängen)

    def melden(event, payload):
        audit.append(event, component='harness', payload=payload)

    cs = CodeStand(root / 'runtime_data' / 'harness' / 'code_stand', projekt['wurzel'], projekt['id'], audit=melden)
    liste = cs.ungesehen()
    if uebernehmen:
        n = cs.uebernehmen()
        melden('HARNESS_CODE_STAND_UEBERNOMMEN', {'projekt': projekt['id'], 'anzahl': n, 'kanal': 'konsole'})
        return 0, json.dumps({'status': 'uebernommen', 'projekt': projekt['id'], 'anzahl': n}, ensure_ascii=False)
    return 0, (cs.vorschau(liste, begrenzt=False)[0] if liste else f"Kein ungesehener Code im Projekt {projekt['id']}.")


def main(argv=None):
    """`python -m guppi_runtime.harness.code_stand --root <projektordner> <projekt> [--uebernehmen]` (so ruft es CODE_STAND.bat)."""
    import argparse
    p = argparse.ArgumentParser(prog='code_stand', description='Code, den der Captain in dieser Fassung noch nicht gesehen hat (G4)')
    p.add_argument('--root', required=True)
    p.add_argument('projekt')
    p.add_argument('--uebernehmen', action='store_true')
    a = p.parse_args(argv)
    code, text = konsole(a.root, a.projekt, a.uebernehmen)
    print(text)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
