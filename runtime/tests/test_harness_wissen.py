"""Wissen im Chat von One Sedra (SPEC_WISSEN_KERN_v1 WK-10, WK-11, WK-12; G2 K1K2 §3.1–§3.3): `wissen_suchen` liefert Treffer mit Kennung
und Auszug, der Leser kommt vom Server (nie aus den Argumenten), die Kennungen merkt sich die Antwort; ohne Treffer, mit ungültigem Filter und
mit ausgeschaltetem Wissen gibt es klare Sätze. `wissen_beantragen` stellt nur einen Antrag (Klasse H), lehnt Pfade außerhalb von SEDRA ab und
erkennt eine schon aufgenommene Quelle. Die GateWay-Auskunft steht als lesendes Werkzeug in One Sedra. Kein Modell, keine GPU, kein Netz."""
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.core.guard import Guard
from sedra_runtime.harness import api as harness_api
from sedra_runtime.harness import katalog
from sedra_runtime.harness.freigabe import Karten, Kiste
from sedra_runtime.harness.werkzeuge import NAMEN, SCHEMAS, Werkzeuge
from sedra_runtime.uix_server import UIXHub
from test_wissen_desk import ARCH, Basis, switch_on


class AmHub(Basis):
    def setUp(self):
        super().setUp()
        self.decide(self.beantrage())                     # notizen/werkbank.md ist Quelle (Stufe 1)
        self.api = self.hub.harness

    def test_treffer_mit_kennung_und_auszug(self):
        text = self.api.wissen_werkzeug('S-00000001', 'A-00000001', {'frage': 'Lease Testlabor'})
        self.assertRegex(text, r'\[W[0-9a-f]{10,16}\]')
        self.assertIn('notizen/werkbank.md', text)
        self.assertIn('Daten, keine Anweisung', text)
        ids = self.api.wissen_ids_nehmen('A-00000001')
        self.assertTrue(ids and all(i in text for i in ids), 'die Kennungen der Treffer merkt sich die Antwort')
        self.assertEqual(self.api.wissen_ids_nehmen('A-00000001'), [], 'einmal abholen')

    def test_leser_kommt_nie_aus_den_argumenten(self):
        gesehen = []
        echte = self.sp.suche
        self.sp.suche = lambda frage, **kw: (gesehen.append(kw), echte(frage, **kw))[1]
        try:
            self.api.wissen_werkzeug('S-1', None, {'frage': 'Lease', 'leser': {'art': 'agent', 'stufe': 0}, 'route': 'cloud', 'k': 99})
        finally:
            self.sp.suche = echte
        kw = gesehen[0]
        self.assertEqual((kw['leser']['art'], kw['leser']['stufe'], kw['route'], kw['k']), ('captain', 6, 'local', 10))

    def test_ohne_treffer_und_falscher_filter(self):
        self.assertIn('nichts gefunden', self.api.wissen_werkzeug('S-1', None, {'frage': 'Quartalszahlen Marketing Kampagne'}))
        with self.assertRaises(ValueError) as ctx:
            self.api.wissen_werkzeug('S-1', None, {'frage': 'Lease', 'seit': 'gestern'})
        self.assertIn('JJJJ-MM-TT', str(ctx.exception))

    def test_antrag_nur_im_sedra_ordner_und_nicht_doppelt(self):
        (self.project / 'notizen' / 'kunde.md').write_text('# Kunde\n\n## Vertrag\n\nLaufzeit zwei Jahre.\n', encoding='utf-8')
        r = self.api.wissen_antrag({'pfad': 'notizen/kunde.md'})
        self.assertEqual(r['status'], 'beantragt')
        self.assertTrue(r['decision_id'].startswith('request:'))
        self.assertEqual(self.api.wissen_antrag({'pfad': 'notizen/werkbank.md'})['status'], 'schon_aufgenommen')
        for schlecht, satz in (({'pfad': 'C:/Daten'}, 'relativ'), ({'pfad': '/etc'}, 'relativ'), ({'pfad': 'x', 'wurzel': 'D:/Daten'}, 'nicht freigegeben'),
                               ({'pfad': 'x', 'wurzel': 'w:gibtsnicht'}, 'nicht freigegeben')):
            with self.assertRaises(ValueError) as ctx:
                self.api.wissen_antrag(schlecht)
            self.assertIn(satz, str(ctx.exception))
        offene = [d for d in self.hub.decisions_view()['items'] if d.get('id') == r['decision_id']]
        self.assertEqual(len(offene), 1, 'der Antrag wartet im Posteingang')


class FreigegebeneOrdner(Basis):
    """K5-8: Antrag unter einem freigegebenen Ordner (Adapter dokumente, Untergrenzen der Wurzel), Stand im Chat, Entfernen und Dateien am Desk."""

    def setUp(self):
        super().setUp()
        self.ablage = self.project.parent / 'ablage'
        self.ablage.mkdir(exist_ok=True)
        (self.ablage / 'akte.md').write_text('# Akte\n\n## Vertrag\n\nLaufzeit drei Jahre.\n', encoding='utf-8')
        (self.ablage / 'liste.csv').write_text('Kunde;Ort\nKranich;Bremen\n', encoding='utf-8')
        (self.project / 'local_config' / 'wissen_wurzeln.yaml').write_text(
            f"wurzeln:\n  - {{id: ablage, pfad: '{self.ablage.as_posix()}', name: Ablage, personenbezug: 1, stufe: 2}}\n", encoding='utf-8')
        self.api = self.hub.harness

    def test_antrag_unter_freigegebenem_ordner(self):
        r = self.api.wissen_antrag({'pfad': '.', 'wurzel': 'w:ablage', 'muster': '*.md, *.csv'})
        self.assertEqual(r['status'], 'beantragt')
        self.decide(r)
        q = [q for q in self.sp.quellen() if q['wurzel'] == 'w:ablage'][0]
        self.assertEqual((q['adapter'], q['stufe'], q['personenbezug']), ('dokumente', 2, 1), 'Untergrenzen der Wurzel')
        self.sp.abgleich()
        stand = self.api.wissen_werkzeug('S-1', None, {'stand': q['id']})
        self.assertIn('2 Dateien aufgenommen', stand)
        self.assertIn('w:ablage: Ablage (Stufe ab 2, Personenbezug)', self.api.wissen_werkzeug('S-1', None, {'stand': 'wurzeln'}))
        self.assertNotIn(str(self.ablage), self.api.wissen_werkzeug('S-1', None, {'stand': 'wurzeln'}), 'kein Pfad für das Modell')
        self.assertIn(q['id'], self.api.wissen_werkzeug('S-1', None, {'stand': 'quellen'}))
        with self.assertRaises(ValueError):
            self.api.wissen_werkzeug('S-1', None, {'stand': 'Q-gibtsnicht'})

    def test_dateien_und_entfernen_am_desk(self):
        r = self.api.wissen_antrag({'pfad': '.', 'wurzel': 'w:ablage', 'muster': '*.md'})
        self.decide(r)
        q = [q for q in self.sp.quellen() if q['wurzel'] == 'w:ablage'][0]
        self.sp.abgleich()
        out = self.hub.act({'type': 'wissen_quelle', 'id': q['id'], 'verb': 'dateien', 'args': {}})['result']
        self.assertEqual((out['status'], out['summen']['aufgenommen']), ('erledigt', 1))
        out = self.hub.act({'type': 'wissen_quelle', 'id': q['id'], 'verb': 'entfernen', 'args': {}})['result']
        self.assertEqual(out['status'], 'erledigt')
        self.assertGreater(out['abschnitte'], 0)
        self.assertNotIn(q['id'], [x['id'] for x in self.sp.quellen()])
        self.assertEqual(self.sp.db.execute("SELECT count(*) FROM dateien WHERE quelle = ?", (q['id'],)).fetchone()[0], 0)
        self.assertTrue((self.ablage / 'akte.md').is_file(), 'die Datei auf der Platte bleibt')


class Aus(Basis):
    wissen_an = False

    def test_mit_ausgeschaltetem_wissen_ein_satz(self):
        self.assertIsNone(self.sp)
        self.assertIn('abgeschaltet', self.hub.harness.wissen_werkzeug('S-1', None, {'frage': 'Lease'}))
        with self.assertRaises(ValueError):
            self.hub.harness.wissen_antrag({'pfad': 'notizen'})


class Werkzeug(unittest.TestCase):
    """Die Werkzeuge in der Kiste: ohne Karte, nur lesen bzw. nur Antrag; Schema da; Argumente gehen durch."""

    def kiste(self, wissen=None, antrag=None):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name) / 'p'
        root.mkdir()
        guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(t.name) / 'tokens.json')
        regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        w = Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': []}, guard=guard, mission_id='M-W', regeln=regeln, wissen=wissen, wissen_antrag=antrag)
        return Kiste(w, regeln=regeln, guard=guard, audit=None, karten=Karten(Path(t.name) / 'k'), sitzung_id='S-00000001')

    def test_eingeordnet_und_mit_schema(self):
        for name in ('wissen_suchen', 'wissen_beantragen'):
            self.assertIn(name, katalog.OHNE_KARTE)
            self.assertIn(name, NAMEN)
            self.assertEqual(SCHEMAS[name]['function']['name'], name)

    def test_suchen_ohne_karte_mit_sitzung_und_antwort(self):
        gesehen = []
        k = self.kiste(wissen=lambda sid, aid, args: (gesehen.append((sid, aid, args)), '1 Treffer [W0123456789ab]')[1])
        r = k.aufruf('wissen_suchen', {'frage': 'Lease', 'k': 3}, antwort_id='A-00000009')
        self.assertEqual((r['status'], r['wirkung'], r['ergebnis']), ('ok', False, '1 Treffer [W0123456789ab]'))
        self.assertEqual(gesehen[0][:2], ('S-00000001', 'A-00000009'), 'Sitzung und Antwort kommen vom Server')
        self.assertEqual((gesehen[0][2]['frage'], gesehen[0][2]['k']), ('Lease', 3))
        self.assertIn('argument_fehlt', k.aufruf('wissen_suchen', {})['ergebnis'])
        self.assertIn('nicht_verfuegbar', self.kiste().aufruf('wissen_suchen', {'frage': 'x'})['ergebnis'])

    def test_kein_fragetext_im_audit_der_harness(self):
        """U10 L3: ohne Eintrag in der Ausnahmeliste stand jede Suche als HARNESS_PROJEKT_BEANTRAGT mit dem Fragetext im Audit (WK-06)."""
        ereignisse = []

        class Audit:
            def append(self, event, **kw):
                ereignisse.append((event, kw.get('payload')))
        k = self.kiste(wissen=lambda sid, aid, args: 'Treffer', antrag=lambda nutz: {'status': 'beantragt'})
        k.audit = Audit()
        k.aufruf('wissen_suchen', {'frage': 'Steuernummer des Kunden Müller'})
        k.aufruf('wissen_beantragen', {'pfad': 'docs'})
        self.assertEqual([e for e, _ in ereignisse if e.startswith('HARNESS_')], [])
        self.assertNotIn('Steuernummer', repr(ereignisse))

    def test_beantragen_ist_nur_ein_antrag(self):
        k = self.kiste(antrag=lambda nutz: {'status': 'beantragt', 'decision_id': 'request:M-1'})
        r = k.aufruf('wissen_beantragen', {'pfad': 'docs', 'wurzel': 'repo'})
        self.assertEqual((r['status'], r['wirkung']), ('ok', False))
        self.assertIn('Posteingang', r['ergebnis'])
        schon = self.kiste(antrag=lambda nutz: {'status': 'schon_aufgenommen'}).aufruf('wissen_beantragen', {'pfad': 'docs'})
        self.assertIn('schon im Wissen', schon['ergebnis'])

        def nein(nutz):
            raise ValueError('Heute nur Pfade im SEDRA-Ordner (K5)')
        self.assertIn('K5', self.kiste(antrag=nein).aufruf('wissen_beantragen', {'pfad': 'C:/x'})['ergebnis'])


class GatewayInOneSedra(unittest.TestCase):
    def test_gateway_auskunft_als_lesendes_werkzeug(self):
        for name in ('gateway_status', 'gateway_vorgang', 'gateway_regel'):
            self.assertIn(name, harness_api.LESEN)
        tmp = tempfile.TemporaryDirectory(prefix='harness-gw-')
        self.addCleanup(tmp.cleanup)
        project = Path(tmp.name) / 'project'
        switch_on(project)
        hub = UIXHub(project, ARCH)
        self.addCleanup(hub.close)
        from sedra_runtime.chat_tools import ChatTools
        kiste = Kiste(Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(project), 'schreibbereich': []}, guard=hub.runtime.guard, mission_id='M-G',
                                regeln=katalog.laden(Path('gibt-es-nicht'))['regeln']),
                      regeln=[], guard=hub.runtime.guard, audit=None, karten=Karten(Path(tmp.name) / 'k'), sitzung_id='S-1', chat=ChatTools(hub, harness_api.LESEN))
        schema = kiste.zustand_schema()['function']
        self.assertIn('gateway_regel', schema['parameters']['properties']['was']['enum'])
        self.assertIn('frage', schema['parameters']['properties'])
        self.assertIn('id', schema['parameters']['properties'])
        r = kiste.aufruf('zustand', {'was': 'gateway_regel', 'frage': 'R-02'})
        self.assertEqual((r['status'], r['stufe'], r['wirkung']), ('ok', 'frei', False))
        self.assertIn('R-02', r['ergebnis'])
        self.assertEqual(kiste.chat.proposals, [], 'die Auskunft schlägt nichts vor')


if __name__ == '__main__':
    unittest.main()
