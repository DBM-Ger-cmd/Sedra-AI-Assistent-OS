"""Umstiegs-Installer auf die SEDRA-Namen: Vorschau schreibt nichts, Anwenden sichert, Rollback stellt den Ausgangszustand her."""
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'runtime/src'))
from sedra_runtime import legacy_names as ln  # noqa: E402

spec = importlib.util.spec_from_file_location('install_namenswechsel', REPO / 'release/install_namenswechsel.py')
inst = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inst)


def baum(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()}


class Umstieg(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        self.cand, self.root = base / 'paket', base / 'installation'
        # Paket
        src = self.cand / 'runtime/src/sedra_runtime'
        src.mkdir(parents=True)
        shutil.copy2(REPO / 'runtime/src/sedra_runtime/legacy_names.py', src / 'legacy_names.py')
        (src / '__init__.py').write_text('', encoding='utf-8')
        (src / 'neu.py').write_text('x = 1\n', encoding='utf-8')
        (self.cand / 'runtime/config').mkdir(parents=True)
        (self.cand / 'runtime/config/a.yaml').write_text('neu: 1\n', encoding='utf-8')
        (self.cand / 'architecture' / (ln.ARCHITEKTUR_NEU + 'v1')).mkdir(parents=True)
        (self.cand / 'architecture' / (ln.ARCHITEKTUR_NEU + 'v1') / 'k.txt').write_text('k', encoding='utf-8')
        (self.cand / 'START_SEDRA.bat').write_bytes(b'neuer start\r\n')
        self.schreibe_manifest()
        # alte Installation
        (self.root / 'runtime/src' / ln.PAKET_ALT).mkdir(parents=True)
        (self.root / 'runtime/src' / ln.PAKET_ALT / 'alt.py').write_text('y = 2\n', encoding='utf-8')
        (self.root / 'runtime/config').mkdir(parents=True)
        (self.root / 'runtime/config/a.yaml').write_text('alt: 1\n', encoding='utf-8')
        (self.root / 'runtime/config/local_paths.yaml').write_text('modelle: X\n', encoding='utf-8')
        (self.root / 'architecture' / (ln.ARCHITEKTUR_ALT + 'v1')).mkdir(parents=True)
        (self.root / 'architecture' / (ln.ARCHITEKTUR_ALT + 'v1') / 'k.txt').write_text('alt', encoding='utf-8')
        (self.root / 'workspace' / ln.PROJEKTORDNER_ALT / 'runtime_data').mkdir(parents=True)
        (self.root / 'workspace' / ln.PROJEKTORDNER_ALT / 'runtime_data' / 'd.txt').write_text('daten', encoding='utf-8')
        (self.root / 'START_SEDRA.bat').write_bytes(b'alter start\r\n')

    def schreibe_manifest(self):
        zeilen = []
        for rel in ('runtime/src/sedra_runtime/__init__.py', 'runtime/src/sedra_runtime/legacy_names.py', 'runtime/src/sedra_runtime/neu.py',
                    'runtime/config/a.yaml', 'architecture/' + ln.ARCHITEKTUR_NEU + 'v1/k.txt', 'START_SEDRA.bat'):
            zeilen.append(hashlib.sha256((self.cand / rel).read_bytes()).hexdigest() + '  ' + rel)
        (self.cand / 'release').mkdir(exist_ok=True)
        (self.cand / inst.MANIFEST).write_text('\n'.join(zeilen) + '\n', encoding='utf-8')

    def test_vorschau_schreibt_nichts(self):
        vorher = baum(self.root)
        plan, schluessel, _, _ = inst.vorschau(self.cand, self.root)
        self.assertEqual(baum(self.root), vorher)
        self.assertTrue(plan['altes_programmpaket_wird_gesichert'])
        self.assertTrue(plan['projektordner_wird_umbenannt'])
        self.assertEqual(len(schluessel), 64)

    def test_anwenden_stellt_um_und_sichert(self):
        plan, schluessel, erwartet, lnm = inst.vorschau(self.cand, self.root)
        r = inst.anwenden(self.cand, self.root, erwartet, lnm)
        self.assertEqual(r['status'], 'umgestellt')
        self.assertEqual((self.root / 'runtime/src/sedra_runtime/neu.py').read_text(encoding='utf-8'), 'x = 1\n')
        self.assertEqual((self.root / 'runtime/config/a.yaml').read_text(encoding='utf-8'), 'neu: 1\n')
        self.assertEqual((self.root / 'runtime/config/local_paths.yaml').read_text(encoding='utf-8'), 'modelle: X\n')
        self.assertEqual((self.root / 'START_SEDRA.bat').read_bytes(), b'neuer start\r\n')
        self.assertEqual((self.root / 'workspace' / ln.PROJEKTORDNER_NEU / 'runtime_data' / 'd.txt').read_text(encoding='utf-8'), 'daten')
        self.assertFalse((self.root / 'workspace' / ln.PROJEKTORDNER_ALT).exists())
        sicherung = self.root / 'local_config/update/sicherung/alt_namen'
        self.assertTrue((sicherung / ln.PAKET_ALT / 'alt.py').is_file())
        self.assertTrue((sicherung / (ln.ARCHITEKTUR_ALT + 'v1') / 'k.txt').is_file())
        self.assertTrue((self.root / inst.PROTOKOLL).is_file())

    def test_rollback_stellt_den_ausgangszustand_her(self):
        vorher = baum(self.root)
        _, _, erwartet, lnm = inst.vorschau(self.cand, self.root)
        inst.anwenden(self.cand, self.root, erwartet, lnm)
        r = inst.zuruecknehmen(self.root, lnm)
        self.assertEqual(r['status'], 'zurueckgenommen')
        nachher = baum(self.root)
        sicherungen = {k for k in nachher if k.startswith('local_config/update/')}
        self.assertEqual({k: v for k, v in nachher.items() if k not in sicherungen}, vorher)
        self.assertFalse((self.root / 'runtime/src/sedra_runtime').exists())

    def test_falsche_pruefsumme_wird_abgelehnt(self):
        (self.cand / 'runtime/src/sedra_runtime/neu.py').write_text('x = 666\n', encoding='utf-8')
        with self.assertRaises(inst.Fehler):
            inst.vorschau(self.cand, self.root)

    def test_manifest_pfad_ausserhalb_wird_abgelehnt(self):
        (self.cand / inst.MANIFEST).write_text('0' * 64 + '  workspace/x.txt\n', encoding='utf-8')
        with self.assertRaises(inst.Fehler):
            inst.vorschau(self.cand, self.root)

    def test_zusatzdatei_im_paket_wird_abgelehnt(self):
        (self.cand / 'runtime/src/sedra_runtime/eingeschmuggelt.py').write_text('z', encoding='utf-8')
        with self.assertRaises(inst.Fehler):
            inst.vorschau(self.cand, self.root)

    def test_nach_umstieg_keine_zweite_vorschau(self):
        _, _, erwartet, lnm = inst.vorschau(self.cand, self.root)
        inst.anwenden(self.cand, self.root, erwartet, lnm)
        with self.assertRaises(inst.Fehler):
            inst.vorschau(self.cand, self.root)

    def lauf(self, *args):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = inst.main(['--root', str(self.root), *args], candidate=self.cand)
        return code, out.getvalue(), err.getvalue()

    def test_ohne_apply_wird_nichts_geschrieben(self):
        vorher = baum(self.root)
        code, out, _ = self.lauf()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['angewendet'], False)
        self.assertEqual(baum(self.root), vorher)

    def test_falsche_bestaetigung_schreibt_nichts(self):
        vorher = baum(self.root)
        code, _, err = self.lauf('--apply', '--confirm', 'falsch')
        self.assertEqual(code, 2)
        self.assertIn('bestaetigen', err)
        self.assertEqual(baum(self.root), vorher)

    def test_genaue_bestaetigung_stellt_um_und_rollback_per_main(self):
        vorher = baum(self.root)
        _, out, _ = self.lauf()
        schluessel = json.loads(out)['bestaetigung']
        code, out, _ = self.lauf('--apply', '--confirm', schluessel)
        self.assertEqual(code, 0)
        self.assertTrue((self.root / 'runtime/src/sedra_runtime/neu.py').is_file())
        code, _, _ = self.lauf('--rollback')
        self.assertEqual(code, 0)
        nachher = {k: v for k, v in baum(self.root).items() if not k.startswith('local_config/update/')}
        self.assertEqual(nachher, vorher)


if __name__ == '__main__':
    unittest.main()
