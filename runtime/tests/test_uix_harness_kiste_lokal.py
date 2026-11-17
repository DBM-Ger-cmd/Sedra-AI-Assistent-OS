"""O-3 (Hardening 16.11.2026, docs/HARDENING_2026-11-16_MASTER.md): `Kiste.lokal` wird aus dem Anbieter der Sitzung abgeleitet.

Vorher blieb es beim Standard `lokal=True`: käme ein Cloud-Anbieter in die Harness, hätten Aufgaben-Freigabe (HS-27), Sitzungs-Erlaubnis (FS-13) und Master-Modus (MM-12) auch Cloud-Läufe gedeckt.
Jetzt gilt nur, was in `LOKALE_PROVIDER` steht; ein anderer Anbieter ist nicht lokal (fail-closed). Ein echter UIXHub auf einem Wegwerf-Projekt, wie in test_uix_harness_master."""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.harness import api as harness_api
from sedra_runtime.uix_server import UIXHub, make_server
from test_uix_harness_api import ARCH, MODELL, anfrage


class KisteLokal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-lokal-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        (cls.wurzel / 'docs').mkdir(parents=True)
        projekt = Path(cls.tmp.name) / 'project'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'harness_projekte.yaml').write_text(
            f"projekte:\n  - id: mit-master\n    name: Mit Master\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [docs/**]\n    master: [docs/**]\n", encoding='utf-8')
        cls.hub = UIXHub(projekt, ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.hub.close()
        cls.tmp.cleanup()

    def setUp(self):
        (self.wurzel / 'docs' / 'log.md').write_text('| a | b |\n', encoding='utf-8')
        self.hub.harness.geladen = lambda: (MODELL, None)
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'mit-master'})
        self.assertEqual(code, 200, kopf)
        self.sid = kopf['id']
        self.addCleanup(self.hub.harness.master.aus, self.sid)

    def kiste(self):
        return self.hub.harness._kiste(self.hub.harness._sitzung(self.sid))[0]

    def aendern(self, neu):
        return self.kiste().aufruf('datei_aendern', {'pfad': 'docs/log.md', 'alt': '| a | b |', 'neu': neu}, antwort_id='A-00000000')

    def test_der_lokale_anbieter_ist_lokal(self):
        self.assertIn(harness_api.PROVIDER, harness_api.LOKALE_PROVIDER, 'die Harness läuft heute nur mit dem lokalen llama-server (HS-50)')
        self.assertTrue(self.kiste().lokal)

    def test_ein_anderer_anbieter_ist_nicht_lokal(self):
        for name in ('cloud-nvidia', 'langdock', 'irgendwas', ''):
            with self.subTest(anbieter=name), mock.patch.object(harness_api, 'PROVIDER', name):
                self.assertFalse(self.kiste().lokal, f'{name!r} steht nicht in LOKALE_PROVIDER')

    def test_der_master_deckt_nur_mit_lokalem_anbieter(self):
        code, out = anfrage(self.url, 'POST', f'/api/harness/sitzungen/{self.sid}/master', {'an': True})
        self.assertEqual(code, 200, out)
        with mock.patch.object(harness_api, 'PROVIDER', 'cloud-nvidia'):
            r = self.aendern('| a | cloud |')
            self.assertEqual(r['status'], 'wartet', 'mit einem Cloud-Anbieter deckt der Master nicht: Karte')
            self.assertEqual((self.wurzel / 'docs' / 'log.md').read_text(encoding='utf-8'), '| a | b |\n', 'nichts geschrieben')
        r = self.aendern('| a | lokal |')
        self.assertEqual(r['status'], 'ok', r)
        self.assertEqual(r.get('stufe'), 'master', 'mit dem lokalen Anbieter deckt der Master wie bisher')
        self.assertIn('lokal', (self.wurzel / 'docs' / 'log.md').read_text(encoding='utf-8'))

    def test_ohne_master_aendert_sich_nichts(self):
        r = self.aendern('| a | karte |')
        self.assertEqual(r['status'], 'wartet', 'ohne Master und ohne Erlaubnis: Karte, wie vorher')


if __name__ == '__main__':
    unittest.main()
