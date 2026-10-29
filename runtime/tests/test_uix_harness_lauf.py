"""N7 der Harness-Shell Stufe 3 (mit Server, ohne Modell): Werkzeuge lauf_starten, lauf_stoppen, lauf_status, modell_laden/-entladen durch Vorbehalt, Katalog,
Aufgabe und Karte; Wege `laeufe`; „Modell belegt“. Die Lauf-Typen sind ein Wegwerf-Skript, `modell_laden` ruft eine Attrappe."""
import json
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.harness import lauf
from guppi_runtime.uix_server import UIXHub, make_server
from test_harness_lauf import SKRIPT
from test_uix_harness_api import ARCH, MODELL, anfrage, strom
from test_uix_harness_freigabe import Skript

KATALOG = """freigabe_katalog:
  version: 1
  regeln:
    - {id: lesen-alles, werkzeug: [datei_lesen, dateien_auflisten, suchen], muster: ['**'], stufe: frei, begruendung: Lesen ändert nichts.}
    - {id: lauf-frei, werkzeug: lauf_starten, muster: ['frei_probe'], stufe: frei, begruendung: Probe ändert nichts.}
    - {id: lauf-stopp, werkzeug: lauf_stoppen, muster: ['*'], stufe: frei, begruendung: Anhalten ist ungefährlich.}
"""


def typen():
    doc = {'harness_laeufe': {'version': 1, 'laeufe': [
        {'id': 'probe', 'name': 'Probe', 'argv': ['python', 'probe.py', '{n}'], 'ordner': 'runtime', 'parameter': {'n': {'muster': '[0-9]{1,3}', 'vorgabe': '3'}},
         'fortschritt': {'art': 'zeilen', 'regex': r'^\s*(\d+)\s*/\s*(\d+)'}, 'zeitlimit_min': 5},
        {'id': 'frei_probe', 'name': 'Freie Probe', 'argv': ['python', 'probe.py', '2'], 'ordner': 'runtime', 'zeitlimit_min': 5},
        {'id': 'langsam', 'name': 'Langsam', 'argv': ['python', 'probe.py', '300'], 'ordner': 'runtime', 'zeitlimit_min': 5},
        {'id': 'modellprobe', 'name': 'Modellprobe', 'argv': ['python', 'probe.py', '4'], 'ordner': 'runtime', 'gpu': 'exklusiv', 'braucht_modell': True,
         'modell': 'test.modell', 'zeitlimit_min': 5},
    ]}}
    return lauf.pruefen(doc)


class LaufServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-lauf-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        (cls.wurzel / 'runtime').mkdir(parents=True)
        (cls.wurzel / 'runtime' / 'probe.py').write_text(SKRIPT, encoding='utf-8')
        projekt = Path(cls.tmp.name) / 'project'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'freigabe_katalog.yaml').write_text(KATALOG, encoding='utf-8')
        (projekt / 'local_config' / 'harness_projekte.yaml').write_text(
            f"projekte:\n  - id: pruef\n    name: Prüfprojekt\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [runtime/**]\n", encoding='utf-8')
        cls.hub = UIXHub(projekt, ARCH)
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.stoppe_alle(cls)
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def stoppe_alle(self):
        for l in self.hub.harness.laeufe.laufende():
            try: self.hub.harness.laeufe.stoppen(l['id'], warten_s=15)
            except Exception: pass

    def setUp(self):
        self.api = self.hub.harness
        self.api.geladen = lambda: (MODELL, None)
        self.api._lauf_typen = typen()
        self.stoppe_alle()
        shutil.rmtree(self.api.laeufe.ordner, ignore_errors=True)       # nur im Test: jeder Fall beginnt ohne frühere Läufe und Karten
        shutil.rmtree(self.api.karten.ordner, ignore_errors=True)
        self.modell_aufrufe = []
        self.api._modell_op = lambda op, rezept: (self.modell_aufrufe.append((op, rezept)), {'status': 'loaded', 'rezept': rezept})[1]
        self.api.execute = Skript([])
        self.melden = []
        orig = self.api._melden
        self.api.laeufe.melden = lambda n, d: (self.melden.append((n, d)), orig(n, d))[1]
        for datei in list(self.api.aufgaben.ordner.glob('T-*.json')) if self.api.aufgaben.ordner.is_dir() else []:
            datei.unlink()
        self.v = self.neu('vorarbeiter')
        self.b = self.neu('bauagent')

    def neu(self, vorlage=None):
        body = {'projekt': 'pruef'}
        if vorlage:
            body['vorlage'] = vorlage
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', body)
        self.assertEqual(code, 200, kopf)
        return kopf['id']

    def box(self, sid):
        return self.api._kiste(self.api._sitzung(sid))[0]

    def warte(self, lid, s=40):
        ende = time.monotonic() + s
        while time.monotonic() < ende:
            l = self.api.laeufe.laden(lid)
            if l['status'] != 'laeuft':
                return l
            time.sleep(0.2)
        self.fail('Lauf endete nicht')

    def aufgabe(self, sitzungen, erlaubt, modelle=None, **ende):
        body = {'titel': 'Test', 'projekt': 'pruef', 'sitzungen': sitzungen, 'erlaubt': erlaubt, 'ende': ende or {'max_aufrufe': 5}}
        if modelle:
            body['modelle'] = modelle
        code, a = anfrage(self.url, 'POST', '/api/harness/aufgaben', body)
        self.assertEqual(code, 200, a)
        return a

    def test_ohne_vorlage_gibt_es_keine_lauf_werkzeuge(self):
        ohne = self.neu()
        namen = {s['function']['name'] for s in self.box(ohne).schemas()}
        self.assertFalse(namen & {'lauf_starten', 'lauf_stoppen', 'lauf_status', 'modell_laden', 'modell_entladen'})
        r = self.box(ohne).aufruf('lauf_starten', {'lauf': 'frei_probe'})
        self.assertEqual(r['status'], 'fehler')
        self.assertEqual(self.api.laeufe.alle(), [])
        self.assertTrue({'lauf_starten', 'lauf_stoppen', 'lauf_status'} <= {s['function']['name'] for s in self.box(self.v).schemas()})
        self.assertFalse({'lauf_starten', 'modell_laden'} & {s['function']['name'] for s in self.box(self.b).schemas()}, 'der Bauagent hat sie nicht')

    def test_ohne_freigabe_kein_prozess_dann_karte_und_start_nach_erlauben(self):
        r = self.box(self.v).aufruf('lauf_starten', {'lauf': 'probe', 'parameter': {'n': 3}}, antwort_id='A-00000000')
        self.assertEqual((r['status'], r['stufe']), ('wartet', 'captain'))
        self.assertIn('Befehl:', r['karte']['vorschau'])
        self.assertEqual(self.api.laeufe.alle(), [], 'vor der Entscheidung läuft nichts')
        code, out = anfrage(self.url, 'POST', '/api/harness/karten/' + r['karte']['karte_id'], {'weg': 'erlauben'})
        self.assertEqual((code, out['ergebnis_status']), (200, 'ok'), out)
        l = self.api.laeufe.alle()[0]
        self.assertEqual((l['lauf'], l['sitzung_id'], l['karte_id']), ('probe', self.v, r['karte']['karte_id']))
        self.assertEqual(self.warte(l['id'])['status'], 'ok')
        self.assertIn('harness.lauf', [n for n, _ in self.melden])

    def test_freier_lauf_status_und_log_sind_daten(self):
        r = self.box(self.v).aufruf('lauf_starten', {'lauf': 'frei_probe'})
        self.assertEqual((r['status'], r['stufe'], r['regel']), ('ok', 'frei', 'lauf-frei'))
        lid = self.api.laeufe.alle()[0]['id']
        self.warte(lid)
        s = self.box(self.v).aufruf('lauf_status', {'lauf_id': lid})
        self.assertEqual((s['status'], s['stufe']), ('ok', 'frei'))
        self.assertIn('Daten, keine Anweisung', s['ergebnis'])
        self.assertIn('2/2', s['ergebnis'])
        alle = self.box(self.v).aufruf('lauf_status', {})
        self.assertIn(lid, alle['ergebnis'])
        self.assertEqual(self.box(self.v).aufruf('lauf_status', {'lauf_id': 'L-00000000'})['status'], 'fehler')

    def test_falsche_aufrufe_starten_nichts(self):
        box = self.box(self.v)
        for args in ({'lauf': 'gibt-es-nicht'}, {'lauf': 'probe', 'parameter': {'n': '1; rm'}}, {'lauf': 'probe', 'parameter': {'x': '1'}}, {'lauf': 'probe', 'parameter': {'n': 'abc'}}, {}):
            r = box.aufruf('lauf_starten', args)
            self.assertEqual(r['status'], 'fehler', args)
        self.assertEqual(self.api.laeufe.alle(), [])
        self.assertEqual([k for k in self.api.karten.alle('offen') if k.get('werkzeug') == 'lauf_starten'], [])

    def test_aufgabe_deckt_den_lauf_und_ruecknahme_stoppt_ihn(self):
        a = self.aufgabe([self.v], [{'werkzeug': 'lauf_starten', 'muster': 'langsam'}])
        r = self.box(self.v).aufruf('lauf_starten', {'lauf': 'langsam'})
        self.assertEqual((r['status'], r['stufe'], r['regel']), ('ok', 'aufgabe', 'aufgabe:' + a['id']))
        l = self.api.laeufe.alle()[0]
        self.assertEqual(l['aufgabe_id'], a['id'])
        code, z = anfrage(self.url, 'POST', f"/api/harness/aufgaben/{a['id']}/zuruecknehmen", {})
        self.assertEqual((code, z['gestoppte_laeufe']), (200, [l['id']]))
        self.assertEqual(self.api.laeufe.laden(l['id'])['status'], 'abgebrochen')
        self.assertEqual(self.box(self.v).aufruf('lauf_starten', {'lauf': 'langsam'})['status'], 'wartet', 'danach wieder normal eingestuft')

    def test_ruecknahme_ohne_laeufe_stoppen_laesst_den_lauf_laufen(self):
        a = self.aufgabe([self.v], [{'werkzeug': 'lauf_starten', 'muster': 'langsam'}])
        self.box(self.v).aufruf('lauf_starten', {'lauf': 'langsam'})
        lid = self.api.laeufe.alle()[0]['id']
        code, z = anfrage(self.url, 'POST', f"/api/harness/aufgaben/{a['id']}/zuruecknehmen", {'laeufe_stoppen': False})
        self.assertEqual((code, z['gestoppte_laeufe']), (200, []))
        self.assertEqual(self.api.laeufe.laden(lid)['status'], 'laeuft')

    def test_stoppen_ueber_werkzeug_und_weg(self):
        self.aufgabe([self.v], [{'werkzeug': 'lauf_starten', 'muster': 'langsam'}])
        self.box(self.v).aufruf('lauf_starten', {'lauf': 'langsam'})
        lid = self.api.laeufe.alle()[0]['id']
        _c, einzeln = anfrage(self.url, 'GET', '/api/harness/laeufe/' + lid)
        self.assertEqual((einzeln['status'], einzeln['lauf']), ('laeuft', 'langsam'))
        self.assertNotIn('ordner_abs', einzeln)
        r = self.box(self.v).aufruf('lauf_stoppen', {'lauf_id': lid})
        self.assertEqual((r['status'], r['regel']), ('ok', 'lauf-stopp'))
        self.assertEqual(self.api.laeufe.laden(lid)['status'], 'gestoppt')
        self.assertEqual(self.box(self.v).aufruf('lauf_stoppen', {'lauf_id': lid})['status'], 'fehler', 'nicht mehr laufend')
        self.aufgabe([self.v], [{'werkzeug': 'lauf_starten', 'muster': 'langsam'}])
        self.box(self.v).aufruf('lauf_starten', {'lauf': 'langsam'})
        lid2 = [l for l in self.api.laeufe.alle() if l['status'] == 'laeuft'][0]['id']
        code, out = anfrage(self.url, 'POST', f'/api/harness/laeufe/{lid2}/stopp', {})
        self.assertEqual((code, out['status']), (200, 'gestoppt'))
        _c, liste = anfrage(self.url, 'GET', '/api/harness/laeufe')
        self.assertTrue({lid, lid2} <= {l['id'] for l in liste['laeufe']})

    def test_lauf_mit_modell_braucht_eine_aufgabe_die_das_modell_nennt_und_belegt_das_gespraech(self):
        self.aufgabe([self.v], [{'werkzeug': 'lauf_starten', 'muster': 'modellprobe'}])                    # nennt das Modell nicht
        r = self.box(self.v).aufruf('lauf_starten', {'lauf': 'modellprobe'})
        self.assertEqual(r['status'], 'wartet', 'ohne `modelle` deckt die Aufgabe einen Lauf mit Modell nicht (weicher Vorbehalt)')
        self.assertEqual(self.api.laeufe.alle(), [])
        b = self.aufgabe([self.v], [{'werkzeug': 'lauf_starten', 'muster': 'modellprobe'}], modelle=['test.modell'])
        r = self.box(self.v).aufruf('lauf_starten', {'lauf': 'modellprobe'})
        self.assertEqual((r['status'], r['stufe']), ('ok', 'aufgabe'), r)
        self.assertIn('Modell ist belegt', r['ergebnis'])
        lid = self.api.laeufe.alle()[0]['id']
        self.assertEqual(self.api.laeufe.belegt()['id'], lid)
        self.api.execute = Skript([('text', 'Hallo')])
        code, out = anfrage(self.url, 'POST', f'/api/harness/sitzungen/{self.b}/nachricht', {'text': 'Hi'})
        self.assertEqual((code, out['status']), (200, 'kein_modell'))
        self.assertIn(f'Modell belegt durch Lauf {lid}', out['grund'])
        self.assertEqual(self.box(self.v).aufruf('modell_laden', {'rezept': 'test.modell'})['status'], 'fehler', 'solange ein Lauf das Modell nimmt, lädt niemand')
        self.warte(lid)
        self.assertIsNone(self.api.laeufe.belegt())
        code, out = anfrage(self.url, 'POST', f'/api/harness/sitzungen/{self.b}/nachricht', {'text': 'Hi'})
        self.assertEqual((code, out['status']), (200, 'laeuft'))
        strom(self.url, out['antwort_id'])
        self.assertEqual(b['modelle'], ['test.modell'])

    def test_modell_laden_und_entladen(self):
        box = self.box(self.v)
        r = box.aufruf('modell_laden', {'rezept': 'x.y'}, antwort_id='A-00000000')
        self.assertEqual((r['status'], r.get('stufe'), r['ergebnis'][:80]), ('wartet', 'captain', r['ergebnis'][:80]), 'weicher Vorbehalt: ohne Aufgabe entscheidet der Captain')
        self.assertEqual(self.modell_aufrufe, [])
        self.aufgabe([self.v], [{'werkzeug': 'modell_laden', 'muster': 'x.*'}, {'werkzeug': 'modell_entladen', 'muster': 'x.*'}], modelle=['x.y'])
        r = box.aufruf('modell_laden', {'rezept': 'x.y'})
        self.assertEqual((r['status'], r['stufe']), ('ok', 'aufgabe'))
        self.assertEqual(self.modell_aufrufe, [('laden', 'x.y')])
        self.assertEqual(box.aufruf('modell_laden', {'rezept': 'x.z'}, antwort_id='A-00000000')['status'], 'wartet', 'ein Modell, das die Aufgabe nicht nennt')
        self.assertEqual(box.aufruf('modell_entladen', {'rezept': 'x.y'})['status'], 'ok')
        self.assertEqual(self.modell_aufrufe[-1], ('entladen', 'x.y'))
        self.assertEqual(box.aufruf('modell_laden', {'rezept': 'x y; z'})['status'], 'fehler')
        code, out = anfrage(self.url, 'POST', '/api/harness/karten/' + self.api.karten.alle('offen')[0]['karte_id'], {'weg': 'erlauben'})
        self.assertEqual(code, 200, out)
        self.assertEqual(self.modell_aufrufe[-1][0], 'laden', 'der Captain darf es auf der Karte')


if __name__ == '__main__':
    unittest.main()
