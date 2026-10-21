"""Die Guard-Regeln der Orchestrierung (Spec 0, D4, K0.23): GR-029 bis GR-038 und ihre Stufen in permission_levels.yaml,
Zeile für Zeile wie die Tabelle D4. Und: der Guard und der Stufen-Lader der Runtime nehmen beide Dateien an."""
import tempfile
import unittest
from pathlib import Path

import yaml

from host_isolation import setUpModule, tearDownModule  # noqa: F401

RUNTIME = Path(__file__).resolve().parents[1]
ARCH = RUNTIME.parent / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'
RULES = ARCH / 'core' / 'guard' / 'guard_rules.yaml'
PERMS = RUNTIME / 'config' / 'permission_levels.yaml'
D4 = [('GR-029', 'set_org', 'CAPTAIN_REQUIRED', 5), ('GR-030', 'assign_task', 'ALLOW', 2), ('GR-031', 'delegate_task', 'ALLOW', 2),
      ('GR-032', 'wake_agent', 'CAPTAIN_REQUIRED', 4), ('GR-033', 'pause_agent', 'ALLOW', 2), ('GR-034', 'resume_agent', 'CAPTAIN_REQUIRED', 5),
      ('GR-035', 'terminate_agent', 'CAPTAIN_REQUIRED', 5), ('GR-036', 'set_budget', 'CAPTAIN_REQUIRED', 5),
      ('GR-037', 'set_routine', 'CAPTAIN_REQUIRED', 5), ('GR-038', 'fire_routine', 'ALLOW', 2)]


class OrchestraGuard(unittest.TestCase):
    def test_the_rules_and_levels_are_table_d4(self):
        rules = yaml.safe_load(RULES.read_text(encoding='utf-8'))['guard_rules']['rules']
        perms = yaml.safe_load(PERMS.read_text(encoding='utf-8'))['permission_levels']['actions']
        self.assertEqual([(r['id'], r['action'], r['decision']) for r in rules[-10:]], [row[:3] for row in D4])
        for rid, action, _, level in D4:
            with self.subTest(rid):
                self.assertEqual(perms[action], {'level': level, 'path_scoped': False})
        self.assertEqual(len({r['id'] for r in rules}), len(rules), 'jede Regel-ID einmal')

    def test_the_guard_decides_by_the_rule_not_by_the_default(self):
        from guppi_runtime.core.audit import AuditLog
        from guppi_runtime.core.guard import Guard
        with tempfile.TemporaryDirectory() as tmp:
            guard = Guard(RULES, AuditLog(Path(tmp) / 'audit.jsonl'), Path(tmp) / 'tokens.json')
            for rid, action, decision, _ in D4:
                with self.subTest(action):
                    out = guard.evaluate(action, target='agent:A-1')
                    self.assertEqual((out['decision'], out['rule_id']), (decision, rid))

    def test_the_runtime_loads_both_files(self):
        from guppi_runtime.runtime import GuppiRuntime
        with tempfile.TemporaryDirectory() as tmp:
            rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
            self.assertIsNone(rt.permission_error)
            levels = rt.permission_status()['actions']
            for _, action, _, level in D4:
                self.assertEqual(levels[action], level, action)


if __name__ == '__main__':
    unittest.main()
