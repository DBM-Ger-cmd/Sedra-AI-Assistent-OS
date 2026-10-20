"""Phase 0.5: one classification source for E1/E2/E3 (finding F-5)."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.selfdev.evolution import EvolutionManager
from guppi_runtime.selfdev.evolution_targets import CORE_TARGETS, MODULE_TARGETS, classify_target
from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.selfdev import self_development
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH = Path(__file__).resolve().parents[2] / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'

# Both pre-0.5 copies. Every entry must keep its old class or become stricter, never looser.
OLD_EVOLUTION_CORE = {'brain', 'mission_state', 'message_bus', 'guard', 'registry', 'lifecycle', 'updater', 'core_contract'}
OLD_EVOLUTION_MODULE = {'new_module', 'module', 'module_logic', 'module_interface', 'privileged_tool_adapter'}


class TargetClassificationTests(unittest.TestCase):
    def test_sets_do_not_overlap(self):
        self.assertEqual(CORE_TARGETS & MODULE_TARGETS, set())

    def test_nothing_became_less_strict(self):
        for name in OLD_EVOLUTION_CORE | CORE_TARGETS:
            self.assertEqual(classify_target(name), 'E3', name)
        for name in OLD_EVOLUTION_MODULE | MODULE_TARGETS:
            self.assertEqual(classify_target(name), 'E2', name)

    def test_formerly_inconsistent_targets_are_core_on_both_paths(self):
        manager = EvolutionManager()
        for name in ('soul_enforcement', 'policy', 'evolution_manager', 'control_core'):
            self.assertEqual(manager.classify(name), 'E3', name)
            self.assertEqual(classify_target(name), 'E3', name)

    def test_formerly_inconsistent_module_targets_are_e2_on_both_paths(self):
        manager = EvolutionManager()
        for name in ('worker', 'adapter', 'connector', 'verification_module', 'context_module', 'tool_adapter'):
            self.assertEqual(manager.classify(name), 'E2', name)

    def test_known_low_risk_and_missing_targets_are_e1(self):
        for value in ('skill', 'topic', 'documentation', ' Skill ', None, '', '  '):
            self.assertEqual(classify_target(value), 'E1', repr(value))

    def test_unknown_and_malformed_targets_need_a_captain_gate(self):
        for value in ('skil', 'brian', 'new_kind_of_thing', 42, ['guard'], {'a': 1}):
            self.assertEqual(classify_target(value), 'E2', repr(value))
        manager = EvolutionManager()
        gap = manager.record_gap('typo target', gap_type='captain_request', target_type='skil')
        self.assertTrue(manager.propose(gap)['development']['requires_captain_gate'])
        gap = manager.record_gap('default target', gap_type='captain_request')
        self.assertFalse(manager.propose(gap)['development']['requires_captain_gate'])

    def test_e1_list_does_not_overlap_protected_sets(self):
        from guppi_runtime.selfdev.evolution_targets import E1_TARGETS
        self.assertEqual(E1_TARGETS & (CORE_TARGETS | MODULE_TARGETS), set())

    def test_case_and_whitespace_cannot_dodge_core_protection(self):
        for value in ('GUARD', ' Guard ', 'Brain\n'):
            self.assertEqual(classify_target(value), 'E3', repr(value))

    def test_both_modules_use_the_same_objects(self):
        self.assertIs(self_development.CORE_TARGETS, CORE_TARGETS)
        self.assertIs(self_development.MODULE_TARGETS, MODULE_TARGETS)

    def test_admission_and_evolution_agree_for_every_listed_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = GuppiRuntime(Path(tmp) / 'project', ARCH)
            manager = EvolutionManager()
            for name in sorted(CORE_TARGETS | MODULE_TARGETS) + ['skill']:
                out = rt.self_development.admission.evaluate(
                    f'cap_for_{name}', evidence=[{'source': 'test'}], target_type=name,
                    checked={'skills': True, 'tools': True, 'modules': True})
                self.assertEqual(out['status'], 'ADMIT', name)
                self.assertEqual(out['classification'], manager.classify(name), name)


    def test_the_gateway_and_the_content_guard_are_core(self):
        # Ticket B6-G-03 / G-07: Selbstentwicklung darf das GateWay und den Inhaltsschutz nie automatisch ändern
        for t in ("gateway", "gateway_wissen", "content_guard", "b6core", "arbeitsplatz"):
            self.assertEqual(classify_target(t), "E3", t)


if __name__ == '__main__':
    unittest.main()
