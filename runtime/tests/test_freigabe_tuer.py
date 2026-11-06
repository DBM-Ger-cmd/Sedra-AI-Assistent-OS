"""G9 (SPEC_APPS_v1_O3PLUS_G9_G2 §2.7, §3.2) und G11-05: Freigaben der Klasse H aus der Seite warten auf ein Ja außerhalb des Browsers.

Ein echter Hub mit HTTP. Die Tür ist hier ausdrücklich an (in den übrigen Tests schaltet host_isolation sie ab). Was hinter der Tür
ausgeführt wird, zählt `ausgefuehrt`; der Systemdialog ist ein Fake."""
import json
import tempfile
import threading
import time
import unittest

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime import uix_clients, uix_server
from sedra_runtime.desk import systemdialog
from sedra_runtime.desk.bestaetigung import Bestaetigungen, BestaetigungFehler
from sedra_runtime.uix_server import make_server
from test_desk_kinds import FakeHost, audit_payloads, data, post

ECHT = uix_server.UIXHub._freigabe_ausserhalb          # beim Import: noch nicht von host_isolation ersetzt


def entscheidung(did, kind, ways, binding=None):
    return {'id': did, 'kind': kind, 'title': f'Titel {did}', 'describe': 'Beschreibung', 'mission_id': None, 'gate_id': None, 'risks': [],
            'rollback': True, 'note': '', 'created_at': None, 'ways': ways, 'apply': None, 'binding': binding or {}, 'agent_id': None}


class TuerHost(FakeHost):
    _freigabe_ausserhalb = ECHT

    def __init__(self, root, fixture):
        super().__init__(root, fixture)
        self.offen = [entscheidung('request:R1', 'request:switch', ['freigeben_und_anwenden', 'ablehnen'], {'section': 'x'}),
                      entscheidung('slot:1', 'slot_server', ['bestaetigen', 'ablehnen']),
                      entscheidung('gw:1', 'request:gateway', ['freigeben_und_anwenden', 'ablehnen'], {'weg': 'LOCAL_ONLY'})]
        self.ausgefuehrt = []

    def decisions_view(self):
        items = json.loads(json.dumps(self.offen))
        return {'items': items, 'summary': {'count': len(items)}}

    def _decide_jetzt(self, decision, did, way, payload):
        self.ausgefuehrt.append((did, way))
        self.offen = [d for d in self.offen if d['id'] != did]
        return {'status': 'answered', 'id': did, 'way': way}

    def approve_gate(self, payload):
        self.ausgefuehrt.append(('approve_gate', payload.get('gate_id')))
        return {'approved': True}

    def cloud_key(self, payload):
        self.ausgefuehrt.append(('cloud_key', payload.get('provider')))
        return {'gespeichert': True}


class Tuer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='freigabe-tuer-')
        self.addCleanup(self.tmp.cleanup)
        self.hub = TuerHost(self.tmp.name, data())
        self.addCleanup(self.hub.close)
        self.server, self.url = make_server(self.hub)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = self.url.split('#')[0]
        systemdialog.setzen(lambda titel, text: None)        # kein Dialog möglich: nur die Konsole
        self.addCleanup(systemdialog.setzen, None)

    def antworten(self, did, way):
        return post(self.url, '/api/decisions/answer', {'id': did, 'way': way})

    def als(self, client, path, body):
        info = uix_clients.read(self.hub.project_root, client)
        return post(self.base + '#' + info['token'], path, body)

    def bid(self):
        offen = self.hub.bestaetigungen.offen()
        self.assertEqual(len(offen), 1)
        return offen[0]['bid']

    # ---- G9-02 / G11-05: Klasse H über die Seite erteilt nichts
    def test_klasse_h_aus_der_seite_wartet(self):
        status, out = self.antworten('request:R1', 'freigeben_und_anwenden')
        self.assertEqual(status, 400)
        self.assertTrue(out['code'].startswith('wartet_auf_bestaetigung'), out)
        self.assertIn('FREIGABE.bat freigeben B-', out['message'])
        self.assertEqual(self.hub.ausgefuehrt, [])
        self.assertEqual(len(audit_payloads(self.hub, 'FREIGABE_WARTET')), 1)

    def test_klasse_n_und_ablehnen_gehen_sofort(self):
        self.assertEqual(self.antworten('slot:1', 'bestaetigen')[0], 200)
        self.assertEqual(self.antworten('gw:1', 'freigeben_und_anwenden')[0], 200)        # GateWay nur lokal = N
        self.assertEqual(self.antworten('request:R1', 'ablehnen')[0], 200)
        self.assertEqual(self.hub.ausgefuehrt, [('slot:1', 'bestaetigen'), ('gw:1', 'freigeben_und_anwenden'), ('request:R1', 'ablehnen')])
        erteilt = audit_payloads(self.hub, 'FREIGABE_ERTEILT')
        self.assertEqual([(e['art'], e['klasse'], e['kanal']) for e in erteilt], [('slot_server', 'N', 'seite'), ('request:gateway', 'N', 'seite')])

    # ---- G9-07/08: Konsole
    def test_konsole_bestaetigt_genau_einmal(self):
        self.antworten('request:R1', 'freigeben_und_anwenden')
        status, out = self.als('cli', '/api/freigabe/offen', {})
        self.assertEqual(status, 200)
        self.assertIn('Klasse H', out['offen'][0]['text'])
        bid = out['offen'][0]['bid']
        status, out = self.als('cli', '/api/freigabe/bestaetigen', {'id': bid, 'antwort': 'ja'})
        self.assertEqual((status, out['status']), (200, 'bestaetigt'))
        self.assertEqual(self.hub.ausgefuehrt, [('request:R1', 'freigeben_und_anwenden')])
        e = audit_payloads(self.hub, 'FREIGABE_ERTEILT')[-1]
        self.assertEqual((e['klasse'], e['kanal'], e['bestaetigung']), ('H', 'konsole', bid))
        self.assertEqual(self.als('cli', '/api/freigabe/bestaetigen', {'id': bid, 'antwort': 'ja'})[0], 400)    # schon verbraucht
        self.assertEqual(len(self.hub.ausgefuehrt), 1)

    def test_konsole_nein_laesst_die_entscheidung_offen(self):
        self.antworten('request:R1', 'freigeben_und_anwenden')
        out = self.als('cli', '/api/freigabe/bestaetigen', {'id': self.bid(), 'antwort': 'nein'})[1]
        self.assertEqual(out['status'], 'abgelehnt')
        self.assertEqual(self.hub.ausgefuehrt, [])
        self.assertIn('request:R1', [d['id'] for d in self.hub.offen])

    def test_seite_und_mcp_erreichen_die_bestaetigung_nicht(self):
        self.antworten('request:R1', 'freigeben_und_anwenden')
        bid = self.bid()
        self.assertEqual(post(self.url, '/api/freigabe/bestaetigen', {'id': bid, 'antwort': 'ja'})[0], 403)
        self.assertEqual(post(self.url, '/api/freigabe/offen', {})[0], 403)
        self.assertEqual(self.als('mcp', '/api/freigabe/bestaetigen', {'id': bid, 'antwort': 'ja'})[0], 403)
        self.assertEqual(self.hub.ausgefuehrt, [])

    def test_konsolen_modul(self):
        from sedra_runtime.desk import freigabe_konsole
        self.assertEqual(freigabe_konsole.ausfuehren(self.hub.project_root, 'liste'), (0, 'Keine Freigabe wartet auf deine Bestätigung.'))
        self.antworten('request:R1', 'freigeben_und_anwenden')
        code, text = freigabe_konsole.ausfuehren(self.hub.project_root, 'liste')
        self.assertEqual(code, 0)
        self.assertIn('Titel request:R1', text)
        code, text = freigabe_konsole.ausfuehren(self.hub.project_root, 'freigeben', self.bid())
        self.assertEqual(code, 0, text)
        self.assertEqual(self.hub.ausgefuehrt, [('request:R1', 'freigeben_und_anwenden')])

    # ---- G9-04: Bindung
    def test_hinfaellig_wenn_die_entscheidung_weg_ist(self):
        self.antworten('request:R1', 'freigeben_und_anwenden')
        bid = self.bid()
        self.hub.offen = [d for d in self.hub.offen if d['id'] != 'request:R1']             # inzwischen anders beantwortet
        status, out = self.als('cli', '/api/freigabe/bestaetigen', {'id': bid, 'antwort': 'ja'})
        self.assertEqual((status, out['code']), (400, 'bestaetigung_hinfaellig'))
        self.assertEqual(self.hub.ausgefuehrt, [])

    def test_geaenderte_bindung_ist_hinfaellig(self):
        self.antworten('request:R1', 'freigeben_und_anwenden')
        bid = self.bid()
        self.hub.offen[0]['binding'] = {'section': 'anders'}
        self.assertEqual(self.als('cli', '/api/freigabe/bestaetigen', {'id': bid, 'antwort': 'ja'})[1]['code'], 'bestaetigung_hinfaellig')
        self.assertEqual(self.hub.ausgefuehrt, [])

    # ---- G9-05: Systemdialog
    def test_systemdialog_ja_fuehrt_aus(self):
        gesehen = []
        fertig = threading.Event()

        def dialog(titel, text):
            gesehen.append(text)
            return True
        systemdialog.setzen(dialog)
        alt = self.hub.freigabe_bestaetigen

        def bestaetigen(*a, **k):
            try:
                return alt(*a, **k)
            finally:
                fertig.set()
        self.hub.freigabe_bestaetigen = bestaetigen
        status, out = self.antworten('request:R1', 'freigeben_und_anwenden')
        self.assertEqual(status, 400)
        self.assertNotIn('hier nicht verfügbar', out['message'])
        self.assertTrue(fertig.wait(10))
        self.assertEqual(self.hub.ausgefuehrt, [('request:R1', 'freigeben_und_anwenden')])
        self.assertIn('Titel request:R1', gesehen[0])
        self.assertEqual(audit_payloads(self.hub, 'FREIGABE_ERTEILT')[-1]['kanal'], 'systemdialog')

    def test_systemdialog_nein(self):
        fertig = threading.Event()
        systemdialog.setzen(lambda t, x: (fertig.set(), False)[1])
        self.antworten('request:R1', 'freigeben_und_anwenden')
        self.assertTrue(fertig.wait(10))
        for _ in range(50):
            if not self.hub.bestaetigungen.offen():
                break
            time.sleep(0.05)
        self.assertEqual(self.hub.bestaetigungen.offen(), [])
        self.assertEqual(self.hub.ausgefuehrt, [])

    # ---- F2 und N6: Routen der Seite hinter der Tür
    def test_mission_approve_und_cloud_key_warten(self):
        mid = data()['missions'][0]['identity']['mission_id'] if data().get('missions') else 'M-1'
        status, out = post(self.url, '/api/mission/approve', {'mission_id': mid, 'gate_id': 'G-1'})
        self.assertEqual(status, 400)
        self.assertTrue(out['code'].startswith('wartet_auf_bestaetigung'))
        status, out = post(self.url, '/api/cloud/key', {'provider': 'x', 'key': 'geheim'})
        self.assertTrue(out['code'].startswith('wartet_auf_bestaetigung'))
        self.assertEqual(self.hub.ausgefuehrt, [])
        texte = ' '.join(b['text'] for b in self.hub.bestaetigungen.offen())
        self.assertNotIn('geheim', texte)                                  # der Schlüssel steht nie im Text
        self.assertNotIn('geheim', self.hub.runtime.audit.path.read_text(encoding='utf-8'))

    # ---- G9-11: Schalter
    def test_schalter_aus(self):
        self.hub.runtime.switches.values['freigabe_ausserhalb'] = {'enabled': False}
        self.assertEqual(self.antworten('request:R1', 'freigeben_und_anwenden')[0], 200)
        self.assertEqual(self.hub.ausgefuehrt, [('request:R1', 'freigeben_und_anwenden')])
        self.assertEqual(len(audit_payloads(self.hub, 'FREIGABE_KLASSE_H_AUS_DER_SEITE')), 1)


class Frist(unittest.TestCase):
    def test_nach_zehn_minuten_abgelaufen(self):
        jetzt = [0.0]
        b = Bestaetigungen(uhr=lambda: jetzt[0])
        bid = b.anlegen(art='gate', id='g', weg='einmal', binding={}, text='t', ausfuehren=lambda: 1)
        jetzt[0] = 601
        with self.assertRaises(BestaetigungFehler):
            b.nehmen(bid)
        self.assertEqual(b.offen(), [])

    def test_neue_antwort_ersetzt_die_alte(self):
        b = Bestaetigungen()
        b.anlegen(art='gate', id='g', weg='einmal', binding={}, text='t', ausfuehren=lambda: 1)
        b.anlegen(art='gate', id='g', weg='einmal', binding={}, text='t', ausfuehren=lambda: 2)
        self.assertEqual(len(b.offen()), 1)


if __name__ == '__main__':
    unittest.main()
