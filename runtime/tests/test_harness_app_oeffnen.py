"""app_oeffnen (02.11.2026): Gemma kann im Chat ein Fenster der Oberfläche (Rekorder, Logbuch …) öffnen. Ohne Modell, mit dem echten Guard.

Das Werkzeug ändert nichts am Rechner: keine Karte, keine Wirkung; die Antwort trägt `ui.oeffnen`, die Shell öffnet das Fenster."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.core.guard import Guard
from guppi_runtime.harness import katalog
from guppi_runtime.harness.freigabe import Karten, Kiste
from guppi_runtime.harness.werkzeuge import NAMEN, SCHEMAS, Werkzeuge, WerkzeugFehler

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
MISSION = 'M-OEFFNEN'


class AppOeffnen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'projekt'
        (root / 'docs').mkdir(parents=True)
        guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(self.tmp.name) / 'tokens.json')
        regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        projekt = {'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': ['docs/**']}
        self.antraege = []
        self.w = Werkzeuge(projekt, guard=guard, mission_id=MISSION, regeln=regeln, projekt_antrag=self.antrag)
        self.ereignisse = []
        audit = type('A', (), {'append': lambda s, event, **kw: self.ereignisse.append((event, kw.get('payload')))})()
        self.kiste = Kiste(self.w, regeln=regeln, guard=guard, audit=audit, karten=Karten(Path(self.tmp.name) / 'karten'), sitzung_id='S-00000001')

    def antrag(self, nutz):
        self.antraege.append(nutz)
        if nutz['wurzel'].startswith('X'):
            raise ValueError('ordner_fehlt')
        return {'projekt': {'wurzel': nutz['wurzel'], 'name': nutz.get('name') or 'Baut', 'schreibbereich': nutz.get('schreibbereich') or ['docs/**']}}

    def test_das_werkzeug_ist_da_und_nennt_den_rekorder(self):
        self.assertIn('app_oeffnen', NAMEN)
        self.assertIn('aufnahme (Rekorder)', SCHEMAS['app_oeffnen']['function']['description'])

    def test_der_rekorder_oeffnet_ohne_karte_und_ohne_wirkung(self):
        r = self.kiste.aufruf('app_oeffnen', {'ort': 'aufnahme'})
        self.assertEqual((r['status'], r['stufe'], r['regel'], r['wirkung']), ('ok', 'frei', 'app-oeffnen', False))
        self.assertEqual(r['ui'], {'oeffnen': 'aufnahme', 'titel': 'Rekorder'})
        self.assertNotIn('karte', r)
        self.assertIn('tut der Captain', r['ergebnis'])                       # nichts startet von selbst
        self.assertEqual([e for e, _ in self.ereignisse], ['HARNESS_APP_OEFFNEN'])

    def test_ein_unbekannter_ort_sagt_die_erlaubten(self):
        r = self.kiste.aufruf('app_oeffnen', {'ort': 'voicerekorder'})
        self.assertEqual(r['status'], 'fehler')
        self.assertIn('ort_unbekannt', r['ergebnis'])
        self.assertIn('aufnahme', r['ergebnis'])
        with self.assertRaises(WerkzeugFehler):
            self.w.vorbereiten('app_oeffnen', {})

    def test_projekt_beantragen_stellt_nur_den_antrag(self):
        r = self.kiste.aufruf('projekt_beantragen', {'wurzel': 'E:/Sedra Umgebung/A1 Sedra Baut', 'name': 'Baut'})
        self.assertEqual((r['status'], r['stufe'], r['regel'], r['wirkung']), ('ok', 'frei', 'projekt-beantragen', False))
        self.assertNotIn('karte', r)
        self.assertEqual(self.antraege, [{'wurzel': 'E:/Sedra Umgebung/A1 Sedra Baut', 'name': 'Baut'}])
        self.assertIn('erst nach seiner Freigabe', r['ergebnis'])                      # das Modell darf nicht so tun, als gäbe es das Projekt schon
        self.assertEqual([e for e, _ in self.ereignisse], ['HARNESS_PROJEKT_BEANTRAGT'])

    def test_projekt_beantragen_gibt_den_grund_des_antrags_weiter(self):
        r = self.kiste.aufruf('projekt_beantragen', {'wurzel': 'X:/gibt-es-nicht'})
        self.assertEqual(r['status'], 'fehler')
        self.assertIn('ordner_fehlt', r['ergebnis'])
        self.assertEqual(self.kiste.aufruf('projekt_beantragen', {})['status'], 'fehler')

    def test_befehl_und_datei_schreiben_nennen_ihre_grenze(self):
        self.assertIn('mkdir', SCHEMAS['befehl']['function']['description'])
        self.assertIn('Ordner', SCHEMAS['datei_schreiben']['function']['description'])


if __name__ == '__main__':
    unittest.main()
