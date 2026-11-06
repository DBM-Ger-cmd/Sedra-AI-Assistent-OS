"""„Wissen zuerst“ im Zug von One Sedra (SPEC_WISSEN_KERN_v1 WK-13, WK-14, WK-15; G2 K1K2 §3.4, §3.4a, §3.5) am echten Hub mit Modell-Attrappe:
der feste Systemsatz steht in jedem Zug (auch ohne Treffer), der Block nur mit Treffern und in derselben Nachricht wie die Frage, im Verlauf
später nur die Marke [Wissen dazu: …] (Möglichkeit C); der Präfix-Test zeigt, dass sich zwei Züge erst bei der vorigen Frage unterscheiden.
Fremde Kennungen werden markiert, Kennungen aus `wissen_suchen` gelten. Je Sitzung abschaltbar; ohne Modell kommt die Trefferliste. Kein Modell, keine GPU."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.harness import schleife
from sedra_runtime.uix_server import UIXHub, make_server
from sedra_runtime.wissen import ausgabe
from test_uix_harness_api import ARCH, MODELL, anfrage, strom
from test_uix_harness_freigabe import Skript
from test_wissen_desk import NOTIZ, switch_on


class Zug(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='harness-wissen-zug-')
        cls.wurzel = Path(cls.tmp.name) / 'arbeit'
        (cls.wurzel / 'docs').mkdir(parents=True)
        projekt = Path(cls.tmp.name) / 'project'
        switch_on(projekt)
        (projekt / 'local_config' / 'harness_projekte.yaml').write_text(
            f"projekte:\n  - id: pruef\n    name: Prüfprojekt\n    wurzel: '{cls.wurzel}'\n    schreibbereich: [docs/**]\n", encoding='utf-8')
        (projekt / 'notizen').mkdir(parents=True)
        (projekt / 'notizen' / 'werkbank.md').write_text(NOTIZ, encoding='utf-8')
        cls.hub = UIXHub(projekt, ARCH)
        out = cls.hub.act({'type': 'wissen', 'verb': 'quelle_beantragen', 'args': {'adapter': 'markdown', 'wurzel': 'projekt', 'pfad': 'notizen/werkbank.md', 'stufe': 1}})['result']
        cls.hub.decide({'id': out['decision_id'], 'way': 'freigeben_und_anwenden'})
        cls.server, cls.url = make_server(cls.hub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.hub.close(); cls.tmp.cleanup()

    def setUp(self):
        self.hub.harness.geladen = lambda: (MODELL, None)

    def sitzung(self, zuege):
        self.modell = Skript(zuege)
        self.hub.harness.execute = self.modell
        code, kopf = anfrage(self.url, 'POST', '/api/harness/sitzungen', {'projekt': 'pruef'})
        self.assertEqual(code, 200, kopf)
        return kopf['id']

    def senden(self, sid, text):
        code, out = anfrage(self.url, 'POST', f'/api/harness/sitzungen/{sid}/nachricht', {'text': text})
        self.assertEqual(code, 200, out)
        ev = strom(self.url, out['antwort_id'])
        for _ in range(100):
            if not self.hub.harness.threads:
                break
            time.sleep(0.05)
        return ev

    def audit(self, event):
        rows = [json.loads(l) for l in self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
        return [r['payload'] for r in rows if r['event_type'] == event]

    def kennung(self):
        return self.hub.runtime.wissen.suche('Lease Testlabor', leser={'art': 'captain', 'stufe': 6, 'projekt': None, 'agent_id': None})['treffer'][0]['id']

    def test_block_vor_der_frage_satz_im_system_marke_im_verlauf(self):
        sid = self.sitzung([('text', 'Erst die Lease holen.'), ('text', 'Gern.')])
        ev = self.senden(sid, 'Wie hole ich die Lease im Testlabor?')
        msgs = self.modell.requests[0]['messages']
        self.assertIn(schleife.WISSEN_KOPF.strip(), msgs[0]['content'])
        self.assertIn(ausgabe.SYSTEM_WISSEN, msgs[0]['content'])
        letzte = msgs[-1]
        self.assertEqual(letzte['role'], 'user')
        self.assertIn('[' + self.kennung() + ']', letzte['content'], 'der Block steht in der Nachricht')
        self.assertTrue(letzte['content'].endswith('Wie hole ich die Lease im Testlabor?'), 'die Frage steht am Ende derselben Nachricht')
        self.assertEqual(sum(1 for m in msgs if m['role'] == 'user'), 1, 'kein zweiter user-Eintrag (Rollenwechsel bleibt)')
        ende = ev[-1][2]
        self.assertIn(self.kennung(), ende['wissen']['ids'])
        captain = [e for e in self.hub.harness.sitzungen.laden(sid)['eintraege'] if e['typ'] == 'captain'][0]
        self.assertIn(self.kennung(), captain['wissen']['ids'])
        self.assertNotIn('=== ', json.dumps(captain), 'der Block selbst wird nicht gespeichert (C)')
        self.senden(sid, 'Danke, und dann?')
        zweiter = self.modell.requests[1]['messages']
        frueher = [m for m in zweiter if m['role'] == 'user'][0]
        self.assertTrue(frueher['content'].startswith('[Wissen dazu: ' + self.kennung()), frueher['content'][:80])
        self.assertNotIn('Vor dem Laden die Lease', frueher['content'], 'im Verlauf nur die Marke, nicht der Text')

    def test_praefix_zwei_zuege_unterscheiden_sich_erst_bei_der_vorigen_frage(self):
        sid = self.sitzung([('text', 'A.'), ('text', 'B.'), ('text', 'C.')])
        for frage in ('Lease Testlabor holen?', 'Quartalszahlen Marketing Kampagne?', 'Und der Halter der Lease?'):
            self.senden(sid, frage)
        r = [req['messages'] for req in self.modell.requests]
        self.assertEqual(r[0][0], r[1][0], 'der Systemprompt ist mit und ohne Treffer gleich')
        self.assertEqual(r[1][0], r[2][0])
        for n in (0, 1):
            vorher, nachher = r[n], r[n + 1]
            self.assertEqual(nachher[:len(vorher) - 1], vorher[:-1], f'Zug {n + 2} beginnt wie Zug {n + 1} bis vor dessen Frage')

    def test_fremde_kennung_wird_markiert_und_auditiert(self):
        sid = self.sitzung([('text', 'Siehe [W0000000000].')])
        ende = self.senden(sid, 'Lease Testlabor holen?')[-1][2]
        self.assertEqual(ende['wissen']['fremd'], ['W0000000000'])
        self.assertTrue(any(p['ids'] == ['W0000000000'] for p in self.audit('WIS_ZITAT_FREMD')))

    def test_kennung_aus_dem_werkzeug_gilt(self):
        sid = self.sitzung([('calls', [('wissen_suchen', {'frage': 'Halter Lease'})]), ('text', 'PLATZHALTER')])
        kennung = self.kennung()
        self.modell.zuege[1] = ('text', f'Laut [{kennung}] erst die Lease holen.')
        code, _ = anfrage(self.url, 'PATCH', f'/api/harness/sitzungen/{sid}', {'wissen_zuerst': 'aus'})
        self.assertEqual(code, 200)
        ev = self.senden(sid, 'Was gilt für den Halter?')
        werkzeug = next(e[2] for e in ev if e[1] == 'werkzeug.ende')
        self.assertEqual((werkzeug['status'], werkzeug['stufe']), ('ok', 'frei'))
        self.assertIn(kennung, werkzeug['ergebnis'])
        ende = ev[-1][2]
        self.assertEqual((ende['wissen']['belegt'], ende['wissen']['fremd']), ([kennung], []))
        self.assertNotIn(ausgabe.SYSTEM_WISSEN, self.modell.requests[0]['messages'][0]['content'], 'Schalter aus: kein Satz')

    def test_schalter_aus_kein_satz_kein_block(self):
        sid = self.sitzung([('text', 'Ok.')])
        code, out = anfrage(self.url, 'PATCH', f'/api/harness/sitzungen/{sid}', {'wissen_zuerst': 'aus'})
        self.assertEqual((code, out.get('wissen_zuerst')), (200, 'aus'))
        ende = self.senden(sid, 'Lease Testlabor holen?')[-1][2]
        msgs = self.modell.requests[0]['messages']
        self.assertNotIn(schleife.WISSEN_KOPF.strip(), msgs[0]['content'])
        self.assertEqual(msgs[-1]['content'], 'Lease Testlabor holen?')
        self.assertNotIn('wissen', ende)
        code, out = anfrage(self.url, 'PATCH', f'/api/harness/sitzungen/{sid}', {'wissen_zuerst': 'vielleicht'})
        self.assertEqual(code, 400)

    def test_ohne_modell_die_trefferliste(self):
        sid = self.sitzung([])
        self.hub.harness.geladen = lambda: ([], None)
        code, out = anfrage(self.url, 'POST', f'/api/harness/sitzungen/{sid}/nachricht', {'text': 'Lease Testlabor holen?'})
        self.assertEqual((code, out['status']), (200, 'kein_modell'))
        self.assertIn('[' + self.kennung() + ']', out['wissen_antwort'])
        eintraege = self.hub.harness.sitzungen.laden(sid)['eintraege']
        self.assertEqual([e['typ'] for e in eintraege if e['typ'] in ('captain', 'wissen')], ['captain', 'wissen'])
        code, out = anfrage(self.url, 'POST', f'/api/harness/sitzungen/{sid}/nachricht', {'text': 'Quartalszahlen Marketing Kampagne'})
        self.assertNotIn('wissen_antwort', out, 'ohne Treffer bleibt es bei „Kein Modell“')


if __name__ == '__main__':
    unittest.main()
