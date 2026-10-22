"""Budgetrechnung (Spec 1, D1.1 `budgetcalc.py`, ORC-09, S1.C2): rein, Text byte-gleich mit der Saat
`benchmarks/s1_schema2_seed/budgetcalc.py`. Summen je Zeitraum, Prozent, Stufe, Vorabprüfung gegen die Ausgabegrenze des Laufs,
Schwellen nur beim Steigen, Ansicht für den Desk."""
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.orchestra import budgetcalc

RUNTIME = Path(__file__).resolve().parents[1]
SEED = RUNTIME / 'benchmarks' / 's1_schema2_seed' / 'budgetcalc.py'
PACKAGE = RUNTIME / 'src' / 'guppi_runtime' / 'orchestra' / 'budgetcalc.py'
NOW = '2026-10-21T08:00:00Z'
ROWS = [{'ts': '2026-09-30T23:59:59Z', 'tokens_in': 100, 'tokens_out': 50, 'eur_cent': 3, 'requests': 1, 'estimated': 0},
        {'ts': '2026-10-01T00:00:00Z', 'tokens_in': 10, 'tokens_out': 20, 'eur_cent': 0, 'requests': 2, 'estimated': 1},
        {'ts': '2026-10-21T07:00:00Z', 'tokens_out': 5}]


class SameAsSeed(unittest.TestCase):
    def test_the_package_text_is_the_seed(self):
        norm = lambda p: p.read_bytes().replace(b'\r\n', b'\n')  # noqa: E731
        self.assertEqual(norm(PACKAGE), norm(SEED))

    def test_pure_no_imports(self):
        self.assertNotIn('import', PACKAGE.read_text(encoding='utf-8'))


class Totals(unittest.TestCase):
    def test_whole_period_counts_everything(self):
        self.assertEqual(budgetcalc.totals(ROWS, 'gesamt', NOW), {'tokens': 185, 'eur_cent': 3, 'requests': 4, 'estimated': 1})

    def test_month_counts_only_the_running_utc_month(self):
        self.assertEqual(budgetcalc.totals(ROWS, 'monat', NOW), {'tokens': 35, 'eur_cent': 0, 'requests': 3, 'estimated': 1})

    def test_no_rows_and_unknown_period(self):
        self.assertEqual(budgetcalc.totals([], 'monat', NOW), {'tokens': 0, 'eur_cent': 0, 'requests': 0, 'estimated': 0})
        with self.assertRaisesRegex(ValueError, '^budget_period_unknown$'):
            budgetcalc.totals(ROWS, 'woche', NOW)


class PercentAndStage(unittest.TestCase):
    def test_percent(self):
        cases = [((0, None), None), ((5, None), None), ((0, 100), 0), ((79, 100), 79), ((80, 100), 80), ((199, 200), 99),
                 ((150, 100), 150), ((0, 0), 100), ((1, -5), 100)]
        for (used, limit), want in cases:
            with self.subTest(used=used, limit=limit):
                self.assertEqual(budgetcalc.percent(used, limit), want)

    def test_stage(self):
        cases = [(None, 'ok'), (0, 'ok'), (79, 'ok'), (80, 'warnung'), (99, 'warnung'), (100, 'gestoppt'), (130, 'gestoppt')]
        for pct, want in cases:
            with self.subTest(pct):
                self.assertEqual(budgetcalc.stage(pct, 80, 100), want)
        self.assertEqual(budgetcalc.stage(50, 50, 50), 'gestoppt', 'stop gewinnt bei gleichen Schwellen')


class Precheck(unittest.TestCase):
    def test_rest_must_cover_the_run_cap(self):
        self.assertIsNone(budgetcalc.precheck(1000, 200, 800))
        self.assertIsNone(budgetcalc.precheck(None, 10 ** 9, 4096), 'ohne Grenze immer')
        for limit, used, cap in ((1000, 201, 800), (100, 100, 1), (0, 0, 1)):
            with self.subTest(limit=limit, used=used, cap=cap):
                with self.assertRaisesRegex(ValueError, '^budget_insufficient$'):
                    budgetcalc.precheck(limit, used, cap)


class Crossing(unittest.TestCase):
    def test_only_when_rising_over_a_threshold(self):
        cases = [((70, 79), None), ((70, 80), 'warnung'), ((79, 99), 'warnung'), ((80, 90), None), ((90, 100), 'stopp'),
                 ((70, 120), 'stopp'), ((100, 110), None), ((None, 85), 'warnung'), ((50, None), None), ((90, 70), None)]
        for (before, after), want in cases:
            with self.subTest(before=before, after=after):
                self.assertEqual(budgetcalc.crossing(before, after, 80, 100), want)


class View(unittest.TestCase):
    def test_the_stricter_share_decides(self):
        agent = {'budget_tokens': 1000, 'budget_eur_cent': 10, 'budget_period': 'monat'}
        out = budgetcalc.view(agent, {'tokens': 500, 'eur_cent': 9, 'requests': 3, 'estimated': 0}, 80, 100)
        self.assertEqual(out, {'grenze_token': 1000, 'verbraucht_token': 500, 'grenze_eur_cent': 10, 'verbraucht_eur_cent': 9,
                               'prozent': 90, 'stufe': 'warnung', 'zeitraum': 'monat'})

    def test_without_limits_there_is_no_percent(self):
        out = budgetcalc.view({}, {'tokens': 7, 'eur_cent': 0, 'requests': 1, 'estimated': 0}, 80, 100)
        self.assertEqual(out, {'grenze_token': None, 'verbraucht_token': 7, 'grenze_eur_cent': None, 'verbraucht_eur_cent': 0,
                               'prozent': None, 'stufe': 'ok', 'zeitraum': 'gesamt'})

    def test_only_tokens_limited(self):
        out = budgetcalc.view({'budget_tokens': 100, 'budget_eur_cent': None, 'budget_period': 'gesamt'},
                              {'tokens': 100, 'eur_cent': 500, 'requests': 1, 'estimated': 0}, 80, 100)
        self.assertEqual((out['prozent'], out['stufe']), (100, 'gestoppt'))


if __name__ == '__main__':
    unittest.main()
