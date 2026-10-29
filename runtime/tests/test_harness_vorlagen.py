"""N1 der Harness-Shell Stufe 3: Vorlagen (HS-19) – Laden und Prüfen, Vorrang des Captain-Ordners, Whitelist, Kopf, Systemprompt."""
import json
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.harness import schleife
from guppi_runtime.harness import vorlagen
from guppi_runtime.uix_server import UIXHub, make_server
from test_uix_harness_api import ARCH, MODELL, anfrage, strom
from test_uix_harness_freigabe import Skript

GUT = {'harness_vorlage': {'id': 'x', 'name': 'X', 'werkzeuge': ['datei_lesen'], 'rechte': {'vorarbeiter_freigabe': True}}}


class PruefenTests(unittest.TestCase):
    def test_gueltig_und_ungueltig_je_grund(self):
        v = vorlagen.pruefen(GUT, 'Text')
        self.assertEqual((v['id'], v['werkzeuge'], v['max_zuege'], v['rechte']), ('x', ['datei_lesen'], 24, {'vorarbeiter_freigabe': True, 'aufgaben_vorschlagen': False}))

        def fehler(aender, text='Text'):
            doc = json.loads(json.dumps(GUT)); aender(doc['harness_vorlage'])
            with self.assertRaises(vorlagen.VorlageFehler) as cm:
                vorlagen.pruefen(doc, text)
            return str(cm.exception)

        self.assertIn('vorlage_fehlt', self._fehl({}))
        self.assertIn('id_ungueltig', fehler(lambda v: v.update(id='X y')))
        self.assertIn('name_fehlt', fehler(lambda v: v.pop('name')))
        self.assertIn('werkzeug_unbekannt: hacken', fehler(lambda v: v.update(werkzeuge=['datei_lesen', 'hacken'])))
        self.assertIn('werkzeuge_fehlen', fehler(lambda v: v.update(werkzeuge=[])))
        self.assertIn('rechte_ungueltig', fehler(lambda v: v.update(rechte={'alles': True})))
        self.assertIn('rechte_ungueltig', fehler(lambda v: v.update(rechte={'vorarbeiter_freigabe': 'ja'})))
        self.assertIn('max_zuege_ungueltig', fehler(lambda v: v.update(max_zuege=99)))
        self.assertIn('system_leer', fehler(lambda v: None, '  '))
        self.assertIn('system_zu_lang', fehler(lambda v: None, 'x' * (vorlagen.SYSTEM_MAX + 1)))

    def _fehl(self, doc):
        try:
            vorlagen.pruefen(doc, 'Text')
        except vorlagen.VorlageFehler as exc:
            return str(exc)


class LadenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='vorlagen-')
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_mitgelieferte_vorlagen_sind_gueltig(self):
        ids = {v['id']: v for v in vorlagen.liste(self.root)}
        self.assertEqual(sorted(ids), ['bauagent', 'pruefer', 'vorarbeiter'])
        self.assertTrue(all(v['fehler'] is None for v in ids.values()), ids)
        self.assertTrue(ids['vorarbeiter']['rechte']['vorarbeiter_freigabe'])
        self.assertFalse(ids['bauagent']['rechte']['vorarbeiter_freigabe'])
        self.assertEqual(ids['pruefer']['werkzeuge'], ['datei_lesen', 'dateien_auflisten', 'suchen', 'befehl'])
        v = vorlagen.laden(self.root, 'vorarbeiter')
        self.assertIn('Vorarbeiter', v['system'])
        self.assertNotIn('Bionic', v['system'])
        self.assertEqual(len(v['hash']), 64)

    def test_local_config_hat_vorrang_und_wird_nicht_beschrieben(self):
        ordner = self.root / 'local_config' / 'harness_vorlagen'
        ordner.mkdir(parents=True)
        (ordner / 'pruefer.yaml').write_text("harness_vorlage:\n  id: pruefer\n  name: Eigener\n  system: pruefer.md\n  werkzeuge: [datei_lesen]\n", encoding='utf-8')
        (ordner / 'pruefer.md').write_text('Eigener Text', encoding='utf-8')
        vorher = sorted(p.name for p in ordner.iterdir())
        v = vorlagen.laden(self.root, 'pruefer')
        self.assertEqual((v['name'], v['system'], v['quelle']), ('Eigener', 'Eigener Text', 'local_config'))
        self.assertEqual(vorlagen.laden(self.root, 'bauagent')['quelle'], 'repo')
        self.assertEqual(sorted(p.name for p in ordner.iterdir()), vorher)

    def test_kaputte_vorlage_ist_ein_fehler_kein_rueckfall(self):
        ordner = self.root / 'local_config' / 'harness_vorlagen'
        ordner.mkdir(parents=True)
        (ordner / 'pruefer.yaml').write_text("harness_vorlage: [kaputt\n", encoding='utf-8')
        with self.assertRaises(vorlagen.VorlageFehler):
            vorlagen.laden(self.root, 'pruefer')
        eintrag = next(v for v in vorlagen.liste(self.root) if v['id'] == 'pruefer')
        self.assertIn('datei_unlesbar', eintrag['fehler'])
        (ordner / 'pruefer.yaml').write_text("harness_vorlage:\n  id: andere\n  name: A\n  system: pruefer.md\n  werkzeuge: [suchen]\n", encoding='utf-8')
        (ordner / 'pruefer.md').write_text('T', encoding='utf-8')
        with self.assertRaisesRegex(vorlagen.VorlageFehler, 'id_passt_nicht'):
            vorlagen.laden(self.root, 'pruefer')

    def test_unbekannt_und_pfadtricks(self):
        for vid in ('gibt-es-nicht', '../x', 'A B', None, ''):
            with self.assertRaisesRegex(vorlagen.VorlageFehler, 'vorlage_unbekannt'):
                vorlagen.laden(self.root, vid)

    def test_system_datei_nur_im_selben_ordner(self):
        ordner = self.root / 'local_config' / 'harness_vorlagen'
        ordner.mkdir(parents=True)
        (ordner / 'q.yaml').write_text("harness_vorlage:\n  id: q\n  name: Q\n  system: ../geheim.md\n  werkzeuge: [suchen]\n", encoding='utf-8')
        with self.assertRaisesRegex(vorlagen.VorlageFehler, 'system_ungueltig'):
            vorlagen.laden(self.root, 'q')


class SchleifeTests(unittest.TestCase):
    def test_systemprompt_mit_vorlage(self):
        text = schleife.system_prompt('Sedra Entwicklung', ['datei_lesen'], 'Du bist der Prüfer.')
        self.assertTrue(text.startswith('Du bist der Prüfer.'))
        self.assertIn('datei_lesen', text)
        self.assertEqual(schleife.system_prompt('P', ['a']), schleife.SYSTEM.format(projekt='P', werkzeuge='a'))


class SitzungMitVorlageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-vorlage-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        (cls.wurzel / 'docs').mkdir(parents=True)
        (cls.wurzel / 'docs' / 'a.md').write_text('inhalt\n', encoding='utf-8')
        projekt = Path(cls.tmp.name) / 'project'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'harness_projekte.yaml').write_text(
            f"projekte:\n  - id: pruef\n    name: Prüfprojekt\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [docs/**]\n", encoding='utf-8')
        cls.hub = UIXHub(projekt, ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def setUp(self):
        self.hub.harness.geladen = lambda: (MODELL, None)

    def neu(self, zuege, vorlage):
        self.modell = Skript(zuege)
        self.hub.harness.execute = self.modell
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef', 'vorlage': vorlage})
        self.assertEqual(code, 200, kopf)
        return kopf

    def test_wege_vorlagen_und_unbekannte_vorlage(self):
        code, out = anfrage(self.url, 'GET', '/api/harness/vorlagen')
        self.assertEqual(code, 200)
        self.assertEqual(sorted(v['id'] for v in out['vorlagen']), ['bauagent', 'pruefer', 'vorarbeiter'])
        code, body = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef', 'vorlage': 'gibt-es-nicht'})
        self.assertEqual((code, body['code']), (400, 'vorlage_unbekannt'))

    def test_kopf_prompt_whitelist_und_ablehnung(self):
        kopf = self.neu([('calls', [('datei_schreiben', {'pfad': 'docs/x.md', 'inhalt': 'a'})]), ('text', 'Nicht erlaubt.')], 'pruefer')
        self.assertEqual(kopf['vorlage'], 'pruefer')
        self.assertEqual(len(kopf['vorlage_hash']), 64)
        code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'Prüfe docs/a.md'})
        self.assertEqual(code, 200, out)
        ev = strom(self.url, out['antwort_id'])
        erster = self.modell.requests[0]
        self.assertIn('Prüfer', erster['messages'][0]['content'])
        angeboten = {t['function']['name'] for t in erster['tools']}
        self.assertEqual(angeboten, {'datei_lesen', 'dateien_auflisten', 'suchen', 'befehl'})
        ende = next(e[2] for e in ev if e[1] == 'werkzeug.ende')
        self.assertEqual(ende['status'], 'fehler')
        self.assertIn('nicht erlaubt', ende['ergebnis'])
        self.assertFalse((self.wurzel / 'docs' / 'x.md').exists(), 'außerhalb der Whitelist wird nichts geschrieben')

    def test_sitzung_ohne_vorlage_bleibt_wie_vorher(self):
        self.modell = Skript([('text', 'Hallo.')])
        self.hub.harness.execute = self.modell
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef'})
        self.assertEqual((code, kopf['vorlage'], kopf['vorlage_hash']), (200, None, None))
        code, out = anfrage(self.url, 'POST', f"/api/harness/sitzungen/{kopf['id']}/nachricht", {'text': 'Hi'})
        strom(self.url, out['antwort_id'])
        angeboten = {t['function']['name'] for t in self.modell.requests[0]['tools']}
        self.assertIn('datei_schreiben', angeboten)
        self.assertIn('SEDRA', self.modell.requests[0]['messages'][0]['content'])


if __name__ == '__main__':
    unittest.main()
