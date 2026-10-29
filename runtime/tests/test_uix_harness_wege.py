"""N9 der Harness-Shell Stufe 3: alle neuen Wege (404/400/403/200), Ereignisse auf dem gemeinsamen Strom, Audit-Namen, Posteingang für beide Kartenarten."""
import http.client
import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.uix_server import UIXHub, make_server
from test_harness_lauf import SKRIPT
from test_uix_harness_api import ARCH, MODELL, anfrage
from test_uix_harness_lauf import KATALOG, typen


class WegeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-wege-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        (cls.wurzel / 'runtime').mkdir(parents=True)
        (cls.wurzel / 'runtime' / 'probe.py').write_text(SKRIPT, encoding='utf-8')
        projekt = Path(cls.tmp.name) / 'project'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'freigabe_katalog.yaml').write_text(KATALOG, encoding='utf-8')
        (projekt / 'local_config' / 'harness_projekte.yaml').write_text(
            f"projekte:\n  - id: pruef\n    name: Prüfprojekt\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [runtime/**]\n", encoding='utf-8')
        cls.hub = UIXHub(projekt, ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for l in cls.hub.harness.laeufe.laufende():
            try: cls.hub.harness.laeufe.stoppen(l['id'], warten_s=15)
            except Exception: pass
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def setUp(self):
        self.api = self.hub.harness
        self.api.geladen = lambda: (MODELL, None)
        self.api._lauf_typen = typen()
        self.api.vorarbeiter._schreiben({'projekte': {}, 'entscheidungen': {}})
        self.v = self.neu('vorarbeiter')
        self.b = self.neu('bauagent')

    def neu(self, vorlage):
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef', 'vorlage': vorlage})
        self.assertEqual(code, 200, kopf)
        return kopf['id']

    def audit(self):
        return [json.loads(l)['event_type'] for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]

    def ereignisse(self, ab):
        return [(e['event'], e['data']) for e in self.hub.events.since(ab)[0]]

    def test_jeder_neue_weg_antwortet_wie_vorgesehen(self):
        tabelle = [('GET', '/api/harness/vorlagen', 200), ('GET', '/api/harness/aufgaben', 200), ('GET', '/api/harness/aufgaben/T-00000000', 404),
                   ('POST', '/api/harness/aufgaben/T-00000000/zuruecknehmen', 404), ('GET', '/api/harness/vorarbeiter', 200),
                   ('POST', '/api/harness/vorarbeiter', 400), ('DELETE', '/api/harness/vorarbeiter?projekt=gibt-es-nicht', 200),
                   ('POST', '/api/harness/karten/K-00000000', 404), ('POST', '/api/harness/karten/K-00000000/zuruecknehmen', 404),
                   ('GET', '/api/harness/laeufe', 200), ('GET', '/api/harness/laeufe/L-00000000', 404), ('POST', '/api/harness/laeufe/L-00000000/stopp', 404),
                   ('GET', '/api/harness/laeufe/L-00000000/stopp', 404), ('GET', '/api/harness/aufgaben/kaputt', 404), ('GET', '/api/harness/laeufe/x', 404),
                   ('DELETE', '/api/harness/aufgaben', 404), ('POST', '/api/harness/vorlagen', 404)]
        for methode, pfad, erwartet in tabelle:
            code, _body = anfrage(self.url, methode, pfad, {} if methode == 'POST' else None)
            self.assertEqual(code, erwartet, (methode, pfad))

    def test_ohne_token_geht_nichts(self):
        parts = urlsplit(self.url)
        for methode, pfad in (('POST', '/api/harness/aufgaben'), ('POST', '/api/harness/vorarbeiter'), ('POST', '/api/harness/karten/K-00000000'),
                              ('POST', '/api/harness/laeufe/L-00000000/stopp'), ('GET', '/api/harness/aufgaben'), ('GET', '/api/harness/laeufe')):
            c = http.client.HTTPConnection(parts.hostname, parts.port, timeout=10)
            c.request(methode, pfad, body=json.dumps({}) if methode == 'POST' else None, headers={'Content-Type': 'application/json'})
            self.assertEqual(c.getresponse().status, 403, (methode, pfad))
            c.close()

    def test_ereignisse_audit_und_posteingang_fuer_aufgaben_und_ernennung(self):
        ab = self.hub.events.last_id
        code, v = anfrage(self.url, 'POST', '/api/harness/vorarbeiter', {'projekt': 'pruef', 'sitzung_id': self.v})
        self.assertEqual(code, 200, v)
        box = self.api._kiste(self.api._sitzung(self.v))[0]
        r = box.aufruf('aufgabe_vorschlagen', {'titel': 'Probe', 'projekt': 'pruef', 'sitzungen': [self.b], 'erlaubt': [{'werkzeug': 'lauf_starten', 'muster': 'frei_probe'}],
                                               'ende': {'max_aufrufe': 2}})
        self.assertEqual(r['status'], 'ok', r)
        _c, entsch = anfrage(self.url, 'GET', '/api/decisions')
        karten = [d for d in entsch['items'] if d['kind'] == 'harness_aufgabe']
        self.assertEqual(len(karten), 1)
        code, out = anfrage(self.url, 'POST', '/api/decisions/answer', {'id': karten[0]['id'], 'way': 'erlauben', 'note': ''})
        self.assertEqual(code, 200, out)
        _c, danach = anfrage(self.url, 'GET', '/api/decisions')
        self.assertNotIn(karten[0]['id'], [d['id'] for d in danach['items']], 'eine Antwort schließt beide Ansichten')
        _c, kk = anfrage(self.url, 'GET', '/api/harness/karten/' + karten[0]['id'].removeprefix('harness:'))
        self.assertEqual((kk['status'], kk['art'], kk['entscheidung'], kk['von'], kk['ueber']), ('beantwortet', 'aufgabe', 'erlauben', 'captain', 'posteingang'))
        self.assertTrue(kk['aufgabe_id'])
        code, z = anfrage(self.url, 'POST', f"/api/harness/aufgaben/{kk['aufgabe_id']}/zuruecknehmen", {'grund': 'Test'})
        self.assertEqual(code, 200, z)
        code, _ = anfrage(self.url, 'DELETE', '/api/harness/vorarbeiter?projekt=pruef')
        self.assertEqual(code, 200)
        namen = self.ereignisse(ab)
        arten = [n for n, _ in namen]
        for erwartet in ('harness.vorarbeiter', 'decision.pending', 'decision.answered', 'harness.aufgabe'):
            self.assertIn(erwartet, arten, erwartet)
        self.assertEqual([d for n, d in namen if n == 'decision.answered'][0]['kind'], 'harness_aufgabe')
        self.assertEqual([d['zustand'] for n, d in namen if n == 'harness.aufgabe'], ['aktiv', 'zurueckgenommen'])
        self.assertEqual([d['sitzung_id'] for n, d in namen if n == 'harness.vorarbeiter'], [self.v, None])
        audit = self.audit()
        for erwartet in ('HARNESS_VORARBEITER_ERNANNT', 'HARNESS_AUFGABE_VORGESCHLAGEN', 'HARNESS_AUFGABE_ANGELEGT', 'HARNESS_FREIGABE',
                         'HARNESS_AUFGABE_ZURUECKGENOMMEN', 'HARNESS_VORARBEITER_ENTZOGEN'):
            self.assertIn(erwartet, audit, erwartet)

    def test_karte_fristet_mit_audit_und_ereignis_und_lauf_ereignis(self):
        self.api.vorarbeiter.ernennen('pruef', self.v)
        r = self.api._kiste(self.api._sitzung(self.b))[0].aufruf('lauf_starten', {'lauf': 'probe'}, antwort_id='A-00000000')
        self.assertEqual(r['status'], 'fehler', 'der Bauagent hat keine Lauf-Werkzeuge')
        k = self.api.karten.anlegen({'sitzung_id': self.b, 'werkzeug': 'datei_aendern', 'ziel': 'x', 'an': 'vorarbeiter', 'art': 'werkzeug', 'projekt': 'pruef'})
        alt = self.api.karten.laden(k['karte_id'])
        alt['angelegt'] = (datetime.now().astimezone() - timedelta(minutes=30)).isoformat(timespec='seconds')
        self.api.karten.speichern(alt)
        ab = self.hub.events.last_id
        self.assertEqual([x['karte_id'] for x in self.api.frist_pruefen()], [k['karte_id']])
        self.assertIn('HARNESS_KARTE_FRIST', self.audit())
        self.assertIn(('harness.karte', {'karte_id': k['karte_id'], 'an': 'captain', 'was': 'frist_abgelaufen'}), self.ereignisse(ab))
        ab = self.hub.events.last_id
        box = self.api._kiste(self.api._sitzung(self.v))[0]
        self.assertEqual(box.aufruf('lauf_starten', {'lauf': 'frei_probe'})['status'], 'ok')
        for _ in range(100):
            if 'ende' in [d['zustand'] for n, d in self.ereignisse(ab) if n == 'harness.lauf']: break
            time.sleep(0.1)
        zustaende = [d['zustand'] for n, d in self.ereignisse(ab) if n == 'harness.lauf']
        self.assertEqual((zustaende[0], zustaende[-1]), ('gestartet', 'ende'))
        self.assertTrue({'HARNESS_LAUF_START', 'HARNESS_LAUF_ENDE'} <= set(self.audit()))


if __name__ == '__main__':
    unittest.main()
