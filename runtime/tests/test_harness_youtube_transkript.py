"""`youtube_transkript` im Chat (04.11.2026): lesen, ohne Karte; das Ergebnis ist ein Ausschnitt mit Kopf, der Text gilt als fremde Daten."""
import unittest

from sedra_runtime.harness.werkzeuge import NAMEN, SCHEMAS
from sedra_runtime.harness.katalog import OHNE_KARTE


class Namen(unittest.TestCase):
    def test_das_werkzeug_ist_bekannt_und_laeuft_ohne_karte(self):
        self.assertIn('youtube_transkript', NAMEN)
        self.assertIn('youtube_transkript', OHNE_KARTE)
        self.assertEqual(SCHEMAS['youtube_transkript']['function']['parameters']['required'], ['video'])


if __name__ == '__main__':
    unittest.main()
