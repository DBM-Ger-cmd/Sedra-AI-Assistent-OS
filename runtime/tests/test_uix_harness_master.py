"""Master-Modus über die Wege der Harness (docs/SPEC_MASTER_MODUS_v1_ENTWURF.md MM-02, MM-03, MM-04, MM-10, MM-11, MM-12).

Ein echter UIXHub auf einem Prüfprojekt (wie test_uix_harness_freigabe); das Harness-Projekt zeigt per local_config/harness_projekte.yaml des Prüfprojekts auf
einen Wegwerf-Ordner. Ersetzt werden nur `harness.geladen` und `harness.execute` (das Modell)."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.desk import freigabeklasse
from sedra_runtime.harness import master
from sedra_runtime.uix_server import UIXHub, make_server
from test_uix_harness_api import ARCH, MODELL, anfrage, strom
from test_uix_harness_freigabe import Skript


class MasterWege(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-master-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        (cls.wurzel / 'docs').mkdir(parents=True)
        (cls.wurzel / 'runtime').mkdir()
        projekt = Path(cls.tmp.name) / 'project'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'harness_projekte.yaml').write_text(
            f"projekte:\n"
            f"  - id: mit-master\n    name: Mit Master\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [docs/**, runtime/**]\n    master: [docs/**]\n"
            f"  - id: ohne-master\n    name: Ohne Master\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [docs/**]\n", encoding='utf-8')
        cls.hub = UIXHub(projekt, ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def setUp(self):
        (self.wurzel / 'docs' / 'log.md').write_text('# Logbuch\n| a | b |\n', encoding='utf-8')
        self.hub.harness.geladen = lambda: (MODELL, None)
        self.addCleanup(self.hub.harness.master.aus, getattr(self, 'sid', 'x'))

    def sitzung(self, zuege=(), projekt='mit-master'):
        self.modell = Skript(zuege)
        self.hub.harness.execute = self.modell
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': projekt})
        self.assertEqual(code, 200, kopf)
        self.sid = kopf['id']
        self.addCleanup(self.hub.harness.master.aus, self.sid)
        return self.sid

    def senden(self, sid, text):
        code, out = anfrage(self.url, 'POST', f'/api/harness/sitzungen/{sid}/nachricht', {'text': text})
        self.assertEqual(code, 200, out)
        ev = strom(self.url, out['antwort_id'])
        for _ in range(100):
            if not self.hub.harness.threads:
                break
            time.sleep(0.05)
        return ev

    def master(self, sid, an):
        return anfrage(self.url, 'POST', f'/api/harness/sitzungen/{sid}/master', {'an': an})

    def audit(self, event):
        rows = [json.loads(l) for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
        return [r['payload'] for r in rows if r['event_type'] == event]

    def aendern(self, neu):
        return ('calls', [('datei_aendern', {'pfad': 'docs/log.md', 'alt': '| a | b |', 'neu': neu})])

    def test_stand_vor_dem_einschalten(self):
        sid = self.sitzung()
        code, s = anfrage(self.url, 'GET', f'/api/harness/sitzungen/{sid}/master')
        self.assertEqual((code, s['aktiv'], s['moeglich'], s['muster']), (200, False, True, ['docs/**']))
        self.assertIn('Netz', s['sperrliste'])

    def test_projekt_ohne_feld_nicht_moeglich(self):
        sid = self.sitzung(projekt='ohne-master')
        code, s = anfrage(self.url, 'GET', f'/api/harness/sitzungen/{sid}/master')
        self.assertEqual((s['moeglich'], s['aktiv']), (False, False))
        code, body = self.master(sid, True)
        self.assertEqual(code, 400)
        self.assertIn('master_nicht_moeglich', json.dumps(body))

    def test_ein_ohne_an_ist_fehler(self):
        sid = self.sitzung()
        code, _ = anfrage(self.url, 'POST', f'/api/harness/sitzungen/{sid}/master', {})
        self.assertEqual(code, 400)

    def test_ein_aendern_ohne_karte_audit_und_aus(self):
        sid = self.sitzung([self.aendern('| a | b |\n| c | d |'), ('text', 'Eingetragen.')])
        code, s = self.master(sid, True)
        self.assertEqual((code, s['aktiv'], s['projekt']), (200, True, 'mit-master'))
        ev = self.senden(sid, 'Trag c d ein')
        enden = [e[2] for e in ev if e[1] == 'werkzeug.ende']
        self.assertEqual([(e['status'], e['stufe']) for e in enden], [('ok', 'master')])
        self.assertFalse(any(e[1] == 'karte' for e in ev))
        self.assertEqual((self.wurzel / 'docs' / 'log.md').read_text(encoding='utf-8'), '# Logbuch\n| a | b |\n| c | d |\n')
        self.assertTrue(any(p['approved_by'] == f'master:{sid}' and p['kanal'] == 'master' for p in self.audit('HARNESS_APPROVED_BY')))
        self.assertTrue(any(p['sitzung_id'] == sid and p['master'] is True for p in self.audit('HARNESS_MASTER_AUFRUF')))
        self.assertTrue(any(p['sitzung_id'] == sid for p in self.audit('HARNESS_MASTER_AN')))
        _c, s = anfrage(self.url, 'GET', f'/api/harness/sitzungen/{sid}/master')
        self.assertEqual((s['aktiv'], s['aufrufe']), (True, 1))
        code, s = self.master(sid, False)
        self.assertEqual((code, s['aktiv'], s['war_an']), (200, False, True))
        self.assertTrue(any(p['sitzung_id'] == sid and p['grund'] == 'captain' for p in self.audit('HARNESS_MASTER_AUS')))

    def test_nach_aus_wieder_karte(self):
        sid = self.sitzung([self.aendern('| a | b |\n| c | d |')])
        self.master(sid, True)
        self.master(sid, False)
        ev = self.senden(sid, 'Trag c d ein')
        self.assertEqual(ev[-1][2]['ende'], 'wartet')
        self.assertEqual((self.wurzel / 'docs' / 'log.md').read_text(encoding='utf-8'), '# Logbuch\n| a | b |\n')

    def test_andere_sitzung_hat_keinen_master(self):
        a = self.sitzung()
        b = self.sitzung([self.aendern('| a | b |\n| x | y |')])
        self.master(a, True)
        ev = self.senden(b, 'Trag ein')
        self.assertEqual(ev[-1][2]['ende'], 'wartet')

    def test_ausserhalb_muster_karte(self):
        sid = self.sitzung([('calls', [('datei_schreiben', {'pfad': 'runtime/x.txt', 'inhalt': 'x'})])])
        self.master(sid, True)
        ev = self.senden(sid, 'Schreib runtime/x.txt')
        self.assertEqual(ev[-1][2]['ende'], 'wartet')
        self.assertFalse((self.wurzel / 'runtime' / 'x.txt').exists())

    def test_sitzung_loeschen_beendet_master(self):
        sid = self.sitzung()
        self.master(sid, True)
        code, _ = anfrage(self.url, 'DELETE', f'/api/harness/sitzungen/{sid}')
        self.assertEqual(code, 200)
        self.assertFalse(self.hub.harness.master.aktiv(sid))
        self.assertTrue(any(p['sitzung_id'] == sid and p['grund'] == 'sitzung_weg' for p in self.audit('HARNESS_MASTER_AUS')))

    def test_neustart_kein_master(self):
        sid = self.sitzung()
        self.master(sid, True)
        self.assertFalse(master.Zustand().aktiv(sid), 'Zustand nur im Speicher: ein neuer Server kennt keinen Master')

    def test_tuer_einschalten_wartet_auf_ja_ausserhalb(self):
        sid = self.sitzung()
        with mock.patch.object(type(self.hub), '_freigabe_ausserhalb', lambda s: True), mock.patch('sedra_runtime.uix_server.systemdialog.zeigen', return_value=None):
            code, body = self.master(sid, True)
            self.assertNotEqual(code, 200, body)
            self.assertIn('wartet_auf_bestaetigung', json.dumps(body))
            self.assertFalse(self.hub.harness.master.aktiv(sid), 'ohne das Ja außerhalb des Browsers bleibt er aus')
            bid = self.audit('FREIGABE_WARTET')[-1]['bestaetigung']
            self.hub.freigabe_bestaetigen(bid, True, 'konsole')
            self.assertTrue(self.hub.harness.master.aktiv(sid))
            code, s = self.master(sid, False)                    # Aus braucht keine Tür
            self.assertEqual((code, s['aktiv']), (200, False))

    def test_klasse_und_wege_sind_eingeordnet(self):
        self.assertEqual(freigabeklasse.klasse('harness:master_schalten', 'einmal', {}), freigabeklasse.H)
        self.assertEqual(freigabeklasse.ROUTEN_HARNESS['POST sitzungen/master'][:2], ('freigabe', freigabeklasse.H))
        from sedra_runtime.harness import api
        self.assertTrue(api.GESCHUETZT.fullmatch('/api/harness/sitzungen/S-0000000A/master'), 'Herkunftsprüfung (S7) gilt für den Weg')

    def test_modell_hat_kein_werkzeug_dafuer(self):
        from sedra_runtime.harness.werkzeuge import NAMEN
        self.assertFalse([n for n in NAMEN if 'master' in n.lower()])


if __name__ == '__main__':
    unittest.main()
