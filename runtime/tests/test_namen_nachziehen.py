"""Werkzeug, das den Namenswechsel in einem älteren Branch nachzieht."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('namen_nachziehen', REPO / 'runtime/benchmarks/namen_nachziehen.py')
nn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nn)
G = nn._G


class Nachziehen(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def schreibe(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8', newline='')
        return p

    def test_inhalt_wird_ersetzt_verlauf_bleibt(self):
        neu_datei = self.schreibe('runtime/src/x.py', f'import {G.lower()}_runtime\nX = "{G}_OS"\n# {G.capitalize()}\n')
        logbuch = self.schreibe('docs/LOGBUCH_AGENT_MANAGER.md', f'{G} alt\n')
        bericht = self.schreibe(f'docs/BERICHT_{G}_2026-10-01.md', f'{G} Bericht\n')
        pruef = self.schreibe('PRUEFSUMMEN.sha256', f'abc  {G.lower()}.txt\n')
        r = nn.nachziehen(self.root)
        self.assertEqual(neu_datei.read_text(encoding='utf-8'), 'import sedra_runtime\nX = "SEDRA_OS"\n# Sedra\n')
        self.assertEqual(logbuch.read_text(encoding='utf-8'), f'{G} alt\n')
        self.assertEqual(bericht.read_text(encoding='utf-8'), f'{G} Bericht\n')
        self.assertEqual(pruef.read_text(encoding='utf-8'), f'abc  {G.lower()}.txt\n')
        self.assertEqual(r['inhalt_geaendert'], ['runtime/src/x.py'])

    def test_probelauf_aendert_nichts(self):
        datei = self.schreibe('a.txt', f'{G}\n')
        r = nn.nachziehen(self.root, dry=True)
        self.assertEqual(datei.read_text(encoding='utf-8'), f'{G}\n')
        self.assertEqual(r['inhalt_geaendert'], ['a.txt'])

    def test_doppelung_wird_aufgeloest_und_zweiter_lauf_tut_nichts(self):
        datei = self.schreibe('b.md', f'Kompatibilitaet SEDRA/{G}\n')
        nn.nachziehen(self.root)
        self.assertEqual(datei.read_text(encoding='utf-8'), 'Kompatibilitaet SEDRA\n')
        self.assertEqual(nn.nachziehen(self.root)['inhalt_geaendert'], [])


if __name__ == '__main__':
    unittest.main()
