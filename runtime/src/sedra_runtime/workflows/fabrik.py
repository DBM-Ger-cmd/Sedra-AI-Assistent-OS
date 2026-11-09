"""Die Fabrikhalle: was die Harness gerade tut (Läufe, Aufgaben) und was auf den Captain wartet (offene Freigaben), als eine schlanke Übersicht.

Reine Rechnung auf den Daten der Harness (`harness/lauf.py`, `harness/aufgabe.py`, `harness/freigabe.py`); nichts wird gestartet, gestoppt oder
freigegeben. Pfade, Befehlszeilen und Parameter der Läufe bleiben draußen, nur Name, Zustand, Fortschritt, Dauer und die letzte Zeile gehen an die
Oberfläche. Der Reiter Live der Workflow-Apps zeigt sie über das Verb `fabrik` (workflows/desk.py)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

LETZTE = 6                         # so viele beendete Läufe stehen unter den laufenden
MAX_TEXT = 140
HALT = ('runtime_data', 'fabrik', 'angehalten.json')      # die Haltemarke: solange sie da ist, startet in der Fabrik nichts Neues
STOPP_WARTEN_S = 5


def _zeit(text):
    try:
        z = datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return None
    return z if z.tzinfo else z.replace(tzinfo=timezone.utc)


def _kurz(text, n=MAX_TEXT):
    t = ' '.join(str(text or '').split())
    return t if len(t) <= n else t[:n - 1] + '…'


def lauf_schlank(lauf, jetzt):
    """Ein Lauf für die Anzeige (rein): ohne Pfade, Befehl und Parameter. `dauer_s` vom Start bis zum Ende, laufend bis jetzt."""
    start, ende = _zeit(lauf.get('gestartet')), _zeit(lauf.get('ende'))
    bis = ende or (jetzt if lauf.get('status') == 'laeuft' else None)
    fort = lauf.get('fortschritt') or {}
    prozent = fort.get('prozent')
    return {'id': lauf.get('id'), 'lauf': lauf.get('lauf'), 'name': _kurz(lauf.get('name') or lauf.get('lauf'), 80), 'status': lauf.get('status'),
            'gestartet': lauf.get('gestartet'), 'ende': lauf.get('ende'),
            'dauer_s': int((bis - start).total_seconds()) if start and bis else None,
            'prozent': int(prozent) if isinstance(prozent, (int, float)) and 0 <= prozent <= 100 else None,
            'text': _kurz(fort.get('text')), 'gpu': lauf.get('gpu'), 'aufgabe_id': lauf.get('aufgabe_id'), 'grund': _kurz(lauf.get('grund'), 80) if lauf.get('status') != 'laeuft' else None}


def aufgabe_schlank(a):
    return {'id': a.get('id'), 'titel': _kurz(a.get('titel'), 80), 'zweck': _kurz(a.get('zweck_anzeige') or a.get('zweck'), 120), 'projekt': a.get('projekt'),
            'rest_aufrufe': a.get('rest_aufrufe'), 'rest_min': a.get('rest_min'), 'aufrufe': a.get('aufrufe')}


def karte_schlank(k):
    """Eine offene Entscheidung des Posteingangs (desk/decisions: id, kind, title, created_at) oder eine Karte der Harness (karte_id, werkzeug, ziel)."""
    return {'karte_id': k.get('karte_id') or k.get('id'), 'werkzeug': k.get('werkzeug') or k.get('kind'), 'ziel': _kurz(k.get('ziel') or k.get('title'), 80),
            'begruendung': _kurz(k.get('begruendung') or k.get('summary'), 120), 'angelegt': k.get('angelegt') or k.get('created_at')}


def uebersicht(laeufe, aufgaben, karten, belegt=None, jetzt=None):
    """{'laeufe': {'laufend', 'zuletzt'}, 'aufgaben', 'freigaben': {'anzahl', 'neueste'}, 'belegung', 'zaehler'} (rein).
    `laeufe`: alle Läufe der Register, `aufgaben`: die aktiven Aufgaben (öffentlich), `karten`: alles, was im Posteingang auf den Captain wartet,
    `belegt`: der Lauf, der das Modell hält."""
    jetzt = jetzt or datetime.now(timezone.utc)
    schlank = [lauf_schlank(l, jetzt) for l in (laeufe or []) if isinstance(l, dict)]
    laufend = [l for l in schlank if l['status'] == 'laeuft']
    laufend.sort(key=lambda l: l.get('gestartet') or '')
    fertig = sorted((l for l in schlank if l['status'] != 'laeuft'), key=lambda l: l.get('ende') or l.get('gestartet') or '', reverse=True)[:LETZTE]
    karten = [karte_schlank(k) for k in (karten or []) if isinstance(k, dict)]
    karten.sort(key=lambda k: k.get('angelegt') or '', reverse=True)
    aufg = [aufgabe_schlank(a) for a in (aufgaben or []) if isinstance(a, dict)]
    return {'laeufe': {'laufend': laufend, 'zuletzt': fertig}, 'aufgaben': aufg, 'freigaben': {'anzahl': len(karten), 'neueste': karten[:3]},
            'belegung': ({'id': belegt.get('id'), 'name': _kurz(belegt.get('name') or belegt.get('lauf'), 80)} if isinstance(belegt, dict) else None),
            'zaehler': {'laeuft': len(laufend), 'aufgaben': len(aufg), 'freigaben': len(karten),
                        'fehler': sum(1 for l in fertig if l['status'] in ('fehler', 'verloren'))}}


# ---- Der rote Knopf: Fabrik anhalten ------------------------------------------------------------------------------------------------------------

def halt_pfad(projekt_root):
    return Path(projekt_root).joinpath(*HALT)


def angehalten(projekt_root):
    """Die Haltemarke ({seit, grund, von}) oder None. Wer in der Fabrik etwas startet (Läufe der Harness, der Bau), fragt zuerst hier; ohne Datei läuft alles."""
    try:
        wert = json.loads(halt_pfad(projekt_root).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return wert if isinstance(wert, dict) else None


def anhalten(projekt_root, grund='Notaus durch den Captain', von='captain'):
    """Die Haltemarke setzen (atomar). Ab jetzt lehnt die Harness neue Läufe ab, bis der Captain die Fabrik wieder freigibt."""
    pfad = halt_pfad(projekt_root)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    marke = {'schema': 1, 'seit': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'grund': _kurz(grund, 200), 'von': _kurz(von, 40)}
    fd, tmp = tempfile.mkstemp(prefix='.halt-', suffix='.tmp', dir=str(pfad.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(marke, f, ensure_ascii=False)
        os.replace(tmp, pfad)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return marke


def freigeben(projekt_root):
    """Die Haltemarke entfernen. Gibt zurück, ob die Fabrik angehalten war."""
    try:
        halt_pfad(projekt_root).unlink()
        return True
    except FileNotFoundError:
        return False


def _befehlszeile(pid):
    """Die Befehlszeile eines Prozesses oder None (Windows: CIM, sonst /proc). Dient nur dazu, eine PID aus einer Sperrdatei zu prüfen."""
    try:
        if sys.platform == 'win32':
            r = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                                "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % int(pid)], capture_output=True, text=True, timeout=20)
            return (r.stdout or '').strip() or None
        return Path('/proc/%d/cmdline' % int(pid)).read_bytes().replace(b'\0', b' ').decode('utf-8', 'replace').strip() or None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def bau_prozess(projekt_root, befehlszeile=_befehlszeile):
    """Die PID des laufenden Baus (`runtime_data/bau_schleife.lock`) oder None. Die PID zählt nur, wenn der Prozess dahinter wirklich bau_schleife ist:
    eine tote oder weitergegebene PID trifft nie einen fremden Prozess."""
    try:
        pid = Path(projekt_root, 'runtime_data', 'bau_schleife.lock').read_text(encoding='utf-8', errors='replace').strip()
    except OSError:
        return None
    if not pid.isdigit() or int(pid) == os.getpid():
        return None
    zeile = befehlszeile(int(pid))
    return int(pid) if zeile and 'bau_schleife' in zeile else None


def bau_beenden(pid):
    """Den Baum des Bau-Prozesses beenden (der Bau startet die microVM und Hilfsprozesse). Gibt zurück, ob ein Beenden versucht wurde."""
    if not pid:
        return False
    if sys.platform == 'win32':
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(pid)], capture_output=True)
    else:
        try:
            os.killpg(os.getpgid(pid), 9)
        except OSError:
            return False
    return True


def notaus(h, projekt_root, grund='Notaus durch den Captain', warten_s=STOPP_WARTEN_S):
    """Die Fabrik sofort anhalten. Reihenfolge: erst die Haltemarke (damit in der Zwischenzeit nichts Neues startet), dann alle laufenden Läufe
    gleichzeitig stoppen, die aktiven Aufgaben zurücknehmen und die laufenden Antworten abbrechen. Ein Fehler bei einem Teil hält die anderen nicht auf;
    alles steht im Bericht. `h` ist die Harness (laeufe, aufgaben, stroeme, _audit). Nichts hier wird freigegeben oder neu gestartet."""
    marke = anhalten(projekt_root, grund)
    bericht = {'marke': marke, 'laeufe': [], 'aufgaben': [], 'antworten': [], 'bau': None, 'prozesse': [], 'fehler': []}
    laufende = list(h.laeufe.laufende()) if getattr(h, 'laeufe', None) is not None else []

    def stoppe(lauf):
        try:
            h.laeufe.stoppen(lauf['id'], grund=_kurz(grund, 120), warten_s=warten_s)
            bericht['laeufe'].append(lauf['id'])
        except Exception as exc:                                  # ein Lauf, der schon fertig ist oder sich nicht stoppen lässt, hält die anderen nicht auf
            bericht['fehler'].append('Lauf %s: %s' % (lauf.get('id'), str(exc)[:100]))
    fäden = [threading.Thread(target=stoppe, args=(l,), daemon=True) for l in laufende]
    for f in fäden:
        f.start()
    try:
        from ..harness import befehl as befehl_mod
    except ImportError:
        befehl_mod = None
    if getattr(h, 'aufgaben', None) is not None:
        for a in h.aufgaben.alle('aktiv'):
            try:
                h.aufgaben.zuruecknehmen(a['id'], _kurz(grund, 120))
                if befehl_mod is not None:
                    befehl_mod.RUECKNAHME.ausloesen(a['id'])
                bericht['aufgaben'].append(a['id'])
            except Exception as exc:
                bericht['fehler'].append('Aufgabe %s: %s' % (a.get('id'), str(exc)[:100]))
    try:                                                          # der Bau läuft als eigener Prozess (Manager), nicht als Lauf der Harness
        pid = bau_prozess(projekt_root)
        if pid and bau_beenden(pid):
            bericht['bau'] = pid
    except Exception as exc:
        bericht['fehler'].append('Bau: %s' % str(exc)[:100])
    try:                                                          # Prozesse, die im Live-Reiter noch „läuft“ melden, stehen jetzt als angehalten da
        from . import live
        for satz in live.lesen(projekt_root):
            if satz['zustand'] in ('laeuft', 'wartet') and satz.get('schritt'):
                live.melde(projekt_root, satz['prozess'], satz['schritt'], 'fehler', text='Fabrik angehalten (Notaus)')
                bericht['prozesse'].append(satz['prozess'])
    except Exception as exc:
        bericht['fehler'].append('Live-Meldungen: %s' % str(exc)[:100])
    if getattr(h, 'stroeme', None) is not None:
        for antwort in list(h.stroeme.laufende()):
            try:
                antwort.stoppen()
                bericht['antworten'].append(getattr(antwort, 'id', None))
            except Exception as exc:
                bericht['fehler'].append('Antwort: %s' % str(exc)[:100])
    for f in fäden:
        f.join(timeout=warten_s + 5)
    try:
        h._audit('FABRIK_NOTAUS', {'laeufe': bericht['laeufe'], 'aufgaben': bericht['aufgaben'], 'antworten': len(bericht['antworten']), 'bau': bericht['bau'], 'fehler': len(bericht['fehler']), 'grund': _kurz(grund, 120)})
    except Exception:
        pass
    return bericht

