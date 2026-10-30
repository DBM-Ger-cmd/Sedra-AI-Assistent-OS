"""Stufe 6 N5 (mit Server, ohne Modell): GET /api/harness/vorschau – nur Pfade aus dem Verlauf der Sitzung, gesperrte Dateien, ungültige Pfade, unbekannte Sitzung."""
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import quote

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.uix_server import UIXHub, make_server
from test_uix_harness_api import ARCH, MODELL, anfrage, strom
from test_uix_harness_freigabe import Skript


class VorschauWegTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-vorschau-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        (cls.wurzel / 'docs').mkdir(parents=True)
        (cls.wurzel / 'docs' / 'log.md').write_text('# Logbuch\nEintrag\n', encoding='utf-8')
        (cls.wurzel / '.env').write_text('GEHEIM=1\n', encoding='utf-8')
        projekt = Path(cls.tmp.name) / 'project'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'harness_projekte.yaml').write_text(
            f"projekte:\n  - id: pruef\n    name: Prüfprojekt\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [docs/**]\n", encoding='utf-8')
        cls.hub = UIXHub(projekt, ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.hub.close()
        cls.tmp.cleanup()

    def sitzung_mit_lesen(self, pfad):
        self.hub.harness.geladen = lambda: (MODELL, None)
        self.hub.harness.execute = Skript([('calls', [('datei_lesen', {'pfad': pfad})]), ('text', 'Gelesen.')])
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef'})
        self.assertEqual(code, 200, kopf)
        code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'lies'})
        self.assertEqual(code, 200, out)
        strom(self.url, out['antwort_id'])
        return kopf['id']

    def holen(self, sid, pfad):
        return anfrage(self.url, 'GET', f'/api/harness/vorschau?sitzung={sid}&pfad={quote(pfad)}')

    def test_datei_aus_dem_verlauf(self):
        sid = self.sitzung_mit_lesen('docs/log.md')
        code, out = self.holen(sid, 'docs/log.md')
        self.assertEqual((code, out['status'], out['zeilen']), (200, 'ok', 2), out)
        self.assertIn('Eintrag', out['text'])

    def test_pfad_ausserhalb_des_verlaufs_und_ungueltige_pfade(self):
        sid = self.sitzung_mit_lesen('docs/log.md')
        code, out = self.holen(sid, '.env')
        self.assertEqual(code, 400, out)
        self.assertIn('pfad_nicht_im_verlauf', out['message'])
        for p in ('../x', '/etc/passwd', ''):
            self.assertEqual(self.holen(sid, p)[0], 400, p)

    def test_gesperrte_datei_im_verlauf_zeigt_keinen_inhalt(self):
        sid = self.sitzung_mit_lesen('.env')
        code, out = self.holen(sid, '.env')
        self.assertEqual(code, 200, out)
        self.assertEqual(out['status'], 'gesperrt')
        self.assertNotIn('GEHEIM', str(out))

    def test_unbekannte_sitzung(self):
        self.assertEqual(self.holen('S-00000000', 'docs/log.md')[0], 404)


if __name__ == '__main__':
    unittest.main()
