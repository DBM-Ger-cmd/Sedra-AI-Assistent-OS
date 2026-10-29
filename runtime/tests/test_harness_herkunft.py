"""N5 der Harness-Shell Stufe 3: Herkunft der Antwort (S7, K14). Rein mit Tabellen-Attrappen; dazu unter Windows ein echter Server und echte Unterprozesse."""
import http.client
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.harness import befehl as befehl_mod
from guppi_runtime.harness import herkunft
from guppi_runtime.uix_server import UIXHub, make_server
from test_uix_harness_api import ARCH, anfrage


class RegisterTests(unittest.TestCase):
    def test_laufende_und_juengst_beendete_bleiben_dann_nicht(self):
        zeit = [0.0]
        r = herkunft.Register(clock=lambda: zeit[0])
        r.registrieren(10, start=111)
        r.registrieren(20, start=222)
        r.austragen(20)
        self.assertEqual(r.eintraege(), {10: 111, 20: 222})
        zeit[0] = herkunft.NACHLAUF_S + 1
        self.assertEqual(r.eintraege(), {10: 111}, 'nach einer Stunde wird ein beendeter Prozess vergessen, ein laufender nie')


class StammtVonTests(unittest.TestCase):
    TABELLE = {1: 0, 100: 1, 101: 100, 102: 101, 200: 1, 201: 200}          # 102 ist ein Enkel von 100; 201 ein Kind von 200 (Browser)

    def test_kind_enkel_und_fremde(self):
        reg = {100: None}
        for pid in (100, 101, 102):
            self.assertTrue(herkunft.stammt_von(pid, reg, self.TABELLE), pid)
        for pid in (1, 200, 201, 999):
            self.assertFalse(herkunft.stammt_von(pid, reg, self.TABELLE), pid)
        self.assertFalse(herkunft.stammt_von(102, {}, self.TABELLE))

    def test_toter_vorfahre_zaehlt_wenn_im_register(self):
        tabelle = {300: 555, 1: 0}                       # 555 lebt nicht mehr (nicht in der Tabelle): ein abgelöstes Kind eines beendeten befehl
        self.assertTrue(herkunft.stammt_von(300, {555: 42}, tabelle))
        self.assertFalse(herkunft.stammt_von(300, {556: 42}, tabelle))

    def test_wiederverwendete_pid_wird_an_der_startzeit_erkannt(self):
        tabelle = {100: 1, 101: 100, 1: 0}
        self.assertFalse(herkunft.stammt_von(101, {100: 5}, tabelle, start_von=lambda pid: 9), 'PID 100 gehört jetzt einem anderen Prozess')
        self.assertTrue(herkunft.stammt_von(101, {100: 5}, tabelle, start_von=lambda pid: 5))
        self.assertTrue(herkunft.stammt_von(101, {100: 5}, tabelle, start_von=lambda pid: None), 'nicht lesbar → im Zweifel abgelehnt')

    def test_schleifen_in_der_tabelle_haengen_nicht(self):
        self.assertFalse(herkunft.stammt_von(1, {99: None}, {1: 2, 2: 1}))


class HerkunftTests(unittest.TestCase):
    def test_pruefung_mit_attrappen_und_audit(self):
        audit = []
        reg = herkunft.Register()
        reg.registrieren(100, start=1)
        h = herkunft.Herkunft(reg, tabelle=lambda: {100: 1, 101: 100, 200: 1, 1: 0}, besitzer=lambda cp, sp: {5001: 101, 5002: 200}.get(cp),
                              start_von=lambda pid: 1, audit=lambda e, p: audit.append((e, p)))
        self.assertEqual(h.pruefen(('127.0.0.1', 5001), 8000), {'ok': False, 'grund': 'von_harness_prozess', 'pid': 101})
        self.assertEqual(audit[-1][0], 'HARNESS_HERKUNFT_ABGELEHNT')
        self.assertEqual(h.pruefen(('127.0.0.1', 5002), 8000), {'ok': True, 'pid': 200})
        out = h.pruefen(('127.0.0.1', 5003), 8000)                       # Gegenstelle nicht aufzulösen: nur Token und Origin gelten, mit Warnung
        self.assertEqual((out['ok'], out['warnung']), (True, 'aufloesung_nicht_moeglich'))
        self.assertEqual(audit[-1][0], 'HARNESS_HERKUNFT_UNGEPRUEFT')

    def test_ausnahme_im_besitzer_wird_zur_warnung(self):
        def kaputt(cp, sp):
            raise OSError('x')
        out = herkunft.Herkunft(herkunft.Register(), besitzer=kaputt).pruefen(('127.0.0.1', 1), 2)
        self.assertEqual((out['ok'], out['warnung']), (True, 'aufloesung_nicht_moeglich'))


@unittest.skipUnless(os.name == 'nt', 'Auflösung der Gegenstelle ist für Windows gebaut')
class EchtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-herkunft-')
        cls.hub = UIXHub(Path(cls.tmp.name) / 'project', ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.port = urlsplit(cls.url).port
        cls.token = urlsplit(cls.url).fragment

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def test_die_gegenstelle_wird_aufgeloest(self):
        import socket
        s = socket.create_connection(('127.0.0.1', self.port))
        try:
            self.assertEqual(herkunft.tcp_besitzer(s.getsockname()[1], self.port), os.getpid())
        finally:
            s.close()
        self.assertIsNone(herkunft.tcp_besitzer(1, 2))
        self.assertEqual(herkunft.prozess_tabelle()[os.getpid()], os.getppid())
        self.assertIsNotNone(herkunft.startzeit(os.getpid()))

    CODE = textwrap.dedent('''
        import http.client, json, sys
        port, token, weg, pfad = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=20)
        c.request('POST', pfad, body=json.dumps({'weg': 'erlauben', 'id': 'x', 'way': 'erlauben'}),
                  headers={'Host': f'127.0.0.1:{port}', 'X-GUPPI-Token': token, 'Content-Type': 'application/json'})
        r = c.getresponse()
        print(r.status, r.read().decode()[:200])
    ''')

    def aus_unterprozess(self, pfad, registriert=True):
        """Ein Kind schreibt/ein Enkel sendet die Anfrage – so wie ein Skript, das ein Agent mit `befehl` startet."""
        kind = ('import subprocess, sys; '
                'sys.exit(subprocess.run([sys.executable, "-c", sys.argv[1]] + sys.argv[2:], capture_output=False).returncode)')
        proc = subprocess.Popen([sys.executable, '-c', kind, self.CODE, str(self.port), self.token, 'x', pfad], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if registriert:
            herkunft.REGISTER.registrieren(proc.pid)            # wie befehl.ausfuehren
        try:
            out, _ = proc.communicate(timeout=60)
        finally:
            herkunft.REGISTER.austragen(proc.pid)
        return out.strip()

    def test_anfrage_aus_einem_harness_prozess_wird_abgelehnt(self):
        for pfad in ('/api/harness/karten/K-00000000', '/api/harness/aufgaben', '/api/harness/vorarbeiter', '/api/decisions/answer'):
            out = self.aus_unterprozess(pfad)
            self.assertTrue(out.startswith('403'), (pfad, out))
            self.assertIn('herkunft_abgelehnt', out)
        ereignisse = [json.loads(l)['event_type'] for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
        self.assertIn('HARNESS_HERKUNFT_ABGELEHNT', ereignisse)

    def test_derselbe_unterprozess_ohne_registrierung_und_der_browser_kommen_durch(self):
        out = self.aus_unterprozess('/api/harness/karten/K-00000000', registriert=False)
        self.assertFalse(out.startswith('403'), 'nicht aus der Harness gestartet → die normale Prüfung gilt (hier: Karte unbekannt)')
        code, body = anfrage(self.url, 'POST', '/api/harness/karten/K-00000000', {'weg': 'erlauben'})
        self.assertEqual(code, 404, body)

    def test_lesen_ist_nicht_betroffen(self):
        proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        herkunft.REGISTER.registrieren(proc.pid)
        try:
            self.assertEqual(anfrage(self.url, 'GET', '/api/harness/karten/K-00000000')[0], 404)
            self.assertEqual(anfrage(self.url, 'GET', '/api/harness/aufgaben')[0], 200)
        finally:
            proc.kill(); proc.wait(); herkunft.REGISTER.austragen(proc.pid)


class BefehlRegistriertTests(unittest.TestCase):
    def test_befehl_traegt_seinen_prozess_ein_und_aus(self):
        from guppi_runtime.core.guard import Guard
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp) / 'p'
            wurzel.mkdir()
            guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(tmp) / 'tokens.json')
            zeile = 'python -c "import time; time.sleep(0.2)"'
            gate = guard.create_gate('M-X', befehl_mod.AKTION, befehl_mod.ziel_text(zeile, '.'), request_binding=befehl_mod.bindung(zeile, '.'))
            token = guard.approve(gate)
            gesehen = []
            echt = herkunft.REGISTER.registrieren
            herkunft.REGISTER.registrieren = lambda pid, start=None: (gesehen.append(pid), echt(pid, start))[1]
            try:
                out = befehl_mod.ausfuehren(wurzel, zeile, '.', 30, guard=guard, mission_id='M-X', token=token)
            finally:
                herkunft.REGISTER.registrieren = echt
            self.assertEqual(out['status'], 'ok', out)
            self.assertEqual(len(gesehen), 1)
            self.assertIn(gesehen[0], herkunft.REGISTER.eintraege(), 'nach dem Ende noch eine Stunde im Register (abgelöste Kinder)')
            self.assertIsNotNone(herkunft.REGISTER._eintraege[gesehen[0]]['ende'])


if __name__ == '__main__':
    unittest.main()
