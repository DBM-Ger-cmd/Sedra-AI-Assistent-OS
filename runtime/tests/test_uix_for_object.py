"""Folgeaufgaben zu Nachtrag N1 (Spec 0, F2/F3): wo die Shell ein Objekt kennt, fragt sie `registry.forObject(objekt)` statt
`registry.for(typ)` – so zählt `typ:alle`, `typ:*`, `typ:<id>` auch im Cockpit, im Minimal und im Rahmen. Und jeder Ort steht
in der Palette des Cockpits einmal (der Ort `labor` kam mit G2-S4-21 in ui/places.js und stand im Cockpit ein zweites Mal)."""
import re
import unittest
from pathlib import Path

UIX = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix'
WITH_OBJECT = (UIX / 'shells' / 'cockpit' / 'dock.js', UIX / 'shells' / 'minimal' / 'windows.js', UIX / 'ui' / 'frame.js')
PLACE_ID = re.compile(r"\{\s*id:\s*'([a-z0-9_-]+)'")


class ForObject(unittest.TestCase):
    def test_the_shells_ask_for_the_object_not_the_type(self):
        for path in WITH_OBJECT:
            with self.subTest(path.name):
                text = path.read_text(encoding='utf-8')
                self.assertNotIn('tools.for(', text)
                self.assertIn('tools.forObject(', text)

    def test_every_place_of_the_cockpit_palette_is_there_once(self):
        contract = PLACE_ID.findall((UIX / 'ui' / 'places.js').read_text(encoding='utf-8'))
        palette = (UIX / 'shells' / 'cockpit' / 'palette.js').read_text(encoding='utf-8')
        own = PLACE_ID.findall(palette[palette.index('PLACES.concat(['):palette.index(']);')])
        self.assertIn('labor', contract)
        self.assertEqual(own, ['master', 'runs'])
        ids = contract + own
        self.assertEqual(sorted({i for i in ids if ids.count(i) > 1}), [])


if __name__ == '__main__':
    unittest.main()
