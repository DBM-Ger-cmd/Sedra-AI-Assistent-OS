"""G4 (docs/SPEC_APPS_v1_G4_MODELLCODE_G2.md): Läufe und Befehle der Harness nur nach Sicht auf geänderten Code.

Teil 1 prüft `harness/code_stand.py` allein, Teil 2 den Vorbehalt, Teil 3 den ganzen Weg mit echtem Guard: das Modell schreibt Code (Katalog frei),
startet einen Befehl → Karte mit dem Code; der Captain gibt frei → der Befehl läuft, der Code gilt als gesehen; der nächste Befehl läuft ohne Karte."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guppi_runtime.core.guard import Guard
from guppi_runtime.harness import code_stand as cs_mod
from guppi_runtime.harness import vorbehalte
from guppi_runtime.harness.code_stand import CodeStand, ist_code, nur_pruefen
from guppi_runtime.harness.freigabe import Karten, Kiste, beantworten, einstufung
from guppi_runtime.harness.werkzeuge import Werkzeuge

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
MISSION = 'M-CODESTAND'


class Projekt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'projekt'
        (self.root / 'tools').mkdir(parents=True)
        (self.root / 'docs').mkdir()
        (self.root / 'tools' / 'skript.py').write_text('print("alt")\n', encoding='utf-8')
        (self.root / 'docs' / 'notiz.md').write_text('kein Code\n', encoding='utf-8')
        self.ablage = Path(self.tmp.name) / 'runtime_data' / 'harness' / 'code_stand'
        self.gemeldet = []
        self.cs = CodeStand(self.ablage, self.root, 'p', audit=lambda e, p: self.gemeldet.append((e, p)))

    def schreiben(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        st = p.stat()
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))       # sicher eine neue Änderungszeit, auch auf groben Dateisystemen


class Erkennung(unittest.TestCase):
    def test_code_dateien(self):
        for rel in ('a.py', 'x/conftest.py', 'b.JS', 'c.ps1', 'd.bat', 'pytest.ini', 'package.json', 'pyproject.toml', 'e.pth', 'f.exe'):
            self.assertTrue(ist_code(rel), rel)
        for rel in ('a.md', 'b.yaml', 'c.json', 'd.txt', 'e.css', 'f.html'):
            self.assertFalse(ist_code(rel), rel)

    def test_nur_pruefen(self):
        self.assertTrue(nur_pruefen('python -m py_compile tools/a.py'))
        self.assertTrue(nur_pruefen('node  --check  ui/x.js'))
        self.assertFalse(nur_pruefen('python tools/a.py'))
        self.assertFalse(nur_pruefen('python -m py_compilex a.py'))


class Stand(Projekt):
    def test_ausgangsstand_gilt_als_gesehen_und_wird_gemeldet(self):
        self.assertEqual(self.cs.ungesehen(), [])
        self.assertEqual([e for e, _ in self.gemeldet], ['HARNESS_CODE_STAND_ANGELEGT'])
        self.assertEqual(self.gemeldet[0][1]['dateien'], 1)
        self.cs.ungesehen()
        self.assertEqual(len(self.gemeldet), 1, 'nur beim ersten Gebrauch')

    def test_aenderung_neu_und_geloescht_sind_ungesehen(self):
        self.cs.stand()
        self.schreiben('tools/skript.py', 'print("neu")\n')
        self.schreiben('tools/neu.py', 'x = 1\n')
        self.schreiben('docs/notiz.md', 'geändert, aber kein Code\n')
        liste = {e['pfad']: e for e in self.cs.ungesehen()}
        self.assertEqual(set(liste), {'tools/skript.py', 'tools/neu.py'})
        self.assertIsNone(liste['tools/neu.py']['alt'])
        (self.root / 'tools' / 'skript.py').unlink()
        liste = {e['pfad']: e for e in self.cs.ungesehen()}
        self.assertIsNone(liste['tools/skript.py']['neu'])

    def test_ausgelassene_ordner_zaehlen_nicht(self):
        self.cs.stand()
        for rel in ('node_modules/x.js', '.git/hooks/pre-commit.sh', 'runtime_data/y.py', '__pycache__/z.py', '.versteckt/a.py',
                    'runtime/portable/python/current/Lib/os.py', 'runtime/portable/python.aus/current/Lib/site.py', 'runtime/portable/sandbox/x.ps1'):
            self.schreiben(rel, 'x\n')
        self.assertEqual(self.cs.ungesehen(), [])
        self.schreiben('tools/portable/x.py', 'nur runtime/portable ist ausgenommen\n')
        self.assertEqual([e['pfad'] for e in self.cs.ungesehen()], ['tools/portable/x.py'])

    def test_gesehen_setzen_nur_bei_der_gebundenen_fassung(self):
        self.cs.stand()
        self.schreiben('tools/skript.py', 'print("eins")\n')
        bindung = cs_mod.bindung(self.cs.ungesehen())
        self.schreiben('tools/skript.py', 'print("zwei")\n')               # nach der Karte noch einmal geändert
        self.assertEqual(self.cs.gesehen_setzen(bindung), 0)
        self.assertEqual(len(self.cs.ungesehen()), 1)
        self.assertEqual(self.cs.gesehen_setzen(cs_mod.bindung(self.cs.ungesehen())), 1)
        self.assertEqual(self.cs.ungesehen(), [])

    def test_vorige_fassung_nur_wenn_sie_gesehen_war(self):
        self.cs.stand()
        sha = self.cs.vorher_merken('tools/skript.py')
        self.assertTrue((self.ablage / 'vorher' / sha).is_file())
        self.schreiben('tools/skript.py', 'print("ungesehen")\n')
        sha2 = self.cs.vorher_merken('tools/skript.py')
        self.assertFalse((self.ablage / 'vorher' / sha2).exists(), 'eine ungesehene Fassung wird nicht als „gesehen“ abgelegt')
        self.assertIsNone(self.cs.vorher_merken('docs/notiz.md'))

    def test_ueber_karte_geschrieben_gilt_nur_bei_gesehener_vorgaengerin(self):
        self.cs.stand()
        alt = self.cs.vorher_merken('tools/skript.py')
        self.schreiben('tools/skript.py', 'print("vom captain gesehen")\n')
        self.assertTrue(self.cs.schreiben_gesehen('tools/skript.py', alt))
        self.assertEqual(self.cs.ungesehen(), [])
        self.schreiben('tools/skript.py', 'print("unbemerkt")\n')                 # ungesehene Zwischenfassung …
        alt = self.cs.vorher_merken('tools/skript.py')
        self.schreiben('tools/skript.py', 'print("darauf aufgebaut")\n')         # … darauf eine Karte: zeigt nur den letzten Schritt
        self.assertFalse(self.cs.schreiben_gesehen('tools/skript.py', alt))
        self.assertEqual(len(self.cs.ungesehen()), 1)

    def test_neue_datei_ueber_karte_gilt_als_gesehen(self):
        self.cs.stand()
        self.assertIsNone(self.cs.vorher_merken('tools/neu.py'))
        self.schreiben('tools/neu.py', 'x = 2\n')
        self.assertTrue(self.cs.schreiben_gesehen('tools/neu.py', None))
        self.assertEqual(self.cs.ungesehen(), [])

    def test_uebernehmen(self):
        self.cs.stand()
        self.schreiben('tools/a.py', 'a\n')
        self.schreiben('tools/b.py', 'b\n')
        self.cs.spur('tools/a.py', 'S-1', 'aufgabe')
        self.assertEqual(self.cs.uebernehmen(), 2)
        self.assertEqual(self.cs.ungesehen(), [])
        self.assertEqual(json.loads((self.ablage / 'p.spur.json').read_text(encoding='utf-8')), {})

    def test_nur_geaenderte_dateien_werden_neu_gehasht(self):
        self.cs.stand()
        self.schreiben('tools/zwei.py', 'zwei\n')
        self.cs.ungesehen()
        with mock.patch.object(cs_mod, '_sha_datei', wraps=cs_mod._sha_datei) as sha:
            self.cs.ungesehen()
            self.assertEqual(sha.call_count, 0)
            self.schreiben('tools/zwei.py', 'drei\n')
            self.cs.ungesehen()
            self.assertEqual(sha.call_count, 1)


class Vorschau(Projekt):
    def test_harness_zuerst_mit_diff_dann_aussen_ohne_vorige_fassung(self):
        self.cs.stand()
        self.cs.vorher_merken('tools/skript.py')
        self.schreiben('tools/skript.py', 'print("von der harness")\n')
        self.cs.spur('tools/skript.py', 'S-12345678', 'sitzung')
        self.schreiben('zzz.py', 'print("von außen, neu")\n')
        text, zu_gross = self.cs.vorschau(self.cs.ungesehen())
        self.assertFalse(zu_gross)
        self.assertLess(text.index('tools/skript.py'), text.index('zzz.py'))
        self.assertIn('Sitzung S-12345678, Weg sitzung', text)
        self.assertIn('-print("alt")', text)
        self.assertIn('+print("von der harness")', text)
        self.assertIn('zzz.py – neu (außerhalb der Harness geändert)', text)

    def test_zu_viele_dateien(self):
        self.cs.stand()
        for i in range(cs_mod.KARTE_DATEIEN_MAX + 1):
            self.schreiben(f'gen/m{i:02d}.py', f'x = {i}\n')
        text, zu_gross = self.cs.vorschau(self.cs.ungesehen())
        self.assertTrue(zu_gross)
        self.assertIn('CODE_STAND.bat p --zeigen', text)

    def test_zu_viele_zeilen(self):
        self.cs.stand()
        self.schreiben('gross.py', 'x = 1\n' * (cs_mod.KARTE_ZEILEN_MAX + 5))
        self.assertTrue(self.cs.vorschau(self.cs.ungesehen())[1])


class Vorbehalt(unittest.TestCase):
    def test_befehl_und_lauf_mit_ungesehenem_code(self):
        liste = [{'pfad': 'a.py', 'alt': None, 'neu': 'h'}]
        for werkzeug in ('befehl', 'lauf_starten'):
            grund = vorbehalte.pruefen(werkzeug, 'python a.py', {}, ungesehen=liste)
            self.assertIn('noch nicht gesehen', grund)
            self.assertIn('1 Datei)', grund)
        self.assertIsNone(vorbehalte.pruefen('befehl', 'python a.py', {}, ungesehen=[]))
        self.assertIsNone(vorbehalte.pruefen('datei_lesen', 'a.py', {}, ungesehen=liste))

    def test_einstufung_macht_einen_harten_vorbehalt(self):
        e = einstufung([], 'befehl', {}, {'ziel': 'python a.py', 'code_ungesehen': [{'pfad': 'a.py', 'alt': None, 'neu': 'h'}]})
        self.assertTrue(e['vorbehalt'])
        self.assertEqual(e['wirkt_als'], 'captain')

    def test_code_stand_ist_selbst_harness_code_unter_vorbehalt(self):
        grund = vorbehalte.pruefen('datei_aendern', 'runtime/src/guppi_runtime/harness/code_stand.py', {})
        self.assertIn('Code-Stand', grund)

    def test_portable_laufzeit_ist_vorbehalt(self):
        """G4 scannt runtime/portable nicht – dafür schreibt das Modell dort nicht (sonst liefe z. B. ein sitecustomize.py ungesehen)."""
        grund = vorbehalte.pruefen('datei_schreiben', 'runtime/portable/python/current/Lib/site-packages/sitecustomize.py', {'inhalt': 'x'})
        self.assertIn('portable Laufzeit', grund)


class Weg(Projekt):
    """Ganzer Weg mit echtem Guard; Katalog: Schreiben und `python *` frei – wie eine großzügige Sitzung."""

    def setUp(self):
        super().setUp()
        self.guard = Guard(ARCH / 'core' / 'guard' / 'guard_rules.yaml', None, Path(self.tmp.name) / 'tokens.json')
        regel = lambda rid, werkzeug, muster, stufe: {'id': rid, 'werkzeug': werkzeug, 'muster': muster, 'stufe': stufe, 'begruendung': rid}
        self.regeln = [regel('lesen', ['datei_lesen', 'dateien_auflisten', 'suchen'], ['**'], 'frei'),
                       regel('schreiben', ['datei_schreiben', 'datei_aendern'], ['**'], 'frei'),
                       regel('python', ['befehl'], ['python *'], 'frei')]
        projekt = {'id': 'p', 'name': 'P', 'wurzel': str(self.root), 'schreibbereich': ['**']}
        self.w = Werkzeuge(projekt, guard=self.guard, mission_id=MISSION, regeln=self.regeln, code_stand=self.cs)
        self.karten = Karten(Path(self.tmp.name) / 'karten')
        self.kiste = Kiste(self.w, regeln=self.regeln, guard=self.guard, audit=None, karten=self.karten, sitzung_id='S-00000001')

    def antworten(self, karte, weg='erlauben'):
        return beantworten(self.karten, karte['karte_id'], weg, guard=self.guard, audit=None, werkzeuge_fuer=lambda k: self.w)

    def test_ohne_ungesehenen_code_laeuft_der_befehl_frei(self):
        out = self.kiste.aufruf('befehl', {'befehl': 'python tools/skript.py'})
        self.assertEqual(out['status'], 'ok', out)
        self.assertIn('alt', out['ergebnis'])

    def test_modell_schreibt_code_dann_braucht_der_befehl_eine_karte(self):
        self.cs.stand()
        geschrieben = self.kiste.aufruf('datei_aendern', {'pfad': 'tools/skript.py', 'alt': 'print("alt")', 'neu': 'print("vom modell")'})
        self.assertEqual(geschrieben['status'], 'ok', geschrieben)
        out = self.kiste.aufruf('befehl', {'befehl': 'python tools/skript.py'})
        self.assertEqual(out['status'], 'wartet', out)
        karte = out['karte']
        self.assertTrue(karte['vorbehalt'])
        self.assertIn('+print("vom modell")', karte['vorschau'])
        self.assertIn('Weg katalog', karte['vorschau'])
        antwort = self.antworten(karte)
        self.assertEqual(antwort['status'], 'ok', antwort)
        self.assertIn('vom modell', antwort['ergebnis'])
        self.assertEqual(self.cs.ungesehen(), [], 'nach der Freigabe gilt der Code als gesehen')
        self.assertEqual(self.kiste.aufruf('befehl', {'befehl': 'python tools/skript.py'})['status'], 'ok', 'danach wieder ohne Karte')

    def test_nur_pruefen_laeuft_trotz_ungesehenem_code(self):
        self.cs.stand()
        self.kiste.aufruf('datei_aendern', {'pfad': 'tools/skript.py', 'alt': 'print("alt")', 'neu': 'print("neu")'})
        out = self.kiste.aufruf('befehl', {'befehl': 'python -m py_compile tools/skript.py'})
        self.assertEqual(out['status'], 'ok', out)
        self.assertEqual(len(self.cs.ungesehen()), 1, 'Prüfen macht den Code nicht gesehen')

    def test_fuer_diese_sitzung_erlauben_geht_nicht(self):
        self.cs.stand()
        self.kiste.aufruf('datei_aendern', {'pfad': 'tools/skript.py', 'alt': 'print("alt")', 'neu': 'print("neu")'})
        karte = self.kiste.aufruf('befehl', {'befehl': 'python tools/skript.py'})['karte']
        with self.assertRaises(ValueError):
            self.antworten(karte, 'sitzung')

    def test_aenderung_zwischen_karte_und_antwort(self):
        self.cs.stand()
        self.kiste.aufruf('datei_aendern', {'pfad': 'tools/skript.py', 'alt': 'print("alt")', 'neu': 'print("gezeigt")'})
        karte = self.kiste.aufruf('befehl', {'befehl': 'python tools/skript.py'})['karte']
        self.schreiben('tools/skript.py', 'print("danach getauscht")\n')
        antwort = self.antworten(karte)
        self.assertNotEqual(antwort['status'], 'ok')
        self.assertNotIn('danach getauscht', antwort['ergebnis'], 'der getauschte Code läuft nicht')
        self.assertEqual(len(self.cs.ungesehen()), 1)

    def test_einzeln_vom_captain_freigegebenes_schreiben_gilt_als_gesehen(self):
        self.cs.stand()
        self.regeln[1]['stufe'] = 'captain'
        out = self.kiste.aufruf('datei_aendern', {'pfad': 'tools/skript.py', 'alt': 'print("alt")', 'neu': 'print("diff gesehen")'})
        self.assertEqual(out['status'], 'wartet', out)
        self.assertEqual(self.antworten(out['karte'])['status'], 'ok')
        self.assertEqual(self.cs.ungesehen(), [])
        self.assertEqual(self.kiste.aufruf('befehl', {'befehl': 'python tools/skript.py'})['status'], 'ok')

    def test_zu_viel_code_laesst_sich_nicht_im_browser_freigeben(self):
        self.cs.stand()
        for i in range(cs_mod.KARTE_DATEIEN_MAX + 1):
            self.schreiben(f'gen/m{i:02d}.py', f'x = {i}\n')
        karte = self.kiste.aufruf('befehl', {'befehl': 'python tools/skript.py'})['karte']
        with self.assertRaises(ValueError) as fehler:
            self.antworten(karte)
        self.assertIn('code_zu_gross', str(fehler.exception))
        self.assertEqual(self.karten.laden(karte['karte_id'])['status'], 'offen', 'nichts entschieden, die Karte bleibt offen')
        self.cs.uebernehmen()
        self.assertEqual(self.kiste.aufruf('befehl', {'befehl': 'python tools/skript.py'})['status'], 'ok')

    def test_ohne_code_stand_wie_bisher(self):
        projekt = {'id': 'p', 'name': 'P', 'wurzel': str(self.root), 'schreibbereich': ['**']}
        w = Werkzeuge(projekt, guard=self.guard, mission_id=MISSION, regeln=self.regeln)
        kiste = Kiste(w, regeln=self.regeln, guard=self.guard, audit=None, karten=self.karten, sitzung_id='S-00000002')
        kiste.aufruf('datei_aendern', {'pfad': 'tools/skript.py', 'alt': 'print("alt")', 'neu': 'print("ohne g4")'})
        self.assertEqual(kiste.aufruf('befehl', {'befehl': 'python tools/skript.py'})['status'], 'ok')


class Konsole(Projekt):
    """G4-16: `guppi code-stand <projekt> [--uebernehmen]` – außerhalb des Browsers, mit Eintrag im Audit."""

    def setUp(self):
        super().setUp()
        self.wurzel_root = Path(self.tmp.name)                       # <root>: dieselbe Ablage wie die Oberfläche (runtime_data/harness/code_stand)
        (self.wurzel_root / 'local_config').mkdir()
        (self.wurzel_root / 'runtime_data' / 'harness').mkdir(parents=True, exist_ok=True)
        (self.wurzel_root / 'local_config' / 'harness_projekte.yaml').write_text(
            'projekte:\n  - id: p\n    name: P\n    wurzel: ' + json.dumps(str(self.root)) + '\n    schreibbereich: ["**"]\n', encoding='utf-8')

    def cli(self, *argv):
        import contextlib, io
        from guppi_runtime import cli
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(['--root', str(self.wurzel_root), 'code-stand', *argv])
        return code, out.getvalue()

    def test_zeigen_und_uebernehmen(self):
        self.cs.stand()
        self.schreiben('tools/neu.py', 'x = 1\n')
        code, text = self.cli('p')
        self.assertEqual(code, 0)
        self.assertIn('tools/neu.py – neu', text)
        self.assertEqual(self.cli('p', '--zeigen'), (code, text), '--zeigen (so nennt es die Karte) ist der Standard')
        code, text = self.cli('p', '--uebernehmen')
        self.assertEqual((code, json.loads(text)['anzahl']), (0, 1))
        self.assertEqual(self.cs.ungesehen(), [])
        ereignisse = [json.loads(z)['event_type'] for z in (self.wurzel_root / 'runtime_data' / 'audit' / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertIn('HARNESS_CODE_STAND_UEBERNOMMEN', ereignisse)
        self.assertIn('Kein ungesehener Code', self.cli('p')[1])

    def test_falscher_root_wird_abgelehnt(self):
        import contextlib, io
        from guppi_runtime import cli
        leer = Path(self.tmp.name) / 'kein_projektordner'
        leer.mkdir()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(['--root', str(leer), 'code-stand', 'p', '--uebernehmen'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())['error'], 'root_ist_nicht_der_projektordner')
        self.assertFalse((leer / 'runtime_data').exists(), 'kein zweiter Stand angelegt')

    def test_schlanker_einstieg_wie_code_stand_bat(self):
        """CODE_STAND.bat ruft `python -m guppi_runtime.harness.code_stand --root … <projekt>` – ohne cli.py und ohne die ganze Runtime (Stick)."""
        import subprocess, sys
        self.cs.stand()
        self.schreiben('tools/neu.py', 'x = 1\n')
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
        for zusatz in ([], ['--zeigen']):                                  # die Karte nennt „CODE_STAND.bat <projekt> --zeigen“
            r = subprocess.run([sys.executable, '-m', 'guppi_runtime.harness.code_stand', '--root', str(self.wurzel_root), 'p', *zusatz],
                               capture_output=True, text=True, encoding='utf-8', env=env, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('tools/neu.py – neu', r.stdout)
        r = subprocess.run([sys.executable, '-m', 'guppi_runtime.harness.code_stand', '--root', str(self.wurzel_root), 'p', '--uebernehmen'],
                           capture_output=True, text=True, encoding='utf-8', env=env, timeout=60)
        self.assertEqual((r.returncode, json.loads(r.stdout)['anzahl']), (0, 1), r.stderr)
        self.assertEqual(self.cs.ungesehen(), [])

    def test_unbekanntes_projekt(self):
        code, text = self.cli('gibt-es-nicht')
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(text)['projekte'], ['p'])


class Route(Projekt):
    """G4-17: GET /api/harness/code_stand?projekt= – nur lesen; Schalter `code_sicht` aus → nicht aktiv."""

    def api(self, schalter=None):
        from types import SimpleNamespace
        from guppi_runtime.harness.api import HarnessApi
        from guppi_runtime.local_switches import LocalSwitches
        self.wurzel_root = Path(self.tmp.name)
        hub = SimpleNamespace(project_root=self.wurzel_root, runtime=SimpleNamespace(switches=LocalSwitches(schalter or {}), audit=mock.Mock()))
        a = HarnessApi.__new__(HarnessApi)
        a.hub, a._code_staende = hub, {}
        a._audit = lambda e, p: None
        a._projekt = lambda pid: {'id': 'p', 'name': 'P', 'wurzel': str(self.root), 'schreibbereich': ['**']}
        return a

    def test_zahl_und_pfade(self):
        a = self.api()
        self.assertEqual(a.code_stand_sicht({'projekt': ['p']})['ungesehen'], 0)
        self.schreiben('tools/neu.py', 'x = 1\n')
        sicht = a.code_stand_sicht({'projekt': ['p']})
        self.assertEqual((sicht['aktiv'], sicht['ungesehen'], sicht['pfade']), (True, 1, ['tools/neu.py']))
        if os.name != 'nt':
            self.assertIn(f'code_stand --root "{self.wurzel_root}" p', sicht['konsole'], 'die Konsole nennt genau den Projektordner dieses Servers')
        else:
            self.assertEqual(sicht['konsole'], 'CODE_STAND.bat p')

    def test_einstufen_zeigt_den_vorbehalt(self):
        """B8: die Einstufungs-Vorschau (Katalog-Editor) sagt dasselbe wie der echte Aufruf."""
        a = self.api()
        a.projekte = lambda: {'projekte': [{'id': 'p', 'name': 'P', 'wurzel': str(self.root), 'schreibbereich': ['**']}]}
        a._regeln = lambda: ([{'id': 'python', 'werkzeug': ['befehl'], 'muster': ['python *'], 'stufe': 'frei', 'begruendung': 'x'}], None)
        self.assertFalse(a.einstufen({'werkzeug': 'befehl', 'ziel': 'python tools/skript.py', 'projekt': 'p'})['vorbehalt'])
        self.schreiben('tools/skript.py', 'print("neu")\n')
        e = a.einstufen({'werkzeug': 'befehl', 'ziel': 'python tools/skript.py', 'projekt': 'p'})
        self.assertTrue(e['vorbehalt'])
        self.assertFalse(a.einstufen({'werkzeug': 'befehl', 'ziel': 'python -m py_compile tools/skript.py', 'projekt': 'p'})['vorbehalt'])
        self.assertIn('G4', a.einstufen({'werkzeug': 'befehl', 'ziel': 'python tools/skript.py'})['hinweis'])

    def test_schalter_aus(self):
        a = self.api({'code_sicht': {'enabled': False}})
        self.assertIsNone(a.code_stand({'id': 'p', 'wurzel': str(self.root)}))
        self.assertFalse(a.code_stand_sicht({'projekt': ['p']})['aktiv'])


if __name__ == '__main__':
    unittest.main()
