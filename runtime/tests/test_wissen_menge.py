"""Messlauf für das Mengenziel (SPEC_WISSEN_KERN_v1 WK-23, F3: 5 000 Dateien / 200 000 Abschnitte; G2 K5 §2.6, D-K5-7).

Läuft nur mit SEDRA_WISSEN_MENGE=1 (dauert Minuten, braucht ≈ 2 GB Speicher), nur auf der CPU. Baut einen synthetischen Bestand direkt in
der Datenbank (200 000 Abschnitte in 5 000 Dateien, FTS5 über die Trigger, Vektoren mit 1 024 Dimensionen) und misst:
- Volltext über `suche` (Modus volltext, Rechtefilter wie im Betrieb): Ziel unter 1 s
- Vektorteil mit numpy (wenn da): Ziel unter 1 s; reines Python: wird gemessen und gemeldet (G2: ≈ 3 s auf dem Bau-Rechner)
Die Zahlen stehen in der Ausgabe (print), damit der Captain sie auf seinem PC vergleichen kann."""
import importlib.util
import os
import random
import tempfile
import time
import unittest

from guppi_runtime.wissen import schema, vektor
from wissen_fixture import FakeEmbedServer, oeffnen

AN = os.environ.get('SEDRA_WISSEN_MENGE') == '1'
N, DATEIEN, DIM = int(os.environ.get('SEDRA_WISSEN_MENGE_N', '200000')), 5000, 1024
WOERTER = ('Vertrag Laufzeit Kündigung Rechnung Mahnung Lieferung Wartung Angebot Auftrag Kunde Lieferant Termin Frist Zahlung Bremen Köln '
           'Kranich Lease Testlabor Modell Karte Kühlung Wächter Schalter Freigabe Posteingang Projekt Ordner Datei Abschnitt').split()


@unittest.skipUnless(AN, 'nur mit SEDRA_WISSEN_MENGE=1')
class Menge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='wissen-menge-')
        cls.srv = FakeEmbedServer(lazy=True)
        cls.srv.__enter__()
        cls.sp = oeffnen(cls.tmp.name, cls.srv.port, server=cls.srv)
        r = random.Random(5)
        db, jetzt = cls.sp.db, '2026-11-06T00:00:00Z'
        t = time.perf_counter()
        with schema._immediate(db):
            db.execute("INSERT INTO quellen (id, art, adapter, wurzel, pfad, muster, freigabe_gate, freigabe_mission, stufe, personenbezug, erstellt) "
                       "VALUES ('Q-menge', 'ordner', 'markdown', 'repo', 'docs', '*.md', 'HG', 'M', 1, 0, ?)", (jetzt,))
            zeilen = []
            for i in range(N):
                text = ' '.join(r.choice(WOERTER) for _ in range(60)) + f' Nummer{i}'
                zeilen.append((f'W{i:012x}', 'Q-menge', f'docs/d{i % DATEIEN}.md', f'Kopf {i % 40} > Teil {i}', text, f'h{i}', jetzt, jetzt, len(text)))
            db.executemany("INSERT INTO abschnitte (id, quelle, datei, stelle, text, hash, datum, aufgenommen, zeichen) VALUES (?,?,?,?,?,?,?,?,?)", zeilen)
        cls.aufbau_s = time.perf_counter() - t
        cls.nr = [row[0] for row in db.execute("SELECT nr FROM abschnitte ORDER BY nr")]

    @classmethod
    def tearDownClass(cls):
        cls.sp.schliessen()
        cls.srv.__exit__(None, None, None)
        cls.tmp.cleanup()

    def test_volltext_unter_einer_sekunde(self):
        leser = {'art': 'captain', 'stufe': 6, 'projekt': None, 'agent_id': None}
        zeiten = []
        for frage in ('Kündigung Frist Bremen', 'Lease Testlabor Modell', 'Nummer123456', 'Rechnung Mahnung Zahlung Kranich'):
            t = time.perf_counter()
            out = self.sp.suche(frage, leser=leser)
            zeiten.append(time.perf_counter() - t)
            self.assertEqual(out['modus'], 'volltext')
            self.assertTrue(out['treffer'])
        print(f"\nMenge: {N} Abschnitte aufgebaut in {self.aufbau_s:.1f} s; Volltext: " + ', '.join(f'{z * 1000:.0f} ms' for z in zeiten))
        self.assertLess(max(zeiten), 1.0)

    def test_vektorteil(self):
        rng = random.Random(7)
        q = vektor.normiere([rng.gauss(0, 1) for _ in range(DIM)])
        blobs = [(nr, vektor.packe([rng.gauss(0, 1) for _ in range(DIM)])) for nr in self.nr[:N]]
        erlaubt = set(self.nr)
        if importlib.util.find_spec('numpy'):
            from guppi_runtime.wissen import vektor_np
            t = time.perf_counter(); m = vektor_np.Matrix(blobs, DIM); aufbau = time.perf_counter() - t
            t = time.perf_counter(); m.top_k(q, 50, erlaubt=erlaubt); d = time.perf_counter() - t
            print(f"\nMenge: numpy {len(m)} Vektoren, Aufbau {aufbau:.2f} s, Suche mit Filter {d * 1000:.0f} ms, Matrix {m.bytes / 1e6:.0f} MB")
            self.assertLess(d, 1.0)
            del m
        liste = [(nr, vektor.lese(b, DIM)) for nr, b in blobs]
        t = time.perf_counter(); vektor.top_k(q, liste, 50, erlaubt=erlaubt.__contains__); d = time.perf_counter() - t
        print(f"Menge: reines Python {len(liste)} Vektoren, Suche mit Filter {d:.2f} s")


if __name__ == '__main__':
    unittest.main()
