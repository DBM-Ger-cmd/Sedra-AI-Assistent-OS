import unittest

from guppi_runtime.redesign_prep import pseudonymize, restore


class OwnTerms(unittest.TestCase):
    def test_findings_become_named_terms_and_the_original_is_not_in_the_text(self):
        text = "Kontakt: max.mustermann@example.com und noch einmal max.mustermann@example.com. Sonst nichts."
        clean, mapping = pseudonymize(text)
        self.assertIsNotNone(mapping)
        self.assertNotIn('max.mustermann@example.com', clean)
        self.assertEqual(clean.count('[PERSON-001]'), 2, 'the same value gets the same term everywhere')
        self.assertEqual(mapping['[PERSON-001]'], 'max.mustermann@example.com')

    def test_restore_brings_the_originals_back(self):
        text = "Schreib an max.mustermann@example.com bitte."
        clean, mapping = pseudonymize(text)
        self.assertEqual(restore(clean, mapping), text)

    def test_clean_text_stays_clean(self):
        clean, mapping = pseudonymize("Ein ganz normaler Satz ohne Auffälligkeiten.")
        self.assertEqual(clean, "Ein ganz normaler Satz ohne Auffälligkeiten.")
        self.assertEqual(mapping, {})


if __name__ == '__main__':
    unittest.main()
