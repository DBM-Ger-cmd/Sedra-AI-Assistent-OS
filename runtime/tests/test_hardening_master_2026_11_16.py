"""Hardening-Runde 16.11.2026 (docs/HARDENING_2026-11-16_MASTER.md), Teil A: Gegenproben zum Master-Modus.

Jeder Test ist ein Angriff und wird ROT, wenn der Schutz fehlt. Alle Namen, Pfade und Werte sind erfunden (Wegwerf-Projekt im Temp-Ordner).
Die Proben laufen gegen `master.sperre_befehl` (reine Zeilenprüfung) und gegen `Kiste.aufruf` mit Master (der ganze Weg: Vorbehalt → Katalog → Deckung → Guard)."""
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sedra_runtime.core.guard import Guard
from sedra_runtime.harness import befehl as befehl_mod, katalog, master
from sedra_runtime.harness.freigabe import Karten, Kiste
from sedra_runtime.harness.werkzeuge import Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'SEDRA_Architecture_v1.20_SELF_DEVELOPMENT'
SID = 'S-00000001'
WIN = os.name == 'nt'


class Audit:
    def __init__(self):
        self.zeilen = []

    def append(self, event, component=None, mission_id=None, payload=None):
        self.zeilen.append((event, payload or {}))

    def alle(self, event):
        return [p for e, p in self.zeilen if e == event]


class Projekt(unittest.TestCase):
    """Ein Wegwerf-Projekt mit geschützten Pfaden; der Master steht auf `**` (der weiteste zulässige Fall)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = (Path(self.tmp.name) / 'projekt').resolve()
        self.hdir = self.root / 'runtime' / 'src' / 'sedra_runtime' / 'harness'
        for d in ('docs', 'local_config', 'runtime/tests'):
            (self.root / d).mkdir(parents=True)
        self.hdir.mkdir(parents=True)
        self.geschuetzt = {self.hdir / 'master.py': 'ORIGINAL-MASTER', self.root / 'local_config' / 'harness_projekte.yaml': 'ORIGINAL-CONFIG',
                           self.root / 'local_config' / 'freigabe_katalog.yaml': 'ORIGINAL-KATALOG'}
        for p, t in self.geschuetzt.items():
            p.write_text(t, encoding='utf-8')
        self.guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(self.tmp.name) / 'tokens.json')
        self.projekt = {'id': 'p', 'name': 'P', 'wurzel': str(self.root), 'schreibbereich': ['docs/**', 'runtime/**', 'local_config/**'], 'master': ['**']}
        self.regeln = katalog.laden(Path('gibt-es-nicht'))['regeln']
        self.audit = Audit()
        self.zustand = master.Zustand(audit=lambda e, p: self.audit.append(e, payload=p))
        self.karten = Karten(Path(self.tmp.name) / 'karten')

    def kiste(self, **kw):
        w = Werkzeuge(self.projekt, guard=self.guard, mission_id='M-HARNESS', regeln=self.regeln)
        return Kiste(w, regeln=self.regeln, guard=self.guard, audit=self.audit, karten=self.karten, sitzung_id=SID, projekt_id='p',
                     master=kw.pop('master', self.zustand), **kw)

    def an(self, muster=('**',)):
        self.zustand.an(SID, 'p', list(muster))

    def unveraendert(self):
        for p, t in self.geschuetzt.items():
            self.assertEqual(p.read_text(encoding='utf-8'), t, f'GESCHÜTZTE DATEI VERÄNDERT: {p.name}')

    def sperre(self, zeile, ordner='.'):
        return master.sperre_befehl(zeile, ordner, self.root, ['**'])


# ------------------------------------------------------------------ A-1: Sperrliste (Programmtext, Installieren, Netz, Systemwerkzeuge)
class SperrlisteUmgehung(Projekt):
    def pruefen(self, zeilen):
        offen = [z for z in zeilen if self.sperre(z) is None]
        self.assertEqual(offen, [], 'diese Zeilen deckt der Master, obwohl sie gesperrt sein müssen')

    def test_python_programmtext_mit_gebuendelten_schaltern(self):
        self.pruefen(['python -Ic "print(1)"', 'python -Sc "print(1)"', 'python -Bc "print(1)"', 'python -cprint(1)', 'python -uc x', 'python -OOc x', 'py -3 -Ic x'])

    def test_python_modul_angehaengt_und_programmtext_module(self):
        self.pruefen(['python -mpip install x', 'python -m pip.__main__ install x', 'python -m timeit -s "import os" x', 'python -m runpy os', 'python -m code',
                      'python -m pdb x.py', 'python -m trace --trackcalls x.py', 'python -m pty', 'python -m idlelib', 'python -m asyncio', 'python -m cgi',
                      'python -m xmlrpc.server', 'python -m uv pip install x', 'python -m pipx run x', 'python -m build', 'python -m easy_install x', 'python -m wheel pack x'])

    def test_installieren_andere_wege(self):
        self.pruefen(['pip --quiet install x', 'pip -q install x', 'pip -v install x', 'pip --proxy x install y', 'pip --index-url x install y', 'pip --user install x',
                      'pipx install x', 'uv pip install x', 'uvx x', 'poetry add x', 'conda install x', 'easy_install x', 'python setup.py install', 'python setup.py develop',
                      'npm --silent install x', 'npm -g install x', 'npm --prefix .. install'])

    def test_node_programmtext_und_vorladen(self):
        self.pruefen(['node --eval=x', 'node -pe 1', 'node --print=1', 'node -r x.js a.js', 'node --require=x a.js', 'node --import x a.js', 'node --loader x a.js'])

    def test_git_zweige_und_verlust(self):
        self.pruefen(['git branch -Df x', 'git branch -fd x', 'git branch -dx', 'git branch -C a b', 'git branch -c a b', 'git tag -fa x', 'git reset --keep HEAD~3', 'git reset --merge',
                      'git checkout .', 'git checkout -- .', 'git restore .', 'git stash drop', 'git stash clear', 'git reflog expire', 'git reflog delete', 'git replace a b',
                      'git daemon', 'git instaweb', 'git ls-remote', 'git hook run x', 'git send-email x', 'git svn x', 'git fast-import', 'git maintenance run',
                      'git difftool', 'git mergetool', 'git bisect run x', 'git commit --amend'])

    def test_netz_und_cloud_werkzeuge(self):
        self.pruefen(['gh api x', 'gh pr create', 'docker run x', 'aws s3 ls', 'az login', 'gcloud x', 'kubectl x', 'rsync x y', 'aria2c x', 'nslookup x', 'nmap x', 'ping x',
                      'terraform x', 'ansible x', 'httpie x'])

    def test_systemwerkzeuge_und_lolbins(self):
        self.pruefen(['conhost cmd', 'forfiles /c x', 'wmic process', 'setx x y', 'regedit /s x.reg', 'runas x', 'shutdown /s', 'installutil x', 'regasm x', 'pcalua x', 'diskpart',
                      'bcdedit x', 'vssadmin x', 'dism x', 'fsutil x', 'compact x', 'takeown /f x', 'attrib x', 'msg x'])

    def test_andere_interpreter_mit_programmtext(self):
        self.pruefen(['perl -e x', 'ruby -e x', 'php -r x', 'lua -e x', 'deno eval x', 'java -jar x', 'cargo run', 'go run x', 'dotnet run', 'make x', 'msbuild x'])

    def test_beabsichtigtes_bleibt_erlaubt(self):
        """Gegenprobe zur Gegenprobe: die Härtung darf den Alltag des Bauens nicht sperren (sonst fiele der Master-Modus in der Praxis aus)."""
        for z in ('python benchmarks/run_tests.py --gruppe harness', 'python -m unittest discover tests', 'python -m pytest -q', 'python -m py_compile a.py', 'git status', 'git diff',
                  'git log --oneline', 'git add .', 'git commit -m "x"', 'git checkout feature', 'git checkout -b neu', 'git branch neu', 'node --check app.js', 'pytest -k "a or b" tests/test_x.py'):
            self.assertIsNone(self.sperre(z), z)


# ------------------------------------------------------------------ A-2: geschützte Pfade über Befehls-Argumente
class GeschuetztePfadeUeberBefehl(Projekt):
    """Der Vorbehalt prüft bei `befehl` nur die Zeile als Text; die Pfade der Argumente prüfte weder er noch die Sperrliste."""

    def test_befehlsargument_auf_geschuetzten_pfad_deckt_der_master_nicht(self):
        for z in ('xcopy x.txt local_config\\harness_projekte.yaml /Y', 'robocopy docs local_config x.txt', 'tar -xf a.tar -C local_config',
                  'python tool.py runtime/src/sedra_runtime/harness/master.py', 'xcopy a.txt runtime\\src\\sedra_runtime\\harness\\ /Y',
                  'git checkout HEAD -- runtime/src/sedra_runtime/harness/master.py', 'xcopy a.txt .git\\hooks\\ /Y', 'python tool.py local_config'):
            self.assertIsNotNone(self.sperre(z), z)

    def test_gleiche_pfade_ueber_umweg_im_argument(self):
        for z in ('xcopy a.txt docs\\..\\local_config\\x.yaml /Y', 'xcopy a.txt LOCAL_CONFIG\\x.yaml /Y', 'xcopy a.txt "local_config\\" /Y', 'xcopy a.txt local_config. /Y'):
            self.assertIsNotNone(self.sperre(z), z)

    def test_arbeitsordner_ist_geschuetzt(self):
        (self.root / 'local_config' / 'x').mkdir()
        self.assertIsNotNone(self.sperre('python tool.py', ordner='local_config'))
        self.assertIsNotNone(self.sperre('xcopy a.txt master.py /Y', ordner='runtime/src/sedra_runtime/harness'))
        self.assertIsNotNone(self.sperre('python tool.py master.py', ordner='runtime/src/sedra_runtime/harness'))

    def test_ganzer_weg_xcopy_in_local_config(self):
        if not WIN:
            self.skipTest('xcopy gibt es nur unter Windows')
        self.an()
        (self.root / 'docs' / 'neu.txt').write_text('EVIL', encoding='utf-8')
        r = self.kiste().aufruf('befehl', {'befehl': 'xcopy docs\\neu.txt local_config\\harness_projekte.yaml /Y', 'ordner': '.'})
        self.assertEqual(r['status'], 'wartet', r)
        self.unveraendert()


# ------------------------------------------------------------------ A-3: Pfad-Eigenheiten bei datei_schreiben unter dem Master
class SchreibenQuirks(Projekt):
    def versuch(self, pfad, inhalt='EVIL'):
        self.an()
        try:
            r = self.kiste().aufruf('datei_schreiben', {'pfad': pfad, 'inhalt': inhalt})
        except Exception as exc:                                       # eine Ausnahme ist kein Freigeben
            r = {'status': 'fehler', 'ergebnis': repr(exc)}
        self.assertIn(r['status'], ('wartet', 'fehler', 'verboten', 'hinweis'), (pfad, r))     # `hinweis` = W-1: nichts geschrieben
        self.unveraendert()

    def test_punkt_zurueck(self):
        self.versuch('docs/../runtime/src/sedra_runtime/harness/master.py')
        self.versuch('docs/../local_config/harness_projekte.yaml')

    def test_gross_klein(self):
        self.versuch('RUNTIME/SRC/SEDRA_RUNTIME/HARNESS/MASTER.PY')
        self.versuch('LOCAL_CONFIG/freigabe_katalog.yaml')

    @unittest.skipUnless(WIN, 'Windows-Eigenheit')
    def test_windows_punkt_und_leerzeichen_am_ende(self):
        self.versuch('runtime/src/sedra_runtime/harness/master.py.')
        self.versuch('runtime/src/sedra_runtime/harness/master.py ')
        self.versuch('local_config./freigabe_katalog.yaml')
        self.versuch('local_config /freigabe_katalog.yaml')

    @unittest.skipUnless(WIN, 'Windows-Eigenheit')
    def test_windows_datenstrom_und_praefix(self):
        self.versuch('runtime/src/sedra_runtime/harness/master.py::$DATA')
        self.versuch('runtime/src/sedra_runtime/harness/master.py:strom')
        self.versuch('\\\\?\\' + str(self.hdir / 'master.py'))
        self.versuch(str(self.hdir / 'master.py'))

    @unittest.skipUnless(WIN, 'Windows-Eigenheit')
    def test_windows_kurzname_8_3(self):
        import ctypes
        buf = ctypes.create_unicode_buffer(600)
        n = ctypes.windll.kernel32.GetShortPathNameW(str(self.hdir / 'master.py'), buf, 600)
        kurz = buf.value if n else ''
        if not kurz or kurz.lower() == str(self.hdir / 'master.py').lower():
            self.skipTest('auf diesem Datenträger gibt es keine 8.3-Kurznamen')
        self.versuch(os.path.relpath(kurz, str(self.root)))

    def test_junction_oder_link_auf_geschuetzten_ordner(self):
        link = self.root / 'docs' / 'weg'
        try:
            if WIN:
                subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(self.hdir)], check=True, capture_output=True)
            else:
                link.symlink_to(self.hdir, target_is_directory=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest('Verknüpfung nicht möglich')
        self.addCleanup(lambda: os.rmdir(link) if link.exists() else None)
        self.versuch('docs/weg/master.py')

    def test_junction_nach_aussen_beim_lesen_und_schreiben(self):
        aussen = Path(self.tmp.name) / 'aussen'
        aussen.mkdir()
        link = self.root / 'docs' / 'raus'
        try:
            if WIN:
                subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(aussen)], check=True, capture_output=True)
            else:
                link.symlink_to(aussen, target_is_directory=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest('Verknüpfung nicht möglich')
        self.addCleanup(lambda: os.rmdir(link) if link.exists() else None)
        self.an()
        r = self.kiste().aufruf('datei_schreiben', {'pfad': 'docs/raus/x.txt', 'inhalt': 'EVIL'})
        self.assertNotEqual(r['status'], 'ok', r)
        self.assertFalse((aussen / 'x.txt').exists())


# ------------------------------------------------------------------ A-4: Zustand und Rücknahme
class ZustandProben(Projekt):
    def test_neuer_zustand_ist_aus_wie_nach_dem_neustart(self):
        self.an()
        self.assertTrue(self.zustand.aktiv(SID))
        self.assertFalse(master.Zustand().aktiv(SID))                  # „Neustart“: ein neues Objekt weiß nichts (nichts steht in einer Datei)
        self.assertEqual([x.name for x in Path(self.tmp.name).rglob('*master*') if x.name != 'master.py'], [])

    def test_ablauf_genau_nach_24_stunden(self):
        t0 = datetime.now().astimezone()
        self.zustand.an(SID, 'p', ['**'], jetzt_z=t0)
        self.assertTrue(self.zustand.aktiv(SID, t0 + timedelta(hours=23, minutes=59)))
        self.assertFalse(self.zustand.aktiv(SID, t0 + timedelta(hours=24)))

    def test_erneutes_an_verlaengert_die_frist_nur_durch_den_captain_weg(self):
        """`an` ist die einzige Stelle, die die Frist setzt – das Modell hat kein Werkzeug dafür (MM-02)."""
        from sedra_runtime.harness.werkzeuge import NAMEN
        for n in NAMEN:
            self.assertNotIn('master', n)
        for n in ('gedaechtnis_vorschlagen', 'gedaechtnis_lesen', 'sitzung_nachricht'):
            self.assertNotIn('master', n)

    def test_aus_loest_die_ruecknahme_des_laufenden_befehls_aus(self):
        self.an()
        ereignis = befehl_mod.RUECKNAHME.ereignis(master.schluessel(SID))
        self.assertFalse(ereignis.is_set())
        self.zustand.aus(SID)
        self.assertTrue(ereignis.is_set())
        self.an()                                                      # erneutes Einschalten vergisst das alte Aus (sonst bräche der nächste Befehl sofort ab)
        self.assertFalse(befehl_mod.RUECKNAHME.ereignis(master.schluessel(SID)).is_set())

    def test_ablauf_loest_die_ruecknahme_aus(self):
        t0 = datetime.now().astimezone()
        self.zustand.an(SID, 'p', ['**'], jetzt_z=t0)
        ereignis = befehl_mod.RUECKNAHME.ereignis(master.schluessel(SID))
        self.zustand.aktiv(SID, t0 + timedelta(hours=25))
        self.assertTrue(ereignis.is_set())

    def test_kaputter_zustand_ist_nie_frei(self):
        self.an()
        self.zustand._an[SID]['bis'] = 'kein-datum'
        self.assertFalse(self.zustand.aktiv(SID))
        self.assertIsNone(self.zustand.deckt(SID, 'p', self.root, 'datei_lesen', 'docs/x', {}))
        self.zustand._an[SID] = 'kaputt'                               # ganz kaputter Eintrag
        self.assertIsNone(self.zustand.deckt(SID, 'p', self.root, 'datei_lesen', 'docs/x', {}))

    def test_ungueltiges_muster_feld_schaltet_nicht_ein(self):
        for roh in (['../**'], ['C:/x'], ['/abs'], [''], 'docs/**', [1], {'a': 'b'}):
            with self.assertRaises(master.MasterFehler):
                self.zustand.an(SID, 'p', roh)
        self.assertFalse(self.zustand.aktiv(SID))
        with self.assertRaises(master.MasterFehler):
            self.zustand.an(SID, 'p', [])                              # kein Feld = nicht möglich
        self.assertFalse(self.zustand.aktiv(SID))

    def test_wiederholungsdeckel_gilt_unter_dem_master(self):
        self.an()
        k = self.kiste()
        st = [k.aufruf('befehl', {'befehl': 'python --version', 'ordner': 'docs'})['status'] for _ in range(4)]
        self.assertEqual(st[:2], ['ok', 'ok'])
        self.assertEqual(st[2], 'wartet', st)

    def test_anderes_projekt_und_andere_sitzung_decken_nicht(self):
        self.an()
        self.assertIsNone(self.zustand.deckt('S-00000002', 'p', self.root, 'datei_lesen', 'docs/a.md', {}))
        self.assertIsNone(self.zustand.deckt(SID, 'q', self.root, 'datei_lesen', 'docs/a.md', {}))

    def test_cloud_modell_bleibt_karte(self):
        self.an()
        r = self.kiste(lokal=False).aufruf('datei_schreiben', {'pfad': 'docs/a.md', 'inhalt': 'x'})
        self.assertEqual(r['status'], 'wartet')

    def test_audit_je_aufruf_vollstaendig(self):
        self.an()
        k = self.kiste()
        k.aufruf('datei_schreiben', {'pfad': 'docs/a.md', 'inhalt': 'x'})
        k.aufruf('befehl', {'befehl': 'python -c x', 'ordner': 'docs'})
        self.assertEqual(len(self.audit.alle('HARNESS_MASTER_AN')), 1)
        self.assertEqual(len(self.audit.alle('HARNESS_MASTER_AUFRUF')), 1)
        self.assertEqual(len(self.audit.alle('HARNESS_MASTER_NICHT')), 1)
        self.assertEqual(self.audit.alle('HARNESS_MASTER_AUFRUF')[0]['ziel'], 'docs/a.md')
        self.zustand.aus(SID)
        self.assertEqual(len(self.audit.alle('HARNESS_MASTER_AUS')), 1)


if __name__ == '__main__':
    unittest.main()
