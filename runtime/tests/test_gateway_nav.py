"""KI GateWay: die Reihenfolge der Ansichten (nav.js), wie sie im Baum links stehen."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

NODE = shutil.which('node')
NAV = Path(__file__).resolve().parents[1] / 'src' / 'guppi_runtime' / 'uix' / 'tools' / 'gateway' / 'nav.js'


def run_node(script):
    out = subprocess.run([NODE, '-e', script], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout.strip().splitlines()[-1])


@unittest.skipIf(NODE is None, 'node ist nicht installiert')
class NavMenue(unittest.TestCase):
    def test_das_menue_hat_die_bereiche_aus_der_skizze(self):
        script = f"const n=require({json.dumps(str(NAV))});console.log(JSON.stringify(n.MENU.map(m=>m[0])));"
        self.assertEqual(run_node(script), ['uebersicht', 'vorgaenge', 'dateien', 'regeln', 'ausprobieren', 'verlauf'])


if __name__ == '__main__':
    unittest.main()
