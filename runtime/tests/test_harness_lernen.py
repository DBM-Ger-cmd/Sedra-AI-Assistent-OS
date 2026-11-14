"""W4-Werkzeuge `rueckblick_schreiben` und `vorschlaege_pflegen` (Spec W4, 14.11.2026).

Tests nach Spec §2 (Spalte "Prüfbar durch"), Gegenproben aus Spec §5 und
F-027 (echter Antrag im Posteingang via gated.request, entscheide über decide/reject).

   PYTHONPATH=<worktree>\runtime\src;<worktree>\runtime\tests SEDRA_WISSEN_STANDARD=aus python -m unittest test_harness_lernen
"""
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from sedra_runtime.core.guard import Guard
from sedra_runtime.desk import gated
from sedra_runtime.harness import antraege_lernen
from sedra_runtime.harness import katalog
from sedra_runtime.harness.katalog import einstufen
from sedra_runtime.harness.werkzeuge import NAMEN, SCHEMAS, WIRKUNGSKLASSE, WerkzeugFehler, Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'


class Hub:
    """Minimaler Hub für gated.request/decide/reject ohne Server."""
    def __init__(self, root):
        self.project_root = root
        self.antraege = []
        self.audit = []
        self.missionen_dict = {}
        self._mid = 0
        self.lock = threading.Lock()
        self.runtime = SimpleNamespace(
            guard=Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, root / 'tokens.json'),
            brain=SimpleNamespace(create_mission=self._create_mission),
            missions=SimpleNamespace(
                save=lambda m: self.missionen_dict.__setitem__(m['identity']['mission_id'], m),
                load=lambda mid: self.missionen_dict[mid],
                execution_lock=lambda mid: self._execution_lock(mid),
            ),
            audit=SimpleNamespace(append=lambda e, component=None, payload=None, **k: self.audit.append((e, payload))),
        )
        self.events = SimpleNamespace(publish=lambda *a, **k: None)

    def _create_mission(self, describe, _, level):
        self._mid += 1
        mid = f'M-{self._mid:06d}'
        return {
            'identity': {'mission_id': mid},
            'human_gates': {'pending': [], 'resolved': []},
            'context': {},
            'execution': {},
            'lifecycle': {'status': 'open'},
        }

    def _open_requests(self):
        return []

    def _remember(self, kind, ctx):
        self.antraege.append((kind, ctx))
        return ctx

    @contextmanager
    def _execution_lock(self, mid):
        yield


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'projekt'
        (root / 'docs').mkdir(parents=True)
        self.root = root
        self.guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(self.tmp.name) / 'tokens.json')
        self.projekt = {'id': 'p', 'name': 'P', 'wurzel': str(root), 'schreibbereich': ['docs/**']}
        self.w = Werkzeuge(self.projekt, guard=self.guard, mission_id='M-LERNEN',
                           regeln=katalog.laden(Path('fehlt'))['regeln'])
        self.angetragene = []

        def rueckblick_antrag(payload):
            self.angetragene.append(('rueckblick', payload))
            return {'mission_id': 'M-MOCK'}

        def vorschlag_antrag(payload):
            self.angetragene.append(('vorschlag', payload))
            return {'mission_id': 'M-MOCK'}

        self.w.rueckblick_antrag = rueckblick_antrag
        self.w.vorschlag_antrag = vorschlag_antrag


class RueckblickTest(Basis):
    def test_rueckblick_erstellen(self):  # W4-01
        plan = self.w.vorbereiten('rueckblick_schreiben', {
            'titel': 'Sitzung 12', 'sitzung_id': 'S-7',
            'was_gelaufen_ist': 'W3-Tests liefen durch.',
            'was_schief_lief': 'Eine Dateisperre unter Last.',
            'massnahmen': [{'beschreibung': 'Teardown prüfen', 'verantwortlich': 'Hermes'}],
            'dokument_ziel': 'docs/AAR/LESSONS.md',
        })
        self.assertEqual(plan['ziel'], 'rueckblick/S-7')
        self.assertIn('Sitzung 12', plan['vorschau'])
        self.assertEqual(plan['gate']['aktion'], 'rueckblick_antrag')
        antrag = plan['antrag']
        self.assertEqual(antrag['titel'], 'Sitzung 12')
        self.assertEqual(antrag['sitzung_id'], 'S-7')
        self.assertEqual(antrag['dokument'], 'docs/AAR/LESSONS.md')
        self.assertEqual(antrag['status'], 'offen')
        self.assertEqual(len(antrag['massnahmen']), 1)

    def test_antrag_nur_posteingang(self):  # W4-02
        plan = self.w.vorbereiten('rueckblick_schreiben', {'titel': 'T', 'was_gelaufen_ist': 'W'})
        out = self.w.ausfuehren('rueckblick_schreiben', {}, plan=plan)
        self.assertEqual(out['status'], 'ok')
        self.assertFalse(out['wirkung'])
        self.assertEqual(len(self.angetragene), 1)
        self.assertEqual(self.angetragene[0][0], 'rueckblick')
        self.assertEqual(self.angetragene[0][1]['titel'], 'T')
        self.assertFalse((self.root / 'docs' / 'AAR' / 'LESSONS.md').exists())

    def test_massnahme_nicht_still_umgesetzt(self):  # W4-03
        plan = self.w.vorbereiten('rueckblick_schreiben', {
            'titel': 'T', 'was_gelaufen_ist': 'W',
            'massnahmen': [{'beschreibung': 'x', 'verantwortlich': 'y', 'frist?': '2026-11-15'}],
        })
        out = self.w.ausfuehren('rueckblick_schreiben', {}, plan=plan)
        self.assertFalse(out['wirkung'])
        self.assertIn('Posteingang', out['ergebnis'])

    def test_pflichtfelder(self):  # W4-04
        for args in ({}, {'titel': 'x'}, {'was_gelaufen_ist': 'x'}):
            with self.assertRaises(WerkzeugFehler) as exc:
                self.w.vorbereiten('rueckblick_schreiben', args)
            self.assertIn('argument_fehlt', str(exc.exception))


class RueckblickSchemaTest(unittest.TestCase):
    def test_wirkungsklasse(self):  # W4-05
        self.assertEqual(WIRKUNGSKLASSE['rueckblick_schreiben'], 'proposal_only')


class VorschlageTest(Basis):
    def test_vorschlag_anlegen(self):  # W4-06
        plan = self.w.vorbereiten('vorschlaege_pflegen', {
            'aktion': 'anlegen', 'titel': 'Cache prüfen', 'quelle': 'test',
            'beschreibung': 'Der Harness-Cache wächst unbegrenzt.', 'prioritaet': 'hoch',
        })
        self.assertEqual(plan['ziel'], 'vorschlag/Cache prüfen')
        self.assertEqual(plan['gate']['aktion'], 'vorschlag_antrag')
        self.assertEqual(plan['antrag']['aktion'], 'anlegen')
        self.assertEqual(plan['antrag']['status'], 'offen')
        self.assertEqual(plan['antrag']['prioritaet'], 'hoch')

    def test_vorschlag_aendern(self):
        plan = self.w.vorbereiten('vorschlaege_pflegen', {
            'aktion': 'aendern', 'titel': 'Cache prüfen', 'status': 'geprüft',
        })
        self.assertEqual(plan['antrag']['status'], 'geprüft')

    def test_antrag_nur_posteingang(self):  # W4-07
        plan = self.w.vorbereiten('vorschlaege_pflegen', {'aktion': 'anlegen', 'titel': 'T'})
        out = self.w.ausfuehren('vorschlaege_pflegen', {}, plan=plan)
        self.assertEqual(out['status'], 'ok')
        self.assertFalse(out['wirkung'])
        self.assertEqual(len(self.angetragene), 1)
        self.assertEqual(self.angetragene[0][0], 'vorschlag')

    def test_status_mit_freigabe(self):  # W4-08 (F-024: auch offen/geprüft über Gate)
        plan = self.w.vorbereiten('vorschlaege_pflegen', {
            'aktion': 'status_setzen', 'titel': 'T', 'status': 'umgesetzt',
        })
        self.assertEqual(plan['gate']['aktion'], 'vorschlag_antrag')
        out = self.w.ausfuehren('vorschlaege_pflegen', {}, plan=plan)
        self.assertFalse(out['wirkung'])

    def test_pflichtfelder(self):  # W4-09
        for args in ({}, {'aktion': 'anlegen'}, {'titel': 'x'}):
            with self.assertRaises(WerkzeugFehler) as exc:
                self.w.vorbereiten('vorschlaege_pflegen', args)
            self.assertIn('argument_fehlt', str(exc.exception))

    def test_keine_automatische_umsetzung(self):  # W4-10
        plan = self.w.vorbereiten('vorschlaege_pflegen', {
            'aktion': 'anlegen', 'titel': 'T', 'status': 'umgesetzt',
        })
        out = self.w.ausfuehren('vorschlaege_pflegen', {}, plan=plan)
        self.assertFalse(out['wirkung'])
        self.assertIn('Keine direkte Wirkung', out['ergebnis'])


class HarnessTest(Basis):
    def test_w4_in_namen(self):  # W4-11
        self.assertIn('rueckblick_schreiben', NAMEN)
        self.assertIn('vorschlaege_pflegen', NAMEN)

    def test_w4_schemas(self):  # W4-12
        for name in ('rueckblick_schreiben', 'vorschlaege_pflegen'):
            self.assertIn(name, SCHEMAS)
            schema = SCHEMAS[name]
            self.assertEqual(schema['function']['name'], name)
            props = schema['function']['parameters']['properties']
            self.assertIn('titel', props)
            self.assertIn('titel', schema['function']['parameters']['required'])

    def test_w4_vorbereiten_ausfuehren(self):  # W4-13
        plan = self.w.vorbereiten('rueckblick_schreiben', {'titel': 'T', 'was_gelaufen_ist': 'W'})
        self.assertIn('gate', plan)
        out = self.w.ausfuehren('rueckblick_schreiben', {}, plan=plan)
        self.assertEqual(out['status'], 'ok')
        self.assertFalse(out['wirkung'])
        plan = self.w.vorbereiten('vorschlaege_pflegen', {'aktion': 'anlegen', 'titel': 'V'})
        out = self.w.ausfuehren('vorschlaege_pflegen', {}, plan=plan)
        self.assertEqual(out['status'], 'ok')
        self.assertFalse(out['wirkung'])


class EinstufungTest(unittest.TestCase):
    def test_w4_captain(self):  # W4-14, Gegenprobe Spec §5: Aufruf ohne Gate -> 403 gate_required
        regeln = katalog.laden(Path('fehlt'))['regeln']
        for name in ('rueckblick_schreiben', 'vorschlaege_pflegen'):
            self.assertEqual(einstufen(regeln, name, 'beliebiges-ziel')['stufe'], 'captain', name)


class AntragFlow(unittest.TestCase):
    """F-027: echter Antrag im Posteingang, entscheide über decide/reject."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.hub = Hub(self.root)
        self.guard = self.hub.runtime.guard
        for kind, applier in ((antraege_lernen.KIND_RUECKBLICK, antraege_lernen.rueckblick_anwenden),
                              (antraege_lernen.KIND_VORSCHLAG, antraege_lernen.vorschlag_anwenden)):
            gated._APPLIERS[kind] = (applier, None)

    def tearDown(self):
        for kind in (antraege_lernen.KIND_RUECKBLICK, antraege_lernen.KIND_VORSCHLAG):
            gated._APPLIERS.pop(kind, None)

    def _werkzeuge(self):
        return Werkzeuge(
            {'id': 'p', 'name': 'P', 'wurzel': str(self.root), 'schreibbereich': ['docs/**']},
            guard=self.guard, mission_id='M-TEST',
            regeln=katalog.laden(Path('fehlt'))['regeln'],
            rueckblick_antrag=lambda p: antraege_lernen.rueckblick_antrag(self.hub, p),
            vorschlag_antrag=lambda p: antraege_lernen.vorschlag_antrag(self.hub, p),
        )

    def test_antrag_steht_im_posteingang_vor_der_freigabe(self):  # F-027-5
        w = self._werkzeuge()
        plan = w.vorbereiten('rueckblick_schreiben', {
            'titel': 'Sitzung 12', 'sitzung_id': 'S-7',
            'was_gelaufen_ist': 'W3-Tests liefen durch.',
            'massnahmen': [{'beschreibung': 'Teardown prüfen', 'verantwortlich': 'Hermes'}],
        })
        out = w.ausfuehren('rueckblick_schreiben', {}, plan=plan)
        self.assertEqual(out['status'], 'ok')
        self.assertFalse(out['wirkung'])
        self.assertEqual(len(self.hub.antraege), 1)
        kind, ctx = self.hub.antraege[0]
        self.assertEqual(kind, antraege_lernen.KIND_RUECKBLICK)
        self.assertEqual(ctx['binding']['antrag']['titel'], 'Sitzung 12')
        self.assertIsNone(ctx['binding']['ziel_stand'])
        self.assertFalse((self.root / 'docs' / 'AAR' / 'LESSONS.md').exists())

    def test_nach_decide_ist_lessons_md_da(self):
        w = self._werkzeuge()
        plan = w.vorbereiten('rueckblick_schreiben', {
            'titel': 'Rückblick', 'was_gelaufen_ist': 'Alles gut.',
            'massnahmen': [{'beschreibung': 'Prüfen', 'verantwortlich': 'Pi'}],
        })
        w.ausfuehren('rueckblick_schreiben', {}, plan=plan)
        mid = self.hub.antraege[-1][1]['mission_id']
        res = gated.decide(self.hub, mid)
        self.assertEqual(res['status'], 'applied')
        pfad = self.root / 'docs' / 'AAR' / 'LESSONS.md'
        self.assertTrue(pfad.is_file())
        inhalt = pfad.read_text(encoding='utf-8')
        self.assertIn('Rückblick', inhalt)
        self.assertIn('Alles gut.', inhalt)
        self.assertIn('Prüfen', inhalt)

    def test_nach_ablehnung_ist_nichts_geschrieben(self):
        w = self._werkzeuge()
        plan = w.vorbereiten('rueckblick_schreiben', {'titel': 'R', 'was_gelaufen_ist': 'W'})
        w.ausfuehren('rueckblick_schreiben', {}, plan=plan)
        mid = self.hub.antraege[-1][1]['mission_id']
        res = gated.reject(self.hub, mid)
        self.assertEqual(res['status'], 'rejected')
        self.assertFalse((self.root / 'docs' / 'AAR' / 'LESSONS.md').exists())

    def test_binding_stale_wenn_ziel_zwischen_zeit_geaendert(self):
        w = self._werkzeuge()
        plan = w.vorbereiten('rueckblick_schreiben', {'titel': 'R', 'was_gelaufen_ist': 'W'})
        w.ausfuehren('rueckblick_schreiben', {}, plan=plan)
        (self.root / 'docs' / 'AAR').mkdir(parents=True)
        (self.root / 'docs' / 'AAR' / 'LESSONS.md').write_text('fremd\n', encoding='utf-8')
        mid = self.hub.antraege[-1][1]['mission_id']
        res = gated.decide(self.hub, mid)
        self.assertEqual(res['status'], 'binding_stale')
        self.assertEqual((self.root / 'docs' / 'AAR' / 'LESSONS.md').read_text(encoding='utf-8'), 'fremd\n')

    def test_vorschlag_nach_decide_in_liste(self):  # Spec §3 Format
        w = self._werkzeuge()
        plan = w.vorbereiten('vorschlaege_pflegen', {
            'aktion': 'anlegen', 'titel': 'Cache prüfen', 'quelle': 'test',
            'beschreibung': 'Der Cache wächst.', 'prioritaet': 'hoch',
        })
        w.ausfuehren('vorschlaege_pflegen', {}, plan=plan)
        mid = self.hub.antraege[-1][1]['mission_id']
        gated.decide(self.hub, mid)
        pfad = self.root / 'docs' / 'AAR' / 'VORSCHLAEGE.md'
        self.assertTrue(pfad.is_file())
        inhalt = pfad.read_text(encoding='utf-8')
        self.assertIn('Cache prüfen', inhalt)
        self.assertIn('anlegen', inhalt)
        self.assertIn('hoch', inhalt)


if __name__ == '__main__':
    unittest.main()
