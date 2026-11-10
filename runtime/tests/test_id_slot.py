import unittest
from sedra_runtime.models.base import ModelAdapterError
from sedra_runtime.models.openai_local import OpenAICompatibleLocalAdapter
from host_isolation import setUpModule, tearDownModule  # noqa: F401


class Recorder(OpenAICompatibleLocalAdapter):
    def __init__(self):
        super().__init__('fake', 'http://127.0.0.1:1234')
        self.payloads = []

    def _request(self, method, path, payload=None):
        self.payloads.append(payload)
        return {'choices': [{'message': {'content': 'ok'}, 'finish_reason': 'stop'}]}


class IdSlotTest(unittest.TestCase):
    def chat(self, **kw):
        a = Recorder()
        a.chat([{'role': 'user', 'content': 'x'}], model='m', **kw)
        return a.payloads[0]

    def test_slot_is_passed_on(self):
        self.assertEqual(self.chat(id_slot=2)['id_slot'], 2)
        self.assertEqual(self.chat(id_slot=0)['id_slot'], 0)

    def test_without_slot_nothing_is_sent(self):
        self.assertNotIn('id_slot', self.chat())

    def test_invalid_slot_is_refused(self):
        for bad in (-1, 64, '1', True, 1.5):
            with self.assertRaises(ModelAdapterError, msg=repr(bad)):
                self.chat(id_slot=bad)


if __name__ == '__main__':
    unittest.main()
