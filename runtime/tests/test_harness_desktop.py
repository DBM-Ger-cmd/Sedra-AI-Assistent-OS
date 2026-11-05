"""Desktop Builder und Profile (05.11.2026): die Wahl des Captains fuer Start-Menue und Taskleiste, Marke, Profile je Auftraggeber (speichern, anwenden, exportieren, importieren, loeschen),
Grundfunktionen bleiben erreichbar, kaputte Eingaben werden abgewiesen, Weg und Herkunftspruefung."""
import json
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.core.guard import Guard
from guppi_runtime.harness import desktop as dt
from guppi_runtime.harness import katalog, vorlagen
from guppi_runtime.harness.freigabe import Karten, Kiste
from guppi_runtime.harness.werkzeuge import Werkzeuge
from guppi_runtime.harness.api import GESCHUETZT, WEG
from guppi_runtime.uix_server import UIXHub

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
WAHL = {'start': {'ausblenden': ['wissen'], 'zuordnung': {'models': 'system'}}, 'zellen': {'ausblenden': ['scheduler'], 'reihenfolge': ['state', 'model']},
        'marke': {'name': 'Muster GmbH', 'akzent': '#2266aa'}}


def projekt():
    return tempfile.mkdtemp(prefix='desktop-')


class Wahl(unittest.TestCase):
    def test_ohne_datei_gilt_die_vorgabe_der_shell(self):
        w = dt.laden(projekt())
        self.assertEqual((w['start'], w['zellen'], w['marke'], w['profil'], w['profile']),
                         ({'ausblenden': [], 'zuordnung': {}}, {'ausblenden': [], 'reihenfolge': []}, {'name': '', 'akzent': ''}, None, []))

    def test_speichern_ersetzt_teile_und_null_setzt_zurueck(self):
        p = projekt()
        dt.speichern(p, WAHL)
        w = dt.speichern(p, {'zellen': None})
        self.assertEqual(w['start'], WAHL['start'], 'der andere Teil bleibt')
        self.assertEqual(w['zellen'], {'ausblenden': [], 'reihenfolge': []})
        self.assertEqual(dt.laden(p)['marke']['name'], 'Muster GmbH')

    def test_kaputte_datei_ist_kein_fehler_beim_start(self):
        p = projekt()
        (Path(p) / 'runtime_data' / 'harness').mkdir(parents=True)
        (Path(p) / 'runtime_data' / 'harness' / 'desktop.json').write_text('{kaputt', encoding='utf-8')
        self.assertEqual(dt.laden(p)['start']['ausblenden'], [])

    def test_grundfunktionen_lassen_sich_nicht_ausblenden(self):
        for schlecht in ({'start': {'ausblenden': ['decisions']}}, {'start': {'ausblenden': ['wissen', 'tasks']}}, {'zellen': {'ausblenden': ['decisions']}}):
            with self.assertRaises(ValueError) as ctx:
                dt.speichern(projekt(), schlecht)
            self.assertTrue(str(ctx.exception).startswith('desktop_grundfunktion'))

    def test_eingaben_werden_geprueft(self):
        for schlecht in ({'start': {'zuordnung': {'x': 'gibtsnicht'}}}, {'start': {'ausblenden': ['../x']}}, {'start': {'ausblenden': 'nein'}}, {'zellen': {'reihenfolge': [1]}},
                         {'marke': {'name': 'x' * 41}}, {'marke': {'akzent': 'rot'}}, {'marke': {'logo': 'x'}}, {'fremd': {}}, {'start': {'ausblenden': ['a'] * 5 + ['b%d' % i for i in range(90)]}}):
            with self.assertRaises(ValueError, msg=str(schlecht)):
                dt.speichern(projekt(), schlecht)
        with self.assertRaises(ValueError):
            dt.speichern(projekt(), {})


class Profile(unittest.TestCase):
    def test_speichern_anwenden_exportieren_loeschen(self):
        p = projekt()
        dt.speichern(p, WAHL)
        w = dt.aktion(p, {'aktion': 'profil_speichern', 'id': 'muster-gmbh', 'name': 'Muster GmbH', 'auftraggeber': 'Muster', 'beschreibung': 'Sachbearbeitung'})
        self.assertEqual((w['profil'], [x['id'] for x in w['profile']]), ('muster-gmbh', ['muster-gmbh']))
        dt.speichern(p, {'start': None, 'marke': None})
        self.assertIsNone(dt.laden(p)['profil'], 'eine Aenderung loest die Bindung')
        w = dt.aktion(p, {'aktion': 'profil_anwenden', 'id': 'muster-gmbh'})
        self.assertEqual((w['profil'], w['start'], w['marke']['name']), ('muster-gmbh', WAHL['start'], 'Muster GmbH'))
        export = dt.profil_lesen(p, 'muster-gmbh')
        self.assertEqual((export['auftraggeber'], export['beschreibung'], export['zellen']), ('Muster', 'Sachbearbeitung', {'ausblenden': ['scheduler'], 'reihenfolge': ['state', 'model']}))
        w = dt.aktion(p, {'aktion': 'profil_loeschen', 'id': 'muster-gmbh'})
        self.assertEqual((w['profile'], w['profil'], w['marke']['name']), ([], None, 'Muster GmbH'), 'die Wahl bleibt, die Bindung faellt')

    def test_export_importieren_in_ein_anderes_projekt(self):
        a, b = projekt(), projekt()
        dt.speichern(a, WAHL)
        dt.aktion(a, {'aktion': 'profil_speichern', 'id': 'kunde-a', 'name': 'Kunde A'})
        export = json.loads(json.dumps(dt.profil_lesen(a, 'kunde-a')))
        w = dt.aktion(b, {'aktion': 'profil_importieren', 'profil': export})
        self.assertEqual([x['id'] for x in w['profile']], ['kunde-a'])
        self.assertEqual(dt.profil_lesen(b, 'kunde-a')['start'], WAHL['start'])
        with self.assertRaises(ValueError):                                                 # ein Profil mit Grundfunktion im Ausblenden wird nie importiert
            dt.aktion(b, {'aktion': 'profil_importieren', 'profil': dict(export, id='boese', start={'ausblenden': ['decisions']})})

    def test_ungueltige_profilangaben(self):
        p = projekt()
        for body in ({'aktion': 'profil_speichern', 'id': 'A B', 'name': 'x'}, {'aktion': 'profil_speichern', 'id': '../x', 'name': 'x'}, {'aktion': 'profil_speichern', 'id': 'ok-id', 'name': ''},
                     {'aktion': 'profil_anwenden', 'id': 'gibtsnicht'}, {'aktion': 'profil_loeschen', 'id': 'gibtsnicht'}, {'aktion': 'profil_importieren', 'profil': 'text'}, {'aktion': 'anderes'}):
            with self.assertRaises(ValueError, msg=str(body)):
                dt.aktion(p, body)

    def test_profile_haben_eine_obergrenze(self):
        p = projekt()
        for i in range(dt.MAX_PROFILE):
            dt.profil_speichern(p, 'kunde-%02d' % i, 'K')
        with self.assertRaises(ValueError):
            dt.profil_speichern(p, 'kunde-zu-viel', 'K')
        dt.profil_speichern(p, 'kunde-00', 'K neu')                                         # ein vorhandenes ersetzen geht immer


class ChatWerkzeug(unittest.TestCase):
    """`desktop_lesen` im Chat (05.11.2026): nur lesen, ohne Karte; der Oberflaechen-Designer kennt es, aendert aber nie selbst."""

    def kiste(self, stand):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name) / 'p'
        root.mkdir()
        guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(t.name) / 'tokens.json')
        regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        w = Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': []}, guard=guard, mission_id='M-D', regeln=regeln, desktop_stand=stand)
        return Kiste(w, regeln=regeln, guard=guard, audit=None, karten=Karten(Path(t.name) / 'k'), sitzung_id='S-00000001')

    def test_lesen_ohne_karte_mit_profil_und_fehlern(self):
        gesehen = []

        def stand(profil):
            gesehen.append(profil)
            if profil == 'weg':
                raise ValueError('profil_unbekannt')
            return {'zuschnitt': {'start': {}}, 'grundfunktionen': {'start': ['decisions', 'tasks']}}
        k = self.kiste(stand)
        r = k.aufruf('desktop_lesen', {})
        self.assertEqual((r['status'], r['wirkung']), ('ok', False))
        self.assertIn('grundfunktionen', r['ergebnis'])
        k.aufruf('desktop_lesen', {'profil': 'kunde-a'})
        self.assertEqual(k.aufruf('desktop_lesen', {'profil': 'weg'})['status'], 'fehler')
        self.assertEqual(gesehen, [None, 'kunde-a', 'weg'])
        self.assertIn('nicht_verfuegbar', self.kiste(None).aufruf('desktop_lesen', {})['ergebnis'])

    def test_der_server_nennt_zuschnitt_grundfunktionen_und_erlaubte_werte(self):
        tmp = tempfile.TemporaryDirectory(prefix='desktop-chat-')
        self.addCleanup(tmp.cleanup)
        projekt_ = Path(tmp.name) / 'project'
        (projekt_ / 'local_config').mkdir(parents=True)
        hub = UIXHub(projekt_, ARCH)
        self.addCleanup(hub.close)
        dt.speichern(str(projekt_), WAHL)
        dt.aktion(str(projekt_), {'aktion': 'profil_speichern', 'id': 'kunde-a', 'name': 'Kunde A'})
        s = hub.harness.desktop_stand()
        self.assertEqual((s['grundfunktionen']['start'], s['gruppen'][:2]), (['decisions', 'tasks'], ['arbeit', 'modelle']))
        self.assertIn('state', s['zellen'])
        self.assertEqual(hub.harness.desktop_stand('kunde-a')['zuschnitt']['name'], 'Kunde A')

    def test_die_vorlage_oberflaechen_designer_liest_nur_und_aendert_code_mit_karte(self):
        wurzel = Path(tempfile.mkdtemp())
        v = vorlagen.laden(wurzel, 'desktop-designer')
        self.assertEqual(v['rechte'], {'vorarbeiter_freigabe': False, 'aufgaben_vorschlagen': False})
        self.assertIn('desktop_lesen', v['werkzeuge'])
        self.assertNotIn('datei_schreiben', v['werkzeuge'], 'bestehende Dateien aendern, nicht ueberschreiben')
        for satz in ('kontextmodule.js', 'Ausblenden ist keine Sperre', 'Profil als Text', 'Erfinde nichts'):
            self.assertIn(satz, v['system'])
        self.assertNotIn('GUPPI', v['system'])

    def test_das_beispiel_im_skill_laesst_sich_importieren(self):
        text = (Path(__file__).resolve().parents[1] / 'config' / 'harness_vorlagen' / 'desktop-designer.md').read_text(encoding='utf-8')
        beispiel = json.loads(text.split('```json')[1].split('```')[0])
        w = dt.aktion(projekt(), {'aktion': 'profil_importieren', 'profil': beispiel})
        self.assertEqual([p['id'] for p in w['profile']], [beispiel['id']], 'ein Skill, dessen Beispiel der Importeur abweist, fuehrt in die Irre')
        erlaubt = text.split('Gruppen `')[1].split('`;')[0]
        self.assertEqual(erlaubt.split(', '), list(dt.GRUPPEN))


class Weg(unittest.TestCase):
    def test_weg_ist_bekannt_und_geschuetzt(self):
        self.assertIn('desktop', WEG.fullmatch('/api/harness/desktop').groups())
        self.assertTrue(GESCHUETZT.match('/api/harness/desktop'))

    def test_route_am_echten_hub(self):
        tmp = tempfile.TemporaryDirectory(prefix='desktop-hub-')
        self.addCleanup(tmp.cleanup)
        projekt_ = Path(tmp.name) / 'project'
        (projekt_ / 'local_config').mkdir(parents=True)
        hub = UIXHub(projekt_, ARCH)
        self.addCleanup(hub.close)
        api = hub.harness
        self.assertEqual(api.handle('GET', '/api/harness/desktop', '')[1]['profile'], [])
        st, w = api.handle('POST', '/api/harness/desktop', '', WAHL)
        self.assertEqual((st, w['marke']['name']), (200, 'Muster GmbH'))
        st, w = api.handle('POST', '/api/harness/desktop', '', {'aktion': 'profil_speichern', 'id': 'muster', 'name': 'Muster'})
        self.assertEqual(w['profil'], 'muster')
        self.assertEqual(api.handle('GET', '/api/harness/desktop', 'profil=muster')[1]['name'], 'Muster')
        with self.assertRaises(ValueError):
            api.handle('POST', '/api/harness/desktop', '', {'start': {'ausblenden': ['decisions']}})
        lines = hub.runtime.audit.path.read_text(encoding='utf-8')
        self.assertEqual(lines.count('"HARNESS_DESKTOP"'), 2)


if __name__ == '__main__':
    unittest.main()
