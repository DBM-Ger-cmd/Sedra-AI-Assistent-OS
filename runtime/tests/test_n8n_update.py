import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from guppi_runtime import update_anwenden as ua

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('n8n_offline_update', REPO / 'release/install_n8n_update.py')
installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)


class UpdateCandidate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / 'target'; self.candidate = Path(self.tmp.name) / 'candidate'
        for root in (self.target, self.candidate):
            (root / 'runtime/src/guppi_runtime').mkdir(parents=True)
            (root / 'runtime/src/guppi_runtime/version.py').write_text('old\n')
        old = 'runtime/src/guppi_runtime/version.py'
        self.baseline = {old: installer.canonical_sha(self.target / old)}
        (self.candidate / old).write_text('new\n')
        (self.candidate / 'runtime/src/guppi_runtime/new_app.py').write_text('app\n')
        (self.candidate / 'release').mkdir()
        (self.candidate / ua.MANIFEST).write_text(ua.manifest_erzeugen(self.candidate))
        (self.candidate / 'release/CANDIDATE.json').write_text(json.dumps({'baseline_files': self.baseline, 'baseline_commit': 'test', 'version': '1.22.1'}))

    def test_preview_is_readonly_and_pins_target_state(self):
        plan, key, manifest, meta = installer.preview(self.candidate, self.target)
        self.assertEqual(len(key), 64)
        self.assertIn('runtime/src/guppi_runtime/new_app.py', plan['dateien_geaendert'])
        self.assertEqual((self.target / 'runtime/src/guppi_runtime/version.py').read_text(), 'old\n')
        (self.target / 'runtime/src/guppi_runtime/version.py').write_text('different')
        with self.assertRaisesRegex(ValueError, 'changed_since_baseline'):
            installer.preview(self.candidate, self.target)

    def test_apply_and_rollback_preserve_machine_paths_backups_and_data(self):
        sentinels = {'runtime/config/local_paths.yaml': 'private model paths',
                     'runtime/config/llama.yaml.bak-local': 'local backup',
                     'local_config/n8n.json': 'private connection', 'runtime_data/workflows/note': 'workflow data'}
        for rel, text in sentinels.items():
            p = self.target / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
        plan, key, manifest, meta = installer.preview(self.candidate, self.target)
        ua.anwenden(self.candidate, self.target, manifest, plan['rechte_schluessel'], meta['version'])
        self.assertTrue((self.target / 'runtime/src/guppi_runtime/new_app.py').exists())
        ua.zurueck(self.target)
        self.assertFalse((self.target / 'runtime/src/guppi_runtime/new_app.py').exists())
        self.assertEqual((self.target / 'runtime/src/guppi_runtime/version.py').read_text(), 'old\n')
        for rel, text in sentinels.items():
            self.assertEqual((self.target / rel).read_text(), text)

    def test_local_files_cannot_be_in_release_manifest(self):
        for name in ('runtime/config/local_paths.yaml', 'runtime/config/a.yaml.bak-local'):
            with self.assertRaisesRegex(ua.UpdateFehler, 'lokale_datei'):
                ua.manifest_lesen('0' * 64 + '  ' + name + '\n')

    def test_unrecognized_program_file_prevents_replacing_installation(self):
        (self.target / 'runtime/src/guppi_runtime/private.py').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'file_set_differs'):
            installer.preview(self.candidate, self.target)

    def test_corrupt_payload_cannot_install(self):
        (self.candidate / 'runtime/src/guppi_runtime/new_app.py').write_text('tampered')
        with self.assertRaises(ua.UpdateFehler): installer.preview(self.candidate, self.target)

    def test_explicit_previous_candidate_baseline_can_upgrade(self):
        path = self.target / 'runtime/src/guppi_runtime/version.py';path.write_text('previous candidate\n')
        meta_path = self.candidate / 'release/CANDIDATE.json';meta = json.loads(meta_path.read_text())
        meta['compatible_baselines'] = [{'version': '1.22.1', 'files': {'runtime/src/guppi_runtime/version.py': installer.canonical_sha(path)}}]
        meta_path.write_text(json.dumps(meta))
        plan, key, manifest, checked = installer.preview(self.candidate, self.target)
        self.assertEqual(len(key), 64)
