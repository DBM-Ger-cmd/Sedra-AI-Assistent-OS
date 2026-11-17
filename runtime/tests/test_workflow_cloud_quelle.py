"""KI-Schritt des Eigenablaufs: Quelle lokal (Standard) oder ausdrücklich Cloud; ohne Netz, mit ersetztem Cloud-Aufruf."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sedra_runtime.workflows import execution


class QuelleTest(unittest.TestCase):
    def test_quelle_pruefen(self):
        self.assertIsNone(execution.modell_quelle(None))
        self.assertIsNone(execution.modell_quelle({}))
        ok = execution.modell_quelle({'anbieter': 'nvidia', 'modell': 'nvidia/nemotron-3.5-lightning-30b-a3b', 'extra': 1})
        self.assertEqual(ok, {'anbieter': 'nvidia', 'modell': 'nvidia/nemotron-3.5-lightning-30b-a3b'})
        for schlecht in ('nvidia', {'anbieter': 'openai', 'modell': 'gpt'}, {'anbieter': 'nvidia', 'modell': ''}, {'anbieter': 'nvidia', 'modell': 'a b; rm'}):
            with self.assertRaises(ValueError):
                execution.modell_quelle(schlecht)

    def test_cloud_antwort_mit_codezaun_wird_zu_json(self):
        with tempfile.TemporaryDirectory() as t:
            control = SimpleNamespace(workspace=Path(t) / 'a' / 'b' / 'w', audit=None)
            quelle = {'anbieter': 'nvidia', 'modell': 'nvidia/x-model'}
            gesehen = {}
            def falsch(config, anbieter, modell, nachrichten, **kw):
                gesehen.update(anbieter=anbieter, modell=modell, system=nachrichten[0]['content'])
                return {'status': 'completed', 'reply': 'Hier:\n```json\n{"nummer": "R-1"}\n```'}
            with mock.patch('sedra_runtime.labor.cloud_chat', falsch):
                fragen = execution._modell(control, 'm1', None, quelle)
                wert = fragen([{'role': 'system', 'content': 'Felder'}, {'role': 'user', 'content': 'Text'}], {'type': 'object'})
            self.assertEqual(wert, {'nummer': 'R-1'})
            self.assertEqual((gesehen['anbieter'], gesehen['modell']), ('nvidia', 'nvidia/x-model'))
            self.assertIn('JSON', gesehen['system'])
            with mock.patch('sedra_runtime.labor.cloud_chat', lambda *a, **k: {'status': 'blocked', 'reasons': ['SG_PERSONAL_CLOUD']}):
                with self.assertRaises(ValueError) as e:
                    execution._modell(control, 'm1', None, quelle)([{'role': 'system', 'content': 'F'}], {})
                self.assertIn('SG_PERSONAL_CLOUD', str(e.exception))


if __name__ == '__main__':
    unittest.main()
