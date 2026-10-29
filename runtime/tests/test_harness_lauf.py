"""N7 der Harness-Shell Stufe 3 (ohne Server): Starter, Hülle, Register der Läufe – mit echten Prozessen und einem Wegwerf-Skript."""
import copy
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from guppi_runtime.harness import herkunft, lauf

SKRIPT = '''import os, subprocess, sys, time
n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
if len(sys.argv) > 2 and sys.argv[2] == 'kind':
    kind = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
    open('kind.pid', 'w').write(str(kind.pid))
for i in range(1, n + 1):
    print(f'{i}/{n}', flush=True)
    time.sleep(0.2)
if len(sys.argv) > 2 and sys.argv[2] == 'fehler':
    sys.exit(3)
'''


def typen():
    doc = {'harness_laeufe': {'version': 1, 'laeufe': [
        {'id': 'probe', 'name': 'Probe', 'argv': ['python', 'probe.py', '{n}'], 'ordner': 'runtime', 'parameter': {'n': {'muster': '[0-9]{1,3}', 'vorgabe': '3'}},
         'fortschritt': {'art': 'zeilen', 'regex': r'^\s*(\d+)\s*/\s*(\d+)'}, 'zeitlimit_min': 5},
        {'id': 'fehler', 'name': 'Fehler', 'argv': ['python', 'probe.py', '2', 'fehler'], 'ordner': 'runtime', 'zeitlimit_min': 5},
        {'id': 'baum', 'name': 'Baum', 'argv': ['python', 'probe.py', '100', 'kind'], 'ordner': 'runtime', 'zeitlimit_min': 5},
        {'id': 'exklusiv', 'name': 'Exklusiv', 'argv': ['python', 'probe.py', '100'], 'ordner': 'runtime', 'gpu': 'exklusiv', 'zeitlimit_min': 5},
    ]}}
    return lauf.pruefen(doc)


class LaufBasis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='lauf-')
        self.addCleanup(self.tmp.cleanup)
        self.wurzel = Path(self.tmp.name) / 'projekt'
        (self.wurzel / 'runtime').mkdir(parents=True)
        (self.wurzel / 'runtime' / 'probe.py').write_text(SKRIPT, encoding='utf-8')
        self.typen = typen()
        self.audit, self.ereignisse = [], []
        self.store = lauf.Laeufe(Path(self.tmp.name) / 'laeufe', typen=self.typen, audit=lambda e, p: self.audit.append((e, p)),
                                 melden=lambda n, d: self.ereignisse.append((n, d)))
        self.addCleanup(self.aufraeumen)

    def aufraeumen(self):
        for l in self.store.laufende():
            try: self.store.stoppen(l['id'], warten_s=15)
            except Exception: pass

    def start(self, lid='probe', parameter=None, store=None, **kw):
        typ = self.typen[lid]
        return (store or self.store).starten(typ, lauf.argv_bauen(typ, parameter, self.wurzel), parameter=parameter, **kw)

    def warte(self, lid, bis=('ok', 'fehler', 'gestoppt', 'abgebrochen', 'verloren', 'zeitlimit'), s=40, store=None):
        ende = time.monotonic() + s
        while time.monotonic() < ende:
            l = (store or self.store).laden(lid)
            if l['status'] in bis:
                return l
            time.sleep(0.2)
        self.fail(f'Lauf {lid} endete nicht: {(store or self.store).laden(lid)["status"]}')


class LaufTests(LaufBasis):
    def test_ein_lauf_von_start_bis_ende(self):
        l = self.start(sitzung_id='S-11111111', antwort_id='A-11111111', aufgabe_id='T-11111111', karte_id='K-11111111')
        self.assertRegex(l['id'], r'L-[0-9A-F]{8}')
        self.assertEqual((l['status'], l['sitzung_id'], l['aufgabe_id']), ('laeuft', 'S-11111111', 'T-11111111'))
        self.assertIn(l['pid'], herkunft.REGISTER.eintraege(), 'die Hülle steht im Herkunfts-Register (S7)')
        ende = self.warte(l['id'])
        self.assertEqual((ende['status'], ende['exit'], ende['fortschritt']['prozent']), ('ok', 0, 100))
        self.assertEqual(self.store.tail(l['id'], 10), ['1/3', '2/3', '3/3'])
        self.assertEqual([e for e, _ in self.audit], ['HARNESS_LAUF_START', 'HARNESS_LAUF_ENDE'])
        zustaende = [d['zustand'] for n, d in self.ereignisse if n == 'harness.lauf']
        self.assertEqual((zustaende[0], zustaende[-1]), ('gestartet', 'ende'))
        d = self.store.ordner / l['id']
        self.assertEqual(sorted(p.name for p in d.iterdir()), ['ausgabe.log', 'ende.json', 'lauf.json'])
        self.assertEqual(json.loads((d / 'ende.json').read_text(encoding='utf-8'))['grund'], 'ok')

    def test_fehler_exit_wird_gemeldet(self):
        l = self.warte(self.start('fehler')['id'])
        self.assertEqual((l['status'], l['exit']), ('fehler', 3))

    def test_stopp_beendet_auch_kindprozesse(self):
        l = self.start('baum')
        kind = self.wurzel / 'runtime' / 'kind.pid'
        for _ in range(100):
            if kind.exists() and kind.read_text().strip(): break
            time.sleep(0.1)
        kind_pid = int(kind.read_text())
        self.assertIn(kind_pid, herkunft.prozess_tabelle())
        gestoppt = self.store.stoppen(l['id'], grund='Test')
        self.assertEqual(gestoppt['status'], 'gestoppt')
        for _ in range(50):
            if kind_pid not in herkunft.prozess_tabelle(): break
            time.sleep(0.1)
        self.assertNotIn(kind_pid, herkunft.prozess_tabelle(), 'der ganze Prozessbaum ist weg')
        self.assertIn('HARNESS_LAUF_STOPP', [e for e, _ in self.audit])
        with self.assertRaisesRegex(lauf.LaufFehler, 'nicht_laufend'):
            self.store.stoppen(l['id'])

    def test_abbruch_durch_aufgabe_hat_einen_eigenen_status(self):
        l = self.start('baum')
        self.assertEqual(self.store.stoppen(l['id'], grund='Aufgabe zurückgenommen', status_wunsch='abgebrochen')['status'], 'abgebrochen')

    def test_zeitlimit(self):
        typ = copy.deepcopy(self.typen['baum'])
        typ['zeitlimit_min'] = 0.04                                  # 2,4 s
        l = self.store.starten(typ, lauf.argv_bauen(typ, None, self.wurzel))
        self.assertEqual(self.warte(l['id'])['status'], 'zeitlimit')

    def test_der_lauf_ueberlebt_den_neustart_des_servers(self):
        l = self.start(parameter={'n': '12'})
        neu = lauf.Laeufe(self.store.ordner, typen=self.typen)         # „Neustart“: ein neues Register findet den laufenden Lauf wieder
        self.assertEqual([x['id'] for x in neu.laufende()], [l['id']])
        self.assertIn(l['pid'], herkunft.REGISTER.eintraege())
        self.assertEqual(self.warte(l['id'], store=neu)['status'], 'ok')

    def test_toter_prozess_ohne_ende_ist_verloren_nie_ok(self):
        l = self.start(parameter={'n': '100'})
        d = self.store.ordner / l['id']
        self.store.stoppen(l['id'])
        (d / 'ende.json').unlink()                                    # als hätte niemand das Ende gesehen
        roh = json.loads((d / 'lauf.json').read_text(encoding='utf-8'))
        roh.update(status='laeuft', ende=None, grund=None)
        (d / 'lauf.json').write_text(json.dumps(roh), encoding='utf-8')
        self.assertEqual(lauf.Laeufe(self.store.ordner, typen=self.typen).laden(l['id'])['status'], 'verloren')

    def test_grenzen(self):
        fake = lambda d: (os.getpid(), None)                          # läuft „für immer“: die PID gehört dem Test
        store = lauf.Laeufe(Path(self.tmp.name) / 'grenzen', typen=self.typen, starten=fake)
        probe = self.typen['probe']
        info = lauf.argv_bauen(probe, None, self.wurzel)
        for _ in range(lauf.MAX_LAUFEND):
            store.starten(probe, info)
        with self.assertRaisesRegex(lauf.LaufFehler, 'zu_viele_laeufe'):
            store.starten(probe, info)
        store2 = lauf.Laeufe(Path(self.tmp.name) / 'grenzen2', typen=self.typen, starten=fake)
        ex = self.typen['exklusiv']
        with self.assertRaisesRegex(lauf.LaufFehler, 'exklusiv_andere_antwort_laeuft'):
            store2.starten(ex, lauf.argv_bauen(ex, None, self.wurzel), andere_antworten=1)
        store2.starten(ex, lauf.argv_bauen(ex, None, self.wurzel))
        self.assertEqual(store2.belegt()['lauf'], 'exklusiv', 'ein exklusiver Lauf nimmt dem Gespräch das Modell')
        with self.assertRaisesRegex(lauf.LaufFehler, 'exklusiv_belegt'):
            store2.starten(ex, lauf.argv_bauen(ex, None, self.wurzel))
        store2.starten(probe, info)                                   # ein nicht exklusiver Lauf daneben geht

    def test_start_fehlgeschlagen_hinterlaesst_einen_fehler_nicht_laeuft(self):
        def kaputt(d):
            raise OSError('x')
        store = lauf.Laeufe(Path(self.tmp.name) / 'kaputt', typen=self.typen, starten=kaputt)
        with self.assertRaisesRegex(lauf.LaufFehler, 'start_fehlgeschlagen'):
            store.starten(self.typen['probe'], lauf.argv_bauen(self.typen['probe'], None, self.wurzel))
        self.assertEqual([l['status'] for l in store.alle()], ['fehler'])
        self.assertEqual(store.laufende(), [])

    def test_unbekannter_lauf(self):
        for lid in ('L-00000000', '../x', None):
            with self.assertRaises(KeyError):
                self.store.laden(lid)


class UmgebungTests(unittest.TestCase):
    def test_lauf_umgebung_behaelt_system_und_streicht_geheimes(self):
        schluessel = {'PROGRAMFILES': 'x', 'LOCALAPPDATA': 'y', 'OPENAI_API_KEY': 'geheim', 'GITHUB_TOKEN': 'geheim', 'MEIN_PASSWORT': 'geheim', 'PATH': 'p'}
        alt = {k: os.environ.get(k) for k in schluessel}
        os.environ.update(schluessel)
        try:
            env = lauf.lauf_umgebung()
        finally:
            for k, v in alt.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v
        self.assertEqual((env['PROGRAMFILES'], env['LOCALAPPDATA'], env['PATH']), ('x', 'y', 'p'))
        self.assertFalse({'OPENAI_API_KEY', 'GITHUB_TOKEN', 'MEIN_PASSWORT'} & set(env))
        self.assertEqual(env['PYTHONIOENCODING'], 'utf-8')


class FortschrittTests(unittest.TestCase):
    def test_die_drei_regeln_und_muell(self):
        z = ['Start', '3/12', 'Rauschen', '6 / 12']
        self.assertEqual(lauf.fortschritt_aus(z, {'art': 'zeilen', 'regex': r'(\d+)\s*/\s*(\d+)'})['prozent'], 50)
        self.assertEqual(lauf.fortschritt_aus(['ab 42.7 %'], {'art': 'prozent', 'regex': r'([\d.]+)\s*%'})['prozent'], 42)
        self.assertEqual(lauf.fortschritt_aus(['a', '', 'letzte Zeile  '], {'art': 'text'})['text'], 'letzte Zeile')
        self.assertEqual(lauf.fortschritt_aus(['12/10'], {'art': 'zeilen', 'regex': r'(\d+)/(\d+)'})['prozent'], 100)
        for muell in (None, [], [None, 5], ['x']):
            self.assertIn(lauf.fortschritt_aus(muell, {'art': 'zeilen', 'regex': r'(\d+)/(\d+)'}), (None, {'prozent': None, 'text': ''}))
        self.assertIsNone(lauf.fortschritt_aus(['0/0'], {'art': 'zeilen', 'regex': r'(\d+)/(\d+)'}))
        self.assertIsNone(lauf.fortschritt_aus(['1/2'], None))


if __name__ == '__main__':
    unittest.main()
