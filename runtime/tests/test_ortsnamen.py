"""Ortsnamen nach der Spezifikation Gateway, Abschnitt 6b: O-1 ersetzt Anschrift und Wohnort, O-2 lässt Ereignisse und Themen stehen."""
import unittest

from guppi_runtime.core.b6core import pseudo
from guppi_runtime.core.b6core.privacy import scan_text


def orte(text):
    return [text[a:b] for a, b, k in pseudo._orte_spans(text) if k == 'ORT']


def ersetzt(text):
    res = pseudo.pseudonymize(text, scan_text('T', text))
    return res.text


class OrtsnamenRegeln(unittest.TestCase):
    def test_o1_a_town_after_a_street_number_is_a_place_of_residence(self):
        self.assertEqual(orte('Ich wohne in der Hauptstraße 1 in Beierswerder.'), ['Beierswerder'])

    def test_o1_a_town_after_a_postcode_is_replaced(self):
        self.assertEqual(orte('Lieferadresse: Hauptstr. 1, 12345 Beierswerder'), ['Beierswerder'])

    def test_o1_a_street_name_is_an_address_not_a_place(self):
        text = 'Ich wohne in der Straße XYZ und ...'
        self.assertEqual([(k, text[a:b]) for a, b, k in pseudo._orte_spans(text)], [('ADDRESS', 'XYZ')])

    def test_o2_an_event_in_a_place_is_kept(self):
        text = 'Gestern Abend hat es in DEF geknallt, ich wollte wissen, ob etwas passiert ist.'
        self.assertEqual(orte(text), [], 'ein Ereignis ist kein Personenbezug')
        self.assertIn('in DEF geknallt', ersetzt(text))

    def test_o2_a_question_about_a_place_is_kept(self):
        self.assertEqual(orte('Wetter in Beierswerder?'), [])
        self.assertIn('Wetter in Beierswerder', ersetzt('Wetter in Beierswerder?'))

    def test_the_resident_place_becomes_a_placeholder_in_the_text(self):
        out = ersetzt('Ich wohne in der Hauptstraße 1 in Beierswerder.')
        self.assertIn('<ORT_001>', out)
        self.assertNotIn('Beierswerder', out)


if __name__ == '__main__':
    unittest.main()
