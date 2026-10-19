"""KI GateWay: das linke Menü. Die Zahlen der Übersicht und der Filter aus den Kacheln (nav.js) werden mit node geprüft."""
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
class NavZahlen(unittest.TestCase):
    def test_zaehlt_die_zustaende_und_die_wege(self):
        liste = [
            {'erstellt': '2026-10-19T09:00:00', 'zustand': 'NEU', 'weg': None, 'klasse': None},
            {'erstellt': '2026-10-19T10:00:00', 'zustand': 'GEPRUEFT', 'weg': None, 'klasse': 'S1'},
            {'erstellt': '2026-10-19T11:00:00', 'zustand': 'GESPERRT', 'weg': None, 'klasse': 'S3'},
            {'erstellt': '2026-10-18T11:00:00', 'zustand': 'ENTWURF', 'weg': 'LOCAL_ONLY', 'klasse': 'S1'},
            {'erstellt': '2026-10-18T12:00:00', 'zustand': 'WARTET', 'weg': 'CLOUD_ALLOWED', 'klasse': 'S1'},
            {'erstellt': '2026-10-18T13:00:00', 'zustand': 'ABGESCHLOSSEN', 'weg': 'LOCAL_ONLY', 'klasse': 'S0'},
        ]
        script = f"const n=require({json.dumps(str(NAV))});console.log(JSON.stringify(n.zaehle({json.dumps(liste)},'2026-10-19')));"
        z = run_node(script)
        self.assertEqual(z['heute'], 3)                  # drei Anfragen vom 19.10.
        self.assertEqual(z['heuteGeprueft'], 2)          # davon mit Einstufung
        self.assertEqual((z['neu'], z['geprueft'], z['gesperrt'], z['entwurf']), (1, 1, 1, 1))
        self.assertEqual(z['wartet'], 4)                 # NEU, GEPRUEFT, ENTWURF und WARTET warten auf dich
        self.assertEqual((z['lokal'], z['cloud']), (2, 1))

    def test_ein_filter_passt_nur_zu_seinem_zustand(self):
        script = (f"const n=require({json.dumps(str(NAV))});"
                  "const v={zustand:'GEPRUEFT'};"
                  "console.log(JSON.stringify([n.passt(v,null),n.passt(v,'freigabe'),n.passt(v,'neu'),n.passt(v,'unbekannt')]));")
        self.assertEqual(run_node(script), [True, True, False, False])

    def test_das_menue_hat_die_bereiche_aus_der_skizze(self):
        script = f"const n=require({json.dumps(str(NAV))});console.log(JSON.stringify(n.MENU.map(m=>m[0])));"
        self.assertEqual(run_node(script), ['uebersicht', 'vorgaenge', 'dateien', 'regeln', 'ausprobieren', 'verlauf'])


if __name__ == '__main__':
    unittest.main()
