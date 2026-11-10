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
                  '--architecture', str(arch), '--shell', shell, '--ohne-fenster']
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

    def aufruf(self, methode, pfad, nutzlast=None, timeout=60):
        k = self._verbindung(timeout)
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


def karte_per_tastatur(karte, eingabe=input):
    """Nur ein Mensch am Terminal entscheidet: j = erlauben, s = erlauben und für die Sitzung merken, n = ablehnen. Eine Leerzeile (etwa ein übrig
    gebliebenes Enter) und jede andere Eingabe zählt nicht: es wird nachgefragt. Nur das Ende der Eingabe lehnt ab."""
    while True:
        try:
            antwort = eingabe('Erlauben? [j]a / [s]itzung / [n]ein: ').strip().lower()
        except EOFError:
            return 'ablehnen'
        if antwort in ('j', 'ja'):
            return 'erlauben'
        if antwort in ('s', 'sitzung'):
            return 'sitzung'
        if antwort in ('n', 'nein'):
            return 'ablehnen'


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


def modelle_zeigen(client, ausgabe=print):
    status, out = client.aufruf('GET', '/api/harness/modelle')
    if status != 200:
        ausgabe(f"Modelle nicht lesbar ({status}): {out.get('message') or out}")
        return
    for m in out.get('modelle', []):
        marke = 'geladen' if m.get('geladen') else ('passt' if m.get('passt') else 'passt nicht: ' + str(m.get('grund') or '')[:80])
        ausgabe(f"  {m.get('id')}  [{marke}]")
    ausgabe('Laden mit: /modell <id>')


def modell_laden(client, rezept, ausgabe=print):
    """Dieselbe Tür wie die Harness-Shell (POST /api/model/load); Speicherprüfung und Fehlertexte kommen vom Server. Dauert bis zu Minuten."""
    ausgabe(f'Lade Modell „{rezept}“ … das kann einige Minuten dauern.')
    status, out = client.aufruf('POST', '/api/model/load', {'recipe_id': rezept}, timeout=1800)
    if status != 200:
        ausgabe(f"Modell nicht geladen ({status}): {out.get('message') or out}")
        return False
    ausgabe('Modell geladen.')
    return True


def nachricht_senden(client, sid, text, karte_beantworten, ausgabe=print, wiederholt=False):
    status, out = client.aufruf('POST', f'/api/harness/sitzungen/{sid}/nachricht', {'text': text})
    if status != 200:
        ausgabe(f"Nachricht abgelehnt ({status}): {out.get('message') or out}")
        return 'fehler'
    if out.get('status') == 'kein_modell' or not out.get('antwort_id'):
        auto = out.get('auto_laden') or {}
        if auto.get('rezept') and not wiederholt and modell_laden(client, auto['rezept'], ausgabe):       # Auto-Laden nur, wenn der Katalog es für dieses Rezept freistellt (wie die Shell)
            return nachricht_senden(client, sid, text, karte_beantworten, ausgabe, wiederholt=True)
        ausgabe(str(out.get('grund') or out.get('message') or out))
        ausgabe('Modelle ansehen: /modell, laden: /modell <id>')
        return 'kein_modell'
    return antwort_zeigen(client, out['antwort_id'], karte_beantworten, ausgabe)


RELAY_PORT = 47635
RELAY_HOST = '127.0.0.1'


def relay_datei(wurzel):
    return Path(wurzel) / 'runtime_data' / 'orca_bruecke.json'


def frage_stellen(client, sid, text, sperre):
    """Eine Frage über die offene Sitzung; Freigabekarten werden abgelehnt und im Text vermerkt (die Entscheidung bleibt dem Captain im Terminal-Chat)."""
    zeilen, abgelehnt = [], []

    def sammeln(*a, end=chr(10), flush=False):
        zeilen.append(''.join(str(x) for x in a) + end)

    def ablehnen(karte):
        abgelehnt.append(f"{karte.get('werkzeug')} → {karte.get('ziel')}")
        return 'ablehnen'

    with sperre:
        ende = nachricht_senden(client, sid, text, ablehnen, sammeln)
    antwort = ''.join(zeilen).strip()
    if abgelehnt:
        antwort += (chr(10) * 2 + '[Freigabe nötig, abgelehnt: ' + '; '.join(abgelehnt)
                    + ' – nur der Captain im Terminal-Chat (SEDRA_AGENT.bat) kann das erlauben.]')
    return {'antwort': antwort, 'ende': ende, 'abgelehnt': abgelehnt}


def dienst(client, sid, wurzel, port=RELAY_PORT, sperre=None, blockieren=True):
    """Ein kleiner Loopback-Dienst vor der Sitzung: POST /frage {text} → {antwort}; GET /status. Das Token des SEDRA-Servers verlässt diesen Prozess nie;
    der Dienst nimmt keine Freigaben an. Jeder lokale Prozess kann dem Modell Fragen stellen, nicht mehr."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    sperre = sperre or threading.Lock()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *_a):
            pass

        def _senden(self, code, daten):
            roh = json.dumps(daten, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(roh)))
            self.end_headers()
            self.wfile.write(roh)

        def do_GET(self):
            if self.path == '/status':
                self._senden(200, {'sitzung': sid, 'beschaeftigt': sperre.locked()})
            else:
                self._senden(404, {'fehler': 'unbekannt'})

        def do_POST(self):
            try:
                laenge = int(self.headers.get('Content-Length') or 0)
                nutzlast = json.loads(self.rfile.read(laenge) or b'{}') if 0 <= laenge <= 65536 else {}
            except ValueError:
                nutzlast = {}
            if self.path == '/frage' and isinstance(nutzlast.get('text'), str) and nutzlast['text'].strip():
                self._senden(200, frage_stellen(client, sid, nutzlast['text'], sperre))
            elif self.path == '/modell' and isinstance(nutzlast.get('id'), str):
                with sperre:
                    ok = modell_laden(client, nutzlast['id'], lambda *a, **k: None)
                self._senden(200, {'geladen': ok})
            else:
                self._senden(400, {'fehler': 'text_fehlt'})

    srv = ThreadingHTTPServer((RELAY_HOST, port), H)
    datei = relay_datei(wurzel)
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(json.dumps({'port': srv.server_port, 'pid': os.getpid()}), encoding='utf-8')
    def aufraeumen():
        try:
            datei.unlink()
        except OSError:
            pass

    if not blockieren:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv, aufraeumen
    try:
        srv.serve_forever()
    finally:
        aufraeumen()


def frage_an_dienst(wurzel, text, port=None, timeout=1800):
    """Der Client zum Dienst: die Antwort als Text; None, wenn der Dienst nicht läuft."""
    if port is None:
        try:
            port = int(json.loads(relay_datei(wurzel).read_text(encoding='utf-8'))['port'])
        except (OSError, ValueError, KeyError):
            port = RELAY_PORT
    k = http.client.HTTPConnection(RELAY_HOST, port, timeout=timeout)
    try:
        k.request('POST', '/frage', body=json.dumps({'text': text}).encode('utf-8'), headers={'Content-Type': 'application/json'})
        r = k.getresponse()
        return json.loads(r.read().decode('utf-8', 'replace')).get('antwort', '')
    except (OSError, ValueError):
        return None
    finally:
        k.close()


def main(argv=None):
    p = argparse.ArgumentParser(prog='sedra-orca-bruecke', description='SEDRA als Agent im Terminal (Orca)')
    p.add_argument('--root', default=None, help='SEDRA-Ordner (Standard: der Ordner dieses Pakets)')
    p.add_argument('--projekt', default=None, help='Harness-Projekt (Standard: das Standardprojekt)')
    p.add_argument('--titel', default='Orca-Sitzung')
    p.add_argument('--einmal', metavar='TEXT', help='eine Nachricht senden, Antwort ausgeben, beenden (Karten werden abgelehnt)')
    p.add_argument('--dienst', action='store_true', help='Dauerdienst: Server und Sitzung offen halten, Fragen über --frage (Loopback, keine Freigaben)')
    p.add_argument('--frage', metavar='TEXT', help='eine Frage an den laufenden Dienst stellen und die Antwort ausgeben')
    p.add_argument('--modell', metavar='ID', help='mit --dienst: dieses Rezept beim Start laden')
    p.add_argument('--replace', action='store_true', help='ein bereits laufendes SEDRA vorher beenden')
    p.add_argument('--python', default=None, help='Python für den Server (Standard: dieses)')
    a = p.parse_args(argv)
    if a.frage:
        antwort = frage_an_dienst(a.root or paket_wurzel(), a.frage)
        if antwort is None:
            print('Kein SEDRA-Dienst erreichbar. Starten mit: SEDRA_AGENT.bat --dienst', file=sys.stderr)
            return 3
        print(antwort)
        return 0
    try:
        server = Server(a.root or paket_wurzel(), python=a.python, ersetzen=a.replace)
    except RuntimeError as exc:
        print('SEDRA konnte nicht gestartet werden:', exc, file=sys.stderr)
        return 3
    try:
        client = Client(server.port, server.token)
        sid = sitzung_anlegen(client, a.projekt, a.titel)
        if a.dienst:
            if a.modell:
                modell_laden(client, a.modell)
            print(f'SEDRA-Dienst bereit · Sitzung {sid} · Port {RELAY_PORT} · Strg+C beendet (Server und Modell werden mit beendet)', flush=True)
            try:
                dienst(client, sid, a.root or paket_wurzel())
            except KeyboardInterrupt:
                pass
            return 0
        if a.einmal:
            ende = nachricht_senden(client, sid, a.einmal, karte_immer_ablehnen)
            return 1 if ende in ('fehler', 'abgebrochen', 'kein_modell') else 0
        sperre, aufraeumen = threading.Lock(), None
        try:                                    # dieselbe Sitzung ist auch für Fragen von außen offen (Loopback, ohne Freigaben)
            _srv, aufraeumen = dienst(client, sid, a.root or paket_wurzel(), sperre=sperre, blockieren=False)
            relay = f' · Fragen von außen: SEDRA_AGENT.bat --frage "…" (Port {RELAY_PORT})'
        except OSError:
            relay = ' · Port für Fragen von außen belegt (ein anderer SEDRA-Chat läuft)'
        print(f'SEDRA im Terminal · Sitzung {sid}{relay} · /modell zeigt und lädt Modelle, /ende beendet, Strg+C bricht eine Antwort ab')
        while True:
            try:
                text = input('\nDu › ').strip()
            except (EOFError, KeyboardInterrupt):
                break
            if text in ('/ende', '/exit', '/quit'):
                break
            if text == '/modell':
                modelle_zeigen(client)
                continue
            if text.startswith('/modell '):
                modell_laden(client, text.split(None, 1)[1].strip())
                continue
            if text:
                try:
                    with sperre:
                        print('SEDRA › ', end='', flush=True)
                        nachricht_senden(client, sid, text, karte_per_tastatur)
                except KeyboardInterrupt:
                    print('\n[abgebrochen]')
        if aufraeumen:
            aufraeumen()
        return 0
    finally:
        server.beenden()


if __name__ == '__main__':
    sys.exit(main())
