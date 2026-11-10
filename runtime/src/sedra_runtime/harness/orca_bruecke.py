"""Orca-Brücke: SEDRAs Harness als Agent im Terminal von Orca (`SEDRA_AGENT.bat`, docs/ORCA_ANBINDUNG.md).

Orca kennt nur einen festen Katalog von Agenten, erlaubt aber je Eintrag einen eigenen Startbefehl. Dieser Befehl startet diese Brücke: Sie startet einen
eigenen SEDRA-Server (`uix_start`, ohne Fenster), liest Adresse und Token aus seiner Ausgabe, legt eine Harness-Sitzung an und chattet im Terminal.

Grenzen (ehrlich): Das Token des Servers bleibt im Speicher dieses Prozesses; es wird weder geschrieben noch ausgegeben. Freigabekarten (Klasse H und alle
anderen) beantwortet nur, wer am Terminal tippt – die Brücke bestätigt nie von selbst, auch nicht mit `--einmal`: dort wird jede Karte abgelehnt.
Läuft schon ein SEDRA (Fenster), startet `uix_start` kein zweites; die Brücke meldet das und bricht ab (mit `--replace` wird das laufende beendet).
Harness-Code (Vorbehalt): SEDRA ändert diese Datei nicht an sich selbst."""
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

URL_MUSTER = re.compile(r'http://127\.0\.0\.1:(\d+)/#(\S+)')
START_WARTEN_S = 180


def paket_wurzel():
    """Der SEDRA-Ordner (enthält runtime/ und workspace/): zwei Ebenen über runtime/src."""
    return Path(__file__).resolve().parents[4]


def sse_ereignisse(zeilen):
    """Zerlegt die Zeilen eines SSE-Stroms in (id, event, daten)-Tupel; Kommentare und Herzschläge fallen weg."""
    eid, event, daten = None, None, []
    for zeile in zeilen:
        zeile = zeile.rstrip('\r\n')
        if zeile == '':
            if event is not None:
                try:
                    nutzlast = json.loads('\n'.join(daten)) if daten else {}
                except ValueError:
                    nutzlast = {}
                yield eid, event, nutzlast
            eid, event, daten = None, None, []
        elif zeile.startswith(':'):
            continue
        elif zeile.startswith('id:'):
            eid = zeile[3:].strip()
        elif zeile.startswith('event:'):
            event = zeile[6:].strip()
        elif zeile.startswith('data:'):
            daten.append(zeile[5:].lstrip(' '))


class Server:
    """Ein eigener SEDRA-Server als Kindprozess; Adresse und Token stehen nur hier."""

    def __init__(self, wurzel, python=None, ersetzen=False, shell='harness'):
        self.wurzel = Path(wurzel)
        rt = self.wurzel / 'runtime'
        gefunden_arch = sorted((self.wurzel / 'architecture').glob('SEDRA_Architecture_*SELF_DEVELOPMENT')) or sorted((self.wurzel / 'architecture').glob('SEDRA_Architecture_*'))
        arch = gefunden_arch[-1] if gefunden_arch else None
        if arch is None:
            raise RuntimeError('architecture_fehlt: Ordner architecture/SEDRA_Architecture_* nicht gefunden')
        proj = self.wurzel / 'workspace' / 'SEDRA_OS'
        proj.mkdir(parents=True, exist_ok=True)
        befehl = [python or sys.executable, '-B', '-X', 'utf8', '-m', 'sedra_runtime.uix_start', '--root', str(proj),
                  '--architecture', str(arch), '--shell', shell]
        if ersetzen:
            befehl.append('--replace')
        env = dict(os.environ, PYTHONUTF8='1', PYTHONPATH=str(rt / 'src'))
        self.proc = subprocess.Popen(befehl, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                                     env=env, cwd=str(self.wurzel))
        self.port = self.token = None
        self.ausgabe = []
        gefunden = threading.Event()

        def lesen():
            for zeile in self.proc.stdout:
                self.ausgabe.append(zeile.rstrip())
                treffer = URL_MUSTER.search(zeile)
                if treffer and not self.token:
                    self.port, self.token = int(treffer.group(1)), treffer.group(2)
                    gefunden.set()
            gefunden.set()

        threading.Thread(target=lesen, daemon=True).start()
        gefunden.wait(START_WARTEN_S)
        if not self.token:
            self.beenden()
            raise RuntimeError('server_start_gescheitert: ' + ' | '.join(self.ausgabe[-6:]))

    def beenden(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


class Client:
    def __init__(self, port, token):
        self.port, self.token = port, token

    def _verbindung(self, timeout=60):
        return http.client.HTTPConnection('127.0.0.1', self.port, timeout=timeout)

    def aufruf(self, methode, pfad, nutzlast=None):
        k = self._verbindung()
        try:
            kopf = {'X-SEDRA-Token': self.token}
            body = None
            if nutzlast is not None:
                body = json.dumps(nutzlast).encode('utf-8')
                kopf['Content-Type'] = 'application/json'
            k.request(methode, pfad, body=body, headers=kopf)
            r = k.getresponse()
            roh = r.read().decode('utf-8', 'replace')
            try:
                daten = json.loads(roh) if roh else {}
            except ValueError:
                daten = {'message': roh[:300]}
            return r.status, daten
        finally:
            k.close()

    def strom(self, antwort_id):
        k = self._verbindung(timeout=None)
        k.request('GET', f'/api/harness/antworten/{antwort_id}/strom', headers={'X-SEDRA-Token': self.token})
        r = k.getresponse()
        if r.status != 200:
            raise RuntimeError(f'strom_{r.status}')

        def zeilen():
            while True:
                z = r.readline()
                if not z:
                    return
                yield z.decode('utf-8', 'replace')
        try:
            yield from sse_ereignisse(zeilen())
        finally:
            k.close()


def antwort_zeigen(client, antwort_id, karte_beantworten, ausgabe=print):
    """Zeigt eine Antwort live; bei einer Karte fragt `karte_beantworten(karte)` nach dem Weg (erlauben|ablehnen|sitzung) und setzt fort.
    Gibt den Endzustand zurück ('fertig', 'fehler', 'abgebrochen', …)."""
    while antwort_id:
        weiter = None
        ende = 'fertig'
        gezeigt = False
        for _eid, event, d in client.strom(antwort_id):
            if event == 'text.ungeprueft':
                ausgabe(d.get('stueck', ''), end='', flush=True); gezeigt = True
            elif event == 'text.geprueft' and d.get('text'):
                ausgabe(d['text'], end='', flush=True); gezeigt = True
            elif event == 'text.zurueckgehalten':
                ausgabe(f"\n[zurückgehalten: {d.get('grund')}]")
            elif event == 'werkzeug.start':
                ausgabe(f"\n→ {d.get('name')} {d.get('kurz', '')}")
            elif event == 'werkzeug.ende' and d.get('status') not in ('wartet', None):
                ausgabe(f"  ({d.get('status')}, {d.get('dauer_s')} s)")
            elif event == 'karte':
                ausgabe('\n' + '─' * 60)
                ausgabe(f"Freigabe nötig: {d.get('werkzeug')} → {d.get('ziel')}  [Stufe {d.get('stufe')}, Karte {d.get('karte_id')}]")
                if d.get('begruendung'):
                    ausgabe('Grund: ' + str(d['begruendung']))
                if d.get('vorschau'):
                    ausgabe(str(d['vorschau'])[:2000])
                if d.get('warnung'):
                    ausgabe('Warnung: ' + str(d['warnung']))
                weg = karte_beantworten(d)
                status, out = client.aufruf('POST', f"/api/harness/karten/{d['karte_id']}", {'weg': weg})
                if status != 200:
                    ausgabe(f"Karte nicht beantwortet ({status}): {out.get('message') or out}")
                else:
                    weiter = out.get('antwort_id') or (out.get('fortsetzung') or {}).get('antwort_id')
                    if not weiter:
                        ausgabe(f"Entscheidung '{weg}' übermittelt. " + str(out.get('hinweis') or out.get('message') or out.get('status') or ''))
            elif event == 'fehler':
                ausgabe(f"\n[Fehler: {d.get('grund')}]")
            elif event == 'ende':
                ende = d.get('ende') or 'fertig'
        if gezeigt:
            ausgabe('')
        if ende != 'wartet' or not weiter:
            return ende
        antwort_id = weiter
    return 'fertig'


def karte_per_tastatur(karte):
    """Nur ein Mensch am Terminal entscheidet: j = erlauben, s = erlauben und für die Sitzung merken, sonst ablehnen."""
    try:
        eingabe = input('Erlauben? [j]a / [s]itzung / [n]ein: ').strip().lower()
    except EOFError:
        return 'ablehnen'
    return {'j': 'erlauben', 'ja': 'erlauben', 's': 'sitzung', 'sitzung': 'sitzung'}.get(eingabe, 'ablehnen')


def karte_immer_ablehnen(karte):
    return 'ablehnen'


def sitzung_anlegen(client, projekt, titel):
    nutzlast = {'titel': titel}
    if projekt:
        nutzlast['projekt'] = projekt
    status, out = client.aufruf('POST', '/api/harness/sitzungen', nutzlast)
    if status != 200 or not out.get('id'):
        raise RuntimeError(f"sitzung_gescheitert ({status}): {out.get('message') or out}")
    return out['id']


def nachricht_senden(client, sid, text, karte_beantworten, ausgabe=print):
    status, out = client.aufruf('POST', f'/api/harness/sitzungen/{sid}/nachricht', {'text': text})
    if status != 200:
        ausgabe(f"Nachricht abgelehnt ({status}): {out.get('message') or out}")
        return 'fehler'
    if out.get('status') == 'kein_modell' or not out.get('antwort_id'):
        ausgabe(str(out.get('grund') or out.get('message') or out))
        return 'kein_modell'
    return antwort_zeigen(client, out['antwort_id'], karte_beantworten, ausgabe)


def main(argv=None):
    p = argparse.ArgumentParser(prog='sedra-orca-bruecke', description='SEDRA als Agent im Terminal (Orca)')
    p.add_argument('--root', default=None, help='SEDRA-Ordner (Standard: der Ordner dieses Pakets)')
    p.add_argument('--projekt', default=None, help='Harness-Projekt (Standard: das Standardprojekt)')
    p.add_argument('--titel', default='Orca-Sitzung')
    p.add_argument('--einmal', metavar='TEXT', help='eine Nachricht senden, Antwort ausgeben, beenden (Karten werden abgelehnt)')
    p.add_argument('--replace', action='store_true', help='ein bereits laufendes SEDRA vorher beenden')
    p.add_argument('--python', default=None, help='Python für den Server (Standard: dieses)')
    a = p.parse_args(argv)
    try:
        server = Server(a.root or paket_wurzel(), python=a.python, ersetzen=a.replace)
    except RuntimeError as exc:
        print('SEDRA konnte nicht gestartet werden:', exc, file=sys.stderr)
        return 3
    try:
        client = Client(server.port, server.token)
        sid = sitzung_anlegen(client, a.projekt, a.titel)
        if a.einmal:
            ende = nachricht_senden(client, sid, a.einmal, karte_immer_ablehnen)
            return 1 if ende in ('fehler', 'abgebrochen', 'kein_modell') else 0
        print(f'SEDRA im Terminal · Sitzung {sid} · /ende beendet, Strg+C bricht eine Antwort ab')
        while True:
            try:
                text = input('\nDu › ').strip()
            except (EOFError, KeyboardInterrupt):
                break
            if text in ('/ende', '/exit', '/quit'):
                break
            if text:
                try:
                    print('SEDRA › ', end='', flush=True)
                    nachricht_senden(client, sid, text, karte_per_tastatur)
                except KeyboardInterrupt:
                    print('\n[abgebrochen]')
        return 0
    finally:
        server.beenden()


if __name__ == '__main__':
    sys.exit(main())
