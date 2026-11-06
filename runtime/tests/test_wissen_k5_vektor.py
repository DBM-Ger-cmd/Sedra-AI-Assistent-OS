"""K5-6 Weg A (SPEC_WISSEN_KERN_v1 WK-23; G2 K5 §2.6, D-K5-2): die numpy-Matrix liefert dieselbe Reihenfolge wie reines Python (auch mit
Filter, Gleichstand nach kleinerer nr, k größer als die Menge, leer); falsche Länge der Anfrage ist ein Fehler; `suche.numpy: aus` schaltet auf
reines Python; die Suche im Speicher nutzt die Matrix und verwirft ihren Cache, wenn neue Vektoren dazukommen; der Stand nennt die Art.
Ohne numpy werden die Matrix-Fälle übersprungen, der Rückfall wird trotzdem geprüft."""
import importlib.util
import random
import tempfile
import unittest
from pathlib import Path

from sedra_runtime.wissen import vektor, vektor_np
from wissen_fixture import FakeEmbedServer, alle_freigeben, oeffnen

NP = importlib.util.find_spec('numpy') is not None
DIM = 16


def zufall(n, seed=3):
    r = random.Random(seed)
    return [(i + 1, vektor.packe([r.gauss(0, 1) for _ in range(DIM)])) for i in range(n)]


@unittest.skipUnless(NP, 'numpy fehlt')
class Matrix(unittest.TestCase):
    def test_gleiche_reihenfolge_wie_reines_python(self):
        blobs = zufall(500)
        liste = [(nr, vektor.lese(b, DIM)) for nr, b in blobs]
        m = vektor_np.Matrix(blobs, DIM)
        q = vektor.normiere([random.Random(9).gauss(0, 1) for _ in range(DIM)])
        for erlaubt in (None, set(range(1, 501, 7)), {3}):
            py = vektor.top_k(q, liste, 20, erlaubt=(None if erlaubt is None else erlaubt.__contains__))
            npy = m.top_k(q, 20, erlaubt=erlaubt)
            self.assertEqual([nr for nr, _ in npy], [nr for nr, _ in py])
            for (_, a), (_, b) in zip(npy, py):
                self.assertAlmostEqual(a, b, places=5)

    def test_gleichstand_grenzen_und_fehler(self):
        b = vektor.packe([1.0] + [0.0] * (DIM - 1))
        m = vektor_np.Matrix([(7, b), (3, b), (5, b)], DIM)
        self.assertEqual([nr for nr, _ in m.top_k([1.0] + [0.0] * (DIM - 1), 10)], [3, 5, 7], 'Gleichstand: kleinere nr zuerst; k > n')
        self.assertEqual(m.top_k([1.0] + [0.0] * (DIM - 1), 2, erlaubt=set()), [])
        self.assertEqual(vektor_np.Matrix([], DIM).top_k([1.0] * DIM, 5), [])
        with self.assertRaisesRegex(ValueError, 'wis_vektor_dim'):
            m.top_k([1.0, 0.0], 2)
        with self.assertRaisesRegex(ValueError, 'wis_k_ungueltig'):
            m.top_k([1.0] * DIM, 0)
        self.assertEqual(len(vektor_np.Matrix([(1, b), (2, b'kurz')], DIM)), 1, 'ein kaputter Blob fällt weg')


class ImSpeicher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wissen-k5-vek-')
        self.addCleanup(self.tmp.cleanup)
        self.srv = FakeEmbedServer(lazy=True)
        self.srv.__enter__()
        self.addCleanup(self.srv.__exit__, None, None, None)
        self.sp = oeffnen(self.tmp.name, self.srv.port, server=self.srv)
        self.addCleanup(self.sp.schliessen)
        alle_freigeben(self.sp)
        self.sp.abgleich()
        self.sp.einbetten_schritt()
        self.leser = {'art': 'captain', 'stufe': 6, 'projekt': None, 'agent_id': None}

    def test_python_und_numpy_finden_dasselbe(self):
        self.sp.konfig.numpy = 'aus'
        self.assertEqual(self.sp.vektorsuche(), 'python')
        py = self.sp.suche('Lease Testlabor', leser=self.leser)
        self.assertEqual(py['modus'], 'hybrid')
        if not NP:
            return
        self.sp.konfig.numpy = 'auto'
        self.assertEqual(self.sp.vektorsuche(), 'numpy')
        self.assertEqual(self.sp.stand()['vektorsuche'], 'numpy')
        npy = self.sp.suche('Lease Testlabor', leser=self.leser)
        self.assertEqual([t['id'] for t in npy['treffer']], [t['id'] for t in py['treffer']])

    @unittest.skipUnless(NP, 'numpy fehlt')
    def test_neue_vektoren_verwerfen_den_cache(self):
        self.sp.suche('Lease', leser=self.leser)
        vorher = len(self.sp._matrix)
        p = self.sp.repo_root / 'docs' / 'neu.md'
        p.write_text('# Neu\n\n## Kühlung\n\nDie Kühlung der Karte prüft der Wächter jede Minute.\n', encoding='utf-8')
        self.sp.abgleich()
        self.sp.einbetten_schritt()
        self.sp.suche('Kühlung', leser=self.leser)
        self.assertGreater(len(self.sp._matrix), vorher)

    def test_schalter_in_der_konfiguration(self):
        from sedra_runtime.wissen import konfig
        paket = Path(__file__).resolve().parents[1] / 'config' / 'wissen.yaml'
        self.assertEqual(konfig.load(paket).numpy, 'auto')
        with tempfile.TemporaryDirectory() as t:
            kaputt = Path(t) / 'w.yaml'
            kaputt.write_text(paket.read_text(encoding='utf-8').replace('numpy: auto', 'numpy: vielleicht'), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'numpy'):
                konfig.load(kaputt)


if __name__ == '__main__':
    unittest.main()
