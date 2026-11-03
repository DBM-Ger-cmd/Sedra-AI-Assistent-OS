"""E9 Variante C (SPEC_APPS_v1_O3PLUS_G9_G2 §9a): der eigene Hardware-Server liefert das Skript seiner Seite und erlaubt kein Inline-Skript.

Vorher (seit der Härtungsrunde 30.10.): Die Seite lud /uix/js/hardware_dashboard.js, der Server antwortete 403, und seine CSP
(`script-src 'unsafe-inline'` ohne 'self') hätte es ohnehin gesperrt – das Fenster zeigte keine Daten."""
import re
import threading
import unittest
import urllib.error
import urllib.request

from guppi_runtime.hardware_manager.dashboard import SKRIPT_PFAD, make_server


class Manager:
    def get_state(self, fresh=False): return {}
    def history(self, n): return []
    def inventory(self): return {'cpu': 'x'}
    def profiles(self): return {}
    def capabilities(self): return {}


class HardwareServer(unittest.TestCase):
    def setUp(self):
        self.srv, url = make_server(Manager())
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.basis, self.token = url.split('#')

    def holen(self, pfad, token=None):
        req = urllib.request.Request(self.basis.rstrip('/') + pfad, headers={'X-GUPPI-Token': token} if token else {})
        return urllib.request.urlopen(req, timeout=10)

    def test_seite_laedt_genau_das_ausgelieferte_skript(self):
        seite = self.holen('/').read().decode('utf-8')
        self.assertEqual(re.findall(r'<script src="([^"]+)"', seite), [SKRIPT_PFAD])
        self.assertNotRegex(seite, r'<script(?![^>]*\bsrc=)')            # kein Inline-Skript

    def test_skript_wird_ausgeliefert(self):
        r = self.holen(SKRIPT_PFAD)
        self.assertEqual(r.status, 200)
        self.assertTrue(r.headers['Content-Type'].startswith('text/javascript'))
        self.assertIn(b'/api/state', r.read())

    def test_csp_ohne_inline_skript(self):
        csp = self.holen('/').headers['Content-Security-Policy']
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn("'unsafe-inline'", csp.split('script-src', 1)[1].split(';')[0])

    def test_andere_dateien_bleiben_zu(self):
        for pfad in ('/uix/js/api.js', '/uix/js/hardware_dashboard.js/../api.js', '/api/state'):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self.holen(pfad)
            self.assertIn(ctx.exception.code, (403, 404), pfad)

    def test_daten_mit_token(self):
        self.assertEqual(self.holen('/api/inventory', self.token).status, 200)


if __name__ == '__main__':
    unittest.main()
