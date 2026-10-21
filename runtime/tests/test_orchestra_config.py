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


if __name__ == '__main__':
    unittest.main()
