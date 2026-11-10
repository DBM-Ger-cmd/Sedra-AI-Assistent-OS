"""Modellmenue der Harness (uix/shells/harness/modell.js): jede Zeile der Liste ist unterscheidbar, Passendes steht zuerst, kein Rohcode im Urteil.
Die reinen Funktionen laufen unter node, ohne Seite und Browser; ohne node wird uebersprungen."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from host_isolation import setUpModule, tearDownModule  # noqa: F401

JS = Path(__file__).resolve().parents[1] / 'src' / 'sedra_runtime' / 'uix' / 'shells' / 'harness' / 'modell.js'
Q = 'qwen3.6-35b-a3b'
REZEPTE = [
    {'id': 'coder.local_primary', 'modell': Q, 'slots': 3, 'kontexte': [32768, 61440, 102400], 'passt': False, 'grund': 'vram_insufficient'},
    {'id': 'coder.local_primary_1x80k', 'modell': Q, 'slots': 1, 'kontexte': [32768, 61440, 102400], 'passt': False, 'grund': 'vram_insufficient'},
    {'id': 'coder.local_primary_power', 'modell': Q, 'slots': 1, 'kontexte': [61440, 102400, 126976], 'passt': True},
    {'id': 'coder.local_primary_team', 'modell': Q, 'slots': 3, 'kontexte': [32768, 61440, 98304], 'passt': True},
    {'id': 'coder.local_primary_4x32k', 'modell': Q, 'slots': 4, 'kontexte': [32768, 61440], 'passt': False, 'grund': 'vram_insufficient'},
    {'id': 'coder.llama_qwen35', 'modell': 'qwen3.5-9b-mtp', 'slots': 2, 'kontexte': [32768], 'passt': True},
    {'id': 'coder.local_qwen3_5_9b_q6_k', 'modell': 'qwen3.5-9b-q6_k', 'slots': 1, 'kontexte': [32768], 'passt': True},
    {'id': 'harness.nemotron_e4b', 'modell': 'nvidia/nemotron-3.5-bolt-e4b', 'slots': 2, 'kontexte': [102400], 'passt': True},
    {'id': 'harness.nemotron_e4b_3x80k', 'modell': 'nvidia/nemotron-3.5-bolt-e4b', 'slots': 3, 'kontexte': [81920], 'passt': True},
    {'id': 'harness.nemotron_e4b_team', 'modell': 'nvidia/nemotron-3.5-bolt-e4b', 'slots': 3, 'kontexte': [131072], 'passt': True},
]
SKRIPT = """
globalThis.window = undefined;
require(%s);
const M = globalThis.sedraHarness.modell;
const rezepte = %s;
const urteil = r=>r.passt ? '✓ passt' : '✗ passt nicht: ' + M.grundtext(r.grund);
const sortiert = [...rezepte].sort(M.reihenfolge);
console.log(JSON.stringify({zeilen: sortiert.map(r=>({id: r.id, passt: r.passt, text: M.optionsText(r, urteil(r))})), roh: M.grundtext('vram_insufficient')}));
"""


@unittest.skipUnless(shutil.which('node'), 'node fehlt')
class MenueListe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(['node', '-e', SKRIPT % (json.dumps(str(JS)), json.dumps(REZEPTE))], capture_output=True, text=True, encoding='utf-8', timeout=60)
        assert out.returncode == 0, out.stderr
        cls.erg = json.loads(out.stdout)
        cls.zeilen = cls.erg['zeilen']

    def test_keine_zwei_zeilen_gleich(self):
        texte = [z['text'] for z in self.zeilen]
        self.assertEqual(len(texte), len(set(texte)), texte)

    def test_passendes_vor_nicht_passendem_je_gruppe(self):
        for gruppe in (('coder.local_primary', 'coder.llama_qwen35', 'coder.local_qwen3_5_9b_q6_k'),):
            reihe = [z['passt'] for z in self.zeilen if z['id'].startswith('coder.')]
            self.assertEqual(reihe, sorted(reihe, reverse=True), reihe)

    def test_power_und_team_stehen_vor_den_bau_rezepten(self):
        ids = [z['id'] for z in self.zeilen if z['id'].startswith('coder.local_primary')]
        self.assertEqual(ids[:2], ['coder.local_primary_power', 'coder.local_primary_team'])
        self.assertLess(ids.index('coder.local_primary_1x80k'), ids.index('coder.local_primary_4x32k'))

    def test_kein_rohcode_im_urteil(self):
        for z in self.zeilen:
            self.assertNotIn('vram_insufficient', z['text'])
        self.assertEqual(self.erg['roh'], 'zu wenig freier Grafikspeicher')

    def test_zeile_nennt_kurzname_modell_kanaele_und_fenster(self):
        power = next(z['text'] for z in self.zeilen if z['id'].endswith('power'))
        self.assertEqual(power, f'Power – {Q} · 1 Kanal · bis 124k · ✓ passt')
        team = next(z['text'] for z in self.zeilen if z['id'].endswith('local_primary_team'))
        self.assertIn('Team', team); self.assertIn('3 Kanäle', team); self.assertIn('bis 96k', team)


if __name__ == '__main__':
    unittest.main()
