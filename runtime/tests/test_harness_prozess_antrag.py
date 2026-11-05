"""„Prozess anlegen“ durch SEDRA (Plan UIX Phase 6): Werkzeug prozess_beantragen -> Antrag im Posteingang -> nach der Freigabe ein Entwurf im Prozessbestand.
Nie ausführbar, nie ohne den Captain, Rechte aus dem Aufruf gehen nie weiter."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from guppi_runtime.core.guard import Guard
from guppi_runtime.harness import antraege, katalog
from guppi_runtime.harness.freigabe import Karten, Kiste
from guppi_runtime.harness.werkzeuge import Werkzeuge
from guppi_runtime.workflows import selbstabbild
from guppi_runtime.workflows.policy import assessment
from guppi_runtime.workflows.process import metadata
from guppi_runtime.workflows.store import WorkflowStore

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'

SCHRITTE = [
    {'name': 'Anfrage erfassen', 'rolle': 'Sachbearbeitung', 'eingabe': 'Anfrage', 'ergebnis': 'Erfasster Vorgang'},
    {'name': 'Vorgang prüfen', 'art': 'decision', 'rolle': 'Sachbearbeitung', 'weiter': ['Antwort senden', 'Rückfrage stellen']},
    {'name': 'Antwort senden', 'arbeitsweise': 'automatable'},
    {'name': 'Rückfrage stellen', 'art': 'end'},
]


class Hub:
    def __init__(self, root, offen=()):
        self.project_root = root
        self._offen = list(offen)
        self.audit = []
        self.runtime = SimpleNamespace(audit=SimpleNamespace(append=lambda e, component=None, payload=None, **k: self.audit.append((e, payload))))
        self.events = SimpleNamespace(publish=lambda name, daten: None)

    def _open_requests(self):
        return self._offen


class Entwurf(unittest.TestCase):
    def test_entwurf_ist_ein_nicht_ausfuehrbares_prozessmodell(self):
        doc = selbstabbild.entwurf({'name': 'Anfrage bearbeiten', 'zweck': 'Anfragen einheitlich beantworten', 'schritte': SCHRITTE})
        self.assertEqual(doc['name'], 'Entwurf · Anfrage bearbeiten')
        self.assertTrue(all(n['disabled'] for n in doc['nodes']))
        self.assertFalse(assessment(doc)['executable'])
        meta = [metadata(n) for n in doc['nodes']]
        self.assertEqual([m['kind'] for m in meta], ['start', 'decision', 'task', 'end'])
        self.assertIn('Zweck: Anfragen einheitlich beantworten', meta[0]['original_notes'])
        self.assertTrue(all(m['source'] == 'proposal' and m['role_status'] == 'proposal' for m in meta), 'alles ist ein Vorschlag')
        self.assertEqual([[e['node'] for e in b] for b in doc['connections']['Vorgang prüfen']['main']], [['Antwort senden'], ['Rückfrage stellen']])
        self.assertEqual([e['node'] for e in doc['connections']['Anfrage erfassen']['main'][0]], ['Vorgang prüfen'], 'ohne weiter folgt der nächste Schritt')

    def test_fehler_sind_saetze(self):
        for payload, code in [({'schritte': SCHRITTE}, 'prozess_name_fehlt'), ({'name': 'X', 'schritte': SCHRITTE[:1]}, 'prozess_schritte_ungueltig'),
                              ({'name': 'X', 'schritte': 'nix'}, 'prozess_schritte_ungueltig'),
                              ({'name': 'X', 'schritte': SCHRITTE[:2] + [{'name': 'Z', 'weiter': ['gibt es nicht']}]}, 'prozess_weiter_unbekannt'),
                              ({'name': 'X', 'schritte': [{'name': 'A', 'art': 'start'}, {'name': 'A', 'art': 'end'}]}, 'selbstabbild_schritt_doppelt'),
                              ({'name': 'X', 'schritte': [{'name': 'A', 'art': 'task'}, {'name': 'B', 'art': 'end'}, {'name': 'C', 'art': 'end'}][1:]}, 'selbstabbild_genau_ein_start')]:
            with self.assertRaisesRegex(ValueError, code):
                selbstabbild.entwurf(payload)

    def test_unbekannte_felder_wie_rechte_werden_nicht_uebernommen(self):
        doc = selbstabbild.entwurf({'name': 'N', 'schritte': [dict(SCHRITTE[0], rechte='alles', disabled=False), dict(SCHRITTE[3])]})
        self.assertTrue(all(n['disabled'] for n in doc['nodes']))
        self.assertNotIn('rechte', str(doc))


class Antrag(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.root = Path(t.name)

    def anfordern(self, hub, payload):
        with mock.patch.object(antraege.gated, 'request', return_value={'mission_id': 'M-P'}) as anfrage:
            return antraege.prozess_antrag(hub, payload), anfrage

    def test_antrag_schreibt_nichts_bevor_der_captain_freigibt(self):
        hub = Hub(self.root)
        out, anfrage = self.anfordern(hub, {'name': 'Anfrage bearbeiten', 'schritte': SCHRITTE})
        self.assertEqual((out['name'], out['schritte']), ('Entwurf · Anfrage bearbeiten', 4))
        self.assertEqual(anfrage.call_args.args[1], antraege.KIND_PROZESS)
        self.assertTrue(anfrage.call_args.kwargs['exact'])
        self.assertEqual(WorkflowStore(self.root).listing(), [], 'vor der Freigabe entsteht nichts')

    def test_nach_der_freigabe_entsteht_eine_erste_revision_und_ein_audit_eintrag(self):
        hub = Hub(self.root)
        _, anfrage = self.anfordern(hub, {'name': 'Anfrage bearbeiten', 'schritte': SCHRITTE})
        binding = anfrage.call_args.args[4]
        out = antraege._prozess_anwenden(hub, binding)
        record = WorkflowStore(self.root).read(out['workflow_id'])
        self.assertEqual(record['revision'], 1)
        self.assertEqual(record['change_note'], 'Entwurf von SEDRA, vom Captain übernommen')
        self.assertEqual(hub.audit[-1][0], 'WORKFLOW_ENTWURF_UEBERNOMMEN')

    def test_ein_manipulierter_antrag_ohne_entwurfsname_wird_abgewiesen(self):
        hub = Hub(self.root)
        doc = selbstabbild.entwurf({'name': 'X', 'schritte': SCHRITTE})
        doc['name'] = 'Normaler Workflow'
        with self.assertRaisesRegex(ValueError, 'prozess_entwurf_ungueltig'):
            antraege._prozess_anwenden(hub, {'workflow': doc})
        self.assertEqual(WorkflowStore(self.root).listing(), [])

    def test_grenzen_doppelt_und_zu_viele(self):
        doc = selbstabbild.entwurf({'name': 'Anfrage bearbeiten', 'schritte': SCHRITTE})
        hub = Hub(self.root, offen=[{'kind': antraege.KIND_PROZESS, 'binding': {'workflow': doc}}])
        with self.assertRaisesRegex(ValueError, 'antrag_liegt_schon_im_posteingang'):
            self.anfordern(hub, {'name': 'Anfrage bearbeiten', 'schritte': SCHRITTE})
        voll = Hub(self.root, offen=[{'kind': antraege.KIND_PROZESS, 'binding': {'workflow': {'name': 'a%d' % i}}} for i in range(antraege.PROZESS_ANTRAEGE_MAX)])
        with self.assertRaisesRegex(ValueError, 'zu_viele_offene_antraege'):
            self.anfordern(voll, {'name': 'Neu', 'schritte': SCHRITTE})


class Werkzeug(unittest.TestCase):
    def kiste(self, antrag):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        root = Path(t.name) / 'p'; root.mkdir()
        guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(t.name) / 'tokens.json')
        regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        w = Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': []}, guard=guard, mission_id='M-P', regeln=regeln, prozess_antrag=antrag)
        return Kiste(w, regeln=regeln, guard=guard, audit=None, karten=Karten(Path(t.name) / 'k'), sitzung_id='S-00000001')

    def test_werkzeug_stellt_nur_einen_antrag_ohne_karte(self):
        gesehen = []

        def antrag(nutz):
            gesehen.append(nutz)
            return {'name': 'Entwurf · X', 'schritte': 4}
        r = self.kiste(antrag).aufruf('prozess_beantragen', {'name': 'X', 'schritte': SCHRITTE, 'rechte': {'alles': True}})
        self.assertEqual(r['status'], 'ok')
        self.assertIn('Posteingang', r['ergebnis'])
        self.assertFalse(r['wirkung'])
        self.assertEqual(gesehen, [{'name': 'X', 'schritte': SCHRITTE}], 'Rechte aus dem Aufruf gehen nie weiter')
        self.assertIn('prozess_beantragen', katalog.OHNE_KARTE)

    def test_fehler_des_antrags_kommen_als_satz_zurueck(self):
        def antrag(nutz):
            raise ValueError('prozess_schritte_ungueltig: 2 bis 16 Schritte')
        r = self.kiste(antrag).aufruf('prozess_beantragen', {'name': 'X', 'schritte': SCHRITTE})
        self.assertEqual(r['status'], 'fehler')
        self.assertIn('prozess_schritte_ungueltig', r['ergebnis'])

    def test_ohne_name_geht_nichts_raus(self):
        r = self.kiste(lambda nutz: {}).aufruf('prozess_beantragen', {'schritte': SCHRITTE})
        self.assertNotEqual(r['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
