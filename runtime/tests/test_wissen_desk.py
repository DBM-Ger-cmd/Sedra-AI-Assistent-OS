"""`wissen/desk_wissen.py` am echten Hub (Spec 7, D7.7 bis D7.9; WIS-02, WIS-10, WIS-13): die Typen gibt es nur mit Schalter
`wissen`; eine Quelle entsteht nur über einen Antrag (`gated`), ohne Freigabe bleibt der Speicher leer; der Leser kommt vom Server;
ein Vorschlag wird Antrag → Freigabe legt genau einen Abschnitt an, Ablehnung keinen, ein geänderter Vorschlag ist `binding_stale`;
der Takt läuft unter `takt.lock`. Ohne Embedding-Server (kein Modell): Modus volltext."""
import json
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.desk import gated
from guppi_runtime.uix_server import UIXHub
from guppi_runtime.wissen import desk_wissen
from guppi_runtime.wissen import speicher as S

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
NOTIZ = "# Werkbank\n\n## Lease\n\nVor dem Laden die Lease des Testlabors holen.\n\n## Vertraulich\n\nDie Steuernummer liegt im Ordner Finanzen.\n"


def switch_on(project, wissen=True):
    (Path(project) / 'local_config').mkdir(parents=True, exist_ok=True)
    (Path(project) / 'local_config' / 'switches.yaml').write_text('switches:\n  wissen: {enabled: %s}\n' % ('true' if wissen else 'false'), encoding='utf-8')


class Basis(unittest.TestCase):
    wissen_an = True

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='wissen-desk-')
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name) / 'project'
        switch_on(self.project, self.wissen_an)
        (self.project / 'notizen').mkdir(parents=True)
        (self.project / 'notizen' / 'werkbank.md').write_text(NOTIZ, encoding='utf-8')
        self.hub = UIXHub(self.project, ARCH)
        self.addCleanup(self.hub.close)
        self.sp = self.hub.runtime.wissen

    def act(self, kind, oid, verb, **args):
        body = {'type': kind, 'verb': verb, 'args': args}
        if oid:
            body['id'] = oid
        return self.hub.act(body)['result']

    def objects(self, **body):
        return self.hub.objects_view(body)

    def decide(self, out, way='freigeben_und_anwenden'):
        return self.hub.decide({'id': out['decision_id'], 'way': way})['result']

    def audit(self, event):
        lines = self.hub.runtime.audit.path.read_text(encoding='utf-8').splitlines()
        return [e['payload'] for e in map(json.loads, filter(str.strip, lines)) if e['event_type'] == event]

    def beantrage(self, pfad='notizen/werkbank.md', **more):
        return self.act('wissen', None, 'quelle_beantragen', adapter='markdown', wurzel='projekt', pfad=pfad, stufe=more.pop('stufe', 1), **more)


class SchalterAus(Basis):
    wissen_an = False

    def test_ohne_schalter_nur_platzhalter_die_aus_sagen(self):
        self.assertIsNone(self.sp)
        self.assertEqual(self.hub.runtime.boot()['wissen'], {'enabled': False, 'error': None})
        self.assertTrue(self.hub.kinds.get('wissen').placeholder)
        obj = self.objects(type='wissen', id='speicher')
        self.assertEqual((obj['state'], obj['stand'], obj['actions']), ('aus', None, []))
        self.assertIn('ausgeschaltet', obj['summary'])
        liste = self.objects(type='wissen')
        self.assertEqual((len(liste['items']), liste['quelle']['zustand'], liste.get('actions')), (1, 'aus', None))
        self.assertEqual(self.objects(type='wissen_quelle')['items'], [])
        with self.assertRaisesRegex(ValueError, 'id_required'):
            self.act('wissen', None, 'suche', frage='x')
        self.assertEqual(self.hub.kinds.problems, [])


class KaputteKonfiguration(unittest.TestCase):
    def test_kaputte_konfiguration_schaltet_ab_und_sagt_warum(self):
        tmp = tempfile.TemporaryDirectory(prefix='wissen-desk-kaputt-')
        self.addCleanup(tmp.cleanup)
        project = Path(tmp.name) / 'project'
        switch_on(project)
        (project / 'local_config' / 'wissen.yaml').write_text('wissen: {engine: 7}\n', encoding='utf-8')
        hub = UIXHub(project, ARCH)
        self.addCleanup(hub.close)
        self.assertIsNone(hub.runtime.wissen)
        self.assertEqual(hub.runtime.wissen_error, 'wissen_config_invalid:engine')
        self.assertEqual(hub.runtime.boot()['wissen'], {'enabled': False, 'error': 'wissen_config_invalid:engine'})
        self.assertEqual(hub.objects_view({'type': 'wissen', 'id': 'speicher'})['grund'], 'wissen_config_invalid:engine')
        events = [json.loads(l)['event_type'] for l in hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
        self.assertIn('WISSEN_OFF', events)


class Typen(Basis):
    def test_die_drei_typen_mit_der_form_und_dem_stand(self):
        self.assertIsNotNone(self.sp)
        self.assertEqual(self.hub.kinds.problems, [])
        for name in desk_wissen.TYPES:
            self.assertEqual(self.hub.kinds.get(name).source, 'wissen', name)
        liste = self.objects(type='wissen')
        self.assertEqual([i['id'] for i in liste['items']], ['speicher'])
        self.assertEqual(liste['quelle']['zustand'], 'bereit')
        self.assertEqual({v['verb'] for v in liste['actions']} >= {'suche', 'nachfuehren', 'quelle_beantragen', 'erstbestueckung'}, True)
        obj = self.objects(type='wissen', id='speicher')
        self.assertTrue({'type', 'id', 'title', 'state', 'summary', 'actions', 'links'} <= set(obj))
        self.assertEqual((obj['state'], obj['stand']['modus'], obj['stand']['bereit'], obj['stand']['grund']), ('volltext', 'volltext', False, 'wis_engine_fehlt'))
        boot = self.hub.runtime.boot()['wissen']
        self.assertEqual((boot['enabled'], boot['error'], boot['modus']), (True, None, 'volltext'))

    def test_der_speicher_liegt_unter_local_config_wissen(self):
        self.assertEqual(self.sp.pfad, self.project / 'local_config' / 'wissen' / 'wissen.sqlite')
        self.assertTrue(self.sp.pfad.is_file())


class Quellen(Basis):
    def test_quelle_nur_ueber_antrag_ohne_freigabe_leer(self):
        out = self.beantrage()
        self.assertEqual((out['status'], out['text']), ('beantragt', desk_wissen.ANTRAG))
        self.assertEqual(self.sp.quellen(), [], 'ohne Freigabe keine Zeile')
        self.assertEqual(self.objects(type='wissen_quelle')['items'], [])
        d = next(d for d in self.hub.decisions_view()['items'] if d['id'] == out['decision_id'])
        self.assertEqual((d['kind'], d['title']), ('request:wissen_quelle', 'Wissensquelle freigeben: projekt/notizen/werkbank.md (markdown, Stufe 1)'))
        self.assertIn('ohne Freigabe wird nichts aufgenommen', d['describe'])
        self.assertEqual(self.decide(out, 'ablehnen')['status'], 'rejected')
        self.assertEqual(self.sp.db.execute('SELECT count(*) FROM abschnitte').fetchone()[0], 0, 'WIS-02')
        out = self.beantrage()
        res = self.decide(out)
        self.assertEqual(res['status'], 'applied')
        q = self.objects(type='wissen_quelle')['items']
        self.assertEqual((len(q), q[0]['abschnitte'], q[0]['stufe'], q[0]['state']), (1, 2, 1, 'aktiv'))
        m = self.hub.runtime.missions.load(out['decision_id'][len('request:'):])
        self.assertEqual((q[0]['freigabe_gate'], self.sp.quelle(q[0]['id'])['freigabe_mission']), (m['human_gates']['resolved'][0]['gate_id'], m['identity']['mission_id']))
        self.assertEqual(self.audit('WIS_QUELLE_AUFGENOMMEN')[0]['quelle'], q[0]['id'])
        self.assertEqual([v['verb'] for v in q[0]['actions']], ['abschalten', 'stufe_heraufsetzen', 'neu_beantragen'])

    def test_falsche_pfade_werden_vor_dem_antrag_abgewiesen(self):
        out = self.beantrage(pfad='/etc/passwd')
        self.assertEqual((out['status'], out['code']), ('fehler', 'wis_pfad_absolut'))
        self.assertIn('relativ', out['satz'])
        self.assertEqual(self.beantrage(pfad='../x')['code'], 'wis_pfad_ausserhalb')
        self.assertEqual(self.act('wissen', None, 'quelle_beantragen', adapter='markdown', wurzel='projekt', pfad='notizen', stufe='sieben')['code'], 'wis_stufe_ungueltig')
        self.assertEqual(self.hub.decisions_view()['items'], [])

    def test_enger_ohne_gate_weiter_mit_antrag(self):
        self.decide(self.beantrage())
        qid = self.sp.quellen()[0]['id']
        self.assertEqual(self.act('wissen_quelle', qid, 'stufe_heraufsetzen', stufe=3)['quelle']['stufe'], 3)
        out = self.act('wissen_quelle', qid, 'neu_beantragen', stufe=1)
        self.assertEqual(out['status'], 'beantragt')
        self.assertEqual(self.sp.quelle(qid)['stufe'], 3, 'bis zur Freigabe bleibt es eng')
        self.decide(out)
        self.assertEqual(self.sp.quelle(qid)['stufe'], 1)
        self.assertEqual(self.act('wissen_quelle', qid, 'abschalten')['quelle']['state'], 'aus')
        self.assertEqual(self.objects(type='wissen_quelle', id=qid)['actions'], [{'verb': 'neu_beantragen', 'label': 'Neu beantragen', 'needs_gate': True, 'confirm': None}])

    def test_erstbestueckung_ist_ein_antrag_mit_einem_gate_je_quelle(self):
        out = self.act('wissen', None, 'erstbestueckung')
        self.assertEqual(out['status'], 'beantragt')
        m = self.hub.runtime.missions.load(out['decision_id'][len('request:'):])
        gates = m['human_gates']['pending']
        self.assertEqual(len(gates), out['quellen'])
        self.assertGreaterEqual(out['quellen'], 2, 'Doku und Logbuch des Repos sind da')
        self.assertTrue(all(g['request']['exact_action'] == 'wissen_quelle_freigeben' for g in gates))
        self.assertEqual(len({g['request']['request_digest'] for g in gates}), 1, 'eine Bindung für alle Gates (G2-S7-m)')
        self.assertEqual(self.sp.quellen(), [])


class Suche(Basis):
    def setUp(self):
        super().setUp()
        self.decide(self.beantrage())

    def test_suche_ueber_actions_mit_captain_als_leser(self):
        out = self.act('wissen', None, 'suche', frage='Lease des Testlabors')
        self.assertEqual((out['status'], out['modus']), ('erledigt', 'volltext'))
        self.assertEqual(out['treffer'][0]['stelle'], 'Werkbank > Lease')
        self.assertTrue(out['hinweis'].startswith('Nur Volltextsuche (wis_engine_fehlt)'))
        su = self.audit('WIS_SUCHE')[-1]
        self.assertEqual((su['leser_art'], su['stufe']), ('captain', 6))
        self.assertEqual(self.act('wissen', None, 'suche', frage='Lease', leser={'art': 'agent'})['code'], 'wis_leser_vom_server')
        self.assertEqual(self.act('wissen', None, 'suche', frage='Lease', stufe=1)['code'], 'wis_leser_vom_server')
        self.assertEqual(self.act('wissen', None, 'suche', frage='')['code'], 'wis_anfrage_leer')
        self.assertEqual(self.audit('UIX_ACTION')[-1]['verb'], 'suche')

    def test_nachfuehren_ohne_gate(self):
        out = self.act('wissen', None, 'nachfuehren')
        self.assertEqual(out['status'], 'erledigt')
        self.assertEqual(out['abgleich']['uebersprungen'], 1)
        self.assertEqual(out['einbetten']['ende'], 'fehler')


class Vorschlaege(Basis):
    def setUp(self):
        super().setUp()
        self.decide(self.beantrage())
        self.block = {r[0] for r in self.sp.db.execute('SELECT id FROM abschnitte')}
        self.leser = S.leser('agent', 1, None, 'A-3')

    def vorschlag(self, titel='Lease zuerst', text='Vor jedem Laden die Lease holen.', belege=None):
        return self.sp.vorschlagen(titel=titel, text=text, belege=belege if belege is not None else list(self.block)[:1], agent_id='A-3', lauf_id='J-1',
                                   aufgabe_id='I-1', block_ids=self.block, leser=self.leser)

    def test_vorschlag_wird_antrag_freigabe_legt_genau_einen_abschnitt_an(self):
        v = self.vorschlag()
        self.assertTrue(v['mission_id'])
        d = next(d for d in self.hub.decisions_view()['items'] if d['id'] == 'request:' + v['mission_id'])
        self.assertEqual((d['kind'], d['title']), ('request:wissen_vorschlag', 'Wissen aufnehmen: Lease zuerst'))
        req = self.hub.runtime.missions.load(v['mission_id'])['context'][gated.CONTEXT]
        self.assertEqual((req['binding']['vorschlag_id'], req['binding']['hash'], req['binding']['stufe']), (v['id'], v['hash'], 1))
        self.assertEqual(self.objects(type='wissen_vorschlag')['items'][0]['state'], 'offen')
        self.assertEqual(self.sp.db.execute("SELECT count(*) FROM abschnitte WHERE datei LIKE 'vorschlag:%'").fetchone()[0], 0, 'ohne Freigabe kein Eintrag')
        res = self.hub.decide({'id': d['id'], 'way': 'freigeben_und_anwenden'})['result']
        self.assertEqual(res['status'], 'applied')
        rows = self.sp.db.execute("SELECT a.datei, a.stelle, q.id, q.adapter, q.stufe FROM abschnitte a JOIN quellen q ON q.id = a.quelle WHERE a.datei LIKE 'vorschlag:%'").fetchall()
        self.assertEqual([tuple(r) for r in rows], [('vorschlag:' + v['id'], 'Vorschlag Lease zuerst', 'Q-VS-1-alle-0', 'vorschlag', 1)])
        self.assertEqual(self.sp.vorschlag(v['id'])['status'], 'freigegeben')
        jsonl = (self.project / 'local_config' / 'wissen' / 'vorschlaege.jsonl').read_text(encoding='utf-8').splitlines()
        self.assertEqual(json.loads(jsonl[0])['id'], v['id'])
        self.assertEqual(self.audit('WIS_VORSCHLAG_AUFGENOMMEN')[0]['id'], v['id'])
        self.assertIn('Vorschlag Lease zuerst', [t['stelle'] for t in self.act('wissen', None, 'suche', frage='Lease holen Laden')['treffer']])
        vo = self.objects(type='wissen_vorschlag', id=v['id'])
        self.assertEqual([a['verb'] for a in vo['actions']], ['zuruecknehmen'])
        self.assertEqual(self.act('wissen_vorschlag', v['id'], 'zuruecknehmen')['status'], 'veraltet')
        self.assertEqual(self.sp.db.execute("SELECT count(*) FROM abschnitte WHERE datei LIKE 'vorschlag:%'").fetchone()[0], 0)

    def test_ablehnung_legt_nichts_an(self):
        v = self.vorschlag()
        res = self.hub.decide({'id': 'request:' + v['mission_id'], 'way': 'ablehnen'})['result']
        self.assertEqual((res['status'], res['result']['status']), ('rejected', 'abgelehnt'))
        self.assertEqual(self.sp.vorschlag(v['id'])['status'], 'abgelehnt')
        self.assertEqual(self.sp.db.execute("SELECT count(*) FROM abschnitte WHERE datei LIKE 'vorschlag:%'").fetchone()[0], 0, 'WIS-10')
        self.assertEqual(self.audit('WIS_VORSCHLAG_ABGELEHNT'), [{'id': v['id']}])

    def test_geaenderter_vorschlag_ist_binding_stale(self):
        v = self.vorschlag()
        self.sp.db.execute("UPDATE vorschlaege SET text = 'anders', hash = 'h-anders' WHERE id = ?", (v['id'],))
        res = self.hub.decide({'id': 'request:' + v['mission_id'], 'way': 'freigeben_und_anwenden'})['result']
        self.assertEqual(res['status'], gated.STALE)
        self.assertEqual(self.sp.db.execute("SELECT count(*) FROM abschnitte WHERE datei LIKE 'vorschlag:%'").fetchone()[0], 0)
        self.assertEqual(self.sp.vorschlag(v['id'])['status'], 'offen')

    def test_regeln_des_vorschlags(self):
        with self.assertRaisesRegex(ValueError, 'wis_beleg_fremd'):
            self.vorschlag(belege=['W0000000000'])
        with self.assertRaisesRegex(ValueError, 'wis_vorschlag_leer'):
            self.vorschlag(titel=' ')
        with self.assertRaisesRegex(ValueError, 'wis_vorschlag_zu_lang'):
            self.vorschlag(text='x' * 4001)
        with self.assertRaisesRegex(ValueError, 'wis_vorschlag_gesperrt'):
            self.vorschlag(text='Karte 4111 1111 1111 1111 CVV 123')
        self.sp.konfig.offene_je_agent = 1
        self.vorschlag()
        with self.assertRaisesRegex(ValueError, 'wis_vorschlaege_zu_viele'):
            self.vorschlag(titel='Noch einer')
        with self.assertRaisesRegex(ValueError, 'wis_vorschlag_unbekannt'):
            self.sp.vorschlag_ablehnen('WV-fehlt')

    def test_personenbezug_wird_von_den_belegen_geerbt(self):
        qid = self.sp.quellen()[0]['id']
        self.sp.db.execute('UPDATE quellen SET personenbezug = 1 WHERE id = ?', (qid,))
        v = self.vorschlag()
        self.assertEqual(v['personenbezug'], 1)
        self.assertEqual(self.audit('WIS_VORSCHLAG_NEU')[0]['personenbezug'], 1)


class Takt(Basis):
    def test_der_takt_laeuft_unter_der_sperre_und_ein_zweiter_nicht(self):
        from guppi_runtime.wissen import aufnahme
        thread = self.hub.start_extensions()
        self.assertIn('guppi_runtime.wissen.desk_wissen', thread)
        self.assertTrue(self.sp.takt_thread.is_alive())
        self.assertTrue((self.project / 'local_config' / 'wissen' / 'takt.lock').exists())
        with self.assertRaisesRegex(ValueError, 'wis_takt_busy'):
            aufnahme.start(self.sp, self.project / 'local_config' / 'wissen' / 'takt.lock', 600)
        self.assertEqual(self.objects(type='wissen')['quelle']['takt'], {'laeuft': True})
        self.hub.close()
        self.assertFalse(self.sp.takt_thread.is_alive())

    def test_ohne_takt_schalter_kein_thread(self):
        self.sp.konfig.takt_an = False
        self.assertIsNone(desk_wissen.start(self.hub))


if __name__ == '__main__':
    unittest.main()
