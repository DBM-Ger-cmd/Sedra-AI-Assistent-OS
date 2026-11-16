"""Master-Modus (docs/SPEC_MASTER_MODUS_v1_ENTWURF.md, MM-01 bis MM-09, MM-13, MM-14): Sperrliste, Wurzel, Muster, Zustand, Entscheidungsfunktion."""
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sedra_runtime.harness import master


class Basis(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.wurzel = Path(self._t.name).resolve()
        for d in ('runtime/tests', 'docs', 'privat'):
            (self.wurzel / d).mkdir(parents=True)
        self.muster = ['runtime/**', 'docs/**']

    def sperre(self, zeile, ordner='runtime'):
        return master.sperre_befehl(zeile, ordner, self.wurzel, self.muster)


class FeldMuster(unittest.TestCase):
    def test_gueltig_und_leer(self):
        self.assertEqual(master.muster_pruefen(None), [])
        self.assertEqual(master.muster_pruefen(['runtime/**', 'docs\\**', 'runtime/**']), ['runtime/**', 'docs/**'])

    def test_ungueltig(self):
        for roh in ('runtime/**', [''], [3], ['../x/**'], ['/abs/**'], ['C:/x/**'], ['a/../b']):
            with self.assertRaises(master.MasterFehler, msg=repr(roh)):
                master.muster_pruefen(roh)


class SperrlisteBefehl(Basis):
    def test_erlaubt(self):
        for z in ('python benchmarks/run_tests.py --gruppe harness', 'python -m unittest discover tests', 'git status', 'git diff', 'git commit -m "x"',
                  'git checkout feature', 'git branch neu', 'node --check app.js', 'pytest -k "a or b" tests/test_x.py::Klasse'):
            self.assertIsNone(self.sperre(z), z)

    def test_netz(self):
        for z in ('curl https://x.de', 'wget http://x', 'Invoke-WebRequest http://x', 'iwr http://x', 'ssh host', 'curl.exe x', 'CURL  x',
                  'python tool.py http://x.de', 'git fetch', 'git pull', 'git clone x', 'git remote add a b'):
            self.assertIsNotNone(self.sperre(z), z)

    def test_installieren(self):
        for z in ('pip install x', 'pip3 install x', 'python -m pip install x', 'py -m pip download x', 'npm install', 'npm i x', 'npm ci', 'npx foo', 'yarn add x',
                  'winget install x', 'choco install x'):
            self.assertIsNotNone(self.sperre(z), z)

    def test_git_verlauf_und_zweige(self):
        for z in ('git push', 'git push origin main', 'git merge x', 'git rebase main', 'git checkout main', 'git switch master', 'git checkout origin/main',
                  'git branch -D x', 'git branch -d x', 'git branch --delete x', 'git branch -m a b', 'git reset --hard', 'git update-ref x y', 'git clean -fd',
                  'git config user.name x', 'git -c core.x=1 status', 'git rm a.txt', 'git tag -d v1'):
            self.assertIsNotNone(self.sperre(z), z)

    def test_loeschen_bleibt_karte(self):
        for z in ('del a.txt', 'rm a.txt', 'rmdir x', 'rd x', 'Remove-Item x', 'format c:', 'robocopy a b /MIR'):
            self.assertIsNotNone(self.sperre(z), z)
        self.assertIn('bleibt Karte', self.sperre('del a.txt'))

    def test_loeschen_menge(self):
        for i in range(25):
            (self.wurzel / 'runtime' / f'm{i}.tmp').write_text('x')
        self.assertIn('mehr als 20', self.sperre('del *.tmp'))
        self.assertIn('bleibt Karte', self.sperre('del m1.tmp'))
        self.assertEqual(master.loeschziele_anzahl(['del', '*.tmp'], self.wurzel / 'runtime', self.wurzel), 25)
        self.assertEqual(master.loeschziele_anzahl(['rmdir', '../runtime'], self.wurzel / 'runtime', self.wurzel), 25)
        self.assertGreater(master.loeschziele_anzahl(['del', 'x'], self.wurzel / 'nichtda' / 'unterwegs', self.wurzel) , 0)

    def test_shell_ausbruch(self):
        for z in ('powershell -File x.ps1', 'pwsh x', 'cmd /c dir', 'bash x.sh', 'wsl ls', 'start x', 'taskkill /pid 1', 'certutil -urlcache x', 'reg add x',
                  'python -c "print(1)"', 'python -m http.server', 'python -m urllib.request x', 'python -m ensurepip', 'node -e "1"'):
            self.assertIsNotNone(self.sperre(z), z)

    def test_nicht_pruefbare_zeile(self):
        self.assertIn('nicht prüfbar', self.sperre('git status | findstr x'))
        self.assertIn('nicht prüfbar', self.sperre('python a.py && python b.py'))
        self.assertIn('nicht prüfbar', self.sperre(''))

    def test_wurzel(self):
        aussen = str(self.wurzel.parent / 'fremd.txt')
        for z in ('python tool.py ..\\..\\x', 'python tool.py ../../x', f'python tool.py "{aussen}"', 'python tool.py C:\\Windows\\x', 'python tool.py \\\\server\\share',
                  'python tool.py --out=../../x', 'python tool.py ~/x', 'python tool.py %TEMP%\\x', 'python tool.py $env:TEMP'):
            self.assertIsNotNone(self.sperre(z), z)
        self.assertIsNone(self.sperre('python tool.py ../docs/a.md'))
        self.assertIsNone(self.sperre(f'python tool.py "{self.wurzel / "docs" / "a.md"}"'))

    def test_arbeitsordner(self):
        self.assertIn('Wurzel', self.sperre('git status', ordner='..'))
        self.assertIn('Muster', self.sperre('git status', ordner='privat'))
        self.assertIsNone(self.sperre('git status', ordner='runtime/tests'))
        self.assertIn('Wurzel', self.sperre('git status', ordner='C:/Windows'))

    def test_junction_oder_link_nach_aussen(self):
        aussen = Path(self._t.name).parent / ('aussen_' + self.wurzel.name)
        aussen.mkdir()
        self.addCleanup(lambda: aussen.rmdir() if aussen.exists() else None)
        link = self.wurzel / 'runtime' / 'weg'
        try:
            link.symlink_to(aussen, target_is_directory=True)
        except (OSError, NotImplementedError):
            import subprocess
            r = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(aussen)], capture_output=True)
            if r.returncode:
                self.skipTest('weder Symlink noch Junction möglich')
        self.addCleanup(lambda: link.rmdir() if link.exists() else None)
        self.assertIn('außerhalb', self.sperre('python tool.py weg/x.txt'))

    def test_gross_klein_und_leerzeichen(self):
        self.assertIsNotNone(self.sperre('  CuRl    https://x '))
        self.assertIsNotNone(self.sperre('GIT   PUSH'))


class DeckungPruefen(Basis):
    def test_werkzeuge_ausserhalb_bleiben(self):
        for w in ('desktop_aendern', 'profil_wechseln', 'auftraege_verteilen', 'sitzungen_aufraeumen', 'erinnern'):
            self.assertIn('gehört nicht', master.pruefen_deckung(self.muster, self.wurzel, w, 'x', {}))

    def test_dateien(self):
        p = lambda w, z, **k: master.pruefen_deckung(self.muster, self.wurzel, w, z, {}, **k)
        self.assertIsNone(p('datei_schreiben', 'runtime/a.py'))
        self.assertIsNone(p('datei_lesen', 'docs/x/y.md'))
        self.assertIsNone(p('dateien_auflisten', 'runtime'))
        self.assertIsNone(p('suchen', 'docs'))
        self.assertIn('Muster', p('datei_schreiben', 'privat/a.txt'))
        self.assertIn('Muster', p('datei_lesen', 'a.txt'))
        self.assertIn('Muster', p('datei_lesen', '../runtime/a.py'))
        self.assertIn('Muster', p('datei_lesen', 'C:/x/a.py'))
        self.assertIn('Schreibbereich', p('datei_aendern', 'docs/a.md', schreibbereich=['runtime/**']))
        self.assertIsNone(p('datei_aendern', 'docs/a.md', schreibbereich=['docs/**']))

    def test_laeufe_und_modelle_ganzes_projekt(self):
        for w in ('lauf_starten', 'lauf_stoppen', 'modell_laden', 'modell_entladen'):
            self.assertIsNone(master.pruefen_deckung(self.muster, self.wurzel, w, 'x', {}))

    def test_befehl_ueber_args(self):
        self.assertIsNone(master.pruefen_deckung(self.muster, self.wurzel, 'befehl', 'git status', {'befehl': 'git status', 'ordner': 'runtime'}))
        self.assertIsNotNone(master.pruefen_deckung(self.muster, self.wurzel, 'befehl', 'git push', {'befehl': 'git push', 'ordner': 'runtime'}))


class ZustandTest(Basis):
    def setUp(self):
        super().setUp()
        self.audit = []
        self.ereignisse = []
        self.z = master.Zustand(audit=lambda e, p: self.audit.append((e, p)), melden=lambda n, d: self.ereignisse.append((n, d)))

    def deckt(self, werkzeug='datei_lesen', ziel='docs/a.md', args=None, sid='S-1', projekt='p', **k):
        return self.z.deckt(sid, projekt, self.wurzel, werkzeug, ziel, args or {}, **k)

    def test_ohne_master_nie(self):
        self.assertIsNone(self.deckt())
        self.assertEqual(self.z.stand('S-1'), {'aktiv': False})

    def test_an_ohne_feld_nicht_moeglich(self):
        with self.assertRaises(master.MasterFehler):
            self.z.an('S-1', 'p', [])

    def test_an_deckt_zaehlt_und_auditiert(self):
        self.z.an('S-1', 'p', self.muster)
        r = self.deckt()
        self.assertEqual((r['regel'], r['nr']), ('master', 1))
        self.assertEqual(self.deckt('datei_schreiben', 'runtime/x.py')['nr'], 2)
        s = self.z.stand('S-1')
        self.assertEqual((s['aktiv'], s['aufrufe'], s['gesperrt'], s['projekt']), (True, 2, 0, 'p'))
        self.assertEqual([e for e, _ in self.audit], ['HARNESS_MASTER_AN'])
        self.assertEqual(self.ereignisse, [('harness.master', {'sitzung_id': 'S-1', 'aktiv': True})])

    def test_sperre_zaehlt_und_auditiert(self):
        self.z.an('S-1', 'p', self.muster)
        self.assertIsNone(self.deckt('befehl', 'curl x', {'befehl': 'curl x', 'ordner': 'runtime'}))
        self.assertEqual(self.z.stand('S-1')['gesperrt'], 1)
        e, p = self.audit[-1]
        self.assertEqual(e, 'HARNESS_MASTER_NICHT')
        self.assertIn('Netz', p['grund'])

    def test_andere_sitzung_und_anderes_projekt(self):
        self.z.an('S-1', 'p', self.muster)
        self.assertIsNone(self.deckt(sid='S-2'))
        self.assertIsNone(self.deckt(projekt='q'))

    def test_aus_sofort_und_audit(self):
        self.z.an('S-1', 'p', self.muster)
        self.deckt()
        self.assertEqual(self.z.aus('S-1')['aufrufe'], 1)
        self.assertIsNone(self.deckt())
        self.assertIsNone(self.z.aus('S-1'))
        e, p = self.audit[-1]
        self.assertEqual((e, p['grund'], p['aufrufe']), ('HARNESS_MASTER_AUS', 'captain', 1))
        self.assertEqual(self.ereignisse[-1][1]['aktiv'], False)

    def test_ablauf_nach_24_stunden(self):
        t0 = datetime.now().astimezone()
        self.z.an('S-1', 'p', self.muster, jetzt_z=t0)
        self.assertIsNotNone(self.deckt(jetzt_z=t0 + timedelta(hours=23, minutes=59)))
        self.assertIsNone(self.deckt(jetzt_z=t0 + timedelta(hours=24)))
        self.assertEqual(self.audit[-1][1]['grund'], 'ablauf')
        self.assertFalse(self.z.aktiv('S-1'))

    def test_neuer_zustand_ist_leer_wie_nach_neustart(self):
        self.z.an('S-1', 'p', self.muster)
        self.assertFalse(master.Zustand().aktiv('S-1'))

    def test_fehler_ist_keine_deckung(self):
        self.z.an('S-1', 'p', self.muster)
        self.assertIsNone(self.z.deckt('S-1', 'p', object(), 'befehl', 'x', {'befehl': 'git status'}))
        self.assertIsNone(self.z.deckt('S-1', 'p', self.wurzel, 'befehl', 'x', 'kein dict'))


class Entscheiden(Basis):
    def e(self, werkzeug, ziel, args=None, **k):
        return master.entscheiden(self.muster, werkzeug=werkzeug, ziel=ziel, args=args or {}, herkunft=k.pop('herkunft', 'fremd'), wurzel=self.wurzel, **k)

    def test_gedeckt(self):
        self.assertEqual(self.e('datei_schreiben', 'docs/a.md', {'inhalt': 'x'})['entscheidung'], 'gedeckt')
        self.assertEqual(self.e('befehl', 'git status', {'befehl': 'git status', 'ordner': 'runtime'})['entscheidung'], 'gedeckt')

    def test_fremde_rechte_nie(self):
        for w in ('berechtigungsmodus', 'Werkzeug_Freischalten', 'netz', 'mcp', 'hook', 'sandbox'):
            r = self.e(w, 'x')
            self.assertEqual((r['entscheidung'], r['grund'][:13]), ('karte', 'fremdes_recht'), w)
        self.assertEqual(self.e('datei_lesen', 'docs/a.md', art='rechte')['entscheidung'], 'karte')

    def test_shell_zeichen_nie(self):
        for z in ('git status | more', 'python a.py > out.txt', 'a && b', 'x; y', 'echo `x`', 'echo $(x)'):
            self.assertEqual(self.e('befehl', z, {'befehl': z, 'ordner': 'runtime'})['entscheidung'], 'karte', z)

    def test_vorbehalt_und_wurzel_nie(self):
        self.assertEqual(self.e('datei_schreiben', 'local_config/x.yaml', {'inhalt': 'x'})['entscheidung'], 'karte')
        self.assertEqual(self.e('befehl', 'git push', {'befehl': 'git push', 'ordner': 'runtime'})['entscheidung'], 'karte')
        self.assertEqual(self.e('datei_lesen', '../x')['entscheidung'], 'karte')
        self.assertEqual(self.e('datei_schreiben', 'privat/a.txt', {'inhalt': 'x'})['entscheidung'], 'karte')

    def test_herkunft_und_fehler(self):
        self.assertEqual(self.e('datei_lesen', 'docs/a.md', herkunft='sedra')['entscheidung'], 'karte')
        self.assertEqual(master.entscheiden('kein-muster', werkzeug='datei_lesen', ziel='x', args={}, herkunft='fremd', wurzel=self.wurzel)['entscheidung'], 'karte')


if __name__ == '__main__':
    unittest.main()
