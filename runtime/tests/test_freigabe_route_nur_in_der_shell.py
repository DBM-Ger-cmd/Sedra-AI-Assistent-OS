"""Entscheidung des Captains (2026-10-19): ein Werkzeug beantwortet keine Freigabe selbst. Die Freigabe-Route steht nur in
den Shells (Schalter der Oberfläche), nicht in den Manifesten der Werkzeuge."""
import unittest
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix' / 'tools'
ROUTE = 'POST /api/decisions/answer'


class FreigabeRoute(unittest.TestCase):
    def test_no_tool_manifest_grants_the_decision_answer_route(self):
        for manifest in sorted(TOOLS.glob('*/tool.yaml')):
            doc = yaml.safe_load(manifest.read_text(encoding='utf-8')) or {}
            routes = (doc.get('tool') or {}).get('api') or []
            self.assertNotIn(ROUTE, routes, f'{manifest.parent.name} darf Freigaben nicht selbst beantworten')


if __name__ == '__main__':
    unittest.main()
