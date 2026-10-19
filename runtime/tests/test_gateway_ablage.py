"""Die Ablage des GateWay (Spezifikation Abschnitt 6): Original bleibt, Vermerk, Arbeitskopie, Speichern unter in den Ausgang."""
import json
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.gateway import ablage


class Ablage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ablage-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        d = ablage.ordner(self.root)
        self.original = d['eingang'] / 'Anfrage.txt'
        self.original.write_text('Max Muster schreibt aus Beierswerder.', encoding='utf-8')
        self.hash_vorher = ablage.sha256_datei(self.original)

    def test_the_original_stays_unchanged_and_gets_a_vermerk(self):
        ablage.original_vermerken(self.original)
        self.assertEqual(ablage.sha256_datei(self.original), self.hash_vorher)
        v = json.loads(ablage.vermerk_pfad(self.original).read_text(encoding='utf-8'))
        self.assertEqual((v['art'], v['hinweis']), ('original', ablage.ORIGINAL_HINWEIS))
        self.assertEqual(v['sha256'], self.hash_vorher)
        self.assertNotIn('Muster', ablage.vermerk_pfad(self.original).read_text(encoding='utf-8'), 'der Vermerk enthält keinen Text')

    def test_a_working_copy_lives_next_to_the_original_and_leaves_it_alone(self):
        kopie = ablage.arbeitskopie(self.root, 'Anfrage.txt')
        self.assertEqual(kopie.parent.name, 'Arbeitskopien')
        self.assertEqual(kopie.read_text(encoding='utf-8'), self.original.read_text(encoding='utf-8'))
        self.assertEqual(ablage.sha256_datei(self.original), self.hash_vorher)

    def test_saving_under_a_new_name_writes_to_ausgang_with_a_vermerk(self):
        v = ablage.speichern_unter(self.root, 'Anfrage.txt', 'Kunde <COMPANY_001> schreibt.', 'Anfrage_anonymisiert.txt',
                                   [{'art': 'ersetzen', 'platzhalter': 'COMPANY_001'}])
        ziel = ablage.ordner(self.root)['ausgang'] / 'Anfrage_anonymisiert.txt'
        self.assertEqual(ziel.read_text(encoding='utf-8'), 'Kunde <COMPANY_001> schreibt.')
        self.assertEqual(v['original_sha256'], self.hash_vorher)
        self.assertEqual(ablage.sha256_datei(self.original), self.hash_vorher, 'das Original bleibt')
        self.assertEqual(v['vorgaben'][0]['platzhalter'], 'COMPANY_001')

    def test_an_existing_output_is_never_replaced(self):
        ablage.speichern_unter(self.root, 'Anfrage.txt', 'eins', 'a.txt', [])
        with self.assertRaisesRegex(ablage.AblageFehler, 'ziel_existiert'):
            ablage.speichern_unter(self.root, 'Anfrage.txt', 'zwei', 'a.txt', [])

    def test_names_with_paths_or_wrong_endings_are_refused(self):
        for bad in ('../x.txt', '.versteckt.txt', 'bild.pdf', 'C:' + chr(92) + 'x.txt', ''):
            with self.assertRaises(ablage.AblageFehler, msg=bad):
                ablage.speichern_unter(self.root, 'Anfrage.txt', 'x', bad, [])

    def test_a_missing_original_is_reported(self):
        with self.assertRaisesRegex(ablage.AblageFehler, 'original_nicht_gefunden'):
            ablage.speichern_unter(self.root, 'fehlt.txt', 'x', 'y.txt', [])


if __name__ == '__main__':
    unittest.main()
