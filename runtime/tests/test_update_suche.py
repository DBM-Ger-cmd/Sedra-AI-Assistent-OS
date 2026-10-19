"""Die Update-Suche (Plan Abschnitt 4, Teil 1): nur lesen, nur auf Klick. Im Test kein Netzzugriff: die Tags werden eingespeist."""
import unittest

from guppi_runtime.update_suche import suche, versionen


class UpdateSuche(unittest.TestCase):
    def test_only_release_tags_count_and_they_are_sorted(self):
        tags = [{'name': 'v1.10.0'}, {'name': 'foo'}, {'name': 'v1.9.0'}, {'name': 'v1.21.0-rc1'}, {'name': 'v2.0.0'}]
        self.assertEqual([n for _, n in versionen(tags)], ['v1.9.0', 'v1.10.0', 'v2.0.0'])

    def test_a_newer_release_is_shown_and_not_applied(self):
        r = suche('1.21.0', tags_holen=lambda: [{'name': 'v1.21.0'}, {'name': 'v1.22.0'}])
        self.assertEqual((r['status'], r['neueste'], r['verfuegbar']), ('neu', 'v1.22.0', True))

    def test_the_installed_release_is_current(self):
        r = suche('1.21.0', tags_holen=lambda: [{'name': 'v1.21.0'}])
        self.assertEqual((r['status'], r['verfuegbar']), ('aktuell', False))

    def test_an_unreachable_github_changes_nothing_and_says_so(self):
        def offline():
            raise OSError('keine Verbindung')
        self.assertEqual(suche('1.21.0', tags_holen=offline)['status'], 'nicht_erreichbar')

    def test_no_release_yet_is_its_own_answer(self):
        self.assertEqual(suche('1.21.0', tags_holen=lambda: [])['status'], 'keine_releases')


if __name__ == '__main__':
    unittest.main()
