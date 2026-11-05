"""Token und Gespräch (02.11.2026): wählbare Grenzen zum Token sparen und das Gedächtnis ansehen, exportieren, löschen."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.core.guard import Guard
from guppi_runtime.harness import gedaechtnis, katalog, kontext, schleife
from guppi_runtime.harness.api import OPTIONEN, VERLAUF_MAX, HarnessApi, verlauf_aus
from guppi_runtime.harness.sitzung import Sitzungen
from guppi_runtime.harness.strom import Stroeme
from guppi_runtime.harness.werkzeuge import LESEN_ZEICHEN_MAX, Werkzeuge

from test_harness_schleife import MISSION, Attrappe, Box, Zug

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'


class OptionenTests(unittest.TestCase):
    def api(self, vorgaben):
        api = HarnessApi.__new__(HarnessApi)
        api._laufzeit_vorgaben = lambda: vorgaben
        return api

    def test_standard_und_unbekannte_werte(self):
        api = self.api({})
        self.assertEqual({n: api._option(n) for n in OPTIONEN}, {n: s for n, (s, _) in OPTIONEN.items()})
        api = self.api({'lese_grenze': '999', 'verlauf_laenge': 'viele', 'denken': 'quatsch'})
        self.assertEqual((api._option('lese_grenze'), api._option('verlauf_laenge'), api._option('denken')), ('8000', '20', 'standard'))
        self.assertEqual(self.api({'lese_grenze': '4000'})._option('lese_grenze'), '4000')

    def test_vorgaben_setzen_prueft_die_werte_und_nimmt_null_als_standard(self):
        with tempfile.TemporaryDirectory() as tmp:
            api = HarnessApi.__new__(HarnessApi)
            api.hub = type('H', (), {'project_root': Path(tmp), 'events': None})()
            api._audit = lambda *a, **k: None
            api._melden = lambda *a, **k: None
            api.vorgaben = lambda: {}
            api.projekte = lambda: {'projekte': [], 'fehler': None}
            for bad in ({'lese_grenze': '1'}, {'denken': 'viel'}, {'kontext_sicherung': 'nie'}):
                with self.assertRaises(ValueError):
                    api.vorgaben_setzen(bad)
            api.vorgaben_setzen({'lese_grenze': '4000', 'denken': 'aus'})
            api._laufzeit_vorgaben = lambda: __import__('guppi_runtime.harness.projekte', fromlist=['x']).laufzeit_laden(Path(tmp))['vorgaben']
            self.assertEqual((api._option('lese_grenze'), api._option('denken')), ('4000', 'aus'))
            api.vorgaben_setzen({'lese_grenze': None})
            self.assertEqual(api._option('lese_grenze'), '8000')
            self.assertEqual(api._option('denken'), 'aus')

    def test_die_verlauflaenge_waehlt_wie_viele_nachrichten_mitgehen(self):
        e = []
        for i in range(30):
            e.append({'typ': 'captain', 'text': f'Frage {i}'})
        self.assertEqual(len(verlauf_aus(e)), VERLAUF_MAX)
        self.assertEqual(len(verlauf_aus(e, 'aus', 10)), 10)
        self.assertEqual(verlauf_aus(e, 'aus', 10)[-1]['content'], 'Frage 29')
        self.assertEqual(len(verlauf_aus(e, 'aus', 30)), 30)


class LeseGrenzeTests(unittest.TestCase):
    def test_die_lese_grenze_bestimmt_wie_viel_ein_aufruf_liefert(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'projekt'
            (root / 'docs').mkdir(parents=True)
            (root / 'docs' / 'a.md').write_text('\n'.join('Zeile ' + 'x' * 40 + f' {i}' for i in range(1, 401)) + '\n', encoding='utf-8')
            guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(tmp) / 'tokens.json')
            regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
            projekt = {'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': ['docs/**']}
            zeilen = {}
            for name, grenze in (('standard', None), ('klein', 2000)):
                w = Werkzeuge(projekt, guard=guard, mission_id='M-L', regeln=regeln, lese_grenze=(lambda g=grenze: g) if grenze else None)
                out = w.ausfuehren('datei_lesen', {'pfad': 'docs/a.md', 'zeilen': 400})
                zeilen[name] = len(out['ergebnis'].splitlines())
                self.assertIn('weiter mit ab_zeile=', out['ergebnis'])
                self.assertLessEqual(len(out['ergebnis']), (grenze or LESEN_ZEICHEN_MAX) + 300)
            self.assertLess(zeilen['klein'], zeilen['standard'])


class SicherungDenkenTests(unittest.TestCase):
    def test_die_schwellen_sind_waehlbar(self):
        self.assertEqual([kontext.pruefen(850, 1000, s) for s in ('frueh', 'normal', 'spaet')], ['kuerzen', 'ok', 'ok'])
        self.assertEqual([kontext.pruefen(920, 1000, s) for s in ('frueh', 'normal', 'spaet')], ['abschluss', 'kuerzen', 'ok'])
        self.assertEqual([kontext.pruefen(960, 1000, s) for s in ('frueh', 'normal', 'spaet')], ['abschluss', 'abschluss', 'kuerzen'])
        self.assertEqual(kontext.pruefen(1000, 1000, 'spaet'), 'voll')
        self.assertEqual(kontext.pruefen(920, 1000, 'quatsch'), kontext.pruefen(920, 1000, 'normal'))

    def lauf(self, denken):
        with tempfile.TemporaryDirectory() as tmp:
            sitzungen = Sitzungen(Path(tmp))
            sid = sitzungen.anlegen('p')['id']
            a = Attrappe([Zug('Antwort.')])
            schleife.laufen(a, MISSION, Box(), [{'role': 'user', 'content': 'Hallo'}], Stroeme().anlegen(sid), modell='m', sitzungen=sitzungen, sitzung_id=sid, denk_modus=denken)
            return a.requests[0]

    def test_denken_eingrenzen_geht_als_feld_an_den_modellaufruf(self):
        standard = self.lauf('standard')
        self.assertNotIn('reasoning_effort', standard)
        self.assertNotIn('thinking_budget_tokens', standard)
        self.assertEqual(self.lauf('aus')['reasoning_effort'], 'none')
        begrenzt = self.lauf('begrenzt')
        self.assertEqual(begrenzt['thinking_budget_tokens'], schleife.DENKEN_BUDGET)
        self.assertNotIn('reasoning_effort', begrenzt)


class GedaechtnisVerwaltung(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for i, (f, a) in enumerate((('Rekorder öffnen', 'geöffnet'), ('Projekt anlegen', 'beantragt'), ('Rekorder Verknüpfung', 'angelegt')), 1):
            gedaechtnis.merken(self.root, 'sedra', 'S-1', {'antwort_id': f'A-{i:08d}', 'zeit': f'2026-11-02T12:0{i}:00+01:00', 'frage': f, 'antwort': a, 'werkzeuge': ['app_oeffnen'], 'gedanken': ''})

    def test_ansehen_neueste_zuerst_mit_suche(self):
        alle = gedaechtnis.ansehen(self.root, 'sedra')
        self.assertEqual((alle['gesamt'], alle['treffer']), (3, 3))
        self.assertEqual([n['antwort_id'] for n in alle['notizen']], ['A-00000003', 'A-00000002', 'A-00000001'])
        s = gedaechtnis.ansehen(self.root, 'sedra', 'rekorder verknüpfung')
        self.assertEqual([n['antwort_id'] for n in s['notizen']], ['A-00000003'])                  # jedes Wort muss vorkommen
        self.assertEqual(gedaechtnis.ansehen(self.root, 'sedra', 'Staubsauger')['treffer'], 0)
        self.assertEqual(len(gedaechtnis.ansehen(self.root, 'sedra', '', 2)['notizen']), 2)

    def test_eine_notiz_loeschen_und_die_zusammenfassung_gibt_ihre_notizen_wieder_frei(self):
        gedaechtnis.merken(self.root, 'sedra', None, {'art': 'zusammenfassung', 'antwort_id': 'Z-00000003', 'frage': 'Z', 'antwort': 'alles', 'deckt': ['A-00000001', 'A-00000002', 'A-00000003']})
        self.assertEqual(gedaechtnis.stand(self.root, 'sedra')['unverdichtet'], 0)
        self.assertEqual(gedaechtnis.loeschen(self.root, 'sedra', 'Z-00000003'), 1)
        self.assertEqual(gedaechtnis.stand(self.root, 'sedra'), {'notizen': 3, 'unverdichtet': 3, 'zusammenfassungen': 0})
        gedaechtnis.loeschen(self.root, 'sedra', 'A-00000002')
        self.assertEqual([n['antwort_id'] for n in gedaechtnis.laden(self.root, 'sedra')], ['A-00000001', 'A-00000003'])
        with self.assertRaises(ValueError):
            gedaechtnis.loeschen(self.root, 'sedra', 'A-DEADBEEF')
        with self.assertRaises(ValueError):
            gedaechtnis.loeschen(self.root, 'sedra', '')

    def test_alles_loeschen_entfernt_die_datei_und_ein_anderes_projekt_bleibt(self):
        gedaechtnis.merken(self.root, 'baut', 'S-2', {'antwort_id': 'A-00000009', 'frage': 'x', 'antwort': 'y'})
        self.assertEqual(gedaechtnis.alle_loeschen(self.root, 'sedra'), 3)
        self.assertEqual(gedaechtnis.laden(self.root, 'sedra'), [])
        self.assertEqual(len(gedaechtnis.laden(self.root, 'baut')), 1)
        self.assertEqual(gedaechtnis.alle_loeschen(self.root, 'sedra'), 0)
        with self.assertRaises(ValueError):
            gedaechtnis.alle_loeschen(self.root, '../x')

    def test_export_als_markdown(self):
        md = gedaechtnis.als_markdown(self.root, 'sedra', 'Sedra')
        self.assertTrue(md.startswith('# Gedächtnis des Projekts Sedra'))
        self.assertIn('## A-00000001', md)
        self.assertIn('- Frage: Rekorder öffnen', md)
        self.assertIn('- Werkzeuge: app_oeffnen', md)

    def test_die_wege_der_api_liefern_loeschen_und_exportieren(self):
        api = HarnessApi.__new__(HarnessApi)
        api.hub = type('H', (), {'project_root': self.root})()
        api._projekt = lambda pid: {'id': pid, 'name': 'Sedra'}
        gesehen = []
        api._audit = lambda event, payload: gesehen.append((event, payload))
        notizen = api.gedaechtnis_weg('GET', {'projekt': ['sedra'], 'suche': ['Projekt']}, {}, 'notizen')
        self.assertEqual([n['antwort_id'] for n in notizen['notizen']], ['A-00000002'])
        export = api.gedaechtnis_weg('GET', {'projekt': ['sedra']}, {}, 'export')
        self.assertEqual(export['dateiname'], 'gedaechtnis-sedra.md')
        self.assertIn('Rekorder', export['text'])
        out = api.gedaechtnis_weg('DELETE', {'projekt': ['sedra'], 'id': ['A-00000001']}, {}, None)
        self.assertEqual(out['geloescht'], 1)
        out = api.gedaechtnis_weg('DELETE', {'projekt': ['sedra'], 'alle': ['1']}, {}, None)
        self.assertEqual((out['geloescht'], out['stand']['notizen']), (2, 0))
        self.assertEqual([e for e, _ in gesehen], ['HARNESS_GEDAECHTNIS_GELOESCHT', 'HARNESS_GEDAECHTNIS_GELOESCHT'])


@unittest.skipUnless(__import__('shutil').which('node'), 'node fehlt')
class GespraechsoptionenTests(unittest.TestCase):
    """Das Feld unter dem Schild (gespraechsoptionen.js) und die Seite „Token und Gespräch“ nutzen dieselben Listen – und die müssen zu den Werten des Servers passen."""

    def optionen(self):
        import json
        import subprocess
        ordner = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix' / 'shells' / 'harness'
        skript = ("globalThis.sedraDom = {}; globalThis.document = {};" + chr(10)
                  + f"require({json.dumps(str(ordner / 'tokenseite.js'))}); require({json.dumps(str(ordner / 'gespraechsoptionen.js'))});" + chr(10)
                  + "console.log(JSON.stringify(globalThis.sedraHarness.gespraechsoptionen.zeilen().map(z=>({k: z.schluessel, werte: z.wahl.map(w=>w[0])}))));")
        r = subprocess.run(['node', '-e', skript], capture_output=True, text=True, timeout=60, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        return {z['k']: z['werte'] for z in json.loads(r.stdout)}

    def test_die_zeilen_unter_dem_schild_passen_zum_server(self):
        from guppi_runtime.harness.api import GEDANKEN_MODI
        z = self.optionen()
        self.assertEqual(list(z), ['denken', 'gedanken_zurueck', 'antwort_budget', 'verlauf_laenge', 'wissen_zuerst'])     # wissen_zuerst: SPEC_WISSEN_KERN_v1 WK-13
        self.assertEqual(set(z['gedanken_zurueck']), set(GEDANKEN_MODI))
        for schluessel in ('denken', 'antwort_budget', 'verlauf_laenge', 'wissen_zuerst'):
            self.assertEqual(set(z[schluessel]), set(OPTIONEN[schluessel][1]), schluessel)                       # dieselben Werte (die Reihenfolge der Anzeige darf anders sein)


if __name__ == '__main__':
    unittest.main()
