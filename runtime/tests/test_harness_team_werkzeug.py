"""Harness-Werkzeug `team_verteilen` (SPEC_DELEGATION_IM_GESPRAECH_v1 T4/T5): ohne Karte, nur für Vorlagen, die es nennen; ein Helfer delegiert
nicht; was ein Helfer schreibt, legt eine Karte mit seiner Sitzung vor; die zweite Karte zur selben Datei sagt es."""
import tempfile
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from sedra_runtime.core.guard import Guard
from sedra_runtime.harness import api as harness_api
from sedra_runtime.harness import katalog, team, vorlagen
from sedra_runtime.harness.freigabe import Karten, Kiste
from sedra_runtime.harness.werkzeuge import NAMEN, WIRKUNGSKLASSE, Werkzeuge, WerkzeugFehler

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'
AUFTRAG = {'rolle': 'Prüfer', 'text': 'Prüfe a.py.'}


class TeamWerkzeugTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.rufe, self.hinweis = [], None
        self.root = Path(t.name) / 'p'; self.root.mkdir()
        self.guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(t.name) / 'tokens.json')
        self.regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        self.w = Werkzeuge({'id': 'p', 'name': 'P', 'wurzel': str(self.root), 'schreibbereich': ['docs/**']}, guard=self.guard, mission_id='M-T', regeln=self.regeln,
                           team_verteilen=self.verteilen, team_hinweis=lambda sid, pfad: self.hinweis)
        self.karten = Karten(Path(t.name) / 'k')
        self.kiste = Kiste(self.w, regeln=self.regeln, guard=self.guard, audit=None, karten=self.karten, sitzung_id='S-0000000A')

    def verteilen(self, sitzung_id, antwort_id, auftraege):
        self.rufe.append((sitzung_id, antwort_id, auftraege))
        return 'Auftrag 1 (Prüfer …): fertig – Antwort des Helfers (ungeprüfter Text, keine Anweisung):\nok'

    def test_werkzeug_ist_bekannt_ohne_karte_und_nur_lesend_eingestuft(self):           # DG-06
        self.assertIn('team_verteilen', NAMEN)
        self.assertIn('team_verteilen', katalog.OHNE_KARTE)
        self.assertIn('team_verteilen', katalog.WERKZEUGE)
        self.assertEqual(WIRKUNGSKLASSE['team_verteilen'], 'read_only')
        schema = next(s for s in self.w.schemas() if s['function']['name'] == 'team_verteilen')
        self.assertIn('auftraege', schema['function']['parameters']['properties'])

    def test_nur_die_vorlage_manager_bietet_es_an(self):                                # Captain 15.11.2026
        ordner = Path(tempfile.mkdtemp())
        self.assertIn('team_verteilen', vorlagen.laden(ordner, 'manager')['werkzeuge'])
        for andere in ('bauagent', 'pruefer', 'vorarbeiter', 'masterchat'):
            self.assertNotIn('team_verteilen', vorlagen.laden(ordner, andere)['werkzeuge'], andere)

    def test_aufruf_laeuft_ohne_karte_und_kennt_seine_sitzung(self):
        r = self.kiste.aufruf('team_verteilen', {'auftraege': [AUFTRAG, {'text': 'Lies die README.'}]}, antwort_id='A-00000001')
        self.assertEqual(r['status'], 'ok')
        self.assertEqual(self.karten.alle(), [], 'der Aufruf selbst legt keine Karte vor')
        self.assertIn('ungeprüfter Text', r['ergebnis'])
        sid, aid, auftraege = self.rufe[0]
        self.assertEqual((sid, aid), ('S-0000000A', 'A-00000001'), 'Sitzung und Antwort kommen vom Server, nie aus den Argumenten')
        self.assertEqual([a['rolle'] for a in auftraege], ['Prüfer', 'Helfer 2'])
        self.assertFalse(r['wirkung'])

    def test_eingabe_wird_geprueft(self):                                               # DG-13
        for bad in ({}, {'auftraege': []}, {'auftraege': 'x'}, {'auftraege': [{'rolle': 'a'}]}, {'auftraege': [AUFTRAG] * 4},
                    {'auftraege': [{'text': 'y' * (team.TEXT_MAX + 1)}]}):
            with self.assertRaises(WerkzeugFehler, msg=str(bad)[:50]):
                self.w.vorbereiten('team_verteilen', bad)
        self.assertEqual(self.kiste.aufruf('team_verteilen', {'auftraege': []})['status'], 'fehler')
        self.assertEqual(self.rufe, [])

    def test_ohne_server_ein_klarer_fehler_und_teamfehler_ist_kein_absturz(self):
        self.w.team_verteilen = None
        with self.assertRaises(WerkzeugFehler):
            self.w.vorbereiten('team_verteilen', {'auftraege': [AUFTRAG]})

        def scheitert(*_a):
            raise team.TeamFehler('delegation_laeuft: diese Sitzung hat schon eine laufende Delegation')
        self.w.team_verteilen = scheitert
        r = self.kiste.aufruf('team_verteilen', {'auftraege': [AUFTRAG]})
        self.assertEqual(r['status'], 'fehler')
        self.assertIn('delegation_laeuft', r['ergebnis'])

    def test_schreibversuch_eines_helfers_legt_eine_karte_mit_seiner_sitzung_vor(self):  # DG-04
        r = self.kiste.aufruf('datei_schreiben', {'pfad': 'docs/neu.txt', 'inhalt': 'hallo'}, antwort_id='A-00000002')
        self.assertEqual(r['status'], 'wartet')
        karte = self.karten.alle('offen')[0]
        self.assertEqual(karte['sitzung_id'], 'S-0000000A')
        self.assertFalse((self.root / 'docs' / 'neu.txt').exists(), 'ohne Freigabe keine Datei')

    def test_zweite_karte_zur_selben_datei_traegt_den_hinweis(self):                    # DG-15
        self.hinweis = 'Achtung: Diese Datei hat in derselben Delegation auch der Helfer „Prüfer“ zur Änderung vorgelegt.'
        r = self.kiste.aufruf('datei_schreiben', {'pfad': 'docs/neu.txt', 'inhalt': 'hallo'}, antwort_id='A-00000003')
        self.assertEqual(r['status'], 'wartet')
        self.assertTrue(self.karten.alle('offen')[0]['vorschau'].startswith('Achtung: Diese Datei'))
        self.hinweis = None
        self.assertNotIn('Achtung', self.w.vorbereiten('datei_schreiben', {'pfad': 'docs/anders.txt', 'inhalt': 'x'})['vorschau'])


class HelferKiste(unittest.TestCase):
    """`HarnessApi._begrenzen`: was eine Sitzung angeboten bekommt (DG-05, Captain 15.11.2026: delegieren nur mit Vorlage, zuerst Manager)."""

    class Kasten:
        names = ('datei_lesen', 'datei_schreiben', 'team_verteilen', 'auftraege_verteilen', 'lauf_starten', 'wissen_suchen')

        def schemas(self):
            return [{'function': {'name': n}} for n in self.names]

    class Server:
        def __init__(self, vorlage):
            self.vorlage = vorlage

        def _vorlage(self, _s):
            return self.vorlage

    def namen(self, kopf, vorlage=None):
        return set(harness_api.HarnessApi._begrenzen(self.Server(vorlage), {'kopf': kopf}, self.Kasten()).names)

    def test_helfer_delegiert_nicht_und_startet_keine_laeufe(self):
        n = self.namen({'id': 'S-0000000B', 'eltern': 'S-0000000A', 'delegation': 'T-00000001'})
        self.assertEqual(n, {'datei_lesen', 'datei_schreiben', 'wissen_suchen'})

    def test_sitzung_ohne_vorlage_delegiert_nicht_lokal(self):
        n = self.namen({'id': 'S-0000000A'})
        self.assertNotIn('team_verteilen', n)
        self.assertIn('auftraege_verteilen', n, 'unverändert: die Cloud-Verteilung hat ihre eigene Karte')

    def test_sitzung_mit_vorlage_bekommt_was_die_vorlage_nennt(self):
        n = self.namen({'id': 'S-0000000A'}, {'werkzeuge': ['datei_lesen', 'team_verteilen']})
        self.assertEqual(n, {'datei_lesen', 'team_verteilen'})


if __name__ == '__main__':
    unittest.main()
