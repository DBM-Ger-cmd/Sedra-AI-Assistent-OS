"""Wissensbasis des Arbeitsumfelds (Captain-Auftrag 16.10.2026): Ordner, Läufe, Regeln, Modelle, Vorarbeiter.

Cockpit und Master-Chat fragen hier nach Kontext, bevor sie antworten. Die Basis wird bei jedem Aufbau aus dem Stand auf der
Platte neu gefüllt (wie gateway/wissen.py), nie von Hand gepflegt. Ablage: `local_config/arbeitsumfeld/wissen.sqlite`.

Was hineinkommt:
  - Ordner unter workspace/GUPPI_OS und redesign/ (nur Namen, Anzahl, Zweck aus einer festen Liste)
  - Läufe: Regelwerk-Tabelle (Abschnitt 8), angelegte Definitionen (laeufe/*.json), letzter Stand aus den Protokollen
  - Regeln und Import-Auftrag: die Abschnitte der beiden Dokumente, gekürzt
  - Modelle: letzter Zustand (Ampel, Antwortzeit) aus modell_zustand.json, ohne Schlüssel
  - Vorarbeiter: die festen Aktionen aus dem Quelltext, mit Zweck

Was nicht hineinkommt: Schlüssel (cloud_keys.json wird nicht gelesen), Prompt- und Dateiinhalte aus den Protokollen,
Ergebnisse von Läufen, personenbezogene Angaben. Keine Netzzugriffe, keine Modellaufrufe.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from pathlib import Path

VERSION = 'arbeitsumfeld-0.1.0'
DATEI = Path('local_config') / 'arbeitsumfeld' / 'wissen.sqlite'
MODELL_DATEI = Path('local_config') / 'modell_zustand.json'
REGELWERK = Path('docs') / 'REGELWERK_STANDARDLAEUFE.md'
AUFTRAG = Path('docs') / 'AUFTRAG_EINHEITLICHER_IMPORT_2026-10-16.md'
VORARBEITER_QUELLE = Path('runtime') / 'src' / 'guppi_runtime' / 'vorarbeiter.py'
ABSCHNITT_LAENGE = 1500
# Gleiche Schwelle wie die Ampel der Modellauswahl (modell_zustand.SCHNELL_MS). Hier kopiert, damit diese Basis nicht
# von einem Modul abhängt, das noch nicht eingecheckt ist.
SCHNELL_MS = 5000

# Zweck je bekanntem Ordner. Unbekannte Ordner erscheinen mit „Zweck nicht beschrieben“, nicht mit einer Vermutung.
ORDNER_ZWECK = {
    'local_config': 'Einstellungen und Zustände: Modelle, Gateway, Schalter. Enthält Schlüssel; der Schlüsselordner wird nie gelesen.',
    'runtime_data': 'Laufzeitdaten: Artefakte, Audit, Kontext, Jobs, Missionen, Wissen.',
    'redesign': 'Sandbox für Läufe: jeder Lauf schreibt nur in seinen Schreibbereich hier (Regelwerk Abschnitt 1).',
    'redesign/laeufe': 'Definitionen frei anlegbarer Läufe, je eine JSON-Datei (Regelwerk Abschnitt 10).',
    'redesign/vorarbeiter': 'Sperrdateien je Lauf-Art (ein Lauf je Art und Sechs-Stunden-Sperre).',
    'redesign/drache_lab': 'Lauf „drache“: Seedrache als Entwurf.',
    'redesign/omni_lab': 'Lauf „omni“: Bewertung eines fremden Projekts, Ausgaben.',
    'redesign/omni_mapping': 'Zuordnung der Platzhalter für fremde Auszüge. Bleibt lokal.',
    'redesign/paperclip_lab': 'Lauf „pipeline“: Bedarf, Auswahl, Varianten, Prüfung, Vorlage.',
    'redesign/spec_lab': 'Lauf „spec“: neue Shell nur aus Spezifikation.',
    'redesign/workbench': 'Werkbank: Ziel des Werkzeugs „rendern“ (OpenSCAD zu STL) und des Laufs sedra-drache.',
    'redesign/uix': 'Schreibbereich der Oberflächen-Läufe (Shells).',
    'redesign/einreichen': 'Zweck im Projekt nicht beschrieben – offen.',
    'redesign/entwurf': 'Zweck im Projekt nicht beschrieben – offen.',
    'redesign/alt_leere_antwort_2026-10-16': 'Altlauf vom 16.10.2026, Name deutet auf eine leere Antwort des Modells hin.',
    'redesign/alt_timeout_2026-10-16': 'Altlauf vom 16.10.2026, Name deutet auf eine Zeitüberschreitung hin.',
}
ORDNER_ZWECK_FALLBACK = 'Zweck nicht beschrieben.'

# Vorarbeiter-Aktionen: Zweck je Aktion. Die Liste der Namen kommt aus dem Quelltext; fehlt hier eine, steht „ohne Beschreibung“.
AKTION_ZWECK = {
    'lauf_status': 'Liste der Läufe mit Stand (Art, Name, Status, Modell, Aufrufe, Schreibvorgänge). Nur lesen.',
    'lauf_anlegen': 'Legt eine Lauf-Definition aus Auftrag, Modell, Schreibbereich und Ausgaben an. Prüft, startet nicht.',
    'lauf_starten': 'Startet einen festen oder angelegten Lauf. Höchstens ein Lauf je Art und sechs Stunden.',
    'rendern': 'Rendert eine .scad-Datei aus der Werkbank mit OpenSCAD zu STL. Zeitlimit 180 Sekunden.',
    'pruefen': 'Prüft die Ausgaben eines Labors (drache_lab, paperclip_lab) nach den Prüfregeln, Abschnitt 5.',
}

_WORT = re.compile(r'[a-zäöüß0-9\-]{3,}')
_STOPP = frozenset('''wie wird das der die den dem des ist was ein eine einen und mit ich mir mich mein meine im in zu zum zur nicht
bitte kann oder auch aus für von bei an auf wo wer wann warum welche welcher welches gibt es sind hat haben werden'''.split())


def _woerter(text):
    return [w for w in _WORT.findall((text or '').lower()) if w not in _STOPP]


def _sha(pfad):
    try:
        return hashlib.sha256(pfad.read_bytes()).hexdigest()[:16]
    except OSError:
        return ''


class ArbeitsumfeldWissen:
    """Wissensbasis über das Arbeitsumfeld. `project_root` ist workspace/GUPPI_OS; `repo_root` der Projektordner mit docs/."""

    def __init__(self, project_root, repo_root=None):
        self.project_root = Path(project_root)
        self.repo_root = Path(repo_root) if repo_root is not None else self.project_root.parents[1]
        self.path = self.project_root / DATEI
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.execute('CREATE TABLE IF NOT EXISTS wissen (id TEXT PRIMARY KEY, art TEXT, titel TEXT, text TEXT, quelle TEXT, version TEXT)')
        self.aufbauen()

    # ------------------------------------------------------------------ Aufbau
    def aufbauen(self):
        """Füllt die Tabelle aus dem Stand auf der Platte neu. Gibt die Zahl der Einträge zurück."""
        zeilen = []
        zeilen += self._ordner()
        zeilen += self._laeufe()
        zeilen += self._dokument_abschnitte(REGELWERK, 'regel')
        zeilen += self._dokument_abschnitte(AUFTRAG, 'auftrag')
        zeilen += self._modelle()
        zeilen += self._vorarbeiter()
        with self._lock:
            self._db.execute('DELETE FROM wissen')
            self._db.executemany('INSERT INTO wissen VALUES (?,?,?,?,?,?)', [(*z, VERSION) for z in zeilen])
            self._db.commit()
        return len(zeilen)

    def _ordner(self):
        out = []
        if not self.project_root.is_dir():
            return out
        for eintrag in sorted(self.project_root.iterdir()):
            if eintrag.name.startswith('.'):
                continue
            out += self._eintrag(eintrag, eintrag.name)
            if eintrag.is_dir() and eintrag.name == 'redesign':
                for kind in sorted(eintrag.iterdir()):
                    if not kind.name.startswith('.'):
                        out += self._eintrag(kind, f'redesign/{kind.name}')
        return out

    def _eintrag(self, pfad, key):
        """Ein Ordner oder eine Datei der Basis. `key` ist der Pfad relativ zu workspace/GUPPI_OS."""
        if pfad.is_dir():
            anzahl = sum(1 for _ in pfad.iterdir())
            text = f'{ORDNER_ZWECK.get(key, ORDNER_ZWECK_FALLBACK)} Einträge: {anzahl}.'
            return [(f'O-{key}', 'ordner', f'Ordner {key}', text, f'workspace/GUPPI_OS/{key}')]
        return [(f'O-{key}', 'datei', f'Datei {key}', self._datei_zweck(pfad.name), f'workspace/GUPPI_OS/{key}')]

    @staticmethod
    def _datei_zweck(name):
        if name.startswith('lauf_') and name.endswith('.jsonl'):
            return f'Protokoll des Laufs {name[5:-6]} (Ereignisse, ohne Inhalte). Stand: siehe Eintrag der Läufe.'
        return ORDNER_ZWECK_FALLBACK

    def _laeufe(self):
        out = []
        for zeile in self._regelwerk_tabelle():
            name = zeile[0]
            out.append((f'L-{name}', 'lauf', f'Lauf {name} (Präzedenzfall)',
                        ' | '.join(f'{k}: {v}' for k, v in zip(('Modell', 'Schreibbereich', 'Zweck', 'Besonderheit'), zeile[1:])),
                        'docs/REGELWERK_STANDARDLAEUFE.md, Abschnitt 8'))
        laeufe_dir = self.project_root / 'redesign' / 'laeufe'
        if laeufe_dir.is_dir():
            for datei in sorted(laeufe_dir.glob('*.json')):
                try:
                    d = json.loads(datei.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    out.append((f'L-{datei.stem}', 'lauf', f'Lauf {datei.stem} (angelegt)', 'Definition nicht lesbar.', f'redesign/laeufe/{datei.name}'))
                    continue
                text = (f'Art: {d.get("art", "bewerten")}. Zweck: {d.get("beschreibung", "")}. Ordner: {d.get("lab", "")}. '
                        f'Modell: {d.get("provider", "")}/{d.get("model", "")}. Ausgaben: {", ".join(d.get("outputs") or []) or "keine"}.')
                out.append((f'L-{datei.stem}', 'lauf', f'Lauf {d.get("name", datei.stem)} (angelegt)', text, f'redesign/laeufe/{datei.name}'))
        redesign = self.project_root / 'redesign'
        for protokoll in (sorted(redesign.glob('lauf_*.jsonl')) if redesign.is_dir() else []):
            ereignisse = []
            for zeile in protokoll.read_text(encoding='utf-8', errors='replace').splitlines():
                try:
                    ereignisse.append(json.loads(zeile).get('event', ''))
                except ValueError:
                    continue
            letztes = ereignisse[-1] if ereignisse else 'leer'
            status = 'beendet' if letztes == 'LAUF_ENDE' else 'nicht sauber beendet (Abbruch oder offen)'
            name = protokoll.stem[5:]
            out.append((f'P-{name}', 'lauf_stand', f'Protokoll {name}',
                        f'Status: {status}. Letztes Ereignis: {letztes}. Modellaufrufe: {ereignisse.count("SG_MODEL_CALL")}. '
                        'Inhalte stehen nicht im Protokoll.', f'redesign/{protokoll.name}'))
        return out

    def _regelwerk_tabelle(self):
        """Zeilen der Präzedenzfall-Tabelle (Abschnitt 8): [Lauf, Modell, Schreibbereich, Zweck, Besonderheit]."""
        datei = self.repo_root / REGELWERK
        if not datei.is_file():
            return []
        text = datei.read_text(encoding='utf-8')
        m = re.search(r'^## 8\..*?$(.*?)^## ', text, re.S | re.M)
        if not m:
            return []
        zeilen = []
        for zeile in m.group(1).splitlines():
            if not zeile.startswith('|') or set(zeile) <= set('|- '):
                continue
            zellen = [z.strip() for z in zeile.strip().strip('|').split('|')]
            if len(zellen) == 5 and zellen[0].lower() != 'lauf':
                zeilen.append([z.strip('`') for z in zellen])
        return zeilen

    def _dokument_abschnitte(self, pfad, art):
        datei = self.repo_root / pfad
        if not datei.is_file():
            return []
        out = []
        titel, body = None, []
        quelle = str(pfad).replace('\\', '/')

        def abschliessen():
            if titel is not None:
                text = ' '.join(' '.join(body).split())[:ABSCHNITT_LAENGE]
                out.append((f'{art[0].upper()}-{len(out) + 1:02d}', art, titel, text, quelle))

        for zeile in datei.read_text(encoding='utf-8').splitlines():
            if zeile.startswith('## '):
                abschliessen()
                titel, body = zeile[3:].strip(), []
            elif titel is not None:
                body.append(zeile)
        abschliessen()
        return out

    @staticmethod
    def _ampel(eintrag):
        if not eintrag: return 'grau'
        if not eintrag.get('ok'): return 'rot'
        return 'gruen' if int(eintrag.get('ms') or 0) < SCHNELL_MS else 'gelb'

    def _modelle(self):
        out = []
        try:
            daten = json.loads((self.project_root / MODELL_DATEI).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            daten = {}
        for schluessel, eintrag in sorted(daten.items()):
            anbieter, _, modell = schluessel.partition('|')
            text = (f'Ampel: {self._ampel(eintrag)} (grün: schnell unter {SCHNELL_MS} ms, gelb: langsam, rot: letzte Anfrage kam nicht durch). '
                    f'Letzte Antwort: {eintrag.get("ms")} ms am {eintrag.get("zeit")}. Stand aus echten Anfragen, keine Testanfragen.')
            out.append((f'M-{anbieter}-{modell}', 'modell', f'Modell {modell} ({anbieter})', text, str(MODELL_DATEI).replace('\\', '/')))
        if not out:
            out.append(('M-leer', 'modell', 'Modelle', 'Noch keine Anfrage an ein Cloud-Modell festgehalten (grau).', str(MODELL_DATEI).replace('\\', '/')))
        return out

    def _vorarbeiter(self):
        out = []
        quelle = self.repo_root / VORARBEITER_QUELLE
        if not quelle.is_file():
            return out
        text = quelle.read_text(encoding='utf-8')
        namen = []
        for n in re.findall(r'name == "(\w+)"', text):
            if n not in namen:
                namen.append(n)
        for n in namen:
            zweck = AKTION_ZWECK.get(n, 'ohne Beschreibung')
            out.append((f'V-{n}', 'vorarbeiter', f'Vorarbeiter-Aktion {n}', zweck, 'runtime/src/guppi_runtime/vorarbeiter.py'))
        m = re.search(r'SPERRE_S = (\d+) \* 3600', text)
        if m:
            out.append(('V-sperre', 'vorarbeiter', 'Sperre je Lauf-Art',
                        f'Ein Lauf je Art höchstens einmal in {m.group(1)} Stunden. Die Sperre hängt an einer Datei je Art.',
                        'runtime/src/guppi_runtime/vorarbeiter.py'))
        return out

    # ------------------------------------------------------------------ Abfrage
    def quellen(self):
        """Welche Dateien die Basis speist, mit kurzer Prüfsumme. Für den Bericht und für die Prüfung auf veralteten Stand."""
        liste = [REGELWERK, AUFTRAG, VORARBEITER_QUELLE]
        out = []
        for rel in liste:
            pfad = self.repo_root / rel
            out.append({'pfad': str(rel).replace('\\', '/'), 'vorhanden': pfad.is_file(), 'sha256': _sha(pfad)})
        for rel in [str(MODELL_DATEI).replace('\\', '/'), 'redesign/laeufe']:
            pfad = self.project_root / rel
            out.append({'pfad': f'workspace/GUPPI_OS/{rel}', 'vorhanden': pfad.exists(), 'sha256': _sha(pfad) if pfad.is_file() else ''})
        return out

    def suche(self, frage, limit=5):
        """Die passendsten Einträge zur Frage. Ohne Treffer leere Liste; kein Modell, kein Netz."""
        worte = set(_woerter(frage))
        if not worte:
            return []
        with self._lock:
            zeilen = self._db.execute('SELECT id, art, titel, text, quelle FROM wissen').fetchall()
        treffer = []
        for rid, art, titel, text, quelle in zeilen:
            kopf = set(_woerter(titel + ' ' + rid))
            rumpf = set(_woerter(text))
            punkte = 3 * len(worte & kopf) + len(worte & rumpf)
            if punkte:
                treffer.append((punkte, rid, art, titel, text, quelle))
        treffer.sort(key=lambda t: (-t[0], t[1]))
        return [{'id': rid, 'art': art, 'titel': titel, 'text': text, 'quelle': quelle, 'punkte': punkte}
                for punkte, rid, art, titel, text, quelle in treffer[:limit]]

    def kontext(self, frage, limit=5, zeichen=2400):
        """Ein Textblock mit den Treffern für den Prompt von Cockpit oder Master-Chat. Leer, wenn nichts passt."""
        zeilen, laenge = [], 0
        for t in self.suche(frage, limit):
            zeile = f'[{t["id"]}] {t["titel"]} – {t["text"]} (Quelle: {t["quelle"]})'
            if laenge + len(zeile) > zeichen:
                break
            zeilen.append(zeile)
            laenge += len(zeile)
        return '\n'.join(zeilen)

    def anzahl(self):
        with self._lock:
            return self._db.execute('SELECT COUNT(*) FROM wissen').fetchone()[0]

    def close(self):
        with self._lock:
            self._db.close()
