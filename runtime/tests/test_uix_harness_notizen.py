"""Gedächtnis-Notizen über die Harness (docs/SPEC_MASTER_MODUS_v1_ENTWURF.md GN-02 bis GN-06, GN-09): Index beim Sitzungsstart eingefroren, Werkzeuge, Antrag,
Wege des Captains, Projekte sehen sich nicht. Echter UIXHub wie in test_uix_harness_master; ersetzt wird nur das Modell."""
import json
import tempfile
import threading
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.harness import antraege_gedaechtnis, gedaechtnis_notizen as gn
from sedra_runtime.uix_server import UIXHub, make_server
from test_uix_harness_api import ARCH, MODELL, anfrage, strom
from test_uix_harness_freigabe import Skript

FB = 'Antworte kurz.\n\n**Warum:** der Captain liest viel.\n**Wann anwenden:** in jeder Antwort.'


class Notizen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-notizen-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        cls.wurzel.mkdir()
        projekt = Path(cls.tmp.name) / 'project'
        (projekt / 'local_config').mkdir(parents=True)
        (projekt / 'local_config' / 'harness_projekte.yaml').write_text(
            f"projekte:\n  - id: pa\n    name: A\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [docs/**]\n"
            f"  - id: pb\n    name: B\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [docs/**]\n", encoding='utf-8')
        cls.hub = UIXHub(projekt, ARCH)
        cls.projekt_root = projekt
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def setUp(self):
        self.hub.harness.geladen = lambda: (MODELL, None)
        for pid in ('pa', 'pb'):
            for n in gn.liste(self.projekt_root, pid):
                gn.loeschen(self.projekt_root, pid, n['name'])

    def sitzung(self, zuege=(), projekt='pa'):
        self.modell = Skript(zuege)
        self.hub.harness.execute = self.modell
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': projekt})
        self.assertEqual(code, 200, kopf)
        return kopf['id']

    def senden(self, sid, text='los'):
        code, out = anfrage(self.url, 'POST', f'/api/harness/sitzungen/{sid}/nachricht', {'text': text})
        self.assertEqual(code, 200, out)
        ev = strom(self.url, out['antwort_id'])
        import time
        for _ in range(100):
            if not self.hub.harness.threads:
                break
            time.sleep(0.05)
        return ev

    def captain_notiz(self, projekt='pa', name='kurz-antworten', **k):
        d = dict(projekt=projekt, typ='feedback', name=name, description='Der Captain will kurze Antworten', text=FB) | k
        return anfrage(self.url, 'POST', '/api/harness/gedaechtnis/index', d)

    def system(self):
        return self.modell.requests[0]['messages'][0]['content']

    def test_captain_legt_an_liest_listet_loescht(self):
        code, n = self.captain_notiz()
        self.assertEqual((code, n['name'], n['geaendert']), (200, 'kurz-antworten', False))
        code, liste = anfrage(self.url, 'GET', '/api/harness/gedaechtnis/index?projekt=pa')
        self.assertEqual([x['name'] for x in liste['notizen']], ['kurz-antworten'])
        self.assertIn('kurz-antworten.md', liste['index'][0])
        code, einzeln = anfrage(self.url, 'GET', '/api/harness/gedaechtnis/index?projekt=pa&name=kurz-antworten')
        self.assertIn('**Warum:**', einzeln['text'])
        code, n2 = self.captain_notiz(text=FB + '\nNeu.')
        self.assertEqual((code, n2['geaendert']), (200, True))
        code, out = anfrage(self.url, 'DELETE', '/api/harness/gedaechtnis/index?projekt=pa&name=kurz-antworten')
        self.assertEqual((code, out['geloescht']), (200, 'kurz-antworten'))

    def test_fehler_der_form_sind_400(self):
        code, body = self.captain_notiz(text='nur ein Satz')
        self.assertEqual(code, 400)
        self.assertIn('warum_wann_fehlen', json.dumps(body))
        code, _ = anfrage(self.url, 'GET', '/api/harness/gedaechtnis/index?projekt=gibtsnicht')
        self.assertEqual(code, 400)

    def test_index_steht_im_systemprompt_und_ist_eingefroren(self):
        self.captain_notiz()
        alt = self.sitzung([('text', 'ok')])
        self.senden(alt)
        self.assertIn('Gedächtnis dieses Projekts', self.system())
        self.assertIn('[kurz-antworten](kurz-antworten.md)', self.system())
        self.captain_notiz(name='zweite-notiz', typ='reference', description='Zweite', text='x')
        self.modell.requests.clear()
        self.modell.zuege.append(('text', 'ok2'))
        self.senden(alt, 'nochmal')
        self.assertNotIn('zweite-notiz', self.system(), 'eingefroren: die laufende Sitzung sieht die neue Notiz nicht')
        neu = self.sitzung([('text', 'ok')])
        self.senden(neu)
        self.assertIn('zweite-notiz', self.system())

    def test_projekt_b_sieht_nichts_von_a(self):
        self.captain_notiz(projekt='pa')
        sid = self.sitzung([('text', 'ok')], projekt='pb')
        self.senden(sid)
        self.assertNotIn('Gedächtnis dieses Projekts', self.system())
        self.assertNotIn('kurz-antworten', self.system())

    def test_ohne_notizen_kein_block(self):
        sid = self.sitzung([('text', 'ok')])
        self.senden(sid)
        self.assertNotIn('Gedächtnis dieses Projekts', self.system())

    def test_werkzeug_lesen_und_projektgrenze(self):
        self.captain_notiz(projekt='pa')
        a = self.sitzung([('calls', [('gedaechtnis_lesen', {'name': 'kurz-antworten'})]), ('text', 'gelesen')])
        ev = self.senden(a)
        ende = next(e[2] for e in ev if e[1] == 'werkzeug.ende')
        self.assertEqual((ende['status'], ende['stufe']), ('ok', 'frei'))
        self.assertIn('Antworte kurz.', ende['ergebnis'])
        b = self.sitzung([('calls', [('gedaechtnis_lesen', {'name': 'kurz-antworten', 'projekt': 'pa'})]), ('text', 'x')], projekt='pb')
        ende = next(e[2] for e in self.senden(b) if e[1] == 'werkzeug.ende')
        self.assertEqual(ende['status'], 'fehler')
        self.assertIn('notiz_unbekannt', ende['ergebnis'])

    def test_werkzeug_vorschlagen_ist_nur_ein_antrag(self):
        args = {'typ': 'feedback', 'name': 'ohne-emojis', 'description': 'Keine Emojis in Antworten', 'text': 'Keine Emojis.\n**Warum:** Captain mag sie nicht.\n**Wann anwenden:** immer.'}
        sid = self.sitzung([('calls', [('gedaechtnis_vorschlagen', args)]), ('text', 'beantragt')])
        ev = self.senden(sid)
        ende = next(e[2] for e in ev if e[1] == 'werkzeug.ende')
        self.assertEqual(ende['status'], 'ok', ende)
        self.assertIn('Posteingang', ende['ergebnis'])
        self.assertEqual(gn.liste(self.projekt_root, 'pa'), [], 'ohne Freigabe keine Datei')
        offen = [r for r in self.hub._open_requests() if r.get('kind') == antraege_gedaechtnis.KIND_NOTIZ and r['binding']['ziel'].endswith('/ohne-emojis')]
        self.assertEqual(len(offen), 1)
        self.assertEqual(offen[0]['binding']['projekt'], 'pa')
        antraege_gedaechtnis.notiz_anwenden(self.hub, offen[0]['binding'])
        self.assertEqual([n['name'] for n in gn.liste(self.projekt_root, 'pa')], ['ohne-emojis'])
        self.assertTrue(any(p['name'] == 'ohne-emojis' for p in self._audit('HARNESS_GEDAECHTNIS_NOTIZ')))

    def _audit(self, event):
        rows = [json.loads(l) for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
        return [r['payload'] for r in rows if r['event_type'] == event]

    def test_vorschlag_aehnlich_und_form_werden_abgelehnt(self):
        self.captain_notiz()
        args = {'typ': 'feedback', 'name': 'kurze-antworten-wunsch', 'description': 'Der Captain will kurze Antworten sehen',
                'text': 'Kurz.\n**Warum:** x.\n**Wann anwenden:** immer.'}
        sid = self.sitzung([('calls', [('gedaechtnis_vorschlagen', args)]), ('calls', [('gedaechtnis_vorschlagen', dict(args, text='Pfad C:\\Users\\x\\a'))]), ('text', 'x')])
        enden = [e[2] for e in self.senden(sid) if e[1] == 'werkzeug.ende']
        self.assertEqual([e['status'] for e in enden], ['fehler', 'fehler'])
        self.assertIn('aehnlich: kurz-antworten', enden[0]['ergebnis'])

    def test_antrag_stale_wenn_die_datei_sich_aendert(self):
        sid = self.sitzung([('calls', [('gedaechtnis_vorschlagen', {'typ': 'reference', 'name': 'ports', 'description': 'Ports der Dienste', 'text': 'Router 8081'})]), ('text', 'x')])
        self.senden(sid)
        offen = [r for r in self.hub._open_requests() if r.get('kind') == antraege_gedaechtnis.KIND_NOTIZ and r['binding']['ziel'].endswith('/ports')][-1]
        gn.speichern(self.projekt_root, 'pa', 'reference', 'ports', 'Ports', 'andere Fassung')
        with self.assertRaises(ValueError):
            antraege_gedaechtnis.notiz_anwenden(self.hub, offen['binding'])

    def test_klasse_und_einordnung(self):
        from sedra_runtime.desk import freigabeklasse as fk
        self.assertEqual(fk.klasse('request:harness_gedaechtnis', 'freigeben_und_anwenden', {}), fk.H)
        from sedra_runtime.harness.werkzeuge import NAMEN, WIRKUNGSKLASSE
        for n in ('gedaechtnis_lesen', 'gedaechtnis_vorschlagen'):
            self.assertIn(n, NAMEN)
            self.assertIn(n, WIRKUNGSKLASSE)


if __name__ == '__main__':
    unittest.main()
