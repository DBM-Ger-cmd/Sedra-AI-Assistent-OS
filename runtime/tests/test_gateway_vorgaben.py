"""Gemerkte Vorgaben im GateWay (Spezifikation 5.3): global, nur als Vorschlag, nie still, keine Doppelungen."""
import json
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.gateway import vorgaben_text as vt


class GemerkteVorgaben(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='vorgaben-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_a_rule_is_kept_and_listed(self):
        e = vt.merken(self.root, 'Bürostuhl AG', 'COMPANY', 'ersetzen', '<COMPANY_001>')
        self.assertEqual([x['id'] for x in vt.laden(self.root)], [e['id']])

    def test_the_same_text_and_type_replace_the_old_rule_instead_of_doubling(self):
        vt.merken(self.root, 'DEF', 'ORT', 'behalten')
        vt.merken(self.root, 'def', 'ORT', 'ersetzen', '<ORT_001>')
        eintraege = vt.laden(self.root)
        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0]['art'], 'ersetzen')

    def test_invalid_values_are_refused(self):
        for args in (('', 'ORT', 'ersetzen'), ('x', 'NICHT', 'ersetzen'), ('x', 'ORT', 'löschen'), ('x' * 201, 'ORT', 'ersetzen')):
            with self.assertRaises(vt.VorgabeFehler, msg=str(args)):
                vt.merken(self.root, *args)

    def test_a_rule_is_only_a_suggestion_and_matches_text_and_type(self):
        vt.merken(self.root, 'Bürostuhl AG', 'COMPANY', 'ersetzen', '<COMPANY_001>')
        fund = [{'id': 0, 'text': 'bürostuhl ag', 'typ': 'COMPANY'}, {'id': 1, 'text': 'Bürostuhl AG', 'typ': 'PERSON'},
                {'id': 2, 'text': 'Berlin', 'typ': 'ORT'}]
        v = vt.vorschlaege(vt.laden(self.root), fund)
        self.assertEqual(sorted(v), [0], 'nur der passende Text und Typ bekommt einen Vorschlag')
        self.assertEqual(v[0]['art'], 'ersetzen')

    def test_a_rule_can_be_deleted_and_a_missing_one_is_reported(self):
        e = vt.merken(self.root, 'DEF', 'ORT', 'behalten')
        self.assertTrue(vt.loeschen(self.root, e['id']))
        self.assertEqual(vt.laden(self.root), [])
        self.assertFalse(vt.loeschen(self.root, 'gibt-es-nicht'))

    def test_an_unreadable_file_is_never_overwritten_as_if_empty(self):
        p = vt._datei(self.root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{kaputt', encoding='utf-8')
        with self.assertRaisesRegex(vt.VorgabeFehler, 'vorgaben_unlesbar'):
            vt.merken(self.root, 'DEF', 'ORT', 'behalten')
        self.assertEqual(p.read_text(encoding='utf-8'), '{kaputt')


if __name__ == '__main__':
    unittest.main()


class VorschlagInDerVorschau(unittest.TestCase):
    """Eine gemerkte Vorgabe erscheint als Vorschlag in der Vorschau eines neuen Dokuments, nicht als stille Ersetzung."""

    def test_a_remembered_rule_is_a_suggestion_in_the_next_preview(self):
        from guppi_runtime.uix_server import UIXHub
        tmp = tempfile.TemporaryDirectory(prefix='vorschlag-')
        self.addCleanup(tmp.cleanup)
        arch = sorted((Path(__file__).resolve().parents[2] / 'architecture').glob('GUPPI_Architecture_v*'))[-1]
        hub = UIXHub(Path(tmp.name) / 'project', arch)
        self.addCleanup(hub.close)
        (hub.gateway_eingang() / 'neu.txt').write_text('Das Team von DEF ist da. Lena Beispiel schreibt.', encoding='utf-8')
        hub.gateway_vorgabe_merken({'text': 'DEF', 'typ': 'ORT', 'art': 'behalten'})
        v = hub.gateway_vorschau({'name': 'neu.txt'})
        def0 = [f for f in v['fundstellen'] if f['text'] == 'DEF']
        self.assertEqual(len(def0), 1, 'die gemerkte Stelle ist eine Fundstelle, auch ohne Regel')
        self.assertEqual(v['vorschlaege'][def0[0]['id']]['art'], 'behalten', 'als Vorschlag, nicht still')
        self.assertEqual(def0[0]['regel'], 'Vorgabe')
        self.assertEqual(hub.gateway_vorgaben_liste()['vorgaben'][0]['text'], 'DEF')
