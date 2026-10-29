"""N8 der Harness-Shell Stufe 3: das Paket `lauf_fortschritt` (Bau von SEDRA im Pilot, ohne die ungenutzte Funktion) und die Referenz von Claude
(benchmarks/devvm_refs/harness_lauf_fortschritt) geben für dieselben Eingaben dieselben Ergebnisse – auch bei kaputten Eingaben. Hält den Bau fest wie bei N2."""
import importlib.util
import random
import unittest
from pathlib import Path

from guppi_runtime.harness import lauf_fortschritt

REF = Path(__file__).resolve().parents[1] / 'benchmarks' / 'devvm_refs' / 'harness_lauf_fortschritt' / 'lauf_fortschritt.py'
Z = {'art': 'zeilen', 'regex': r'(\d+)\s*/\s*(\d+)'}
P = {'art': 'prozent', 'regex': r'([\d.]+)\s*%'}
T = {'art': 'text'}
SAUBER = [Z, P, T]
KAPUTT = SAUBER + [None, 'x', {}, {'art': 'magie', 'regex': 'x'}, {'art': 'zeilen'}, {'art': 'zeilen', 'regex': '(['}, {'art': 'zeilen', 'regex': 5},
                   {'art': 'zeilen', 'regex': r'(\d+)'}, {'art': 'prozent', 'regex': r'(\d+)(\d+)'}, {'art': 'zeilen', 'regex': r'(\w)/(\w)'}, {'art': 'prozent', 'regex': r'(\w+)%'}]
TEILE = ['12/40', '3 / 10', '5/0', 'x', '', '  ', '42 %', '7.5%', '150 %', 'a/b', '1.5/3', '99/100', 'Start', 'Rauschen ' * 12, '10/20 fertig', '-5 %', '0/5', '1e2 %', '٣/٥']


def referenz():
    spec = importlib.util.spec_from_file_location('lauf_fortschritt_referenz', REF)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ergebnis(modul, zeilen, regel):
    try:
        return ('ok', modul.fortschritt_aus(zeilen, regel))
    except Exception as exc:
        return ('fehler', type(exc).__name__)


class VergleichTests(unittest.TestCase):
    def vergleiche(self, sauber, regeln):
        ref, z = referenz(), random.Random(7)
        abweichungen = []
        for _ in range(3000):
            if not sauber and z.random() < 0.15:
                zeilen = z.choice([None, 'x', 5, [None, 5, ['1/2']], ('1/2', '2/4'), {'1/2'}])
            else:
                zeilen = [z.choice(TEILE) for _ in range(z.randint(0, 5))]
            regel = z.choice(regeln)
            if ergebnis(lauf_fortschritt, zeilen, regel) != ergebnis(ref, zeilen, regel):
                abweichungen.append((zeilen, regel))
        self.assertEqual(abweichungen[:2], [], f'{len(abweichungen)} Abweichungen')

    def test_saubere_eingaben(self):
        self.vergleiche(True, SAUBER)

    def test_kaputte_eingaben(self):
        self.vergleiche(False, KAPUTT)

    def test_das_paket_hat_keinen_toten_code(self):
        quelltext = (Path(lauf_fortschritt.__file__)).read_text(encoding='utf-8')
        self.assertNotIn('def _gültige_regel', quelltext)


if __name__ == '__main__':
    unittest.main()
