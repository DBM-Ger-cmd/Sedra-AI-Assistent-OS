from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.runtime import GuppiRuntime
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

ARCH = sorted((Path(__file__).resolve().parents[2] / 'architecture').glob('GUPPI_Architecture_v*'))[-1]


class CapabilityRouterCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rt = GuppiRuntime(Path(self.tmp.name), ARCH)

    def tearDown(self):
        self.tmp.cleanup()

    def ids(self, route, key):
        return {x['id'] for x in route[key]}

    def test_registry_contains_initial_skill_catalog(self):
        self.assertGreaterEqual(len(self.rt.registry.skills), 8)
        self.assertIn('project-inspection', self.rt.registry.skills)
        self.assertIn('safe-code-change', self.rt.registry.skills)
        self.assertIn('hardware-diagnostics', self.rt.registry.skills)

    def test_project_analysis_selects_filesystem_git_and_skill(self):
        route = self.rt.capability_router.route('Analysiere dieses Projekt und prüfe das Repository')
        self.assertEqual(route['primary_intent'], 'project_analysis')
        self.assertIn('project-inspection', self.ids(route, 'skills'))
        self.assertIn('filesystem', self.ids(route, 'tools'))
        if self.rt.tools.list()['git']['healthy']:
            self.assertIn('git', self.ids(route, 'tools'))

    def test_code_change_selects_skill_and_sandbox(self):
        route = self.rt.capability_router.route('Implementiere das Feature und führe Tests aus')
        self.assertIn('safe-code-change', self.ids(route, 'skills'))
        self.assertIn('sandbox', self.ids(route, 'tools'))
        self.assertEqual(route['model_policy']['profile'], 'coding')

    def test_model_request_selects_runtime_skill_and_tool(self):
        route = self.rt.capability_router.route('Benchmark Qwen als lokales LLM und prüfe den Hardware Model Pass')
        self.assertIn('model-runtime-ops', self.ids(route, 'skills'))
        self.assertIn('model-runtime', self.ids(route, 'tools'))

    def test_hardware_request_selects_hardware_manager(self):
        route = self.rt.capability_router.route('Zeige GPU Temperatur und Hardware Sensoren')
        self.assertIn('hardware-diagnostics', self.ids(route, 'skills'))
        self.assertIn('hardware-manager', self.ids(route, 'tools'))

    def test_high_risk_signal_is_exposed(self):
        route = self.rt.capability_router.route('Löschen und danach in Produktion deployen')
        self.assertEqual(route['risk']['level'], 'high')
        self.assertTrue(route['risk']['guard_required'])

    def test_brain_persists_route_before_planning(self):
        m = self.rt.brain.create_mission('Analysiere dieses Projekt')
        mid = m['identity']['mission_id']
        self.rt.brain.step(mid)  # NEW -> UNDERSTAND
        out = self.rt.brain.step(mid)  # route + UNDERSTAND -> PLAN
        self.assertEqual(out['lifecycle']['phase'], 'PLAN')
        self.assertIn('project-inspection', self.ids(out['routing']['route'], 'skills'))
        planned = self.rt.brain.step(mid)
        self.assertIn('project-inspection', planned['plan']['selected_skills'])
        self.assertIn('filesystem', planned['plan']['selected_tools'])

    def test_control_master_rejects_unselected_tool(self):
        m = self.rt.brain.create_mission('Zeige Hardware Temperatur')
        mid = m['identity']['mission_id']
        self.rt.brain.step(mid); self.rt.brain.step(mid)
        m = self.rt.missions.load(mid)
        out = self.rt.control.execute(m, {'action':'tool_call','tool':'filesystem','operation':'list_dir','args':{'path':'.'}})
        self.assertEqual(out['status'], 'failed')
        self.assertIn('tool_not_selected_by_capability_router', out['error'])

    def test_selected_tool_is_allowed_to_reach_tool_manager(self):
        m = self.rt.brain.create_mission('Zeige Hardware Temperatur')
        mid = m['identity']['mission_id']
        self.rt.brain.step(mid); self.rt.brain.step(mid)
        m = self.rt.missions.load(mid)
        # hardware-manager is selected; state is a read-only operation in the live implementation.
        out = self.rt.control.execute(m, {'action':'tool_call','tool':'hardware-manager','operation':'state','args':{}})
        self.assertNotIn('tool_not_selected_by_capability_router', str(out))

    def test_general_request_still_routes_safely(self):
        route = self.rt.capability_router.route('Hallo Guppi')
        self.assertEqual(route['primary_intent'], 'general')
        self.assertIn('knowledge-retrieval', self.ids(route, 'skills'))
        self.assertTrue(route['enforce_tool_allowlist'])


if __name__ == '__main__':
    unittest.main()
