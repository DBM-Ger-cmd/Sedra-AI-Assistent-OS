"""Bausteine der Aufgaben-Freigabe (Analyse Freigaben S1, 04.11.2026): Vorgabe im Repo, eigene des Captains in local_config, nie vom Modell; nur Auswahlhilfe."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.harness import bausteine as bs
from guppi_runtime.harness.api import WEG


def doc(*eintraege):
    return {'bausteine': list(eintraege)}


def b(bid='x', name='X', zeilen=None, **k):
    return dict({'id': bid, 'name': name, 'zeilen': zeilen if zeilen is not None else [{'werkzeug': 'datei_aendern', 'muster': 'docs/**'}]}, **k)


class Pruefen(unittest.TestCase):
    def test_gueltig(self):
        out = bs.pruefen(doc(b(hinweis='Hallo')), 'repo')
        self.assertEqual((out[0]['id'], out[0]['hinweis'], out[0]['quelle']), ('x', 'Hallo', 'repo'))

    def test_abweisungen_sind_ein_satz_mit_kennung(self):
        faelle = [({}, 'bausteine_ohne_liste'), (doc('text'), 'baustein_kein_objekt'), (doc(b('X Y')), 'baustein_id_ungueltig'), (doc(b(), b()), 'baustein_id_doppelt'),
                  (doc(b(name='')), 'baustein_name_fehlt'), (doc(b(zeilen=[])), 'baustein_zeilen_ungueltig'),
                  (doc(b(zeilen=[{'werkzeug': 'rm', 'muster': 'a/**'}])), 'baustein_werkzeug_unbekannt'),
                  (doc(b(zeilen=[{'werkzeug': 'datei_aendern', 'muster': ''}])), 'baustein_muster_fehlt'),
                  (doc(b(zeilen=[{'werkzeug': 'datei_aendern', 'muster': '**'}])), 'baustein_muster_zu_weit'),
                  (doc(b(zeilen=[{'werkzeug': 'datei_schreiben', 'muster': '*'}])), 'baustein_muster_zu_weit'),
                  (doc(b(zeilen=[{'werkzeug': 'datei_aendern', 'muster': 'a/**'}] * 7)), 'baustein_zeilen_ungueltig')]
        for d, code in faelle:
            with self.assertRaisesRegex(ValueError, code):
                bs.pruefen(d, 'repo')


class Laden(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        (self.root / 'local_config').mkdir()

    def test_die_mitgelieferten_bausteine_sind_gueltig_und_nennen_das_noetige(self):
        ids = [x['id'] for x in bs.laden(self.root)['bausteine']]
        for erwartet in ('tests-starten', 'docs-aendern', 'docs-anlegen'):
            self.assertIn(erwartet, ids)

    def test_eigene_ersetzen_gleiche_id_und_ergaenzen_neue(self):
        (self.root / 'local_config' / bs.DATEI).write_text(
            'bausteine:\n  - {id: docs-aendern, name: Meine Docs, zeilen: [{werkzeug: datei_aendern, muster: "doku/**"}]}\n'
            '  - {id: neu, name: Neu, zeilen: [{werkzeug: lauf_starten, muster: spec_check}]}\n', encoding='utf-8')
        out = {x['id']: x for x in bs.laden(self.root)['bausteine']}
        self.assertEqual((out['docs-aendern']['name'], out['docs-aendern']['quelle']), ('Meine Docs', 'local_config'))
        self.assertEqual(out['neu']['zeilen'][0]['muster'], 'spec_check')
        self.assertEqual(out['tests-starten']['quelle'], 'repo')

    def test_eine_kaputte_eigene_datei_laesst_die_vorgabe_und_nennt_den_grund(self):
        (self.root / 'local_config' / bs.DATEI).write_text('bausteine:\n  - {id: x, name: X, zeilen: [{werkzeug: datei_aendern, muster: "**"}]}\n', encoding='utf-8')
        out = bs.laden(self.root)
        self.assertTrue(out['bausteine'])
        self.assertIn('baustein_muster_zu_weit', out['hinweise'][0])
        (self.root / 'local_config' / bs.DATEI).write_text('{{{', encoding='utf-8')
        self.assertIn('bausteine_nicht_lesbar', bs.laden(self.root)['hinweise'][0])

    def test_der_weg_ist_bekannt(self):
        m = WEG.fullmatch('/api/harness/bausteine')
        self.assertIsNotNone(m)
        self.assertIn('bausteine', m.groups())


if __name__ == '__main__':
    unittest.main()
