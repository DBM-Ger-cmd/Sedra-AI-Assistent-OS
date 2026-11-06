"""Desktop Builder und Profile (05.11.2026): die Wahl des Captains fuer Start-Menue und Taskleiste, Marke, Profile je Auftraggeber (speichern, anwenden, exportieren, importieren, loeschen),
Grundfunktionen bleiben erreichbar, kaputte Eingaben werden abgewiesen, Weg und Herkunftspruefung."""
import json
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.core.guard import Guard
from sedra_runtime.harness import desktop as dt
from sedra_runtime.harness import katalog, vorlagen
from sedra_runtime.harness.freigabe import Karten, Kiste
from sedra_runtime.harness.werkzeuge import Werkzeuge
from sedra_runtime.harness.api import GESCHUETZT, WEG
from sedra_runtime.uix_server import UIXHub

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'
WAHL = {'start': {'ausblenden': ['logbook'], 'zuordnung': {'models': 'system'}}, 'zellen': {'ausblenden': ['scheduler'], 'reihenfolge': ['state', 'model']},
        'marke': {'name': 'Muster GmbH', 'akzent': '#2266aa'}}


def projekt():
    return tempfile.mkdtemp(prefix='desktop-')


class Wahl(unittest.TestCase):
    def test_ohne_datei_gilt_die_vorgabe_der_shell(self):
        w = dt.laden(projekt())
        self.assertEqual((w['start'], w['zellen'], w['marke'], w['profil'], w['profile']),
                         ({'ausblenden': [], 'zuordnung': {}}, {'ausblenden': [], 'reihenfolge': []}, {'name': '', 'akzent': '', 'logo': '', 'schrift': ''}, None, []))
        self.assertEqual(w['startseite'], {'ort': '', 'titel': '', 'text': ''})

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
        for schlecht in ({'start': {'ausblenden': ['decisions']}}, {'start': {'ausblenden': ['logbook', 'tasks']}}, {'start': {'ausblenden': ['wissen']}}, {'zellen': {'ausblenden': ['decisions']}}):
            with self.assertRaises(ValueError) as ctx:
                dt.speichern(projekt(), schlecht)
            self.assertTrue(str(ctx.exception).startswith('desktop_grundfunktion'))

    def test_alter_zuschnitt_mit_wissen_ausgeblendet_bleibt_erhalten(self):
        """SPEC_WISSEN_KERN_v1 WK-04: Wissen ist seit 05.11.2026 Grundfunktion; ein früher gespeicherter Zuschnitt verliert beim Laden nur diesen Eintrag."""
        p = projekt()
        (Path(p) / 'runtime_data' / 'harness' / 'profile').mkdir(parents=True)
        alt = {'start': {'ausblenden': ['wissen', 'logbook']}, 'marke': {'name': 'Alt GmbH'}}
        (Path(p) / 'runtime_data' / 'harness' / 'desktop.json').write_text(json.dumps(alt), encoding='utf-8')
        jetzt = dt.laden(p)
        self.assertEqual((jetzt['start']['ausblenden'], jetzt['marke']['name']), (['logbook'], 'Alt GmbH'))
        (Path(p) / 'runtime_data' / 'harness' / 'profile' / 'alt.json').write_text(json.dumps(dict(alt, name='Alt')), encoding='utf-8')
        self.assertEqual(dt.profil_lesen(p, 'alt')['start']['ausblenden'], ['logbook'])

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


PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
SVG = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciLz4='


class LogoSchriftStartseite(unittest.TestCase):
    """Marke mit Logo und Schrift, Startseite (05.11.2026): was erlaubt ist, was nie durchkommt, und dass Profile alles mitnehmen."""

    def test_logo_schrift_und_startseite_werden_gespeichert(self):
        p = projekt()
        w = dt.speichern(p, {'marke': {'name': 'Muster', 'logo': PNG, 'schrift': 'serif'}, 'startseite': {'ort': 'tasks', 'titel': 'Willkommen', 'text': 'Hier arbeitest du.'}})
        self.assertEqual((w['marke']['logo'], w['marke']['schrift'], w['startseite']),
                         (PNG, 'serif', {'ort': 'tasks', 'titel': 'Willkommen', 'text': 'Hier arbeitest du.'}))
        self.assertEqual(dt.speichern(p, {'marke': {'logo': SVG}})['marke']['logo'], SVG)
        self.assertEqual(dt.speichern(p, {'startseite': None})['startseite'], {'ort': '', 'titel': '', 'text': ''})

    def test_ungueltige_logos_schriften_und_startseiten(self):
        for schlecht in ({'marke': {'logo': 'https://fremd.example/logo.png'}}, {'marke': {'logo': 'data:text/html;base64,PHNjcmlwdD4='}},
                         {'marke': {'logo': 'data:image/png;base64,' + 'A' * 200_001}}, {'marke': {'logo': 'data:image/png;base64,@@@'}}, {'marke': {'logo': 5}},
                         {'marke': {'schrift': 'Comic Sans'}}, {'marke': {'schrift': 'serif; background: url(x)'}},
                         {'startseite': {'ort': '../x'}}, {'startseite': {'titel': 'x' * 61}}, {'startseite': {'text': 'x' * 301}}, {'startseite': {'html': '<b>'}}):
            with self.assertRaises(ValueError, msg=str(schlecht)[:60]):
                dt.speichern(projekt(), schlecht)

    def test_ein_profil_nimmt_logo_schrift_und_startseite_mit(self):
        a, b = projekt(), projekt()
        dt.speichern(a, {'marke': {'name': 'Kunde', 'logo': PNG, 'schrift': 'humanist'}, 'startseite': {'ort': 'decisions', 'titel': 'Hallo'}})
        dt.aktion(a, {'aktion': 'profil_speichern', 'id': 'kunde', 'name': 'Kunde'})
        export = json.loads(json.dumps(dt.profil_lesen(a, 'kunde')))
        self.assertEqual((export['marke']['schrift'], export['startseite']['ort']), ('humanist', 'decisions'))
        dt.aktion(b, {'aktion': 'profil_importieren', 'profil': export})
        w = dt.aktion(b, {'aktion': 'profil_anwenden', 'id': 'kunde'})
        self.assertEqual((w['marke']['logo'], w['startseite']['titel']), (PNG, 'Hallo'))


class LayoutBaukasten(unittest.TestCase):
    """Baukasten und Raster (05.11.2026): das Layout ist Teil der Wahl und der Profile; nur bekannte Bausteine, nur Zellen im Raster, Grundfunktionen bleiben sichtbar."""

    LAYOUT = {'start': {'schritte': {'x': 4, 'y': 5, 'b': 6, 'h': 3, 'sichtbar': True}, 'hilfe': {'sichtbar': False}},
              'zeile': {'reihenfolge': ['vorgabe', 'projekt'], 'ausblenden': ['neues-projekt']},
              'werkzeuge': {'reihenfolge': ['plus', 'schild', 'modell', 'senden', 'mikro'], 'ausblenden': ['mikro']}}

    def test_layout_wird_gespeichert_und_zurueckgesetzt(self):
        p = projekt()
        w = dt.speichern(p, {'layout': self.LAYOUT})
        self.assertEqual(w['layout']['start']['schritte'], {'x': 4, 'y': 5, 'b': 6, 'h': 3, 'sichtbar': True})
        self.assertEqual(w['layout']['start']['hilfe'], {'x': 1, 'y': 1, 'b': 12, 'h': 1, 'sichtbar': False}, 'fehlende Angaben werden aufgefuellt')
        self.assertEqual((w['layout']['zeile']['ausblenden'], w['layout']['werkzeuge']['reihenfolge'][3]), (['neues-projekt'], 'senden'))
        w = dt.speichern(p, {'layout': None})
        leer = {'reihenfolge': [], 'ausblenden': []}
        self.assertEqual(w['layout'], {'start': {}, 'zeile': leer, 'werkzeuge': leer, 'menue': leer, 'blick': leer, 'zonen': dt.ZONEN_VORGABE})

    def test_ungueltiges_layout_wird_abgewiesen(self):
        for schlecht in ({'start': {'gibtsnicht': {}}}, {'start': {'gruss': {'x': 12, 'b': 2}}}, {'start': {'gruss': {'x': 0}}}, {'start': {'gruss': {'y': 41}}}, {'start': {'gruss': {'h': 21}}},
                         {'start': {'gruss': {'x': '1'}}}, {'start': {'gruss': {'x': True}}}, {'start': {'gruss': {'sichtbar': 'ja'}}}, {'start': {'gruss': {'z': 1}}}, {'start': []},
                         {'zeile': {'reihenfolge': ['plus']}}, {'zeile': {'ausblenden': ['../x']}}, {'werkzeuge': {'reihenfolge': ['gibtsnicht']}}, {'fremd': {}}):
            with self.assertRaises(ValueError, msg=str(schlecht)[:70]):
                dt.speichern(projekt(), {'layout': schlecht})

    def test_start_menue_abschnitte_und_kacheln(self):
        p = projekt()
        w = dt.speichern(p, {'layout': {'menue': {'reihenfolge': ['gruppen', 'blick'], 'ausblenden': ['zuletzt', 'oberflaechen']}, 'blick': {'reihenfolge': ['hardware', 'einstellungen'], 'ausblenden': ['labor']}}})
        self.assertEqual((w['layout']['menue']['ausblenden'], w['layout']['blick']['reihenfolge']), (['zuletzt', 'oberflaechen'], ['hardware', 'einstellungen']))
        for schlecht, grund in (({'menue': {'ausblenden': ['gruppen']}}, 'desktop_grundfunktion'), ({'blick': {'ausblenden': ['einstellungen']}}, 'desktop_grundfunktion'),
                                ({'menue': {'reihenfolge': ['plus']}}, 'desktop_layout_ungueltig'), ({'blick': {'reihenfolge': ['gibtsnicht']}}, 'desktop_layout_ungueltig')):
            with self.assertRaises(ValueError, msg=str(schlecht)) as ctx:
                dt.speichern(projekt(), {'layout': schlecht})
            self.assertTrue(str(ctx.exception).startswith(grund))
        dt.speichern(projekt(), {'layout': {'menue': {'reihenfolge': ['gruppen']}, 'blick': {'reihenfolge': ['einstellungen']}}})      # verschieben darf man sie

    def test_seitenaufbau_platz_und_breite(self):
        p = projekt()
        w = dt.speichern(p, {'layout': {'zonen': {'seite': {'platz': 'rechts', 'breite': 320}, 'taskleiste': {'platz': 'oben'}, 'eingabe': {'platz': 'oben', 'breite': 900}}}})
        self.assertEqual(w['layout']['zonen'], {'seite': {'platz': 'rechts', 'breite': 320}, 'taskleiste': {'platz': 'oben'}, 'eingabe': {'platz': 'oben', 'breite': 900}})
        w = dt.speichern(p, {'layout': {'zonen': {'seite': {'platz': 'rechts'}}}})
        self.assertEqual(w['layout']['zonen']['seite'], {'platz': 'rechts', 'breite': 0}, 'fehlende Angaben gelten als Vorgabe')
        self.assertEqual(w['layout']['zonen']['eingabe'], {'platz': 'unten', 'breite': 0})
        for schlecht in ({'seite': {'platz': 'aus'}}, {'seite': {'platz': 'mitte'}}, {'taskleiste': {'platz': 'links'}}, {'eingabe': {'platz': 'oben', 'breite': 100}}, {'seite': {'breite': 9999}},
                         {'seite': {'breite': '300'}}, {'seite': {'breite': True}}, {'taskleiste': {'breite': 300}}, {'reiter': {'platz': 'oben'}}, {'seite': 'rechts'}):
            with self.assertRaises(ValueError, msg=str(schlecht)):
                dt.speichern(projekt(), {'layout': {'zonen': schlecht}})
        self.assertEqual(dt.speichern(p, {'layout': None})['layout']['zonen'], dt.ZONEN_VORGABE)

    def test_freigabe_schild_und_senden_lassen_sich_nie_ausblenden(self):
        for baustein in dt.GRUND_WERKZEUGE:
            with self.assertRaises(ValueError) as ctx:
                dt.speichern(projekt(), {'layout': {'werkzeuge': {'ausblenden': [baustein]}}})
            self.assertTrue(str(ctx.exception).startswith('desktop_grundfunktion'), baustein)
        w = dt.speichern(projekt(), {'layout': {'werkzeuge': {'reihenfolge': ['senden', 'schild']}}})          # verschieben darf man sie
        self.assertEqual(w['layout']['werkzeuge']['reihenfolge'], ['senden', 'schild'])

    def test_ein_profil_nimmt_das_layout_mit_auch_beim_importieren(self):
        a, b = projekt(), projekt()
        dt.speichern(a, {'layout': self.LAYOUT})
        dt.aktion(a, {'aktion': 'profil_speichern', 'id': 'kunde', 'name': 'Kunde'})
        export = json.loads(json.dumps(dt.profil_lesen(a, 'kunde')))
        dt.aktion(b, {'aktion': 'profil_importieren', 'profil': export})
        w = dt.aktion(b, {'aktion': 'profil_anwenden', 'id': 'kunde'})
        self.assertEqual(w['layout'], dt.laden(a)['layout'])
        boese = json.loads(json.dumps(export))
        boese['id'] = 'boese'
        boese['layout']['werkzeuge']['ausblenden'] = ['senden']
        with self.assertRaises(ValueError):
            dt.aktion(b, {'aktion': 'profil_importieren', 'profil': boese})


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
        self.assertEqual((s['grundfunktionen']['start'], s['gruppen'][:2]), (['decisions', 'tasks', 'wissen'], ['arbeit', 'modelle']))
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
