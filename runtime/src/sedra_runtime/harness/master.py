"""Master-Modus der Harness-Shell (docs/SPEC_MASTER_MODUS_v1_ENTWURF.md, MM-01 bis MM-16; Captain 16.11.2026).

Der Captain schaltet den Master-Modus je Sitzung ein (Oberfläche, hinter der Tür). Solange er an ist, deckt er Dateien, Läufe, Modelle und
Befehle **ohne Karte** – eingegrenzt auf die Muster `master` des Projekts und mit einer **Sperrliste** für Befehle. Er macht nur aus „Karte“ ein
„gedeckt“: nie `verboten`, nie ein harter Vorbehalt, nie eine Warnkarte, nie der weiche Vorbehalt der Oberfläche, nie ungesehener Code (G4).
Das entscheidet `deckung.deckt` (Quelle 3b) und `freigabe.Kiste.aufruf`; hier liegen nur die reinen Prüfungen und der Zustand im Speicher.

Der Zustand lebt **nur im Speicher** des Servers (je Sitzung): er endet mit dem Aus-Knopf, mit der Sitzung, nach 24 Stunden und mit dem Neustart.
Jeder Fehler in dieser Datei heißt „nicht gedeckt“ (Karte), nie ein stilles Freigeben (MM-14).

Die Sperrliste ist eine Prüfung der **Befehlszeile**, kein Käfig: was ein gestartetes Skript selbst tut, sieht sie nicht (Spec §6).
Harness-Code (Vorbehalt): SEDRA ändert diese Datei nicht an sich selbst."""
from __future__ import annotations

import re
import threading
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath

from . import befehl as befehl_mod
from .katalog import passt, pfad_normal

HOECHSTDAUER = timedelta(hours=24)          # MM-03 / O-5: gleiche Grenze wie die Sitzungs-Erlaubnis (FS-14)
LOESCHEN_MAX = 20                           # MM-09: ab mehr Löschzielen immer Karte
LOESCHEN_OHNE_KARTE = False                 # v1 (O-2): Löschbefehle bleiben Karte; eine Lockerung braucht eine Entscheidung des Captains und G4

DATEI_LESEN = ('datei_lesen', 'dateien_auflisten', 'suchen')
DATEI_SCHREIBEN = ('datei_schreiben', 'datei_aendern')
LAUF_MODELL = ('lauf_starten', 'lauf_stoppen', 'modell_laden', 'modell_entladen')
DECKT = DATEI_LESEN + DATEI_SCHREIBEN + ('befehl',) + LAUF_MODELL      # MM-05: alles andere bleibt unverändert

# ---------------------------------------------------------------- Sperrliste (MM-07)
NETZ = frozenset({'curl', 'wget', 'invoke-webrequest', 'iwr', 'invoke-restmethod', 'irm', 'ssh', 'scp', 'sftp', 'ftp', 'tftp', 'nc', 'ncat', 'telnet',
                  'test-netconnection', 'start-bitstransfer'})
INSTALLIEREN = frozenset({'winget', 'choco', 'scoop', 'yarn', 'pnpm', 'npx', 'bun', 'msiexec'})
LOESCHEN = frozenset({'del', 'erase', 'rm', 'rmdir', 'rd', 'remove-item', 'ri', 'format', 'cipher', 'sdelete'})
SHELL = frozenset({'powershell', 'pwsh', 'cmd', 'bash', 'sh', 'zsh', 'wsl', 'wscript', 'cscript', 'mshta', 'rundll32', 'regsvr32', 'certutil', 'bitsadmin',
                   'start', 'explorer', 'schtasks', 'reg', 'sc', 'net', 'netsh', 'taskkill', 'stop-process', 'kill', 'invoke-expression', 'iex'})
PIP = frozenset({'install', 'download', 'uninstall', 'wheel'})
NPM = frozenset({'install', 'i', 'ci', 'add', 'update', 'up', 'upgrade', 'publish', 'exec', 'x', 'uninstall', 'remove', 'link'})
GIT_GESPERRT = frozenset({'push', 'fetch', 'pull', 'clone', 'remote', 'merge', 'rebase', 'update-ref', 'clean', 'config', 'filter-branch', 'rm', 'gc', 'prune',
                          'cherry-pick', 'revert', 'am', 'apply', 'submodule', 'worktree'})
GIT_ZWEIGE = frozenset({'main', 'master'})
PY_MODULE = frozenset({'pip', 'ensurepip', 'http.server', 'urllib', 'urllib.request', 'webbrowser', 'ftplib', 'smtplib', 'socketserver', 'xmlrpc', 'venv', 'zipapp'})
PROGRAMM_ENDUNG = re.compile(r'\.(exe|cmd|bat|ps1|com)$')
LAUFWERK = re.compile(r'^[A-Za-z]:')
SCHEMA = re.compile(r'^[A-Za-z][A-Za-z0-9+.-]*://')


class MasterFehler(ValueError):
    """Ungültiges Feld `master` oder ungültige Eingabe; der Text nennt den Grund."""


def schluessel(sitzung_id):
    """Der Schlüssel, unter dem Befehle und Läufe unter dem Master laufen (`kontext['aufgabe_id']`) und mit dem Aus sie beendet."""
    return f'master:{sitzung_id}'


def jetzt():
    return datetime.now().astimezone()


def _iso(z):
    return z.isoformat(timespec='seconds')


# ---------------------------------------------------------------- MM-01: das Feld `master`
def muster_pruefen(roh):
    """Die Muster des Feldes `master` (Liste von Texten relativ zur Wurzel, ohne `..` und Laufwerk) – oder MasterFehler. Fehlt es: leere Liste (kein Master)."""
    if roh is None:
        return []
    if not isinstance(roh, list):
        raise MasterFehler('master_ungueltig: eine Liste von Mustern relativ zur Wurzel')
    out = []
    for m in roh:
        if not isinstance(m, str) or not m.strip():
            raise MasterFehler('master_ungueltig: jedes Muster ist ein nicht leerer Text')
        p = m.strip().replace('\\', '/')
        if p.startswith('/') or LAUFWERK.match(p) or '..' in PurePosixPath(p).parts:
            raise MasterFehler(f'master_ungueltig: „{m}“ – nur Muster relativ zur Wurzel, ohne „..“ und ohne Laufwerk')
        if p not in out:
            out.append(p)
    return out


def _im_muster(muster, werkzeug, rel):
    probe = 'datei_lesen'
    if rel.split('/')[0] == '..' or rel.startswith('/') or LAUFWERK.match(rel):
        return False
    return any(passt(m, probe, rel) or (werkzeug in ('dateien_auflisten', 'suchen') and passt(m, probe, rel + '/x')) for m in muster)


# ---------------------------------------------------------------- MM-07 bis MM-09: Sperrliste für `befehl`
def _programm(token):
    name = str(token or '').replace('\\', '/').rsplit('/', 1)[-1].strip('"\'').casefold()
    return PROGRAMM_ENDUNG.sub('', name)


def _wie_pfad(t):
    return ('/' in t or '\\' in t or LAUFWERK.match(t) is not None or t.startswith('~') or t == '..' or t == '.'
            or ('%' in t and t.count('%') >= 2) or t.startswith('$'))


def _schalter(t):
    return t.startswith('-') or (t.startswith('/') and len(t) <= 3 and '/' not in t[1:])


def _ausserhalb(t, ordner_abs, wurzel, muster):
    """Grund, wenn das Argument `t` ein Pfad ist, der die Wurzel verlässt; sonst None."""
    if SCHEMA.match(t) or t.startswith('\\\\'):
        return 'Netz oder Netzwerkpfad'
    if '%' in t and t.count('%') >= 2 or t.startswith('$') or t.startswith('~'):
        return 'Umgebungsvariable oder Benutzerordner'
    if not _wie_pfad(t):
        return None
    try:
        ziel = (ordner_abs / t).resolve() if not LAUFWERK.match(t) and not t.startswith(('/', '\\')) else Path(t).resolve()
        rel = ziel.relative_to(wurzel).as_posix()
    except (ValueError, OSError):
        return 'Pfad außerhalb der Wurzel'
    return None


def loeschziele_anzahl(teile, ordner_abs, wurzel):
    """MM-09: Zahl der Löschziele eines Löschbefehls (Platzhalter zählt die Treffer, ein Ordner zählt rekursiv seine Dateien); unlesbar = über die Grenze."""
    n = 0
    try:
        for t in teile[1:]:
            if _schalter(t):
                continue
            ziel = (ordner_abs / t)
            if any(c in t for c in '*?'):
                n += sum(1 for _ in ziel.parent.glob(ziel.name))
            elif ziel.is_dir():
                n += sum(1 for p in ziel.rglob('*') if p.is_file()) or 1
            else:
                n += 1
    except (OSError, ValueError):
        return LOESCHEN_MAX + 1
    return n


def sperre_befehl(zeile, ordner_rel, wurzel, muster):
    """Der Grund, warum der Master diese Befehlszeile **nicht** deckt – oder None (MM-07, MM-08). Jede Ausnahme gilt als Sperre."""
    try:
        teile = befehl_mod.zerlegen(zeile)
    except befehl_mod.BefehlFehler as exc:
        return f'Zeile nicht prüfbar: {exc}'
    try:
        wurzel = Path(wurzel).resolve()
        ordner_abs = (wurzel / str(ordner_rel or '.')).resolve()
        ordner_abs.relative_to(wurzel)
    except (ValueError, OSError):
        return 'Arbeitsordner außerhalb der Wurzel'
    ordner = ordner_abs.relative_to(wurzel).as_posix()
    if not _im_muster(muster, 'befehl', '' if ordner == '.' else ordner) and not any(passt(m, 'datei_lesen', (ordner + '/x') if ordner != '.' else 'x') for m in muster):
        return 'Arbeitsordner liegt nicht im Muster des Master-Modus'
    prog = _programm(teile[0])
    args = [a.strip('"\'') for a in teile[1:]]
    kleinbuchstaben = [a.casefold() for a in args]
    if prog in NETZ:
        return f'Netz ({prog})'
    if prog in INSTALLIEREN:
        return f'Installieren ({prog})'
    if prog in SHELL:
        return f'Shell oder Systemwerkzeug ({prog})'
    if prog in LOESCHEN:
        n = loeschziele_anzahl(teile, ordner_abs, wurzel)
        return f'Löschen ({prog}, {n} Ziele): mehr als {LOESCHEN_MAX} Dateien' if n > LOESCHEN_MAX else f'Löschen ({prog}): bleibt Karte'
    if prog == 'robocopy' and any(a in ('/mir', '/purge') for a in kleinbuchstaben):
        return 'Löschen (robocopy /mir, /purge)'
    if prog in ('pip', 'pip3') and kleinbuchstaben[:1] and kleinbuchstaben[0] in PIP:
        return 'Installieren (pip)'
    if prog in ('npm', 'npm.cmd') and any(a in NPM for a in kleinbuchstaben[:1]):
        return 'Installieren (npm)'
    if prog in ('python', 'python3', 'py', 'pythonw') or re.fullmatch(r'python[0-9.]+', prog):
        if '-c' in kleinbuchstaben or '-' in kleinbuchstaben:
            return 'Programmtext auf der Befehlszeile (python -c)'
        if '-m' in kleinbuchstaben:
            i = kleinbuchstaben.index('-m')
            modul = kleinbuchstaben[i + 1] if i + 1 < len(kleinbuchstaben) else ''
            if modul in PY_MODULE or modul.split('.')[0] in ('urllib', 'http', 'ftplib', 'smtplib'):
                return f'Netz oder Installieren (python -m {modul})'
    if prog in ('node', 'nodejs') and any(a in ('-e', '--eval', '-p', '--print') for a in kleinbuchstaben):
        return 'Programmtext auf der Befehlszeile (node -e)'
    if prog == 'git':
        i = 0
        while i < len(args) and args[i].startswith('-'):            # globale Schalter: -C <pfad> hat ein Argument, -c setzt eine Einstellung
            if args[i] == '-c' or args[i].startswith('--exec-path') or args[i].startswith('--git-dir') or args[i].startswith('--work-tree'):
                return 'Git mit eigener Einstellung oder fremdem Ordner'
            i += 2 if args[i] == '-C' else 1
        sub = kleinbuchstaben[i] if i < len(kleinbuchstaben) else ''
        rest = kleinbuchstaben[i + 1:]
        if sub in GIT_GESPERRT:
            return f'Git ({sub}): Verlauf, Zweige oder Netz'
        if sub in ('checkout', 'switch') and any(a.removeprefix('origin/') in GIT_ZWEIGE for a in rest):
            return 'Git: Wechsel auf main'
        if sub == 'branch' and any(a in ('-d', '-m', '-f', '--delete', '--move', '--force') or (a.startswith('-') and not a.startswith('--') and any(c in a for c in 'dmf') and a.lower() in ('-d', '-m', '-f')) for a in rest):
            return 'Git (branch): Zweig löschen, umbenennen oder verschieben'
        if sub == 'reset' and '--hard' in rest:
            return 'Git (reset --hard)'
        if sub == 'tag' and any(a in ('-d', '--delete', '-f', '--force') for a in rest):
            return 'Git (tag): Tag löschen oder verschieben'
    # Pfade: das Programm selbst (falls mit Pfad) und jedes Argument, auch hinter `--option=`
    kandidaten = [teile[0].strip('"\'')]
    for a in args:
        if _schalter(a):
            if '=' in a:
                kandidaten.append(a.split('=', 1)[1])
            continue
        kandidaten.append(a)
    for t in kandidaten:
        grund = _ausserhalb(t, ordner_abs, wurzel, muster)
        if grund:
            return f'{grund}: {t[:80]}'
    return None


def sperrliste_klartext():
    """Die Sperrliste in einem Satz für die Oberfläche und die Tür (MM-11): was der Master-Modus nicht deckt."""
    return ('Netz (curl, wget, git fetch/pull …), Installieren (pip, npm, winget …), Git-Verlauf und Zweige (push, merge, rebase, Wechsel auf main …), '
            'Löschen (bleibt Karte), Shells und Systemwerkzeuge (powershell, cmd, python -c …), jeder Pfad außerhalb der Wurzel; dazu bleiben alle festen Vorbehalte, '
            'Code der Oberfläche und ungesehener Code bei der Karte')


# ---------------------------------------------------------------- MM-05, MM-06: Deckung (rein)
def pruefen_deckung(muster, wurzel, werkzeug, ziel, args, *, schreibbereich=None):
    """Der Grund der Nicht-Deckung – oder None, wenn der Master diesen Aufruf deckt. Reine Funktion; sie kennt keine Sitzung und keine Vorbehalte
    (die prüft vorher `freigabe.einstufung`; `entscheiden` fügt sie für fremde Harnesses hinzu)."""
    if werkzeug not in DECKT:
        return f'Werkzeug {werkzeug} gehört nicht zum Master-Modus'
    if werkzeug in LAUF_MODELL:
        return None
    if werkzeug == 'befehl':
        a = args if isinstance(args, dict) else {}
        return sperre_befehl(a.get('befehl'), a.get('ordner') or '.', wurzel, muster)
    rel = pfad_normal(ziel)
    if not _im_muster(muster, werkzeug, rel):
        return 'Pfad liegt nicht im Muster des Master-Modus'
    if werkzeug in DATEI_SCHREIBEN and schreibbereich is not None and not any(passt(m, werkzeug, rel) for m in schreibbereich):
        return 'Pfad liegt nicht im Schreibbereich'
    return None


# ---------------------------------------------------------------- MM-03: Zustand im Speicher
class Zustand:
    """Die Sitzungen mit Master-Modus. Nur im Speicher (Neustart = alles aus). Sperre für Zähler und Wechsel; `melden(name, daten)` und `audit(event, payload)` optional."""

    def __init__(self, audit=None, melden=None):
        self.audit, self.melden = audit, melden
        self._sperre = threading.RLock()
        self._an = {}                                   # sitzung_id → {projekt, muster, seit, bis, aufrufe, gesperrt}

    def _sagen(self, event, payload):
        if self.audit is not None:
            try: self.audit(event, payload)
            except Exception: pass

    def _melden(self, sitzung_id, aktiv):
        if self.melden is not None:
            try: self.melden('harness.master', {'sitzung_id': sitzung_id, 'aktiv': aktiv})
            except Exception: pass

    def an(self, sitzung_id, projekt, muster, *, jetzt_z=None):
        muster = muster_pruefen(muster)
        if not muster:
            raise MasterFehler('master_nicht_moeglich: das Projekt hat kein Feld „master“ in local_config/harness_projekte.yaml')
        jetzt_z = jetzt_z or jetzt()
        befehl_mod.RUECKNAHME.vergessen(schluessel(sitzung_id))          # ein früheres Aus soll nicht den nächsten Befehl abbrechen
        with self._sperre:
            e = {'projekt': projekt, 'muster': muster, 'seit': _iso(jetzt_z), 'bis': _iso(jetzt_z + HOECHSTDAUER), 'aufrufe': 0, 'gesperrt': 0}
            self._an[str(sitzung_id)] = e
        self._sagen('HARNESS_MASTER_AN', {'sitzung_id': sitzung_id, 'projekt': projekt, 'muster': muster, 'bis': e['bis']})
        self._melden(sitzung_id, True)
        return dict(e)

    def aus(self, sitzung_id, grund='captain'):
        """Schaltet aus (Klasse N, jederzeit). Gibt den letzten Stand zurück oder None, wenn er nicht an war."""
        with self._sperre:
            e = self._an.pop(str(sitzung_id), None)
        if e is not None:
            befehl_mod.RUECKNAHME.ausloesen(schluessel(sitzung_id))        # MM-04: ein laufender `befehl` unter dem Master endet jetzt
            self._sagen('HARNESS_MASTER_AUS', {'sitzung_id': sitzung_id, 'grund': grund, 'aufrufe': e['aufrufe'], 'gesperrt': e['gesperrt']})
            self._melden(sitzung_id, False)
        return e

    def _aktuell(self, sitzung_id, jetzt_z):
        e = self._an.get(str(sitzung_id))
        if e is None:
            return None
        try:
            if jetzt_z >= datetime.fromisoformat(e['bis']):
                self._an.pop(str(sitzung_id), None)
                befehl_mod.RUECKNAHME.ausloesen(schluessel(sitzung_id))
                self._sagen('HARNESS_MASTER_AUS', {'sitzung_id': sitzung_id, 'grund': 'ablauf', 'aufrufe': e['aufrufe'], 'gesperrt': e['gesperrt']})
                self._melden(sitzung_id, False)
                return None
        except (ValueError, TypeError):
            self._an.pop(str(sitzung_id), None)
            return None
        return e

    def stand(self, sitzung_id, jetzt_z=None):
        """{aktiv, projekt, muster, seit, bis, aufrufe, gesperrt} (MM-11)."""
        with self._sperre:
            e = self._aktuell(sitzung_id, jetzt_z or jetzt())
            return dict(e, aktiv=True) if e else {'aktiv': False}

    def letzter_grund(self, sitzung_id, werkzeug, ziel):
        """Warum der Master genau diesen Aufruf (Werkzeug und Ziel) zuletzt nicht gedeckt hat (für die Karte) – oder None."""
        with self._sperre:
            e = self._an.get(str(sitzung_id))
            l = e.get('letzter') if e else None
            return l[2] if l and l[0] == werkzeug and l[1] == str(ziel) else None

    def aktiv(self, sitzung_id, jetzt_z=None):
        return bool(self.stand(sitzung_id, jetzt_z).get('aktiv'))

    def alle(self):
        with self._sperre:
            return [dict(e, sitzung_id=s) for s, e in self._an.items()]

    def deckt(self, sitzung_id, projekt, wurzel, werkzeug, ziel, args, *, schreibbereich=None, jetzt_z=None):
        """{sitzung_id, regel, nr} – oder None (keine Deckung; ein Fehler gilt auch als keine Deckung). Zählt den Aufruf; eine Sperre zählt als `gesperrt`
        und schreibt `HARNESS_MASTER_NICHT` ins Audit."""
        try:
            with self._sperre:
                e = self._aktuell(sitzung_id, jetzt_z or jetzt())
                if e is None or e['projekt'] != projekt:
                    return None
                grund = pruefen_deckung(e['muster'], wurzel, werkzeug, ziel, args, schreibbereich=schreibbereich)
                e['letzter'] = (werkzeug, str(ziel), grund)
                if grund:
                    if werkzeug in DECKT:
                        e['gesperrt'] += 1
                        self._sagen('HARNESS_MASTER_NICHT', {'sitzung_id': sitzung_id, 'werkzeug': werkzeug, 'ziel': str(ziel)[:300], 'grund': grund})
                    return None
                e['aufrufe'] += 1
                return {'sitzung_id': str(sitzung_id), 'regel': 'master', 'nr': e['aufrufe']}
        except Exception:
            return None


# ---------------------------------------------------------------- MM-13: Schnittstelle für fremde Harnesses (nur festgehalten)
FREMDE_RECHTE = ('berechtigungsmodus', 'werkzeug_freischalten', 'netz', 'mcp', 'hook', 'sandbox', 'plugin', 'einstellung')
SHELL_ZEICHEN = re.compile(r'[|<>&;`]|\$\(')


def entscheiden(muster, *, werkzeug, ziel, args, herkunft, wurzel, schreibbereich=None, art='aufruf'):
    """Die eine Entscheidungsfunktion, die ein späterer Anschluss fremder Harnesses aufruft: {'entscheidung': 'gedeckt'|'karte', 'regel', 'grund'}.
    Rein: kein Zustand, kein `approve`. Der Anschluss prüft vorher, dass die Sitzung den Master an hat (`Zustand.aktiv`), und gibt nur bei `gedeckt` über den
    Guard frei (jede solche Stelle braucht einen Eintrag in desk/freigabeklasse.APPROVE_STELLEN).
    Nie gedeckt: `art` ≠ `aufruf` oder eine Rechte-Frage des fremden Harness selbst (FREMDE_RECHTE); jeder Pfad und jede Zeile außerhalb der Wurzel; harte Vorbehalte;
    Befehlszeilen mit Shell-Zeichen; `herkunft` ≠ `fremd` ist keine Anwendung dieser Funktion (dafür gibt es `Zustand.deckt`)."""
    karte = lambda grund: {'entscheidung': 'karte', 'regel': 'master', 'grund': grund}
    try:
        if herkunft != 'fremd':
            return karte('herkunft_unbekannt')
        if art != 'aufruf' or str(werkzeug or '').casefold() in FREMDE_RECHTE:
            return karte('fremdes_recht: Rechte des fremden Harness selbst entscheidet nur der Captain')
        if werkzeug == 'befehl':
            zeile = (args or {}).get('befehl') if isinstance(args, dict) else None
            if SHELL_ZEICHEN.search(str(zeile or '')):
                return karte('shell_zeichen: die Zeile ist mit Pipes, Umleitungen oder „;“ nicht prüfbar')
        from . import vorbehalte
        vorb = vorbehalte.pruefen(werkzeug, ziel, args if isinstance(args, dict) else {}, True)
        if vorb or vorbehalte.pruefen_lesen(werkzeug, ziel):
            return karte(vorb or 'Lesen gesperrt')
        grund = pruefen_deckung(muster_pruefen(muster), wurzel, werkzeug, ziel, args, schreibbereich=schreibbereich)
        return karte(grund) if grund else {'entscheidung': 'gedeckt', 'regel': 'master', 'grund': None}
    except Exception as exc:                                             # MM-14: jeder Fehler = Karte
        return karte(f'fehler: {type(exc).__name__}')
