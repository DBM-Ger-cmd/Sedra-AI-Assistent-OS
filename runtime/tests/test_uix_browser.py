"""The UIX in a real browser (benchmarks/uix_check.py): the Cockpit loads, every tool fills its container, cleans up after itself and
stays inside its allowlist. Skipped when playwright or a browser is missing, so the suite still runs on a PC without them; with them it
is the acceptance for every UIX change (SHELL_WERKZEUG_VERTRAG_v1 §8; Claude 2026-10-13: the static tests did not see a chat window
without a title bar, and since Build 7 they would not see a tool that leaves its container behind)."""
import sys
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))


class UIXBrowserTest(unittest.TestCase):
    def test_every_tool_keeps_the_contract_in_a_real_browser(self):
        try:
            import playwright  # noqa: F401
        except ImportError:
            self.skipTest('playwright is not installed')
        import uix_check
        lines = []
        url, stop = uix_check.start_server(lines.append, shell='cockpit')     # der Vertragstest braucht eine Shell, die Werkzeuge zeigt
        self.addCleanup(stop)
        try:
            results = uix_check.run_checks(url, say=lines.append, shell='cockpit')
        except RuntimeError as exc:                     # playwright without a browser
            if 'no browser' in str(exc): self.skipTest(str(exc))
            raise
        bad = [f'{n}: {d}' for n, ok, d in results if ok is False]      # None heißt „nicht geprüft“, nicht „gefallen“
        self.assertEqual(bad, [], '\n'.join(lines))
        self.assertGreaterEqual(len(results), 13)


if __name__ == '__main__':
    unittest.main()
