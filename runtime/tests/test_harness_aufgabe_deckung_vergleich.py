"""N2 der Harness-Shell Stufe 3: das Paket `aufgabe_deckung` (Bau von SEDRA mit drei Korrekturen von Claude) und die Referenz von Claude
(benchmarks/devvm_refs/harness_aufgabe_deckung) geben für dieselben Eingaben dieselben Ergebnisse – auch bei kaputten Eingaben. Wie bei `einstufen`
hält dieser Vergleich den Bau fest: ändert jemand eines von beiden, muss es zum anderen passen."""
import importlib.util
import random
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from guppi_runtime.harness import aufgabe_deckung

REF = Path(__file__).resolve().parents[1] / 'benchmarks' / 'devvm_refs' / 'harness_aufgabe_deckung' / 'aufgabe_deckung.py'
J = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def referenz():
    spec = importlib.util.spec_from_file_location('aufgabe_deckung_referenz', REF)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def passt(m, w, z):
    if not isinstance(m, str):
        raise TypeError('kein Muster')
    return m == '**' or m == z or (m.endswith('**') and z.startswith(m[:-2]))


class Fall:
    def __init__(self, sauber, seed=20261029):
        self.sauber, self.z = sauber, random.Random(seed)

    def bis(self):
        z = self.z
        iso = lambda: (J + timedelta(minutes=z.randint(-90, 90))).isoformat()
        sauber = [None, None, iso(), iso(), '2026-10-29T13:00:00', 'kaputt', J.isoformat()]
        return z.choice(sauber if self.sauber else sauber + [5, True, [], J + timedelta(hours=1), J - timedelta(hours=1)])

    def aufgabe(self, i):
        z, s = self.z, self.sauber
        t = {'id': z.choice(['T-%08d' % i, 'T-%08d' % z.randint(0, 5), 'T-%08d' % i]),
             'sitzungen': z.choice([['S-1'], ['S-1', 'S-2'], ['S-2'], []] + ([] if s else ['S-1'])),
             'erlaubt': [z.choice([{'werkzeug': 'datei_schreiben', 'muster': 'docs/**'}, {'werkzeug': 'datei_aendern', 'muster': 'docs/a.md'},
                                   {'werkzeug': 'datei_schreiben', 'muster': 'x'}] + ([] if s else [{'werkzeug': 'datei_schreiben', 'muster': 5}, 'kaputt', {'werkzeug': 'datei_schreiben'}]))
                         for _ in range(z.randint(0, 3))],
             'status': z.choice(['aktiv'] * 6 + ['erledigt', 'abgelaufen', 'zurueckgenommen'] + ([] if s else [5, None])),
             'aufrufe': z.choice([0, 1, 2, 3, 3] + ([] if s else ['x', True, None])),
             'ende': {'bis': self.bis(), 'max_aufrufe': z.choice([None, None, 1, 2, 3] + ([] if s else ['x', True, 2.5]))}}
        if not s and z.random() < 0.03:
            del t['id']
        if not s and z.random() < 0.05:
            t['ende'] = z.choice([None, 'x', 5, {}])
        return t


def ergebnis(modul, name, *args):
    try:
        return ('ok', getattr(modul, name)(*args))
    except Exception as exc:
        return ('fehler', type(exc).__name__)


class VergleichTests(unittest.TestCase):
    def vergleiche(self, sauber):
        ref, fall, z = referenz(), None, None
        fall = Fall(sauber)
        z, faelle, abweichungen = fall.z, 0, []
        for n in range(800):
            aufgaben = [fall.aufgabe(n * 10 + i) for i in range(z.randint(0, 5))]
            for a in aufgaben:
                faelle += 1
                if ergebnis(aufgabe_deckung, 'zustand', a, J) != ergebnis(ref, 'zustand', a, J):
                    abweichungen.append(('zustand', a))
            args = (aufgaben, z.choice(['S-1', 'S-2']), z.choice(['datei_schreiben', 'datei_aendern']), z.choice(['docs/a.md', 'docs/b/c.md', 'runtime/x.py']), J, passt)
            faelle += 1
            if ergebnis(aufgabe_deckung, 'deckt', *args) != ergebnis(ref, 'deckt', *args):
                abweichungen.append(('deckt', aufgaben))
        self.assertGreater(faelle, 2500)
        self.assertEqual(abweichungen[:2], [], f'{len(abweichungen)} Abweichungen')

    def test_saubere_eingaben(self):
        self.vergleiche(True)

    def test_kaputte_eingaben(self):
        self.vergleiche(False)

    def test_das_paket_wirft_nie(self):
        for muell in (None, 'x', 5, [], {}, {'status': 'aktiv'}, {'status': 'aktiv', 'ende': 'kaputt'}, {'status': 'aktiv', 'sitzungen': ['S-1'], 'erlaubt': ['x', None]}):
            aufgabe_deckung.zustand(muell, J)
            self.assertIsNone(aufgabe_deckung.deckt([muell], 'S-1', 'datei_schreiben', 'docs/a.md', J, passt))


if __name__ == '__main__':
    unittest.main()
