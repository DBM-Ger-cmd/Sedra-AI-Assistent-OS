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
        self.root = root
        self.w = Werkzeuge(projekt, guard=guard, mission_id=MISSION, regeln=regeln, projekt_antrag=self.antrag, verknuepfung=self.verknuepfung)
        self.ereignisse = []
        audit = type('A', (), {'append': lambda s, event, **kw: self.ereignisse.append((event, kw.get('payload')))})()
        self.kiste = Kiste(self.w, regeln=regeln, guard=guard, audit=audit, karten=Karten(Path(self.tmp.name) / 'karten'), sitzung_id='S-00000001')

    def antrag(self, nutz):
        self.antraege.append(nutz)
        if nutz['wurzel'].startswith('X'):
            raise ValueError('ordner_fehlt')
        return {'projekt': {'wurzel': nutz['wurzel'], 'name': nutz.get('name') or 'Baut', 'schreibbereich': nutz.get('schreibbereich') or ['docs/**']}}

    def verknuepfung(self, ort, name):
        from guppi_runtime.harness import verknuepfungen
        from guppi_runtime.harness.werkzeuge import ORTE
        try:
            return verknuepfungen.hinzufuegen(self.root, ort, name, ORTE)
        except verknuepfungen.VerknuepfungFehler as exc:
            raise ValueError(str(exc)) from exc

    def test_das_werkzeug_ist_da_und_nennt_den_rekorder(self):
        self.assertIn('app_oeffnen', NAMEN)
        self.assertIn('aufnahme=Rekorder', SCHEMAS['app_oeffnen']['function']['description'])

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

    def test_verknuepfung_anlegen_legt_den_knopf_an_und_sagt_der_shell_bescheid(self):
        from guppi_runtime.harness import verknuepfungen
        r = self.kiste.aufruf('app_oeffnen', {'ort': 'aufnahme', 'verknuepfung': True, 'name': 'Rekorder schnell'})
        self.assertEqual((r['status'], r['stufe'], r['regel'], r['wirkung']), ('ok', 'frei', 'app-oeffnen', False))
        self.assertEqual(r['ui'], {'oeffnen': 'aufnahme', 'titel': 'Rekorder', 'verknuepfungen': True})                 # Fenster öffnen UND Knopf anlegen
        self.assertNotIn('karte', r)
        liste = verknuepfungen.laden(self.root)
        self.assertEqual([(v['ort'], v['name']) for v in liste], [('aufnahme', 'Rekorder schnell')])
        self.assertIn('mit dem Kreuz', r['ergebnis'])

    def test_verknuepfung_grenzen(self):
        from guppi_runtime.harness import verknuepfungen
        self.assertEqual(self.kiste.aufruf('app_oeffnen', {'ort': 'gibtsnicht', 'verknuepfung': True})['status'], 'fehler')
        self.assertEqual(self.kiste.aufruf('app_oeffnen', {'ort': 'logbook', 'verknuepfung': True})['status'], 'ok')
        zweite = self.kiste.aufruf('app_oeffnen', {'ort': 'logbook', 'verknuepfung': True})                 # ein Ort nur einmal
        self.assertEqual(zweite['status'], 'fehler')
        self.assertIn('schon_vorhanden', zweite['ergebnis'])
        v = verknuepfungen.laden(self.root)[0]
        self.assertEqual(v['name'], 'Logbuch')                                                  # ohne Namen: der Name des Ortes
        langer = verknuepfungen.hinzufuegen(self.root, 'models', 'x' * 100 + ' y', {'models': ('Werkstatt', '')})
        self.assertEqual(len(langer['name']), verknuepfungen.NAME_MAX)
        verknuepfungen.entfernen(self.root, v['id'])
        self.assertEqual([e['ort'] for e in verknuepfungen.laden(self.root)], ['models'])
        with self.assertRaises(verknuepfungen.VerknuepfungFehler):
            verknuepfungen.entfernen(self.root, 'V-00000000')
        with self.assertRaises(verknuepfungen.VerknuepfungFehler):
            verknuepfungen.entfernen(self.root, '../x')

    def test_hoechstens_zwoelf_verknuepfungen(self):
        from guppi_runtime.harness import verknuepfungen
        orte = {f'o{i}': (f'Ort {i}', '') for i in range(verknuepfungen.MAX + 1)}
        for i in range(verknuepfungen.MAX):
            verknuepfungen.hinzufuegen(self.root, f'o{i}', None, orte)
        with self.assertRaises(verknuepfungen.VerknuepfungFehler) as ctx:
            verknuepfungen.hinzufuegen(self.root, f'o{verknuepfungen.MAX}', None, orte)
        self.assertIn('zu_viele', str(ctx.exception))

    def test_eine_verboten_regel_des_captains_schaltet_die_werkzeuge_ab(self):
        verbot = [{'id': 'kein-fenster', 'werkzeug': ['app_oeffnen', 'projekt_beantragen'], 'muster': ['**'], 'stufe': 'verboten', 'begruendung': 'Test'}]
        kiste = Kiste(self.w, regeln=verbot, guard=self.kiste.guard, audit=None, karten=self.kiste.karten, sitzung_id='S-00000002')
        for name, args in (('app_oeffnen', {'ort': 'aufnahme'}), ('app_oeffnen', {'ort': 'aufnahme', 'verknuepfung': True}), ('projekt_beantragen', {'wurzel': 'E:/x'})):
            r = kiste.aufruf(name, args)
            self.assertEqual((r['status'], r['wirkung']), ('verboten', False), name)
        self.assertEqual(self.antraege, [])                                              # nichts davon lief
        from guppi_runtime.harness import verknuepfungen
        self.assertEqual(verknuepfungen.laden(self.root), [])

    def test_die_verknuepfung_nennt_im_audit_wer_sie_angelegt_hat(self):
        from guppi_runtime.harness.api import HarnessApi
        fake = type('H', (), {'project_root': self.root, 'events': None})()
        api = HarnessApi.__new__(HarnessApi)
        api.hub = fake
        api.herkunft = None
        gesehen = []
        api._audit = lambda event, payload: gesehen.append((event, payload))
        api._melden = lambda *a, **k: None
        api.verknuepfung_anlegen('logbook', None, von='modell')
        self.assertEqual(gesehen[0][0], 'HARNESS_VERKNUEPFUNG_ANGELEGT')
        self.assertEqual(gesehen[0][1]['von'], 'modell')


if __name__ == '__main__':
    unittest.main()
