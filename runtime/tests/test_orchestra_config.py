"""Die Konfiguration der Orchestrierung (Spec 0, D3.4, D3.5, KERN-06).

K0.19: die Paket-Vorgabe `runtime/config/orchestra.yaml` ist gültig und aus; fehlt die Datei oder ist ein Feld ungültig, sagt der
Fehler welches. Der Schalter `orchestra` steht in `local_switches.ALLOWED`."""
import tempfile
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

from guppi_runtime.local_switches import ALLOWED, LocalSwitches
from guppi_runtime.orchestra.config import OrchestraConfig

RUNTIME = Path(__file__).resolve().parents[1]
SHIPPED = RUNTIME / 'config' / 'orchestra.yaml'
D34 = {'orchestra': {'schema': 1, 'enabled': False, 'database': 'orchestra/orchestra.db',
                     'heartbeat': {'tick_s': 5, 'coalesce_s': 2, 'max_runs_per_tick': 1}, 'checkout': {'stall_s': 900},
                     'budget': {'warn_percent': 80, 'stop_percent': 100}, 'routines': {'max_catch_up': 3}, 'org': {'max_depth': 6}}}


def changed(section, key, value):
    doc = yaml.safe_load(SHIPPED.read_text(encoding='utf-8'))
    if key is None:
        doc['orchestra'][section] = value
    else:
        doc['orchestra'][section][key] = value
    return doc


class Shipped(unittest.TestCase):
    def test_the_package_default_is_d34_and_off(self):
        cfg = OrchestraConfig.load(SHIPPED)
        self.assertEqual(cfg.as_dict(), D34)
        self.assertEqual(yaml.safe_load(SHIPPED.read_text(encoding='utf-8')), D34)
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.database_path(Path('rd')), Path('rd') / 'orchestra' / 'orchestra.db')

    def test_a_missing_file_and_each_invalid_field_say_why(self):
        with self.assertRaisesRegex(ValueError, '^orchestra_config_missing$'):
            OrchestraConfig.load(RUNTIME / 'config' / 'gibt_es_nicht.yaml')
        cases = {'heartbeat.tick_s': ('heartbeat', 'tick_s', 0), 'heartbeat.coalesce_s': ('heartbeat', 'coalesce_s', 5),
                 'checkout.stall_s': ('checkout', 'stall_s', 1), 'budget.warn_percent': ('budget', 'warn_percent', 100),
                 'routines.max_catch_up': ('routines', 'max_catch_up', -1), 'org.max_depth': ('org', 'max_depth', 'tief'),
                 'database': ('database', None, '../ausserhalb.db'), 'enabled': ('enabled', None, 'ja'),
                 'schema': ('schema', None, 2), 'unbekannt': ('unbekannt', None, 1)}
        for field, (section, key, value) in cases.items():
            with self.subTest(field):
                with self.assertRaisesRegex(ValueError, '^orchestra_config_invalid:' + field.replace('.', r'\.') + '$'):
                    OrchestraConfig.from_dict(changed(section, key, value))

    def test_the_switch_orchestra_is_accepted(self):
        self.assertEqual(ALLOWED['orchestra'], {'enabled'})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'switches.yaml'
            path.write_text('switches:\n  orchestra: {enabled: true}\n', encoding='utf-8')
            sw = LocalSwitches.load(path)
            self.assertEqual((sw.apply('orchestra', 'enabled', False), sw.problems), (True, []))
            path.write_text('switches:\n  orchestra: {enabled: true, takt: 3}\n', encoding='utf-8')
            self.assertEqual(LocalSwitches.load(path).problems, ['unknown_key:orchestra'])


ARCH = RUNTIME.parent / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
ON = 'switches:\n  orchestra: {enabled: true}\n'


class Runtime(unittest.TestCase):
    """K0.20: `runtime.py` baut die Orchestrierung über `_optional("orchestra", …)` und meldet sie in `boot()` (D3.5, KERN-06)."""

    def runtime(self, switches=None, config=None):
        from unittest import mock
        from guppi_runtime.runtime import GuppiRuntime
        tmp = tempfile.TemporaryDirectory(prefix='orchestra-rt-')
        self.addCleanup(tmp.cleanup)
        project = Path(tmp.name) / 'project'
        if switches is not None:
            (project / 'local_config').mkdir(parents=True)
            (project / 'local_config' / 'switches.yaml').write_text(switches, encoding='utf-8')
        if config is None:
            rt = GuppiRuntime(project, ARCH)
        else:
            with mock.patch.object(GuppiRuntime, 'ORCHESTRA_CONFIG', str(config)):
                rt = GuppiRuntime(project, ARCH)
        if rt.orchestra is not None:
            self.addCleanup(rt.orchestra.close)
        return rt

    def off_events(self, rt):
        lines = rt.audit.path.read_text(encoding='utf-8').splitlines()
        return [__import__('json').loads(l)['payload'] for l in lines if '"ORCHESTRA_OFF"' in l]

    def test_switch_off_is_the_default_and_changes_nothing(self):
        rt = self.runtime()
        self.assertEqual((rt.orchestra, rt.orchestra_error), (None, None))
        boot = rt.boot()
        self.assertEqual(boot['orchestra'], {'enabled': False, 'error': None, 'schema_version': None})
        self.assertEqual(boot['state'], 'READY')
        self.assertFalse((rt.project_root / 'runtime_data' / 'orchestra').exists(), 'aus heißt: keine Datenbank')
        self.assertEqual(self.off_events(rt), [])

    def test_switch_on_with_a_valid_config_opens_the_database(self):
        rt = self.runtime(ON)
        self.assertIsNone(rt.orchestra_error)
        self.assertEqual(rt.boot()['orchestra'], {'enabled': True, 'error': None, 'schema_version': 1})
        self.assertTrue((rt.project_root / 'runtime_data' / 'orchestra' / 'orchestra.db').is_file())
        self.assertIs(rt.orchestra.guard, rt.guard)

    def test_switch_on_and_the_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = self.runtime(ON, Path(tmp) / 'fehlt.yaml')
        boot = rt.boot()
        self.assertEqual((rt.orchestra, boot['orchestra']['error'], boot['state']), (None, 'orchestra_config_missing', 'READY'))
        self.assertEqual(self.off_events(rt), [{'reason': 'orchestra_config_missing'}])

    def test_switch_on_and_an_invalid_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            for field, (section, key, value) in {'heartbeat.tick_s': ('heartbeat', 'tick_s', 0), 'database': ('database', None, '/abs.db'),
                                                 'budget.warn_percent': ('budget', 'warn_percent', 100)}.items():
                with self.subTest(field):
                    path = Path(tmp) / (field + '.yaml')
                    path.write_text(yaml.safe_dump(changed(section, key, value)), encoding='utf-8')
                    rt = self.runtime(ON, path)
                    self.assertEqual(rt.boot()['orchestra'], {'enabled': False, 'error': 'orchestra_config_invalid:' + field, 'schema_version': None})
                    self.assertEqual(rt.boot()['state'], 'READY')

    def test_a_database_newer_than_the_code(self):
        import sqlite3
        from guppi_runtime.runtime import GuppiRuntime
        tmp = tempfile.TemporaryDirectory(prefix='orchestra-new-')
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / 'project' / 'runtime_data' / 'orchestra' / 'orchestra.db'
        db.parent.mkdir(parents=True)
        conn = sqlite3.connect(db)
        conn.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        conn.execute("INSERT INTO meta VALUES ('schema_version', '2')")
        conn.commit(); conn.close()
        (db.parents[2] / 'local_config').mkdir()
        (db.parents[2] / 'local_config' / 'switches.yaml').write_text(ON, encoding='utf-8')
        rt = GuppiRuntime(db.parents[2], ARCH)
        self.assertEqual((rt.orchestra, rt.orchestra_error), (None, 'orchestra_db_error:schema_newer'))

    def test_doctor_prints_the_entry(self):
        import contextlib
        import io
        import json
        from guppi_runtime import cli
        with tempfile.TemporaryDirectory(prefix='orchestra-doctor-') as tmp:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(['--root', str(Path(tmp) / 'project'), '--architecture', str(ARCH), 'doctor']), 0)
        self.assertEqual(json.loads(out.getvalue())['orchestra'], {'enabled': False, 'error': None, 'schema_version': None})


if __name__ == '__main__':
    unittest.main()
