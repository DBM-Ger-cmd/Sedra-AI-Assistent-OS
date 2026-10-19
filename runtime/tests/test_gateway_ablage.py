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


class VorschauUndAusgabe(unittest.TestCase):
    """Vorschau und Ausgabe über den Server (Spezifikation Abschnitt 3 und 5): das Original bleibt, die Ausgabe trägt Platzhalter."""

    def setUp(self):
        from unittest import mock
        from guppi_runtime.uix_server import UIXHub
        self.tmp = tempfile.TemporaryDirectory(prefix='vorschau-')
        self.addCleanup(self.tmp.cleanup)
        arch = sorted((Path(__file__).resolve().parents[2] / 'architecture').glob('GUPPI_Architecture_v*'))[-1]
        self.hub = UIXHub(Path(self.tmp.name) / 'project', arch)
        self.addCleanup(self.hub.close)
        self.eingang = self.hub.gateway_eingang()
        self.original = self.eingang / 'Anfrage.txt'
        self.original.write_text('Ich wohne in der Hauptstraße 1 in Beierswerder. Lena Beispiel schreibt. '
                                 'Lena Beispiel bittet um einen Stand. Es hat in DEF geknallt.', encoding='utf-8')
        self.hash_vorher = ablage.sha256_datei(self.original)

    def test_the_preview_finds_the_places_and_keeps_the_original(self):
        v = self.hub.gateway_vorschau({'name': 'Anfrage.txt'})
        orte = [f['text'] for f in v['fundstellen'] if f['typ'] == 'ORT']
        self.assertEqual(orte, ['Beierswerder'])
        self.assertNotIn('DEF', [f['text'] for f in v['fundstellen']], 'ein Ereignis bleibt stehen')
        self.assertEqual(ablage.sha256_datei(self.original), self.hash_vorher)

    def test_the_output_replaces_all_equal_places_and_keeps_the_rest(self):
        v = self.hub.gateway_vorschau({'name': 'Anfrage.txt'})
        auswahl = [{'id': f['id'], 'art': 'ersetzen'} for f in v['fundstellen'] if f['typ'] in ('ORT', 'PERSON')]
        out = self.hub.gateway_ausgabe({'name': 'Anfrage.txt', 'auswahl': auswahl, 'ziel': 'Anfrage_anonymisiert.txt'})
        fassung = (ablage.ordner(self.hub.project_root)['ausgang'] / 'Anfrage_anonymisiert.txt').read_text(encoding='utf-8')
        self.assertIn('<ORT_001>', fassung)
        self.assertNotIn('Beierswerder', fassung)
        self.assertNotIn('Lena Beispiel', fassung, 'gleiche Stellen werden überall ersetzt')
        self.assertEqual(fassung.count('<PERSON_001>'), 2)
        self.assertIn('DEF', fassung, 'das Ereignis bleibt')
        self.assertEqual(out['vermerk']['original_sha256'], self.hash_vorher)
        self.assertEqual(ablage.sha256_datei(self.original), self.hash_vorher, 'das Original bleibt')

    def test_behalten_keeps_a_place_and_bad_choices_are_refused(self):
        v = self.hub.gateway_vorschau({'name': 'Anfrage.txt'})
        orte = [f['id'] for f in v['fundstellen'] if f['typ'] == 'ORT']
        self.hub.gateway_ausgabe({'name': 'Anfrage.txt', 'auswahl': [{'id': orte[0], 'art': 'behalten'}], 'ziel': 'b.txt'})
        fassung = (ablage.ordner(self.hub.project_root)['ausgang'] / 'b.txt').read_text(encoding='utf-8')
        self.assertIn('Beierswerder', fassung)
        with self.assertRaisesRegex(ValueError, 'vorgabe_unbekannt'):
            self.hub.gateway_ausgabe({'name': 'Anfrage.txt', 'auswahl': [{'id': orte[0], 'art': 'löschen'}], 'ziel': 'c.txt'})
        with self.assertRaisesRegex(ValueError, 'fundstelle_unbekannt'):
            self.hub.gateway_ausgabe({'name': 'Anfrage.txt', 'auswahl': [{'id': 999, 'art': 'ersetzen'}], 'ziel': 'd.txt'})
