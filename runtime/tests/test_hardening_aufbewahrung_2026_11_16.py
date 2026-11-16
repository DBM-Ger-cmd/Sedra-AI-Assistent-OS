"""Hardening-Runde 16.11.2026 (docs/HARDENING_2026-11-16_MASTER.md), Teil D: Aufbewahrung (desk/aufbewahrung.py) – Zeitstempel, Schreibfehler, Inhalte im Audit.
Attrappen statt Server; alle Werte erfunden."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from sedra_runtime.desk import aufbewahrung

TAG = 86400


class Audit:
    def __init__(self):
        self.zeilen = []

    def append(self, event, component=None, payload=None, **kw):
        self.zeilen.append((event, payload))


class Sitzungen:
    def __init__(self, z):
        self.z = z

    def liste(self):
        return list(self.z)


class Harness:
    def __init__(self, z):
        self.sitzungen = Sitzungen(z)
        self.weg = []

    def loeschen(self, sid):
        self.weg.append(sid)


def hub(root, tage=30, sitzungen=()):
    audit = Audit()
    h = SimpleNamespace(project_root=root, betrieb_an=True, richtlinie=SimpleNamespace(aktiv=True, daten={'aufbewahrung': {'gespraeche_tage': tage, 'entwuerfe_stunden': 24}}),
                        gw=SimpleNamespace(aufraeumen=lambda: 0), harness=Harness(sitzungen), runtime=SimpleNamespace(audit=audit))
    return h, audit


def iso(t):
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(t))


class Probe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'local_config').mkdir()
        self.datei = self.root / 'local_config' / 'aufbewahrung.json'

    def test_zeitpunkt_in_der_zukunft_sperrt_den_lauf_nicht(self):
        h, _ = hub(self.root)
        jetzt = time.time()
        for zukunft in (jetzt + 3650 * TAG, 1e300):
            self.datei.write_text(json.dumps({'zuletzt': zukunft}), encoding='utf-8')
            self.assertIsNotNone(aufbewahrung.lauf(h, jetzt), zukunft)

    def test_unendlich_und_unsinn_im_zeitpunkt(self):
        h, _ = hub(self.root)
        jetzt = time.time()
        for roh in ('{"zuletzt": Infinity}', '{"zuletzt": NaN}', '{"zuletzt": "gestern"}', '{"zuletzt": true}', '[]', '', '{"zuletzt": -1e300}', '\x00\x00'):
            self.datei.write_text(roh, encoding='utf-8')
            self.assertIsNotNone(aufbewahrung.lauf(h, jetzt), roh)

    def test_hoechstens_einmal_je_24_stunden(self):
        h, _ = hub(self.root)
        jetzt = time.time()
        self.assertIsNotNone(aufbewahrung.lauf(h, jetzt))
        self.assertIsNone(aufbewahrung.lauf(h, jetzt + 3600))
        self.assertIsNotNone(aufbewahrung.lauf(h, jetzt + TAG + 1))

    def test_nur_alte_sitzungen_und_grenze(self):
        jetzt = time.time()
        z = [{'id': 'S-ALT', 'zuletzt': iso(jetzt - 31 * TAG)}, {'id': 'S-NEU', 'zuletzt': iso(jetzt - 29 * TAG)}, {'id': 'S-KAPUTT', 'zuletzt': 'kein-datum'}, {'id': 'S-OHNE'}]
        h, _ = hub(self.root, 30, z)
        aufbewahrung.lauf(h, jetzt, erzwingen=True)
        self.assertEqual(h.harness.weg, ['S-ALT'])

    def test_schreibfehler_beim_zeitpunkt_ist_kein_absturz(self):
        (self.root / 'local_config').rmdir()
        (self.root / 'local_config').write_text('ich bin eine Datei', encoding='utf-8')       # der Ordner ist keiner
        h, audit = hub(self.root)
        erg = aufbewahrung.lauf(h, time.time(), erzwingen=True)
        self.assertTrue(erg.get('zeitpunkt_nicht_gespeichert'))
        self.assertEqual(audit.zeilen[-1][0], 'AUFBEWAHRUNG_LAUF')

    def test_fehler_im_gateway_oder_in_der_liste_stoppt_den_lauf_nicht(self):
        h, audit = hub(self.root)
        h.gw = SimpleNamespace(aufraeumen=lambda: 1 / 0)
        h.harness.sitzungen = SimpleNamespace(liste=lambda: 1 / 0)
        erg = aufbewahrung.lauf(h, time.time(), erzwingen=True)
        self.assertTrue(erg['entwuerfe_fehler'] and erg['gespraeche_fehler'])

    def test_audit_nennt_nie_titel_oder_namen(self):
        jetzt = time.time()
        h, audit = hub(self.root, 30, [{'id': 'S-ALT', 'zuletzt': iso(jetzt - 40 * TAG), 'titel': 'GEHEIMER-TITEL'}])
        aufbewahrung.lauf(h, jetzt, erzwingen=True)
        self.assertNotIn('GEHEIMER-TITEL', repr(audit.zeilen))
        self.assertNotIn('S-ALT', repr(audit.zeilen))

    def test_ohne_richtlinie_oder_betrieb_tut_der_lauf_nichts(self):
        h, _ = hub(self.root)
        h.richtlinie.aktiv = False
        self.assertIsNone(aufbewahrung.lauf(h, time.time(), erzwingen=True))
        h.richtlinie.aktiv, h.betrieb_an = True, False
        self.assertIsNone(aufbewahrung.lauf(h, time.time(), erzwingen=True))
        self.assertFalse(self.datei.exists())

    def test_endgueltig_geloescht_wird_nichts(self):
        """Der Lauf ruft nur `harness.loeschen` (verschiebt nach geloescht/); er löscht selbst keine Datei."""
        quelle = Path(aufbewahrung.__file__).read_text(encoding='utf-8')
        for gefaehrlich in ('unlink(', 'rmtree', 'os.remove', 'os.rmdir'):
            self.assertNotIn(gefaehrlich, quelle)


if __name__ == '__main__':
    unittest.main()
