import unittest

from guppi_runtime import uix_server


class FriendlyErrors(unittest.TestCase):
    def test_the_two_decision_codes_have_a_sentence(self):
        for code in ('unknown_decision', 'way_not_offered'):
            self.assertIn(code, uix_server.FRIENDLY_400)
            self.assertNotIn('_', uix_server.FRIENDLY_400[code])


if __name__ == '__main__':
    unittest.main()
