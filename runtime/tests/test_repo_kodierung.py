"""Kodierung und Lesbarkeit der versionierten Quellen (16.11.2026, Befund nach der Integration von uix-3d): ein Schreibwerkzeug speicherte sieben Dateien als UTF-8 **mit BOM**. Python startet damit,
aber `ast.parse(read_text(…))` in den Prüfstellen der Freigabe (`test_freigabe_vollstaendig`) bricht ab – und der Fehler verdeckte einen zweiten, echten. Dieser Test findet es früher und überall:

1. Keine versionierte Textdatei (Quellen, Doku, Konfiguration) beginnt mit einem BOM.
2. Jede versionierte Python-Datei unter `runtime/src`, `runtime/tests` und `runtime/benchmarks` ist lesbar (`ast.parse`) – eine Testdatei mit Syntaxfehler lässt sonst ganze Gruppen ohne Ergebnis.
3. Jede versionierte JSON-Datei und jedes Manifest/jede Konfiguration (YAML) unter `runtime/` ist lesbar.
Die Prüfung nutzt `git ls-files`; ohne Git (etwa in einem entpackten Paket) wird sie übersprungen."""
import ast
import json
import subprocess
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TEXT = {'.py', '.js', '.css', '.html', '.md', '.yaml', '.yml', '.json', '.txt'}
PY_ORDNER = ('runtime/src/', 'runtime/tests/', 'runtime/benchmarks/')
AUSGENOMMEN = ('devvm_seeds', 'devvm_snapshots', '_template', 'fixtures', 'node_modules', '/vendor/', '.venv/', 'portable/')       # absichtlich unvollständig oder nicht von uns
BOM = b'\xef\xbb\xbf'


def versioniert():
    try:
        out = subprocess.run(['git', 'ls-files', '-z'], cwd=REPO, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [n for n in out.decode('utf-8', errors='replace').split('\0') if n and not any(a in n for a in AUSGENOMMEN)]


def hat_bom(daten):
    return daten.startswith(BOM)


class Kodierung(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dateien = versioniert()
        if cls.dateien is None:
            raise unittest.SkipTest('kein Git: die Kodierung der versionierten Dateien lässt sich nicht listen')

    def test_kein_bom_in_versionierten_textdateien(self):
        fehler = []
        for name in self.dateien:
            if Path(name).suffix.lower() in TEXT:
                p = REPO / name
                if p.is_file():
                    with open(p, 'rb') as f:
                        if hat_bom(f.read(3)):
                            fehler.append(name)
        self.assertEqual(fehler, [], 'Datei mit BOM am Anfang (als UTF-8 ohne BOM speichern: Python startet damit, aber `ast.parse(read_text())` der Prüfstellen bricht ab)')

    def test_python_dateien_sind_lesbar(self):
        fehler = []
        for name in self.dateien:
            if name.endswith('.py') and name.startswith(PY_ORDNER) and (REPO / name).is_file():
                try:
                    ast.parse((REPO / name).read_bytes().decode('utf-8-sig'), filename=name)
                except (SyntaxError, ValueError, UnicodeDecodeError) as exc:
                    fehler.append(f'{name}: {type(exc).__name__}: {str(exc)[:90]}')
        self.assertEqual(fehler, [], 'Python-Datei nicht lesbar (Syntaxfehler lässt ganze Testgruppen ohne Ergebnis)')

    def test_json_und_yaml_sind_lesbar(self):
        fehler = []
        for name in self.dateien:
            if not name.startswith('runtime/') or not (REPO / name).is_file():
                continue
            endung = Path(name).suffix.lower()
            if endung not in ('.json', '.yaml', '.yml'):
                continue
            if '/tests/' in name or 'beispiel' in name or 'example' in name or '/devvm_' in name:
                continue                                                  # Beispiele und Testdaten dürfen unvollständig sein
            try:
                text = (REPO / name).read_bytes().decode('utf-8-sig')
                if endung == '.json':
                    json.loads(text)
                else:
                    list(yaml.safe_load_all(text))
            except (ValueError, yaml.YAMLError, UnicodeDecodeError) as exc:
                fehler.append(f'{name}: {type(exc).__name__}: {str(exc)[:90]}')
        self.assertEqual(fehler, [], 'JSON oder YAML nicht lesbar')


class Gegenprobe(unittest.TestCase):
    def test_die_pruefung_erkennt_ein_bom(self):
        self.assertTrue(hat_bom(b'\xef\xbb\xbf"""Doc"""'))
        self.assertFalse(hat_bom(b'"""Doc"""'))

    def test_ast_parse_scheitert_wirklich_am_bom_im_text(self):
        """Das ist der Fehler der Prüfstellen: `read_text(encoding='utf-8')` behält das BOM, `ast.parse` lehnt es ab."""
        with self.assertRaises(SyntaxError):
            ast.parse(BOM.decode('utf-8') + '"""Doc"""')
        ast.parse((BOM + b'"""Doc"""').decode('utf-8-sig'))               # mit utf-8-sig geht es – das nutzt dieser Test, um Dateien zu lesen und trotzdem das BOM zu melden


if __name__ == '__main__':
    unittest.main()
