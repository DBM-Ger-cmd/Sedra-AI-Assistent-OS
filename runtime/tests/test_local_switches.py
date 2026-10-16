"""Phase 8e: machine-local switches. Shipped configs stay off; a local file turns features on for one machine."""
import tempfile
import unittest
from pathlib import Path

from guppi_runtime.local_switches import ALLOWED, LocalSwitches
from guppi_runtime.runtime import GuppiRuntime
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

RUNTIME = Path(__file__).resolve().parents[1]
ARCH = RUNTIME.parent / 'architecture' / 'GUPPI_Architecture_v1.20_SELF_DEVELOPMENT'


def write(root, text):
    path = Path(root) / 'local_config' / 'switches.yaml'
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding='utf-8')
    return path


class ParseTest(unittest.TestCase):
    def test_missing_file_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            switches = LocalSwitches.load(Path(tmp) / 'none.yaml')
            self.assertEqual((switches.apply('job_supervisor', 'enabled', False), switches.apply('model_loader', 'evict_idle_models', False)), (False, False))

    def test_values_are_applied_per_key_and_the_rest_keeps_the_shipped_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            switches = LocalSwitches.load(write(tmp, 'switches:\n  model_loader: {enabled: true}\n  token_policy: {enabled: true}\n'))
            self.assertTrue(switches.apply('model_loader', 'enabled', False)); self.assertFalse(switches.apply('model_loader', 'evict_idle_models', False))
            self.assertTrue(switches.apply('token_policy', 'enabled', False)); self.assertFalse(switches.apply('job_supervisor', 'enabled', False))
            self.assertTrue(switches.apply('job_supervisor', 'enabled', True))

    def test_anything_unknown_or_not_boolean_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            for text in ('switches:\n  kev: {enabled: true}\n', 'switches:\n  model_loader: {parallel: 4}\n', 'switches:\n  token_policy: {enabled: "yes"}\n',
                         'switches:\n  token_policy: {enabled: 1}\n', 'other: 1\n', 'switches: [a]\n', 'switches:\n  token_policy: true\n', 'a: [unclosed\n'):
                with self.assertRaises(ValueError, msg=text): LocalSwitches.load(write(tmp, text))

    def test_role_routing_is_not_switched_here(self):
        self.assertNotIn('role_routing', ALLOWED)


class RuntimeTest(unittest.TestCase):
    def runtime(self, text=None):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        project = Path(tmp.name) / 'project'; project.mkdir()
        if text is not None: write(project, text)
        return GuppiRuntime(project, architecture_root=ARCH)

    def test_without_a_file_every_feature_is_off(self):
        rt = self.runtime()
        self.assertFalse(rt.job_supervisor.enabled); self.assertFalse(rt.token_policy.enabled)
        self.assertFalse(rt.model_loader.enabled); self.assertFalse(rt.context_manager.enabled); self.assertFalse(rt.resource_scheduler.enabled)

    def test_the_file_turns_exactly_the_named_features_on_and_the_audit_says_so(self):
        rt = self.runtime('switches:\n  job_supervisor: {enabled: true}\n  token_policy: {enabled: true}\n  model_loader: {evict_idle_models: true}\n')
        self.assertTrue(rt.job_supervisor.enabled); self.assertTrue(rt.token_policy.enabled)
        self.assertFalse(rt.model_loader.enabled); self.assertTrue(rt.model_loader.config.evict_idle_models)       # asked for eviction, not for the loader
        self.assertFalse(rt.context_manager.enabled); self.assertFalse(rt.resource_scheduler.enabled)
        events = [e for e in rt.audit.path.read_text(encoding='utf-8').splitlines() if 'LOCAL_SWITCHES_APPLIED' in e]
        self.assertEqual(len(events), 1)
        self.assertEqual(rt.boot()['local_switches']['values']['token_policy'], {'enabled': True})

    def test_a_broken_file_applies_nothing_and_is_reported(self):
        rt = self.runtime('switches:\n  job_supervisor: {enabled: true}\n  kev: {enabled: true}\n')
        self.assertFalse(rt.job_supervisor.enabled)
        status = rt.boot()
        self.assertIn('unknown_section:kev', status['local_switches']['error'])
        self.assertTrue(any('LOCAL_SWITCHES_REFUSED' in e for e in rt.audit.path.read_text(encoding='utf-8').splitlines()))


if __name__ == '__main__':
    unittest.main()
