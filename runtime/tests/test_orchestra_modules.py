"""Abnahme der Orchestrierungs-Module gegen `src` (Spec 1, D1.7: ORC-02, 03, 05, 06, 08, 10, 11, 17, 18 stecken in den versteckten Tests der Bau-Specs).

Die SEDRA-Bauten `s1_*` wurden beim Bau gegen den Kandidaten geprüft; nach der Übernahme in `guppi_runtime/orchestra/` lief ihre
Abnahme nie wieder. Dieser Test führt die versteckten Tests der letzten Stufe jeder Spec gegen den übernommenen Code aus:
die Module werden in einen temporären Ordner kopiert (nur die relativen Importe werden zu einfachen Namen, wie die Specs sie
brauchen), jede versteckte Datei läuft als `python <datei>` mit diesem Ordner als Arbeitsordner, Exit-Code 0 = bestanden.

Neue Module bekommen ihren Eintrag in SPECS (Schritt 'Abnahme beim Übernehmen', Vorschlag Bauweg 2026-10-25)."""
import re
import tempfile
import unittest
from pathlib import Path

import bau_abnahme

RUNTIME = Path(__file__).resolve().parents[1]
ORCHESTRA = RUNTIME / 'src' / 'guppi_runtime' / 'orchestra'
SPECS = ('s1_graphs', 's1_wakeplan', 's1_decompose', 's1_cron', 's1_org', 's1_board', 's1_heartbeat', 's1_messages', 's1_routines',
         's1_budget', 's1_runner')
PURE = ('board', 'budget', 'budgetcalc', 'chain', 'cron', 'decompose', 'graphs', 'heartbeat', 'messages', 'org', 'routines', 'runner',
        'store', 'wakeplan')                        # ohne guppi_runtime-Importe; service, tick und config gehören zum Desk
SEED = RUNTIME / 'benchmarks' / 's1_schema2_seed'
# Bekannte, gewollte Abweichungen von den versteckten Tests (spätere Spezifikationen, die den Bau-Spec nicht kannte): (Datei, Muster, Ersatz, Grund).
# Jede Abweichung steht hier mit Grund; eine neue Abweichung ist ein Befund, kein Grund, den Test zu lockern.
KNOWN = (
    ('hidden_runner_3.py', r'("recherche_urls": (?:None|\[[^\]]*\]), "fertig": (?:True|False))\}', r'\1, "wissen_vorschlag": None}',
     'Spec 7 (D7.8): `runner.outcome` reicht `wissen_vorschlag` weiter, der Bau-Spec kennt das Feld nicht'),
)


class Modules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='orchestra-modules-')
        cls.tree = Path(cls.tmp.name)
        bau_abnahme.plain_tree(ORCHESTRA, PURE, cls.tree)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_hidden(self, spec):
        return bau_abnahme.run_hidden(spec, self.tree, PURE, KNOWN)

    def test_the_hidden_acceptance_of_each_build_spec_passes_against_src(self):
        for spec in SPECS:
            with self.subTest(spec=spec):
                failed = {n: tail for n, (code, tail) in self.run_hidden(spec).items() if code != 0}
                self.assertEqual(failed, {})

    def test_the_tree_has_only_plain_imports(self):
        for name in PURE:
            text = (self.tree / f'{name}.py').read_text(encoding='utf-8')
            self.assertIsNone(re.search(r'^from \.', text, flags=re.M), name)
            self.assertNotIn('guppi_runtime', text, name)


if __name__ == '__main__':
    unittest.main()
